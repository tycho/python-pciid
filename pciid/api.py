from __future__ import annotations
from dataclasses import dataclass
from typing import Protocol, Optional, runtime_checkable, Union


@runtime_checkable
class PciDb(Protocol):
    def get_vendor_name(self, vendor_id: int) -> Optional[str]: ...
    def get_device_name(self, vendor_id: int, device_id: int) -> Optional[str]: ...
    def get_subsystem_name(
        self, vendor_id: int, device_id: int, subvendor_id: int, subdevice_id: int
    ) -> Optional[str]: ...
    def get_class_name(
        self, base: int, subclass: Optional[int] = None, prog_if: Optional[int] = None
    ) -> Optional[str]: ...
    def get_class_name_from_code(self, class_code_24bit: int) -> Optional[str]: ...
    def describe_device_best_effort(
        self, vendor_id: int, device_id: int, class_code_24bit: Optional[int]
    ) -> str: ...
    def close(self) -> None: ...


class PciDbBinary:
    def __init__(self, path: str):
        from .backends import bindb

        self._impl = bindb.PciIds(path)

    def __getattr__(self, name):
        return getattr(self._impl, name)

    def close(self) -> None:
        self._impl.close()


class PciDbText:
    def __init__(self, path: str):
        from .backends import textdb

        self._impl = textdb.PciIds(path)

    def __getattr__(self, name):
        return getattr(self._impl, name)

    def close(self) -> None:
        pass  # text loader has nothing to release


def open_db(path: Optional[str] = None) -> PciDb:
    from .backends.discovery import discover_db

    return discover_db(path)
