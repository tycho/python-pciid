from __future__ import annotations
from importlib import resources

try:
    from importlib.resources.abc import Traversable
except ImportError:  # pragma: no cover
    from importlib.abc import Traversable
from typing import Optional

# These are resource names we ship in the wheel/sdist.
TEXT_NAME = "pci.ids"
BIN_NAME = "pci.ids.bin"
MANIFEST_NAME = "manifest.json"  # optional; see updater script below


def text_resource() -> Traversable:
    return resources.files(__package__).joinpath(TEXT_NAME)


def bin_resource() -> Traversable:
    return resources.files(__package__).joinpath(BIN_NAME)


def manifest_resource() -> Traversable:
    return resources.files(__package__).joinpath(MANIFEST_NAME)


def bundled_text_available() -> bool:
    try:
        return text_resource().is_file()
    except Exception:  # pragma: no cover
        return False


def bundled_bin_available() -> bool:
    try:
        return bin_resource().is_file()
    except Exception:  # pragma: no cover
        return False
