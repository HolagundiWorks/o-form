# SPDX-FileCopyrightText: 2026 O-Form Authors
#
# SPDX-License-Identifier: GPL-2.0-or-later

"""Heuristic IFC class from object bounds (wall / slab / column / proxy)."""

from __future__ import annotations

from mathutils import Vector

from . import taxonomy


def _dims(obj):
    """Axis-aligned world dimensions (x, y, z) of the object bound box."""
    if obj is None or obj.type != "MESH":
        return None
    corners = [obj.matrix_world @ Vector(corner) for corner in obj.bound_box]
    xs = [c.x for c in corners]
    ys = [c.y for c in corners]
    zs = [c.z for c in corners]
    return (
        max(xs) - min(xs),
        max(ys) - min(ys),
        max(zs) - min(zs),
    )


def suggest_class(obj) -> str:
    """Return a likely Ifc* class for a mesh object."""
    dims = _dims(obj)
    if dims is None:
        return taxonomy.DEFAULT_ELEMENT
    dx, dy, dz = dims
    # Degenerate
    if max(dx, dy, dz) < 1e-6:
        return taxonomy.DEFAULT_ELEMENT
    flat = sorted((dx, dy, dz))
    # Slab / roof: dominant horizontal extent, thin vertical
    if dz < flat[1] * 0.35 and max(dx, dy) > dz * 3.0:
        return "IfcSlab"
    # Column: tall, roughly square footprint
    footprint = min(dx, dy)
    if dz > footprint * 2.5 and max(dx, dy) / max(footprint, 1e-6) < 2.5:
        return "IfcColumn"
    # Beam: elongated horizontal prism
    if max(dx, dy) > dz * 2.5 and dz > min(dx, dy) * 0.5:
        long_h = max(dx, dy)
        short_h = min(dx, dy)
        if long_h > short_h * 2.0 and dz < long_h * 0.5:
            return "IfcBeam"
    # Wall: vertical plane-ish — one horizontal thin, height significant
    if dz > min(dx, dy) * 1.2:
        thickness = min(dx, dy)
        length = max(dx, dy)
        if length > thickness * 2.0 and dz > thickness:
            return "IfcWall"
    return taxonomy.DEFAULT_ELEMENT
