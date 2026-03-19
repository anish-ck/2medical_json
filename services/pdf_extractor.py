"""
PDF extraction service using pdfplumber.
Extracts text and tables from PDF files.
"""

from dataclasses import dataclass
from io import BytesIO

import pdfplumber


@dataclass
class PDFContent:
    """Container for extracted PDF content."""
    text: str
    tables: list[list[list[str]]]
    page_count: int


def extract_pdf_content(file_bytes: bytes) -> PDFContent:
    """
    Extract text and tables from a PDF file.

    Args:
        file_bytes: Raw bytes of the PDF file

    Returns:
        PDFContent object containing extracted text and tables

    Raises:
        ValueError: If PDF cannot be read or is empty
    """
    all_text = []
    all_tables = []

    try:
        with pdfplumber.open(BytesIO(file_bytes)) as pdf:
            page_count = len(pdf.pages)

            if page_count == 0:
                raise ValueError("PDF file contains no pages")

            for page in pdf.pages:
                page_text = _extract_page_text(page)
                if page_text:
                    all_text.append(page_text)

                page_tables = page.extract_tables()
                if page_tables:
                    for table in page_tables:
                        cleaned_table = _clean_table(table)
                        if cleaned_table:
                            all_tables.append(cleaned_table)

    except Exception as e:
        if "PDF" in str(e) or "password" in str(e).lower():
            raise ValueError(f"Cannot read PDF file: {e}")
        raise

    combined_text = "\n".join(all_text)

    return PDFContent(text=combined_text, tables=all_tables, page_count=page_count)


def _extract_page_text(page) -> str:
    """Extract text from a page using progressively more tolerant strategies."""
    page_text = page.extract_text()
    if page_text and page_text.strip():
        return page_text

    # Some reports have complex layouts where the default extractor returns None.
    page_text = page.extract_text(layout=True)
    if page_text and page_text.strip():
        return page_text

    words = page.extract_words()
    if words:
        return " ".join(word.get("text", "") for word in words if word.get("text"))

    return ""


def _clean_table(table: list[list]) -> list[list[str]]:
    """Clean a table by removing empty rows and normalizing cell values."""
    if not table:
        return []

    cleaned = []
    for row in table:
        if not row:
            continue

        cleaned_row = []
        for cell in row:
            if cell is None:
                cleaned_row.append("")
            else:
                cleaned_row.append(str(cell).strip())

        if any(cell for cell in cleaned_row):
            cleaned.append(cleaned_row)

    return cleaned
