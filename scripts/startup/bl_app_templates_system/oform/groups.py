# SPDX-FileCopyrightText: 2026 O-Form Authors
#
# SPDX-License-Identifier: GPL-2.0-or-later

"""SketchUp-style Groups and Components.

Groups are unique mesh objects. Components share a mesh datablock so instances
update together. The edit context is the object named on the scene as
``oform_context`` (defaults to ``Model``).
"""

from __future__ import annotations

import bmesh
import bpy
from mathutils import Matrix, Vector

KIND_GROUP = "group"
KIND_COMPONENT = "component"
KIND_ROOT = "root"
PROP_KIND = "oform_kind"
PROP_DEF = "oform_definition"
CONTEXT_PROP = "oform_context"
STACK_PROP = "oform_context_stack"


def _tag(obj, kind, definition=""):
    obj[PROP_KIND] = kind
    if definition:
        obj[PROP_DEF] = definition
    elif PROP_DEF in obj:
        del obj[PROP_DEF]


def kind_of(obj):
    if obj is None:
        return ""
    return str(obj.get(PROP_KIND, KIND_ROOT if obj.name == "Model" else ""))


def is_container(obj):
    return kind_of(obj) in {KIND_GROUP, KIND_COMPONENT}


def ensure_root(context):
    scene = context.scene
    obj = scene.objects.get("Model")
    if obj is None or obj.type != "MESH":
        mesh = bpy.data.meshes.new("Model")
        obj = bpy.data.objects.new("Model", mesh)
        scene.collection.objects.link(obj)
    _tag(obj, KIND_ROOT)
    # Use ID-property access (scene.get), not getattr — these are custom props.
    if not scene.get(CONTEXT_PROP):
        scene[CONTEXT_PROP] = obj.name
    if STACK_PROP not in scene:
        scene[STACK_PROP] = []
    return obj


def context_object(context):
    scene = context.scene
    ensure_root(context)
    name = scene.get(CONTEXT_PROP, "Model") or "Model"
    obj = scene.objects.get(name)
    if obj is None or obj.type != "MESH":
        obj = ensure_root(context)
        scene[CONTEXT_PROP] = obj.name
    return obj


def set_context(context, obj):
    scene = context.scene
    if obj is None or obj.type != "MESH":
        return
    scene[CONTEXT_PROP] = obj.name
    view_layer = context.view_layer
    for other in list(view_layer.objects):
        if other is None:
            continue
        other.select_set(other == obj)
    view_layer.objects.active = obj
    if obj.mode != "EDIT":
        bpy.ops.object.mode_set(mode="EDIT")
    context.tool_settings.mesh_select_mode = (True, True, True)


def push_context(context, obj):
    scene = context.scene
    stack = list(scene.get(STACK_PROP, []))
    current = scene.get(CONTEXT_PROP, "Model")
    if current:
        stack.append(current)
    scene[STACK_PROP] = stack
    set_context(context, obj)


def pop_context(context):
    scene = context.scene
    stack = list(scene.get(STACK_PROP, []))
    if not stack:
        set_context(context, ensure_root(context))
        return ensure_root(context)
    name = stack.pop()
    scene[STACK_PROP] = stack
    obj = scene.objects.get(name) or ensure_root(context)
    set_context(context, obj)
    return obj


def context_depth(context):
    return len(list(context.scene.get(STACK_PROP, [])))


def _selected_geom(bm):
    verts = [v for v in bm.verts if v.select]
    edges = [e for e in bm.edges if e.select]
    faces = [f for f in bm.faces if f.select]
    # Include edges/faces implied by selected verts for a solid extract.
    if faces:
        return faces[:]
    if edges:
        return edges[:]
    return verts[:]


def _world_bbox_center(obj):
    corners = [obj.matrix_world @ Vector(corner) for corner in obj.bound_box]
    if not corners:
        return obj.matrix_world.translation.copy()
    acc = Vector((0.0, 0.0, 0.0))
    for corner in corners:
        acc += corner
    return acc / len(corners)


