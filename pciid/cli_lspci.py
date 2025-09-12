#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import os, sys, argparse
from typing import Tuple, Optional
import pciid

SYSFS_DEVICES_DEFAULT = "/sys/bus/pci/devices"


def read_hex(path: str) -> Optional[int]:
    try:
        with open(path, "r", encoding="ascii", errors="ignore") as f:
            s = f.read().strip()
        if s.startswith("0x") or s.startswith("0X"):
            return int(s, 16)
        # modalias-like hex ints may appear without 0x (rare here)
        return int(s, 16)
    except (FileNotFoundError, PermissionError, ValueError):
        return None


def format_line(
    pci: pciid.PciDb, sbdf: pciid.PciAddress, class16: int, ven: int, dev: int, rev: int
) -> str:
    base = (class16 >> 8) & 0xFF
    sub = (class16 >> 0) & 0xFF

    cname = (
        pci.get_class_name(base, sub, None)
        or pci.get_class_name(base, None, None)
        or f"Class {class16:04x}"
    )

    vname = pci.get_vendor_name(ven)
    dname = pci.get_device_name(ven, dev)

    if vname and dname:
        rdesc = f"{vname} {dname}"
    elif vname:
        rdesc = f"{vname} Device {dev:04x}"
    elif dname:
        rdesc = f"Vendor {ven:04x} {dname}"
    else:
        rdesc = f"Device [{ven:04x}:{dev:04x}]"

    revdesc = ""
    if rev != 0:
        revdesc = f" (rev {rev:02x})"

    return f"{sbdf} {cname} [{class16:04x}]: {rdesc} [{ven:04x}:{dev:04x}]{revdesc}"


def main():
    ap = argparse.ArgumentParser(
        description="Minimal lspci -nnD clone via sysfs + pciids_bin"
    )
    ap.add_argument("--db", default=None, help="path to pci.ids.bin")
    ap.add_argument(
        "--sysfs", default=SYSFS_DEVICES_DEFAULT, help="path to /sys/bus/pci/devices"
    )
    args = ap.parse_args()

    pci = pciid.open_db(args.db)
    sysfs = pciid.SysfsEnumerator()
    devices = sysfs.scan()

    out_lines = []

    for sbdf, device in sorted(devices.items()):
        out_lines.append(
            format_line(
                pci,
                device.bdf,
                device.class_code,
                device.vendor_id,
                device.device_id,
                device.revision,
            )
        )

    # Print in order
    for line in out_lines:
        print(line)

    pci.close()


if __name__ == "__main__":
    main()
