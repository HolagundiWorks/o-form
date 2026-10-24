# SPDX-FileCopyrightText: 2026 O-Form Authors
#
# SPDX-License-Identifier: GPL-2.0-or-later

"""Suite take-off producer/consumer — ``hcw-takeoff-shilpi`` on shared ShilpiDB.

Compatible with O-Draft ``takeoff.record`` and O-CoreOp ``ShilpiTakeoff.Read``.
IFC file I/O stays in ``ifc4.py``; IFC semantic sidecar (kinds 20–21) in
``shilpi_ifc.py``. This module owns kinds 1 and 3–8 only.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone

from . import bridge_rows
from . import spatial
from . import suite_ids
from .shilpi_client import (
    DEFAULT_GATEWAY,
    DEFAULT_SHILPID,
    Record,
    ShilpiHttp,
    ensure_server,
)

ROW_KINDS = (
    suite_ids.KIND_WALL,
    suite_ids.KIND_OPENING,
    suite_ids.KIND_COLUMN,
    suite_ids.KIND_LINTEL,
    suite_ids.KIND_ROOM,
    suite_ids.KIND_SLAB,
)


def _addrs(scene) -> tuple[str, str]:
    addr = (
        str(scene.get(suite_ids.SCENE_SHILPI_ADDR, "") or DEFAULT_SHILPID).strip()
        or DEFAULT_SHILPID
    )
    gateway = (
        str(scene.get(suite_ids.SCENE_SHILPI_GATEWAY, "") or DEFAULT_GATEWAY).strip()
        or DEFAULT_GATEWAY
    )
    return addr, gateway


def connect(scene) -> tuple[bool, str]:
    from . import project_folder

    addr, gateway = _addrs(scene)
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
        scene[suite_ids.SCENE_SHILPI_ADDR] = addr
        scene[suite_ids.SCENE_SHILPI_GATEWAY] = gateway
    return ok, message


def _build_header(scene, state: str, levels: list, schedule: list) -> dict:
    tree = spatial.ensure_project(scene)
    drawing_id = suite_ids.ensure_drawing_id(scene)
    source = {
        "app": "O-Form",
        "drawing": "(oform-model)",
        "drawing_id": drawing_id,
        "exported": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
    }
    office = suite_ids.project_office_id(scene)
    if office:
        source["project_office_id"] = office
    pref = suite_ids.project_ref(scene)
    if pref:
        source["project_ref"] = pref
    return {
        "format": suite_ids.TAKEOFF_FORMAT,
        "version": suite_ids.TAKEOFF_VERSION,
        "units": "mm",
        "state": state,
        "source": source,
        "project": {
            "name": tree["project"],
            "client_name": "",
            "company_name": "",
            "location": "",
            "address": "",
        },
        "levels": levels,
        "beam_depths_mm": [450.0],
        "opening_schedule": schedule,
    }


def push_takeoff(context, *, replace: bool = True) -> tuple[bool, str]:
    """Write O-CoreOp-compatible take-off records to the shared ShilpiDB."""
    scene = context.scene
    ok, message = connect(scene)
    if not ok:
        return False, message

    spatial.ensure_project(scene)
    _, gateway = _addrs(scene)
    client = ShilpiHttp(gateway)
    drawing_id, slot = suite_ids.resolve_slot(scene, client, header_kind=suite_ids.KIND_TO_HEADER)

    products = bridge_rows.collect_products(scene)
    storeys = spatial.list_storeys(scene)
    levels = bridge_rows.levels_from_storeys(storeys)
    # Ensure every row level exists in header levels.
    level_names = {lv["name"] for lv in levels}
    for _obj, _kind, row, _bbox, _n in products:
        name = str(row.get("level") or "")
        if name and name not in level_names:
            levels.append(
                {
                    "name": name,
                    "height_mm": 3000.0,
                    "slab_thickness_mm": 150.0,
                    "beam_depth_mm": 450.0,
                    "ceiling_mm": 2850.0,
                    "lintel_bottom_mm": 2100.0,
                }
            )
            level_names.add(name)

    schedule = bridge_rows.opening_schedule(products)
    header_rid = suite_ids.header_id(slot)

    # 1) recording
    recording = json.dumps(
        _build_header(scene, "recording", levels, schedule),
        separators=(",", ":"),
    ).encode("utf-8")
    client.put_record(Record(header_rid, 0, 0, 0, 0, recording))

    # 2) rows
    written = set()
    counts = {k: 0 for k in ROW_KINDS}
    for _obj, kind, row, bbox, n in products:
        rid = suite_ids.make_id(kind, slot, n)
        written.add(rid)
        counts[kind] = counts.get(kind, 0) + 1
        min_x, min_y, max_x, max_y = bbox
        if abs(max_x - min_x) < 1e-3:
            min_x -= 50.0
            max_x += 50.0
        if abs(max_y - min_y) < 1e-3:
            min_y -= 50.0
            max_y += 50.0
        payload = json.dumps(row, separators=(",", ":")).encode("utf-8")
        client.put_record(Record(rid, min_x, min_y, max_x, max_y, payload))

    # 3) delete stale row kinds in this slot
    deleted = 0
    if replace:
        for item in client.list_boxes():
            rid = int(item["id"])
            kind, item_slot, _n = suite_ids.unpack_id(rid)
            if item_slot != slot or kind not in ROW_KINDS:
                continue
            if rid in written:
                continue
            if client.delete_record(rid):
                deleted += 1

    # 4) complete + save
    complete = json.dumps(
        _build_header(scene, "complete", levels, schedule),
        separators=(",", ":"),
    ).encode("utf-8")
    client.put_record(Record(header_rid, 0, 0, 0, 0, complete))
    client.save()

    total = sum(counts.values())
    return True, (
        "Take-off push: {} rows (slot {}, walls {}, slabs {}, deleted {}) · {}".format(
            total,
            slot,
            counts.get(suite_ids.KIND_WALL, 0),
            counts.get(suite_ids.KIND_SLAB, 0),
            deleted,
            drawing_id[:8],
        )
    )


def pull_takeoff_summary(context) -> tuple[bool, str, dict | None]:
    """Read this drawing's take-off header + row counts from ShilpiDB."""
    scene = context.scene
    ok, message = connect(scene)
    if not ok:
        return False, message, None

    _, gateway = _addrs(scene)
    client = ShilpiHttp(gateway)
    drawing_id, slot = suite_ids.resolve_slot(scene, client, header_kind=suite_ids.KIND_TO_HEADER)
    header = client.get_record(suite_ids.header_id(slot))
    if header is None:
        return False, "No take-off header for drawing_id " + drawing_id[:8], None
    try:
        doc = json.loads(header.payload.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError):
        return False, "Corrupt take-off header", None
    if doc.get("format") != suite_ids.TAKEOFF_FORMAT:
        return False, "Header is not hcw-takeoff-shilpi (got {})".format(doc.get("format")), None
    if doc.get("state") == "recording":
        return False, "Take-off still recording — wait for complete", None

    counts = {k: 0 for k in ROW_KINDS}
    for item in client.list_boxes():
        rid = int(item["id"])
        kind, item_slot, _n = suite_ids.unpack_id(rid)
        if item_slot == slot and kind in ROW_KINDS:
            counts[kind] += 1

    summary = {
        "drawing_id": drawing_id,
        "slot": slot,
        "header": doc,
        "counts": {
            "walls": counts[suite_ids.KIND_WALL],
            "openings": counts[suite_ids.KIND_OPENING],
            "columns": counts[suite_ids.KIND_COLUMN],
            "lintels": counts[suite_ids.KIND_LINTEL],
            "rooms": counts[suite_ids.KIND_ROOM],
            "slabs": counts[suite_ids.KIND_SLAB],
        },
    }
    msg = "Take-off: {} walls · {} openings · {} slabs · state {}".format(
        summary["counts"]["walls"],
        summary["counts"]["openings"],
        summary["counts"]["slabs"],
        doc.get("state"),
    )
    return True, msg, summary


