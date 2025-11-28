# Bajaj Health Datathon 2025 – Bill Extraction API

## Problem Summary
This project implements a solution for extracting line items from multi-page medical bills provided as PDFs or images. The API exposes a POST `/extract-bill-data` endpoint that accepts a document URL and returns structured JSON data containing line items per page, following the problem statement's schema.

## Approach
- **Document Loading**: The API accepts a URL (or local path), downloads the file to a temporary location.
- **PDF and Image Handling**: Uses `pdf2image` to convert PDF pages to images and `Pillow` for image manipulation.
- **OCR**: Utilizes `pytesseract` (Tesseract OCR) to extract text and layout information from each page.
- **LLM Extraction**: Uses **Google Gemini 1.5 Flash** to intelligently parse the OCR text, identifying line items, filtering out noise, and structuring the data into the required JSON format.
- **Total Count**: `total_item_count` is calculated as the sum of all extracted items across all pages.

## API Behaviour
- **Success Response**: Returns HTTP 200 with JSON body containing `is_success: true`, `token_usage` (from LLM), and `data` populated with `pagewise_line_items` and `total_item_count`.
- **Error Response**: Returns HTTP 200 with JSON body containing `is_success: false` and a `message` describing the error.

## How to Run Locally

### Prerequisites
Ensure you have **Poppler** (for `pdf2image`) and **Tesseract OCR** installed on your system.

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

### Deployment (For Submission)
To expose the local API to the internet for the hackathon submission:

1.  **Start the Server**:
    ```bash
    uvicorn app.main:app --host 0.0.0.0 --port 8000
    ```
2.  **Start ngrok** (in a new terminal):
    ```bash
    ngrok http 8000
    ```
3.  **Copy the Forwarding URL**:
    Copy the `https` URL provided by ngrok (e.g., `https://a1b2-c3d4.ngrok-free.app`).
4.  **Submit**:
    Use this URL as your API endpoint (e.g., `https://a1b2-c3d4.ngrok-free.app/extract-bill-data`).

### Example Usage
```bash
curl -X POST "https://your-ngrok-url.ngrok-free.app/extract-bill-data" \
     -H "Content-Type: application/json" \
     -d '{"document": "https://example.com/sample_bill.pdf"}'
```
