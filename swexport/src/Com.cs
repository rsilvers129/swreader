// Late-bound COM access to the SolidWorks API.
//
// swexport does not reference the SolidWorks interop assemblies: every call goes through IDispatch, so the tool builds
// without SolidWorks installed and runs against any SolidWorks version. A member is invoked with both the "method" and
// "property get" flags, so properties, parameterized properties and methods are all called the same way.
using System;
using System.Collections.Generic;
using System.Globalization;
using System.Reflection;
using System.Runtime.InteropServices;

namespace SwExport
{
    public static class Com
    {
        const BindingFlags Call = BindingFlags.InvokeMethod | BindingFlags.GetProperty;

        /// Invoke a method or read a property; throws on failure.
        public static object Get(object o, string member, params object[] args)
        {
            if (o == null) throw new ArgumentNullException(nameof(o), "COM object is null (" + member + ")");
            return o.GetType().InvokeMember(member, Call, null, o, args ?? new object[0], CultureInfo.InvariantCulture);
        }

        /// Like Get, but returns null instead of throwing (member missing in this SolidWorks version, bad state ...).
        public static object Try(object o, string member, params object[] args)
        {
            if (o == null) return null;
            try { return Get(o, member, args); }
            catch { return null; }
        }

        /// Set a property.
        public static void Set(object o, string member, object value)
        {
            o.GetType().InvokeMember(member, BindingFlags.SetProperty, null, o, new[] { value }, CultureInfo.InvariantCulture);
        }

        public static bool TrySet(object o, string member, object value)
        {
            try { Set(o, member, value); return true; } catch { return false; }
        }

        /// Invoke a method with by-reference (out) arguments. byRef[i] marks args[i]; the updated values are written back
        /// into args. Returns the method's return value.
        public static object CallRef(object o, string member, object[] args, bool[] byRef)
        {
            var mod = new ParameterModifier(args.Length);
            for (int i = 0; i < args.Length; i++) mod[i] = byRef[i];
            return o.GetType().InvokeMember(member, BindingFlags.InvokeMethod, null, o, args,
                                            new[] { mod }, CultureInfo.InvariantCulture, null);
        }

        // -- conversions ---------------------------------------------------------------------------------------------

        public static string Str(object v) => v == null || v is DBNull ? null : Convert.ToString(v, CultureInfo.InvariantCulture);

        public static double? Dbl(object v)
        {
            if (v == null || v is DBNull) return null;
            try { return Convert.ToDouble(v, CultureInfo.InvariantCulture); } catch { return null; }
        }

        public static int? Int(object v)
        {
            if (v == null || v is DBNull) return null;
            try { return Convert.ToInt32(v, CultureInfo.InvariantCulture); } catch { return null; }
        }

        public static bool? Bool(object v)
        {
            if (v == null || v is DBNull) return null;
            if (v is bool b) return b;
            var i = Int(v);
            return i.HasValue ? (bool?)(i.Value != 0) : null;
        }

        /// Any COM array (SAFEARRAY of VARIANT, double, int, string ...) as object[]; null stays null.
        public static object[] Arr(object v)
        {
            if (v is object[] oa) return oa;
            if (v is Array a)
            {
                var r = new object[a.Length];
                int k = 0;
                foreach (var x in a) r[k++] = x;
                return r;
            }
            return null;
        }

        public static List<double> Doubles(object v)
        {
            var a = Arr(v);
            if (a == null) return null;
            var r = new List<double>(a.Length);
            foreach (var x in a) { var d = Dbl(x); if (d.HasValue) r.Add(d.Value); }
            return r;
        }

        public static List<string> Strings(object v)
        {
            var a = Arr(v);
            if (a == null) return null;
            var r = new List<string>(a.Length);
            foreach (var x in a) r.Add(Str(x));
            return r;
        }

        /// Release a COM object now instead of at the next garbage collection (keeps SolidWorks memory down in batches).
        public static void Release(object o)
        {
            if (o != null && Marshal.IsComObject(o))
            {
                try { Marshal.ReleaseComObject(o); } catch { }
            }
        }
    }
}
