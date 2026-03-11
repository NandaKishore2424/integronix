"""
pdf_service.py — Extract raw text from uploaded PDF files.
Uses pdfplumber (primary) with pytesseract OCR as fallback for scanned docs.
"""
import io
import pdfplumber


def extract_text_from_pdf(file_bytes: bytes) -> tuple[str, bool]:
    """
    Extract text from PDF bytes.
    Returns (text, ocr_used):
      - ocr_used=False when pdfplumber succeeds on a digital PDF
      - ocr_used=True  when Tesseract OCR fallback was needed (scanned PDF)
    Raises ValueError if no text could be extracted at all.
    """
    text_pages = []

    with pdfplumber.open(io.BytesIO(file_bytes)) as pdf:
        for page in pdf.pages:
            page_text = page.extract_text()
            if page_text:
                text_pages.append(page_text.strip())

    extracted = "\n\n".join(text_pages).strip()

    # If pdfplumber got nothing, it's likely a scanned PDF — try OCR
    if not extracted:
        extracted = _ocr_fallback(file_bytes)
        if not extracted:
            raise ValueError(
                "Could not extract any text from the PDF. "
                "File may be corrupted or image-only without readable text."
            )
        return extracted, True   # OCR was used

    return extracted, False      # Digital PDF — no OCR needed


def _ocr_fallback(file_bytes: bytes) -> str:
    """
    OCR fallback using pytesseract for scanned PDFs.
    Requires: tesseract-ocr + poppler installed on the system.
    """
    try:
        import pytesseract
        from PIL import Image
        import pdf2image  # type: ignore

        images = pdf2image.convert_from_bytes(file_bytes, dpi=200)
        pages = [pytesseract.image_to_string(img) for img in images]
        return "\n\n".join(pages).strip()
    except ImportError:
        return ""
    except Exception:
        return ""
