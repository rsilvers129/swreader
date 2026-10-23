// Geometric descriptions of B-rep entities (edges, faces, vertices), so a selection made in SolidWorks (a filleted
// edge, a sketch face, an up-to surface) can be found again by position in another CAD system.
// All coordinates are model space, metres.
namespace SwExport
{
    public static class Geometry
    {
        // swSurfaceTypes_e
        static readonly System.Collections.Generic.Dictionary<int, string> SurfaceKinds =
            new System.Collections.Generic.Dictionary<int, string>
            {
                { 4001, "plane" }, { 4002, "cylinder" }, { 4003, "cone" }, { 4004, "sphere" }, { 4005, "torus" },
                { 4006, "bspline" }, { 4007, "blend" }, { 4008, "offset" }, { 4009, "extrusion" }, { 4010, "revolution" },
            };

        /// Describe a selected/attached entity: edge, face, vertex, sketch segment/point, plane/axis feature.
        public static JObj Entity(object e)
        {
            if (e == null) return null;
            // sketch entities first: they carry a sketch-local ID
            var id = Com.Arr(Com.Try(e, "GetID"));
            var segType = Com.Int(Com.Try(e, "GetType"));
            if (id != null && id.Length == 2 && Com.Try(e, "GetSketch") != null)
            {
                bool isPoint = Com.Try(e, "X") != null && Com.Try(e, "GetLength") == null;
                return new JObj().Add("kind", isPoint ? "sketch_point" : "sketch_segment").Add("id", SketchId(id));
            }
            var edgeCurve = Com.Try(e, "GetCurve");
            if (edgeCurve != null && Com.Try(e, "GetCurveParams2") != null) return Edge(e);
            if (Com.Try(e, "GetSurface") != null) return Face(e);
            var pt = Com.Doubles(Com.Try(e, "GetPoint"));
            if (pt != null && pt.Count >= 3) return new JObj().Add("kind", "vertex").Add("point", pt.GetRange(0, 3));
            var name = Com.Str(Com.Try(e, "Name"));
            var typeName = Com.Str(Com.Try(e, "GetTypeName2"));
            if (typeName != null) return new JObj().Add("kind", "feature").Add("name", name).Add("type", typeName);
            return new JObj().Add("kind", "unknown");
        }

        public static string SketchId(object[] id) =>
            id == null || id.Length < 2 ? null : Com.Str(id[0]) + "-" + Com.Str(id[1]);

        public static JObj Edge(object edge)
        {
            var o = new JObj().Add("kind", "edge");
            var p = Com.Doubles(Com.Try(edge, "GetCurveParams2"));     // start xyz, end xyz, t0, t1, ...
            var curve = Com.Try(edge, "GetCurve");
            if (p != null && p.Count >= 8)
            {
                o.Add("start", p.GetRange(0, 3)).Add("end", p.GetRange(3, 3));
                var mid = Com.Doubles(Com.Try(curve, "Evaluate2", (p[6] + p[7]) / 2, 0));
                if (mid != null && mid.Count >= 3) o.Add("mid", mid.GetRange(0, 3));
            }
            if (Com.Bool(Com.Try(curve, "IsLine")) == true) o.Add("curve", "line");
            else if (Com.Bool(Com.Try(curve, "IsCircle")) == true)
            {
                var c = Com.Doubles(Com.Try(curve, "CircleParams"));     // center xyz, axis xyz, radius
                o.Add("curve", "circle");
                if (c != null && c.Count >= 7) o.Add("center", c.GetRange(0, 3)).Add("axis", c.GetRange(3, 3)).Add("radius", c[6]);
            }
            else if (Com.Bool(Com.Try(curve, "IsEllipse")) == true) o.Add("curve", "ellipse");
            else o.Add("curve", "other");
            return o;
        }

        public static JObj Face(object face)
        {
            var o = new JObj().Add("kind", "face");
            var surf = Com.Try(face, "GetSurface");
            var ident = Com.Int(Com.Try(surf, "Identity"));
            o.Add("surface", Sw.Name(SurfaceKinds, ident) ?? Com.Str(ident));
            var box = Com.Doubles(Com.Try(face, "GetBox"));
            if (box != null && box.Count >= 6)
            {
                o.Add("box", box);
                var c = new[] { (box[0] + box[3]) / 2, (box[1] + box[4]) / 2, (box[2] + box[5]) / 2 };
                var on = Com.Doubles(Com.Try(face, "GetClosestPointOn", c[0], c[1], c[2]));
                if (on != null && on.Count >= 3) o.Add("point", on.GetRange(0, 3));
            }
            if (ident == 4001)
            {
                var n = Com.Doubles(Com.Try(face, "Normal"));
                if (n != null && n.Count >= 3) o.Add("normal", n.GetRange(0, 3));
            }
            else if (ident == 4002)
            {
                var cp = Com.Doubles(Com.Try(surf, "CylinderParams"));  // origin xyz, axis xyz, radius
                if (cp != null && cp.Count >= 7) o.Add("axis_origin", cp.GetRange(0, 3)).Add("axis", cp.GetRange(3, 3)).Add("radius", cp[6]);
            }
            o.Add("area", Com.Dbl(Com.Try(face, "GetArea")));
            return o;
        }

        public static JArr Transform(object mathTransform)
        {
            var a = Com.Doubles(Com.Try(mathTransform, "ArrayData"));
            return a == null ? null : new JArr(a.ConvertAll(x => (object)x));
        }
    }
}
