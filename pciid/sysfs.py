# pciid/sysfs.py
from __future__ import annotations
from dataclasses import dataclass, field
from enum import Flag, IntFlag, auto
from pathlib import Path
from typing import Dict, Iterable, Iterator, Optional, List, Tuple
import sys
import weakref

SYSFS_DEVICES_DEFAULT = "/sys/bus/pci/devices"

ROM_ADDRESS_MASK = ~0x7FF


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
        resource: Optional[List[ResourceEntry]]
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
        resource: Optional[List[ResourceEntry]]
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


class IOResourceFlag(IntFlag):
    # fmt: off
    # Generic Linux resource flags (subset that commonly appears in PCI sysfs)
    BUS_SPECIFIC_BITS = 0x000000ff  # low byte: BAR attributes (PCI-only meaning)
    IO                = 0x00000100
    MEM               = 0x00000200
    IRQ               = 0x00000400
    DMA               = 0x00000800

    PREFETCH          = 0x00002000  # “no side effects”
    READONLY          = 0x00004000  # often true for ROM

    RANGELENGTH       = 0x00010000  # internal alignment/rangelength encodings
    SIZEALIGN         = 0x00040000

    MEM_64            = 0x00100000  # 64-bit MMIO window
    WINDOW            = 0x00200000  # forwarded by a bridge
    MUXED             = 0x00400000  # software-muxed
    # fmt: on


class PciRomAttr(Flag):
    # fmt: off
    ROM_ENABLE      = 0x01
    ROM_SHADOW      = 0x02

    PCI_FIXED       = 0x10
    PCI_EA_BEI      = 0x20
    # fmt: on

    @classmethod
    def from_flags(cls, flags: int) -> "PciRomAttr":
        return PciRomAttr(flags & IOResourceFlag.BUS_SPECIFIC_BITS)


class PciBarAttr(Flag):
    # fmt: off
    # Interpretation of the low 8 bits (PCI BAR low bits mirrored here)
    # If bit0 set => I/O BAR. If clear => Memory BAR; bits 2:1 select type.
    IO_SPACE        = 0x01  # BAR bit0 = 1 => I/O port BAR

    # For memory BARs (bit0 == 0):
    MEM_TYPE_32     = 0x00  # bits 2:1 = 00
    MEM_TYPE_1M     = 0x02  # bits 2:1 = 01 (legacy < 1MB)
    MEM_TYPE_64     = 0x04  # bits 2:1 = 10
    PREFETCH        = 0x08  # bit3
    # fmt: on

    @classmethod
    def from_flags(cls, flags: int) -> "PciBarAttr":
        return PciBarAttr(flags & IOResourceFlag.BUS_SPECIFIC_BITS)


@dataclass(frozen=True)
class ResourceEntry:
    index: int
    start: int
    end: int
    flags: int

    @property
    def size(self) -> int:
        # sysfs ‘end’ is inclusive; an unused slot is all zeros
        if self.start == 0 and self.end == 0:
            return 0
        return (self.end - self.start) + 1

    @property
    def io_flags(self) -> IOResourceFlag:
        return IOResourceFlag(self.flags)

    @property
    def rom_attr(self) -> PciRomAttr:
        return PciRomAttr.from_flags(self.flags)

    @property
    def bar_attr(self) -> PciBarAttr:
        return PciBarAttr.from_flags(self.flags)

    @property
    def is_unused(self) -> bool:
        return self.start == 0 and self.end == 0 and self.flags == 0

    @property
    def is_io(self) -> bool:
        # Prefer generic flag; fall back to BAR low bit if needed
        if self.io_flags & IOResourceFlag.IO:
            return True
        return bool(self.bar_attr & PciBarAttr.IO_SPACE)

    @property
    def is_rom(self) -> bool:
        return self.index == 6

    @property
    def is_mem(self) -> bool:
        if self.io_flags & IOResourceFlag.MEM:
            return True
        return not self.is_io and self.size > 0

    @property
    def is_prefetchable(self) -> bool:
        if self.io_flags & IOResourceFlag.PREFETCH:
            return True
        return bool(self.bar_attr & PciBarAttr.PREFETCH)

    @property
    def is_64bit(self) -> bool:
        # Either generic MEM_64 or BAR’s 64-bit type
        if self.io_flags & IOResourceFlag.MEM_64:
            return True
        ba = self.bar_attr
        return (not (ba & PciBarAttr.IO_SPACE)) and (ba & PciBarAttr.MEM_TYPE_64)

    def _fmt_addr(self) -> str:
        return f"{self.start:0x}"

    @staticmethod
    def _fmt_size(n: int) -> str:
        # Match lspci-ish units: K/M/G (binary)
        if n >= 1 << 30 and (n % (1 << 30) == 0):
            return f"{n >> 30}G"
        if n >= 1 << 20 and (n % (1 << 20) == 0):
            return f"{n >> 20}M"
        if n >= 1 << 10 and (n % (1 << 10) == 0):
            return f"{n >> 10}K"
        return f"{n}"

    def to_dict(self) -> Dict[str, str]:
        return {
            "index": self.index,
            "start": self.start,
            "end": self.end,
            "flags": self.flags,
        }

    def __str__(self) -> str:
        if self.is_unused:
            return f"Region {self.index}: Unused"

        size_s = self._fmt_size(self.size)

        if self.is_rom:
            bits = []
            if self.start & ROM_ADDRESS_MASK:
                bits.append(f"{self.start & ROM_ADDRESS_MASK:08x}")
            elif self.flags & ROM_ADDRESS_MASK:
                bits.append(f"<ignored>")
            else:
                bits.append(f"<unassigned>")
            bits.append(f"[size={size_s}]")
            return f"Expansion ROM at " + " ".join(bits)

        if self.is_io:
            return (
                f"Region {self.index}: I/O ports at {self._fmt_addr()} [size={size_s}]"
            )

        if self.is_mem:
            bits = []
            bits.append("64-bit" if self.is_64bit else "32-bit")
            bits.append("prefetchable" if self.is_prefetchable else "non-prefetchable")
            attrs = ", ".join(bits)
            return f"Region {self.index}: Memory at {self._fmt_addr()} ({attrs}) [size={size_s}]"

        # Fallback (rare): unknown type
        return f"Region {self.index}: start=0x{self.start:x} end=0x{self.end:x} flags=0x{self.flags:08x} [size={size_s}]"


def parse_pci_resource_file(path: Path) -> List[ResourceEntry]:
    """
    Parse /sys/bus/pci/devices/0000:BB:DD.F/resource and return entries for:
    BAR0..5, the ROM, and possible bridge windows (ordering is the kernel's).
    """
    entries: List[ResourceEntry] = []
    try:
        lines = path.read_text().split("\n")
        for idx, line in enumerate(lines):
            if not line:
                continue
            s, e, fl = (int(tok, 16) for tok in line.strip().split())
            if s == 0 and e == 0 and fl == 0:
                continue
            entries.append(ResourceEntry(index=idx, start=s, end=e, flags=fl))
    except FileNotFoundError:
        return None
    return entries


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

            resource = parse_pci_resource_file((d / "resource"))

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
                resource=resource,
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
