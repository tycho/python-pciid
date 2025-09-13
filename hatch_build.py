# hatch_build.py
from __future__ import annotations

import gzip
import hashlib
import json
import os
import sys
import types
import urllib.request
from datetime import datetime, timezone
from importlib import util as importlib_util
from pathlib import Path

from hatchling.builders.hooks.plugin.interface import BuildHookInterface

PCI_IDS_URL_GZ = "https://pci-ids.ucw.cz/v2.2/pci.ids.gz"
SYSTEM_PCI_IDS = "/usr/share/hwdata/pci.ids"


def _sha256(p: Path) -> str:
    h = hashlib.sha256()
    with p.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def _load_converter(repo_root: Path):
    mod_path = repo_root / "scripts" / "pciids_text_to_bin.py"
    spec = importlib_util.spec_from_file_location("pciids_text_to_bin", str(mod_path))
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Cannot import converter at {mod_path}")
    mod = importlib_util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    if not hasattr(mod, "build"):
        raise RuntimeError("Converter must expose a `build(args)` function")
    return mod


class CustomBuildHook(BuildHookInterface):
    """
    During *build* (wheel/sdist):
      - write pciid/data/pci.ids from:
          1) /usr/share/hwdata/pci.ids, or
          2) download pci.ids.gz and decompress
      - run scripts/pciids_text_to_bin.py -> pciid/data/pci.ids.bin
      - write pciid/data/manifest.json
    Never runs at user install time; only while building artifacts.
    """

    def _ensure_generated(self) -> tuple[Path, Path, Path]:
        root = Path(self.root).resolve()
        data_dir = root / "pciid" / "data"
        data_dir.mkdir(parents=True, exist_ok=True)

        text_out = data_dir / "pci.ids"
        bin_out = data_dir / "pci.ids.bin"
        manifest_out = data_dir / "manifest.json"

        prefer_dl = os.getenv("PCIID_FORCE_DOWNLOAD") == "1"
        no_net = os.getenv("PCIID_NO_NETWORK") == "1"

        # 1) get pci.ids into the *source tree*
        source = {}
        if not prefer_dl and Path(SYSTEM_PCI_IDS).is_file():
            text_out.write_bytes(Path(SYSTEM_PCI_IDS).read_bytes())
            source = {"method": "system", "path": SYSTEM_PCI_IDS}
        else:
            if no_net:
                raise RuntimeError("No system pci.ids and PCIID_NO_NETWORK=1 set")
            with urllib.request.urlopen(PCI_IDS_URL_GZ) as r:
                raw = gzip.decompress(r.read())
            text_out.write_bytes(raw)
            source = {"method": "download", "url": PCI_IDS_URL_GZ}

        # 2) convert text -> bin in the *source tree*
        converter = _load_converter(root)
        args = types.SimpleNamespace(
            input_path=str(text_out), output_path=str(bin_out), no_compress=False
        )
        converter.build(args)

        # 3) manifest
        manifest = {
            "generated_at_utc": datetime.now(timezone.utc).strftime(
                "%Y-%m-%dT%H:%M:%SZ"
            ),
            "source": source,
            "text": {"sha256": _sha256(text_out), "size": text_out.stat().st_size},
            "bin": {"sha256": _sha256(bin_out), "size": bin_out.stat().st_size},
            "python": sys.version.split()[0],
            "tool": "hatch_build.py",
        }
        manifest_out.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
        return text_out, bin_out, manifest_out

    # Run early so the files exist before file selection
    def initialize(self, version: str, build_data: dict) -> None:
        # Run for both wheel and sdist so both carry the prebaked data
        text_out, bin_out, manifest_out = self._ensure_generated()
        # force-include is belt-and-suspenders: ensure the files land in the wheel
        build_data.setdefault("force_include", {})
        for p in (text_out, bin_out, manifest_out):
            rel = str(p.relative_to(self.root))
            build_data["force_include"][str(p)] = rel

    # And for sdists, append to the file list too (Hatch calls this with candidate files)
    def update_files(self, files: list[dict]) -> None:
        root = Path(self.root)
        for rel in (
            "pciid/data/pci.ids",
            "pciid/data/pci.ids.bin",
            "pciid/data/manifest.json",
        ):
            p = root / rel
            if p.exists():
                files.append({"path": rel})
