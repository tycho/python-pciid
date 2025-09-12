#!/usr/bin/env python3
# scripts/update_pciids.py
from __future__ import annotations
import argparse, hashlib, json, shutil, subprocess, time
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = REPO_ROOT / "pciid" / "data"
TEXT_OUT = DATA_DIR / "pci.ids"
BIN_OUT = DATA_DIR / "pci.ids.bin"
MANIFEST = DATA_DIR / "manifest.json"


def sha256_of(p: Path) -> str:
    h = hashlib.sha256()
    with p.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("source", help="Path to a pci.ids file (from hwdata/pciids)")
    ap.add_argument("--commit", help="Upstream commit/tag for manifest", default="")
    ap.add_argument(
        "--url", help="Upstream URL for manifest", default="https://pci-ids.ucw.cz/"
    )
    args = ap.parse_args()

    src = Path(args.source).resolve()
    if not src.is_file():
        raise SystemExit(f"no such pci.ids: {src}")

    DATA_DIR.mkdir(parents=True, exist_ok=True)

    # 1) copy text
    shutil.copy2(src, TEXT_OUT)

    # 2) build binary using converter
    #    Assumes scripts/pciids_text_to_bin.py exists and is importable/run-able.
    conv = REPO_ROOT / "scripts" / "pciids_text_to_bin.py"
    if not conv.is_file():
        raise SystemExit("converter scripts/pciids_text_to_bin.py not found")
    subprocess.run(
        ["python", str(conv), "-i", str(TEXT_OUT), "-o", str(BIN_OUT)], check=True
    )

    # 3) write manifest
    manifest = {
        "generated_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "source_url": args.url,
        "source_commit": args.commit,
        "text_sha256": sha256_of(TEXT_OUT),
        "bin_sha256": sha256_of(BIN_OUT),
        "text_size": TEXT_OUT.stat().st_size,
        "bin_size": BIN_OUT.stat().st_size,
    }
    MANIFEST.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    print("Updated:", TEXT_OUT, MANIFEST, BIN_OUT, sep="\n  ")


if __name__ == "__main__":
    main()
