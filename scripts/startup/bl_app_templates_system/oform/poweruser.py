# SPDX-FileCopyrightText: 2026 O-Form Authors
#
# SPDX-License-Identifier: GPL-2.0-or-later

"""SketchUp power-user workflows: arrays, hide stack, paste-in-place, face styles.

Grounded in SketchUp QRC 2024, Measurements Box docs, Reddit r/Sketchup
shortcut threads, and SketchUp Training Series (Copies and Arrays).
"""

from __future__ import annotations

from mathutils import Matrix, Vector

# Last successful copy transform — enables Nx / N/ arrays while still in Move/Rotate.
_LAST_ARRAY = None
# Last Push/Pull distance for double-click repeat.
_LAST_PUSH_PULL = 0.0
# Hide stack for Unhide Last (Reddit power-user staple).
_HIDE_STACK = []
# Clipboard for Paste in Place (world matrix + mesh data name or object).
_CLIPBOARD = None
# Face style: shaded | xray | wire | mono
_FACE_STYLE = "shaded"
# Camera history for Previous View
_VIEW_HISTORY = []


def remember_array(kind, **payload):
    """Store a completed copy so the user can type 3x or 3/ (SketchUp VCB)."""
    global _LAST_ARRAY
    _LAST_ARRAY = {"kind": kind, **payload}


def clear_array():
    global _LAST_ARRAY
    _LAST_ARRAY = None


def last_array():
    return _LAST_ARRAY


def set_last_push_pull(distance):
    global _LAST_PUSH_PULL
    _LAST_PUSH_PULL = float(distance)


def last_push_pull():
    return _LAST_PUSH_PULL


def parse_array_token(buf):
    """
    Parse SketchUp array VCB tokens.

    External: ``3x`` or ``3*`` — N copies at the same spacing as the first copy.
    Internal: ``3/`` — N total copies subdivided between original and first copy.
    Returns (count, mode) where mode is 'external' | 'internal', or None.
    """
    text = (buf or "").strip().lower().replace(" ", "")
    if len(text) < 2:
        return None
    suffix = text[-1]
    if suffix not in {"x", "*", "/"}:
        return None
    raw = text[:-1]
    try:
        count = int(float(raw))
    except ValueError:
        return None
    if count < 2:
        return None
    mode = "internal" if suffix == "/" else "external"
    return count, mode


def apply_move_array(context, count, mode):
    """Instantiate remaining copies after the first Ctrl-Move copy.

    SketchUp semantics (Training Series / Measurements Box):
    - ``Nx`` external: N total copies at spacing Δ (first copy already placed).
    - ``N/`` internal: N total copies subdivided between original and first copy.
    """
    import bpy

    state = _LAST_ARRAY
    if state is None or state.get("kind") != "move":
        return False, "Make a Ctrl-Move copy first, then type e.g. 5x or 3/"
    delta = Vector(state["delta"])
    if delta.length < 1e-12:
        return False, "Array spacing is zero"

    entity = state.get("entity")
    src_name = entity if isinstance(entity, str) else getattr(entity, "name", None)
    src = context.scene.objects.get(src_name) if src_name else None
    if src is None:
        return False, "Array source object missing"

    base = Matrix(state.get("base_matrix", src.matrix_world.copy()))
    for old in list(state.get("extra_names", [])):
        obj = context.scene.objects.get(old)
        if obj is not None:
            bpy.data.objects.remove(obj, do_unlink=True)

    first = context.scene.objects.get(state.get("first_copy") or "")
    extras = []
    unique = state.get("unique_mesh", True)

    def _spawn(offset):
        clone = src.copy()
        clone.data = src.data.copy() if unique else src.data
        context.scene.collection.objects.link(clone)
        clone.matrix_world = base.copy()
        clone.matrix_world.translation = base.translation + offset
        extras.append(clone.name)
        return clone

    if mode == "external":
        # Copies at 1Δ…NΔ; first copy already at 1Δ — add 2…N.
        if first is not None:
            first.matrix_world = base.copy()
            first.matrix_world.translation = base.translation + delta
        for step in range(2, count + 1):
            _spawn(delta * step)
    else:
        if count < 3:
            return False, "Internal array needs at least 3 (e.g. 3/)"
        step = delta / float(count - 1)
        if first is not None:
            first.matrix_world = base.copy()
            first.matrix_world.translation = base.translation + delta
        for i in range(1, count - 1):
            _spawn(step * i)

    remember_array(
        "move",
        delta=delta,
        entity=src.name,
        base_matrix=base,
        first_copy=state.get("first_copy"),
        unique_mesh=unique,
        extra_names=extras,
    )
    return True, "Array {} {}".format(count, "×" if mode == "external" else "/")


