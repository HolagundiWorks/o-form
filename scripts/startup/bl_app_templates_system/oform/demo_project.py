# SPDX-FileCopyrightText: 2026 O-Form Authors
#
# SPDX-License-Identifier: GPL-2.0-or-later

"""Build a complete OSAS demo project folder and exercise CAD + BIM + Shilpi sync.

Run::

    oform.exe --background --factory-startup --python .../demo_project.py

Creates ``%LOCALAPPDATA%/OSAS/demo-studio/`` with company-style layout,
scaffolds draft/form/shilpi, places a wall mesh, pushes suite take-off, verifies.
"""

from __future__ import annotations

import json
import os
import sys
import uuid

import bpy
import bmesh


def _fail(msg: str) -> None:
    print("OFORM_DEMO_FAIL:", msg)
    raise SystemExit(1)


def _ok(msg: str) -> None:
    print("OFORM_DEMO:", msg)


def _demo_root() -> str:
    base = os.environ.get("LOCALAPPDATA") or os.path.expanduser("~")
    return os.path.join(base, "OSAS", "demo-studio")


def _write(path: str, text: str) -> None:
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    with open(path, "w", encoding="utf-8", newline="\n") as handle:
        handle.write(text)


def scaffold_demo() -> dict:
    root = os.path.join(_demo_root(), "projects", "demo-villa-1")
    company_uuid = "aaaaaaaa-bbbb-4ccc-8ddd-eeeeeeeeeeee"
    drawing_id = "0b7d9c34-1e6f-4f0b-8a13-9b2c7d5e41aa"  # known SlotFor vector
    project_ref = {
        "v": 1,
        "company_uuid": company_uuid,
        "project_id": 1,
    }
    office = "{}:{}".format(company_uuid, 1)

    draft_dxf = (
        "0\nSECTION\n2\nHEADER\n0\nENDSEC\n"
        "0\nSECTION\n2\nENTITIES\n"
        "0\nLINE\n8\n0\n10\n0.0\n20\n0.0\n11\n4000.0\n21\n0.0\n"
        "0\nLINE\n8\n0\n10\n4000.0\n20\n0.0\n11\n4000.0\n21\n3000.0\n"
        "0\nLINE\n8\n0\n10\n4000.0\n20\n3000.0\n11\n0.0\n21\n3000.0\n"
        "0\nLINE\n8\n0\n10\n0.0\n20\n3000.0\n11\n0.0\n21\n0.0\n"
        "0\nENDSEC\n0\nEOF\n"
    )

    manifest = {
        "v": 1,
        "format": "osas-project",
        "name": "Demo Villa",
        "code": "DEMO",
        "project_ref": project_ref,
        "drawing_id": drawing_id,
        "project_office_id": office,
        "files": {
            "draft": "draft/model.dxf",
            "form": "form/model.blend",
            "shilpi": "shilpi/project.vdb",
            "odraft_project": "draft/project.json",
        },
        "sync": {
            "mode": "live",
            "shilpid": "127.0.0.1:7420",
            "gateway": "127.0.0.1:7421",
            "poll_ms": 1500,
            "data_rel": "shilpi/project.vdb",
        },
        "apps": {
            "ostudio": {"role": "owner"},
            "odraft": {"file": "draft/model.dxf"},
            "oform": {"file": "form/model.blend"},
            "shilpidb": {"file": "shilpi/project.vdb"},
        },
    }

    draft_project = {
        "schema_version": 1,
        "project": {
            "id": "prj-1",
            "code": "DEMO",
            "name": "Demo Villa",
            "type": "building",
            "description": "OSAS demo project",
            "units": {"length": "mm", "area": "m2"},
        },
        "floors": [
            {
                "id": "fl-ground",
                "name": "Ground",
                "code": "GF",
                "kind": "floor",
                "sequence": 0,
                "elevation": 0.0,
                "floor_to_floor": 3000.0,
            }
        ],
        "suite": {
            "osas_project": "../osas.project.json",
            "drawing_id": drawing_id,
            "project_ref": project_ref,
        },
    }

    studio = _demo_root()
    os.makedirs(os.path.join(studio, "projects"), exist_ok=True)
    _write(
        os.path.join(studio, "README.txt"),
        "OSAS demo studio — company placeholder for Demo Villa project.\n",
    )
    _write(os.path.join(root, "osas.project.json"), json.dumps(manifest, indent=2) + "\n")
    _write(os.path.join(root, "draft", "model.dxf"), draft_dxf)
    _write(os.path.join(root, "draft", "project.json"), json.dumps(draft_project, indent=2) + "\n")
    form_blend = os.path.join(root, "form", "model.blend")
    os.makedirs(os.path.dirname(form_blend), exist_ok=True)
    if not os.path.isfile(form_blend):
        open(form_blend, "wb").close()
    os.makedirs(os.path.join(root, "shilpi"), exist_ok=True)

    return {
        "studio": studio,
        "root": root,
        "drawing_id": drawing_id,
        "project_ref": project_ref,
        "office": office,
        "form": form_blend,
        "draft": os.path.join(root, "draft", "model.dxf"),
        "shilpi": os.path.join(root, "shilpi", "project.vdb"),
    }


