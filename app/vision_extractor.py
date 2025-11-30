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

def repair_bill_items(bill_data: BillData) -> BillData:
    """
    Safely repairs missing values using basic math (Rate * Qty = Amount).
    This fixes '0.0' gaps without calling the AI again.
    """
    for page in bill_data.pagewise_line_items:
        for item in page.bill_items:
            # Case 1: Missing Amount, but we have Rate & Qty
            if item.item_amount == 0.0 and item.item_rate > 0 and item.item_quantity > 0:
                item.item_amount = round(item.item_rate * item.item_quantity, 2)
                
            # Case 2: Missing Rate, but we have Amount & Qty
            elif item.item_rate == 0.0 and item.item_amount > 0 and item.item_quantity > 0:
                item.item_rate = round(item.item_amount / item.item_quantity, 2)

            # Case 3: Missing Quantity (Default to 1 if Amount matches Rate)
            elif item.item_quantity == 0.0 and item.item_amount > 0 and item.item_rate > 0:
                if abs(item.item_amount - item.item_rate) < 0.1:
                    item.item_quantity = 1.0
                else:
                    # Calculate implied quantity
                    item.item_quantity = round(item.item_amount / item.item_rate, 2)

    return bill_data
    
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
        # --- THE UNIVERSAL PROMPT (Medical + Generic + Edge Cases) ---
        prompt = """
        You are an expert data extractor for ALL types of invoices and bills (Medical, Retail, Generic, Repair, etc.). 
        Analyze the provided image and extract structured data.

        **CRITICAL INSTRUCTIONS:**
        1. **EXTRACT EVERYTHING:** - Do not limit yourself to "Medical" items. If it looks like a line item with a price, EXTRACT IT.
           - Extract items from bike repairs, grocery receipts, hospital bills, or handwritten notes equally.

        2. **SIDE-BY-SIDE RECEIPTS (The "Merge" Rule):**
           - If the image contains multiple receipts (e.g., left and right), MERGE them into a single list.
           - Do not create separate page entries. All items belong to this single PDF page.

        3. **HANDWRITING & NOISE:** - Look carefully at handwritten text. If a number is overwritten, use your best judgment.
           - If you are >50% sure, extract it. Do not return 0.0 unless it is completely illegible.

        4. **QUANTITY LOGIC (Crucial):**
           - If Quantity is written as 'AxB' (e.g., '3x10' or '10x15'), extract ONLY the first number (A) as the `item_quantity`.
           - Example: "3x10" -> Extract 3.0.

        5. **NO DOUBLE COUNTING:**
           - Do NOT extract rows labeled "Total", "Subtotal", "Brought Forward", or "Carried Over".
           - Only extract the specific line items.

        6. **PAGE CLASSIFICATION:**
           - Default to "Bill Detail" for most pages.
           - Only use "Pharmacy" if you explicitly see drug names.
           - Only use "Final Bill" if it is a summary page with NO individual items.

        **JSON OUTPUT FORMAT:**
        Return ONLY valid JSON matching this structure:
        {
            "pagewise_line_items": [
                {
                    "page_no": "1", 
                    "page_type": "Bill Detail", 
                    "bill_items": [
                        {
                            "item_name": "Item Name", 
                            "item_amount": 100.0, 
                            "item_rate": 100.0, 
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
                    p_no = str(page_num)
                    
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
   # OPTIMIZED THROTTLING
    # 12 pages / 3 concurrent = 4 batches.
    # 4 batches * 2s sleep = 8s total wait (We save 16 seconds vs the old code!)
    semaphore = asyncio.Semaphore(3) 

    async def safe_process(page_num, img):
        async with semaphore:
            # Sleep 2s is enough to stay under 10 RPM because processing takes time too
            await asyncio.sleep(2) 
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

    # 1. Create the Raw Data
    raw_data = BillData(
        pagewise_line_items=final_pagewise,
        total_item_count=final_total
    )

    # 2. Run the "Math Repair" Safety Net
    final_data = repair_bill_items(raw_data)

    return final_data, final_usage
