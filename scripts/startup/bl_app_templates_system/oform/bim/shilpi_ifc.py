# SPDX-FileCopyrightText: 2026 O-Form Authors
#
# SPDX-License-Identifier: GPL-2.0-or-later

"""IFC semantic sidecar on ShilpiDB (kinds 20–21).

Shares ``drawing_id`` / slot with suite take-off (``takeoff.py``, kinds 1+3–8)
so O-Draft / O-CoreOp / O-Form join on one identity. O-CoreOp take-off UI
ignores kinds 20–21; use ``takeoff.push_takeoff`` for BOQ import.
"""

from __future__ import annotations

import json

from mathutils import Vector

from . import classify
from . import guid as guid_mod
from . import props
from . import quantities
from . import spatial
from . import suite_ids
from . import taxonomy
from .shilpi_client import Record, ShilpiHttp, ensure_server

FORMAT = suite_ids.IFC_FORMAT
VERSION = suite_ids.IFC_VERSION
KIND_HEADER = suite_ids.KIND_IFC_HEADER
KIND_ELEMENT = suite_ids.KIND_IFC_ELEMENT

# Re-exports for callers / tests.
SCENE_DRAWING_ID = suite_ids.SCENE_DRAWING_ID
SCENE_PROJECT_OFFICE = suite_ids.SCENE_PROJECT_OFFICE
SCENE_SHILPI_ADDR = suite_ids.SCENE_SHILPI_ADDR
SCENE_SHILPI_GATEWAY = suite_ids.SCENE_SHILPI_GATEWAY
ensure_drawing_id = suite_ids.ensure_drawing_id
project_office_id = suite_ids.project_office_id
set_project_office_id = suite_ids.set_project_office_id
make_id = suite_ids.make_id
unpack_id = suite_ids.unpack_id


def shilpi_addrs(scene) -> tuple[str, str]:
    from .shilpi_client import DEFAULT_GATEWAY, DEFAULT_SHILPID

    addr = (
        str(scene.get(SCENE_SHILPI_ADDR, "") or DEFAULT_SHILPID).strip() or DEFAULT_SHILPID
    )
    gateway = (
        str(scene.get(SCENE_SHILPI_GATEWAY, "") or DEFAULT_GATEWAY).strip()
        or DEFAULT_GATEWAY
    )
    return addr, gateway


def _world_bbox_xy(obj) -> tuple[float, float, float, float]:
    corners = [obj.matrix_world @ Vector(c) for c in obj.bound_box]
    xs = [c.x for c in corners]
    ys = [c.y for c in corners]
    return min(xs), min(ys), max(xs), max(ys)


def _products(scene):
    out = []
    for obj in scene.objects:
        if obj.type != "MESH":
            continue
        if obj.name == "Model" and len(obj.data.polygons) == 0:
            continue
        if len(obj.data.polygons) == 0:
            continue
        out.append(obj)
    return out


def _header_doc(scene, state: str, counts: dict) -> dict:
    tree = spatial.ensure_project(scene)
    drawing_id = ensure_drawing_id(scene)
    office = project_office_id(scene)
    source = {
        "app": "O-Form",
        "drawing_id": drawing_id,
        "building": tree["building"],
        "site": tree["site"],
        "project": tree["project"],
    }
    if office:
        source["project_office_id"] = office
    return {
        "format": FORMAT,
        "version": VERSION,
        "kind": "header",
        "state": state,
        "units": "m",
        "source": source,
        "storeys": tree["storeys"],
        "active_storey": tree["active_storey"],
        "counts": counts,
    }


