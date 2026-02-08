import PyPDF2
from PIL import Image

try:
    import pytesseract
except Exception:
    pytesseract = None

def extract_text_from_pdf(file):
    file.seek(0)
    reader = PyPDF2.PdfReader(file)
    text = ""

    for page in reader.pages:
        text += page.extract_text() + "\n"

    return text


def extract_text_from_image(file):
    if pytesseract is None:
        raise RuntimeError("pytesseract not installed")

    file.seek(0)
    image = Image.open(file)
    if image.mode not in ("RGB", "L"):
        image = image.convert("RGB")
    try:
        text = pytesseract.image_to_string(image)
    except Exception as exc:
        raise RuntimeError("tesseract-ocr not available") from exc

    return text or ""


def extract_text_from_file(file):
    name = (getattr(file, "name", "") or "").lower()
    content_type = (getattr(file, "content_type", "") or "").lower()

    if name.endswith(".pdf") or content_type == "application/pdf":
        return extract_text_from_pdf(file)

    if name.endswith((".png", ".jpg", ".jpeg", ".tif", ".tiff", ".bmp", ".webp")) or content_type.startswith("image/"):
        return extract_text_from_image(file)

    return ""
