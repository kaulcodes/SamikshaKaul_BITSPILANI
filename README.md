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

## 🚀 Differentiators & Pre-processing
As requested in the problem statement, we have implemented specific pre-processing techniques to handle complex documents:
1.  **Grayscale Conversion**: All input images are converted to grayscale (`L` mode) before OCR. This significantly improves accuracy on documents with colored backgrounds or "whitener" marks by enhancing the contrast of the text.
2.  **LLM-First Approach**: We utilize Google Gemini 1.5 Flash for its superior reasoning capabilities, allowing us to handle "hidden rules" (like excluding totals) that rule-based parsers miss.
3.  **Strict Schema Validation**: We use Pydantic models to enforce the exact JSON structure required, ensuring 0% schema errors.

## 🛠️ Deployment
The API is deployed on **Render** for high availability.
**Base URL**: `https://bajaj-health-api-xxxx.onrender.com` (Replace with your actual URL)

### Endpoints
-   `POST /extract-bill-data`: Main extraction endpoint.
-   `GET /health`: Health check endpoint to verify uptime.

## 🏃‍♂️ How to Run Locally

### Example Usage
```bash
curl -X POST "https://your-ngrok-url.ngrok-free.app/extract-bill-data" \
     -H "Content-Type: application/json" \
     -d '{"document": "https://example.com/sample_bill.pdf"}'
```
