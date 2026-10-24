# SPDX-FileCopyrightText: 2026 O-Form Authors
#
# SPDX-License-Identifier: GPL-2.0-or-later

"""O-Form workspace shell v2 — architecture-first chrome.

Layout: left tool rail · dominant VIEW_3D · right inspector.
Primary modelling tools live in the 3D View header.
Existing ``oform.*`` operators are reused; this module is presentation only.

Activated when ``design.UI_SHELL_V2`` is True.
"""

from __future__ import annotations

import traceback

import bpy
from bpy.props import StringProperty
from bpy.types import Operator, Panel

import brand
import design

_RAIL_WIDTH_MAX = 168
_INSPECTOR_WIDTH_MIN = 200


def _tool_icon(idname):
    import ui as ui_mod

    return ui_mod._tool_icon(idname)


def _tool_icon_value(idname):
    import ui as ui_mod

    return ui_mod._tool_icon_value(idname)


def _active_tool(context):
    scene = context.scene
    active = getattr(scene, "oform_tool", "") if scene is not None else ""
    return active or "oform.tool_select"


def props_role(context):
    """Return 'rail' | 'inspector' | None for the current PROPERTIES area."""
    area = getattr(context, "area", None)
    if area is None or area.type != "PROPERTIES":
        return None
    screen = context.screen
    if screen is None:
        return None
    props_areas = [a for a in screen.areas if a.type == "PROPERTIES"]
    if not props_areas:
        return None
    if len(props_areas) == 1:
        # Single pane: prefer rail if narrow, else inspector.
        return "rail" if area.width <= _RAIL_WIDTH_MAX else "inspector"
    leftmost = min(props_areas, key=lambda a: (a.x, a.width))
    rightmost = max(props_areas, key=lambda a: (a.x, a.width))
    if area.as_pointer() == leftmost.as_pointer():
        return "rail"
    if area.as_pointer() == rightmost.as_pointer():
        return "inspector"
    return "inspector"


def _poll_rail(context):
    return props_role(context) == "rail"


def _poll_inspector(context):
    return props_role(context) == "inspector"


def _operator_button(layout, idname, label, active, icon_only=False):
    custom = _tool_icon_value(idname)
    kwargs = {"text": "" if icon_only else label, "depress": active == idname, "emboss": True}
    if custom:
        kwargs["icon_value"] = custom
    else:
        kwargs["icon"] = _tool_icon(idname)
    layout.operator(idname, **kwargs)


# ---------------------------------------------------------------------------
# Panels
# ---------------------------------------------------------------------------


class OFORM_PT_v2_rail(Panel):
    """Secondary tools — left narrow PROPERTIES pane."""

    bl_idname = "OFORM_PT_v2_rail"
    bl_space_type = "PROPERTIES"
    bl_region_type = "WINDOW"
    bl_context = "scene"
    bl_label = "Tools"
    bl_order = 0
    bl_options = {"HIDE_HEADER"}

    @classmethod
    def poll(cls, context):
        return _poll_rail(context)

    def draw(self, context):
        active = _active_tool(context)
        layout = self.layout
        col = layout.column(align=True)
        col.scale_y = 1.15
        for group_name, tools in design.RAIL_GROUPS:
            box = col.column(align=True)
            hdr = box.row()
            hdr.enabled = False
            hdr.label(text=group_name)
            for idname, label in tools:
                row = box.row(align=True)
                row.alignment = "CENTER"
                _operator_button(row, idname, label, active, icon_only=True)
            col.separator(factor=0.4)


