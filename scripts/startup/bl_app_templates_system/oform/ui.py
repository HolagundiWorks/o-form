# SPDX-FileCopyrightText: 2026 O-Form Authors
#
# SPDX-License-Identifier: GPL-2.0-or-later

"""Menus, toolbar, status bar, keymap, and the factory modeling scene."""

import traceback

import bpy
from bpy.app.handlers import persistent
from bpy.props import FloatVectorProperty, StringProperty
from bpy.types import Menu, Panel

import brand

_DRAW = []
_KEYMAPS = []
_SAVED_KEYS = []
_UI = False

# Same shell as the suite: a menu bar, then a left pane whose sections are grouped by job.
_GROUPS = (
    ("Select", (
        ("oform.tool_select", "Select"),
        ("oform.tool_eraser", "Eraser"),
        ("oform.tool_paint", "Paint"),
    )),
    ("Draw", (
        ("oform.tool_line", "Line"),
        ("oform.tool_arc", "Arc"),
        ("oform.tool_rectangle", "Rectangle"),
        ("oform.tool_circle", "Circle"),
    )),
    ("Edit", (
        ("oform.tool_push_pull", "Push/Pull"),
        ("oform.tool_offset", "Offset"),
        ("oform.tool_move", "Move"),
        ("oform.tool_rotate", "Rotate"),
        ("oform.tool_scale", "Scale"),
    )),
    ("View", (
        ("oform.tool_orbit", "Orbit"),
        ("oform.tool_pan", "Pan"),
        ("oform.tool_zoom", "Zoom"),
        ("oform.tool_zoom_extents", "Zoom Extents"),
    )),
)

_TOOLS = tuple(tool for _group, tools in _GROUPS for tool in tools)
_GROUP_OF = {idname: group for group, tools in _GROUPS for idname, _label in tools}

# (idname, key, shift). Shift+Z is the only modified shortcut.
_SHORTCUTS = (
    ("oform.tool_select", "SPACE", False),
    ("oform.tool_eraser", "E", False),
    ("oform.tool_paint", "B", False),
    ("oform.tool_line", "L", False),
    ("oform.tool_arc", "A", False),
    ("oform.tool_rectangle", "R", False),
    ("oform.tool_circle", "C", False),
    ("oform.tool_push_pull", "P", False),
    ("oform.tool_offset", "F", False),
    ("oform.tool_move", "M", False),
    ("oform.tool_rotate", "Q", False),
    ("oform.tool_scale", "S", False),
    ("oform.tool_orbit", "O", False),
    ("oform.tool_pan", "H", False),
    ("oform.tool_zoom", "Z", False),
    ("oform.tool_zoom_extents", "Z", True),
)

_PLAIN_KEYS = {item[1] for item in _SHORTCUTS}


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


class OFORM_MT_view(Menu):
    bl_idname = "OFORM_MT_view"
    bl_label = "View"

    def draw(self, _context):
        layout = self.layout
        layout.operator("oform.tool_orbit", text="Orbit")
        layout.operator("oform.tool_pan", text="Pan")
        layout.operator("oform.tool_zoom", text="Zoom")
        layout.operator("oform.tool_zoom_extents", text="Zoom Extents")


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
        layout.operator("oform.tool_line", text="Line")
        layout.operator("oform.tool_arc", text="Arc")
        layout.operator("oform.tool_rectangle", text="Rectangle")
        layout.operator("oform.tool_circle", text="Circle")


class OFORM_MT_tools(Menu):
    bl_idname = "OFORM_MT_tools"
    bl_label = "Tools"

    def draw(self, _context):
        layout = self.layout
        layout.operator("oform.tool_select", text="Select")
        layout.operator("oform.tool_eraser", text="Eraser")
        layout.operator("oform.tool_paint", text="Paint")
        layout.separator()
        layout.operator("oform.tool_push_pull", text="Push/Pull")
        layout.operator("oform.tool_offset", text="Offset")
        layout.separator()
        layout.operator("oform.tool_move", text="Move")
        layout.operator("oform.tool_rotate", text="Rotate")
        layout.operator("oform.tool_scale", text="Scale")


class OFORM_MT_window(Menu):
    bl_idname = "OFORM_MT_window"
    bl_label = "Window"

    def draw(self, _context):
        layout = self.layout
        layout.operator("wm.window_fullscreen_toggle", text="Toggle Full Screen")
        layout.operator("screen.userpref_show", text="Preferences...")


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
        layout.label(text="L Line    A Arc    R Rectangle    C Circle")
        layout.label(text="P Push/Pull    F Offset    M Move")
        layout.label(text="Q Rotate    S Scale    O Orbit    H Pan    Z Zoom")
        layout.label(text="Shift+Z Zoom Extents")
        layout.label(text="Arrow keys lock an axis. Type a length, then Enter.")


