#!/usr/bin/python
#
# Python pciid library
# Binary database format parser
#
# (c) 2025 Steven Noonan
# Licensed under the MIT license
#

from typing import Optional, Dict, List, Tuple
from array import array
import bisect

Subvendor = Tuple[int, int, str]
Device = Tuple[int, str, List[Subvendor]]
VendorDict = Dict[int, Tuple[str, List[Device]]]
ClassDict = Dict[int, Tuple[str, Dict[int, Tuple[str, Dict[int, str]]]]]


def _clamp(x: int, low: int, high: int) -> int:
    return max(low, min(x, high))


# ---------- String pool ----------
class _StringPool:
    __slots__ = ("_id_of", "vec")

    def __init__(self) -> None:
        self._id_of: Dict[str, int] = {}
        self.vec: List[str] = []

    def intern(self, s: str) -> int:
        # Normalize whitespace minimally (pci.ids often has single-spaces already)
        if s in self._id_of:
            return self._id_of[s]
        i = len(self.vec)
        self.vec.append(s)
        self._id_of[s] = i
        return i

    def get(self, sid: int) -> str:
        return self.vec[sid]


# ---------- Parser for plaintext pci.ids ----------
def _parse_pci_ids(path: str) -> Tuple[VendorDict, ClassDict]:
    """
    Returns:
      vendors: dict[vendor_id] = (vendor_name, list[(dev_id, dev_name, list[(subven, subdev, subname)])])
      classes: dict[base] = (base_name, dict[sub] = (sub_name, dict[prog_if] = prog_if_name))
    """
    vendors: VendorDict = {}
    classes: ClassDict = {}

    in_classes = False
    cur_vendor: Optional[int] = None
    cur_device: Optional[int] = None
    cur_base: Optional[int] = None
    cur_sub: Optional[int] = None

    with open(path, "r", encoding="utf-8", errors="replace") as f:
        for raw in f:
            line = raw.rstrip("\n")
            if not line or line.startswith("#"):
                continue

            if line.startswith("C "):
                in_classes = True
                parts = line.split(None, 2)  # ['C','02','Network controller']
                if len(parts) >= 3:
                    base = int(parts[1], 16)
                    name = parts[2]
                    classes[base] = (name, {})
                    cur_base = base
                    cur_sub = None
                continue

            if not in_classes:
                # Vendors / devices / subsystems
                if line[0] != "\t":
                    tok = line.split(None, 1)
                    if len(tok) >= 1 and len(tok[0]) == 4:  # vendor id
                        ven = int(tok[0], 16)
                        name = tok[1] if len(tok) > 1 else ""
                        vendors[ven] = (name, [])
                        cur_vendor, cur_device = ven, None
                    continue

                if line.startswith("\t\t"):
                    s = line.strip()
                    # "ssss vvvv  name"
                    tok = s.split(None, 2)
                    if len(tok) >= 2:
                        subven = int(tok[0], 16)
                        subdev = int(tok[1], 16)
                        name = tok[2] if len(tok) > 2 else ""
                        assert cur_vendor is not None
                        vendors[cur_vendor][1][-1][2].append((subven, subdev, name))
                    continue

                if line.startswith("\t"):
                    s = line.strip()
                    tok = s.split(None, 1)
                    dev = int(tok[0], 16)
                    name = tok[1] if len(tok) > 1 else ""
                    assert cur_vendor is not None
                    vendors[cur_vendor][1].append((dev, name, []))
                    cur_device = dev
                    continue
            else:
                # Classes / subclasses / prog-if
                if line.startswith("\t") and not line.startswith("\t\t"):
                    s = line.strip()
                    tok = s.split(None, 1)
                    sub = int(tok[0], 16)
                    name = tok[1] if len(tok) > 1 else ""
                    assert cur_base is not None
                    classes[cur_base][1][sub] = (name, {})
                    cur_sub = sub
                    continue

                if line.startswith("\t\t"):
                    s = line.strip()
                    tok = s.split(None, 1)
                    pi = int(tok[0], 16)
                    name = tok[1] if len(tok) > 1 else ""
                    assert cur_base is not None
                    assert cur_sub is not None
                    classes[cur_base][1][cur_sub][1][pi] = name
                    continue

    return vendors, classes


