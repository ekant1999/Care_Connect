#!/usr/bin/env bash
# Start the Care Connect API (uses project .venv).
cd "$(dirname "$0")"
exec .venv/bin/python -m uvicorn api.main:app --reload --port 8011
