import os
from math import isfinite
from dotenv import load_dotenv
load_dotenv()
EMBEDDING_MODEL = os.getenv("EMBEDDING_MODEL", "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2")
GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-3.1-flash-lite")
try:
    TOP_K = int(os.getenv("TOP_K", "3"))
except ValueError:
    raise ValueError("TOP_K must be a positive integer") from None
if TOP_K < 1:
    raise ValueError("TOP_K must be a positive integer")
# Optional: calibrate on real data. Empty means no distance gate.
try:
    MAX_DISTANCE = float(os.environ["MAX_DISTANCE"]) if os.getenv("MAX_DISTANCE") else None
except ValueError:
    raise ValueError("MAX_DISTANCE must be empty or a finite number") from None
if MAX_DISTANCE is not None and not isfinite(MAX_DISTANCE):
    raise ValueError("MAX_DISTANCE must be empty or a finite number")
NO_ANSWER = "لا توجد معلومات كافية للإجابة عن هذا السؤال."
DATA_PATH = os.getenv("DATA_PATH", "data/chunks.json")
FRONTEND_ORIGINS = [x.strip() for x in os.getenv("FRONTEND_ORIGINS", "http://localhost:5173,http://127.0.0.1:5173,http://localhost:3000,http://127.0.0.1:3000").split(",") if x.strip()]
ASSISTANT_ROLE = os.getenv("ASSISTANT_ROLE", "مساعد معلومات يعتمد على المستندات المتاحة")
