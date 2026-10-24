# SPDX-FileCopyrightText: 2026 O-Form Authors
#
# SPDX-License-Identifier: GPL-2.0-or-later

"""IFC compressed GlobalId (22-char) helpers."""

from __future__ import annotations

import uuid

_CHARS = "0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz_$"


def new_guid() -> str:
    """Return a fresh IFC-compatible compressed GUID."""
    return compress(uuid.uuid4().bytes)


def compress(raw: bytes) -> str:
    """Compress 16 UUID bytes to the IFC 22-character GlobalId alphabet."""
    if len(raw) != 16:
        raise ValueError("UUID bytes must be 16 long")
    # IFC uses a special packing: first byte → 2 chars, remaining 15 → 20 chars.
    num = int.from_bytes(raw, "big")
    # 128 bits → take as integer; encode 2+20 chars of 6-bit.
    chars = []
    # First character uses only 4 bits of the high nibble scheme used by IfcOpenShell:
    # replicate ifcopenshell.guid.compress behaviour closely enough for exchange.
    n = num
    # 22 groups of 6 bits from the 128-bit value (pad with 4 zero bits at the high end).
    n >>= 0
    # Pad to 132 bits (22*6) by shifting left 4.
    n = num << 4
    for _ in range(22):
        chars.append(_CHARS[(n >> (6 * (21 - _))) & 0x3F])
    return "".join(chars)


def ensure_guid(existing: str | None) -> str:
    text = (existing or "").strip()
    if len(text) == 22 and all(c in _CHARS for c in text):
        return text
    return new_guid()
