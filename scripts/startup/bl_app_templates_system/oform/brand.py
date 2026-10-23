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

# Suite shell tokens (aligned with O-Draft Fluent graphite / off-white).
# Light
FOG = (243, 243, 243)       # #F3F3F3 app background
SOFT = (249, 249, 249)      # #F9F9F9 surface / side pane
WHITE = (255, 255, 255)
INK = (26, 26, 26)          # #1A1A1A
MUTED = (92, 92, 92)        # #5C5C5C
EDGE = (209, 209, 209)      # #D1D1D1
# O-Form product accent (pastel green) + O-Draft AI channel blue.
ACCENT = (198, 230, 211)    # #C6E6D3 plate / soft highlight
ACCENT_ON = (143, 203, 170)  # #8FCBAA selected control fill
ACCENT_PRESS = (176, 216, 193)
SELECT = (63, 163, 106)     # #3FA36A selection / outline_sel
AI_ACCENT = (0, 120, 212)   # #0078D4 Ask channel (light)
CANVAS_LIGHT = (255, 255, 255)
# Dark (O-Draft graphite)
FOG_DARK = (27, 27, 27)     # #1B1B1B
SOFT_DARK = (32, 32, 32)    # #202020
SURFACE_DARK = (44, 44, 44) # #2C2C2C
INK_DARK = (243, 243, 243)  # #F3F3F3
MUTED_DARK = (200, 200, 200)
EDGE_DARK = (61, 61, 61)    # #3D3D3D
AI_ACCENT_DARK = (96, 205, 255)  # #60CDFF
CANVAS_DARK = (0, 0, 0)
SELECT_DARK = (96, 205, 255)

PRODUCT = "O-Form"
SUBTITLE = "Modeling"
TAGLINE = "Push/pull solid modeling"
PRINCIPLE = "Open Source. Built for Architects. Driven by Community."
SUITE = "OSAS · Open Source Architecture Suit"
DEVELOPER = "Human Centric Works"
COMPANY_LINE = "Human Centric Works · Hospet"
DEVELOPED_BY = "Developed by Human Centric Works · Hospet"
CLONE_OF = "A clone of Blender"
# End-user About line — engine credit without leading with Blender product chrome.
ENGINE_LINE = "Modelling engine"
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


def mark_svg(name=PRODUCT, plate=None, ink=None):
    """Official OSAS suite mark: C + lower arc + centre ring on a coloured plate.

    Sister apps use white strokes on saturated plates; O-Form uses ink on the
    pastel green plate so the glyph stays readable.
    """
    plate = plate or ACCENT
    ink = ink or INK
    fill = "#{:02X}{:02X}{:02X}".format(*plate)
    stroke = "#{:02X}{:02X}{:02X}".format(*ink)
    return (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 194 194" '
        'width="194" height="194">\n'
        "  <title>{}</title>\n"
        '  <rect width="194" height="194" rx="34" ry="34" fill="{}"/>\n'
        '  <g fill="none" stroke="{}">\n'
        '    <path d="M107 27A69 69 0 0 0 107 165" stroke-width="18"/>\n'
        '    <path d="M57 96A50 50 0 0 0 157 96" stroke-width="12"/>\n'
        '    <circle cx="107" cy="96" r="18.5" stroke-width="5"/>\n'
        "  </g>\n"
        "</svg>\n"
    ).format(name, fill, stroke)


def _ico(images):
    """ICO container of PNG frames (Vista+). ``images`` is [(size, png_bytes), ...]."""
    count = len(images)
    offset = 6 + 16 * count
    header = struct.pack("<HHH", 0, 1, count)
    entries = bytearray()
    body = bytearray()
    for size, data in images:
        w = 0 if size >= 256 else size
        h = 0 if size >= 256 else size
        entries.extend(struct.pack("<BBBBHHII", w, h, 0, 0, 1, 32, len(data), offset))
        body.extend(data)
        offset += len(data)
    return bytes(header) + bytes(entries) + bytes(body)


