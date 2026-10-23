// SolidWorks API enumeration values used by swexport (from swconst; defined here because swexport is late-bound).
// The JSON always carries the raw number next to any name, so a wrong or missing name never loses information.
using System.Collections.Generic;

namespace SwExport
{
    public static class Sw
    {
        // swDocumentTypes_e
        public const int DocPart = 1, DocAssembly = 2, DocDrawing = 3;

        // swOpenDocOptions_e
        public const int OpenSilent = 1, OpenReadOnly = 2;

        // swSaveAsVersion_e / swSaveAsOptions_e
        public const int SaveAsCurrentVersion = 0, SaveAsSilent = 1;

        // swExportDataFileType_e / swExportDataSheetsToExport_e
        public const int ExportPdfData = 1, ExportAllSheets = 1;

        // swSketchSegments_e
        public const int SegLine = 0, SegArc = 1, SegEllipse = 2, SegSpline = 3, SegText = 4, SegParabola = 5;

        public static readonly Dictionary<int, string> SegmentKinds = new Dictionary<int, string>
        {
            { SegLine, "line" }, { SegArc, "arc" }, { SegEllipse, "ellipse" }, { SegSpline, "spline" },
            { SegText, "text" }, { SegParabola, "parabola" },
        };

        // swLengthUnit_e
        public static readonly Dictionary<int, string> LengthUnits = new Dictionary<int, string>
        {
            { 0, "mm" }, { 1, "cm" }, { 2, "m" }, { 3, "in" }, { 4, "ft" }, { 5, "ft-in" },
            { 6, "angstrom" }, { 7, "nm" }, { 8, "micron" }, { 9, "mil" }, { 10, "microinch" },
        };

        // swAnnotationType_e
        public const int AnnCThread = 1, AnnDatumTag = 2, AnnDatumTarget = 3, AnnDimension = 4, AnnGTol = 5, AnnNote = 6,
                         AnnSurfaceFinish = 7, AnnWeld = 8, AnnTable = 14;

        public static readonly Dictionary<int, string> AnnotationKinds = new Dictionary<int, string>
        {
            { 1, "cosmetic_thread" }, { 2, "datum_tag" }, { 3, "datum_target" }, { 4, "dimension" }, { 5, "gtol" },
            { 6, "note" }, { 7, "surface_finish" }, { 8, "weld_symbol" }, { 9, "custom_symbol" }, { 10, "dowel_pin" },
            { 11, "leader" }, { 12, "block" }, { 13, "center_mark" }, { 14, "table" }, { 15, "center_line" },
            { 16, "datum_origin" }, { 17, "weld_bead" }, { 18, "revision_cloud" },
        };

        // swTolType_e
        public static readonly Dictionary<int, string> ToleranceKinds = new Dictionary<int, string>
        {
            { 0, "none" }, { 1, "basic" }, { 2, "bilateral" }, { 3, "limit" }, { 4, "symmetric" }, { 5, "min" },
            { 6, "max" }, { 7, "block" }, { 8, "general" }, { 9, "fit" }, { 10, "fit_with_tolerance" },
            { 11, "fit_tolerance_only" },
        };

        // swConstraintType_e (sketch relations)
        public static readonly Dictionary<int, string> RelationKinds = new Dictionary<int, string>
        {
            { 1, "distance" }, { 2, "angle" }, { 3, "radius" }, { 4, "horizontal" }, { 5, "vertical" },
            { 6, "tangent" }, { 7, "parallel" }, { 8, "perpendicular" }, { 9, "coincident" }, { 10, "concentric" },
            { 11, "symmetric" }, { 12, "midpoint" }, { 13, "intersection" }, { 14, "equal" }, { 15, "diameter" },
            { 16, "offset_edge" }, { 17, "fixed" }, { 25, "horizontal_points" }, { 26, "vertical_points" },
            { 27, "collinear" }, { 28, "coradial" }, { 32, "use_edge" },
        };

        // swMateType_e
        public static readonly Dictionary<int, string> MateKinds = new Dictionary<int, string>
        {
            { 0, "coincident" }, { 1, "concentric" }, { 2, "perpendicular" }, { 3, "parallel" }, { 4, "tangent" },
            { 5, "distance" }, { 6, "angle" }, { 8, "symmetric" }, { 9, "cam_follower" }, { 10, "gear" },
            { 11, "width" }, { 12, "lock_to_sketch" }, { 13, "rack_pinion" }, { 15, "path" }, { 16, "lock" },
            { 17, "screw" }, { 18, "linear_coupler" }, { 19, "universal_joint" }, { 20, "coordinate" },
            { 21, "slot" }, { 22, "hinge" }, { 23, "slider" }, { 24, "profile_center" }, { 25, "magnetic" },
        };

        // swDrawingViewTypes_e
        public static readonly Dictionary<int, string> ViewKinds = new Dictionary<int, string>
        {
            { 1, "sheet" }, { 2, "section" }, { 3, "detail" }, { 4, "projected" }, { 5, "auxiliary" },
            { 6, "standard" }, { 7, "named" }, { 8, "relative" }, { 9, "detached" }, { 10, "alternate_position" },
        };

        public static string Name(Dictionary<int, string> table, int? v)
        {
            if (!v.HasValue) return null;
            return table.TryGetValue(v.Value, out var s) ? s : null;
        }
    }
}
