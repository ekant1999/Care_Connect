"""
Tests for the topic lookup flow (link + summary from DB or on-demand fetch).
Uses mocks so no ChromaDB or network is required.
"""
import importlib
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch


class TestChunksToItems(unittest.TestCase):
    def test_dedupes_by_url(self):
        """When DB returns chunks, we get one item per unique url with link + summary."""
        from src.lookup.topic_lookup import _chunks_to_items
        chunks = [
            {"text": "First part of doc.", "metadata": {"url": "https://a.com/1", "title": "Doc A", "source": "pubmed"}},
            {"text": "Second part of same doc.", "metadata": {"url": "https://a.com/1", "title": "Doc A", "source": "pubmed"}},
            {"text": "Another doc.", "metadata": {"url": "https://b.com/2", "title": "Doc B", "source": "medlineplus"}},
        ]
        items = _chunks_to_items(chunks)
        self.assertEqual(len(items), 2)
        urls = {it["url"] for it in items}
        self.assertEqual(urls, {"https://a.com/1", "https://b.com/2"})
        for it in items:
            self.assertIn("url", it)
            self.assertIn("title", it)
            self.assertIn("summary", it)
            self.assertIn("source", it)

    def test_skips_empty_url(self):
        from src.lookup.topic_lookup import _chunks_to_items
        chunks = [{"text": "No url.", "metadata": {"title": "X", "source": "pubmed"}}]
        items = _chunks_to_items(chunks)
        self.assertEqual(len(items), 0)


class TestTopicLookup(unittest.TestCase):
    def test_when_in_db_returns_found_in_db_true(self):
        """If retrieve_with_distances returns chunks that pass relevance + keyword checks, found_in_db=True."""
        mock_chunks = [
            {"text": "Depression is a mood disorder.", "metadata": {"url": "https://nimh.nih.gov/depression", "title": "Depression", "source": "nimh"}, "distance": 0.5},
        ]
        lookup_cfg = {"min_chunks_in_db": 1, "max_distance": 1.0, "require_keyword_match": True, "keyword_check_top_k": 3}
        mod = importlib.import_module("src.lookup.topic_lookup")
        with patch.object(mod, "retrieve_with_distances", return_value=mock_chunks):
            with patch.object(mod, "fetch_on_demand") as mock_fetch:
                with patch.object(mod, "get_lookup_config", return_value=lookup_cfg):
                    result = mod.topic_lookup("depression", top_k=5)
        self.assertTrue(result["found_in_db"])
        self.assertIsNone(result["file"])
        self.assertEqual(len(result["items"]), 1)
        self.assertEqual(result["items"][0]["url"], "https://nimh.nih.gov/depression")
        self.assertEqual(result["items"][0]["title"], "Depression")
        self.assertEqual(result["items"][0]["source"], "nimh")
        mock_fetch.assert_not_called()

    def test_when_not_in_db_calls_fetch_on_demand(self):
        """If retrieve_with_distances returns no chunks, we call fetch_on_demand and return found_in_db=False."""
        mod = importlib.import_module("src.lookup.topic_lookup")
        on_demand_items = [
            {"url": "https://pubmed.ncbi.nlm.nih.gov/123/", "title": "Diabetes study", "summary": "Abstract...", "source": "pubmed"},
        ]
        with patch.object(mod, "retrieve_with_distances", return_value=[]):
            with patch.object(mod, "fetch_on_demand", return_value=(on_demand_items, Path("/tmp/diabetes.json"))):
                result = mod.topic_lookup("diabetes", top_k=5)
        self.assertFalse(result["found_in_db"])
        self.assertEqual(result["file"], "/tmp/diabetes.json")
        self.assertEqual(result["items"], on_demand_items)

    def test_when_retrieve_raises_falls_back_to_on_demand(self):
        """If retrieve_with_distances raises (e.g. no collection), we fall back to fetch_on_demand."""
        mod = importlib.import_module("src.lookup.topic_lookup")
        on_demand_items = [{"url": "https://example.com/1", "title": "T", "summary": "S", "source": "medlineplus"}]
        with patch.object(mod, "retrieve_with_distances", side_effect=Exception("No collection")):
            with patch.object(mod, "fetch_on_demand", return_value=(on_demand_items, Path("/tmp/x.json"))):
                result = mod.topic_lookup("diabetes", top_k=5)
        self.assertFalse(result["found_in_db"])
        self.assertEqual(len(result["items"]), 1)
        self.assertEqual(result["items"][0]["url"], "https://example.com/1")

    def test_when_relevance_fails_falls_back_to_on_demand(self):
        """If nearest chunk distance > max_distance, we do not use DB and call fetch_on_demand."""
        mock_chunks = [
            {"text": "Rabies virus.", "metadata": {"url": "https://a.com/r", "title": "Rabies", "source": "nimh"}, "distance": 1.5},
        ]
        lookup_cfg = {"min_chunks_in_db": 1, "max_distance": 0.9, "require_keyword_match": False, "keyword_check_top_k": 3}
        mod = importlib.import_module("src.lookup.topic_lookup")
        on_demand_items = [{"url": "https://b.com/bt", "title": "Brain tumor", "summary": "Info.", "source": "pubmed"}]
        with patch.object(mod, "retrieve_with_distances", return_value=mock_chunks):
            with patch.object(mod, "fetch_on_demand", return_value=(on_demand_items, Path("/tmp/brain-tumor.json"))) as mock_fetch:
                with patch.object(mod, "get_lookup_config", return_value=lookup_cfg):
                    result = mod.topic_lookup("brain tumor", top_k=5)
        self.assertFalse(result["found_in_db"])
        self.assertEqual(result["items"], on_demand_items)
        mock_fetch.assert_called_once()

    def test_when_keyword_check_fails_falls_back_to_on_demand(self):
        """If require_keyword_match is True and no top chunk contains a query term, we call fetch_on_demand."""
        mock_chunks = [
            {"text": "Rabies is a viral disease.", "metadata": {"url": "https://a.com/r", "title": "Rabies", "source": "nimh"}, "distance": 0.3},
        ]
        lookup_cfg = {"min_chunks_in_db": 1, "max_distance": 1.0, "require_keyword_match": True, "keyword_check_top_k": 3}
        mod = importlib.import_module("src.lookup.topic_lookup")
        on_demand_items = [{"url": "https://b.com/bt", "title": "Brain tumor", "summary": "Info.", "source": "pubmed"}]
        with patch.object(mod, "retrieve_with_distances", return_value=mock_chunks):
            with patch.object(mod, "fetch_on_demand", return_value=(on_demand_items, Path("/tmp/brain-tumor.json"))) as mock_fetch:
                with patch.object(mod, "get_lookup_config", return_value=lookup_cfg):
                    result = mod.topic_lookup("brain tumor", top_k=5)
        self.assertFalse(result["found_in_db"])
        self.assertEqual(result["items"], on_demand_items)
        mock_fetch.assert_called_once()


