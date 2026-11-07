import json
import re
from pathlib import Path

UNKNOWN_PAGE = "Unknown"
_PAGE_NUMBERS = r"\d+(?:\s*[-–—]\s*\d+)?(?:\s*(?:و|،|,)\s*\d+(?:\s*[-–—]\s*\d+)?)*"
_PAGE_REFERENCE = re.compile(rf"(?:ص(?:فحة)?\s*)?{_PAGE_NUMBERS}(?:\s+وما بعدها)?")
_ARTICLE_PAGE = re.compile(rf"(?:^|[،,]\s*)(ص(?:فحة)?\s*{_PAGE_NUMBERS})$")


def _is_valid_page(page):
    if isinstance(page, str) and page.strip():
        reference = page.strip()
        digits = reference[1:] if reference.startswith(("+", "-")) else reference
        return not digits.isdecimal() or (
            not reference.startswith("-") and any(int(digit) for digit in digits)
        )
    return type(page) is int and page > 0


def _is_explicit_reference(reference):
    return (
        isinstance(reference, str)
        and _PAGE_REFERENCE.fullmatch(reference.strip()) is not None
        and all(_is_valid_page(number) for number in re.findall(r"\d+", reference))
    )


def resolve_page(chunk):
    page = chunk.get("page")
    if _is_valid_page(page):
        return str(page)

    metadata = chunk.get("metadata")
    if not isinstance(metadata, dict):
        return UNKNOWN_PAGE
    for field in ("source_page", "page"):
        page = metadata.get(field)
        if _is_valid_page(page):
            return str(page)

    pages = metadata.get("source_pages")
    if isinstance(pages, list) and pages and all(type(page) is int and page > 0 for page in pages):
        return ", ".join(map(str, pages))

    reference = metadata.get("page_reference")
    if _is_explicit_reference(reference):
        return reference

    reference = metadata.get("source_reference")
    if isinstance(reference, str):
        match = _ARTICLE_PAGE.search(reference.strip())
        if match and _is_explicit_reference(match[1]):
            return match[1]
    return UNKNOWN_PAGE


def load_chunks(path):
    file = Path(path)
    if not file.is_absolute():
        file = Path(__file__).parent / file
    chunks = json.loads(file.read_text(encoding="utf-8"))
    if not isinstance(chunks, list) or not chunks:
        raise ValueError("chunks.json must contain a nonempty list")
    ids = set()
    for i, chunk in enumerate(chunks):
        if not isinstance(chunk, dict):
            raise ValueError(f"Chunk {i} must be an object")
        chunk_id = chunk.get("id")
        label = f"Chunk {i}"
        if isinstance(chunk_id, str) and chunk_id.strip():
            label += f" (id={chunk_id!r})"
        for field in ("id", "text", "source", "chunk_index"):
            if field not in chunk:
                raise ValueError(f"{label} missing {field}")
        for field in ("id", "text", "source"):
            value = chunk[field]
            if not isinstance(value, str) or not value.strip():
                raise ValueError(f"{label} has invalid {field}: expected a non-empty string")
        page = chunk.get("page")
        if page is not None and not _is_valid_page(page):
            raise ValueError(f"{label} has invalid page: expected a positive integer or a non-empty page reference")
        chunk_index = chunk["chunk_index"]
        if type(chunk_index) is not int or chunk_index < 0:
            raise ValueError(f"{label} has invalid chunk_index: expected a nonnegative integer")
        if chunk_id in ids:
            raise ValueError(f"{label} has duplicate id")
        ids.add(chunk_id)
    return chunks
