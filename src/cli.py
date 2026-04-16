"""
CLI entrypoint for the Care Connect data extraction pipeline.
Run: python -m src.cli extract medlineplus | pubmed | nimh
     python -m src.cli extract nimh --search "depression"
     python -m src.cli process   # chunk, embed, store in ChromaDB
"""
from pathlib import Path
from typing import Optional

import click

from src.config import get_project_root
from src.extractors.medlineplus import MedlinePlusExtractor
from src.extractors.nimh import NIMHExtractor, NimhSearchError
from src.extractors.pubmed import PubMedExtractor
from src.lookup import get_document_full_text, topic_lookup
from src.pipeline import run_process
from src.rag import rag_query
from src.utils.logger import setup_logger


@click.group()
def main() -> None:
    """Care Connect — Data extraction pipeline."""
    setup_logger()


@main.command("process")
@click.option(
    "--no-replace",
    is_flag=True,
    help="Do not replace existing ChromaDB collection (add to it).",
)
def process(no_replace: bool) -> None:
    """Load raw data, chunk, embed, and store in ChromaDB."""
    setup_logger()
    n = run_process(replace_collection=not no_replace)
    click.echo("Done. Total chunks stored: %d" % n)


@main.command("query")
@click.argument("question", nargs=-1, required=True)
@click.option("--top-k", type=int, default=None, help="Number of chunks to retrieve (default: config).")
@click.option("--show-chunks", is_flag=True, help="Print retrieved chunk snippets.")
@click.option(
    "--source",
    type=click.Choice(["medlineplus", "pubmed", "nimh"]),
    default=None,
    help="Filter retrieval to a single source.",
)
def query(question: tuple, top_k: Optional[int], show_chunks: bool, source: Optional[str]) -> None:
    """RAG query: retrieve from ChromaDB + generate answer with Ollama (DeepSeek R1)."""
    setup_logger()
    q = " ".join(question).strip()
    if not q:
        click.echo("Provide a question, e.g. python -m src.cli query 'what is depression?'")
        raise SystemExit(1)
    result = rag_query(q, top_k=top_k, source=source)
    click.echo("\nAnswer:\n")
    click.echo(result["answer"])
    if show_chunks and result.get("chunks"):
        click.echo("\n--- Retrieved chunks ---")
        for i, c in enumerate(result["chunks"][:5], 1):
            meta = c.get("metadata") or {}
            click.echo("[%d] %s | %s" % (i, meta.get("source", ""), meta.get("title", "")))
            click.echo((c.get("text") or "")[:200] + "..." if len(c.get("text") or "") > 200 else (c.get("text") or ""))
            click.echo("")


@main.command("lookup")
@click.argument("topic", nargs=-1, required=True)
@click.option("--top-k", type=int, default=20, help="Chunks to consider when checking DB (default: 20).")
def lookup(topic: tuple, top_k: int) -> None:
    """Topic lookup: return link + summary from DB, or fetch from PubMed/MedlinePlus/NIMH in parallel."""
    setup_logger()
    t = " ".join(topic).strip()
    if not t:
        click.echo("Provide a topic, e.g. python -m src.cli lookup diabetes")
        raise SystemExit(1)
    result = topic_lookup(t, top_k=top_k)
    from_db = result["found_in_db"]
    items = result.get("items") or []
    click.echo("From database: %s" % ("yes" if from_db else "no (fetched on demand)"))
    if result.get("file"):
        click.echo("Saved to: %s" % result["file"])
    click.echo("")
    if not items:
        click.echo("No results found.")
        return
    for i, it in enumerate(items, 1):
        click.echo("[%d] %s" % (i, it.get("source", "")))
        click.echo("    %s" % it.get("title", ""))
        click.echo("    %s" % it.get("url", ""))
        click.echo("    %s" % (it.get("summary", "") or ""))
        click.echo("")


@main.command("show")
@click.argument("topic", nargs=-1, required=True)
@click.option("--url", "-u", required=True, help="Document URL (from a previous lookup).")
def show(topic: tuple, url: str) -> None:
    """Show full text for a document from a previous on-demand lookup (e.g. lookup diabetes then show diabetes -u 'https://...')."""
    setup_logger()
    t = " ".join(topic).strip()
    if not t:
        click.echo("Provide the topic used in lookup, e.g. python -m src.cli show diabetes -u 'https://...'")
        raise SystemExit(1)
    text = get_document_full_text(t, url.strip())
    if text is None:
        click.echo("No cached document found for that topic and URL. Run 'lookup %s' first." % t)
        raise SystemExit(1)
    click.echo(text)


@main.command("extract")
@click.argument("source", type=click.Choice(["medlineplus", "pubmed", "nimh"]))
@click.option(
    "--output-dir",
    type=click.Path(path_type=Path),
    default=None,
    help="Override output directory for raw data (default: config paths).",
)
@click.option(
    "--search",
    "search_query",
    default=None,
    help="NIMH only: search nimh.nih.gov via DuckDuckGo and scrape the result URLs.",
)
@click.option(
    "--search-only",
    is_flag=True,
    help="NIMH only: scrape only URLs from --search, not topics.yaml.",
)
@click.option(
    "--search-max",
    type=int,
    default=None,
    help="NIMH only: max URLs from search (default: config nimh.search_max_results).",
)
def extract(
    source: str,
    output_dir: Optional[Path],
    search_query: Optional[str],
    search_only: bool,
    search_max: Optional[int],
) -> None:
    """Extract data from a source and save to the filesystem."""
    if source != "nimh" and (search_query or search_only or search_max is not None):
        raise click.BadParameter("--search / --search-only / --search-max apply only to nimh.")
    if search_only and not (search_query or "").strip():
        raise click.BadParameter("--search-only requires --search.")

    root = get_project_root()
    if source == "medlineplus":
        extractor = MedlinePlusExtractor(project_root=root)
        extractor.run(output_dir=output_dir)
    elif source == "pubmed":
        extractor = PubMedExtractor(project_root=root)
        extractor.run(output_dir=output_dir)
    elif source == "nimh":
        extractor = NIMHExtractor(project_root=root)
        try:
            extractor.run(
                output_dir=output_dir,
                search_query=(search_query or "").strip() or None,
                search_only=search_only,
                search_max=search_max,
            )
        except NimhSearchError as e:
            raise click.ClickException(str(e)) from e
    else:
        raise click.BadParameter(f"Unknown source: {source}")


if __name__ == "__main__":
    main()
