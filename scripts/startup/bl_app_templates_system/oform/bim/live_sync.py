# SPDX-FileCopyrightText: 2026 O-Form Authors
#
# SPDX-License-Identifier: GPL-2.0-or-later

"""Live sync between O-Form and the project ShilpiDB (shared with O-Draft / O-CoreOp).

Polls the take-off header ``source.exported`` timestamp. When another app writes
a newer header, O-Form pulls IFC sidecar semantics. Local mesh edits debounce
into ``takeoff.push_coherent``.
"""

from __future__ import annotations

import json
import time

import bpy

from . import project_folder
from . import suite_ids
from . import takeoff
from .shilpi_client import ShilpiHttp

_timer_running = False
_last_remote_exported = ""
_last_local_push = 0.0
_dirty = False
_last_stats_count = -1


def mark_dirty() -> None:
    global _dirty
    _dirty = True


def _poll_ms(scene) -> float:
    root = project_folder.project_root_of(scene)
    if not root:
        return 1.5
    try:
        doc = project_folder.load_manifest(root)
        _a, _g, ms = project_folder.sync_addrs(doc)
        return ms / 1000.0
    except (OSError, ValueError, json.JSONDecodeError):
        return 1.5


def _tick():
    global _last_remote_exported, _last_local_push, _dirty, _last_stats_count

    if not bpy.context or not getattr(bpy.context, "scene", None):
        return 2.0

    scene = bpy.context.scene
    if not project_folder.live_sync_enabled(scene):
        return 2.0
    root = project_folder.project_root_of(scene)
    if not root:
        return 2.0

    interval = _poll_ms(scene)
    gateway = str(scene.get(suite_ids.SCENE_SHILPI_GATEWAY, "") or "127.0.0.1:7421")

    try:
        client = ShilpiHttp(gateway)
        # Cheap change signal: record count
        try:
            stats = client.stats()
            count = int(stats.get("count") or stats.get("records") or -1)
        except Exception:
            count = -1

        drawing_id, slot = suite_ids.resolve_slot(scene, client, header_kind=suite_ids.KIND_TO_HEADER)
        header = client.get_record(suite_ids.header_id(slot))
        exported = ""
        remote_app = ""
        if header is not None:
            try:
                doc = json.loads(header.payload.decode("utf-8"))
                source = doc.get("source") or {}
                exported = str(source.get("exported") or "")
                remote_app = str(source.get("app") or "")
            except (UnicodeDecodeError, json.JSONDecodeError, AttributeError):
                pass

        # Pull when another app published a newer complete header.
        if exported and exported != _last_remote_exported and remote_app and remote_app != "O-Form":
            from . import shilpi_ifc

            ok, msg = shilpi_ifc.pull_ifc(bpy.context)
            scene.oform_status = ("sync pull: " + msg)[:80]
            _last_remote_exported = exported

        # Push local dirty state (debounce 2s).
        now = time.monotonic()
        if _dirty and (now - _last_local_push) > 2.0:
            ok, msg = takeoff.push_coherent(bpy.context)
            scene.oform_status = ("sync push: " + msg)[:80]
            _dirty = False
            _last_local_push = now
            if ok:
                # Refresh our notion of exported so we don't pull our own write.
                header = client.get_record(suite_ids.header_id(slot))
                if header is not None:
                    try:
                        doc = json.loads(header.payload.decode("utf-8"))
                        _last_remote_exported = str((doc.get("source") or {}).get("exported") or "")
                    except (UnicodeDecodeError, json.JSONDecodeError, AttributeError):
                        pass

        if count >= 0 and count != _last_stats_count:
            _last_stats_count = count

        _ = drawing_id  # identity kept on scene
    except Exception as exc:
        scene.oform_status = ("sync: " + str(exc))[:80]

    return interval


def start():
    global _timer_running
    if _timer_running:
        return
    if not bpy.app.timers.is_registered(_tick):
        bpy.app.timers.register(_tick, first_interval=1.5, persistent=True)
    _timer_running = True


def stop():
    global _timer_running
    if bpy.app.timers.is_registered(_tick):
        bpy.app.timers.unregister(_tick)
    _timer_running = False


def register():
    start()


def unregister():
    stop()