def _element_doc(scene, obj) -> dict:
    ifc_class = props.ifc_class_of(obj) or classify.suggest_class(obj)
    if not props.ifc_class_of(obj):
        props.set_ifc_class(obj, ifc_class)
    g = guid_mod.ensure_guid(props.guid_of(obj))
    props.set_guid(obj, g)
    storey = props.storey_of(obj) or spatial.active_storey(scene)
    props.set_storey(obj, storey)
    stats = quantities.mesh_stats(obj)
    size = stats["size"]
    return {
        "format": FORMAT,
        "version": VERSION,
        "kind": "element",
        "global_id": g,
        "ifc_class": ifc_class,
        "ifc_label": taxonomy.label_of(ifc_class),
        "name": props.element_name(obj),
        "storey": storey,
        "object_name": obj.name,
        "bbox_m": {
            "size": [size[0], size[1], size[2]],
            "volume": stats["volume"],
            "area": stats["area"],
            "solid": stats["solid"],
        },
        "source": {
            "app": "O-Form",
            "drawing_id": ensure_drawing_id(scene),
            "project_office_id": project_office_id(scene) or None,
        },
    }


def connect(scene) -> tuple[bool, str]:
    from . import project_folder

    addr, gateway = shilpi_addrs(scene)
    data_path = None
    root = project_folder.project_root_of(scene)
    if root:
        try:
            data_path = project_folder.shilpi_data_path(root)
        except (OSError, ValueError):
            data_path = None
    kwargs = {"data_path": data_path} if data_path else {}
    ok, message = ensure_server(addr, gateway, **kwargs)
    if ok:
        scene[SCENE_SHILPI_ADDR] = addr
        scene[SCENE_SHILPI_GATEWAY] = gateway
    return ok, message


def status(scene) -> dict:
    addr, gateway = shilpi_addrs(scene)
    client = ShilpiHttp(gateway)
    healthy = client.health()
    info = {
        "addr": addr,
        "gateway": gateway,
        "connected": healthy,
        "drawing_id": str(scene.get(SCENE_DRAWING_ID, "") or ""),
        "project_office_id": project_office_id(scene),
        "slot": None,
    }
    cached = suite_ids.persisted_slot(scene)
    if cached:
        info["slot"] = cached[1]
    if healthy:
        try:
            info["stats"] = client.stats()
        except Exception as exc:
            info["stats_error"] = str(exc)
    return info


def push_ifc(context, *, replace: bool = True) -> tuple[bool, str]:
    """Push BIM/IFC semantics (kinds 20–21) using the suite take-off slot."""
    scene = context.scene
    ok, message = connect(scene)
    if not ok:
        return False, message

    products = _products(scene)
    for obj in products:
        if not props.ifc_class_of(obj):
            props.set_ifc_class(obj, classify.suggest_class(obj))
        if not props.guid_of(obj):
            props.set_guid(obj, guid_mod.new_guid())
        if not props.storey_of(obj):
            props.set_storey(obj, spatial.active_storey(scene))

    _, gateway = shilpi_addrs(scene)
    client = ShilpiHttp(gateway)
    # Same slot as hcw-takeoff-shilpi so O-Draft / O-CoreOp join on drawing_id.
    _drawing_id, slot = suite_ids.resolve_slot(
        scene, client, header_kind=suite_ids.KIND_TO_HEADER
    )
    header_rid = make_id(KIND_HEADER, slot, 0)

    counts = {"elements": len(products)}
    client.put_record(
        Record(
            header_rid,
            -1e6,
            -1e6,
            1e6,
            1e6,
            json.dumps(_header_doc(scene, "recording", counts), separators=(",", ":")).encode(
                "utf-8"
            ),
        )
    )

    written_ids = set()
    for obj in products:
        doc = _element_doc(scene, obj)
        n = suite_ids.fnv1a_32(doc["global_id"])
        rid = make_id(KIND_ELEMENT, slot, n)
        written_ids.add(rid)
        min_x, min_y, max_x, max_y = _world_bbox_xy(obj)
        if abs(max_x - min_x) < 1e-6:
            min_x -= 0.05
            max_x += 0.05
        if abs(max_y - min_y) < 1e-6:
            min_y -= 0.05
            max_y += 0.05
        client.put_record(
            Record(
                rid,
                min_x,
                min_y,
                max_x,
                max_y,
                json.dumps(doc, separators=(",", ":")).encode("utf-8"),
            )
        )

    deleted = 0
    if replace:
        for item in client.list_boxes():
            rid = int(item["id"])
            kind, item_slot, _n = unpack_id(rid)
            if kind != KIND_ELEMENT or item_slot != slot:
                continue
            if rid in written_ids:
                continue
            if client.delete_record(rid):
                deleted += 1

    client.put_record(
        Record(
            header_rid,
            -1e6,
            -1e6,
            1e6,
            1e6,
            json.dumps(_header_doc(scene, "complete", counts), separators=(",", ":")).encode(
                "utf-8"
            ),
        )
    )
    client.save()
    return True, "IFC sidecar: {} elements (slot {}, deleted {})".format(
        len(products), slot, deleted
    )