class OFORM_PT_v2_structure(Panel):
    bl_idname = "OFORM_PT_v2_structure"
    bl_space_type = "PROPERTIES"
    bl_region_type = "WINDOW"
    bl_context = "scene"
    bl_label = "Structure"
    bl_order = 10

    @classmethod
    def poll(cls, context):
        return _poll_inspector(context)

    def draw(self, context):
        import groups

        layout = self.layout
        # Read-only: never call ensure_root from draw (ID writes forbidden).
        root = groups.get_root(context)
        ctx = groups.context_object(context, create=False)
        layout.label(text="Model")
        col = layout.column(align=True)
        for obj in context.scene.objects:
            if obj.type != "MESH":
                continue
            row = col.row(align=True)
            is_ctx = obj == ctx
            is_root = obj == root
            kind = groups.kind_of(obj) if groups.is_container(obj) else "mesh"
            label = obj.name if not is_root else obj.name + " (root)"
            op = row.operator("oform.shell_focus_object", text=label, depress=is_ctx)
            op.object_name = obj.name
            meta = row.row()
            meta.enabled = False
            meta.label(text=kind[:4])


class OFORM_PT_v2_organize(Panel):
    bl_idname = "OFORM_PT_v2_organize"
    bl_space_type = "PROPERTIES"
    bl_region_type = "WINDOW"
    bl_context = "scene"
    bl_label = "Organize"
    bl_order = 20

    @classmethod
    def poll(cls, context):
        return _poll_inspector(context)

    def draw(self, context):
        layout = self.layout
        layout.operator("oform.make_group", text="Make Group", icon="GROUP")
        layout.operator("oform.make_component", text="Make Component", icon="MOD_ARRAY")
        layout.operator("oform.explode", text="Explode")
        row = layout.row(align=True)
        row.operator("oform.enter_group", text="Edit")
        row.operator("oform.exit_group", text="Close")
        layout.separator()
        layout.operator("oform.hide_rest", text="Hide Rest of Model")
        layout.operator("oform.unhide_all", text="Unhide All")


class OFORM_PT_v2_properties(Panel):
    bl_idname = "OFORM_PT_v2_properties"
    bl_space_type = "PROPERTIES"
    bl_region_type = "WINDOW"
    bl_context = "scene"
    bl_label = "Properties"
    bl_order = 30

    @classmethod
    def poll(cls, context):
        return _poll_inspector(context)

    def draw(self, context):
        import groups
        import solids

        layout = self.layout
        obj = groups.context_object(context, create=False)
        entity = groups.get_entity(context)
        target = entity if entity is not None else obj
        col = layout.column(align=True)
        if target is None:
            col.label(text="Nothing selected")
            return
        col.label(text=target.name)
        kind = groups.kind_of(target) if groups.is_container(target) else "Mesh"
        col.label(text="Type: " + kind)
        if target.type == "MESH":
            col.label(text="Solid: yes" if solids.object_is_solid(target) else "Solid: no")
            loc = target.matrix_world.translation
            col.separator()
            col.label(text="Position")
            grid = layout.grid_flow(row_major=True, columns=1, even_columns=True)
            grid.label(text="X  {:.2f}".format(loc.x))
            grid.label(text="Y  {:.2f}".format(loc.y))
            grid.label(text="Z  {:.2f}".format(loc.z))
            if target.mode == "EDIT":
                import bmesh

                bm = bmesh.from_edit_mesh(target.data)
                faces = sum(1 for f in bm.faces if f.select)
                edges = sum(1 for e in bm.edges if e.select)
                verts = sum(1 for v in bm.verts if v.select)
                col.separator()
                col.label(text="Selection  F {}  E {}  V {}".format(faces, edges, verts))
        layout.separator()
        layout.label(text="Solids")
        layout.operator("oform.boolean_union", text="Union")
        layout.operator("oform.boolean_subtract", text="Subtract")
        layout.operator("oform.boolean_intersect", text="Intersect")
        layout.operator("oform.boolean_trim", text="Trim")
        layout.operator("oform.solid_inspect", text="Inspect Solid")


