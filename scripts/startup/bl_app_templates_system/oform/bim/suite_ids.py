# SPDX-FileCopyrightText: 2026 O-Form Authors
#
# SPDX-License-Identifier: GPL-2.0-or-later

"""Shared suite identity for ShilpiDB take-off (O-Draft / O-CoreOp / O-Form).

Ports ``SlotFor`` / ``MakeId`` from:
- O-DRAFT ``crates/engine/src/cmd/takeoffrec.rs``
- O-COREOP ``AQC.CadImport/ShilpiTakeoff.cs``

Test vectors (must match O-CoreOp):
  drawing_id ``0b7d9c34-1e6f-4f0b-8a13-9b2c7d5e41aa`` → slot 6389047
  drawing_id ``6f1c1b0e-7a52-4d0a-9c1e-2d8a3f4b5c60`` → slot 15751439
"""

from __future__ import annotations

import json
import uuid

# Take-off kinds (hcw-takeoff-shilpi) — O-CoreOp Kind* constants.
KIND_TO_HEADER = 1
KIND_WALL = 3
KIND_OPENING = 4
KIND_COLUMN = 5
KIND_LINTEL = 6
KIND_ROOM = 7
KIND_SLAB = 8
KIND_PDF_CHUNK = 9

# O-Form IFC semantic sidecar (coexists; ignored by O-CoreOp take-off UI).
KIND_IFC_HEADER = 20
KIND_IFC_ELEMENT = 21

TAKEOFF_FORMAT = "hcw-takeoff-shilpi"
TAKEOFF_VERSION = 1
IFC_FORMAT = "oform-ifc-shilpi"
IFC_VERSION = 1

SCENE_DRAWING_ID = "oform_drawing_id"
SCENE_PROJECT_OFFICE = "oform_project_office_id"
SCENE_PROJECT_REF = "oform_project_ref"  # JSON {v, company_uuid, project_id}
SCENE_SHILPI_SLOT = "oform_shilpi_slot"  # JSON {drawingId, slot}
SCENE_SHILPI_ADDR = "oform_shilpi_addr"
SCENE_SHILPI_GATEWAY = "oform_shilpi_gateway"


def fnv1a_32(text: str) -> int:
    h = 2166136261
    for byte in (text or "").encode("utf-8"):
        h ^= byte
        h = (h * 16777619) & 0xFFFFFFFF
    return h


def slot_for(drawing_id: str) -> int:
    """24-bit drawing slot — identical to O-CoreOp ``ShilpiTakeoff.SlotFor``."""
    h = fnv1a_32(drawing_id)
    slot = (h ^ (h >> 24)) & 0xFFFFFF
    return 1 if slot == 0 else slot


def next_slot(slot: int) -> int:
    return 1 if slot >= 0xFFFFFF else slot + 1


def make_id(kind: int, slot: int, n: int) -> int:
    return ((kind & 0xFF) << 56) | ((slot & 0xFFFFFF) << 32) | (n & 0xFFFFFFFF)


def unpack_id(record_id: int) -> tuple[int, int, int]:
    kind = (record_id >> 56) & 0xFF
    slot = (record_id >> 32) & 0xFFFFFF
    n = record_id & 0xFFFFFFFF
    return kind, slot, n


def header_id(slot: int) -> int:
    return make_id(KIND_TO_HEADER, slot, 0)


def ensure_drawing_id(scene) -> str:
    existing = str(scene.get(SCENE_DRAWING_ID, "") or "").strip()
    if existing:
        return existing
    value = str(uuid.uuid4())
    scene[SCENE_DRAWING_ID] = value
    return value


def project_office_id(scene) -> str:
    return str(scene.get(SCENE_PROJECT_OFFICE, "") or "").strip()


def set_project_office_id(scene, value: str) -> None:
    text = (value or "").strip()
    if text:
        scene[SCENE_PROJECT_OFFICE] = text
    elif SCENE_PROJECT_OFFICE in scene:
        del scene[SCENE_PROJECT_OFFICE]


def project_ref(scene) -> dict | None:
    raw = scene.get(SCENE_PROJECT_REF, "")
    if not raw:
        return None
    try:
        data = json.loads(raw) if isinstance(raw, str) else dict(raw)
    except (TypeError, json.JSONDecodeError, ValueError):
        return None
    if not isinstance(data, dict):
        return None
    return data


def set_project_ref(scene, ref: dict | None) -> None:
    if not ref:
        if SCENE_PROJECT_REF in scene:
            del scene[SCENE_PROJECT_REF]
        return
    scene[SCENE_PROJECT_REF] = json.dumps(ref)


def persisted_slot(scene) -> tuple[str, int] | None:
    raw = scene.get(SCENE_SHILPI_SLOT, "")
    if not raw:
        return None
    try:
        data = json.loads(raw) if isinstance(raw, str) else dict(raw)
        did = str(data.get("drawingId") or data.get("drawing_id") or "").strip()
        slot = int(data.get("slot", 0))
        if did and slot > 0:
            return did, slot
    except (TypeError, json.JSONDecodeError, ValueError):
        pass
    return None


def persist_slot(scene, drawing_id: str, slot: int) -> None:
    scene[SCENE_SHILPI_SLOT] = json.dumps({"drawingId": drawing_id, "slot": int(slot)})


def resolve_slot(scene, client, *, header_kind: int = KIND_TO_HEADER) -> tuple[str, int]:
    """Claim a take-off slot for this drawing (probe like O-Draft).

    ``client`` must provide ``get_record(id) -> Record|None`` with UTF-8 JSON payload.
    """
    drawing_id = ensure_drawing_id(scene)
    cached = persisted_slot(scene)
    if cached and cached[0] == drawing_id:
        return drawing_id, cached[1]

    slot = slot_for(drawing_id)
    for _ in range(256):
        rec = client.get_record(make_id(header_kind, slot, 0))
        if rec is None:
            persist_slot(scene, drawing_id, slot)
            return drawing_id, slot
        try:
            doc = json.loads(rec.payload.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError, AttributeError):
            persist_slot(scene, drawing_id, slot)
            return drawing_id, slot
        source = doc.get("source") or {}
        existing = str(source.get("drawing_id") or "").strip()
        if not existing or existing == drawing_id:
            persist_slot(scene, drawing_id, slot)
            return drawing_id, slot
        slot = next_slot(slot)

    persist_slot(scene, drawing_id, slot_for(drawing_id))
    return drawing_id, slot_for(drawing_id)


def assert_slot_vectors() -> None:
    """Raise if suite slot algorithm drifts from O-CoreOp."""
    cases = (
        ("0b7d9c34-1e6f-4f0b-8a13-9b2c7d5e41aa", 6389047),
        ("6f1c1b0e-7a52-4d0a-9c1e-2d8a3f4b5c60", 15751439),
    )
    for drawing_id, expected in cases:
        got = slot_for(drawing_id)
        if got != expected:
            raise AssertionError(
                "slot_for({!r}) = {} != {} (O-CoreOp vector)".format(
                    drawing_id, got, expected
                )
            )
