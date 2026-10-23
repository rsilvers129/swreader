// Sketch export: placement, points, segments with geometry, relations. Coordinates are sketch space, metres
// (z = 0 for 2D sketches); "model_to_sketch" is the SolidWorks MathTransform array (rotation 3x3, translation 3,
// scale 1, 3 unused) that maps model coordinates into the sketch.
namespace SwExport
{
    public static class Sketches
    {
        public static JObj Sketch(Ctx c, object feat)
        {
            var sk = Com.Get(feat, "GetSpecificFeature2");
            var o = new JObj()
                .Add("is_3d", Com.Bool(Com.Try(sk, "Is3D")))
                .Add("model_to_sketch", Geometry.Transform(Com.Try(sk, "ModelToSketchTransform")));

            var refArgs = new object[] { 0 };
            try
            {
                var plane = Com.CallRef(sk, "GetReferenceEntity", refArgs, new[] { true });
                if (plane != null) o.Add("plane", Geometry.Entity(plane)).Add("plane_entity_type", Com.Int(refArgs[0]));
            }
            catch { }

            var points = new JArr();
            var pts = Com.Arr(Com.Try(sk, "GetSketchPoints2"));
            if (pts != null)
                foreach (var p in pts) points.Add(Point(p));
            o.Add("points", points);

            var segs = new JArr();
            var ss = Com.Arr(Com.Try(sk, "GetSketchSegments"));
            if (ss != null)
                foreach (var s in ss) { var j = c.Section("sketch segment", () => Segment(s)); if (j != null) segs.Add(j); }
            o.Add("segments", segs);

            o.Add("relations", c.Section("sketch relations", () => Relations(sk)));
            return o;
        }

        public static JObj Point(object p)
        {
            return new JObj()
                .Add("id", Geometry.SketchId(Com.Arr(Com.Try(p, "GetID"))))
                .Add("xyz", new JArr { Com.Dbl(Com.Try(p, "X")), Com.Dbl(Com.Try(p, "Y")), Com.Dbl(Com.Try(p, "Z")) });
        }

        static JObj Segment(object s)
        {
            var t = Com.Int(Com.Try(s, "GetType"));
            var o = new JObj()
                .Add("id", Geometry.SketchId(Com.Arr(Com.Try(s, "GetID"))))
                .Add("kind", Sw.Name(Sw.SegmentKinds, t) ?? "unknown")
                .Add("type", t)
                .Add("construction", Com.Bool(Com.Try(s, "ConstructionGeometry")))
                .Add("length", Com.Dbl(Com.Try(s, "GetLength")));
            switch (t)
            {
                case Sw.SegLine:
                    o.Add("start", Ref(s, "GetStartPoint2")).Add("end", Ref(s, "GetEndPoint2"));
                    break;
                case Sw.SegArc:
                    o.Add("center", Ref(s, "GetCenterPoint2")).Add("start", Ref(s, "GetStartPoint2")).Add("end", Ref(s, "GetEndPoint2"))
                     .Add("radius", Com.Dbl(Com.Try(s, "GetRadius")))
                     .Add("circle", Com.Bool(Com.Try(s, "IsCircle")))
                     .Add("direction", Com.Int(Com.Try(s, "GetRotationDir")));      // 1 counter-clockwise, -1 clockwise
                    break;
                case Sw.SegEllipse:
                    o.Add("center", Ref(s, "GetCenterPoint2")).Add("major", Ref(s, "GetMajorPoint2")).Add("minor", Ref(s, "GetMinorPoint2"))
                     .Add("start", Ref(s, "GetStartPoint2")).Add("end", Ref(s, "GetEndPoint2"));
                    break;
                case Sw.SegSpline:
                    var sp = Com.Arr(Com.Try(s, "GetPoints2"));
                    if (sp != null) { var a = new JArr(); foreach (var p in sp) a.Add(Point(p)); o.Add("points", a); }
                    o.Add("params", Com.Doubles(Com.Try(s, "GetSplineParams")));
                    break;
                case Sw.SegText:
                    o.Add("text", Com.Str(Com.Try(s, "Text")));
                    break;
                case Sw.SegParabola:
                    o.Add("focus", Ref(s, "GetFocalPoint2")).Add("apex", Ref(s, "GetApexPoint2"))
                     .Add("start", Ref(s, "GetStartPoint2")).Add("end", Ref(s, "GetEndPoint2"));
                    break;
            }
            return o;
        }

        static JObj Ref(object seg, string member)
        {
            var p = Com.Try(seg, member);
            return p == null ? null : Point(p);
        }

        static JArr Relations(object sk)
        {
            var rm = Com.Try(sk, "RelationManager");
            var rels = Com.Arr(Com.Try(rm, "GetRelations", 0));        // swAll
            if (rels == null) return null;
            var r = new JArr();
            foreach (var rel in rels)
            {
                var t = Com.Int(Com.Try(rel, "GetRelationType"));
                var o = new JObj().Add("type", t).Add("kind", Sw.Name(Sw.RelationKinds, t));
                var ents = Com.Arr(Com.Try(rel, "GetEntities"));
                if (ents != null) { var a = new JArr(); foreach (var e in ents) a.Add(Geometry.Entity(e)); o.Add("entities", a); }
                o.Add("entity_types", Definitions.Simple(Com.Try(rel, "GetEntitiesType")));
                r.Add(o);
            }
            return r;
        }
    }
}