def extract_selection_to_object(context, *, kind, name_prefix, definition="", linked=False):
    """Cut the current edit selection into a new Group/Component object."""
    parent = context_object(context)
    if parent.mode != "EDIT":
        bpy.ops.object.mode_set(mode="EDIT")
    bm = bmesh.from_edit_mesh(parent.data)
    geom = _selected_geom(bm)
    if not geom:
        return None

    # Duplicate selection, then delete the original selection from the parent.
    dup = bmesh.ops.duplicate(bm, geom=geom)
    new_geom = dup.get("geom", [])
    new_verts = [ele for ele in new_geom if isinstance(ele, bmesh.types.BMVert)]
    if not new_verts:
        return None

    # Build a fresh mesh from the duplicated geometry.
    temp = bmesh.new()
    vert_map = {}
    for vert in new_verts:
        vert_map[vert] = temp.verts.new(vert.co.copy())
    temp.verts.ensure_lookup_table()
    for ele in new_geom:
        if isinstance(ele, bmesh.types.BMEdge):
            try:
                temp.edges.new((vert_map[ele.verts[0]], vert_map[ele.verts[1]]))
            except (ValueError, KeyError):
                pass
    for ele in new_geom:
        if isinstance(ele, bmesh.types.BMFace):
            try:
                temp.faces.new([vert_map[v] for v in ele.verts])
            except (ValueError, KeyError):
                pass
    temp.normal_update()

    # Origin at selection centroid (SketchUp-like local origin).
    centroid = Vector((0.0, 0.0, 0.0))
    for vert in temp.verts:
        centroid += vert.co
    centroid /= max(len(temp.verts), 1)
    for vert in temp.verts:
        vert.co -= centroid

    if definition and definition in bpy.data.meshes:
        mesh = bpy.data.meshes[definition]
        mesh.clear_geometry()
    else:
        mesh = bpy.data.meshes.new(definition or name_prefix)
    temp.to_mesh(mesh)
    mesh.update()
    mesh_name = mesh.name
    temp.free()

    # Delete original selection from parent (verts remove connected edges/faces).
    verts_to_del = set()
    for ele in geom:
        if isinstance(ele, bmesh.types.BMVert):
            verts_to_del.add(ele)
        elif isinstance(ele, bmesh.types.BMEdge):
            verts_to_del.update(ele.verts)
        elif isinstance(ele, bmesh.types.BMFace):
            verts_to_del.update(ele.verts)
    if verts_to_del:
        bmesh.ops.delete(bm, geom=list(verts_to_del), context="VERTS")
    bmesh.update_edit_mesh(parent.data)

    bpy.ops.object.mode_set(mode="OBJECT")
    obj = bpy.data.objects.new(name_prefix, mesh)
    context.scene.collection.objects.link(obj)
    obj.matrix_world = parent.matrix_world @ Matrix.Translation(centroid)
    _tag(obj, kind, mesh_name if kind == KIND_COMPONENT else "")
    obj.show_name = True

    # Stay outside the new container; keep it selected as an entity.
    set_entity(context, obj)
    set_context(context, parent)
    return obj


def set_entity(context, obj):
    scene = context.scene
    if obj is None:
        scene["oform_entity"] = ""
        return
    scene["oform_entity"] = obj.name


def get_entity(context):
    name = context.scene.get("oform_entity", "") or ""
    if not name:
        return None
    obj = context.scene.objects.get(name)
    if obj is None or not is_container(obj):
        return None
    return obj


def make_group(context):
    return extract_selection_to_object(context, kind=KIND_GROUP, name_prefix="Group")


def make_component(context, definition=""):
    def_name = (definition or "").strip() or "Component"
    base = def_name
    index = 1
    while def_name in bpy.data.meshes:
        existing = bpy.data.meshes.get(def_name)
        if existing is not None and existing.users == 0:
            break
        def_name = "{}.{:03d}".format(base, index)
        index += 1
        if index > 999:
            break
    return extract_selection_to_object(
        context,
        kind=KIND_COMPONENT,
        name_prefix=def_name,
        definition=def_name,
        linked=False,
    )


