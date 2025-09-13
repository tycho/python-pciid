# tests/test_bindb.py
from __future__ import annotations
from pciid.cli_lspci import ProgramArgs, run

expected_stdout = """\
0000:00:01.0 PCI bridge [0604]: Intel Corporation Device 2448 [8086:2448]
0000:65:00.0 VGA compatible controller [0300]: NVIDIA Corporation GV100GL [Tesla V100 PCIe 32GB] [10de:1db6] (rev 01)
0000:66:00.0 Ethernet controller [0200]: Device [15b3:1017] [15b3:1017]
0000:68:00.0 Ethernet controller [0200]: Vendor beef Device Without Vendor Name [beef:babe]
"""


def test_pciid_cli(capfd, fake_sysfs, pci_ids_bin):
    # TODO: More testing to validate output, right now we're just doing this
    # for coverage.
    args = ProgramArgs(db_path=pci_ids_bin, sysfs_path=fake_sysfs)
    run(args)
    out, err = capfd.readouterr()
    assert out == expected_stdout
