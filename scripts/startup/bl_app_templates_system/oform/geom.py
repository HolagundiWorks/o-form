# SPDX-FileCopyrightText: 2026 O-Form Authors
#
# SPDX-License-Identifier: GPL-2.0-or-later

"""Mesh edits for the O-Form tools.

Closed shapes drawn on a face split that face. The new inner face is selected
so Push/Pull can extrude it.
"""

import math

import bmesh
from mathutils import Matrix, Vector

TOL = 1e-5


def _basis(normal):
    n = normal.normalized()
    if abs(n.z) < 0.9:
        tmp = Vector((0.0, 0.0, 1.0))
    else:
        tmp = Vector((1.0, 0.0, 0.0))
    u = n.cross(tmp).normalized()
    v = n.cross(u).normalized()
    if u.cross(v).dot(n) < 0.0:
        v = -v
    return u, v


def _project(origin, u, v, co):
    d = co - origin
    return (d.dot(u), d.dot(v))


def _cross2(a, b, c):
    return (b[0] - a[0]) * (c[1] - a[1]) - (b[1] - a[1]) * (c[0] - a[0])


def _point_in_tri(p, a, b, c):
    c1 = _cross2(a, b, p)
    c2 = _cross2(b, c, p)
    c3 = _cross2(c, a, p)
    has_neg = (c1 < -1e-12) or (c2 < -1e-12) or (c3 < -1e-12)
    has_pos = (c1 > 1e-12) or (c2 > 1e-12) or (c3 > 1e-12)
    return not (has_neg and has_pos)


def _point_in_poly(pts, p, tol=TOL):
    # Boundary counts as inside.
    n = len(pts)
    if n < 3:
        return False
    for i in range(n):
        a = pts[i]
        b = pts[(i + 1) % n]
        if abs(_cross2(a, b, p)) <= 1e-8:
            dot = (p[0] - a[0]) * (b[0] - a[0]) + (p[1] - a[1]) * (b[1] - a[1])
            if -tol <= dot <= (b[0] - a[0]) ** 2 + (b[1] - a[1]) ** 2 + tol:
                return True
    inside = False
    j = n - 1
    for i in range(n):
        yi, yj = pts[i][1], pts[j][1]
        xi, xj = pts[i][0], pts[j][0]
        if (yi > p[1]) != (yj > p[1]):
            xint = (xj - xi) * (p[1] - yi) / ((yj - yi) or 1e-30) + xi
            if p[0] < xint:
                inside = not inside
        j = i
    return inside


def _signed_area(pts):
    area = 0.0
    for i in range(len(pts)):
        x1, y1 = pts[i]
        x2, y2 = pts[(i + 1) % len(pts)]
        area += x1 * y2 - x2 * y1
    return area * 0.5


def _ensure(bm):
    bm.verts.ensure_lookup_table()
    bm.edges.ensure_lookup_table()
    bm.faces.ensure_lookup_table()
    bm.normal_update()


def _new_vert(bm, co, tol=TOL):
    for vert in bm.verts:
        if (vert.co - co).length <= tol:
            return vert
    return bm.verts.new(co)


def rectangle_corners(corner_a, corner_b, normal):
    """Axis-aligned rectangle on the plane, opposite corners corner_a and corner_b."""
    a = Vector(corner_a)
    b = Vector(corner_b)
    n = Vector(normal)
    if n.length < 1e-8:
        n = Vector((0.0, 0.0, 1.0))
    n.normalize()
    if abs(n.z) > 0.999:
        u = Vector((1.0, 0.0, 0.0))
        v = Vector((0.0, 1.0, 0.0))
        if n.z < 0.0:
            v = -v
    else:
        u, v = _basis(n)
    du = (b - a).dot(u)
    dv = (b - a).dot(v)
    return [a, a + u * du, a + u * du + v * dv, a + v * dv]


def circle_points(center, radius, normal, segments):
    c = Vector(center)
    n = Vector(normal)
    if n.length < 1e-8:
        n = Vector((0.0, 0.0, 1.0))
    u, v = _basis(n.normalized())
    count = max(3, int(segments))
    pts = []
    for i in range(count):
        ang = 2.0 * math.pi * i / count
        pts.append(c + u * (math.cos(ang) * radius) + v * (math.sin(ang) * radius))
    return pts


def polygon_points(center, radius, normal, sides):
    """Regular polygon on the plane (SketchUp Polygon tool)."""
    return circle_points(center, radius, normal, max(3, int(sides)))


def freehand_points(points):
    """Deduplicate nearly-identical samples for the Freehand tool."""
    out = []
    for co in points:
        p = Vector(co)
        if not out or (p - out[-1]).length > 1e-4:
            out.append(p)
    return out


def arc_points(start, end, bulge, segments=12):
    """Polyline from start to end bowed through bulge. Endpoints are included."""
    p0 = Vector(start)
    p1 = Vector(end)
    p2 = Vector(bulge)
    count = max(2, int(segments))
    # Circle through three points. Fall back to a quadratic sample if they are colinear.
    a = p0 - p2
    b = p1 - p2
    n = a.cross(b)
    if n.length < 1e-8:
        pts = []
        for i in range(count + 1):
            t = i / count
            # Quadratic through the three samples.
            pts.append((1 - t) * (1 - t) * p0 + 2 * (1 - t) * t * p2 + t * t * p1)
        return pts
    n.normalize()
    ab = p1 - p0
    mid_ab = (p0 + p1) * 0.5
    mid_a2 = (p0 + p2) * 0.5
    # Plane normals of the perpendicular bisectors, intersected with the circle plane.
    n1 = ab.cross(n)
    n2 = (p2 - p0).cross(n)
    if n1.length < 1e-8 or n2.length < 1e-8:
        return [p0, p2, p1]
    n1.normalize()
    n2.normalize()
    # Line mid_ab + s * n1  and  mid_a2 + t * n2, both in the plane.
    # Solve (mid_ab - mid_a2) + s n1 - t n2 = 0 in the plane basis.
    delta = mid_a2 - mid_ab
    # s * n1 - t * n2 = delta
    # Use least squares in 3D via cross products.
    n1xn2 = n1.cross(n2)
    denom = n1xn2.length_squared
    if denom < 1e-12:
        return [p0, p2, p1]
    s = delta.cross(n2).dot(n1xn2) / denom
    center = mid_ab + n1 * s
    radius = (p0 - center).length
    if radius < 1e-8:
        return [p0, p1]
    u = (p0 - center).normalized()
    v = n.cross(u).normalized()

    def _ang(p):
        d = p - center
        return math.atan2(d.dot(v), d.dot(u))

    a0 = _ang(p0)
    a1 = _ang(p1)
    a2 = _ang(p2)

    def _wrap(delta_ang):
        while delta_ang <= -math.pi:
            delta_ang += 2.0 * math.pi
        while delta_ang > math.pi:
            delta_ang -= 2.0 * math.pi
        return delta_ang

    # Sweep from start to end that passes closest to the bulge angle.
    sweep_short = _wrap(a1 - a0)
    bulge_off = _wrap(a2 - a0)
    if sweep_short == 0.0:
        sweep = math.copysign(2.0 * math.pi, bulge_off or 1.0)
    elif bulge_off == 0.0 or (bulge_off > 0) == (sweep_short > 0):
        if abs(bulge_off) <= abs(sweep_short) + 1e-6:
            sweep = sweep_short
        else:
            sweep = sweep_short - math.copysign(2.0 * math.pi, sweep_short)
    else:
        sweep = sweep_short - math.copysign(2.0 * math.pi, sweep_short)
    pts = []
    for i in range(count + 1):
        ang = a0 + sweep * (i / count)
        pts.append(center + u * (math.cos(ang) * radius) + v * (math.sin(ang) * radius))
    return pts


