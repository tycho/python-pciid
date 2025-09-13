#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import sys, argparse, shlex
from typing import Any, Dict, Optional, Tuple
import pciid


def parse_hex(s: str) -> Optional[int]:
    if s is None or s == "" or s == '""':
        return None
    try:
        return int(s, 16)
    except ValueError:
        return None


def parse_lspci_mm_line(line: str) -> Optional[Dict[str, Any]]:
    """
    Parses one line of `lspci -nD -mm` (machine-readable).
    Format (common case):
      SBDF  "class"  "vendor"  "device"  [-rNN]  [-pNN]  "subven"  "subdev"
    The -rNN / -pNN flags may be present or absent; order can vary.
    Subsystem IDs may be empty quotes ("").
    Returns dict with keys:
      sbdf (str), class16 (int), prog_if (Optional[int]),
      vendor (int), device (int),
      subvendor (Optional[int]), subdevice (Optional[int]),
      revision (Optional[int])
    """
    toks = shlex.split(line.strip())
    if not toks:
        return None
    sbdf = toks[0]
    # Expect at least three quoted hex fields after SBDF
    if len(toks) < 4:
        return None

    # First three fields after SBDF are class, vendor, device (quoted in -mm)
    class_hex = toks[1].strip('"')
    vendor_hex = toks[2].strip('"')
    device_hex = toks[3].strip('"')

    class16 = parse_hex(class_hex)  # upper 16 bits of class code: base<<8 | subclass
    vendor = parse_hex(vendor_hex)
    device = parse_hex(device_hex)

    prog_if = None
    revision = None
    subvendor = None
    subdevice = None

    # Remaining tokens: mix of flags and possibly two quoted substrings for subsystem IDs
    rest = toks[4:]
    # collect any trailing quoted tokens (could be "", "")
    tail_hex = []
    for t in rest:
        if t.startswith("-p") or t.startswith("-P"):
            # prog-if (hex)
            prog_if = parse_hex(t[2:])
        elif t.startswith("-r") or t.startswith("-R"):
            # revision (hex)
            revision = parse_hex(t[2:])
        else:
            # may be quoted hex (subsystem pieces)
            val = t.strip('"')
            if val != "-" and val != "":
                tail_hex.append(val)
            else:
                tail_hex.append("")  # keep positions
    if len(tail_hex) >= 2:
        subvendor = parse_hex(tail_hex[-2])
        subdevice = parse_hex(tail_hex[-1])

    return {
        "sbdf": sbdf,
        "class16": class16,
        "prog_if": prog_if,
        "vendor": vendor,
        "device": device,
        "subvendor": subvendor,
        "subdevice": subdevice,
        "revision": revision,
    }


def class_name(
    pci: pciid.PciDb, class16: Optional[int], prog_if: Optional[int]
) -> Optional[str]:
    if class16 is None:
        return None
    base = (class16 >> 8) & 0xFF
    sub = class16 & 0xFF
    if prog_if is not None and False:
        # DISABLED: results in output that's hard to read
        return (
            pci.get_class_name(base, sub, prog_if)
            or pci.get_class_name(base, sub, None)
            or pci.get_class_name(base, None, None)
        )
    return pci.get_class_name(base, sub, None) or pci.get_class_name(base, None, None)


def make_modalias(row: Dict[str, Any]) -> str:
    """pci:v%08X d%08X sv%08X sd%08X bc%02X sc%02X i%02X (kernel format)"""
    ven = row.get("vendor") or 0
    dev = row.get("device") or 0
    subv = row.get("subvendor") or 0
    subd = row.get("subdevice") or 0
    class16 = row.get("class16") or 0
    pi = row.get("prog_if")
    base = (class16 >> 8) & 0xFF
    sub = class16 & 0xFF
    if pi is None:
        pi = 0
    return f"pci:v{ven:08X}d{dev:08X}sv{subv:08X}sd{subd:08X}bc{base:02X}sc{sub:02X}i{pi:02X}"


def describe_row(
    pci: pciid.PciDb, row: Dict[str, Any], append_modalias: bool = False
) -> str:
    ven = row["vendor"]
    dev = row["device"]
    subv = row["subvendor"]
    subd = row["subdevice"]
    class16 = row["class16"]
    prog_if = row["prog_if"]

    # Build class code (24-bit) if we have prog-if; else derive from 16-bit only
    class_code_24 = None
    if class16 is not None:
        base = (class16 >> 8) & 0xFF
        sub = class16 & 0xFF
        pi = prog_if if prog_if is not None else 0
        class_code_24 = (base << 16) | (sub << 8) | pi

    # Names
    vname = pci.get_vendor_name(ven) if ven is not None else None
    dname = (
        pci.get_device_name(ven, dev) if (ven is not None and dev is not None) else None
    )
    cname = class_name(pci, class16, prog_if)

    # Device best-effort if unknown
    if vname is None or dname is None:
        best = pci.describe_device_best_effort(ven or 0, dev or 0, class_code_24 or 0)
        dev_desc = best
    else:
        dev_desc = f"{vname} {dname}"

    # Subsystem, if present
    subs_desc = None
    if subv is not None and subd is not None and ven is not None and dev is not None:
        sname = pci.get_subsystem_name(ven, dev, subv, subd)
        svname = pci.get_vendor_name(subv) or f"0x{subv:04x}"
        if sname:
            subs_desc = f"{svname} {sname} [{subv:04x}:{subd:04x}]"
        else:
            subs_desc = f"{svname} subsystem [{subv:04x}:{subd:04x}]"

    # Class/prog-if string
    cstr = cname or (f"class {class16:04x}" if class16 is not None else "class ?")
    if prog_if is not None and cname is None:
        cstr += f", prog-if {prog_if:02x}"

    # Revision (optional, informational)
    rstr = f" rev {row['revision']:02x}" if row["revision"] is not None else ""

    # Modalias (optional)
    modalias = make_modalias(row) if append_modalias else None

    # Final line
    parts = [row["sbdf"], cstr, dev_desc]
    if subs_desc:
        parts.append(subs_desc)
    if modalias:
        parts.append(modalias)
    return "  ::  ".join(parts)


def main() -> None:
    ap = argparse.ArgumentParser(description="Probe lspci -nD -mm against pciids_bin")
    ap.add_argument("--db", default=None, help="path to pci.ids.bin")
    ap.add_argument(
        "--in",
        dest="inp",
        default="-",
        help="path to lspci -nD -mm output (default: stdin)",
    )
    ap.add_argument(
        "-m",
        "--modalias",
        action="store_true",
        help="append modalias to each output line",
    )
    ap.add_argument(
        "--only-modalias",
        action="store_true",
        help="print only modalias values (one per line)",
    )
    args = ap.parse_args()

    pci = pciid.open_db(args.db)
    try:
        fh = (
            sys.stdin
            if args.inp == "-"
            else open(args.inp, "r", encoding="utf-8", errors="replace")
        )
        with fh:
            for line in fh:
                line = line.strip()
                if not line:
                    continue
                row = parse_lspci_mm_line(line)
                if not row:
                    print(line)
                    continue
                if args.only_modalias:
                    print(make_modalias(row))
                else:
                    print(describe_row(pci, row, append_modalias=args.modalias))
    finally:
        pci.close()


if __name__ == "__main__":
    main()
