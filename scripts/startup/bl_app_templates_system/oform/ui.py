# SPDX-FileCopyrightText: 2026 O-Form Authors
#
# SPDX-License-Identifier: GPL-2.0-or-later

"""Menus, sidebars, status bar, keymap, theme, Ask AI, and factory scene.

Layout mirrors O-Draft: menu → left tool/side pane → canvas → status, with a
fixed Ask strip over the viewport. Canvas is SketchUp-like (solid paper, axes,
no ground grid).
"""

import traceback

import bpy
from bpy.app.handlers import persistent
from bpy.props import EnumProperty, FloatVectorProperty, StringProperty
from bpy.types import Menu, Operator, Panel

import ai
import brand

_DRAW = []
_KEYMAPS = []
_SAVED_KEYS = []
_UI = False
_ASK_HANDLERS = []
_SIDE_WIDTH = 0.062  # SketchUp Large Tool Set — left icon rail
_ICON_SCALE = 1.65  # Equal X/Y scale → roughly square icon buttons

# SketchUp Large Tool Set order (icon-only). Separators match the reference strip.
# https://help.sketchup.com/en/sketchup/getting-started-toolbar
_LARGE_TOOL_SET = (
    # Select / modify
    ("oform.tool_select", "Select"),
    ("oform.make_component", "Make Component"),
    ("oform.tool_paint", "Paint Bucket"),
    ("oform.tool_eraser", "Eraser"),
    None,  # separator
    # Draw
    ("oform.tool_line", "Line"),
    ("oform.tool_freehand", "Freehand"),
    ("oform.tool_rectangle", "Rectangle"),
    ("oform.tool_circle", "Circle"),
    ("oform.tool_polygon", "Polygon"),
    ("oform.tool_arc", "Arc"),
    None,
    # Transform
    ("oform.tool_move", "Move"),
    ("oform.tool_push_pull", "Push/Pull"),
    ("oform.tool_rotate", "Rotate"),
    ("oform.tool_follow_me", "Follow Me"),
    ("oform.tool_scale", "Scale"),
    ("oform.tool_offset", "Offset"),
    None,
    # Construction
    ("oform.tool_tape", "Tape Measure"),
    ("oform.tool_protractor", "Protractor"),
    ("oform.tool_back_edges", "Back Edges"),
    None,
    # Camera
    ("oform.tool_orbit", "Orbit"),
    ("oform.tool_pan", "Pan"),
    ("oform.tool_zoom", "Zoom"),
    ("oform.tool_zoom_extents", "Zoom Extents"),
    None,
    # Solids (overflow from classic SketchUp LTS — discoverability)
    ("oform.boolean_union", "Solid Union"),
    ("oform.boolean_subtract", "Solid Subtract"),
    ("oform.boolean_intersect", "Solid Intersect"),
)

# Named groups kept for header status / menus (not drawn as separate panels).
_GROUPS = (
    ("Select", (
        ("oform.tool_select", "Select"),
        ("oform.make_component", "Make Component"),
        ("oform.tool_paint", "Paint"),
        ("oform.tool_eraser", "Eraser"),
    )),
    ("Draw", (
        ("oform.tool_line", "Line"),
        ("oform.tool_freehand", "Freehand"),
        ("oform.tool_rectangle", "Rectangle"),
        ("oform.tool_circle", "Circle"),
        ("oform.tool_polygon", "Polygon"),
        ("oform.tool_arc", "Arc"),
    )),
    ("Edit", (
        ("oform.tool_move", "Move"),
        ("oform.tool_push_pull", "Push/Pull"),
        ("oform.tool_rotate", "Rotate"),
        ("oform.tool_follow_me", "Follow Me"),
        ("oform.tool_scale", "Scale"),
        ("oform.tool_offset", "Offset"),
    )),
    ("Measure", (
        ("oform.tool_tape", "Tape Measure"),
        ("oform.tool_protractor", "Protractor"),
        ("oform.tool_back_edges", "Back Edges"),
    )),
    ("View", (
        ("oform.tool_orbit", "Orbit"),
        ("oform.tool_pan", "Pan"),
        ("oform.tool_zoom", "Zoom"),
        ("oform.tool_zoom_extents", "Zoom Extents"),
    )),
    ("Solids", (
        ("oform.boolean_union", "Solid Union"),
        ("oform.boolean_subtract", "Solid Subtract"),
        ("oform.boolean_intersect", "Solid Intersect"),
        ("oform.solid_inspect", "Inspect Solid"),
    )),
)

_TOOLS = tuple(
    tool for item in _LARGE_TOOL_SET if item is not None for tool in (item,)
)
_GROUP_OF = {idname: group for group, tools in _GROUPS for idname, _label in tools}

# Built-in Blender icons approximating the SketchUp Large Tool Set glyphs.
_TOOL_ICONS = {
    "oform.tool_select": "CURSOR",
    "oform.make_component": "MOD_ARRAY",
    "oform.tool_eraser": "X",
    "oform.tool_paint": "BRUSH_DATA",
    "oform.tool_line": "LINE_DATA",
    "oform.tool_freehand": "GREASEPENCIL",
    "oform.tool_arc": "FORCE_CURVE",
    "oform.tool_rectangle": "MESH_PLANE",
    "oform.tool_circle": "MESH_CIRCLE",
    "oform.tool_polygon": "SEQ_CHROMA_SCOPE",
    "oform.tool_push_pull": "EMPTY_SINGLE_ARROW",
    "oform.tool_follow_me": "CURVE_PATH",
    "oform.tool_offset": "MOD_SOLIDIFY",
    "oform.tool_move": "ORIENTATION_GLOBAL",
    "oform.tool_rotate": "DRIVER_ROTATIONAL_DIFFERENCE",
    "oform.tool_scale": "FULLSCREEN_ENTER",
    "oform.boolean_union": "SELECT_EXTEND",
    "oform.boolean_subtract": "SELECT_SUBTRACT",
    "oform.boolean_intersect": "SELECT_INTERSECT",
    "oform.solid_inspect": "MESH_CUBE",
    "oform.tool_tape": "DRIVER_DISTANCE",
    "oform.tool_protractor": "DRIVER_ROTATIONAL_DIFFERENCE",
    "oform.tool_back_edges": "MOD_WIREFRAME",
    "oform.tool_orbit": "VIEW3D",
    "oform.tool_pan": "VIEW_PAN",
    "oform.tool_zoom": "VIEWZOOM",
    "oform.tool_zoom_extents": "ZOOM_ALL",
}


def _tool_icon(idname):
    return _TOOL_ICONS.get(idname, "NONE")


