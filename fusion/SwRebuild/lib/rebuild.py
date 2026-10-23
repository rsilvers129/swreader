"""Rebuild a SolidWorks part in Fusion from swexport JSON - feature by feature, as an engineer would remodel it:
same sketch planes, same sketch geometry, the same relations and named driving dimensions, then the features in
history order, driven by those parameters.

Supported (v1): default and offset/angled reference planes, 2D sketches (lines, arcs, circles, ellipses, splines,
points, construction geometry, relations, dimensions), extrude / cut-extrude (blind, mid-plane, through all, two
directions, draft), revolve / cut-revolve, constant-radius fillets, equal-distance chamfers, simple / counterbore /
countersink holes from the Hole Wizard, linear and circular patterns, mirrors. Anything else is reported and skipped,
and the rebuild continues.
"""
from __future__ import annotations

import math
import re
import traceback

import adsk.core
import adsk.fusion

from . import geom

CM = geom.CM
TOL = 1e-4                    # cm: geometric matching tolerance (1 micron)

# swEndConditions_e
END_BLIND, END_THROUGH_ALL, END_THROUGH_NEXT, END_UP_TO_VERTEX, END_UP_TO_SURFACE, END_OFFSET_SURFACE, \
    END_MID_PLANE, END_UP_TO_BODY = range(8)
END_THROUGH_ALL_BOTH, END_UP_TO_SELECTION, END_UP_TO_NEXT = 9, 10, 11

DISTANCE_UNITS = {"mm": "MillimeterDistanceUnits", "cm": "CentimeterDistanceUnits", "m": "MeterDistanceUnits",
                  "in": "InchDistanceUnits", "ft": "FootDistanceUnits", "ft-in": "InchDistanceUnits"}

SKIP = {"CommentsFolder", "FavoriteFolder", "HistoryFolder", "SelectionSetFolder", "SensorFolder", "DocsFolder",
        "DetailCabinet", "SurfaceBodyFolder", "SolidBodyFolder", "EqnFolder", "MaterialFolder", "InkMarkupFolder",
        "NotesAreaFtrFolder", "OriginProfileFeature", "MateGroup", "Reference", "FtrFolder", "LiveSection",
        "EnvFolder", "BlockFolder", "AmbientLight", "DirectionLight", "CommentsFolder"}


class Skip(Exception):
    """A feature this version cannot rebuild (reported, rebuild continues)."""


def P(xyz):
    """SolidWorks metres -> Fusion Point3D (cm)."""
    return adsk.core.Point3D.create(xyz[0] * CM, xyz[1] * CM, xyz[2] * CM)


def V(real_cm):
    return adsk.core.ValueInput.createByReal(real_cm)


