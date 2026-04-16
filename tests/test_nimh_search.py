"""Tests for NIMH search URL discovery (Google Custom Search JSON API)."""
import pytest

from src.extractors.nimh import (
    NimhSearchError,
    _normalize_nimh_url,
    fetch_nimh_search_urls,
)


def test_normalize_nimh_url_accepts_https() -> None:
    u = _normalize_nimh_url("https://www.nimh.nih.gov/health/topics/depression")
    assert u == "https://www.nimh.nih.gov/health/topics/depression"


def test_normalize_nimh_url_upgrades_http() -> None:
    u = _normalize_nimh_url("http://www.nimh.nih.gov/health/topics/depression")
    assert u == "https://www.nimh.nih.gov/health/topics/depression"


def test_normalize_nimh_url_rejects_other_hosts() -> None:
    assert _normalize_nimh_url("https://www.nih.gov/") is None


def test_fetch_requires_api_key() -> None:
    with pytest.raises(NimhSearchError, match="GOOGLE_CSE_API_KEY"):
        fetch_nimh_search_urls(
            "depression",
            api_key="",
            cx="0200a7a0799e146ca",
            max_results=5,
            timeout=10,
        )


def test_fetch_parses_items(monkeypatch: pytest.MonkeyPatch) -> None:
    import src.extractors.nimh as nimh_mod

    class FakeResp:
        status_code = 200

        def raise_for_status(self) -> None:
            return None

        def json(self) -> dict:
            return {
                "items": [
                    {"link": "https://www.nimh.nih.gov/health/topics/depression"},
                    {"link": "https://www.nimh.nih.gov/health/topics/anxiety-disorders"},
                ]
            }

    def fake_get(url: str, params: dict, timeout: int) -> FakeResp:
        assert "customsearch" in url
        assert params["q"] == "test"
        return FakeResp()

    monkeypatch.setattr(nimh_mod.requests, "get", fake_get)
    urls = fetch_nimh_search_urls(
        "test",
        api_key="fake",
        cx="0200a7a0799e146ca",
        max_results=10,
        timeout=10,
    )
    assert len(urls) == 2
    assert "depression" in urls[0]


def test_collect_url_topic_pairs_search_only() -> None:
    from src.extractors.nimh import _collect_url_topic_pairs

    tree = {
        "depression": {"nimh_pages": ["https://www.nimh.nih.gov/health/topics/depression"]},
    }
    pairs = _collect_url_topic_pairs(
        tree,
        search_urls=["https://www.nimh.nih.gov/health/topics/anxiety-disorders"],
        search_query="anxiety",
        search_only=True,
    )
    assert len(pairs) == 1
    assert pairs[0][1] == "search:anxiety"
