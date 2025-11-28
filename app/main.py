from requests import HTTPError
from fastapi import FastAPI

from app.schemas import (
    BillRequest,
    BillResponseSuccess,
    BillData,
    PageLineItems,
    BillItem,
    TokenUsage,
)
from app.downloader import download_document
from app.pdf_utils import load_document_pages
from app.ocr_engine import run_ocr_on_page
from app.llm_extractor import extract_data_with_llm

app = FastAPI()


@app.post("/extract-bill-data")
async def extract_bill_data(request: BillRequest):
    print("HIT /extract-bill-data with document:", request.document, flush=True)

    try:
        # download and load pages
        path = download_document(request.document)
        pages = load_document_pages(path)
        print(f"Loaded {len(pages)} page(s) from document", flush=True)

        all_pages_lines = []
        for idx, img in enumerate(pages, start=1):
            lines = run_ocr_on_page(img)
            all_pages_lines.append(lines)
            # for debugging, print the first few lines of the first page
            if idx == 1:
                print("First page, first 10 OCR lines:", flush=True)
                for l in lines[:10]:
                    print(l, flush=True)

        bill_data, token_usage = extract_data_with_llm(all_pages_lines)

        response = BillResponseSuccess(
            is_success=True,
            token_usage=token_usage,
            data=bill_data,
        )
        return response

    except HTTPError as e:
        print("Download failed:", e, flush=True)
        return {
            "is_success": False,
            "message": "Failed to process document. Could not download file.",
        }
    except Exception as e:
        print("Unexpected error:", e, flush=True)
        return {
            "is_success": False,
            "message": "Failed to process document. Internal server error occurred",
        }
