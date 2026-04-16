"""Tests for exact RAG response cache."""
import pytest

from src.rag.response_cache import (
    ExactResponseCache,
    build_cache_key,
    clear_response_cache,
    get_response_cache,
    normalize_query,
)


def test_normalize_query_collapses_whitespace_and_case():
    assert normalize_query("  What IS  anxiety?  ") == "what is anxiety?"


def test_build_cache_key_same_for_equivalent_queries():
    cfg = {
        "ollama_model": "m",
        "ollama_think": True,
        "collection_name": "c",
        "embedding_model_name": "e",
        "system_prompt": "sys",
        "response_cache_version": "1",
    }
    assert build_cache_key("  HELLO ", 5, cfg) == build_cache_key("hello", 5, cfg)


def test_build_cache_key_differs_when_top_k_changes():
    cfg = {
        "ollama_model": "m",
        "ollama_think": True,
        "collection_name": "c",
        "embedding_model_name": "e",
        "system_prompt": "sys",
        "response_cache_version": "1",
    }
    assert build_cache_key("q", 5, cfg) != build_cache_key("q", 6, cfg)


def test_lru_evicts_oldest():
    c = ExactResponseCache(2)
    c.set("a", {"x": 1})
    c.set("b", {"x": 2})
    c.set("c", {"x": 3})
    assert c.get("a") is None
    assert c.get("b") == {"x": 2}
    assert c.get("c") == {"x": 3}


def test_get_returns_deep_copy():
    c = ExactResponseCache(10)
    inner = {"chunks": [{"text": "t"}]}
    c.set("k", inner)
    got = c.get("k")
    got["chunks"][0]["text"] = "mutated"
    assert c.get("k")["chunks"][0]["text"] == "t"


def test_get_response_cache_recreates_when_max_changes():
    clear_response_cache()
    a = get_response_cache(100)
    b = get_response_cache(200)
    assert a is not b
    clear_response_cache()


def test_rag_query_second_call_uses_cache(monkeypatch, tmp_path):
    """Same message should not call retrieve or ask_ollama twice."""
    from src.rag import ollama_rag as mod

    clear_response_cache()
    calls = {"retrieve": 0, "ollama": 0}

    def fake_retrieve(q, top_k=None, project_root=None, source=None):
        calls["retrieve"] += 1
        return [{"text": "ctx", "metadata": {"url": "http://x", "title": "T", "source": "nimh"}}]

    def fake_ollama(messages, **kwargs):
        calls["ollama"] += 1
        return "answer"

    monkeypatch.setattr(mod, "retrieve", fake_retrieve)
    monkeypatch.setattr(mod, "ask_ollama", fake_ollama)

    cfg = {
        "top_k": 5,
        "ollama_model": "test-model",
        "ollama_think": False,
        "rag_debug_log": False,
        "system_prompt": "sys",
        "chroma_persist_directory": tmp_path / "chroma",
        "collection_name": "col",
        "embedding_model_name": "emb",
        "response_cache_enabled": True,
        "response_cache_max_entries": 256,
        "response_cache_version": "1",
        "ollama_base_url": "http://localhost:11434",
        "ollama_timeout_seconds": 60,
    }

    def fake_get_rag_config(root=None):
        return cfg

    monkeypatch.setattr(mod, "get_rag_config", fake_get_rag_config)

    r1 = mod.rag_query("What is anxiety?", project_root=tmp_path)
    r2 = mod.rag_query("  what IS anxiety?  ", project_root=tmp_path)

    assert r1["answer"] == "answer"
    assert r2["answer"] == "answer"
    assert calls["retrieve"] == 1
    assert calls["ollama"] == 1

    clear_response_cache()
