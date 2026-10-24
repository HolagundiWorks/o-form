# SPDX-FileCopyrightText: 2026 O-Form Authors
#
# SPDX-License-Identifier: GPL-2.0-or-later

"""BIM operators — classify, assign storey, IFC import/export."""

from __future__ import annotations

import bpy
from bpy.props import EnumProperty, FloatProperty, StringProperty
from bpy.types import Operator

from . import classify
from . import guid as guid_mod
from . import ifc4
from . import props
from . import quantities
from . import live_sync
from . import project_folder
from . import shilpi_ifc
from . import spatial
from . import suite_ids
from . import takeoff
from . import taxonomy


def _targets(context):
    """Mesh objects to tag: entity → selected meshes → active mesh."""
    try:
        import groups
    except ImportError:
        groups = None
    if groups is not None:
        entity = groups.get_entity(context)
        if entity is not None and entity.type == "MESH":
            return [entity]
    selected = [o for o in context.selected_objects if o.type == "MESH"]
    if selected:
        return selected
    active = context.view_layer.objects.active
    if active is not None and active.type == "MESH":
        return [active]
    return []


def _has_edit_geom_selection(context):
    import bmesh

    obj = getattr(context, "edit_object", None)
    if obj is None or obj.type != "MESH" or obj.mode != "EDIT":
        return False
    bm = bmesh.from_edit_mesh(obj.data)
    return (
        any(face.select for face in bm.faces)
        or any(edge.select for edge in bm.edges)
        or any(vert.select for vert in bm.verts)
    )


def _promote_edit_selection(context, definition="Component"):
    """Turn the current edit selection into a component object for IFC tagging."""
    import groups

    if not _has_edit_geom_selection(context):
        return None
    return groups.make_component(context, definition=definition)


class OFORM_OT_bim_ensure_project(Operator):
    bl_idname = "oform.bim_ensure_project"
    bl_label = "Initialize BIM Project"
    bl_description = "Create Project / Site / Building / default storeys"
    bl_options = {"REGISTER", "UNDO"}

    def execute(self, context):
        tree = spatial.ensure_project(context.scene)
        context.scene.oform_status = "BIM: {} · {} storeys".format(
            tree["building"], len(tree["storeys"])
        )
        return {"FINISHED"}


class OFORM_OT_bim_add_storey(Operator):
    bl_idname = "oform.bim_add_storey"
    bl_label = "Add Storey"
    bl_options = {"REGISTER", "UNDO"}

    name: StringProperty(name="Name", default="Level")
    elevation: FloatProperty(name="Elevation (m)", default=3.0)

    def execute(self, context):
        entry = spatial.add_storey(context.scene, self.name, self.elevation)
        context.scene.oform_status = "Storey {} @ {:.2f} m".format(
            entry["name"], entry["elevation"]
        )
        return {"FINISHED"}

    def invoke(self, context, _event):
        return context.window_manager.invoke_props_dialog(self)


class OFORM_OT_bim_set_storey(Operator):
    bl_idname = "oform.bim_set_storey"
    bl_label = "Set Active Storey"
    bl_options = {"REGISTER", "UNDO"}

    storey: StringProperty(name="Storey")

    def execute(self, context):
        if not spatial.set_active_storey(context.scene, self.storey):
            self.report({"WARNING"}, "Unknown storey")
            return {"CANCELLED"}
        context.scene.oform_status = "Active storey: " + self.storey
        return {"FINISHED"}


class OFORM_OT_bim_assign_storey(Operator):
    bl_idname = "oform.bim_assign_storey"
    bl_label = "Assign to Storey"
    bl_description = "Assign selected elements to the active storey"
    bl_options = {"REGISTER", "UNDO"}

    def execute(self, context):
        spatial.ensure_project(context.scene)
        storey = spatial.active_storey(context.scene)
        targets = _targets(context)
        if not targets:
            self.report({"WARNING"}, "Nothing selected")
            return {"CANCELLED"}
        for obj in targets:
            props.set_storey(obj, storey)
            if not props.guid_of(obj):
                props.set_guid(obj, guid_mod.new_guid())
        context.scene.oform_status = "Assigned {} to {}".format(len(targets), storey)
        return {"FINISHED"}


