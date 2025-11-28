from typing import List, Dict
import re

IGNORE_KEYWORDS = [
    "total",
    "grand total",
    "sub total",
    "subtotal",
    "bill summary",
    "summary",
    "category total",
]


def to_float(num_str: str) -> float:
    return float(num_str.replace(",", ""))


def parse_line_items(lines: List[str]) -> List[Dict]:
    """
    Given OCR text lines for a page, return a list of dicts:
    {
      "item_name": str,
      "item_amount": float,
      "item_rate": float,
      "item_quantity": float
    }
    Very simple heuristic:
      - skip header / total lines using IGNORE_KEYWORDS
      - find numeric tokens in the line
      - if less than 2 numbers, skip
      - last number -> amount
      - second last -> rate
      - third last if exists -> quantity, else 1.0
      - item_name is the text before the quantity token, trimmed
    """
    results: List[Dict] = []

    for raw in lines:
        if not raw or not raw.strip():
            continue

        lower = raw.lower()
        if any(k in lower for k in IGNORE_KEYWORDS):
            continue

        # find numbers including commas and decimals
        num_matches = list(re.finditer(r"\d[\d,]*(?:\.\d+)?", raw))
        if len(num_matches) < 2:
            continue

        # take last, second last, optional third last
        last = num_matches[-1]
        amount_str = last.group()

        rate_str = num_matches[-2].group()

        if len(num_matches) >= 3:
            qty_match = num_matches[-3]
            qty_str = qty_match.group()
            name_end_idx = qty_match.start()
        else:
            qty_str = "1"
            name_end_idx = num_matches[-2].start()

        try:
            amount = to_float(amount_str)
            rate = to_float(rate_str)
            quantity = to_float(qty_str)
        except ValueError:
            continue

        item_name = raw[:name_end_idx].strip(" -|:,")
        if len(item_name) < 2:
            continue

        # basic sanity check
        if amount <= 0:
            continue

        results.append(
            {
                "item_name": item_name,
                "item_amount": float(amount),
                "item_rate": float(rate),
                "item_quantity": float(quantity),
            }
        )

    return results