def _face_frame(face):
    origin = face.verts[0].co
    u, v = _basis(face.normal)
    pts = [_project(origin, u, v, loop.vert.co) for loop in face.loops]
    return origin, u, v, pts


def _contains_points(face, points, tol=TOL):
    origin, u, v, poly = _face_frame(face)
    if _signed_area(poly) < 0.0:
        poly = list(reversed(poly))
    for co in points:
        if abs(face.normal.dot(co - face.verts[0].co)) > tol * 10.0:
            return False
        if not _point_in_poly(poly, _project(origin, u, v, co), tol):
            return False
    return True


def _strictly_inside(face, points, tol=1e-4):
    origin, u, v, poly = _face_frame(face)
    for co in points:
        flat = _project(origin, u, v, co)
        # Reject points that sit on the boundary; those need an edge split.
        for i in range(len(poly)):
            a = poly[i]
            b = poly[(i + 1) % len(poly)]
            # Distance from point to segment.
            abx, aby = b[0] - a[0], b[1] - a[1]
            length_sq = abx * abx + aby * aby
            if length_sq < 1e-16:
                continue
            t = ((flat[0] - a[0]) * abx + (flat[1] - a[1]) * aby) / length_sq
            t = min(max(t, 0.0), 1.0)
            dx = flat[0] - (a[0] + abx * t)
            dy = flat[1] - (a[1] + aby * t)
            if dx * dx + dy * dy <= tol * tol:
                return False
    return True


def find_host_face(bm, points, tol=TOL):
    """Smallest face that contains every point, or None."""
    _ensure(bm)
    best = None
    best_area = None
    for face in bm.faces:
        if not _contains_points(face, points, tol):
            continue
        area = face.calc_area()
        if best is None or area < best_area:
            best = face
            best_area = area
    return best


def _select_only_face(bm, face):
    for vert in bm.verts:
        vert.select = False
    for edge in bm.edges:
        edge.select = False
    for other in bm.faces:
        other.select = False
    if face is not None and face.is_valid:
        face.select = True
        for vert in face.verts:
            vert.select = True
        for edge in face.edges:
            edge.select = True
    bm.select_flush(True)
    # select_flush turns on every face whose vertices are all selected.
    # Push/Pull must see only the face the tool asked for.
    if face is not None and face.is_valid:
        for other in bm.faces:
            if other is not face:
                other.select = False


def _same2(a, b, eps=1e-9):
    return abs(a[0] - b[0]) <= eps and abs(a[1] - b[1]) <= eps


def _point_in_tri_strict(p, a, b, c, eps=1e-10):
    """True only for the open interior. Bridge vertices lie on corners and must not block an ear."""
    c1 = _cross2(a, b, p)
    c2 = _cross2(b, c, p)
    c3 = _cross2(c, a, p)
    if c1 > eps and c2 > eps and c3 > eps:
        return True
    if c1 < -eps and c2 < -eps and c3 < -eps:
        return True
    return False


def _ear_clip(points):
    """Triangulate a simple CCW polygon. Returns index triples, or None if it gets stuck."""
    n = len(points)
    if n < 3:
        return None
    if n == 3:
        if _cross2(points[0], points[1], points[2]) <= 1e-12:
            return None
        return [(0, 1, 2)]
    idx = list(range(n))
    tris = []
    guard = 0
    while len(idx) > 3 and guard < n * n:
        guard += 1
        found = False
        m = len(idx)
        for i in range(m):
            ia = idx[(i - 1) % m]
            ib = idx[i]
            ic = idx[(i + 1) % m]
            a, b, c = points[ia], points[ib], points[ic]
            if _same2(a, b) or _same2(b, c) or _same2(a, c):
                continue
            if _cross2(a, b, c) <= 1e-12:
                continue
            ear = True
            for j in idx:
                if j in (ia, ib, ic):
                    continue
                pj = points[j]
                if _same2(pj, a) or _same2(pj, b) or _same2(pj, c):
                    continue
                if _point_in_tri_strict(pj, a, b, c):
                    ear = False
                    break
            if ear:
                tris.append((ia, ib, ic))
                del idx[i]
                found = True
                break
        if not found:
            return None
    if len(idx) == 3:
        a, b, c = points[idx[0]], points[idx[1]], points[idx[2]]
        if _cross2(a, b, c) <= 1e-12 or _same2(a, b) or _same2(b, c) or _same2(a, c):
            return None
        tris.append((idx[0], idx[1], idx[2]))
    elif len(idx) > 3:
        return None
    return tris


def _tri_area_sum(points, tris):
    area = 0.0
    for ia, ib, ic in tris:
        area += abs(_cross2(points[ia], points[ib], points[ic])) * 0.5
    return area


def _new_face(bm, verts, normal):
    cleaned = []
    for vert in verts:
        if vert is None or not vert.is_valid:
            return None
        if not cleaned or cleaned[-1] != vert:
            cleaned.append(vert)
    if len(cleaned) >= 2 and cleaned[0] == cleaned[-1]:
        cleaned.pop()
    if len(set(cleaned)) < 3:
        return None
    try:
        face = bm.faces.new(cleaned)
    except ValueError:
        face = bm.faces.get(tuple(cleaned))
        if face is None:
            try:
                face = bm.faces.get(tuple(reversed(cleaned)))
            except Exception:
                face = None
    except ReferenceError:
        return None
    if face is None or not face.is_valid:
        return None
    try:
        face.normal_update()
        if Vector(normal).length > 1e-12 and face.normal.dot(normal) < 0.0:
            face.normal_flip()
    except ReferenceError:
        return None
    return face


def _project_to_plane(co, origin, normal):
    n = Vector(normal)
    if n.length_squared < 1e-16:
        return Vector(co)
    n.normalize()
    p = Vector(co)
    o = Vector(origin)
    return p - n * (p - o).dot(n)


def _soften_bridge_edges(bm, rim_faces, outer_verts, inner_verts):
    """Hide rim construction edges (SketchUp soft) — keep outer + inner loops hard."""
    keep = set()
    for loop in (outer_verts, inner_verts):
        count = len(loop)
        for i in range(count):
            edge = bm.edges.get((loop[i], loop[(i + 1) % count]))
            if edge is not None:
                keep.add(edge)
    for face in rim_faces:
        if face is None or not face.is_valid:
            continue
        for edge in face.edges:
            if edge in keep:
                continue
            edge.smooth = True
            edge.hide = True


