# Care Connect Extraction Pipeline

This stage implements configurable data extraction + raw filesystem storage for:

- MedlinePlus
- PubMed
- NIMH
- HuggingFace datasets
- CDC YRBS statistics

Chunking, embeddings, and vector database storage (ChromaDB) are used for RAG and for the topic lookup flow.

## Setup

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e .
```

## Config

Edit `config/topics.yaml` to control:

- topic tree and search fan-out
- HuggingFace datasets + field mapping
- CDC statistics records

Pipeline settings (paths, API limits, chunking, ChromaDB, RAG) are in `config/pipeline.yaml`.

---

## Run

### Bulk extract and process (topic tree)

Extract from each source, then chunk and load into ChromaDB:

```bash
python -m src.cli extract medlineplus
python -m src.cli extract pubmed
python -m src.cli extract nimh
python -m src.cli process
```

Raw outputs are written to `data/raw/<source>/` (e.g. `data/raw/pubmed/pubmed_raw.json`). After `process`, the vector DB is at `data/chroma_db/`.

### RAG query (answer from knowledge base)

Ask a question; the app retrieves relevant chunks from ChromaDB and generates an answer with Ollama (DeepSeek R1):

```bash
python -m src.cli query "what is depression?"
python -m src.cli query "what is depression?" --show-chunks
```

---

## Topic lookup flow (link + summary)

Use **lookup** when you want results as **links and short summaries** for a topic (e.g. "diabetes", "rectal disorders"), instead of a single RAG answer.

### How it works

1. **If the topic is already in the database:**  
   Results are taken from ChromaDB and shown as link + summary (source, title, URL, snippet).  
   **Matching:** We use the DB only when (a) the nearest chunk is within a **relevance threshold** (`max_distance` in config), and (b) at least one of the top chunks **contains a query keyword** (optional, `require_keyword_match`). This avoids returning unrelated hits (e.g. “brain tumor” → rabies).

2. **If the topic is not in the database:**  
   The app fetches from **PubMed**, **MedlinePlus**, and **NIMH** in parallel, then:
   - Saves the full payload to `data/on_demand/<topic-slug>.json`
   - Appends documents to the respective raw files: `data/raw/pubmed/`, `data/raw/medlineplus/`, `data/raw/nimh/`
   - Chunks the new documents, embeds them, and adds them to ChromaDB (append, no replace)
   - Returns link + summary for each result

So: **extract full text via API → store in raw + on_demand → chunk and add to DB → show summary first.**

### Commands

**Look up a topic (link + summary):**

```bash
python -m src.cli lookup diabetes
python -m src.cli lookup "rectal disorders"
```

Output shows whether results came from the database or from an on-demand fetch, then lists each result with source, title, URL, and a short summary.

**Show full text for one document (after an on-demand lookup):**

```bash
python -m src.cli show diabetes -u "https://pubmed.ncbi.nlm.nih.gov/12345/"
```

Use the same topic string you used in `lookup` and the URL of the document you want to read in full. The full text is read from the cached on-demand file for that topic.
