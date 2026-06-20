"""
MediScan AI — PDF Extractor
Uses PyMuPDF (fitz) to extract text from digital PDF lab reports.
Supports any Unicode text (handles international PDFs).
Scanned image PDFs are not supported (out of scope for v1).
"""

import fitz  # PyMuPDF


def extract_text_from_pdf(pdf_bytes: bytes) -> str:
    """
    Extracts all text from a PDF file given its raw bytes.
    Returns clean, concatenated text string.
    
    Args:
        pdf_bytes: Raw bytes of the uploaded PDF file
        
    Returns:
        Extracted text as a single string, or error message if extraction fails
    """
    try:
        # Open PDF from bytes (no temp file needed)
        doc = fitz.open(stream=pdf_bytes, filetype="pdf")

        extracted_pages = []

        for page_num in range(len(doc)):
            page = doc[page_num]

            # Extract text with layout preservation
            text = page.get_text("text")

            if text.strip():
                extracted_pages.append(f"--- Page {page_num + 1} ---\n{text.strip()}")

        doc.close()

        if not extracted_pages:
            return ""

        full_text = "\n\n".join(extracted_pages)
        return full_text

    except Exception as e:
        raise ValueError(f"PDF extraction failed: {str(e)}. "
                         "Make sure the PDF is a digital (not scanned/image) PDF.")


def is_pdf_readable(pdf_bytes: bytes) -> bool:
    """
    Quick check: can we extract meaningful text from this PDF?
    Returns False for scanned/image-only PDFs.
    """
    try:
        doc = fitz.open(stream=pdf_bytes, filetype="pdf")
        total_text = ""
        for page in doc:
            total_text += page.get_text("text")
        doc.close()
        # If less than 50 characters total, it's likely a scanned PDF
        return len(total_text.strip()) > 50
    except Exception:
        return False