def apply_rotate_array(context, count, mode):
    import bpy

    state = _LAST_ARRAY
    if state is None or state.get("kind") != "rotate":
        return False, "Make a Ctrl-Rotate copy first, then type e.g. 8x or 6/"
    angle = float(state["angle"])
    center = Vector(state["center"])
    axis = Vector(state["axis"])
    entity = state.get("entity")
    src_name = entity if isinstance(entity, str) else getattr(entity, "name", None)
    src = context.scene.objects.get(src_name) if src_name else None
    if src is None:
        return False, "Array source object missing"
    base = Matrix(state.get("base_matrix", src.matrix_world.copy()))
    for old in list(state.get("extra_names", [])):
        obj = context.scene.objects.get(old)
        if obj is not None:
            bpy.data.objects.remove(obj, do_unlink=True)
    first = context.scene.objects.get(state.get("first_copy") or "")
    unique = state.get("unique_mesh", True)
    extras = []

    def _spawn(i):
        rot = Matrix.Rotation(angle * i if mode == "external" else (angle / float(count - 1)) * i, 4, axis)
        clone = src.copy()
        clone.data = src.data.copy() if unique else src.data
        context.scene.collection.objects.link(clone)
        pivot = Matrix.Translation(center) @ rot @ Matrix.Translation(-center)
        clone.matrix_world = pivot @ base
        extras.append(clone.name)

    if mode == "external":
        if first is not None:
            rot1 = Matrix.Rotation(angle, 4, axis)
            first.matrix_world = (Matrix.Translation(center) @ rot1 @ Matrix.Translation(-center)) @ base
        for i in range(2, count + 1):
            _spawn(i)
    else:
        if count < 3:
            return False, "Internal array needs at least 3 (e.g. 3/)"
        if first is not None:
            rot1 = Matrix.Rotation(angle, 4, axis)
            first.matrix_world = (Matrix.Translation(center) @ rot1 @ Matrix.Translation(-center)) @ base
        for i in range(1, count - 1):
            _spawn(i)

    remember_array(
        "rotate",
        angle=angle,
        center=center,
        axis=axis,
        entity=src.name,
        base_matrix=base,
        unique_mesh=unique,
        extra_names=extras,
        first_copy=state.get("first_copy"),
    )
    return True, "Rotate array {} {}".format(count, "×" if mode == "external" else "/")


def hide_selected_objects(context):
    """Hide selected objects; push onto unhide stack."""
    hidden = []
    for obj in list(context.selected_objects):
        if obj.hide_get():
            continue
        obj.hide_set(True)
        hidden.append(obj.name)
    if not hidden:
        # Hide selected mesh geometry in edit mode.
        import bmesh
        import groups

        obj = groups.context_object(context)
        if obj is not None and obj.mode == "EDIT" and obj.type == "MESH":
            bm = bmesh.from_edit_mesh(obj.data)
            faces = [f for f in bm.faces if f.select]
            edges = [e for e in bm.edges if e.select]
            verts = [v for v in bm.verts if v.select]
            for f in faces:
                f.hide = True
            for e in edges:
                e.hide = True
            for v in verts:
                v.hide = True
            bmesh.update_edit_mesh(obj.data)
            if faces or edges or verts:
                _HIDE_STACK.append(("geom", obj.name))
                return True, "Hidden selection"
        return False, "Nothing to hide"
    _HIDE_STACK.append(("objects", hidden))
    return True, "Hidden {}".format(len(hidden))


def unhide_last(context):
    if not _HIDE_STACK:
        return False, "Nothing to unhide"
    kind, payload = _HIDE_STACK.pop()
    if kind == "objects":
        for name in payload:
            obj = context.scene.objects.get(name)
            if obj is not None:
                obj.hide_set(False)
        return True, "Unhid last"
    if kind == "geom":
        import bmesh

        obj = context.scene.objects.get(payload)
        if obj is None or obj.type != "MESH":
            return False, "Hidden mesh missing"
        mode = obj.mode
        import bpy

        if mode != "EDIT":
            bpy.context.view_layer.objects.active = obj
            bpy.ops.object.mode_set(mode="EDIT")
        bm = bmesh.from_edit_mesh(obj.data)
        for f in bm.faces:
            f.hide = False
        for e in bm.edges:
            e.hide = False
        for v in bm.verts:
            v.hide = False
        bmesh.update_edit_mesh(obj.data)
        return True, "Unhid geometry"
    return False, "Unknown hide entry"


def unhide_all(context):
    count = 0
    for obj in context.scene.objects:
        if obj.hide_get():
            obj.hide_set(False)
            count += 1
    import bmesh

    for obj in context.scene.objects:
        if obj.type != "MESH":
            continue
        bm = bmesh.new()
        bm.from_mesh(obj.data)
        changed = False
        for f in bm.faces:
            if f.hide:
                f.hide = False
                changed = True
        for e in bm.edges:
            if e.hide:
                e.hide = False
                changed = True
        for v in bm.verts:
            if v.hide:
                v.hide = False
                changed = True
        if changed:
            bm.to_mesh(obj.data)
            count += 1
        bm.free()
    _HIDE_STACK.clear()
    return True, "Unhid all ({})".format(count)


