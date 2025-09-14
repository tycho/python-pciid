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

def flag_char(flags: enum.Flag, bit: enum.Flag) -> str:
    return '+' if flags & bit else '-'

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
    raw: bytes   # bytes from start of this cap up to start of next (or 0x100)
    decoded: Optional[object] = None


@dataclass(frozen=True)
class ExtCapRecord:
    ext_id: int  # raw numeric ID
    ext_id_enum: Optional[PciExtCapID]
    version: int # 0..F
    offset: int  # byte offset (DWORD aligned)
    raw: bytes   # bytes from this header up to next cap (or end)
    decoded: Optional[object] = None


@dataclass(frozen=True)
class ParsedCapabilities:
    classic: List[ClassicCapRecord]
    extended: List[ExtCapRecord]


# =========================
# Decoder registries (hooks)
# =========================

DecodeResult = Tuple[bytes, object]

ClassicDecoders: Dict[PciCapID, Callable[[bytes, int], DecodeResult]] = {}
ExtDecoders: Dict[PciExtCapID, Callable[[bytes, int], DecodeResult]] = {}

def decode_generic(raw: bytes, flags: int) -> DecodeResult:
    return raw, None

def decode_ext_generic(raw: bytes, ver: int) -> DecodeResult:
    return raw, None

class PMFlags(enum.Flag):
    PME_CLOCK = 1 << 3
    DSI = 1 << 5
    D1 = 1 << 9
    D2 = 1 << 10
    PME_D0 = 1 << 11
    PME_D1 = 1 << 12
    PME_D2 = 1 << 13
    PME_D3_HOT = 1 << 14
    PME_D3_COLD = 1 << 15

    @classmethod
    def _missing_(cls, value):
        # Allow any integer value, even with unknown bits
        pseudo_member = object.__new__(cls)
        pseudo_member._name_ = f"PMFlags({value})"
        pseudo_member._value_ = value
        return pseudo_member

class PMStatusFlags(enum.Flag):
    NO_SOFT_RST = 1 << 3
    PME_ENABLE = 1 << 8
    PME_STATUS = 1 << 15

    @classmethod
    def _missing_(cls, value):
        # Allow any integer value, even with unknown bits
        pseudo_member = object.__new__(cls)
        pseudo_member._name_ = f"PMStatusFlags({value})"
        pseudo_member._value_ = value
        return pseudo_member

@dataclass(frozen=True)
class PMStatus:
    raw: int

    @property
    def flags(self) -> PMStatusFlags:
        return PMStatusFlags(self.raw)

    @property
    def power_state(self) -> int:
        # D0, D1 or D2
        return self.raw & 0x3

    @property
    def dsel(self) -> int:
        return (self.raw & 0x1e00) >> 9

    @property
    def dscale(self) -> int:
        return (self.raw & 0x6000) >> 13

@dataclass(frozen=True)
class Cap_PM:
    version: int
    flags_raw: int
    status: PMStatus
    aux_current: int # mA
    bridge_flags: int

    @property
    def has_details(self): return True

    @property
    def flags(self) -> PMFlags:
        return PMFlags(self.flags_raw)

    @property
    def name(self) -> str:
        return f"Power Management version {self.version}"

    def __str__(self) -> str:
        flags = self.flags
        status_flags = self.status.flags

        formatted = (
            f"\t\tFlags: "
            f"PMEClk{flag_char(flags, PMFlags.PME_CLOCK)} "
            f"DSI{flag_char(flags, PMFlags.DSI)} "
            f"D1{flag_char(flags, PMFlags.D1)} "
            f"D2{flag_char(flags, PMFlags.D2)} "
            f"AuxCurrent={self.aux_current}mA "
            f"PME("
            f"D0{flag_char(flags, PMFlags.PME_D0)},"
            f"D1{flag_char(flags, PMFlags.PME_D1)},"
            f"D2{flag_char(flags, PMFlags.PME_D2)},"
            f"D3hot{flag_char(flags, PMFlags.PME_D3_HOT)},"
            f"D3cold{flag_char(flags, PMFlags.PME_D3_COLD)})\n"
            f"\t\tStatus: "
            f"D{self.status.power_state} "
            f"NoSoftRst{flag_char(status_flags, PMStatusFlags.NO_SOFT_RST)} "
            f"PME-Enable{flag_char(status_flags, PMStatusFlags.PME_ENABLE)} "
            f"DSel={self.status.dsel} "
            f"DScale={self.status.dscale} "
            f"PME{flag_char(status_flags, PMStatusFlags.PME_STATUS)}"
        )
        return formatted