def build_bim_wall():
    from bim import classify, props, spatial

    # Clear meshes
    for obj in list(bpy.context.scene.objects):
        if obj.type == "MESH":
            bpy.data.objects.remove(obj, do_unlink=True)

    spatial.ensure_project(bpy.context.scene)
    mesh = bpy.data.meshes.new("DemoWall")
    obj = bpy.data.objects.new("DemoWall", mesh)
    bpy.context.collection.objects.link(obj)
    bm = bmesh.new()
    bmesh.ops.create_cube(bm, size=1.0)
    for v in bm.verts:
        v.co.x *= 4.0
        v.co.y *= 0.2
        v.co.z *= 2.7
        v.co.z += 1.35
    bm.to_mesh(mesh)
    bm.free()
    mesh.update()
    props.set_ifc_class(obj, "IfcWall")
    props.set_guid(obj, "2O2Gr$t4X7Zf8NOew3FLOH")
    props.set_storey(obj, "Level 0")
    assert classify.suggest_class(obj) == "IfcWall"
    return obj


def main():
    here = os.path.dirname(os.path.abspath(__file__))
    if here not in sys.path:
        sys.path.insert(0, here)

    from bim import bridge_rows, live_sync, project_folder, suite_ids, takeoff
    from bim.shilpi_client import find_program

    suite_ids.assert_slot_vectors()
    info = scaffold_demo()
    _ok("scaffolded " + info["root"])

    # CAD artifact present
    if not os.path.isfile(info["draft"]) or os.path.getsize(info["draft"]) < 40:
        _fail("draft DXF missing")
    _ok("CAD draft/model.dxf ok")

    ok, message, bound = project_folder.open_project(bpy.context, info["root"])
    if not ok:
        _fail("open_project: " + message)
    _ok(message)

    scene = bpy.context.scene
    if suite_ids.ensure_drawing_id(scene) != info["drawing_id"]:
        _fail("drawing_id mismatch")
    if suite_ids.project_office_id(scene) != info["office"]:
        _fail("project_office_id mismatch")
    if suite_ids.slot_for(info["drawing_id"]) != 6389047:
        _fail("slot vector drift")

    build_bim_wall()
    products = bridge_rows.collect_products(scene)
    if len(products) < 1:
        _fail("no BIM products after wall")
    _ok("BIM wall tagged ({})".format(len(products)))

    # Save blend into project
    ok, message = project_folder.save_form_into_project(bpy.context)
    if not ok:
        _fail("save form: " + message)
    if os.path.getsize(info["form"]) < 64:
        _fail("form/model.blend still empty after save")
    _ok("form/model.blend saved")

    if find_program("shilpid"):
        ok, message = takeoff.push_coherent(bpy.context)
        if not ok:
            _fail("push: " + message)
        _ok(message)
        ok, message, summary = takeoff.pull_takeoff_summary(bpy.context)
        if not ok or not summary:
            _fail("status: " + message)
        if summary["header"].get("format") != "hcw-takeoff-shilpi":
            _fail("bad format")
        if summary["counts"]["walls"] < 1:
            _fail("expected wall rows")
        if summary["slot"] != 6389047:
            _fail("slot {} != 6389047".format(summary["slot"]))
        src = summary["header"].get("source") or {}
        if src.get("app") != "O-Form":
            _fail("source.app")
        if src.get("project_office_id") != info["office"]:
            _fail("source.project_office_id")
        _ok(
            "Shilpi take-off walls={} slot={} state={}".format(
                summary["counts"]["walls"],
                summary["slot"],
                summary["header"].get("state"),
            )
        )
        live_sync.mark_dirty()
        live_sync.start()
        _ok("live sync armed")
    else:
        _ok("shilpid not installed — folder + BIM save verified only")

    # Completeness checklist
    required = [
        os.path.join(info["root"], "osas.project.json"),
        info["draft"],
        os.path.join(info["root"], "draft", "project.json"),
        info["form"],
        os.path.join(info["root"], "shilpi"),
    ]
    for path in required:
        if not os.path.exists(path):
            _fail("missing " + path)

    print("OFORM_DEMO_OK")
    print("DEMO_ROOT=" + info["studio"])
    print("PROJECT_ROOT=" + info["root"])


if __name__ == "__main__":
    main()
