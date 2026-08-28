from __future__ import annotations

from io import BytesIO
from pathlib import Path

from docx import Document
from pypdf import PdfReader


class CVParseError(ValueError):
    """Raised when a CV cannot be converted to useful text."""


def extract_cv_text(filename: str, content: bytes) -> str:
    """Extract text from a PDF, DOCX, or TXT CV without saving it to disk."""
    suffix = Path(filename).suffix.lower()

    try:
        if suffix == ".pdf":
            reader = PdfReader(BytesIO(content))
            text = "\n".join(page.extract_text() or "" for page in reader.pages)
        elif suffix == ".docx":
            document = Document(BytesIO(content))
            paragraphs = [paragraph.text for paragraph in document.paragraphs]
            table_cells = [
                cell.text
                for table in document.tables
                for row in table.rows
                for cell in row.cells
            ]
            text = "\n".join(paragraphs + table_cells)
        elif suffix == ".txt":
            text = content.decode("utf-8", errors="replace")
        else:
            raise CVParseError("Use a PDF, DOCX, or TXT file.")
    except CVParseError:
        raise
    except Exception as exc:
        raise CVParseError(f"The CV could not be read: {exc}") from exc

    text = "\n".join(line.strip() for line in text.splitlines() if line.strip())
    if len(text) < 100:
        raise CVParseError(
            "Very little text was extracted. The PDF may be scanned; OCR is not "
            "included in this first version. Try a text-based PDF or DOCX."
        )
    return text
