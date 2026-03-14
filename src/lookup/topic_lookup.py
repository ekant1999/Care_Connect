"""
Topic lookup flow: return link + summary for one topic.
If the topic is in the database (ChromaDB), format chunks as link+summary.
Otherwise run on-demand fetch (PubMed, MedlinePlus, NIMH in parallel) and return same shape.
Uses relevance threshold (max_distance) and keyword check before trusting DB results.
"""
import re
from pathlib import Path
from typing import Any, Dict, List, Optional

from src.config import get_lookup_config, get_project_root
from src.lookup.on_demand_fetch import fetch_on_demand, ingest_on_demand_to_db
from src.rag.ollama_rag import retrieve_with_distances
from src.utils.logger import get_logger, setup_logger

# Max length for summary when formatting from DB chunks
SUMMARY_MAX_LEN = 300

# Minimum length for a word to count as a query term (skip very short tokens)
MIN_TERM_LEN = 2


def _query_terms(topic: str) -> set[str]:
    """Normalize topic into a set of terms (lowercase, alphanumeric, length >= MIN_TERM_LEN)."""
    tokens = re.sub(r"[^\w\s]", " ", topic).lower().split()
    return {t for t in tokens if len(t) >= MIN_TERM_LEN}


def _chunk_contains_any_term(chunk: Dict[str, Any], terms: set[str]) -> bool:
    """True if chunk text or title contains at least one of the given terms (case-insensitive)."""
    if not terms:
        return True
    text = (chunk.get("text") or "").lower()
    meta = chunk.get("metadata") or {}
    title = (meta.get("title") or "").lower()
    combined = f"{text} {title}"
    return any(term in combined for term in terms)


def _passes_relevance_and_keyword_checks(
    chunks: List[Dict[str, Any]],
    topic: str,
    lookup_cfg: dict,
) -> bool:
    """Return True only if chunks pass max_distance and (if enabled) keyword check."""
    if not chunks:
        return False
    max_distance = lookup_cfg.get("max_distance")
    if max_distance is not None and isinstance(max_distance, (int, float)):
        first_distance = chunks[0].get("distance")
        if first_distance is not None and first_distance > max_distance:
            return False
    if lookup_cfg.get("require_keyword_match", True):
        terms = _query_terms(topic)
        if terms:
            top_k = lookup_cfg.get("keyword_check_top_k", 3)
            top_chunks = chunks[:top_k]
            if not any(_chunk_contains_any_term(c, terms) for c in top_chunks):
                return False
    return True


def _chunks_to_items(chunks: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Deduplicate chunks by url and build list of { url, title, summary, source }."""
    by_url: Dict[str, Dict[str, Any]] = {}
    for c in chunks:
        meta = c.get("metadata") or {}
        url = meta.get("url", "")
        if not url:
            continue
        text = (c.get("text") or "").strip()
        summary = text[:SUMMARY_MAX_LEN].rstrip()
        if len(text) > SUMMARY_MAX_LEN:
            summary += "…"
        if url not in by_url:
            by_url[url] = {
                "url": url,
                "title": meta.get("title", ""),
                "summary": summary or meta.get("title", ""),
                "source": meta.get("source", ""),
            }
        else:
            # Prefer longer summary if we see another chunk for same doc
            if len(text) > len(by_url[url].get("summary", "")):
                by_url[url]["summary"] = summary or by_url[url].get("title", "")
    return list(by_url.values())


def topic_lookup(
    topic: str,
    top_k: int = 20,
    project_root: Optional[Path] = None,
) -> Dict[str, Any]:
    """
    Look up a single topic: return link + summary from DB if available,
    otherwise fetch from PubMed, MedlinePlus, and NIMH in parallel and return same shape.

    Returns:
        {
            "found_in_db": bool,
            "items": [ { "url", "title", "summary", "source" }, ... ],
            "file": str | None  # path to on-demand JSON when found_in_db is False
        }
    """
    root = project_root or get_project_root()
    setup_logger()
    log = get_logger()

    chunks: List[Dict[str, Any]] = []
    try:
        chunks = retrieve_with_distances(query=topic, top_k=top_k, project_root=root)
    except Exception as e:
        log.debug("Retrieve failed (e.g. no collection yet): %s", e)

    lookup_cfg = get_lookup_config(root)
    min_chunks = lookup_cfg["min_chunks_in_db"]
    use_db = (
        chunks
        and len(chunks) >= min_chunks
        and _passes_relevance_and_keyword_checks(chunks, topic, lookup_cfg)
    )
    if use_db:
        items = _chunks_to_items(chunks)
        return {
            "found_in_db": True,
            "items": items,
            "file": None,
        }

    # Not in DB or no collection: on-demand fetch
    items, out_path = fetch_on_demand(query=topic, project_root=root)
    # Always ingest after successful on-demand fetch: chunk, embed, add to ChromaDB
    if items:
        try:
            n = ingest_on_demand_to_db(out_path, topic=topic, project_root=root)
            log.info("Ingested %d chunks from on-demand fetch into ChromaDB", n)
        except Exception as e:
            log.warning("Failed to ingest on-demand docs into DB: %s", e)
    return {
        "found_in_db": False,
        "items": items,
        "file": str(out_path),
    }
