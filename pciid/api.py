from __future__ import annotations
from typing import Optional
from .backends.bindb import PciDbBinary
from .backends.textdb import PciDbText
from .types import PciDb


def open_db(path: Optional[str] = None) -> PciDb:
    from .backends.discovery import discover_db

    return discover_db(path)


__all__ = ["PciDb", "PciDbBinary", "PciDbText", "open_db"]
