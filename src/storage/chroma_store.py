"""
ChromaDB vector store: persist chunks and embeddings with metadata.
"""
import math
from pathlib import Path
from typing import Any, Dict, List, Optional

import chromadb
from chromadb.config import Settings

from src.config import get_embedding_config, get_project_root
from src.utils.logger import get_logger, setup_logger

# ChromaDB metadata values must be str, int, float, or bool
META_KEYS = [
    "source", "url", "title", "topic", "content_type", "doc_id",
    "chunk_index", "total_chunks",
]
OPTIONAL_META_KEYS = ["source_year", "year", "journal", "authors", "mesh_terms", "dataset", "pmid"]


def _chunk_to_metadata(chunk: Dict[str, Any]) -> Dict[str, Any]:
    """Convert chunk dict to ChromaDB-safe metadata (scalars only)."""
    meta = {}
    for key in META_KEYS:
        val = chunk.get(key)
        if val is not None and val != "":
            if isinstance(val, (str, int, float, bool)):
                meta[key] = val
            else:
                meta[key] = str(val)
    for key in OPTIONAL_META_KEYS:
        val = chunk.get(key)
        if val is not None and val != "":
            meta[key] = str(val) if not isinstance(val, (str, int, float, bool)) else val
    return meta


def store_in_chromadb(
    chunks: List[Dict[str, Any]],
    embeddings: List[List[float]],
    persist_directory: Optional[Path] = None,
    collection_name: Optional[str] = None,
    replace: bool = True,
    project_root: Optional[Path] = None,
) -> None:
    """
    Store chunks and embeddings in ChromaDB with full metadata.
    If replace=True, deletes existing collection and recreates it.
    """
    root = project_root or get_project_root()
    cfg = get_embedding_config(root)
    persist_directory = Path(persist_directory or cfg["chroma_persist_directory"])
    collection_name = collection_name or cfg["collection_name"]

    persist_directory.mkdir(parents=True, exist_ok=True)
    client = chromadb.PersistentClient(path=str(persist_directory))

    if replace:
        try:
            client.delete_collection(collection_name)
        except Exception:
            pass
        collection = client.create_collection(
            name=collection_name,
            metadata={"description": "Care Connect mental health knowledge base"},
        )
    else:
        collection = client.get_or_create_collection(
            name=collection_name,
            metadata={"description": "Care Connect mental health knowledge base"},
        )

    setup_logger()
    log = get_logger()
    chroma_batch = 5000
    total_batches = math.ceil(len(chunks) / chroma_batch)

    for batch_idx in range(total_batches):
        start = batch_idx * chroma_batch
        end = min(start + chroma_batch, len(chunks))
        batch_chunks = chunks[start:end]
        batch_embeddings = embeddings[start:end]

        ids = [c["chunk_id"] for c in batch_chunks]
        documents = [c["text"] for c in batch_chunks]
        metadatas = [_chunk_to_metadata(c) for c in batch_chunks]

        collection.add(
            ids=ids,
            documents=documents,
            embeddings=batch_embeddings,
            metadatas=metadatas,
        )
        log.info("ChromaDB: inserted batch %d/%d (%d chunks)", batch_idx + 1, total_batches, len(ids))

    log.info("ChromaDB: total stored %d chunks in '%s'", collection.count(), collection_name)