def _annular_rim_faces(bm, outer_verts, outer_2d, inner_verts, inner_2d, normal):
    """Fill the frame between outer and inner loops with side strips (no corner fan)."""
    if len(outer_verts) < 3 or len(inner_verts) < 3:
        return []
    cx = sum(p[0] for p in inner_2d) / len(inner_2d)
    cy = sum(p[1] for p in inner_2d) / len(inner_2d)

    def ang(p):
        return math.atan2(p[1] - cy, p[0] - cx)

    inner_order = sorted(range(len(inner_verts)), key=lambda i: ang(inner_2d[i]))
    made = []
    n = len(outer_verts)
    for i in range(n):
        i1 = (i + 1) % n
        a0 = ang(outer_2d[i])
        a1 = ang(outer_2d[i1])
        span = (a1 - a0) % (2.0 * math.pi)
        if span < 1e-12:
            span = 2.0 * math.pi
        picked = []
        for j in inner_order:
            d = (ang(inner_2d[j]) - a0) % (2.0 * math.pi)
            if 1e-9 < d <= span + 1e-9:
                picked.append(j)
        if not picked:
            # Empty wedge: pin the nearest inner corner to this outer edge.
            mid = (
                0.5 * (outer_2d[i][0] + outer_2d[i1][0]),
                0.5 * (outer_2d[i][1] + outer_2d[i1][1]),
            )
            best_j = min(
                range(len(inner_verts)),
                key=lambda j: (inner_2d[j][0] - mid[0]) ** 2 + (inner_2d[j][1] - mid[1]) ** 2,
            )
            picked = [best_j]
        verts = [outer_verts[i], outer_verts[i1]]
        for j in reversed(picked):
            verts.append(inner_verts[j])
        # Drop consecutive duplicates.
        cleaned = []
        for vert in verts:
            if not cleaned or cleaned[-1] != vert:
                cleaned.append(vert)
        if len(cleaned) >= 2 and cleaned[0] == cleaned[-1]:
            cleaned.pop()
        if len(cleaned) < 3:
            continue
        item = _new_face(bm, cleaned, normal)
        if item is not None:
            made.append(item)
    return made


def _valid_verts(verts):
    return [vert for vert in verts if vert is not None and vert.is_valid]


def _split_face_with_hole(bm, face, points):
    """Replace face with an inner cap plus a clean rim (SketchUp face-on-face)."""
    normal = face.normal.copy()
    if normal.length < 1e-12:
        return None, []
    normal.normalize()
    origin, u, v, outer_2d = _face_frame(face)
    plane_origin = face.verts[0].co.copy()
    # Snap every point onto the host face plane so coplanar splits stay clean.
    pts = [_project_to_plane(Vector(p), plane_origin, normal) for p in points]
    outer_verts = [loop.vert for loop in face.loops]
    if _signed_area(outer_2d) < 0.0:
        outer_verts.reverse()
        outer_2d.reverse()
    # Snapshot coordinates — vert refs can die across delete/rebuild.
    outer_cos = [vert.co.copy() for vert in outer_verts]
    inner_cos = [Vector(co) for co in pts]
    if _signed_area([_project(origin, u, v, co) for co in inner_cos]) < 0.0:
        inner_cos.reverse()

    inner_verts = [_new_vert(bm, co) for co in inner_cos]
    inner_2d = [_project(origin, u, v, vert.co) for vert in inner_verts]
    target = abs(_signed_area(outer_2d)) - abs(_signed_area(inner_2d))

    bm.faces.remove(face)
    made = _annular_rim_faces(bm, outer_verts, outer_2d, inner_verts, inner_2d, normal)
    _ensure(bm)
    rim_area = sum(item.calc_area() for item in made if item.is_valid)
    ok_rim = bool(made) and abs(rim_area - target) <= max(1e-3, abs(target) * 0.08)
    if ok_rim:
        inner_face = _new_face(bm, inner_verts, normal)
        if inner_face is not None:
            _soften_bridge_edges(bm, made, outer_verts, inner_verts)
            _ensure(bm)
            _select_only_face(bm, inner_face)
            return inner_face, made

    # Rim failed — clear strips and rebuild from coordinate snapshots (no stale refs).
    for item in list(made):
        if item is not None and item.is_valid:
            bm.faces.remove(item)
    outer_fresh = [_new_vert(bm, co) for co in outer_cos]
    inner_fresh = [_new_vert(bm, co) for co in inner_cos]
    outer_set = set(outer_fresh)
    inner_set = set(inner_fresh)
    spokes = []
    for edge in list(bm.edges):
        if not edge.is_valid:
            continue
        ends = set(edge.verts)
        if ends & outer_set and ends & inner_set:
            spokes.append(edge)
    if spokes:
        bmesh.ops.delete(bm, geom=spokes, context="EDGES")
    # Drop loose edges that only bound the failed inner loop (0 faces).
    loose = [
        edge
        for edge in list(bm.edges)
        if edge.is_valid
        and len(edge.link_faces) == 0
        and set(edge.verts) <= inner_set
    ]
    if loose:
        bmesh.ops.delete(bm, geom=loose, context="EDGES")
    _ensure(bm)
    outer_fresh = _valid_verts([_new_vert(bm, co) for co in outer_cos])
    inner_fresh = _valid_verts([_new_vert(bm, co) for co in inner_cos])
    if len(outer_fresh) < 3 or len(inner_fresh) < 3:
        return None, []
    outer_2d = [_project(origin, u, v, vert.co) for vert in outer_fresh]
    inner_2d = [_project(origin, u, v, vert.co) for vert in inner_fresh]
    host = _new_face(bm, outer_fresh, normal)
    if host is None:
        return None, []
    return _split_face_with_hole_bridge(
        bm, host, outer_fresh, outer_2d, inner_fresh, inner_2d, normal, origin, u, v, target
    )


def _split_face_with_hole_bridge(
    bm, face, outer_verts, outer_2d, inner_verts, inner_2d, normal, origin, u, v, target
):
    """Legacy single-bridge triangulation; softens diagonals so they do not read as hard edges."""
    outer_verts = _valid_verts(outer_verts)
    inner_verts = _valid_verts(inner_verts)
    if len(outer_verts) < 3 or len(inner_verts) < 3:
        return None, []
    if len(outer_2d) != len(outer_verts):
        outer_2d = [_project(origin, u, v, vert.co) for vert in outer_verts]
    if len(inner_2d) != len(inner_verts):
        inner_2d = [_project(origin, u, v, vert.co) for vert in inner_verts]

    hole_verts = list(reversed(inner_verts))
    hole_2d = list(reversed(inner_2d))
    pairs = []
    for i, ov in enumerate(outer_verts):
        if not ov.is_valid:
            continue
        for j, hv in enumerate(hole_verts):
            if not hv.is_valid:
                continue
            pairs.append(((ov.co - hv.co).length_squared, i, j))
    pairs.sort(key=lambda item: item[0])

    chosen = None
    for _dist, i0, j0 in pairs:
        ring_v = outer_verts[i0:] + outer_verts[: i0 + 1] + hole_verts[j0:] + hole_verts[: j0 + 1]
        ring_p = outer_2d[i0:] + outer_2d[: i0 + 1] + hole_2d[j0:] + hole_2d[: j0 + 1]
        if any(not vert.is_valid for vert in ring_v):
            continue
        if _signed_area(ring_p) < 0.0:
            ring_v.reverse()
            ring_p.reverse()
        tris = _ear_clip(ring_p)
        if not tris:
            continue
        area = _tri_area_sum(ring_p, tris)
        if abs(area - target) <= max(1e-4, abs(target) * 1e-4):
            chosen = (ring_v, tris)
            break

    if chosen is None:
        if face is not None and face.is_valid:
            return _split_face_with_fill(bm, face, inner_verts, inner_2d, normal, origin, u, v)
        return None, []

    ring_v, tris = chosen
    if face is not None and face.is_valid:
        bm.faces.remove(face)
    made = []
    for ia, ib, ic in tris:
        verts = (ring_v[ia], ring_v[ib], ring_v[ic])
        if any(not vert.is_valid for vert in verts):
            continue
        tri = _new_face(bm, verts, normal)
        if tri is not None:
            made.append(tri)
    inner_face = _new_face(bm, inner_verts, normal)
    if inner_face is None:
        return None, made
    _soften_bridge_edges(bm, made, outer_verts, inner_verts)
    _ensure(bm)
    _select_only_face(bm, inner_face)
    return inner_face, made


