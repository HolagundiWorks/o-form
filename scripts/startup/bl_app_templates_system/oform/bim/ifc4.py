# SPDX-FileCopyrightText: 2026 O-Form Authors
#
# SPDX-License-Identifier: GPL-2.0-or-later

"""Minimal IFC4 SPF writer/reader for O-Form BIM (no IfcOpenShell required).

Exports tagged mesh products as ``IfcTriangulatedFaceSet`` under a standard
spatial tree (Project → Site → Building → Storey). Import recreates meshes
and restores ``oform_ifc_*`` properties.

This is an O-Form native BIM engine — not BlenderBIM/Bonsai.
"""

from __future__ import annotations

import os
import re
from datetime import datetime, timezone

import bmesh
import bpy
from mathutils import Vector

from . import classify
from . import guid as guid_mod
from . import props
from . import spatial
from . import taxonomy


def _esc(text: str) -> str:
    return (text or "").replace("\\", "\\\\").replace("'", "''")


class _Spf:
    def __init__(self):
        self.lines = []
        self._n = 0

    def add(self, entity: str) -> int:
        self._n += 1
        self.lines.append("#{}={};".format(self._n, entity))
        return self._n

    def ref(self, n: int) -> str:
        return "#{}".format(n)


def _mesh_triangles(obj):
    """World-space verts + triangle index triples."""
    mesh = obj.data
    if obj.mode == "EDIT":
        bm = bmesh.from_edit_mesh(mesh)
        own = False
    else:
        bm = bmesh.new()
        bm.from_mesh(mesh)
        own = True
    try:
        bm.faces.ensure_lookup_table()
        bmesh.ops.triangulate(bm, faces=bm.faces[:])
        bm.transform(obj.matrix_world)
        verts = [(v.co.x, v.co.y, v.co.z) for v in bm.verts]
        index = {v.index: i for i, v in enumerate(bm.verts)}
        faces = []
        for face in bm.faces:
            ids = [index[v.index] + 1 for v in face.verts]  # 1-based for IFC
            if len(ids) == 3:
                faces.append(tuple(ids))
        return verts, faces
    finally:
        if own:
            bm.free()


