from typing import List
from PIL import Image
import pytesseract
from pytesseract import Output

# Set the tesseract binary path if needed
# Replace this with whatever `which tesseract` printed
pytesseract.pytesseract.tesseract_cmd = "/opt/homebrew/bin/tesseract"


def run_ocr_on_page(image: Image.Image) -> List[str]:
    """
    Run OCR on the given image and return a list of text lines
    in reading order.
    Use pytesseract.image_to_data, group by line_num, and join words.
    Skip words with confidence < 40 or empty text.
    """
    data = pytesseract.image_to_data(image, output_type=Output.DICT)
    lines = {}

    n = len(data["text"])
    for i in range(n):
        text = data["text"][i]
        conf_str = data["conf"][i]
        try:
            conf = int(conf_str)
        except ValueError:
            conf = -1

        if conf < 40 or not text.strip():
            continue

        line_no = data["line_num"][i]
        lines.setdefault(line_no, []).append(text)

    line_texts = [" ".join(words) for _, words in sorted(lines.items())]
    return line_texts