class OFORM_OT_bim_classify(Operator):
    bl_idname = "oform.bim_classify"
    bl_label = "Auto-Classify"
    bl_description = "Guess IFC class from shape (Wall / Slab / Column / …)"
    bl_options = {"REGISTER", "UNDO"}

    def execute(self, context):
        spatial.ensure_project(context.scene)
        targets = _targets(context)
        if not targets:
            self.report({"WARNING"}, "Nothing selected")
            return {"CANCELLED"}
        storey = spatial.active_storey(context.scene)
        for obj in targets:
            ifc_class = classify.suggest_class(obj)
            props.set_ifc_class(obj, ifc_class)
            if not props.guid_of(obj):
                props.set_guid(obj, guid_mod.new_guid())
            if not props.storey_of(obj):
                props.set_storey(obj, storey)
        live_sync.mark_dirty()
        context.scene.oform_status = "Classified {} elements".format(len(targets))
        return {"FINISHED"}


def _apply_ifc_class(context, targets, ifc_class):
    spatial.ensure_project(context.scene)
    storey = spatial.active_storey(context.scene)
    for obj in targets:
        props.set_ifc_class(obj, ifc_class)
        if not props.guid_of(obj):
            props.set_guid(obj, guid_mod.new_guid())
        if not props.storey_of(obj):
            props.set_storey(obj, storey)
    live_sync.mark_dirty()
    return len(targets)


class OFORM_OT_bim_set_class(Operator):
    bl_idname = "oform.bim_set_class"
    bl_label = "Set IFC Class"
    bl_options = {"REGISTER", "UNDO"}

    ifc_class: EnumProperty(
        name="IFC Class",
        items=tuple((key, label, "") for key, label in taxonomy.ELEMENTS),
        default=taxonomy.DEFAULT_ELEMENT,
    )

    def execute(self, context):
        targets = _targets(context)
        if not targets and _has_edit_geom_selection(context):
            promoted = _promote_edit_selection(
                context, definition=taxonomy.label_of(self.ifc_class)
            )
            if promoted is not None:
                targets = [promoted]
        if not targets:
            self.report({"WARNING"}, "Select a component or geometry first")
            return {"CANCELLED"}
        count = _apply_ifc_class(context, targets, self.ifc_class)
        msg = "Mapped {} → {}".format(count, taxonomy.label_of(self.ifc_class))
        context.scene.oform_status = msg
        self.report({"INFO"}, msg)
        return {"FINISHED"}

    def invoke(self, context, _event):
        return context.window_manager.invoke_props_dialog(self)


class OFORM_OT_bim_map_to(Operator):
    bl_idname = "oform.bim_map_to"
    bl_label = "Map to IFC Component"
    bl_description = (
        "Map the selection to an IFC component. "
        "Edit-mode geometry is promoted to a component first"
    )
    bl_options = {"REGISTER", "UNDO"}

    ifc_class: EnumProperty(
        name="IFC Class",
        items=tuple((key, label, "") for key, label in taxonomy.ELEMENTS),
        default=taxonomy.DEFAULT_ELEMENT,
    )

    def execute(self, context):
        targets = _targets(context)
        if not targets and _has_edit_geom_selection(context):
            promoted = _promote_edit_selection(
                context, definition=taxonomy.label_of(self.ifc_class)
            )
            if promoted is not None:
                targets = [promoted]
        if not targets:
            self.report(
                {"WARNING"},
                "Select a group/component or faces, then map to an IFC type",
            )
            return {"CANCELLED"}
        count = _apply_ifc_class(context, targets, self.ifc_class)
        label = taxonomy.label_of(self.ifc_class)
        msg = "Mapped {} → {}".format(count, label)
        context.scene.oform_status = msg
        self.report({"INFO"}, msg)
        return {"FINISHED"}