_MENUS = (
    OFORM_MT_file,
    OFORM_MT_edit,
    OFORM_MT_view,
    OFORM_MT_camera,
    OFORM_MT_draw,
    OFORM_MT_tools,
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
    column.separator()
    column.label(text=brand.SUITE)
    credit = column.row()
    credit.enabled = False
    credit.label(text=brand.DEVELOPED_BY)


def _draw_about(self, _context):
    column = self.layout.column()
    column.label(text=brand.PRODUCT)
    column.label(text=brand.TAGLINE)
    column.separator()
    column.label(text=brand.SUITE)
    column.label(text=brand.DEVELOPED_BY)
    column.separator()
    column.label(text=brand.CLONE_OF + " " + bpy.app.version_string)
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
    # Page line for the work area: the group, then the tool that is on.
    active = _active_tool(context)
    label = dict(_TOOLS).get(active, "Select")
    group = _GROUP_OF.get(active, "Select")
    self.layout.label(text=group + "  ·  " + label)


def _draw_tool_header(self, _context):
    # Leave the mode switcher off this header. The region is hidden at startup.
    return


def _draw_status(self, context):
    layout = self.layout
    scene = context.scene
    status = getattr(scene, "oform_status", "") if scene is not None else ""
    measure = getattr(scene, "oform_measure", "") if scene is not None else ""
    layout.label(text=status)
    layout.separator_spacer()
    credit = layout.row()
    credit.enabled = False
    credit.label(text=brand.COMPANY_LINE)
    layout.separator()
    box = layout.row(align=True)
    box.alignment = "RIGHT"
    box.ui_units_x = 16
    box.label(text=measure if measure else " ")


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
    for name in ("oform_status", "oform_measure", "oform_tool", "oform_color"):
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
        for idname, key, shift in _SHORTCUTS:
            keymap.keymap_items.new(idname, key, "PRESS", shift=shift)


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


def _enable_gltf():
    try:
        import addon_utils
        addon_utils.enable("io_scene_gltf2", default_set=False, persistent=True)
    except Exception:
        traceback.print_exc()


def _close_extra_areas(context):
    window = context.window
    screen = context.screen if context.screen is not None else getattr(window, "screen", None)
    if window is None or screen is None:
        return
    screen.show_statusbar = True
    for _guard in range(16):
        extra = [
            area for area in screen.areas if area.type not in {"VIEW_3D", "TOPBAR", "STATUSBAR"}
        ]
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


def _draw_nav_group(layout, context, tools):
    active = _active_tool(context)
    column = layout.column(align=True)
    for idname, label in tools:
        column.operator(idname, text=label, depress=(active == idname))


def _nav_panel(group, tools, order):
    class NavPanel(Panel):
        bl_idname = "OFORM_PT_nav_" + group.lower()
        bl_space_type = "PROPERTIES"
        bl_region_type = "WINDOW"
        bl_context = "scene"
        bl_label = group
        bl_order = order

        def draw(self, context):
            _draw_nav_group(self.layout, context, tools)

    NavPanel.__name__ = "OFORM_PT_nav_" + group.lower()
    return NavPanel


_NAV_PANELS = [
    _nav_panel(group, tools, index) for index, (group, tools) in enumerate(_GROUPS)
]

_RETIRED_PANELS = []


def _retire_stock_panels():
    """Drop Blender's property tabs so the left pane is only the grouped tools."""
    found = []

    def walk(cls):
        for sub in list(cls.__subclasses__()):
            walk(sub)
        space = getattr(cls, "bl_space_type", None)
        if space == "PROPERTIES" and not str(getattr(cls, "bl_idname", "")).startswith("OFORM_"):
            found.append(cls)

    walk(bpy.types.Panel)
    for cls in found:
        if not getattr(cls, "is_registered", False):
            continue
        try:
            bpy.utils.unregister_class(cls)
        except RuntimeError:
            continue
        _RETIRED_PANELS.append(cls)


def _restore_stock_panels():
    for cls in reversed(_RETIRED_PANELS):
        if getattr(cls, "is_registered", False):
            continue
        try:
            bpy.utils.register_class(cls)
        except RuntimeError:
            pass
    _RETIRED_PANELS.clear()


def _style_view(context):
    screen = context.screen
    if screen is None and context.window is not None:
        screen = context.window.screen
    if screen is None:
        return
    screen.show_statusbar = True
    for area in screen.areas:
        if area.type != "VIEW_3D":
            continue
        space = area.spaces.active
        space.show_region_header = True
        if hasattr(space, "show_region_tool_header"):
            space.show_region_tool_header = False
        space.show_region_toolbar = False
        space.show_region_ui = False
        if hasattr(space, "show_gizmo_navigate"):
            space.show_gizmo_navigate = False
        space.shading.type = "SOLID"
        try:
            space.shading.color_type = "MATERIAL"
        except (TypeError, ValueError):
            pass
        space.overlay.show_overlays = True
        space.overlay.show_floor = True
        space.overlay.show_axis_x = True
        space.overlay.show_axis_y = True
        space.overlay.show_axis_z = True
        if hasattr(space.overlay, "show_text"):
            space.overlay.show_text = False
        if hasattr(space.overlay, "show_stats"):
            space.overlay.show_stats = False
        space.region_3d.view_perspective = "PERSP"


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

    try:
        brand.apply_theme(context)
    except Exception:
        traceback.print_exc()
    if not bpy.app.background:
        _close_extra_areas(context)
        bpy.app.timers.register(_open_nav, first_interval=0.05)
    _style_view(context)
    if hasattr(scene, "oform_tool"):
        scene.oform_tool = "oform.tool_select"
        scene.oform_status = "Click to select. L line, R rectangle, P push/pull"
        scene.oform_measure = ""
    if not bpy.app.background:
        bpy.app.timers.register(_arm_select, first_interval=0.25)


def _open_nav():
    """Split a left pane off the view, the same place the suite keeps its sections."""
    try:
        context = bpy.context
        window = context.window
        if window is None:
            return 0.2
        screen = window.screen
        if any(area.type == "PROPERTIES" for area in screen.areas):
            _use_scene_context(screen)
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
            result = bpy.ops.screen.area_split(direction="VERTICAL", factor=0.16)
        if "FINISHED" not in result:
            return None
        # A factor under one half adds the new area on the left. Coordinates are
        # still stale here, so the new area is the one that did not exist before.
        created = [area for area in screen.areas if area.as_pointer() not in before]
        if not created:
            return None
        created[0].type = "PROPERTIES"
        _use_scene_context(screen)
        _style_view(context)
        _retire_stock_panels()
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
        _retire_stock_panels()
    except Exception:
        traceback.print_exc()


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
    from bl_operators.wm import WM_MT_splash, WM_MT_splash_about
    from bl_ui.space_properties import PROPERTIES_HT_header
    from bl_ui.space_statusbar import STATUSBAR_HT_header
    from bl_ui.space_topbar import TOPBAR_HT_upper_bar, TOPBAR_MT_editor_menus
    from bl_ui.space_view3d import VIEW3D_HT_header, VIEW3D_HT_tool_header

    _retire_stock_panels()
    for cls in _NAV_PANELS:
        if not getattr(cls, "is_registered", False):
            bpy.utils.register_class(cls)
    _swap(TOPBAR_MT_editor_menus, "draw", _draw_menus)
    _swap(TOPBAR_HT_upper_bar, "draw", _draw_topbar)
    _swap(PROPERTIES_HT_header, "draw", _draw_properties_header)
    _swap(WM_MT_splash, "draw", _draw_splash)
    _swap(WM_MT_splash_about, "draw", _draw_about)
    _swap(VIEW3D_HT_header, "draw", _draw_view3d_header)
    _swap(VIEW3D_HT_tool_header, "draw", _draw_tool_header)
    _swap(STATUSBAR_HT_header, "draw", _draw_status)
    if _load_post not in bpy.app.handlers.load_post:
        bpy.app.handlers.load_post.append(_load_post)
    if _load_factory not in bpy.app.handlers.load_factory_startup_post:
        bpy.app.handlers.load_factory_startup_post.append(_load_factory)
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
    _remove_keymap()
    while _DRAW:
        cls, name, original = _DRAW.pop()
        setattr(cls, name, original)
    for cls in reversed(_NAV_PANELS):
        if getattr(cls, "is_registered", False):
            bpy.utils.unregister_class(cls)
    _restore_stock_panels()
    brand.release_icon()
    for cls in reversed(_MENUS):
        if getattr(cls, "is_registered", False):
            bpy.utils.unregister_class(cls)
    _UI = False
