import os
import logging
import json
import re
import google.generativeai as genai
from typing import List, Tuple
from PIL import Image
import io

# Import your strict Pydantic models
from app.schemas import PageLineItems, BillItem, BillData, TokenUsage, PageTypeEnum

# Configure Gemini
# Ensure GEMINI_API_KEY is set in your environment variables
genai.configure(api_key=os.environ.get("GEMINI_API_KEY"))

import asyncio
from fastapi.concurrency import run_in_threadpool

logger = logging.getLogger(__name__)

async def extract_data_with_llm(pages: List[Image.Image]) -> Tuple[BillData, TokenUsage]:
    """
    Uses Gemini 1.5 Flash (Vision) to extract data directly from bill images.
    This bypasses OCR errors and handles handwriting/layouts much better.
    """
    
    # Create chunks. Processing 1 page at a time is safest for Vision accuracy.
    # You can try 2 if you need more speed, but 1 is recommended for complex bills.
    chunks = []
    for i, page_img in enumerate(pages):
        chunks.append((i + 1, page_img))

    logger.info(f"Processing {len(pages)} pages using Vision-based Extraction.")

    def process_page_vision(page_num: int, image: Image.Image) -> Tuple[BillData, TokenUsage]:
        # gemini-1.5-flash is Multimodal (Text + Images) and fast
        model = genai.GenerativeModel('gemini-flash-latest')
        
        # --- THE VISION PROMPT ---
        prompt = """
        You are an expert medical bill data extractor. 
        Analyze the provided image of the document and extract structured data.

        **CRITICAL VISUAL INSTRUCTIONS:**
        1. **Handwriting & Noise:** - Look carefully at handwritten text (common in Pharmacy bills). 
           - If a number is overwritten or unclear, use your best judgment. If illegible, set to 0.0.
           - Ignore "Whitener" marks or scribbles that cross out text.
        
        2. **Table Structure:** - Visually align the columns. Do not mix up 'Rate' and 'Amount'.
           - 'Rate' is usually the unit price. 'Amount' is usually Rate * Qty.

        3. **Page Classification (Strict):**
           - If the page contains a list of medicines/drugs -> "Pharmacy"
           - If the page shows the "Grand Total" or "Net Payable" -> "Final Bill"
           - Otherwise -> "Bill Detail"

        4. **NO DOUBLE COUNTING:**
           - Do NOT extract rows labeled "Total", "Subtotal", "Brought Forward", or "Carried Over".
           - Only extract the specific line items (medicines, services, charges).

        **JSON OUTPUT FORMAT:**
        Return ONLY valid JSON matching this structure:
        {
            "pagewise_line_items": [
                {
                    "page_no": "1", 
                    "page_type": "Bill Detail",
                    "bill_items": [
                        {
                            "item_name": "Consultation Fee", 
                            "item_amount": 500.0, 
                            "item_rate": 500.0, 
                            "item_quantity": 1.0
                        }
                    ]
                }
            ],
            "total_item_count": 1
        }
        """

        # Retry logic for 429 Rate Limits
        max_retries = 2
        base_delay = 2
        
        for attempt in range(max_retries):
            try:
                # SEND IMAGE + PROMPT DIRECTLY TO GEMINI
                response = model.generate_content(
                    [prompt, image],
                    generation_config=genai.types.GenerationConfig(
                        temperature=0.0,  # Zero temperature for deterministic results
                        response_mime_type="application/json" # Forces the model to output valid JSON
                    )
                )
                
                # Parse Response
                response_text = response.text.strip()
                # Remove markdown fencing if present
                if "```" in response_text:
                    response_text = re.sub(r"```json|```", "", response_text).strip()
                
                data = json.loads(response_text)
                
                # --- SANITIZATION & VALIDATION ---
                # Reconstruct into Pydantic Models to fix types (float vs str) automatically
                pagewise = []
                calculated_count = 0
                
                for p in data.get("pagewise_line_items", []):
                    items = []
                    for i in p.get("bill_items", []):
                        # The Pydantic validators in schemas.py will handle stripping '$', ',', etc.
                        valid_item = BillItem(
                            item_name=str(i.get("item_name", "Unknown")),
                            item_amount=i.get("item_amount", 0.0),
                            item_rate=i.get("item_rate", 0.0),
                            item_quantity=i.get("item_quantity", 0.0)
                        )
                        items.append(valid_item)
                    
                    calculated_count += len(items)
                    
                    # Ensure page_no is the one we assigned if missing
                    p_no = str(p.get("page_no", str(page_num)))
                    
                    pagewise.append(PageLineItems(
                        page_no=p_no,
                        page_type=p.get("page_type", "Bill Detail"),
                        bill_items=items
                    ))

                # Token Usage Tracking
                usage = TokenUsage(total_tokens=0, input_tokens=0, output_tokens=0)
                if response.usage_metadata:
                    usage.total_tokens = response.usage_metadata.total_token_count
                    usage.input_tokens = response.usage_metadata.prompt_token_count
                    usage.output_tokens = response.usage_metadata.candidates_token_count
                
                return BillData(
                    pagewise_line_items=pagewise, 
                    total_item_count=calculated_count
                ), usage

            except Exception as e:
                if "429" in str(e) or "quota" in str(e).lower():
                    if attempt < max_retries - 1:
                        delay = base_delay
                        logger.warning(f"Rate limit hit for page {page_num}. Retrying in {delay}s... (Attempt {attempt + 1}/{max_retries})")
                        import time
                        time.sleep(delay)
                        continue
                
                logger.error(f"Vision extraction failed for page {page_num}: {e}")
                # Return empty structure on failure to prevent API crash
                return BillData(pagewise_line_items=[], total_item_count=0), TokenUsage(total_tokens=0, input_tokens=0, output_tokens=0)

    # --- PARALLEL EXECUTION ---
    # Limit concurrency to 5 to avoid hitting Gemini Rate Limits
    semaphore = asyncio.Semaphore(5)

    async def safe_process(page_num, img):
        async with semaphore:
            return await run_in_threadpool(process_page_vision, page_num, img)

    tasks = [safe_process(page_num, img) for page_num, img in chunks]
    results = await asyncio.gather(*tasks)

    # --- AGGREGATION ---
    final_pagewise = []
    final_total = 0
    final_usage = TokenUsage(total_tokens=0, input_tokens=0, output_tokens=0)

    for bill_data, usage in results:
        final_pagewise.extend(bill_data.pagewise_line_items)
        final_total += bill_data.total_item_count
        final_usage.total_tokens += usage.total_tokens
        final_usage.input_tokens += usage.input_tokens
        final_usage.output_tokens += usage.output_tokens

    # Sort pages to keep JSON orderly
    final_pagewise.sort(key=lambda x: int(x.page_no) if x.page_no.isdigit() else 0)

    return BillData(
        pagewise_line_items=final_pagewise,
        total_item_count=final_total
    ), final_usage
