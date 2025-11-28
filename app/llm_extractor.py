import os
import json
import google.generativeai as genai
from typing import List, Dict, Tuple
from app.schemas import PageLineItems, BillItem, BillData, TokenUsage

# Configure Gemini
# Expects GEMINI_API_KEY to be set in environment variables
genai.configure(api_key=os.environ.get("GEMINI_API_KEY"))

def extract_data_with_llm(all_pages_lines: List[List[str]]) -> Tuple[BillData, TokenUsage]:
    """
    Uses Gemini to extract structured bill data from OCR text.
    Concatenates all pages and sends a single prompt.
    """
    
    # Concatenate text with page markers
    full_text = ""
    for idx, lines in enumerate(all_pages_lines, start=1):
        page_text = "\n".join(lines)
        full_text += f"--- PAGE {idx} ---\n{page_text}\n\n"

    model = genai.GenerativeModel('gemini-flash-latest')

    prompt = """
    You are an expert data extraction AI. Your task is to extract bill line items from the provided OCR text of a medical bill.
    
    The OCR text may contain noise, headers, footers, and layout artifacts. You must identify the actual line items (medicines, services, consultations, etc.) and their details.
    
    **Extraction Rules:**
    1. Extract the following fields for each line item:
       - `item_name`: Name of the service, medicine, or charge. Clean up noise.
       - `item_quantity`: The quantity (default to 1.0 if not specified).
       - `item_rate`: The unit price/rate.
       - `item_amount`: The total amount for this item.
    2. **Strictly exclude** headers, footers, page numbers, dates, times, and invoice metadata (like Bill No, UHID, etc.) from the line items.
    3. **Strictly exclude** Subtotals, Totals, Discounts, and Tax lines from the line items. Only extract the individual chargeable items.
    4. If a value is missing, infer it logically (e.g., if Amount and Qty are present, Rate = Amount/Qty).
    5. Return the output in the following **STRICT JSON format**:

    ```json
    {
      "pagewise_line_items": [
        {
          "page_no": "1",
          "page_type": "Bill Detail",
          "bill_items": [
            {
              "item_name": "Consultation",
              "item_amount": 500.0,
              "item_rate": 500.0,
              "item_quantity": 1.0
            }
          ]
        }
      ],
      "total_item_count": 1,
      "reconciled_amount": 500.0
    }
    ```
    
    - `pagewise_line_items`: A list of objects, one for each page where items were found.
    - `page_no`: The page number as a string ("1", "2", etc.).
    - `page_type`: One of "Bill Detail", "Final Bill", "Pharmacy".
    - `reconciled_amount`: The sum of all `item_amount` values.
    
    **Input OCR Text:**
    """
    
    full_prompt = prompt + "\n" + full_text

    try:
        response = model.generate_content(full_prompt)
        response_text = response.text
        
        # Clean up Markdown code blocks if present
        if "```json" in response_text:
            response_text = response_text.split("```json")[1].split("```")[0]
        elif "```" in response_text:
            response_text = response_text.split("```")[1].split("```")[0]
            
        data = json.loads(response_text)
        
        # Validate and convert to Pydantic models
        pagewise = []
        for p in data.get("pagewise_line_items", []):
            items = []
            for i in p.get("bill_items", []):
                items.append(BillItem(
                    item_name=i["item_name"],
                    item_amount=float(i["item_amount"]),
                    item_rate=float(i["item_rate"]),
                    item_quantity=float(i["item_quantity"])
                ))
            pagewise.append(PageLineItems(
                page_no=str(p["page_no"]),
                page_type=p.get("page_type", "Bill Detail"),
                bill_items=items
            ))
            
        # Extract usage metadata if available
        usage = TokenUsage(total_tokens=0, input_tokens=0, output_tokens=0)
        if response.usage_metadata:
            usage.total_tokens = response.usage_metadata.total_token_count
            usage.input_tokens = response.usage_metadata.prompt_token_count
            usage.output_tokens = response.usage_metadata.candidates_token_count

        return BillData(
            pagewise_line_items=pagewise,
            total_item_count=data.get("total_item_count", 0),
            reconciled_amount=float(data.get("reconciled_amount", 0.0))
        ), usage

    except Exception as e:
        print(f"LLM Extraction failed: {e}", flush=True)
        # Fallback
        return BillData(pagewise_line_items=[], total_item_count=0, reconciled_amount=0.0), TokenUsage(total_tokens=0, input_tokens=0, output_tokens=0)
