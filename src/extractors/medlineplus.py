"""
MedlinePlus API Extractor.

For each search term in the topic tree:
1. Call the NLM API with the search term
2. Parse XML response
3. Extract title, URL, FullSummary, snippet, mesh terms, and group
4. Strip HTML from FullSummary to get clean text
5. Deduplicate by URL (many terms return the same health topic page)
6. Save raw JSON to the configured output directory
"""
import hashlib
import json
import time
from pathlib import Path
from typing import Any, Dict, List, Optional
from xml.etree import ElementTree

import requests

from src.config import get_medlineplus_config, get_project_root, get_topic_tree
from src.extractors.base import BaseExtractor
from src.processing.cleaner import clean_text, strip_html
from src.utils.logger import get_logger, setup_logger


def _element_text(el: Optional[ElementTree.Element]) -> str:
    """Get full text from an XML element (including nested/itertext)."""
    if el is None:
        return ""
    return (el.text or "") + "".join(el.itertext()).strip()


def extract_medlineplus(
    search_term: str,
    *,
    base_url: str,
    db: str,
    retmax: int = 10,
    timeout: int = 30,
) -> list[dict]:
    """
    Query MedlinePlus API for a search term and return extracted documents.

    Returns a list of dicts with keys:
      - source: "medlineplus"
      - url: str (canonical URL of the health topic)
      - title: str
      - full_text: str (clean text, HTML stripped)
      - snippet: str
      - mesh_terms: str
      - group: str
      - search_term: str (the term that found this document)
      - content_type: "health_topic"
      - doc_id: str (MD5 of URL)
    """
    params = {
        "db": db,
        "term": search_term,
        "retmax": retmax,
    }
    response = requests.get(base_url, params=params, timeout=timeout)
    response.raise_for_status()

    root = ElementTree.fromstring(response.text)
    documents = []

    for doc in root.findall(".//document"):
        url = doc.get("url", "")

        title_el = doc.find(".//content[@name='title']")
        summary_el = doc.find(".//content[@name='FullSummary']")
        snippet_el = doc.find(".//content[@name='snippet']")
        mesh_el = doc.find(".//content[@name='mesh']")
        group_el = doc.find(".//content[@name='groupName']")

        title = _element_text(title_el)
        raw_summary = _element_text(summary_el)
        snippet = _element_text(snippet_el)
        mesh = _element_text(mesh_el)
        group = _element_text(group_el)

        full_text_clean = clean_text(raw_summary)
        if full_text_clean.strip():
            documents.append({
                "source": "medlineplus",
                "url": url,
                "title": strip_html(title),
                "full_text": full_text_clean,
                "snippet": strip_html(snippet),
                "mesh_terms": strip_html(mesh),
                "group": strip_html(group),
                "search_term": search_term,
                "content_type": "health_topic",
                "doc_id": hashlib.md5(url.encode()).hexdigest(),
            })

    return documents


class MedlinePlusExtractor(BaseExtractor):
    """Extract health topics from MedlinePlus API and save to filesystem."""

    name = "medlineplus"

    def __init__(self, project_root: Optional[Path] = None):
        self._root = project_root or get_project_root()
        self._config = get_medlineplus_config(self._root)
        self._topic_tree = get_topic_tree(self._root)
        setup_logger()
        self._log = get_logger()

    def run(
        self,
        output_dir: Optional[Path] = None,
        topic_tree: Optional[Dict] = None,
        **kwargs: Any,
    ) -> List[Dict[str, Any]]:
        """
        Extract all MedlinePlus documents for all topics in the tree.
        Deduplicates by URL across all search terms.
        Writes to output_dir (from config if not provided).
        """
        topic_tree = topic_tree or self._topic_tree
        out_dir = Path(output_dir) if output_dir else self._config["output_dir"]
        out_dir.mkdir(parents=True, exist_ok=True)

        base_url = self._config["base_url"]
        db = self._config["db"]
        retmax = self._config["retmax"]
        timeout = self._config["request_timeout_seconds"]
        delay = self._config["rate_limit_delay_seconds"]
        output_filename = self._config["output_filename"]
        save_per_topic = self._config["save_per_topic"]

        all_docs: dict[str, dict] = {}  # url -> doc (dedup)

        for topic_name, topic_config in topic_tree.items():
            terms = topic_config.get("medlineplus_terms", [])
            for term in terms:
                self._log.info("Querying: %s (topic: %s)", term, topic_name)
                try:
                    docs = extract_medlineplus(
                        term,
                        base_url=base_url,
                        db=db,
                        retmax=retmax,
                        timeout=timeout,
                    )
                    for doc in docs:
                        doc["topic"] = topic_name
                        if doc["url"] not in all_docs:
                            all_docs[doc["url"]] = doc
                        else:
                            existing = all_docs[doc["url"]]
                            existing["search_term"] = existing.get("search_term", "") + "; " + term
                except Exception as e:
                    self._log.exception("Error for term %s: %s", term, e)
                time.sleep(delay)

            if save_per_topic:
                topic_docs = [d for d in all_docs.values() if d.get("topic") == topic_name]
                if topic_docs:
                    topic_file = out_dir / f"{topic_name}.json"
                    with open(topic_file, "w", encoding="utf-8") as f:
                        json.dump(topic_docs, f, indent=2, ensure_ascii=False)
                    self._log.info("Wrote %s: %d documents", topic_file.name, len(topic_docs))

        docs_list = list(all_docs.values())

        if not save_per_topic or docs_list:
            output_file = out_dir / output_filename
            with open(output_file, "w", encoding="utf-8") as f:
                json.dump(docs_list, f, indent=2, ensure_ascii=False)
            self._log.info("Wrote %s: %d unique documents", output_file.name, len(docs_list))

        self._log.info("MedlinePlus extraction complete: %d unique documents", len(docs_list))
        return docs_list
