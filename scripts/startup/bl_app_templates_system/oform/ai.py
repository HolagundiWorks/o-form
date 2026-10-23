# SPDX-FileCopyrightText: 2026 O-Form Authors
#
# SPDX-License-Identifier: GPL-2.0-or-later

"""O-Draft-style Ask assistant for O-Form.

Thin UI, allow-listed tools, confirmation for mutating actions. The default
matcher is keyword-based so the app works offline without a local LLM. When
``%APPDATA%\\O-Draft\\models`` or ``OFORM_ASK_CMD`` is present, requests can be
forwarded to an external ask command.
"""

from __future__ import annotations

import json
import os
import re
import subprocess
from dataclasses import dataclass

# Mirror O-Draft: AI channel uses accent blue; CAD stays on tool/status chrome.
CHANNEL_LABEL = "Ask:"


@dataclass
class ToolSpec:
    name: str
    summary: str
    mutating: bool
    keywords: tuple


# Allow-listed tools (name → operator / handler).
TOOLS = (
    ToolSpec("get_model_summary", "Report faces, edges, and context", False, ("summary", "what is", "status", "overview")),
    ToolSpec("zoom_extents", "Frame the model in the view", False, ("zoom extents", "frame", "fit view", "zoom all")),
    ToolSpec("make_group", "Make a group from the selection", True, ("make group", "group selection", "create group")),
    ToolSpec("make_component", "Make a component from the selection", True, ("make component", "component", "create component")),
    ToolSpec("explode", "Explode the selected group or component", True, ("explode", "ungroup")),
    ToolSpec("enter_group", "Edit the selected group or component", False, ("enter group", "edit group", "edit component", "open group")),
    ToolSpec("exit_group", "Close the current group or component", False, ("exit group", "close group", "leave group")),
    ToolSpec("tool_select", "Switch to Select", False, ("select tool", "selection tool")),
    ToolSpec("tool_line", "Switch to Line", False, ("line tool", "draw line")),
    ToolSpec("tool_rectangle", "Switch to Rectangle", False, ("rectangle tool", "draw rectangle")),
    ToolSpec("tool_push_pull", "Switch to Push/Pull", False, ("push pull", "push/pull", "extrude")),
    ToolSpec("tool_move", "Switch to Move", False, ("move tool",)),
    ToolSpec("theme_light", "Use the light theme", False, ("light theme", "light mode", "day mode")),
    ToolSpec("theme_dark", "Use the dark theme", False, ("dark theme", "dark mode", "night mode")),
)


def _history(scene):
    raw = scene.get("oform_ask_history", "[]")
    try:
        data = json.loads(raw) if isinstance(raw, str) else list(raw)
    except (TypeError, json.JSONDecodeError):
        data = []
    if not isinstance(data, list):
        data = []
    return data[-12:]


def _push_history(scene, role, text):
    data = _history(scene)
    data.append({"role": role, "text": text})
    scene["oform_ask_history"] = json.dumps(data[-12:])


def clear_pending(scene):
    scene["oform_ask_pending"] = ""
    scene["oform_ask_pending_label"] = ""
    scene["oform_ask_phase"] = "idle"


def pending(scene):
    name = scene.get("oform_ask_pending", "") or ""
    label = scene.get("oform_ask_pending_label", "") or ""
    return name, label


def phase(scene):
    return scene.get("oform_ask_phase", "idle") or "idle"


def match_request(text):
    """Return (tool_name, args_dict) or None."""
    cleaned = (text or "").strip().lower()
    if not cleaned:
        return None
    if cleaned.startswith("/"):
        cleaned = cleaned[1:].strip()
    for tool in TOOLS:
        for key in tool.keywords:
            if key in cleaned:
                return tool.name, {}
    # Soft fallbacks.
    if re.search(r"\b(help|tools|commands)\b", cleaned):
        return "get_model_summary", {}
    return None


def _tool_by_name(name):
    for tool in TOOLS:
        if tool.name == name:
            return tool
    return None


def _model_summary(context):
    import bmesh
    import groups

    obj = groups.context_object(context)
    faces = edges = verts = 0
    if obj is not None and obj.type == "MESH":
        if obj.mode == "EDIT":
            bm = bmesh.from_edit_mesh(obj.data)
            faces, edges, verts = len(bm.faces), len(bm.edges), len(bm.verts)
        else:
            faces = len(obj.data.polygons)
            edges = len(obj.data.edges)
            verts = len(obj.data.vertices)
    entity = groups.get_entity(context)
    lines = [
        "Context: " + (obj.name if obj else "none"),
        "Depth: {}".format(groups.context_depth(context)),
        "Mesh: {} faces, {} edges, {} verts".format(faces, edges, verts),
    ]
    if entity is not None:
        lines.append("Selected entity: {} ({})".format(entity.name, groups.kind_of(entity)))
    return "\n".join(lines)


