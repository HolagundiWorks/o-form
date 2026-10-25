# SPDX-FileCopyrightText: 2026 O-Form Authors
#
# SPDX-License-Identifier: GPL-2.0-or-later

"""File exchange: OBJ, DXF, and best-effort SKP/DWG.

OBJ uses Blender's importer. DXF reads and writes lines, polylines, circles,
arcs, and 3D faces. Binary DWG and SketchUp SKP are recognized; ASCII DXF
payloads inside those names are imported as DXF.
"""

from __future__ import annotations

import math
import os

import bpy
from bpy.props import StringProperty
from bpy.types import Operator

_CLASSES = []


def _register(cls):
    _CLASSES.append(cls)
    return cls


def _pairs(text):
    lines = text.replace("\r\n", "\n").replace("\r", "\n").split("\n")
    index = 0
    while index + 1 < len(lines):
        raw = lines[index].strip()
        value = lines[index + 1].rstrip()
        index += 2
        try:
            yield int(raw), value.strip()
        except ValueError:
            continue


def _as_float(value, default=0.0):
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _entities(text):
    """Yield entity dicts from an ASCII DXF ENTITIES section."""
    in_entities = False
    expect_name = False
    current = None
    for code, value in _pairs(text):
        if code == 0 and value == "SECTION":
            expect_name = True
            continue
        if expect_name and code == 2:
            in_entities = value == "ENTITIES"
            expect_name = False
            continue
        if code == 0 and value == "ENDSEC":
            if current is not None and in_entities:
                yield current
                current = None
            in_entities = False
            continue
        if not in_entities:
            continue
        if code == 0:
            if current is not None:
                yield current
            current = {"kind": value, "nums": {}}
            continue
        if current is None:
            continue
        bucket = current["nums"].setdefault(code, [])
        bucket.append(value)
    if current is not None and in_entities:
        yield current


def _num(entity, code, index=0, default=0.0):
    values = entity["nums"].get(code) or []
    if index >= len(values):
        return default
    return _as_float(values[index], default)


def _points_from_codes(entity, codes):
    count = max((len(entity["nums"].get(code, ())) for code in codes), default=0)
    points = []
    for index in range(count):
        points.append(
            (
                _num(entity, codes[0], index),
                _num(entity, codes[1], index),
                _num(entity, codes[2], index) if len(codes) > 2 else 0.0,
            )
        )
    return points


def _circle(center, radius, segments, start=0.0, sweep=None):
    if radius <= 0.0:
        return []
    span = math.tau if sweep is None else sweep
    points = []
    steps = max(int(segments), 8)
    for step in range(steps + (0 if sweep is None else 1)):
        angle = start + span * (step / float(steps))
        points.append(
            (
                center[0] + radius * math.cos(angle),
                center[1] + radius * math.sin(angle),
                center[2],
            )
        )
    return points


def _entity_geometry(entity):
    """Return (loops, faces) in metres-as-file-units."""
    kind = entity["kind"]
    loops = []
    faces = []
    if kind == "LINE":
        start = (_num(entity, 10), _num(entity, 20), _num(entity, 30))
        end = (_num(entity, 11), _num(entity, 21), _num(entity, 31))
        loops.append([start, end])
    elif kind == "LWPOLYLINE":
        xs = entity["nums"].get(10) or []
        ys = entity["nums"].get(20) or []
        elevation = _num(entity, 38)
        points = [
            (_as_float(x), _as_float(ys[index]) if index < len(ys) else 0.0, elevation)
            for index, x in enumerate(xs)
        ]
        flags = int(_num(entity, 70))
        if flags & 1 and len(points) > 2:
            points.append(points[0])
        if len(points) >= 2:
            loops.append(points)
    elif kind == "POLYLINE":
        # Vertices arrive as separate VERTEX entities; handled by the caller.
        return loops, faces
    elif kind == "CIRCLE":
        center = (_num(entity, 10), _num(entity, 20), _num(entity, 30))
        points = _circle(center, _num(entity, 40), 32)
        if points:
            points.append(points[0])
            loops.append(points)
    elif kind == "ARC":
        center = (_num(entity, 10), _num(entity, 20), _num(entity, 30))
        start = math.radians(_num(entity, 50))
        end = math.radians(_num(entity, 51))
        sweep = end - start
        if sweep <= 0.0:
            sweep += math.tau
        points = _circle(center, _num(entity, 40), 24, start, sweep)
        if len(points) >= 2:
            loops.append(points)
    elif kind == "3DFACE":
        corners = []
        for code_x, code_y, code_z in ((10, 20, 30), (11, 21, 31), (12, 22, 32), (13, 23, 33)):
            if code_x not in entity["nums"]:
                continue
            corners.append((_num(entity, code_x), _num(entity, code_y), _num(entity, code_z)))
        if len(corners) >= 3:
            if len(corners) == 4 and corners[2] == corners[3]:
                corners = corners[:3]
            faces.append(corners)
    return loops, faces


