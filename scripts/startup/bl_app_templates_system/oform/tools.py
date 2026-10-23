# SPDX-FileCopyrightText: 2026 O-Form Authors
#
# SPDX-License-Identifier: GPL-2.0-or-later

"""SketchUp-style tools. Action operators record undo. Modal tools stay active."""

import math
import os
import sys

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
from mathutils import Vector

_HERE = os.path.dirname(os.path.abspath(__file__))
if _HERE not in sys.path:
    sys.path.insert(0, _HERE)

import geom
import inference

preview_points = []

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
    "O": "tool_orbit",
    "H": "tool_pan",
    "Z": "tool_zoom",
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
    global preview_points
    preview_points = [Vector(p) for p in points]


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
    scene = context.scene
    obj = scene.objects.get("Model")
    if obj is None or obj.type != "MESH":
        mesh = bpy.data.meshes.new("Model")
        obj = bpy.data.objects.new("Model", mesh)
        scene.collection.objects.link(obj)
    view_layer = context.view_layer
    for other in list(view_layer.objects):
        if other is None:
            continue
        other.select_set(other == obj)
    view_layer.objects.active = obj
    if obj.mode != "EDIT":
        bpy.ops.object.mode_set(mode="EDIT")
    context.tool_settings.mesh_select_mode = (True, True, True)
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


def _parse_length(text):
    raw = text.strip().lower().replace(" ", "")
    if not raw:
        raise ValueError("empty")
    factor = 1.0
    for suffix, scale in (("mm", 0.001), ("cm", 0.01), ("m", 1.0)):
        if raw.endswith(suffix):
            raw = raw[: -len(suffix)]
            factor = scale
            break
    return float(raw) * factor


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
        if op is not None:
            try:
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
        _status(context, status)
        _measure(context, "")
        set_preview([])
        # mode_set has to finish before the modal handler exists. Calling it
        # from a modal event runs inside the handler and skips the undo step.
        _edit(context)
        context.window_manager.modal_handler_add(self)
        return {"RUNNING_MODAL"}

    def _event(self, context, event):
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
        if event.type in {"ESC", "RIGHTMOUSE"} and event.value == "PRESS":
            self._points.clear()
            self._anchor = None
            self._buf = ""
            set_preview([])
            _measure(context, "")
            _status(context, self._idle_status())
            return {"RUNNING_MODAL"}
        if event.value == "PRESS" and not event.ctrl and not event.alt:
            if event.type == "Z" and event.shift:
                _later("tool_zoom_extents")
                set_preview([])
                return {"FINISHED"}
            name = TOOL_KEYS.get(event.type)
            if name and not event.shift:
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
        if event.value == "PRESS" and event.unicode and event.unicode in "0123456789.,-sSmMcC ":
            self._buf += event.unicode
            _measure(context, self._buf)
            return {"RUNNING_MODAL"}
        if event.value == "PRESS" and event.type in {"RET", "NUMPAD_ENTER"}:
            return {"APPLY"}
        return None

    def _idle_status(self):
        return "Choose a point"


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

    def execute(self, context):
        _obj, bm = _edit(context)
        face = geom.selected_face(bm, self.face_index)
        geom.push_pull(bm, face, self.distance)
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


class OFORM_OT_move(Operator):
    bl_idname = "oform.move"
    bl_label = "Move"
    bl_options = {"UNDO"}

    delta: FloatVectorProperty(size=3)
    copy: BoolProperty(default=False)

    def execute(self, context):
        _obj, bm = _edit(context)
        if self.copy:
            geom.duplicate_selected(bm)
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

    def execute(self, context):
        _obj, bm = _edit(context)
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


# ---------------------------------------------------------------------------
# Modal tools.
# ---------------------------------------------------------------------------


def _snap(context, bm, event, axis, parallel, anchor):
    return inference.infer(
        context,
        bm,
        _mouse(event),
        axis=axis,
        parallel=parallel,
        anchor=anchor,
    )


