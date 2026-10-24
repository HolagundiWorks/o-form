# SPDX-FileCopyrightText: 2026 O-Form Authors
#
# SPDX-License-Identifier: GPL-2.0-or-later

"""SketchUp-style inference: working planes, snaps, locks, and guide cues.

Pipeline: ray → plane hit → geometric candidates (screen-space priority) →
axis / parallel locks → Snap with guide segments for the preview renderer.
"""

from __future__ import annotations

from mathutils import Vector
from mathutils.bvhtree import BVHTree
from mathutils.geometry import intersect_line_line
from bpy_extras import view3d_utils

import geom

VERTEX_PX = 16.0
EDGE_PX = 14.0
ALIGN_PX = 10.0


class WorkingPlane:
    """Active drawing plane: point + normal (model / local space)."""

    __slots__ = ("origin", "normal", "source")

    def __init__(self, origin, normal, source="ground"):
        self.origin = Vector(origin)
        n = Vector(normal)
        self.normal = n.normalized() if n.length > 1e-8 else Vector((0.0, 0.0, 1.0))
        self.source = source  # "face" | "ground" | "inferred" | "locked"

    def copy(self):
        return WorkingPlane(self.origin, self.normal, self.source)


class Snap:
    __slots__ = ("co", "kind", "normal", "tangent", "label", "guides", "plane")

    def __init__(self, co, kind, normal, tangent=None, label="", guides=None, plane=None):
        self.co = Vector(co)
        self.kind = kind
        self.normal = Vector(normal) if normal is not None else Vector((0.0, 0.0, 1.0))
        self.tangent = None if tangent is None else Vector(tangent)
        self.label = label or _default_label(kind)
        self.guides = list(guides or [])  # [[Vector, Vector], ...] world/local segments
        self.plane = plane


def _default_label(kind):
    return {
        "vertex": "Endpoint",
        "midpoint": "Midpoint",
        "edge": "On Edge",
        "face": "On Face",
        "plane": "On Plane",
        "axis": "Axis",
        "parallel": "Parallel",
        "perpendicular": "Perpendicular",
        "intersection": "Intersection",
        "from_point": "From Point",
    }.get(kind, kind.replace("_", " ").title())


def _edit_matrix(context):
    """World matrix of the active edit-mesh object (identity if unknown)."""
    import groups

    obj = groups.context_object(context, create=False)
    if obj is None:
        obj = getattr(context, "edit_object", None) or getattr(context, "object", None)
    if obj is not None and getattr(obj, "matrix_world", None) is not None:
        return obj.matrix_world
    from mathutils import Matrix

    return Matrix.Identity(4)


def _screen(context, co, matrix_world=None):
    """Project a point to region 2D. ``co`` is local unless already world.

    Pass ``matrix_world`` when ``co`` is mesh-local (BMesh vert/edge coords).
    """
    if matrix_world is not None:
        co = matrix_world @ Vector(co)
    else:
        co = Vector(co)
    return view3d_utils.location_3d_to_region_2d(context.region, context.region_data, co)


def _ray(context, mouse):
    """World-space ray from the mouse."""
    region = context.region
    rv3d = context.region_data
    origin = view3d_utils.region_2d_to_origin_3d(region, rv3d, mouse)
    direction = view3d_utils.region_2d_to_vector_3d(region, rv3d, mouse)
    return origin, direction


def _ray_local(context, mouse, matrix_world=None):
    """Ray in mesh-local space for BVHTree.FromBMesh casts."""
    origin, direction = _ray(context, mouse)
    mat = matrix_world if matrix_world is not None else _edit_matrix(context)
    try:
        imat = mat.inverted()
    except ValueError:
        return origin, direction
    origin_l = imat @ origin
    direction_l = (imat.to_3x3() @ direction).normalized()
    return origin_l, direction_l


def ray_plane_intersect(origin, direction, plane: WorkingPlane):
    """R(t)=O+tD ∩ plane (P0, n). Returns point or None."""
    denom = plane.normal.dot(direction)
    if abs(denom) < 1e-8:
        return None
    t = plane.normal.dot(plane.origin - origin) / denom
    if t < 0.0:
        return None
    return origin + direction * t


def plane_from_face(face):
    return WorkingPlane(face.calc_center_median(), face.normal, "face")


