"""
pciid — PCI ID database readers (text/binary) + sysfs enumeration/topology helpers.

Public API:
    - Protocol & factory:
        PciDb, open_db
    - Concrete DBs (if callers want to force a backend):
        PciDbText, PciDbBinary
    - Sysfs enumeration (Linux):
        SysfsEnumerator, PciAddress, PciDevice
"""

from __future__ import annotations

# Version from installed dist; falls back to dev string when run from source tree.
try:
    from importlib.metadata import version, PackageNotFoundError
except Exception:  # pragma: no cover
    version = None  # type: ignore[assignment]
    PackageNotFoundError = Exception  # type: ignore[misc]

try:  # pragma: no cover
    __version__ = version("pciid")  # the distribution name you’ll publish under
except (PackageNotFoundError, Exception):  # pragma: no cover
    __version__ = "0.0.0.dev0"

# Public API re-exports
from .api import PciDb, PciDbText, PciDbBinary, open_db
from .sysfs import SysfsEnumerator, PciAddress, PciDevice

__all__ = [
    "__version__",
    # DB protocol/factory
    "PciDb",
    "open_db",
    # Concrete DBs
    "PciDbText",
    "PciDbBinary",
    # Sysfs
    "SysfsEnumerator",
    "PciAddress",
    "PciDevice",
]
