"""Pure-Python geometry for the rebuild (no Fusion imports, so it is unit-tested outside Fusion).

Vectors are tuples (x, y, z). SolidWorks values are metres; Fusion's internal unit is centimetres (CM = 100).
"""
from __future__ import annotations

import math

CM = 100.0          # metres -> Fusion internal centimetres


def add(a, b): return (a[0] + b[0], a[1] + b[1], a[2] + b[2])
def sub(a, b): return (a[0] - b[0], a[1] - b[1], a[2] - b[2])
def mul(a, k): return (a[0] * k, a[1] * k, a[2] * k)
def dot(a, b): return a[0] * b[0] + a[1] * b[1] + a[2] * b[2]
def cross(a, b): return (a[1] * b[2] - a[2] * b[1], a[2] * b[0] - a[0] * b[2], a[0] * b[1] - a[1] * b[0])
def norm(a): return math.sqrt(dot(a, a))
def dist(a, b): return norm(sub(a, b))


def unit(a):
    n = norm(a)
    return a if n == 0 else (a[0] / n, a[1] / n, a[2] / n)


# -- SolidWorks MathTransform ------------------------------------------------------------------------------------

class SwTransform:
    """A SolidWorks MathTransform ArrayData: rotation [0..8], translation [9..11], scale [12].

    SolidWorks documentation is ambiguous about row/column convention in practice, so both are supported:
    ``row=True``: p' = p·R + t (R[i][j] = a[3i+j]);  ``row=False``: p' = R·p + t.
    """

    def __init__(self, arr, row=True):
        self.r = [arr[0:3], arr[3:6], arr[6:9]]
        self.t = tuple(arr[9:12])
        self.s = arr[12] if len(arr) > 12 and arr[12] else 1.0
        self.row = row

    def apply(self, p):
        r = self.r
        if self.row:
            q = (p[0] * r[0][0] + p[1] * r[1][0] + p[2] * r[2][0],
                 p[0] * r[0][1] + p[1] * r[1][1] + p[2] * r[2][1],
                 p[0] * r[0][2] + p[1] * r[1][2] + p[2] * r[2][2])
        else:
            q = (dot(r[0], p), dot(r[1], p), dot(r[2], p))
        return add(mul(q, self.s), self.t)

    def inverse_apply(self, p):
        """Undo apply (rotation is orthonormal)."""
        q = mul(sub(p, self.t), 1.0 / self.s)
        r = self.r
        if self.row:                    # p = q·R^T
            return (dot(r[0], q), dot(r[1], q), dot(r[2], q))
        return (q[0] * r[0][0] + q[1] * r[1][0] + q[2] * r[2][0],
                q[0] * r[0][1] + q[1] * r[1][1] + q[2] * r[2][1],
                q[0] * r[0][2] + q[1] * r[1][2] + q[2] * r[2][2])


def sketch_frame(model_to_sketch, row=True):
    """(origin, x_dir, y_dir, normal) of a SolidWorks sketch in model space."""
    t = SwTransform(model_to_sketch, row)
    o = t.inverse_apply((0, 0, 0))
    x = sub(t.inverse_apply((1, 0, 0)), o)
    y = sub(t.inverse_apply((0, 1, 0)), o)
    return o, unit(x), unit(y), unit(cross(x, y))


def sketch_to_model(points, model_to_sketch):
    """Map sketch-space points to model space. Returns (points, convention) choosing the convention under which
    the points are coplanar with the sketch plane (both agree for symmetric cases)."""
    best = None
    for row in (True, False):
        t = SwTransform(model_to_sketch, row)
        pts = [t.inverse_apply(p) for p in points]
        back = [t.apply(p) for p in pts]
        err = max((abs(b[2] - p[2]) for b, p in zip(back, points)), default=0.0)
        if best is None or err < best[2]:
            best = (pts, row, err)
    return best[0], best[1]


# -- default planes ----------------------------------------------------------------------------------------------

DEFAULT_PLANES = {"front": (0, 0, 1), "top": (0, 1, 0), "right": (1, 0, 0)}


def default_plane_of(normal, origin=(0, 0, 0), tol=1e-9):
    """'front' / 'top' / 'right' when the plane is a default plane through the origin, else None."""
    if norm(origin) > 1e-9:
        return None
    n = unit(normal)
    for name, d in DEFAULT_PLANES.items():
        if abs(abs(dot(n, d)) - 1) < 1e-7:
            return name
    return None


# -- regions: which sketch profiles are material (SolidWorks even-odd rule) ---------------------------------------

