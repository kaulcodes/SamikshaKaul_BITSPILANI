from typing import List
import re
from app.schemas import BillItem, PageLineItems

def is_header_or_meta(line: str) -> bool:
    lower = line.lower()
    # Reduced keywords to avoid false positives on valid items that might contain these words
    keywords = [
        "invoice", "bill no", "bill number", "date:", "time:", "uhid", "ip no",
        "ward", "bed", "age", "sex", "doctor", "consultant", "total",
        "sub total", "subtotal", "grand total", "net amount", "amount in words"
    ]
    if any(k in lower for k in keywords):
        return True
    return False

def extract_pagewise_line_items(all_pages_lines: List[List[str]]) -> List[PageLineItems]:
    pagewise_items = []
    
    for idx, lines in enumerate(all_pages_lines, start=1):
        bill_items = []
        
        for line in lines:
            if not line or not line.strip():
                continue
                
            # Skip header/meta lines
            if is_header_or_meta(line):
                continue
                
            stripped_line = line.strip()
            
            # Skip lines with no digits
            if not any(c.isdigit() for c in stripped_line):
                continue
                
            # Skip very short lines
            if len(stripped_line) < 5:
                continue
                
            # Extract numbers
            num_pattern = r"\d+(?:\.\d+)?"
            
            # Identify date patterns to exclude
            date_pattern = r"\b\d{1,2}[/.-]\d{1,2}[/.-]\d{2,4}\b"
            line_no_dates = re.sub(date_pattern, "", line)
            
            # Extract potential numbers
            raw_numbers = re.findall(num_pattern, line_no_dates)
            numbers = []
            for x in raw_numbers:
                try:
                    val = float(x)
                    # Filter pure years 1900-2100 if they look like integers
                    if 1900 <= val <= 2100 and val.is_integer() and "." not in x:
                         continue
                    numbers.append(val)
                except ValueError:
                    continue
            
            if not numbers:
                continue
                
            # Logic for Quantity, Rate, Amount
            quantity = 1.0
            rate = 0.0
            amount = 0.0
            
            # Heuristics
            if len(numbers) == 1:
                # Only one number -> Amount. Qty=1, Rate=Amount
                amount = numbers[0]
                rate = amount
                quantity = 1.0
            elif len(numbers) >= 2:
                # Take last two as candidates for Rate/Amount or Qty/Amount
                # Usually Amount is last.
                cand_amount = numbers[-1]
                cand_2 = numbers[-2]
                
                # Check if we have a 3rd candidate
                cand_3 = numbers[-3] if len(numbers) >= 3 else None
                
                matched = False
                
                # Case A: 3 numbers available. Try Qty * Rate = Amount
                if cand_3 is not None:
                    # Option 1: Qty=cand_3, Rate=cand_2, Amt=cand_amount
                    if abs(cand_3 * cand_2 - cand_amount) < max(1.0, 0.05 * cand_amount):
                        quantity = cand_3
                        rate = cand_2
                        amount = cand_amount
                        matched = True
                    # Option 2: Rate=cand_3, Qty=cand_2, Amt=cand_amount
                    elif abs(cand_2 * cand_3 - cand_amount) < max(1.0, 0.05 * cand_amount):
                        quantity = cand_2
                        rate = cand_3
                        amount = cand_amount
                        matched = True
                
                if not matched:
                    # Fallback or 2 numbers case
                    # Assume last is Amount.
                    amount = cand_amount
                    
                    # Decide if cand_2 is Rate or Qty
                    # Qty is usually small integer. Rate can be anything.
                    # If cand_2 is small integer (<= 100) and cand_2 != amount, assume Qty?
                    # But often Rate is also present.
                    # If we have 3 numbers and didn't match, maybe the first one is just garbage/ID.
                    
                    if cand_3 is not None:
                         # We have 3 numbers but math didn't check out.
                         # Trust the last one as Amount.
                         # If cand_3 is small integer, take it as Qty.
                         if cand_3 <= 100 and cand_3.is_integer():
                             quantity = cand_3
                             rate = amount / quantity if quantity > 0 else amount
                         else:
                             # Fallback: Qty=1, Rate=Amount
                             quantity = 1.0
                             rate = amount
                    else:
                        # Only 2 numbers: cand_2 and cand_amount
                        # If cand_2 is small integer, treat as Qty?
                        if cand_2 <= 50 and cand_2.is_integer():
                            quantity = cand_2
                            rate = amount / quantity if quantity > 0 else amount
                        else:
                            # Treat cand_2 as Rate, Qty=1?
                            # Or ignore cand_2 (maybe it's a code) and set Qty=1, Rate=Amount?
                            # Let's assume cand_2 is Rate if it matches Amount (Qty=1)
                            if abs(cand_2 - cand_amount) < 0.1:
                                quantity = 1.0
                                rate = cand_2
                            else:
                                # Ambiguous. Default to Qty=1, Rate=Amount
                                quantity = 1.0
                                rate = amount

            # Sanity checks
            if not (0.0 < quantity <= 1000.0): # Relaxed upper bound slightly
                continue
                
            if amount <= 0:
                continue
                
            # Extract Item Name
            # Use original line to find name part
            first_num_match = re.search(num_pattern, line)
            if first_num_match:
                name = line[:first_num_match.start()]
            else:
                name = line
            
            name = name.strip(" :-\t|")
            
            # Clean up name
            # Remove leading digits/serial numbers
            name = re.sub(r"^\d+\s*[\.\-\)]?\s*", "", name)
            # Remove common noise
            name = name.replace("$G", "").replace("RR", "")
            name = name.strip()
            
            if not name or len(name) < 3:
                continue
                
            bill_items.append(BillItem(
                item_name=name,
                item_quantity=quantity,
                item_rate=rate,
                item_amount=amount
            ))
            
        pagewise_items.append(PageLineItems(
            page_no=str(idx),
            page_type="Bill Detail",
            bill_items=bill_items
        ))
        
    return pagewise_items