class OFORM_OT_bim_context_menu(Operator):
    bl_idname = "oform.bim_context_menu"
    bl_label = "BIM Menu"
    bl_description = "Open the BIM context menu (map selection to IFC)"
    bl_options = {"REGISTER"}

    def invoke(self, context, _event):
        return self.execute(context)

    def execute(self, context):
        try:
            bpy.ops.wm.call_menu(name="OFORM_MT_bim_context")
        except RuntimeError as exc:
            self.report({"WARNING"}, str(exc))
            return {"CANCELLED"}
        return {"FINISHED"}


class OFORM_OT_bim_export_ifc(Operator):
    bl_idname = "oform.bim_export_ifc"
    bl_label = "Export IFC…"
    bl_description = "Export the BIM model as IFC4 (native O-Form writer)"
    bl_options = {"REGISTER"}

    filepath: StringProperty(subtype="FILE_PATH")
    filename_ext = ".ifc"
    filter_glob: StringProperty(default="*.ifc", options={"HIDDEN"})

    def execute(self, context):
        path = self.filepath
        if not path.lower().endswith(".ifc"):
            path += ".ifc"
        ok, message = ifc4.export_ifc(context, path)
        context.scene.oform_status = message[:80]
        if not ok:
            self.report({"ERROR"}, message)
            return {"CANCELLED"}
        self.report({"INFO"}, message)
        return {"FINISHED"}

    def invoke(self, context, _event):
        if not self.filepath:
            self.filepath = "model.ifc"
        context.window_manager.fileselect_add(self)
        return {"RUNNING_MODAL"}


class OFORM_OT_bim_import_ifc(Operator):
    bl_idname = "oform.bim_import_ifc"
    bl_label = "Import IFC…"
    bl_description = "Import tessellated IFC4 products"
    bl_options = {"REGISTER", "UNDO"}

    filepath: StringProperty(subtype="FILE_PATH")
    filter_glob: StringProperty(default="*.ifc", options={"HIDDEN"})

    def execute(self, context):
        ok, message = ifc4.import_ifc(context, self.filepath)
        context.scene.oform_status = message[:80]
        if not ok:
            self.report({"ERROR"}, message)
            return {"CANCELLED"}
        self.report({"INFO"}, message)
        return {"FINISHED"}

    def invoke(self, context, _event):
        context.window_manager.fileselect_add(self)
        return {"RUNNING_MODAL"}


class OFORM_OT_bim_inspect(Operator):
    bl_idname = "oform.bim_inspect"
    bl_label = "Inspect BIM Element"
    bl_options = {"REGISTER"}

    def execute(self, context):
        targets = _targets(context)
        if not targets:
            self.report({"WARNING"}, "Nothing selected")
            return {"CANCELLED"}
        obj = targets[0]
        stats = quantities.mesh_stats(obj)
        ifc_class = props.ifc_class_of(obj) or "(untyped)"
        message = "{} · {} · V={:.3f} A={:.3f} · {}".format(
            obj.name,
            taxonomy.label_of(ifc_class) if ifc_class != "(untyped)" else ifc_class,
            stats["volume"],
            stats["area"],
            "solid" if stats["solid"] else "open",
        )
        context.scene.oform_status = message[:80]
        self.report({"INFO"}, message)
        return {"FINISHED"}


class OFORM_OT_bim_shilpi_connect(Operator):
    bl_idname = "oform.bim_shilpi_connect"
    bl_label = "Connect ShilpiDB"
    bl_description = "Connect to the shared suite shilpid (same as O-Draft, 127.0.0.1:7420)"
    bl_options = {"REGISTER"}

    def execute(self, context):
        ok, message = shilpi_ifc.connect(context.scene)
        context.scene.oform_status = message[:80]
        if not ok:
            self.report({"ERROR"}, message)
            return {"CANCELLED"}
        self.report({"INFO"}, message)
        return {"FINISHED"}


class OFORM_OT_bim_shilpi_status(Operator):
    bl_idname = "oform.bim_shilpi_status"
    bl_label = "ShilpiDB Status"
    bl_options = {"REGISTER"}

    def execute(self, context):
        info = shilpi_ifc.status(context.scene)
        if info["connected"]:
            stats = info.get("stats") or {}
            message = "ShilpiDB ok · {} records · drawing {}".format(
                stats.get("count", "?"),
                (info.get("drawing_id") or "")[:8],
            )
        else:
            message = "ShilpiDB offline · " + info["gateway"]
        context.scene.oform_status = message[:80]
        self.report({"INFO"}, message)
        return {"FINISHED"}


