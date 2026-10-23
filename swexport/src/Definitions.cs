// Type-specific feature parameters, read from the feature's definition object (IExtrudeFeatureData2,
// IRevolveFeatureData2, ISimpleFilletFeatureData2 ...). Members are probed by name: one that does not exist in this
// SolidWorks version is simply absent from the JSON. Driving values are also in the feature's "dimensions".
using System;
using System.Collections.Generic;

namespace SwExport
{
    public static class Definitions
    {
        // (json key, member, args)
        sealed class P
        {
            public string Key, Member; public object[] Args;
            public P(string key, string member, params object[] args) { Key = key; Member = member; Args = args; }
        }

        static readonly P[] Extrude =
        {
            new P("end_condition", "GetEndCondition", true), new P("end_condition_2", "GetEndCondition", false),
            new P("depth", "GetDepth", true), new P("depth_2", "GetDepth", false),
            new P("draft_angle", "GetDraftAngle", true), new P("draft_angle_2", "GetDraftAngle", false),
            new P("draft_outward", "GetDraftOutward", true), new P("draft_while_extruding", "GetDraftWhileExtruding", true),
            new P("offset_reverse", "GetReverseOffset", true), new P("wall_thickness", "GetWallThickness", true),
            new P("both_directions", "BothDirections"), new P("reverse_direction", "ReverseDirection"),
            new P("flip_side_to_cut", "FlipSideToCut"), new P("merge", "Merge"), new P("normal_cut", "NormalCut"),
            new P("is_boss", "IsBossFeature"), new P("is_thin", "IsThinFeature"), new P("thin_type", "ThinWallType"),
            new P("from_type", "FromType"), new P("from_offset", "FromOffsetDistance"),
            new P("auto_select_bodies", "AutoSelect"),
        };

        static readonly P[] Revolve =
        {
            new P("type", "Type"), new P("angle", "GetRevolutionAngle", true), new P("angle_2", "GetRevolutionAngle", false),
            new P("reverse_direction", "ReverseDirection"), new P("merge", "Merge"), new P("is_boss", "IsBossFeature"),
            new P("is_thin", "IsThinFeature"), new P("wall_thickness", "GetWallThickness", true),
        };

        static readonly P[] Fillet =
        {
            new P("type", "Type"), new P("radius", "DefaultRadius"), new P("conic_type", "ConicTypeForCrossSectionProfile"),
            new P("propagate_tangent", "PropagateToTangentFaces"), new P("item_count", "FilletItemsCount"),
            new P("overflow", "OverflowType"),
        };

        static readonly P[] Chamfer =
        {
            new P("type", "Type"), new P("angle", "EdgeChamferAngle"),
            new P("distance", "GetEdgeChamferDistance", 0), new P("distance_2", "GetEdgeChamferDistance", 1),
            new P("flip_direction", "FlipDirection"), new P("propagate_tangent", "PropagateFeatureToParts"),
        };

        static readonly P[] Hole =
        {
            new P("type", "Type"), new P("standard", "Standard"), new P("fastener_type", "FastenerType"),
            new P("fastener_size", "FastenerSize"), new P("end_condition", "EndCondition"), new P("depth", "Depth"),
            new P("diameter", "Diameter"), new P("drill_angle", "DrillAngle"),
            new P("thread_class", "ThreadClass"), new P("thread_diameter", "ThreadDiameter"),
            new P("thread_depth", "ThreadDepth"), new P("thread_end_condition", "ThreadEndCondition"),
            new P("tap_drill_diameter", "TapDrillDiameter"), new P("tap_drill_depth", "TapDrillDepth"),
            new P("counterbore_diameter", "CounterBoreDiameter"), new P("counterbore_depth", "CounterBoreDepth"),
            new P("countersink_diameter", "CounterSinkDiameter"), new P("countersink_angle", "CounterSinkAngle"),
            new P("near_countersink_diameter", "NearCounterSinkDiameter"), new P("near_countersink_angle", "NearCounterSinkAngle"),
            new P("far_countersink_diameter", "FarCounterSinkDiameter"), new P("far_countersink_angle", "FarCounterSinkAngle"),
            new P("head_clearance", "HeadClearance"), new P("cosmetic_thread_type", "CosmeticThreadType"),
        };

