# SPDX-FileCopyrightText: 2026 O-Form Authors
#
# SPDX-License-Identifier: GPL-2.0-or-later

"""Simple BIM quantities from mesh geometry (no IFC Qto dependency)."""

from __future__ import annotations

import bmesh
from mathutils import Vector


def mesh_stats(obj) -> dict:
    """Return area (m² surface), volume (m³ if manifold), bbox size."""
    empty = {"area": 0.0, "volume": 0.0, "solid": False, "size": (0.0, 0.0, 0.0)}
    if obj is None or obj.type != "MESH" or obj.data is None:
        return empty
    mesh = obj.data
    if obj.mode == "EDIT":
        bm = bmesh.from_edit_mesh(mesh)
        own = False
    else:
        bm = bmesh.new()
        bm.from_mesh(mesh)
        own = True
    try:
        bm.transform(obj.matrix_world)
        bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
        area = sum(f.calc_area() for f in bm.faces)
        solid = False
        volume = 0.0
        try:
            volume = abs(float(bm.calc_volume(signed=False)))
            solid = True
        except Exception:
            volume = 0.0
        corners = [obj.matrix_world @ Vector(c) for c in obj.bound_box]
        xs = [c.x for c in corners]
        ys = [c.y for c in corners]
        zs = [c.z for c in corners]
        size = (max(xs) - min(xs), max(ys) - min(ys), max(zs) - min(zs))
        return {"area": area, "volume": volume, "solid": solid, "size": size}
    finally:
        if own:
            bm.free()
