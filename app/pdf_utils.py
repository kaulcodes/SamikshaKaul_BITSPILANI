from typing import List
from PIL import Image
from pdf2image import convert_from_path
import os

def load_document_pages(path: str) -> List[Image.Image]:
    """
    If the file is a PDF, convert each page to an image at 300 dpi using pdf2image.
    If it is an image (png, jpg, jpeg), open it with PIL and return a single element list.
    """
    if path.lower().endswith(".pdf"):
        return convert_from_path(path, dpi=300)
    else:
        # For other types, assume it's an image that PIL can open
        return [Image.open(path)]
