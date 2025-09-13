from __future__ import annotations
from dataclasses import dataclass
import os
import weakref
from pathlib import Path
from typing import Callable, Iterable, List, Optional, Tuple
from importlib import resources
from ..types import PciDb
from .bindb import PciDbBinary
from .textdb import PciDbText
from ..data import (
    bin_resource,
    text_resource,
    bundled_bin_available,
    bundled_text_available,
)


def _is_bin_path(path: str) -> bool:
    try:
        with open(path, "rb") as f:
            sig = f.read(4)
        # "PCIB" (0x42494350 LE). Accept a couple of variants.
        return sig in (b"PCIB", b"PCID", b"\x50\x43\x49\x42")
    except OSError:
        return False


@dataclass(frozen=True)
class Candidate:
    """Represents a potential DB source in the discovery order."""

    kind: str  # "env-bin", "env-text", "sys-bin", "bundled-bin", "sys-text", "bundled-text", "path-auto"
    ref: str  # path or resource name for debugging
    opener: Callable[[], PciDb]  # returns an opened DB instance, or raises


def _resolve_candidates(
    *,
    explicit_path: Optional[str],
    env_bin: Optional[str],
    env_text: Optional[str],
    system_bin: str,
    system_text: str,
    allow_bundled: bool,
    allow_system: bool,
) -> List[Candidate]:
    """
    Build an ordered list of candidates. Pure function -> easy to unit test:
    - Pass in env values and desired system paths
    - allow_bundled gates whether bundled files are considered
    """
    cands: List[Candidate] = []

    # Explicit path (single-candidate short path)
    if explicit_path:
        p = explicit_path

        def open_path() -> PciDb:
            return PciDbBinary(p) if _is_bin_path(p) else PciDbText(p)

        cands.append(Candidate("path-auto", p, open_path))
        return cands

    # ENV overrides (bin preferred)
    if env_bin:

        def open_env_bin(p: Optional[str] = env_bin) -> PciDb:
            if p is None:
                raise ValueError("Path cannot be None")
            if not _is_bin_path(p):
                raise ValueError(f"PCIID_BIN is not a valid binary DB: {p}")
            return PciDbBinary(p)

        cands.append(Candidate("env-bin", env_bin, open_env_bin))

    if env_text:

        def open_env_text(p: Optional[str] = env_text) -> PciDb:
            if p is None:
                raise ValueError("Path cannot be None")
            if not Path(p).exists():
                raise FileNotFoundError(f"PCIID_TEXT not found: {p}")
            return PciDbText(p)

        cands.append(Candidate("env-text", env_text, open_env_text))

    # System paths: bin → (later) text
    def open_sys_bin(p: str = system_bin) -> PciDb:
        if not Path(p).exists() or not _is_bin_path(p):
            raise FileNotFoundError(p)
        return PciDbBinary(p)

    def open_sys_text(p: str = system_text) -> PciDb:
        if not Path(p).exists():
            raise FileNotFoundError(p)
        return PciDbText(p)

    # Bundled resources: wrap importlib.resources.as_file with lifetime tied to DB.close()
    def open_bundled_bin() -> PciDb:
        res = bin_resource()
        cm = resources.as_file(res)
        p = cm.__enter__()
        db = PciDbBinary(str(p))

        # ensure resource is released on .close() and at GC
        _orig_close = db.close

        def _close_and_release() -> None:
            try:
                _orig_close()
            finally:
                cm.__exit__(None, None, None)

        db.close = _close_and_release  # type: ignore[method-assign]

        weakref.finalize(db, cm.__exit__, None, None, None)
        return db

    def open_bundled_text() -> PciDb:
        res = text_resource()
        cm = resources.as_file(res)
        p = cm.__enter__()
        db = PciDbText(str(p))

        _orig_close = db.close

        def _close_and_release() -> None:
            try:
                _orig_close()
            finally:
                cm.__exit__(None, None, None)

        db.close = _close_and_release  # type: ignore[method-assign]

        weakref.finalize(db, cm.__exit__, None, None, None)
        return db

    # Preferred order (bin > text regardless of source)
    if allow_system:
        cands.append(Candidate("sys-bin", system_bin, open_sys_bin))

    if allow_bundled and bundled_bin_available():
        cands.append(Candidate("bundled-bin", "<pkg>/pci.ids.bin", open_bundled_bin))

    if allow_system:
        cands.append(Candidate("sys-text", system_text, open_sys_text))

    if allow_bundled and bundled_text_available():
        cands.append(Candidate("bundled-text", "<pkg>/pci.ids", open_bundled_text))

    return cands


# -------- public entry --------


def discover_db(path: Optional[str]) -> PciDb:
    allow_bundled = os.getenv("PCIID_NO_BUNDLED") != "1"
    allow_system = os.getenv("PCIID_NO_SYSTEM") != "1"
    cands = _resolve_candidates(
        explicit_path=path,
        env_bin=os.getenv("PCIID_BIN"),
        env_text=os.getenv("PCIID_TEXT"),
        system_bin="/usr/share/hwdata/pci.ids.bin",
        system_text="/usr/share/hwdata/pci.ids",
        allow_bundled=allow_bundled,
        allow_system=allow_system,
    )

    last_err: Optional[Exception] = None
    for c in cands:
        try:
            return c.opener()
        except Exception as e:
            last_err = e
            continue

    raise FileNotFoundError(
        "No PCI ID database found. "
        "Set PCIID_BIN/PCIID_TEXT, install hwdata, or allow bundled resources."
    ) from last_err
