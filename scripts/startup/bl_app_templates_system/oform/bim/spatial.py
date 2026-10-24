# SPDX-FileCopyrightText: 2026 O-Form Authors
#
# SPDX-License-Identifier: GPL-2.0-or-later

"""Project → Site → Building → Storey spatial structure."""

from __future__ import annotations

import json

from . import guid as guid_mod
from . import props


def project_snapshot(scene) -> dict:
    """Read-only project view for panel draw (no ID writes)."""
    storeys = list_storeys(scene)
    return {
        "project": str(scene.get(props.SCENE_PROJECT, "") or "O-Form Project"),
        "site": str(scene.get(props.SCENE_SITE, "") or "Site"),
        "building": str(scene.get(props.SCENE_BUILDING, "") or "Building"),
        "storeys": storeys,
        "active_storey": str(
            scene.get(props.SCENE_ACTIVE_STOREY, "")
            or (storeys[0]["name"] if storeys else "Level 0")
        ),
        "initialized": bool(scene.get(props.SCENE_PROJECT)),
    }


def ensure_project(scene) -> dict:
    """Ensure scene has a default BIM project tree. Call from operators only."""
    if not scene.get(props.SCENE_PROJECT):
        scene[props.SCENE_PROJECT] = "O-Form Project"
    if not scene.get(props.SCENE_SITE):
        scene[props.SCENE_SITE] = "Site"
    if not scene.get(props.SCENE_BUILDING):
        scene[props.SCENE_BUILDING] = "Building"
    storeys = list_storeys(scene)
    if not storeys:
        storeys = [
            {"name": "Level 0", "elevation": 0.0, "guid": guid_mod.new_guid()},
            {"name": "Level 1", "elevation": 3.0, "guid": guid_mod.new_guid()},
        ]
        _write_storeys(scene, storeys)
    if not scene.get(props.SCENE_ACTIVE_STOREY):
        scene[props.SCENE_ACTIVE_STOREY] = storeys[0]["name"]
    return project_snapshot(scene)


def list_storeys(scene) -> list:
    raw = scene.get(props.SCENE_STOREYS, "[]")
    try:
        data = json.loads(raw) if isinstance(raw, str) else list(raw)
    except (TypeError, json.JSONDecodeError, ValueError):
        data = []
    out = []
    for item in data:
        if not isinstance(item, dict):
            continue
        name = str(item.get("name", "")).strip()
        if not name:
            continue
        out.append(
            {
                "name": name,
                "elevation": float(item.get("elevation", 0.0)),
                "guid": guid_mod.ensure_guid(item.get("guid")),
            }
        )
    return out


def _write_storeys(scene, storeys) -> None:
    scene[props.SCENE_STOREYS] = json.dumps(storeys)


def add_storey(scene, name: str, elevation: float = 0.0) -> dict:
    ensure_project(scene)
    storeys = list_storeys(scene)
    name = (name or "Level").strip() or "Level"
    base = name
    index = 1
    existing = {s["name"] for s in storeys}
    while name in existing:
        index += 1
        name = "{} {}".format(base, index)
    entry = {"name": name, "elevation": float(elevation), "guid": guid_mod.new_guid()}
    storeys.append(entry)
    _write_storeys(scene, storeys)
    scene[props.SCENE_ACTIVE_STOREY] = name
    return entry


def set_active_storey(scene, name: str) -> bool:
    storeys = list_storeys(scene)
    names = {s["name"] for s in storeys}
    if name not in names:
        return False
    scene[props.SCENE_ACTIVE_STOREY] = name
    return True


def active_storey(scene) -> str:
    return project_snapshot(scene)["active_storey"]
