# SPDX-FileCopyrightText: 2026 O-Form Authors
#
# SPDX-License-Identifier: GPL-2.0-or-later

"""SketchUp-style tools. Action operators record undo. Modal tools stay active."""

import math
import os
import sys
import time

import bmesh
import bpy
from bpy.props import (
    BoolProperty,
    EnumProperty,
    FloatProperty,
    FloatVectorProperty,
    IntProperty,
    StringProperty,
)
from bpy.types import Operator
from mathutils import Matrix, Vector

_HERE = os.path.dirname(os.path.abspath(__file__))
if _HERE not in sys.path:
    sys.path.insert(0, _HERE)

import geom
import groups
import inference
import poweruser
import selection
import solids
import units

preview_strokes = []  # list of polylines in model/local space
preview_guides = []  # inference guide segments [[a, b], ...]
preview_label = ""
preview_label_pos = None  # region 2D (x, y) for POST_PIXEL snap tip
preview_snap_co = None  # local-space snap point for marker overlay
_PREVIEW_HANDLE = None
_LABEL_HANDLE = None

# SketchUp-aligned defaults: https://help.sketchup.com/en/default-keyboard-shortcuts
TOOL_KEYS = {
    "SPACE": "tool_select",
    "E": "tool_eraser",
    "B": "tool_paint",
    "L": "tool_line",
    "A": "tool_arc",
    "R": "tool_rectangle",
    "C": "tool_circle",
    "P": "tool_push_pull",
    "F": "tool_offset",
    "M": "tool_move",
    "Q": "tool_rotate",
    "S": "tool_scale",
    "T": "tool_tape",
    "N": "tool_polygon",
    "J": "tool_follow_me",
    "X": "tool_protractor",
    "K": "tool_back_edges",
    "G": "make_component",
    "O": "tool_orbit",
    "H": "tool_pan",
    "Z": "tool_zoom",
}

# Shift+letter tools (Shift+Z remains Zoom Extents).
SHIFT_TOOL_KEYS = {
    "L": "tool_freehand",
    "Z": "tool_zoom_extents",
}

ARROWS = {
    "RIGHT_ARROW": "X",
    "LEFT_ARROW": "Y",
    "UP_ARROW": "Z",
    "DOWN_ARROW": "PARALLEL",
}

COLORS = (
    (0.776, 0.902, 0.827),
    (0.95, 0.95, 0.95),
    (0.80, 0.20, 0.15),
    (0.20, 0.55, 0.25),
    (0.20, 0.35, 0.75),
    (0.90, 0.75, 0.15),
    (0.85, 0.45, 0.10),
    (0.45, 0.28, 0.14),
)


def set_preview(points):
    """Rubber-band polyline in model space (drawn live while a tool is active)."""
    global preview_strokes
    if not points:
        preview_strokes = []
    else:
        preview_strokes = [[Vector(p) for p in points]]
    _tag_preview_redraw()


def set_preview_strokes(strokes):
    """Several rubber-band polylines (e.g. Push/Pull top + verticals)."""
    global preview_strokes
    preview_strokes = [[Vector(p) for p in stroke] for stroke in strokes if stroke]
    _tag_preview_redraw()


def set_inference_feedback(snap):
    """Store snap label + guide lines for the viewport overlay."""
    global preview_guides, preview_label, preview_label_pos, preview_snap_co
    if snap is None:
        preview_guides = []
        preview_label = ""
        preview_label_pos = None
        preview_snap_co = None
    else:
        preview_guides = [[Vector(a), Vector(b)] for a, b in (snap.guides or [])]
        preview_label = snap.label or ""
        preview_label_pos = None
        preview_snap_co = Vector(snap.co) if getattr(snap, "co", None) is not None else None
        if preview_snap_co is not None:
            try:
                screen = inference._screen(bpy.context, preview_snap_co)
                if screen is not None:
                    preview_label_pos = (float(screen.x) + 14.0, float(screen.y) + 14.0)
            except Exception:
                preview_label_pos = None
    _tag_preview_redraw()


def _tag_preview_redraw():
    screen = getattr(bpy.context, "screen", None)
    if screen is None:
        return
    for area in screen.areas:
        if area.type == "VIEW_3D":
            area.tag_redraw()


def _preview_world_strokes():
    """Transform preview strokes from the edit-context object into world space."""
    if not preview_strokes:
        return []
    obj = groups.context_object(bpy.context)
    mat = obj.matrix_world if obj is not None else None
    out = []
    for stroke in preview_strokes:
        if mat is None:
            out.append([tuple(p) for p in stroke])
        else:
            out.append([tuple(mat @ p) for p in stroke])
    return out


def _world_seg(seg):
    obj = groups.context_object(bpy.context)
    mat = obj.matrix_world if obj is not None else None
    if mat is None:
        return [tuple(seg[0]), tuple(seg[1])]
    return [tuple(mat @ seg[0]), tuple(mat @ seg[1])]


def _draw_tool_preview():
    """POST_VIEW: live geometry preview + inference guides."""
    strokes = _preview_world_strokes()
    try:
        import gpu
        from gpu_extras.batch import batch_for_shader
    except ImportError:
        return
    shader = gpu.shader.from_builtin("UNIFORM_COLOR")
    gpu.state.depth_test_set("NONE")
    gpu.state.blend_set("ALPHA")
    gpu.state.line_width_set(2.0)
    shader.bind()
    markers = []
    if strokes:
        # SketchUp-like inference green on the rubber band.
        shader.uniform_float("color", (0.15, 0.72, 0.35, 0.95))
        for coords in strokes:
            if len(coords) < 2:
                continue
            batch_for_shader(shader, "LINE_STRIP", {"pos": coords}).draw(shader)
            markers.append(coords[0])
            markers.append(coords[-1])
    # Inference guides (axis / from-point) — RGB like SketchUp axes.
    for seg in preview_guides:
        if len(seg) < 2:
            continue
        a, b = _world_seg(seg)
        delta = Vector(b) - Vector(a)
        if abs(delta.x) >= abs(delta.y) and abs(delta.x) >= abs(delta.z):
            color = (0.9, 0.15, 0.15, 0.9)
        elif abs(delta.y) >= abs(delta.z):
            color = (0.15, 0.75, 0.2, 0.9)
        else:
            color = (0.2, 0.35, 0.95, 0.9)
        shader.uniform_float("color", color)
        batch_for_shader(shader, "LINES", {"pos": [a, b]}).draw(shader)
    # Live snap point (endpoint / midpoint / on-edge / on-face).
    if preview_snap_co is not None:
        obj = groups.context_object(bpy.context)
        mat = obj.matrix_world if obj is not None else None
        pt = tuple(mat @ preview_snap_co) if mat is not None else tuple(preview_snap_co)
        markers.append(pt)
    if markers:
        if hasattr(gpu.state, "point_size_set"):
            gpu.state.point_size_set(8.0)
        shader.uniform_float("color", (0.12, 0.72, 0.32, 1.0))
        batch_for_shader(shader, "POINTS", {"pos": markers}).draw(shader)
        if hasattr(gpu.state, "point_size_set"):
            gpu.state.point_size_set(1.0)
    gpu.state.line_width_set(1.0)
    gpu.state.blend_set("NONE")
    gpu.state.depth_test_set("LESS_EQUAL")


def _draw_snap_label():
    """POST_PIXEL: SketchUp-style snap tip next to the inferred point."""
    if not preview_label:
        return
    try:
        import blf
    except ImportError:
        return
    context = bpy.context
    if context.area is None or context.area.type != "VIEW_3D":
        return
    region = context.region
    if region is None or region.type != "WINDOW":
        return
    x, y = preview_label_pos if preview_label_pos is not None else (24.0, region.height - 36.0)
    x = max(8.0, min(x, region.width - 120.0))
    y = max(8.0, min(y, region.height - 20.0))
    font_id = 0
    blf.size(font_id, 12)
    # Soft shadow for contrast on both light and dark paper.
    blf.color(font_id, 0.0, 0.0, 0.0, 0.55)
    blf.position(font_id, x + 1.0, y - 1.0, 0)
    blf.draw(font_id, preview_label[:40])
    blf.color(font_id, 0.12, 0.55, 0.28, 1.0)
    blf.position(font_id, x, y, 0)
    blf.draw(font_id, preview_label[:40])


def _prop(scene, name, value=None):
    if not hasattr(scene, name):
        return None
    if value is None:
        return getattr(scene, name)
    setattr(scene, name, value)
    return value


def _status(context, text):
    _prop(context.scene, "oform_status", text)
    _redraw(context)


def _measure(context, text):
    _prop(context.scene, "oform_measure", text)
    _redraw(context)


def _tool(context, idname):
    _prop(context.scene, "oform_tool", idname)


def _redraw(context):
    screen = getattr(context, "screen", None)
    if screen is None:
        return
    for area in screen.areas:
        if area.type in {"VIEW_3D", "STATUSBAR"}:
            area.tag_redraw()


def _ensure_model(context):
    """Ensure the root Model exists and activate the current edit context."""
    groups.ensure_root(context)
    obj = groups.context_object(context)
    groups.set_context(context, obj)
    return obj


def _edit(context):
    obj = _ensure_model(context)
    bm = bmesh.from_edit_mesh(obj.data)
    return obj, bm


def _commit(obj):
    bmesh.update_edit_mesh(obj.data)


def _do(op, **kwargs):
    # bpy.ops from Python skips the undo step unless this flag is set.
    return op(True, **kwargs)


def _parse_length(text, context=None):
    """Parse a VCB length into metres. Accepts ', \", mm, m, cm, ft, in, 5'6\"."""
    scene = None
    if context is not None:
        scene = getattr(context, "scene", None)
    default = units.current_unit(scene)
    return units.parse_length(text, default_unit=default)


def _fmt_length(meters, context=None):
    scene = getattr(context, "scene", None) if context is not None else None
    return units.format_length(meters, scene=scene)


def _view3d(context):
    window = context.window
    screen = context.screen
    if screen is None:
        return None
    for area in screen.areas:
        if area.type != "VIEW_3D":
            continue
        region = next((r for r in area.regions if r.type == "WINDOW"), None)
        if region is not None:
            return {"window": window, "screen": screen, "area": area, "region": region}
    return None


def _later(tool_name):
    def run():
        op = getattr(bpy.ops.oform, tool_name, None)
        if op is None:
            return None
        context = bpy.context
        override = _view3d(context)
        try:
            if override is not None:
                with context.temp_override(**override):
                    op("INVOKE_DEFAULT")
            else:
                op("INVOKE_DEFAULT")
        except RuntimeError:
            pass
        return None

    bpy.app.timers.register(run, first_interval=0.01)


