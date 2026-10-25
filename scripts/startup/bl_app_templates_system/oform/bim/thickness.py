# SPDX-FileCopyrightText: 2026 O-Form Authors
#
# SPDX-License-Identifier: GPL-2.0-or-later

"""Wall thickness measure and snap to standard widths (4.5\" / 9\").

Straight walls: the thinner object-local horizontal axis is the width
(X or Y, whichever is shorter in world length). Corner / L walls are
detected from perpendicular vertical-face clusters and are not scaled
as a whole — only a local face-pair normalize is offered.
"""

from __future__ import annotations

import math

import bmesh
from mathutils import Vector

INCH = 0.0254
WIDTH_4_5 = 4.5 * INCH  # 0.1143 m
WIDTH_9 = 9.0 * INCH  # 0.2286 m
STANDARDS = (
    ("4.5", WIDTH_4_5),
    ("9", WIDTH_9),
)

# Snap is the default only when the measured width is this close to a standard.
_BAND_INCH = INCH
_BAND_RATIO = 0.25


def _band(standard: float) -> float:
    return max(_BAND_INCH, _BAND_RATIO * standard)


def nearest_standard(width_m: float):
    """Return (id, metres, in_band) for the closer of 4.5\" and 9\"."""
    best_id, best_m, best_d = STANDARDS[0][0], STANDARDS[0][1], abs(width_m - STANDARDS[0][1])
    for sid, metres in STANDARDS[1:]:
        dist = abs(width_m - metres)
        if dist < best_d:
            best_id, best_m, best_d = sid, metres, dist
    return best_id, best_m, best_d <= _band(best_m)


def format_inches(metres: float) -> str:
    inches = metres / INCH
    return '{:.2f}"'.format(inches)


def _local_extents(obj):
    """World length of each object axis from the bound box."""
    if obj is None or obj.type != "MESH" or obj.data is None:
        return None
    corners = [Vector(corner) for corner in obj.bound_box]
    spans = []
    for axis in range(3):
        coords = [corner[axis] for corner in corners]
        spans.append(max(coords) - min(coords))
    mat = obj.matrix_world.to_3x3()
    world = []
    for axis, span in enumerate(spans):
        direction = Vector((0.0, 0.0, 0.0))
        direction[axis] = span
        world.append((mat @ direction).length)
    center = sum((obj.matrix_world @ corner for corner in corners), Vector()) / 8.0
    local_center = sum(corners, Vector()) / 8.0
    return {
        "local": tuple(spans),
        "world": tuple(world),
        "center": center,
        "local_center": local_center,
    }


def _world_bm(obj):
    """BMesh in world space. Caller frees it."""
    bm = bmesh.new()
    bm.from_mesh(obj.data)
    bm.transform(obj.matrix_world)
    bm.normal_update()
    return bm


def _vertical_clusters(bm):
    """Bin vertical faces into 8 plan-angle buckets. Returns {key: [faces]}."""
    bins = {}
    for face in bm.faces:
        normal = face.normal
        if normal.length < 1e-8:
            continue
        normal = normal.normalized()
        if abs(normal.z) >= 0.35:
            continue
        angle = math.atan2(normal.y, normal.x)
        key = int(round(angle / (math.pi / 4.0))) % 8
        bins.setdefault(key, []).append(face)
    return bins


def _cluster_area(faces):
    return sum(face.calc_area() for face in faces if face.is_valid)


def is_corner(obj) -> bool:
    """True when the plan has two significant vertical runs about 90° apart."""
    if obj is None or obj.type != "MESH" or obj.data is None or not obj.data.polygons:
        return False
    bm = _world_bm(obj)
    try:
        bins = _vertical_clusters(bm)
        areas = {key: _cluster_area(faces) for key, faces in bins.items()}
        if len(areas) < 2:
            return False
        top = max(areas.values())
        if top < 1e-8:
            return False
        significant = [key for key, area in areas.items() if area > top * 0.2]
        for index, left in enumerate(significant):
            for right in significant[index + 1 :]:
                delta = min((left - right) % 8, (right - left) % 8)
                if delta == 2:
                    return True
        return False
    finally:
        bm.free()


def inspect(obj) -> dict:
    """Measure width and whether a standard snap is in range."""
    empty = {
        "ok": False,
        "corner": False,
        "width": 0.0,
        "axis": "Y",
        "nearest_id": "9",
        "nearest_m": WIDTH_9,
        "in_band": False,
        "label": "",
    }
    extents = _local_extents(obj)
    if extents is None:
        return empty
    wx, wy, _wz = extents["world"]
    if wx <= wy:
        width, axis = wx, "X"
    else:
        width, axis = wy, "Y"
    nearest_id, nearest_m, in_band = nearest_standard(width)
    corner = is_corner(obj)
    return {
        "ok": width > 1e-6,
        "corner": corner,
        "width": width,
        "axis": axis,
        "nearest_id": nearest_id,
        "nearest_m": nearest_m,
        "in_band": in_band and not corner,
        "label": format_inches(width),
        "local_center": extents["local_center"],
    }


def _edit_local(obj, mutate):
    """Run ``mutate(bm)`` on the object mesh in local space."""
    edit = getattr(obj, "mode", "OBJECT") == "EDIT"
    if edit:
        bm = bmesh.from_edit_mesh(obj.data)
        mutate(bm)
        bmesh.update_edit_mesh(obj.data)
        return
    bm = bmesh.new()
    bm.from_mesh(obj.data)
    mutate(bm)
    bm.to_mesh(obj.data)
    bm.free()
    obj.data.update()