class OFORM_PT_v2_ask(Panel):
    bl_idname = "OFORM_PT_v2_ask"
    bl_space_type = "PROPERTIES"
    bl_region_type = "WINDOW"
    bl_context = "scene"
    bl_label = "Ask"
    bl_order = 40
    bl_options = {"DEFAULT_CLOSED"}

    @classmethod
    def poll(cls, context):
        return _poll_inspector(context)

    def draw(self, context):
        import ai

        layout = self.layout
        scene = context.scene
        layout.label(text=ai.CHANNEL_LABEL)
        layout.prop(scene, "oform_ask", text="")
        layout.operator("oform.ask_submit", text="Ask")
        phase = ai.phase(scene)
        _name, label = ai.pending(scene)
        if phase == "confirm" and label:
            box = layout.box()
            box.label(text=label)
            row = box.row(align=True)
            row.operator("oform.ask_allow", text="Allow")
            row.operator("oform.ask_decline", text="Decline")


class OFORM_PT_v2_instructor(Panel):
    bl_idname = "OFORM_PT_v2_instructor"
    bl_space_type = "PROPERTIES"
    bl_region_type = "WINDOW"
    bl_context = "scene"
    bl_label = "Instructor"
    bl_order = 50
    bl_options = {"DEFAULT_CLOSED"}

    @classmethod
    def poll(cls, context):
        return _poll_inspector(context)

    def draw(self, context):
        layout = self.layout
        active = _active_tool(context)
        label = dict(design.PRIMARY_TOOLS).get(active)
        if label is None:
            for _g, tools in design.RAIL_GROUPS:
                for idname, lab in tools:
                    if idname == active:
                        label = lab
                        break
        layout.label(text=label or active, icon=_tool_icon(active))
        try:
            import tools as tools_mod

            tip = tools_mod._TOOL_DESCRIPTIONS.get(active, "")
        except Exception:
            tip = ""
        if tip:
            row = layout.row()
            row.enabled = False
            row.label(text=tip)


_PANELS = (
    OFORM_PT_v2_rail,
    OFORM_PT_v2_structure,
    OFORM_PT_v2_organize,
    OFORM_PT_v2_properties,
    OFORM_PT_v2_ask,
    OFORM_PT_v2_instructor,
)


# ---------------------------------------------------------------------------
# Header / status draws (swapped in when v2 is active)
# ---------------------------------------------------------------------------


def draw_view3d_header(self, context):
    """Primary tool strip + active command — viewport-dominant chrome."""
    layout = self.layout
    active = _active_tool(context)
    row = layout.row(align=True)
    for idname, label in design.PRIMARY_TOOLS:
        _operator_button(row, idname, label, active, icon_only=True)
    layout.separator()
    # Active command label (architecture tone).
    label = dict(design.PRIMARY_TOOLS).get(active, "")
    if not label:
        for _g, tools in design.RAIL_GROUPS:
            for idname, lab in tools:
                if idname == active:
                    label = lab
                    break
    name = row.row()
    name.enabled = False
    name.label(text=label or "Select")


def draw_properties_header(self, context):
    role = props_role(context)
    row = self.layout.row(align=True)
    try:
        row.template_icon(icon_value=brand.icon_id(), scale=1.35)
    except Exception:
        pass
    if role == "rail":
        row.label(text="Tools")
    else:
        row.label(text=brand.PRODUCT)
        sub = row.row()
        sub.enabled = False
        sub.label(text=brand.SUBTITLE)


def draw_status(self, context):
    """Command · unit chips · view · selection · VCB (O-Draft command bar)."""
    import units as units_mod

    layout = self.layout
    scene = context.scene
    status = getattr(scene, "oform_status", "") if scene is not None else ""
    measure = getattr(scene, "oform_measure", "") if scene is not None else ""

    layout.label(text=status or "Ready")
    layout.separator_spacer()

    # Unit chips — same pattern as O-Draft bottom bar.
    units_mod.draw_status_chips(layout, scene)

    # Perspective / parallel
    view_label = "Perspective"
    for area in context.screen.areas if context.screen else []:
        if area.type != "VIEW_3D":
            continue
        persp = area.spaces.active.region_3d.view_perspective
        view_label = "Parallel" if persp == "ORTHO" else "Perspective"
        break
    meta2 = layout.row()
    meta2.enabled = False
    meta2.label(text=view_label)

    # Selection count
    sel_n = len(context.selected_objects) if context.selected_objects else 0
    sel = layout.row()
    sel.enabled = False
    if sel_n:
        sel.label(text="Selection: {} object{}".format(sel_n, "s" if sel_n != 1 else ""))
    else:
        sel.label(text="Selection: —")

    layout.separator()
    dark = brand.is_dark(context)
    theme_row = layout.row(align=True)
    theme_row.operator(
        "oform.toggle_theme",
        text="Light",
        depress=not dark,
    ).mode = "LIGHT"
    theme_row.operator(
        "oform.toggle_theme",
        text="Dark",
        depress=dark,
    ).mode = "DARK"

    layout.separator()
    vcb = layout.row(align=True)
    vcb.alignment = "RIGHT"
    vcb.ui_units_x = 16
    if measure:
        vcb.label(text="Distance: " + measure)
    else:
        vcb.label(text="Distance")