class _Tool:
    """Shared modal bookkeeping. Operators also subclass bpy.types.Operator."""

    def _arm(self, context, status):
        _tool(context, self.bl_idname)
        self._axis = None
        self._parallel = None
        self._buf = ""
        self._anchor = None
        self._points = []
        self._plane = None  # inference.WorkingPlane after first click on a face
        self._last_snap = None
        _status(context, status)
        _measure(context, "")
        set_preview([])
        set_inference_feedback(None)
        # mode_set has to finish before the modal handler exists. Calling it
        # from a modal event runs inside the handler and skips the undo step.
        _edit(context)
        context.window_manager.modal_handler_add(self)
        return {"RUNNING_MODAL"}

    def _adopt_plane(self, snap, bm=None):
        """Lock the working plane from the first drawing point (SketchUp-style)."""
        if self._plane is None and snap is not None:
            self._plane = inference.establish_plane(bm, snap, inference.ground_plane())

    def _start(self, context, status):
        """Begin a modal tool in the 3D view (sidebar / keymap safe)."""
        if context.area is not None and context.area.type == "VIEW_3D":
            return self._arm(context, status)
        override = _view3d(context)
        if override is None:
            self.report({"WARNING"}, "No 3D View to draw in")
            return {"CANCELLED"}
        with context.temp_override(**override):
            return self._arm(context, status)

    def _event(self, context, event):
        # Clicks / moves outside the 3D view must reach the status bar, menus,
        # and side toolbars (theme toggle, units, BIM strip, etc.).
        if event.type in {
            "LEFTMOUSE",
            "RIGHTMOUSE",
            "MOUSEMOVE",
            "INBETWEEN_MOUSEMOVE",
        }:
            region = context.region
            if region is not None:
                x, y = event.mouse_region_x, event.mouse_region_y
                if x < 0 or y < 0 or x >= region.width or y >= region.height:
                    return {"PASS_THROUGH"}
        # Orbit, pan, and zoom stay on the middle mouse and the wheel.
        # Ctrl+Z / Ctrl+S stay undo and save. The modal must not swallow them.
        if event.type in {
            "MIDDLEMOUSE",
            "WHEELUPMOUSE",
            "WHEELDOWNMOUSE",
            "WHEELINMOUSE",
            "WHEELOUTMOUSE",
            "TRACKPADPAN",
            "TRACKPADZOOM",
        }:
            return {"PASS_THROUGH"}
        if event.ctrl and not event.alt and event.type in {"Z", "S"} and event.value == "PRESS":
            return {"PASS_THROUGH"}
        if event.ctrl and not event.alt and not event.shift and event.type == "G" and event.value == "PRESS":
            try:
                bpy.ops.oform.make_group()
            except RuntimeError:
                pass
            return {"RUNNING_MODAL"}
        if event.type == "ESC" and event.value == "PRESS":
            return self._cancel_command(context)
        if event.type == "RIGHTMOUSE" and event.value == "PRESS":
            # Right-click opens the BIM menu (map selection → IFC). Esc cancels.
            had_state = (
                bool(getattr(self, "_points", None))
                or self._anchor is not None
                or bool(self._buf)
            )
            if had_state:
                if getattr(self, "_points", None) is not None:
                    self._points.clear()
                self._anchor = None
                self._buf = ""
                self._plane = None
                self._axis = None
                set_preview([])
                _measure(context, "")
            try:
                bpy.ops.wm.call_menu(name="OFORM_MT_bim_context")
            except RuntimeError:
                try:
                    bpy.ops.oform.bim_context_menu("INVOKE_DEFAULT")
                except RuntimeError:
                    pass
            return {"RUNNING_MODAL"}
        if event.value == "PRESS" and not event.ctrl and not event.alt:
            if event.shift:
                name = SHIFT_TOOL_KEYS.get(event.type)
                if name:
                    if "oform." + name != self.bl_idname:
                        _later(name)
                        set_preview([])
                        return {"FINISHED"}
                    return {"RUNNING_MODAL"}
            name = TOOL_KEYS.get(event.type)
            if name and not event.shift:
                # Non-modal group commands run immediately.
                if name in {"make_component", "make_group", "explode", "enter_group", "exit_group"}:
                    op = getattr(bpy.ops.oform, name, None)
                    if op is not None:
                        try:
                            op()
                        except RuntimeError:
                            pass
                    return {"RUNNING_MODAL"}
                if "oform." + name != self.bl_idname:
                    _later(name)
                    set_preview([])
                    return {"FINISHED"}
                return {"RUNNING_MODAL"}
            if event.type in ARROWS:
                chosen = ARROWS[event.type]
                if chosen == "PARALLEL":
                    self._axis = None if self._axis == "PARALLEL" else "PARALLEL"
                else:
                    self._axis = None if self._axis == chosen else chosen
                label = inference.axis_label(self._axis)
                if label:
                    _status(context, self._idle_status() + "  " + label)
                return {"RUNNING_MODAL"}
        if event.value == "PRESS" and event.type == "BACK_SPACE":
            self._buf = self._buf[:-1]
            _measure(context, self._buf)
            return {"RUNNING_MODAL"}
        if event.value == "PRESS" and event.type in {"DEL", "DELETE"}:
            # While typing a length, Del edits the buffer; otherwise delete selection.
            if self._buf:
                self._buf = self._buf[:-1]
                _measure(context, self._buf)
                return {"RUNNING_MODAL"}
            had_draw = bool(getattr(self, "_points", None)) or self._anchor is not None
            if had_draw:
                if getattr(self, "_points", None) is not None:
                    self._points.clear()
                self._anchor = None
                self._plane = None
                set_preview([])
                set_inference_feedback(None)
                _measure(context, "")
                _status(context, self._idle_status())
                return {"RUNNING_MODAL"}
            try:
                _do(bpy.ops.oform.delete_selection)
            except RuntimeError:
                pass
            return {"RUNNING_MODAL"}
        # Shift locks the current inference (SketchUp QRC: hold Shift to lock).
        if event.type in {"LEFT_SHIFT", "RIGHT_SHIFT"} and event.value == "PRESS":
            snap = self._last_snap
            if snap is not None and getattr(snap, "tangent", None) is not None:
                self._parallel = snap.tangent.copy()
                self._axis = "PARALLEL"
                _status(context, "Inference locked · " + (snap.label or "Parallel"))
                return {"RUNNING_MODAL"}
            if snap is not None and self._anchor is not None:
                delta = snap.co - self._anchor
                if delta.length > 1e-8:
                    if abs(delta.x) >= abs(delta.y) and abs(delta.x) >= abs(delta.z):
                        self._axis = "X"
                    elif abs(delta.y) >= abs(delta.z):
                        self._axis = "Y"
                    else:
                        self._axis = "Z"
                    _status(context, "Inference locked · " + inference.axis_label(self._axis))
                    return {"RUNNING_MODAL"}
        # VCB: digits, units (' " mm m cm ft in), array suffixes x * /, segments s.
        if event.value == "PRESS" and event.unicode and event.unicode in units.VCB_CHARS:
            self._buf += event.unicode
            _measure(context, self._buf)
            return {"RUNNING_MODAL"}
        if event.value == "PRESS" and event.type in {"RET", "NUMPAD_ENTER"}:
            token = poweruser.parse_array_token(self._buf)
            if token is not None:
                count, mode = token
                if poweruser.last_array() and poweruser.last_array().get("kind") == "rotate":
                    ok, message = poweruser.apply_rotate_array(context, count, mode)
                else:
                    ok, message = poweruser.apply_move_array(context, count, mode)
                self._buf = ""
                _measure(context, "")
                _status(context, message)
                if not ok:
                    self.report({"WARNING"}, message)
                return {"RUNNING_MODAL"}
            # O-Draft slash transfer: "/…" alone (no trailing digit pattern) → Ask.
            stripped = self._buf.strip()
            if stripped.startswith("/") and not poweruser.parse_array_token("2" + stripped):
                import ai as ask

                text = stripped[1:].strip() or stripped
                context.scene.oform_ask = text
                ask.propose(context, text)
                self._buf = ""
                _measure(context, "")
                _status(context, context.scene.get("oform_status", "Ask"))
                return {"RUNNING_MODAL"}
            return {"APPLY"}
        return None

    def _idle_status(self):
        return "Choose a point"

    def _cancel_command(self, context):
        """Esc: cancel in-progress command, then leave the tool.

        SketchUp ladder:
        1. Mid-command state (points, VCB, plane) → clear it, stay on tool
        2. Entity selection → clear it
        3. Inside a group/component → exit one level
        4. Non-Select tool → exit modal and return to Select
        5. Already Select with nothing pending → stay idle

        Right-click opens the BIM context menu (see ``_event``).
        """
        had_state = (
            bool(getattr(self, "_points", None))
            or self._anchor is not None
            or bool(self._buf)
            or getattr(self, "_plane", None) is not None
        )
        if getattr(self, "_points", None) is not None:
            self._points.clear()
        self._anchor = None
        self._buf = ""
        self._plane = None
        self._axis = None
        self._parallel = None
        self._last_snap = None
        if hasattr(self, "_segments"):
            self._segments = 0
        if hasattr(self, "_clicks") and self._clicks is not None:
            try:
                self._clicks.reset()
            except Exception:
                pass
        set_preview([])
        set_inference_feedback(None)
        _measure(context, "")

        if had_state:
            _status(context, "Cancelled · " + self._idle_status())
            return {"RUNNING_MODAL"}

        if groups.get_entity(context) is not None:
            groups.set_entity(context, None)
            _status(context, "Selection cleared")
            return {"RUNNING_MODAL"}

        if groups.context_depth(context) > 0:
            groups.pop_context(context)
            _status(context, "Closed " + groups.context_object(context).name)
            return {"RUNNING_MODAL"}

        # No pending command — leave the active tool for Select.
        if self.bl_idname != "oform.tool_select":
            set_preview([])
            _status(context, "Cancelled")
            _later("tool_select")
            return {"FINISHED"}

        _status(context, self._idle_status())
        return {"RUNNING_MODAL"}


def _mouse(event):
    return event.mouse_region_x, event.mouse_region_y


# ---------------------------------------------------------------------------
# Actions. These are what the headless test and the modal tools both call.
# ---------------------------------------------------------------------------


class OFORM_OT_rectangle(Operator):
    bl_idname = "oform.rectangle"
    bl_label = "Rectangle"
    bl_options = {"UNDO"}

    corner_a: FloatVectorProperty(size=3)
    corner_b: FloatVectorProperty(size=3)
    normal: FloatVectorProperty(size=3, default=(0.0, 0.0, 1.0))

    def execute(self, context):
        _obj, bm = _edit(context)
        corners = geom.rectangle_corners(self.corner_a, self.corner_b, self.normal)
        geom.add_polygon(bm, corners)
        _commit(_obj)
        return {"FINISHED"}


class OFORM_OT_line_add(Operator):
    bl_idname = "oform.line_add"
    bl_label = "Line"
    bl_options = {"UNDO"}

    a: FloatVectorProperty(size=3)
    b: FloatVectorProperty(size=3)

    def execute(self, context):
        _obj, bm = _edit(context)
        geom.add_segment(bm, self.a, self.b)
        _commit(_obj)
        return {"FINISHED"}


class OFORM_OT_circle(Operator):
    bl_idname = "oform.circle"
    bl_label = "Circle"
    bl_options = {"UNDO"}

    center: FloatVectorProperty(size=3)
    radius: FloatProperty(default=1.0)
    normal: FloatVectorProperty(size=3, default=(0.0, 0.0, 1.0))
    segments: IntProperty(default=24, min=3, max=256)

    def execute(self, context):
        if self.radius <= 1e-8:
            return {"CANCELLED"}
        _obj, bm = _edit(context)
        pts = geom.circle_points(self.center, self.radius, self.normal, self.segments)
        geom.add_polygon(bm, pts)
        _commit(_obj)
        return {"FINISHED"}


class OFORM_OT_arc(Operator):
    bl_idname = "oform.arc"
    bl_label = "Arc"
    bl_options = {"UNDO"}

    start: FloatVectorProperty(size=3)
    end: FloatVectorProperty(size=3)
    bulge: FloatVectorProperty(size=3)
    segments: IntProperty(default=12, min=2, max=128)

    def execute(self, context):
        _obj, bm = _edit(context)
        pts = geom.arc_points(self.start, self.end, self.bulge, self.segments)
        if len(pts) >= 2:
            for p0, p1 in zip(pts, pts[1:]):
                geom.add_segment(bm, p0, p1)
        _commit(_obj)
        return {"FINISHED"}


class OFORM_OT_push_pull(Operator):
    bl_idname = "oform.push_pull"
    bl_label = "Push/Pull"
    bl_options = {"UNDO"}

    distance: FloatProperty(default=0.0)
    face_index: IntProperty(default=-1)
    copy: BoolProperty(default=False)

    def execute(self, context):
        _obj, bm = _edit(context)
        face = geom.selected_face(bm, self.face_index)
        if face is None:
            self.report({"WARNING"}, "Select a face to push/pull")
            return {"CANCELLED"}
        try:
            result = geom.push_pull(bm, face, self.distance, copy=self.copy)
        except Exception as exc:
            self.report({"ERROR"}, "Push/Pull failed: " + str(exc))
            _status(context, "Push/Pull failed")
            return {"CANCELLED"}
        _commit(_obj)
        if result is None and abs(self.distance) > 1e-9:
            self.report({"WARNING"}, "Push/Pull could not modify that face")
            return {"CANCELLED"}
        if abs(self.distance) > 1e-9:
            poweruser.set_last_push_pull(self.distance)
        return {"FINISHED"}


class OFORM_OT_polygon(Operator):
    bl_idname = "oform.polygon"
    bl_label = "Polygon"
    bl_options = {"UNDO"}

    center: FloatVectorProperty(size=3)
    radius: FloatProperty(default=1.0)
    normal: FloatVectorProperty(size=3, default=(0.0, 0.0, 1.0))
    sides: IntProperty(default=6, min=3, max=256)

    def execute(self, context):
        if self.radius <= 1e-8:
            return {"CANCELLED"}
        _obj, bm = _edit(context)
        pts = geom.polygon_points(self.center, self.radius, self.normal, self.sides)
        geom.add_polygon(bm, pts)
        _commit(_obj)
        return {"FINISHED"}


_FREEHAND_BUF = []
_FOLLOW_PATH = []


class OFORM_OT_freehand(Operator):
    bl_idname = "oform.freehand"
    bl_label = "Freehand"
    bl_options = {"UNDO"}

    def execute(self, context):
        pts = geom.freehand_points(_FREEHAND_BUF)
        if len(pts) < 2:
            return {"CANCELLED"}
        _obj, bm = _edit(context)
        geom.add_polyline(bm, pts, close=False)
        _commit(_obj)
        return {"FINISHED"}


class OFORM_OT_tape(Operator):
    bl_idname = "oform.tape"
    bl_label = "Tape Measure"
    bl_options = {"UNDO"}

    a: FloatVectorProperty(size=3)
    b: FloatVectorProperty(size=3)
    create_guide: BoolProperty(default=False)

    def execute(self, context):
        _obj, bm = _edit(context)
        if self.create_guide:
            geom.add_guide(bm, self.a, self.b)
            _commit(_obj)
        length = (Vector(self.b) - Vector(self.a)).length
        _measure(context, _fmt_length(length, context))
        _status(context, "Distance " + _fmt_length(length, context))
        return {"FINISHED"}


class OFORM_OT_follow_me(Operator):
    bl_idname = "oform.follow_me"
    bl_label = "Follow Me"
    bl_options = {"UNDO"}

    face_index: IntProperty(default=-1)

    def execute(self, context):
        _obj, bm = _edit(context)
        face = geom.selected_face(bm, self.face_index)
        path = list(_FOLLOW_PATH)
        if not path:
            path = geom.ordered_path_coords([edge for edge in bm.edges if edge.select])
        if face is None or len(path) < 2:
            self.report({"WARNING"}, "Select a path of edges, then a profile face")
            return {"CANCELLED"}
        geom.follow_me(bm, face, path)
        _commit(_obj)
        return {"FINISHED"}