def _looks_like_dxf(text):
    head = text[:4000].upper()
    return "SECTION" in head and ("ENTITIES" in head or "HEADER" in head)


def _read_text(path):
    raw = open(path, "rb").read()
    if raw.startswith(b"AC10") or raw.startswith(b"AC1") or raw.startswith(b"AC2"):
        return None
    for encoding in ("utf-8", "latin-1"):
        try:
            return raw.decode(encoding)
        except UnicodeDecodeError:
            continue
    return None


def import_dxf(context, path):
    text = _read_text(path)
    if text is None or not _looks_like_dxf(text):
        return False, "Not an ASCII DXF file"
    loops = []
    faces = []
    poly = None
    for entity in _entities(text):
        kind = entity["kind"]
        if kind == "POLYLINE":
            poly = []
            continue
        if kind == "VERTEX" and poly is not None:
            poly.append((_num(entity, 10), _num(entity, 20), _num(entity, 30)))
            continue
        if kind == "SEQEND" and poly is not None:
            if len(poly) >= 2:
                loops.append(poly)
            poly = None
            continue
        entity_loops, entity_faces = _entity_geometry(entity)
        loops.extend(entity_loops)
        faces.extend(entity_faces)
    if not loops and not faces:
        return False, "DXF has no drawable entities"
    import bmesh

    mesh = bpy.data.meshes.new("DXF")
    obj = bpy.data.objects.new(os.path.splitext(os.path.basename(path))[0] or "DXF", mesh)
    context.collection.objects.link(obj)
    bm = bmesh.new()
    index = {}

    def vert(point):
        key = (round(point[0], 6), round(point[1], 6), round(point[2], 6))
        found = index.get(key)
        if found is not None:
            return found
        created = bm.verts.new(point)
        index[key] = created
        return created

    bm.verts.ensure_lookup_table()
    for loop in loops:
        made = [vert(point) for point in loop]
        for start, end in zip(made, made[1:]):
            if start != end:
                try:
                    bm.edges.new((start, end))
                except ValueError:
                    pass
    for face in faces:
        made = [vert(point) for point in face]
        unique = []
        for item in made:
            if item not in unique:
                unique.append(item)
        if len(unique) >= 3:
            try:
                bm.faces.new(unique)
            except ValueError:
                pass
    bm.to_mesh(mesh)
    bm.free()
    mesh.update()
    return True, "Imported {} ({} edges, {} faces)".format(
        obj.name, len(mesh.edges), len(mesh.polygons)
    )


