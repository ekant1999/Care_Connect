"""
NIMH Fact Sheet Extractor (web scraping).

For each NIMH URL in the topic tree:
1. Fetch the HTML page with a polite User-Agent and rate limit
2. Extract the main content area (article body)
3. Preserve heading structure for chunking context
4. Strip HTML and clean text via shared cleaner
5. Save raw JSON to the configured output directory
"""
import hashlib
import json
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

import requests
from bs4 import BeautifulSoup

from src.config import get_nimh_config, get_project_root, get_topic_tree
from src.extractors.base import BaseExtractor
from src.processing.cleaner import clean_text, strip_html
from src.utils.logger import get_logger, setup_logger


# NIMH uses Drupal. The gov banner is in the first main/div; real content is in article#main_content_inner.
# Try these in order so we get the article body, not the banner.
CONTENT_SELECTORS = [
    ("article", {"id": "main_content_inner"}),
    ("div", {"class_": "node__content"}),
    ("div", {"id": "block-nimhtheme-content"}),
]


def _find_content(soup: BeautifulSoup) -> Optional[Any]:
    """Find the main content container on an NIMH page (article body, not gov banner)."""
    # Prefer known main-content containers (no banner)
    for tag, kwargs in CONTENT_SELECTORS:
        el = soup.find(tag, **kwargs)
        if el and len(el.get_text(separator=" ", strip=True)) > 200:
            return el
    # Fallback: first field--name-body that looks like article content (skip banner/short blocks)
    for div in soup.find_all("div", class_=lambda c: c and "field--name-body" in c):
        text = div.get_text(separator=" ", strip=True)
        if len(text) > 400 and "An official website of the United States government" not in text[:350]:
            return div
    return None


def extract_nimh_page(
    url: str,
    *,
    timeout: int = 30,
    user_agent: str = "CareConnect-Research/1.0 (university research project)",
) -> Optional[Dict[str, Any]]:
    """
    Fetch a single NIMH page and extract clean text, preserving heading structure.
    Returns None if the page has no extractable content.
    """
    headers = {"User-Agent": user_agent}
    response = requests.get(url, headers=headers, timeout=timeout)
    response.raise_for_status()

    soup = BeautifulSoup(response.text, "html.parser")
    content = _find_content(soup)
    if not content:
        return None

    sections = []
    current_heading = "Overview"
    current_text = []

    for element in content.find_all(["h1", "h2", "h3", "h4", "p", "li"]):
        if element.name in ("h1", "h2", "h3", "h4"):
            if current_text:
                sections.append({
                    "heading": current_heading,
                    "text": "\n".join(current_text),
                })
                current_text = []
            current_heading = element.get_text(strip=True) or current_heading
        elif element.name == "p":
            text = element.get_text(strip=True)
            if text:
                current_text.append(text)
        elif element.name == "li":
            text = element.get_text(strip=True)
            if text:
                current_text.append(f"• {text}")

    if current_text:
        sections.append({"heading": current_heading, "text": "\n".join(current_text)})

    full_text_parts = [f"## {s['heading']}\n{s['text']}" for s in sections]
    full_text = "\n\n".join(full_text_parts)

    # Fallback: if we got very little, take all text from content
    if len(full_text.strip()) < 200:
        full_text = content.get_text(separator="\n", strip=True)
        if full_text:
            full_text = "\n\n".join(line.strip() for line in full_text.splitlines() if line.strip())

    if not full_text.strip():
        return None

    title_el = soup.find("h1") or soup.find("title")
    title = title_el.get_text(strip=True) if title_el else url.rstrip("/").split("/")[-1]

    return {
        "source": "nimh",
        "url": url,
        "title": strip_html(title),
        "full_text": clean_text(full_text),
        "sections": sections,
        "content_type": "fact_sheet",
        "doc_id": hashlib.md5(url.encode()).hexdigest(),
    }


class NIMHExtractor(BaseExtractor):
    """Scrape NIMH fact sheet pages and save to filesystem."""

    name = "nimh"

    def __init__(self, project_root: Optional[Path] = None):
        self._root = project_root or get_project_root()
        self._config = get_nimh_config(self._root)
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
        Fetch all NIMH pages listed in the topic tree. Deduplicates by URL.
        """
        topic_tree = topic_tree or self._topic_tree
        out_dir = Path(output_dir) if output_dir else self._config["output_dir"]
        out_dir.mkdir(parents=True, exist_ok=True)

        timeout = self._config["request_timeout_seconds"]
        delay = self._config["rate_limit_delay_seconds"]
        user_agent = self._config["user_agent"]
        output_filename = self._config["output_filename"]

        all_docs: Dict[str, Dict[str, Any]] = {}

        for topic_name, topic_config in topic_tree.items():
            urls = topic_config.get("nimh_pages", [])
            for url in urls:
                self._log.info("Fetching: %s (topic: %s)", url, topic_name)
                try:
                    doc = extract_nimh_page(
                        url,
                        timeout=timeout,
                        user_agent=user_agent,
                    )
                    if doc:
                        doc["topic"] = topic_name
                        all_docs[url] = doc
                except Exception as e:
                    self._log.exception("Error for %s: %s", url, e)
                time.sleep(delay)

        docs_list = list(all_docs.values())
        output_file = out_dir / output_filename
        with open(output_file, "w", encoding="utf-8") as f:
            json.dump(docs_list, f, indent=2, ensure_ascii=False)

        self._log.info("Wrote %s: %d fact sheets", output_file.name, len(docs_list))
        return docs_list
