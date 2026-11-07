"""Generate answers for manual evaluation against reference questions."""
import json
import time
from pathlib import Path
from rag_pipeline import ask_rag

path = Path(__file__).parent / "data/eval_questions.json"
questions = json.loads(path.read_text(encoding="utf-8"))
if not questions:
    print("Add real questions to data/eval_questions.json first.")
else:
    for item in questions:
        start = time.perf_counter()
        result = ask_rag(item["question"])
        seconds = time.perf_counter() - start
        print(json.dumps({"question": item["question"], "expected": item.get("expected_answer"), "actual": result, "seconds": round(seconds, 2)}, ensure_ascii=False))
    print("Review answer accuracy, source support and refusal manually; no automatic correctness score is claimed.")
