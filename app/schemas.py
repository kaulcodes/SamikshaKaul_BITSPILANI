from typing import List, Optional
from pydantic import BaseModel

class BillItem(BaseModel):
    item_name: str
    item_amount: float
    item_rate: float
    item_quantity: float

class PageLineItems(BaseModel):
    page_no: str
    page_type: str  # "Bill Detail" | "Final Bill" | "Pharmacy"
    bill_items: List[BillItem]

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
