# tests/conftest.py
from __future__ import annotations
import os, stat
from pathlib import Path
from typing import Optional
import importlib.util
import types
import pytest

MINIMAL_PCI_IDS = """\
8086  Intel Corporation
\t1237  440FX - 82441FX PMC
beef
\tbabe Device Without Vendor Name
10de  NVIDIA Corporation
\t0020  NV4 [Riva TNT]
\t\t1043 0200  V3400 TNT
\t\t1048 0c18  Erazor II SGRAM
\t\t1048 0c19  Erazor II
\t\t1048 0c1b  Erazor II
\t\t1048 0c1c  Erazor II
\t\t1092 0550  Viper V550
\t\t1092 0552  Viper V550
\t\t1092 4804  Viper V550
\t\t1092 4808  Viper V550
\t\t1092 4810  Viper V550
\t\t1092 4812  Viper V550
\t\t1092 4815  Viper V550
\t\t1092 4820  Viper V550 with TV out
\t\t1092 4822  Viper V550
\t\t1092 4904  Viper V550
\t\t1092 4914  Viper V550
\t\t1092 8225  Viper V550
\t\t10b4 273d  Velocity 4400
\t\t10b4 273e  Velocity 4400
\t\t10b4 2740  Velocity 4400
\t\t10de 0020  Riva TNT
\t\t1102 1015  Graphics Blaster CT6710
\t\t1102 1016  Graphics Blaster RIVA TNT
\t1db6  GV100GL [Tesla V100 PCIe 32GB]
\t1ba1  GP104M [GeForce GTX 1070 Mobile]
\t\t1458 1651  GeForce GTX 1070 Max-Q
\t\tbaad
C 02  Network controller
\t00  Ethernet controller
\t01  Token ring network controller
\t02  FDDI network controller
\t03  ATM network controller
\t04  ISDN controller
\t05  WorldFip controller
\t06  PICMG controller
\t07  Infiniband controller
\t08  Fabric controller
\t80  Network controller
C 03  Display controller
\t00  VGA compatible controller
\t\t00  VGA controller
\t\t01  8514 controller
\t\t02
C 0c  Serial bus controller
\t00  FireWire (IEEE 1394)
\t\t00  Generic
\t\t10  OHCI
\t01  ACCESS Bus
\t02  SSA
\t03  USB controller
\t\t00  UHCI
\t\t10  OHCI
\t\t20  EHCI
\t\t30  XHCI
\t\t40  USB4 Host Interface
\t\t80  Unspecified
\t\tfe  USB Device
\t01  XGA compatible controller
\t02  3D controller
\t80  Display controller
C 04
\t01
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
    args = types.SimpleNamespace(
        input_path=str(pci_ids_text), output_path=str(out), no_compress=False
    )
    conv.build(args)
    return out


@pytest.fixture
def pci_ids_bin_uncompressed(tmp_path: Path, pci_ids_text: Path) -> Path:
    # Use in-repo converter to build a bin file
    root = Path(__file__).resolve().parents[1]
    conv = _import_converter(root)
    out = tmp_path / "pci.ids.bin"
    args = types.SimpleNamespace(
        input_path=str(pci_ids_text), output_path=str(out), no_compress=True
    )
    conv.build(args)
    return out


def write_hex_file(p: Path, value: int) -> None:
    p.write_text(f"0x{value:04x}\n", encoding="ascii")


def make_device_dir(
    real_root: Path,
    bdf: str,
    *,
    vendor: int,
    device: int,
    klass24: int,
    revision: int = 0x00,
    subvendor: int = 0x0000,
    subdevice: int = 0x0000,
    include_link_speed: bool = True,
    driver: Optional[str] = None,
) -> Path:
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
    if driver:
        (d / "driver").write_text(driver)
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
    parent_real = make_device_dir(
        real,
        parent_bdf,
        vendor=0x8086,
        device=0x2448,
        klass24=0x060400,
        include_link_speed=False,
    )
    (parent_real / "resource").write_text(
        """\
0x00000000f9000000 0x00000000f9ffffff 0x0000000000040200
0x00000000fa000000 0x00000000fa01ffff 0x0000000000040200
0x000000000000c000 0x000000000000c07f 0x0000000000040101
0x0000000000000000 0x0000000000000000 0x0000000000000000
0x0000000000000000 0x0000000000000000 0x0000000000000000
0x0000000000000000 0x0000000000000000 0x0000000000000000
0x00000000000c0000 0x00000000000dffff 0x0000000000000212
0x0000000000000000 0x0000000000000000 0x0000000000000000
0x0000000000000000 0x0000000000000000 0x0000000000000000
0x0000000000000000 0x0000000000000000 0x0000000000000000
0x0000000000000000 0x0000000000000000 0x0000000000000000
0x0000000000000000 0x0000000000000000 0x0000000000000000
0x0000000000000000 0x0000000000000000 0x0000000000000000
"""
    )

    # Child function 0000:65:00.0 under the parent path to encode parentage in resolved() path.
    child_bdf = "0000:00:01.0/0000:65:00.0"
    child_real = make_device_dir(
        real,
        child_bdf,
        vendor=0x10DE,
        device=0x1DB6,
        klass24=0x030000,
        revision=0x01,
        driver="nvidia",
    )

    (child_real / "resource").write_text(
        """\
0x00000000fb000000 0x00000000fbffffff 0x0000000000040200
0x0000007000000000 0x00000077ffffffff 0x000000000014220c
0x0000000000000000 0x0000000000000000 0x0000000000000000
0x0000007800000000 0x0000007801ffffff 0x000000000014220c
0x0000000000000000 0x0000000000000000 0x0000000000000000
0x000000000000f000 0x000000000000f07f 0x0000000000040101
0x00000000fc000000 0x00000000fc07ffff 0x0000000000046200
0x0000000000000000 0x0000000000000000 0x0000000000000000
0x0000000000000000 0x0000000000000000 0x0000000000000000
0x0000000000000000 0x0000000000000000 0x0000000000000000
0x0000000000000000 0x0000000000000000 0x0000000000000000
0x0000000000000000 0x0000000000000000 0x0000000000000000
0x0000000000000000 0x0000000000000000 0x0000000000000000
"""
    )

    # Grandchild 0000:66:00.0 under same parent (sibling of 65:00.0)
    sib_bdf = "0000:00:01.0/0000:66:00.0"
    sib_real = make_device_dir(
        real, sib_bdf, vendor=0x15B3, device=0x1017, klass24=0x020000
    )

    # Grandchild with corrupt data
    corrupt_bdf = "0000:00:01.0/0000:67:00.0"
    corrupt_real = make_device_dir_badhex(real, corrupt_bdf)

    weird_vendor_bdf = "0000:00:01.0/0000:68:00.0"
    weird_vendor_real = make_device_dir(
        real, weird_vendor_bdf, vendor=0xBEEF, device=0xBABE, klass24=0x020000
    )

    # Symlinks in the "devices" directory (what SysfsEnumerator.iterdir() reads)
    (root / "0000:00:01.0").symlink_to(parent_real, target_is_directory=True)
    (root / "0000:65:00.0").symlink_to(child_real, target_is_directory=True)
    (root / "0000:66:00.0").symlink_to(sib_real, target_is_directory=True)
    (root / "0000:67:00.0").symlink_to(corrupt_real, target_is_directory=True)
    (root / "0000:68:00.0").symlink_to(weird_vendor_real, target_is_directory=True)

    # Dummy to exercise non-bdf check
    (root / "dummy").mkdir()

    return root
