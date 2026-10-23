// Drawing export: sheets, views, annotations (dimensions with tolerances, notes, GD&T, surface finish, datums ...)
// and tables (BOM, revision, hole, general). Positions are sheet space, metres.
namespace SwExport
{
    public static class Drawing
    {
        public static JObj Export(Ctx c)
        {
            var names = Com.Strings(Com.Try(c.Model, "GetSheetNames"));
            var perSheet = Com.Arr(Com.Try(c.Model, "GetViews"));      // one array per sheet; [0] is the sheet itself
            var sheets = new JArr();
            for (int i = 0; names != null && i < names.Count; i++)
            {
                var views = perSheet != null && i < perSheet.Length ? Com.Arr(perSheet[i]) : null;
                var name = names[i];
                sheets.Add(c.Section("sheet " + name, () => Sheet(c, name, views)));
            }
            return new JObj().Add("sheets", sheets);
        }

        static JObj Sheet(Ctx c, string name, object[] views)
        {
            var sheet = Com.Try(c.Model, "Sheet", name);
            var props = Com.Doubles(Com.Try(sheet, "GetProperties2"));  // paper size, template, scale num/den, 1st angle, w, h
            var o = new JObj().Add("name", name)
                .Add("template", Com.Str(Com.Try(sheet, "GetTemplateName")))
                .Add("properties_view", Com.Str(Com.Try(sheet, "CustomPropertyView")));
            if (props != null && props.Count >= 7)
                o.Add("scale", new JArr { props[2], props[3] }).Add("first_angle", props[4] != 0)
                 .Add("size", new JArr { props[5], props[6] }).Add("paper_size", (int)props[0]);

            var vs = new JArr();
            if (views != null)
                for (int i = 0; i < views.Length; i++)
                {
                    var v = views[i];
                    var j = c.Section("view", () => View(c, v, i == 0));
                    if (j != null) vs.Add(j);
                }
            o.Add("views", vs);
            return o;
        }

        static JObj View(Ctx c, object v, bool isSheet)
        {
            var t = Com.Int(Com.Try(v, "Type"));
            var o = new JObj()
                .Add("name", Com.Str(Com.Try(v, "GetName2")))
                .Add("role", isSheet ? "sheet" : "view")
                .Add("type", t).Add("kind", Sw.Name(Sw.ViewKinds, t));
            if (!isSheet)
            {
                o.Add("scale", Com.Doubles(Com.Try(v, "ScaleRatio")))
                 .Add("position", Com.Doubles(Com.Try(v, "Position")))
                 .Add("outline", Com.Doubles(Com.Try(v, "GetOutline")))
                 .Add("orientation", Com.Str(Com.Try(v, "GetOrientationName")))
                 .Add("display_mode", Com.Int(Com.Try(v, "GetDisplayMode2")))
                 .Add("model", Com.Str(Com.Try(Com.Try(v, "ReferencedDocument"), "GetPathName")))
                 .Add("configuration", Com.Str(Com.Try(v, "ReferencedConfiguration")))
                 .Add("base_view", Com.Str(Com.Try(Com.Try(v, "GetBaseView"), "GetName2")));
            }
            o.Add("annotations", Annotations(c, v));
            o.Add("tables", Tables(v));
            return o;
        }

        static JArr Annotations(Ctx c, object view)
        {
            var anns = Com.Arr(Com.Try(view, "GetAnnotations"));
            if (anns == null || anns.Length == 0) return null;
            var r = new JArr();
            foreach (var a in anns)
            {
                var j = c.Section("annotation", () => Annotation(c, a));
                if (j != null) r.Add(j);
            }
            return r;
        }

        static JObj Annotation(Ctx c, object a)
        {
            var t = Com.Int(Com.Try(a, "GetType"));
            var o = new JObj()
                .Add("kind", Sw.Name(Sw.AnnotationKinds, t) ?? "other").Add("type", t)
                .Add("name", Com.Str(Com.Try(a, "GetName")))
                .Add("position", Com.Doubles(Com.Try(a, "GetPosition")))
                .Add("layer", Empty(Com.Str(Com.Try(a, "Layer"))));

            var n = Com.Int(Com.Try(a, "GetTextCount"));               // the displayed text of any annotation
            if (n.HasValue && n.Value > 0)
            {
                var texts = new JArr();
                for (int i = 0; i < n.Value; i++) texts.Add(Com.Str(Com.Try(a, "GetTextAtIndex", i)));
                o.Add("text", texts);
            }

            var s = Com.Try(a, "GetSpecificAnnotation");
            switch (t)
            {
                case Sw.AnnDimension:
                    o.Add("dimension", Dimensions.Of(c, s, true));
                    break;
                case Sw.AnnNote:
                    o.Add("note", new JObj()
                        .Add("text", Com.Str(Com.Try(s, "GetText")))
                        .Add("balloon", Com.Bool(Com.Try(s, "IsBomBalloon")))
                        .Add("height", Com.Dbl(Com.Try(s, "GetHeight")))
                        .Add("angle", Com.Dbl(Com.Try(s, "Angle"))));
                    break;
                case Sw.AnnGTol:
                    var frames = Com.Int(Com.Try(s, "GetFrameCount"));
                    var fr = new JArr();
                    for (int i = 0; frames.HasValue && i < frames.Value; i++)
                        fr.Add(new JObj()
                            .Add("values", Definitions.Simple(Com.Try(s, "GetFrameValues", i)))
                            .Add("symbols", Definitions.Simple(Com.Try(s, "GetFrameSymbols3", i))));
                    o.Add("gtol", new JObj().Add("frames", fr).Add("datum_label", Com.Str(Com.Try(s, "GetDatumLabel"))));
                    break;
                case Sw.AnnDatumTag:
                    o.Add("datum", Com.Str(Com.Try(s, "GetLabel")));
                    break;
                case Sw.AnnSurfaceFinish:
                    o.Add("surface_finish", new JObj().Add("symbol", Com.Int(Com.Try(s, "GetSymbol2"))));
                    break;
            }
            return o;
        }

        static JArr Tables(object view)
        {
            var tables = Com.Arr(Com.Try(view, "GetTableAnnotations"));
            if (tables == null || tables.Length == 0) return null;
            var r = new JArr();
            foreach (var t in tables)
            {
                var rows = Com.Int(Com.Try(t, "RowCount")) ?? 0;
                var cols = Com.Int(Com.Try(t, "ColumnCount")) ?? 0;
                var cells = new JArr();
                for (int i = 0; i < rows; i++)
                {
                    var row = new JArr();
                    for (int j = 0; j < cols; j++) row.Add(Com.Str(Com.Try(t, "Text", i, j)) ?? "");
                    cells.Add(row);
                }
                r.Add(new JObj()
                    .Add("type", Com.Int(Com.Try(t, "Type")))
                    .Add("title", Empty(Com.Str(Com.Try(t, "Title"))))
                    .Add("rows", rows).Add("columns", cols)
                    .Add("cells", cells));
            }
            return r;
        }

        static string Empty(string s) => string.IsNullOrEmpty(s) ? null : s;
    }
}
