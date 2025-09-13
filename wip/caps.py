from __future__ import annotations

import enum
import os
import struct
from dataclasses import dataclass
from typing import Callable, Dict, List, Optional, Tuple

# =========================
# Enumerations (IDs)
# =========================


class PciCapID(enum.IntEnum):
    NULL     =  0x00
    PM       =  0x01
    AGP      =  0x02
    VPD      =  0x03
    SLOT_ID  =  0x04
    MSI      =  0x05
    CHSWP    =  0x06
    PCIX     =  0x07
    HT       =  0x08
    VNDR     =  0x09
    DBG      =  0x0A
    CCRC     =  0x0B
    HOTPLUG  =  0x0C
    SSVID    =  0x0D
    AGP3     =  0x0E
    SECURE   =  0x0F
    EXP      =  0x10
    MSIX     =  0x11
    SATA     =  0x12
    AF       =  0x13
    EA       =  0x14
    FPB      =  0x15


CAP_NAMES: dict[PciCapID, Tuple[str, str]] = {
    PciCapID.PM: ("Power Management", "Power Management Capability"),
    PciCapID.AGP: ("AGP", "Accelerated Graphics Port"),
    PciCapID.VPD: ("VPD", "Vital Product Data"),
    PciCapID.SLOT_ID: ("Slot Identification", "Slot Identification"),
    PciCapID.MSI: ("MSI", "Message Signaled Interrupts"),
    PciCapID.CHSWP: ("Hot-Swap", "CompactPCI hot-swap"),
    PciCapID.PCIX: ("PCI-X", "PCI-X Capability"),
    PciCapID.HT: ("HyperTransport", "HyperTransport Capability"),
    PciCapID.VNDR: ("Vendor Specific", "Vendor-Specific Capability"),
    PciCapID.DBG: ("Debug Port", "Debug Port"),
    PciCapID.CCRC: ("Central Resource Control", "CompactPCI Central Resource Control"),
    PciCapID.HOTPLUG: ("Hot-Plug", "Hot-plug capable"),
    PciCapID.SSVID: ("Bridge SSID", "PCI-to-PCI Bridge Subsystem ID"),
    PciCapID.AGP3: ("AGP 3.0", "AGP 3.0"),
    PciCapID.EXP: ("PCI Express", "PCI Express Capability"),
    PciCapID.MSIX: ("MSI-X", "Message Signaled Interrupts eXtended"),
    PciCapID.SATA: ("SATA", "Serial ATA Capability"),
    PciCapID.AF: ("AF", "Advanced Features"),
}


def cap_short_name(capid: PciCapID) -> Optional[str]:
    short, _ = CAP_NAMES.get(capid, (None, None))
    if short is None:
        return f"Unknown 0x{capid:04x}"
    return short


def cap_long_name(capid: PciCapID) -> Optional[str]:
    _, long = CAP_NAMES.get(capid, (None, None))
    if long is None:
        return f"Unknown 0x{capid:04x}"
    return long


class PciExtCapID(enum.IntEnum):
    NULL           =  0x0000
    AER            =  0x0001
    VC             =  0x0002
    DSN            =  0x0003
    RC_LINK        =  0x0004
    RC_INT_LINK    =  0x0005
    RCEC_ASSOC     =  0x0006
    MULTI_FUNC_VC  =  0x0007
    VC2            =  0x0008
    RCRB           =  0x000A
    VNDR           =  0x000B
    ACS            =  0x000D
    ARI            =  0x000E
    ATS            =  0x000F
    SRIOV          =  0x0010
    MRIOV          =  0x0011
    MULTICAST      =  0x0012
    PRI            =  0x0013
    AME            =  0x0014
    REBAR          =  0x0015
    DPA            =  0x0016
    TPH            =  0x0017
    LTR            =  0x0018
    SECPCI         =  0x0019
    PMUX           =  0x001A
    PASID          =  0x001B
    LNR            =  0x001C
    DPC            =  0x001D
    L1PM           =  0x001E
    PTM            =  0x001F
    M_PCIE         =  0x0020
    FRS            =  0x0021
    RTR            =  0x0022
    DVSEC          =  0x0023
    VF_REBAR       =  0x0024
    DLNK           =  0x0025
    PL16GT         =  0x0026
    LMR            =  0x0027
    HIER_ID        =  0x0028
    NPEM           =  0x0029
    PL32GT         =  0x002A
    ALT_PROT       =  0x002B
    SFI            =  0x002C
    DOE            =  0x002E
    DEV3           =  0x002F
    IDE            =  0x0030
    PL64GT         =  0x0031
    FLIT_LOG       =  0x0032
    FLIT_PM        =  0x0033
    FLIT_EI        =  0x0034
    SVC            =  0x0035
    MMIO_RBL       =  0x0036
    NOP_FLIT       =  0x0037
    SIOV           =  0x0038
    PL128GT        =  0x0039
    CAPT_D         =  0x003A


