# SPDX-FileCopyrightText: 2026 O-Form Authors
#
# SPDX-License-Identifier: GPL-2.0-or-later

"""Open / bind an OSAS project folder created by O-Studio.

Manifest ``osas.project.json`` links O-Draft, O-Form and ShilpiDB:
same ``drawing_id``, ``project_ref``, and project-scoped ``shilpi/project.vdb``.
"""

from __future__ import annotations

import json
import os
from typing import Any

from . import suite_ids

MANIFEST = "osas.project.json"
FORMAT = "osas-project"
SCENE_PROJECT_ROOT = "oform_project_root"
SCENE_LIVE_SYNC = "oform_live_sync"


def manifest_path(root: str) -> str:
    return os.path.join(root, MANIFEST)


def load_manifest(root: str) -> dict[str, Any]:
    path = manifest_path(root)
    with open(path, "r", encoding="utf-8") as handle:
        doc = json.load(handle)
    if not isinstance(doc, dict):
        raise ValueError("osas.project.json is not an object")
    if doc.get("format") != FORMAT:
        raise ValueError("not an OSAS project folder (format={!r})".format(doc.get("format")))
    if int(doc.get("v") or 0) != 1:
        raise ValueError("unsupported osas.project.json version {}".format(doc.get("v")))
    return doc


def resolve_file(root: str, doc: dict, key: str, default_rel: str) -> str:
    files = doc.get("files") or {}
    rel = str(files.get(key) or default_rel).replace("/", os.sep)
    return os.path.normpath(os.path.join(root, rel))


def shilpi_data_path(root: str, doc: dict | None = None) -> str:
    doc = doc or load_manifest(root)
    sync = doc.get("sync") or {}
    rel = str(sync.get("data_rel") or "shilpi/project.vdb").replace("/", os.sep)
    return os.path.normpath(os.path.join(root, rel))


def sync_addrs(doc: dict) -> tuple[str, str, int]:
    sync = doc.get("sync") or {}
    addr = str(sync.get("shilpid") or "127.0.0.1:7420").strip() or "127.0.0.1:7420"
    gateway = str(sync.get("gateway") or "127.0.0.1:7421").strip() or "127.0.0.1:7421"
    try:
        poll_ms = int(sync.get("poll_ms") or 1500)
    except (TypeError, ValueError):
        poll_ms = 1500
    return addr, gateway, max(500, poll_ms)


def bind_scene(scene, root: str, doc: dict | None = None) -> dict[str, Any]:
    """Apply project identity to the Blender scene and remember the folder."""
    root = os.path.abspath(root)
    doc = doc or load_manifest(root)
    scene[SCENE_PROJECT_ROOT] = root

    drawing_id = str(doc.get("drawing_id") or "").strip()
    if drawing_id:
        scene[suite_ids.SCENE_DRAWING_ID] = drawing_id

    office = str(doc.get("project_office_id") or "").strip()
    if not office:
        pref = doc.get("project_ref") or {}
        if isinstance(pref, dict) and pref.get("company_uuid") and pref.get("project_id") is not None:
            office = "{}:{}".format(pref["company_uuid"], pref["project_id"])
    if office:
        suite_ids.set_project_office_id(scene, office)

    pref = doc.get("project_ref")
    if isinstance(pref, dict):
        suite_ids.set_project_ref(scene, pref)

    addr, gateway, _poll = sync_addrs(doc)
    scene[suite_ids.SCENE_SHILPI_ADDR] = addr
    scene[suite_ids.SCENE_SHILPI_GATEWAY] = gateway

    # Clear cached slot so resolve_slot re-probes with this drawing_id.
    if suite_ids.SCENE_SHILPI_SLOT in scene:
        del scene[suite_ids.SCENE_SHILPI_SLOT]

    return {
        "root": root,
        "drawing_id": drawing_id,
        "project_office_id": office,
        "form": resolve_file(root, doc, "form", "form/model.blend"),
        "draft": resolve_file(root, doc, "draft", "draft/model.dxf"),
        "shilpi": shilpi_data_path(root, doc),
        "addr": addr,
        "gateway": gateway,
    }


def project_root_of(scene) -> str:
    return str(scene.get(SCENE_PROJECT_ROOT, "") or "").strip()


def live_sync_enabled(scene) -> bool:
    return bool(scene.get(SCENE_LIVE_SYNC, True))


def set_live_sync(scene, enabled: bool) -> None:
    scene[SCENE_LIVE_SYNC] = bool(enabled)


def open_project(context, root: str) -> tuple[bool, str, dict | None]:
    """Bind folder, connect project ShilpiDB, optionally load form/model.blend."""
    import bpy

    from . import shilpi_client

    try:
        doc = load_manifest(root)
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        return False, str(exc), None

    info = bind_scene(context.scene, root, doc)
    data = info["shilpi"]
    os.makedirs(os.path.dirname(data) or ".", exist_ok=True)

    ok, message = shilpi_client.ensure_server(
        info["addr"],
        info["gateway"],
        data_path=data,
    )
    if not ok:
        return False, message, info

    form_path = info["form"]
    # Load model if it looks like a real .blend (non-empty stub from O-Studio).
    if os.path.isfile(form_path) and os.path.getsize(form_path) > 64:
        try:
            bpy.ops.wm.open_mainfile(filepath=form_path)
            # Re-bind after load (scene replaced).
            info = bind_scene(bpy.context.scene, root, doc)
            set_live_sync(bpy.context.scene, True)
        except RuntimeError as exc:
            return False, "Opened project but could not load model: " + str(exc), info
    else:
        set_live_sync(context.scene, True)
        # Remember intended save path for first File → Save.
        context.scene["oform_save_path"] = form_path

    return True, "Project linked · drawing {} · {}".format(
        (info.get("drawing_id") or "")[:8],
        info["root"],
    ), info


def save_form_into_project(context) -> tuple[bool, str]:
    """Save the current .blend into the project's form/model.blend path."""
    import bpy

    root = project_root_of(context.scene)
    if not root:
        return False, "No project folder bound"
    try:
        doc = load_manifest(root)
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        return False, str(exc)
    path = resolve_file(root, doc, "form", "form/model.blend")
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    try:
        bpy.ops.wm.save_as_mainfile(filepath=path, copy=False)
    except RuntimeError as exc:
        return False, str(exc)
    return True, "Saved " + path
