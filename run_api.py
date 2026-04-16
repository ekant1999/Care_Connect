"""
Start the FastAPI app from any working directory.

Usage (from anywhere):
  python /path/to/Care-Connect/run_api.py

Or from project root:
  python run_api.py
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
os.chdir(ROOT)
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "api.main:app",
        reload=True,
        reload_dirs=[str(ROOT / "api"), str(ROOT / "src")],
        host="127.0.0.1",
        port=8000,
    )