class OFORM_OT_soften(Operator):
    bl_idname = "oform.soften"
    bl_label = "Soften Edges"
    bl_options = {"UNDO"}

    edge_index: IntProperty(default=-1)
    smooth: BoolProperty(default=True)

    def execute(self, context):
        _obj, bm = _edit(context)
        bm.edges.ensure_lookup_table()
        edges = []
        if 0 <= self.edge_index < len(bm.edges):
            edges.append(bm.edges[self.edge_index])
        else:
            edges = [edge for edge in bm.edges if edge.select]
        geom.soften_edges(bm, edges, smooth=self.smooth)
        _commit(_obj)
        return {"FINISHED"}


class OFORM_OT_hide_edges(Operator):
    bl_idname = "oform.hide_edges"
    bl_label = "Hide Edges"
    bl_options = {"UNDO"}

    edge_index: IntProperty(default=-1)
    hide: BoolProperty(default=True)

    def execute(self, context):
        _obj, bm = _edit(context)
        bm.edges.ensure_lookup_table()
        edges = []
        if 0 <= self.edge_index < len(bm.edges):
            edges.append(bm.edges[self.edge_index])
        else:
            edges = [edge for edge in bm.edges if edge.select]
        geom.hide_edges(bm, edges, hide=self.hide)
        _commit(_obj)
        return {"FINISHED"}


class OFORM_OT_offset(Operator):
    bl_idname = "oform.offset"
    bl_label = "Offset"
    bl_options = {"UNDO"}

    distance: FloatProperty(default=0.0)
    face_index: IntProperty(default=-1)

    def execute(self, context):
        _obj, bm = _edit(context)
        face = geom.selected_face(bm, self.face_index)
        geom.offset_face(bm, face, self.distance)
        _commit(_obj)
        return {"FINISHED"}


class OFORM_OT_erase(Operator):
    bl_idname = "oform.erase"
    bl_label = "Erase"
    bl_options = {"UNDO"}

    edge_index: IntProperty(default=-1)

    def execute(self, context):
        _obj, bm = _edit(context)
        bm.edges.ensure_lookup_table()
        edges = []
        if 0 <= self.edge_index < len(bm.edges):
            edges.append(bm.edges[self.edge_index])
        else:
            edges = [edge for edge in bm.edges if edge.select]
        geom.erase_edges(bm, edges)
        _commit(_obj)
        return {"FINISHED"}


class OFORM_OT_delete_selection(Operator):
    bl_idname = "oform.delete_selection"
    bl_label = "Delete"
    bl_options = {"UNDO"}

    def execute(self, context):
        entity = groups.get_entity(context)
        if entity is not None and groups.is_container(entity):
            name = entity.name
            # Never delete the root Model workspace object via Delete.
            root = groups.ensure_root(context)
            if entity == root:
                self.report({"WARNING"}, "Cannot delete the root Model")
                return {"CANCELLED"}
            groups.set_entity(context, None)
            try:
                bpy.data.objects.remove(entity, do_unlink=True)
            except ReferenceError:
                return {"CANCELLED"}
            _status(context, "Deleted " + name)
            return {"FINISHED"}

        # Selected mesh objects other than the active edit context.
        selected = [
            obj
            for obj in context.selected_objects
            if obj.type == "MESH" and obj != groups.context_object(context)
        ]
        if selected and context.mode == "OBJECT":
            for obj in selected:
                if groups.is_container(obj) or obj.name != "Model":
                    try:
                        bpy.data.objects.remove(obj, do_unlink=True)
                    except ReferenceError:
                        pass
            groups.set_entity(context, None)
            _status(context, "Deleted selection")
            return {"FINISHED"}

        obj, bm = _edit(context)
        if geom.delete_selected(bm):
            _commit(obj)
            _status(context, "Deleted")
            return {"FINISHED"}
        self.report({"INFO"}, "Nothing selected to delete")
        return {"CANCELLED"}


class OFORM_OT_move(Operator):
    bl_idname = "oform.move"
    bl_label = "Move"
    bl_options = {"UNDO"}

    delta: FloatVectorProperty(size=3)
    copy: BoolProperty(default=False)

    def execute(self, context):
        entity = groups.get_entity(context)
        if entity is not None:
            delta = Vector(self.delta)
            if self.copy:
                base_matrix = entity.matrix_world.copy()
                unique = True
                if groups.kind_of(entity) == groups.KIND_COMPONENT:
                    inst = groups.instance_component(context, entity)
                    if inst is None:
                        return {"CANCELLED"}
                    inst.matrix_world.translation = entity.matrix_world.translation + delta
                    groups.set_entity(context, inst)
                    unique = False
                    first = inst
                else:
                    bpy.ops.object.mode_set(mode="OBJECT")
                    clone = entity.copy()
                    clone.data = entity.data.copy()
                    context.scene.collection.objects.link(clone)
                    groups._tag(clone, groups.KIND_GROUP)
                    clone.matrix_world = entity.matrix_world.copy()
                    clone.matrix_world.translation = entity.matrix_world.translation + delta
                    groups.set_entity(context, clone)
                    groups.set_context(context, groups.context_object(context))
                    first = clone
                poweruser.remember_array(
                    "move",
                    delta=delta,
                    entity=entity.name,
                    base_matrix=base_matrix,
                    first_copy=first.name,
                    unique_mesh=unique,
                    extra_names=[],
                )
                _status(context, "Copied — type 5x or 3/ for array, Enter")
            else:
                entity.matrix_world.translation = entity.matrix_world.translation + delta
                poweruser.clear_array()
            return {"FINISHED"}
        _obj, bm = _edit(context)
        if self.copy:
            geom.duplicate_selected(bm)
            poweruser.remember_array(
                "move",
                delta=Vector(self.delta),
                entity=None,
                base_matrix=None,
                first_copy=None,
                unique_mesh=True,
                extra_names=[],
            )
            _status(context, "Copied mesh — type 5x or 3/ for array")
        else:
            poweruser.clear_array()
        geom.translate_verts(geom.selected_verts(bm), self.delta)
        geom._ensure(bm)
        _commit(_obj)
        return {"FINISHED"}


class OFORM_OT_rotate(Operator):
    bl_idname = "oform.rotate"
    bl_label = "Rotate"
    bl_options = {"UNDO"}

    center: FloatVectorProperty(size=3)
    axis: FloatVectorProperty(size=3, default=(0.0, 0.0, 1.0))
    angle: FloatProperty(default=0.0, subtype="ANGLE")
    copy: BoolProperty(default=False)

    def execute(self, context):
        entity = groups.get_entity(context)
        center = Vector(self.center)
        axis = Vector(self.axis)
        if axis.length < 1e-8:
            axis = Vector((0.0, 0.0, 1.0))
        rot = (
            Matrix.Translation(center)
            @ Matrix.Rotation(self.angle, 4, axis.normalized())
            @ Matrix.Translation(-center)
        )
        if entity is not None:
            if self.copy:
                base_matrix = entity.matrix_world.copy()
                bpy.ops.object.mode_set(mode="OBJECT")
                clone = entity.copy()
                clone.data = (
                    entity.data
                    if groups.kind_of(entity) == groups.KIND_COMPONENT
                    else entity.data.copy()
                )
                context.scene.collection.objects.link(clone)
                if groups.kind_of(entity) == groups.KIND_GROUP:
                    groups._tag(clone, groups.KIND_GROUP)
                clone.matrix_world = rot @ entity.matrix_world
                groups.set_entity(context, clone)
                poweruser.remember_array(
                    "rotate",
                    angle=self.angle,
                    center=center,
                    axis=axis.normalized(),
                    entity=entity.name,
                    base_matrix=base_matrix,
                    first_copy=clone.name,
                    unique_mesh=groups.kind_of(entity) != groups.KIND_COMPONENT,
                    extra_names=[],
                )
                _status(context, "Rotated copy — type 8x or 6/ for array, Enter")
            else:
                entity.matrix_world = rot @ entity.matrix_world
                poweruser.clear_array()
            return {"FINISHED"}
        _obj, bm = _edit(context)
        if self.copy:
            geom.duplicate_selected(bm)
        geom.rotate_verts(geom.selected_verts(bm), self.center, self.axis, self.angle)
        geom._ensure(bm)
        _commit(_obj)
        return {"FINISHED"}


class OFORM_OT_scale(Operator):
    bl_idname = "oform.scale"
    bl_label = "Scale"
    bl_options = {"UNDO"}

    center: FloatVectorProperty(size=3)
    factor: FloatProperty(default=1.0)
    axis_name: StringProperty(default="")

    def execute(self, context):
        entity = groups.get_entity(context)
        if entity is not None:
            center = Vector(self.center)
            factor = self.factor
            scale_vec = Vector((factor, factor, factor))
            if self.axis_name == "X":
                scale_vec = Vector((factor, 1.0, 1.0))
            elif self.axis_name == "Y":
                scale_vec = Vector((1.0, factor, 1.0))
            elif self.axis_name == "Z":
                scale_vec = Vector((1.0, 1.0, factor))
            scl = (
                Matrix.Translation(center)
                @ Matrix.Diagonal(scale_vec.to_4d())
                @ Matrix.Translation(-center)
            )
            entity.matrix_world = scl @ entity.matrix_world
            return {"FINISHED"}
        _obj, bm = _edit(context)
        axis = self.axis_name or None
        geom.scale_verts(geom.selected_verts(bm), self.center, self.factor, axis)
        geom._ensure(bm)
        _commit(_obj)
        return {"FINISHED"}


class OFORM_OT_paint(Operator):
    bl_idname = "oform.paint"
    bl_label = "Paint"
    bl_options = {"UNDO"}

    face_index: IntProperty(default=-1)
    color: FloatVectorProperty(size=3, default=(0.8, 0.8, 0.8))

    def execute(self, context):
        obj, bm = _edit(context)
        face = geom.selected_face(bm, self.face_index)
        geom.paint_face(obj, bm, face, self.color)
        _commit(obj)
        return {"FINISHED"}


class OFORM_OT_make_group(Operator):
    bl_idname = "oform.make_group"
    bl_label = "Make Group"
    bl_options = {"UNDO"}

    def execute(self, context):
        obj = groups.make_group(context)
        if obj is None:
            self.report({"WARNING"}, "Select geometry first")
            return {"CANCELLED"}
        _status(context, "Created group " + obj.name)
        return {"FINISHED"}


class OFORM_OT_make_component(Operator):
    bl_idname = "oform.make_component"
    bl_label = "Make Component"
    bl_options = {"UNDO"}

    definition: StringProperty(default="Component")

    def execute(self, context):
        obj = groups.make_component(context, self.definition)
        if obj is None:
            self.report({"WARNING"}, "Select geometry first")
            return {"CANCELLED"}
        _status(context, "Created component " + obj.name)
        return {"FINISHED"}


class OFORM_OT_explode(Operator):
    bl_idname = "oform.explode"
    bl_label = "Explode"
    bl_options = {"UNDO"}

    def execute(self, context):
        entity = groups.get_entity(context)
        if entity is None:
            active = context.view_layer.objects.active
            if groups.is_container(active):
                entity = active
        if entity is None:
            self.report({"WARNING"}, "Select a group or component")
            return {"CANCELLED"}
        name = entity.name
        if not groups.explode(context, entity):
            return {"CANCELLED"}
        _status(context, "Exploded " + name)
        return {"FINISHED"}


class OFORM_OT_enter_group(Operator):
    bl_idname = "oform.enter_group"
    bl_label = "Edit Group/Component"
    bl_options = {"UNDO"}

    def execute(self, context):
        entity = groups.get_entity(context)
        if entity is None:
            self.report({"WARNING"}, "Select a group or component")
            return {"CANCELLED"}
        groups.set_entity(context, None)
        groups.push_context(context, entity)
        _status(context, "Editing " + entity.name)
        return {"FINISHED"}


class OFORM_OT_exit_group(Operator):
    bl_idname = "oform.exit_group"
    bl_label = "Close Group/Component"
    bl_options = {"UNDO"}

    def execute(self, context):
        if groups.context_depth(context) <= 0:
            self.report({"INFO"}, "Already at model root")
            return {"CANCELLED"}
        groups.set_entity(context, None)
        obj = groups.pop_context(context)
        _status(context, "Closed — editing " + obj.name)
        return {"FINISHED"}


class OFORM_OT_instance_component(Operator):
    bl_idname = "oform.instance_component"
    bl_label = "Instance Component"
    bl_options = {"UNDO"}

    def execute(self, context):
        entity = groups.get_entity(context)
        if entity is None or groups.kind_of(entity) != groups.KIND_COMPONENT:
            self.report({"WARNING"}, "Select a component")
            return {"CANCELLED"}
        inst = groups.instance_component(context, entity)
        if inst is None:
            return {"CANCELLED"}
        groups.set_entity(context, inst)
        _status(context, "Instanced " + inst.name)
        return {"FINISHED"}


