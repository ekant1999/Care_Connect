"""
NIMH Fact Sheet Extractor (web scraping).

For each NIMH URL in the topic tree:
1. Fetch the HTML page with a polite User-Agent and rate limit
2. Extract the main content area (article body)
3. Preserve heading structure for chunking context
4. Strip HTML and clean text via shared cleaner
5. Save raw JSON to the configured output directory

Search-driven extraction uses DuckDuckGo HTML search (site:nimh.nih.gov)
to discover page URLs — no API key required.
"""
import hashlib
import json
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
from urllib.parse import urlparse

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

# NIMH listing pages that enumerate all topics and publications
NIMH_LISTING_PAGES = [
    "https://www.nimh.nih.gov/health/topics",
    "https://www.nimh.nih.gov/health/publications",
    "https://www.nimh.nih.gov/health/statistics",
]


class NimhSearchError(Exception):
    """Raised when NIMH search cannot return URLs."""


def _normalize_nimh_url(url: str) -> Optional[str]:
    """Keep only https URLs on www.nimh.nih.gov, strip fragments."""
    if not url or not url.strip():
        return None
    u = url.strip().split("#")[0]
    try:
        parsed = urlparse(u)
    except Exception:
        return None
    host = (parsed.netloc or "").lower()
    if "nimh.nih.gov" not in host:
        return None
    if parsed.scheme not in ("http", "https"):
        return None
    if parsed.scheme == "http":
        return u.replace("http://", "https://", 1)
    return u


def _listing_links(listing_url: str, *, timeout: int, user_agent: str) -> List[Tuple[str, str]]:
    """
    Fetch a NIMH listing page and return (link_text, full_url) pairs for
    individual content pages (paths with at least 3 segments under /health/).
    """
    headers = {"User-Agent": user_agent}
    resp = requests.get(listing_url, headers=headers, timeout=timeout)
    resp.raise_for_status()
    soup = BeautifulSoup(resp.text, "html.parser")
    pairs: List[Tuple[str, str]] = []
    seen: set = set()
    for a in soup.find_all("a", href=True):
        href = (a["href"] or "").strip().split("#")[0]
        if not href:
            continue
        if href.startswith("/"):
            href = "https://www.nimh.nih.gov" + href
        url = _normalize_nimh_url(href)
        if not url or url in seen:
            continue
        # Keep only individual content pages (not the listing pages themselves)
        path = urlparse(url).path.rstrip("/")
        segments = [s for s in path.split("/") if s]
        if len(segments) < 3:
            continue
        seen.add(url)
        pairs.append((a.get_text(strip=True), url))
    return pairs


def fetch_nimh_search_urls(
    query: str,
    *,
    max_results: int,
    timeout: int,
    user_agent: str = "CareConnect-Research/1.0 (university research project)",
) -> List[str]:
    """
    Discover NIMH page URLs matching a query by scraping NIMH's own listing
    pages (/health/topics, /health/publications, /health/statistics) and
    filtering by keyword match in the link text or URL slug. No API key needed.
    """
    q = (query or "").strip()
    if not q:
        return []

    cap = max(1, min(int(max_results), 100))
    keywords = [w.lower() for w in q.split() if len(w) > 2]

    collected: List[str] = []
    seen: set = set()

    for listing in NIMH_LISTING_PAGES:
        try:
            pairs = _listing_links(listing, timeout=timeout, user_agent=user_agent)
        except Exception:
            continue
        for text, url in pairs:
            if url in seen:
                continue
            slug = urlparse(url).path.lower()
            haystack = (text + " " + slug).lower()
            if any(kw in haystack for kw in keywords):
                seen.add(url)
                collected.append(url)
            if len(collected) >= cap:
                break
        if len(collected) >= cap:
            break

    if not collected:
        raise NimhSearchError(
            "No NIMH pages found matching %r in topics, publications, or statistics listings." % q
        )

    return collected[:cap]


def _collect_url_topic_pairs(
    topic_tree: Dict[str, Any],
    *,
    search_urls: Optional[List[str]],
    search_query: Optional[str],
    search_only: bool,
) -> List[Tuple[str, str]]:
    """Build ordered (url, topic_label) list; topic tree first unless search_only."""
    pairs: List[Tuple[str, str]] = []
    seen = set()

    if not search_only:
        for topic_name, topic_config in topic_tree.items():
            for url in topic_config.get("nimh_pages", []) or []:
                if url and url not in seen:
                    seen.add(url)
                    pairs.append((url, topic_name))

    if search_query and search_urls:
        label = "search:%s" % search_query.strip()
        for url in search_urls:
            if url and url not in seen:
                seen.add(url)
                pairs.append((url, label))

    return pairs


def _find_content(soup: BeautifulSoup) -> Optional[Any]:
    """Find the main content container on an NIMH page (article body, not gov banner)."""
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
        *,
        search_query: Optional[str] = None,
        search_only: bool = False,
        search_max: Optional[int] = None,
        **kwargs: Any,
    ) -> List[Dict[str, Any]]:
        """
        Fetch all NIMH pages listed in the topic tree. Deduplicates by URL.
        Optionally merge or replace with URLs from DuckDuckGo site search.
        """
        topic_tree = topic_tree or self._topic_tree
        out_dir = Path(output_dir) if output_dir else self._config["output_dir"]
        out_dir.mkdir(parents=True, exist_ok=True)

        timeout = self._config["request_timeout_seconds"]
        delay = self._config["rate_limit_delay_seconds"]
        user_agent = self._config["user_agent"]
        output_filename = self._config["output_filename"]

        search_urls: Optional[List[str]] = None
        sq = (search_query or "").strip()
        if sq:
            max_r = int(search_max if search_max is not None else self._config["search_max_results"])
            search_urls = fetch_nimh_search_urls(sq, max_results=max_r, timeout=timeout, user_agent=user_agent)
            self._log.info("Search %r returned %d URL(s)", sq, len(search_urls))

        url_topic_pairs = _collect_url_topic_pairs(
            topic_tree,
            search_urls=search_urls,
            search_query=sq if sq else None,
            search_only=search_only,
        )
        if not url_topic_pairs:
            self._log.warning("No NIMH URLs to fetch (empty topic list and search).")

        all_docs: Dict[str, Dict[str, Any]] = {}

        for url, topic_name in url_topic_pairs:
            self._log.info("Fetching: %s (topic: %s)", url, topic_name)
            try:
                doc = extract_nimh_page(url, timeout=timeout, user_agent=user_agent)
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