EXT_CAP_NAMES: dict[PciExtCapID, Tuple[str, str]] = {
    PciExtCapID.AER: ("Advanced Error Reporting", "Advanced Error Reporting"),
    PciExtCapID.VC: ("Virtual Channel", "Virtual Channel"),
    PciExtCapID.DSN: ("Device Serial Number", "Device Serial Number"),
    PciExtCapID.RC_LINK: ("Root Complex Link", "Root Complex Link Declaration"),
    PciExtCapID.RC_INT_LINK: ("RC Internal Link", "Root Complex Internal Link"),
    PciExtCapID.RCEC_ASSOC: ("RCEC Association", "Root Complex Event Collector Association"),
    PciExtCapID.VC2: ("Virtual Channel", "Virtual Channel (alternate)"),
    PciExtCapID.RCRB: ("RCRB", "Root Complex Register Block"),
    PciExtCapID.VNDR: ("VNDR", "Vendor specific"),
    PciExtCapID.ACS: ("ACS", "Access Control Services"),
    PciExtCapID.ARI: ("ARI", "Alternate Routing-ID Interpretation"),
    PciExtCapID.ATS: ("ATS", "Address Translation Services"),
    PciExtCapID.SRIOV: ("SR-IOV", "Single Root I/O Virtualization"),
    PciExtCapID.MRIOV: ("MR-IOV", "Multi-Root I/O Virtualization"),
    PciExtCapID.MULTICAST: ("Multicast", "Multicast"),
    PciExtCapID.PRI: ("PRI", "Page Request Interface"),
    PciExtCapID.REBAR: ("REBAR", "Resizable BAR"),
    PciExtCapID.DPA: ("DPA", "Dynamic Power Allocation"),
    PciExtCapID.TPH: ("TPH", "TLP Processing Hints"),
    PciExtCapID.LTR: ("LTR", "Latency Tolerance Reporting"),
    PciExtCapID.SECPCI: ("Secondary PCIe", "Secondary PCI Express"),
    PciExtCapID.PMUX: ("PMUX", "Protocol Multiplexing"),
    PciExtCapID.PASID: ("PASID", "Process Address Space ID"),
    PciExtCapID.LNR: ("LNR", "LN Requester"),
    PciExtCapID.DPC: ("DPC", "Downstream Port Containment"),
    PciExtCapID.L1PM: ("L1 PM Substates", "L1 PM Substates"),
    PciExtCapID.PTM: ("PTM", "Precision Time Measurement"),
    PciExtCapID.M_PCIE: ("M_PCIE", "PCIe over M-PHY"),
    PciExtCapID.FRS: ("FRS", "FRS Queueing"),
    PciExtCapID.RTR: ("RTR", "Readiness Time Reporting"),
    PciExtCapID.DVSEC: ("DVSEC", "Designated Vendor-Specific"),
    PciExtCapID.VF_REBAR: ("VF REBAR", "VF Resizable BAR"),
    PciExtCapID.DLNK: ("DLNK", "Data Link Feature"),
    PciExtCapID.PL16GT: ("Physical Layer 16.0 GT/s", "Physical Layer 16.0 GT/s"),
    PciExtCapID.LMR: ("Lane Margining", "Lane Margining at the Receiver"),
    PciExtCapID.HIER_ID: ("Hierarchy ID", "Hierarchy ID"),
    PciExtCapID.NPEM: ("NPEM", "Native PCIe Enclosure Management"),
    PciExtCapID.PL32GT: ("Physical Layer 32.0 GT/s", "Physical Layer 32.0 GT/s"),
    PciExtCapID.ALT_PROT: ("Alternate Protocol", "Alternate Protocol"),
    PciExtCapID.SFI: ("SFI", "System Firmware Intermediary"),
    PciExtCapID.DOE: ("DOE", "Data Object Exchange"),
    PciExtCapID.DEV3: ("DEV3", "Device 3"),
    PciExtCapID.IDE: ("IDE", "Integrity and Data Encryption"),
    PciExtCapID.PL64GT: ("Physical Layer 64.0 GT/s", "Physical Layer 64.0 GT/s"),
    PciExtCapID.FLIT_LOG: ("Flit Logging", "Flit Logging"),
    PciExtCapID.FLIT_PM: ("Flit Performance Measurement", "Flit Performance Measurement"),
    PciExtCapID.FLIT_EI: ("Flit Error Injection", "Flit Error Injection"),
    PciExtCapID.SVC: ("SVC", "Streamlined Virtual Channel"),
    PciExtCapID.MMIO_RBL: ("MMIO RBL", "MMIO Register Block Locator"),
    PciExtCapID.NOP_FLIT: ("NOP Flit", "NOP Flit Extended Capability"),
    PciExtCapID.SIOV: ("SIOV", "Scalable I/O Virtualization"),
    PciExtCapID.PL128GT: ("Physical Layer 128.0 GT/s", "Physical Layer 128.0 GT/s"),
    PciExtCapID.CAPT_D: ("Captured Data", "Captured Data"),
}