def _boolean_operands(context):
    """Active mesh = target; another selected mesh = tool. Or entity pair."""
    view = context.view_layer.objects
    active = view.active
    selected = [obj for obj in context.selected_objects if obj.type == "MESH"]
    entity = groups.get_entity(context)
    if entity is not None and entity.type == "MESH":
        others = [obj for obj in selected if obj != entity and obj.type == "MESH"]
        if others:
            return entity, others[0]
    if active is not None and active.type == "MESH":
        others = [obj for obj in selected if obj != active]
        if others:
            return active, others[0]
    if len(selected) >= 2:
        return selected[0], selected[1]
    return None, None


class OFORM_OT_boolean(Operator):
    bl_idname = "oform.boolean"
    bl_label = "Boolean"
    bl_description = (
        "Combine two mesh solids. Select target (active) and tool, then run Union / Subtract / Intersect"
    )
    bl_options = {"UNDO"}

    operation: EnumProperty(
        items=(
            ("UNION", "Union", "Combine solids"),
            ("DIFFERENCE", "Subtract", "Subtract tool from target"),
            ("INTERSECT", "Intersect", "Keep shared volume"),
        ),
        default="UNION",
    )

    def execute(self, context):
        target, tool = _boolean_operands(context)
        if target is None or tool is None:
            hint = (
                "Solid Boolean: select two closed meshes in Object mode "
                "(active = keep). Use rail Solids or Solids menu."
            )
            self.report({"WARNING"}, hint)
            _status(context, hint)
            return {"CANCELLED"}
        if context.mode != "OBJECT":
            bpy.ops.object.mode_set(mode="OBJECT")
        ok, message = solids.boolean_objects(context, target, tool, self.operation)
        if not ok:
            self.report({"ERROR"}, message)
            _status(context, message)
            return {"CANCELLED"}
        # Keep target; deselect tool so the result is clear.
        for obj in context.selected_objects:
            obj.select_set(obj == target)
        context.view_layer.objects.active = target
        _status(context, message)
        self.report({"INFO"}, message)
        return {"FINISHED"}


class OFORM_OT_boolean_union(Operator):
    bl_idname = "oform.boolean_union"
    bl_label = "Solid Union"
    bl_description = "Union two solids (active mesh kept). Select two closed meshes first"
    bl_options = {"UNDO"}

    def execute(self, context):
        return bpy.ops.oform.boolean(operation="UNION")


class OFORM_OT_boolean_subtract(Operator):
    bl_idname = "oform.boolean_subtract"
    bl_label = "Solid Subtract"
    bl_description = "Subtract the other solid from the active mesh"
    bl_options = {"UNDO"}

    def execute(self, context):
        return bpy.ops.oform.boolean(operation="DIFFERENCE")


class OFORM_OT_boolean_intersect(Operator):
    bl_idname = "oform.boolean_intersect"
    bl_label = "Solid Intersect"
    bl_description = "Keep only the shared volume of two solids"
    bl_options = {"UNDO"}

    def execute(self, context):
        return bpy.ops.oform.boolean(operation="INTERSECT")


class OFORM_OT_solid_inspect(Operator):
    bl_idname = "oform.solid_inspect"
    bl_label = "Inspect Solid"
    bl_description = "Report whether the active mesh is a closed manifold solid"
    bl_options = {"REGISTER"}

    def execute(self, context):
        obj = context.view_layer.objects.active
        if obj is None or obj.type != "MESH":
            self.report({"WARNING"}, "Select a mesh object")
            return {"CANCELLED"}
        bm = bmesh.new()
        bm.from_mesh(obj.data)
        ok = solids.is_solid(bm)
        bm.free()
        message = "Solid (closed manifold)" if ok else "Not a solid — open or non-manifold"
        _status(context, message)
        self.report({"INFO"} if ok else {"WARNING"}, message)
        return {"FINISHED"}


class OFORM_OT_boolean_trim(Operator):
    """SketchUp Trim: cutter subtracts from target but cutter remains."""

    bl_idname = "oform.boolean_trim"
    bl_label = "Solid Trim"
    bl_description = "Trim the active solid with the other (cutter stays)"
    bl_options = {"UNDO"}

    def execute(self, context):
        target, tool = _boolean_operands(context)
        if target is None or tool is None:
            hint = "Trim: select two solids (active = keep/trim target)"
            self.report({"WARNING"}, hint)
            _status(context, hint)
            return {"CANCELLED"}
        if context.mode != "OBJECT":
            bpy.ops.object.mode_set(mode="OBJECT")
        # Snapshot cutter — DIFFERENCE deletes overlapping volume from target only.
        ok, message = solids.boolean_objects(context, target, tool, "DIFFERENCE")
        if not ok:
            self.report({"ERROR"}, message)
            _status(context, message)
            return {"CANCELLED"}
        _status(context, "Trim complete (cutter kept)")
        self.report({"INFO"}, "Trim complete")
        return {"FINISHED"}


class OFORM_OT_boolean_outer_shell(Operator):
    bl_idname = "oform.boolean_outer_shell"
    bl_label = "Outer Shell"
    bl_description = "Union overlapping solids into a single outer shell"
    bl_options = {"UNDO"}

    def execute(self, context):
        return bpy.ops.oform.boolean(operation="UNION")


class OFORM_OT_reverse_faces(Operator):
    bl_idname = "oform.reverse_faces"
    bl_label = "Reverse Faces"
    bl_description = "Flip normals on selected faces (SketchUp Reverse Faces)"
    bl_options = {"UNDO"}

    def execute(self, context):
        obj, bm = _edit(context)
        n = geom.reverse_faces(bm)
        _commit(obj)
        _status(context, "Reversed {} face(s)".format(n))
        return {"FINISHED"}


class OFORM_OT_delete_guides(Operator):
    bl_idname = "oform.delete_guides"
    bl_label = "Delete Guides"
    bl_description = "Remove all construction guides from the current edit context"
    bl_options = {"UNDO"}

    def execute(self, context):
        obj, bm = _edit(context)
        n = geom.delete_guides(bm)
        _commit(obj)
        msg = "Deleted {} guide(s)".format(n) if n else "No guides"
        _status(context, msg)
        return {"FINISHED"}


class OFORM_OT_hide_selected(Operator):
    bl_idname = "oform.hide_selected"
    bl_label = "Hide"
    bl_description = "Hide selection (Unhide Last restores)"
    bl_options = {"UNDO"}

    def execute(self, context):
        ok, message = poweruser.hide_selected_objects(context)
        _status(context, message)
        if not ok:
            self.report({"WARNING"}, message)
            return {"CANCELLED"}
        return {"FINISHED"}


class OFORM_OT_unhide_last(Operator):
    bl_idname = "oform.unhide_last"
    bl_label = "Unhide Last"
    bl_description = "Unhide the last hidden selection (Reddit power-user U)"
    bl_options = {"UNDO"}

    def execute(self, context):
        ok, message = poweruser.unhide_last(context)
        _status(context, message)
        return {"FINISHED"} if ok else {"CANCELLED"}


class OFORM_OT_unhide_all(Operator):
    bl_idname = "oform.unhide_all"
    bl_label = "Unhide All"
    bl_description = "Show all hidden objects and geometry"
    bl_options = {"UNDO"}

    def execute(self, context):
        _ok, message = poweruser.unhide_all(context)
        _status(context, message)
        return {"FINISHED"}


class OFORM_OT_hide_rest(Operator):
    bl_idname = "oform.hide_rest"
    bl_label = "Hide Rest of Model"
    bl_description = "While editing a group, hide everything else"
    bl_options = {"UNDO"}

    def execute(self, context):
        ok, message = poweruser.hide_rest_of_model(context)
        _status(context, message)
        return {"FINISHED"} if ok else {"CANCELLED"}


class OFORM_OT_copy_selection(Operator):
    bl_idname = "oform.copy_selection"
    bl_label = "Copy"
    bl_description = "Copy selection for Paste in Place"
    bl_options = {"REGISTER"}

    def execute(self, context):
        ok, message = poweruser.copy_selection(context)
        _status(context, message)
        return {"FINISHED"} if ok else {"CANCELLED"}


class OFORM_OT_paste_in_place(Operator):
    bl_idname = "oform.paste_in_place"
    bl_label = "Paste in Place"
    bl_description = "Paste clipboard objects at their original world location"
    bl_options = {"UNDO"}

    def execute(self, context):
        ok, message = poweruser.paste_in_place(context)
        _status(context, message)
        return {"FINISHED"} if ok else {"CANCELLED"}


class OFORM_OT_face_style(Operator):
    bl_idname = "oform.face_style"
    bl_label = "Face Style"
    bl_description = "Cycle Shaded / X-Ray / Wireframe / Monochrome"
    bl_options = {"REGISTER"}

    style: EnumProperty(
        items=(
            ("CYCLE", "Cycle", ""),
            ("shaded", "Shaded", ""),
            ("xray", "X-Ray", ""),
            ("wire", "Wireframe", ""),
            ("mono", "Monochrome", ""),
        ),
        default="CYCLE",
    )

    def execute(self, context):
        style = None if self.style == "CYCLE" else self.style
        name = poweruser.face_style(context, style)
        _status(context, "Face style: " + name)
        return {"FINISHED"}


class OFORM_OT_previous_view(Operator):
    bl_idname = "oform.previous_view"
    bl_label = "Previous View"
    bl_description = "Restore the previous camera (SketchUp Previous)"
    bl_options = {"REGISTER"}

    def execute(self, context):
        ok, message = poweruser.previous_view(context)
        _status(context, message)
        return {"FINISHED"} if ok else {"CANCELLED"}


class OFORM_OT_zoom_window(Operator):
    bl_idname = "oform.zoom_window"
    bl_label = "Zoom Window"
    bl_description = "Zoom to a drawn rectangle (Blender border zoom)"
    bl_options = {"REGISTER"}

    def invoke(self, context, event):
        poweruser.push_view(context)
        try:
            return bpy.ops.view3d.zoom_border("INVOKE_DEFAULT")
        except RuntimeError:
            self.report({"WARNING"}, "Zoom Window needs a 3D View")
            return {"CANCELLED"}


# ---------------------------------------------------------------------------
# Modal tools.
# ---------------------------------------------------------------------------


def _snap(context, bm, event, axis, parallel, anchor, plane=None, tool=None):
    snap = inference.infer(
        context,
        bm,
        _mouse(event),
        axis=axis,
        parallel=parallel,
        anchor=anchor,
        plane=plane,
    )
    set_inference_feedback(snap)
    if tool is not None:
        tool._last_snap = snap
    return snap


class OFORM_OT_tool_line(Operator, _Tool):
    bl_idname = "oform.tool_line"
    bl_label = "Line"

    def invoke(self, context, _event):
        self._segments = 0
        return self._start(context, "Click to set the first point")

    def modal(self, context, event):
        handled = self._event(context, event)
        if handled in ({"FINISHED"}, {"PASS_THROUGH"}):
            return handled
        if handled == {"RUNNING_MODAL"} and event.type == "ESC":
            self._segments = 0
            return handled
        _obj, bm = _edit(context)
        anchor = self._points[-1] if self._points else None
        snap = _snap(
            context, bm, event, self._axis, self._parallel, anchor, plane=self._plane
        )
        if snap.tangent is not None:
            self._parallel = snap.tangent
        if event.type == "LEFTMOUSE" and event.value == "PRESS":
            self._adopt_plane(snap, bm)
            self._points.append(snap.co.copy())
            hint = snap.label + " · " if snap.label else ""
            if len(self._points) >= 2:
                _do(bpy.ops.oform.line_add, a=self._points[-2], b=self._points[-1])
                self._segments += 1
                _status(context, hint + "Click the next point, or type a length")
            else:
                _status(context, hint + "Click the next point, or type a length")
            return {"RUNNING_MODAL"}
        if handled == {"APPLY"} and self._points and self._buf.strip():
            try:
                length = _parse_length(self._buf, context)
            except ValueError:
                return {"RUNNING_MODAL"}
            direction = snap.co - self._points[-1]
            if direction.length < 1e-8:
                direction = Vector((1.0, 0.0, 0.0))
            end = self._points[-1] + direction.normalized() * length
            _do(bpy.ops.oform.line_add, a=self._points[-1], b=end)
            self._points.append(end)
            self._buf = ""
            _measure(context, "")
            return {"RUNNING_MODAL"}
        if self._points:
            set_preview([self._points[-1], snap.co])
            label = ("  " + snap.label) if snap.label else ""
            _measure(context, _fmt_length((snap.co - self._points[-1]).length, context) + label)
            _status(context, (snap.label + "  " if snap.label else "") + "Click the next point, or type a length")
        return {"RUNNING_MODAL"}


