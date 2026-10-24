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

    # Ensure normals are current before the manifold check.
    for obj in (obj_a, obj_b):
        try:
            obj.data.calc_normals_split()
        except Exception:
            pass
        obj.data.update()

    if not object_is_solid(obj_a) or not object_is_solid(obj_b):
        return False, "Both operands must be closed solids (manifold)"

    # Snapshot so a failed apply can restore the target without silent corruption.
    original = obj_a.data
    backup = original.copy()
    backup.name = original.name + "_oform_backup"
    prev_active = context.view_layer.objects.active
    prev_selected = [obj for obj in context.selected_objects]
    prev_mode = context.mode
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
        # Lite builds ship without GMP — EXACT can wipe the mesh. Stay on float.
        if hasattr(mod, "solver"):
            try:
                mod.solver = "FLOAT"
            except (TypeError, ValueError):
                pass
        before_faces = len(obj_a.data.polygons)
        bpy.ops.object.modifier_apply(modifier=mod.name)
        # Reject empty / collapsed results from a bad float solve.
        if before_faces > 0 and len(obj_a.data.polygons) == 0:
            raise RuntimeError("Boolean produced an empty mesh")
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
        _restore_object_context(context, prev_active, prev_selected, prev_mode)
        return False, "Boolean failed: " + str(exc)

    # Success: drop the unused backup copy.
    if backup.users == 0:
        bpy.data.meshes.remove(backup)
    # Clean micro-gaps left by the float solver.
    try:
        bm = bmesh.new()
        bm.from_mesh(obj_a.data)
        bmesh.ops.remove_doubles(bm, verts=list(bm.verts), dist=1e-5)
        bm.to_mesh(obj_a.data)
        bm.free()
    except Exception:
        pass
    obj_a.data.update()
    _restore_object_context(context, prev_active, prev_selected, prev_mode)
    if not object_is_solid(obj_a):
        return True, operation.title() + " complete (result is not a closed solid)"
    return True, operation.title() + " complete"


def _restore_object_context(context, active, selected, mode):
    import bpy

    try:
        for obj in list(context.selected_objects):
            obj.select_set(False)
        for obj in selected:
            if obj is not None:
                try:
                    obj.select_set(True)
                except ReferenceError:
                    pass
        if active is not None:
            try:
                context.view_layer.objects.active = active
            except ReferenceError:
                pass
        if mode == "EDIT_MESH":
            bpy.ops.object.mode_set(mode="EDIT")
        elif mode == "OBJECT" and context.mode != "OBJECT":
            bpy.ops.object.mode_set(mode="OBJECT")
    except Exception:
        pass


def boolean_edit_meshes(bm_target, bm_tool, operation):
    """
    Boolean two BMesh shells via temporary objects (lite build has no
    bmesh.ops.boolean). Mutates bm_target on success.

    Preserves the caller's edit-mode object so Push/Pull can keep using the
    same BMesh wrapper afterwards.
    """
    import bpy

    if not is_solid(bm_target) or not is_solid(bm_tool):
        return False, "Both operands must be closed solids"
    mode = {"UNION": "UNION", "DIFFERENCE": "DIFFERENCE", "INTERSECT": "INTERSECT"}.get(
        operation
    )
    if mode is None:
        return False, "Unknown Boolean operation"

    edit_obj = bpy.context.edit_object
    mesh_a = bpy.data.meshes.new("OFormBoolA")
    mesh_b = bpy.data.meshes.new("OFormBoolB")
    obj_a = bpy.data.objects.new("OFormBoolA", mesh_a)
    obj_b = bpy.data.objects.new("OFormBoolB", mesh_b)
    try:
        # Flush edit bmesh into its mesh datablock before we leave edit mode.
        if edit_obj is not None and edit_obj.mode == "EDIT":
            try:
                bmesh.update_edit_mesh(edit_obj.data)
            except Exception:
                pass
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
        if len(obj_a.data.polygons) == 0:
            return False, "Boolean produced an empty mesh"
        # Write into the edit object first, then reload the wrapper from it.
        if edit_obj is not None and edit_obj.type == "MESH":
            try:
                if getattr(edit_obj, "mode", "OBJECT") == "EDIT":
                    bpy.ops.object.mode_set(mode="OBJECT")
                # Replace geometry in place.
                edit_mesh = edit_obj.data
                edit_mesh.clear_geometry()
                import bmesh as bmesh_mod

                tmp = bmesh_mod.new()
                tmp.from_mesh(obj_a.data)
                tmp.to_mesh(edit_mesh)
                tmp.free()
                edit_mesh.update()
                bpy.context.view_layer.objects.active = edit_obj
                for obj in list(bpy.context.selected_objects):
                    obj.select_set(obj == edit_obj)
                edit_obj.select_set(True)
                bpy.ops.object.mode_set(mode="EDIT")
                bm_target.clear()
                bm_target.from_edit_mesh(edit_mesh)
                bm_target.normal_update()
            except Exception as exc:
                return False, "Boolean edit sync failed: " + str(exc)
        else:
            bm_target.clear()
            bm_target.from_mesh(obj_a.data)
            bm_target.normal_update()
        if not bm_target.faces:
            return False, "Boolean produced an empty mesh"
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
