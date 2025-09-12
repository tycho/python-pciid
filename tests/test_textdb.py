# tests/test_textdb.py
from __future__ import annotations
from pciid.api import PciDbText

def test_textdb_known_lookups(pci_ids_text):
    db = PciDbText(str(pci_ids_text))
    assert db.get_vendor_name(0x8086) == "Intel Corporation"
    assert "440FX" in (db.get_device_name(0x8086, 0x1237) or "")
    assert db.get_subsystem_name(0x10de, 0x1ba1, 0x1458, 0x1651) == "GeForce GTX 1070 Max-Q"
    assert db.describe_device_best_effort(0x10de, 0x1ba1, 0x030000)

    # Class base 0x02 / subclass 0x00
    assert db.get_class_name(0x02, 0x00) in {"Ethernet controller", "Ethernet Controller"}

    # VGA controller variants
    assert db.get_class_name_from_code(0x030000, 3) == "VGA controller"
    assert db.get_class_name_from_code(0x030000, 2) == "VGA compatible controller"

    # Deliberately missing
    assert db.describe_device_best_effort(0x10de, 0x1234, 0x030000)
    assert db.get_vendor_name(0x1234) is None
    assert db.get_device_name(0x1234, 0x1234) is None
    assert db.get_subsystem_name(0x1234, 0x1234, 0x1234, 0x1234) is None

    db.close()

def test_textdb_unknowns(pci_ids_text):
    db = PciDbText(str(pci_ids_text))
    assert db.get_vendor_name(0xdead) is None
    assert db.get_device_name(0x8086, 0xbeef) is None
    assert db.get_class_name(0x07, 0x09) is None
    # Best-effort description should fall back to "Unknown <vendor|hex> <class|PCI device>"
    s = db.describe_device_best_effort(0x1234, 0x5678, None)
    assert "Unknown" in s and "0x5678" in s
