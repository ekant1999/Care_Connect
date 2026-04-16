"""
RAG: retrieve from ChromaDB (same embedding model as index) + generate with Ollama (DeepSeek R1).
"""
import logging
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

import chromadb
import requests
from sentence_transformers import SentenceTransformer

from src.config import get_project_root, get_rag_config
from src.rag.response_cache import build_cache_key, get_response_cache

# Debug: log retrieved chunks + CoT to logs/rag_chunks.log when rag_debug_log is true
RAG_DEBUG_LOG_NAME = "rag_chunks.log"


def _log_chunks_to_file(project_root: Path, query: str, chunks: List[Dict[str, Any]], top_k: int) -> None:
    """Append query and full retrieved chunks to logs/rag_chunks.log for debugging retrieval quality."""
    log_dir = project_root / "logs"
    log_dir.mkdir(parents=True, exist_ok=True)
    log_path = log_dir / RAG_DEBUG_LOG_NAME
    ts = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")
    lines = [
        "",
        "=" * 60,
        f"[{ts}] RAG retrieve",
        f"  query: {query!r}",
        f"  top_k: {top_k}  chunks_returned: {len(chunks)}",
    ]
    for i, c in enumerate(chunks, 1):
        meta = c.get("metadata") or {}
        source = meta.get("source", "")
        title = meta.get("title", "")
        url = meta.get("url", "")
        text = c.get("text") or ""
        lines.append(f"  --- chunk {i} ---")
        lines.append(f"    source: {source}  title: {title}")
        lines.append(f"    url: {url}")
        lines.append(f"    text: {text!r}")
    lines.append("")
    try:
        with open(log_path, "a", encoding="utf-8") as f:
            f.write("\n".join(lines) + "\n")
    except OSError as e:
        logging.getLogger(__name__).warning("Could not write RAG debug log %s: %s", log_path, e)


def _log_cot_to_file(project_root: Path, query: str, thinking: str) -> None:
    """Append chain-of-thought (reasoning) to logs/rag_chunks.log when model returns it (think=true)."""
    if not (thinking or "").strip():
        return
    log_dir = project_root / "logs"
    log_dir.mkdir(parents=True, exist_ok=True)
    log_path = log_dir / RAG_DEBUG_LOG_NAME
    ts = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")
    lines = [
        "",
        "-" * 60,
        f"[{ts}] RAG chain-of-thought (DeepSeek R1 reasoning)",
        f"  query: {query!r}",
        "  thinking:",
        thinking.strip(),
        "",
    ]
    try:
        with open(log_path, "a", encoding="utf-8") as f:
            f.write("\n".join(lines) + "\n")
    except OSError as e:
        logging.getLogger(__name__).warning("Could not write RAG CoT log %s: %s", log_path, e)


def _get_embedding_model(model_name: str):
    """Load SentenceTransformer once; same model used for indexing."""
    return SentenceTransformer(model_name)


def _get_collection(project_root: Optional[Path] = None):
    """Get ChromaDB collection and embedding model from config."""
    root = project_root or get_project_root()
    cfg = get_rag_config(root)
    client = chromadb.PersistentClient(path=str(cfg["chroma_persist_directory"]))
    collection = client.get_collection(name=cfg["collection_name"])
    return collection, cfg


def retrieve(
    query: str,
    top_k: Optional[int] = None,
    project_root: Optional[Path] = None,
    source: Optional[str] = None,
) -> List[Dict[str, Any]]:
    """
    Embed the query, search ChromaDB, return list of chunk dicts (text + metadata).
    """
    root = project_root or get_project_root()
    cfg = get_rag_config(root)
    top_k = top_k or cfg["top_k"]
    collection, _ = _get_collection(root)
    model = _get_embedding_model(cfg["embedding_model_name"])
    query_embedding = model.encode([query], show_progress_bar=False).tolist()[0]

    query_kwargs: Dict[str, Any] = {
        "query_embeddings": [query_embedding],
        "n_results": top_k,
        "include": ["documents", "metadatas"],
    }
    if source:
        query_kwargs["where"] = {"source": source}
    results = collection.query(**query_kwargs)
    chunks = []
    if results["documents"] and results["documents"][0]:
        for i, doc in enumerate(results["documents"][0]):
            meta = (results["metadatas"][0][i] or {}) if results["metadatas"] else {}
            chunks.append({"text": doc, "metadata": meta})
    return chunks


