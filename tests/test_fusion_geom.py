"""Tests for the Fusion rebuild's pure geometry (fusion/SwRebuild/lib/geom.py)."""
import math
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "fusion", "SwRebuild", "lib"))
import geom  # noqa: E402

TOP = [1, 0, 0, 0, 0, -1, 0, 1, 0, 0, 0, 0, 1, 0, 0, 0]      # model -> sketch for a sketch on the Top plane


def square(c, h):
    return [(c[0] - h, c[1] - h), (c[0] + h, c[1] - h), (c[0] + h, c[1] + h), (c[0] - h, c[1] + h)]


def test_transform_roundtrip():
    for row in (True, False):
        t = geom.SwTransform(TOP, row)
        p = (0.1, 0.2, 0.3)
        q = t.inverse_apply(t.apply(p))
        assert geom.dist(p, q) < 1e-12


def test_sketch_to_model_is_planar():
    pts, row = geom.sketch_to_model([(0.01, 0.02, 0), (0.03, -0.01, 0)], TOP)
    assert all(abs(p[1]) < 1e-12 for p in pts)            # on the Top plane: y = 0


def test_default_plane():
    o, x, y, n = geom.sketch_frame(TOP)
    assert geom.default_plane_of(n, o) == "top"
    assert geom.default_plane_of((0, 0, 1), (0, 0, 0.01)) is None


def test_material_even_odd():
    outer = square((0, 0), 10)
    hole = square((0, 0), 5)
    island = square((0, 0), 2)
    profiles = [(outer, [hole]), (hole, [island]), (island, [])]
    assert geom.material_profiles(profiles) == [0, 2]


def test_interior_point_concave():
    u = [(0, 0), (6, 0), (6, 6), (4, 6), (4, 2), (2, 2), (2, 6), (0, 6)]
    p = geom.interior_point([u])
    assert geom.point_in_polygon(p, u)


def test_arc_mid():
    m = geom.arc_mid((0, 0, 0), (1, 0, 0), (0, 1, 0), 1)
    assert abs(m[0] - math.cos(math.pi / 4)) < 1e-12 and abs(m[1] - math.sin(math.pi / 4)) < 1e-12
    m = geom.arc_mid((0, 0, 0), (1, 0, 0), (0, 1, 0), -1)
    assert m[0] < 0 and m[1] < 0                          # the long way round, clockwise


def test_param_name():
    assert geom.param_name("D1@Sketch1@Part.SLDPRT") == "Sketch1_D1"
    assert geom.param_name("D2@Boss-Extrude1") == "Boss_Extrude1_D2"