def extcap_short_name(capid: PciExtCapID) -> Optional[str]:
    short, _ = EXT_CAP_NAMES.get(capid, (None, None))
    if short is None:
        return f"Unknown 0x{capid:04x}"
    return short


def extcap_long_name(capid: PciExtCapID) -> Optional[str]:
    _, long = EXT_CAP_NAMES.get(capid, (None, None))
    if long is None:
        return f"Unknown 0x{capid:04x}"
    return long


# =========================
# Data structures
# =========================


@dataclass(frozen=True)
class ClassicCapRecord:
    cap_id: int  # raw numeric ID (still provide the enum below)
    cap_id_enum: Optional[PciCapID]
    offset: int  # byte offset within config space
    raw: bytes  # bytes from start of this cap up to start of next (or 0x100)
    # Placeholders for future decoded form:
    decoded: Optional[object] = None


@dataclass(frozen=True)
class ExtCapRecord:
    ext_id: int  # raw numeric ID
    ext_id_enum: Optional[PciExtCapID]
    version: int  # 0..F
    offset: int  # byte offset (DWORD aligned)
    raw: bytes  # bytes from this header up to next cap (or end)
    # Placeholders for future decoded form:
    decoded: Optional[object] = None


@dataclass(frozen=True)
class ParsedCapabilities:
    classic: List[ClassicCapRecord]
    extended: List[ExtCapRecord]


# =========================
# Decoder registries (hooks)
# =========================

ClassicDecoders: Dict[int, Callable[[bytes, int], object]] = {}
ExtDecoders: Dict[int, Callable[[bytes, int, int], object]] = {}
# Register future decoders like:
# ClassicDecoders[PciCapID.MSI] = decode_msi
# ExtDecoders[PciExtCapID.SRIOV] = decode_sriov


# =========================
# Low-level helpers
# =========================


def _u8(b: bytes, off: int) -> int:
    return b[off]


def _u16(b: bytes, off: int) -> int:
    return struct.unpack_from("<H", b, off)[0]


def _u32(b: bytes, off: int) -> int:
    return struct.unpack_from("<I", b, off)[0]


def _has_cap_list(cfg: bytes) -> bool:
    # Status register bit 4 (Capabilities List)
    if len(cfg) < 0x08:
        return False
    status = _u16(cfg, 0x06)
    return bool(status & 0x0010)


def _enum_or_none(enum_cls, value: int):
    try:
        return enum_cls(value)
    except ValueError:
        return None


# =========================
# Config read
# =========================


def read_pci_config(sbdf: str, max_len: int = 4096) -> bytes:
    """
    Read up to 4 KiB from /sys/bus/pci/devices/<sbdf>/config.
    Short reads (e.g., 256 B) are expected on platforms without ECAM exposure.
    """
    path = f"/sys/bus/pci/devices/{sbdf}/config"
    with open(path, "rb", buffering=0) as f:
        data = f.read(max_len)
    return data


# =========================
# Walkers
# =========================


def _parse_classic_caps(cfg: bytes) -> List[ClassicCapRecord]:
    out: List[ClassicCapRecord] = []
    if len(cfg) < 0x40 or not _has_cap_list(cfg):
        return out

    # Capability Pointer at 0x34 (8-bit)
    ptr = _u8(cfg, 0x34)
    seen: set[int] = set()

    # Valid classic region is within first 256 bytes; typical range >= 0x40
    def _valid_ptr(p: int) -> bool:
        return 0x40 <= p <= 0xFC and (p % 4 == 0)

    while ptr and _valid_ptr(ptr):
        if ptr in seen:
            break  # loop protection
        seen.add(ptr)

        if ptr + 2 > len(cfg):  # need at least cap_id + next_ptr
            break

        cap_id = _u8(cfg, ptr)
        next_ptr = _u8(cfg, ptr + 1)

        # Compute a safe slice for raw: from ptr up to next_ptr (if sane), else to 0x100.
        if _valid_ptr(next_ptr) and next_ptr > ptr:
            end = next_ptr
        else:
            end = min(0x100, len(cfg))  # cap list confined to first 256 B

        raw = cfg[ptr:end]
        cap_enum = _enum_or_none(PciCapID, cap_id)

        # Future: decode if registered
        decoded = None
        decoder = ClassicDecoders.get(cap_id)
        if decoder:
            try:
                decoded = decoder(cfg, ptr)
            except Exception:
                decoded = None  # keep robust; raw always preserved

        out.append(
            ClassicCapRecord(
                cap_id=cap_id,
                cap_id_enum=cap_enum,
                offset=ptr,
                raw=raw,
                decoded=decoded,
            )
        )

        ptr = next_ptr

    return out