def point_in_polygon(pt, poly):
    """Even-odd test, 2D (x, y)."""
    x, y = pt
    inside = False
    n = len(poly)
    for i in range(n):
        x1, y1 = poly[i]
        x2, y2 = poly[(i + 1) % n]
        if (y1 > y) != (y2 > y):
            xi = x1 + (y - y1) * (x2 - x1) / (y2 - y1)
            if xi > x:
                inside = not inside
    return inside


def interior_point(loops):
    """A point strictly inside the region bounded by `loops` (outer + inner polygons, even-odd)."""
    ys = sorted({p[1] for lp in loops for p in lp})
    if len(ys) < 2:
        return None
    # try several scanlines between distinct vertex heights
    cands = [(ys[i] + ys[i + 1]) / 2 for i in range(len(ys) - 1)]
    cands.sort(key=lambda y: abs(y - (ys[0] + ys[-1]) / 2))
    for y in cands[:50]:
        xs = []
        for lp in loops:
            n = len(lp)
            for i in range(n):
                x1, y1 = lp[i]
                x2, y2 = lp[(i + 1) % n]
                if (y1 > y) != (y2 > y):
                    xs.append(x1 + (y - y1) * (x2 - x1) / (y2 - y1))
        xs.sort()
        best = None
        for i in range(0, len(xs) - 1, 2):
            w = xs[i + 1] - xs[i]
            if w > 1e-12 and (best is None or w > best[0]):
                best = (w, ((xs[i] + xs[i + 1]) / 2, y))
        if best:
            return best[1]
    return None


def material_profiles(profiles):
    """profiles: list of (outer_polygon, [inner_polygons]) in sketch space.
    Returns the indexes of profiles SolidWorks would treat as material: regions enclosed by an odd number of
    the sketch's closed loops (outer area = material, a loop inside it = hole, an island inside the hole = material)."""
    loops = []
    for outer, inners in profiles:
        for lp in [outer] + list(inners):
            if not any(_same_loop(lp, x) for x in loops):
                loops.append(lp)
    keep = []
    for i, (outer, inners) in enumerate(profiles):
        q = interior_point([outer] + list(inners))
        if q is None:
            continue
        depth = sum(1 for lp in loops if point_in_polygon(q, lp))
        if depth % 2 == 1:
            keep.append(i)
    return keep


def _same_loop(a, b, tol=1e-9):
    if len(a) != len(b):
        return False
    sa = sorted((round(p[0] / tol), round(p[1] / tol)) for p in a) if tol > 1e-6 else sorted(a)
    sb = sorted((round(p[0] / tol), round(p[1] / tol)) for p in b) if tol > 1e-6 else sorted(b)
    return all(abs(x[0] - y[0]) < 1e-9 and abs(x[1] - y[1]) < 1e-9 for x, y in zip(sa, sb))


# -- arcs ----------------------------------------------------------------------------------------------------------

def arc_mid(center, start, end, direction):
    """Mid point of a sketch arc (2D/3D with z ignored) from SolidWorks data; direction 1 = CCW, -1 = CW."""
    a0 = math.atan2(start[1] - center[1], start[0] - center[0])
    a1 = math.atan2(end[1] - center[1], end[0] - center[0])
    r = math.hypot(start[0] - center[0], start[1] - center[1])
    if direction >= 0:
        sweep = (a1 - a0) % (2 * math.pi) or 2 * math.pi
    else:
        sweep = -((a0 - a1) % (2 * math.pi) or 2 * math.pi)
    am = a0 + sweep / 2
    z = start[2] if len(start) > 2 else 0.0
    return (center[0] + r * math.cos(am), center[1] + r * math.sin(am), z)


# -- matching B-rep entities by geometry ---------------------------------------------------------------------------

def best_match(target, candidates, key, tol):
    """The candidate whose key point is nearest `target` (within tol), else None. candidates: iterable of objects;
    key(obj) -> point or None."""
    best = None
    for c in candidates:
        p = key(c)
        if p is None:
            continue
        d = dist(target, p)
        if d <= tol and (best is None or d < best[0]):
            best = (d, c)
    return best[1] if best else None


# -- names ---------------------------------------------------------------------------------------------------------

def param_name(full_name: str) -> str:
    """'D1@Sketch1@Part.SLDPRT' -> 'Sketch1_D1' (a valid Fusion parameter name)."""
    parts = (full_name or "").split("@")
    name = f"{parts[1]}_{parts[0]}" if len(parts) >= 2 else parts[0]
    out = "".join(ch if ch.isalnum() or ch == "_" else "_" for ch in name)
    if not out or not (out[0].isalpha() or out[0] == "_"):
        out = "p_" + out
    return out