def retrieve_with_distances(
    query: str,
    top_k: Optional[int] = None,
    project_root: Optional[Path] = None,
    source: Optional[str] = None,
) -> List[Dict[str, Any]]:
    """
    Like retrieve() but each chunk includes a "distance" key (ChromaDB L2 or cosine distance).
    Lower distance = more similar. Used for relevance threshold in topic lookup.
    """
    root = project_root or get_project_root()
    cfg = get_rag_config(root)
    top_k = top_k or cfg["top_k"]
    collection, _ = _get_collection(root)
    model = _get_embedding_model(cfg["embedding_model_name"])
    query_embedding = model.encode([query], show_progress_bar=False).tolist()[0]

    query_kwargs: Dict[str, Any] = {
        "query_embeddings": [query_embedding],
        "n_results": top_k,
        "include": ["documents", "metadatas", "distances"],
    }
    if source:
        query_kwargs["where"] = {"source": source}
    results = collection.query(**query_kwargs)
    chunks = []
    if results["documents"] and results["documents"][0]:
        distances = (results.get("distances") or [[]])[0] if results.get("distances") else []
        for i, doc in enumerate(results["documents"][0]):
            meta = (results["metadatas"][0][i] or {}) if results["metadatas"] else {}
            dist = distances[i] if i < len(distances) else None
            chunks.append({"text": doc, "metadata": meta, "distance": dist})
    return chunks


def _build_rag_prompt(context_chunks: List[Dict[str, Any]], user_query: str, system_prompt: str) -> str:
    """Build user message: context blocks + question."""
    context_parts = []
    for i, c in enumerate(context_chunks, 1):
        text = c.get("text", "")
        source = (c.get("metadata") or {}).get("source", "")
        title = (c.get("metadata") or {}).get("title", "")
        if source or title:
            context_parts.append(f"[{i}] (Source: {source}; {title})\n{text}")
        else:
            context_parts.append(f"[{i}]\n{text}")
    context_block = "\n\n---\n\n".join(context_parts)
    return (
        "Use the following context from trusted health sources to answer the question.\n\n"
        "Context:\n\n"
        f"{context_block}\n\n"
        "Question: "
        f"{user_query}\n\n"
        "Answer based only on the context above. If the context does not contain relevant information, say so."
    )


def ask_ollama(
    messages: List[Dict[str, str]],
    model: Optional[str] = None,
    base_url: Optional[str] = None,
    timeout: Optional[int] = None,
    project_root: Optional[Path] = None,
    debug_query: Optional[str] = None,
) -> str:
    """
    Send messages to Ollama chat API (e.g. DeepSeek R1). Returns assistant content.
    When debug_query is set and the response has message.thinking, appends CoT to logs/rag_chunks.log.
    messages: [{"role": "user"|"system"|"assistant", "content": "..."}]
    """
    root = project_root or get_project_root()
    cfg = get_rag_config(root)
    url = f"{(base_url or cfg['ollama_base_url']).rstrip('/')}/api/chat"
    payload = {
        "model": model or cfg["ollama_model"],
        "messages": messages,
        "stream": False,
        "think": cfg.get("ollama_think", True),
    }
    resp = requests.post(
        url,
        json=payload,
        timeout=timeout or cfg["ollama_timeout_seconds"],
    )
    resp.raise_for_status()
    data = resp.json()
    msg = data.get("message") or {}
    content = msg.get("content", "")
    thinking = msg.get("thinking", "")
    if debug_query is not None and thinking:
        _log_cot_to_file(root, debug_query, thinking)
    return content


def rag_query(
    query: str,
    top_k: Optional[int] = None,
    project_root: Optional[Path] = None,
    source: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Run RAG: retrieve relevant chunks from ChromaDB, then ask Ollama (DeepSeek R1) to answer.
    Returns {"answer": str, "chunks": list of retrieved chunk dicts}.
    When response_cache_enabled is true, identical normalized queries reuse the prior answer
    and chunks without retrieval or LLM calls (until LRU eviction or cache version bump).
    """
    root = project_root or get_project_root()
    cfg = get_rag_config(root)
    top_k = top_k or cfg["top_k"]

    if cfg.get("response_cache_enabled"):
        cache = get_response_cache(cfg["response_cache_max_entries"])
        cache_key = build_cache_key(query, top_k, cfg, source=source)
        hit = cache.get(cache_key)
        if hit is not None:
            return hit

    chunks = retrieve(query, top_k=top_k, project_root=root, source=source)
    if cfg.get("rag_debug_log"):
        _log_chunks_to_file(root, query, chunks, top_k)
    if not chunks:
        out = {
            "answer": "No relevant context found in the knowledge base. Try rephrasing or a different question.",
            "chunks": [],
        }
        if cfg.get("response_cache_enabled"):
            get_response_cache(cfg["response_cache_max_entries"]).set(
                build_cache_key(query, top_k, cfg, source=source), out
            )
        return out

    user_content = _build_rag_prompt(chunks, query, cfg["system_prompt"])
    messages = []
    if cfg.get("system_prompt"):
        messages.append({"role": "system", "content": cfg["system_prompt"]})
    messages.append({"role": "user", "content": user_content})

    answer = ask_ollama(
        messages,
        project_root=root,
        debug_query=query if cfg.get("rag_debug_log") else None,
    )
    result = {"answer": answer, "chunks": chunks}
    if cfg.get("response_cache_enabled"):
        get_response_cache(cfg["response_cache_max_entries"]).set(
            build_cache_key(query, top_k, cfg, source=source), result
        )
    return result
