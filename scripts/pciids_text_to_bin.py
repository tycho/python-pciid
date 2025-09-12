#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import sys, struct, zlib, argparse
from collections import defaultdict

MAGIC = 0x42494350  # 'PCIB'
VERSION = 1


# ------------ String pool (two-phase: collect -> finalize -> write) ------------
class StringPool:
    """
    Dedup strings, assign IDs at finalize(), then emit block-front-coded blocks.
    IDs are stable after finalize(); we DO NOT reorder after that.
    """

    def __init__(self, block_stride=32, compress_level=6):
        self._seen = set()
        self._strings = []  # temporary (unique strings, insertion order)
        self._final = False
        self.block_stride = block_stride
        self.compress_level = compress_level
        self.id_of = {}  # str -> id (after finalize)
        self.vec = []  # id -> str (after finalize)

    def add(self, s: str) -> None:
        if s not in self._seen:
            self._seen.add(s)
            self._strings.append(s)

    def finalize(self, sort="lex"):
        assert not self._final
        if sort == "lex":
            self.vec = sorted(self._strings)
        else:
            self.vec = list(self._strings)
        for i, s in enumerate(self.vec):
            self.id_of[s] = i
        self._final = True

    def _emit_block(self, items):
        # Block front-coding; first in block is full, others are prefix-delta vs block base
        payload = bytearray()
        payload += struct.pack("<H", self.block_stride)
        base = None
        for i, s in enumerate(items):
            if (i % self.block_stride) == 0 or base is None:
                bs = s.encode("utf-8")
                payload += struct.pack("<H", 1)  # kind=full
                payload += struct.pack("<I", len(bs))
                payload += bs
                base = s
            else:
                # compute common prefix against block base
                pref = 0
                maxp = min(len(base), len(s))
                while pref < maxp and base[pref] == s[pref]:
                    pref += 1
                suf = s[pref:].encode("utf-8")
                payload += struct.pack("<H", 2)  # kind=delta
                payload += struct.pack("<H", pref)
                payload += struct.pack("<I", len(suf))
                payload += suf
        if self.compress_level is not None:
            payload = zlib.compress(bytes(payload), self.compress_level)
        return payload

    def write(self, f, base_offset):
        assert self._final
        # Build blocks
        block_offsets = []
        blocks_buf = bytearray()
        stride = self.block_stride
        # Directory will be written first; we need its size to compute offsets → so we compute offsets
        # assuming directory is: 4 (count) + 4*block_count
        block_count = (len(self.vec) + stride - 1) // stride
        dir_size = 4 + 4 * block_count
        dir_off = base_offset
        blocks_off = dir_off + dir_size

        # Emit blocks
        off = blocks_off
        for i in range(0, len(self.vec), stride):
            block = self.vec[i : i + stride]
            blob = self._emit_block(block)
            block_offsets.append(off)
            blocks_buf += blob
            off += len(blob)

        # Write directory then blocks
        f.seek(dir_off)
        f.write(struct.pack("<I", block_count))
        for boff in block_offsets:
            f.write(struct.pack("<I", boff))
        f.write(blocks_buf)

        return (
            dir_off,
            4 + 4 * block_count,
            blocks_off,
            len(blocks_buf),
            block_count,
            stride,
        )


