// Feature tree export: every feature in history order with its type, state, relations, dimensions, type-specific
// parameters, and the B-rep entities it references (described geometrically so another CAD system can find them).
using System;
using System.Collections.Generic;

namespace SwExport
{
    public static class Features
    {
        public static JArr Tree(Ctx c)
        {
            var list = new JArr();
            var owner = new Dictionary<string, string>();          // sub-feature name -> owning feature name
            var feats = new List<object>();
            for (var f = Com.Try(c.Model, "FirstFeature"); f != null; f = Com.Try(f, "GetNextFeature")) feats.Add(f);
            foreach (var f in feats)
            {
                var name = Com.Str(Com.Try(f, "Name"));
                foreach (var s in SubFeatures(f)) { var sn = Com.Str(Com.Try(s, "Name")); if (sn != null && !owner.ContainsKey(sn)) owner[sn] = name; }
            }
            int index = 0;
            foreach (var f in feats)
            {
                var name = Com.Str(Com.Try(f, "Name"));
                var rec = c.Section("feature " + name, () => Feature(c, f, index, owner));
                if (rec != null) list.Add(rec);
                index++;
            }
            return list;
        }

        public static List<object> SubFeatures(object f)
        {
            var r = new List<object>();
            for (var s = Com.Try(f, "GetFirstSubFeature"); s != null; s = Com.Try(s, "GetNextSubFeature")) r.Add(s);
            return r;
        }

        static JArr Names(object v)
        {
            var a = Com.Arr(v);
            if (a == null) return null;
            var r = new JArr();
            foreach (var x in a) { var n = Com.Str(Com.Try(x, "Name")); if (n != null) r.Add(n); }
            return r;
        }

        public static JObj Feature(Ctx c, object f, int index, Dictionary<string, string> owner)
        {
            var name = Com.Str(Com.Try(f, "Name"));
            var type = Com.Str(Com.Try(f, "GetTypeName2"));
            var o = new JObj()
                .Add("index", index)
                .Add("name", name)
                .Add("type", type)
                .Add("id", Com.Int(Com.Try(f, "GetID")))
                .Add("suppressed", Suppressed(f))
                .Add("description", Empty(Com.Str(Com.Try(f, "Description"))))
                .Add("created", Com.Str(Com.Try(f, "DateCreated")))
                .Add("modified", Com.Str(Com.Try(f, "DateModified")))
                .Add("created_by", Empty(Com.Str(Com.Try(f, "CreatedBy"))))
                .Add("owner", owner.TryGetValue(name ?? "", out var ow) ? ow : null)
                .Add("parents", Names(Com.Try(f, "GetParents")))
                .Add("children", Names(Com.Try(f, "GetChildren")));

            var subs = new JArr();
            foreach (var s in SubFeatures(f)) subs.Add(Com.Str(Com.Try(s, "Name")));
            if (subs.Count > 0) o.Add("sub_features", subs);

            o.Add("dimensions", c.Section("dimensions " + name, () => Dimensions.OfFeature(c, f)));

            if (type == "ProfileFeature" || type == "3DProfileFeature")
                o.Add("sketch", c.Section("sketch " + name, () => Sketches.Sketch(c, f)));
            else if (type != null && type != "Reference")
                o.Add("definition", c.Section("definition " + name, () => Definitions.Of(c, f, type)));

            if (Definitions.WantsResultFaces(type))
                o.Add("result_faces", c.Section("faces " + name, () => ResultFaces(f)));
            return o;
        }

        static string Empty(string s) => string.IsNullOrEmpty(s) ? null : s;

        static object Suppressed(object f)
        {
            var a = Com.Arr(Com.Try(f, "IsSuppressed2", 1, null));        // swThisConfiguration
            if (a != null && a.Length > 0) return Com.Bool(a[0]);
            return Com.Bool(Com.Try(f, "IsSuppressed"));
        }