class OFORM_OT_tool_rectangle(Operator, _Tool):
    bl_idname = "oform.tool_rectangle"
    bl_label = "Rectangle"

    def invoke(self, context, _event):
        return self._start(context, "Click to set the first corner")

    def modal(self, context, event):
        handled = self._event(context, event)
        if handled in ({"FINISHED"}, {"PASS_THROUGH"}):
            return handled
        _obj, bm = _edit(context)
        anchor = self._anchor
        snap = _snap(
            context, bm, event, self._axis, self._parallel, anchor, plane=self._plane
        )
        if snap.tangent is not None:
            self._parallel = snap.tangent
        if event.type == "LEFTMOUSE" and event.value == "PRESS":
            if self._anchor is None:
                self._adopt_plane(snap, bm)
                self._anchor = snap.co.copy()
                self._normal = (
                    self._plane.normal.copy()
                    if self._plane is not None
                    else snap.normal.copy()
                )
                _status(context, "Click the opposite corner, or type width, depth")
            else:
                _do(
                    bpy.ops.oform.rectangle,
                    corner_a=self._anchor,
                    corner_b=snap.co,
                    normal=self._normal,
                )
                self._anchor = None
                self._plane = None
                self._buf = ""
                set_preview([])
                set_inference_feedback(None)
                _measure(context, "")
                _status(context, "Click to set the first corner")
            return {"RUNNING_MODAL"}
        if handled == {"APPLY"} and self._anchor is not None and "," in self._buf:
            try:
                width_s, depth_s = self._buf.split(",", 1)
                width = _parse_length(width_s, context)
                depth = _parse_length(depth_s, context)
            except ValueError:
                return {"RUNNING_MODAL"}
            normal = getattr(self, "_normal", Vector((0.0, 0.0, 1.0)))
            u, v = geom._basis(normal)
            if abs(normal.z) > 0.999:
                u = Vector((1.0, 0.0, 0.0))
                v = Vector((0.0, 1.0, 0.0 if normal.z > 0 else -1.0))
            corner_b = self._anchor + u * width + v * depth
            _do(bpy.ops.oform.rectangle, corner_a=self._anchor, corner_b=corner_b, normal=normal)
            self._anchor = None
            self._plane = None
            self._buf = ""
            set_preview([])
            set_inference_feedback(None)
            _measure(context, "")
            _status(context, "Click to set the first corner")
            return {"RUNNING_MODAL"}
        if self._anchor is not None:
            normal = getattr(self, "_normal", snap.normal)
            corners = geom.rectangle_corners(self._anchor, snap.co, normal)
            set_preview(corners + [corners[0]])
            _measure(
                context,
                "{}, {}".format(
                    _fmt_length((corners[1] - corners[0]).length, context),
                    _fmt_length((corners[3] - corners[0]).length, context),
                ),
            )
        return {"RUNNING_MODAL"}


class OFORM_OT_tool_circle(Operator, _Tool):
    bl_idname = "oform.tool_circle"
    bl_label = "Circle"

    def invoke(self, context, _event):
        self._segments = 24
        return self._start(context, "Click to set the center")

    def modal(self, context, event):
        handled = self._event(context, event)
        if handled in ({"FINISHED"}, {"PASS_THROUGH"}):
            return handled
        _obj, bm = _edit(context)
        snap = _snap(
            context, bm, event, self._axis, self._parallel, self._anchor, plane=self._plane
        )
        raw = self._buf.strip().lower()
        if raw.endswith("s") and raw[:-1].isdigit():
            self._segments = max(3, int(raw[:-1]))
            self._buf = ""
            _status(context, "Circle segments: {}. Click the radius, or type it.".format(self._segments))
            _measure(context, "")
            return {"RUNNING_MODAL"}
        if event.type == "LEFTMOUSE" and event.value == "PRESS":
            if self._anchor is None:
                self._adopt_plane(snap, bm)
                self._anchor = snap.co.copy()
                self._normal = (
                    self._plane.normal.copy()
                    if self._plane is not None
                    else snap.normal.copy()
                )
                _status(context, "Click the radius, type a radius, or type 24s for segments")
            else:
                radius = (snap.co - self._anchor).length
                _do(
                    bpy.ops.oform.circle,
                    center=self._anchor,
                    radius=radius,
                    normal=self._normal,
                    segments=self._segments,
                )
                self._anchor = None
                self._plane = None
                set_preview([])
                set_inference_feedback(None)
                _measure(context, "")
                _status(context, "Click to set the center")
            return {"RUNNING_MODAL"}
        if handled == {"APPLY"} and self._anchor is not None and self._buf.strip():
            try:
                radius = _parse_length(self._buf, context)
            except ValueError:
                return {"RUNNING_MODAL"}
            _do(
                bpy.ops.oform.circle,
                center=self._anchor,
                radius=radius,
                normal=getattr(self, "_normal", Vector((0.0, 0.0, 1.0))),
                segments=self._segments,
            )
            self._anchor = None
            self._plane = None
            self._buf = ""
            set_preview([])
            set_inference_feedback(None)
            _measure(context, "")
            _status(context, "Click to set the center")
            return {"RUNNING_MODAL"}
        if self._anchor is not None:
            pts = geom.circle_points(
                self._anchor, (snap.co - self._anchor).length, self._normal, self._segments
            )
            if pts:
                set_preview(pts + [pts[0]])
            _measure(context, _fmt_length((snap.co - self._anchor).length, context))
        return {"RUNNING_MODAL"}


class OFORM_OT_tool_arc(Operator, _Tool):
    bl_idname = "oform.tool_arc"
    bl_label = "Arc"

    def invoke(self, context, _event):
        return self._start(context, "Click the arc start point")

    def modal(self, context, event):
        handled = self._event(context, event)
        if handled in ({"FINISHED"}, {"PASS_THROUGH"}):
            return handled
        _obj, bm = _edit(context)
        anchor = self._points[-1] if self._points else None
        snap = _snap(
            context, bm, event, self._axis, self._parallel, anchor, plane=self._plane
        )
        if event.type == "LEFTMOUSE" and event.value == "PRESS":
            self._adopt_plane(snap, bm)
            self._points.append(snap.co.copy())
            if len(self._points) == 1:
                _status(context, "Click the arc end point")
            elif len(self._points) == 2:
                _status(context, "Click the bulge, or type a bulge distance")
            else:
                _do(
                    bpy.ops.oform.arc,
                    start=self._points[0],
                    end=self._points[1],
                    bulge=self._points[2],
                )
                self._points.clear()
                self._plane = None
                set_preview([])
                set_inference_feedback(None)
                _measure(context, "")
                _status(context, "Click the arc start point")
            return {"RUNNING_MODAL"}
        if len(self._points) == 2:
            pts = geom.arc_points(self._points[0], self._points[1], snap.co, 12)
            set_preview(pts)
        elif len(self._points) == 1:
            set_preview([self._points[0], snap.co])
        return {"RUNNING_MODAL"}


class OFORM_OT_tool_push_pull(Operator, _Tool):
    bl_idname = "oform.tool_push_pull"
    bl_label = "Push/Pull"

    def invoke(self, context, _event):
        self._face_index = -1
        self._origin = None
        self._direction = Vector((0.0, 0.0, 1.0))
        self._clicks = selection.ClickTracker()
        last = poweruser.last_push_pull()
        hint = " · double-click repeats {:.3f}".format(last) if abs(last) > 1e-9 else ""
        return self._start(context, "Click a face to push/pull · Ctrl copies" + hint)

    def modal(self, context, event):
        handled = self._event(context, event)
        if handled in ({"FINISHED"}, {"PASS_THROUGH"}):
            return handled
        obj, bm = _edit(context)
        if self._origin is None:
            _snap(context, bm, event, None, None, None, tool=self)
        if event.type == "LEFTMOUSE" and event.value == "PRESS":
            if self._origin is None:
                face = _face_under_mouse(context, bm, event)
                if face is None:
                    return {"RUNNING_MODAL"}
                count = self._clicks.register(_mouse(event))
                last = poweruser.last_push_pull()
                # SketchUp: double-click applies last Push/Pull amount.
                if count >= 2 and abs(last) > 1e-9:
                    geom._select_only_face(bm, face)
                    _commit(obj)
                    bm.faces.ensure_lookup_table()
                    _do(
                        bpy.ops.oform.push_pull,
                        distance=last,
                        face_index=face.index,
                        copy=event.ctrl,
                    )
                    _status(context, "Repeated Push/Pull {:.3f}".format(last))
                    return {"RUNNING_MODAL"}
                geom._select_only_face(bm, face)
                _commit(obj)
                bm.faces.ensure_lookup_table()
                self._face_index = face.index
                self._origin = face.calc_center_median().copy()
                self._direction = face.normal.copy()
                _status(context, "Move to extrude, or type a distance. Ctrl copies the face")
            else:
                distance = self._distance(context, event)
                _do(
                    bpy.ops.oform.push_pull,
                    distance=distance,
                    face_index=self._face_index,
                    copy=event.ctrl,
                )
                self._origin = None
                self._face_index = -1
                self._buf = ""
                set_preview([])
                _measure(context, "")
                _status(context, "Click a face · double-click repeats last")
            return {"RUNNING_MODAL"}
        if handled == {"APPLY"} and self._origin is not None and self._buf.strip():
            try:
                distance = _parse_length(self._buf, context)
            except ValueError:
                return {"RUNNING_MODAL"}
            _do(
                bpy.ops.oform.push_pull,
                distance=distance,
                face_index=self._face_index,
                copy=event.ctrl,
            )
            self._origin = None
            self._buf = ""
            set_preview([])
            _measure(context, "")
            _status(context, "Click a face · double-click repeats last")
            return {"RUNNING_MODAL"}
        if self._origin is not None:
            distance = self._distance(context, event)
            _measure(context, _fmt_length(distance, context))
            self._preview_extrude(bm, distance)
        else:
            set_preview([])
        return {"RUNNING_MODAL"}

    def _preview_extrude(self, bm, distance):
        bm.faces.ensure_lookup_table()
        if self._face_index < 0 or self._face_index >= len(bm.faces):
            set_preview([])
            return
        face = bm.faces[self._face_index]
        axis = self._direction.copy()
        if self._axis == "X":
            axis = Vector((1.0, 0.0, 0.0))
        elif self._axis == "Y":
            axis = Vector((0.0, 1.0, 0.0))
        elif self._axis == "Z":
            axis = Vector((0.0, 0.0, 1.0))
        delta = axis.normalized() * distance
        base = [vert.co.copy() for vert in face.verts]
        lifted = [co + delta for co in base]
        strokes = [lifted + [lifted[0]]]
        strokes.extend([[a, b] for a, b in zip(base, lifted)])
        set_preview_strokes(strokes)

    def _distance(self, context, event):
        from bpy_extras import view3d_utils
        from mathutils.geometry import intersect_line_line

        region = context.region
        rv3d = context.region_data
        mouse = _mouse(event)
        origin = view3d_utils.region_2d_to_origin_3d(region, rv3d, mouse)
        direction = view3d_utils.region_2d_to_vector_3d(region, rv3d, mouse)
        axis = self._direction
        if self._axis == "X":
            axis = Vector((1.0, 0.0, 0.0))
        elif self._axis == "Y":
            axis = Vector((0.0, 1.0, 0.0))
        elif self._axis == "Z":
            axis = Vector((0.0, 0.0, 1.0))
        hits = intersect_line_line(self._origin, self._origin + axis, origin, origin + direction * 1000.0)
        if not hits or hits[0] is None:
            return 0.0
        return (hits[0] - self._origin).dot(axis)


class OFORM_OT_tool_offset(Operator, _Tool):
    bl_idname = "oform.tool_offset"
    bl_label = "Offset"

    def invoke(self, context, _event):
        self._face_index = -1
        self._origin = None
        return self._start(context, "Click a face to offset")

    def modal(self, context, event):
        handled = self._event(context, event)
        if handled in ({"FINISHED"}, {"PASS_THROUGH"}):
            return handled
        obj, bm = _edit(context)
        if event.type == "LEFTMOUSE" and event.value == "PRESS":
            if self._face_index < 0:
                face = _face_under_mouse(context, bm, event)
                if face is None:
                    return {"RUNNING_MODAL"}
                geom._select_only_face(bm, face)
                _commit(obj)
                bm.faces.ensure_lookup_table()
                self._face_index = face.index
                self._origin = face.calc_center_median().copy()
                _status(context, "Move to set the offset, or type a distance")
            else:
                snap = _snap(context, bm, event, None, None, self._origin)
                distance = (snap.co - self._origin).length
                _do(bpy.ops.oform.offset, distance=distance, face_index=self._face_index)
                self._face_index = -1
                self._buf = ""
                _measure(context, "")
                _status(context, "Click a face to offset")
            return {"RUNNING_MODAL"}
        if handled == {"APPLY"} and self._face_index >= 0 and self._buf.strip():
            try:
                distance = _parse_length(self._buf, context)
            except ValueError:
                return {"RUNNING_MODAL"}
            _do(bpy.ops.oform.offset, distance=distance, face_index=self._face_index)
            self._face_index = -1
            self._buf = ""
            _measure(context, "")
            return {"RUNNING_MODAL"}
        if self._origin is not None and self._face_index >= 0:
            snap = _snap(context, bm, event, None, None, self._origin)
            _measure(context, _fmt_length((snap.co - self._origin).length, context))
        return {"RUNNING_MODAL"}