# ------------ Robust pci.ids parser (vendors/devices/subsystems + classes) ------------
def parse_pci_ids(path):
    """
    Returns:
      vendors: dict[vendor_id] = (vendor_name: str, devices: list[(dev_id, dev_name, subs: list[(subven, subdev, name)])])
      classes: dict[base] = (base_name: str, subclasses: dict[sub] = (sub_name: str, progifs: dict[pi] = name))
    """
    vendors = {}
    classes = {}
    in_classes = False

    cur_vendor = None
    cur_device = None
    cur_base = None
    cur_sub = None

    with open(path, "r", encoding="utf-8", errors="replace") as f:
        for raw in f:
            line = raw.rstrip("\n")
            if not line or line.startswith("#"):
                continue

            # Class section starts with lines like: "C 02  Network controller"
            if line.startswith("C "):
                in_classes = True
                parts = line.split(None, 2)  # ['C', '02', 'Network controller']
                if len(parts) >= 3 and len(parts[1]) <= 2:
                    base = int(parts[1], 16)
                    name = parts[2]
                    classes[base] = [name, {}]
                    cur_base = base
                    cur_sub = None
                continue

            if not in_classes:
                # Vendors/devices/subsystems section
                if line[0] != "\t":
                    # Vendor line: "vvvv  Vendor Name"
                    tok = line.split(None, 1)
                    if len(tok[0]) == 4:
                        ven = int(tok[0], 16)
                        name = tok[1] if len(tok) > 1 else ""
                        vendors[ven] = [name, []]
                        cur_vendor, cur_device = ven, None
                        continue

                if line.startswith("\t") and not line.startswith("\t\t"):
                    # Device line under current vendor: "\tdddd  Device Name"
                    s = line.strip()
                    tok = s.split(None, 1)
                    dev = int(tok[0], 16)
                    name = tok[1] if len(tok) > 1 else ""
                    vendors[cur_vendor][1].append([dev, name, []])
                    cur_device = dev
                    continue

                if line.startswith("\t\t"):
                    # Subsystem line under current device: "\t\tssss vvvv  Name" (subvendor, subdevice)
                    s = line.strip()
                    # It is "ssss vvvv  name" → two hex tokens, then the rest
                    tok = s.split(None, 2)
                    if len(tok) >= 2:
                        subven = int(tok[0], 16)
                        subdev = int(tok[1], 16)
                        name = tok[2] if len(tok) > 2 else ""
                        vendors[cur_vendor][1][-1][2].append((subven, subdev, name))
                    continue

            else:
                # Class/subclass/prog-if section
                if line[0] != "\t":
                    # Another base line without 'C ' (rare), handle defensively if present like "02  Network controller"
                    tok = line.split(None, 1)
                    if len(tok) >= 2 and len(tok[0]) <= 2:
                        base = int(tok[0], 16)
                        name = tok[1]
                        classes[base] = [name, {}]
                        cur_base = base
                        cur_sub = None
                    continue

                if line.startswith("\t") and not line.startswith("\t\t"):
                    # Subclass: "\tss  Subclass Name"
                    s = line.strip()
                    tok = s.split(None, 1)
                    sub = int(tok[0], 16)
                    name = tok[1] if len(tok) > 1 else ""
                    classes[cur_base][1][sub] = [name, {}]
                    cur_sub = sub
                    continue

                if line.startswith("\t\t"):
                    # Programming interface under current (base, sub): "\t\tpp  Prog-If Name"
                    s = line.strip()
                    tok = s.split(None, 1)
                    pi = int(tok[0], 16)
                    name = tok[1] if len(tok) > 1 else ""
                    classes[cur_base][1][cur_sub][1][pi] = name
                    continue

    return vendors, classes


# ------------ Binary layout ------------
HEADER_FMT = "<IHH" + "I" * 26  # magic,u16 ver,u16 flags + 26 u32s

VendorRow = struct.Struct("<H I I I")  # vendor_id, vendor_name_id, dev_start, dev_count
DeviceRow = struct.Struct("<H I I I")  # device_id, device_name_id, sub_start, sub_count
SubsysRow = struct.Struct("<H H I")  # subvendor_id, subdevice_id, name_id
SubclassRow = struct.Struct(
    "<H I I I"
)  # key=(base<<8|sub), subclass_name_id, start, count
ProgIfRow = struct.Struct("<B I")  # prog_if, name_id