class Rebuilder:
    def __init__(self, doc: dict, design: adsk.fusion.Design, log):
        self.doc, self.design, self.log = doc, design, log
        self.root = design.rootComponent
        self.planes = {}          # SW feature name -> Fusion planar entity
        self.axes = {}            # SW feature name -> Fusion linear entity
        self.sketches = {}        # SW sketch name -> (Fusion sketch, {sw id: fusion entity}, sw sketch dict)
        self.features = {}        # SW feature name -> Fusion feature
        self.params = {}          # SW full dimension name -> Fusion parameter
        self.built, self.skipped = [], []
        units = ((doc.get("document") or {}).get("units") or {}).get("length")
        if units in DISTANCE_UNITS:
            design.fusionUnitsManager.distanceDisplayUnits = getattr(adsk.fusion.DistanceUnits, DISTANCE_UNITS[units])

    # -- the feature list ----------------------------------------------------------------------------------------

    def steps(self):
        """The SolidWorks features to rebuild, in history order (sketches absorbed by a feature come first)."""
        feats = (self.doc.get("part") or {}).get("features") or []
        return [f for f in feats if f.get("type") not in SKIP and not f.get("suppressed")]

    def build(self, f) -> str:
        """Rebuild one feature. Returns a status line."""
        t, name = f.get("type"), f.get("name")
        fn = BUILDERS.get(t)
        try:
            if fn is None:
                raise Skip(f"feature type {t} is not supported yet")
            fn(self, f)
            self.built.append(name)
            return f"built {name} ({t})"
        except Skip as e:
            self.skipped.append((name, t, str(e)))
            return f"SKIPPED {name} ({t}): {e}"
        except Exception as e:                                  # noqa: BLE001 - report and continue
            self.skipped.append((name, t, f"{type(e).__name__}: {e}"))
            self.log(traceback.format_exc())
            return f"FAILED {name} ({t}): {e}"

    def finish(self):
        """Apply equations once every parameter exists."""
        for e in (self.doc.get("document") or {}).get("equations") or []:
            self._equation(e)

    # -- parameters ----------------------------------------------------------------------------------------------

    def _name_param(self, param, sw_dim):
        """Give a Fusion parameter the SolidWorks dimension's name (Sketch1_D1) and exact value."""
        if param is None or not sw_dim:
            return
        full = sw_dim.get("full_name") or sw_dim.get("name") or ""
        self.params[full.rsplit("@", 1)[0] if full.count("@") >= 2 else full] = param
        nm = geom.param_name(full)
        try:
            param.name = nm
        except Exception:                                       # name taken (duplicate) - keep Fusion's
            pass

    def _equation(self, e):
        text = e.get("equation") or ""
        m = re.match(r'\s*"([^"]+)"\s*=\s*(.+)$', text)
        if not m:
            return
        lhs, rhs = m.group(1), m.group(2)

        def ref(mm):
            p = self.params.get(mm.group(1))
            return p.name if p is not None else mm.group(0)
        expr = re.sub(r'"([^"]+)"', ref, rhs)
        try:
            if e.get("global_variable"):
                up = self.design.userParameters
                if up.itemByName(geom.param_name(lhs)) is None:
                    up.add(geom.param_name(lhs), adsk.core.ValueInput.createByString(expr), "", "SolidWorks global variable")
            else:
                p = self.params.get(lhs)
                if p is not None:
                    p.expression = expr
        except Exception as ex:                                 # noqa: BLE001
            self.log(f"equation not applied: {text} ({ex})")

    # -- planes --------------------------------------------------------------------------------------------------

    def ref_plane(self, f):
        d = f.get("definition") or {}
        tr = d.get("transform")
        if tr:
            o = tuple(tr[9:12])
            n = geom.SwTransform(tr).apply((0, 0, 1))
            n = geom.sub(n, geom.SwTransform(tr).apply((0, 0, 0)))
        else:
            o, n = (0, 0, 0), None
        default = geom.default_plane_of(n, o) if n else None
        if default is None and not (f.get("parents") or []):
            # the first three planes of every part are the default planes (names are localized: use the order)
            default = ["front", "top", "right"][len([k for k in self.planes if k.startswith("__default")]) % 3]
        if default:
            plane = {"front": self.root.xYConstructionPlane, "top": self.root.xZConstructionPlane,
                     "right": self.root.yZConstructionPlane}[default]
            self.planes[f["name"]] = plane
            self.planes["__default_" + default] = plane
            return
        # an offset plane from a known plane, else a plane through three points of the SolidWorks plane
        parent = next((self.planes[p] for p in f.get("parents") or [] if p in self.planes), None)
        inp = self.root.constructionPlanes.createInput()
        dist = d.get("distance")
        if parent is not None and dist and n:
            pn = _plane_normal(parent)
            po = _plane_origin(parent)
            signed = geom.dot(geom.sub(geom.mul(o, CM), po), pn) if pn else dist * CM
            if pn and abs(abs(geom.dot(geom.unit(n), pn)) - 1) < 1e-6:
                inp.setByOffset(parent, V(signed))
                pl = self.root.constructionPlanes.add(inp)
                pl.name = f["name"]
                self.planes[f["name"]] = pl
                dims = f.get("dimensions") or []
                if dims:
                    self._name_param(_param_of(pl.definition, "offset"), dims[0])
                return
        if not tr:
            raise Skip("plane has no placement in the export")
        t = geom.SwTransform(tr)
        pts = [t.apply(p) for p in ((0, 0, 0), (0.01, 0, 0), (0, 0.01, 0))]
        sk = self.root.sketches.add(self.root.xYConstructionPlane)
        sk.name = f["name"] + " points"
        sp = [sk.sketchPoints.add(P(p)) for p in pts]
        sk.isVisible = False
        inp.setByThreePoints(sp[0], sp[1], sp[2])
        pl = self.root.constructionPlanes.add(inp)
        pl.name = f["name"]
        self.planes[f["name"]] = pl

    def ref_axis(self, f):
        a = (f.get("definition") or {}).get("axis")
        if not a or len(a) < 6:
            raise Skip("axis has no geometry in the export")
        sk = self.root.sketches.add(self.root.xYConstructionPlane)
        sk.name = f["name"] + " line"
        line = sk.sketchCurves.sketchLines.addByTwoPoints(P(a[0:3]), P(a[3:6]))
        sk.isVisible = False
        inp = self.root.constructionAxes.createInput()
        inp.setByLine(line)
        ax = self.root.constructionAxes.add(inp)
        ax.name = f["name"]
        self.axes[f["name"]] = ax

    # -- sketches ------------------------------------------------------------------------------------------------

    def _sketch_plane(self, f, sk):
        for p in f.get("parents") or []:
            if p in self.planes:
                return self.planes[p]
        o, x, y, n = geom.sketch_frame(sk["model_to_sketch"])
        face = self._find_face(o, n)                           # sketched on a face (the usual case)
        if face is not None:
            return face
        d = geom.default_plane_of(n, o)
        if d:
            return self.planes.get("__default_" + d)
        # a plane parallel to a default plane: offset construction plane
        for name, axis in geom.DEFAULT_PLANES.items():
            if abs(abs(geom.dot(n, axis)) - 1) < 1e-7:
                base = {"front": self.root.xYConstructionPlane, "top": self.root.xZConstructionPlane,
                        "right": self.root.yZConstructionPlane}[name]
                inp = self.root.constructionPlanes.createInput()
                inp.setByOffset(base, V(geom.dot(o, axis) * CM))
                pl = self.root.constructionPlanes.add(inp)
                pl.name = f["name"] + " plane"
                return pl
        raise Skip("could not find or build the sketch plane")

    def _find_face(self, origin_m, normal):
        """A planar face of the current bodies that contains the sketch plane."""
        o = geom.mul(origin_m, CM)
        for body in self.root.bRepBodies:
            for face in body.faces:
                g = face.geometry
                if g.surfaceType != adsk.core.SurfaceTypes.PlaneSurfaceType:
                    continue
                pn = (g.normal.x, g.normal.y, g.normal.z)
                if abs(abs(geom.dot(geom.unit(pn), normal)) - 1) > 1e-6:
                    continue
                po = (g.origin.x, g.origin.y, g.origin.z)
                if abs(geom.dot(geom.sub(o, po), geom.unit(pn))) < TOL:
                    return face
        return None

    def sketch(self, f):
        sk = f.get("sketch") or {}
        if sk.get("is_3d"):
            raise Skip("3D sketches are not supported yet")
        if not sk.get("model_to_sketch"):
            raise Skip("sketch has no placement in the export")
        plane = self._sketch_plane(f, sk)
        s = self.root.sketches.add(plane)
        s.name = f["name"]
        s.isComputeDeferred = True
        ids = {}

        pts = {p["id"]: p["xyz"] for p in sk.get("points") or [] if p.get("id")}
        for seg in sk.get("segments") or []:
            for k in ("start", "end", "center", "major", "minor", "focus", "apex"):
                if seg.get(k) and seg[k].get("id"):
                    pts.setdefault(seg[k]["id"], seg[k]["xyz"])
        model_pts, row = geom.sketch_to_model(list(pts.values()), sk["model_to_sketch"])
        model_of = dict(zip(pts.keys(), model_pts))

        def sp(pid):
            if pid not in ids:
                ids[pid] = s.sketchPoints.add(s.modelToSketchSpace(P(model_of[pid])))
            return ids[pid]

        def local(pid):
            return s.modelToSketchSpace(P(model_of[pid]))

        curves = s.sketchCurves
        for seg in sk.get("segments") or []:
            kind, sid = seg.get("kind"), seg.get("id")
            try:
                if kind == "line":
                    ent = curves.sketchLines.addByTwoPoints(sp(seg["start"]["id"]), sp(seg["end"]["id"]))
                elif kind == "arc" and seg.get("circle"):
                    ent = curves.sketchCircles.addByCenterRadius(sp(seg["center"]["id"]), seg["radius"] * CM)
                elif kind == "arc":
                    c, a, b = (pts[seg[k]["id"]] for k in ("center", "start", "end"))
                    mid_sk = geom.arc_mid(c, a, b, seg.get("direction") or 1)
                    mid = geom.sketch_to_model([mid_sk], sk["model_to_sketch"])[0][0]
                    ent = curves.sketchArcs.addByThreePoints(sp(seg["start"]["id"]), s.modelToSketchSpace(P(mid)),
                                                            sp(seg["end"]["id"]))
                    try:
                        ent.centerSketchPoint.merge(sp(seg["center"]["id"]))
                    except Exception:
                        pass
                elif kind == "ellipse":
                    ent = curves.sketchEllipses.add(sp(seg["center"]["id"]), local(seg["major"]["id"]), local(seg["minor"]["id"]))
                elif kind == "spline":
                    coll = adsk.core.ObjectCollection.create()
                    for p in seg.get("points") or []:
                        pts.setdefault(p["id"], p["xyz"])
                        if p["id"] not in model_of:
                            model_of[p["id"]] = geom.sketch_to_model([p["xyz"]], sk["model_to_sketch"])[0][0]
                        coll.add(sp(p["id"]))
                    ent = curves.sketchFittedSplines.add(coll)
                else:
                    self.log(f"  {f['name']}: {kind} not drawn")
                    continue
                if seg.get("construction"):
                    ent.isConstruction = True
                ids[sid] = ent
            except Exception as e:                              # noqa: BLE001
                self.log(f"  {f['name']}: {kind} {sid} not drawn ({e})")

        # free-standing points (hole centres etc.)
        for pid in pts:
            if pid not in ids:
                sp(pid)

        self._relations(s, sk, ids)
        self._dimensions(s, f, ids)
        s.isComputeDeferred = False
        self.sketches[f["name"]] = (s, ids, sk)
        self.features[f["name"]] = s

    def _ent(self, s, ids, e):
        if not e:
            return None
        if e.get("kind") in ("sketch_point", "sketch_segment"):
            return ids.get(e.get("id"))
        if e.get("kind") == "feature" and (e.get("name") or "").startswith("Point1@"):
            return s.originPoint
        return None

    def _relations(self, s, sk, ids):
        gc = s.geometricConstraints
        for r in sk.get("relations") or []:
            k = r.get("kind")
            ents = [self._ent(s, ids, e) for e in r.get("entities") or []]
            if any(e is None for e in ents):
                continue
            try:
                if k == "horizontal" and len(ents) == 1:
                    gc.addHorizontal(ents[0])
                elif k == "vertical" and len(ents) == 1:
                    gc.addVertical(ents[0])
                elif k == "horizontal_points" or (k == "horizontal" and len(ents) == 2):
                    gc.addHorizontalPoints(ents[0], ents[1])
                elif k == "vertical_points" or (k == "vertical" and len(ents) == 2):
                    gc.addVerticalPoints(ents[0], ents[1])
                elif k in ("coincident", "merge_points") and len(ents) == 2:
                    a, b = ents
                    if isinstance(b, adsk.fusion.SketchPoint) and not isinstance(a, adsk.fusion.SketchPoint):
                        a, b = b, a
                    if a != b:
                        gc.addCoincident(a, b)
                elif k == "parallel":
                    gc.addParallel(ents[0], ents[1])
                elif k == "perpendicular":
                    a, b = ents if isinstance(ents[0], adsk.fusion.SketchLine) else ents[::-1]
                    gc.addPerpendicular2(a, b)
                elif k == "tangent":
                    gc.addTangent(ents[0], ents[1])
                elif k in ("concentric", "coradial"):
                    gc.addConcentric(ents[0], ents[1])
                elif k == "equal":
                    gc.addEqual(ents[0], ents[1])
                elif k == "collinear":
                    gc.addCollinear(ents[0], ents[1])
                elif k == "midpoint" and len(ents) == 2:
                    pt, ln = (ents if isinstance(ents[0], adsk.fusion.SketchPoint) else ents[::-1])
                    gc.addMidPoint(pt, ln)
                elif k == "symmetric" and len(ents) == 3:
                    gc.addSymmetry(ents[0], ents[1], ents[2])
                elif k == "fixed":
                    for e in ents:
                        e.isFixed = True
            except Exception as e:                              # noqa: BLE001 - redundant / conflicting: skip
                self.log(f"  relation {k} not added ({e})")

    def _dimensions(self, s, f, ids):
        dims = s.sketchDimensions
        for d in f.get("dimensions") or []:
            att = [self._ent(s, ids, e) for e in d.get("attached") or []]
            att = [a for a in att if a is not None]
            value = d.get("value")
            if not att or value is None:
                continue
            try:
                dim = self._add_dimension(s, dims, att, value, d.get("dimension_type"))
                if dim is not None:
                    try:
                        dim.parameter.value = value if _is_angle(dim) else value * CM
                    except Exception:
                        pass
                    self._name_param(dim.parameter, d)
            except Exception as e:                              # noqa: BLE001
                self.log(f"  dimension {d.get('name')} not added ({e})")

    def _add_dimension(self, s, dims, att, value, sw_type=None):
        F = adsk.fusion
        text = _text_point(att)
        if len(att) == 1:
            a = att[0]
            if isinstance(a, F.SketchLine):
                return dims.addDistanceDimension(a.startSketchPoint, a.endSketchPoint,
                                                 F.DimensionOrientations.AlignedDimensionOrientation, text)
            if isinstance(a, (F.SketchCircle, F.SketchArc)):
                if sw_type == 5 or (sw_type != 6 and isinstance(a, F.SketchArc)):
                    return dims.addRadialDimension(a, text)
                return dims.addDiameterDimension(a, text)
            return None
        a, b = att[0], att[1]
        if isinstance(a, F.SketchPoint) and isinstance(b, F.SketchPoint):
            pa, pb = a.geometry, b.geometry
            dx, dy = abs(pa.x - pb.x), abs(pa.y - pb.y)
            v = value * CM
            orient = F.DimensionOrientations.AlignedDimensionOrientation
            if abs(dx - v) < TOL and abs(dy - v) > TOL:
                orient = F.DimensionOrientations.HorizontalDimensionOrientation
            elif abs(dy - v) < TOL and abs(dx - v) > TOL:
                orient = F.DimensionOrientations.VerticalDimensionOrientation
            return dims.addDistanceDimension(a, b, orient, text)
        if isinstance(a, F.SketchLine) and isinstance(b, F.SketchLine):
            da, db = _dir(a), _dir(b)
            if abs(abs(geom.dot(da, db)) - 1) < 1e-9:
                return dims.addOffsetDimension(a, b, text)
            return dims.addAngularDimension(a, b, text)
        line = a if isinstance(a, F.SketchLine) else b if isinstance(b, F.SketchLine) else None
        other = b if line is a else a
        if line is not None and isinstance(other, F.SketchPoint):
            return dims.addOffsetDimension(line, other, text)
        if isinstance(a, (F.SketchCircle, F.SketchArc)) or isinstance(b, (F.SketchCircle, F.SketchArc)):
            ca = a.centerSketchPoint if hasattr(a, "centerSketchPoint") else a
            cb = b.centerSketchPoint if hasattr(b, "centerSketchPoint") else b
            if isinstance(ca, F.SketchPoint) and isinstance(cb, F.SketchPoint):
                return dims.addDistanceDimension(ca, cb, F.DimensionOrientations.AlignedDimensionOrientation, text)
        return None

    # -- profiles ------------------------------------------------------------------------------------------------

    def _sketch_for(self, f):
        for n in (f.get("sub_features") or []) + (f.get("parents") or []):
            if n in self.sketches:
                return self.sketches[n]
        raise Skip("its sketch was not rebuilt")

    def _profiles(self, s):
        """The sketch regions SolidWorks would extrude (even-odd rule), as an ObjectCollection."""
        polys = []
        for prof in s.profiles:
            loops = []
            outer, inners = None, []
            for lp in prof.profileLoops:
                poly = _sample_loop(lp)
                if lp.isOuter:
                    outer = poly
                else:
                    inners.append(poly)
            polys.append((outer or [], inners))
        keep = geom.material_profiles(polys)
        coll = adsk.core.ObjectCollection.create()
        for i in keep:
            coll.add(s.profiles.item(i))
        if coll.count == 0:
            raise Skip("the sketch has no closed region")
        return coll

    def _operation(self, f, cut):
        F = adsk.fusion.FeatureOperations
        if cut:
            return F.CutFeatureOperation
        d = f.get("definition") or {}
        if self.root.bRepBodies.count == 0 or d.get("merge") is False:
            return F.NewBodyFeatureOperation
        return F.JoinFeatureOperation

    def _direction(self, s, sk, reverse):
        """Fusion extent direction matching SolidWorks' sketch normal (reversed if the feature says so)."""
        _, _, _, n_sw = geom.sketch_frame(sk["model_to_sketch"])
        x, y = s.xDirection, s.yDirection
        n_f = geom.cross((x.x, x.y, x.z), (y.x, y.y, y.z))
        same = geom.dot(n_sw, n_f) > 0
        E = adsk.fusion.ExtentDirections
        positive = same != bool(reverse)
        return E.PositiveExtentDirection if positive else E.NegativeExtentDirection

    # -- features ------------------------------------------------------------------------------------------------

    def extrude(self, f, cut=False):
        s, ids, sk = self._sketch_for(f)
        d = f.get("definition") or {}
        if d.get("is_thin"):
            raise Skip("thin-feature extrudes are not supported yet")
        ext = self.root.features.extrudeFeatures
        prof = self._profiles(s)
        cond = d.get("end_condition", END_BLIND)
        depth = d.get("depth")
        dims = f.get("dimensions") or []
        taper = V(d["draft_angle"]) if d.get("draft_while_extruding") and d.get("draft_angle") else V(0)

        def attempt(reverse):
            inp = ext.createInput(prof, self._operation(f, cut))
            direction = self._direction(s, sk, reverse)
            if cond == END_THROUGH_ALL_BOTH:
                inp.setTwoSidesExtent(adsk.fusion.ThroughAllExtentDefinition.create(),
                                      adsk.fusion.ThroughAllExtentDefinition.create())
            elif cond == END_MID_PLANE:
                inp.setSymmetricExtent(V(depth * CM), True)
            elif cond == END_THROUGH_ALL or (cut and cond in (END_THROUGH_NEXT, END_UP_TO_NEXT, END_UP_TO_SURFACE,
                                                                END_UP_TO_BODY, END_UP_TO_SELECTION)):
                inp.setOneSideExtent(adsk.fusion.ThroughAllExtentDefinition.create(), direction)
            elif d.get("both_directions"):
                d2 = d.get("depth_2") or depth
                inp.setTwoSidesExtent(adsk.fusion.DistanceExtentDefinition.create(V(depth * CM)),
                                      adsk.fusion.DistanceExtentDefinition.create(V(d2 * CM)))
            elif cond in (END_BLIND,) and depth:
                inp.setOneSideExtent(adsk.fusion.DistanceExtentDefinition.create(V(depth * CM)), direction, taper)
            else:
                raise Skip(f"end condition {cond} is not supported yet")
            return ext.add(inp)

        # SolidWorks' default side for cuts depends on the face; if the first side removes nothing, try the other
        try:
            feat = attempt(bool(d.get("reverse_direction")))
        except Skip:
            raise
        except Exception:
            feat = attempt(not d.get("reverse_direction"))
        feat.name = f["name"]
        self.features[f["name"]] = feat
        if dims:
            self._name_param(_param_of(feat.extentOne, "distance"), dims[0])
            if len(dims) > 1 and d.get("both_directions"):
                self._name_param(_param_of(feat.extentTwo, "distance"), dims[1])

    def cut(self, f):
        self.extrude(f, cut=True)

    def revolve(self, f, cut=False):
        s, ids, sk = self._sketch_for(f)
        d = f.get("definition") or {}
        axis = None
        sel = (d.get("selections") or {}).get("axis")
        if sel:
            axis = self._ent(s, ids, sel) or self._match_edge(sel) or self.axes.get(sel.get("name"))
        if axis is None:                                        # first construction line of the sketch
            axis = next((e for e in ids.values() if isinstance(e, adsk.fusion.SketchLine) and e.isConstruction), None)
        if axis is None:
            raise Skip("revolve axis not found")
        rev = self.root.features.revolveFeatures
        inp = rev.createInput(self._profiles(s), axis, self._operation(f, cut))
        angle = d.get("angle") or 2 * math.pi
        inp.setAngleExtent(False, V(angle))
        feat = rev.add(inp)
        feat.name = f["name"]
        self.features[f["name"]] = feat
        dims = f.get("dimensions") or []
        if dims:
            self._name_param(_param_of(feat.extentDefinition, "angle"), dims[0])

    def revcut(self, f):
        self.revolve(f, cut=True)

    def _edges(self, items):
        coll = adsk.core.ObjectCollection.create()
        for it in items or []:
            e = self._match_edge(it)
            if e is not None and not _in(coll, e):
                coll.add(e)
        return coll

    def _match_edge(self, desc):
        if not desc or desc.get("kind") != "edge" or not desc.get("mid"):
            return None
        target = geom.mul(desc["mid"], CM)
        edges = [e for b in self.root.bRepBodies for e in b.edges]
        return geom.best_match(target, edges, _edge_mid, TOL * 10)

    def fillet(self, f):
        d = f.get("definition") or {}
        edges = self._edges((d.get("selections") or {}).get("items"))
        if edges.count == 0:
            raise Skip("filleted edges not found (export has no edge selections or they did not match)")
        r = d.get("radius")
        if not r:
            raise Skip("fillet radius missing")
        fil = self.root.features.filletFeatures
        inp = fil.createInput()
        inp.edgeSetInputs.addConstantRadiusEdgeSet(edges, V(r * CM), True)
        feat = fil.add(inp)
        feat.name = f["name"]
        self.features[f["name"]] = feat
        dims = f.get("dimensions") or []
        if dims:
            try:
                self._name_param(feat.edgeSets.item(0).radius, dims[0])
            except Exception:
                pass

    def chamfer(self, f):
        d = f.get("definition") or {}
        edges = self._edges((d.get("selections") or {}).get("items"))
        if edges.count == 0:
            raise Skip("chamfered edges not found")
        dist = d.get("distance")
        if not dist:
            raise Skip("chamfer distance missing")
        ch = self.root.features.chamferFeatures
        inp = ch.createInput2()
        inp.chamferEdgeSets.addEqualDistanceChamferEdgeSet(edges, V(dist * CM), True)
        feat = ch.add(inp)
        feat.name = f["name"]
        self.features[f["name"]] = feat

    def hole(self, f):
        d = f.get("definition") or {}
        sketch = next((self.sketches[n] for n in f.get("sub_features") or [] if n in self.sketches), None)
        if sketch is None:
            raise Skip("hole position sketch not rebuilt")
        s, ids, sk = sketch
        pts = adsk.core.ObjectCollection.create()
        for e in ids.values():
            if isinstance(e, adsk.fusion.SketchPoint) and not e.connectedEntities:
                pts.add(e)
        if pts.count == 0:
            raise Skip("no hole positions")
        dia = d.get("tap_drill_diameter") or d.get("diameter")
        if not dia:
            raise Skip("hole diameter missing")
        holes = self.root.features.holeFeatures
        if d.get("counterbore_diameter"):
            inp = holes.createCounterboreInput(V(dia * CM), V(d["counterbore_diameter"] * CM), V((d.get("counterbore_depth") or 0) * CM))
        elif d.get("countersink_diameter"):
            inp = holes.createCountersinkInput(V(dia * CM), V(d["countersink_diameter"] * CM), V(d.get("countersink_angle") or math.radians(82)))
        else:
            inp = holes.createSimpleInput(V(dia * CM))
        inp.setPositionBySketchPoints(pts)
        if d.get("end_condition") == END_THROUGH_ALL or not d.get("depth"):
            inp.setAllExtent(adsk.fusion.ExtentDirections.NegativeExtentDirection)
        else:
            inp.setDistanceExtent(V(d["depth"] * CM))
        feat = holes.add(inp)
        feat.name = f["name"]
        self.features[f["name"]] = feat
        if d.get("thread_diameter"):
            self.log(f"  {f['name']}: tapped hole rebuilt at tap-drill size; add the thread "
                     f"({d.get('fastener_size') or ''} {d.get('standard') or ''}) with Thread")

    def _pattern_inputs(self, f):
        names = ((f.get("definition") or {}).get("selections") or {}).get("features") or []
        coll = adsk.core.ObjectCollection.create()
        for n in names:
            if n in self.features:
                coll.add(self.features[n])
        if coll.count == 0:
            raise Skip("patterned features were not rebuilt")
        return coll

    def _direction_entity(self, desc):
        if not desc:
            return None
        if desc.get("kind") == "edge":
            return self._match_edge(desc)
        if desc.get("kind") == "feature":
            return self.axes.get(desc.get("name")) or self.planes.get(desc.get("name"))
        return None

    def linear_pattern(self, f):
        d = f.get("definition") or {}
        sel = d.get("selections") or {}
        d1 = self._direction_entity(sel.get("direction_1"))
        if d1 is None:
            raise Skip("pattern direction not found")
        pat = self.root.features.rectangularPatternFeatures
        inp = pat.createInput(self._pattern_inputs(f), d1, V(d.get("count_1") or 2), V((d.get("spacing_1") or 0) * CM),
                              adsk.fusion.PatternDistanceType.SpacingPatternDistanceType)
        d2 = self._direction_entity(sel.get("direction_2"))
        if d2 is not None and (d.get("count_2") or 1) > 1:
            inp.setDirectionTwo(d2, V(d["count_2"]), V((d.get("spacing_2") or 0) * CM))
        feat = pat.add(inp)
        feat.name = f["name"]
        self.features[f["name"]] = feat

    def circular_pattern(self, f):
        d = f.get("definition") or {}
        axis = self._direction_entity((d.get("selections") or {}).get("axis"))
        if axis is None:
            raise Skip("pattern axis not found")
        pat = self.root.features.circularPatternFeatures
        inp = pat.createInput(self._pattern_inputs(f), axis)
        inp.quantity = V(d.get("count") or 2)
        total = (d.get("spacing") or 0) * ((d.get("count") or 1) - 1) if not d.get("equal_spacing") else d.get("spacing")
        inp.totalAngle = V(total or 2 * math.pi)
        inp.isSymmetric = False
        feat = pat.add(inp)
        feat.name = f["name"]
        self.features[f["name"]] = feat

    def mirror(self, f):
        d = f.get("definition") or {}
        plane_desc = (d.get("selections") or {}).get("plane")
        plane = None
        if plane_desc:
            if plane_desc.get("kind") == "feature":
                plane = self.planes.get(plane_desc.get("name"))
            elif plane_desc.get("kind") == "face":
                pt = plane_desc.get("point")
                nm = plane_desc.get("normal")
                if pt and nm:
                    plane = self._find_face(pt, geom.unit(nm))
        if plane is None:
            raise Skip("mirror plane not found")
        mir = self.root.features.mirrorFeatures
        inp = mir.createInput(self._pattern_inputs(f), plane)
        feat = mir.add(inp)
        feat.name = f["name"]
        self.features[f["name"]] = feat