def _split_face_with_fill(bm, face, inner_verts, inner_2d, normal, origin, u, v):
    """Scanfill fallback when the bridge triangulation does not cover the frame."""
    outer_edges = [loop.edge for loop in face.loops]
    bm.faces.remove(face)
    inner_edges = []
    count = len(inner_verts)
    for i in range(count):
        a = inner_verts[i]
        b = inner_verts[(i + 1) % count]
        if a == b:
            continue
        edge = bm.edges.get((a, b))
        if edge is None:
            edge = bm.edges.new((a, b))
        inner_edges.append(edge)
    try:
        filled = bmesh.ops.triangle_fill(
            bm,
            edges=list(outer_edges) + inner_edges,
            normal=normal,
            use_beauty=False,
            use_dissolve=False,
        )
    except (ValueError, RuntimeError):
        filled = {}
    hole = inner_2d if _signed_area(inner_2d) >= 0.0 else list(reversed(inner_2d))
    made = []
    for ele in filled.get("geom", []):
        if not isinstance(ele, bmesh.types.BMFace) or not ele.is_valid:
            continue
        center = _project(origin, u, v, ele.calc_center_median())
        if _point_in_poly(hole, center) and not _on_boundary(hole, center):
            bm.faces.remove(ele)
            continue
        ele.normal_update()
        if ele.normal.dot(normal) < 0.0:
            ele.normal_flip()
        made.append(ele)
    inner_face = _new_face(bm, inner_verts, normal)
    outer_verts = []
    for edge in outer_edges:
        if edge.is_valid:
            outer_verts.extend(list(edge.verts))
    # Prefer loop order from inner for soften keep-set.
    _soften_bridge_edges(bm, made, list(dict.fromkeys(outer_verts)), inner_verts)
    _ensure(bm)
    _select_only_face(bm, inner_face)
    return inner_face, made


def _on_boundary(pts, p, tol=1e-5):
    for i in range(len(pts)):
        a = pts[i]
        b = pts[(i + 1) % len(pts)]
        abx, aby = b[0] - a[0], b[1] - a[1]
        length_sq = abx * abx + aby * aby
        if length_sq < 1e-16:
            continue
        t = ((p[0] - a[0]) * abx + (p[1] - a[1]) * aby) / length_sq
        t = min(max(t, 0.0), 1.0)
        dx = p[0] - (a[0] + abx * t)
        dy = p[1] - (a[1] + aby * t)
        if dx * dx + dy * dy <= tol * tol:
            return True
    return False


def _merge_coplanar_hosts(bm, pts, tol=TOL):
    """Dissolve coplanar faces the sketch overlaps so a single host can be split."""
    if len(pts) < 3:
        return None
    centroid = sum(pts, Vector((0.0, 0.0, 0.0))) / float(len(pts))
    seed = find_host_face(bm, [centroid], tol)
    if seed is None:
        # Fall back: any face containing at least one sketch point.
        for point in pts:
            seed = find_host_face(bm, [point], tol)
            if seed is not None:
                break
    if seed is None:
        return None
    normal = seed.normal.copy()
    if normal.length < 1e-12:
        return None
    normal.normalize()
    origin = seed.verts[0].co.copy()
    u, v = _basis(normal)
    sketch_2d = [_project(origin, u, v, p) for p in pts]
    if _signed_area(sketch_2d) < 0.0:
        sketch_2d = list(reversed(sketch_2d))

    region = []
    for face in list(bm.faces):
        if not face.is_valid:
            continue
        fn = face.normal.copy()
        if fn.length < 1e-12:
            continue
        fn.normalize()
        if abs(fn.dot(normal)) < 0.999:
            continue
        if abs((face.verts[0].co - origin).dot(normal)) > tol * 10.0:
            continue
        if any(_contains_points(face, [p], tol) for p in pts):
            region.append(face)
            continue
        center = face.calc_center_median()
        if _point_in_poly(sketch_2d, _project(origin, u, v, center), tol):
            region.append(face)
    if seed not in region:
        region.append(seed)
    if len(region) == 1:
        return region[0]
    try:
        bmesh.ops.dissolve_faces(bm, faces=region, use_verts=False)
    except (ValueError, RuntimeError):
        return seed
    _ensure(bm)
    return find_host_face(bm, pts, tol) or find_host_face(bm, [centroid], tol)


def add_polygon(bm, points, tol=TOL):
    """Add a face, splitting a host face when the polygon lies inside it."""
    pts = [Vector(p) for p in points]
    if len(pts) < 3:
        return None
    # Drop a zero-area polygon.
    if (pts[1] - pts[0]).cross(pts[2] - pts[0]).length < 1e-10:
        return None
    host = find_host_face(bm, pts, tol)
    if host is None or not _strictly_inside(host, pts):
        # After a cut the surface is many coplanar faces — merge, then split.
        host = _merge_coplanar_hosts(bm, pts, tol)
    if host is not None and host.is_valid:
        # Auto-snap the sketch onto the host face plane before splitting / creating.
        origin = host.verts[0].co
        normal = host.normal.copy()
        pts = [_project_to_plane(co, origin, normal) for co in pts]
    if host is not None and host.is_valid and (
        _strictly_inside(host, pts) or _contains_points(host, pts, tol)
    ):
        try:
            face, _made = _split_face_with_hole(bm, host, pts)
        except (ReferenceError, ValueError, RuntimeError):
            face = None
        if face is not None:
            return face
    verts = [_new_vert(bm, co, tol) for co in pts]
    # Unique consecutive verts.
    cleaned = []
    for vert in verts:
        if not cleaned or cleaned[-1] != vert:
            cleaned.append(vert)
    if len(cleaned) >= 2 and cleaned[0] == cleaned[-1]:
        cleaned.pop()
    if len(cleaned) < 3:
        _ensure(bm)
        return None
    try:
        face = bm.faces.new(cleaned)
    except ValueError:
        face = bm.faces.get(tuple(cleaned))
    _ensure(bm)
    _select_only_face(bm, face)
    return face


def add_segment(bm, a, b, tol=TOL):
    """Add an edge. An edge that crosses a face from border to border splits it."""
    pa = Vector(a)
    pb = Vector(b)
    if (pb - pa).length <= tol:
        return None
    host = find_host_face(bm, [pa, pb], tol)
    if host is None:
        v1 = _new_vert(bm, pa, tol)
        v2 = _new_vert(bm, pb, tol)
        edge = bm.edges.get((v1, v2))
        if edge is None and v1 != v2:
            edge = bm.edges.new((v1, v2))
        _ensure(bm)
        return edge

    origin, u, v, poly = _face_frame(host)
    a2 = _project(origin, u, v, pa)
    b2 = _project(origin, u, v, pb)
    hits = []
    loops = list(host.loops)
    for loop in loops:
        edge = loop.edge
        c2 = _project(origin, u, v, edge.verts[0].co)
        d2 = _project(origin, u, v, edge.verts[1].co)
        hit = _segment_hit(a2, b2, c2, d2)
        if hit is None:
            continue
        _t, _s, point = hit
        co = origin + u * point[0] + v * point[1]
        hits.append((edge, co))
    # Unique edges.
    unique = []
    for edge, co in hits:
        if any(edge == other for other, _co in unique):
            continue
        unique.append((edge, co))
    if len(unique) >= 2:
        v1 = _split_edge_at(bm, unique[0][0], unique[0][1], tol)
        v2 = _split_edge_at(bm, unique[1][0], unique[1][1], tol)
        if v1 != v2 and host.is_valid:
            try:
                bmesh.utils.face_split(host, v1, v2)
            except ValueError:
                pass
        _ensure(bm)
        edge = bm.edges.get((v1, v2))
        return edge

    v1 = _new_vert(bm, pa, tol)
    v2 = _new_vert(bm, pb, tol)
    edge = bm.edges.get((v1, v2))
    if edge is None and v1 != v2:
        edge = bm.edges.new((v1, v2))
    _ensure(bm)
    return edge