class OFORM_OT_bim_shilpi_push(Operator):
    bl_idname = "oform.bim_shilpi_push"
    bl_label = "Push IFC to ShilpiDB"
    bl_description = "Store IFC/BIM semantics on the shared ShilpiDB for O-Draft / suite"
    bl_options = {"REGISTER"}

    def execute(self, context):
        ok, message = shilpi_ifc.push_ifc(context, replace=True)
        context.scene.oform_status = message[:80]
        if not ok:
            self.report({"ERROR"}, message)
            return {"CANCELLED"}
        self.report({"INFO"}, message)
        return {"FINISHED"}


class OFORM_OT_bim_shilpi_pull(Operator):
    bl_idname = "oform.bim_shilpi_pull"
    bl_label = "Pull IFC from ShilpiDB"
    bl_description = "Load IFC/BIM semantics for this drawing_id from ShilpiDB"
    bl_options = {"REGISTER", "UNDO"}

    def execute(self, context):
        ok, message = shilpi_ifc.pull_ifc(context)
        context.scene.oform_status = message[:80]
        if not ok:
            self.report({"ERROR"}, message)
            return {"CANCELLED"}
        self.report({"INFO"}, message)
        return {"FINISHED"}


class OFORM_OT_bim_set_office_id(Operator):
    bl_idname = "oform.bim_set_office_id"
    bl_label = "Set AORMS Project Id"
    bl_description = "Shared project_office_id used by O-Draft take-off / suite"
    bl_options = {"REGISTER", "UNDO"}

    project_office_id: StringProperty(name="project_office_id", default="")

    def execute(self, context):
        suite_ids.set_project_office_id(context.scene, self.project_office_id)
        suite_ids.ensure_drawing_id(context.scene)
        context.scene.oform_status = "project_office_id set"
        return {"FINISHED"}

    def invoke(self, context, _event):
        self.project_office_id = suite_ids.project_office_id(context.scene)
        return context.window_manager.invoke_props_dialog(self)


class OFORM_OT_bim_takeoff_push(Operator):
    bl_idname = "oform.bim_takeoff_push"
    bl_label = "Push Take-off (suite)"
    bl_description = "Write hcw-takeoff-shilpi rows for O-Draft / O-CoreOp"
    bl_options = {"REGISTER"}

    def execute(self, context):
        ok, message = takeoff.push_takeoff(context, replace=True)
        context.scene.oform_status = message[:80]
        if not ok:
            self.report({"ERROR"}, message)
            return {"CANCELLED"}
        self.report({"INFO"}, message)
        return {"FINISHED"}


class OFORM_OT_bim_takeoff_status(Operator):
    bl_idname = "oform.bim_takeoff_status"
    bl_label = "Take-off Status"
    bl_description = "Read this drawing's hcw-takeoff-shilpi header from ShilpiDB"
    bl_options = {"REGISTER"}

    def execute(self, context):
        ok, message, _summary = takeoff.pull_takeoff_summary(context)
        context.scene.oform_status = message[:80]
        if not ok:
            self.report({"WARNING"}, message)
            return {"CANCELLED"}
        self.report({"INFO"}, message)
        return {"FINISHED"}


class OFORM_OT_bim_suite_push(Operator):
    bl_idname = "oform.bim_suite_push"
    bl_label = "Push BIM + Take-off"
    bl_description = "Push IFC sidecar and suite take-off with one drawing_id/slot"
    bl_options = {"REGISTER"}

    def execute(self, context):
        ok, message = takeoff.push_coherent(context)
        context.scene.oform_status = message[:80]
        if not ok:
            self.report({"ERROR"}, message)
            return {"CANCELLED"}
        self.report({"INFO"}, message)
        return {"FINISHED"}


