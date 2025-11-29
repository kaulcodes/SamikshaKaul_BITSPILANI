from typing import List, Optional, Union, Any
from pydantic import BaseModel, Field, field_validator, model_validator
from enum import Enum

# 1. FIX: Define the Strict Enum to match the Organizer's Requirements
class PageTypeEnum(str, Enum):
    BILL_DETAIL = "Bill Detail"
    FINAL_BILL = "Final Bill"
    PHARMACY = "Pharmacy"
    # Fallback for AI inconsistencies, mapped later
    UNKNOWN = "Bill Detail" 

class BillItem(BaseModel):
    item_name: str
    item_amount: float
    item_rate: float
    item_quantity: float

    # 2. FIX: The "Sanitizer" - Prevents the "Empty Array" bug
    @field_validator('item_amount', 'item_rate', 'item_quantity', mode='before')
    @classmethod
    def clean_floats(cls, v: Any) -> float:
        if isinstance(v, (float, int)):
            return float(v)
        if isinstance(v, str):
            # Remove currency symbols, commas, and whitespace
            clean_str = v.replace(',', '').replace('Rs', '').replace('$', '').replace('₹', '').strip()
            # Handle empty/null strings
            if not clean_str or clean_str.lower() in ['nan', 'null', 'n/a', 'none', '']:
                return 0.0
            try:
                return float(clean_str)
            except ValueError:
                return 0.0
        return 0.0

class PageLineItems(BaseModel):
    page_no: str
    page_type: PageTypeEnum
    bill_items: List[BillItem]

    # 3. FIX: Handle Page Type Mismatches
    @field_validator('page_type', mode='before')
    @classmethod
    def validate_page_type(cls, v):
        # Normalize input to title case to match Enum
        if isinstance(v, str):
            if "pharmacy" in v.lower():
                return PageTypeEnum.PHARMACY
            if "final" in v.lower() or "summary" in v.lower():
                return PageTypeEnum.FINAL_BILL
            return PageTypeEnum.BILL_DETAIL
        return v

class BillData(BaseModel):
    pagewise_line_items: List[PageLineItems]
    total_item_count: int

class TokenUsage(BaseModel):
    total_tokens: int
    input_tokens: int
    output_tokens: int

class BillResponseSuccess(BaseModel):
    is_success: bool
    token_usage: TokenUsage
    data: BillData

class BillErrorResponse(BaseModel):
    is_success: bool
    message: str

class BillRequest(BaseModel):
    document: str