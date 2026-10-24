# SPDX-FileCopyrightText: 2026 O-Form Authors
#
# SPDX-License-Identifier: GPL-2.0-or-later

"""Map O-Form IFC-tagged meshes → hcw-aqc-bridge take-off rows (mm).

Row JSON matches O-Draft ``bridge.export`` / O-CoreOp ``CadImporter`` payloads
(see ``odraft-takeoff-records.json`` fixture). No plaster/paint/cost fields.
"""

from __future__ import annotations

from mathutils import Vector

from . import classify
from . import guid as guid_mod
from . import props
from . import quantities
from . import suite_ids
from . import taxonomy


def _m_to_mm(value: float) -> float:
    return float(value) * 1000.0


def _world_bbox(obj):
    corners = [obj.matrix_world @ Vector(c) for c in obj.bound_box]
    xs = [c.x for c in corners]
    ys = [c.y for c in corners]
    zs = [c.z for c in corners]
    return min(xs), min(ys), min(zs), max(xs), max(ys), max(zs)


def plan_bbox_mm(obj) -> tuple[float, float, float, float]:
    min_x, min_y, _z0, max_x, max_y, _z1 = _world_bbox(obj)
    return _m_to_mm(min_x), _m_to_mm(min_y), _m_to_mm(max_x), _m_to_mm(max_y)


def compact_ref(prefix: str, global_id: str) -> str:
    """O-Draft-style ref: letter + compact hex from GlobalId FNV."""
    n = suite_ids.fnv1a_32(global_id) & 0xFFFF
    return "{}{:X}".format(prefix, n)


def item_n(global_id: str) -> int:
    return suite_ids.fnv1a_32(global_id)


def levels_from_storeys(storeys: list, *, default_height_m: float = 3.0) -> list:
    """Build bridge ``levels[]`` from O-Form storeys (elevations in metres)."""
    ordered = sorted(storeys or [], key=lambda s: float(s.get("elevation", 0.0)))
    if not ordered:
        return [
            {
                "name": "Level 0",
                "height_mm": _m_to_mm(default_height_m),
                "slab_thickness_mm": 150.0,
                "beam_depth_mm": 450.0,
                "ceiling_mm": _m_to_mm(default_height_m) - 150.0,
                "lintel_bottom_mm": 2100.0,
            }
        ]
    out = []
    for i, storey in enumerate(ordered):
        elev = float(storey.get("elevation", 0.0))
        if i + 1 < len(ordered):
            height_m = float(ordered[i + 1].get("elevation", elev + default_height_m)) - elev
        else:
            height_m = default_height_m
        if height_m <= 0.05:
            height_m = default_height_m
        height_mm = _m_to_mm(height_m)
        out.append(
            {
                "name": str(storey.get("name") or "Level"),
                "height_mm": height_mm,
                "slab_thickness_mm": 150.0,
                "beam_depth_mm": 450.0,
                "ceiling_mm": max(0.0, height_mm - 150.0),
                "lintel_bottom_mm": min(2100.0, height_mm * 0.7),
            }
        )
    return out


def _ensure_tagged(obj, scene):
    ifc_class = props.ifc_class_of(obj) or classify.suggest_class(obj)
    props.set_ifc_class(obj, ifc_class)
    g = guid_mod.ensure_guid(props.guid_of(obj))
    props.set_guid(obj, g)
    storey = props.storey_of(obj) or "Level 0"
    props.set_storey(obj, storey)
    return ifc_class, g, storey


