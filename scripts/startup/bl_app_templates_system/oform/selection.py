# SPDX-FileCopyrightText: 2026 O-Form Authors
#
# SPDX-License-Identifier: GPL-2.0-or-later

"""SketchUp-style selection: single / double / triple click semantics.

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


class ClickTracker:
    """Distinguishes single, double, and triple clicks at a screen position."""

    __slots__ = ("_times", "_pos", "_pending")

    def __init__(self):
        self._times = []
        self._pos = None
        self._pending = None  # deferred single-click callback token

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
        # Drop stale clicks outside the multi-click window.
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


def select_entity(bm, hit, extend=False):
    """Single-click: one edge, face, or leave verts as picked."""
    if not extend:
        clear_mesh_selection(bm)
    if hit is None:
        return
    kind, elem = hit
    if kind == "vert":
        elem.select = True
        bm.select_flush(True)
    elif kind == "edge":
        elem.select = True
        for vert in elem.verts:
            vert.select = True
    elif kind == "face":
        elem.select = True
        for vert in elem.verts:
            vert.select = True


def select_related(bm, hit, extend=False):
    """Double-click: face+boundary edges, or edge+adjacent faces."""
    if hit is None:
        return
    kind, elem = hit
    if not extend:
        clear_mesh_selection(bm)
    if kind == "face":
        elem.select = True
        for edge in elem.edges:
            edge.select = True
            for vert in edge.verts:
                vert.select = True
        for vert in elem.verts:
            vert.select = True
    elif kind == "edge":
        elem.select = True
        for vert in elem.verts:
            vert.select = True
        for face in elem.link_faces:
            face.select = True
            for vert in face.verts:
                vert.select = True
    else:
        select_entity(bm, hit, extend=True)


def select_connected(bm, hit, extend=False):
    """Triple-click: flood connected faces/edges from the hit entity."""
    if hit is None:
        return
    if not extend:
        clear_mesh_selection(bm)
    kind, elem = hit
    seed_faces = set()
    if kind == "face":
        seed_faces.add(elem)
    elif kind == "edge":
        seed_faces.update(elem.link_faces)
    elif kind == "vert":
        seed_faces.update(elem.link_faces)
    if not seed_faces:
        select_related(bm, hit, extend=True)
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
    """Hit-test mesh under the cursor. Returns (kind, element) or None."""
    from bpy_extras import view3d_utils
    from mathutils.bvhtree import BVHTree

    mouse_v = Vector(mouse)
    best_vert = None
    best = 12.0
    for vert in bm.verts:
        screen = inference._screen(context, vert.co)
        if screen is None:
            continue
        dist = (screen - mouse_v).length
        if dist < best:
            best = dist
            best_vert = vert
    if best_vert is not None and best <= 12.0 and not prefer_face:
        return ("vert", best_vert)

    # Edge proximity
    best_edge = None
    best_px = 10.0
    for edge in bm.edges:
        a = inference._screen(context, edge.verts[0].co)
        b = inference._screen(context, edge.verts[1].co)
        if a is None or b is None:
            continue
        ab = b - a
        length_sq = ab.length_squared
        if length_sq < 1e-8:
            continue
        t = (mouse_v - a).dot(ab) / length_sq
        t = min(max(t, 0.0), 1.0)
        dist = (a + ab * t - mouse_v).length
        if dist < best_px:
            best_px = dist
            best_edge = edge
    if best_edge is not None and not prefer_face:
        return ("edge", best_edge)

    if bm.faces:
        region = context.region
        rv3d = context.region_data
        origin = view3d_utils.region_2d_to_origin_3d(region, rv3d, mouse)
        direction = view3d_utils.region_2d_to_vector_3d(region, rv3d, mouse)
        _hit, _n, index, _d = BVHTree.FromBMesh(bm).ray_cast(origin, direction, 10000.0)
        if index is not None:
            bm.faces.ensure_lookup_table()
            if 0 <= index < len(bm.faces):
                return ("face", bm.faces[index])
    if best_vert is not None:
        return ("vert", best_vert)
    if best_edge is not None:
        return ("edge", best_edge)
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
        # Double/triple on a group/component: enter edit context
        groups.set_entity(context, None)
        groups.push_context(context, container)
        return "enter"
    if count == 1:
        groups.set_entity(context, None)
    hit = pick_mesh(context, bm, mouse)
    if count <= 1:
        select_entity(bm, hit, extend=extend)
        return "single"
    if count == 2:
        select_related(bm, hit, extend=extend)
        return "double"
    select_connected(bm, hit, extend=extend)
    return "triple"
