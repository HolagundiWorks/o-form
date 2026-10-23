# SPDX-FileCopyrightText: 2026 O-Form Authors
#
# SPDX-License-Identifier: GPL-2.0-or-later

"""Point inference for O-Form tools.

Snap order matches a push/pull modeler: vertex, midpoint, edge, face, then the
ground plane. Arrow keys lock the result to an axis or to a parallel edge.
"""

from mathutils import Vector
from mathutils.bvhtree import BVHTree
from mathutils.geometry import intersect_line_line
from bpy_extras import view3d_utils

import geom

VERTEX_PX = 12.0
EDGE_PX = 8.0


class Snap:
    def __init__(self, co, kind, normal, tangent=None):
        self.co = Vector(co)
        self.kind = kind
        self.normal = Vector(normal) if normal is not None else Vector((0.0, 0.0, 1.0))
        self.tangent = None if tangent is None else Vector(tangent)


def _screen(context, co):
    return view3d_utils.location_3d_to_region_2d(context.region, context.region_data, co)


def _ray(context, mouse):
    region = context.region
    rv3d = context.region_data
    origin = view3d_utils.region_2d_to_origin_3d(region, rv3d, mouse)
    direction = view3d_utils.region_2d_to_vector_3d(region, rv3d, mouse)
    return origin, direction


def _ground(origin, direction):
    if abs(direction.z) < 1e-8:
        return None
    t = -origin.z / direction.z
    if t < 0.0:
        return None
    return origin + direction * t


def infer(context, bm, mouse, axis=None, parallel=None, anchor=None):
    """Return a Snap for the mouse position."""
    origin, direction = _ray(context, mouse)
    geom._ensure(bm)
    best = None
    best_px = VERTEX_PX

    for vert in bm.verts:
        screen = _screen(context, vert.co)
        if screen is None:
            continue
        dist = (screen - Vector(mouse)).length
        if dist <= best_px:
            best_px = dist
            best = Snap(vert.co, "vertex", Vector((0.0, 0.0, 1.0)))

    if best is None or best.kind != "vertex":
        for edge in bm.edges:
            mid = (edge.verts[0].co + edge.verts[1].co) * 0.5
            screen = _screen(context, mid)
            if screen is None:
                continue
            dist = (screen - Vector(mouse)).length
            if dist <= VERTEX_PX and (best is None or dist < best_px):
                best_px = dist
                tangent = edge.verts[1].co - edge.verts[0].co
                best = Snap(mid, "midpoint", Vector((0.0, 0.0, 1.0)), tangent)

    if best is None:
        for edge in bm.edges:
            a = _screen(context, edge.verts[0].co)
            b = _screen(context, edge.verts[1].co)
            if a is None or b is None:
                continue
            ab = b - a
            length_sq = ab.length_squared
            if length_sq < 1e-8:
                continue
            t = (Vector(mouse) - a).dot(ab) / length_sq
            if t < 0.0 or t > 1.0:
                continue
            closest = a + ab * t
            dist = (closest - Vector(mouse)).length
            if dist <= EDGE_PX:
                tangent = edge.verts[1].co - edge.verts[0].co
                co = edge.verts[0].co.lerp(edge.verts[1].co, t)
                best = Snap(co, "edge", Vector((0.0, 0.0, 1.0)), tangent)
                break

    if best is None and len(bm.faces):
        tree = BVHTree.FromBMesh(bm, epsilon=0.0)
        hit, normal, _index, _dist = tree.ray_cast(origin, direction, 10000.0)
        if hit is not None:
            best = Snap(hit, "face", normal)

    if best is None:
        ground = _ground(origin, direction)
        if ground is None:
            ground = origin + direction * 10.0
            ground.z = 0.0
        best = Snap(ground, "plane", Vector((0.0, 0.0, 1.0)))

    best.co = constrain(origin, direction, best.co, axis, parallel, anchor)
    if axis in {"X", "Y", "Z"}:
        best.kind = "axis"
    elif axis == "PARALLEL":
        best.kind = "parallel"
    return best


def constrain(origin, direction, co, axis, parallel, anchor):
    if anchor is None or axis is None:
        return Vector(co)
    anchor = Vector(anchor)
    if axis == "X":
        direction_axis = Vector((1.0, 0.0, 0.0))
    elif axis == "Y":
        direction_axis = Vector((0.0, 1.0, 0.0))
    elif axis == "Z":
        direction_axis = Vector((0.0, 0.0, 1.0))
    elif axis == "PARALLEL" and parallel is not None and parallel.length > 1e-8:
        direction_axis = Vector(parallel).normalized()
    else:
        return Vector(co)
    hits = intersect_line_line(
        anchor,
        anchor + direction_axis,
        origin,
        origin + direction * 1000.0,
    )
    if hits is None or hits[0] is None:
        locked = Vector(co)
        if axis == "X":
            locked.y = anchor.y
            locked.z = anchor.z
        elif axis == "Y":
            locked.x = anchor.x
            locked.z = anchor.z
        elif axis == "Z":
            locked.x = anchor.x
            locked.y = anchor.y
        return locked
    return Vector(hits[0])


def axis_label(axis):
    return {
        "X": "On Red Axis",
        "Y": "On Green Axis",
        "Z": "On Blue Axis",
        "PARALLEL": "Parallel to Edge",
    }.get(axis, "")
