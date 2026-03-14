"""
PubMed E-utilities Extractor.

For each PubMed query in the topic tree:
1. ESearch: search PubMed for the query, get list of PMIDs
2. EFetch: fetch article details (title, abstract, authors, journal, year)
3. Extract abstract text as clean string; strip/format via shared cleaner
4. Filter for articles with abstracts (skip those without)
5. Save raw JSON to the configured output directory
"""
import json
import os
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

from Bio import Entrez

from src.config import get_project_root, get_pubmed_config, get_topic_tree
from src.extractors.base import BaseExtractor
from src.processing.cleaner import clean_text, strip_html
from src.utils.logger import get_logger, setup_logger


def _safe_str(val: Any) -> str:
    """Coerce to string; handle Entrez dict-like and attribute objects."""
    if val is None:
        return ""
    if isinstance(val, str):
        return val
    return str(val)


def _get_abstract(article: Any) -> str:
    """Extract abstract text from Article; handle AbstractText list with optional labels."""
    abstract_data = article.get("Abstract", {}) if hasattr(article, "get") else {}
    if not abstract_data:
        return ""
    parts = abstract_data.get("AbstractText", [])
    if not parts:
        return ""
    sections = []
    for part in parts:
        label = ""
        if hasattr(part, "attributes"):
            attrs = getattr(part, "attributes", {})
            label = _safe_str(attrs.get("Label", ""))
        text = _safe_str(part)
        if label:
            sections.append(f"{label}: {text}")
        else:
            sections.append(text)
    return "\n".join(sections)


def _get_year(article: Any, journal: Any) -> str:
    """Extract publication year from Article or Journal."""
    pub_dates = article.get("ArticleDate", []) if hasattr(article, "get") else []
    if pub_dates:
        first = pub_dates[0] if isinstance(pub_dates, list) else pub_dates
        if hasattr(first, "get"):
            y = first.get("Year", "")
            if y:
                return _safe_str(y)
    if journal and hasattr(journal, "get"):
        issue = journal.get("JournalIssue", {})
        pub_date = issue.get("PubDate", {}) if isinstance(issue, dict) else {}
        if hasattr(pub_date, "get"):
            return _safe_str(pub_date.get("Year", ""))
    return ""


def search_pubmed(
    query: str,
    *,
    retmax: int = 10,
    email: str = "",
    api_key: str = "",
) -> List[str]:
    """Search PubMed and return list of PMIDs."""
    if email:
        Entrez.email = email
    if api_key:
        Entrez.api_key = api_key
    handle = Entrez.esearch(
        db="pubmed",
        term=query,
        retmax=retmax,
        sort="relevance",
    )
    results = Entrez.read(handle)
    handle.close()
    return list(results.get("IdList", []))


