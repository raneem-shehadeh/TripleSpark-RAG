import re
import unicodedata

from citations import source_citation
from config import NO_ANSWER
from data_loader import resolve_page


_CODE = re.compile(r"(?<!\w)\d{7,8}(?!\w)")
_COURSE_INTENT = re.compile(r"مساق|مقرر|متطلب|\bcourses?\b|\bprerequisites?\b", re.I)
_COMPARISON = re.compile(r"الفرق بين|قارن|مقارنة|\b(?:compare|difference between)\b", re.I)
_NAME_INTENT = re.compile(r"ما (?:اسم|رمز|هو|هي)|شو|\bwhat (?:is|are)\b", re.I)
_AMBIGUOUS_COURSE = re.compile(
    r"(?:هذا|ذلك|ه(?:ال|اد))\s*(?:المساق|المقرر)"
    r"|\b(?:this|that|the aforementioned) course\b"
    r"|\bwhat(?:'s| is) its name\b",
    re.I,
)


def course_codes(question):
    return list(dict.fromkeys(_digits(match) for match in _CODE.findall(question)))


def _digits(code):
    return "".join(str(int(digit)) for digit in code)


def _name_tokens(text):
    text = unicodedata.normalize("NFKC", text.casefold()).translate(str.maketrans("أإآٱى", "ااااي"))
    text = "".join(char for char in text if unicodedata.category(char) != "Mn" and char != "ـ")
    return tuple(
        _digits(word) if word.isdecimal() else word.removeprefix("ال") if len(word) > 3 else word
        for word in re.findall(r"[^\W_]+", text)
    )


def course_codes_by_name(question, chunks):
    """Find whole catalog names. None means the question needs disambiguation."""
    words = _name_tokens(question)
    if not words:
        return []
    names = {}
    for chunk in chunks:
        metadata = chunk.get("metadata")
        if not isinstance(metadata, dict):
            continue
        name, code = metadata.get("course_name"), metadata.get("course_code")
        if isinstance(name, str) and isinstance(code, str) and _CODE.fullmatch(code):
            tokens = _name_tokens(name)
            if tokens and len(tokens) <= len(words):
                names.setdefault(tokens, set()).add(_digits(code))
    if words not in names and not any(
        pattern.search(question) for pattern in (_COURSE_INTENT, _COMPARISON, _NAME_INTENT)
    ):
        return []

    matched = []
    lengths = sorted({len(name) for name in names}, reverse=True)
    position = 0
    while position < len(words):
        for length in lengths:
            candidate = words[position:position + length]
            if len(candidate) != length:
                continue
            codes = names.get(candidate)
            if not codes and candidate[0].startswith("و"):
                first = candidate[0][1:]
                if len(first) > 3:
                    first = first.removeprefix("ال")
                codes = names.get((first, *candidate[1:]))
            if codes:
                matched.append(codes)
                position += length
                break
        else:
            position += 1

    if not matched:
        return []
    codes = []
    for candidates in matched:
        if len(candidates) > 1:
            scoped = {
                code for code, records in course_records(chunks, candidates).items()
                if any(_program_matches(question, chunk) for chunk, _ in records)
            }
            candidates = scoped or candidates
        if len(candidates) != 1:
            return None
        codes.append(next(iter(candidates)))
    return list(dict.fromkeys(codes))


def course_lookup_targets(question, chunks):
    explicit = course_codes(question)
    comparison = _COMPARISON.search(question) is not None
    if explicit and not comparison:
        return explicit
    named = course_codes_by_name(question, chunks)
    if named is None:
        return None
    codes = list(dict.fromkeys([*explicit, *named]))
    return None if comparison and len(codes) == 1 else codes


def needs_course_clarification(question):
    return _AMBIGUOUS_COURSE.search(question) is not None


def course_records(chunks, codes):
    matches = {code: [] for code in codes}
    for chunk in chunks:
        metadata = chunk.get("metadata")
        if not isinstance(metadata, dict):
            continue
        code = metadata.get("course_code")
        if not isinstance(code, str) or not _CODE.fullmatch(code):
            continue
        code = _digits(code)
        if code not in matches:
            continue
        name = metadata.get("course_name")
        prerequisites = metadata.get("prerequisites")
        if not isinstance(name, str) or not name.strip():
            continue
        if not isinstance(prerequisites, list) or any(
            not isinstance(item, str) or not item.strip() for item in prerequisites
        ):
            prerequisites = None
        facts = (name, tuple(prerequisites) if prerequisites else ())
        matches[code].append((chunk, facts))
    return matches


def _program_matches(question, chunk):
    program = chunk["metadata"].get("program")
    return isinstance(program, str) and program.strip() and program.casefold() in question.casefold()


def select_course(question, code, candidates):
    program_matches = [
        (chunk, facts) for chunk, facts in candidates
        if _program_matches(question, chunk)
    ]
    candidates = program_matches or candidates
    if not candidates or len({facts for _, facts in candidates}) != 1:
        return None
    # Prefer the actual course row over a continuation carrying the same metadata.
    return max(candidates, key=lambda item: code in item[0]["text"] and item[1][0] in item[0]["text"])


def exact_course_answer(question, chunks, codes):
    """Return facts from the row that owns each code, or defer to semantic search."""
    matches = course_records(chunks, codes)
    if not any(matches.values()) and not (_COURSE_INTENT.search(question) or _CODE.fullmatch(question)):
        return None

    paragraphs = []
    sources = []
    requirements = []
    for code, candidates in matches.items():
        if not candidates:
            return {"answer": NO_ANSWER, "sources": []}
        selected = select_course(question, code, candidates)
        if selected is None:
            return {
                "answer": "تختلف بيانات هذا الرمز بين السجلات. يرجى تحديد البرنامج أو مراجعة الخطة الدراسية.",
                "sources": [],
            }
        chunk, (name, prerequisites) = selected
        requirements.append(prerequisites)
        requirement = "، ".join(prerequisites) if prerequisites else "غير مذكورة في السجل المسترجع"
        paragraphs.append(f"اسم المساق {code}: {name}\nالمتطلبات السابقة: {requirement}")
        citation = source_citation(chunk["source"], resolve_page(chunk))
        if citation not in sources:
            sources.append(citation)
    if _COMPARISON.search(question) and len(requirements) == 2 and all(requirements):
        if requirements[0] == requirements[1]:
            paragraphs.append("المتطلبات السابقة المذكورة متطابقة للمساقين.")
    return {"answer": "\n\n".join(paragraphs), "sources": sources}
