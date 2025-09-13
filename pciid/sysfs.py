# pciid/sysfs.py
from __future__ import annotations
from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterator, Optional, Dict, List
import sys
import weakref

SYSFS_DEVICES_DEFAULT = "/sys/bus/pci/devices"


def _read_hex(p: Path) -> Optional[int]:
    try:
        s = p.read_text(encoding="ascii", errors="ignore").strip()
        return int(s, 16)
    except Exception:
        return None


@dataclass(frozen=True, slots=True)
class PciAddress:
    domain: int
    bus: int
    device: int
    function: int

    def __str__(self) -> str:
        return f"{self.domain:04x}:{self.bus:02x}:{self.device:02x}.{self.function}"


# Python 3.11+ supports weakref_slot; older Pythons don’t.
if sys.version_info >= (3, 11):

    @dataclass(slots=True, weakref_slot=True)
    class PciDevice:
        bdf: PciAddress
        vendor_id: int
        device_id: int
        subvendor_id: int
        subdevice_id: int
        class_code: int
        revision: int
        numa_node: Optional[int] = None
        driver: Optional[str] = None
        iommu_group: Optional[int] = None
        link: Optional[Dict[str, str]] = None
        parent_bdf: Optional[str] = None
        _parent: Optional[weakref.ReferenceType["PciDevice"]] = field(
            default=None, repr=False
        )
        children: List[weakref.ReferenceType["PciDevice"]] = field(
            default_factory=list, repr=False
        )

        @property
        def parent(self) -> Optional["PciDevice"]:
            return self._parent() if self._parent else None

else:
    # Fallback for 3.9/3.10: drop slots so instances are weakref-able.
    @dataclass  # no slots here
    class PciDevice:
        bdf: PciAddress
        vendor_id: int
        device_id: int
        subvendor_id: int
        subdevice_id: int
        class_code: int
        revision: int
        numa_node: Optional[int] = None
        driver: Optional[str] = None
        iommu_group: Optional[int] = None
        link: Optional[Dict[str, str]] = None
        parent_bdf: Optional[str] = None
        _parent: Optional[weakref.ReferenceType["PciDevice"]] = field(
            default=None, repr=False
        )
        children: List[weakref.ReferenceType["PciDevice"]] = field(
            default_factory=list, repr=False
        )

        @property
        def parent(self) -> Optional["PciDevice"]:
            return self._parent() if self._parent else None


class SysfsEnumerator:
    def __init__(self, root: str = SYSFS_DEVICES_DEFAULT):
        self.root = Path(root)

    def scan(self) -> Dict[str, PciDevice]:
        devices: Dict[str, PciDevice] = {}
        for d in self.root.iterdir():
            name = d.name
            if ":" not in name or "." not in name:  # skip non-BDF entries
                continue
            dom = int(name[0:4], 16)
            bus = int(name[5:7], 16)
            slot = int(name[8:10], 16)
            func = int(name[11], 16)
            bdf = PciAddress(dom, bus, slot, func)

            vendor = _read_hex(d / "vendor")
            device = _read_hex(d / "device")
            cls24 = _read_hex(d / "class")
            rev = _read_hex(d / "revision")
            if vendor is None or device is None or cls24 is None:
                continue

            subven = _read_hex(d / "subsystem_vendor") or 0
            subdev = _read_hex(d / "subsystem_device") or 0

            driver = None
            pdrv = d / "driver"
            if pdrv.exists():
                driver = pdrv.resolve().name

            iommu_group = None
            try:
                iommu_group = int((d / "iommu_group").resolve().name)
            except Exception:
                pass

            link: Optional[Dict[str, str]] = {}
            for name2 in (
                "current_link_speed",
                "current_link_width",
                "max_link_speed",
                "max_link_width",
            ):
                p = d / name2
                if p.exists():
                    assert link is not None
                    link[name2] = p.read_text().strip()
            if not link:
                link = None

            # parent inference by finding the previous BDF in the resolved path chain
            parent_bdf = None
            parts = d.resolve().parts
            for part in reversed(parts):
                if part.count(":") == 2 and part.count(".") == 1 and part != name:
                    parent_bdf = part
                    break

            dev = PciDevice(
                bdf=bdf,
                vendor_id=vendor & 0xFFFF,
                device_id=device & 0xFFFF,
                subvendor_id=subven & 0xFFFF,
                subdevice_id=subdev & 0xFFFF,
                class_code=(cls24 >> 8)
                & 0xFFFF,  # 16-bit (base:sub) for storage; 24-bit is recoverable if needed
                revision=(rev or 0) & 0xFF,
                driver=driver,
                iommu_group=iommu_group,
                link=link,
                parent_bdf=parent_bdf,
            )
            devices[str(bdf)] = dev

        # stitch topology (weakrefs)
        for ibdf, idev in devices.items():
            if idev.parent_bdf and idev.parent_bdf in devices:
                parent = devices[idev.parent_bdf]
                idev._parent = weakref.ref(parent)
                parent.children.append(weakref.ref(idev))

        return devices

    # Convenience queries
    @staticmethod
    def find_by_bdf(devs: Dict[str, PciDevice], bdf: str) -> Optional[PciDevice]:
        return devs.get(bdf)

    @staticmethod
    def find_by_vendor(devs: Dict[str, PciDevice], vendor_id: int) -> list[PciDevice]:
        return [d for d in devs.values() if d.vendor_id == (vendor_id & 0xFFFF)]

    @staticmethod
    def find_by_vendor_device(
        devs: Dict[str, PciDevice], vendor_id: int, device_id: int
    ) -> list[PciDevice]:
        v = vendor_id & 0xFFFF
        di = device_id & 0xFFFF
        return [d for d in devs.values() if d.vendor_id == v and d.device_id == di]

    @staticmethod
    def sbr_affected(devs: Dict[str, PciDevice], origin: PciDevice) -> list[PciDevice]:
        """
        Devices impacted by a Secondary Bus Reset issued on the *parent bridge* of `origin`:
        - find origin.parent; all descendants under that parent are affected.
        - if origin has no parent, return [] (host bridge reset not modeled here).
        """
        parent = origin.parent
        if not parent:
            return []
        out: list[PciDevice] = []
        stack = [parent]
        seen = set()
        while stack:
            cur = stack.pop()
            if id(cur) in seen:
                continue
            seen.add(id(cur))
            # all children of cur (including nested) are affected
            for chref in cur.children:
                ch = chref()
                if not ch:
                    continue
                out.append(ch)
                stack.append(ch)
        return out