# Custom SketchUp-style glyphs (icons/*.png). Fallback to Blender icons.
_ICON_FILES = {
    "oform.tool_select": "select.png",
    "oform.make_component": "component.png",
    "oform.tool_paint": "paint.png",
    "oform.tool_eraser": "eraser.png",
    "oform.tool_line": "line.png",
    "oform.tool_freehand": "freehand.png",
    "oform.tool_rectangle": "rectangle.png",
    "oform.tool_circle": "circle.png",
    "oform.tool_polygon": "polygon.png",
    "oform.tool_arc": "arc.png",
    "oform.tool_move": "move.png",
    "oform.tool_push_pull": "push_pull.png",
    "oform.tool_rotate": "rotate.png",
    "oform.tool_follow_me": "follow_me.png",
    "oform.tool_scale": "scale.png",
    "oform.tool_offset": "offset.png",
    "oform.tool_tape": "tape.png",
    "oform.tool_protractor": "protractor.png",
    "oform.tool_back_edges": "back_edges.png",
    "oform.tool_orbit": "orbit.png",
    "oform.tool_pan": "pan.png",
    "oform.tool_zoom": "zoom.png",
    "oform.tool_zoom_extents": "zoom_extents.png",
    # Solids use built-in icons until dedicated glyphs ship
}
_TOOL_PREVIEWS = None


def _tool_icon_value(idname):
    """Custom preview icon id, or 0 to use the built-in ``icon=`` fallback."""
    global _TOOL_PREVIEWS
    path_name = _ICON_FILES.get(idname)
    if not path_name:
        return 0
    import os

    folder = os.path.join(os.path.dirname(os.path.abspath(__file__)), "icons")
    path = os.path.join(folder, path_name)
    if not os.path.isfile(path):
        return 0
    if _TOOL_PREVIEWS is None:
        import bpy.utils.previews

        _TOOL_PREVIEWS = bpy.utils.previews.new()
    key = idname.replace(".", "_")
    if key not in _TOOL_PREVIEWS:
        _TOOL_PREVIEWS.load(key, path, "IMAGE")
    return _TOOL_PREVIEWS[key].icon_id


def _release_tool_icons():
    global _TOOL_PREVIEWS
    if _TOOL_PREVIEWS is None:
        return
    import bpy.utils.previews

    bpy.utils.previews.remove(_TOOL_PREVIEWS)
    _TOOL_PREVIEWS = None

# (idname, key, shift, ctrl). Shift+Z and Ctrl+G are the modified shortcuts.
# SketchUp-aligned defaults: https://help.sketchup.com/en/default-keyboard-shortcuts
_SHORTCUTS = (
    ("oform.tool_select", "SPACE", False, False),
    ("oform.tool_eraser", "E", False, False),
    ("oform.tool_paint", "B", False, False),
    ("oform.tool_line", "L", False, False),
    ("oform.tool_freehand", "L", True, False),
    ("oform.tool_arc", "A", False, False),
    ("oform.tool_rectangle", "R", False, False),
    ("oform.tool_circle", "C", False, False),
    ("oform.tool_polygon", "N", False, False),
    ("oform.tool_push_pull", "P", False, False),
    ("oform.tool_follow_me", "J", False, False),
    ("oform.tool_offset", "F", False, False),
    ("oform.tool_move", "M", False, False),
    ("oform.tool_rotate", "Q", False, False),
    ("oform.tool_scale", "S", False, False),
    ("oform.tool_tape", "T", False, False),
    ("oform.tool_protractor", "X", False, False),
    ("oform.tool_back_edges", "K", False, False),
    ("oform.make_component", "G", False, False),
    ("oform.make_group", "G", False, True),
    ("oform.delete_selection", "DEL", False, False),
    ("oform.tool_orbit", "O", False, False),
    ("oform.tool_pan", "H", False, False),
    ("oform.tool_zoom", "Z", False, False),
    ("oform.tool_zoom_extents", "Z", True, False),
)

_PLAIN_KEYS = {item[1] for item in _SHORTCUTS if not item[2] and not item[3]}


def _operator_exists(idname):
    category, name = idname.split(".", 1)
    group = getattr(bpy.ops, category, None)
    return group is not None and hasattr(group, name)


def _view_item(layout, mode, text):
    operator = layout.operator("oform.view", text=text)
    operator.mode = mode


class OFORM_MT_file(Menu):
    bl_idname = "OFORM_MT_file"
    bl_label = "File"

    def draw(self, _context):
        layout = self.layout
        layout.operator("wm.read_homefile", text="New")
        layout.operator("wm.open_mainfile", text="Open...")
        layout.separator()
        layout.operator("wm.save_mainfile", text="Save")
        layout.operator("wm.save_as_mainfile", text="Save As...")
        layout.separator()
        if _operator_exists("wm.obj_export"):
            layout.operator("wm.obj_export", text="Export OBJ...")
        if _operator_exists("export_scene.gltf"):
            layout.operator("export_scene.gltf", text="Export glTF...")
        layout.separator()
        layout.operator("wm.quit_blender", text="Quit")


class OFORM_MT_edit(Menu):
    bl_idname = "OFORM_MT_edit"
    bl_label = "Edit"

    def draw(self, _context):
        layout = self.layout
        layout.operator("ed.undo", text="Undo")
        layout.operator("ed.redo", text="Redo")
        layout.separator()
        layout.operator("oform.delete_selection", text="Delete", icon="TRASH")
        layout.separator()
        layout.operator("oform.make_group", text="Make Group")
        layout.operator("oform.make_component", text="Make Component")
        layout.operator("oform.instance_component", text="Instance Component")
        layout.operator("oform.explode", text="Explode")
        layout.separator()
        layout.operator("oform.enter_group", text="Edit Group/Component")
        layout.operator("oform.exit_group", text="Close Group/Component")
        layout.separator()
        layout.operator("oform.boolean_union", text="Solid Union")
        layout.operator("oform.boolean_subtract", text="Solid Subtract")
        layout.operator("oform.boolean_intersect", text="Solid Intersect")
        layout.operator("oform.solid_inspect", text="Inspect Solid")


class OFORM_MT_solids(Menu):
    bl_idname = "OFORM_MT_solids"
    bl_label = "Solids"

    def draw(self, _context):
        layout = self.layout
        layout.operator("oform.boolean_union", text="Union", icon=_tool_icon("oform.boolean_union"))
        layout.operator(
            "oform.boolean_subtract", text="Subtract", icon=_tool_icon("oform.boolean_subtract")
        )
        layout.operator(
            "oform.boolean_intersect",
            text="Intersect",
            icon=_tool_icon("oform.boolean_intersect"),
        )
        layout.separator()
        layout.operator(
            "oform.solid_inspect", text="Inspect Solid", icon=_tool_icon("oform.solid_inspect")
        )