def fetch_articles(
    pmids: List[str],
    email: str = "",
    api_key: str = "",
) -> List[Dict[str, Any]]:
    """Fetch article details for a list of PMIDs. Skips articles without abstracts."""
    if not pmids:
        return []
    if email:
        Entrez.email = email
    if api_key:
        Entrez.api_key = api_key

    handle = Entrez.efetch(db="pubmed", id=",".join(pmids), rettype="xml")
    raw = Entrez.read(handle)
    handle.close()

    # Entrez.read returns ListElement (list of PubmedArticle) or dict with PubmedArticleSet
    records = raw
    if hasattr(raw, "get") and isinstance(raw, dict):
        records = raw.get("PubmedArticle", raw.get("PubmedArticleSet", []))
    if not isinstance(records, list):
        records = [records] if records else []

    articles = []
    for rec in records:
        citation = rec.get("MedlineCitation", {}) if hasattr(rec, "get") else {}
        article = citation.get("Article", {}) if hasattr(citation, "get") else {}
        pmid = _safe_str(citation.get("PMID", "")) if hasattr(citation, "get") else ""

        title = _safe_str(article.get("ArticleTitle", ""))
        abstract = _get_abstract(article)
        if not abstract.strip():
            continue

        journal = article.get("Journal", {}) if hasattr(article, "get") else {}
        journal_title = _safe_str(journal.get("Title", "")) if hasattr(journal, "get") else ""
        year = _get_year(article, journal)

        author_list = article.get("AuthorList", []) if hasattr(article, "get") else []
        authors = []
        for author in author_list[:5]:
            if hasattr(author, "get"):
                last = _safe_str(author.get("LastName", ""))
                first = _safe_str(author.get("ForeName", ""))
                if last:
                    authors.append(f"{last} {first}".strip())

        mesh_list = citation.get("MeshHeadingList", []) if hasattr(citation, "get") else []
        mesh_terms = []
        for mesh in mesh_list:
            if hasattr(mesh, "get"):
                desc = mesh.get("DescriptorName", "")
                if desc:
                    mesh_terms.append(_safe_str(desc))

        full_text = f"Title: {title}\n\nAbstract:\n{abstract}"
        articles.append({
            "source": "pubmed",
            "pmid": pmid,
            "url": f"https://pubmed.ncbi.nlm.nih.gov/{pmid}/",
            "title": title,
            "full_text": full_text,
            "abstract": abstract,
            "authors": "; ".join(authors),
            "journal": journal_title,
            "year": year,
            "mesh_terms": "; ".join(mesh_terms),
            "content_type": "research_article",
            "doc_id": f"pubmed_{pmid}",
        })

    return articles


class PubMedExtractor(BaseExtractor):
    """Extract research articles from PubMed E-utilities and save to filesystem."""

    name = "pubmed"

    def __init__(self, project_root: Optional[Path] = None):
        self._root = project_root or get_project_root()
        self._config = get_pubmed_config(self._root)
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
        Extract all PubMed articles for all pubmed_queries in the topic tree.
        Deduplicates by PMID. Cleans title, abstract, full_text with shared cleaner.
        """
        topic_tree = topic_tree or self._topic_tree
        out_dir = Path(output_dir) if output_dir else self._config["output_dir"]
        out_dir.mkdir(parents=True, exist_ok=True)

        email = self._config.get("email") or os.environ.get("NCBI_EMAIL", "careconnect@example.com")
        api_key = self._config.get("api_key") or os.environ.get("NCBI_API_KEY", "")
        if api_key:
            Entrez.email = email
            Entrez.api_key = api_key
        retmax = self._config["retmax"]
        delay = self._config["rate_limit_delay_seconds"]
        output_filename = self._config["output_filename"]

        all_articles: Dict[str, Dict[str, Any]] = {}

        for topic_name, topic_config in topic_tree.items():
            queries = topic_config.get("pubmed_queries", [])
            for query in queries:
                self._log.info("Searching: %s (topic: %s)", query, topic_name)
                try:
                    pmids = search_pubmed(query, retmax=retmax, email=email, api_key=api_key)
                    time.sleep(delay)

                    arts = fetch_articles(pmids, email=email, api_key=api_key)
                    for art in arts:
                        art["topic"] = topic_name
                        art["query"] = query
                        # Clean text fields for chunking/embedding
                        art["title"] = strip_html(art.get("title", ""))
                        art["abstract"] = clean_text(art.get("abstract", ""))
                        art["full_text"] = f"Title: {art['title']}\n\nAbstract:\n{art['abstract']}"
                        art["mesh_terms"] = strip_html(art.get("mesh_terms", ""))
                        if art["pmid"] not in all_articles:
                            all_articles[art["pmid"]] = art
                except Exception as e:
                    self._log.exception("Error for query %s: %s", query, e)
                time.sleep(delay)

        articles_list = list(all_articles.values())
        output_file = out_dir / output_filename
        with open(output_file, "w", encoding="utf-8") as f:
            json.dump(articles_list, f, indent=2, ensure_ascii=False)

        self._log.info("Wrote %s: %d unique articles", output_file.name, len(articles_list))
        return articles_list