# ---------- Loader building compact arrays ----------
class PciDbText:
    # Row layouts (kept implicit via parallel arrays):
    # Vendors: vendor_ids[H], vendor_name_sid[I], vendor_dev_start[I], vendor_dev_count[I]
    # Devices: device_ids[H], device_name_sid[I], dev_sub_start[I], dev_sub_count[I]
    # Subsys : subvendor_ids[H], subdevice_ids[H], subsys_name_sid[I]
    # Classes: class_base_sid[256 * I]
    #          subclass_keys[H], subclass_name_sid[I], subclass_pi_start[I], subclass_pi_count[I]
    #          prog_if_vals[B], prog_if_name_sid[I]

    def __init__(self, pci_ids_path: str):
        vendors: VendorDict
        classes: ClassDict

        # Parse to high-level
        vendors, classes = _parse_pci_ids(pci_ids_path)
        if not vendors or not classes:
            raise ValueError("Corrupt or empty text database")

        # Build string pool
        sp = _StringPool()
        for ven, (vname, devs) in vendors.items():
            sp.intern(vname)
            for did, dname, sublist in devs:
                sp.intern(dname)
                for sv, sd, sname in sublist:
                    sp.intern(sname)
        for base, (bname, subs) in classes.items():
            sp.intern(bname)
            for sub, (sname, pifs) in subs.items():
                sp.intern(sname)
                for pi, piname in pifs.items():
                    sp.intern(piname)

        # Vendors/devices/subsystems → compact arrays
        self.vendor_ids = array("H")
        self.vendor_name_sid = array("I")
        self.vendor_dev_start = array("I")
        self.vendor_dev_count = array("I")

        self.device_ids = array("H")
        self.device_name_sid = array("I")
        self.dev_sub_start = array("I")
        self.dev_sub_count = array("I")

        self.subvendor_ids = array("H")
        self.subdevice_ids = array("H")
        self.subsys_name_sid = array("I")

        # Sorted vendors
        for ven_id in sorted(vendors.keys()):
            vname, devs = vendors[ven_id]
            devs.sort(key=lambda d: d[0])

            dev_start = len(self.device_ids)
            for dev_id, dname, sublist in devs:
                sublist.sort(key=lambda x: (x[0], x[1]))
                sub_start = len(self.subvendor_ids)
                for sv, sd, sname in sublist:
                    self.subvendor_ids.append(sv & 0xFFFF)
                    self.subdevice_ids.append(sd & 0xFFFF)
                    self.subsys_name_sid.append(sp.intern(sname))
                self.device_ids.append(dev_id & 0xFFFF)
                self.device_name_sid.append(sp.intern(dname))
                self.dev_sub_start.append(sub_start)
                self.dev_sub_count.append(len(self.subvendor_ids) - sub_start)

            self.vendor_ids.append(ven_id & 0xFFFF)
            self.vendor_name_sid.append(sp.intern(vname))
            self.vendor_dev_start.append(dev_start)
            self.vendor_dev_count.append(len(self.device_ids) - dev_start)

        # Classes
        self.class_base_sid = array("I", [0] * 256)
        for base, (bname, _) in classes.items():
            self.class_base_sid[base & 0xFF] = sp.intern(bname)

        self.subclass_keys = array("H")
        self.subclass_name_sid = array("I")
        self.subclass_pi_start = array("I")
        self.subclass_pi_count = array("I")

        self.prog_if_vals = array("B")
        self.prog_if_name_sid = array("I")

        for base in sorted(classes.keys()):
            _, subs = classes[base]
            for sub in sorted(subs.keys()):
                sname, pifs = subs[sub]
                start = len(self.prog_if_vals)
                for pi in sorted(pifs.keys()):
                    self.prog_if_vals.append(pi & 0xFF)
                    self.prog_if_name_sid.append(sp.intern(pifs[pi]))
                count = len(self.prog_if_vals) - start
                key = ((base & 0xFF) << 8) | (sub & 0xFF)
                self.subclass_keys.append(key)
                self.subclass_name_sid.append(sp.intern(sname))
                self.subclass_pi_start.append(start)
                self.subclass_pi_count.append(count)

        # Keep vendor_ids as a Python list for bisect speed (array works too, but list is fine)
        self._vendor_ids_list = list(self.vendor_ids)
        self._subclass_keys_list = list(self.subclass_keys)

        self._sp = sp

    # ----- lookup helpers -----
    def _vendor_index(self, vendor_id: int) -> int:
        i = bisect.bisect_left(self._vendor_ids_list, vendor_id & 0xFFFF)
        if i >= len(self._vendor_ids_list) or self._vendor_ids_list[i] != (
            vendor_id & 0xFFFF
        ):
            return -1
        return i

    def _find_device_in_vendor(self, v_idx: int, device_id: int) -> int:
        start = self.vendor_dev_start[v_idx]
        count = self.vendor_dev_count[v_idx]
        lo, hi = start, start + count
        did = device_id & 0xFFFF
        # manual bisect over device_ids array
        arr = self.device_ids
        while lo < hi:
            mid = (lo + hi) // 2
            if arr[mid] < did:
                lo = mid + 1
            else:
                hi = mid
        if lo >= start + count or arr[lo] != did:
            return -1
        return lo

    def _find_subsystem_in_device(self, d_idx: int, subven: int, subdev: int) -> int:
        s_start = self.dev_sub_start[d_idx]
        s_count = self.dev_sub_count[d_idx]
        lo, hi = s_start, s_start + s_count
        key = ((subven & 0xFFFF) << 16) | (subdev & 0xFFFF)
        # two parallel arrays; compare (sv,sd)
        while lo < hi:
            mid = (lo + hi) // 2
            cmp_key = (self.subvendor_ids[mid] << 16) | self.subdevice_ids[mid]
            if cmp_key < key:
                lo = mid + 1
            else:
                hi = mid
        if lo >= s_start + s_count:
            return -1
        if self.subvendor_ids[lo] != (subven & 0xFFFF) or self.subdevice_ids[lo] != (
            subdev & 0xFFFF
        ):
            return -1
        return lo

    def _subclass_index(self, base: int, sub: int) -> int:
        key = ((base & 0xFF) << 8) | (sub & 0xFF)
        i = bisect.bisect_left(self._subclass_keys_list, key)
        if i >= len(self._subclass_keys_list) or self._subclass_keys_list[i] != key:
            return -1
        return i

    # ----- public API -----
    def get_vendor_name(self, vendor_id: int) -> Optional[str]:
        i = self._vendor_index(vendor_id)
        if i < 0:
            return None
        sid = self.vendor_name_sid[i]
        return self._sp.get(sid)

    def get_device_name(self, vendor_id: int, device_id: int) -> Optional[str]:
        vi = self._vendor_index(vendor_id)
        if vi < 0:
            return None
        di = self._find_device_in_vendor(vi, device_id)
        if di < 0:
            return None
        sid = self.device_name_sid[di]
        return self._sp.get(sid)

    def get_subsystem_name(
        self, vendor_id: int, device_id: int, subvendor_id: int, subdevice_id: int
    ) -> Optional[str]:
        vi = self._vendor_index(vendor_id)
        if vi < 0:
            return None
        di = self._find_device_in_vendor(vi, device_id)
        if di < 0:
            return None
        si = self._find_subsystem_in_device(di, subvendor_id, subdevice_id)
        if si < 0:
            return None
        sid = self.subsys_name_sid[si]
        return self._sp.get(sid)

    def get_class_name(
        self, base: int, subclass: Optional[int] = None, prog_if: Optional[int] = None
    ) -> Optional[str]:
        base &= 0xFF
        if subclass is None:
            sid = self.class_base_sid[base]
            return None if sid == 0 else self._sp.get(sid)

        sub = subclass & 0xFF
        i = self._subclass_index(base, sub)
        if i < 0:
            # unknown subclass → fall back to base only
            sid = self.class_base_sid[base]
            return None if sid == 0 else self._sp.get(sid)

        if prog_if is None:
            return self._sp.get(self.subclass_name_sid[i])

        start = self.subclass_pi_start[i]
        count = self.subclass_pi_count[i]
        lo, hi = start, start + count
        piv = prog_if & 0xFF
        # prog_if arrays are parallel
        arr = self.prog_if_vals
        while lo < hi:
            mid = (lo + hi) // 2
            if arr[mid] < piv:
                lo = mid + 1
            else:
                hi = mid
        if lo >= start + count or arr[lo] != piv:
            # fall back to subclass name if specific prog-if not found
            return self._sp.get(self.subclass_name_sid[i])
        return self._sp.get(self.prog_if_name_sid[lo])

    def get_class_name_from_code(
        self, class_code_24bit: int, depth: int = 3
    ) -> Optional[str]:
        base = (class_code_24bit >> 16) & 0xFF
        sub = (class_code_24bit >> 8) & 0xFF
        pi = class_code_24bit & 0xFF
        depth = _clamp(depth, 0, 3)
        if depth > 2:
            name = self.get_class_name(base, sub, pi)
            if name is not None:
                return name
        if depth > 1:
            name = self.get_class_name(base, sub, None)
            if name is not None:
                return name
        return self.get_class_name(base, None, None)

    def describe_device_best_effort(
        self, vendor_id: int, device_id: int, class_code_24bit: Optional[int]
    ) -> str:
        dn: Optional[str]
        vn: Optional[str]
        cn: Optional[str]

        dn = self.get_device_name(vendor_id, device_id)
        if dn:
            vn = self.get_vendor_name(vendor_id) or f"0x{vendor_id:04x}"
            return f"{vn} {dn}"
        vn = self.get_vendor_name(vendor_id)
        cn = self.get_class_name_from_code(class_code_24bit or 0, depth=2)
        vendor_part = vn if vn else f"0x{vendor_id:04x}"
        class_part = cn if cn else "PCI device"
        return f"Unknown {vendor_part} {class_part} (0x{device_id:04x})"

    def close(self) -> None:
        # nothing to release
        pass
