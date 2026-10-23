// A small JSON object model and writer (no external packages). Objects keep insertion order so output is stable and
// diff-friendly; null values are dropped from objects.
using System;
using System.Collections;
using System.Collections.Generic;
using System.Globalization;
using System.IO;
using System.Text;

namespace SwExport
{
    public sealed class JObj : IEnumerable<KeyValuePair<string, object>>
    {
        readonly List<KeyValuePair<string, object>> items = new List<KeyValuePair<string, object>>();

        public JObj Add(string key, object value)
        {
            if (value != null) items.Add(new KeyValuePair<string, object>(key, value));
            return this;
        }

        public int Count => items.Count;
        public IEnumerator<KeyValuePair<string, object>> GetEnumerator() => items.GetEnumerator();
        IEnumerator IEnumerable.GetEnumerator() => items.GetEnumerator();
    }

    public sealed class JArr : List<object>
    {
        public JArr() { }
        public JArr(IEnumerable<object> xs) : base(xs) { }
    }

    public static class Json
    {
        public static string Write(object value, bool indent = true)
        {
            var sb = new StringBuilder();
            WriteValue(sb, value, indent, 0);
            if (indent) sb.Append('\n');
            return sb.ToString();
        }

        public static void WriteFile(string path, object value)
        {
            Directory.CreateDirectory(Path.GetDirectoryName(Path.GetFullPath(path)));
            var tmp = path + ".tmp";
            File.WriteAllText(tmp, Write(value), new UTF8Encoding(false));
            if (File.Exists(path)) File.Delete(path);
            File.Move(tmp, path);
        }

        static void WriteValue(StringBuilder sb, object v, bool indent, int depth)
        {
            switch (v)
            {
                case null: sb.Append("null"); break;
                case string s: WriteString(sb, s); break;
                case bool b: sb.Append(b ? "true" : "false"); break;
                case double d: WriteDouble(sb, d); break;
                case float f: WriteDouble(sb, f); break;
                case int _: case long _: case short _: case uint _: case ulong _: case ushort _: case byte _:
                    sb.Append(Convert.ToString(v, CultureInfo.InvariantCulture)); break;
                case JObj o: WriteObject(sb, o, indent, depth); break;
                case IDictionary<string, object> dct:
                    var jo = new JObj();
                    foreach (var kv in dct) jo.Add(kv.Key, kv.Value);
                    WriteObject(sb, jo, indent, depth);
                    break;
                case IEnumerable e: WriteArray(sb, e, indent, depth); break;
                default: WriteString(sb, Convert.ToString(v, CultureInfo.InvariantCulture)); break;
            }
        }

        static void WriteDouble(StringBuilder sb, double d)
        {
            if (double.IsNaN(d) || double.IsInfinity(d)) { sb.Append("null"); return; }
            sb.Append(d.ToString("R", CultureInfo.InvariantCulture));
        }

        static void NewLine(StringBuilder sb, bool indent, int depth)
        {
            if (!indent) return;
            sb.Append('\n').Append(' ', depth * 2);
        }

        static bool IsScalarList(IEnumerable e)
        {
            foreach (var x in e)
                if (x is JObj || x is IDictionary<string, object> || (x is IEnumerable && !(x is string))) return false;
            return true;
        }

        static void WriteArray(StringBuilder sb, IEnumerable e, bool indent, int depth)
        {
            bool flat = IsScalarList(e);                 // numbers/strings stay on one line: [1, 2, 3]
            sb.Append('[');
            bool first = true;
            foreach (var x in e)
            {
                if (!first) sb.Append(flat && indent ? ", " : ",");
                if (!flat) NewLine(sb, indent, depth + 1);
                WriteValue(sb, x, indent, depth + 1);
                first = false;
            }
            if (!first && !flat) NewLine(sb, indent, depth);
            sb.Append(']');
        }

        static void WriteObject(StringBuilder sb, JObj o, bool indent, int depth)
        {
            sb.Append('{');
            bool first = true;
            foreach (var kv in o)
            {
                if (!first) sb.Append(',');
                NewLine(sb, indent, depth + 1);
                WriteString(sb, kv.Key);
                sb.Append(indent ? ": " : ":");
                WriteValue(sb, kv.Value, indent, depth + 1);
                first = false;
            }
            if (!first) NewLine(sb, indent, depth);
            sb.Append('}');
        }

        static void WriteString(StringBuilder sb, string s)
        {
            sb.Append('"');
            foreach (var c in s)
            {
                switch (c)
                {
                    case '"': sb.Append("\\\""); break;
                    case '\\': sb.Append("\\\\"); break;
                    case '\n': sb.Append("\\n"); break;
                    case '\r': sb.Append("\\r"); break;
                    case '\t': sb.Append("\\t"); break;
                    default:
                        if (c < 0x20) sb.Append("\\u").Append(((int)c).ToString("x4"));
                        else sb.Append(c);
                        break;
                }
            }
            sb.Append('"');
        }
    }
}