def export_ifc(context, filepath: str) -> tuple[bool, str]:
    """Write an IFC4 CoordinationView-ish SPF for the current scene."""
    scene = context.scene
    tree = spatial.ensure_project(scene)
    storeys = tree["storeys"]
    if not storeys:
        return False, "No storeys defined"

    products = [
        obj
        for obj in scene.objects
        if obj.type == "MESH" and obj.name != "Model" and len(obj.data.polygons) > 0
    ]
    # Include Model only if it has geometry and is tagged (or always skip empty root).
    root = scene.objects.get("Model")
    if root is not None and root.type == "MESH" and len(root.data.polygons) > 0:
        if props.ifc_class_of(root) or classify.suggest_class(root) != taxonomy.DEFAULT_ELEMENT:
            if root not in products:
                products.insert(0, root)

    if not products:
        # Still allow empty spatial export for pipeline tests — tag nothing.
        pass

    spf = _Spf()
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S")
    app = "O-Form BIM Engine"

    # --- Owner history / units / context ---
    org = spf.add("IFCORGANIZATION($,'Human Centric Works',$,$,$)")
    person = spf.add("IFCPERSON($,$,'O-Form',$,$,$,$,$)")
    person_org = spf.add(
        "IFCPERSONANDORGANIZATION({},{},$)".format(spf.ref(person), spf.ref(org))
    )
    app_id = spf.add(
        "IFCAPPLICATION({},'1.0','{}','OFORM')".format(spf.ref(org), _esc(app))
    )
    owner = spf.add(
        "IFCOWNERHISTORY({},{},$,.ADDED.,$,$,{},0)".format(
            spf.ref(person_org), spf.ref(app_id), spf.ref(person_org)
        )
    )
    si_len = spf.add("IFCSIUNIT(*,.LENGTHUNIT.,$,.METRE.)")
    units = spf.add("IFCUNITASSIGNMENT(({}))".format(spf.ref(si_len)))

    axis_x = spf.add("IFCDIRECTION((1.,0.,0.))")
    axis_z = spf.add("IFCDIRECTION((0.,0.,1.))")
    origin = spf.add("IFCCARTESIANPOINT((0.,0.,0.))")
    world = spf.add(
        "IFCAXIS2PLACEMENT3D({},{},{})".format(
            spf.ref(origin), spf.ref(axis_z), spf.ref(axis_x)
        )
    )
    ctx = spf.add(
        "IFCGEOMETRICREPRESENTATIONCONTEXT($,'Model',3,1.E-05,{},$)".format(spf.ref(world))
    )
    body_ctx = spf.add(
        "IFCGEOMETRICREPRESENTATIONSUBCONTEXT('Body','Model',*,*,*,*,{},.MODEL_VIEW.,$)".format(
            spf.ref(ctx)
        )
    )

    project_guid = guid_mod.new_guid()
    project = spf.add(
        "IFCPROJECT('{}',{},'{}',$,$,$,$,({}),{})".format(
            project_guid,
            spf.ref(owner),
            _esc(tree["project"]),
            spf.ref(ctx),
            spf.ref(units),
        )
    )

    def local_placement(parent_placement, elevation=0.0):
        pt = spf.add("IFCCARTESIANPOINT((0.,0.,{:.6f}))".format(elevation))
        axis = spf.add(
            "IFCAXIS2PLACEMENT3D({},{},{})".format(spf.ref(pt), spf.ref(axis_z), spf.ref(axis_x))
        )
        if parent_placement is None:
            return spf.add("IFCLOCALPLACEMENT($,{})".format(spf.ref(axis)))
        return spf.add(
            "IFCLOCALPLACEMENT({},{})".format(spf.ref(parent_placement), spf.ref(axis))
        )

    site_place = local_placement(None)
    site = spf.add(
        "IFCSITE('{}',{},'{}',$,$,{},$,$,.ELEMENT.,$,$,$,$,$)".format(
            guid_mod.new_guid(),
            spf.ref(owner),
            _esc(tree["site"]),
            spf.ref(site_place),
        )
    )
    building_place = local_placement(site_place)
    building = spf.add(
        "IFCBUILDING('{}',{},'{}',$,$,{},$,$,.ELEMENT.,$,$,$)".format(
            guid_mod.new_guid(),
            spf.ref(owner),
            _esc(tree["building"]),
            spf.ref(building_place),
        )
    )

    storey_ids = {}
    for storey in storeys:
        place = local_placement(building_place, storey["elevation"])
        sid = spf.add(
            "IFCBUILDINGSTOREY('{}',{},'{}',$,$,{},$,$,.ELEMENT.,{:.6f})".format(
                storey["guid"],
                spf.ref(owner),
                _esc(storey["name"]),
                spf.ref(place),
                storey["elevation"],
            )
        )
        storey_ids[storey["name"]] = sid

    # Aggregations
    spf.add(
        "IFCRELAGGREGATES('{}',{},$,$,{},({}))".format(
            guid_mod.new_guid(), spf.ref(owner), spf.ref(project), spf.ref(site)
        )
    )
    spf.add(
        "IFCRELAGGREGATES('{}',{},$,$,{},({}))".format(
            guid_mod.new_guid(), spf.ref(owner), spf.ref(site), spf.ref(building)
        )
    )
    if storey_ids:
        spf.add(
            "IFCRELAGGREGATES('{}',{},$,$,{},({}))".format(
                guid_mod.new_guid(),
                spf.ref(owner),
                spf.ref(building),
                ",".join(spf.ref(s) for s in storey_ids.values()),
            )
        )

    # Contained products per storey
    contained = {name: [] for name in storey_ids}

    for obj in products:
        ifc_class = props.ifc_class_of(obj) or classify.suggest_class(obj)
        if taxonomy.is_spatial(ifc_class):
            ifc_class = taxonomy.DEFAULT_ELEMENT
        g = guid_mod.ensure_guid(props.guid_of(obj))
        props.set_guid(obj, g)
        if not props.ifc_class_of(obj):
            props.set_ifc_class(obj, ifc_class)

        verts, faces = _mesh_triangles(obj)
        if not verts or not faces:
            continue

        coord_list = ",".join(
            "({:.6f},{:.6f},{:.6f})".format(x, y, z) for x, y, z in verts
        )
        coords = spf.add("IFCCARTESIANPOINTLIST3D(({}))".format(coord_list))
        face_list = ",".join("({},{},{})".format(a, b, c) for a, b, c in faces)
        tfs = spf.add(
            "IFCTRIANGULATEDFACESET({},$,.T.,({}),$)".format(spf.ref(coords), face_list)
        )
        shape_rep = spf.add(
            "IFCSHAPEREPRESENTATION({},'Body','Tessellation',({}))".format(
                spf.ref(body_ctx), spf.ref(tfs)
            )
        )
        prod_def = spf.add("IFCPRODUCTDEFINITIONSHAPE($,$,({}))".format(spf.ref(shape_rep)))
        # Identity placement under storey (geometry already world-space).
        place = local_placement(None)
        name = props.element_name(obj)
        if ifc_class == "IfcWall":
            entity = "IFCWALL('{}',{},'{}',$,$,{},{},$,$)".format(
                g, spf.ref(owner), _esc(name), spf.ref(place), spf.ref(prod_def)
            )
        elif ifc_class == "IfcSlab":
            entity = "IFCSLAB('{}',{},'{}',$,$,{},{},$,.FLOOR.)".format(
                g, spf.ref(owner), _esc(name), spf.ref(place), spf.ref(prod_def)
            )
        elif ifc_class == "IfcColumn":
            entity = "IFCCOLUMN('{}',{},'{}',$,$,{},{},$,$)".format(
                g, spf.ref(owner), _esc(name), spf.ref(place), spf.ref(prod_def)
            )
        elif ifc_class == "IfcBeam":
            entity = "IFCBEAM('{}',{},'{}',$,$,{},{},$,$)".format(
                g, spf.ref(owner), _esc(name), spf.ref(place), spf.ref(prod_def)
            )
        elif ifc_class == "IfcDoor":
            entity = "IFCDOOR('{}',{},'{}',$,$,{},{},$,$,$)".format(
                g, spf.ref(owner), _esc(name), spf.ref(place), spf.ref(prod_def)
            )
        elif ifc_class == "IfcWindow":
            entity = "IFCWINDOW('{}',{},'{}',$,$,{},{},$,$,$)".format(
                g, spf.ref(owner), _esc(name), spf.ref(place), spf.ref(prod_def)
            )
        else:
            entity = "IFCBUILDINGELEMENTPROXY('{}',{},'{}',$,$,{},{},$,.NOTDEFINED.)".format(
                g, spf.ref(owner), _esc(name), spf.ref(place), spf.ref(prod_def)
            )

        pid = spf.add(entity)
        storey_name = props.storey_of(obj) or tree["active_storey"]
        if storey_name not in contained:
            storey_name = storeys[0]["name"]
            props.set_storey(obj, storey_name)
        contained[storey_name].append(pid)

    for storey_name, pids in contained.items():
        if not pids:
            continue
        sid = storey_ids[storey_name]
        spf.add(
            "IFCRELCONTAINEDINSPATIALSTRUCTURE('{}',{},$,$,({}),{})".format(
                guid_mod.new_guid(),
                spf.ref(owner),
                ",".join(spf.ref(p) for p in pids),
                spf.ref(sid),
            )
        )

    header = (
        "ISO-10303-21;\n"
        "HEADER;\n"
        "FILE_DESCRIPTION(('ViewDefinition [CoordinationView_V2.0]'),'2;1');\n"
        "FILE_NAME('{}','{}',('O-Form'),('Human Centric Works'),'{}','{}','');\n"
        "FILE_SCHEMA(('IFC4'));\n"
        "ENDSEC;\n"
        "DATA;\n"
    ).format(_esc(os.path.basename(filepath)), now, _esc(app), _esc(app))

    body = "\n".join(spf.lines) + "\nENDSEC;\nEND-ISO-10303-21;\n"
    os.makedirs(os.path.dirname(os.path.abspath(filepath)) or ".", exist_ok=True)
    with open(filepath, "w", encoding="utf-8", newline="\n") as handle:
        handle.write(header)
        handle.write(body)
    return True, "Exported {} products to {}".format(len(products), filepath)