class OFORM_OT_tool_line(Operator, _Tool):
    bl_idname = "oform.tool_line"
    bl_label = "Line"

    def invoke(self, context, _event):
        if context.area is None or context.area.type != "VIEW_3D":
            return {"CANCELLED"}
        self._segments = 0
        return self._arm(context, "Click to set the first point")

    def modal(self, context, event):
        handled = self._event(context, event)
        if handled in ({"FINISHED"}, {"PASS_THROUGH"}):
            return handled
        if handled == {"RUNNING_MODAL"} and event.type in {"ESC", "RIGHTMOUSE"}:
            self._segments = 0
            return handled
        _obj, bm = _edit(context)
        anchor = self._points[-1] if self._points else None
        snap = _snap(context, bm, event, self._axis, self._parallel, anchor)
        if snap.tangent is not None:
            self._parallel = snap.tangent
        if event.type == "LEFTMOUSE" and event.value == "PRESS":
            self._points.append(snap.co.copy())
            if len(self._points) >= 2:
                _do(bpy.ops.oform.line_add, a=self._points[-2], b=self._points[-1])
                self._segments += 1
                _status(context, "Click the next point, or type a length")
            else:
                _status(context, "Click the next point, or type a length")
            return {"RUNNING_MODAL"}
        if handled == {"APPLY"} and self._points and self._buf.strip():
            try:
                length = _parse_length(self._buf)
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
            _measure(context, "{:.3f}".format((snap.co - self._points[-1]).length))
        return {"RUNNING_MODAL"}


class OFORM_OT_tool_rectangle(Operator, _Tool):
    bl_idname = "oform.tool_rectangle"
    bl_label = "Rectangle"

    def invoke(self, context, _event):
        if context.area is None or context.area.type != "VIEW_3D":
            return {"CANCELLED"}
        return self._arm(context, "Click to set the first corner")

    def modal(self, context, event):
        handled = self._event(context, event)
        if handled in ({"FINISHED"}, {"PASS_THROUGH"}):
            return handled
        _obj, bm = _edit(context)
        anchor = self._anchor
        snap = _snap(context, bm, event, self._axis, self._parallel, anchor)
        if snap.tangent is not None:
            self._parallel = snap.tangent
        if event.type == "LEFTMOUSE" and event.value == "PRESS":
            if self._anchor is None:
                self._anchor = snap.co.copy()
                self._normal = snap.normal.copy()
                _status(context, "Click the opposite corner, or type width, depth")
            else:
                _do(bpy.ops.oform.rectangle, 
                    corner_a=self._anchor, corner_b=snap.co, normal=self._normal
                )
                self._anchor = None
                self._buf = ""
                set_preview([])
                _measure(context, "")
                _status(context, "Click to set the first corner")
            return {"RUNNING_MODAL"}
        if handled == {"APPLY"} and self._anchor is not None and "," in self._buf:
            try:
                width_s, depth_s = self._buf.split(",", 1)
                width = _parse_length(width_s)
                depth = _parse_length(depth_s)
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
            self._buf = ""
            set_preview([])
            _measure(context, "")
            _status(context, "Click to set the first corner")
            return {"RUNNING_MODAL"}
        if self._anchor is not None:
            corners = geom.rectangle_corners(self._anchor, snap.co, getattr(self, "_normal", snap.normal))
            set_preview(corners + [corners[0]])
            _measure(context, "{:.3f}, {:.3f}".format(
                (corners[1] - corners[0]).length,
                (corners[3] - corners[0]).length,
            ))
        return {"RUNNING_MODAL"}


