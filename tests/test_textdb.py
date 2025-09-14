# tests/test_textdb.py
from __future__ import annotations
from pciid.api import PciDbText


def test_textdb_known_lookups(pci_ids_text):
    db = PciDbText(str(pci_ids_text))
    assert db.get_vendor_name(0x8086) == "Intel Corporation"
    assert "440FX" in (db.get_device_name(0x8086, 0x1237) or "")
    assert db.describe_device_best_effort(0x10DE, 0x1BA1, 0x030000)

    # Subsystem lookups
    assert (
        db.get_subsystem_name(0x10DE, 0x1BA1, 0x1458, 0x1651)
        == "GeForce GTX 1070 Max-Q"
    )

    # Valid vendor + device, invalid subvendor
    assert db.get_subsystem_name(0x10DE, 0x1BA1, 0x1043, 0x0020) is None
    assert db.get_subsystem_name(0x10DE, 0x1BA1, 0xFFFF, 0xFFFF) is None

    # Large subvendor list checks
    assert db.get_subsystem_name(0x10DE, 0x0020, 0x1043, 0x0200) == "V3400 TNT"
    assert db.get_subsystem_name(0x10DE, 0x0020, 0x1092, 0x8225) == "Viper V550"

    # Test class lookups
    assert db.get_class_name(0x02, 0x00) == "Ethernet controller"
    assert db.get_class_name(0x02, 0x02) == "FDDI network controller"
    assert db.get_class_name(0x02, 0x80) == "Network controller"

    # Test prog_if lookups
    assert db.get_class_name(0x0C, 0x03, 0xBA) == "USB controller"
    assert db.get_class_name(0x0C, 0x03, 0x00) == "UHCI"
    assert db.get_class_name(0x0C, 0x03, 0x40) == "USB4 Host Interface"

    # VGA controller variants
    assert db.get_class_name_from_code(0x030000, 3) == "VGA controller"
    assert db.get_class_name_from_code(0x030000, 2) == "VGA compatible controller"

    # Invalid subclass, valid class
    assert db.get_class_name(0x03, 0x09) == "Display controller"

    db.close()


def test_textdb_unknowns(pci_ids_text):
    db = PciDbText(str(pci_ids_text))

    # Deliberately missing
    assert db.describe_device_best_effort(0x10DE, 0x1234, 0x030000)
    assert db.get_class_name(0xFFFF) is None
    assert db.get_class_name(0xFF) is None
    assert db.get_class_name(0x1F) is None
    assert db.get_class_name(0x00) is None
    assert db.get_vendor_name(0x1234) is None
    assert db.get_device_name(0x10DE, 0x1234) is None
    assert db.get_device_name(0x1234, 0x1234) is None
    assert db.get_subsystem_name(0x10DE, 0x1BA1, 0x1234, 0x1234) is None
    assert db.get_subsystem_name(0x10DE, 0x1234, 0x1234, 0x1234) is None
    assert db.get_subsystem_name(0x1234, 0x1234, 0x1234, 0x1234) is None

    # Best-effort description should fall back to "Unknown <vendor|hex> <class|PCI device>"
    s = db.describe_device_best_effort(0x1234, 0x5678, None)
    assert "Unknown" in s and "0x5678" in s