class OFORM_OT_tool_eraser(Operator, _Tool):
    bl_idname = "oform.tool_eraser"
    bl_label = "Eraser"

    def invoke(self, context, _event):
        return self._start(context, "Click an edge to erase. Ctrl softens. Shift hides")

    def modal(self, context, event):
        handled = self._event(context, event)
        if handled in ({"FINISHED"}, {"PASS_THROUGH"}):
            return handled
        if event.type == "LEFTMOUSE" and event.value in {"PRESS", "CLICK"}:
            _obj, bm = _edit(context)
            edge = _edge_under_mouse(context, bm, event)
            if edge is not None:
                bm.edges.ensure_lookup_table()
                index = edge.index
                if event.ctrl:
                    _do(bpy.ops.oform.soften, edge_index=index, smooth=True)
                elif event.shift:
                    _do(bpy.ops.oform.hide_edges, edge_index=index, hide=True)
                else:
                    _do(bpy.ops.oform.erase, edge_index=index)
            return {"RUNNING_MODAL"}
        return {"RUNNING_MODAL"}


class OFORM_OT_tool_paint(Operator, _Tool):
    bl_idname = "oform.tool_paint"
    bl_label = "Paint"

    def invoke(self, context, _event):
        if _prop(context.scene, "oform_color") is None:
            pass
        return self._start(context, "Click a face to paint. Keys 1-8 pick a color")

    def modal(self, context, event):
        # Number keys also match the measurement buffer. Pick the color first.
        if event.value == "PRESS" and event.type in {
            "ONE", "TWO", "THREE", "FOUR", "FIVE", "SIX", "SEVEN", "EIGHT",
            "NUMPAD_1", "NUMPAD_2", "NUMPAD_3", "NUMPAD_4",
            "NUMPAD_5", "NUMPAD_6", "NUMPAD_7", "NUMPAD_8",
        }:
            table = {
                "ONE": 0, "NUMPAD_1": 0, "TWO": 1, "NUMPAD_2": 1,
                "THREE": 2, "NUMPAD_3": 2, "FOUR": 3, "NUMPAD_4": 3,
                "FIVE": 4, "NUMPAD_5": 4, "SIX": 5, "NUMPAD_6": 5,
                "SEVEN": 6, "NUMPAD_7": 6, "EIGHT": 7, "NUMPAD_8": 7,
            }
            color = COLORS[table[event.type]]
            _prop(context.scene, "oform_color", color)
            _status(context, "Paint color {:d}. Click a face".format(table[event.type] + 1))
            return {"RUNNING_MODAL"}
        handled = self._event(context, event)
        if handled in ({"FINISHED"}, {"PASS_THROUGH"}):
            return handled
        if event.type == "LEFTMOUSE" and event.value == "PRESS":
            obj, bm = _edit(context)
            face = _face_under_mouse(context, bm, event)
            if face is None:
                return {"RUNNING_MODAL"}
            geom._select_only_face(bm, face)
            _commit(obj)
            bm.faces.ensure_lookup_table()
            color = _prop(context.scene, "oform_color") or COLORS[0]
            _do(bpy.ops.oform.paint, face_index=face.index, color=color)
            return {"RUNNING_MODAL"}
        return {"RUNNING_MODAL"}


class OFORM_OT_tool_select(Operator, _Tool):
    bl_idname = "oform.tool_select"
    bl_label = "Select"
    bl_description = "Click line · double face · triple connected faces. Alt+1/2/3"

    def invoke(self, context, _event):
        self._box = None
        self._clicks = selection.ClickTracker()
        return self._start(
            context,
            "Click point/line · double face · triple connected · Alt+1/2/3",
        )

    def _apply_selection(self, context, mouse, count, extend):
        obj, bm = _edit(context)
        # Ensure verts/edges/faces can all highlight (SketchUp Select).
        try:
            context.tool_settings.mesh_select_mode = (True, True, True)
        except Exception:
            pass
        mode = selection.apply_click(context, bm, mouse, count, extend=extend)
        _commit(obj)
        if mode == "enter":
            ctx = groups.context_object(context)
            _status(context, "Editing " + (ctx.name if ctx else "group"))
        elif mode == "entity":
            entity = groups.get_entity(context)
            if entity is not None:
                _status(
                    context,
                    "Selected {} ({})".format(entity.name, groups.kind_of(entity)),
                )
        elif mode == "double":
            _status(context, "Face selected")
        elif mode == "triple":
            _status(context, "Connected faces selected")
        elif mode == "single":
            hit = selection.pick_mesh(context, bm, mouse)
            if hit and hit[0] == "vert":
                _status(context, "Point selected")
            elif hit and hit[0] == "edge":
                _status(context, "Line selected")
            elif hit and hit[0] == "face":
                _status(context, "Face selected")
            else:
                _status(context, "Selected")
        else:
            _status(context, "Selection cleared")

    def _hover_snap(self, context, event):
        obj, bm = _edit(context)
        snap = selection.hover_snap(context, bm, _mouse(event))
        set_inference_feedback(snap)
        self._last_snap = snap
        if snap is not None and snap.label:
            current = getattr(context.scene, "oform_status", "") or ""
            if current in {
                "",
                "Select a tool",
                "Click line · double face · triple connected · Alt+1/2/3",
                "Line selected",
                "Face selected",
                "Connected faces selected",
                "Selection cleared",
                "Endpoint",
                "Midpoint",
                "On Edge",
                "On Face",
            }:
                _status(context, snap.label)

    def modal(self, context, event):
        handled = self._event(context, event)
        if handled in ({"FINISHED"}, {"PASS_THROUGH"}):
            return handled
        # Keyboard alternatives to multi-click (accessibility).
        if event.value == "PRESS" and event.type == "ONE" and event.alt:
            obj, bm = _edit(context)
            hit = selection.pick_mesh(context, bm, _mouse(event))
            selection.select_entity(bm, hit, extend=event.shift)
            _commit(obj)
            _status(context, "Line selected (Alt+1)")
            return {"RUNNING_MODAL"}
        if event.value == "PRESS" and event.type == "TWO" and event.alt:
            obj, bm = _edit(context)
            hit = selection.pick_mesh(context, bm, _mouse(event))
            selection.select_related(
                bm, hit, extend=event.shift, mouse=_mouse(event), context=context
            )
            _commit(obj)
            _status(context, "Face selected (Alt+2)")
            return {"RUNNING_MODAL"}
        if event.value == "PRESS" and event.type == "THREE" and event.alt:
            obj, bm = _edit(context)
            hit = selection.pick_mesh(context, bm, _mouse(event))
            selection.select_connected(
                bm, hit, extend=event.shift, mouse=_mouse(event), context=context
            )
            _commit(obj)
            _status(context, "Connected faces (Alt+3)")
            return {"RUNNING_MODAL"}
        if event.type == "MOUSEMOVE" and self._box is None:
            self._hover_snap(context, event)
            return {"RUNNING_MODAL"}
        if event.type == "LEFTMOUSE" and event.value == "PRESS":
            self._box = (_mouse(event), _mouse(event), event.shift or event.ctrl)
            return {"RUNNING_MODAL"}
        if event.type == "MOUSEMOVE" and self._box is not None:
            self._box = (self._box[0], _mouse(event), self._box[2])
            return {"RUNNING_MODAL"}
        if event.type == "LEFTMOUSE" and event.value == "RELEASE" and self._box is not None:
            start, end, extend = self._box
            self._box = None
            if (Vector(start) - Vector(end)).length < 4.0:
                # SketchUp: apply immediately; double/triple upgrades the selection.
                count = self._clicks.register(end)
                self._apply_selection(context, end, count, extend)
            else:
                self._clicks.reset()
                groups.set_entity(context, None)
                obj, bm = _edit(context)
                _box_select(context, bm, start, end, extend)
                _commit(obj)
            return {"RUNNING_MODAL"}
        return {"RUNNING_MODAL"}


class OFORM_OT_tool_move(Operator, _Tool):
    bl_idname = "oform.tool_move"
    bl_label = "Move"

    def invoke(self, context, _event):
        self._copy = False
        return self._start(
            context, "Click a base point · Ctrl toggles copy · then 5x / 3/ for arrays"
        )

    def modal(self, context, event):
        handled = self._event(context, event)
        if handled in ({"FINISHED"}, {"PASS_THROUGH"}):
            return handled
        if event.type == "LEFT_CTRL" or event.type == "RIGHT_CTRL":
            if event.value == "PRESS":
                self._copy = not getattr(self, "_copy", False)
                _status(
                    context,
                    "Copy ON — click destination, then type 5x or 3/"
                    if self._copy
                    else "Copy OFF — move selection",
                )
                return {"RUNNING_MODAL"}
        obj, bm = _edit(context)
        entity = groups.get_entity(context)
        if (
            event.type == "LEFTMOUSE"
            and event.value == "PRESS"
            and entity is None
            and not geom.selected_verts(bm)
        ):
            container = groups.pick_container(context, _mouse(event))
            if container is not None:
                groups.set_entity(context, container)
                entity = container
            else:
                _pick_select(context, bm, _mouse(event), False)
                _commit(obj)
        snap = _snap(context, bm, event, self._axis, self._parallel, self._anchor, tool=self)
        if snap.tangent is not None:
            self._parallel = snap.tangent
        do_copy = getattr(self, "_copy", False) or event.ctrl
        if event.type == "LEFTMOUSE" and event.value == "PRESS":
            if self._anchor is None:
                self._anchor = snap.co.copy()
                _status(
                    context,
                    "Click destination · Ctrl=copy · type distance · after copy: 5x / 3/",
                )
            else:
                delta = snap.co - self._anchor
                _do(bpy.ops.oform.move, delta=delta, copy=do_copy)
                self._anchor = None
                self._buf = ""
                set_preview([])
                _measure(context, "")
                _status(
                    context,
                    "Array: type 5x or 3/ then Enter"
                    if do_copy
                    else "Click a base point on the selection",
                )
            return {"RUNNING_MODAL"}
        if handled == {"APPLY"} and self._anchor is not None and self._buf.strip():
            if poweruser.parse_array_token(self._buf):
                return {"RUNNING_MODAL"}  # handled in _event
            try:
                length = _parse_length(self._buf, context)
            except ValueError:
                return {"RUNNING_MODAL"}
            direction = snap.co - self._anchor
            if direction.length < 1e-8:
                direction = Vector((1.0, 0.0, 0.0))
            delta = direction.normalized() * length
            _do(bpy.ops.oform.move, delta=delta, copy=do_copy)
            self._anchor = None
            self._buf = ""
            set_preview([])
            _measure(context, "")
            return {"RUNNING_MODAL"}
        if self._anchor is not None:
            set_preview([self._anchor, snap.co])
            _measure(context, _fmt_length((snap.co - self._anchor).length, context))
        return {"RUNNING_MODAL"}


class OFORM_OT_tool_rotate(Operator, _Tool):
    bl_idname = "oform.tool_rotate"
    bl_label = "Rotate"

    def invoke(self, context, _event):
        self._ref = None
        self._axis_vec = Vector((0.0, 0.0, 1.0))
        self._copy = False
        return self._start(context, "Click rotation center · Ctrl toggles copy (circular arrays)")

    def modal(self, context, event):
        handled = self._event(context, event)
        if handled in ({"FINISHED"}, {"PASS_THROUGH"}):
            return handled
        if event.type in {"LEFT_CTRL", "RIGHT_CTRL"} and event.value == "PRESS":
            self._copy = not getattr(self, "_copy", False)
            _status(context, "Copy ON" if self._copy else "Copy OFF")
            return {"RUNNING_MODAL"}
        obj, bm = _edit(context)
        if event.type == "LEFTMOUSE" and event.value == "PRESS" and self._anchor is None and not geom.selected_verts(bm):
            _pick_select(context, bm, _mouse(event), False)
            _commit(obj)
        snap = _snap(context, bm, event, None, None, None, tool=self)
        do_copy = getattr(self, "_copy", False) or event.ctrl
        if event.type == "LEFTMOUSE" and event.value == "PRESS":
            if self._anchor is None:
                self._anchor = snap.co.copy()
                self._axis_vec = snap.normal if snap.normal.length > 0 else Vector((0.0, 0.0, 1.0))
                _status(context, "Click the reference point")
            elif self._ref is None:
                self._ref = snap.co.copy()
                _status(context, "Click destination or type degrees · Ctrl=copy · then 8x / 6/")
            else:
                angle = _signed_angle(self._anchor, self._ref, snap.co, self._axis_vec)
                _do(
                    bpy.ops.oform.rotate,
                    center=self._anchor,
                    axis=self._axis_vec,
                    angle=angle,
                    copy=do_copy,
                )
                self._anchor = None
                self._ref = None
                self._buf = ""
                set_preview([])
                _measure(context, "")
                _status(
                    context,
                    "Array: type 8x or 6/ then Enter" if do_copy else "Click the rotation center",
                )
            return {"RUNNING_MODAL"}
        if handled == {"APPLY"} and self._anchor is not None and self._ref is not None and self._buf.strip():
            if poweruser.parse_array_token(self._buf):
                return {"RUNNING_MODAL"}
            try:
                angle = math.radians(_parse_length(self._buf, context))
            except ValueError:
                return {"RUNNING_MODAL"}
            _do(
                bpy.ops.oform.rotate,
                center=self._anchor,
                axis=self._axis_vec,
                angle=angle,
                copy=do_copy,
            )
            self._anchor = None
            self._ref = None
            self._buf = ""
            set_preview([])
            _measure(context, "")
            return {"RUNNING_MODAL"}
        if self._anchor is not None and self._ref is not None:
            set_preview([self._ref, self._anchor, snap.co])
            angle = _signed_angle(self._anchor, self._ref, snap.co, self._axis_vec)
            _measure(context, "{:.1f}".format(math.degrees(angle)))
        elif self._anchor is not None:
            set_preview([self._anchor, snap.co])
        return {"RUNNING_MODAL"}


