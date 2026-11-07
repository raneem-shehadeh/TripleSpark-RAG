import json
from pathlib import Path
from unittest.mock import Mock

import httpx
import numpy as np
import pytest
from fastapi.testclient import TestClient
from google import genai
from google.genai.errors import APIError

import embeddings_store
import rag_pipeline
import retriever
from config import FRONTEND_ORIGINS
from data_loader import load_chunks
from main import app


@pytest.fixture
def client():
    with TestClient(app) as client:
        yield client


@pytest.mark.parametrize("origin", [
    "http://localhost:5173", "http://127.0.0.1:5173",
    "http://localhost:3000", "http://127.0.0.1:3000",
])
def test_react_preflight(client, origin):
    response = client.options("/api/ask", headers={
        "Origin": origin,
        "Access-Control-Request-Method": "POST",
        "Access-Control-Request-Headers": "content-type",
    })
    allowed = origin in FRONTEND_ORIGINS
    assert response.status_code == (200 if allowed else 400)
    assert response.headers.get("access-control-allow-origin") == (origin if allowed else None)


@pytest.mark.parametrize("page,metadata,expected_page", [
    (3, {}, "3"),
    (None, {}, "Unknown"),
    (None, {"source_pages": [60, 98, 99]}, "60, 98, 99"),
    ("12-14", {"page_reference": "ص 12–14"}, "12-14"),
    ("12, 15, 18", {"source_pages": [12, 15, 18]}, "12, 15, 18"),
    ("Unknown", {"page_reference": "ص 92 وما بعدها"}, "Unknown"),
])
def test_synthetic_dataset_through_gemini_sdk(client, monkeypatch, tmp_path, page, metadata, expected_page):
    quote = "يبدأ تسجيل المساقات يوم الأحد."
    question = "إمتى ببلّش تسجيل المواد؟"
    chunk = {
        "id": "registration-1", "text": quote, "source": "دليل التسجيل.pdf",
        "page": page, "chunk_index": 0, "metadata": metadata,
    }
    path = tmp_path / "chunks.json"
    path.write_text(json.dumps([chunk], ensure_ascii=False), encoding="utf-8")

    model = Mock()
    model.encode.return_value = np.array([[1.0, 0.0]])
    real_store = embeddings_store.VectorStore
    stores = []

    def make_store(chunks):
        store = real_store(chunks, model=model)
        stores.append(store)
        return store

    def gemini_response(request):
        assert request.url.path.endswith(":generateContent")
        payload = json.loads(request.content)
        config = payload["generationConfig"]
        assert config["responseMimeType"] == "application/json"
        assert set(config["responseSchema"]["required"]) == {"answer", "insufficient_evidence", "evidence"}
        assert question in payload["contents"][0]["parts"][0]["text"]
        structured = {
            "answer": quote,
            "insufficient_evidence": False,
            "evidence": [{"chunk_number": 1, "quote": quote}],
        }
        return httpx.Response(200, json={"candidates": [{"content": {
            "role": "model", "parts": [{"text": json.dumps(structured, ensure_ascii=False)}],
        }}]})

    monkeypatch.setattr(rag_pipeline, "DATA_PATH", path)
    monkeypatch.setattr(rag_pipeline, "_store", None)
    monkeypatch.setattr(retriever, "MAX_DISTANCE", None)
    monkeypatch.setattr(embeddings_store, "VectorStore", make_store)
    try:
        with httpx.Client(transport=httpx.MockTransport(gemini_response)) as transport_client:
            with genai.Client(vertexai=False, api_key="offline-test", http_options={"httpx_client": transport_client}) as gemini:
                monkeypatch.setattr(rag_pipeline, "_client", gemini)
                assert client.get("/").json() == {"status": "ok"}
                response = client.post("/api/ask", json={"question": question})
                assert response.status_code == 200
                assert response.json() == {
                    "answer": quote,
                    "sources": [{"source": chunk["source"], "page": expected_page}],
                }
    finally:
        for store in stores:
            store.client.delete_collection(store.collection.name)


