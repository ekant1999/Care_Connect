"""
On-demand fetch: parallel calls to PubMed, MedlinePlus, and NIMH for a single topic.
Used when the topic is not found in the database. Saves results to data/on_demand/.
"""
import json
import re
import os
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from src.config import (
    get_project_root,
    get_medlineplus_config,
    get_nimh_config,
    get_pubmed_config,
)
from src.extractors.medlineplus import extract_medlineplus
from src.extractors.nimh import extract_nimh_page
from src.extractors.pubmed import fetch_articles, search_pubmed
from src.utils.logger import get_logger, setup_logger

# Max length for summary in link+summary response
SUMMARY_MAX_LEN = 300


def _slug(topic: str) -> str:
    """Normalize topic to a filename-safe slug."""
    s = topic.strip().lower()
    s = re.sub(r"[^\w\s-]", "", s)
    s = re.sub(r"[-\s]+", "-", s).strip("-")
    return s or "topic"


def _fetch_pubmed(query: str, project_root: Optional[Path] = None) -> List[Dict[str, Any]]:
    """Fetch PubMed results for query. Returns list of doc dicts (url, title, summary, full_text, doc_id, source)."""
    root = project_root or get_project_root()
    cfg = get_pubmed_config(root)
    email = cfg.get("email") or os.environ.get("NCBI_EMAIL", "careconnect@example.com")
    api_key = cfg.get("api_key") or os.environ.get("NCBI_API_KEY", "")
    retmax = min(cfg.get("retmax", 10), 15)
    docs: List[Dict[str, Any]] = []
    try:
        from Bio import Entrez
        if email:
            Entrez.email = email
        if api_key:
            Entrez.api_key = api_key
        pmids = search_pubmed(query, retmax=retmax, email=email, api_key=api_key)
        if not pmids:
            return docs
        articles = fetch_articles(pmids, email=email, api_key=api_key)
        for art in articles:
            summary = (art.get("abstract") or "")[:SUMMARY_MAX_LEN]
            if len(art.get("abstract") or "") > SUMMARY_MAX_LEN:
                summary = summary.rstrip() + "…"
            docs.append({
                "source": "pubmed",
                "url": art.get("url", ""),
                "title": art.get("title", ""),
                "summary": summary or art.get("title", ""),
                "full_text": art.get("full_text", ""),
                "doc_id": art.get("doc_id", ""),
            })
    except Exception as e:
        setup_logger()
        get_logger().warning("On-demand PubMed fetch failed for %r: %s", query, e)
    return docs


def _fetch_medlineplus(query: str, project_root: Optional[Path] = None) -> List[Dict[str, Any]]:
    """Fetch MedlinePlus results for query. Returns same doc shape."""
    root = project_root or get_project_root()
    cfg = get_medlineplus_config(root)
    docs: List[Dict[str, Any]] = []
    try:
        raw = extract_medlineplus(
            query,
            base_url=cfg["base_url"],
            db=cfg["db"],
            retmax=min(cfg.get("retmax", 15), 15),
            timeout=cfg.get("request_timeout_seconds", 30),
        )
        for d in raw:
            summary = (d.get("snippet") or d.get("full_text", ""))[:SUMMARY_MAX_LEN]
            if len(d.get("full_text") or "") > SUMMARY_MAX_LEN:
                summary = summary.rstrip() + "…"
            docs.append({
                "source": "medlineplus",
                "url": d.get("url", ""),
                "title": d.get("title", ""),
                "summary": summary or d.get("title", ""),
                "full_text": d.get("full_text", ""),
                "doc_id": d.get("doc_id", ""),
            })
    except Exception as e:
        setup_logger()
        get_logger().warning("On-demand MedlinePlus fetch failed for %r: %s", query, e)
    return docs