class OFORM_OT_tool_circle(Operator, _Tool):
    bl_idname = "oform.tool_circle"
    bl_label = "Circle"

    def invoke(self, context, _event):
        if context.area is None or context.area.type != "VIEW_3D":
            return {"CANCELLED"}
        self._segments = 24
        return self._arm(context, "Click to set the center")

    def modal(self, context, event):
        handled = self._event(context, event)
        if handled in ({"FINISHED"}, {"PASS_THROUGH"}):
            return handled
        _obj, bm = _edit(context)
        snap = _snap(context, bm, event, self._axis, self._parallel, self._anchor)
        raw = self._buf.strip().lower()
        if raw.endswith("s") and raw[:-1].isdigit():
            self._segments = max(3, int(raw[:-1]))
            self._buf = ""
            _status(context, "Circle segments: {}. Click the radius, or type it.".format(self._segments))
            _measure(context, "")
            return {"RUNNING_MODAL"}
        if event.type == "LEFTMOUSE" and event.value == "PRESS":
            if self._anchor is None:
                self._anchor = snap.co.copy()
                self._normal = snap.normal.copy()
                _status(context, "Click the radius, type a radius, or type 24s for segments")
            else:
                radius = (snap.co - self._anchor).length
                _do(bpy.ops.oform.circle, 
                    center=self._anchor,
                    radius=radius,
                    normal=self._normal,
                    segments=self._segments,
                )
                self._anchor = None
                set_preview([])
                _measure(context, "")
                _status(context, "Click to set the center")
            return {"RUNNING_MODAL"}
        if handled == {"APPLY"} and self._anchor is not None and self._buf.strip():
            try:
                radius = _parse_length(self._buf)
            except ValueError:
                return {"RUNNING_MODAL"}
            _do(bpy.ops.oform.circle, 
                center=self._anchor,
                radius=radius,
                normal=getattr(self, "_normal", Vector((0.0, 0.0, 1.0))),
                segments=self._segments,
            )
            self._anchor = None
            self._buf = ""
            set_preview([])
            _measure(context, "")
            _status(context, "Click to set the center")
            return {"RUNNING_MODAL"}
        if self._anchor is not None:
            pts = geom.circle_points(self._anchor, (snap.co - self._anchor).length, self._normal, self._segments)
            if pts:
                set_preview(pts + [pts[0]])
            _measure(context, "{:.3f}".format((snap.co - self._anchor).length))
        return {"RUNNING_MODAL"}


class OFORM_OT_tool_arc(Operator, _Tool):
    bl_idname = "oform.tool_arc"
    bl_label = "Arc"

    def invoke(self, context, _event):
        if context.area is None or context.area.type != "VIEW_3D":
            return {"CANCELLED"}
        return self._arm(context, "Click the arc start point")

    def modal(self, context, event):
        handled = self._event(context, event)
        if handled in ({"FINISHED"}, {"PASS_THROUGH"}):
            return handled
        _obj, bm = _edit(context)
        anchor = self._points[-1] if self._points else None
        snap = _snap(context, bm, event, self._axis, self._parallel, anchor)
        if event.type == "LEFTMOUSE" and event.value == "PRESS":
            self._points.append(snap.co.copy())
            if len(self._points) == 1:
                _status(context, "Click the arc end point")
            elif len(self._points) == 2:
                _status(context, "Click the bulge, or type a bulge distance")
            else:
                _do(bpy.ops.oform.arc, start=self._points[0], end=self._points[1], bulge=self._points[2])
                self._points.clear()
                set_preview([])
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
        if context.area is None or context.area.type != "VIEW_3D":
            return {"CANCELLED"}
        self._face_index = -1
        self._origin = None
        self._direction = Vector((0.0, 0.0, 1.0))
        return self._arm(context, "Click a face to push or pull")

    def modal(self, context, event):
        handled = self._event(context, event)
        if handled in ({"FINISHED"}, {"PASS_THROUGH"}):
            return handled
        obj, bm = _edit(context)
        if self._origin is None:
            snap = _snap(context, bm, event, None, None, None)
            if snap.kind == "face":
                _status(context, "Click the face")
        if event.type == "LEFTMOUSE" and event.value == "PRESS":
            if self._origin is None:
                face = _face_under_mouse(context, bm, event)
                if face is None:
                    return {"RUNNING_MODAL"}
                geom._select_only_face(bm, face)
                _commit(obj)
                bm.faces.ensure_lookup_table()
                self._face_index = face.index
                self._origin = face.calc_center_median().copy()
                self._direction = face.normal.copy()
                _status(context, "Move to extrude, or type a distance")
            else:
                distance = self._distance(context, event)
                _do(bpy.ops.oform.push_pull, distance=distance, face_index=self._face_index)
                self._origin = None
                self._face_index = -1
                self._buf = ""
                _measure(context, "")
                _status(context, "Click a face to push or pull")
            return {"RUNNING_MODAL"}
        if handled == {"APPLY"} and self._origin is not None and self._buf.strip():
            try:
                distance = _parse_length(self._buf)
            except ValueError:
                return {"RUNNING_MODAL"}
            _do(bpy.ops.oform.push_pull, distance=distance, face_index=self._face_index)
            self._origin = None
            self._buf = ""
            _measure(context, "")
            _status(context, "Click a face to push or pull")
            return {"RUNNING_MODAL"}
        if self._origin is not None:
            distance = self._distance(context, event)
            _measure(context, "{:.3f}".format(distance))
        return {"RUNNING_MODAL"}

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
        if context.area is None or context.area.type != "VIEW_3D":
            return {"CANCELLED"}
        self._face_index = -1
        self._origin = None
        return self._arm(context, "Click a face to offset")

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
                distance = _parse_length(self._buf)
            except ValueError:
                return {"RUNNING_MODAL"}
            _do(bpy.ops.oform.offset, distance=distance, face_index=self._face_index)
            self._face_index = -1
            self._buf = ""
            _measure(context, "")
            return {"RUNNING_MODAL"}
        if self._origin is not None and self._face_index >= 0:
            snap = _snap(context, bm, event, None, None, self._origin)
            _measure(context, "{:.3f}".format((snap.co - self._origin).length))
        return {"RUNNING_MODAL"}


