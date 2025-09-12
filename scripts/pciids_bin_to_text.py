#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Convert pci.ids.bin (built by build_pciids_bin.py) back to a plaintext pci.ids.
Comments are not preserved; ordering matches the binary's sorted order.
"""

import sys
import argparse
import bisect

from pciids_bin import (
    PciIds,
    SubclassRow,
    ProgIfRow,
)  # uses internal structs for efficient iteration


def dump_text(pci: PciIds, out):
    w = out.write

    # --- Vendors / Devices / Subsystems ---
    for vi in range(pci._vendor_count):
        ven_id, ven_sid, dev_start, dev_count = pci._vendor_row_at(vi)
        vname = pci.get_string(ven_sid)
        w(f"{ven_id:04x}  {vname}\n")
        for di in range(dev_start, dev_start + dev_count):
            dev_id, dev_sid, sub_start, sub_count = pci._device_row_at(di)
            dname = pci.get_string(dev_sid)
            w(f"\t{dev_id:04x}  {dname}\n")
            for si in range(sub_start, sub_start + sub_count):
                sven, sdev, ssid = pci._subsys_row_at(si)
                sname = pci.get_string(ssid)
                w(f"\t\t{sven:04x} {sdev:04x}  {sname}\n")

    w("\n")  # separator before classes

    # --- Classes / Subclasses / Prog-IF ---
    # Print each base class that exists, then its subclasses and prog-if entries.
    # subclass_keys are sorted by key=(base<<8)|sub; use range search per base.
    subclass_keys = pci._subclass_keys
    get_subrow = lambda idx: SubclassRow.unpack_from(
        pci.mm, pci._subclass_off + idx * SubclassRow.size
    )

    for base in range(256):
        # base class name (0 means absent)
        sid = int.from_bytes(
            pci.mm[
                pci._class_base_off + base * 4 : pci._class_base_off + (base + 1) * 4
            ],
            "little",
        )
        if sid == 0:
            continue
        bname = pci.get_string(sid)
        w(f"C {base:02x}  {bname}\n")

        # subclasses for this base
        lo = bisect.bisect_left(subclass_keys, (base << 8) | 0x00)
        hi = bisect.bisect_left(subclass_keys, ((base + 1) << 8))
        for i in range(lo, hi):
            key, sname_id, pi_start, pi_count = get_subrow(i)
            sub = key & 0xFF
            sname = pci.get_string(sname_id)
            w(f"\t{sub:02x}  {sname}\n")

            # program interfaces for this (base, sub)
            for j in range(pi_start, pi_start + pi_count):
                pi, piname_id = ProgIfRow.unpack_from(
                    pci.mm, pci._prog_if_off + j * ProgIfRow.size
                )
                piname = pci.get_string(piname_id)
                w(f"\t\t{pi:02x}  {piname}\n")


def main():
    ap = argparse.ArgumentParser(
        description="Reconstruct plaintext pci.ids from pci.ids.bin"
    )
    ap.add_argument(
        "-i", "--input", dest="input", required=True, help="pci.ids binary input path"
    )
    ap.add_argument(
        "-o",
        "--output",
        dest="output",
        required=True,
        help="pci.ids text output path",
    )
    args = ap.parse_args()

    pci = PciIds(args.input)
    try:
        out = (
            sys.stdout
            if args.output == "-"
            else open(args.output, "w", encoding="utf-8", newline="\n")
        )
        with out:
            dump_text(pci, out)
    finally:
        pci.close()


if __name__ == "__main__":
    main()
