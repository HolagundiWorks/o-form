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
    if len(set(verts)) < 3:
        return None
    try:
        face = bm.faces.new(verts)
    except ValueError:
        face = bm.faces.get(tuple(verts))
    if face is None or not face.is_valid:
        return None
    face.normal_update()
    if face.normal.dot(normal) < 0.0:
        face.normal_flip()
    return face


def _split_face_with_hole(bm, face, points):
    """Replace face with an inner cap plus the frame around it. points are CCW in 3D."""
    normal = face.normal.copy()
    origin, u, v, outer_2d = _face_frame(face)
    outer_verts = [loop.vert for loop in face.loops]
    if _signed_area(outer_2d) < 0.0:
        outer_verts.reverse()
        outer_2d.reverse()
    inner_verts = [_new_vert(bm, co) for co in points]
    inner_2d = [_project(origin, u, v, vert.co) for vert in inner_verts]
    if _signed_area(inner_2d) < 0.0:
        inner_verts.reverse()
        inner_2d.reverse()

    target = abs(_signed_area(outer_2d)) - abs(_signed_area(inner_2d))
    hole_verts = list(reversed(inner_verts))
    hole_2d = list(reversed(inner_2d))
    pairs = []
    for i, ov in enumerate(outer_verts):
        for j, hv in enumerate(hole_verts):
            pairs.append(((ov.co - hv.co).length_squared, i, j))
    pairs.sort(key=lambda item: item[0])

    chosen = None
    for _dist, i0, j0 in pairs:
        ring_v = outer_verts[i0:] + outer_verts[: i0 + 1] + hole_verts[j0:] + hole_verts[: j0 + 1]
        ring_p = outer_2d[i0:] + outer_2d[: i0 + 1] + hole_2d[j0:] + hole_2d[: j0 + 1]
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
        return _split_face_with_fill(bm, face, inner_verts, inner_2d, normal, origin, u, v)

    ring_v, tris = chosen
    bm.faces.remove(face)
    made = []
    for ia, ib, ic in tris:
        tri = _new_face(bm, (ring_v[ia], ring_v[ib], ring_v[ic]), normal)
        if tri is not None:
            made.append(tri)
    inner_face = _new_face(bm, inner_verts, normal)
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


def add_polygon(bm, points, tol=TOL):
    """Add a face, splitting a host face when the polygon lies inside it."""
    pts = [Vector(p) for p in points]
    if len(pts) < 3:
        return None
    # Drop a zero-area polygon.
    if (pts[1] - pts[0]).cross(pts[2] - pts[0]).length < 1e-10:
        return None
    host = find_host_face(bm, pts, tol)
    if host is not None and _strictly_inside(host, pts):
        face, _made = _split_face_with_hole(bm, host, pts)
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


def push_pull(bm, face, distance, copy=False):
    if face is None or not face.is_valid or abs(distance) < 1e-9:
        return None
    normal = face.normal.copy()
    working = face
    if copy:
        # SketchUp Ctrl+Push/Pull leaves the original face and extrudes a copy.
        dup = bmesh.ops.duplicate(bm, geom=[face])
        faces = [ele for ele in dup.get("geom", []) if isinstance(ele, bmesh.types.BMFace)]
        if not faces:
            return None
        working = faces[0]
    ret = bmesh.ops.extrude_discrete_faces(bm, faces=[working])
    faces = ret.get("faces") or []
    if not faces:
        return None
    top = faces[0]
    bmesh.ops.translate(bm, verts=list(top.verts), vec=normal * distance)
    _ensure(bm)
    _select_only_face(bm, top)
    return top


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
    return add_segment(bm, start, end, tol=tol)


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


def offset_face(bm, face, distance):
    if face is None or not face.is_valid or abs(distance) < 1e-9:
        return None
    ret = bmesh.ops.inset_region(
        bm,
        faces=[face],
        thickness=abs(distance),
        depth=0.0,
        use_even_offset=True,
        use_outset=distance < 0.0,
    )
    faces = [f for f in ret.get("faces", []) if f.is_valid]
    _ensure(bm)
    inner = None
    for item in faces:
        if item is not face and item.is_valid:
            inner = item
    if inner is None and face.is_valid:
        inner = face
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
