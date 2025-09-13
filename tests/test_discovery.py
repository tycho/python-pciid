# tests/test_discovery.py
from __future__ import annotations
import os
import pytest
import struct
from pciid.api import open_db, PciDbText, PciDbBinary


def test_open_db_env_text(monkeypatch, pci_ids_text, tmp_path):
    monkeypatch.setenv("PCIID_TEXT", str(pci_ids_text))
    monkeypatch.delenv("PCIID_BIN", raising=False)
    db = open_db()
    assert isinstance(db, PciDbText)
    assert db.get_vendor_name(0x8086) == "Intel Corporation"


def test_open_db_env_bin(monkeypatch, pci_ids_bin):
    monkeypatch.setenv("PCIID_BIN", str(pci_ids_bin))
    monkeypatch.delenv("PCIID_TEXT", raising=False)
    db = open_db()
    assert isinstance(db, PciDbBinary)
    assert db.get_device_name(0x10DE, 0x1DB6)
    db.close()


def test_open_db_env_text_missing(monkeypatch, tmp_path):
    monkeypatch.setenv("PCIID_NO_BUNDLED", "1")
    monkeypatch.setenv("PCIID_NO_SYSTEM", "1")
    monkeypatch.delenv("PCIID_BIN", raising=False)
    monkeypatch.setenv("PCIID_TEXT", str(tmp_path / "nonexistent"))
    with pytest.raises(FileNotFoundError) as ei:
        open_db()


def test_open_db_env_bin_missing(monkeypatch, tmp_path):
    monkeypatch.setenv("PCIID_NO_BUNDLED", "1")
    monkeypatch.setenv("PCIID_NO_SYSTEM", "1")
    monkeypatch.setenv("PCIID_BIN", str(tmp_path / "nonexistent"))
    monkeypatch.delenv("PCIID_TEXT", raising=False)
    with pytest.raises(FileNotFoundError) as ei:
        open_db()


def test_open_db_env_text_as_bin(monkeypatch, pci_ids_text):
    monkeypatch.setenv("PCIID_NO_BUNDLED", "1")
    monkeypatch.setenv("PCIID_NO_SYSTEM", "1")
    monkeypatch.setenv("PCIID_BIN", str(pci_ids_text))
    monkeypatch.delenv("PCIID_TEXT", raising=False)
    with pytest.raises(FileNotFoundError) as ei:
        open_db()


def test_open_db_env_bin_as_text(monkeypatch, pci_ids_bin):
    monkeypatch.setenv("PCIID_NO_BUNDLED", "1")
    monkeypatch.setenv("PCIID_NO_SYSTEM", "1")
    monkeypatch.delenv("PCIID_BIN", raising=False)
    monkeypatch.setenv("PCIID_TEXT", str(pci_ids_bin))
    with pytest.raises(FileNotFoundError) as ei:
        open_db()


def test_open_db_explicit_text(monkeypatch, pci_ids_text):
    monkeypatch.delenv("PCIID_BIN", raising=False)
    monkeypatch.delenv("PCIID_TEXT", raising=False)
    db = open_db(path=pci_ids_text)
    assert isinstance(db, PciDbText)
    assert db.get_device_name(0x10DE, 0x1DB6)
    db.close()


def test_open_db_explicit_bin(monkeypatch, pci_ids_bin):
    monkeypatch.delenv("PCIID_BIN", raising=False)
    monkeypatch.delenv("PCIID_TEXT", raising=False)
    db = open_db(path=pci_ids_bin)
    assert isinstance(db, PciDbBinary)
    assert db.get_device_name(0x10DE, 0x1DB6)
    db.close()


def test_open_db_default(monkeypatch):
    monkeypatch.delenv("PCIID_NO_SYSTEM", raising=False)
    monkeypatch.delenv("PCIID_NO_BUNDLED", raising=False)
    monkeypatch.delenv("PCIID_BIN", raising=False)
    monkeypatch.delenv("PCIID_TEXT", raising=False)
    db = open_db()
    assert db is not None
    assert db.get_device_name(0x10DE, 0x1DB6)
    db.close()


def test_open_db_bundled_bin(monkeypatch):
    monkeypatch.setenv("PCIID_NO_SYSTEM", "1")
    monkeypatch.delenv("PCIID_NO_BUNDLED", raising=False)
    monkeypatch.delenv("PCIID_BIN", raising=False)
    monkeypatch.delenv("PCIID_TEXT", raising=False)
    db = open_db()
    assert isinstance(db, PciDbBinary)
    assert db.get_device_name(0x10DE, 0x1DB6)
    db.close()


def test_open_db_no_bundled(monkeypatch):
    monkeypatch.delenv("PCIID_BIN", raising=False)
    monkeypatch.delenv("PCIID_TEXT", raising=False)
    monkeypatch.setenv("PCIID_NO_BUNDLED", "1")
    db = open_db()
    assert isinstance(db, PciDbText)
    assert db.get_device_name(0x10DE, 0x1DB6)
    db.close()


def test_open_db_missing_file(monkeypatch, tmp_path):
    with pytest.raises(FileNotFoundError) as ei:
        open_db(str(tmp_path / "nonexistent"))


MINIMAL_PCI_IDS = """\
8086  Intel Corporation
\t1237  440FX - 82441FX PMC
C 06  Bridge
\t04  PCI bridge
"""


def test_open_db_bundled_text(monkeypatch, tmp_path: Path):
    # Arrange temp files: bad bin (wrong magic) + good text
    bad_bin = tmp_path / "pci.ids.bin"
    # match header size bindb expects but with wrong magic
    HEADER_FMT = "<IHH" + "I" * 26
    bad_bin.write_bytes(struct.pack(HEADER_FMT, 0xDEADBEEF, 0, 0, *([0] * 26)))
    good_text = tmp_path / "pci.ids"
    good_text.write_text(MINIMAL_PCI_IDS, encoding="utf-8")

    # Patch discovery so system paths don't exist and bundled resources are used.
    from pciid.backends import discovery

    # 1) Force candidate construction to skip system paths and allow bundled
    orig_resolve = discovery._resolve_candidates

    def fake_resolve(**_kw):
        # env_bin/env_text None; system paths point to nowhere; allow_bundled True
        return orig_resolve(
            explicit_path=None,
            env_bin=None,
            env_text=None,
            system_bin="/no/system/bin",
            system_text="/no/system/text",
            allow_bundled=True,
            allow_system=False,
        )

    monkeypatch.setattr(discovery, "_resolve_candidates", fake_resolve)

    # 2) Say "bundled bin/text are available"
    monkeypatch.setattr(discovery, "bundled_bin_available", lambda: True)
    monkeypatch.setattr(discovery, "bundled_text_available", lambda: True)

    # 3) Make resources.as_file yield our temp paths:
    #    first call -> bad_bin (so bundled-bin opener raises),
    #    second call -> good_text (so bundled-text opener succeeds)
    class _CM:
        def __init__(self, p: Path):
            self.p = p

        def __enter__(self):
            return self.p

        def __exit__(self, *exc):
            return False

    calls = {"n": 0}

    def fake_as_file(_res):
        calls["n"] += 1
        return _CM(bad_bin if calls["n"] == 1 else good_text)

    monkeypatch.setattr(discovery.resources, "as_file", fake_as_file)

    # Act
    db = open_db()

    # Assert we fell through bundled-bin -> bundled-text and returned a text DB
    assert isinstance(db, PciDbText)
    # Sanity: lookups work on the bundled text file
    assert "Intel" in (db.get_vendor_name(0x8086) or "")
    db.close()
