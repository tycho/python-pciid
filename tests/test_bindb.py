# tests/test_bindb.py
from __future__ import annotations
from pciid.api import PciDbText, PciDbBinary


def test_text_vs_bin_parity(pci_ids_text, pci_ids_bin):
    dt = PciDbText(str(pci_ids_text))
    db = PciDbBinary(str(pci_ids_bin))
    for vid, did in [(0x8086, 0x1237), (0x10DE, 0x1DB6)]:
        assert db.get_vendor_name(vid) == dt.get_vendor_name(vid)
        assert db.get_device_name(vid, did) == dt.get_device_name(vid, did)
    assert db.get_subsystem_name(
        0x10DE, 0x1BA1, 0x1458, 0x1651
    ) == dt.get_subsystem_name(0x10DE, 0x1BA1, 0x1458, 0x1651)
    assert db.describe_device_best_effort(
        0x10DE, 0x1234, 0x030000
    ) == dt.describe_device_best_effort(0x10DE, 0x1234, 0x030000)
    assert db.describe_device_best_effort(
        0x10DE, 0x1BA1, 0x030000
    ) == dt.describe_device_best_effort(0x10DE, 0x1BA1, 0x030000)

    # Valid vendor + device, invalid subvendor
    assert db.get_subsystem_name(
        0x10DE, 0x1BA1, 0x1043, 0x0020
    ) == dt.get_subsystem_name(0x10DE, 0x1BA1, 0x1043, 0x0020)
    assert db.get_subsystem_name(
        0x10DE, 0x1BA1, 0xFFFF, 0xFFFF
    ) == dt.get_subsystem_name(0x10DE, 0x1BA1, 0xFFFF, 0xFFFF)

    # Large subvendor list checks
    assert db.get_subsystem_name(
        0x10DE, 0x0020, 0x1043, 0x0200
    ) == dt.get_subsystem_name(0x10DE, 0x0020, 0x1043, 0x0200)
    assert db.get_subsystem_name(
        0x10DE, 0x0020, 0x1092, 0x8225
    ) == dt.get_subsystem_name(0x10DE, 0x0020, 0x1092, 0x8225)

    # invalid device ids
    assert db.get_device_name(0x10DE, 0x0000) is None
    assert db.get_device_name(0x10DE, 0xFFFF) is None
    assert db.get_subsystem_name(0x10DE, 0x0000, 0x0000, 0x000) is None
    assert db.get_subsystem_name(0x10DE, 0xFFFF, 0x0000, 0x000) is None

    # classes
    assert db.get_class_name(0xFFFF) is None
    assert db.get_class_name(0xFF) is None
    assert db.get_class_name(0x1F) is None
    assert db.get_class_name(0x00) is None
    assert db.get_class_name(0x02, 0x00) == dt.get_class_name(0x02, 0x00)
    assert db.get_class_name_from_code(0x030000, 3) == dt.get_class_name_from_code(
        0x030000, 3
    )
    assert db.get_class_name_from_code(0x030000, 2) == dt.get_class_name_from_code(
        0x030000, 2
    )
    assert db.get_class_name(0x02, 0x02) == dt.get_class_name(0x02, 0x02)
    assert db.get_class_name(0x02, 0x80) == dt.get_class_name(0x02, 0x80)

    # Test prog_if lookups
    assert db.get_class_name(0x0C, 0x03, 0xBA) == dt.get_class_name(0x0C, 0x03, 0xBA)
    assert db.get_class_name(0x0C, 0x03, 0x00) == dt.get_class_name(0x0C, 0x03, 0x00)
    assert db.get_class_name(0x0C, 0x03, 0x40) == dt.get_class_name(0x0C, 0x03, 0x40)
    assert db.get_class_name(0x0C, 0x03, 0xFF) == dt.get_class_name(0x0C, 0x03, 0xFF)

    # deliberately missing
    assert db.describe_device_best_effort(
        0x10DE, 0x1234, 0x030000
    ) == dt.describe_device_best_effort(0x10DE, 0x1234, 0x030000)
    assert db.get_vendor_name(0x0000) == dt.get_vendor_name(0x0000)
    assert db.get_vendor_name(0xFFFF) == dt.get_vendor_name(0xFFFF)
    assert db.get_vendor_name(0x1234) == dt.get_vendor_name(0x1234)
    assert db.get_device_name(0x1234, 0x1234) == dt.get_device_name(0x1234, 0x1234)
    assert db.get_subsystem_name(
        0x1234, 0x1234, 0x1234, 0x1234
    ) == dt.get_subsystem_name(0x1234, 0x1234, 0x1234, 0x1234)
    assert db.get_class_name_from_code(0x1F0000, 3) == dt.get_class_name_from_code(
        0x1F0000, 3
    )
    assert db.get_class_name_from_code(0x1F0000, 2) == dt.get_class_name_from_code(
        0x1F0000, 2
    )
    assert db.get_class_name_from_code(0x1F0000, 1) == dt.get_class_name_from_code(
        0x1F0000, 1
    )

    db.close()


def test_bin_vs_uncompressed_parity(pci_ids_bin, pci_ids_bin_uncompressed):
    dt = PciDbBinary(str(pci_ids_bin))
    db = PciDbBinary(str(pci_ids_bin_uncompressed))
    for vid, did in [(0x8086, 0x1237), (0x10DE, 0x1DB6)]:
        assert db.get_vendor_name(vid) == dt.get_vendor_name(vid)
        assert db.get_device_name(vid, did) == dt.get_device_name(vid, did)
    # classes
    assert db.get_class_name(0x02, 0x00) == dt.get_class_name(0x02, 0x00)
    assert db.get_class_name_from_code(0x030000, 3) == dt.get_class_name_from_code(
        0x030000, 3
    )
    assert db.get_class_name_from_code(0x030000, 2) == dt.get_class_name_from_code(
        0x030000, 2
    )
    db.close()
