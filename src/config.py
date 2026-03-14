"""
Load and validate pipeline and topic configuration.
All paths and extraction settings are configurable via config/pipeline.yaml and config/topics.yaml.
"""
import os
from pathlib import Path
from typing import Any, Optional

import yaml


def _load_dotenv(root: Optional[Path] = None) -> None:
    """Load .env (or .env.example if .env missing) from project root into os.environ."""
    root = root or _project_root()
    env_file = root / ".env"
    if not env_file.exists():
        env_file = root / ".env.example"
    if not env_file.exists():
        return
    with open(env_file, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            if "=" in line:
                key, _, value = line.partition("=")
                key = key.strip()
                value = value.strip().strip('"').strip("'")
                if key:
                    os.environ.setdefault(key, value)


def _project_root() -> Path:
    """Resolve project root (directory containing config/)."""
    # When running as module (python -m src.cli), cwd is typically project root
    root = Path.cwd()
    if (root / "config" / "pipeline.yaml").exists():
        return root
    # If run from src/, go up one level
    parent = root.parent
    if (parent / "config" / "pipeline.yaml").exists():
        return parent
    return root


def load_yaml(path: Path) -> dict[str, Any]:
    """Load a YAML file. Returns empty dict if file missing."""
    if not path.exists():
        return {}
    with open(path, encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


def get_pipeline_config(project_root: Optional[Path] = None) -> dict:
    """Load pipeline settings from config/pipeline.yaml."""
    root = project_root or _project_root()
    path = root / "config" / "pipeline.yaml"
    return load_yaml(path)


def get_topic_tree(project_root: Optional[Path] = None) -> dict:
    """Load topic tree from config/topics.yaml."""
    root = project_root or _project_root()
    path = root / "config" / "topics.yaml"
    data = load_yaml(path)
    return data.get("topic_tree", {})


def get_medlineplus_config(project_root: Optional[Path] = None) -> dict:
    """MedlinePlus-specific config with defaults."""
    pipeline = get_pipeline_config(project_root)
    root = project_root or _project_root()
    paths = pipeline.get("paths", {})
    data_dir = Path(paths.get("data_dir", "data"))
    raw_subdir = paths.get("raw_subdir", "raw")
    mp = pipeline.get("medlineplus", {})

    return {
        "base_url": mp.get("base_url", "https://wsearch.nlm.nih.gov/ws/query"),
        "db": mp.get("db", "healthTopics"),
        "retmax": int(mp.get("retmax", 15)),
        "rate_limit_delay_seconds": float(mp.get("rate_limit_delay_seconds", 0.75)),
        "request_timeout_seconds": int(mp.get("request_timeout_seconds", 30)),
        "output_dir": root / data_dir / raw_subdir / "medlineplus",
        "output_filename": mp.get("output_filename", "medlineplus_raw.json"),
        "save_per_topic": bool(mp.get("save_per_topic", False)),
    }


def get_pubmed_config(project_root: Optional[Path] = None) -> dict:
    """PubMed-specific config with defaults. Uses NCBI_EMAIL and NCBI_API_KEY env if set."""
    root = project_root or _project_root()
    _load_dotenv(root)
    pipeline = get_pipeline_config(project_root)
    paths = pipeline.get("paths", {})
    data_dir = Path(paths.get("data_dir", "data"))
    raw_subdir = paths.get("raw_subdir", "raw")
    pm = pipeline.get("pubmed", {})

    api_key = os.environ.get("NCBI_API_KEY", "")
    email = os.environ.get("NCBI_EMAIL", pm.get("email", "careconnect@example.com"))
    # With API key: 10 req/sec → 0.35s delay; without: 3 req/sec → 1.0s
    default_delay = 0.35 if api_key else 1.0

    return {
        "email": email,
        "api_key": api_key,
        "retmax": int(pm.get("retmax", 10)),
        "rate_limit_delay_seconds": float(pm.get("rate_limit_delay_seconds", default_delay)),
        "request_timeout_seconds": int(pm.get("request_timeout_seconds", 30)),
        "output_dir": root / data_dir / raw_subdir / "pubmed",
        "output_filename": pm.get("output_filename", "pubmed_raw.json"),
    }


def get_nimh_config(project_root: Optional[Path] = None) -> dict:
    """NIMH scraper config with defaults."""
    pipeline = get_pipeline_config(project_root)
    root = project_root or _project_root()
    paths = pipeline.get("paths", {})
    data_dir = Path(paths.get("data_dir", "data"))
    raw_subdir = paths.get("raw_subdir", "raw")
    nimh = pipeline.get("nimh", {})

    return {
        "rate_limit_delay_seconds": float(nimh.get("rate_limit_delay_seconds", 2.0)),
        "request_timeout_seconds": int(nimh.get("request_timeout_seconds", 30)),
        "user_agent": nimh.get("user_agent", "CareConnect-Research/1.0 (university research project)"),
        "output_dir": root / data_dir / raw_subdir / "nimh",
        "output_filename": nimh.get("output_filename", "nimh_raw.json"),
    }


def get_chunking_config(project_root: Optional[Path] = None) -> dict:
    """Chunking config for RAG (token size, overlap, tokenizer)."""
    pipeline = get_pipeline_config(project_root)
    ch = pipeline.get("chunking", {})
    return {
        "chunk_size": int(ch.get("chunk_size", 800)),
        "chunk_overlap": int(ch.get("chunk_overlap", 100)),
        "tokenizer": ch.get("tokenizer", "cl100k_base"),
    }


def get_embedding_config(project_root: Optional[Path] = None) -> dict:
    """Embedding model config."""
    pipeline = get_pipeline_config(project_root)
    root = project_root or _project_root()
    paths = pipeline.get("paths", {})
    data_dir = Path(paths.get("data_dir", "data"))
    emb = pipeline.get("embedding", {})
    chroma = pipeline.get("chroma", {})
    return {
        "model_name": emb.get("model_name", "all-MiniLM-L6-v2"),
        "dimension": int(emb.get("dimension", 384)),
        "batch_size": int(emb.get("batch_size", 128)),
        "chroma_persist_directory": root / chroma.get("persist_directory", "data/chroma_db"),
        "collection_name": chroma.get("collection_name", "care_connect"),
    }


def get_rag_config(project_root: Optional[Path] = None) -> dict:
    """RAG config: retrieval top_k and Ollama (DeepSeek R1) settings."""
    pipeline = get_pipeline_config(project_root)
    emb_cfg = get_embedding_config(project_root)
    rag = pipeline.get("rag", {})
    return {
        "top_k": int(rag.get("top_k", 5)),
        "ollama_base_url": rag.get("ollama_base_url", "http://localhost:11434").rstrip("/"),
        "ollama_model": rag.get("ollama_model", "deepseek-r1"),
        "ollama_timeout_seconds": int(rag.get("ollama_timeout_seconds", 120)),
        "ollama_think": bool(rag.get("ollama_think", True)),
        "rag_debug_log": bool(rag.get("rag_debug_log", False)),
        "system_prompt": rag.get(
            "system_prompt",
            "You are a helpful mental health information assistant. Use only the provided context to answer.",
        ),
        "chroma_persist_directory": emb_cfg["chroma_persist_directory"],
        "collection_name": emb_cfg["collection_name"],
        "embedding_model_name": emb_cfg["model_name"],
    }


def get_lookup_config(project_root: Optional[Path] = None) -> dict:
    """Lookup flow config: when to use DB vs on-demand (relevance + keyword checks)."""
    pipeline = get_pipeline_config(project_root)
    lookup = pipeline.get("lookup", {})
    return {
        "min_chunks_in_db": int(lookup.get("min_chunks_in_db", 1)),
        "max_distance": float(lookup.get("max_distance", 1.0)),  # only use DB if nearest chunk distance <= this (L2)
        "require_keyword_match": bool(lookup.get("require_keyword_match", True)),
        "keyword_check_top_k": int(lookup.get("keyword_check_top_k", 3)),  # check top N chunks for query terms
    }


def get_raw_data_dir(project_root: Optional[Path] = None) -> Path:
    """Directory containing raw JSON per source (medlineplus, pubmed, nimh)."""
    pipeline = get_pipeline_config(project_root)
    root = project_root or _project_root()
    paths = pipeline.get("paths", {})
    data_dir = Path(paths.get("data_dir", "data"))
    raw_subdir = paths.get("raw_subdir", "raw")
    return root / data_dir / raw_subdir


def get_project_root() -> Path:
    """Return resolved project root."""
    return _project_root()