class OFORM_OT_tool_eraser(Operator, _Tool):
    bl_idname = "oform.tool_eraser"
    bl_label = "Eraser"

    def invoke(self, context, _event):
        if context.area is None or context.area.type != "VIEW_3D":
            return {"CANCELLED"}
        return self._arm(context, "Click an edge to erase it")

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
                _do(bpy.ops.oform.erase, edge_index=index)
            return {"RUNNING_MODAL"}
        return {"RUNNING_MODAL"}


class OFORM_OT_tool_paint(Operator, _Tool):
    bl_idname = "oform.tool_paint"
    bl_label = "Paint"

    def invoke(self, context, _event):
        if context.area is None or context.area.type != "VIEW_3D":
            return {"CANCELLED"}
        if _prop(context.scene, "oform_color") is None:
            pass
        return self._arm(context, "Click a face to paint. Keys 1-8 pick a color")

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

    def invoke(self, context, _event):
        if context.area is None or context.area.type != "VIEW_3D":
            return {"CANCELLED"}
        self._box = None
        return self._arm(context, "Click to select. Drag a box. Shift toggles")

    def modal(self, context, event):
        handled = self._event(context, event)
        if handled in ({"FINISHED"}, {"PASS_THROUGH"}):
            return handled
        if event.type == "LEFTMOUSE" and event.value == "PRESS":
            self._box = (_mouse(event), _mouse(event), event.shift)
            return {"RUNNING_MODAL"}
        if event.type == "MOUSEMOVE" and self._box is not None:
            self._box = (self._box[0], _mouse(event), self._box[2])
            return {"RUNNING_MODAL"}
        if event.type == "LEFTMOUSE" and event.value == "RELEASE" and self._box is not None:
            start, end, extend = self._box
            self._box = None
            obj, bm = _edit(context)
            if (Vector(start) - Vector(end)).length < 4.0:
                _pick_select(context, bm, end, extend)
            else:
                _box_select(context, bm, start, end, extend)
            _commit(obj)
            return {"RUNNING_MODAL"}
        return {"RUNNING_MODAL"}


class OFORM_OT_tool_move(Operator, _Tool):
    bl_idname = "oform.tool_move"
    bl_label = "Move"

    def invoke(self, context, _event):
        if context.area is None or context.area.type != "VIEW_3D":
            return {"CANCELLED"}
        return self._arm(context, "Click a base point on the selection")

    def modal(self, context, event):
        handled = self._event(context, event)
        if handled in ({"FINISHED"}, {"PASS_THROUGH"}):
            return handled
        obj, bm = _edit(context)
        if event.type == "LEFTMOUSE" and event.value == "PRESS" and not geom.selected_verts(bm):
            _pick_select(context, bm, _mouse(event), False)
            _commit(obj)
        snap = _snap(context, bm, event, self._axis, self._parallel, self._anchor)
        if snap.tangent is not None:
            self._parallel = snap.tangent
        if event.type == "LEFTMOUSE" and event.value == "PRESS":
            if self._anchor is None:
                self._anchor = snap.co.copy()
                _status(context, "Click the destination, or type a distance. Ctrl copies")
            else:
                delta = snap.co - self._anchor
                _do(bpy.ops.oform.move, delta=delta, copy=event.ctrl)
                self._anchor = None
                self._buf = ""
                set_preview([])
                _measure(context, "")
                _status(context, "Click a base point on the selection")
            return {"RUNNING_MODAL"}
        if handled == {"APPLY"} and self._anchor is not None and self._buf.strip():
            try:
                length = _parse_length(self._buf)
            except ValueError:
                return {"RUNNING_MODAL"}
            direction = snap.co - self._anchor
            if direction.length < 1e-8:
                direction = Vector((1.0, 0.0, 0.0))
            delta = direction.normalized() * length
            _do(bpy.ops.oform.move, delta=delta, copy=event.ctrl)
            self._anchor = None
            self._buf = ""
            set_preview([])
            _measure(context, "")
            return {"RUNNING_MODAL"}
        if self._anchor is not None:
            set_preview([self._anchor, snap.co])
            _measure(context, "{:.3f}".format((snap.co - self._anchor).length))
        return {"RUNNING_MODAL"}