def draw_topbar(self, context):
    if context.region.alignment == "RIGHT":
        # Workspace / settings cluster (O-Form owned; no Blender spill).
        layout = self.layout
        layout.operator("ed.undo", text="", icon="LOOP_BACK")
        layout.operator("ed.redo", text="", icon="LOOP_FORWARDS")
        layout.separator()
        layout.operator("oform.preferences_hint", text="", icon="PREFERENCES")
        return
    from bl_ui.space_topbar import TOPBAR_MT_editor_menus

    TOPBAR_MT_editor_menus.draw_collapsible(context, self.layout)


# ---------------------------------------------------------------------------
# Focus object operator (structure list)
# ---------------------------------------------------------------------------


class OFORM_OT_shell_focus_object(Operator):
    bl_idname = "oform.shell_focus_object"
    bl_label = "Focus Object"
    bl_description = "Select and activate this object in the hierarchy"
    bl_options = {"REGISTER"}

    object_name: StringProperty()

    def execute(self, context):
        import groups

        obj = context.scene.objects.get(self.object_name)
        if obj is None:
            return {"CANCELLED"}
        for other in context.selected_objects:
            other.select_set(False)
        obj.select_set(True)
        context.view_layer.objects.active = obj
        if groups.is_container(obj):
            groups.set_entity(context, obj)
        else:
            groups.set_entity(context, None)
            groups.set_context(context, obj)
        context.scene.oform_status = "Selected " + obj.name
        return {"FINISHED"}


# ---------------------------------------------------------------------------
# Layout
# ---------------------------------------------------------------------------


def _close_area(context, window, screen, area):
    try:
        region = next((r for r in area.regions if r.type == "WINDOW"), None)
        ov = {"window": window, "screen": screen, "area": area}
        if region is not None:
            ov["region"] = region
        with context.temp_override(**ov):
            bpy.ops.screen.area_close()
        return True
    except (RuntimeError, TypeError, AttributeError):
        return False


def _collapse_editors(context, screen, window):
    for _ in range(16):
        extras = [
            a
            for a in screen.areas
            if a.type not in {"VIEW_3D", "TOPBAR", "STATUSBAR"}
        ]
        if not extras:
            break
        if not _close_area(context, window, screen, extras[0]):
            if extras[0].type == "PROPERTIES":
                extras[0].type = "VIEW_3D"
            else:
                break
    views = [a for a in screen.areas if a.type == "VIEW_3D"]
    while len(views) > 1:
        extra = sorted(views, key=lambda a: (a.width, -a.x))[0]
        if not _close_area(context, window, screen, extra):
            break
        views = [a for a in screen.areas if a.type == "VIEW_3D"]
    return any(a.type == "VIEW_3D" for a in screen.areas)


def _split_vertical(context, window, screen, area, factor):
    region = next((r for r in area.regions if r.type == "WINDOW"), None)
    ov = {"window": window, "screen": screen, "area": area}
    if region is not None:
        ov["region"] = region
    before = {a.as_pointer() for a in screen.areas}
    with context.temp_override(**ov):
        result = bpy.ops.screen.area_split(direction="VERTICAL", factor=factor)
    if "FINISHED" not in result:
        return None
    created = [a for a in screen.areas if a.as_pointer() not in before]
    return created[0] if created else None


