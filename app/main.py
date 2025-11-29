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
from app.vision_extractor import extract_data_with_llm

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

@app.post("/health")
async def health_check_post(request: BillRequest):
    return {"status": "alive", "message": "Ready to process"}

@app.post("/extract-bill-data")
async def extract_bill_data(request: BillRequest):
    logger.info(f"Processing document: {request.document}")
    return await process_extraction(request.document)

from urllib.parse import urlencode

@app.get("/extract-bill-data")
async def extract_bill_data_get(request: Request):
    params = dict(request.query_params)
    document = params.pop("document", None)
    
    if not document:
        return {"is_success": False, "message": "Missing 'document' query parameter."}

    # Reconstruct the full URL if there are extra params (like Azure SAS tokens)
    if params:
        # Check if the document URL already has query params
        separator = "&" if "?" in document else "?"
        # Re-append the stripped parameters, properly encoded
        extra_params = urlencode(params)
        document = f"{document}{separator}{extra_params}"

    logger.info(f"Processing document (GET): {document}")
    return await process_extraction(document)

async def process_extraction(document_url: str):
    try:
        # download and load pages
        path = download_document(document_url)
        pages = load_document_pages(path)
        logger.info(f"Loaded {len(pages)} page(s) from document")

        # --- VISION EXTRACTION (No OCR needed) ---
        # We pass the PIL images directly to Gemini 1.5 Flash
        bill_data, token_usage = await extract_data_with_llm(pages)

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