def ground_plane(z=0.0):
    return WorkingPlane(Vector((0.0, 0.0, z)), Vector((0.0, 0.0, 1.0)), "ground")


def establish_plane(bm, snap, fallback=None):
    """Choose a working plane from the first click snap."""
    if snap is None:
        return fallback or ground_plane()
    if snap.kind == "face" and snap.normal.length > 1e-8:
        return WorkingPlane(snap.co, snap.normal, "face")
    if snap.plane is not None and snap.kind in {"plane", "face"}:
        return snap.plane.copy()
    if snap.kind in {"vertex", "midpoint", "edge"} and bm is not None:
        # Prefer a connected face so drawing on a vertical wall stays on that wall.
        best = None
        for face in bm.faces:
            for vert in face.verts:
                if (vert.co - snap.co).length < 1e-5:
                    best = face
                    break
            if best is not None:
                break
            for edge in face.edges:
                a, b = edge.verts[0].co, edge.verts[1].co
                ab = b - a
                length_sq = ab.length_squared
                if length_sq < 1e-12:
                    continue
                t = (snap.co - a).dot(ab) / length_sq
                if 0.0 <= t <= 1.0 and (a + ab * t - snap.co).length < 1e-4:
                    best = face
                    break
            if best is not None:
                break
        if best is not None and best.normal.length > 1e-8:
            return WorkingPlane(snap.co, best.normal, "face")
        base = fallback or ground_plane()
        return WorkingPlane(snap.co, base.normal, "inferred")
    if snap.kind == "plane":
        return WorkingPlane(snap.co, snap.normal, "plane")
    return fallback or ground_plane()


def _axis_vector(axis):
    return {
        "X": Vector((1.0, 0.0, 0.0)),
        "Y": Vector((0.0, 1.0, 0.0)),
        "Z": Vector((0.0, 0.0, 1.0)),
    }.get(axis)


