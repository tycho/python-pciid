# tests/test_weird_topology.py
from __future__ import annotations
from pathlib import Path
from pciid.sysfs import SysfsEnumerator
from pciid.topology import dumps_devices_and_edges, loads_devices_and_edges


def test_unparented_device(tmp_path: Path):
    root = tmp_path / "devices"
    real = tmp_path / "real"
    root.mkdir()
    real.mkdir()
    # Real path NOT nested under a parent BDF => parent_bdf remains None
    real_dev = real / "0000:65:00.0"
    real_dev.mkdir(parents=True)
    (real_dev / "vendor").write_text("0x10de\n")
    (real_dev / "device").write_text("0x1db6\n")
    (real_dev / "class").write_text("0x030000\n")
    (real_dev / "revision").write_text("0x00\n")
    (real_dev / "subsystem_vendor").write_text("0x0000\n")
    (real_dev / "subsystem_device").write_text("0x0000\n")
    (root / "0000:65:00.0").symlink_to(real_dev, target_is_directory=True)

    enum = SysfsEnumerator(root=str(root))
    devs = enum.scan()
    assert devs["0000:65:00.0"].parent_bdf is None

    # JSON round-trip preserves unparented state
    js = dumps_devices_and_edges(devs)
    devs2 = loads_devices_and_edges(js)
    assert devs2["0000:65:00.0"].parent_bdf is None