# -- helpers -------------------------------------------------------------------------------------------------------

def _is_angle(dim):
    return isinstance(dim, adsk.fusion.SketchAngularDimension)


def _dir(line):
    a, b = line.startSketchPoint.geometry, line.endSketchPoint.geometry
    return geom.unit((b.x - a.x, b.y - a.y, b.z - a.z))


def _text_point(att):
    """A spot for the dimension text: just off the first entity."""
    g = None
    a = att[0]
    try:
        if hasattr(a, "startSketchPoint"):
            p, q = a.startSketchPoint.geometry, a.endSketchPoint.geometry
            g = adsk.core.Point3D.create((p.x + q.x) / 2 + 0.2, (p.y + q.y) / 2 + 0.2, 0)
        elif hasattr(a, "centerSketchPoint"):
            c = a.centerSketchPoint.geometry
            g = adsk.core.Point3D.create(c.x + a.radius + 0.2, c.y + 0.2, 0)
        else:
            c = a.geometry
            g = adsk.core.Point3D.create(c.x + 0.2, c.y + 0.2, 0)
    except Exception:
        g = adsk.core.Point3D.create(0, 0, 0)
    return g


def _sample_loop(loop, n=24):
    """A profile loop as a 2D polygon (sketch space)."""
    pts = []
    for pc in loop.profileCurves:
        ev = pc.sketchEntity.geometry.evaluator if pc.sketchEntity else pc.geometry.evaluator
        ok, t0, t1 = ev.getParameterExtents()
        ts = [t0 + (t1 - t0) * i / n for i in range(n)]
        ok, ps = ev.getPointsAtParameters(ts)
        if ok:
            pts += [(p.x, p.y) for p in ps]
    return pts


