"""
Structured logging for the extraction pipeline.
"""
import logging
import sys
from typing import Optional


def setup_logger(
    name: str = "care_connect",
    level: int = logging.INFO,
    format_string: Optional[str] = None,
) -> logging.Logger:
    """Configure and return a logger."""
    log = logging.getLogger(name)
    if log.handlers:
        return log
    log.setLevel(level)
    fmt = format_string or "%(asctime)s [%(levelname)s] %(name)s: %(message)s"
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(logging.Formatter(fmt))
    log.addHandler(handler)
    return log


def get_logger(name: str = "care_connect") -> logging.Logger:
    """Get the pipeline logger (use after setup_logger)."""
    return logging.getLogger(name)
