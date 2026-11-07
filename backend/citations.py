from pydantic import BaseModel

from data_loader import UNKNOWN_PAGE


class Evidence(BaseModel):
    chunk_number: int
    quote: str


def source_citation(source, page):
    if source.lstrip().startswith(("https://", "http://")):
        source = source.strip().rstrip(" ·\t\r\n")
    return {"source": source, "page": str(page) if page is not None else UNKNOWN_PAGE}


def cited_sources(evidence, matches):
    """Verify quote provenance and return source metadata in retrieval order."""
    verified_numbers = set()
    for item in evidence:
        number = item.chunk_number
        if not 1 <= number <= len(matches):
            return None
        if not item.quote.strip() or item.quote not in matches[number - 1]["text"]:
            return None
        verified_numbers.add(number)

    sources = []
    seen = set()
    for n in sorted(verified_numbers):
        m = matches[n - 1]
        citation = source_citation(m["source"], m.get("page"))
        key = (citation["source"], citation["page"])
        if key not in seen:
            sources.append(citation)
            seen.add(key)
    return sources