_LINE_ENTITY_RE = re.compile(
    r"^\s*#(\d+)\s*=\s*(IFC[A-Z0-9]+)\s*\((.*)\)\s*;\s*$",
    re.IGNORECASE,
)
_GUID_RE = re.compile(r"^'([0-9A-Za-z_$]{22})'")
_POINT_RE = re.compile(r"\(([-\d.eE]+)\s*,\s*([-\d.eE]+)\s*,\s*([-\d.eE]+)\)")
_TRI_RE = re.compile(r"\((\d+)\s*,\s*(\d+)\s*,\s*(\d+)\)")


def _split_args(blob: str) -> list:
    """Split top-level IFC attribute list (handles nested parentheses / strings)."""
    args = []
    buf = []
    depth = 0
    in_str = False
    i = 0
    while i < len(blob):
        ch = blob[i]
        if in_str:
            buf.append(ch)
            if ch == "'" and i + 1 < len(blob) and blob[i + 1] == "'":
                buf.append("'")
                i += 2
                continue
            if ch == "'":
                in_str = False
            i += 1
            continue
        if ch == "'":
            in_str = True
            buf.append(ch)
        elif ch == "(":
            depth += 1
            buf.append(ch)
        elif ch == ")":
            depth -= 1
            buf.append(ch)
        elif ch == "," and depth == 0:
            args.append("".join(buf).strip())
            buf = []
        else:
            buf.append(ch)
        i += 1
    if buf:
        args.append("".join(buf).strip())
    return args