def scale_to_width(obj, axis: str, target_m: float) -> bool:
    """Scale the thin local axis about the bound-box center. Length and height stay."""
    info = inspect(obj)
    if not info["ok"] or info["width"] < 1e-8:
        return False
    use_axis = axis or info["axis"]
    index = 0 if use_axis == "X" else 1
    factor = float(target_m) / float(info["width"])
    if abs(factor - 1.0) < 1e-6:
        return True
    center = info["local_center"]

    def mutate(bm):
        for vert in bm.verts:
            co = vert.co
            co[index] = center[index] + (co[index] - center[index]) * factor

    _edit_local(obj, mutate)
    return True


def _pair_thickness(faces_a, faces_b, axis):
    def _pos(faces):
        area = 0.0
        acc = 0.0
        for face in faces:
            if not face.is_valid:
                continue
            weight = face.calc_area()
            acc += face.calc_center_median()[axis] * weight
            area += weight
        if area < 1e-10:
            return None, 0.0
        return acc / area, area

    pos_a, area_a = _pos(faces_a)
    pos_b, area_b = _pos(faces_b)
    if pos_a is None or pos_b is None:
        return None
    return {
        "axis": axis,
        "pos_a": pos_a,
        "pos_b": pos_b,
        "area_a": area_a,
        "area_b": area_b,
        "thickness": abs(pos_a - pos_b),
        "faces_a": faces_a,
        "faces_b": faces_b,
    }


def normalize_local(obj, target_m=None) -> bool:
    """Flatten each wall run onto the nearest standard thickness. No global scale.

    Corner junctions are updated once per axis, so an L keeps its plan turn
    while each leg's thickness is reset.
    """
    if obj is None or obj.type != "MESH" or obj.data is None:
        return False
    bm = _world_bm(obj)
    try:
        bins = _vertical_clusters(bm)
        pairs = []
        # 0/+X with 4/-X, 2/+Y with 6/-Y.
        for left, right, axis in ((0, 4, 0), (2, 6, 1)):
            if left not in bins or right not in bins:
                continue
            pair = _pair_thickness(bins[left], bins[right], axis)
            if pair is None or pair["thickness"] < 1e-4:
                continue
            pairs.append(pair)
        if not pairs:
            return False
        samples = [pair["thickness"] for pair in pairs]
        median = sorted(samples)[len(samples) // 2]
        _sid, nearest_m, _in_band = nearest_standard(median)
        target = float(target_m) if target_m else nearest_m

        # Work in world, then write back through the object matrix.
        # Corner verts collect one delta per axis so the L junction stays square.
        moves = {}
        for pair in pairs:
            if pair["area_a"] >= pair["area_b"]:
                ext_pos, ext_faces = pair["pos_a"], pair["faces_a"]
                int_pos, int_faces = pair["pos_b"], pair["faces_b"]
            else:
                ext_pos, ext_faces = pair["pos_b"], pair["faces_b"]
                int_pos, int_faces = pair["pos_a"], pair["faces_a"]
            sign = 1.0 if int_pos >= ext_pos else -1.0
            desired = ext_pos + sign * target
            ext_verts = {vert for face in ext_faces for vert in face.verts}
            axis = pair["axis"]
            for face in int_faces:
                for vert in face.verts:
                    if vert in ext_verts:
                        continue
                    if abs(vert.co[axis] - int_pos) > abs(vert.co[axis] - ext_pos):
                        continue
                    moves.setdefault(vert.index, {})[axis] = desired - vert.co[axis]
        for vert in bm.verts:
            shift = moves.get(vert.index)
            if not shift:
                continue
            for axis, delta in shift.items():
                vert.co[axis] += delta
        bm.transform(obj.matrix_world.inverted())
        bm.to_mesh(obj.data)
        obj.data.update()
        if getattr(obj, "mode", "OBJECT") == "EDIT":
            edit = bmesh.from_edit_mesh(obj.data)
            edit.clear()
            edit.from_mesh(obj.data)
            bmesh.update_edit_mesh(obj.data)
        return True
    finally:
        bm.free()


def apply_mode(obj, mode: str) -> str:
    """Apply KEEP / SNAP45 / SNAP9 / LOCAL. Returns a short status fragment."""
    info = inspect(obj)
    if not info["ok"] or mode in {None, "", "KEEP"}:
        return "kept " + (info["label"] or "width")
    if info["corner"]:
        if mode != "LOCAL":
            return "corner kept " + info["label"]
        nearest = info["nearest_m"]
        if not normalize_local(obj, nearest):
            return "corner unchanged"
        return "corner normalized to " + format_inches(nearest)
    if mode == "LOCAL":
        if not normalize_local(obj, info["nearest_m"]):
            return "unchanged"
        return "normalized to " + format_inches(info["nearest_m"])
    target = WIDTH_4_5 if mode == "SNAP45" else WIDTH_9
    if mode not in {"SNAP45", "SNAP9"}:
        return "kept " + info["label"]
    scale_to_width(obj, info["axis"], target)
    return "width {} → {}".format(info["label"], format_inches(target))
