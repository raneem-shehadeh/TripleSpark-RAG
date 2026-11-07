import logging

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from config import FRONTEND_ORIGINS
from conversation import ChatTurn, MAX_HISTORY_MESSAGES
from rag_pipeline import RagUnavailable, ask_rag

logger = logging.getLogger(__name__)
app = FastAPI(title="Triple Spark Universal RAG API")
app.add_middleware(
    CORSMiddleware,
    allow_origins=FRONTEND_ORIGINS,
    allow_credentials=False,
    allow_methods=["GET", "POST"],
    allow_headers=["Content-Type"],
)

class AskRequest(BaseModel):
    question: str = Field(min_length=1)
    history: list[ChatTurn] = Field(default_factory=list, max_length=MAX_HISTORY_MESSAGES)

@app.get("/")
def health():
    return {"status": "ok"}

@app.post("/api/ask")
def ask(request: AskRequest):
    try:
        return ask_rag(request.question, request.history)
    except RagUnavailable as error:
        logger.warning("RAG request failed [%s]: %s", error.category, error)
        raise HTTPException(status_code=error.status_code, detail=str(error)) from None
