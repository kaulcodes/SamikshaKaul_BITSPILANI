import logging
from app.downloader import download_document
from app.pdf_utils import load_document_pages
from app.ocr_engine import run_ocr_on_page

# Setup basic logging
logging.basicConfig(level=logging.INFO)

def analyze_pdf(source):
    if source.startswith("http"):
        print(f"Downloading: {source}")
        path = download_document(source)
    else:
        print(f"Using local file: {source}")
        path = source

    try:
        print(f"Processing: {path}")
        pages = load_document_pages(path)
        print(f"Loaded {len(pages)} pages.")
        
        for i, page in enumerate(pages):
            print(f"\n--- Page {i+1} Raw OCR Content ---")
            text = run_ocr_on_page(page)
            print(text)
            print("-----------------------------------")
            
    except Exception as e:
        print(f"Error: {e}")

import glob
import os

if __name__ == "__main__":
    # Local training samples directory
    directory = "/Users/samikshakaul/.gemini/antigravity/scratch/bajaj_health_api/training_data/TRAINING_SAMPLES"
    pdf_files = glob.glob(os.path.join(directory, "*.pdf"))
    
    print(f"Found {len(pdf_files)} PDF files.")
    for pdf_path in pdf_files:
        print(f"\nProcessing file: {os.path.basename(pdf_path)}")
        analyze_pdf(pdf_path)