def pull_ifc(context) -> tuple[bool, str]:
    """Pull IFC element rows for this drawing_id into the scene (props + stubs)."""
    import bpy

    scene = context.scene
    ok, message = connect(scene)
    if not ok:
        return False, message

    _, gateway = shilpi_addrs(scene)
    client = ShilpiHttp(gateway)
    drawing_id, slot = suite_ids.resolve_slot(
        scene, client, header_kind=suite_ids.KIND_TO_HEADER
    )

    header = client.get_record(make_id(KIND_HEADER, slot, 0))
    if header is None:
        return False, "No IFC sidecar header for drawing_id " + drawing_id[:8]
    try:
        header_doc = json.loads(header.payload.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError):
        return False, "Corrupt IFC header payload"
    if header_doc.get("format") != FORMAT:
        return False, "Unexpected header format"
    if header_doc.get("state") == "recording":
        return False, "IFC push still recording — try again"

    source = header_doc.get("source") or {}
    if source.get("project"):
        scene[props.SCENE_PROJECT] = source["project"]
    if source.get("site"):
        scene[props.SCENE_SITE] = source["site"]
    if source.get("building"):
        scene[props.SCENE_BUILDING] = source["building"]
    if source.get("project_office_id"):
        set_project_office_id(scene, source["project_office_id"])
    storeys = header_doc.get("storeys") or []
    if storeys:
        scene[props.SCENE_STOREYS] = json.dumps(storeys)
    if header_doc.get("active_storey"):
        scene[props.SCENE_ACTIVE_STOREY] = header_doc["active_storey"]

    by_guid = {}
    for obj in scene.objects:
        g = props.guid_of(obj)
        if g:
            by_guid[g] = obj

    updated = 0
    created = 0
    for item in client.list_boxes():
        rid = int(item["id"])
        kind, item_slot, _n = unpack_id(rid)
        if kind != KIND_ELEMENT or item_slot != slot:
            continue
        rec = client.get_record(rid)
        if rec is None:
            continue
        try:
            doc = json.loads(rec.payload.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError):
            continue
        if doc.get("format") != FORMAT or doc.get("kind") != "element":
            continue
        g = doc.get("global_id") or ""
        ifc_class = doc.get("ifc_class") or taxonomy.DEFAULT_ELEMENT
        name = doc.get("name") or doc.get("object_name") or "Element"
        storey = doc.get("storey") or spatial.active_storey(scene)
        obj = by_guid.get(g)
        if obj is None:
            mesh = bpy.data.meshes.new(name)
            obj = bpy.data.objects.new(name, mesh)
            scene.collection.objects.link(obj)
            bb = item.get("bbox") or {}
            try:
                cx = 0.5 * (float(bb.get("minX", 0)) + float(bb.get("maxX", 0)))
                cy = 0.5 * (float(bb.get("minY", 0)) + float(bb.get("maxY", 0)))
                obj.location = (cx, cy, 0.0)
            except (TypeError, ValueError):
                pass
            created += 1
            by_guid[g] = obj
        else:
            updated += 1
        props.set_guid(obj, g)
        props.set_ifc_class(obj, ifc_class)
        props.set_storey(obj, storey)
        props.set_str(obj, props.PROP_IFC_NAME, name)

    return True, "IFC pull: {} updated, {} created".format(updated, created)
