# Care Connect Extraction Pipeline

This stage implements configurable data extraction + raw filesystem storage for:

- MedlinePlus
- PubMed
- NIMH
- HuggingFace datasets
- CDC YRBS statistics

Chunking, embeddings, and vector database storage are intentionally deferred.

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

## Run

```bash
python -m src.cli extract --source medlineplus
python -m src.cli run-all
```

Raw outputs are written to `data/raw/<source>/`.