def _parse_ext_caps(cfg: bytes) -> List[ExtCapRecord]:
    out: List[ExtCapRecord] = []
    ecam_end = min(len(cfg), 0x1000)
    if ecam_end <= 0x100:
        return out

    def _valid_off(o: int) -> bool:
        return 0x100 <= o <= 0xFFC and (o % 4 == 0)

    def _read_hdr(off: int) -> Tuple[int, int, int]:
        """Return (ext_id, version, next_off_bytes or 0)."""
        hdr = _u32(cfg, off)
        if hdr == 0x00000000 or hdr == 0xFFFFFFFF:
            return (0, 0, 0)
        ext_id = hdr & 0xFFFF
        ver = (hdr >> 16) & 0xF
        nxt = (hdr >> 20) & 0xFFF

        def ok(x: int) -> bool:
            return _valid_off(x) and (x != off)

        if not ok(nxt):
            nxt = 0
        return (ext_id, ver, nxt)

    # -------- Pass 1: follow the chain and record headers --------
    nodes: Dict[int, Tuple[int, int, int]] = {}  # off -> (id, ver, next_off)
    order: List[int] = []
    off = 0x100
    seen: set[int] = set()

    while _valid_off(off) and (off + 4) <= ecam_end:
        if off in seen:
            break
        seen.add(off)

        ext_id, ver, next_off = _read_hdr(off)
        if ext_id == 0:  # padding/invalid
            break
        nodes[off] = (ext_id, ver, next_off)
        order.append(off)

        if next_off == 0:
            break

        off = next_off

    if not nodes:
        return out

    # -------- Pass 2: compute record boundaries via sorted offsets --------
    sorted_offs = sorted(nodes.keys())
    # Map each start -> end (next higher start, else ecam_end)
    boundaries: Dict[int, int] = {}
    for i, start in enumerate(sorted_offs):
        end = sorted_offs[i + 1] if (i + 1) < len(sorted_offs) else ecam_end
        # Be safe in case of sparse/short reads
        end = max(end, start + 4)
        end = min(end, ecam_end)
        boundaries[start] = end

    # Emit records in the *walk* order (matches how lspci lists them),
    # while sizing each raw slice by the next higher offset.
    for start in order:
        ext_id, ver, _ = nodes[start]
        end = boundaries[start]
        raw = cfg[start:end]
        out.append(
            ExtCapRecord(
                ext_id=ext_id,
                ext_id_enum=_enum_or_none(PciExtCapID, ext_id),
                version=ver,
                offset=start,
                raw=raw,
                decoded=None,
            )
        )

    return out


# =========================
# Public API
# =========================


def parse_pci_capabilities(sbdf: str) -> ParsedCapabilities:
    """
    Read the device's config space and return classic and extended capability records.
    No decoding is performed yet (placeholders are present).
    """
    cfg = read_pci_config(sbdf, 4096)
    classic = _parse_classic_caps(cfg)
    extended = _parse_ext_caps(cfg)
    return ParsedCapabilities(classic=classic, extended=extended)


# =========================
# Example usage
# =========================
if __name__ == "__main__":
    import sys

    if len(sys.argv) != 2:
        print("Usage: python pci_caps.py 0000:BB:DD.F")
        sys.exit(1)
    dev = sys.argv[1]
    parsed = parse_pci_capabilities(dev)

    print("Classic capabilities:")
    for c in parsed.classic:
        name = cap_long_name(c.cap_id_enum) if c.cap_id_enum else f"0x{c.cap_id:02x}"
        print(f"  @0x{c.offset:02x}: {name}  (len={len(c.raw)})")

    print("Extended capabilities:")
    for e in parsed.extended:
        name = extcap_long_name(e.ext_id_enum) if e.ext_id_enum else f"0x{e.ext_id:04x}"
        print(f"  @0x{e.offset:03x}: {name} v{e.version}  (len={len(e.raw)})")
