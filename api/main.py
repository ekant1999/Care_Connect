"""
Care Connect API — RAG chat endpoint for the UI.
Run from project root: uvicorn api.main:app --reload --port 8000
"""
from pathlib import Path
from typing import List, Optional

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from src.rag import rag_query

# Resolve project root from this file (api/main.py -> project root) so RAG uses
# the same config and ChromaDB path as the CLI regardless of uvicorn cwd.
PROJECT_ROOT = Path(__file__).resolve().parent.parent

app = FastAPI(
    title="Care Connect API",
    description="RAG-backed mental health Q&A",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class ChatRequest(BaseModel):
    message: str


class Citation(BaseModel):
    title: str
    source: str
    url: Optional[str] = None


class ChatResponse(BaseModel):
    answer: str
    citations: List[Citation]


def _source_display(source: str) -> str:
    if source == "medlineplus":
        return "MedlinePlus (NLM)"
    if source == "pubmed":
        return "PubMed"
    if source == "nimh":
        return "NIMH"
    return source or ""


def _normalize_title(title: str) -> str:
    """Fix duplicated titles from sources (e.g. 'MemoryMemory' -> 'Memory')."""
    if not title or len(title) < 2:
        return title or "Health information"
    half = len(title) // 2
    if title[:half] == title[half:] and 2 * half == len(title):
        return title[:half]
    return title


@app.post("/api/chat", response_model=ChatResponse)
def chat(request: ChatRequest) -> ChatResponse:
    """Run RAG: retrieve context from ChromaDB, generate answer with Ollama (DeepSeek R1)."""
    if not (request.message or "").strip():
        raise HTTPException(status_code=400, detail="Message cannot be empty")
    try:
        result = rag_query(request.message.strip(), project_root=PROJECT_ROOT)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"RAG error: {str(e)}")
    answer = result.get("answer", "")
    chunks = result.get("chunks", [])
    seen_urls = set()
    citations = []
    for c in chunks:
        meta = c.get("metadata") or {}
        url = meta.get("url") or ""
        if url and url not in seen_urls:
            seen_urls.add(url)
            title = _normalize_title(meta.get("title") or "Health information")
            source = _source_display(meta.get("source") or "")
            citations.append(Citation(title=title, source=source, url=url or None))
    return ChatResponse(answer=answer, citations=citations)