        static readonly P[] LinearPattern =
        {
            new P("count_1", "D1TotalInstances"), new P("spacing_1", "D1Spacing"), new P("reverse_1", "D1ReverseDirection"),
            new P("count_2", "D2TotalInstances"), new P("spacing_2", "D2Spacing"), new P("reverse_2", "D2ReverseDirection"),
            new P("seed_only_2", "D2PatternSeedOnly"), new P("geometry_pattern", "GeometryPattern"),
            new P("vary_sketch", "VarySketch"),
        };

        static readonly P[] CircularPattern =
        {
            new P("count", "TotalInstances"), new P("spacing", "Spacing"), new P("equal_spacing", "EqualSpacing"),
            new P("reverse", "ReverseDirection"), new P("geometry_pattern", "GeometryPattern"),
        };

        static readonly P[] Mirror = { new P("geometry_pattern", "GeometryPattern") };
        static readonly P[] Shell = { new P("thickness", "Thickness"), new P("outward", "Outward") };
        static readonly P[] Draft = { new P("type", "Type"), new P("angle", "Angle"), new P("reverse", "ReverseDirection") };
        static readonly P[] Helix =
        {
            new P("defined_by", "DefinedBy"), new P("height", "Height"), new P("pitch", "Pitch"),
            new P("revolutions", "Revolution"), new P("start_angle", "StartingAngle"), new P("clockwise", "Clockwise"),
            new P("reverse", "ReverseDirection"), new P("taper_angle", "TaperAngle"), new P("taper_outward", "TaperOutward"),
        };
        static readonly P[] RefPlane = { new P("type", "Type"), new P("distance", "Distance"), new P("angle", "Angle"), new P("reverse", "ReversedReferenceDirection", 0) };
        static readonly P[] CosmeticThread =
        {
            new P("diameter", "Diameter"), new P("length", "Length"), new P("end_condition", "EndCondition"),
            new P("standard", "Standard"), new P("size", "Size"), new P("callout", "ThreadCallout"),
            new P("thread_class", "ThreadClass"), new P("apply_thread", "ApplyThread"),
        };
        static readonly P[] Sweep = { new P("twist_type", "TwistControlType"), new P("twist_angle", "TwistAngle"), new P("merge", "Merge"), new P("is_boss", "IsBossFeature"), new P("is_thin", "IsThinFeature") };
        static readonly P[] Loft = { new P("closed", "Close"), new P("merge", "Merge"), new P("is_boss", "IsBossFeature"), new P("is_thin", "IsThinFeature") };

        static P[] TableFor(string t)
        {
            switch (t)
            {
                case "Extrusion": case "Cut": case "Boss": case "BossThin": case "CutThin": case "ExtrusionThin":
                case "ICE": case "SurfExtrude": case "SurfCut": return Extrude;
                case "Revolution": case "RevCut": case "RevolutionThin": case "RevCutThin": case "SurfRevolve": return Revolve;
                case "Fillet": case "VarFillet": case "FaceFillet": return Fillet;
                case "Chamfer": return Chamfer;
                case "HoleWzd": case "AdvHoleWzd": return Hole;
                case "LPattern": return LinearPattern;
                case "CirPattern": return CircularPattern;
                case "MirrorPattern": case "MirrorSolid": case "MirrorStock": return Mirror;
                case "Shell": return Shell;
                case "Draft": case "DraftXpert": return Draft;
                case "Helix": return Helix;
                case "RefPlane": return RefPlane;
                case "CosmeticThread": return CosmeticThread;
                case "Sweep": case "SweepCut": case "SweepThread": return Sweep;
                case "Blend": case "BlendCut": return Loft;
                default: return null;
            }
        }

        public static bool WantsResultFaces(string type) =>
            type == "Fillet" || type == "VarFillet" || type == "Chamfer" || type == "Shell" || type == "Draft" ||
            type == "HoleWzd" || type == "AdvHoleWzd";

        public static JObj Of(Ctx c, object feat, string type)
        {
            var o = new JObj();
            var spec = Com.Try(feat, "GetSpecificFeature2");
            if (type == "RefPlane")
                o.Add("transform", Geometry.Transform(Com.Try(spec, "Transform")));
            else if (type == "RefAxis")
                o.Add("axis", Com.Doubles(Com.Try(spec, "GetRefAxisParams")));
            else if (type == "RefPoint")
                o.Add("point", Com.Doubles(Com.Try(Com.Try(spec, "GetRefPoint"), "ArrayData")));
            else if (type == "CoordSys")
                o.Add("transform", Geometry.Transform(Com.Try(spec, "Transform")));

            var table = TableFor(type);
            if (table == null) return o.Count > 0 ? o : null;

            var def = Com.Try(feat, "GetDefinition");
            if (def == null) return o.Count > 0 ? o : null;
            foreach (var p in table) o.Add(p.Key, Simple(Com.Try(def, p.Member, p.Args)));

            // selections need AccessSelections; always released again (the document is read-only anyway)
            bool access = Com.Bool(Com.Try(def, "AccessSelections", c.Model, null)) == true;
            try { o.Add("selections", Selections(def, type)); }
            finally { if (access) Com.Try(def, "ReleaseSelectionAccess"); }
            return o;
        }

