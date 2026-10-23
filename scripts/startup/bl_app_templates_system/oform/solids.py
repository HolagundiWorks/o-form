# SPDX-FileCopyrightText: 2026 O-Form Authors
#
# SPDX-License-Identifier: GPL-2.0-or-later

"""Solid validation and Boolean operations for O-Form.

Operands must be closed manifold shells. Failures raise ValueError with a
safe message — callers must not corrupt source geometry.

Uses the Boolean modifier (applied) because the lite build does not ship
``bmesh.ops.boolean``.
"""

from __future__ import annotations

import bmesh
from mathutils import Matrix


def is_solid(bm):
    """True if bm looks like a closed manifold shell."""
    if not bm.faces or not bm.edges:
        return False
    for edge in bm.edges:
        if len(edge.link_faces) != 2:
            return False
    try:
        bm.normal_update()
    except Exception:
        return False
    return True


def object_is_solid(obj):
    if obj is None or obj.type != "MESH" or obj.data is None:
        return False
    bm = bmesh.new()
    bm.from_mesh(obj.data)
    ok = is_solid(bm)
    bm.free()
    return ok


def _bm_from_object(obj, matrix=None):
    bm = bmesh.new()
    bm.from_mesh(obj.data)
    if matrix is not None:
        bm.transform(matrix)
    bm.normal_update()
    return bm


def boolean_objects(context, obj_a, obj_b, operation):
    """
    Boolean two mesh objects into obj_a's mesh (in place).

    operation: 'UNION' | 'DIFFERENCE' | 'INTERSECT'
    Returns (ok: bool, message: str)
    """
    import bpy

    if obj_a is None or obj_b is None or obj_a.type != "MESH" or obj_b.type != "MESH":
        return False, "Select two mesh solids"
    if obj_a == obj_b:
        return False, "Operands must be different objects"

    op_map = {
        "UNION": "UNION",
        "DIFFERENCE": "DIFFERENCE",
        "INTERSECT": "INTERSECT",
    }
    mode = op_map.get(operation)
    if mode is None:
        return False, "Unknown Boolean operation"

    if not object_is_solid(obj_a) or not object_is_solid(obj_b):
        return False, "Both operands must be closed solids (manifold)"

    # Snapshot so a failed apply can restore the target without silent corruption.
    original = obj_a.data
    backup = original.copy()
    backup.name = original.name + "_oform_backup"
    was_edit = obj_a.mode == "EDIT"
    applied = False
    try:
        if context.mode != "OBJECT":
            bpy.ops.object.mode_set(mode="OBJECT")
        for obj in list(context.selected_objects):
            obj.select_set(False)
        obj_a.select_set(True)
        context.view_layer.objects.active = obj_a

        mod = obj_a.modifiers.new(name="OFormBoolean", type="BOOLEAN")
        mod.operation = mode
        mod.object = obj_b
        # Lite builds often lack GMP; keep the default float solver.
        bpy.ops.object.modifier_apply(modifier=mod.name)
        applied = True
    except Exception as exc:
        try:
            if "OFormBoolean" in obj_a.modifiers:
                obj_a.modifiers.remove(obj_a.modifiers["OFormBoolean"])
        except Exception:
            pass
        # Restore pre-boolean mesh.
        damaged = obj_a.data
        obj_a.data = backup
        if damaged is not original and damaged.users == 0:
            bpy.data.meshes.remove(damaged)
        if was_edit:
            try:
                bpy.ops.object.mode_set(mode="EDIT")
            except RuntimeError:
                pass
        return False, "Boolean failed: " + str(exc)

    # Success: drop the unused backup copy.
    if backup.users == 0:
        bpy.data.meshes.remove(backup)
    if was_edit:
        try:
            bpy.ops.object.mode_set(mode="EDIT")
        except RuntimeError:
            pass
    obj_a.data.update()
    return True, operation.title() + " complete"


def boolean_edit_meshes(bm_target, bm_tool, operation):
    """
    Boolean two BMesh shells via temporary objects (lite build has no
    bmesh.ops.boolean). Mutates bm_target on success.
    """
    import bpy

    if not is_solid(bm_target) or not is_solid(bm_tool):
        return False, "Both operands must be closed solids"
    mode = {"UNION": "UNION", "DIFFERENCE": "DIFFERENCE", "INTERSECT": "INTERSECT"}.get(
        operation
    )
    if mode is None:
        return False, "Unknown Boolean operation"

    mesh_a = bpy.data.meshes.new("OFormBoolA")
    mesh_b = bpy.data.meshes.new("OFormBoolB")
    obj_a = bpy.data.objects.new("OFormBoolA", mesh_a)
    obj_b = bpy.data.objects.new("OFormBoolB", mesh_b)
    try:
        bm_target.to_mesh(mesh_a)
        bm_tool.to_mesh(mesh_b)
        mesh_a.update()
        mesh_b.update()
        col = bpy.context.scene.collection
        col.objects.link(obj_a)
        col.objects.link(obj_b)
        ok, message = boolean_objects(bpy.context, obj_a, obj_b, operation)
        if not ok:
            return False, message
        bm_target.clear()
        bm_target.from_mesh(obj_a.data)
        bm_target.normal_update()
        return True, message
    finally:
        for obj in (obj_a, obj_b):
            try:
                bpy.data.objects.remove(obj, do_unlink=True)
            except Exception:
                pass
        for mesh in (mesh_a, mesh_b):
            try:
                if mesh.users == 0:
                    bpy.data.meshes.remove(mesh)
            except Exception:
                pass
