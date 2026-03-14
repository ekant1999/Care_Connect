"""
Abstract base for all data extractors.
Each extractor fetches from a source and writes raw data to the filesystem.
"""
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any, Dict, List, Optional


class BaseExtractor(ABC):
    """Base class for source extractors. Subclasses implement run()."""

    name: str = "base"

    @abstractmethod
    def run(self, output_dir: Optional[Path] = None, **kwargs: Any) -> List[Dict[str, Any]]:
        """
        Run extraction and save raw data to the filesystem.
        :param output_dir: Override output directory; if None, use config default.
        :param kwargs: Source-specific options.
        :return: List of extracted document dicts.
        """
        pass