def _segment_hit(a, b, c, d):
    """Intersection of segment ab with segment cd. Returns (t, s, point) or None."""
    rx, ry = b[0] - a[0], b[1] - a[1]
    sx, sy = d[0] - c[0], d[1] - c[1]
    denom = rx * sy - ry * sx
    if abs(denom) < 1e-12:
        return None
    qpx, qpy = c[0] - a[0], c[1] - a[1]
    t = (qpx * sy - qpy * sx) / denom
    s = (qpx * ry - qpy * rx) / denom
    if t < -1e-6 or t > 1.0 + 1e-6 or s < -1e-6 or s > 1.0 + 1e-6:
        return None
    return t, s, (a[0] + rx * t, a[1] + ry * t)


def _split_edge_at(bm, edge, co, tol):
    if (edge.verts[0].co - co).length <= tol:
        return edge.verts[0]
    if (edge.verts[1].co - co).length <= tol:
        return edge.verts[1]
    direction = edge.verts[1].co - edge.verts[0].co
    length_sq = direction.length_squared
    if length_sq < 1e-16:
        return edge.verts[0]
    fac = (co - edge.verts[0].co).dot(direction) / length_sq
    fac = min(max(fac, 0.0), 1.0)
    _new_edge, new_vert = bmesh.utils.edge_split(edge, edge.verts[0], fac)
    return new_vert


def selected_verts(bm):
    return [vert for vert in bm.verts if vert.select]


def selected_face(bm, face_index=-1):
    bm.faces.ensure_lookup_table()
    if 0 <= face_index < len(bm.faces):
        return bm.faces[face_index]
    for face in bm.faces:
        if face.select:
            return face
    return None


def _face_is_open(face):
    """True when every edge is a boundary (lone face / open shell rim)."""
    for edge in face.edges:
        if len(edge.link_faces) != 1:
            return False
    return True


def _side_normal(a, b, delta):
    edge = b.co - a.co
    n = edge.cross(delta)
    if n.length_squared < 1e-16:
        return delta.normalized()
    return n.normalized()


def _extrude_face_prism(bm, face, delta, keep_bottom=True):
    """Build a closed prism from a face. Keeps ``face`` as the bottom cap when asked."""
    if face is None or not face.is_valid or delta.length < 1e-9:
        return None
    normal = face.normal.copy()
    if normal.length < 1e-12:
        normal = delta.normalized()
    else:
        normal.normalize()
    bottom = [loop.vert for loop in face.loops]
    count = len(bottom)
    if count < 3:
        return None
    top = [bm.verts.new(vert.co + delta) for vert in bottom]
    for i in range(count):
        a = bottom[i]
        b = bottom[(i + 1) % count]
        c = top[(i + 1) % count]
        d = top[i]
        _new_face(bm, (a, b, c, d), _side_normal(a, b, delta))
    top_face = _new_face(bm, top, delta)
    if keep_bottom and face.is_valid:
        # Outward bottom faces opposite the extrusion direction.
        face.normal_update()
        if face.normal.dot(delta) > 0.0:
            face.normal_flip()
    elif face.is_valid:
        bm.faces.remove(face)
    _ensure(bm)
    if top_face is not None and top_face.is_valid:
        _select_only_face(bm, top_face)
    return top_face


def _ray_hit_face(bm, origin, direction, max_dist, skip):
    """Return (face, distance, point) for the nearest face hit, or None."""
    if direction.length < 1e-12:
        return None
    direction = direction.normalized()
    best = None
    best_dist = max_dist
    for face in bm.faces:
        if face in skip or not face.is_valid:
            continue
        denom = face.normal.dot(direction)
        if abs(denom) < 1e-10:
            continue
        plane_co = face.verts[0].co
        t = (plane_co - origin).dot(face.normal) / denom
        if t < 1e-5 or t > best_dist:
            continue
        hit = origin + direction * t
        if not _contains_points(face, [hit], tol=1e-4):
            continue
        best = (face, t, hit)
        best_dist = t
    return best


def _find_face_on_plane(bm, point, plane_normal, plane_origin, skip=None):
    """Pick the face under ``point`` that lies on the given plane."""
    skip = skip or set()
    n = Vector(plane_normal).normalized()
    o = Vector(plane_origin)
    best = None
    best_area = None
    for face in bm.faces:
        if face in skip or not face.is_valid:
            continue
        fn = face.normal.copy()
        if fn.length < 1e-12:
            continue
        fn.normalize()
        if abs(fn.dot(n)) < 0.995:
            continue
        if abs((face.verts[0].co - o).dot(n)) > 1e-3:
            continue
        if not _contains_points(face, [point], tol=1e-3):
            continue
        area = face.calc_area()
        if best is None or area < best_area:
            best = face
            best_area = area
    return best


def _face_on_plane(face, origin, normal, ang_tol=0.995, dist_tol=1e-3):
    if face is None or not face.is_valid:
        return False
    fn = face.normal.copy()
    if fn.length < 1e-12:
        return False
    fn.normalize()
    if abs(fn.dot(normal)) < ang_tol:
        return False
    return abs((face.verts[0].co - origin).dot(normal)) <= dist_tol


def _trace_edge_loops(edges):
    """Ordered closed vert loops from a set of boundary edges."""
    unused = {edge for edge in edges if edge is not None and edge.is_valid}
    adj = {}
    for edge in unused:
        a, b = edge.verts
        adj.setdefault(a, []).append(edge)
        adj.setdefault(b, []).append(edge)
    loops = []
    while unused:
        seed = unused.pop()
        v0, v1 = seed.verts[0], seed.verts[1]
        ordered = [v0]
        prev, curr = v0, v1
        guard = 0
        while guard < 10000:
            guard += 1
            ordered.append(curr)
            if curr == v0 and len(ordered) > 2:
                ordered.pop()
                break
            picked = None
            for edge in adj.get(curr, []):
                if edge not in unused:
                    continue
                other = edge.other_vert(curr)
                if other == prev:
                    continue
                picked = (edge, other)
                break
            if picked is None:
                for edge in adj.get(curr, []):
                    if edge in unused:
                        picked = (edge, edge.other_vert(curr))
                        break
            if picked is None:
                break
            edge, other = picked
            unused.discard(edge)
            prev, curr = curr, other
            if curr == v0:
                break
        if len(ordered) >= 3:
            loops.append(ordered)
    return loops


