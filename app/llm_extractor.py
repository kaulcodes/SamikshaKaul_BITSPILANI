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
    You are an expert data extractor for medical bills. Your job is to extract **every single valid medical line item** from the provided OCR text.
    
    **Scope of Extraction:**
    - Extract ALL charges including: Medicines, Consultation Fees, Investigation Charges (Lab tests, X-Rays, Scans), Bed/Room Charges, Nursing Charges, Procedure Charges, Equipment Charges, etc.
    - Do NOT stop at medicines. If it is a charge for a service or item, extract it.

    **Strict Rules for Extraction:**
    1. **Exact Values**: Extract `item_name`, `item_rate`, `item_quantity`, and `item_amount` EXACTLY as they appear in the text. Do NOT round off.
    2. **Missing Values**: 
       - If `item_rate` is NOT explicitly present, set it to `0.0`. Do NOT calculate it.
       - If `item_quantity` is NOT explicitly present, set it to `0.0`. Do NOT calculate it.
       - `item_amount` MUST be present.
    3. **No Double Counting**: 
       - Strictly EXCLUDE "Subtotal", "Total", "Grand Total", "Net Amount", "Category Total", "Daily Total" lines.
       - Only extract the individual line items that make up these totals.
       - Example: If there are 4 days of Bed Charges and a "Total Bed Charges" line, extract the 4 days and IGNORE the total line.
    4. **Exclusions**: Do NOT extract:
       - Header/Footer info (Hospital name, address, GSTIN).
       - Patient details (Name, Age, IPD No).
       - Tax lines (CGST, SGST) unless they are listed as specific line items (rare).
       - Discount lines.
    
    **Page Type Classification:**
    - `Bill Detail`: Contains detailed daily breakdown of charges (Bed charges, Nursing, etc.).
    - `Pharmacy`: Contains list of medicines/consumables.
    - `Final Bill`: The summary page (often has "Final Bill" or "Summary" in header).
    
    **Output Format:**
    Return a JSON object with this EXACT structure:
    {
        "pagewise_line_items": [
            {
                "page_no": "1",
                "page_type": "Bill Detail", 
                "bill_items": [
                    {"item_name": "...", "item_amount": 100.00, "item_rate": 0.0, "item_quantity": 0.0},
                    ...
                ]
            }
        ],
        "total_item_count": 10
    }
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
            total_item_count=data.get("total_item_count", 0)
        ), usage

    except Exception as e:
        print(f"LLM Extraction failed: {e}", flush=True)
        # Fallback
        return BillData(pagewise_line_items=[], total_item_count=0), TokenUsage(total_tokens=0, input_tokens=0, output_tokens=0)