class OFORM_MT_view(Menu):
    bl_idname = "OFORM_MT_view"
    bl_label = "View"

    def draw(self, _context):
        layout = self.layout
        layout.operator("oform.tool_orbit", text="Orbit", icon=_tool_icon("oform.tool_orbit"))
        layout.operator("oform.tool_pan", text="Pan", icon=_tool_icon("oform.tool_pan"))
        layout.operator("oform.tool_zoom", text="Zoom", icon=_tool_icon("oform.tool_zoom"))
        layout.operator(
            "oform.tool_zoom_extents",
            text="Zoom Extents",
            icon=_tool_icon("oform.tool_zoom_extents"),
        )
        layout.separator()
        layout.operator(
            "oform.tool_back_edges",
            text="Back Edges",
            icon=_tool_icon("oform.tool_back_edges"),
        )


class OFORM_MT_camera(Menu):
    bl_idname = "OFORM_MT_camera"
    bl_label = "Camera"

    def draw(self, _context):
        layout = self.layout
        _view_item(layout, "TOP", "Top")
        _view_item(layout, "FRONT", "Front")
        _view_item(layout, "RIGHT", "Right")
        _view_item(layout, "ISO", "Iso")
        layout.separator()
        _view_item(layout, "PERSP", "Perspective")
        _view_item(layout, "ORTHO", "Parallel Projection")
        layout.separator()
        _view_item(layout, "EXTENTS", "Zoom Extents")


class OFORM_MT_draw(Menu):
    bl_idname = "OFORM_MT_draw"
    bl_label = "Draw"

    def draw(self, _context):
        layout = self.layout
        layout.operator("oform.tool_line", text="Line", icon=_tool_icon("oform.tool_line"))
        layout.operator("oform.tool_freehand", text="Freehand", icon=_tool_icon("oform.tool_freehand"))
        layout.operator("oform.tool_arc", text="Arc", icon=_tool_icon("oform.tool_arc"))
        layout.operator("oform.tool_rectangle", text="Rectangle", icon=_tool_icon("oform.tool_rectangle"))
        layout.operator("oform.tool_circle", text="Circle", icon=_tool_icon("oform.tool_circle"))
        layout.operator("oform.tool_polygon", text="Polygon", icon=_tool_icon("oform.tool_polygon"))


class OFORM_MT_tools(Menu):
    bl_idname = "OFORM_MT_tools"
    bl_label = "Tools"

    def draw(self, _context):
        layout = self.layout
        layout.operator("oform.tool_select", text="Select", icon=_tool_icon("oform.tool_select"))
        layout.operator("oform.tool_eraser", text="Eraser", icon=_tool_icon("oform.tool_eraser"))
        layout.operator("oform.tool_paint", text="Paint", icon=_tool_icon("oform.tool_paint"))
        layout.separator()
        layout.operator("oform.tool_push_pull", text="Push/Pull", icon=_tool_icon("oform.tool_push_pull"))
        layout.operator("oform.tool_follow_me", text="Follow Me", icon=_tool_icon("oform.tool_follow_me"))
        layout.operator("oform.tool_offset", text="Offset", icon=_tool_icon("oform.tool_offset"))
        layout.separator()
        layout.operator("oform.tool_move", text="Move", icon=_tool_icon("oform.tool_move"))
        layout.operator("oform.tool_rotate", text="Rotate", icon=_tool_icon("oform.tool_rotate"))
        layout.operator("oform.tool_scale", text="Scale", icon=_tool_icon("oform.tool_scale"))
        layout.separator()
        layout.operator("oform.tool_tape", text="Tape Measure", icon=_tool_icon("oform.tool_tape"))
        layout.operator("oform.tool_protractor", text="Protractor", icon=_tool_icon("oform.tool_protractor"))


class OFORM_MT_window(Menu):
    bl_idname = "OFORM_MT_window"
    bl_label = "Window"

    def draw(self, context):
        layout = self.layout
        dark = brand.is_dark(context)
        layout.operator(
            "oform.toggle_theme",
            text="Light Theme" if dark else "Dark Theme",
        ).mode = "LIGHT" if dark else "DARK"
        layout.separator()
        layout.operator("wm.window_fullscreen_toggle", text="Toggle Full Screen")
        layout.operator("oform.preferences_hint", text="Preferences...")


class OFORM_MT_help(Menu):
    bl_idname = "OFORM_MT_help"
    bl_label = "Help"

    def draw(self, _context):
        layout = self.layout
        layout.operator("wm.splash_about", text="About " + brand.PRODUCT)
        layout.separator()
        layout.label(text=brand.SUITE)
        layout.label(text=brand.DEVELOPED_BY)
        layout.separator()
        layout.label(text="Space Select    E Eraser    B Paint")
        layout.label(text="L Line    Shift+L Freehand    A Arc")
        layout.label(text="R Rectangle    C Circle    N Polygon")
        layout.label(text="P Push/Pull    J Follow Me    F Offset")
        layout.label(text="M Move    Q Rotate    S Scale")
        layout.label(text="T Tape    X Protractor    K Back Edges")
        layout.label(text="G Component    Ctrl+G Group    Delete removes selection")
        layout.label(text="O Orbit    H Pan    Z Zoom    Shift+Z Extents")
        layout.label(text="Double-click a group to edit. Esc closes.")
        layout.label(text="Select: click · double related · triple connected (Alt+1/2/3).")
        layout.label(text="Draw on a face to lock that working plane.")
        layout.label(text="Ask: type in the left Ask panel. Allow/Decline confirms changes.")
        layout.label(text="Ctrl Move/PushPull copies. Eraser: Ctrl soften, Shift hide.")
        layout.label(text="Arrow keys lock an axis. Type a length, then Enter (VCB in status).")
        layout.label(text="Solids: two meshes Object mode → rail Union / Subtract / Intersect.")
        layout.label(text="Hover a tool icon for its description. Shortcuts listed above.")


_MENUS = (
    OFORM_MT_file,
    OFORM_MT_edit,
    OFORM_MT_view,
    OFORM_MT_camera,
    OFORM_MT_draw,
    OFORM_MT_tools,
    OFORM_MT_solids,
    OFORM_MT_window,
    OFORM_MT_help,
)


def _draw_menus(self, _context):
    layout = self.layout
    for menu in _MENUS:
        layout.menu(menu.bl_idname)


def _draw_topbar(self, context):
    # Menu bar across the window, the same row the suite uses for File, Edit, and Help.
    if context.region.alignment == "RIGHT":
        return
    from bl_ui.space_topbar import TOPBAR_MT_editor_menus

    TOPBAR_MT_editor_menus.draw_collapsible(context, self.layout)


def _draw_splash(self, _context):
    layout = self.layout
    layout.operator_context = "EXEC_DEFAULT"
    column = layout.column()
    column.operator("wm.read_homefile", text="New")
    column.operator("wm.open_mainfile", text="Open...")
    column.separator()
    column.label(text=brand.PRODUCT)
    column.label(text=brand.TAGLINE)
    column.label(text=brand.PRINCIPLE)
    column.separator()
    column.label(text=brand.SUITE)
    credit = column.row()
    credit.enabled = False
    credit.label(text=brand.DEVELOPED_BY)