def instance_component(context, source):
    """Place another instance of a component (shared mesh)."""
    if not is_container(source) or kind_of(source) != KIND_COMPONENT:
        return None
    bpy.ops.object.mode_set(mode="OBJECT")
    inst = source.copy()
    inst.data = source.data  # linked mesh
    context.scene.collection.objects.link(inst)
    inst.location = source.location + Vector((source.dimensions.x + 0.25, 0.0, 0.0))
    _tag(inst, KIND_COMPONENT, source.get(PROP_DEF, source.data.name))
    parent = context_object(context)
    set_context(context, parent)
    return inst


def explode(context, obj):
    """Merge a group/component into the current edit context and delete it."""
    if obj is None or not is_container(obj):
        return False
    parent = context_object(context)
    if parent == obj:
        pop_context(context)
        parent = context_object(context)
    if get_entity(context) == obj:
        set_entity(context, None)
    if parent.mode == "EDIT":
        bpy.ops.object.mode_set(mode="OBJECT")

    # Apply object transform into parent local space.
    mat = parent.matrix_world.inverted() @ obj.matrix_world
    bm_src = bmesh.new()
    bm_src.from_mesh(obj.data)
    bm_src.transform(mat)

    if parent.mode != "EDIT":
        bpy.ops.object.mode_set(mode="EDIT")
    bm = bmesh.from_edit_mesh(parent.data)
    vert_map = {}
    for vert in bm_src.verts:
        vert_map[vert.index] = bm.verts.new(vert.co.copy())
    bm.verts.ensure_lookup_table()
    bm_src.edges.ensure_lookup_table()
    bm_src.faces.ensure_lookup_table()
    for edge in bm_src.edges:
        try:
            bm.edges.new((vert_map[edge.verts[0].index], vert_map[edge.verts[1].index]))
        except ValueError:
            pass
    for face in bm_src.faces:
        try:
            bm.faces.new([vert_map[v.index] for v in face.verts])
        except ValueError:
            pass
    bm.normal_update()
    bmesh.update_edit_mesh(parent.data)
    bm_src.free()

    mesh = obj.data
    bpy.data.objects.remove(obj, do_unlink=True)
    if mesh is not None and mesh.users == 0:
        bpy.data.meshes.remove(mesh)
    set_context(context, parent)
    return True


def pick_container(context, mouse):
    """Raycast oform group/component objects under the mouse."""
    from bpy_extras import view3d_utils
    from mathutils.bvhtree import BVHTree

    region = context.region
    rv3d = context.region_data
    if region is None or rv3d is None:
        return None
    origin = view3d_utils.region_2d_to_origin_3d(region, rv3d, mouse)
    direction = view3d_utils.region_2d_to_vector_3d(region, rv3d, mouse)
    best = None
    best_dist = 1e9
    current = context_object(context)
    deps = context.evaluated_depsgraph_get()
    for obj in context.scene.objects:
        if obj.type != "MESH" or not is_container(obj) or obj == current:
            continue
        eval_obj = obj.evaluated_get(deps)
        try:
            mesh = eval_obj.to_mesh()
        except RuntimeError:
            continue
        if mesh is None or (len(mesh.polygons) == 0 and len(mesh.edges) == 0):
            eval_obj.to_mesh_clear()
            continue
        bm = bmesh.new()
        bm.from_mesh(mesh)
        bm.transform(obj.matrix_world)
        tree = BVHTree.FromBMesh(bm)
        hit = tree.ray_cast(origin, direction, 10000.0)
        bm.free()
        eval_obj.to_mesh_clear()
        if hit[0] is None:
            continue
        dist = (hit[0] - origin).length
        if dist < best_dist:
            best_dist = dist
            best = obj
    return best
