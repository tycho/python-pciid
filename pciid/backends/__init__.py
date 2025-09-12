"""
Internal backends package.

Only `discover_db` is considered part of the importable surface here.
Backends themselves are loaded by adapters in `pciid.api` as needed.
"""

from __future__ import annotations

from .discovery import discover_db  # re-export for internal use

__all__ = ["discover_db"]