def decode_pm(raw: bytes, flags: int) -> DecodeResult:
    pm_aux_current = (0, 55, 100, 160, 220, 270, 320, 375)
    version = flags & 0x7
    aux_current = (flags & 0x1c0) >> 6

    status = _u16(raw, 4)
    bridge_flags = _u8(raw, 6)

    pm = Cap_PM(
        version=version,
        flags_raw=flags,
        aux_current=pm_aux_current[aux_current],
        status=PMStatus(raw=status),
        bridge_flags=bridge_flags
    )
    return raw, pm
ClassicDecoders[PciCapID.PM] = decode_pm

class MSIFlags(enum.Flag):
    ENABLE = 1 << 0
    MASK = 1 << 8
    ADDR_64 = 1 << 7

    @classmethod
    def _missing_(cls, value):
        # Allow any integer value, even with unknown bits
        pseudo_member = object.__new__(cls)
        pseudo_member._name_ = f"MSIFlags({value})"
        pseudo_member._value_ = value
        return pseudo_member

#         Capabilities: [68] MSI: Enable- Count=1/1 Maskable- 64bit+
#                Address: 0000000000000000  Data: 0000

@dataclass(frozen=True)
class Cap_MSI:
    flags_raw: int
    qsize: int
    qmask: int
    addr: int
    data: int
    mask: int
    pending: int

    @property
    def has_details(self): return True

    @property
    def flags(self) -> MSIFlags:
        return MSIFlags(self.flags_raw)

    @property
    def name(self) -> str:
        flags = self.flags
        formatted = (
            f"MSI: "
            f"Enable{flag_char(flags, MSIFlags.ENABLE)} "
            f"Count={self.qsize}/{self.qmask} "
            f"Maskable{flag_char(flags, MSIFlags.MASK)} "
            f"64bit{flag_char(flags, MSIFlags.ADDR_64)}"
        )
        return formatted

    def __str__(self) -> str:
        flags = self.flags
        formatted_addr = f"{self.addr:016x}" if flags & MSIFlags.ADDR_64 else f"{self.addr:08x}"
        formatted = (
                f"\t\tAddress: {formatted_addr} "
                f"Data: {self.data:04x}"
        )
        if flags & MSIFlags.MASK:
            formatted += f"\n\t\tMasking: {self.mask:08x}  Pending: {self.pending:08x}"
        return formatted

def decode_msi(raw: bytes, flags_raw: int):
    flags = MSIFlags(flags_raw)
    is64 = flags & MSIFlags.ADDR_64
    qsize = 1 << ((flags_raw & 0x70) >> 4)
    qmask = 1 << ((flags_raw & 0x0e) >> 1)
    mask = 0
    pending = 0
    if is64:
        addr = _u32(raw, 4) | (_u32(raw, 8) << 32)
        data = _u16(raw, 12)
        if flags & MSIFlags.MASK:
            mask = _u32(raw, 16)
            pending = _u32(raw, 20)
    else:
        addr = _u32(raw, 4)
        data = _u16(raw, 8)
        if flags & MSIFlags.MASK:
            mask = _u32(raw, 12)
            pending = _u32(raw, 16)
    decoded = Cap_MSI(
        flags_raw=flags_raw,
        qsize=qsize,
        qmask=qmask,
        addr=addr,
        data=data,
        mask=mask,
        pending=pending,
    )
    return raw, decoded

ClassicDecoders[PciCapID.MSI] = decode_msi


