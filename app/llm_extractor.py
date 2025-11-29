import os
import logging
import json
import re
import google.generativeai as genai
from typing import List, Tuple
from app.schemas import PageLineItems, BillItem, BillData, TokenUsage, PageTypeEnum

# Configure Gemini
genai.configure(api_key=os.environ.get("GEMINI_API_KEY"))

import asyncio
from fastapi.concurrency import run_in_threadpool

logger = logging.getLogger(__name__)

async def extract_data_with_llm(all_pages_lines: List[List[str]]) -> Tuple[BillData, TokenUsage]:
    """
    Uses Gemini to extract structured bill data.
    """
    # OPTIMIZATION: Process in larger chunks to maintain context (e.g., table headers)
    CHUNK_SIZE = 2 
    chunks = []
    
    for i in range(0, len(all_pages_lines), CHUNK_SIZE):
        chunk_pages = all_pages_lines[i:i + CHUNK_SIZE]
        chunks.append((i + 1, chunk_pages))

    logger.info(f"Splitting {len(all_pages_lines)} pages into {len(chunks)} chunks.")

    def process_chunk(start_idx: int, pages: List[List[str]]) -> Tuple[BillData, TokenUsage]:
        full_text = ""
        for idx, lines in enumerate(pages, start=start_idx):
            page_text = "\n".join(lines)
            full_text += f"--- PAGE {idx} ---\n{page_text}\n\n"

        model = genai.GenerativeModel('gemini-1.5-flash-latest')
        
        # --- THE SNIPER PROMPT ---
        prompt = """
        You are an API backend for a medical bill processor. 
        Your ONLY GOAL is to convert the OCR text into strict JSON.

        **CRITICAL EXTRACTION RULES (STRICT COMPLIANCE REQUIRED):**

        1. **NO DOUBLE COUNTING:** - IGNORE lines that are totals or subtotals (e.g., "Total", "Subtotal", "Net Amount", "Grand Total").
           - IGNORE "Brought Forward" or "Carried Over" amounts.
           - ONLY extract the individual line items that sum up to the total.

        2. **NUMERIC FORMATTING:**
           - OUTPUT RAW NUMBERS ONLY. No symbols ($ , Rs ₹).
           - Example: Return `1200.50`, NOT `Rs. 1,200.50`.
           - If a value is missing or illegible, return `0.0`.

        3. **PAGE CLASSIFICATION (Enum Strictness):**
           - If the page lists medicines/drugs -> "Pharmacy"
           - If the page shows the final Grand Total/Summary -> "Final Bill"
           - Otherwise -> "Bill Detail"

        4. **HANDWRITING/NOISE:**
           - If text is handwritten (common in Pharmacy bills), infer the medicine name and price.
           - If you are unsure of the price, set it to `0.0`. Do not hallucinate.

        **JSON OUTPUT FORMAT:**
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
        
        full_prompt = prompt + "\n\n**INPUT OCR TEXT:**\n" + full_text

        try:
            # Set temperature to 0 for maximum deterministic behavior
            response = model.generate_content(
                full_prompt, 
                generation_config=genai.types.GenerationConfig(temperature=0.0)
            )
            
            # CLEANUP JSON RESPONSE
            response_text = response.text.strip()
            # Remove Markdown code blocks if present
            if "```" in response_text:
                response_text = re.sub(r"```json|```", "", response_text).strip()
                
            data = json.loads(response_text)
            
            pagewise = []
            calculated_total_count = 0

            for p in data.get("pagewise_line_items", []):
                items = []
                for i in p.get("bill_items", []):
                    # Schema validation happens here automatically via Pydantic
                    valid_item = BillItem(
                        item_name=str(i.get("item_name", "Unknown")),
                        item_amount=i.get("item_amount", 0.0),
                        item_rate=i.get("item_rate", 0.0),
                        item_quantity=i.get("item_quantity", 0.0)
                    )
                    items.append(valid_item)
                
                calculated_total_count += len(items)
                
                pagewise.append(PageLineItems(
                    page_no=str(p.get("page_no", str(start_idx))),
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
                total_item_count=calculated_total_count
            ), usage

        except json.JSONDecodeError:
            logger.error(f"LLM produced invalid JSON for chunk {start_idx}")
            return BillData(pagewise_line_items=[], total_item_count=0), TokenUsage(total_tokens=0, input_tokens=0, output_tokens=0)
        except Exception as e:
            logger.error(f"LLM Chunk Extraction failed for chunk {start_idx}: {str(e)}")
            # Return empty data instead of crashing the whole server
            return BillData(pagewise_line_items=[], total_item_count=0), TokenUsage(total_tokens=0, input_tokens=0, output_tokens=0)

    # PARALLEL EXECUTION
    # Using semaphore to prevent hitting Gemini Rate Limits (RPM)
    semaphore = asyncio.Semaphore(5) 

    async def safe_process(start_idx, pages):
        async with semaphore:
            return await run_in_threadpool(process_chunk, start_idx, pages)

    tasks = [safe_process(start_idx, pages) for start_idx, pages in chunks]
    results = await asyncio.gather(*tasks)

    # AGGREGATION
    final_pagewise_items = []
    final_total_count = 0
    final_usage = TokenUsage(total_tokens=0, input_tokens=0, output_tokens=0)

    for bill_data, usage in results:
        final_pagewise_items.extend(bill_data.pagewise_line_items)
        final_total_count += bill_data.total_item_count
        final_usage.total_tokens += usage.total_tokens
        final_usage.input_tokens += usage.input_tokens
        final_usage.output_tokens += usage.output_tokens

    # Sort results by page number to ensure JSON order is correct
    final_pagewise_items.sort(key=lambda x: int(x.page_no) if x.page_no.isdigit() else 0)

    return BillData(
        pagewise_line_items=final_pagewise_items,
        total_item_count=final_total_count
    ), final_usage