def list_suite_drawings(context) -> tuple[bool, str, list]:
    """List all ``hcw-takeoff-shilpi`` headers on the shared server (O-CoreOp view)."""
    scene = context.scene
    ok, message = connect(scene)
    if not ok:
        return False, message, []

    _, gateway = _addrs(scene)
    client = ShilpiHttp(gateway)
    drawings = []
    for item in client.list_boxes():
        rid = int(item["id"])
        kind, slot, n = suite_ids.unpack_id(rid)
        if kind != suite_ids.KIND_TO_HEADER or n != 0:
            continue
        rec = client.get_record(rid)
        if rec is None:
            continue
        try:
            doc = json.loads(rec.payload.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError):
            continue
        if doc.get("format") != suite_ids.TAKEOFF_FORMAT:
            continue
        source = doc.get("source") or {}
        drawings.append(
            {
                "id": rid,
                "slot": slot,
                "drawing_id": source.get("drawing_id"),
                "app": source.get("app"),
                "project_office_id": source.get("project_office_id"),
                "state": doc.get("state"),
                "levels": [lv.get("name") for lv in (doc.get("levels") or [])],
            }
        )
    return True, "{} take-off drawing(s) on ShilpiDB".format(len(drawings)), drawings


def push_coherent(context) -> tuple[bool, str]:
    """Push IFC sidecar + suite take-off with the same drawing_id / slot."""
    from . import shilpi_ifc

    ok1, msg1 = shilpi_ifc.push_ifc(context, replace=True)
    if not ok1:
        return False, "IFC sidecar: " + msg1
    ok2, msg2 = push_takeoff(context, replace=True)
    if not ok2:
        return False, "Take-off: " + msg2
    return True, msg1 + " · " + msg2
