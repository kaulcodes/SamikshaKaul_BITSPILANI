import logging
import time
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from requests import HTTPError

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

# Setup Logger
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI()

@app.middleware("http")
async def log_requests(request: Request, call_next):
    start_time = time.time()
    body = await request.body()
    logger.info(f"Incoming Request: {request.method} {request.url}")
    if body:
        logger.info(f"Request Body: {body.decode()}")
    
    try:
        response = await call_next(request)
    except Exception as exc:
        logger.error(f"Request failed: {exc}")
        return JSONResponse(content={"is_success": False, "message": str(exc)}, status_code=500)

    process_time = time.time() - start_time
    logger.info(f"Response Status: {response.status_code} | Time: {process_time:.2f}s")
    return response

@app.get("/health")
def health_check():
    return {"status": "ok", "message": "Service is healthy"}

@app.post("/extract-bill-data")
async def extract_bill_data(request: BillRequest):
    logger.info(f"Processing document: {request.document}")

    try:
        # download and load pages
        path = download_document(request.document)
        pages = load_document_pages(path)
        logger.info(f"Loaded {len(pages)} page(s) from document")

        all_pages_lines = []
        for idx, img in enumerate(pages, start=1):
            lines = run_ocr_on_page(img)
            all_pages_lines.append(lines)
            if idx == 1:
                logger.info(f"First page sample: {lines[:3]}")

        bill_data, token_usage = extract_data_with_llm(all_pages_lines)

        response = BillResponseSuccess(
            is_success=True,
            token_usage=token_usage,
            data=bill_data,
        )
        logger.info("Extraction successful")
        return response

    except HTTPError as e:
        logger.error(f"Download failed: {e}")
        return {
            "is_success": False,
            "message": "Failed to process document. Could not download file.",
        }
    except Exception as e:
        logger.error(f"Unexpected error: {e}")
        return {
            "is_success": False,
            "message": "Failed to process document. Internal server error occurred",
        }
