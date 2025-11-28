from typing import List
from PIL import Image
import pytesseract

# Set the tesseract binary path if needed
# pytesseract.pytesseract.tesseract_cmd = "/usr/bin/tesseract" # Default for Linux/Render

def run_ocr_on_page(image: Image.Image) -> List[str]:
    """
    Runs OCR on a single PIL Image and returns a list of strings (lines).
    Includes preprocessing to handle noise/whitener (grayscale).
    """
    # Preprocessing: Convert to grayscale to handle colored backgrounds/noise better
    image = image.convert('L')
    
    # Run OCR with page segmentation mode 6 (Assume a single uniform block of text)
    # This is often better for table-like structures than default
    text = pytesseract.image_to_string(image, config='--psm 6')
    
    # Split into lines and clean up
    lines = [line.strip() for line in text.split('\n') if line.strip()]
    return lines