def execute_tool(context, name, *, confirmed=False):
    """Run a registered tool. Mutating tools require confirmed=True."""
    import bpy

    tool = _tool_by_name(name)
    if tool is None:
        return False, "Unknown tool"
    if tool.mutating and not confirmed:
        return False, "Needs confirmation"

    scene = context.scene
    if name == "get_model_summary":
        text = _model_summary(context)
        _push_history(scene, "assistant", text)
        return True, text
    if name == "zoom_extents":
        bpy.ops.oform.view(mode="EXTENTS")
        return True, "Zoomed to extents"
    if name == "theme_light":
        bpy.ops.oform.toggle_theme(mode="LIGHT")
        return True, "Light theme"
    if name == "theme_dark":
        bpy.ops.oform.toggle_theme(mode="DARK")
        return True, "Dark theme"
    if name.startswith("tool_"):
        op = getattr(bpy.ops.oform, name, None)
        if op is None:
            return False, "Tool missing"
        try:
            op("INVOKE_DEFAULT")
        except RuntimeError as exc:
            return False, str(exc)
        return True, "Activated " + name.replace("tool_", "").replace("_", " ")
    op = getattr(bpy.ops.oform, name, None)
    if op is None:
        return False, "Operator missing"
    result = op()
    ok = "FINISHED" in result
    return ok, ("Done: " + tool.summary) if ok else "Cancelled"


def _external_ask(text):
    """Optional bridge to O-Draft / custom ask command."""
    cmd = os.environ.get("OFORM_ASK_CMD", "").strip()
    if not cmd:
        return None
    try:
        completed = subprocess.run(
            cmd,
            input=text,
            text=True,
            capture_output=True,
            timeout=60,
            shell=True,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired):
        return None
    out = (completed.stdout or "").strip()
    if not out:
        return None
    # Expect either a bare tool name or JSON {"name": "..."}
    try:
        payload = json.loads(out)
        if isinstance(payload, dict) and "name" in payload:
            return payload["name"], payload.get("arguments") or {}
    except json.JSONDecodeError:
        pass
    line = out.splitlines()[0].strip()
    if _tool_by_name(line):
        return line, {}
    return None


def propose(context, text):
    """Interpret Ask text. May set a pending confirmation."""
    scene = context.scene
    cleaned = (text or "").strip()
    if not cleaned:
        return "idle", "Type a request"
    _push_history(scene, "user", cleaned)

    matched = _external_ask(cleaned) or match_request(cleaned)
    if matched is None:
        msg = "No matching tool. Try: summary, zoom extents, make group, dark theme…"
        _push_history(scene, "assistant", msg)
        scene["oform_ask_phase"] = "idle"
        clear_pending(scene)
        return "idle", msg

    name, _args = matched
    tool = _tool_by_name(name)
    if tool is None:
        return "idle", "Unknown tool"

    if tool.mutating:
        scene["oform_ask_pending"] = name
        scene["oform_ask_pending_label"] = tool.summary
        scene["oform_ask_phase"] = "confirm"
        msg = "Allow: " + tool.summary + "?"
        _push_history(scene, "assistant", msg)
        return "confirm", msg

    ok, result = execute_tool(context, name, confirmed=True)
    scene["oform_ask_phase"] = "idle"
    clear_pending(scene)
    if ok and result and result != _model_summary(context):
        _push_history(scene, "assistant", result)
    return "idle", result if ok else (result or "Failed")


def allow(context):
    scene = context.scene
    name, label = pending(scene)
    if not name:
        return "idle", "Nothing to allow"
    ok, result = execute_tool(context, name, confirmed=True)
    clear_pending(scene)
    scene["oform_ask_phase"] = "idle"
    msg = result if ok else (result or "Failed")
    _push_history(scene, "assistant", msg)
    return "idle", msg


def decline(context):
    scene = context.scene
    clear_pending(scene)
    scene["oform_ask_phase"] = "idle"
    msg = "Declined"
    _push_history(scene, "assistant", msg)
    return "idle", msg
