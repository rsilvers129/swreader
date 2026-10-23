// Document-level export (all types) plus part and assembly specifics.
using System;
using System.Collections.Generic;
using System.IO;

namespace SwExport
{
    public static class Document
    {
        public const int FormatVersion = 1;

        public static JObj Export(Ctx c)
        {
            var root = new JObj()
                .Add("format", "swexport")
                .Add("format_version", FormatVersion)
                .Add("exporter", new JObj()
                    .Add("name", "swexport").Add("version", Program.Version)
                    .Add("solidworks", Com.Str(Com.Try(c.App, "RevisionNumber")))
                    .Add("exported_utc", DateTime.UtcNow.ToString("o")))
                .Add("source", Source(c.Path))
                .Add("document", c.Section("document", () => Info(c)));

            switch (c.DocType)
            {
                case Sw.DocPart: root.Add("part", c.Section("part", () => Part(c))); break;
                case Sw.DocAssembly: root.Add("assembly", c.Section("assembly", () => Assembly(c))); break;
                case Sw.DocDrawing: root.Add("drawing", c.Section("drawing", () => Drawing.Export(c))); break;
            }
            return root;
        }

        static JObj Source(string path)
        {
            var fi = new FileInfo(path);
            return new JObj().Add("path", fi.FullName).Add("file", fi.Name).Add("bytes", fi.Length)
                             .Add("modified_utc", fi.LastWriteTimeUtc.ToString("o"));
        }

        public static string TypeName(int t) => t == Sw.DocPart ? "part" : t == Sw.DocAssembly ? "assembly" : t == Sw.DocDrawing ? "drawing" : "unknown";

        static JObj Info(Ctx c)
        {
            var o = new JObj()
                .Add("type", TypeName(c.DocType))
                .Add("title", Com.Str(Com.Try(c.Model, "GetTitle")))
                .Add("active_configuration", Com.Str(Com.Try(Com.Try(c.Model, "GetActiveConfiguration"), "Name")))
                .Add("units", Units(c))
                .Add("custom_properties", c.Section("custom properties", () => Properties(c, "")));
            if (c.DocType != Sw.DocDrawing)
            {
                o.Add("configurations", c.Section("configurations", () => Configurations(c)));
                o.Add("equations", c.Section("equations", () => Equations(c)));
            }
            return o;
        }

        static JObj Units(Ctx c)
        {
            var u = Com.Arr(Com.Try(c.Model, "GetUnits"));     // [linear unit, fraction base, denominator, decimals, round]
            var o = new JObj().Add("values", "SI: metres, radians, kilograms");
            if (u != null && u.Length >= 4)
            {
                var lin = Com.Int(u[0]);
                o.Add("length", Sw.Name(Sw.LengthUnits, lin) ?? Com.Str(lin)).Add("decimals", Com.Int(u[3]));
            }
            return o;
        }

        /// Custom properties of the document ("" ) or of one configuration: expression and evaluated value.
        public static JObj Properties(Ctx c, string configuration)
        {
            var cpm = Com.Try(c.Ext, "CustomPropertyManager", configuration);
            var names = Com.Strings(Com.Try(cpm, "GetNames"));
            if (names == null || names.Count == 0) return null;
            var o = new JObj();
            foreach (var n in names)
            {
                string expr = null, val = null;
                foreach (var (member, args, refs) in new (string, object[], bool[])[]
                {
                    ("Get6", new object[] { n, false, "", "", false, false }, new[] { false, false, true, true, true, true }),
                    ("Get5", new object[] { n, false, "", "", false }, new[] { false, false, true, true, true }),
                    ("Get4", new object[] { n, false, "", "" }, new[] { false, false, true, true }),
                })
                {
                    try { Com.CallRef(cpm, member, args, refs); expr = Com.Str(args[2]); val = Com.Str(args[3]); break; }
                    catch { }
                }
                var p = new JObj().Add("expression", expr);
                if (val != expr) p.Add("value", val);
                o.Add(n, p);
            }
            return o;
        }