class AERUncorrectableError(enum.Flag):
    TRAIN = 1 << 0
    DLP = 1 << 4
    SDES = 1 << 5
    POISON_TLP = 1 << 12
    FCP = 1 << 13
    COMP_TIME = 1 << 14
    COMP_ABORT = 1 << 15
    UNX_COMP = 1 << 16
    RX_OVER = 1 << 17
    MALF_TLP = 1 << 18
    ECRC = 1 << 19
    UNSUP = 1 << 20
    ACS_VIOL = 1 << 21
    INTERNAL = 1 << 22
    MC_BLOCKED_TLP = 1 << 23
    ATOMICOP_EGRESS_BLOCKED = 1 << 24
    TLP_PREFIX_BLOCKED = 1 << 25
    POISONED_TLP_EGRESS = 1 << 26
    DMWR_REQ_EGRESS_BLOCKED = 1 << 27
    IDE_CHECK = 1 << 28
    MISR_IDE_TLP = 1 << 29
    PCRC_CHECK = 1 << 30
    TLP_XLAT_EGRESS_BLOCKED = 1 << 31

    @classmethod
    def _missing_(cls, value):
        # Allow any integer value, even with unknown bits
        pseudo_member = object.__new__(cls)
        pseudo_member._name_ = f"AERUncorrectableError({value})"
        pseudo_member._value_ = value
        return pseudo_member

    def __str__(self) -> str:
        formatted = (
            f"DLP{flag_char(self, AERUncorrectableError.DLP)} "
            f"SDES{flag_char(self, AERUncorrectableError.SDES)} "
            f"TLP{flag_char(self, AERUncorrectableError.POISON_TLP)} "
            f"FCP{flag_char(self, AERUncorrectableError.FCP)} "
            f"CmpltTO{flag_char(self, AERUncorrectableError.COMP_TIME)} "
            f"CmpltAbrt{flag_char(self, AERUncorrectableError.COMP_ABORT)} "
            f"UnxCmplt{flag_char(self, AERUncorrectableError.UNX_COMP)} "
            f"RxOF{flag_char(self, AERUncorrectableError.RX_OVER)} "
            f"MalfTLP{flag_char(self, AERUncorrectableError.MALF_TLP)}\n\t\t\t"
            f"ECRC{flag_char(self, AERUncorrectableError.ECRC)} "
            f"UnsupReq{flag_char(self, AERUncorrectableError.UNSUP)} "
            f"ACSViol{flag_char(self, AERUncorrectableError.ACS_VIOL)} "
            f"UncorrIntErr{flag_char(self, AERUncorrectableError.INTERNAL)} "
            f"BlockedTLP{flag_char(self, AERUncorrectableError.MC_BLOCKED_TLP)} "
            f"AtomicOpBlocked{flag_char(self, AERUncorrectableError.ATOMICOP_EGRESS_BLOCKED)} "
            f"TLPBlockedErr{flag_char(self, AERUncorrectableError.TLP_PREFIX_BLOCKED)}\n\t\t\t"
            f"PoisonTLPBlocked{flag_char(self, AERUncorrectableError.POISONED_TLP_EGRESS)} "
            f"DMWrReqBlocked{flag_char(self, AERUncorrectableError.DMWR_REQ_EGRESS_BLOCKED)} "
            f"IDECheck{flag_char(self, AERUncorrectableError.IDE_CHECK)} "
            f"MisIDETLP{flag_char(self, AERUncorrectableError.MISR_IDE_TLP)} "
            f"PCRC_CHECK{flag_char(self, AERUncorrectableError.PCRC_CHECK)} "
            f"TLPXlatBlocked{flag_char(self, AERUncorrectableError.TLP_XLAT_EGRESS_BLOCKED)}\n"
        )
        return formatted

