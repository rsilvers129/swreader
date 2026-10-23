// swexport - batch-convert SolidWorks documents to open formats with SolidWorks itself.
//
//   swexport <file-or-folder> [options]
//
// For every .SLDPRT / .SLDASM / .SLDDRW (recursively) it writes, into an output tree that mirrors the input:
//   <name>.<ext>.json   design data (format: docs/EXPORT.md)       all documents
//   <name>.step         geometry (STEP)                            parts, assemblies
//   <name>.pdf          all sheets                                 drawings
//   <name>.stl          tessellated geometry (--stl)               parts
//   <name>-<sheet>.dxf  one per sheet (--dxf)                      drawings
// plus manifest.jsonl (one line per document) in the output root. Documents whose outputs are newer than the source
// are skipped, so an interrupted run continues where it stopped.
using System;
using System.Collections.Generic;
using System.Diagnostics;
using System.IO;
using System.Linq;
using System.Runtime.InteropServices;

namespace SwExport
{
    public static class Program
    {
        public const string Version = "1.0.1";

        const string Usage = @"swexport " + Version + @" - export SolidWorks documents to open formats (needs SolidWorks)

usage: swexport <file-or-folder> [options]

  -o, --out DIR        output folder (default: <folder>-export next to the input)
  --no-recurse         only the top folder
  --types LIST         part,assembly,drawing (default: all)
  --no-json            skip the design-data JSON
  --no-step            skip STEP for parts and assemblies
  --no-pdf             skip PDF for drawings
  --stl                also write STL for parts
  --dxf                also write one DXF per drawing sheet
  --all-configs        also record dimension values for every configuration
  --force              re-export even when outputs are up to date
  --visible            show the SolidWorks window while exporting
  -h, --help           this text
";

        static int Main(string[] argv)
        {
            Options opt;
            try { opt = Parse(argv); }
            catch (ArgumentException e) { Console.Error.WriteLine(e.Message); Console.Error.WriteLine(Usage); return 2; }
            if (opt == null) { Console.WriteLine(Usage); return 0; }

            var files = Collect(opt);
            if (files.Count == 0) { Console.Error.WriteLine("no SolidWorks documents found in " + opt.Input); return 1; }
            var inRoot = Directory.Exists(opt.Input) ? Path.GetFullPath(opt.Input) : Path.GetDirectoryName(Path.GetFullPath(opt.Input));
            var outRoot = Path.GetFullPath(opt.Output ?? inRoot.TrimEnd('\\', '/') + "-export");
            Directory.CreateDirectory(outRoot);
            Console.WriteLine($"swexport {Version}: {files.Count} documents -> {outRoot}");

            if (Type.GetTypeFromProgID("SldWorks.Application") == null)
            {
                Console.Error.WriteLine("SolidWorks is not installed on this computer (no SldWorks.Application COM class).");
                return 4;
            }
            if (Process.GetProcessesByName("SLDWORKS").Length > 0)
            {
                Console.Error.WriteLine("SolidWorks is running. Save your work and close it first: swexport starts its own SolidWorks\n" +
                                        "instance and closes every document it opens.");
                return 4;
            }
            var session = new Session(opt);
            int ok = 0, skipped = 0, failed = 0, n = 0;
            using (var manifest = new StreamWriter(Path.Combine(outRoot, "manifest.jsonl"), true, new System.Text.UTF8Encoding(false)))
            {
                foreach (var f in files)
                {
                    n++;
                    var rel = RelativePath(inRoot, f);
                    var outBase = Path.Combine(outRoot, rel);
                    var plan = Outputs(opt, f, outBase);
                    if (!opt.Force && plan.All(p => File.Exists(p) && File.GetLastWriteTimeUtc(p) >= File.GetLastWriteTimeUtc(f)))
                    {
                        skipped++;
                        continue;
                    }
                    var sw = Stopwatch.StartNew();
                    Console.Write($"[{n}/{files.Count}] {rel} ... ");
                    var rec = session.ExportOne(f, outBase);
                    rec.Add("source", rel).Add("seconds", Math.Round(sw.Elapsed.TotalSeconds, 2));
                    manifest.WriteLine(Json.Write(rec, false));
                    manifest.Flush();
                    var status = rec.First(kv => kv.Key == "status").Value as string;
                    if (status.StartsWith("ok")) ok++; else failed++;
                    Console.WriteLine($"{status} ({sw.Elapsed.TotalSeconds:F1}s)");
                }
            }
            session.Dispose();
            Console.WriteLine($"done: {ok} exported, {skipped} up to date, {failed} failed");
            return failed > 0 ? 3 : 0;
        }