def _draw_about(self, _context):
    column = self.layout.column()
    column.label(text=brand.PRODUCT)
    column.label(text=brand.TAGLINE)
    column.label(text=brand.PRINCIPLE)
    column.separator()
    column.label(text=brand.SUITE)
    column.label(text=brand.DEVELOPED_BY)
    column.separator()
    column.label(text=brand.ENGINE_LINE + " " + bpy.app.version_string)
    column.label(text=brand.LICENSE_LINE)


def _draw_properties_header(self, _context):
    # Pane header: the mark, the product name, and the one-line role.
    row = self.layout.row(align=True)
    try:
        row.template_icon(icon_value=brand.icon_id(), scale=1.6)
    except Exception:
        pass
    row.label(text=brand.PRODUCT)
    subtitle = row.row()
    subtitle.enabled = False
    subtitle.label(text=brand.SUBTITLE)


def _active_tool(context):
    scene = context.scene
    active = getattr(scene, "oform_tool", "") if scene is not None else ""
    return active or "oform.tool_select"


def _draw_view3d_header(self, context):
    # Active tool once (avoid "Select · Select"); prefer custom glyph.
    active = _active_tool(context)
    label = dict(_TOOLS).get(active, "Select")
    group = _GROUP_OF.get(active, "Select")
    if group == label:
        text = label
    elif group in {"Select", "Draw", "Edit", "Measure", "View", "Solids"}:
        text = "{} · {}".format(group, label) if group != label else label
        if group == "Select" and label == "Select":
            text = "Select"
    else:
        text = label
    custom = _tool_icon_value(active)
    row = self.layout.row(align=True)
    if custom:
        row.label(text=text, icon_value=custom)
    else:
        row.label(text=text, icon=_tool_icon(active))


def _draw_status(self, context):
    layout = self.layout
    scene = context.scene
    status = getattr(scene, "oform_status", "") if scene is not None else ""
    measure = getattr(scene, "oform_measure", "") if scene is not None else ""
    layout.label(text=status)
    layout.separator_spacer()
    theme_row = layout.row(align=True)
    dark = brand.is_dark(context)
    theme_row.operator(
        "oform.toggle_theme",
        text="Dark" if not dark else "Light",
        depress=dark,
    ).mode = "TOGGLE"
    layout.separator()
    credit = layout.row()
    credit.enabled = False
    credit.label(text=brand.COMPANY_LINE)
    layout.separator()
    # Visible VCB (Measurements) — SketchUp-style typed dimensions surface.
    box = layout.row(align=True)
    box.alignment = "RIGHT"
    box.ui_units_x = 18
    if measure:
        box.label(text="VCB  " + measure, icon="DRIVER_DISTANCE")
    else:
        box.label(text="VCB")


def _swap(cls, name, fn):
    _DRAW.append((cls, name, getattr(cls, name)))
    setattr(cls, name, fn)


def register_properties():
    scene = bpy.types.Scene
    if hasattr(scene, "oform_status"):
        return
    scene.oform_status = StringProperty(name="O-Form Status", default="Select a tool")
    scene.oform_measure = StringProperty(name="O-Form Measure", default="")
    scene.oform_tool = StringProperty(name="O-Form Tool", default="")
    scene.oform_ask = StringProperty(
        name="Ask",
        description="Natural-language request (O-Draft Ask channel)",
        default="",
        options={"TEXTEDIT_UPDATE"},
    )
    scene.oform_color = FloatVectorProperty(
        name="O-Form Color",
        size=3,
        subtype="COLOR",
        min=0.0,
        max=1.0,
        default=brand.accent_rgb(),
    )


def unregister_properties():
    scene = bpy.types.Scene
    for name in ("oform_status", "oform_measure", "oform_tool", "oform_ask", "oform_color"):
        if hasattr(scene, name):
            delattr(scene, name)


def _conflicts(kmi):
    if kmi.idname.startswith("oform."):
        return False
    if kmi.idname == "object.mode_set" and kmi.type == "TAB":
        return True
    if kmi.type not in _PLAIN_KEYS:
        return False
    if kmi.ctrl or kmi.alt or kmi.oskey or getattr(kmi, "hyper", False):
        return False
    if kmi.type == "Z":
        return True
    return not kmi.shift


def _known_key(kmi):
    for saved, _active in _SAVED_KEYS:
        try:
            if saved == kmi:
                return True
        except ReferenceError:
            continue
    return False


def _deactivate_conflicts():
    user = bpy.context.window_manager.keyconfigs.user
    if user is None:
        return
    for keymap in user.keymaps:
        for kmi in keymap.keymap_items:
            if not _conflicts(kmi) or _known_key(kmi):
                continue
            _SAVED_KEYS.append((kmi, kmi.active))
            kmi.active = False


def _addon_has_tools():
    addon = bpy.context.window_manager.keyconfigs.addon
    if addon is None:
        return False
    for keymap in addon.keymaps:
        for kmi in keymap.keymap_items:
            if kmi.idname == "oform.tool_line":
                return True
    return False


def _setup_keymap():
    if _addon_has_tools():
        return
    addon = bpy.context.window_manager.keyconfigs.addon
    if addon is None:
        return
    _deactivate_conflicts()
    window_map = addon.keymaps.new(name="Window", space_type="EMPTY", region_type="WINDOW")
    view_map = addon.keymaps.new(name="3D View", space_type="VIEW_3D", region_type="WINDOW")
    _KEYMAPS.extend((window_map, view_map))
    for keymap in (window_map, view_map):
        for idname, key, shift, ctrl in _SHORTCUTS:
            keymap.keymap_items.new(idname, key, "PRESS", shift=shift, ctrl=ctrl)


def _remove_keymap():
    addon = None
    try:
        addon = bpy.context.window_manager.keyconfigs.addon
    except (AttributeError, RuntimeError):
        addon = None
    if addon is not None:
        for keymap in list(_KEYMAPS):
            try:
                addon.keymaps.remove(keymap)
            except (RuntimeError, ReferenceError):
                pass
    _KEYMAPS.clear()
    for kmi, active in _SAVED_KEYS:
        try:
            kmi.active = active
        except (ReferenceError, RuntimeError):
            pass
    _SAVED_KEYS.clear()


_REMOVED_ADDONS = (
    "io_anim_bvh",
    "pose_library",
    "rigify",
    "viewport_vr_preview",
    "node_wrangler",
    "hydra_storm",
)


def _enable_gltf():
    try:
        import addon_utils

        prefs = bpy.context.preferences
        for name in _REMOVED_ADDONS:
            addon = prefs.addons.get(name)
            if addon is None:
                continue
            # Module may already be gone — drop the preference entry itself.
            try:
                prefs.addons.remove(addon)
            except Exception:
                try:
                    addon_utils.disable(name, default_set=True)
                except Exception:
                    pass
        addon_utils.enable("io_scene_gltf2", default_set=False, persistent=True)
    except Exception:
        traceback.print_exc()


