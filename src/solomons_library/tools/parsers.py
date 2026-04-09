"""File content parsers — extract plain text from various file formats."""

from __future__ import annotations

import csv
import io
import json
from pathlib import Path

from loguru import logger

# Mapping of MIME type → parser function name
SUPPORTED_MIME_TYPES: dict[str, str] = {
    "text/plain": "_parse_text",
    "text/markdown": "_parse_text",
    "text/csv": "_parse_csv",
    "application/pdf": "_parse_pdf",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document": "_parse_docx",
    "text/html": "_parse_html",
    "application/json": "_parse_json",
    "application/x-yaml": "_parse_yaml",
    "text/yaml": "_parse_yaml",
}

# File extension → MIME type for detection fallback
EXTENSION_TO_MIME: dict[str, str] = {
    ".txt": "text/plain",
    ".md": "text/markdown",
    ".csv": "text/csv",
    ".pdf": "application/pdf",
    ".docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    ".html": "text/html",
    ".htm": "text/html",
    ".json": "application/json",
    ".yaml": "application/x-yaml",
    ".yml": "application/x-yaml",
}


def detect_mime_type(filename: str) -> str:
    """Detect MIME type from file extension."""
    ext = Path(filename).suffix.lower()
    return EXTENSION_TO_MIME.get(ext, "application/octet-stream")


def parse_file(file_path: str, mime_type: str) -> str:
    """Extract plain text from a file based on its MIME type.

    Args:
        file_path: Absolute path to the file on disk.
        mime_type: MIME type of the file.

    Returns:
        Extracted text content.

    Raises:
        ValueError: If MIME type is not supported.
    """
    parser_name = SUPPORTED_MIME_TYPES.get(mime_type)
    if not parser_name:
        raise ValueError(f"Unsupported file type: {mime_type}")

    parser_fn = globals()[parser_name]
    logger.debug(f"Parsing {file_path} with {parser_name} (mime={mime_type})")
    return parser_fn(file_path)


def _parse_text(file_path: str) -> str:
    """Parse plain text / markdown files."""
    return Path(file_path).read_text(encoding="utf-8")


def _parse_csv(file_path: str) -> str:
    """Parse CSV into a readable text representation."""
    text = Path(file_path).read_text(encoding="utf-8")
    reader = csv.reader(io.StringIO(text))
    rows = list(reader)
    if not rows:
        return ""
    # Format: header row as context, then each data row
    header = rows[0] if rows else []
    lines = []
    for row in rows[1:]:
        pairs = [f"{h}: {v}" for h, v in zip(header, row) if v.strip()]
        lines.append("; ".join(pairs))
    return f"Headers: {', '.join(header)}\n\n" + "\n".join(lines)


def _parse_pdf(file_path: str) -> str:
    """Parse PDF using pymupdf."""
    import pymupdf

    doc = pymupdf.open(file_path)
    pages = []
    for page in doc:
        pages.append(page.get_text())
    doc.close()
    return "\n\n".join(pages)


def _parse_docx(file_path: str) -> str:
    """Parse DOCX using python-docx."""
    from docx import Document

    doc = Document(file_path)
    return "\n\n".join(para.text for para in doc.paragraphs if para.text.strip())


def _parse_html(file_path: str) -> str:
    """Parse HTML using BeautifulSoup, extracting visible text."""
    from bs4 import BeautifulSoup

    html = Path(file_path).read_text(encoding="utf-8")
    soup = BeautifulSoup(html, "html.parser")
    # Remove script and style elements
    for tag in soup(["script", "style", "nav", "footer", "header"]):
        tag.decompose()
    return soup.get_text(separator="\n", strip=True)


def _parse_json(file_path: str) -> str:
    """Parse JSON into readable text representation."""
    data = json.loads(Path(file_path).read_text(encoding="utf-8"))
    return json.dumps(data, indent=2, ensure_ascii=False)


def _parse_yaml(file_path: str) -> str:
    """Parse YAML into readable text representation.

    Uses json.dumps for output since PyYAML may not be installed —
    the stdlib yaml module isn't available, so we parse manually
    or fall back to reading as plain text.
    """
    # YAML is a superset of JSON for simple cases; for complex YAML
    # we just read as plain text which is still perfectly embeddable
    text = Path(file_path).read_text(encoding="utf-8")
    try:
        import yaml

        data = yaml.safe_load(text)
        return json.dumps(data, indent=2, ensure_ascii=False, default=str)
    except ImportError:
        return text
