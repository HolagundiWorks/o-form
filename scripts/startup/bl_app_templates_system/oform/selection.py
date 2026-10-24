# SPDX-FileCopyrightText: 2026 O-Form Authors
#
# SPDX-License-Identifier: GPL-2.0-or-later

"""SketchUp-style selection: single / double / triple click semantics.

SketchUp Select tool (when clicking geometry):
  1 click  → the line (edge) under the cursor
  2 clicks → the face (that edge belongs to, or the face hit)
  3 clicks → all connected faces

Central pointer-event recognition so tools do not reimplement click counting.
"""

from __future__ import annotations

import time

import bmesh
from mathutils import Vector

import groups
import inference

# OS-like double-click window (seconds) and movement tolerance (px).
DOUBLE_S = 0.35
MOVE_PX = 8.0

# Hit tolerances — generous so points/lines win over faces (SketchUp-like).
EDGE_PX = 22.0
VERT_PX = 16.0


class ClickTracker:
    """Distinguishes single, double, and triple clicks at a screen position."""

    __slots__ = ("_times", "_pos", "_pending")

    def __init__(self):
        self._times = []
        self._pos = None
        self._pending = None

    def reset(self):
        self._times.clear()
        self._pos = None
        self._pending = None

    def register(self, mouse, now=None):
        """Return 1, 2, or 3 for the click count at this mouse position."""
        now = time.monotonic() if now is None else now
        mouse = tuple(mouse)
        if self._pos is not None:
            if (Vector(self._pos) - Vector(mouse)).length > MOVE_PX:
                self._times.clear()
        self._pos = mouse
        self._times = [t for t in self._times if now - t <= DOUBLE_S]
        self._times.append(now)
        count = min(len(self._times), 3)
        if count == 3:
            self._times.clear()
        return count


def clear_mesh_selection(bm):
    for vert in bm.verts:
        vert.select = False
    for edge in bm.edges:
        edge.select = False
    for face in bm.faces:
        face.select = False


def _select_edge(bm, edge):
    edge.select = True
    for vert in edge.verts:
        vert.select = True


def _select_face(bm, face):
    face.select = True
    for edge in face.edges:
        edge.select = True
        for vert in edge.verts:
            vert.select = True
    for vert in face.verts:
        vert.select = True


def _face_from_hit(hit, mouse=None, context=None):
    """Resolve a face for double-click: prefer face hit, else edge's faces."""
    if hit is None:
        return None
    kind, elem = hit
    if kind == "face":
        return elem
    if kind == "edge":
        faces = list(elem.link_faces)
        if not faces:
            return None
        if len(faces) == 1:
            return faces[0]
        # Prefer the face whose screen projection is nearer the cursor.
        if mouse is not None and context is not None:
            mouse_v = Vector(mouse)
            best = faces[0]
            best_d = 1e9
            for face in faces:
                center = face.calc_center_median()
                screen = inference._screen(context, center)
                if screen is None:
                    continue
                dist = (screen - mouse_v).length
                if dist < best_d:
                    best_d = dist
                    best = face
            return best
        return faces[0]
    if kind == "vert":
        faces = list(elem.link_faces)
        return faces[0] if faces else None
    return None


def select_entity(bm, hit, extend=False):
    """Single-click: point, then line, then face (whatever was picked)."""
    if not extend:
        clear_mesh_selection(bm)
    if hit is None:
        return
    kind, elem = hit
    if kind == "vert":
        elem.select = True
    elif kind == "edge":
        _select_edge(bm, elem)
    elif kind == "face":
        elem.select = True
        for vert in elem.verts:
            vert.select = True


def select_related(bm, hit, extend=False, *, mouse=None, context=None):
    """Double-click: the face (SketchUp: expand to face)."""
    if hit is None:
        return
    if not extend:
        clear_mesh_selection(bm)
    face = _face_from_hit(hit, mouse=mouse, context=context)
    if face is not None:
        _select_face(bm, face)
        return
    select_entity(bm, hit, extend=True)


def select_connected(bm, hit, extend=False, *, mouse=None, context=None):
    """Triple-click: all faces connected through shared edges."""
    if hit is None:
        return
    if not extend:
        clear_mesh_selection(bm)
    seed = _face_from_hit(hit, mouse=mouse, context=context)
    if seed is None:
        kind, elem = hit
        if kind == "edge":
            seed_faces = set(elem.link_faces)
        elif kind == "face":
            seed_faces = {elem}
        elif kind == "vert":
            seed_faces = set(elem.link_faces)
        else:
            seed_faces = set()
    else:
        seed_faces = {seed}
    if not seed_faces:
        select_related(bm, hit, extend=True, mouse=mouse, context=context)
        return
    stack = list(seed_faces)
    seen = set()
    while stack:
        face = stack.pop()
        if face.index in seen:
            continue
        seen.add(face.index)
        face.select = True
        for vert in face.verts:
            vert.select = True
        for edge in face.edges:
            edge.select = True
            for other in edge.link_faces:
                if other.index not in seen:
                    stack.append(other)