        static JObj Selections(object def, string type)
        {
            var s = new JObj();
            switch (type)
            {
                case "Revolution": case "RevCut": case "RevolutionThin": case "RevCutThin": case "SurfRevolve":
                    s.Add("axis", Geometry.Entity(Com.Try(def, "Axis")));
                    break;
                case "Extrusion": case "Cut": case "Boss": case "BossThin": case "CutThin": case "ExtrusionThin": case "ICE":
                    s.Add("end_reference", Geometry.Entity(Com.Try(def, "GetEndConditionReference", true)));
                    s.Add("end_reference_2", Geometry.Entity(Com.Try(def, "GetEndConditionReference", false)));
                    s.Add("direction", Geometry.Entity(Com.Try(def, "Direction")));
                    break;
                case "Fillet": case "VarFillet":
                    s.Add("items", Items(def, "FilletItemsCount", "GetFilletItemAtIndex"));
                    break;
                case "Chamfer":
                    s.Add("items", List(Com.Try(def, "GetEdges")) ?? Items(def, "GetEntitiesToChamferCount", "GetEntitiesToChamfer"));
                    break;
                case "LPattern":
                    s.Add("direction_1", Geometry.Entity(Com.Try(def, "D1Axis")));
                    s.Add("direction_2", Geometry.Entity(Com.Try(def, "D2Axis")));
                    s.Add("features", FeatureNames(Com.Try(def, "PatternFeatureArray")));
                    break;
                case "CirPattern":
                    s.Add("axis", Geometry.Entity(Com.Try(def, "Axis")));
                    s.Add("features", FeatureNames(Com.Try(def, "PatternFeatureArray")));
                    break;
                case "MirrorPattern": case "MirrorSolid":
                    s.Add("plane", Geometry.Entity(Com.Try(def, "Plane")));
                    s.Add("features", FeatureNames(Com.Try(def, "PatternFeatureArray")));
                    break;
                case "Shell":
                    s.Add("removed_faces", List(Com.Try(def, "FacesRemoved")));
                    break;
                case "Draft":
                    s.Add("neutral_plane", Geometry.Entity(Com.Try(def, "NeutralPlane")));
                    s.Add("faces", List(Com.Try(def, "FacesToDraft")));
                    break;
            }
            return s.Count > 0 ? s : null;
        }

        static JArr Items(object def, string countMember, string itemMember)
        {
            var n = Com.Int(Com.Try(def, countMember));
            if (!n.HasValue || n.Value <= 0) return null;
            var r = new JArr();
            // the index base differs between API members; try 0-based, then 1-based
            for (int i = 0; i <= n.Value; i++)
            {
                var it = Com.Try(def, itemMember, i);
                if (it != null) r.Add(Geometry.Entity(it));
                if (r.Count >= n.Value) break;
            }
            return r.Count > 0 ? r : null;
        }

        static JArr List(object v)
        {
            var a = Com.Arr(v);
            if (a == null || a.Length == 0) return null;
            var r = new JArr();
            foreach (var e in a) r.Add(Geometry.Entity(e));
            return r;
        }

        static JArr FeatureNames(object v)
        {
            var a = Com.Arr(v);
            if (a == null) return null;
            var r = new JArr();
            foreach (var f in a) r.Add(Com.Str(Com.Try(f, "Name")));
            return r;
        }

        /// Plain values only: numbers, strings, bools and arrays of them (COM objects are dropped).
        public static object Simple(object v)
        {
            if (v == null || v is DBNull) return null;
            if (v is string || v is bool || v is double || v is float || v is int || v is short || v is long) return v;
            var a = Com.Arr(v);
            if (a != null)
            {
                var r = new JArr();
                foreach (var x in a) { var s = Simple(x); if (s != null) r.Add(s); }
                return r;
            }
            return null;
        }
    }
}
