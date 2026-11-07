import logging
import os
from threading import Lock
from time import sleep
import httpx
from google import genai
from google.genai.errors import APIError
from pydantic import BaseModel, ValidationError
from config import DATA_PATH, GEMINI_MODEL, NO_ANSWER
from data_loader import load_chunks
from retriever import retrieve
from prompts import build_prompt
from citations import Evidence, cited_sources
from course_lookup import course_codes, course_lookup_targets, exact_course_answer
from conversation import is_course_follow_up, resolve_course_follow_up, retrieval_context

try:
    from httpx2 import TimeoutException as SdkTimeout, TransportError as SdkTransportError
except ImportError:
    SdkTimeout = httpx.TimeoutException
    SdkTransportError = httpx.TransportError

_store = None
_client = None
_initialize_lock = Lock()
logger = logging.getLogger(__name__)

class RagUnavailable(RuntimeError):
    """An operational failure with a message safe to expose over HTTP."""

    def __init__(self, message, *, status_code=500, category="backend"):
        super().__init__(message)
        self.status_code = status_code
        self.category = category


def _gemini_failure(error):
    code = error.code if isinstance(error, APIError) and type(error.code) is int else None
    if code == 429:
        return RagUnavailable(
            "بلغت خدمة الإجابة حد الاستخدام. حاول مرة أخرى لاحقًا.",
            status_code=429, category="gemini_quota_or_rate_limit",
        )
    if code in (408, 504) or isinstance(error, (TimeoutError, httpx.TimeoutException, SdkTimeout)):
        return RagUnavailable(
            "انتهت مهلة خدمة الإجابة. حاول مرة أخرى.",
            status_code=504, category="gemini_timeout",
        )
    if code is not None and 500 <= code <= 599:
        return RagUnavailable(
            "خدمة الإجابة غير متاحة مؤقتًا. حاول مرة أخرى لاحقًا.",
            status_code=503, category=f"gemini_upstream_{code}",
        )
    if isinstance(error, (httpx.TransportError, SdkTransportError)):
        return RagUnavailable(
            "تعذّر الاتصال بخدمة الإجابة. حاول مرة أخرى لاحقًا.",
            status_code=503, category="gemini_transport",
        )
    category = {
        400: "gemini_invalid_request", 401: "gemini_authentication",
        403: "gemini_permission", 404: "gemini_model_not_found",
    }.get(code, "gemini_generation_failure")
    return RagUnavailable(
        "تعذّر الحصول على رد من خدمة الإجابة. حاول مرة أخرى أو تواصل مع فريق الدعم.",
        status_code=502, category=category,
    )

class GroundedResponse(BaseModel):
    answer: str
    insufficient_evidence: bool
    evidence: list[Evidence]

def initialize():
    global _store, _client
    with _initialize_lock:
        if _client is None:
            api_key = os.getenv("GEMINI_API_KEY", "").strip()
            if not api_key:
                raise RagUnavailable("Gemini is not configured.")
            try:
                _client = genai.Client(
                    api_key=api_key,
                    http_options={"timeout": 30000, "retry_options": {"attempts": 1}},
                )
            except Exception:
                raise RagUnavailable("Could not initialize Gemini.") from None
        if _store is None:
            try:
                chunks = load_chunks(DATA_PATH)
            except (OSError, ValueError):
                raise RagUnavailable("Could not load the chunk dataset. Check DATA_PATH and the chunk schema.") from None
            try:
                from embeddings_store import VectorStore

                _store = VectorStore(chunks)
            except Exception:
                raise RagUnavailable("Could not build the retrieval index.") from None

def ask_rag(question, history=()):
    question = question.strip()
    if not question:
        return {"answer": "يرجى إدخال سؤال.", "sources": []}
    codes = course_codes(question)
    previous = [turn.content.strip() for turn in history if turn.role == "user" and turn.content.strip()]
    course_follow_up = not codes and is_course_follow_up(question)
    clarification = {"answer": "يرجى ذكر رمز المساق أو اسمه في السؤال حتى أتمكن من تحديده.", "sources": []}
    if course_follow_up and not previous:
        return clarification
    context = retrieval_context(question, previous)
    if not course_follow_up and not codes and context is None:
        return {"answer": "يرجى توضيح الموضوع الذي تشير إليه في سؤالك.", "sources": []}
    initialize()
    lookup_question = question
    codes = course_lookup_targets(question, _store.chunks)
    if codes is None:
        return clarification
    if codes:
        course_follow_up = False
    if course_follow_up:
        target = resolve_course_follow_up(question, history, _store.chunks)
        if target is None:
            return clarification
        code, anchor = target
        codes = [code]
        lookup_question = f"{question}\n{anchor}\n{code}"
    if codes:
        exact = exact_course_answer(lookup_question, _store.chunks, codes)
        if exact is not None:
            return exact
        if course_follow_up:
            return clarification
    try:
        matches = retrieve(_store, f"{context}\n{question}" if context else question)
    except Exception:
        raise RagUnavailable("Could not retrieve document chunks.") from None
    if not matches:
        return {"answer": NO_ANSWER, "sources": []}
    prompt = build_prompt(question, matches, context=context or "")
    for attempt in range(2):
        try:
            response = _client.models.generate_content(
                model=GEMINI_MODEL,
                contents=prompt,
                config={"response_mime_type": "application/json", "response_schema": GroundedResponse},
            )
            break
        except Exception as error:
            if attempt == 0 and isinstance(error, APIError) and error.code == 503:
                logger.warning("Gemini upstream HTTP 503; retrying once after 0.5 seconds.")
                sleep(0.5)
                continue
            raise _gemini_failure(error) from None
    try:
        result = GroundedResponse.model_validate_json(response.text or "", strict=True)
    except ValidationError:
        return {"answer": NO_ANSWER, "sources": []}

    answer = result.answer.strip()
    if result.insufficient_evidence or not answer or answer == NO_ANSWER:
        return {"answer": NO_ANSWER, "sources": []}
    sources = cited_sources(result.evidence, matches)
    if not sources:
        return {"answer": NO_ANSWER, "sources": []}
    return {"answer": answer, "sources": sources}
