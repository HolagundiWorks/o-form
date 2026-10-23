# SPDX-FileCopyrightText: 2026 O-Form Authors
#
# SPDX-License-Identifier: GPL-2.0-or-later

"""O-Form identity — OSAS suite mark, light shell, pastel green accent.

O-Form is a clone of Blender. Display strings follow the same pattern as
O-CoreOp / O-Studio / O-Draft: product name, one-line role, suite line,
developer credit. The arcs are the suite mark (left half-ring, lower
half-ring, centre ring). Sister apps fill the plate with a saturated
accent and draw white arcs; O-Form's pastel plate needs ink arcs.
"""

import os
import struct
import zlib

_HERE = os.path.dirname(os.path.abspath(__file__))

# Suite light shell (Architecture Office Suit / OSAS).
FOG = (242, 244, 247)       # #F2F4F7 page background
SOFT = (236, 238, 242)      # #ECEEF2 navigation pane
WHITE = (255, 255, 255)
INK = (23, 24, 27)          # #17181B
MUTED = (92, 99, 112)       # #5C6370
EDGE = (208, 212, 220)      # #D0D4DC
# Pastel green accent. Ink sits on it; SELECT is only for viewport picks.
ACCENT = (198, 230, 211)    # #C6E6D3 plate / soft highlight
ACCENT_ON = (143, 203, 170)  # #8FCBAA selected control fill
ACCENT_PRESS = (176, 216, 193)
SELECT = (63, 163, 106)     # #3FA36A selection / outline_sel

PRODUCT = "O-Form"
SUBTITLE = "Modeling"
TAGLINE = "Push/pull solid modeling"
SUITE = "OSAS · Open Source Architecture Suit"
SUITE_FULL = "OSAS, the Open Source Architecture Suit"
DEVELOPER = "Human Centric Works"
COMPANY_LINE = "Human Centric Works · Hospet"
DEVELOPED_BY = "Developed by Human Centric Works · Hospet"
CLONE_OF = "A clone of Blender"
LICENSE_LINE = "Licensed under the GNU General Public License, version 2 or later"

# Suite mark, in the 194 box used by the other apps.
_ART = 194.0
_CENTRE = (107.0, 96.0)
_C_BAND = (60.0, 78.0)
_ARC_BAND = (44.0, 56.0)
_RING_BAND = (16.0, 21.0)

_PREVIEWS = None


def _unit(color):
    return tuple(channel / 255.0 for channel in color)


def accent_rgb():
    return _unit(ACCENT)


def _in_mark(x, y):
    dx = x - _CENTRE[0]
    dy = y - _CENTRE[1]
    radius = (dx * dx + dy * dy) ** 0.5
    if _C_BAND[0] <= radius <= _C_BAND[1] and dx <= 0.0:
        return True
    if _ARC_BAND[0] <= radius <= _ARC_BAND[1] and dy >= 0.0:
        return True
    return _RING_BAND[0] <= radius <= _RING_BAND[1]


def _png(width, height, rgba):
    raw = bytearray()
    stride = width * 4
    for y in range(height):
        raw.append(0)
        start = y * stride
        raw.extend(rgba[start:start + stride])

    def chunk(tag, data):
        body = tag + data
        return struct.pack(">I", len(data)) + body + struct.pack(">I", zlib.crc32(body) & 0xFFFFFFFF)

    ihdr = struct.pack(">IIBBBBB", width, height, 8, 6, 0, 0, 0)
    return b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", ihdr) + chunk(b"IDAT", zlib.compress(bytes(raw), 9)) + chunk(b"IEND", b"")


def _rounded(size, plate, mark, radius_factor=0.22):
    """Square icon. `plate` and `mark` are RGB byte triples."""
    samples = 4
    radius = size * radius_factor
    out = bytearray(size * size * 4)
    for py in range(size):
        for px in range(size):
            cover = 0
            ink = 0
            for sy in range(samples):
                for sx in range(samples):
                    u = px + (sx + 0.5) / samples
                    v = py + (sy + 0.5) / samples
                    cx = min(max(u, radius), size - radius)
                    cy = min(max(v, radius), size - radius)
                    if (u - cx) ** 2 + (v - cy) ** 2 > radius * radius:
                        continue
                    cover += 1
                    if _in_mark(u / size * _ART, v / size * _ART):
                        ink += 1
            if cover == 0:
                continue
            total = samples * samples
            alpha = int(round(255 * cover / total))
            mix = ink / cover
            rgb = tuple(int(round(mark[c] * mix + plate[c] * (1.0 - mix))) for c in range(3))
            index = (py * size + px) * 4
            out[index:index + 4] = bytes((*rgb, alpha))
    return out


def write_assets():
    mark = _rounded(256, ACCENT, INK)
    with open(os.path.join(_HERE, "mark.png"), "wb") as handle:
        handle.write(_png(256, 256, mark))


def icon_id():
    """Preview icon for layout rows. Loaded on first draw, outside register()."""
    global _PREVIEWS
    import bpy
    if _PREVIEWS is None:
        import bpy.utils.previews
        _PREVIEWS = bpy.utils.previews.new()
        _PREVIEWS.load("mark", os.path.join(_HERE, "mark.png"), "IMAGE")
    return _PREVIEWS["mark"].icon_id


def release_icon():
    global _PREVIEWS
    if _PREVIEWS is None:
        return
    import bpy.utils.previews
    bpy.utils.previews.remove(_PREVIEWS)
    _PREVIEWS = None


