import json

import numpy as np
import pytest

import retriever
from embeddings_store import VectorStore
from evaluate_retrieval import evaluate_retrieval, load_cases


DIRECT = "متى يبدأ تسجيل المساقات؟"
COLLOQUIAL = "إمتى ببلّش تسجيل المواد؟"
MULTI_CHUNK = "إمتى ببلّش التسجيل وإمتى آخر موعد لدفع الرسوم؟"
UNSUPPORTED = "كم قيمة منحة التفوق؟"


class ControlledModel:
    def __init__(self, vectors):
        self.vectors = vectors

    def encode(self, texts):
        return np.array([self.vectors[text] for text in texts])


@pytest.fixture
def store(monkeypatch):
    monkeypatch.setattr(retriever, "MAX_DISTANCE", None)
    chunks = [
        {"id": "registration", "text": "يبدأ تسجيل المساقات يوم الأحد.",
         "source": "دليل التسجيل.pdf", "page": 3, "chunk_index": 0},
        {"id": "fees", "text": "آخر موعد لدفع رسوم التسجيل هو يوم الخميس.",
         "source": "التقويم الجامعي.pdf", "page": "iv", "chunk_index": 0},
        {"id": "library", "text": "تُعاد كتب المكتبة خلال أسبوعين من الإعارة.",
         "source": "دليل المكتبة.pdf", "page": "أ-٢", "chunk_index": 0},
    ]
    model = ControlledModel({
        chunks[0]["text"]: [0, 0], chunks[1]["text"]: [2, 0], chunks[2]["text"]: [10, 0],
        DIRECT: [0, 0], COLLOQUIAL: [0.25, 0], MULTI_CHUNK: [0.75, 0], UNSUPPORTED: [30, 0],
    })
    vector_store = VectorStore(chunks, model=model)
    yield vector_store
    vector_store.client.delete_collection(vector_store.collection.name)


@pytest.mark.parametrize("question,distance", [(DIRECT, 0), (COLLOQUIAL, 0.0625)])
def test_registration_ranks_first_with_original_metadata(store, question, distance):
    matches = retriever.retrieve(store, question, k=3)
    assert [match["id"] for match in matches] == ["registration", "fees", "library"]
    assert matches[0] == {
        "id": "registration", "text": "يبدأ تسجيل المساقات يوم الأحد.",
        "source": "دليل التسجيل.pdf", "page": "3", "distance": pytest.approx(distance),
    }


def test_cutoff_is_optional_and_inclusive(store, monkeypatch):
    candidates = retriever.retrieve(store, UNSUPPORTED, k=1)
    assert candidates[0]["distance"] == pytest.approx(400)

    monkeypatch.setattr(retriever, "MAX_DISTANCE", 0)
    assert retriever.retrieve(store, UNSUPPORTED, k=1) == []
    assert [match["id"] for match in retriever.retrieve(store, DIRECT, k=2)] == ["registration"]


@pytest.mark.parametrize("question", [
    "ما هي العلامة المسموح فيها إعادة المساق؟",
    "ما الدرجة المسموح فيها إعادة مادة؟",
])
def test_regulation_rerank_promotes_eligibility_over_nearby_results(question, monkeypatch):
    monkeypatch.setattr(retriever, "MAX_DISTANCE", None)
    chunks = [
        {"id": "grading", "text": "العلامة النهائية تجمع الامتحان والمشاركة."},
        {"id": "medical", "text": "يجوز إعادة المساق السريري بحسب علامة التدريب.",
         "metadata": {"collection": "medical_program_regulations", "program": "دكتور في الطب"}},
        {"id": "other", "text": "تطرح الجامعة المساقات ضمن الخطة الدراسية."},
        {"id": "general", "text": "يجوز إعادة المساق بحسب العلامة لرفع المعدل.",
         "metadata": {"collection": "academic_regulations"}},
    ]
    for i, chunk in enumerate(chunks):
        chunk.update(source="student-guide.pdf", page=i + 1)
    vectors = {chunk["text"]: [i + 1, 0] for i, chunk in enumerate(chunks)}
    vectors[question] = [0, 0]
    store = VectorStore(chunks, model=ControlledModel(vectors))
    try:
        assert store.search(question, 3)["ids"][0] == ["grading", "medical", "other"]
        ranked = retriever.retrieve(store, question, k=3)
        assert [row["id"] for row in ranked] == ["general", "grading", "medical"]
        assert ranked[0]["page"] == "4"
        assert ranked[0]["distance"] == pytest.approx(16)
        monkeypatch.setattr(retriever, "MAX_DISTANCE", 9)
        assert [row["id"] for row in retriever.retrieve(store, question)] == ["grading", "medical", "other"]
    finally:
        store.client.delete_collection(store.collection.name)


def test_retrieval_evaluation_scores_multiple_chunks_and_tracks_unsupported(store, tmp_path):
    labels = [
        {"question": DIRECT, "expected_chunk_ids": ["registration"], "should_refuse": False},
        {"question": COLLOQUIAL, "expected_chunk_ids": ["registration"], "should_refuse": False},
        {"question": MULTI_CHUNK, "expected_chunk_ids": ["registration", "fees"], "should_refuse": False},
        {"question": UNSUPPORTED, "expected_chunk_ids": [], "should_refuse": True},
    ]
    path = tmp_path / "retrieval_cases.json"
    path.write_text(json.dumps(labels, ensure_ascii=False), encoding="utf-8")
    cases = load_cases(path)
    at_one = evaluate_retrieval(store, cases, k=1)
    at_two = evaluate_retrieval(store, cases, k=2)

    assert at_one["mean_recall_at_k"] == pytest.approx(5 / 6)
    assert at_one["questions"][2]["recall_at_k"] == 0.5
    assert at_two["mean_recall_at_k"] == 1.0
    assert at_two["answerable_questions"] == 3
    assert at_two["unsupported_questions"] == at_two["unsupported_with_results"] == 1
    assert at_two["questions"][3]["recall_at_k"] is None
    assert at_two["questions"][2]["retrieved"] == [
        {"id": "registration", "source": "دليل التسجيل.pdf", "page": "3", "distance": pytest.approx(0.5625)},
        {"id": "fees", "source": "التقويم الجامعي.pdf", "page": "iv", "distance": pytest.approx(1.5625)},
    ]