class OFORM_OT_tool_scale(Operator, _Tool):
    bl_idname = "oform.tool_scale"
    bl_label = "Scale"

    def invoke(self, context, _event):
        self._base = None
        return self._start(context, "Click to set the scale center")

    def modal(self, context, event):
        handled = self._event(context, event)
        if handled in ({"FINISHED"}, {"PASS_THROUGH"}):
            return handled
        obj, bm = _edit(context)
        if event.type == "LEFTMOUSE" and event.value == "PRESS" and not geom.selected_verts(bm):
            _pick_select(context, bm, _mouse(event), False)
            _commit(obj)
        snap = _snap(context, bm, event, None, None, None)
        if event.type == "LEFTMOUSE" and event.value == "PRESS":
            if self._anchor is None:
                center = geom.selection_center(bm) if geom.selected_verts(bm) else snap.co
                self._anchor = center.copy()
                self._base = max((snap.co - self._anchor).length, 0.1)
                _status(context, "Move to scale, or type a factor")
            else:
                factor = (snap.co - self._anchor).length / self._base
                _do(bpy.ops.oform.scale, 
                    center=self._anchor,
                    factor=factor,
                    axis_name=self._axis or "",
                )
                self._anchor = None
                self._buf = ""
                _measure(context, "")
                _status(context, "Click to set the scale center")
            return {"RUNNING_MODAL"}
        if handled == {"APPLY"} and self._anchor is not None and self._buf.strip():
            try:
                factor = float(self._buf)
            except ValueError:
                return {"RUNNING_MODAL"}
            _do(bpy.ops.oform.scale, center=self._anchor, factor=factor, axis_name=self._axis or "")
            self._anchor = None
            self._buf = ""
            _measure(context, "")
            return {"RUNNING_MODAL"}
        if self._anchor is not None and self._base:
            factor = (snap.co - self._anchor).length / self._base
            _measure(context, "{:.3f}".format(factor))
        return {"RUNNING_MODAL"}


class OFORM_OT_tool_tape(Operator, _Tool):
    bl_idname = "oform.tool_tape"
    bl_label = "Tape Measure"

    def invoke(self, context, _event):
        return self._start(context, "Click the tape start. Ctrl+second click creates a guide")

    def modal(self, context, event):
        handled = self._event(context, event)
        if handled in ({"FINISHED"}, {"PASS_THROUGH"}):
            return handled
        _obj, bm = _edit(context)
        snap = _snap(context, bm, event, self._axis, self._parallel, self._anchor)
        if snap.tangent is not None:
            self._parallel = snap.tangent
        if event.type == "LEFTMOUSE" and event.value == "PRESS":
            if self._anchor is None:
                self._anchor = snap.co.copy()
                _status(context, "Click the end point. Ctrl creates a construction guide")
            else:
                _do(
                    bpy.ops.oform.tape,
                    a=self._anchor,
                    b=snap.co,
                    create_guide=event.ctrl,
                )
                self._anchor = None
                self._buf = ""
                set_preview([])
                _status(context, "Click the tape start. Ctrl+second click creates a guide")
            return {"RUNNING_MODAL"}
        if handled == {"APPLY"} and self._anchor is not None and self._buf.strip():
            try:
                length = _parse_length(self._buf, context)
            except ValueError:
                return {"RUNNING_MODAL"}
            direction = snap.co - self._anchor
            if direction.length < 1e-8:
                direction = Vector((1.0, 0.0, 0.0))
            end = self._anchor + direction.normalized() * length
            _do(bpy.ops.oform.tape, a=self._anchor, b=end, create_guide=event.ctrl)
            self._anchor = None
            self._buf = ""
            set_preview([])
            return {"RUNNING_MODAL"}
        if self._anchor is not None:
            set_preview([self._anchor, snap.co])
            _measure(context, _fmt_length((snap.co - self._anchor).length, context))
        return {"RUNNING_MODAL"}


class OFORM_OT_tool_polygon(Operator, _Tool):
    bl_idname = "oform.tool_polygon"
    bl_label = "Polygon"

    def invoke(self, context, _event):
        self._sides = 6
        self._normal = Vector((0.0, 0.0, 1.0))
        return self._start(context, "Click the polygon center. Type Ns for sides (e.g. 8s)")

    def modal(self, context, event):
        handled = self._event(context, event)
        if handled in ({"FINISHED"}, {"PASS_THROUGH"}):
            return handled
        _obj, bm = _edit(context)
        snap = _snap(
            context, bm, event, self._axis, self._parallel, self._anchor, plane=self._plane
        )
        if snap.kind == "face":
            self._normal = snap.normal.copy()
        if handled == {"APPLY"} and self._buf.strip().lower().endswith("s"):
            try:
                self._sides = max(3, int(float(self._buf[:-1])))
            except ValueError:
                return {"RUNNING_MODAL"}
            self._buf = ""
            _measure(context, "")
            _status(context, "{:d}-gon. Click center, then radius".format(self._sides))
            return {"RUNNING_MODAL"}
        if event.type == "LEFTMOUSE" and event.value == "PRESS":
            if self._anchor is None:
                self._adopt_plane(snap, bm)
                self._anchor = snap.co.copy()
                if self._plane is not None:
                    self._normal = self._plane.normal.copy()
                _status(context, "Click the radius, or type a length")
            else:
                radius = (snap.co - self._anchor).length
                _do(
                    bpy.ops.oform.polygon,
                    center=self._anchor,
                    radius=radius,
                    normal=self._normal,
                    sides=self._sides,
                )
                self._anchor = None
                self._plane = None
                self._buf = ""
                set_preview([])
                set_inference_feedback(None)
                _measure(context, "")
                _status(context, "Click the polygon center. Type Ns for sides (e.g. 8s)")
            return {"RUNNING_MODAL"}
        if handled == {"APPLY"} and self._anchor is not None and self._buf.strip():
            try:
                radius = _parse_length(self._buf, context)
            except ValueError:
                return {"RUNNING_MODAL"}
            _do(
                bpy.ops.oform.polygon,
                center=self._anchor,
                radius=radius,
                normal=self._normal,
                sides=self._sides,
            )
            self._anchor = None
            self._plane = None
            self._buf = ""
            set_preview([])
            set_inference_feedback(None)
            return {"RUNNING_MODAL"}
        if self._anchor is not None:
            radius = (snap.co - self._anchor).length
            pts = geom.polygon_points(self._anchor, radius, self._normal, self._sides)
            if pts:
                set_preview(pts + [pts[0]])
            _measure(context, _fmt_length(radius, context))
        return {"RUNNING_MODAL"}


class OFORM_OT_tool_freehand(Operator, _Tool):
    bl_idname = "oform.tool_freehand"
    bl_label = "Freehand"

    def invoke(self, context, _event):
        self._drawing = False
        self._stroke = []
        return self._start(context, "Drag to draw a freehand curve (Shift+L)")

    def modal(self, context, event):
        handled = self._event(context, event)
        if handled in ({"FINISHED"}, {"PASS_THROUGH"}):
            return handled
        _obj, bm = _edit(context)
        snap = _snap(context, bm, event, self._axis, self._parallel, None)
        if event.type == "LEFTMOUSE" and event.value == "PRESS":
            self._drawing = True
            self._stroke = [snap.co.copy()]
            return {"RUNNING_MODAL"}
        if event.type == "MOUSEMOVE" and self._drawing:
            if not self._stroke or (snap.co - self._stroke[-1]).length > 0.02:
                self._stroke.append(snap.co.copy())
                set_preview(self._stroke)
            return {"RUNNING_MODAL"}
        if event.type == "LEFTMOUSE" and event.value == "RELEASE" and self._drawing:
            self._drawing = False
            global _FREEHAND_BUF
            _FREEHAND_BUF = list(self._stroke)
            if len(_FREEHAND_BUF) >= 2:
                _do(bpy.ops.oform.freehand)
            self._stroke = []
            set_preview([])
            _status(context, "Drag to draw a freehand curve (Shift+L)")
            return {"RUNNING_MODAL"}
        return {"RUNNING_MODAL"}


class OFORM_OT_tool_follow_me(Operator, _Tool):
    bl_idname = "oform.tool_follow_me"
    bl_label = "Follow Me"

    def invoke(self, context, _event):
        return self._start(context, "Select a path of edges, then click the profile face (J)")

    def modal(self, context, event):
        handled = self._event(context, event)
        if handled in ({"FINISHED"}, {"PASS_THROUGH"}):
            return handled
        if event.type == "LEFTMOUSE" and event.value == "PRESS":
            obj, bm = _edit(context)
            face = _face_under_mouse(context, bm, event)
            if face is None:
                _pick_select(context, bm, _mouse(event), event.shift)
                _commit(obj)
                _status(context, "Path selected. Click the face to extrude along the path")
                return {"RUNNING_MODAL"}
            path_edges = [edge for edge in bm.edges if edge.select]
            path = geom.ordered_path_coords(path_edges)
            if len(path) < 2:
                _status(context, "Select connected edges for the path first")
                return {"RUNNING_MODAL"}
            global _FOLLOW_PATH
            _FOLLOW_PATH = path
            geom._select_only_face(bm, face)
            _commit(obj)
            bm.faces.ensure_lookup_table()
            _do(bpy.ops.oform.follow_me, face_index=face.index)
            _status(context, "Select a path of edges, then click the profile face (J)")
            return {"RUNNING_MODAL"}
        return {"RUNNING_MODAL"}


class OFORM_OT_tool_protractor(Operator, _Tool):
    bl_idname = "oform.tool_protractor"
    bl_label = "Protractor"

    def invoke(self, context, _event):
        self._points = []
        return self._start(context, "Click the protractor center (X)")

    def modal(self, context, event):
        handled = self._event(context, event)
        if handled in ({"FINISHED"}, {"PASS_THROUGH"}):
            return handled
        _obj, bm = _edit(context)
        snap = _snap(context, bm, event, self._axis, self._parallel, self._points[-1] if self._points else None)
        if event.type == "LEFTMOUSE" and event.value == "PRESS":
            self._points.append(snap.co.copy())
            if len(self._points) == 1:
                _status(context, "Click the first ray")
            elif len(self._points) == 2:
                _status(context, "Click the second ray. Ctrl creates guide lines")
            else:
                center, a, b = self._points
                angle = math.degrees(_signed_angle(center, a, b, Vector((0.0, 0.0, 1.0))))
                _measure(context, "{:.2f} deg".format(angle))
                _status(context, "Angle {:.2f} deg".format(angle))
                if event.ctrl:
                    geom.add_guide(bm, center, a)
                    geom.add_guide(bm, center, b)
                    _commit(_obj)
                self._points.clear()
                set_preview([])
                _status(context, "Click the protractor center (X)")
            return {"RUNNING_MODAL"}
        if len(self._points) == 1:
            set_preview([self._points[0], snap.co])
        elif len(self._points) == 2:
            set_preview([self._points[0], self._points[1], self._points[0], snap.co])
            angle = math.degrees(_signed_angle(self._points[0], self._points[1], snap.co, Vector((0.0, 0.0, 1.0))))
            _measure(context, "{:.2f} deg".format(angle))
        return {"RUNNING_MODAL"}


class OFORM_OT_tool_back_edges(Operator):
    bl_idname = "oform.tool_back_edges"
    bl_label = "Back Edges"

    def invoke(self, context, _event):
        space = None
        for area in context.screen.areas:
            if area.type == "VIEW_3D":
                space = area.spaces.active
                break
        if space is None:
            return {"CANCELLED"}
        overlay = getattr(space, "overlay", None)
        if overlay is not None and hasattr(overlay, "show_occlude_wire"):
            overlay.show_occlude_wire = not overlay.show_occlude_wire
            state = "on" if overlay.show_occlude_wire else "off"
            _status(context, "Back edges " + state)
        elif hasattr(space, "show_occlude_wire"):
            space.show_occlude_wire = not space.show_occlude_wire
            state = "on" if space.show_occlude_wire else "off"
            _status(context, "Back edges " + state)
        else:
            _status(context, "Back edges toggle unavailable in this viewport")
        _tool(context, self.bl_idname)
        return {"FINISHED"}


