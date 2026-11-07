import re
from typing import Literal

from pydantic import BaseModel, Field

from course_lookup import (
    course_codes, course_lookup_targets, course_records, needs_course_clarification, select_course,
)


MAX_HISTORY_MESSAGES = 8


class ChatTurn(BaseModel):
    role: Literal["user", "assistant"]
    content: str = Field(min_length=1, max_length=1000)


_PREREQUISITE_REFERENCE = re.compile(
    r"(?:هذا|ذلك|هاد|هال)\s*(?:المتطلب|الشرط)|\b(?:this|that) prerequisite\b"
    r"|المتطلب المشترك|\b(?:shared|common) prerequisite\b", re.I,
)
_SHARED_REFERENCE = re.compile(r"المتطلب المشترك|\b(?:shared|common) prerequisite\b", re.I)
_NAME_REFERENCE = re.compile(
    r"(?:شو|ما|ايش)\s*(?:هو\s+)?اسم(?:ه|ها)"
    r"|\b(?:what(?:'s| is) its name|what is it called)\b", re.I,
)
_PREREQUISITE_QUESTION = re.compile(r"متطلب|\bprerequisites?\b", re.I)
_COURSE_FOLLOW_UP = re.compile(
    r"متطلب(?:ه|ها)|(?:شو|ما|ايش)\s*(?:هو\s+)?اسم(?:ه|ها)"
    r"|\bits prerequisites?\b|\bprerequisites? (?:for|of) it\b"
    r"|\bwhat (?:does it require|is it called)\b", re.I,
)
_GENERAL_FOLLOW_UP = re.compile(
    r"^(?:and\b|what about\b|how about\b|when (?:does|can) it\b"
    r"|what (?:is|are) (?:its|their)\b|وماذا عن|ومتى|وكم|طيب\s+)", re.I,
)


def is_course_follow_up(question):
    return (
        needs_course_clarification(question)
        or _COURSE_FOLLOW_UP.search(question) is not None
        or _PREREQUISITE_REFERENCE.search(question) is not None
    )


def _prerequisite_target(text, anchor, codes, chunks, assistant, *, needs_clue):
    requirements = []
    for code, candidates in course_records(chunks, codes).items():
        selected = select_course(anchor, code, candidates)
        if selected is None or not selected[1][1]:
            return []
        requirements.append(selected[1][1])
    if not requirements:
        return []

    # Alternatives written in a single field do not establish a required code.
    verified = [
        {code for item in items if item.strip().isdecimal() for code in course_codes(item)}
        for items in requirements
    ]
    common = set.intersection(*verified)
    if len(common) != 1:
        return []
    clue_matches = set(course_codes(assistant)) - set(codes) == common
    if needs_clue and not clue_matches:
        return []
    if all(len(items) == 1 for items in requirements) or (
        len(codes) > 1 and (_SHARED_REFERENCE.search(text) or clue_matches)
    ):
        return list(common)
    return []


def resolve_course_follow_up(question, history, chunks):
    """Use assistant text to narrow references that are independently verified in the catalog."""
    anchor = ""
    codes = []
    assistant = ""
    previous_asked_prerequisite = False
    turns = [(turn.role, turn.content) for turn in history]
    for role, content in (*turns, ("user", question)):
        if role == "assistant":
            assistant = content
            continue
        text = content.strip()
        explicit = course_lookup_targets(text, chunks)
        prerequisite_reference = _PREREQUISITE_REFERENCE.search(text) is not None
        implicit_shared = (
            not prerequisite_reference and len(codes) > 1
            and previous_asked_prerequisite and _NAME_REFERENCE.search(text) is not None
        )
        if explicit is None or explicit or not is_course_follow_up(text):
            anchor, codes = text, explicit or []
        elif implicit_shared or prerequisite_reference:
            codes = _prerequisite_target(text, anchor, codes, chunks, assistant, needs_clue=implicit_shared)
        elif len(codes) == 1:
            code = codes[0]
            selected = select_course(anchor, code, course_records(chunks, codes)[code])
            if selected is None:
                codes = []
            elif previous_asked_prerequisite and not re.search(
                r"متطلب|المساق|المقرر|\b(?:course|prerequisites?)\b", text, re.I
            ):
                codes = []
        assistant = ""
        previous_asked_prerequisite = (
            not prerequisite_reference
            and _PREREQUISITE_QUESTION.search(text) is not None
        )
    return (codes[0], anchor) if len(codes) == 1 else None


def retrieval_context(question, previous_questions):
    if _GENERAL_FOLLOW_UP.search(question):
        context = next((
            text for text in reversed(previous_questions)
            if not _GENERAL_FOLLOW_UP.search(text) and not is_course_follow_up(text)
        ), "")
        if not context and re.search(r"\b(?:it|its|they|their)\b", question, re.I):
            return None
        return context
    return ""
