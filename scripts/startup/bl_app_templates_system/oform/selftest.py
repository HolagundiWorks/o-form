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

    # SketchUp-style polygon action (regular hex).
    result = bpy.ops.oform.polygon(
        True,
        center=(0.0, 0.0, 0.0),
        radius=1.0,
        normal=(0.0, 0.0, 1.0),
        sides=6,
    )
    if "FINISHED" not in result:
        _fail("polygon returned " + str(set(result)))

    # Groups / components: select all faces, make component, enter, exit, explode.
    import bmesh
    import groups as groups_mod

    bm = bmesh.from_edit_mesh(obj.data)
    for face in bm.faces:
        face.select = True
    for edge in bm.edges:
        edge.select = True
    for vert in bm.verts:
        vert.select = True
    bmesh.update_edit_mesh(obj.data)

    result = bpy.ops.oform.make_component(True, definition="SelftestComp")
    if "FINISHED" not in result:
        _fail("make_component returned " + str(set(result)))
    entity = groups_mod.get_entity(bpy.context)
    if entity is None:
        _fail("make_component did not select the new component")
    if groups_mod.kind_of(entity) != groups_mod.KIND_COMPONENT:
        _fail("new object is not a component")

    result = bpy.ops.oform.enter_group(True)
    if "FINISHED" not in result:
        _fail("enter_group returned " + str(set(result)))
    if groups_mod.context_depth(bpy.context) < 1:
        _fail("enter_group did not push context")
    if groups_mod.context_object(bpy.context) != entity:
        _fail("enter_group did not activate the component")

    result = bpy.ops.oform.exit_group(True)
    if "FINISHED" not in result:
        _fail("exit_group returned " + str(set(result)))
    if groups_mod.context_depth(bpy.context) != 0:
        _fail("exit_group did not restore root context")

    entity_name = entity.name
    groups_mod.set_entity(bpy.context, entity)
    result = bpy.ops.oform.explode(True)
    if "FINISHED" not in result:
        _fail("explode returned " + str(set(result)))
    if bpy.data.objects.get(entity_name) is not None:
        _fail("explode left the component object behind")

    # Theme + Ask (O-Draft shell).
    import ai as ask
    import brand

    result = bpy.ops.oform.toggle_theme(True, mode="DARK")
    if "FINISHED" not in result:
        _fail("toggle_theme dark returned " + str(set(result)))
    if not brand.is_dark(bpy.context):
        _fail("dark theme flag not set")
    result = bpy.ops.oform.toggle_theme(True, mode="LIGHT")
    if "FINISHED" not in result:
        _fail("toggle_theme light returned " + str(set(result)))
    phase, _msg = ask.propose(bpy.context, "model summary")
    if phase != "idle":
        _fail("ask summary should be idle, got " + phase)

    # Working plane + selection + solids foundation.
    import inference
    import selection
    import solids
    from mathutils import Vector

    plane = inference.WorkingPlane(Vector((0, 0, 1)), Vector((0, 0, 1)), "face")
    hit = inference.ray_plane_intersect(
        Vector((0, 0, 5)), Vector((0, 0, -1)), plane
    )
    if hit is None or abs(hit.z - 1.0) > 1e-5:
        _fail("ray_plane_intersect failed: " + str(hit))

    tracker = selection.ClickTracker()
    if tracker.register((10, 10)) != 1:
        _fail("ClickTracker first click should be 1")
    if tracker.register((10, 10)) != 2:
        _fail("ClickTracker second click should be 2")
    if tracker.register((10, 10)) != 3:
        _fail("ClickTracker third click should be 3")

    # Two unit cubes → Boolean union must succeed.
    bpy.ops.object.mode_set(mode="OBJECT")
    bpy.ops.mesh.primitive_cube_add(size=2.0, location=(0.0, 0.0, 0.0))
    cube_a = bpy.context.view_layer.objects.active
    bpy.ops.mesh.primitive_cube_add(size=2.0, location=(1.0, 0.0, 0.0))
    cube_b = bpy.context.view_layer.objects.active
    cube_a.select_set(True)
    cube_b.select_set(True)
    bpy.context.view_layer.objects.active = cube_a
    ok, message = solids.boolean_objects(bpy.context, cube_a, cube_b, "UNION")
    if not ok:
        _fail("boolean union failed: " + message)
    if not hasattr(bpy.ops.oform, "boolean_union"):
        _fail("oform.boolean_union was not registered")


def main():
    import bpy

    _load_template()
    if not hasattr(bpy.ops.oform, "rectangle"):
        _fail("oform.rectangle was not registered")
    for name in (
        "polygon",
        "tape",
        "follow_me",
        "freehand",
        "tool_tape",
        "make_component",
        "make_group",
        "explode",
        "enter_group",
        "exit_group",
        "toggle_theme",
        "ask_submit",
        "boolean",
        "boolean_union",
        "boolean_subtract",
        "boolean_intersect",
        "solid_inspect",
        "delete_selection",
    ):
        if not hasattr(bpy.ops.oform, name):
            _fail("oform." + name + " was not registered")

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
