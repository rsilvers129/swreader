// Per-document export state: the SolidWorks objects in use, options, and the error list written into the JSON.
using System;

namespace SwExport
{
    public sealed class Options
    {
        public string Input;                 // a document or a folder
        public string Output;                // output folder (default: "<input>-export" next to the input folder)
        public bool Recurse = true;
        public bool Json = true, Step = true, Pdf = true, Stl = false, Dxf = false;
        public bool AllConfigurations = false;
        public bool Force = false;           // re-export even when outputs are newer than the source
        public bool Visible = false;
        public string StepVersion = "214";   // STEP application protocol: 203, 214 or 242
        public string[] Types = { "part", "assembly", "drawing" };
    }

    public sealed class Ctx
    {
        public object App, Model, Ext;
        public int DocType;
        public string Path;
        public Options Opt;
        public readonly JArr Errors = new JArr();

        public void Error(string where, Exception e)
        {
            var msg = e is System.Reflection.TargetInvocationException t && t.InnerException != null ? t.InnerException.Message : e.Message;
            Errors.Add(new JObj().Add("where", where).Add("message", msg));
        }

        /// Run one export section; a failure is recorded and the rest of the document still exports.
        public T Section<T>(string where, Func<T> f) where T : class
        {
            try { return f(); }
            catch (Exception e) { Error(where, e); return null; }
        }
    }
}