def _cut_hole_on_plane(bm, hole_verts, plane_normal, plane_origin, skip_faces=None):
    """Open a through-hole on a plane using the tunnel-end verts as the rim.

    ``hole_verts`` must already lie on the far plane and be shared with the
    tunnel side faces — that keeps the opening manifold (no stray spikes).
    """
    skip_faces = set(skip_faces or [])
    hole_verts = [vert for vert in hole_verts if vert is not None and vert.is_valid]
    count = len(hole_verts)
    if count < 3:
        return False
    n = Vector(plane_normal).normalized()
    o = Vector(plane_origin)
    # Snap tunnel ends onto the plane and ensure the rim edges exist.
    for vert in hole_verts:
        vert.co = _project_to_plane(vert.co, o, n)
    for i in range(count):
        a = hole_verts[i]
        b = hole_verts[(i + 1) % count]
        if a != b and bm.edges.get((a, b)) is None:
            try:
                bm.edges.new((a, b))
            except ValueError:
                pass

    u, v = _basis(n)
    hole_2d = [_project(o, u, v, vert.co) for vert in hole_verts]
    if _signed_area(hole_2d) < 0.0:
        hole_verts = list(reversed(hole_verts))
        hole_2d = list(reversed(hole_2d))
    hole_poly = list(hole_2d)
    cx = sum(p[0] for p in hole_2d) / float(count)
    cy = sum(p[1] for p in hole_2d) / float(count)
    hole_pts = [vert.co.copy() for vert in hole_verts]

    def _host_contains_hole(face):
        if not _contains_points(face, hole_pts, tol=1e-3):
            return False
        frame = [_project(o, u, v, loop.vert.co) for loop in face.loops]
        if _signed_area(frame) < 0.0:
            frame = list(reversed(frame))
        return _point_in_poly(frame, (cx, cy), tol=1e-4)

    # Prefer a single host face that fully contains the opening.
    host = None
    for face in list(bm.faces):
        if face in skip_faces or not face.is_valid:
            continue
        if not _face_on_plane(face, o, n):
            continue
        if _host_contains_hole(face):
            host = face
            break

    def _fill_frame_and_open(fill_edges, hole_polys, normal):
        """Triangle-fill an outer+holes edge net, then delete hole interiors."""
        try:
            filled = bmesh.ops.triangle_fill(
                bm,
                edges=list(fill_edges),
                normal=normal,
                use_beauty=True,
                use_dissolve=False,
            )
        except (ValueError, RuntimeError):
            filled = {}
        doomed = []
        made = 0
        for ele in filled.get("geom", []):
            if not isinstance(ele, bmesh.types.BMFace) or not ele.is_valid:
                continue
            center = _project(o, u, v, ele.calc_center_median())
            if any(
                _point_in_poly(poly, center) and not _on_boundary(poly, center)
                for poly in hole_polys
            ):
                doomed.append(ele)
                continue
            if ele.normal.dot(normal) < 0.0:
                ele.normal_flip()
            made += 1
        if doomed:
            bmesh.ops.delete(bm, geom=doomed, context="FACES")
        loose = [
            edge
            for edge in list(bm.edges)
            if edge.is_valid and len(edge.link_faces) == 0
        ]
        if loose:
            bmesh.ops.delete(bm, geom=loose, context="EDGES")
        _ensure(bm)
        return made > 0

    def _loop_edges(verts):
        edges = []
        for i in range(len(verts)):
            a = verts[i]
            b = verts[(i + 1) % len(verts)]
            if not a.is_valid or not b.is_valid or a == b:
                continue
            edge = bm.edges.get((a, b))
            if edge is None:
                try:
                    edge = bm.edges.new((a, b))
                except ValueError:
                    edge = None
            if edge is not None:
                edges.append(edge)
        return edges

    if host is not None:
        normal = host.normal.copy()
        if normal.length < 1e-12:
            normal = n.copy()
        else:
            normal.normalize()
        if normal.dot(n) < 0.0:
            normal = -normal
        outer_edges = [loop.edge for loop in host.loops]
        bm.faces.remove(host)
        _ensure(bm)
        return _fill_frame_and_open(
            list(outer_edges) + _loop_edges(hole_verts),
            [hole_poly],
            normal,
        )

    # Far side already has openings: rebuild the whole planar patch with holes.
    plane_faces = [
        face
        for face in list(bm.faces)
        if face not in skip_faces and face.is_valid and _face_on_plane(face, o, n)
    ]
    if not plane_faces:
        return False
    plane_set = set(plane_faces)
    border = []
    for face in plane_faces:
        for edge in face.edges:
            linked = sum(1 for item in edge.link_faces if item in plane_set)
            if linked == 1:
                border.append(edge)
    loops = _trace_edge_loops(border)
    if not loops:
        return False
    scored = []
    for loop in loops:
        pts2 = [_project(o, u, v, vert.co) for vert in loop]
        scored.append((abs(_signed_area(pts2)), loop, pts2))
    scored.sort(key=lambda item: item[0], reverse=True)
    outer_verts = scored[0][1]
    existing_holes = []
    for _area, loop, pts2 in scored[1:]:
        if set(loop) == set(hole_verts):
            continue
        poly = pts2 if _signed_area(pts2) >= 0.0 else list(reversed(pts2))
        existing_holes.append((loop, poly))

    bmesh.ops.delete(bm, geom=plane_faces, context="FACES")
    _ensure(bm)

    all_hole_loops = [item[0] for item in existing_holes] + [hole_verts]
    all_hole_polys = [item[1] for item in existing_holes] + [hole_poly]
    fill_edges = _loop_edges(outer_verts)
    for loop in all_hole_loops:
        fill_edges.extend(_loop_edges(loop))
    return _fill_frame_and_open(fill_edges, all_hole_polys, n)


def _make_cutter_prism(loop_cos, direction, depth, extend=1e-3):
    """Closed cutter prism along ``direction`` for through-cut boolean."""
    if len(loop_cos) < 3 or direction.length < 1e-12 or depth < 1e-9:
        return None
    direction = Vector(direction).normalized()
    cutter = bmesh.new()
    start = -direction * extend
    end = direction * (depth + extend)
    bottom = [cutter.verts.new(Vector(co) + start) for co in loop_cos]
    top = [cutter.verts.new(Vector(co) + end) for co in loop_cos]
    move = end - start
    count = len(bottom)
    for i in range(count):
        a = bottom[i]
        b = bottom[(i + 1) % count]
        c = top[(i + 1) % count]
        d = top[i]
        _new_face(cutter, (a, b, c, d), _side_normal(a, b, move))
    _new_face(cutter, list(reversed(bottom)), -move)
    _new_face(cutter, top, move)
    cutter.normal_update()
    return cutter


def _punch_through_boolean(bm, face, delta, thick):
    """Through-opening via solid boolean — reliable with multiple windows."""
    try:
        import solids
    except ImportError:
        return False
    loop = [loop.vert.co.copy() for loop in face.loops]
    direction = delta.normalized()
    cutter = _make_cutter_prism(loop, direction, max(thick, delta.length))
    if cutter is None:
        return False
    try:
        if not solids.is_solid(bm) or not solids.is_solid(cutter):
            return False
        ok, _message = solids.boolean_edit_meshes(bm, cutter, "DIFFERENCE")
        return bool(ok)
    except Exception:
        return False
    finally:
        cutter.free()