def _parse_entities(text: str) -> dict:
    """Parse DATA section entities (one SPF assignment per line from our writer)."""
    data_match = re.search(r"DATA;(.*)ENDSEC;", text, re.IGNORECASE | re.DOTALL)
    if not data_match:
        return {}
    entities = {}
    for line in data_match.group(1).splitlines():
        match = _LINE_ENTITY_RE.match(line.strip())
        if not match:
            continue
        num = int(match.group(1))
        kind = match.group(2).upper()
        entities[num] = (kind, _split_args(match.group(3)))
    return entities


def import_ifc(context, filepath: str) -> tuple[bool, str]:
    """Import tessellated IFC products into the scene (minimal SPF parser)."""
    if not os.path.isfile(filepath):
        return False, "File not found"
    with open(filepath, "r", encoding="utf-8", errors="replace") as handle:
        text = handle.read()
    entities = _parse_entities(text)
    if not entities:
        return False, "No DATA entities"

    point_lists = {}
    for num, (kind, args) in entities.items():
        if kind != "IFCCARTESIANPOINTLIST3D" or not args:
            continue
        pts = [(float(x), float(y), float(z)) for x, y, z in _POINT_RE.findall(args[0])]
        point_lists[num] = pts

    face_sets = {}
    for num, (kind, args) in entities.items():
        if kind != "IFCTRIANGULATEDFACESET" or len(args) < 4:
            continue
        ref = args[0].strip()
        if not ref.startswith("#"):
            continue
        coord_id = int(ref[1:])
        tris = [(int(a), int(b), int(c)) for a, b, c in _TRI_RE.findall(args[3])]
        face_sets[num] = (coord_id, tris)

    # Map shape rep → faceset, product def → shape, product → def
    shape_to_fs = {}
    for num, (kind, args) in entities.items():
        if kind != "IFCSHAPEREPRESENTATION":
            continue
        for arg in args:
            for ref in re.findall(r"#(\d+)", arg):
                rid = int(ref)
                if rid in face_sets:
                    shape_to_fs[num] = rid

    pdef_to_shape = {}
    for num, (kind, args) in entities.items():
        if kind != "IFCPRODUCTDEFINITIONSHAPE":
            continue
        for arg in args:
            for ref in re.findall(r"#(\d+)", arg):
                rid = int(ref)
                if rid in shape_to_fs:
                    pdef_to_shape[num] = rid

    product_kinds = {
        "IFCWALL",
        "IFCWALLSTANDARDCASE",
        "IFCSLAB",
        "IFCCOLUMN",
        "IFCBEAM",
        "IFCDOOR",
        "IFCWINDOW",
        "IFCROOF",
        "IFCBUILDINGELEMENTPROXY",
        "IFCSTAIR",
        "IFCRAILING",
        "IFCMEMBER",
        "IFCPLATE",
        "IFCCOVERING",
        "IFCFURNISHINGELEMENT",
        "IFCCURTAINWALL",
    }

    scene = context.scene
    spatial.ensure_project(scene)
    collection = scene.collection
    count = 0
    for num, (kind, args) in entities.items():
        if kind not in product_kinds or len(args) < 8:
            continue
        gmatch = _GUID_RE.match(args[0].strip())
        product_guid = gmatch.group(1) if gmatch else guid_mod.new_guid()
        name = "Element"
        # Name is typically attribute index 2
        if len(args) > 2 and args[2].startswith("'"):
            name = args[2].strip("'").replace("''", "'") or name
        pdef_id = None
        for arg in args:
            for ref in re.findall(r"#(\d+)", arg):
                rid = int(ref)
                if rid in pdef_to_shape:
                    pdef_id = rid
        if pdef_id is None:
            continue
        shape_id = pdef_to_shape.get(pdef_id)
        fs_id = shape_to_fs.get(shape_id) if shape_id else None
        if fs_id is None:
            continue
        coord_id, tris = face_sets[fs_id]
        verts = point_lists.get(coord_id)
        if not verts or not tris:
            continue

        mesh = bpy.data.meshes.new(name)
        mesh.from_pydata(
            [Vector(v) for v in verts],
            [],
            [(a - 1, b - 1, c - 1) for a, b, c in tris],
        )
        mesh.update()
        obj = bpy.data.objects.new(name, mesh)
        collection.objects.link(obj)
        ifc_class = kind[:1] + kind[1:].title().replace("Ifc", "Ifc")
        # Normalize IFCWALL → IfcWall
        ifc_class = "Ifc" + kind[3:].title().replace("_", "")
        # Fix known names
        mapping = {
            "IFCWALL": "IfcWall",
            "IFCWALLSTANDARDCASE": "IfcWallStandardCase",
            "IFCSLAB": "IfcSlab",
            "IFCCOLUMN": "IfcColumn",
            "IFCBEAM": "IfcBeam",
            "IFCDOOR": "IfcDoor",
            "IFCWINDOW": "IfcWindow",
            "IFCROOF": "IfcRoof",
            "IFCBUILDINGELEMENTPROXY": "IfcBuildingElementProxy",
        }
        ifc_class = mapping.get(kind, "IfcBuildingElementProxy")
        props.set_ifc_class(obj, ifc_class)
        props.set_guid(obj, product_guid)
        props.set_storey(obj, spatial.active_storey(scene))
        count += 1

    return True, "Imported {} products from {}".format(count, os.path.basename(filepath))
