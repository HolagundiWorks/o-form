# SPDX-FileCopyrightText: 2026 O-Form Authors
#
# SPDX-License-Identifier: GPL-2.0-or-later

"""Multi-unit length parsing and display for the VCB.

Internal geometry stays in metres (Blender). Typed values accept mixed units:

- ``10'`` / ``10ft`` → feet
- ``6"`` / ``6in`` → inches
- ``5'6"`` / ``5' 6`` → feet + inches
- ``100mm`` → millimetres
- ``30cm`` → centimetres
- ``2.5m`` → metres

A bare number uses the model's current length unit.
"""

from __future__ import annotations

import re

PROP_LENGTH_UNIT = "oform_length_unit"

# Metres per unit.
METER = 1.0
MILLIMETER = 0.001
CENTIMETER = 0.01
INCH = 0.0254
FOOT = 0.3048

# Display / default-unit ids shown in the UI.
UNIT_CHOICES = (
    ("m", "Meters (m)", METER),
    ("mm", "Millimeters (mm)", MILLIMETER),
    ("cm", "Centimeters (cm)", CENTIMETER),
    ("ft", "Feet (')", FOOT),
    ("in", "Inches (\")", INCH),
)

_UNIT_SCALE = {key: scale for key, _label, scale in UNIT_CHOICES}
_UNIT_LABEL = {key: label for key, label, _scale in UNIT_CHOICES}

# 5'6", 5' 6, 5'-6", 5ft 6in, 5 ft 6"
_FEET_INCHES = re.compile(
    r"""
    ^\s*
    (?P<sign>-)?
    (?P<feet>\d+(?:\.\d+)?)\s*(?:'|ft|feet)\s*[- ]?\s*
    (?:(?P<inches>\d+(?:\.\d+)?)\s*(?:"|in|inch|inches)?)?
    \s*$
    """,
    re.IGNORECASE | re.VERBOSE,
)

# Single-quantity with optional unit suffix.
_SINGLE = re.compile(
    r"""
    ^\s*
    (?P<sign>-)?
    (?P<value>\d+(?:\.\d+)?)\s*
    (?P<unit>
        mm|cm|m|
        ft|feet|'|
        in|inch|inches|"
    )?
    \s*$
    """,
    re.IGNORECASE | re.VERBOSE,
)

# Characters the VCB accepts while typing a length (plus array / segment tokens).
VCB_CHARS = "0123456789.,-sSmMcCxX*/'\"fFtTiInN "


def scale_of(unit: str) -> float:
    return _UNIT_SCALE.get((unit or "m").lower(), METER)


def label_of(unit: str) -> str:
    key = (unit or "m").lower()
    return _UNIT_LABEL.get(key, key)


def normalize_unit(token: str) -> str:
    raw = (token or "").strip().lower()
    if raw in {"", "m", "meter", "meters", "metre", "metres"}:
        return "m"
    if raw in {"mm", "millimeter", "millimeters", "millimetre", "millimetres"}:
        return "mm"
    if raw in {"cm", "centimeter", "centimeters", "centimetre", "centimetres"}:
        return "cm"
    if raw in {"'", "ft", "foot", "feet"}:
        return "ft"
    if raw in {'"', "in", "inch", "inches"}:
        return "in"
    return "m"


def current_unit(scene) -> str:
    """Active length unit for bare numbers and display."""
    if scene is not None:
        custom = str(scene.get(PROP_LENGTH_UNIT, "") or "").strip().lower()
        if custom in _UNIT_SCALE:
            return custom
        try:
            settings = scene.unit_settings
            if settings.system == "IMPERIAL":
                if settings.length_unit == "INCHES":
                    return "in"
                return "ft"
            length = settings.length_unit
            if length == "MILLIMETERS":
                return "mm"
            if length == "CENTIMETERS":
                return "cm"
            if length == "KILOMETERS":
                return "m"
            return "m"
        except Exception:
            pass
    return "m"


