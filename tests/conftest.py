# tests/conftest.py
from __future__ import annotations
import os, stat
from pathlib import Path
import importlib.util
import types
import pytest

MINIMAL_PCI_IDS = """\
8086  Intel Corporation
\t1237  440FX - 82441FX PMC
10de  NVIDIA Corporation
\t1db6  GV100GL [Tesla V100 PCIe 32GB]
\t1ba1  GP104M [GeForce GTX 1070 Mobile]
\t\t1458 1651  GeForce GTX 1070 Max-Q
C 02  Network controller
\t00  Ethernet controller
C 03  Display controller
\t00  VGA compatible controller
\t\t00  VGA controller
\t\t01  8514 controller
\t01  XGA compatible controller
\t02  3D controller
\t80  Display controller
C 06  Bridge
\t04  PCI bridge
"""

@pytest.fixture
def pci_ids_text(tmp_path: Path) -> Path:
    p = tmp_path / "pci.ids"
    p.write_text(MINIMAL_PCI_IDS, encoding="utf-8")
    return p

def _import_converter(root: Path):
    mod_path = root / "scripts" / "pciids_text_to_bin.py"
    spec = importlib.util.spec_from_file_location("pciids_text_to_bin", str(mod_path))
    if spec is None or spec.loader is None:
        raise RuntimeError("cannot import converter")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod

@pytest.fixture
def pci_ids_bin(tmp_path: Path, pci_ids_text: Path) -> Path:
    # Use in-repo converter to build a bin file
    root = Path(__file__).resolve().parents[1]
    conv = _import_converter(root)
    out = tmp_path / "pci.ids.bin"
    args = types.SimpleNamespace(input=str(pci_ids_text), output=str(out), no_compress=False)
    conv.build(args)
    return out

@pytest.fixture
def pci_ids_bin_uncompressed(tmp_path: Path, pci_ids_text: Path) -> Path:
    # Use in-repo converter to build a bin file
    root = Path(__file__).resolve().parents[1]
    conv = _import_converter(root)
    out = tmp_path / "pci.ids.bin"
    args = types.SimpleNamespace(input=str(pci_ids_text), output=str(out), no_compress=True)
    conv.build(args)
    return out

def write_hex_file(p: Path, value: int) -> None:
    p.write_text(f"0x{value:04x}\n", encoding="ascii")

def make_device_dir(real_root: Path, bdf: str, *,
                    vendor: int, device: int, klass24: int,
                    revision: int = 0x00,
                    subvendor: int = 0x0000, subdevice: int = 0x0000,
                    include_link_speed: bool = True) -> Path:
    d = real_root
    # create nested path fragments so resolved() contains a parent BDF if we choose to nest
    for frag in bdf.split("/"):
        d = d / frag
    d.mkdir(parents=True, exist_ok=True)
    write_hex_file(d / "vendor", vendor)
    write_hex_file(d / "device", device)
    # class file in sysfs is 24-bit hex; write as 0xHHHHHH
    (d / "class").write_text(f"0x{klass24:06x}\n", encoding="ascii")
    (d / "revision").write_text(f"0x{revision:02x}\n", encoding="ascii")
    if include_link_speed:
        (d / "current_link_speed").write_text(f"8.0 GT/s PCIe")
        (d / "current_link_width").write_text(f"4")
        (d / "max_link_speed").write_text(f"8.0 GT/s PCIe")
        (d / "max_link_width").write_text(f"4")
    write_hex_file(d / "subsystem_vendor", subvendor)
    write_hex_file(d / "subsystem_device", subdevice)
    return d

def make_device_dir_badhex(real_root: Path, bdf: str) -> Path:
    d = real_root
    # create nested path fragments so resolved() contains a parent BDF if we choose to nest
    for frag in bdf.split("/"):
        d = d / frag
    d.mkdir(parents=True, exist_ok=True)
    (d / "vendor").write_text("0xbogusvendor")
    (d / "device").write_text("0xbogusdevice")
    return d

@pytest.fixture
def fake_sysfs(tmp_path: Path):
    """
    Build a fake /sys/bus/pci/devices tree using symlinks that resolve to
    nested real paths (imitating Linux' /sys symlink layout).
    """
    root = tmp_path / "devices_linkdir"
    real = tmp_path / "real"
    root.mkdir()
    real.mkdir()

    # Parent bridge 0000:00:01.0
    parent_bdf = "0000:00:01.0"
    parent_real = make_device_dir(real, parent_bdf, vendor=0x8086, device=0x2448, klass24=0x060400, include_link_speed=False)

    # Child function 0000:65:00.0 under the parent path to encode parentage in resolved() path.
    child_bdf = "0000:00:01.0/0000:65:00.0"
    child_real = make_device_dir(real, child_bdf, vendor=0x10de, device=0x1db6, klass24=0x030000)

    # Grandchild 0000:66:00.0 under same parent (sibling of 65:00.0)
    sib_bdf = "0000:00:01.0/0000:66:00.0"
    sib_real = make_device_dir(real, sib_bdf, vendor=0x15b3, device=0x1017, klass24=0x020000)

    # Grandchild with corrupt data
    corrupt_bdf = "0000:00:01.0/0000:67:00.0"
    corrupt_real = make_device_dir_badhex(real, corrupt_bdf)

    # Symlinks in the "devices" directory (what SysfsEnumerator.iterdir() reads)
    (root / "0000:00:01.0").symlink_to(parent_real, target_is_directory=True)
    (root / "0000:65:00.0").symlink_to(child_real, target_is_directory=True)
    (root / "0000:66:00.0").symlink_to(sib_real, target_is_directory=True)
    (root / "0000:67:00.0").symlink_to(corrupt_real, target_is_directory=True)

    return root
