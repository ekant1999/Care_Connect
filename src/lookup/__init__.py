"""Topic lookup: link + summary from DB or on-demand fetch (PubMed, MedlinePlus, NIMH)."""
from src.lookup.on_demand_fetch import fetch_on_demand, get_document_full_text, ingest_on_demand_to_db
from src.lookup.topic_lookup import topic_lookup

__all__ = ["topic_lookup", "fetch_on_demand", "get_document_full_text", "ingest_on_demand_to_db"]
