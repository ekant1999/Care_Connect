"""
Process pipeline: load raw JSON → chunk → embed → store in ChromaDB.
"""
import json
from pathlib import Path
from typing import Any, List, Optional

from src.config import get_project_root, get_raw_data_dir
from src.processing.chunker import chunk_all_documents
from src.storage.chroma_store import store_in_chromadb
from src.storage.embedder import create_embeddings
from src.utils.logger import get_logger, setup_logger


# Raw JSON filenames per source (under raw_dir / source_name /)
RAW_FILES = {
    "medlineplus": "medlineplus_raw.json",
    "pubmed": "pubmed_raw.json",
    "nimh": "nimh_raw.json",
}


def load_raw_documents(raw_dir: Optional[Path] = None) -> List[dict]:
    """
    Load all raw JSON files from data/raw/{source}/ and return a single list of documents.
    Each doc must have full_text and doc_id; topic/source/url/title etc. come from extractors.
    """
    raw_dir = raw_dir or get_raw_data_dir()
    setup_logger()
    log = get_logger()
    all_docs: List[dict] = []
    for source_name, filename in RAW_FILES.items():
        path = raw_dir / source_name / filename
        if not path.exists():
            log.warning("Raw file not found: %s", path)
            continue
        with open(path, encoding="utf-8") as f:
            docs = json.load(f)
        if not isinstance(docs, list):
            docs = [docs]
        for d in docs:
            d.setdefault("source", source_name)
        all_docs.extend(docs)
        log.info("Loaded %d documents from %s", len(docs), source_name)
    log.info("Total documents loaded: %d", len(all_docs))
    return all_docs


def run_process(
    raw_dir: Optional[Path] = None,
    project_root: Optional[Path] = None,
    replace_collection: bool = True,
) -> int:
    """
    Load raw data, chunk, embed, and store in ChromaDB.
    Returns number of chunks stored.
    """
    root = project_root or get_project_root()
    raw_dir = raw_dir or get_raw_data_dir(root)

    documents = load_raw_documents(raw_dir)
    if not documents:
        raise SystemExit("No documents found in raw data. Run extract first (medlineplus, pubmed, nimh).")

    chunks = chunk_all_documents(documents, project_root=root)
    if not chunks:
        raise SystemExit("No chunks produced. Check that documents have 'full_text' and 'doc_id'.")

    embeddings = create_embeddings(chunks, project_root=root)
    if len(embeddings) != len(chunks):
        raise SystemExit("Embedding count mismatch.")

    store_in_chromadb(
        chunks,
        embeddings,
        project_root=root,
        replace=replace_collection,
    )
    return len(chunks)