def set_unit(scene, unit: str) -> str:
    """Persist the model length unit and sync Blender unit_settings."""
    key = normalize_unit(unit)
    if scene is None:
        return key
    scene[PROP_LENGTH_UNIT] = key
    try:
        settings = scene.unit_settings
        settings.scale_length = 1.0
        if key in {"ft", "in"}:
            settings.system = "IMPERIAL"
            settings.length_unit = "INCHES" if key == "in" else "FEET"
        else:
            settings.system = "METRIC"
            settings.length_unit = {
                "mm": "MILLIMETERS",
                "cm": "CENTIMETERS",
                "m": "METERS",
            }.get(key, "METERS")
    except Exception:
        pass
    return key


def parse_length(text, default_unit: str = "m") -> float:
    """Parse a typed length into metres. Raises ValueError on failure."""
    raw = (text or "").strip()
    if not raw:
        raise ValueError("empty")
    # Allow comma as decimal separator (EU).
    raw = raw.replace(",", ".")
    default = normalize_unit(default_unit)

    match = _FEET_INCHES.match(raw)
    if match:
        sign = -1.0 if match.group("sign") else 1.0
        feet = float(match.group("feet"))
        inches = float(match.group("inches") or 0.0)
        return sign * (feet * FOOT + inches * INCH)

    match = _SINGLE.match(raw)
    if match:
        sign = -1.0 if match.group("sign") else 1.0
        value = float(match.group("value"))
        unit_tok = match.group("unit")
        unit = normalize_unit(unit_tok) if unit_tok else default
        return sign * value * scale_of(unit)

    raise ValueError("bad length: " + text)


def format_length(meters: float, unit: str = None, scene=None, precision: int = None) -> str:
    """Format metres for the VCB using the active (or given) unit."""
    if meters is None:
        return ""
    key = normalize_unit(unit) if unit else current_unit(scene)
    value = float(meters)

    if key == "ft":
        # Architectural feet + inches when it reads cleanly.
        sign = "-" if value < 0 else ""
        total_in = abs(value) / INCH
        feet = int(total_in // 12.0)
        inches = total_in - feet * 12.0
        if precision is None:
            # Whole inches when close; otherwise one decimal.
            if abs(inches - round(inches)) < 0.05:
                inches_i = int(round(inches))
                if inches_i == 12:
                    feet += 1
                    inches_i = 0
                if feet and inches_i:
                    return "{}{:d}'{:d}\"".format(sign, feet, inches_i)
                if feet:
                    return "{}{:d}'".format(sign, feet)
                return '{}{:d}"'.format(sign, inches_i)
            if feet:
                return "{}{:d}'{:.1f}\"".format(sign, feet, inches)
            return '{}{:.1f}"'.format(sign, inches)
        return "{}{:.{}f}'".format(sign, abs(value) / FOOT, precision)

    scale = scale_of(key)
    amount = value / scale
    if precision is None:
        if key == "mm":
            precision = 1 if abs(amount) >= 10 else 2
        elif key == "in":
            precision = 2
        else:
            precision = 3
    suffix = {"m": "m", "mm": "mm", "cm": "cm", "in": '"', "ft": "'"}.get(key, "m")
    return "{:.{}f}{}".format(amount, precision, suffix)


def system_label(scene) -> str:
    key = current_unit(scene)
    if key in {"ft", "in"}:
        return "Imperial"
    return "Metric"


# Short labels for O-Draft-style status-bar chips.
STATUS_CHIPS = (
    ("m", "m"),
    ("mm", "mm"),
    ("cm", "cm"),
    ("ft", "'"),
    ("in", '"'),
)


def draw_status_chips(layout, scene):
    """Row of depressible unit chips for the bottom command bar."""
    current = current_unit(scene)
    row = layout.row(align=True)
    row.scale_y = 0.95
    for key, short in STATUS_CHIPS:
        op = row.operator(
            "oform.set_units",
            text=short,
            depress=key == current,
        )
        op.unit = key