        /// Faces a feature created, described geometrically (capped; a big feature can have thousands).
        static JArr ResultFaces(object f)
        {
            var faces = Com.Arr(Com.Try(f, "GetFaces"));
            if (faces == null) return null;
            var r = new JArr();
            foreach (var face in faces)
            {
                if (r.Count >= 200) break;
                r.Add(Geometry.Face(face));
            }
            return r;
        }
    }

    public static class Dimensions
    {
        public static JArr OfFeature(Ctx c, object f)
        {
            var r = new JArr();
            for (var dd = Com.Try(f, "GetFirstDisplayDimension"); dd != null; dd = Com.Try(f, "GetNextDisplayDimension", dd))
            {
                var d = Of(c, dd, false);
                if (d != null) r.Add(d);
            }
            return r.Count > 0 ? r : null;
        }

        /// A display dimension: name, value (metres / radians), tolerance, text, and what it is attached to.
        public static JObj Of(Ctx c, object dd, bool inDrawing)
        {
            var dim = Com.Try(dd, "GetDimension2", 0);
            var o = new JObj()
                .Add("name", Com.Str(Com.Try(dim, "Name")))
                .Add("full_name", Com.Str(Com.Try(dim, "FullName")))
                .Add("value", Com.Dbl(Com.Try(dim, "SystemValue")))
                .Add("display_value", Com.Dbl(Com.Try(dim, "Value")))
                .Add("dimension_type", Com.Int(Com.Try(dd, "Type2")))
                .Add("driven_state", Com.Int(Com.Try(dim, "DrivenState")))
                .Add("read_only", Com.Bool(Com.Try(dim, "ReadOnly")));

            var tol = Com.Try(dim, "Tolerance");
            if (tol != null)
            {
                var tt = Com.Int(Com.Try(tol, "Type"));
                if (tt.HasValue && tt.Value != 0)
                {
                    var t = new JObj().Add("type", tt).Add("kind", Sw.Name(Sw.ToleranceKinds, tt))
                        .Add("min", Com.Dbl(Com.Try(tol, "GetMinValue")))
                        .Add("max", Com.Dbl(Com.Try(tol, "GetMaxValue")))
                        .Add("hole_fit", Com.Str(Com.Try(tol, "GetHoleFitValue")))
                        .Add("shaft_fit", Com.Str(Com.Try(tol, "GetShaftFitValue")));
                    o.Add("tolerance", t);
                }
            }

            var text = new JObj();
            string[] parts = { null, "all", "prefix", "suffix", "callout_above", "callout_below" };
            for (int i = 1; i <= 5; i++)
            {
                var s = Com.Str(Com.Try(dd, "GetText", i));
                if (!string.IsNullOrEmpty(s)) text.Add(parts[i], s);
            }
            if (text.Count > 0) o.Add("text", text);

            var ann = Com.Try(dd, "GetAnnotation");
            var ents = Com.Arr(Com.Try(ann, "GetAttachedEntities3"));
            if (ents != null && ents.Length > 0)
            {
                var a = new JArr();
                foreach (var e in ents) a.Add(Geometry.Entity(e));
                o.Add("attached", a);
            }
            if (inDrawing)
            {
                var pos = Com.Doubles(Com.Try(ann, "GetPosition"));
                if (pos != null) o.Add("position", pos);
            }
            if (c.Opt.AllConfigurations && c.DocType != Sw.DocDrawing)
                o.Add("by_configuration", PerConfiguration(c, dim));
            return o;
        }

        static JObj PerConfiguration(Ctx c, object dim)
        {
            var names = Com.Arr(Com.Try(c.Model, "GetConfigurationNames"));
            if (names == null || names.Length < 2) return null;
            var vals = Com.Arr(Com.Try(dim, "GetSystemValue3", 3, names));   // swSpecifyConfiguration
            if (vals == null || vals.Length != names.Length) return null;
            var o = new JObj();
            for (int i = 0; i < names.Length; i++) o.Add(Com.Str(names[i]), Com.Dbl(vals[i]));
            return o;
        }
    }
}
