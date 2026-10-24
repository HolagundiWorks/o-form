import sys
import traceback

sys.path.insert(0, r"D:\o-form\scripts\startup\bl_app_templates_system\oform")
print("THROUGH START", flush=True)

import bmesh
from mathutils import Vector
import geom


def report(bm, label):
    bm.normal_update()
    open_e = sum(1 for e in bm.edges if len(e.link_faces) != 2)
    wire = sum(1 for e in bm.edges if len(e.link_faces) == 0)
    print(
        "{}: f={} v={} open={} wire={}".format(
            label, len(bm.faces), len(bm.verts), open_e, wire
        ),
        flush=True,
    )


def main():
    bm = bmesh.new()
    # Wall slab: 4 x 0.2 x 3, front face at y=0
    face = geom.add_polygon(
        bm,
        [
            Vector((0, 0, 0)),
            Vector((4, 0, 0)),
            Vector((4, 0, 3)),
            Vector((0, 0, 3)),
        ],
    )
    # Extrude in +Y to thickness 0.2
    # Normal of face in XY... face on x-z plane, normal should be -Y or +Y
    face.normal_update()
    print("wall face normal", tuple(face.normal), flush=True)
    # Force extrude along +Y
    solid = geom.push_pull(bm, face, -0.2)  # if normal is -Y, -0.2 goes +Y
    if solid is None:
        # try other sign
        face2 = [f for f in bm.faces if abs(f.normal.y) > 0.9]
        print("retry faces", len(bm.faces), flush=True)
    report(bm, "wall solid")

    # Find front face (y≈0)
    front = None
    for f in bm.faces:
        c = f.calc_center_median()
        if abs(c.y) < 1e-4 and abs(f.normal.y) > 0.9:
            front = f
            break
    if front is None:
        for f in bm.faces:
            print(" face", f.index, "n", tuple(round(x, 3) for x in f.normal), "c", tuple(round(x, 3) for x in f.calc_center_median()), flush=True)
        print("FAIL no front", flush=True)
        return 1
    print("front n", tuple(front.normal), "c", tuple(front.calc_center_median()), flush=True)

    # Window 1
    win1 = geom.add_polygon(
        bm,
        [
            Vector((0.5, 0, 0.8)),
            Vector((1.5, 0, 0.8)),
            Vector((1.5, 0, 2.0)),
            Vector((0.5, 0, 2.0)),
        ],
    )
    report(bm, "after win1 draw")
    print("win1", win1, flush=True)
    if win1 is None:
        return 2
    # Push through into the wall. Front normal is -Y (outward), so negative
    # distance moves along -normal = +Y into the solid past thickness 0.2.
    try:
        result = geom.push_pull(bm, win1, -0.25)
        print("win1 result", result, flush=True)
    except Exception:
        traceback.print_exc()
        return 3
    report(bm, "after win1 push")

    # Window 2
    win2 = geom.add_polygon(
        bm,
        [
            Vector((2.2, 0, 0.8)),
            Vector((3.2, 0, 0.8)),
            Vector((3.2, 0, 2.0)),
            Vector((2.2, 0, 2.0)),
        ],
    )
    report(bm, "after win2 draw")
    print("win2", win2, flush=True)
    if win2 is None:
        return 4
    try:
        r2 = geom.push_pull(bm, win2, -0.25)
        report(bm, "after win2 push")
        print("r2", r2, flush=True)
    except Exception:
        traceback.print_exc()
        return 5

    open_e = sum(1 for e in bm.edges if len(e.link_faces) != 2)
    wire = sum(1 for e in bm.edges if len(e.link_faces) == 0)
    if wire:
        print("FAIL wire edges remain", wire, flush=True)
        return 6
    # Through holes: some boundary edges around openings are OK for a shell with holes
    # Actually a wall with 2 through holes is still manifold (each edge 2 faces)
    if open_e:
        print("FAIL open edges", open_e, flush=True)
        for e in bm.faces:
            pass
        for e in bm.edges:
            if len(e.link_faces) != 2:
                print(" open edge", [tuple(round(c, 3) for c in v.co) for v in e.verts], "nf", len(e.link_faces), flush=True)
        return 7
    print("OK", flush=True)
    bm.free()
    return 0


if __name__ == "__main__":
    try:
        code = main()
    except Exception:
        traceback.print_exc()
        code = 99
    print("EXIT", code, flush=True)