def _close_extra_areas(context):
    """Keep only the modeling shell: 3D view, top bar, status, left tools pane."""
    window = context.window
    screen = context.screen if context.screen is not None else getattr(window, "screen", None)
    if window is None or screen is None:
        return
    screen.show_statusbar = True
    keep = {"VIEW_3D", "TOPBAR", "STATUSBAR", "PROPERTIES"}
    for _guard in range(24):
        extra = [area for area in screen.areas if area.type not in keep]
        if not extra:
            return
        area = extra[0]
        region = next((item for item in area.regions if item.type == "WINDOW"), None)
        override = {"window": window, "screen": screen, "area": area}
        if region is not None:
            override["region"] = region
        before = len(screen.areas)
        try:
            with context.temp_override(**override):
                bpy.ops.screen.area_close()
        except (RuntimeError, TypeError):
            return
        if len(screen.areas) >= before:
            return


def _draw_large_tool_set(layout, context):
    """SketchUp Large Tool Set: compact square icon buttons (equal scale_x/y)."""
    active = _active_tool(context)
    column = layout.column(align=True)
    column.scale_x = _ICON_SCALE
    column.scale_y = _ICON_SCALE
    for item in _LARGE_TOOL_SET:
        if item is None:
            column.separator(factor=0.35)
            continue
        idname, _label = item
        is_active = active == idname
        custom = _tool_icon_value(idname)
        kwargs = {"text": "", "depress": is_active, "emboss": True}
        if custom:
            kwargs["icon_value"] = custom
        else:
            kwargs["icon"] = _tool_icon(idname)
        column.operator(idname, **kwargs)


class OFORM_PT_large_tool_set(Panel):
    """Primary SketchUp-style Large Tool Set rail."""

    bl_idname = "OFORM_PT_large_tool_set"
    bl_space_type = "PROPERTIES"
    bl_region_type = "WINDOW"
    bl_context = "scene"
    bl_label = "Tools"
    bl_order = 0
    bl_options = {"HIDE_HEADER"}

    def draw(self, context):
        _draw_large_tool_set(self.layout, context)


_NAV_PANELS = (OFORM_PT_large_tool_set,)


class OFORM_PT_properties(Panel):
    bl_idname = "OFORM_PT_properties"
    bl_space_type = "PROPERTIES"
    bl_region_type = "WINDOW"
    bl_context = "scene"
    bl_label = "Properties"
    bl_order = 40
    # Open by default so group context stays discoverable (Make Component is on the rail).

    def draw(self, context):
        import groups

        layout = self.layout
        obj = groups.context_object(context)
        entity = groups.get_entity(context)
        col = layout.column(align=True)
        col.label(text="Context: " + (obj.name if obj else "—"))
        col.label(text="Depth: {}".format(groups.context_depth(context)))
        if entity is not None:
            col.label(text="Entity: " + entity.name)
            col.label(text="Kind: " + groups.kind_of(entity))
        else:
            col.label(text="Entity: (none)")
        layout.separator()
        layout.operator("oform.make_group", text="Make Group", icon="GROUP")
        layout.operator("oform.explode", text="Explode")
        row = layout.row(align=True)
        row.operator("oform.enter_group", text="Edit")
        row.operator("oform.exit_group", text="Close")
        dark = brand.is_dark(context)
        layout.separator()
        layout.operator(
            "oform.toggle_theme",
            text="Switch to Light" if dark else "Switch to Dark",
        ).mode = "TOGGLE"
        layout.separator()
        layout.label(text="Solids")
        layout.operator("oform.boolean_union", text="Union", icon=_tool_icon("oform.boolean_union"))
        layout.operator(
            "oform.boolean_subtract", text="Subtract", icon=_tool_icon("oform.boolean_subtract")
        )
        layout.operator(
            "oform.boolean_intersect", text="Intersect", icon=_tool_icon("oform.boolean_intersect")
        )
        layout.operator("oform.solid_inspect", text="Inspect", icon=_tool_icon("oform.solid_inspect"))


class OFORM_PT_ask(Panel):
    bl_idname = "OFORM_PT_ask"
    bl_space_type = "PROPERTIES"
    bl_region_type = "WINDOW"
    bl_context = "scene"
    bl_label = "Ask"
    bl_order = 50

    def draw(self, context):
        layout = self.layout
        scene = context.scene
        layout.label(text=ai.CHANNEL_LABEL + " — type here")
        layout.prop(scene, "oform_ask", text="")
        layout.operator("oform.ask_submit", text="Ask", depress=False)
        phase = ai.phase(scene)
        _name, label = ai.pending(scene)
        if phase == "confirm" and label:
            box = layout.box()
            box.label(text=label)
            row = box.row(align=True)
            row.operator("oform.ask_allow", text="Allow")
            row.operator("oform.ask_decline", text="Decline")
        history = ai._history(scene)
        if history:
            layout.separator()
            layout.label(text="Recent")
            for item in history[-6:]:
                role = item.get("role", "")
                text = item.get("text", "")
                line = layout.row()
                line.enabled = False
                prefix = "You: " if role == "user" else "AI: "
                line.label(text=(prefix + text)[:64])


class OFORM_OT_toggle_theme(Operator):
    bl_idname = "oform.toggle_theme"
    bl_label = "Toggle Theme"
    bl_description = "Switch between light paper and dark graphite themes"
    bl_options = {"REGISTER"}

    mode: EnumProperty(
        items=(
            ("TOGGLE", "Toggle", ""),
            ("LIGHT", "Light", ""),
            ("DARK", "Dark", ""),
        ),
        default="TOGGLE",
    )

    def execute(self, context):
        if self.mode == "LIGHT":
            dark = False
        elif self.mode == "DARK":
            dark = True
        else:
            dark = not brand.is_dark(context)
        try:
            brand.apply_theme(context, dark=dark)
        except Exception:
            traceback.print_exc()
            return {"CANCELLED"}
        _style_view(context)
        for area in context.screen.areas:
            area.tag_redraw()
        context.scene.oform_status = "Dark theme" if dark else "Light theme"
        return {"FINISHED"}


class OFORM_OT_preferences_hint(Operator):
    """O-Form settings surface — avoids dumping users into Blender Preferences."""

    bl_idname = "oform.preferences_hint"
    bl_label = "Preferences"
    bl_description = "O-Form theme and modelling preferences"
    bl_options = {"REGISTER"}

    def invoke(self, context, _event):
        return context.window_manager.invoke_props_dialog(self, width=360)

    def draw(self, context):
        layout = self.layout
        layout.label(text=brand.PRODUCT + " preferences")
        layout.separator()
        dark = brand.is_dark(context)
        layout.operator(
            "oform.toggle_theme",
            text="Use Light Theme" if dark else "Use Dark Theme",
        ).mode = "LIGHT" if dark else "DARK"
        layout.separator()
        layout.label(text="Tools and Ask live in the left pane.")
        layout.label(text="Measurements (VCB) appear in the status bar.")
        layout.label(text="Shortcuts: Help menu.")

    def execute(self, context):
        context.scene.oform_status = "Theme: use Window menu or status bar toggle"
        return {"FINISHED"}