def _push_into_shell(bm, face, delta):
    """Chop a face on a shell: open the surface and push a pocket (or through-hole)."""
    if face is None or not face.is_valid or delta.length < 1e-9:
        return None
    try:
        center = face.calc_center_median()
        direction = delta.normalized()
        thickness_hit = _ray_hit_face(
            bm,
            center + direction * 1e-4,
            direction,
            max_dist=max(delta.length, 1e-3) + 10.0,
            skip={face},
        )
        bottom_cos = [loop.vert.co.copy() for loop in face.loops]
        count = len(bottom_cos)
        if count < 3:
            return None

        punch = False
        move = delta
        thick = None
        opp_normal = None
        opp_origin = None
        if thickness_hit is not None:
            opp, thick, _pt = thickness_hit
            # Through-cut when the push reaches (or passes) the far face.
            if thick > 1e-6 and delta.length + 1e-4 >= thick:
                move = direction * thick
                punch = True
                opp_normal = opp.normal.copy()
                opp_origin = opp.verts[0].co.copy()

        # Note: modifier boolean on the lite (float) solver is unsafe for punch
        # (can wipe the mesh). Use geometric tunnel + triangulated far-face cut.

        bm.faces.remove(face)
        bottom = [_new_vert(bm, co) for co in bottom_cos]
        top = [bm.verts.new(co + move) for co in bottom_cos]
        # Snap tunnel end exactly onto the far plane for a clean through-weld.
        if punch and opp_normal is not None:
            nn = opp_normal.normalized()
            for vert in top:
                vert.co = vert.co - nn * (vert.co - opp_origin).dot(nn)

        side_faces = []
        for i in range(count):
            a = bottom[i]
            b = bottom[(i + 1) % count]
            c = top[(i + 1) % count]
            d = top[i]
            side = _new_face(bm, (a, b, c, d), _side_normal(a, b, move))
            if side is not None:
                side_faces.append(side)
        _ensure(bm)

        if punch:
            # Tunnel ends are the hole rim — never invent a second set of verts.
            _cut_hole_on_plane(bm, top, opp_normal, opp_origin, skip_faces=side_faces)
            return None

        top_face = _new_face(bm, top, move)
        if top_face is not None and top_face.is_valid:
            _select_only_face(bm, top_face)
        return top_face
    except (ReferenceError, ValueError, RuntimeError):
        return None


def push_pull(bm, face, distance, copy=False):
    """Extrude a face into a solid, or push into a shell to chop a pocket/opening."""
    if face is None or not face.is_valid or abs(distance) < 1e-9:
        return None
    try:
        normal = face.normal.copy()
    except ReferenceError:
        return None
    if normal.length < 1e-12:
        return None
    normal.normalize()
    delta = normal * distance
    working = face
    if copy:
        # SketchUp Ctrl+Push/Pull leaves the original face and extrudes a copy.
        dup = bmesh.ops.duplicate(bm, geom=[face])
        faces = [ele for ele in dup.get("geom", []) if isinstance(ele, bmesh.types.BMFace)]
        if not faces:
            return None
        working = faces[0]
        # Duplicated face is disconnected — always build a closed prism.
        return _extrude_face_prism(bm, working, delta, keep_bottom=True)

    try:
        is_open = _face_is_open(working)
    except ReferenceError:
        return None
    if is_open:
        # Lone face / open rim: keep bottom so the result is a closed solid.
        return _extrude_face_prism(bm, working, delta, keep_bottom=True)

    # Face sits on a shell (e.g. rectangle drawn on a wall): chop into the volume.
    result = _push_into_shell(bm, working, delta)
    if result is not None:
        return result
    # Fallback if the shell chop hit bad topology (e.g. after a prior boolean).
    if working.is_valid:
        return _extrude_face_prism(bm, working, delta, keep_bottom=False)
    return None


def add_polyline(bm, points, close=False, tol=TOL):
    pts = [Vector(p) for p in points]
    if len(pts) < 2:
        return []
    created = []
    for i in range(len(pts) - 1):
        created.append(add_segment(bm, pts[i], pts[i + 1], tol=tol))
    if close and len(pts) > 2:
        created.append(add_segment(bm, pts[-1], pts[0], tol=tol))
    _ensure(bm)
    return created


def _guide_layer(bm):
    layer = bm.edges.layers.int.get("oform_guide")
    if layer is None:
        layer = bm.edges.layers.int.new("oform_guide")
    return layer


def add_guide(bm, a, b, extend=10.0, tol=TOL):
    """Construction line through a–b, extended both ways (SketchUp Tape Measure guide)."""
    p0 = Vector(a)
    p1 = Vector(b)
    direction = p1 - p0
    if direction.length < 1e-8:
        return None
    direction.normalize()
    start = p0 - direction * extend
    end = p1 + direction * extend
    edge = add_segment(bm, start, end, tol=tol)
    if edge is not None:
        layer = _guide_layer(bm)
        edge[layer] = 1
    return edge


def delete_guides(bm):
    """Remove all construction guides tagged by ``add_guide`` (SketchUp Delete Guides)."""
    layer = bm.edges.layers.int.get("oform_guide")
    if layer is None:
        return 0
    doomed = [edge for edge in list(bm.edges) if edge[layer] == 1]
    count = len(doomed)
    if doomed:
        bmesh.ops.delete(bm, geom=doomed, context="EDGES")
        _ensure(bm)
    return count


def reverse_faces(bm, faces=None):
    """Flip face normals (SketchUp Reverse Faces)."""
    targets = list(faces) if faces is not None else [f for f in bm.faces if f.select]
    if not targets:
        targets = list(bm.faces)
    for face in targets:
        if face is not None and face.is_valid:
            face.normal_flip()
    _ensure(bm)
    return len(targets)


def ordered_path_coords(edges):
    """Walk selected edges into an ordered polyline of coordinates."""
    valid = [edge for edge in edges if edge is not None and edge.is_valid]
    if not valid:
        return []
    adj = {}
    for edge in valid:
        a, b = edge.verts
        adj.setdefault(a, []).append((b, edge))
        adj.setdefault(b, []).append((a, edge))
    ends = [vert for vert, nbrs in adj.items() if len(nbrs) == 1]
    start = ends[0] if ends else valid[0].verts[0]
    path = [start]
    used = set()
    while True:
        current = path[-1]
        nxt = None
        for other, edge in adj.get(current, []):
            if edge.index in used:
                continue
            used.add(edge.index)
            nxt = other
            break
        if nxt is None:
            break
        path.append(nxt)
        if len(used) >= len(valid):
            break
    return [vert.co.copy() for vert in path]


def follow_me(bm, face, path_coords):
    """Extrude a face along an ordered path (SketchUp Follow Me, straight/bent paths)."""
    if face is None or not face.is_valid or len(path_coords) < 2:
        return None
    coords = [Vector(p) for p in path_coords]
    current = face
    # Place the profile at the path start.
    center = current.calc_center_median()
    bmesh.ops.translate(bm, verts=list(current.verts), vec=coords[0] - center)
    _ensure(bm)
    for i in range(len(coords) - 1):
        delta = coords[i + 1] - coords[i]
        length = delta.length
        if length < 1e-9:
            continue
        direction = delta.normalized()
        # Align a face edge direction toward the path when the path bends.
        if i > 0:
            prev = (coords[i] - coords[i - 1]).normalized()
            axis = prev.cross(direction)
            if axis.length > 1e-8:
                axis.normalize()
                angle = prev.angle(direction)
                rot = Matrix.Rotation(angle, 4, axis)
                pivot = coords[i]
                for vert in current.verts:
                    vert.co = pivot + rot @ (vert.co - pivot)
                _ensure(bm)
        ret = bmesh.ops.extrude_discrete_faces(bm, faces=[current])
        faces = ret.get("faces") or []
        if not faces:
            break
        current = faces[0]
        bmesh.ops.translate(bm, verts=list(current.verts), vec=direction * length)
        _ensure(bm)
    _select_only_face(bm, current)
    return current


def soften_edges(bm, edges, smooth=True):
    for edge in edges:
        if edge is None or not edge.is_valid:
            continue
        edge.smooth = smooth