        static JArr Configurations(Ctx c)
        {
            var names = Com.Strings(Com.Try(c.Model, "GetConfigurationNames"));
            if (names == null) return null;
            var r = new JArr();
            foreach (var n in names)
            {
                var cfg = Com.Try(c.Model, "GetConfigurationByName", n);
                r.Add(new JObj()
                    .Add("name", n)
                    .Add("description", Empty(Com.Str(Com.Try(cfg, "Description"))))
                    .Add("comment", Empty(Com.Str(Com.Try(cfg, "Comment"))))
                    .Add("derived", Com.Bool(Com.Try(cfg, "IsDerived")))
                    .Add("parent", Com.Str(Com.Try(Com.Try(cfg, "GetParent"), "Name")))
                    .Add("custom_properties", c.Section("configuration properties " + n, () => Properties(c, n))));
            }
            return r;
        }

        static JArr Equations(Ctx c)
        {
            var m = Com.Try(c.Model, "GetEquationMgr");
            var n = Com.Int(Com.Try(m, "GetCount"));
            if (!n.HasValue || n.Value == 0) return null;
            var r = new JArr();
            for (int i = 0; i < n.Value; i++)
                r.Add(new JObj()
                    .Add("equation", Com.Str(Com.Try(m, "Equation", i)))
                    .Add("value", Com.Dbl(Com.Try(m, "Value", i)))
                    .Add("global_variable", Com.Bool(Com.Try(m, "GlobalVariable", i)))
                    .Add("suppressed", Com.Bool(Com.Try(m, "Suppression", i))));
            return r;
        }

        static string Empty(string s) => string.IsNullOrEmpty(s) ? null : s;

        // -- part ---------------------------------------------------------------------------------------------------

        static JObj Part(Ctx c)
        {
            var cfg = Com.Str(Com.Try(Com.Try(c.Model, "GetActiveConfiguration"), "Name")) ?? "";
            var o = new JObj();
            var matArgs = new object[] { cfg, "" };
            try
            {
                var mat = Com.Str(Com.CallRef(c.Model, "GetMaterialPropertyName2", matArgs, new[] { false, true }));
                if (!string.IsNullOrEmpty(mat)) o.Add("material", new JObj().Add("name", mat).Add("database", Com.Str(matArgs[1])));
            }
            catch (Exception e) { c.Error("material", e); }

            o.Add("mass", c.Section("mass", () => Mass(c)));
            o.Add("bounding_box", Com.Doubles(Com.Try(c.Model, "GetPartBox", true)));
            o.Add("bodies", c.Section("bodies", () => Bodies(c)));
            o.Add("features", c.Section("features", () => Features.Tree(c)));
            return o;
        }

        static JObj Mass(Ctx c)
        {
            var mp = Com.Try(c.Ext, "CreateMassProperty");
            if (mp == null) return null;
            Com.TrySet(mp, "UseSystemUnits", true);
            return new JObj()
                .Add("mass", Com.Dbl(Com.Try(mp, "Mass")))
                .Add("volume", Com.Dbl(Com.Try(mp, "Volume")))
                .Add("surface_area", Com.Dbl(Com.Try(mp, "SurfaceArea")))
                .Add("density", Com.Dbl(Com.Try(mp, "Density")))
                .Add("center_of_mass", Com.Doubles(Com.Try(mp, "CenterOfMass")))
                .Add("moments_of_inertia", Com.Doubles(Com.Try(mp, "GetMomentOfInertia", 0)));   // about the centre of mass
        }

        static JArr Bodies(Ctx c)
        {
            var bodies = Com.Arr(Com.Try(c.Model, "GetBodies2", 0, false));      // solid bodies, visible and hidden
            if (bodies == null) return null;
            var r = new JArr();
            foreach (var b in bodies)
                r.Add(new JObj()
                    .Add("name", Com.Str(Com.Try(b, "Name")))
                    .Add("faces", Com.Int(Com.Try(b, "GetFaceCount")))
                    .Add("edges", Com.Int(Com.Try(b, "GetEdgeCount")))
                    .Add("box", Com.Doubles(Com.Try(b, "GetBodyBox"))));
            return r;
        }

        // -- assembly -----------------------------------------------------------------------------------------------