class OFORM_OT_ask_submit(Operator):
    bl_idname = "oform.ask_submit"
    bl_label = "Ask"
    bl_options = {"REGISTER"}

    def execute(self, context):
        text = getattr(context.scene, "oform_ask", "") or ""
        _phase, message = ai.propose(context, text)
        context.scene.oform_ask = ""
        context.scene.oform_status = message.split("\n")[0][:80]
        for area in context.screen.areas:
            area.tag_redraw()
        return {"FINISHED"}


class OFORM_OT_ask_allow(Operator):
    bl_idname = "oform.ask_allow"
    bl_label = "Allow"
    bl_options = {"REGISTER", "UNDO"}

    def execute(self, context):
        _phase, message = ai.allow(context)
        context.scene.oform_status = message.split("\n")[0][:80]
        for area in context.screen.areas:
            area.tag_redraw()
        return {"FINISHED"}


class OFORM_OT_ask_decline(Operator):
    bl_idname = "oform.ask_decline"
    bl_label = "Decline"
    bl_options = {"REGISTER"}

    def execute(self, context):
        _phase, message = ai.decline(context)
        context.scene.oform_status = message
        for area in context.screen.areas:
            area.tag_redraw()
        return {"FINISHED"}


def _draw_ask_overlay():
    """On-canvas hints only — never a fake text field (Ask lives in the left pane)."""
    try:
        import blf
        import gpu
        from gpu_extras.batch import batch_for_shader
    except ImportError:
        return

    context = bpy.context
    if context.area is None or context.area.type != "VIEW_3D":
        return
    region = context.region
    if region is None or region.type != "WINDOW":
        return
    scene = context.scene
    dark = brand.is_dark(context)
    colors = brand.palette(dark)
    phase = ai.phase(scene)
    _name, pending_label = ai.pending(scene)
    measure = (getattr(scene, "oform_measure", "") or "").strip()

    # Honest chrome: confirmation pointer, or VCB while measuring — not a faux input.
    if phase == "confirm" and pending_label:
        label = "Confirm in Ask (left pane): " + pending_label
        accent_rgb = colors["ai"]
    elif measure:
        label = "VCB  " + measure
        accent_rgb = colors.get("select", colors["ai"])
    else:
        return

    width = min(520, max(240, region.width - 48))
    height = 28
    x = (region.width - width) * 0.5
    y = 14
    shader = gpu.shader.from_builtin("UNIFORM_COLOR")
    fill = (*[c / 255.0 for c in (colors["surface"] if not dark else (31, 31, 31))], 0.92)
    accent = (*[c / 255.0 for c in accent_rgb], 1.0)
    verts = (
        (x, y), (x + width, y), (x + width, y + height), (x, y + height),
    )
    batch = batch_for_shader(shader, "TRI_FAN", {"pos": verts})
    gpu.state.blend_set("ALPHA")
    shader.bind()
    shader.uniform_float("color", fill)
    batch.draw(shader)
    accent_verts = (
        (x, y),
        (x + 4, y),
        (x + 4, y + height),
        (x, y + height),
    )
    shader.uniform_float("color", accent)
    batch_for_shader(shader, "TRI_FAN", {"pos": accent_verts}).draw(shader)
    gpu.state.blend_set("NONE")

    font_id = 0
    blf.size(font_id, 12)
    blf.color(font_id, *[c / 255.0 for c in colors["ink"]], 1.0)
    blf.position(font_id, x + 14, y + 8, 0)
    blf.draw(font_id, label[:70])


def _ensure_ask_overlay():
    if bpy.app.background:
        return None
    if _ASK_HANDLERS:
        return None
    try:
        handle = bpy.types.SpaceView3D.draw_handler_add(
            _draw_ask_overlay, (), "WINDOW", "POST_PIXEL"
        )
        _ASK_HANDLERS.append(handle)
    except Exception:
        traceback.print_exc()
    return None


def _remove_ask_overlay():
    while _ASK_HANDLERS:
        handle = _ASK_HANDLERS.pop()
        try:
            bpy.types.SpaceView3D.draw_handler_remove(handle, "WINDOW")
        except Exception:
            pass


_SIDE_PANELS = (OFORM_PT_properties, OFORM_PT_ask)
_SHELL_OPS = (
    OFORM_OT_toggle_theme,
    OFORM_OT_preferences_hint,
    OFORM_OT_ask_submit,
    OFORM_OT_ask_allow,
    OFORM_OT_ask_decline,
)

# Editors / UI modules O-Form does not ship. Classes are unregistered (removed),
# not poll-disabled or region-hidden.
_UNUSED_SPACE_TYPES = frozenset({
    "DOPESHEET_EDITOR",
    "GRAPH_EDITOR",
    "NLA_EDITOR",
    "SEQUENCE_EDITOR",
    "CLIP_EDITOR",
    "CONSOLE",
    "INFO",
    "TEXT_EDITOR",
    "NODE_EDITOR",
    "IMAGE_EDITOR",
    "OUTLINER",
    "FILE_BROWSER",
    "SPREADSHEET",
})

_UNUSED_BL_UI_MODULES = (
    "bl_ui.anim",
    "bl_ui.properties_animviz",
    "bl_ui.space_dopesheet",
    "bl_ui.space_graph",
    "bl_ui.space_nla",
    "bl_ui.space_sequencer",
    "bl_ui.space_clip",
    "bl_ui.space_console",
    "bl_ui.space_info",
    "bl_ui.space_text",
    "bl_ui.space_time",
    "bl_ui.space_node",
    "bl_ui.space_outliner",
    "bl_ui.space_spreadsheet",
    "bl_ui.space_view3d_sidebar",
    "bl_ui.space_view3d_toolbar",
    "bl_ui.properties_particle",
    "bl_ui.properties_physics_cloth",
    "bl_ui.properties_physics_dynamicpaint",
    "bl_ui.properties_physics_fluid",
    "bl_ui.properties_physics_softbody",
    "bl_ui.properties_physics_rigidbody",
    "bl_ui.properties_physics_rigidbody_constraint",
    "bl_ui.properties_constraint",
    "bl_ui.properties_data_armature",
    "bl_ui.properties_data_bone",
    "bl_ui.properties_data_camera",
    "bl_ui.properties_data_speaker",
    "bl_ui.properties_data_lightprobe",
    "bl_ui.properties_data_volume",
    "bl_ui.properties_data_grease_pencil",
    "bl_ui.properties_material_gpencil",
    "bl_ui.properties_grease_pencil_common",
    "bl_ui.properties_strip",
    "bl_ui.properties_strip_modifier",
)

