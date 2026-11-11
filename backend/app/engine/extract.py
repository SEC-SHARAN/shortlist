"""Safe text extraction from PDF / DOCX / TXT with content (magic-byte) validation."""
from __future__ import annotations
import io, zipfile

MAX_UNCOMPRESSED = 50 * 1024 * 1024  # zip-bomb guard for DOCX


class ExtractionError(Exception):
    pass


def detect_type(data: bytes) -> str:
    """Trust file *content*, not the client-supplied filename/MIME."""
    if data[:5] == b"%PDF-":
        return "pdf"
    if data[:4] == b"PK\x03\x04":
        try:
            with zipfile.ZipFile(io.BytesIO(data)) as z:
                if sum(i.file_size for i in z.infolist()) > MAX_UNCOMPRESSED:
                    raise ExtractionError("Archive expands to an unsafe size")
                if "word/document.xml" in z.namelist():
                    return "docx"
        except zipfile.BadZipFile:
            pass
    raise ExtractionError("Unsupported or corrupt file: only PDF and DOCX are accepted")


def extract_text(data: bytes, kind: str | None = None) -> str:
    kind = kind or detect_type(data)
    try:
        text = _pdf(data) if kind == "pdf" else _docx(data)
    except ExtractionError:
        raise
    except Exception as e:  # library errors -> clean message
        raise ExtractionError(f"Could not read {kind.upper()}: {type(e).__name__}") from e
    text = text.replace("\x00", "").replace("\r", "\n")
    if len(text.strip()) < 40:
        raise ExtractionError("No readable text found (scanned/image-only PDF? OCR is not enabled)")
    return text


def _pdf(data: bytes) -> str:
    import pdfplumber
    pages = []
    with pdfplumber.open(io.BytesIO(data)) as pdf:
        if len(pdf.pages) > 30:
            raise ExtractionError("PDF has more than 30 pages")
        for p in pdf.pages:
            pages.append(p.extract_text() or "")
    return "\n".join(pages)


def _docx(data: bytes) -> str:
    import docx
    d = docx.Document(io.BytesIO(data))
    lines = [p.text for p in d.paragraphs]
    for t in d.tables:
        for row in t.rows:
            cells = []
            for c in row.cells:
                if c.text not in cells:
                    cells.append(c.text)
            lines.append(" | ".join(cells))
    return "\n".join(lines)