class OFORM_OT_tool_rotate(Operator, _Tool):
    bl_idname = "oform.tool_rotate"
    bl_label = "Rotate"

    def invoke(self, context, _event):
        if context.area is None or context.area.type != "VIEW_3D":
            return {"CANCELLED"}
        self._ref = None
        self._axis_vec = Vector((0.0, 0.0, 1.0))
        return self._arm(context, "Click the rotation center")

    def modal(self, context, event):
        handled = self._event(context, event)
        if handled in ({"FINISHED"}, {"PASS_THROUGH"}):
            return handled
        obj, bm = _edit(context)
        if event.type == "LEFTMOUSE" and event.value == "PRESS" and self._anchor is None and not geom.selected_verts(bm):
            _pick_select(context, bm, _mouse(event), False)
            _commit(obj)
        snap = _snap(context, bm, event, None, None, None)
        if event.type == "LEFTMOUSE" and event.value == "PRESS":
            if self._anchor is None:
                self._anchor = snap.co.copy()
                self._axis_vec = snap.normal if snap.normal.length > 0 else Vector((0.0, 0.0, 1.0))
                _status(context, "Click the reference point")
            elif self._ref is None:
                self._ref = snap.co.copy()
                _status(context, "Click the destination, or type degrees")
            else:
                angle = _signed_angle(self._anchor, self._ref, snap.co, self._axis_vec)
                _do(bpy.ops.oform.rotate, center=self._anchor, axis=self._axis_vec, angle=angle)
                self._anchor = None
                self._ref = None
                self._buf = ""
                set_preview([])
                _measure(context, "")
                _status(context, "Click the rotation center")
            return {"RUNNING_MODAL"}
        if handled == {"APPLY"} and self._anchor is not None and self._ref is not None and self._buf.strip():
            try:
                angle = math.radians(_parse_length(self._buf))
            except ValueError:
                return {"RUNNING_MODAL"}
            _do(bpy.ops.oform.rotate, center=self._anchor, axis=self._axis_vec, angle=angle)
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
        if context.area is None or context.area.type != "VIEW_3D":
            return {"CANCELLED"}
        self._base = None
        return self._arm(context, "Click to set the scale center")

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


_CLASSES = (
    OFORM_OT_rectangle,
    OFORM_OT_line_add,
    OFORM_OT_circle,
    OFORM_OT_arc,
    OFORM_OT_push_pull,
    OFORM_OT_offset,
    OFORM_OT_erase,
    OFORM_OT_move,
    OFORM_OT_rotate,
    OFORM_OT_scale,
    OFORM_OT_paint,
    OFORM_OT_tool_select,
    OFORM_OT_tool_eraser,
    OFORM_OT_tool_paint,
    OFORM_OT_tool_line,
    OFORM_OT_tool_arc,
    OFORM_OT_tool_rectangle,
    OFORM_OT_tool_circle,
    OFORM_OT_tool_push_pull,
    OFORM_OT_tool_offset,
    OFORM_OT_tool_move,
    OFORM_OT_tool_rotate,
    OFORM_OT_tool_scale,
    OFORM_OT_view,
    OFORM_OT_tool_orbit,
    OFORM_OT_tool_pan,
    OFORM_OT_tool_zoom,
    OFORM_OT_tool_zoom_extents,
)


def register():
    for cls in _CLASSES:
        if getattr(cls, "is_registered", False):
            continue
        bpy.utils.register_class(cls)


def unregister():
    for cls in reversed(_CLASSES):
        if getattr(cls, "is_registered", False):
            bpy.utils.unregister_class(cls)
