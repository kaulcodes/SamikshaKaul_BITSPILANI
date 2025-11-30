# Bajaj Health Datathon 2025 - Vision-First Bill Extraction API

## 🏆 Problem Summary
This project implements a high-accuracy, production-grade solution for extracting line items from complex medical bills, pharmacy receipts, and generic invoices. The API exposes a POST `/extract-bill-data` endpoint that accepts a document URL and returns strictly structured JSON data.

**The Core Innovation:**
Unlike traditional OCR solutions that struggle with layout shifts, handwritten notes, and "whitener" corrections, this solution utilizes a **Vision-First Architecture** powered by **Gemini 1.5 Flash**. This allows the model to "see" the document contextually, ensuring higher accuracy on edge cases where standard parsers fail.

---

## 🚀 Differentiators & Key Features

### 1. Vision vs. Traditional OCR
We replaced legacy Tesseract OCR with a Multimodal Vision pipeline. This provides distinct advantages:
* **Handwriting Recognition:** Accurately deciphers scribbled pharmacy notes and doctor prescriptions.
* **Structure Awareness:** Understands implicit table columns without visible grid lines.
* **Contextual Intelligence:** Distinguishes between a "Subtotal" line and a "Line Item" to prevent double-counting.
* **Fraud/Noise Handling:** Effectively ignores "whitener" marks and stamps that confuse standard OCR.

### 2. Production-Grade Reliability
* **Smart Async Throttling:** Implements a custom Semaphore logic to process multiple pages concurrently while strictly adhering to API rate limits. The system auto-regulates speed to prevent 429/500 crashes.
* **Math Repair Layer:** Includes a post-processing validation step that mathematically cross-verifies `Rate * Qty = Amount`. If the AI misses a decimal, the math layer silently repairs it.
* **Universal Prompting:** Uses a dynamic prompt strategy that handles both Medical Bills and Generic Invoices (Retail/Repair) with equal precision.

### 3. Strict Schema Enforcement
We use **Pydantic Validators** to enforce the output schema. This prevents "400 Bad Request" errors by automatically sanitizing currency symbols (`$`, `Rs`, `,`) and converting types (String -> Float) before the response is sent.

---

## 🛠️ Technical Architecture

1.  **Document Loading**: Accepts URLs, handles downloading, and converts PDFs to high-res images using `pdf2image` and `Pillow`.
2.  **Parallel Processing**: Uses `asyncio` to process pages in optimized batches (3 pages/batch) to balance speed (<100s for 12 pages) with rate limits.
3.  **Extraction Engine**: Gemini 1.5 Flash Vision analyzes the visual layout to extract line items.
4.  **Edge Case Logic**: Automatically merges "Side-by-Side" receipts into a single list and filters out "Brought Forward" totals.

---

## 💻 How to Run Locally

### Prerequisites
* **Python 3.10+**
* **Poppler**: Required for PDF processing.
    * *Mac:* `brew install poppler`
    * *Linux:* `sudo apt-get install -y poppler-utils`
    * *Windows:* Download and add binary to PATH.

### Installation
1.  **Install Dependencies**:
    ```bash
    pip install -r requirements.txt
    ```

2.  **Set API Key**:
    You need a Google Gemini API key.
    ```bash
    export GEMINI_API_KEY="your_api_key_here"
    ```

3.  **Start the Server**:
    ```bash
    uvicorn app.main:app --host 0.0.0.0 --port 8000
    ```

### Example Usage
You can test the API using `curl` or Postman.

**Request:**
```bash
curl -X POST "http://localhost:8000/extract-bill-data" \
     -H "Content-Type: application/json" \
     -d '{"document": "[https://hackrx.blob.core.windows.net/sample_bill.pdf](https://hackrx.blob.core.windows.net/sample_bill.pdf)"}'