def pick_mesh(context, bm, mouse, prefer_face=False):
    """Hit-test for Select: point → line → face (faces only when not near an edge).

    Screen tests use the edit object's world matrix so picks match what you see.
    """
    from mathutils.bvhtree import BVHTree

    mouse_v = Vector(mouse)
    mat = inference._edit_matrix(context)
    bm.edges.ensure_lookup_table()
    bm.faces.ensure_lookup_table()
    bm.verts.ensure_lookup_table()

    # 1) Vertices (points) — highest priority when close
    best_vert = None
    best_vert_px = VERT_PX
    for vert in bm.verts:
        screen = inference._screen(context, vert.co, mat)
        if screen is None:
            continue
        dist = (screen - mouse_v).length
        if dist < best_vert_px:
            best_vert_px = dist
            best_vert = vert

    # 2) Edges (lines)
    best_edge = None
    best_edge_px = EDGE_PX
    for edge in bm.edges:
        a = inference._screen(context, edge.verts[0].co, mat)
        b = inference._screen(context, edge.verts[1].co, mat)
        if a is None or b is None:
            continue
        ab = b - a
        length_sq = ab.length_squared
        if length_sq < 1e-8:
            continue
        t = (mouse_v - a).dot(ab) / length_sq
        t = min(max(t, 0.0), 1.0)
        dist = (a + ab * t - mouse_v).length
        if dist < best_edge_px:
            best_edge_px = dist
            best_edge = edge

    # 3) Face raycast in local space
    face_hit = None
    if bm.faces:
        origin_l, direction_l = inference._ray_local(context, mouse, mat)
        _hit, _n, index, _d = BVHTree.FromBMesh(bm).ray_cast(
            origin_l, direction_l, 10000.0
        )
        if index is not None and 0 <= index < len(bm.faces):
            face_hit = bm.faces[index]

    if prefer_face and face_hit is not None:
        return ("face", face_hit)

    # Point wins when within tolerance, then line, then face interior.
    if best_vert is not None:
        return ("vert", best_vert)
    if best_edge is not None:
        return ("edge", best_edge)
    if face_hit is not None:
        return ("face", face_hit)
    return None


def apply_click(context, bm, mouse, count, extend=False):
    """Apply SketchUp selection for a finalized click count."""
    container = None
    if count >= 1:
        container = groups.pick_container(context, mouse)
    if container is not None and count == 1:
        groups.set_entity(context, container)
        clear_mesh_selection(bm)
        return "entity"
    if container is not None and count >= 2:
        groups.set_entity(context, None)
        groups.push_context(context, container)
        return "enter"
    if count == 1:
        groups.set_entity(context, None)
    hit = pick_mesh(context, bm, mouse)
    if count <= 1:
        select_entity(bm, hit, extend=extend)
        return "single" if hit else "clear"
    if count == 2:
        select_related(bm, hit, extend=extend, mouse=mouse, context=context)
        return "double" if hit else "clear"
    select_connected(bm, hit, extend=extend, mouse=mouse, context=context)
    return "triple" if hit else "clear"


def hover_snap(context, bm, mouse):
    """Lightweight snap under cursor for Select / draw hover feedback."""
    mat = inference._edit_matrix(context)
    hit = pick_mesh(context, bm, mouse)
    if hit is None:
        return inference.infer(context, bm, mouse)
    kind, elem = hit
    if kind == "vert":
        return inference.Snap(elem.co, "vertex", Vector((0, 0, 1)), label="Endpoint")
    if kind == "edge":
        a = elem.verts[0].co
        b = elem.verts[1].co
        mouse_v = Vector(mouse)
        sa = inference._screen(context, a, mat)
        sb = inference._screen(context, b, mat)
        if sa is not None and sb is not None:
            ab = sb - sa
            length_sq = ab.length_squared
            if length_sq > 1e-8:
                t = (mouse_v - sa).dot(ab) / length_sq
                t = min(max(t, 0.0), 1.0)
                if t < 0.12:
                    return inference.Snap(a, "vertex", Vector((0, 0, 1)), label="Endpoint")
                if t > 0.88:
                    return inference.Snap(b, "vertex", Vector((0, 0, 1)), label="Endpoint")
                if abs(t - 0.5) < 0.08:
                    mid = (a + b) * 0.5
                    return inference.Snap(
                        mid, "midpoint", Vector((0, 0, 1)), b - a, label="Midpoint"
                    )
                co = a.lerp(b, t)
                return inference.Snap(co, "edge", Vector((0, 0, 1)), b - a, label="On Edge")
        return inference.Snap(
            (a + b) * 0.5, "edge", Vector((0, 0, 1)), b - a, label="On Edge"
        )
    if kind == "face":
        from mathutils.bvhtree import BVHTree

        origin_l, direction_l = inference._ray_local(context, mouse, mat)
        hit_pt, normal, _i, _d = BVHTree.FromBMesh(bm).ray_cast(
            origin_l, direction_l, 10000.0
        )
        if hit_pt is not None:
            return inference.Snap(hit_pt, "face", normal, label="On Face")
        return inference.Snap(
            elem.calc_center_median(), "face", elem.normal, label="On Face"
        )
    return inference.infer(context, bm, mouse)
