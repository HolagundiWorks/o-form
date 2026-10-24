# SPDX-FileCopyrightText: 2026 O-Form Authors
#
# SPDX-License-Identifier: GPL-2.0-or-later

"""O-Form design system — O-Draft WinUI Density + ColorTokens.

Source of truth for chrome colours: ``brand`` (aligned with
``O-DRAFT/apps/aad-winui/Themes/ColorTokens.xaml``).
Sizing mirrors ``Density.cs`` / ``ControlTokens.xaml``.
"""

from __future__ import annotations

import brand

# ---------------------------------------------------------------------------
# Feature flags
# ---------------------------------------------------------------------------

UI_SHELL_V2 = False  # experimental right-inspector shell
UI_ARCH_LABELS = True


# ---------------------------------------------------------------------------
# Density (DIP) — O-Draft apps/aad-winui/Density.cs
# ---------------------------------------------------------------------------

SPACE_XS = 2
SPACE_SM = 4
SPACE_MD = 8
SPACE_LG = 12
SPACE_XL = 16

MIN_TARGET = 32
CONTROL_HEIGHT = 32
ICON_BUTTON = 32
ICON_SIZE = 20
SPLITTER = 8
SIDE_PANEL_DIP = 280
SIDE_PANEL_MIN_DIP = 180
SIDE_PANEL_MAX_DIP = 640
TOOL_STRIP_DIP = 40  # 32 button + padding (WinUI strip column)
ASK_BAR_MAX_DIP = 600
ASK_BAR_HEIGHT = 36
CORNER_CHROME = 3
CORNER_CONTROL = 4

# Blender UI scale ≈ DIP target / default button (~20 px).
ICON_SCALE = ICON_BUTTON / 20.0  # 1.6 → ~32 px targets

# Layout fractions (fallback when window width unknown).
TOOL_STRIP_RATIO = 0.04
SIDE_PANEL_RATIO = 0.18
LEFT_STACK_RATIO = TOOL_STRIP_RATIO + SIDE_PANEL_RATIO  # ~0.22
LEFT_STACK_MAX_RATIO = 0.38

# Aliases used by older ui.py / shell_v2.
LEFT_PANE_RATIO = LEFT_STACK_RATIO
LEFT_PANE_MAX_RATIO = LEFT_STACK_MAX_RATIO
LEFT_RAIL_RATIO = TOOL_STRIP_RATIO
RIGHT_BIM_RATIO = SIDE_PANEL_RATIO  # full BIM panel (~280 DIP), right of canvas
RIGHT_INSPECTOR_RATIO = 0.22
STATUS_HEIGHT_PX = 26
SPACE_BASE = SPACE_SM
RADIUS_CONTROL = CORNER_CONTROL
RADIUS_PANEL = 8

TYPE_UI = "Segoe UI"
TYPE_MONO = "Consolas"

# Width heuristics for dual PROPERTIES panes (px).
TOOL_STRIP_MAX_W = 72
SIDE_PANEL_MIN_W = 120


# ---------------------------------------------------------------------------
# Tokens — brand / ColorTokens.xaml
# ---------------------------------------------------------------------------

FOG = brand.FOG
SOFT = brand.SOFT
WHITE = brand.WHITE
INK = brand.INK
MUTED = brand.MUTED
EDGE = brand.EDGE
ACCENT = brand.ACCENT
ACCENT_ON = brand.ACCENT_ON
SELECT = brand.SELECT
AI_ACCENT = brand.AI_ACCENT
CANVAS_LIGHT = brand.CANVAS_LIGHT
FOG_DARK = brand.FOG_DARK
SOFT_DARK = brand.SOFT_DARK
SURFACE_DARK = brand.SURFACE_DARK
INK_DARK = brand.INK_DARK
MUTED_DARK = brand.MUTED_DARK
EDGE_DARK = brand.EDGE_DARK
AI_ACCENT_DARK = brand.AI_ACCENT_DARK
CANVAS_DARK = brand.CANVAS_DARK
SELECT_DARK = brand.SELECT_DARK


def tokens(dark: bool) -> dict:
    """Chrome tokens for the active theme (O-Draft / brand palette)."""
    p = brand.palette(dark)
    return {
        "app": p["fog"],
        "pane": p["panel"],
        "raised": p["surface"],
        "ink": p["ink"],
        "muted": p["muted"],
        "edge": p["edge"],
        "accent": p["accent"],
        "accent_on": p["accent_on"],
        "select": p["select"],
        "canvas": p["canvas"],
        "ai": p["ai"],
        "cad": p["cad"],
        "header": p["header"],
        "soft": p["soft"],
        "selected": p["selected"],
    }


# ---------------------------------------------------------------------------
# Tool strip — O-Draft ToolCatalog mapped to O-Form operators
# (WinUI: line, pline, circle, arc, rectang, move, copy, rotate, offset,
#  trim, erase, dimlinear, text, hatch — plus Select / Push-Pull for 3D.)
# ---------------------------------------------------------------------------

TOOL_STRIP = (
    ("oform.tool_select", "Select"),
    ("oform.tool_line", "Line"),
    ("oform.tool_circle", "Circle"),
    ("oform.tool_arc", "Arc"),
    ("oform.tool_rectangle", "Rectangle"),
    None,
    ("oform.tool_move", "Move"),
    ("oform.tool_rotate", "Rotate"),
    ("oform.tool_offset", "Offset"),
    ("oform.tool_push_pull", "Push/Pull"),
    ("oform.boolean_trim", "Trim"),
    ("oform.tool_eraser", "Eraser"),
    None,
    ("oform.tool_tape", "Measure"),
    ("oform.tool_paint", "Paint"),
)

# BIM toolbar — classify / storey / suite sync (same 32 DIP targets as TOOL_STRIP).
BIM_TOOLBAR = (
    ("oform.bim_classify", "Auto-Classify"),
    ("oform.bim_set_class", "Set IFC Class"),
    ("oform.bim_assign_storey", "Assign Storey"),
    ("oform.bim_inspect", "Inspect"),
    None,
    ("oform.bim_suite_push", "Push BIM + Take-off"),
    ("oform.bim_takeoff_status", "Take-off Status"),
    ("oform.open_project", "Open Project"),
    ("oform.live_sync_toggle", "Live Sync"),
)

PRIMARY_TOOLS = tuple(t for t in TOOL_STRIP if t is not None)
BIM_TOOLS = tuple(t for t in BIM_TOOLBAR if t is not None)
RAIL_GROUPS = ()
INSPECTOR_SECTIONS = ("Entity Info", "BIM", "Instructor", "Ask")
STATUS_FIELDS = ("command", "units", "view", "selection", "vcb")


def shell_enabled() -> bool:
    return bool(UI_SHELL_V2)


def left_stack_ratio(window_width: int) -> float:
    """Fraction of window for tool strip + side panel (~320 DIP)."""
    total = float(TOOL_STRIP_DIP + SIDE_PANEL_DIP)
    w = max(int(window_width), 800)
    return min(LEFT_STACK_MAX_RATIO, max(0.16, total / w))


def tool_strip_of_stack() -> float:
    """Strip share of the left stack (strip | panel)."""
    return float(TOOL_STRIP_DIP) / float(TOOL_STRIP_DIP + SIDE_PANEL_DIP)
