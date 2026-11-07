import json
from types import SimpleNamespace
from unittest.mock import Mock

import pytest
from fastapi.testclient import TestClient
from google.genai.errors import APIError

import rag_pipeline
import retriever
from config import NO_ANSWER
from main import app

client = TestClient(app)

def test_health():
    r = client.get("/")
    assert r.status_code == 200
    assert r.json()["status"] == "ok"

def test_missing_question():
    r = client.post("/api/ask", json={"message": "hello"})
    assert r.status_code == 422

def test_empty_question():
    r = client.post("/api/ask", json={"question": ""})
    assert r.status_code == 422


@pytest.mark.parametrize("history", [
    [{"role": "user", "content": "previous"}] * 9,
    [{"role": "user", "content": "x" * 1001}],
    [{"role": "system", "content": "untrusted"}],
])
def test_history_is_bounded_and_validated(history):
    assert client.post("/api/ask", json={"question": "When?", "history": history}).status_code == 422


REGISTRATION_QUOTE = "يبدأ تسجيل المساقات يوم الأحد."
FEES_QUOTE = "تُدفع رسوم التسجيل قبل بداية الفصل."
REGISTRATION_EVIDENCE = {"chunk_number": 1, "quote": REGISTRATION_QUOTE}
FEES_EVIDENCE = {"chunk_number": 2, "quote": FEES_QUOTE}


@pytest.fixture
def stub_rag(monkeypatch):
    store = Mock()
    store.chunks = []
    store.search.return_value = {
        "ids": [["registration", "fees"]],
        "documents": [[f"مواعيد الفصل: {REGISTRATION_QUOTE}", FEES_QUOTE]],
        "metadatas": [[
            {"source": "دليل التسجيل.pdf", "page": "٣"},
            {"source": "الرسوم الجامعية.pdf", "page": "iv"},
        ]],
        "distances": [[0.1, 0.2]],
    }
    gemini = Mock()
    monkeypatch.setattr(rag_pipeline, "_store", store)
    monkeypatch.setattr(rag_pipeline, "_client", gemini)
    monkeypatch.setattr(retriever, "MAX_DISTANCE", None)
    return store, gemini.models.generate_content


def model_output(evidence, answer="التسجيل ببلّش يوم الأحد.", insufficient_evidence=False):
    return json.dumps({"answer": answer, "insufficient_evidence": insufficient_evidence, "evidence": evidence})


def test_supported_colloquial_question(stub_rag):
    store, generate = stub_rag
    answer = "التسجيل ببلّش يوم الأحد."
    generate.return_value = SimpleNamespace(text=model_output([REGISTRATION_EVIDENCE], answer=answer))
    question = "إمتى ببلّش تسجيل المواد؟"
    r = client.post("/api/ask", json={"question": question})

    assert r.status_code == 200
    assert r.json() == {"answer": answer, "sources": [{"source": "دليل التسجيل.pdf", "page": "٣"}]}
    assert store.search.call_args.args[0] == question
    assert generate.call_args.kwargs["config"]["response_mime_type"] == "application/json"


def test_transient_gemini_503_retries_once_and_verifies_evidence(stub_rag, monkeypatch):
    store, generate = stub_rag
    pause = Mock()
    monkeypatch.setattr(rag_pipeline, "sleep", pause)
    generate.side_effect = [
        APIError(503, {"error": {"code": 503, "message": "Temporary capacity issue"}}),
        SimpleNamespace(text=model_output([REGISTRATION_EVIDENCE])),
    ]
    response = client.post("/api/ask", json={"question": "إمتى التسجيل؟"})
    assert response.status_code == 200
    assert response.json()["sources"] == [{"source": "دليل التسجيل.pdf", "page": "٣"}]
    assert generate.call_count == 2
    assert generate.call_args_list[0] == generate.call_args_list[1]
    store.search.assert_called_once()
    pause.assert_called_once_with(0.5)