        static Options Parse(string[] a)
        {
            var o = new Options();
            for (int i = 0; i < a.Length; i++)
            {
                string Next() => ++i < a.Length ? a[i] : throw new ArgumentException("missing value after " + a[i - 1]);
                switch (a[i])
                {
                    case "-h": case "--help": case "/?": return null;
                    case "-o": case "--out": o.Output = Next(); break;
                    case "--no-recurse": o.Recurse = false; break;
                    case "--types": o.Types = Next().Split(',').Select(s => s.Trim().ToLowerInvariant()).ToArray(); break;
                    case "--no-json": o.Json = false; break;
                    case "--no-step": o.Step = false; break;
                    case "--no-pdf": o.Pdf = false; break;
                    case "--stl": o.Stl = true; break;
                    case "--dxf": o.Dxf = true; break;
                    case "--all-configs": o.AllConfigurations = true; break;
                    case "--force": o.Force = true; break;
                    case "--visible": o.Visible = true; break;
                    default:
                        if (a[i].StartsWith("-")) throw new ArgumentException("unknown option " + a[i]);
                        if (o.Input != null) throw new ArgumentException("only one input file or folder");
                        o.Input = a[i];
                        break;
                }
            }
            if (o.Input == null) throw new ArgumentException("no input given");
            if (!File.Exists(o.Input) && !Directory.Exists(o.Input)) throw new ArgumentException("not found: " + o.Input);
            return o;
        }

        static readonly Dictionary<string, string> TypeOfExt = new Dictionary<string, string>(StringComparer.OrdinalIgnoreCase)
        {
            { ".sldprt", "part" }, { ".sldasm", "assembly" }, { ".slddrw", "drawing" },
        };

        static List<string> Collect(Options o)
        {
            IEnumerable<string> all;
            if (File.Exists(o.Input)) all = new[] { Path.GetFullPath(o.Input) };
            else all = Directory.EnumerateFiles(o.Input, "*.*", o.Recurse ? SearchOption.AllDirectories : SearchOption.TopDirectoryOnly);
            var want = new HashSet<string>(o.Types);
            // parts first, then assemblies, then drawings: referenced files are exported (and cached) before users
            int Rank(string f) => TypeOfExt[Path.GetExtension(f)] == "part" ? 0 : TypeOfExt[Path.GetExtension(f)] == "assembly" ? 1 : 2;
            return all.Where(f => TypeOfExt.ContainsKey(Path.GetExtension(f)))
                      .Where(f => !Path.GetFileName(f).StartsWith("~$") && !Path.GetFileName(f).StartsWith("._"))
                      .Where(f => new FileInfo(f).Length > 0)
                      .Where(f => want.Contains(TypeOfExt[Path.GetExtension(f)]))
                      .OrderBy(Rank).ThenBy(f => f, StringComparer.OrdinalIgnoreCase)
                      .ToList();
        }

        static string RelativePath(string root, string file)
        {
            var r = Path.GetFullPath(root).TrimEnd('\\', '/') + Path.DirectorySeparatorChar;
            var f = Path.GetFullPath(file);
            return f.StartsWith(r, StringComparison.OrdinalIgnoreCase) ? f.Substring(r.Length) : Path.GetFileName(f);
        }

        /// The files a complete export of this document produces (used to decide whether it is up to date).
        public static List<string> Outputs(Options o, string src, string outBase)
        {
            var t = TypeOfExt[Path.GetExtension(src)];
            var stem = Path.Combine(Path.GetDirectoryName(outBase), Path.GetFileNameWithoutExtension(outBase));
            var r = new List<string>();
            if (o.Json) r.Add(outBase + ".json");
            if (o.Step && t != "drawing") r.Add(stem + ".step");
            if (o.Stl && t == "part") r.Add(stem + ".stl");
            if (o.Pdf && t == "drawing") r.Add(stem + ".pdf");
            return r;
        }
    }

    /// One SolidWorks instance for the whole batch; restarted if it dies.
    sealed class Session : IDisposable
    {
        readonly Options opt;
        object app;
        readonly HashSet<int> ours = new HashSet<int>();     // SolidWorks processes this session started

        public Session(Options o) { opt = o; }

        object App()
        {
            if (app != null) return app;
            var t = Type.GetTypeFromProgID("SldWorks.Application");
            if (t == null) throw new InvalidOperationException("SolidWorks is not installed (no SldWorks.Application COM class)");
            var before = new HashSet<int>(Process.GetProcessesByName("SLDWORKS").Select(p => p.Id));
            app = Activator.CreateInstance(t);
            foreach (var p in Process.GetProcessesByName("SLDWORKS")) if (!before.Contains(p.Id)) ours.Add(p.Id);
            Com.TrySet(app, "Visible", opt.Visible);
            Com.TrySet(app, "UserControl", false);
            Com.TrySet(app, "CommandInProgress", true);      // fewer UI updates while working
            return app;
        }

        static bool Fatal(Exception e)
        {
            var c = (e as COMException) ?? (e.InnerException as COMException);
            if (c == null) return false;
            uint h = unchecked((uint)c.ErrorCode);
            return h == 0x800706BA || h == 0x800706BE || h == 0x80010108 || h == 0x80010105;   // server gone / crashed
        }

