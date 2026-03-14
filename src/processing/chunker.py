"""
Text chunker for RAG: token-aware recursive splitting with metadata inheritance.

Strategy:
- Chunk size: 800 tokens (~600 words), overlap: 100 tokens
- Split on: paragraph > sentence > word breaks
- Each chunk inherits metadata from the parent document
"""
from typing import Any, Dict, List, Optional

from langchain_text_splitters import RecursiveCharacterTextSplitter

from src.config import get_chunking_config, get_project_root
from src.utils.logger import get_logger, setup_logger

try:
    import tiktoken
    TIKTOKEN_AVAILABLE = True
except ImportError:
    TIKTOKEN_AVAILABLE = False


def _get_length_fn(tokenizer_name: str):
    """Return a length function (token count). Fallback to char count if tiktoken missing."""
    if not TIKTOKEN_AVAILABLE:
        return lambda t: len(t) // 4  # rough proxy for tokens
    try:
        enc = tiktoken.get_encoding(tokenizer_name)
        return lambda text: len(enc.encode(text))
    except Exception:
        return lambda t: len(t) // 4


def create_chunker(
    chunk_size: int = 800,
    chunk_overlap: int = 100,
    tokenizer_name: str = "cl100k_base",
) -> RecursiveCharacterTextSplitter:
    """Create a token-aware recursive character text splitter."""
    length_fn = _get_length_fn(tokenizer_name)
    return RecursiveCharacterTextSplitter(
        chunk_size=chunk_size,
        chunk_overlap=chunk_overlap,
        length_function=length_fn,
        separators=["\n\n", "\n", ". ", " ", ""],
        keep_separator=True,
    )


# Metadata keys to copy from doc to chunk (all must be scalar for ChromaDB)
CHUNK_META_KEYS = [
    "source", "url", "title", "topic", "content_type", "doc_id",
    "chunk_index", "total_chunks",
]
OPTIONAL_META_KEYS = ["source_year", "year", "journal", "authors", "mesh_terms", "dataset", "pmid"]


def chunk_document(
    doc: Dict[str, Any],
    chunker: RecursiveCharacterTextSplitter,
) -> List[Dict[str, Any]]:
    """
    Split a single document into chunks, each inheriting parent metadata.
    Returns list of chunk dicts ready for embedding.
    """
    full_text = doc.get("full_text", "") or ""
    if not full_text.strip():
        return []

    doc_id = doc.get("doc_id", "unknown")
    text_chunks = chunker.split_text(full_text)
    chunks = []

    for i, chunk_text in enumerate(text_chunks):
        chunk = {
            "chunk_id": f"{doc_id}_chunk_{i}",
            "chunk_index": i,
            "total_chunks": len(text_chunks),
            "text": chunk_text,
            "source": doc.get("source", ""),
            "url": doc.get("url", ""),
            "title": doc.get("title", ""),
            "topic": doc.get("topic", ""),
            "content_type": doc.get("content_type", ""),
            "doc_id": doc_id,
        }
        for key in OPTIONAL_META_KEYS:
            if key in doc and doc[key] is not None and doc[key] != "":
                chunk[key] = str(doc[key]) if not isinstance(doc[key], str) else doc[key]
        chunks.append(chunk)

    return chunks


def chunk_all_documents(
    documents: List[Dict[str, Any]],
    chunk_size: Optional[int] = None,
    chunk_overlap: Optional[int] = None,
    tokenizer_name: Optional[str] = None,
    project_root: Optional[Any] = None,
) -> List[Dict[str, Any]]:
    """Chunk all documents and return a flat list of chunks."""
    root = project_root or get_project_root()
    cfg = get_chunking_config(root)
    chunk_size = chunk_size or cfg["chunk_size"]
    chunk_overlap = chunk_overlap or cfg["chunk_overlap"]
    tokenizer_name = tokenizer_name or cfg["tokenizer"]

    chunker = create_chunker(
        chunk_size=chunk_size,
        chunk_overlap=chunk_overlap,
        tokenizer_name=tokenizer_name,
    )
    all_chunks = []
    for doc in documents:
        all_chunks.extend(chunk_document(doc, chunker))

    setup_logger()
    log = get_logger()
    log.info("Chunker created %d chunks from %d documents", len(all_chunks), len(documents))
    return all_chunks