def _splash_rgba(width=960, height=420):
    """Lockup: pastel mark + O-Form / Modeling text (splash / about strip)."""
    out = bytearray(width * height * 4)
    # Transparent / white paper background
    for i in range(0, len(out), 4):
        out[i:i + 4] = bytes((255, 255, 255, 255))
    mark_size = min(height - 40, 280)
    mark = _rounded(mark_size, ACCENT, INK)
    ox = 48
    oy = (height - mark_size) // 2
    for py in range(mark_size):
        for px in range(mark_size):
            src = (py * mark_size + px) * 4
            a = mark[src + 3]
            if a == 0:
                continue
            dx = ox + px
            dy = oy + py
            if not (0 <= dx < width and 0 <= dy < height):
                continue
            dst = (dy * width + dx) * 4
            # Alpha-over onto white
            alpha = a / 255.0
            for c in range(3):
                out[dst + c] = int(round(mark[src + c] * alpha + out[dst + c] * (1.0 - alpha)))
            out[dst + 3] = 255
    # Title block is drawn by the UI splash; keep a wide mark-only strip usable
    # as a fallback bitmap. (Text raster would need a font atlas.)
    return out


def write_assets(extra_dirs=None):
    """Regenerate mark, splash, SVG, and multi-size ICO / favicon assets."""
    destinations = [_HERE]
    if extra_dirs:
        destinations.extend(extra_dirs)
    for dest in destinations:
        os.makedirs(dest, exist_ok=True)

    mark_256 = _rounded(256, ACCENT, INK)
    mark_png = _png(256, 256, mark_256)
    splash = _png(960, 420, _splash_rgba(960, 420))
    svg = mark_svg()

    sizes = (16, 24, 32, 48, 64, 128, 256)
    ico_frames = []
    for size in sizes:
        rgba = _rounded(size, ACCENT, INK)
        ico_frames.append((size, _png(size, size, rgba)))
    ico_bytes = _ico(ico_frames)

    # File-type icon: same mark (suite convention); Windows associates .blend → this.
    file_ico = ico_bytes

    for dest in destinations:
        with open(os.path.join(dest, "mark.png"), "wb") as handle:
            handle.write(mark_png)
        with open(os.path.join(dest, "mark-256.png"), "wb") as handle:
            handle.write(mark_png)
        with open(os.path.join(dest, "splash.png"), "wb") as handle:
            handle.write(splash)
        with open(os.path.join(dest, "mark.svg"), "w", encoding="utf-8") as handle:
            handle.write(svg)
        with open(os.path.join(dest, "app.ico"), "wb") as handle:
            handle.write(ico_bytes)
        with open(os.path.join(dest, "favicon.ico"), "wb") as handle:
            handle.write(ico_bytes)
        with open(os.path.join(dest, "file.ico"), "wb") as handle:
            handle.write(file_ico)

    return {
        "mark_png": mark_png,
        "ico": ico_bytes,
        "svg": svg,
        "splash": splash,
    }


def icon_id():
    """Preview icon for layout rows. Loaded on first draw, outside register()."""
    global _PREVIEWS
    import bpy
    path = os.path.join(_HERE, "mark.png")
    if not os.path.isfile(path):
        write_assets()
    if _PREVIEWS is None:
        import bpy.utils.previews
        _PREVIEWS = bpy.utils.previews.new()
        _PREVIEWS.load("mark", path, "IMAGE")
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


def is_dark(context):
    scene = getattr(context, "scene", None)
    if scene is not None and "oform_dark" in scene:
        return bool(scene.get("oform_dark", False))
    return False


def set_dark(context, dark):
    scene = getattr(context, "scene", None)
    if scene is not None:
        scene["oform_dark"] = bool(dark)


def palette(dark):
    """Shell + canvas colours for the active theme."""
    if dark:
        return {
            "fog": FOG_DARK,
            "soft": SOFT_DARK,
            "surface": SURFACE_DARK,
            "ink": INK_DARK,
            "muted": MUTED_DARK,
            "edge": EDGE_DARK,
            "accent": ACCENT,
            "accent_on": ACCENT_ON,
            "select": SELECT_DARK,
            "canvas": CANVAS_DARK,
            "ai": AI_ACCENT_DARK,
            "header": FOG_DARK,
            "panel": SOFT_DARK,
        }
    return {
        "fog": FOG,
        "soft": SOFT,
        "surface": WHITE,
        "ink": INK,
        "muted": MUTED,
        "edge": EDGE,
        "accent": ACCENT,
        "accent_on": ACCENT_ON,
        "select": SELECT,
        "canvas": CANVAS_LIGHT,
        "ai": AI_ACCENT,
        "header": WHITE,
        "panel": SOFT,
    }