class OFORM_OT_bim_suite_list(Operator):
    bl_idname = "oform.bim_suite_list"
    bl_label = "List Suite Take-offs"
    bl_description = "List hcw-takeoff-shilpi drawings on the shared ShilpiDB"
    bl_options = {"REGISTER"}

    def execute(self, context):
        ok, message, drawings = takeoff.list_suite_drawings(context)
        context.scene.oform_status = message[:80]
        if not ok:
            self.report({"ERROR"}, message)
            return {"CANCELLED"}
        for item in drawings[:12]:
            self.report(
                {"INFO"},
                "{} · {} · {}".format(
                    item.get("app") or "?",
                    (item.get("drawing_id") or "")[:8],
                    item.get("state"),
                ),
            )
        self.report({"INFO"}, message)
        return {"FINISHED"}


class OFORM_OT_open_project(Operator):
    bl_idname = "oform.open_project"
    bl_label = "Open Project Folder…"
    bl_description = "Open an OSAS project folder (osas.project.json) from O-Studio"
    bl_options = {"REGISTER"}

    directory: StringProperty(name="Project Folder", subtype="DIR_PATH")

    def execute(self, context):
        root = (self.directory or "").rstrip("\\/")
        if not root:
            self.report({"ERROR"}, "Choose a project folder")
            return {"CANCELLED"}
        ok, message, _info = project_folder.open_project(context, root)
        context.scene.oform_status = message[:80]
        if not ok:
            self.report({"ERROR"}, message)
            return {"CANCELLED"}
        live_sync.start()
        self.report({"INFO"}, message)
        return {"FINISHED"}

    def invoke(self, context, _event):
        context.window_manager.fileselect_add(self)
        return {"RUNNING_MODAL"}


class OFORM_OT_save_project_model(Operator):
    bl_idname = "oform.save_project_model"
    bl_label = "Save into Project"
    bl_description = "Save form/model.blend inside the bound OSAS project folder"
    bl_options = {"REGISTER"}

    def execute(self, context):
        ok, message = project_folder.save_form_into_project(context)
        context.scene.oform_status = message[:80]
        if not ok:
            self.report({"ERROR"}, message)
            return {"CANCELLED"}
        live_sync.mark_dirty()
        self.report({"INFO"}, message)
        return {"FINISHED"}


class OFORM_OT_live_sync_toggle(Operator):
    bl_idname = "oform.live_sync_toggle"
    bl_label = "Toggle Live Sync"
    bl_description = "Enable or disable live ShilpiDB sync for this project"
    bl_options = {"REGISTER"}

    def execute(self, context):
        enabled = not project_folder.live_sync_enabled(context.scene)
        project_folder.set_live_sync(context.scene, enabled)
        if enabled:
            live_sync.start()
            msg = "Live sync on"
        else:
            msg = "Live sync off"
        context.scene.oform_status = msg
        self.report({"INFO"}, msg)
        return {"FINISHED"}


CLASSES = (
    OFORM_OT_bim_ensure_project,
    OFORM_OT_bim_add_storey,
    OFORM_OT_bim_set_storey,
    OFORM_OT_bim_assign_storey,
    OFORM_OT_bim_classify,
    OFORM_OT_bim_set_class,
    OFORM_OT_bim_map_to,
    OFORM_OT_bim_context_menu,
    OFORM_OT_bim_export_ifc,
    OFORM_OT_bim_import_ifc,
    OFORM_OT_bim_inspect,
    OFORM_OT_bim_shilpi_connect,
    OFORM_OT_bim_shilpi_status,
    OFORM_OT_bim_shilpi_push,
    OFORM_OT_bim_shilpi_pull,
    OFORM_OT_bim_set_office_id,
    OFORM_OT_bim_takeoff_push,
    OFORM_OT_bim_takeoff_status,
    OFORM_OT_bim_suite_push,
    OFORM_OT_bim_suite_list,
    OFORM_OT_open_project,
    OFORM_OT_save_project_model,
    OFORM_OT_live_sync_toggle,
)


def register():
    for cls in CLASSES:
        if not getattr(cls, "is_registered", False):
            bpy.utils.register_class(cls)
    live_sync.register()


def unregister():
    live_sync.unregister()
    for cls in reversed(CLASSES):
        if getattr(cls, "is_registered", False):
            bpy.utils.unregister_class(cls)
