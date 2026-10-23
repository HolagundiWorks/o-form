# SPDX-FileCopyrightText: 2026 O-Form Authors
#
# SPDX-License-Identifier: GPL-2.0-or-later

"""Headless mesh check for the O-Form tools.

Run with:
  oform.exe --background --factory-startup --python selftest.py
"""

import os
import sys
import traceback


def _fail(message):
    print("OFORM_SELFTEST_FAIL: " + message, file=sys.stderr, flush=True)
    raise SystemExit(1)


def _load_template():
    import importlib
    import importlib.util

    here = os.path.dirname(os.path.abspath(__file__))
    startup = os.path.dirname(os.path.dirname(here))
    if startup not in sys.path:
        sys.path.insert(0, startup)
    if here not in sys.path:
        sys.path.insert(0, here)
    try:
        module = importlib.import_module("bl_app_templates_system.oform")
    except ModuleNotFoundError:
        module = None
        for name, candidate in list(sys.modules.items()):
            if name.endswith("oform") and hasattr(candidate, "register"):
                module = candidate
                break
        if module is None:
            spec = importlib.util.spec_from_file_location(
                "oform", os.path.join(here, "__init__.py")
            )
            module = importlib.util.module_from_spec(spec)
            sys.modules["oform"] = module
            spec.loader.exec_module(module)
    module.register()
    return module


def _override():
    import bpy

    context = bpy.context
    window = context.window
    if window is None and len(context.window_manager.windows):
        window = context.window_manager.windows[0]
    if window is None:
        return None
    screen = window.screen
    area = next((item for item in screen.areas if item.type == "VIEW_3D"), None)
    if area is None and len(screen.areas):
        area = screen.areas[0]
    region = None
    if area is not None:
        region = next((item for item in area.regions if item.type == "WINDOW"), None)
    values = {"window": window, "screen": screen}
    if area is not None:
        values["area"] = area
    if region is not None:
        values["region"] = region
    return context.temp_override(**values)


def _zs(obj):
    import bmesh

    if obj.mode == "EDIT":
        bm = bmesh.from_edit_mesh(obj.data)
        bm.verts.ensure_lookup_table()
        return [vert.co.z for vert in bm.verts]
    return [vert.co.z for vert in obj.data.vertices]


def _mesh_report(obj):
    import bmesh

    if obj.mode != "EDIT":
        return 0, 0.0
    bm = bmesh.from_edit_mesh(obj.data)
    bm.faces.ensure_lookup_table()
    area = sum(face.calc_area() for face in bm.faces)
    return len(bm.faces), area


def _prepare():
    import bmesh
    import bpy

    view_layer = bpy.context.view_layer
    active = view_layer.objects.active
    if active is not None and getattr(active, "mode", "OBJECT") != "OBJECT":
        try:
            bpy.ops.object.mode_set(mode="OBJECT")
        except RuntimeError as exc:
            _fail("could not leave edit mode: " + str(exc))

    obj = bpy.data.objects.get("Model")
    if obj is None or obj.type != "MESH":
        mesh = bpy.data.meshes.new("Model")
        obj = bpy.data.objects.new("Model", mesh)
        bpy.context.scene.collection.objects.link(obj)
    if obj.name not in view_layer.objects:
        try:
            bpy.context.scene.collection.objects.link(obj)
        except RuntimeError:
            pass
    for other in list(view_layer.objects):
        other.select_set(other == obj)
    view_layer.objects.active = obj
    if obj.mode != "EDIT":
        result = bpy.ops.object.mode_set(mode="EDIT")
        if "FINISHED" not in result:
            _fail("mode_set returned " + str(set(result)))
    bm = bmesh.from_edit_mesh(obj.data)
    if bm.verts:
        bmesh.ops.delete(bm, geom=list(bm.verts), context="VERTS")
        bmesh.update_edit_mesh(obj.data)
    # Background mode does not create an undo stack until this runs.
    result = bpy.ops.ed.undo_push(message="O-Form selftest")
    if "FINISHED" not in result:
        _fail("undo_push returned " + str(set(result)))
    return obj


def _run(obj):
    import bpy

    result = bpy.ops.oform.rectangle(
        True,
        corner_a=(0.0, 0.0, 0.0),
        corner_b=(4.0, 3.0, 0.0),
        normal=(0.0, 0.0, 1.0),
    )
    if "FINISHED" not in result:
        _fail("rectangle returned " + str(set(result)))
    result = bpy.ops.oform.rectangle(
        True,
        corner_a=(1.0, 1.0, 0.0),
        corner_b=(2.0, 2.0, 0.0),
        normal=(0.0, 0.0, 1.0),
    )
    if "FINISHED" not in result:
        _fail("inner rectangle returned " + str(set(result)))

    count, area = _mesh_report(obj)
    if count < 2:
        _fail("inner rectangle did not split the face (polygons=%d, area=%.4f)" % (count, area))
    if abs(area - 12.0) > 0.05:
        _fail("face area is %.4f, expected about 12" % area)

    result = bpy.ops.oform.push_pull(True, distance=1.5, face_index=-1)
    if "FINISHED" not in result:
        _fail("push_pull returned " + str(set(result)))
    heights = _zs(obj)
    if not any(height > 1.0 for height in heights):
        _fail("push/pull did not raise a vertex: " + str(heights))
    if not any(abs(height) < 1e-3 for height in heights):
        _fail("push/pull moved every vertex off the ground: " + str(heights))

    result = bpy.ops.ed.undo()
    if "FINISHED" not in result:
        _fail("undo returned " + str(set(result)))
    bpy.context.view_layer.update()
    obj = bpy.data.objects.get("Model")
    if obj is None:
        _fail("undo removed Model")
    heights = _zs(obj)
    if not heights or any(abs(height) > 1e-3 for height in heights):
        _fail("undo did not restore z=0: " + str(heights))


def main():
    import bpy

    _load_template()
    if not hasattr(bpy.ops.oform, "rectangle"):
        _fail("oform.rectangle was not registered")

    override = _override()
    if override is None:
        _prepare()
        _run(bpy.data.objects["Model"])
    else:
        with override:
            obj = _prepare()
            _run(obj)
    print("OFORM_SELFTEST_OK", flush=True)
    raise SystemExit(0)


if __name__ == "__main__":
    try:
        main()
    except SystemExit:
        raise
    except Exception:
        traceback.print_exc()
        raise SystemExit(1)
