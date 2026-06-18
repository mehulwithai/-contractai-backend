import fitz  # PyMuPDF
from docx import Document
from io import BytesIO


def extract_text(file_bytes: bytes, filename: str) -> str:
    """
    Extract plain text from a PDF or DOCX file.
    Always raises ValueError with a user-friendly message on failure.
    """
    fname = filename.lower()

    if fname.endswith(".pdf"):
        return _extract_pdf(file_bytes)
    elif fname.endswith(".docx"):
        return _extract_docx(file_bytes)
    else:
        raise ValueError(f"Unsupported file type: {filename}. Please upload a PDF or DOCX.")


def _extract_pdf(file_bytes: bytes) -> str:
    if not file_bytes:
        raise ValueError("File is empty. Please upload a valid PDF.")

    try:
        doc = fitz.open(stream=file_bytes, filetype="pdf")
    except Exception:
        raise ValueError("Could not open this file as a PDF. It may be corrupted.")

    pages = []
    try:
        for page in doc:
            text = page.get_text().strip()
            if text:
                pages.append(text)
    finally:
        doc.close()

    if not pages:
        raise ValueError(
            "Could not extract text from this PDF. "
            "It may be a scanned image — please use a text-based PDF."
        )

    return "\n\n".join(pages)


def _extract_docx(file_bytes: bytes) -> str:
    if not file_bytes:
        raise ValueError("File is empty. Please upload a valid DOCX.")

    try:
        doc = Document(BytesIO(file_bytes))
    except Exception:
        raise ValueError("Could not open this file as a DOCX. It may be corrupted.")

    paragraphs = [p.text.strip() for p in doc.paragraphs if p.text.strip()]

    if not paragraphs:
        raise ValueError("Could not extract text from this DOCX file. It may be empty.")

    return "\n\n".join(paragraphs)


def get_word_count(text: str) -> int:
    return len(text.split())


def truncate_for_api(text: str, max_chars: int = 80000) -> str:
    """
    Cap at 80k chars (~20k tokens) to control API costs.
    Most contracts are well under this limit.
    """
    if len(text) <= max_chars:
        return text
    return text[:max_chars] + "\n\n[Contract truncated — first 80,000 characters analysed]"