def hide_edges(bm, edges, hide=True):
    for edge in edges:
        if edge is None or not edge.is_valid:
            continue
        edge.hide = hide
        if hide:
            for vert in edge.verts:
                if all(e.hide for e in vert.link_edges):
                    vert.hide = True
        else:
            for vert in edge.verts:
                vert.hide = False


def _line_intersect_2d(a0, a1, b0, b1):
    """Intersection of infinite lines a0–a1 and b0–b1, or None if parallel."""
    rax, ray = a1[0] - a0[0], a1[1] - a0[1]
    rbx, rby = b1[0] - b0[0], b1[1] - b0[1]
    denom = rax * rby - ray * rbx
    if abs(denom) < 1e-14:
        return None
    dx, dy = b0[0] - a0[0], b0[1] - a0[1]
    t = (dx * rby - dy * rbx) / denom
    return (a0[0] + rax * t, a0[1] + ray * t)


def _offset_poly_2d(pts, dist):
    """Even offset of a simple polygon. Positive ``dist`` insets a CCW ring."""
    count = len(pts)
    if count < 3:
        return None
    poly = list(pts)
    if _signed_area(poly) < 0.0:
        poly.reverse()
        # Caller keeps vert order; we only use geometry here — return None to signal flip needed? 
        # Work on a local CCW copy and map back by reversing result if needed.
        reversed_input = True
    else:
        reversed_input = False
    lines = []
    for i in range(count):
        a = poly[i]
        b = poly[(i + 1) % count]
        dx, dy = b[0] - a[0], b[1] - a[1]
        length = math.hypot(dx, dy)
        if length < 1e-12:
            nx, ny = 0.0, 0.0
        else:
            # CCW left normal = inward.
            nx, ny = -dy / length, dx / length
        ox, oy = nx * dist, ny * dist
        lines.append(((a[0] + ox, a[1] + oy), (b[0] + ox, b[1] + oy)))
    out = []
    for i in range(count):
        prev = lines[i - 1]
        cur = lines[i]
        hit = _line_intersect_2d(prev[0], prev[1], cur[0], cur[1])
        if hit is None:
            # Parallel edges: fall back to the offset of the shared vertex.
            hit = cur[0]
        out.append(hit)
    # Reject collapsed / inverted offsets.
    if abs(_signed_area(out)) < 1e-10:
        return None
    if dist > 0.0 and _signed_area(out) * _signed_area(poly) < 0.0:
        return None
    if reversed_input:
        out.reverse()
    return out


def offset_face(bm, face, distance):
    """Offset every edge of a face (SketchUp Offset). Positive = inset."""
    if face is None or not face.is_valid or abs(distance) < 1e-9:
        return None
    normal = face.normal.copy()
    origin, u, v, pts2d = _face_frame(face)
    verts = [loop.vert for loop in face.loops]
    count = len(verts)
    if count < 3:
        return None
    # Match winding used by the offset helper.
    poly = list(pts2d)
    order = list(range(count))
    if _signed_area(poly) < 0.0:
        poly.reverse()
        order.reverse()
    inset = _offset_poly_2d(poly, distance)
    if inset is None:
        return None
    # Map inset points back to original loop order.
    ordered_inset = [None] * count
    for i, idx in enumerate(order):
        ordered_inset[idx] = inset[i]
    inner_verts = []
    for i in range(count):
        p = ordered_inset[i]
        inner_verts.append(bm.verts.new(origin + u * p[0] + v * p[1]))
    bm.faces.remove(face)
    for i in range(count):
        a = verts[i]
        b = verts[(i + 1) % count]
        c = inner_verts[(i + 1) % count]
        d = inner_verts[i]
        _new_face(bm, (a, b, c, d), normal)
    inner = _new_face(bm, inner_verts, normal)
    _ensure(bm)
    _select_only_face(bm, inner)
    return inner


def erase_edges(bm, edges):
    valid = [edge for edge in edges if edge is not None and edge.is_valid]
    if not valid:
        return
    bmesh.ops.dissolve_edges(bm, edges=valid, use_verts=True, use_face_split=False)
    _ensure(bm)


def delete_selected(bm):
    """Remove selected faces, then edges, then verts (SketchUp Delete)."""
    faces = [face for face in bm.faces if face.select]
    if faces:
        bmesh.ops.delete(bm, geom=faces, context="FACES")
        _ensure(bm)
        return True
    edges = [edge for edge in bm.edges if edge.select]
    if edges:
        bmesh.ops.delete(bm, geom=edges, context="EDGES")
        _ensure(bm)
        return True
    verts = [vert for vert in bm.verts if vert.select]
    if verts:
        bmesh.ops.delete(bm, geom=verts, context="VERTS")
        _ensure(bm)
        return True
    return False


def translate_verts(verts, delta):
    offset = Vector(delta)
    for vert in verts:
        if vert.is_valid:
            vert.co += offset


def duplicate_selected(bm):
    geom = [v for v in bm.verts if v.select]
    geom += [e for e in bm.edges if e.select]
    geom += [f for f in bm.faces if f.select]
    if not geom:
        return []
    ret = bmesh.ops.duplicate(bm, geom=geom)
    new_verts = [ele for ele in ret.get("geom", []) if isinstance(ele, bmesh.types.BMVert)]
    _select_only_verts(bm, new_verts)
    return new_verts


def _select_only_verts(bm, verts):
    wanted = set(verts)
    for vert in bm.verts:
        vert.select = vert in wanted
    for edge in bm.edges:
        edge.select = all(vert in wanted for vert in edge.verts)
    for face in bm.faces:
        face.select = all(vert in wanted for vert in face.verts)


def rotate_verts(verts, center, axis, angle):
    if abs(angle) < 1e-12:
        return
    rot = Matrix.Rotation(angle, 4, Vector(axis).normalized())
    origin = Vector(center)
    for vert in verts:
        if vert.is_valid:
            vert.co = origin + rot @ (vert.co - origin)


def scale_verts(verts, center, factor, axis=None):
    origin = Vector(center)
    for vert in verts:
        if not vert.is_valid:
            continue
        delta = vert.co - origin
        if axis == "X":
            delta.x *= factor
        elif axis == "Y":
            delta.y *= factor
        elif axis == "Z":
            delta.z *= factor
        else:
            delta *= factor
        vert.co = origin + delta


def paint_face(obj, bm, face, color):
    if face is None or not face.is_valid:
        return
    mesh = obj.data
    rgb = (float(color[0]), float(color[1]), float(color[2]), 1.0)
    name = "OForm {:02X}{:02X}{:02X}".format(
        int(rgb[0] * 255), int(rgb[1] * 255), int(rgb[2] * 255)
    )
    mat = None
    for slot in mesh.materials:
        if slot is not None and slot.name == name:
            mat = slot
            break
    if mat is None:
        import bpy
        mat = bpy.data.materials.new(name)
        mat.diffuse_color = rgb
        mat.use_nodes = True
        node = mat.node_tree.nodes.get("Principled BSDF") if mat.node_tree else None
        if node is not None and "Base Color" in node.inputs:
            node.inputs["Base Color"].default_value = rgb
        mesh.materials.append(mat)
    index = mesh.materials.find(mat.name)
    if index < 0:
        mesh.materials.append(mat)
        index = mesh.materials.find(mat.name)
    face.material_index = index
    _select_only_face(bm, face)


def selection_center(bm):
    verts = selected_verts(bm)
    if not verts:
        return Vector((0.0, 0.0, 0.0))
    acc = Vector((0.0, 0.0, 0.0))
    for vert in verts:
        acc += vert.co
    return acc / len(verts)
