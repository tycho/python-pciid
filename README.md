[![tests workflow](https://github.com/tycho/python-pciid/actions/workflows/tests.yml/badge.svg)](https://github.com/tycho/python-pciid/actions/workflows/tests.yml)
[![codecov](https://codecov.io/github/tycho/python-pciid/branch/master/graph/badge.svg?token=P8FBPQMY3O)](https://codecov.io/github/tycho/python-pciid)

# pciid

Fast, boring PCI ID lookups for Python.  
Reads `pci.ids` (text **or** binary), enumerates PCI devices via Linux sysfs, and offers a tiny `lspci -D -nn`-style CLI.

## Features
- **Two backends:** text (`pci.ids`) and mmap’d binary (`pci.ids.bin`) with identical API.
- **Autodiscovery:** prefers binary for speed; falls back to system/bundled text.
- **Sysfs enumeration (Linux):** discover devices and basic topology (parent/children).
- **No runtime deps.** Pure stdlib.

## Install
_PyPI soon; for now from source:_
```bash
uv pip install -e .
````

## Quick start

```python
from pciid import open_db, SysfsEnumerator

# 1) Load a DB (binary/text autodetected; env/system/bundled discovery)
db = open_db()  # or open_db(path="/path/to/pci.ids[.bin]")

# 2) Enumerate devices from sysfs (no names needed for discovery)
enum = SysfsEnumerator()
devices = enum.scan()

# 3) Print discovered devices
for bdf, d in sorted(devices.items()):
    vend = db.get_vendor_name(d.vendor_id) or f"0x{d.vendor_id:04x}"
    name = db.get_device_name(d.vendor_id, d.device_id) or f"0x{d.device_id:04x}"
    print(f"{bdf} [{d.vendor_id:04x}:{d.device_id:04x}] {vend} {name}")
```

## CLI

After install, you get an `lspci`-like tool:

```bash
$ pciid-lspci
```

The output should be equivalent to pciutils `lspci -nnD`.

## Data discovery

At runtime, `open_db()` tries (highest → lowest):

1. `PCIID_BIN` (binary)
2. `PCIID_TEXT` (text)
3. System: `/usr/share/hwdata/pci.ids.bin` → `/usr/share/hwdata/pci.ids`
4. Bundled: package `pci.ids.bin` → `pci.ids`

Env knobs:

* `PCIID_BIN`, `PCIID_TEXT` – explicit paths
* `PCIID_NO_BUNDLED=1` – disable bundled `pci.ids` and `pci.ids.bin` files
* `PCIID_NO_SYSTEM=1` – disable `hwdata` system file fallback

*Build-time (wheel creation)*: the project prebakes `pci.ids` and `pci.ids.bin` into `pciid/data/`. If a system file isn’t available, it downloads from the official PCI IDs snapshot and converts it. Set `PCIID_FORCE_DOWNLOAD=1` or `PCIID_NO_NETWORK=1` for CI policy.

## API (tiny)

```python
from pciid import PciDb, PciDbText, PciDbBinary, open_db, SysfsEnumerator, PciDevice

# Lookups
db.get_vendor_name(0x8086)
db.get_device_name(0x8086, 0x1237)
db.get_subsystem_name(vid, did, subvid, subdid)
db.get_class_name(base=0x06, subclass=0x04)        # PCI bridge
db.get_class_name_from_code(0x020000)              # Network/Ethernet

# Sysfs & topology helpers
devs = SysfsEnumerator().scan()                    # { "0000:65:00.0": PciDevice, ... }
parent = devs["0000:65:00.0"].parent               # -> PciDevice | None
children = [c() for c in devs["0000:00:01.0"].children if c()]
affected = SysfsEnumerator.sbr_affected(devs, devs["0000:65:00.0"])
```