def _edge_mid(edge):
    try:
        ev = edge.evaluator
        ok, t0, t1 = ev.getParameterExtents()
        ok, p = ev.getPointAtParameter((t0 + t1) / 2)
        return (p.x, p.y, p.z) if ok else None
    except Exception:
        return None


def _in(coll, e):
    return any(coll.item(i) == e for i in range(coll.count))


def _plane_normal(entity):
    try:
        g = entity.geometry
        return geom.unit((g.normal.x, g.normal.y, g.normal.z))
    except Exception:
        return None


def _plane_origin(entity):
    try:
        g = entity.geometry
        return (g.origin.x, g.origin.y, g.origin.z)
    except Exception:
        return (0, 0, 0)


def _param_of(extent, attr):
    try:
        return getattr(extent, attr)
    except Exception:
        return None


BUILDERS = {
    "RefPlane": Rebuilder.ref_plane,
    "RefAxis": Rebuilder.ref_axis,
    "ProfileFeature": Rebuilder.sketch,
    "Extrusion": Rebuilder.extrude, "Boss": Rebuilder.extrude, "ICE": Rebuilder.extrude,
    "Cut": Rebuilder.cut,
    "Revolution": Rebuilder.revolve, "RevCut": Rebuilder.revcut,
    "Fillet": Rebuilder.fillet,
    "Chamfer": Rebuilder.chamfer,
    "HoleWzd": Rebuilder.hole,
    "LPattern": Rebuilder.linear_pattern,
    "CirPattern": Rebuilder.circular_pattern,
    "MirrorPattern": Rebuilder.mirror,
}