def _use_scene_context(screen):
    for area in screen.areas:
        if area.type != "PROPERTIES":
            continue
        space = area.spaces.active
        if hasattr(space, "context"):
            try:
                space.context = "SCENE"
            except (TypeError, ValueError):
                pass


def _peel_narrow_properties(context, window, screen, view_area, keep_ratio):
    """Split ``view_area``; convert the narrower half to PROPERTIES. Returns canvas."""
    factor = max(0.7, min(0.94, keep_ratio))
    _split_vertical(context, window, screen, view_area, factor)
    views = [a for a in screen.areas if a.type == "VIEW_3D"]
    if len(views) < 2:
        return next((a for a in screen.areas if a.type == "VIEW_3D"), None)
    narrow, wide = sorted(views, key=lambda a: (a.width, a.x))
    wide.type = "VIEW_3D"
    narrow.type = "PROPERTIES"
    return wide


def open_workspace(context=None):
    """Build left rail | VIEW_3D | right inspector."""
    try:
        context = context or bpy.context
        window = context.window
        if window is None:
            return 0.2
        screen = window.screen
        screen.show_statusbar = True

        # Already healthy? Skip rebuild (second timer pass).
        props = sorted(
            [a for a in screen.areas if a.type == "PROPERTIES"], key=lambda a: a.x
        )
        views = [a for a in screen.areas if a.type == "VIEW_3D"]
        if (
            len(views) == 1
            and len(props) == 2
            and views[0].width > props[0].width
            and views[0].width > props[1].width
        ):
            _use_scene_context(screen)
            return None

        if not _collapse_editors(context, screen, window):
            return None

        view = next(a for a in screen.areas if a.type == "VIEW_3D")
        # 1) Right inspector (~22%).
        canvas = _peel_narrow_properties(
            context, window, screen, view, 1.0 - design.RIGHT_INSPECTOR_RATIO
        )
        if canvas is None:
            return None
        # 2) Left rail (~6–8% of remaining canvas).
        canvas = _peel_narrow_properties(
            context, window, screen, canvas, 1.0 - design.LEFT_RAIL_RATIO
        )
        if canvas is None:
            return None

        # Drop extra panes; keep widest VIEW_3D and up to two PROPERTIES.
        views = [a for a in screen.areas if a.type == "VIEW_3D"]
        while len(views) > 1:
            extra = sorted(views, key=lambda a: a.width)[0]
            _close_area(context, window, screen, extra)
            views = [a for a in screen.areas if a.type == "VIEW_3D"]
        props = sorted(
            [a for a in screen.areas if a.type == "PROPERTIES"], key=lambda a: a.x
        )
        while len(props) > 2:
            _close_area(context, window, screen, props[1])
            props = sorted(
                [a for a in screen.areas if a.type == "PROPERTIES"], key=lambda a: a.x
            )

        _use_scene_context(screen)
        views = [a for a in screen.areas if a.type == "VIEW_3D"]
        props = [a for a in screen.areas if a.type == "PROPERTIES"]
        if not views:
            return None
        canvas = max(views, key=lambda a: a.width)
        for p in props:
            if p.width >= canvas.width:
                p.type = "VIEW_3D"
        return None
    except Exception:
        traceback.print_exc()
    return None


def register():
    if not getattr(OFORM_OT_shell_focus_object, "is_registered", False):
        bpy.utils.register_class(OFORM_OT_shell_focus_object)
    for cls in _PANELS:
        if not getattr(cls, "is_registered", False):
            bpy.utils.register_class(cls)


def unregister():
    for cls in reversed(_PANELS):
        if getattr(cls, "is_registered", False):
            bpy.utils.unregister_class(cls)
    if getattr(OFORM_OT_shell_focus_object, "is_registered", False):
        bpy.utils.unregister_class(OFORM_OT_shell_focus_object)
