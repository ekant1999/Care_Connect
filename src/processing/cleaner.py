"""
Text cleaning utility for all extraction sources (MedlinePlus, PubMed, NIMH, etc.).

Use for stripping HTML and normalizing text before chunking and embedding.
- strip_html: remove HTML/XML tags, return plain text (for short/metadata fields).
- clean_text: full normalization for body text (strip HTML, Unicode, boilerplate, whitespace).
- clean_document: apply cleaning to all text fields of a document dict.
"""
import re
import unicodedata
from typing import Any, Dict, List, Optional

from bs4 import BeautifulSoup


# Boilerplate phrases to remove from body text (e.g. site chrome, footers)
BOILERPLATE_PATTERNS = [
    r"Skip to main content",
    r"Print this page",
    r"Share on \w+",
    r"Last reviewed:.*",
    r"Page last updated:.*",
    r"Content source:.*",
    r"For more information.*contact.*",
    r"Subscribe to .* newsletter",
    r"Follow us on.*",
    r"Was this page helpful\?",
    # U.S. government site chrome (e.g. NIMH)
    r"An official website of the United States government",
    r"Here's how you know",
    r"Official websites use \.gov.*?United States\.",
    r"Secure \.gov websites use HTTPS.*?safely connected\.",
    r"LockLocked padlock icon",
    r"\.gov A \.gov website belongs to an official government organization",
]

# Document keys that contain text to clean (used by clean_document when fields=None)
DEFAULT_TEXT_FIELDS = ["full_text", "title", "snippet", "mesh_terms", "group"]


def strip_html(text: str) -> str:
    """
    Remove HTML/XML tags and return plain text.
    Use for short or metadata fields (title, snippet, mesh_terms, group).
    """
    if not text or not isinstance(text, str):
        return ""
    soup = BeautifulSoup(text, "html.parser")
    out = soup.get_text(separator=" ", strip=True)
    # Collapse multiple spaces
    out = re.sub(r"\s+", " ", out)
    return out.strip()


def clean_text(text: str) -> str:
    """
    Full cleaning for body text: strip HTML, normalize Unicode, remove boilerplate,
    normalize whitespace. Use for full_text and other long content before chunking/embedding.
    """
    if not text or not isinstance(text, str):
        return ""

    # Strip any HTML/XML
    text = BeautifulSoup(text, "html.parser").get_text(separator="\n")

    # Normalize Unicode (fancy quotes, dashes, etc.)
    text = unicodedata.normalize("NFKD", text)

    # Remove boilerplate
    for pattern in BOILERPLATE_PATTERNS:
        text = re.sub(pattern, "", text, flags=re.IGNORECASE)

    # Normalize whitespace
    text = re.sub(r"\n{3,}", "\n\n", text)
    text = re.sub(r" {2,}", " ", text)
    text = re.sub(r"\t", " ", text)

    # Normalize bullet points to a single style
    text = re.sub(r"^[\s]*[►▪▸●○◦‣⁃]\s*", "• ", text, flags=re.MULTILINE)

    # Strip leading/trailing whitespace per line
    lines = [line.strip() for line in text.split("\n")]
    text = "\n".join(lines)

    return text.strip()


def clean_document(
    doc: Dict[str, Any],
    fields: Optional[List[str]] = None,
    use_full_clean: Optional[List[str]] = None,
) -> Dict[str, Any]:
    """
    Clean all text fields in a document. Returns a new dict; does not mutate the original.

    :param doc: Document dict (e.g. from MedlinePlus, PubMed, NIMH).
    :param fields: Keys to clean. If None, uses DEFAULT_TEXT_FIELDS.
    :param use_full_clean: Keys that get clean_text(); all others in `fields` get strip_html().
                           If None, only "full_text" and "snippet" get clean_text; rest get strip_html.
    """
    doc = doc.copy()
    fields = fields or DEFAULT_TEXT_FIELDS
    if use_full_clean is None:
        use_full_clean = ["full_text", "snippet"]

    for key in fields:
        if key not in doc:
            continue
        val = doc[key]
        if not isinstance(val, str):
            continue
        if key in use_full_clean:
            doc[key] = clean_text(val)
        else:
            doc[key] = strip_html(val)

    return doc


def clean_documents(
    documents: List[Dict[str, Any]],
    fields: Optional[List[str]] = None,
    use_full_clean: Optional[List[str]] = None,
) -> List[Dict[str, Any]]:
    """Clean a list of documents. See clean_document for parameters."""
    return [
        clean_document(doc, fields=fields, use_full_clean=use_full_clean)
        for doc in documents
    ]