def _fetch_nimh(query: str, project_root: Optional[Path] = None) -> List[Dict[str, Any]]:
    """Try NIMH health topic page for query (e.g. .../health/topics/depression). Returns same doc shape."""
    root = project_root or get_project_root()
    cfg = get_nimh_config(root)
    slug = _slug(query)
    # NIMH topic URLs are like https://www.nimh.nih.gov/health/topics/depression
    url = f"https://www.nimh.nih.gov/health/topics/{slug}"
    docs: List[Dict[str, Any]] = []
    try:
        doc = extract_nimh_page(
            url,
            timeout=cfg.get("request_timeout_seconds", 30),
            user_agent=cfg.get("user_agent", "CareConnect-Research/1.0"),
        )
        if doc:
            full_text = doc.get("full_text", "")
            summary = full_text[:SUMMARY_MAX_LEN].rstrip()
            if len(full_text) > SUMMARY_MAX_LEN:
                summary += "…"
            docs.append({
                "source": "nimh",
                "url": doc.get("url", ""),
                "title": doc.get("title", ""),
                "summary": summary or doc.get("title", ""),
                "full_text": full_text,
                "doc_id": doc.get("doc_id", ""),
            })
    except Exception as e:
        setup_logger()
        get_logger().debug("On-demand NIMH fetch failed for %r (may be 404): %s", query, e)
    return docs


def fetch_on_demand(
    query: str,
    project_root: Optional[Path] = None,
) -> tuple[List[Dict[str, Any]], Path]:
    """
    Fetch from PubMed, MedlinePlus, and NIMH in parallel for the given topic.
    Saves full results to data/on_demand/{slug}.json.
    Returns (items, path) where items = [{ "url", "title", "summary", "source" }, ...].
    """
    root = project_root or get_project_root()
    setup_logger()
    log = get_logger()
    slug = _slug(query)
    on_demand_dir = root / "data" / "on_demand"
    on_demand_dir.mkdir(parents=True, exist_ok=True)
    out_path = on_demand_dir / f"{slug}.json"

    def run_pubmed() -> List[Dict[str, Any]]:
        return _fetch_pubmed(query, root)

    def run_medlineplus() -> List[Dict[str, Any]]:
        return _fetch_medlineplus(query, root)

    def run_nimh() -> List[Dict[str, Any]]:
        return _fetch_nimh(query, root)

    all_docs: List[Dict[str, Any]] = []
    with ThreadPoolExecutor(max_workers=3) as executor:
        futures = {
            executor.submit(run_pubmed): "pubmed",
            executor.submit(run_medlineplus): "medlineplus",
            executor.submit(run_nimh): "nimh",
        }
        for future in as_completed(futures):
            source = futures[future]
            try:
                docs = future.result()
                all_docs.extend(docs)
                log.info("On-demand %s: %d results for %r", source, len(docs), query)
            except Exception as e:
                log.warning("On-demand %s failed: %s", source, e)

    # Deduplicate by url
    seen_urls: set[str] = set()
    unique_docs: List[Dict[str, Any]] = []
    for d in all_docs:
        u = d.get("url", "")
        if u and u not in seen_urls:
            seen_urls.add(u)
            unique_docs.append(d)

    # Build response items (link + summary only)
    items = [
        {
            "url": d.get("url", ""),
            "title": d.get("title", ""),
            "summary": d.get("summary", ""),
            "source": d.get("source", ""),
        }
        for d in unique_docs
    ]

    # Save full payload for "tell me more" later
    payload = {
        "query": query,
        "fetched_at": datetime.now(timezone.utc).isoformat(),
        "documents": unique_docs,
    }
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2, ensure_ascii=False)
    log.info("Saved on-demand results to %s (%d documents)", out_path, len(unique_docs))

    # Append to respective raw source files (data/raw/pubmed/, medlineplus/, nimh/)
    _append_on_demand_to_raw(unique_docs, query, root, log)

    return items, out_path


