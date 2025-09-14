# pciid/topology.py  (additions)
from __future__ import annotations
import json
from typing import Dict, List, Tuple
from .sysfs import PciDevice, PciAddress, ResourceEntry

# Existing: build_topology(...), to_json(), to_indented() ...


def dumps_devices_and_edges(devs: Dict[str, PciDevice]) -> str:
    """Serialize a device inventory + edges (no names, discovery-only)."""
    nodes = {}
    edges: List[Tuple[str, str]] = []
    has_parent = set()

    for bdf, d in devs.items():
        resources = []
        if d.resource:
            resources = [r.to_dict() for r in d.resource]
        nodes[bdf] = {
            "class_code": f"0x{d.class_code:04x}",
            "vendor_id": f"0x{d.vendor_id:04x}",
            "device_id": f"0x{d.device_id:04x}",
            "subvendor_id": f"0x{d.subvendor_id:04x}",
            "subdevice_id": f"0x{d.subdevice_id:04x}",
            "revision": f"0x{d.revision:02x}",
            "driver": d.driver,
            "resource": resources,
            "iommu_group": d.iommu_group,
            "link": d.link,
            "parent_bdf": d.parent_bdf,
        }
        if d.parent_bdf:
            edges.append((str(d.parent_bdf), str(bdf)))
            has_parent.add(bdf)

    roots = [b for b in nodes.keys() if b not in has_parent]
    payload = {"version": 1, "nodes": nodes, "edges": edges, "roots": roots}
    return json.dumps(payload, separators=(",", ":"), sort_keys=True)


def loads_devices_and_edges(s: str) -> Dict[str, PciDevice]:
    """Deserialize devices+edges JSON back into live PciDevice objects and stitch topology."""
    obj = json.loads(s)
    nodes = obj["nodes"]
    devs: Dict[str, PciDevice] = {}

    # First pass: create devices with parent_bdf recorded (weakrefs stitched after)
    for bdf, n in nodes.items():
        dom, bus, devfunc = bdf.split(":")
        dev, func = devfunc.split(".")
        resources = []
        for res in n.get("resource", []):
            resources.append(ResourceEntry(**res))
        if not resources:
            resources = None
        pd = PciDevice(
            bdf=PciAddress(int(dom, 16), int(bus, 16), int(dev, 16), int(func, 10)),
            vendor_id=int(n["vendor_id"], 16),
            device_id=int(n["device_id"], 16),
            subvendor_id=int(n["subvendor_id"], 16),
            subdevice_id=int(n["subdevice_id"], 16),
            class_code=int(n["class_code"], 16),
            revision=int(n["revision"], 16),
            driver=n.get("driver"),
            resource=resources,
            iommu_group=n.get("iommu_group"),
            link=n.get("link"),
            parent_bdf=n.get("parent_bdf"),
        )
        devs[bdf] = pd

    # Second pass: stitch weak parent/children
    from .sysfs import SysfsEnumerator

    # reuse the same stitching logic SysfsEnumerator.scan() uses
    for bdf, d in devs.items():
        if d.parent_bdf and d.parent_bdf in devs:
            parent = devs[d.parent_bdf]
            # set private weakref + append child weakref
            import weakref

            d._parent = weakref.ref(parent)
            parent.children.append(weakref.ref(d))

    return devs
