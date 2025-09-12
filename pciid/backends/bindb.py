#!/usr/bin/python
#
# Python pciid library
# Binary database format parser
#
# (c) 2025 Steven Noonan
# Licensed under the MIT license
#

import mmap, struct, zlib, bisect
from typing import Optional

MAGIC = 0x42494350
HEADER_FMT = "<IHH" + "I" * 26
VendorRow = struct.Struct("<H I I I")
DeviceRow = struct.Struct("<H I I I")
SubsysRow = struct.Struct("<H H I")
SubclassRow = struct.Struct("<H I I I")
ProgIfRow = struct.Struct("<B I")


def _clamp(x, low, high):
    return max(low, min(x, high))


class PciIds:
    def __init__(self, path: str):
        self.f = open(path, "rb")
        self.mm = mmap.mmap(self.f.fileno(), 0, access=mmap.ACCESS_READ)
        self._parse_header()
        self._load_vendor_index()
        self._load_device_index()
        self._load_subsys_index()
        self._load_class_indexes()
        # Strings
        self.block_count = struct.unpack_from("<I", self.mm, self.str_dir_off)[0]
        self.block_offsets = list(
            struct.unpack_from(
                "<" + "I" * self.block_count, self.mm, self.str_dir_off + 4
            )
        )
        self._block_cache = {}

    def close(self):
        self.mm.close()
        self.f.close()

    # ----- header/indices -----
    def _parse_header(self):
        tup = struct.unpack_from(HEADER_FMT, self.mm, 0)
        if tup[0] != MAGIC:
            raise ValueError("bad magic")
        fields = tup[3:]
        names = [
            "str_dir_off",
            "str_dir_len",
            "str_blk_off",
            "str_blk_len",
            "vendors_off",
            "vendors_len",
            "devices_off",
            "devices_len",
            "subsys_off",
            "subsys_len",
            "class_base_off",
            "class_base_len",
            "subclass_off",
            "subclass_len",
            "prog_if_off",
            "prog_if_len",
            "misc_off",
            "misc_len",
            "r1_off",
            "r1_len",
            "r2_off",
            "r2_len",
            "r3_off",
            "r3_len",
            "r4_off",
            "r4_len",
        ]
        for i, n in enumerate(names):
            setattr(self, n, fields[i])

    def _load_vendor_index(self):
        n = self.vendors_len // VendorRow.size
        self._vendor_rows_off = self.vendors_off
        self._vendor_count = n
        self.vendor_ids = [
            VendorRow.unpack_from(self.mm, self._vendor_rows_off + i * VendorRow.size)[
                0
            ]
            for i in range(n)
        ]

    def _load_device_index(self):
        self._device_rows_off = self.devices_off
        self._device_count = self.devices_len // DeviceRow.size

    def _load_subsys_index(self):
        self._subsys_off = self.subsys_off
        self._subsys_count = self.subsys_len // SubsysRow.size

    def _load_class_indexes(self):
        self._class_base_off = self.class_base_off
        self._subclass_off = self.subclass_off
        self._subclass_count = self.subclass_len // SubclassRow.size
        self._subclass_keys = [
            SubclassRow.unpack_from(self.mm, self._subclass_off + i * SubclassRow.size)[
                0
            ]
            for i in range(self._subclass_count)
        ]
        self._prog_if_off = self.prog_if_off

    # ----- string decoding -----
    def _load_block_payload(self, block_idx: int):
        if block_idx in self._block_cache:
            return self._block_cache[block_idx]
        off = self.block_offsets[block_idx]
        end = (
            self.block_offsets[block_idx + 1]
            if block_idx + 1 < len(self.block_offsets)
            else self.str_blk_off + self.str_blk_len
        )
        raw = bytes(self.mm[off:end])
        try:
            payload = zlib.decompress(raw)
        except zlib.error:
            payload = raw
        self._block_cache[block_idx] = payload
        return payload

    def _decode_string_in_block(self, payload: bytes, index_in_block: int) -> str:
        p = 0
        stride = struct.unpack_from("<H", payload, p)[0]
        p += 2
        base = None
        for i in range(index_in_block + 1):
            kind = struct.unpack_from("<H", payload, p)[0]
            p += 2
            if kind == 1:
                slen = struct.unpack_from("<I", payload, p)[0]
                p += 4
                s = payload[p : p + slen].decode("utf-8")
                p += slen
                base = s
            else:
                pref = struct.unpack_from("<H", payload, p)[0]
                p += 2
                slen = struct.unpack_from("<I", payload, p)[0]
                p += 4
                suf = payload[p : p + slen].decode("utf-8")
                p += slen
                s = base[:pref] + suf
            if i == index_in_block:
                return s
        raise IndexError

    def get_string(self, string_id: int) -> str:
        stride = 32  # must match builder
        block_idx = string_id // stride
        idx = string_id % stride
        payload = self._load_block_payload(block_idx)
        return self._decode_string_in_block(payload, idx)

    # ----- helpers to read rows -----
    def _vendor_row_at(self, idx: int):
        return VendorRow.unpack_from(
            self.mm, self._vendor_rows_off + idx * VendorRow.size
        )

    def _device_row_at(self, idx: int):
        return DeviceRow.unpack_from(
            self.mm, self._device_rows_off + idx * DeviceRow.size
        )

    def _subsys_row_at(self, idx: int):
        return SubsysRow.unpack_from(self.mm, self._subsys_off + idx * SubsysRow.size)

    # ----- lookups -----
    def get_vendor_name(self, vendor_id: int) -> Optional[str]:
        i = bisect.bisect_left(self.vendor_ids, vendor_id)
        if i == self._vendor_count or self.vendor_ids[i] != vendor_id:
            return None
        _, sid, _, _ = self._vendor_row_at(i)
        return self.get_string(sid)

    def get_device_name(self, vendor_id: int, device_id: int) -> Optional[str]:
        i = bisect.bisect_left(self.vendor_ids, vendor_id)
        if i == self._vendor_count or self.vendor_ids[i] != vendor_id:
            return None
        _, _, start, count = self._vendor_row_at(i)
        lo, hi = start, start + count
        while lo < hi:
            mid = (lo + hi) // 2
            did, _, _, _ = self._device_row_at(mid)
            if did < device_id:
                lo = mid + 1
            else:
                hi = mid
        if lo >= start + count:
            return None
        did, sid, _, _ = self._device_row_at(lo)
        return self.get_string(sid) if did == device_id else None

    def get_subsystem_name(
        self, vendor_id: int, device_id: int, subvendor_id: int, subdevice_id: int
    ) -> Optional[str]:
        i = bisect.bisect_left(self.vendor_ids, vendor_id)
        if i == self._vendor_count or self.vendor_ids[i] != vendor_id:
            return None
        _, _, start, count = self._vendor_row_at(i)
        # device
        lo, hi = start, start + count
        while lo < hi:
            mid = (lo + hi) // 2
            did, _, sub_start, sub_count = self._device_row_at(mid)
            if did < device_id:
                lo = mid + 1
            else:
                hi = mid
        if lo >= start + count:
            return None
        did, _, sub_start, sub_count = self._device_row_at(lo)
        if did != device_id:
            return None
        # subsystem
        lo2, hi2 = sub_start, sub_start + sub_count
        while lo2 < hi2:
            mid = (lo2 + hi2) // 2
            sv, sd, _ = self._subsys_row_at(mid)
            if (sv, sd) < (subvendor_id, subdevice_id):
                lo2 = mid + 1
            else:
                hi2 = mid
        if lo2 >= sub_start + sub_count:
            return None
        sv, sd, sid = self._subsys_row_at(lo2)
        return (
            self.get_string(sid) if (sv, sd) == (subvendor_id, subdevice_id) else None
        )

    def get_class_name(
        self, base: int, subclass: Optional[int] = None, prog_if: Optional[int] = None
    ) -> Optional[str]:
        if not (0 <= base < 256):
            return None
        if subclass is None:
            sid = struct.unpack_from("<I", self.mm, self._class_base_off + base * 4)[0]
            return None if sid == 0 else self.get_string(sid)
        key = ((base & 0xFF) << 8) | (subclass & 0xFF)
        i = bisect.bisect_left(self._subclass_keys, key)
        if i == self._subclass_count or self._subclass_keys[i] != key:
            # subclass unknown → fall back to base
            return self.get_class_name(base, None, None)
        _, sname_id, start, count = SubclassRow.unpack_from(
            self.mm, self._subclass_off + i * SubclassRow.size
        )
        if prog_if is None:
            return self.get_string(sname_id)
        lo, hi = start, start + count
        while lo < hi:
            mid = (lo + hi) // 2
            pi, _ = ProgIfRow.unpack_from(
                self.mm, self._prog_if_off + mid * ProgIfRow.size
            )
            if pi < prog_if:
                lo = mid + 1
            else:
                hi = mid
        if lo >= start + count:
            return self.get_string(sname_id)  # fall back to subclass name
        pi, sid = ProgIfRow.unpack_from(
            self.mm, self._prog_if_off + lo * ProgIfRow.size
        )
        return self.get_string(sid) if pi == prog_if else self.get_string(sname_id)

    # Convenience: decode 24-bit class code like 0x030000 -> (03,00,00)
    def get_class_name_from_code(
        self, class_code_24bit: int, depth: int = 3
    ) -> Optional[str]:
        base = (class_code_24bit >> 16) & 0xFF
        sub = (class_code_24bit >> 8) & 0xFF
        pi = (class_code_24bit) & 0xFF
        depth = _clamp(depth, 0, 3)
        # Prefer the most specific that exists
        if depth > 2:
            name = self.get_class_name(base, sub, pi)
            if name is not None:
                return name
        if depth > 1:
            name = self.get_class_name(base, sub, None)
            if name is not None:
                return name
        return self.get_class_name(base, None, None)

    # Best-effort formatter for unknown devices
    def describe_device_best_effort(
        self, vendor_id: int, device_id: int, class_code_24bit: Optional[int]
    ) -> str:
        # If exact vendor+device known, return "Vendor Device"
        dn = self.get_device_name(vendor_id, device_id)
        if dn:
            vn = self.get_vendor_name(vendor_id) or f"0x{vendor_id:04x}"
            return f"{vn} {dn}"

        vn = self.get_vendor_name(vendor_id)
        cn = (
            self.get_class_name_from_code(class_code_24bit, depth=2)
            if class_code_24bit is not None
            else None
        )
        vendor_part = vn if vn else f"0x{vendor_id:04x}"
        class_part = cn if cn else "PCI device"
        return f"Unknown {vendor_part} {class_part} (0x{device_id:04x})"