def test_full_dataset_indexes_without_dropping_chunks():
    path = Path(__file__).resolve().parents[1] / "data" / "chunks.json"
    raw_chunks = json.loads(path.read_text(encoding="utf-8"))
    chunks = load_chunks(path)
    assert chunks == raw_chunks
    model = Mock()
    model.encode.return_value = np.ones((len(chunks), 2))
    store = embeddings_store.VectorStore(chunks, model=model)
    try:
        assert store.collection.count() == len(raw_chunks)
        records = store.collection.get(include=["metadatas"])
        assert dict(zip(records["ids"], records["metadatas"])) == {
            chunk["id"]: {"source": chunk["source"], "page": str(chunk["page"])}
            for chunk in raw_chunks
        }
    finally:
        store.client.delete_collection(store.collection.name)


@pytest.mark.parametrize("failure,upstream,status,category,detail", [
    ("dataset", None, 500, "backend", "Could not load the chunk dataset. Check DATA_PATH and the chunk schema."),
    ("retrieval", None, 500, "backend", "Could not retrieve document chunks."),
    ("gemini", 429, 429, "gemini_quota_or_rate_limit", "بلغت خدمة الإجابة حد الاستخدام. حاول مرة أخرى لاحقًا."),
    ("gemini", "timeout", 504, "gemini_timeout", "انتهت مهلة خدمة الإجابة. حاول مرة أخرى."),
    ("gemini", "connect", 503, "gemini_transport", "تعذّر الاتصال بخدمة الإجابة. حاول مرة أخرى لاحقًا."),
    ("gemini", 503, 503, "gemini_upstream_503", "خدمة الإجابة غير متاحة مؤقتًا. حاول مرة أخرى لاحقًا."),
    ("gemini", 401, 502, "gemini_authentication", "تعذّر الحصول على رد من خدمة الإجابة. حاول مرة أخرى أو تواصل مع فريق الدعم."),
    ("gemini", 404, 502, "gemini_model_not_found", "تعذّر الحصول على رد من خدمة الإجابة. حاول مرة أخرى أو تواصل مع فريق الدعم."),
    ("gemini", 400, 502, "gemini_invalid_request", "تعذّر الحصول على رد من خدمة الإجابة. حاول مرة أخرى أو تواصل مع فريق الدعم."),
])
def test_operational_errors_are_safe(client, monkeypatch, caplog, failure, upstream, status, category, detail):
    sensitive = "private-upstream-error"
    store = Mock()
    store.chunks = []
    gemini = Mock()
    pause = Mock()
    monkeypatch.setattr(rag_pipeline, "sleep", pause)
    monkeypatch.setattr(rag_pipeline, "_store", store)
    monkeypatch.setattr(rag_pipeline, "_client", gemini)
    if failure == "dataset":
        monkeypatch.setattr(rag_pipeline, "_store", None)
        monkeypatch.setattr(rag_pipeline, "load_chunks", Mock(side_effect=ValueError(sensitive)))
    elif failure == "retrieval":
        store.search.side_effect = RuntimeError(sensitive)
    else:
        monkeypatch.setattr(rag_pipeline, "retrieve", Mock(return_value=[{"text": "سياسة الجامعة"}]))
        if upstream == "timeout":
            error = httpx.ReadTimeout(sensitive)
        elif upstream == "connect":
            error = httpx.ConnectError(sensitive)
        else:
            error = APIError(upstream, {"error": {"code": upstream, "message": sensitive}})
        gemini.models.generate_content.side_effect = error

    response = client.post("/api/ask", json={"question": "إمتى التسجيل؟"})
    assert response.status_code == status
    assert response.json() == {"detail": detail}
    assert detail in caplog.text
    assert category in caplog.text
    assert sensitive not in caplog.text
    if failure == "gemini":
        assert gemini.models.generate_content.call_count == (2 if upstream == 503 else 1)
        assert pause.call_count == (1 if upstream == 503 else 0)