        static JObj Assembly(Ctx c)
        {
            var root = Com.Try(Com.Try(Com.Try(c.Model, "ConfigurationManager"), "ActiveConfiguration"), "GetRootComponent3", true);
            var o = new JObj();
            var comps = new JArr();
            var kids = Com.Arr(Com.Try(root, "GetChildren"));
            if (kids != null) foreach (var k in kids) comps.Add(Component(c, k, 0));
            o.Add("components", comps);
            o.Add("mates", c.Section("mates", () => Mates(c)));
            o.Add("mass", c.Section("mass", () => Mass(c)));
            o.Add("features", c.Section("features", () => AssemblyFeatures(c)));
            return o;
        }

        static JObj Component(Ctx c, object comp, int depth)
        {
            var o = new JObj()
                .Add("name", Com.Str(Com.Try(comp, "Name2")))
                .Add("path", Com.Str(Com.Try(comp, "GetPathName")))
                .Add("configuration", Com.Str(Com.Try(comp, "ReferencedConfiguration")))
                .Add("suppressed", Com.Bool(Com.Try(comp, "IsSuppressed")))
                .Add("hidden", Com.Bool(Com.Try(comp, "IsHidden", true)))
                .Add("fixed", Com.Bool(Com.Try(comp, "IsFixed")))
                .Add("virtual", Com.Bool(Com.Try(comp, "IsVirtual")))
                .Add("envelope", Com.Bool(Com.Try(comp, "IsEnvelope")))
                .Add("exclude_from_bom", Com.Bool(Com.Try(comp, "ExcludeFromBOM")))
                .Add("transform", Geometry.Transform(Com.Try(comp, "Transform2")));
            if (depth < 32)
            {
                var kids = Com.Arr(Com.Try(comp, "GetChildren"));
                if (kids != null && kids.Length > 0)
                {
                    var a = new JArr();
                    foreach (var k in kids) a.Add(Component(c, k, depth + 1));
                    o.Add("children", a);
                }
            }
            return o;
        }

        static JArr Mates(Ctx c)
        {
            var r = new JArr();
            for (var f = Com.Try(c.Model, "FirstFeature"); f != null; f = Com.Try(f, "GetNextFeature"))
            {
                if (Com.Str(Com.Try(f, "GetTypeName2")) != "MateGroup") continue;
                foreach (var m in Features.SubFeatures(f))
                {
                    var spec = Com.Try(m, "GetSpecificFeature2");
                    var t = Com.Int(Com.Try(spec, "Type"));
                    var o = new JObj()
                        .Add("name", Com.Str(Com.Try(m, "Name")))
                        .Add("feature_type", Com.Str(Com.Try(m, "GetTypeName2")))
                        .Add("type", t).Add("kind", Sw.Name(Sw.MateKinds, t))
                        .Add("alignment", Com.Int(Com.Try(spec, "Alignment")))
                        .Add("suppressed", Com.Bool(Com.Try(m, "IsSuppressed")))
                        .Add("dimensions", Dimensions.OfFeature(c, m));
                    var n = Com.Int(Com.Try(spec, "GetMateEntityCount"));
                    if (n.HasValue && n.Value > 0)
                    {
                        var ents = new JArr();
                        for (int i = 0; i < n.Value; i++)
                        {
                            var me = Com.Try(spec, "MateEntity", i);
                            ents.Add(new JObj()
                                .Add("component", Com.Str(Com.Try(Com.Try(me, "ReferenceComponent"), "Name2")))
                                .Add("reference_type", Com.Int(Com.Try(me, "ReferenceType2")))
                                .Add("params", Com.Doubles(Com.Try(me, "EntityParams")))
                                .Add("entity", Geometry.Entity(Com.Try(me, "Reference"))));
                        }
                        o.Add("entities", ents);
                    }
                    r.Add(o);
                }
            }
            return r;
        }

        /// Assembly-level features (planes, sketches, cuts, patterns) - components and mates are exported separately.
        static JArr AssemblyFeatures(Ctx c)
        {
            var r = new JArr();
            var owner = new Dictionary<string, string>();
            int index = 0;
            for (var f = Com.Try(c.Model, "FirstFeature"); f != null; f = Com.Try(f, "GetNextFeature"), index++)
            {
                var t = Com.Str(Com.Try(f, "GetTypeName2"));
                if (t == "Reference" || t == "MateGroup") continue;
                var rec = c.Section("assembly feature", () => Features.Feature(c, f, index, owner));
                if (rec != null) r.Add(rec);
            }
            return r;
        }
    }
}