class OFORM_OT_view(Operator):
    bl_idname = "oform.view"
    bl_label = "View"
    bl_options = {"REGISTER"}

    mode: EnumProperty(
        items=(
            ("ORBIT", "Orbit", ""),
            ("PAN", "Pan", ""),
            ("ZOOM", "Zoom", ""),
            ("EXTENTS", "Zoom Extents", ""),
            ("TOP", "Top", ""),
            ("FRONT", "Front", ""),
            ("RIGHT", "Right", ""),
            ("ISO", "Iso", ""),
            ("PERSP", "Perspective", ""),
            ("ORTHO", "Parallel", ""),
        ),
        default="ORBIT",
    )

    def execute(self, context):
        override = _view3d(context)
        if override is None:
            return {"CANCELLED"}
        if self.mode in {"EXTENTS", "TOP", "FRONT", "RIGHT", "ISO", "PERSP", "ORTHO"}:
            poweruser.push_view(context)
        with context.temp_override(**override):
            if self.mode == "ORBIT":
                bpy.ops.view3d.rotate("INVOKE_DEFAULT")
            elif self.mode == "PAN":
                bpy.ops.view3d.move("INVOKE_DEFAULT")
            elif self.mode == "ZOOM":
                bpy.ops.view3d.zoom("INVOKE_DEFAULT")
            elif self.mode == "EXTENTS":
                bpy.ops.view3d.view_all(center=False)
            elif self.mode in {"TOP", "FRONT", "RIGHT"}:
                bpy.ops.view3d.view_axis(type=self.mode)
            elif self.mode == "ISO":
                rv3d = override["area"].spaces.active.region_3d
                rv3d.view_perspective = "PERSP"
                rv3d.view_rotation = __import__("mathutils").Euler(
                    (math.radians(54.736), 0.0, math.radians(45.0)), "XYZ"
                ).to_quaternion()
            elif self.mode == "PERSP":
                override["area"].spaces.active.region_3d.view_perspective = "PERSP"
            elif self.mode == "ORTHO":
                override["area"].spaces.active.region_3d.view_perspective = "ORTHO"
        return {"FINISHED"}

    def invoke(self, context, _event):
        return self.execute(context)


class OFORM_OT_tool_orbit(Operator):
    bl_idname = "oform.tool_orbit"
    bl_label = "Orbit"

    def invoke(self, context, _event):
        bpy.ops.oform.view(mode="ORBIT")
        _tool(context, self.bl_idname)
        _status(context, "Drag to orbit. Shift+middle mouse pans")
        return {"FINISHED"}


class OFORM_OT_tool_pan(Operator):
    bl_idname = "oform.tool_pan"
    bl_label = "Pan"

    def invoke(self, context, _event):
        bpy.ops.oform.view(mode="PAN")
        _tool(context, self.bl_idname)
        return {"FINISHED"}


class OFORM_OT_tool_zoom(Operator):
    bl_idname = "oform.tool_zoom"
    bl_label = "Zoom"

    def invoke(self, context, _event):
        bpy.ops.oform.view(mode="ZOOM")
        _tool(context, self.bl_idname)
        return {"FINISHED"}


class OFORM_OT_tool_zoom_extents(Operator):
    bl_idname = "oform.tool_zoom_extents"
    bl_label = "Zoom Extents"

    def invoke(self, context, _event):
        bpy.ops.oform.view(mode="EXTENTS")
        _tool(context, self.bl_idname)
        return {"FINISHED"}


def _face_under_mouse(context, bm, event):
    from bpy_extras import view3d_utils
    from mathutils.bvhtree import BVHTree

    if not bm.faces:
        return None
    mouse = _mouse(event)
    region = context.region
    rv3d = context.region_data
    origin = view3d_utils.region_2d_to_origin_3d(region, rv3d, mouse)
    direction = view3d_utils.region_2d_to_vector_3d(region, rv3d, mouse)
    tree = BVHTree.FromBMesh(bm)
    _hit, _normal, index, _dist = tree.ray_cast(origin, direction, 10000.0)
    if index is None:
        return None
    bm.faces.ensure_lookup_table()
    if 0 <= index < len(bm.faces):
        return bm.faces[index]
    return None


def _edge_under_mouse(context, bm, event):
    mouse = Vector(_mouse(event))
    best = None
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
        t = (mouse - a).dot(ab) / length_sq
        t = min(max(t, 0.0), 1.0)
        dist = (a + ab * t - mouse).length
        if dist < best_px:
            best_px = dist
            best = edge
    return best


def _pick_select(context, bm, mouse, extend):
    from bpy_extras import view3d_utils

    if not extend:
        for vert in bm.verts:
            vert.select = False
        for edge in bm.edges:
            edge.select = False
        for face in bm.faces:
            face.select = False
    chosen = None
    best = 12.0
    for vert in bm.verts:
        screen = inference._screen(context, vert.co)
        if screen is None:
            continue
        dist = (screen - Vector(mouse)).length
        if dist < best:
            best = dist
            chosen = vert
    if chosen is not None:
        chosen.select = not chosen.select if extend else True
        bm.select_flush(True)
        return
    edge = _edge_under_mouse(context, bm, _FakeEvent(mouse))
    if edge is not None:
        edge.select = not edge.select if extend else True
        for vert in edge.verts:
            vert.select = edge.select
        return
    region = context.region
    rv3d = context.region_data
    origin = view3d_utils.region_2d_to_origin_3d(region, rv3d, mouse)
    direction = view3d_utils.region_2d_to_vector_3d(region, rv3d, mouse)
    from mathutils.bvhtree import BVHTree
    if bm.faces:
        _hit, _normal, index, _dist = BVHTree.FromBMesh(bm).ray_cast(origin, direction, 10000.0)
        if index is not None:
            bm.faces.ensure_lookup_table()
            face = bm.faces[index]
            face.select = not face.select if extend else True
            for vert in face.verts:
                vert.select = face.select


class _FakeEvent:
    def __init__(self, mouse):
        self.mouse_region_x = mouse[0]
        self.mouse_region_y = mouse[1]


def _box_select(context, bm, start, end, extend):
    x0, x1 = sorted((start[0], end[0]))
    y0, y1 = sorted((start[1], end[1]))
    if not extend:
        for vert in bm.verts:
            vert.select = False
        for edge in bm.edges:
            edge.select = False
        for face in bm.faces:
            face.select = False
    for vert in bm.verts:
        screen = inference._screen(context, vert.co)
        if screen is None:
            continue
        if x0 <= screen.x <= x1 and y0 <= screen.y <= y1:
            vert.select = True
    for edge in bm.edges:
        edge.select = any(vert.select for vert in edge.verts)
    for face in bm.faces:
        face.select = any(vert.select for vert in face.verts)


def _signed_angle(center, reference, dest, axis):
    a = Vector(reference) - Vector(center)
    b = Vector(dest) - Vector(center)
    axis_v = Vector(axis).normalized()
    if a.length < 1e-8 or b.length < 1e-8:
        return 0.0
    a -= axis_v * a.dot(axis_v)
    b -= axis_v * b.dot(axis_v)
    if a.length < 1e-8 or b.length < 1e-8:
        return 0.0
    a.normalize()
    b.normalize()
    cosine = max(-1.0, min(1.0, a.dot(b)))
    angle = math.acos(cosine)
    if a.cross(b).dot(axis_v) < 0.0:
        angle = -angle
    return angle


class OFORM_OT_cancel_command(Operator):
    """Cancel the active command when no modal tool is eating Esc."""

    bl_idname = "oform.cancel_command"
    bl_label = "Cancel Command"
    bl_description = "Cancel the active command (Esc)"
    bl_options = {"REGISTER"}

    def execute(self, context):
        set_preview([])
        set_inference_feedback(None)
        _measure(context, "")
        active = _prop(context.scene, "oform_tool") or ""
        if groups.get_entity(context) is not None:
            groups.set_entity(context, None)
            _status(context, "Selection cleared")
            return {"FINISHED"}
        if groups.context_depth(context) > 0:
            groups.pop_context(context)
            _status(context, "Closed " + groups.context_object(context).name)
            return {"FINISHED"}
        if active and active != "oform.tool_select":
            _status(context, "Cancelled")
            _later("tool_select")
            return {"FINISHED"}
        _status(context, "Select a tool")
        _tool(context, "oform.tool_select")
        return {"FINISHED"}


_CLASSES = (
    OFORM_OT_cancel_command,
    OFORM_OT_rectangle,
    OFORM_OT_line_add,
    OFORM_OT_circle,
    OFORM_OT_arc,
    OFORM_OT_push_pull,
    OFORM_OT_offset,
    OFORM_OT_erase,
    OFORM_OT_delete_selection,
    OFORM_OT_move,
    OFORM_OT_rotate,
    OFORM_OT_scale,
    OFORM_OT_paint,
    OFORM_OT_polygon,
    OFORM_OT_freehand,
    OFORM_OT_tape,
    OFORM_OT_follow_me,
    OFORM_OT_soften,
    OFORM_OT_hide_edges,
    OFORM_OT_make_group,
    OFORM_OT_make_component,
    OFORM_OT_explode,
    OFORM_OT_enter_group,
    OFORM_OT_exit_group,
    OFORM_OT_instance_component,
    OFORM_OT_boolean,
    OFORM_OT_boolean_union,
    OFORM_OT_boolean_subtract,
    OFORM_OT_boolean_intersect,
    OFORM_OT_boolean_trim,
    OFORM_OT_boolean_outer_shell,
    OFORM_OT_solid_inspect,
    OFORM_OT_reverse_faces,
    OFORM_OT_delete_guides,
    OFORM_OT_hide_selected,
    OFORM_OT_unhide_last,
    OFORM_OT_unhide_all,
    OFORM_OT_hide_rest,
    OFORM_OT_copy_selection,
    OFORM_OT_paste_in_place,
    OFORM_OT_face_style,
    OFORM_OT_previous_view,
    OFORM_OT_zoom_window,
    OFORM_OT_tool_select,
    OFORM_OT_tool_eraser,
    OFORM_OT_tool_paint,
    OFORM_OT_tool_line,
    OFORM_OT_tool_arc,
    OFORM_OT_tool_rectangle,
    OFORM_OT_tool_circle,
    OFORM_OT_tool_polygon,
    OFORM_OT_tool_freehand,
    OFORM_OT_tool_push_pull,
    OFORM_OT_tool_offset,
    OFORM_OT_tool_follow_me,
    OFORM_OT_tool_tape,
    OFORM_OT_tool_protractor,
    OFORM_OT_tool_move,
    OFORM_OT_tool_rotate,
    OFORM_OT_tool_scale,
    OFORM_OT_tool_back_edges,
    OFORM_OT_view,
    OFORM_OT_tool_orbit,
    OFORM_OT_tool_pan,
    OFORM_OT_tool_zoom,
    OFORM_OT_tool_zoom_extents,
)


# Tooltips for icon-only Large Tool Set buttons (bl_description → hover / a11y).
_TOOL_DESCRIPTIONS = {
    "oform.tool_line": "Draw edges. Type a length, Enter. Arrow keys lock axes",
    "oform.tool_rectangle": "Draw a rectangle on the working plane",
    "oform.tool_circle": "Draw a circle. Type segments as 24s, then radius",
    "oform.tool_arc": "Draw an arc with three clicks",
    "oform.tool_polygon": "Regular polygon. Type 8s for sides before radius",
    "oform.tool_freehand": "Sketch a freehand curve",
    "oform.tool_push_pull": "Extrude a face. Ctrl copies. Double-click repeats last",
    "oform.tool_follow_me": "Extrude a face along a path",
    "oform.tool_offset": "Offset edges of a face",
    "oform.tool_move": "Move. Ctrl copies. After copy type 5x or 3/ for arrays",
    "oform.tool_rotate": "Rotate. Ctrl copies. After copy type 8x or 6/ for circular arrays",
    "oform.tool_scale": "Scale selection",
    "oform.tool_eraser": "Erase edges and faces. Ctrl soften, Shift hide",
    "oform.tool_paint": "Paint faces with the current material colour",
    "oform.tool_tape": "Measure distance. Ctrl creates a guide",
    "oform.tool_protractor": "Measure / lock an angle. Ctrl creates guides",
    "oform.tool_back_edges": "Toggle seeing edges behind faces",
    "oform.tool_orbit": "Orbit the camera (also middle mouse)",
    "oform.tool_pan": "Pan the camera (also Shift+middle mouse)",
    "oform.tool_zoom": "Zoom the camera (also mouse wheel)",
    "oform.tool_zoom_extents": "Frame all geometry",
    "oform.make_component": "Make a component from the selection (G)",
    "oform.make_group": "Make a group from the selection (Ctrl+G)",
}


def register():
    global _PREVIEW_HANDLE, _LABEL_HANDLE
    for cls in _CLASSES:
        desc = _TOOL_DESCRIPTIONS.get(getattr(cls, "bl_idname", ""))
        if desc:
            cls.bl_description = desc
        if getattr(cls, "is_registered", False):
            continue
        bpy.utils.register_class(cls)
    if bpy.app.background:
        return
    if _PREVIEW_HANDLE is None:
        _PREVIEW_HANDLE = bpy.types.SpaceView3D.draw_handler_add(
            _draw_tool_preview, (), "WINDOW", "POST_VIEW"
        )
    if _LABEL_HANDLE is None:
        _LABEL_HANDLE = bpy.types.SpaceView3D.draw_handler_add(
            _draw_snap_label, (), "WINDOW", "POST_PIXEL"
        )


def unregister():
    global _PREVIEW_HANDLE, _LABEL_HANDLE
    if _LABEL_HANDLE is not None:
        try:
            bpy.types.SpaceView3D.draw_handler_remove(_LABEL_HANDLE, "WINDOW")
        except Exception:
            pass
        _LABEL_HANDLE = None
    if _PREVIEW_HANDLE is not None:
        try:
            bpy.types.SpaceView3D.draw_handler_remove(_PREVIEW_HANDLE, "WINDOW")
        except Exception:
            pass
        _PREVIEW_HANDLE = None
    for cls in reversed(_CLASSES):
        if getattr(cls, "is_registered", False):
            bpy.utils.unregister_class(cls)
