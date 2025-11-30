# Bajaj Health Datathon 2025 - Vision-First Bill Extraction API

## Problem Summary
This project implements a high-accuracy solution for extracting line items from complex medical bills, pharmacy receipts, and generic invoices. The API exposes a POST `/extract-bill-data` endpoint that accepts a document URL and returns structured JSON data.

**Key Features:**
* **Vision-First Architecture:** Unlike traditional OCR, this solution uses **Gemini 1.5 Flash Vision** to "see" the document. This allows it to handle handwritten prescriptions, "whitener" corrections, and complex side-by-side receipt layouts that break standard parsers.
* **Production-Grade Reliability:** Implements smart **Async Throttling** (Semaphore logic) to handle rate limits gracefully without crashing.
* **Math Validation:** Includes a post-processing "Math Repair" layer that cross-verifies Rate * Qty = Amount to ensure data integrity.

## Approach & Differentiators

### 1. Vision vs. OCR
We moved beyond legacy OCR (Tesseract). By feeding the raw document images to a Multimodal LLM, we achieve superior accuracy on:
* **Handwriting:** Deciphers scribbled pharmacy notes.
*   **Handwriting:** Deciphers scribbled pharmacy notes.
*   **Structure:** Understands implicit table columns without visible grid lines.
*   **Context:** Distinguishes between a "Subtotal" line and a "Line Item" to prevent double-counting.

## Approach
- **Document Loading**: The API accepts a URL (or local path), downloads the file to a temporary location.
- **PDF and Image Handling**: Uses `pdf2image` to convert PDF pages to images and `Pillow` for image manipulation.
- **Vision Extraction**: Uses **Google Gemini 1.5 Flash (Vision)** to directly analyze bill images. This bypasses traditional OCR (Tesseract) errors and handles handwriting, complex layouts, and "whitener" marks significantly better.
- **Parallel Processing**: Implements a **Map-Reduce** strategy with `asyncio` to process multiple pages concurrently, reducing processing time for large documents (e.g., 12 pages) from >300s to <80s.
- **Total Count**: `total_item_count` is calculated as the sum of all extracted items across all pages.

## API Behaviour
- **Success Response**: Returns HTTP 200 with JSON body containing `is_success: true`, `token_usage` (from LLM), and `data` populated with `pagewise_line_items` and `total_item_count`.
- **Error Response**: Returns HTTP 200 with JSON body containing `is_success: false` and a `message` describing the error.

## How to Run Locally

### Prerequisites
Ensure you have **Poppler** (for `pdf2image`) installed. **Tesseract is NO LONGER REQUIRED.**

### Setup & Running

1.  **Install Dependencies**:
    ```bash
    pip install -r requirements.txt
    ```

2.  **Set API Key**:
    You need a Google Gemini API key.
    ```bash
    export GEMINI_API_KEY="your_api_key_here"
    ```

3.  **Run the Server**:
    ```bash
    uvicorn app.main:app --host 0.0.0.0 --port 8000
    ```

## 🚀 Differentiators & Pre-processing
As requested in the problem statement, we have implemented specific pre-processing techniques to handle complex documents:
1.  **Vision-First Approach**: We switched from OCR to **Gemini 1.5 Flash Vision**. This allows the model to "see" the bill directly, improving accuracy for handwriting and complex layouts while being significantly faster.
2.  **Parallel Map-Reduce**: We process document pages in parallel chunks to ensure even large files (12+ pages) are processed well within the 150s timeout limit.
3.  **Robust Rate Limiting**: Implemented intelligent retry logic with backoff to handle API rate limits gracefully without crashing.
4.  **Strict Schema Validation**: We use Pydantic models to enforce the exact JSON structure required, ensuring 0% schema errors.