def build(args):
    vendors, classes = parse_pci_ids(args.input)

    # Collect all strings first (two-phase)
    sp = StringPool(block_stride=32, compress_level=(None if args.no_compress else 6))

    def add_all_strings():
        for ven_id, (vname, devs) in vendors.items():
            sp.add(vname)
            for dev_id, dname, subs in devs:
                sp.add(dname)
                for sv, sd, sname in subs:
                    sp.add(sname)
        for base, (bname, subs) in classes.items():
            sp.add(bname)
            for sub, (sname, pifs) in subs.items():
                sp.add(sname)
                for pi, piname in pifs.items():
                    sp.add(piname)

    add_all_strings()
    sp.finalize(sort="lex")  # lexicographic improves prefix sharing

    # Flatten structures → pack with finalized string IDs
    vendor_rows = []
    device_rows = []
    subsys_rows = []

    for ven_id in sorted(vendors.keys()):
        vname, devs = vendors[ven_id]
        devs.sort(key=lambda d: d[0])
        dev_start = len(device_rows)
        for dev_id, dname, subs in devs:
            subs.sort(key=lambda x: (x[0], x[1]))
            sub_start = len(subsys_rows)
            for sv, sd, sname in subs:
                subsys_rows.append(SubsysRow.pack(sv, sd, sp.id_of[sname]))
            device_rows.append(
                DeviceRow.pack(
                    dev_id, sp.id_of[dname], sub_start, len(subsys_rows) - sub_start
                )
            )
        vendor_rows.append(
            VendorRow.pack(
                ven_id, sp.id_of[vname], dev_start, len(device_rows) - dev_start
            )
        )

    # Classes
    class_base = [0] * 256  # dense base-class table
    for base, (bname, _) in classes.items():
        class_base[base] = sp.id_of[bname]

    subclass_rows = []
    prog_if_rows = []
    for base in sorted(classes.keys()):
        _, subs = classes[base]
        for sub in sorted(subs.keys()):
            sname, pifs = subs[sub]
            start = len(prog_if_rows)
            for pi in sorted(pifs.keys()):
                prog_if_rows.append(ProgIfRow.pack(pi, sp.id_of[pifs[pi]]))
            count = len(prog_if_rows) - start
            key = ((base & 0xFF) << 8) | (sub & 0xFF)
            subclass_rows.append(SubclassRow.pack(key, sp.id_of[sname], start, count))

    with open(args.output, "wb") as f:
        # Header placeholder
        f.write(b"\x00" * struct.calcsize(HEADER_FMT))

        # Strings
        str_dir_off = f.tell()
        (str_dir_off, str_dir_len, str_blk_off, str_blk_len, block_count, stride) = (
            sp.write(f, str_dir_off)
        )

        # Vendors/devices/subsystems
        vendors_off = f.tell()
        f.write(b"".join(vendor_rows))
        vendors_len = f.tell() - vendors_off

        devices_off = f.tell()
        f.write(b"".join(device_rows))
        devices_len = f.tell() - devices_off

        subsys_off = f.tell()
        f.write(b"".join(subsys_rows))
        subsys_len = f.tell() - subsys_off

        # Classes
        class_base_off = f.tell()
        f.write(struct.pack("<" + "I" * 256, *class_base))
        class_base_len = f.tell() - class_base_off

        subclass_off = f.tell()
        f.write(b"".join(subclass_rows))
        subclass_len = f.tell() - subclass_off

        prog_if_off = f.tell()
        f.write(b"".join(prog_if_rows))
        prog_if_len = f.tell() - prog_if_off

        # No misc
        misc_off = f.tell()
        misc_len = 0

        # Header
        flags = 0
        fields = [
            str_dir_off,
            str_dir_len,
            str_blk_off,
            str_blk_len,
            vendors_off,
            vendors_len,
            devices_off,
            devices_len,
            subsys_off,
            subsys_len,
            class_base_off,
            class_base_len,
            subclass_off,
            subclass_len,
            prog_if_off,
            prog_if_len,
            misc_off,
            misc_len,
            0,
            0,
            0,
            0,
            0,
            0,
            0,
            0,
        ]
        hdr = struct.pack("<IHH", MAGIC, VERSION, flags) + struct.pack(
            "<" + "I" * len(fields), *fields
        )
        f.seek(0)
        f.write(hdr)


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("-i", "--input", help="pci.ids text path", required=True)
    ap.add_argument("-o", "--output", help="pci.ids binary output path", required=True)
    ap.add_argument(
        "--no-compress",
        action="store_true",
        help="disable zlib compression of string blocks",
    )
    args = ap.parse_args()
    build(args)
