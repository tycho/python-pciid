# tests/test_sysfs_topology.py
from __future__ import annotations
from pciid.sysfs import SysfsEnumerator
from pciid.topology import dumps_devices_and_edges, loads_devices_and_edges

def format_resource_lines(device):
    resource_lines = []
    for res in device.resource:
        resource_lines.append(str(res))
    return "\n".join(resource_lines)

def test_sysfs_fake_tree(fake_sysfs, tmp_path):
    enum = SysfsEnumerator(root=str(fake_sysfs))
    devs = enum.scan()

    # We created three: parent + two children
    assert "0000:00:01.0" in devs
    assert "0000:65:00.0" in devs
    assert "0000:66:00.0" in devs
    assert "0000:68:00.0" in devs

    # Bad device, unparsable vendor/device IDs
    assert "0000:67:00.0" not in devs

    assert enum.find_by_bdf(devs, "0000:00:01.0") is not None
    assert enum.find_by_bdf(devs, "0000:67:00.0") is None

    idev = enum.find_by_bdf(devs, "0000:00:01.0")
    assert format_resource_lines(idev) == """\
Region 0: Memory at f9000000 (32-bit, non-prefetchable) [size=16M]
Region 1: Memory at fa000000 (32-bit, non-prefetchable) [size=128K]
Region 2: I/O ports at c000 [size=128]
Expansion ROM at 000c0000 [size=128K]"""

    nv_devs = enum.find_by_vendor(devs, 0x10DE)
    assert len(nv_devs) == 1
    assert nv_devs[0].vendor_id == 0x10DE
    assert enum.find_by_vendor(devs, 0x4321) == []

    nv_devs = enum.find_by_vendor_device(devs, 0x10DE, 0x1DB6)
    assert len(nv_devs) == 1
    assert nv_devs[0].vendor_id == 0x10DE
    assert nv_devs[0].device_id == 0x1DB6
    assert format_resource_lines(nv_devs[0]) == """\
Region 0: Memory at fb000000 (32-bit, non-prefetchable) [size=16M]
Region 1: Memory at 7000000000 (64-bit, prefetchable) [size=32G]
Region 3: Memory at 7800000000 (64-bit, prefetchable) [size=32M]
Region 5: I/O ports at f000 [size=128]
Expansion ROM at fc000000 [size=512K]"""

    # Parentage
    assert devs["0000:65:00.0"].parent_bdf == "0000:00:01.0"
    assert devs["0000:66:00.0"].parent_bdf == "0000:00:01.0"
    assert devs["0000:00:01.0"].parent_bdf in (None, "")  # unparented root

    # SBR: devices affected by resetting secondary bus of the parent of 65:00.0
    origin = devs["0000:65:00.0"]
    affected = {str(d.bdf) for d in enum.sbr_affected(devs, origin)}
    # Expect both children under the same parent
    assert affected == {"0000:65:00.0", "0000:66:00.0", "0000:68:00.0"}

    assert enum.sbr_affected(devs, devs["0000:00:01.0"]) == []

    # JSON round-trip of devices+edges (no name resolution involved)
    js = dumps_devices_and_edges(devs)
    devs2 = loads_devices_and_edges(js)
    assert set(devs.keys()) == set(devs2.keys())
    assert devs2["0000:65:00.0"].parent_bdf == "0000:00:01.0"