def load_json(path):
    """Load a swexport document (format check without importing swreader, which is not installed in Fusion)."""
    import json
    with open(path, encoding="utf-8") as f:
        doc = json.load(f)
    if doc.get("format") != "swexport":
        raise ValueError(f"{path} is not swexport output")
    if doc.get("format_version") != 1:
        raise ValueError(f"{path}: unsupported format_version {doc.get('format_version')}")
    return doc


# -- company profile (properties, materials) ---------------------------------------------------------------------

def load_profile(path):
    """The company profile (docs/PROFILE.md), or None."""
    import json
    import os
    if not path or not os.path.exists(path):
        return None
    with open(path, encoding="utf-8") as f:
        p = json.load(f)
    return p if p.get("format") == "swreader-company-profile" else None


def apply_profile(rb, profile, log):
    """Set part number, description and material from the SolidWorks properties as the company profile says, and
    keep every SolidWorks property as an attribute (group 'SolidWorks') so nothing is lost."""
    info = rb.doc.get("document") or {}
    props = {k: (v.get("value") or v.get("expression") or "") for k, v in (info.get("custom_properties") or {}).items()}
    cfg = info.get("active_configuration")
    for c in info.get("configurations") or []:
        if c.get("name") == cfg:
            props.update({k: (v.get("value") or v.get("expression") or "")
                          for k, v in (c.get("custom_properties") or {}).items()})
    comp = rb.root
    for k, v in props.items():
        try:
            comp.attributes.add("SolidWorks", k, str(v))
        except Exception as e:                                  # noqa: BLE001
            log(f"  attribute {k} not stored ({e})")
    if not profile:
        log("  no company profile: part number / description / material not mapped")
        return
    rules = profile.get("properties") or {}
    for k, rule in rules.items():
        if not isinstance(rule, dict) or k not in props or not props[k]:
            continue
        target = rule.get("fusion") or ""
        if target.startswith("component.partNumber"):
            comp.partNumber = props[k]
        elif target.startswith("component.description"):
            comp.description = props[k]
    mat_name = ((rb.doc.get("part") or {}).get("material") or {}).get("name")
    fusion_mat = (profile.get("materials") or {}).get(mat_name) if mat_name else None
    if mat_name and not fusion_mat:
        log(f"  material '{mat_name}' has no Fusion material in the profile (kept as attribute)")
    if fusion_mat:
        app = adsk.core.Application.get()
        mat = None
        for lib in app.materialLibraries:
            mat = lib.materials.itemByName(fusion_mat)
            if mat:
                break
        if mat is None:
            log(f"  Fusion material '{fusion_mat}' not found in any material library")
        else:
            for body in comp.bRepBodies:
                body.material = mat
            log(f"  material: {mat_name} -> {fusion_mat}")