class AERCorrectableError(enum.Flag):
    RCVR = 1 << 0
    BAD_TLP = 1 << 6
    BAD_DLLP = 1 << 7
    REP_ROLL = 1 << 8
    REP_TIMER = 1 << 12
    REP_ANFE = 1 << 13
    INTERNAL = 1 << 14
    HDRLOG_OVER = 1 << 15

    @classmethod
    def _missing_(cls, value):
        # Allow any integer value, even with unknown bits
        pseudo_member = object.__new__(cls)
        pseudo_member._name_ = f"AERCorrectableError({value})"
        pseudo_member._value_ = value
        return pseudo_member

    def __str__(self) -> str:
        formatted = (
            f"RxErr{flag_char(self, AERCorrectableError.RCVR)} "
            f"BadTLP{flag_char(self, AERCorrectableError.BAD_TLP)} "
            f"BadDLLP{flag_char(self, AERCorrectableError.BAD_DLLP)} "
            f"Rollover{flag_char(self, AERCorrectableError.REP_ROLL)} "
            f"Timeout{flag_char(self, AERCorrectableError.REP_TIMER)} "
            f"AdvNonFatalErr{flag_char(self, AERCorrectableError.REP_ANFE)} "
            f"CorrIntErr{flag_char(self, AERCorrectableError.INTERNAL)} "
            f"HeaderOF{flag_char(self, AERCorrectableError.HDRLOG_OVER)}\n"
        )
        return formatted

class AERCapability(enum.Flag):
    ECRC_GENC = 1 << 5
    ECRC_GENE = 1 << 6
    ECRC_CHKC = 1 << 7
    ECRC_CHKE = 1 << 8
    MULT_HDRC = 1 << 9
    MULT_HDRE = 1 << 10
    TLP_PFX = 1 << 11
    HDR_LOG = 1 << 12

    @classmethod
    def _missing_(cls, value):
        # Allow any integer value, even with unknown bits
        pseudo_member = object.__new__(cls)
        pseudo_member._name_ = f"AERCapability({value})"
        pseudo_member._value_ = value
        return pseudo_member

    @property
    def first_error_pointer(self) -> int:
        return self._value_ & 0x1F

    def __str__(self) -> str:
        formatted = (
            f"First Error Pointer: {self.first_error_pointer:02x}, "
            f"ECRCGenCap{flag_char(self, AERCapability.ECRC_GENC)} "
            f"ECRCGenEn{flag_char(self, AERCapability.ECRC_GENE)} "
            f"ECRCChkCap{flag_char(self, AERCapability.ECRC_CHKC)} "
            f"ECRCChkEn{flag_char(self, AERCapability.ECRC_CHKE)}\n\t\t\t"
            f"MultHdrRecCap{flag_char(self, AERCapability.MULT_HDRC)} "
            f"MultHdrRecEn{flag_char(self, AERCapability.MULT_HDRE)} "
            f"TLPPfxPres{flag_char(self, AERCapability.TLP_PFX)} "
            f"HdrLogCap{flag_char(self, AERCapability.HDR_LOG)}\n"
        )
        return formatted

@dataclass(frozen=True)
class ExtCap_AER:
    uncor_status_raw: int
    uncor_mask_raw: int
    uncor_severity_raw: int
    cor_status_raw: int
    cor_mask_raw: int
    err_cap_raw: int
    hdr_log: Tuple[int, int, int, int]

    @property
    def has_details(self): return True

    @property
    def uncor_status(self) -> AERUncorrectableError:
        return AERUncorrectableError(self.uncor_status_raw)

    @property
    def uncor_mask(self) -> AERUncorrectableError:
        return AERUncorrectableError(self.uncor_mask_raw)

    @property
    def uncor_severity(self) -> AERUncorrectableError:
        return AERUncorrectableError(self.uncor_severity_raw)

    @property
    def cor_status(self) -> AERCorrectableError:
        return AERCorrectableError(self.cor_status_raw)

    @property
    def cor_mask(self) -> AERCorrectableError:
        return AERCorrectableError(self.cor_mask_raw)

    @property
    def err_cap(self) -> AERCapability:
        return AERCapability(self.err_cap_raw)

    @property
    def name(self) -> str:
        return "Advanced Error Reporting"

    def __str__(self) -> str:
        formatted = (
            f"\t\tUESta:\t{str(self.uncor_status)}"
            f"\t\tUEMsk:\t{str(self.uncor_mask)}"
            f"\t\tUESvrt:\t{str(self.uncor_severity)}"
            f"\t\tCESta:\t{str(self.cor_status)}"
            f"\t\tCEMsk:\t{str(self.cor_mask)}"
            f"\t\tAERCap:\t{str(self.err_cap)}"
            f"\t\tHeaderLog: {self.hdr_log[0]:08x} {self.hdr_log[1]:08x} {self.hdr_log[2]:08x} {self.hdr_log[3]:08x}"
        )
        return formatted