        public JObj ExportOne(string path, string outBase)
        {
            var rec = new JObj();
            var outputs = new JArr();
            for (int attempt = 0; attempt < 2; attempt++)
            {
                try
                {
                    var a = App();
                    var ext = Path.GetExtension(path).ToLowerInvariant();
                    int type = ext == ".sldprt" ? Sw.DocPart : ext == ".sldasm" ? Sw.DocAssembly : Sw.DocDrawing;
                    var args = new object[] { path, type, Sw.OpenSilent | Sw.OpenReadOnly, "", 0, 0 };
                    var model = Com.CallRef(a, "OpenDoc6", args, new[] { false, false, false, false, true, true });
                    if (model == null)
                        return rec.Add("status", "failed").Add("error", $"open failed (errors {args[4]}, warnings {args[5]})");
                    try
                    {
                        var c = new Ctx { App = a, Model = model, Ext = Com.Try(model, "Extension"), DocType = type, Path = path, Opt = opt };
                        Directory.CreateDirectory(Path.GetDirectoryName(outBase));
                        var stem = Path.Combine(Path.GetDirectoryName(outBase), Path.GetFileNameWithoutExtension(outBase));
                        if (type != Sw.DocDrawing && opt.Step) SaveAs(c, stem + ".step", outputs);
                        if (type == Sw.DocPart && opt.Stl) SaveAs(c, stem + ".stl", outputs);
                        if (type == Sw.DocDrawing && opt.Pdf) SavePdf(c, stem + ".pdf", outputs);
                        if (type == Sw.DocDrawing && opt.Dxf) SaveDxf(c, stem, outputs);
                        if (opt.Json)
                        {
                            var doc = Document.Export(c);
                            doc.Add("outputs", outputs);
                            doc.Add("errors", c.Errors);
                            Json.WriteFile(outBase + ".json", doc);
                            outputs.Add(Path.GetFileName(outBase + ".json"));
                        }
                        return rec.Add("status", c.Errors.Count == 0 ? "ok" : "ok_with_warnings").Add("type", Document.TypeName(type))
                                  .Add("outputs", outputs).Add("warnings", c.Errors.Count);
                    }
                    finally
                    {
                        Com.Try(a, "CloseAllDocuments", true);
                        Com.Release(model);
                    }
                }
                catch (Exception e) when (Fatal(e) && attempt == 0)
                {
                    Console.Write("(SolidWorks stopped responding - restarting) ");
                    app = null;
                    KillSolidWorks();
                }
                catch (Exception e)
                {
                    var m = e is System.Reflection.TargetInvocationException t && t.InnerException != null ? t.InnerException.Message : e.Message;
                    return rec.Add("status", "failed").Add("error", m);
                }
            }
            return rec.Add("status", "failed").Add("error", "SolidWorks crashed twice on this document");
        }

        void SaveAs(Ctx c, string file, JArr outputs, object exportData = null)
        {
            var args = new object[] { file, Sw.SaveAsCurrentVersion, Sw.SaveAsSilent, exportData, 0, 0 };
            try
            {
                var ok = Com.Bool(Com.CallRef(c.Ext, "SaveAs", args, new[] { false, false, false, false, true, true }));
                if (ok == true && File.Exists(file)) outputs.Add(Path.GetFileName(file));
                else c.Errors.Add(new JObj().Add("where", "save " + Path.GetFileName(file)).Add("message", $"errors {args[4]}, warnings {args[5]}"));
            }
            catch (Exception e) { c.Error("save " + Path.GetFileName(file), e); }
        }

        void SavePdf(Ctx c, string file, JArr outputs)
        {
            var data = Com.Try(c.App, "GetExportFileData", Sw.ExportPdfData);
            if (data != null) Com.Try(data, "SetSheets", Sw.ExportAllSheets, null);
            SaveAs(c, file, outputs, data);
        }

        void SaveDxf(Ctx c, string stem, JArr outputs)
        {
            var names = Com.Strings(Com.Try(c.Model, "GetSheetNames"));
            if (names == null) return;
            foreach (var n in names)
            {
                Com.Try(c.Model, "ActivateSheet", n);
                SaveAs(c, stem + "-" + Safe(n) + ".dxf", outputs);
            }
        }

        static string Safe(string s)
        {
            foreach (var ch in Path.GetInvalidFileNameChars()) s = s.Replace(ch, '_');
            return s;
        }

        /// Stop only the SolidWorks processes this session started.
        void KillSolidWorks()
        {
            foreach (var p in Process.GetProcessesByName("SLDWORKS"))
                if (ours.Contains(p.Id))
                    try { p.Kill(); p.WaitForExit(30000); } catch { }
            ours.Clear();
        }

        public void Dispose()
        {
            if (app == null) return;
            Com.Try(app, "CloseAllDocuments", true);
            Com.Try(app, "ExitApp");
            Com.Release(app);
            app = null;
        }
    }
}