class TestGetDocumentFullText(unittest.TestCase):
    def test_returns_full_text_when_url_in_cache(self):
        """get_document_full_text loads on-demand JSON and returns full_text for the given url."""
        from src.lookup.on_demand_fetch import get_document_full_text, _slug
        topic = "diabetes"
        slug = _slug(topic)
        docs = [
            {"url": "https://pubmed.ncbi.nlm.nih.gov/999/", "title": "Study", "summary": "Short.", "full_text": "Title: Study\n\nAbstract: Full content here."},
        ]
        payload = {"query": topic, "documents": docs}
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            on_demand_dir = root / "data" / "on_demand"
            on_demand_dir.mkdir(parents=True)
            path = on_demand_dir / f"{slug}.json"
            with open(path, "w", encoding="utf-8") as f:
                json.dump(payload, f)
            text = get_document_full_text(topic, "https://pubmed.ncbi.nlm.nih.gov/999/", project_root=root)
        self.assertEqual(text, "Title: Study\n\nAbstract: Full content here.")

    def test_returns_none_when_file_missing(self):
        from src.lookup.on_demand_fetch import get_document_full_text
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            text = get_document_full_text("nonexistent", "https://example.com/1", project_root=root)
        self.assertIsNone(text)


class TestSlug(unittest.TestCase):
    def test_normalizes_topic_for_filename(self):
        from src.lookup.on_demand_fetch import _slug
        self.assertEqual(_slug("diabetes"), "diabetes")
        self.assertEqual(_slug("Type 2 Diabetes"), "type-2-diabetes")
        self.assertEqual(_slug("  anxiety  "), "anxiety")


if __name__ == "__main__":
    unittest.main()
