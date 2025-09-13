from __future__ import annotations
import struct
import pytest


def test_corrupt_bindb_bad_magic(tmp_path):
    # Build a header the binary reader can unpack, but with wrong magic.
    # bindb.HEADER_FMT is "<IHH" + "I"*26  -> 4 + 2 + 2 + 26*4 = 112 bytes
    HEADER_FMT = "<IHH" + "I" * 26
    bad_hdr = struct.pack(HEADER_FMT, 0xDEADBEEF, 0, 0, *([0] * 26))
    p = tmp_path / "bad.ids.bin"
    # Add a little padding so mmap isn’t confused by exact size.
    p.write_bytes(bad_hdr + b"\x00" * 16)

    from pciid.api import PciDbBinary

    with pytest.raises(ValueError) as ei:
        PciDbBinary(str(p))
    assert "bad magic" in str(ei.value)


def test_corrupt_bindb_missing_file(tmp_path):
    from pciid.api import PciDbBinary

    with pytest.raises(FileNotFoundError) as ei:
        PciDbBinary(str(tmp_path / "nonexistent"))