def constrain(origin, direction, co, axis, parallel, anchor):
    if anchor is None or axis is None:
        return Vector(co)
    anchor = Vector(anchor)
    if axis in {"X", "Y", "Z"}:
        direction_axis = _axis_vector(axis)
    elif axis == "PARALLEL" and parallel is not None and parallel.length > 1e-8:
        direction_axis = Vector(parallel).normalized()
    else:
        return Vector(co)
    hits = intersect_line_line(
        anchor,
        anchor + direction_axis,
        origin,
        origin + direction * 10000.0,
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


def infer(
    context,
    bm,
    mouse,
    axis=None,
    parallel=None,
    anchor=None,
    plane: WorkingPlane | None = None,
):
    """Resolve cursor → Snap with optional working-plane preference."""
    mat = _edit_matrix(context)
    origin, direction = _ray(context, mouse)
    origin_l, direction_l = _ray_local(context, mouse, mat)
    geom._ensure(bm)
    mouse_v = Vector(mouse)
    active_plane = plane or ground_plane()

    candidates = []

    # --- Point snaps (screen-space, mesh-local → world for projection) ---
    for vert in bm.verts:
        screen = _screen(context, vert.co, mat)
        if screen is None:
            continue
        dist = (screen - mouse_v).length
        if dist <= VERTEX_PX:
            candidates.append((dist, 0, Snap(vert.co, "vertex", active_plane.normal)))

    for edge in bm.edges:
        a_co = edge.verts[0].co
        b_co = edge.verts[1].co
        mid = (a_co + b_co) * 0.5
        screen = _screen(context, mid, mat)
        if screen is not None:
            dist = (screen - mouse_v).length
            if dist <= VERTEX_PX:
                tangent = b_co - a_co
                candidates.append(
                    (dist, 1, Snap(mid, "midpoint", active_plane.normal, tangent))
                )
        a = _screen(context, a_co, mat)
        b = _screen(context, b_co, mat)
        if a is None or b is None:
            continue
        ab = b - a
        length_sq = ab.length_squared
        if length_sq < 1e-8:
            continue
        t = (mouse_v - a).dot(ab) / length_sq
        if 0.0 <= t <= 1.0:
            closest = a + ab * t
            dist = (closest - mouse_v).length
            if dist <= EDGE_PX:
                co = a_co.lerp(b_co, t)
                tangent = b_co - a_co
                candidates.append(
                    (dist, 2, Snap(co, "edge", active_plane.normal, tangent))
                )

    # From-point / square / alignment when an anchor exists
    if anchor is not None:
        for other in bm.verts:
            # Align X/Y/Z with anchor (from point)
            for axis_name, vec in (("X", Vector((1, 0, 0))), ("Y", Vector((0, 1, 0))), ("Z", Vector((0, 0, 1)))):
                projected = Vector(anchor)
                if axis_name == "X":
                    projected.x = other.co.x
                elif axis_name == "Y":
                    projected.y = other.co.y
                else:
                    projected.z = other.co.z
                screen = _screen(context, projected)
                if screen is None:
                    continue
                dist = (screen - mouse_v).length
                if dist <= ALIGN_PX:
                    guides = [[Vector(anchor), projected]]
                    candidates.append(
                        (
                            dist,
                            3,
                            Snap(
                                projected,
                                "from_point",
                                active_plane.normal,
                                vec,
                                label="From Point",
                                guides=guides,
                            ),
                        )
                    )

    # Face hit (BVH in local space) — also seeds plane when none locked
    face_hit = None
    if len(bm.faces):
        tree = BVHTree.FromBMesh(bm, epsilon=0.0)
        hit, normal, index, _dist = tree.ray_cast(origin_l, direction_l, 10000.0)
        if hit is not None:
            face_hit = Snap(hit, "face", normal)
            screen = _screen(context, hit, mat)
            dist = (screen - mouse_v).length if screen is not None else 50.0
            candidates.append((dist, 4, face_hit))

    # Preferred plane intersection in local space (not forced to ground)
    plane_pt = ray_plane_intersect(origin_l, direction_l, active_plane)
    if plane_pt is not None:
        screen = _screen(context, plane_pt, mat)
        dist = (screen - mouse_v).length if screen is not None else 80.0
        candidates.append(
            (
                dist,
                5,
                Snap(plane_pt, "plane", active_plane.normal, plane=active_plane),
            )
        )
    elif face_hit is None:
        # Degenerate: fall back along ray onto Z=0 (local)
        ground = ray_plane_intersect(origin_l, direction_l, ground_plane())
        if ground is None:
            ground = origin_l + direction_l * 10.0
            ground.z = 0.0
        candidates.append((999.0, 6, Snap(ground, "plane", Vector((0.0, 0.0, 1.0)))))

    candidates.sort(key=lambda item: (item[0], item[1]))
    best = candidates[0][2] if candidates else Snap(Vector((0, 0, 0)), "plane", Vector((0, 0, 1)))

    # Axis / parallel lock after pick (local-space ray)
    locked = constrain(origin_l, direction_l, best.co, axis, parallel, anchor)
    best.co = locked
    if axis in {"X", "Y", "Z"}:
        best.kind = "axis"
        best.label = axis_label(axis)
        if anchor is not None:
            best.guides = [[Vector(anchor), Vector(best.co)]]
    elif axis == "PARALLEL":
        best.kind = "parallel"
        best.label = axis_label(axis)
        if anchor is not None:
            best.guides = [[Vector(anchor), Vector(best.co)]]

    # Inference guides from anchor along axes when unlocked and close
    if anchor is not None and axis is None and best.kind in {"plane", "face", "edge", "from_point"}:
        delta = best.co - Vector(anchor)
        guides = list(best.guides)
        for name, unit, color_kind in (
            ("X", Vector((1, 0, 0)), "axis_x"),
            ("Y", Vector((0, 1, 0)), "axis_y"),
            ("Z", Vector((0, 0, 1)), "axis_z"),
        ):
            if abs(delta.dot(unit)) > 1e-6 and delta.cross(unit).length < 1e-3 * max(delta.length, 1e-6):
                best.kind = "axis"
                best.label = axis_label(name)
                guides.append([Vector(anchor), Vector(best.co)])
                break
        best.guides = guides

    # Draw-on-face: keep every snap stuck to the locked working plane.
    if plane is not None:
        n = plane.normal
        best.co = best.co - n * (best.co - plane.origin).dot(n)
        best.plane = plane
        best.normal = n.copy()
        if best.kind in {"plane", "face"} or not best.label:
            best.label = "On Plane"
    else:
        best.plane = active_plane
    return best