def row_for_object(obj, scene) -> tuple[int, dict, tuple[float, float, float, float]] | None:
    """Return (kind, row_dict, bbox_mm) or None if not a take-off product."""
    if obj is None or obj.type != "MESH" or not obj.data or len(obj.data.polygons) == 0:
        return None
    ifc_class, g, storey = _ensure_tagged(obj, scene)
    min_x, min_y, min_z, max_x, max_y, max_z = _world_bbox(obj)
    dx = abs(max_x - min_x)
    dy = abs(max_y - min_y)
    dz = abs(max_z - min_z)
    bbox = plan_bbox_mm(obj)
    length = max(dx, dy)
    thickness = min(dx, dy)
    stats = quantities.mesh_stats(obj)

    if ifc_class in {"IfcWall", "IfcWallStandardCase"}:
        row = {
            "ref": compact_ref("W", g),
            "level": storey,
            "length_mm": _m_to_mm(length),
            "height_mm": _m_to_mm(dz),
            "thickness_mm": _m_to_mm(thickness),
            "layer": "A-WALL",
        }
        return suite_ids.KIND_WALL, row, bbox

    if ifc_class == "IfcDoor":
        row = {
            "ref": compact_ref("O", g),
            "kind": "Door",
            "mark": props.element_name(obj)[:16] or "D",
            "level": storey,
            "width_mm": _m_to_mm(max(dx, dy)),
            "height_mm": _m_to_mm(dz),
            "sill_mm": 0.0,
        }
        return suite_ids.KIND_OPENING, row, bbox

    if ifc_class == "IfcWindow":
        row = {
            "ref": compact_ref("O", g),
            "kind": "Window",
            "mark": props.element_name(obj)[:16] or "W",
            "level": storey,
            "width_mm": _m_to_mm(max(dx, dy)),
            "height_mm": _m_to_mm(dz),
            "sill_mm": _m_to_mm(max(0.0, min_z)),
        }
        return suite_ids.KIND_OPENING, row, bbox

    if ifc_class == "IfcColumn":
        row = {
            "ref": compact_ref("C", g),
            "mark": props.element_name(obj)[:16] or "C",
            "level": storey,
            "width_mm": _m_to_mm(min(dx, dy)),
            "depth_mm": _m_to_mm(max(dx, dy)),
        }
        return suite_ids.KIND_COLUMN, row, bbox

    if ifc_class == "IfcSpace":
        area = stats["area"] * 0.5 if stats["area"] else (dx * dy)
        # Prefer footprint for room area when solid volume exists.
        if stats["solid"] and dz > 1e-3:
            area = abs(stats["volume"] / dz) if dz else area
        row = {
            "ref": compact_ref("R", g),
            "name": props.element_name(obj),
            "level": storey,
            "area_m2": float(area),
            "length_mm": _m_to_mm(max(dx, dy)),
            "breadth_mm": _m_to_mm(min(dx, dy)),
            "rectangular": True,
        }
        return suite_ids.KIND_ROOM, row, bbox

    if ifc_class in {"IfcSlab", "IfcRoof"}:
        area = dx * dy
        if stats["solid"] and dz > 1e-3:
            area = abs(stats["volume"] / dz)
        row = {
            "ref": compact_ref("S", g),
            "level": storey,
            "area_m2": float(area),
            "thickness_mm": _m_to_mm(dz) if dz > 1e-4 else 150.0,
            "length_mm": _m_to_mm(max(dx, dy)),
            "breadth_mm": _m_to_mm(min(dx, dy)),
            "rectangular": True,
        }
        return suite_ids.KIND_SLAB, row, bbox

    # Beams as lintels only when thin and elongated — otherwise skip.
    if ifc_class == "IfcBeam" and length > thickness * 2.0 and dz < length:
        row = {
            "ref": compact_ref("L", g),
            "level": storey,
            "mark": props.element_name(obj)[:16] or "L",
            "opening_mm": _m_to_mm(length),
            "width_mm": _m_to_mm(thickness),
            "depth_mm": _m_to_mm(dz),
            "bearing_mm": 150.0,
        }
        return suite_ids.KIND_LINTEL, row, bbox

    return None


def collect_products(scene) -> list:
    """[(obj, kind, row, bbox_mm, n), ...] for take-off push."""
    out = []
    for obj in scene.objects:
        if obj.type != "MESH":
            continue
        if obj.name == "Model" and len(obj.data.polygons) == 0:
            continue
        mapped = row_for_object(obj, scene)
        if mapped is None:
            continue
        kind, row, bbox = mapped
        g = props.guid_of(obj)
        out.append((obj, kind, row, bbox, item_n(g)))
    return out


def opening_schedule(rows: list) -> list:
    """Aggregate door/window marks for header ``opening_schedule``."""
    buckets = {}
    for _obj, kind, row, _bbox, _n in rows:
        if kind != suite_ids.KIND_OPENING:
            continue
        mark = str(row.get("mark") or "")
        okind = str(row.get("kind") or "Opening")
        key = (okind, mark, float(row.get("width_mm", 0)), float(row.get("height_mm", 0)))
        entry = buckets.get(key)
        if entry is None:
            buckets[key] = {
                "kind": okind,
                "mark": mark,
                "width_mm": float(row.get("width_mm", 0)),
                "height_mm": float(row.get("height_mm", 0)),
                "sill_mm": float(row.get("sill_mm", 0)),
                "nos": 1,
            }
        else:
            entry["nos"] += 1
    return list(buckets.values())