def _append_on_demand_to_raw(
    documents: List[Dict[str, Any]],
    query: str,
    project_root: Path,
    log: Any,
) -> None:
    """
    Append on-demand documents to the respective raw JSON per source
    (data/raw/pubmed/pubmed_raw.json, medlineplus/medlineplus_raw.json, nimh/nimh_raw.json).
    Deduplicates by doc_id. Adds topic and content_type so pipeline/chunker can use them.
    """
    if not documents:
        return
    # Group by source
    by_source: Dict[str, List[Dict[str, Any]]] = {}
    for doc in documents:
        src = doc.get("source", "")
        if src not in ("pubmed", "medlineplus", "nimh"):
            continue
        by_source.setdefault(src, []).append(doc)

    config_getters = {
        "pubmed": get_pubmed_config,
        "medlineplus": get_medlineplus_config,
        "nimh": get_nimh_config,
    }
    for source, docs in by_source.items():
        try:
            cfg = config_getters[source](project_root)
            out_dir = Path(cfg["output_dir"])
            out_dir.mkdir(parents=True, exist_ok=True)
            out_file = out_dir / cfg["output_filename"]

            # Load existing if present
            existing_list: List[Dict[str, Any]] = []
            if out_file.exists():
                with open(out_file, encoding="utf-8") as f:
                    raw = json.load(f)
                existing_list = raw if isinstance(raw, list) else [raw]
            existing_ids = {d.get("doc_id") for d in existing_list if d.get("doc_id")}

            # Add topic and content_type; append only new doc_ids
            added = 0
            for d in docs:
                doc_id = d.get("doc_id")
                if not doc_id or doc_id in existing_ids:
                    continue
                d = {**d, "topic": query, "content_type": _CONTENT_TYPE_BY_SOURCE.get(source, "article")}
                existing_list.append(d)
                existing_ids.add(doc_id)
                added += 1
            if added == 0:
                continue
            with open(out_file, "w", encoding="utf-8") as f:
                json.dump(existing_list, f, indent=2, ensure_ascii=False)
            log.info("Appended %d on-demand docs to %s/%s", added, source, out_file.name)
        except Exception as e:
            log.warning("Failed to append on-demand docs to raw %s: %s", source, e)


def get_document_full_text(
    topic: str,
    url: str,
    project_root: Optional[Path] = None,
) -> Optional[str]:
    """
    Load on-demand cache for the topic and return full_text for the document with the given url.
    Returns None if file not found or url not in cache.
    """
    root = project_root or get_project_root()
    slug = _slug(topic)
    path = root / "data" / "on_demand" / f"{slug}.json"
    if not path.exists():
        return None
    with open(path, encoding="utf-8") as f:
        data = json.load(f)
    for doc in data.get("documents", []):
        if (doc.get("url") or "").strip() == url.strip():
            return doc.get("full_text")
    return None


# content_type by source (for chunker/Chromadb)
_CONTENT_TYPE_BY_SOURCE = {
    "pubmed": "research_article",
    "medlineplus": "health_topic",
    "nimh": "fact_sheet",
}


def ingest_on_demand_to_db(
    on_demand_json_path: Path,
    topic: str,
    project_root: Optional[Path] = None,
) -> int:
    """
    Chunk, embed, and add on-demand documents to ChromaDB (append, no replace).
    Loads documents from the JSON file written by fetch_on_demand.
    Returns the number of chunks added.
    """
    root = project_root or get_project_root()
    setup_logger()
    log = get_logger()

    if not on_demand_json_path.exists():
        log.warning("On-demand file not found: %s", on_demand_json_path)
        return 0

    with open(on_demand_json_path, encoding="utf-8") as f:
        data = json.load(f)
    documents = data.get("documents", [])
    if not documents:
        log.info("No documents to ingest from %s", on_demand_json_path)
        return 0

    # Normalize to pipeline doc shape (chunker expects topic, content_type, full_text, doc_id, etc.)
    for doc in documents:
        doc.setdefault("topic", topic)
        doc.setdefault("content_type", _CONTENT_TYPE_BY_SOURCE.get(doc.get("source", ""), "article"))

    from src.processing.chunker import chunk_all_documents
    from src.storage.embedder import create_embeddings
    from src.storage.chroma_store import store_in_chromadb

    chunks = chunk_all_documents(documents, project_root=root)
    if not chunks:
        log.warning("No chunks produced from on-demand documents")
        return 0

    embeddings = create_embeddings(chunks, project_root=root)
    if len(embeddings) != len(chunks):
        log.error("Embedding count mismatch, skipping ChromaDB add")
        return 0

    store_in_chromadb(
        chunks,
        embeddings,
        project_root=root,
        replace=False,
    )
    log.info("Ingested %d chunks from on-demand fetch into ChromaDB", len(chunks))
    return len(chunks)
