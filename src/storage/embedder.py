"""
Embedding generator using sentence-transformers (local, no API key).

Uses all-MiniLM-L6-v2 by default; runs entirely locally after model download.
"""
from pathlib import Path
from typing import Any, Dict, List, Optional

from sentence_transformers import SentenceTransformer

from src.config import get_embedding_config, get_project_root
from src.utils.logger import get_logger, setup_logger


def create_embeddings(
    chunks: List[Dict[str, Any]],
    model_name: Optional[str] = None,
    batch_size: Optional[int] = None,
    project_root: Optional[Path] = None,
) -> List[List[float]]:
    """
    Generate embeddings for all chunks using sentence-transformers.
    Returns list of embedding vectors (each list of floats).
    """
    root = project_root or get_project_root()
    cfg = get_embedding_config(root)
    model_name = model_name or cfg["model_name"]
    batch_size = batch_size or cfg["batch_size"]

    setup_logger()
    log = get_logger()
    log.info("Loading embedding model: %s", model_name)
    model = SentenceTransformer(model_name)

    texts = [c["text"] for c in chunks]
    log.info("Generating embeddings for %d chunks (batch_size=%d)...", len(texts), batch_size)
    all_embeddings = []
    for i in range(0, len(texts), batch_size):
        batch = texts[i : i + batch_size]
        batch_emb = model.encode(batch, show_progress_bar=False)
        all_embeddings.extend(batch_emb.tolist())
    log.info("Generated %d embeddings (dim=%d)", len(all_embeddings), len(all_embeddings[0]) if all_embeddings else 0)
    return all_embeddings