def apply_theme(context, dark=None):
    """O-Draft-aligned shell: graphite or off-white chrome, black/white canvas."""
    if dark is None:
        dark = is_dark(context)
    set_dark(context, dark)
    colors = palette(dark)
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
        _widget(
            widget,
            colors["surface"],
            colors["ink"],
            inner_sel=colors["accent_on"],
            text_sel=INK if not dark else INK,
            outline=colors["edge"],
        )
    _paint(ui, "editor_border", _unit(colors["edge"]))
    _paint(ui, "editor_outline", (*_unit(colors["edge"]), 1.0))
    _paint(ui, "editor_outline_active", (*_unit(colors["accent"]), 1.0))
    _paint(ui, "widget_text_cursor", _unit(colors["ink"]))
    _paint(ui, "panel_header", (*_unit(colors["header"]), 1.0))
    _paint(ui, "panel_title", _unit(colors["ink"]))
    _paint(ui, "panel_text", _unit(colors["ink"]))
    _paint(ui, "panel_back", (*_unit(colors["panel"]), 1.0))
    _paint(ui, "panel_sub_back", (*_unit(colors["soft"]), 1.0))
    _paint(ui, "panel_outline", (*_unit(colors["edge"]), 1.0))
    _paint(ui, "panel_active", (*_unit(colors["accent"]), 1.0))
    if hasattr(ui, "panel_roundness"):
        ui.panel_roundness = 0.15

    for space_name in ("topbar", "view_3d", "properties", "statusbar", "outliner", "preferences"):
        space = getattr(theme, space_name, None)
        if space is None:
            continue
        slot = getattr(space, "space", space)
        back = colors["panel"] if space_name == "properties" else colors["fog"]
        header = colors["header"]
        _paint(slot, "header", (*_unit(header), 1.0))
        _paint(slot, "header_text", _unit(colors["ink"]))
        _paint(slot, "header_text_hi", _unit(colors["ink"]))
        _paint(slot, "title", _unit(colors["ink"]))
        _paint(slot, "text", _unit(colors["ink"]))
        _paint(slot, "text_hi", _unit(colors["ink"]))
        _paint(slot, "back", _unit(back))
        gradients = getattr(slot, "gradients", None)
        if gradients is not None and hasattr(gradients, "background_type"):
            try:
                gradients.background_type = "SINGLE_COLOR"
            except (TypeError, ValueError):
                pass
            # SketchUp / O-Draft canvas: solid paper, independent of chrome.
            canvas = colors["canvas"] if space_name == "view_3d" else colors["fog"]
            _paint(gradients, "high_gradient", _unit(canvas))
            _paint(gradients, "gradient", _unit(canvas))

    view = getattr(theme, "view_3d", None)
    if view is not None:
        wire = colors["muted"] if not dark else (160, 160, 160)
        _paint(view, "wire", _unit(wire))
        _paint(view, "wire_edit", _unit(colors["ink"]))
        _paint(view, "vertex", _unit(colors["ink"]))
        _paint(view, "vertex_select", _unit(colors["select"]))
        _paint(view, "edge_select", _unit(colors["select"]))
        face_fill = colors["canvas"]
        _paint(view, "face", (*_unit(face_fill), 0.0))
        _paint(view, "face_select", (*_unit(colors["accent"]), 0.45))
        _paint(view, "face_mode_select", (*_unit(colors["accent"]), 0.45))
        _paint(view, "grid", _unit(colors["edge"]))
        _paint(view, "object_selected", _unit(colors["select"]))
        _paint(view, "object_active", _unit(colors["select"]))

    font = os.path.join(os.environ.get("WINDIR", r"C:\Windows"), "Fonts", "segoeui.ttf")
    preferences = getattr(context.preferences, "view", None)
    if preferences is not None and hasattr(preferences, "show_splash"):
        preferences.show_splash = False
    if preferences is not None and hasattr(preferences, "font_path_ui") and os.path.isfile(font):
        if not preferences.font_path_ui:
            preferences.font_path_ui = font


if __name__ == "__main__":
    write_assets()