_REMOVED_UI = []


def _unregister_ui_class(cls):
    if not getattr(cls, "is_registered", False):
        return
    if str(getattr(cls, "bl_idname", "")).startswith("OFORM_"):
        return
    try:
        bpy.utils.unregister_class(cls)
    except RuntimeError:
        return
    _REMOVED_UI.append(cls)


def _remove_unused_ui():
    """Unregister Blender UI that O-Form does not use (modeling shell only)."""
    import sys

    for name in _UNUSED_BL_UI_MODULES:
        mod = sys.modules.get(name)
        if mod is None:
            continue
        for cls in reversed(list(getattr(mod, "classes", ()))):
            _unregister_ui_class(cls)

    def walk(base):
        for sub in list(base.__subclasses__()):
            walk(sub)
            space = getattr(sub, "bl_space_type", None)
            region = getattr(sub, "bl_region_type", "")
            idname = str(getattr(sub, "bl_idname", ""))
            if idname.startswith("OFORM_"):
                continue
            if space in _UNUSED_SPACE_TYPES:
                _unregister_ui_class(sub)
                continue
            if space == "PROPERTIES":
                _unregister_ui_class(sub)
                continue
            if space == "VIEW_3D" and region in {"UI", "TOOLS", "TOOL_PROPS", "HUD"}:
                _unregister_ui_class(sub)
                continue
            if space == "VIEW_3D" and region == "HEADER" and "tool_header" in idname.lower():
                _unregister_ui_class(sub)

    for base_name in ("Panel", "Header", "Menu", "UIList"):
        base = getattr(bpy.types, base_name, None)
        if base is not None:
            walk(base)


_VIEW_REGION_OFF = (
    ("show_region_tool_header", False),
    ("show_region_toolbar", False),
    ("show_region_ui", False),
    ("show_region_hud", False),
    ("show_gizmo_navigate", False),
)


def _apply_view_region_flags(space):
    for attr, value in _VIEW_REGION_OFF:
        if hasattr(space, attr):
            try:
                setattr(space, attr, value)
            except (TypeError, AttributeError):
                pass


def _hide_empty_view_regions(context, area):
    """Collapse leftover TOOLS / N-panel strips (the black gap beside the canvas).

    New oform View3D spaces omit those regions in C++, but older screens and
    factory layouts can still carry an empty UI region that draws as a dark gutter
    between the viewport and the Properties tool rail.
    """
    space = area.spaces.active
    _apply_view_region_flags(space)
    window = context.window
    for region in list(area.regions):
        if region.type not in {
            "UI",
            "TOOLS",
            "TOOL_HEADER",
            "HUD",
            "ASSET_SHELF",
            "ASSET_SHELF_HEADER",
        }:
            continue
        # Still occupying layout space despite the flags — force closed once.
        if getattr(region, "width", 0) <= 8:
            continue
        try:
            with context.temp_override(window=window, area=area, region=region):
                bpy.ops.screen.region_toggle(region_type=region.type)
        except (RuntimeError, TypeError, AttributeError):
            pass
        _apply_view_region_flags(space)


def _hide_properties_nav(context, area):
    """Hide an empty Properties navigation bar if a leftover layout still has one."""
    window = context.window
    for region in list(area.regions):
        if region.type != "NAVIGATION_BAR":
            continue
        if getattr(region, "width", 0) <= 8:
            continue
        try:
            with context.temp_override(window=window, area=area, region=region):
                bpy.ops.screen.region_toggle(region_type="NAVIGATION_BAR")
        except (RuntimeError, TypeError, AttributeError):
            pass


def _style_view(context):
    """SketchUp-like work area: solid paper, RGB axes, no ground grid."""
    screen = context.screen
    if screen is None and context.window is not None:
        screen = context.window.screen
    if screen is None:
        return
    screen.show_statusbar = True
    dark = brand.is_dark(context)
    canvas = brand.palette(dark)["canvas"]
    for area in screen.areas:
        if area.type == "PROPERTIES":
            _hide_properties_nav(context, area)
            continue
        if area.type != "VIEW_3D":
            continue
        space = area.spaces.active
        space.show_region_header = True
        _hide_empty_view_regions(context, area)
        if hasattr(space, "show_gizmo"):
            space.show_gizmo = True
        space.shading.type = "SOLID"
        try:
            space.shading.light = "FLAT"
        except (TypeError, ValueError, AttributeError):
            pass
        try:
            space.shading.color_type = "MATERIAL"
        except (TypeError, ValueError):
            pass
        overlay = space.overlay
        overlay.show_overlays = True
        overlay.show_floor = False
        if hasattr(overlay, "show_ortho_grid"):
            overlay.show_ortho_grid = False
        if hasattr(overlay, "show_floor_grid"):
            overlay.show_floor_grid = False
        overlay.show_axis_x = True
        overlay.show_axis_y = True
        overlay.show_axis_z = True
        for attr in ("show_cursor", "show_object_origins", "show_text", "show_stats"):
            if hasattr(overlay, attr):
                setattr(overlay, attr, False)
        space.region_3d.view_perspective = "PERSP"
        # Theme gradient already paints the paper; keep world unused.
        world = context.scene.world
        if world is not None and hasattr(world, "color"):
            try:
                world.color = tuple(c / 255.0 for c in canvas)
            except (TypeError, ValueError):
                pass