def export_dxf(context, path):
    objects = [obj for obj in context.view_layer.objects if obj.type == "MESH" and obj.visible_get()]
    if not objects:
        objects = [obj for obj in bpy.data.objects if obj.type == "MESH"]
    lines = ["0", "SECTION", "2", "ENTITIES"]
    count = 0
    import bmesh

    for obj in objects:
        bm = bmesh.new()
        bm.from_mesh(obj.data)
        bm.transform(obj.matrix_world)
        faces = [face for face in bm.faces]
        if faces:
            for face in faces:
                coords = [vert.co.copy() for vert in face.verts]
                if len(coords) < 3:
                    continue
                if len(coords) == 3:
                    coords.append(coords[-1])
                coords = coords[:4]
                lines.extend(["0", "3DFACE", "8", "0"])
                for code, coord in zip((10, 11, 12, 13), coords):
                    lines.extend(
                        [
                            str(code),
                            "{:.6f}".format(coord.x),
                            str(code + 10),
                            "{:.6f}".format(coord.y),
                            str(code + 20),
                            "{:.6f}".format(coord.z),
                        ]
                    )
                count += 1
        else:
            for edge in bm.edges:
                a, b = (vert.co for vert in edge.verts)
                lines.extend(
                    [
                        "0",
                        "LINE",
                        "8",
                        "0",
                        "10",
                        "{:.6f}".format(a.x),
                        "20",
                        "{:.6f}".format(a.y),
                        "30",
                        "{:.6f}".format(a.z),
                        "11",
                        "{:.6f}".format(b.x),
                        "21",
                        "{:.6f}".format(b.y),
                        "31",
                        "{:.6f}".format(b.z),
                    ]
                )
                count += 1
        bm.free()
    lines.extend(["0", "ENDSEC", "0", "EOF"])
    if count == 0:
        return False, "Nothing to write"
    with open(path, "w", encoding="utf-8", newline="\n") as handle:
        handle.write("\n".join(lines) + "\n")
    return True, "Exported {} entities to {}".format(count, os.path.basename(path))


def _binary_note(path, label):
    text = _read_text(path)
    if text is not None and _looks_like_dxf(text):
        return None
    return (
        "{} is a binary {} file. O-Form reads OBJ, ASCII DXF, and IFC. "
        "Save this drawing as DXF or OBJ and import that."
    ).format(os.path.basename(path), label)


def import_dwg(context, path):
    note = _binary_note(path, "DWG")
    if note is None:
        return import_dxf(context, path)
    return False, note


def import_skp(context, path):
    note = _binary_note(path, "SketchUp")
    if note is None:
        return import_dxf(context, path)
    return False, note


def _obj(operator_name, path):
    operator = getattr(bpy.ops.wm, operator_name, None)
    if operator is None:
        return False, "OBJ translator is not available"
    try:
        result = operator(filepath=path)
    except TypeError:
        result = operator(filepath=path, export_selected_objects=False)
    if "FINISHED" not in result:
        return False, "OBJ did not finish"
    return True, "OBJ " + os.path.basename(path)


def _ensure_ext(path, ext):
    if not path.lower().endswith(ext):
        return path + ext
    return path


class _Exchange(Operator):
    bl_options = {"REGISTER", "UNDO"}
    filepath: StringProperty(subtype="FILE_PATH")
    filename_ext = ""
    filter_glob: StringProperty(default="*", options={"HIDDEN"})

    def invoke(self, context, _event):
        if not self.filepath and self.filename_ext:
            self.filepath = "model" + self.filename_ext
        context.window_manager.fileselect_add(self)
        return {"RUNNING_MODAL"}

    def _finish(self, context, ok, message):
        context.scene.oform_status = message[:120]
        self.report({"INFO"} if ok else {"ERROR"}, message)
        return {"FINISHED"} if ok else {"CANCELLED"}


@_register
class OFORM_OT_import_obj(_Exchange):
    bl_idname = "oform.import_obj"
    bl_label = "Import OBJ"
    bl_description = "Import a Wavefront .obj mesh"
    filename_ext = ".obj"
    filter_glob: StringProperty(default="*.obj", options={"HIDDEN"})

    def execute(self, context):
        ok, message = _obj("obj_import", self.filepath)
        return self._finish(context, ok, message)


@_register
class OFORM_OT_export_obj(_Exchange):
    bl_idname = "oform.export_obj"
    bl_label = "Export OBJ"
    bl_description = "Export the model as Wavefront .obj"
    bl_options = {"REGISTER"}
    filename_ext = ".obj"
    filter_glob: StringProperty(default="*.obj", options={"HIDDEN"})

    def execute(self, context):
        path = _ensure_ext(self.filepath, ".obj")
        ok, message = _obj("obj_export", path)
        return self._finish(context, ok, message)