def _paint(obj, name, color):
    if obj is None or not hasattr(obj, name):
        return
    current = getattr(obj, name)
    try:
        length = len(current)
    except TypeError:
        setattr(obj, name, color[0] if not isinstance(color, tuple) else color)
        return
    value = color[:length]
    if length == 4 and len(color) == 3:
        value = (*color, 1.0)
    try:
        setattr(obj, name, value)
    except (TypeError, ValueError):
        pass


def _widget(widget, inner, text, inner_sel=None, text_sel=None, outline=None):
    _paint(widget, "inner", (*_unit(inner), 1.0))
    _paint(widget, "text", _unit(text))
    _paint(widget, "inner_sel", (*_unit(inner_sel or ACCENT_ON), 1.0))
    _paint(widget, "text_sel", _unit(text_sel or INK))
    _paint(widget, "outline", (*_unit(outline or EDGE), 1.0))
    _paint(widget, "outline_sel", (*_unit(SELECT), 1.0))
    _paint(widget, "item", (*_unit(ACCENT), 1.0))
    if hasattr(widget, "show_shaded"):
        widget.show_shaded = False
    if hasattr(widget, "shadetop"):
        widget.shadetop = 0
        widget.shadedown = 0
    if hasattr(widget, "roundness"):
        widget.roundness = 0.4


def apply_theme(context):
    """Light suite shell: fog page, white bars, ink text, pastel green accent."""
    theme = context.preferences.themes[0]
    ui = theme.user_interface
    names = (
        "wcol_regular", "wcol_tool", "wcol_toolbar_item", "wcol_radio",
        "wcol_text", "wcol_option", "wcol_toggle", "wcol_num", "wcol_numslider",
        "wcol_box", "wcol_menu", "wcol_pulldown", "wcol_menu_back",
        "wcol_pie_menu", "wcol_tooltip", "wcol_menu_item", "wcol_scroll",
        "wcol_progress", "wcol_list_item", "wcol_state",
    )
    for name in names:
        widget = getattr(ui, name, None)
        if widget is None or not hasattr(widget, "inner"):
            continue
        if name in {"wcol_menu_back", "wcol_tooltip", "wcol_box"}:
            _widget(widget, WHITE, INK)
        else:
            _widget(widget, WHITE, INK)
    _paint(ui, "editor_border", _unit(EDGE))
    _paint(ui, "editor_outline", (*_unit(EDGE), 1.0))
    _paint(ui, "editor_outline_active", (*_unit(ACCENT_PRESS), 1.0))
    _paint(ui, "widget_text_cursor", _unit(INK))
    _paint(ui, "panel_header", (*_unit(WHITE), 1.0))
    _paint(ui, "panel_title", _unit(INK))
    _paint(ui, "panel_text", _unit(INK))
    _paint(ui, "panel_back", (*_unit(WHITE), 1.0))
    _paint(ui, "panel_sub_back", (*_unit(SOFT), 1.0))
    _paint(ui, "panel_outline", (*_unit(EDGE), 1.0))
    _paint(ui, "panel_active", (*_unit(ACCENT), 1.0))
    if hasattr(ui, "panel_roundness"):
        ui.panel_roundness = 0.2

    for space_name in ("topbar", "view_3d", "properties", "statusbar", "outliner", "preferences"):
        space = getattr(theme, space_name, None)
        if space is None:
            continue
        colors = getattr(space, "space", space)
        _paint(colors, "header", (*_unit(WHITE), 1.0))
        _paint(colors, "header_text", _unit(INK))
        _paint(colors, "header_text_hi", _unit(INK))
        _paint(colors, "title", _unit(INK))
        _paint(colors, "text", _unit(INK))
        _paint(colors, "text_hi", _unit(INK))
        _paint(colors, "back", _unit(SOFT if space_name == "properties" else FOG))
        gradients = getattr(colors, "gradients", None)
        if gradients is not None and hasattr(gradients, "background_type"):
            try:
                gradients.background_type = "SINGLE_COLOR"
            except (TypeError, ValueError):
                pass
            _paint(gradients, "high_gradient", _unit(FOG))
            _paint(gradients, "gradient", _unit(FOG))

    view = getattr(theme, "view_3d", None)
    if view is not None:
        _paint(view, "wire", _unit(MUTED))
        _paint(view, "wire_edit", _unit(INK))
        _paint(view, "vertex", _unit(INK))
        _paint(view, "vertex_select", _unit(SELECT))
        _paint(view, "edge_select", _unit(SELECT))
        _paint(view, "face", (*_unit(WHITE), 0.0))
        _paint(view, "face_select", (*_unit(ACCENT), 0.55))
        _paint(view, "face_mode_select", (*_unit(ACCENT), 0.55))
        _paint(view, "grid", _unit(EDGE))
        _paint(view, "object_selected", _unit(SELECT))
        _paint(view, "object_active", _unit(SELECT))

    font = os.path.join(os.environ.get("WINDIR", r"C:\Windows"), "Fonts", "segoeui.ttf")
    preferences = getattr(context.preferences, "view", None)
    if preferences is not None and hasattr(preferences, "show_splash"):
        preferences.show_splash = False
    if preferences is not None and hasattr(preferences, "font_path_ui") and os.path.isfile(font):
        if not preferences.font_path_ui:
            preferences.font_path_ui = font


if __name__ == "__main__":
    write_assets()