def _startup_scene():
    context = bpy.context
    scene = context.scene
    view_layer = context.view_layer
    active = view_layer.objects.active
    if active is not None and active.mode != "OBJECT":
        try:
            bpy.ops.object.mode_set(mode="OBJECT")
        except RuntimeError:
            pass
    for name in ("Cube", "Light", "Camera"):
        obj = scene.objects.get(name)
        if obj is not None:
            bpy.data.objects.remove(obj, do_unlink=True)
    view_layer.update()
    scene.camera = None

    model = scene.objects.get("Model")
    if model is None or model.type != "MESH":
        mesh = bpy.data.meshes.new("Model")
        model = bpy.data.objects.new("Model", mesh)
        scene.collection.objects.link(model)
    elif model.name not in view_layer.objects:
        try:
            scene.collection.objects.link(model)
        except RuntimeError:
            pass
    for obj in list(view_layer.objects):
        if obj is None:
            continue
        obj.select_set(obj == model)
    view_layer.objects.active = model
    if model.mode != "EDIT":
        bpy.ops.object.mode_set(mode="EDIT")
    context.tool_settings.mesh_select_mode = (True, True, True)

    units = scene.unit_settings
    units.system = "METRIC"
    units.length_unit = "METERS"
    units.scale_length = 1.0

    inputs = context.preferences.inputs
    if hasattr(inputs, "view_rotate_method"):
        try:
            inputs.view_rotate_method = "TURNTABLE"
        except (TypeError, ValueError):
            pass

    # Default to light paper (SketchUp); dark is one click in the status bar.
    if "oform_dark" not in scene:
        scene["oform_dark"] = False
    try:
        brand.apply_theme(context, dark=brand.is_dark(context))
    except Exception:
        traceback.print_exc()
    if not bpy.app.background:
        _close_extra_areas(context)
        bpy.app.timers.register(_open_nav, first_interval=0.05)
    _style_view(context)
    if hasattr(scene, "oform_tool"):
        scene.oform_tool = "oform.tool_select"
        scene.oform_status = (
            "Click to select · Alt+1/2/3 · Ask in left pane · Esc closes groups"
        )
        scene.oform_measure = ""
    if hasattr(scene, "oform_ask"):
        scene.oform_ask = ""
    scene["oform_ask_phase"] = "idle"
    scene["oform_ask_history"] = "[]"
    if not bpy.app.background:
        bpy.app.timers.register(_arm_select, first_interval=0.25)
        bpy.app.timers.register(_ensure_ask_overlay, first_interval=0.3)


def _ensure_tools_on_left(screen):
    """Keep the Properties tool rail on the left of the 3D view (O-Draft shell)."""
    pair = [area for area in screen.areas if area.type in {"VIEW_3D", "PROPERTIES"}]
    if len(pair) < 2:
        return
    left, right = sorted(pair, key=lambda area: (area.x, area.width))[:2]
    if left.type == "PROPERTIES":
        return
    # Swap editor types so the left strip hosts Tools / Properties / Ask.
    if right.type == "PROPERTIES":
        right.type = "VIEW_3D"
    left.type = "PROPERTIES"


def _open_nav():
    """Split a left pane off the view, the same place the suite keeps its sections."""
    try:
        context = bpy.context
        window = context.window
        if window is None:
            return 0.2
        screen = window.screen
        if any(area.type == "PROPERTIES" for area in screen.areas):
            _ensure_tools_on_left(screen)
            _use_scene_context(screen)
            _style_view(context)
            return None
        view = next((area for area in screen.areas if area.type == "VIEW_3D"), None)
        if view is None:
            return None
        region = next((item for item in view.regions if item.type == "WINDOW"), None)
        override = {"window": window, "screen": screen, "area": view}
        if region is not None:
            override["region"] = region
        before = {area.as_pointer() for area in screen.areas}
        with context.temp_override(**override):
            result = bpy.ops.screen.area_split(direction="VERTICAL", factor=_SIDE_WIDTH)
        if "FINISHED" not in result:
            return None
        # New area is the one that did not exist before; pin tools to the left edge.
        created = [area for area in screen.areas if area.as_pointer() not in before]
        if not created:
            return None
        created[0].type = "PROPERTIES"
        _ensure_tools_on_left(screen)
        _use_scene_context(screen)
        _style_view(context)
        _remove_unused_ui()
    except Exception:
        traceback.print_exc()
    return None


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


def _arm_select():
    try:
        window = bpy.context.window
        if window is None:
            return None
        area = next((item for item in window.screen.areas if item.type == "VIEW_3D"), None)
        if area is None:
            return None
        region = next((item for item in area.regions if item.type == "WINDOW"), None)
        with bpy.context.temp_override(window=window, area=area, region=region):
            bpy.ops.oform.tool_select("INVOKE_DEFAULT")
    except Exception:
        return None
    return None


@persistent
def _load_post(_dummy):
    try:
        _setup_keymap()
    except Exception:
        traceback.print_exc()
    _enable_gltf()
    try:
        _remove_unused_ui()
    except Exception:
        traceback.print_exc()
    if not bpy.app.background:
        _ensure_ask_overlay()


@persistent
def _load_factory(_dummy):
    try:
        _startup_scene()
    except Exception:
        traceback.print_exc()


def register():
    global _UI
    if _UI:
        return
    for cls in _MENUS:
        if not getattr(cls, "is_registered", False):
            bpy.utils.register_class(cls)
    for cls in _SHELL_OPS:
        if not getattr(cls, "is_registered", False):
            bpy.utils.register_class(cls)
    from bl_operators.wm import WM_MT_splash, WM_MT_splash_about
    from bl_ui.space_properties import PROPERTIES_HT_header
    from bl_ui.space_statusbar import STATUSBAR_HT_header
    from bl_ui.space_topbar import TOPBAR_HT_upper_bar, TOPBAR_MT_editor_menus
    from bl_ui.space_view3d import VIEW3D_HT_header

    _remove_unused_ui()
    for cls in list(_NAV_PANELS) + list(_SIDE_PANELS):
        if not getattr(cls, "is_registered", False):
            bpy.utils.register_class(cls)
    _swap(TOPBAR_MT_editor_menus, "draw", _draw_menus)
    _swap(TOPBAR_HT_upper_bar, "draw", _draw_topbar)
    _swap(PROPERTIES_HT_header, "draw", _draw_properties_header)
    _swap(WM_MT_splash, "draw", _draw_splash)
    _swap(WM_MT_splash_about, "draw", _draw_about)
    _swap(VIEW3D_HT_header, "draw", _draw_view3d_header)
    _swap(STATUSBAR_HT_header, "draw", _draw_status)
    if _load_post not in bpy.app.handlers.load_post:
        bpy.app.handlers.load_post.append(_load_post)
    if _load_factory not in bpy.app.handlers.load_factory_startup_post:
        bpy.app.handlers.load_factory_startup_post.append(_load_factory)
    if not bpy.app.background:
        _ensure_ask_overlay()
    _UI = True


def unregister():
    global _UI
    if not _UI:
        return
    handlers = bpy.app.handlers
    if _load_post in handlers.load_post:
        handlers.load_post.remove(_load_post)
    if _load_factory in handlers.load_factory_startup_post:
        handlers.load_factory_startup_post.remove(_load_factory)
    _remove_ask_overlay()
    _remove_keymap()
    while _DRAW:
        cls, name, original = _DRAW.pop()
        setattr(cls, name, original)
    for cls in reversed(list(_SIDE_PANELS) + list(_NAV_PANELS)):
        if getattr(cls, "is_registered", False):
            bpy.utils.unregister_class(cls)
    for cls in reversed(_SHELL_OPS):
        if getattr(cls, "is_registered", False):
            bpy.utils.unregister_class(cls)
    # Unused Blender UI stays unregistered — do not re-add animation/physics chrome.
    _REMOVED_UI.clear()
    brand.release_icon()
    _release_tool_icons()
    for cls in reversed(_MENUS):
        if getattr(cls, "is_registered", False):
            bpy.utils.unregister_class(cls)
    _UI = False