@_register
class OFORM_OT_import_dxf(_Exchange):
    bl_idname = "oform.import_dxf"
    bl_label = "Import DXF"
    bl_description = "Import ASCII DXF lines, polylines, circles, arcs, and 3D faces"
    filename_ext = ".dxf"
    filter_glob: StringProperty(default="*.dxf", options={"HIDDEN"})

    def execute(self, context):
        ok, message = import_dxf(context, self.filepath)
        return self._finish(context, ok, message)


@_register
class OFORM_OT_export_dxf(_Exchange):
    bl_idname = "oform.export_dxf"
    bl_label = "Export DXF"
    bl_description = "Write mesh faces as DXF 3DFACE entities, or edges as LINE"
    bl_options = {"REGISTER"}
    filename_ext = ".dxf"
    filter_glob: StringProperty(default="*.dxf", options={"HIDDEN"})

    def execute(self, context):
        path = _ensure_ext(self.filepath, ".dxf")
        ok, message = export_dxf(context, path)
        return self._finish(context, ok, message)


@_register
class OFORM_OT_import_dwg(_Exchange):
    bl_idname = "oform.import_dwg"
    bl_label = "Import DWG"
    bl_description = "Import a DWG drawing. ASCII DXF saved with a .dwg name is read as DXF"
    filename_ext = ".dwg"
    filter_glob: StringProperty(default="*.dwg", options={"HIDDEN"})

    def execute(self, context):
        ok, message = import_dwg(context, self.filepath)
        return self._finish(context, ok, message)


@_register
class OFORM_OT_export_dwg(_Exchange):
    bl_idname = "oform.export_dwg"
    bl_label = "Export DWG"
    bl_description = "DWG is a binary AutoCAD file. O-Form writes DXF, which DWG editors open"
    bl_options = {"REGISTER"}
    filename_ext = ".dwg"
    filter_glob: StringProperty(default="*.dwg;*.dxf", options={"HIDDEN"})

    def execute(self, context):
        path = self.filepath
        if path.lower().endswith(".dwg"):
            path = path[:-4] + ".dxf"
        path = _ensure_ext(path, ".dxf")
        ok, message = export_dxf(context, path)
        if ok:
            message = "Wrote DXF (open in a DWG editor): " + os.path.basename(path)
        return self._finish(context, ok, message)


@_register
class OFORM_OT_import_skp(_Exchange):
    bl_idname = "oform.import_skp"
    bl_label = "Import SketchUp"
    bl_description = "Import a SketchUp file. ASCII DXF saved with a .skp name is read as DXF"
    filename_ext = ".skp"
    filter_glob: StringProperty(default="*.skp", options={"HIDDEN"})

    def execute(self, context):
        ok, message = import_skp(context, self.filepath)
        return self._finish(context, ok, message)


@_register
class OFORM_OT_export_skp(_Exchange):
    bl_idname = "oform.export_skp"
    bl_label = "Export SketchUp"
    bl_description = "SketchUp opens OBJ and DXF. O-Form writes DXF beside the chosen name"
    bl_options = {"REGISTER"}
    filename_ext = ".skp"
    filter_glob: StringProperty(default="*.skp;*.dxf", options={"HIDDEN"})

    def execute(self, context):
        path = self.filepath
        if path.lower().endswith(".skp"):
            path = path[:-4] + ".dxf"
        path = _ensure_ext(path, ".dxf")
        ok, message = export_dxf(context, path)
        if ok:
            message = "Wrote DXF for SketchUp: " + os.path.basename(path)
        return self._finish(context, ok, message)


def register():
    for cls in _CLASSES:
        if not getattr(cls, "is_registered", False):
            bpy.utils.register_class(cls)


def unregister():
    for cls in reversed(_CLASSES):
        if getattr(cls, "is_registered", False):
            bpy.utils.unregister_class(cls)