def hide_rest_of_model(context):
    """While editing a group/component, hide everything else (Reddit: X / Ctrl+H)."""
    import groups

    active = groups.context_object(context)
    if active is None:
        return False, "No edit context"
    hidden = []
    for obj in context.scene.objects:
        if obj == active:
            continue
        if obj.hide_get():
            continue
        obj.hide_set(True)
        hidden.append(obj.name)
    if hidden:
        _HIDE_STACK.append(("objects", hidden))
    return True, "Hid rest of model ({} objects)".format(len(hidden))


def copy_selection(context):
    """Store selected object(s) for Paste in Place."""
    global _CLIPBOARD
    import groups

    selected = [obj for obj in context.selected_objects if obj.type == "MESH"]
    if not selected:
        entity = groups.get_entity(context)
        if entity is not None:
            selected = [entity]
    if not selected:
        return False, "Select a group, component, or mesh to copy"
    entries = []
    for obj in selected:
        share = groups.kind_of(obj) == "component"
        entries.append(
            {
                "name": obj.name,
                "matrix": obj.matrix_world.copy(),
                "mesh": obj.data if share else (obj.data.copy() if obj.data else None),
                "share": share,
            }
        )
    _CLIPBOARD = entries
    return True, "Copied {}".format(len(entries))


def paste_in_place(context):
    """Paste clipboard objects at their original world matrices (Shift+V workflow)."""
    import bpy
    import groups

    if not _CLIPBOARD:
        return False, "Clipboard empty — Copy first"
    created = []
    for entry in _CLIPBOARD:
        mesh = entry["mesh"]
        if mesh is None:
            continue
        if entry.get("share"):
            data = mesh
        else:
            data = mesh.copy() if hasattr(mesh, "copy") else mesh
        obj = bpy.data.objects.new(entry["name"] + "_copy", data)
        context.scene.collection.objects.link(obj)
        obj.matrix_world = entry["matrix"].copy()
        created.append(obj)
    for obj in context.selected_objects:
        obj.select_set(False)
    for obj in created:
        obj.select_set(True)
    if created:
        context.view_layer.objects.active = created[-1]
    return True, "Pasted in place ({})".format(len(created))


def face_style(context, style=None):
    """Toggle SketchUp-like face styles: shaded, xray, wire, mono."""
    global _FACE_STYLE
    if style is None:
        order = ("shaded", "xray", "wire", "mono")
        style = order[(order.index(_FACE_STYLE) + 1) % len(order)] if _FACE_STYLE in order else "shaded"
    _FACE_STYLE = style
    screen = context.screen
    if screen is None:
        return style
    for area in screen.areas:
        if area.type != "VIEW_3D":
            continue
        space = area.spaces.active
        shading = space.shading
        if style == "shaded":
            shading.type = "SOLID"
            try:
                shading.light = "FLAT"
            except (TypeError, AttributeError):
                pass
            try:
                shading.color_type = "MATERIAL"
            except (TypeError, AttributeError):
                pass
            if hasattr(shading, "show_xray"):
                shading.show_xray = False
        elif style == "xray":
            shading.type = "SOLID"
            if hasattr(shading, "show_xray"):
                shading.show_xray = True
            try:
                shading.color_type = "MATERIAL"
            except (TypeError, AttributeError):
                pass
        elif style == "wire":
            shading.type = "WIREFRAME"
        elif style == "mono":
            shading.type = "SOLID"
            if hasattr(shading, "show_xray"):
                shading.show_xray = False
            try:
                shading.color_type = "SINGLE"
            except (TypeError, AttributeError):
                pass
        area.tag_redraw()
    return style


def push_view(context):
    """Snapshot camera for Previous View."""
    for area in context.screen.areas if context.screen else []:
        if area.type != "VIEW_3D":
            continue
        rv3d = area.spaces.active.region_3d
        _VIEW_HISTORY.append(
            {
                "view_matrix": rv3d.view_matrix.copy(),
                "view_distance": rv3d.view_distance,
                "view_location": rv3d.view_location.copy(),
                "view_rotation": rv3d.view_rotation.copy(),
                "perspective": rv3d.view_perspective,
            }
        )
        if len(_VIEW_HISTORY) > 32:
            _VIEW_HISTORY.pop(0)
        return


def previous_view(context):
    if not _VIEW_HISTORY:
        return False, "No previous view"
    snap = _VIEW_HISTORY.pop()
    for area in context.screen.areas:
        if area.type != "VIEW_3D":
            continue
        rv3d = area.spaces.active.region_3d
        rv3d.view_matrix = snap["view_matrix"]
        rv3d.view_distance = snap["view_distance"]
        rv3d.view_location = snap["view_location"]
        rv3d.view_rotation = snap["view_rotation"]
        rv3d.view_perspective = snap["perspective"]
        return True, "Previous view"
    return False, "No 3D view"