def test_general_followup_uses_user_context_and_fresh_evidence(stub_rag):
    store, generate = stub_rag
    generate.return_value = SimpleNamespace(text=model_output([REGISTRATION_EVIDENCE]))
    r = client.post("/api/ask", json={
        "question": "And when does it start?",
        "history": [
            {"role": "user", "content": "Tell me about registration"},
            {"role": "assistant", "content": "Unverified historical claim"},
        ],
    })
    assert r.status_code == 200
    assert r.json()["sources"] == [{"source": "دليل التسجيل.pdf", "page": "٣"}]
    assert store.search.call_args.args[0] == "Tell me about registration\nAnd when does it start?"
    prompt = generate.call_args.kwargs["contents"]
    assert "reference context only; never evidence" in prompt
    assert "Tell me about registration" in prompt
    assert "Unverified historical claim" not in prompt


def test_general_followup_with_no_user_referent_asks_for_clarification(stub_rag):
    store, generate = stub_rag
    r = client.post("/api/ask", json={
        "question": "When does it start?",
        "history": [{"role": "assistant", "content": "I assume you mean registration"}],
    })
    assert r.status_code == 200
    assert r.json()["sources"] == []
    assert "توضيح" in r.json()["answer"]
    store.search.assert_not_called()
    generate.assert_not_called()


def test_multiple_sources_are_deduplicated_and_preserve_metadata(stub_rag):
    _, generate = stub_rag
    answer = "يبدأ التسجيل الأحد، وتُدفع الرسوم قبل بداية الفصل."
    generate.return_value = SimpleNamespace(text=model_output(
        [FEES_EVIDENCE, REGISTRATION_EVIDENCE, REGISTRATION_EVIDENCE], answer=answer,
    ))
    r = client.post("/api/ask", json={"question": "إمتى التسجيل وإمتى لازم أدفع الرسوم؟"})

    assert r.status_code == 200
    assert r.json() == {"answer": answer, "sources": [
        {"source": "دليل التسجيل.pdf", "page": "٣"},
        {"source": "الرسوم الجامعية.pdf", "page": "iv"},
    ]}


@pytest.mark.parametrize("output", [
    model_output([], answer="التسجيل الأحد [1]."),
    model_output([{"chunk_number": 0, "quote": REGISTRATION_QUOTE}]),
    model_output([{"chunk_number": 3, "quote": REGISTRATION_QUOTE}]),
    model_output([{"chunk_number": True, "quote": REGISTRATION_QUOTE}]),
    model_output([{"chunk_number": "1", "quote": REGISTRATION_QUOTE}]),
    model_output([{"chunk_number": 1, "quote": " "}]),
    model_output([{"chunk_number": 1, "quote": FEES_QUOTE}]),
    model_output([REGISTRATION_EVIDENCE, {"chunk_number": 2, "quote": "الرسوم مجانية."}]),
    model_output([REGISTRATION_EVIDENCE], answer="  "),
    model_output([REGISTRATION_EVIDENCE], insufficient_evidence=True),
    '{"answer":"answer","insufficient_evidence":false}',
    '{"answer":"answer","insufficient_evidence":"false","evidence":[]}',
    "not JSON",
    None,
])
def test_unverified_model_output_is_refused(stub_rag, output):
    _, generate = stub_rag
    generate.return_value = SimpleNamespace(text=output)
    r = client.post("/api/ask", json={"question": "إمتى التسجيل؟"})

    assert r.status_code == 200
    assert r.json() == {"answer": NO_ANSWER, "sources": []}


def test_unrelated_question_with_retrieved_chunks_is_refused(stub_rag):
    _, generate = stub_rag
    generate.return_value = SimpleNamespace(text=model_output([], answer=NO_ANSWER, insufficient_evidence=True))
    r = client.post("/api/ask", json={"question": "شو طقس بكرة؟"})

    generate.assert_called_once()
    assert r.status_code == 200
    assert r.json() == {"answer": NO_ANSWER, "sources": []}


def test_empty_retrieval_skips_gemini(stub_rag):
    store, generate = stub_rag
    store.search.return_value = {"ids": [[]], "documents": [[]], "metadatas": [[]], "distances": [[]]}
    r = client.post("/api/ask", json={"question": "شو طقس بكرة؟"})

    generate.assert_not_called()
    assert r.status_code == 200
    assert r.json() == {"answer": NO_ANSWER, "sources": []}