def decode_ext_aer(raw: bytes, ver: int):
    uncor_status = _u32(raw, 4)
    uncor_mask = _u32(raw, 8)
    uncor_sever = _u32(raw, 12)
    cor_status = _u32(raw, 16)
    cor_mask = _u32(raw, 20)
    err_cap = _u32(raw, 24)
    hdr_log = (_u32(raw, 28), _u32(raw, 32), _u32(raw, 36), _u32(raw, 40))

    decoded = ExtCap_AER(
        uncor_status_raw=uncor_status,
        uncor_mask_raw=uncor_mask,
        uncor_severity_raw=uncor_sever,
        cor_status_raw=cor_status,
        cor_mask_raw=cor_mask,
        err_cap_raw=err_cap,
        hdr_log=hdr_log,
    )

    return raw, decoded
ExtDecoders[PciExtCapID.AER] = decode_ext_aer

@dataclass(frozen=True)
class ExtCap_VNDR:
    vid: int
    rev: int
    length: int

    @property
    def has_details(self): return False

    @property
    def name(self):
        formatted = (
            f"Vendor Specific Information: "
            f"Len={self.length:02x} <?>"
        )
        return formatted

def decode_ext_vndr(raw: bytes, ver: int):
    PCI_EVNDR_HEADER = 4
    hdr = _u32(raw, PCI_EVNDR_HEADER)
    decoded = ExtCap_VNDR(
        vid=((hdr >> 0) & 0xFFFF),
        rev=((hdr >> 16) & 0xF),
        length=((hdr >> 20) & 0xFFF)
    )
    return raw[:decoded.length], decoded
ExtDecoders[PciExtCapID.VNDR] = decode_ext_vndr

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

        if ptr + 4 > len(cfg):  # need at least cap_id + next_ptr + flags
            break

        cap_id = _u8(cfg, ptr)
        next_ptr = _u8(cfg, ptr + 1) & ~3
        flags = _u16(cfg, ptr + 2)

        # Compute a safe slice for raw: from ptr up to next_ptr (if sane), else to 0x100.
        if _valid_ptr(next_ptr) and next_ptr > ptr:
            end = next_ptr
        else:
            end = min(0x100, len(cfg))  # cap list confined to first 256 B

        raw = cfg[ptr:end]
        cap_enum = _enum_or_none(PciCapID, cap_id)

        # Future: decode if registered
        decoded = None
        decoder = ClassicDecoders.get(cap_id, decode_generic)
        raw, decoded = decoder(raw, flags)

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

        # 16 bits for capability ID
        ext_id = hdr & 0xFFFF

        # 3 bits for version
        ver = (hdr >> 16) & 0x7

        # Bottom two bits have a reserved usage, and must be masked off
        nxt = (hdr >> 20) & 0xFFC

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
        decoder = ExtDecoders.get(ext_id, decode_ext_generic)
        raw, decoded = decoder(raw, ver)
        out.append(
            ExtCapRecord(
                ext_id=ext_id,
                ext_id_enum=_enum_or_none(PciExtCapID, ext_id),
                version=ver,
                offset=start,
                raw=raw,
                decoded=decoded,
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

    for c in parsed.classic:
        name = cap_long_name(c.cap_id_enum) if c.cap_id_enum else f"0x{c.cap_id:02x}"
        if getattr(c.decoded, "name", None):
            name = c.decoded.name
        print(f"  Capabilities: [{c.offset:02x}]: {name}")
        if c.decoded is not None and c.decoded.has_details:
            print(c.decoded)

    for e in parsed.extended:
        name = extcap_long_name(e.ext_id_enum) if e.ext_id_enum else f"0x{e.ext_id:04x}"
        if getattr(e.decoded, "name", None):
            name = e.decoded.name
        print(f"  Capabilities: [{e.offset:03x} v{e.version}]: {name}")
        if e.decoded is not None and e.decoded.has_details:
            print(e.decoded)
