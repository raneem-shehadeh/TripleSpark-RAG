"""Score labeled chunk retrieval without calling the answer generator."""

import argparse
import json
from pathlib import Path
from statistics import mean

from pydantic import BaseModel, ConfigDict, TypeAdapter, model_validator

import retriever
from config import DATA_PATH, TOP_K
from data_loader import load_chunks


class RetrievalCase(BaseModel):
    model_config = ConfigDict(strict=True)

    question: str
    expected_chunk_ids: list[str]
    should_refuse: bool

    @model_validator(mode="after")
    def validate_labels(self):
        if not self.question.strip():
            raise ValueError("question must not be blank")
        if any(not chunk_id.strip() for chunk_id in self.expected_chunk_ids):
            raise ValueError("expected chunk IDs must not be blank")
        if self.should_refuse == bool(self.expected_chunk_ids):
            raise ValueError("only refusal cases must have an empty expected_chunk_ids list")
        return self


def load_cases(path):
    cases = TypeAdapter(list[RetrievalCase]).validate_json(Path(path).read_bytes())
    if not cases:
        raise ValueError("evaluation dataset must contain at least one case")
    return cases


def evaluate_retrieval(store, cases, k=TOP_K):
    if k < 1:
        raise ValueError("k must be positive")

    indexed_ids = {chunk["id"] for chunk in store.chunks}
    rows = []
    recalls = []
    unsupported_with_results = 0
    for case in cases:
        expected = set(case.expected_chunk_ids)
        unknown = expected - indexed_ids
        if unknown:
            raise ValueError(f"Unknown expected chunk IDs for {case.question!r}: {sorted(unknown)}")

        matches = retriever.retrieve(store, case.question, k=k)
        recall = None
        if expected:
            recall = len(expected.intersection(match["id"] for match in matches)) / len(expected)
            recalls.append(recall)
        elif matches:
            unsupported_with_results += 1

        rows.append({
            **case.model_dump(),
            "recall_at_k": recall,
            "retrieved": [
                {key: match[key] for key in ("id", "source", "page", "distance")}
                for match in matches
            ],
        })

    return {
        "k": k,
        "max_distance": retriever.MAX_DISTANCE,
        "mean_recall_at_k": mean(recalls) if recalls else None,
        "answerable_questions": len(recalls),
        "unsupported_questions": len(rows) - len(recalls),
        "unsupported_with_results": unsupported_with_results,
        "questions": rows,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("questions", type=Path, help="JSON file with labeled retrieval cases")
    parser.add_argument("--chunks", type=Path, help="path to chunks.json (default: configured DATA_PATH)")
    parser.add_argument("--k", type=int, default=TOP_K)
    args = parser.parse_args()
    if args.k < 1:
        parser.error("--k must be positive")

    from embeddings_store import VectorStore

    cases = load_cases(args.questions)
    chunks_path = args.chunks.resolve() if args.chunks else DATA_PATH
    store = VectorStore(load_chunks(chunks_path))
    print(json.dumps(evaluate_retrieval(store, cases, args.k), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
