#!/usr/bin/env python3
"""Check swexport and SwRebuild against the official API references - run before every commit that touches them.

  check_api.py sw      every SolidWorks API member swexport calls exists in the SolidWorks API reference
  check_api.py fusion  every Fusion class/member SwRebuild uses exists in the installed Fusion API stubs
  check_api.py enum NAME          print a SolidWorks enumeration (e.g. swEndConditions_e) with its values
  check_api.py member IFACE NAME  print a SolidWorks member's C# signature (e.g. IExtrudeFeatureData2 GetDepth)
  check_api.py fsig CLASS NAME    print a Fusion member's signature and docstring (e.g. ExtrudeFeatureInput setOneSideExtent)

Reference locations (environment):
  SW_API     folder of SolidWorks API Markdown pages (sldworksapi/ and swconst/ inside)
  FUSION_PY  folder with the Fusion API stubs core.py and fusion.py
"""
import ast
import collections
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SW_API = os.environ.get("SW_API", "/reference/cad/solidworks/md/api")
FUSION_PY = os.environ.get("FUSION_PY", "")
SW_PREFIX = "SolidWorks.Interop.sldworks~SolidWorks.Interop.sldworks."


def fusion_dir():
    if FUSION_PY:
        return FUSION_PY
    base = "/reference/cad/fusion"
    for d in sorted(os.listdir(base), reverse=True) if os.path.isdir(base) else []:
        if d.startswith("api-stubs-"):
            return os.path.join(base, d, "python")
    sys.exit("set FUSION_PY to the folder holding the Fusion stubs (core.py, fusion.py)")


def sw_members():
    mem = collections.defaultdict(set)
    for f in os.listdir(os.path.join(SW_API, "sldworksapi")):
        m = re.match(r"SolidWorks\.Interop\.sldworks~SolidWorks\.Interop\.sldworks\.(\w+)~(\w+)\.md$", f)
        if m:
            mem[m.group(2)].add(m.group(1))
    return mem


def check_sw():
    mem = sw_members()
    used = collections.defaultdict(set)
    src = os.path.join(ROOT, "swexport", "src")
    for fn in os.listdir(src):
        s = open(os.path.join(src, fn), encoding="utf-8").read()
        for m in re.findall(r'Com\.(?:Get|Try|CallRef|Set|TrySet)\([^,]+,\s*"(\w+)"', s):
            used[m].add(fn)
        for m in re.findall(r'new P\("\w+",\s*"(\w+)"', s):
            used[m].add(fn)
    missing = {k: v for k, v in used.items() if k not in mem}
    print(f"{len(used)} SolidWorks members used; {len(missing)} not in the API reference")
    for k, v in sorted(missing.items()):
        print(f"  MISSING {k}  (in {', '.join(sorted(v))})")
    return not missing


def sw_enum(name):
    p = os.path.join(SW_API, "swconst", f"SolidWorks.Interop.swconst~SolidWorks.Interop.swconst.{name}.md")
    if not os.path.exists(p):
        sys.exit(f"no enumeration {name}")
    t = open(p, encoding="utf-8").read()
    for n, d in re.findall(r"\| \*\*([\w\\]+)\*\* \| ([^|]*)\|", t):
        print(f"  {d.strip()[:60]:<60} {n.replace(chr(92), '')}")


def sw_member(iface, name):
    p = os.path.join(SW_API, "sldworksapi", f"{SW_PREFIX}{iface}~{name}.md")
    if not os.path.exists(p):
        sys.exit(f"no member {iface}.{name}; members of {iface}: " + " ".join(sorted(
            f.split("~")[-1][:-3] for f in os.listdir(os.path.join(SW_API, "sldworksapi"))
            if f.startswith(f"{SW_PREFIX}{iface}~"))))
    t = open(p, encoding="utf-8").read()
    m = re.search(r"C#\s*\n+```\s*\n(.*?)```", t, re.S)
    print(" ".join((m.group(1) if m else t[:800]).split()))
    for sec in ("Parameters", "Return Value", "Remarks"):
        m = re.search(rf"#+ {sec}\s*\n(.*?)(?:\n#)", t, re.S)
        if m:
            print(f"--- {sec}\n" + m.group(1).strip()[:1200])


def fusion_classes():
    d = fusion_dir()
    members, bases = collections.defaultdict(dict), collections.defaultdict(set)
    for mod in ("core", "fusion"):
        tree = ast.parse(open(os.path.join(d, mod + ".py"), encoding="utf-8").read())
        for n in tree.body:
            if isinstance(n, ast.ClassDef):
                bases[n.name] |= {b.id for b in n.bases if isinstance(b, ast.Name)}
                for b in n.body:
                    if isinstance(b, ast.FunctionDef):
                        members[n.name][b.name] = b
                    elif isinstance(b, ast.Assign):
                        for tg in b.targets:
                            if isinstance(tg, ast.Name):
                                members[n.name][tg.id] = b
    return members, bases


def check_fusion():
    members, bases = fusion_classes()

    def has(c, m):
        return m in members.get(c, {}) or any(has(b, m) for b in bases.get(c, ()))

    src = ""
    for f in ("lib/rebuild.py", "SwRebuild.py"):
        src += open(os.path.join(ROOT, "fusion", "SwRebuild", f), encoding="utf-8").read()
    bad = []
    for mod, cls, mem in re.findall(r"adsk\.(core|fusion)\.(\w+)(?:\.(\w+))?", src):
        if cls not in members:
            bad.append(f"adsk.{mod}.{cls}: no such class")
        elif mem and not has(cls, mem) and mem not in ("cast",):
            bad.append(f"adsk.{mod}.{cls}.{mem}: no such member")
    every = set().union(*(set(v) for v in members.values()))
    calls = set(re.findall(r"\.([a-z]\w*)\(", src))
    geom_src = open(os.path.join(ROOT, "fusion", "SwRebuild", "lib", "geom.py"), encoding="utf-8").read()
    ours = set(re.findall(r"def (\w+)\(", src + geom_src)) | {"doEvents",                     # adsk.doEvents()
                                                                 "append", "items", "get", "keys", "values", "startswith", "rsplit",
                                                    "split", "group", "format", "sort", "replace", "join", "write",
                                                    "flush", "close", "setdefault", "add", "item", "splitext",
                                                    "format_exc", "match", "sub", "cos", "sin", "atan2", "hypot",
                                                    "radians", "dot", "cross", "unit", "mul", "dist", "apply",
                                                    "isalnum", "isalpha", "load", "dirname", "basename", "lower"}
    unknown = sorted(c for c in calls if c not in every and c not in ours)
    print(f"{len(bad)} class/member problems; {len(unknown)} called names not in any Fusion class")
    for b in sorted(set(bad)):
        print("  " + b)
    for u in unknown:
        print("  UNKNOWN CALL ." + u + "(")
    return not bad and not unknown


def fusion_sig(cls, name):
    members, _ = fusion_classes()
    node = members.get(cls, {}).get(name)
    if node is None:
        sys.exit(f"no {cls}.{name}; members: " + " ".join(sorted(members.get(cls, {}))))
    if isinstance(node, ast.FunctionDef):
        print(f"def {name}({ast.unparse(node.args)})" + (f" -> {ast.unparse(node.returns)}" if node.returns else ""))
        print(ast.get_docstring(node) or "")
    else:
        print(ast.unparse(node))


if __name__ == "__main__":
    a = sys.argv[1:]
    if not a:
        sys.exit(__doc__)
    if a[0] == "sw":
        sys.exit(0 if check_sw() else 1)
    if a[0] == "fusion":
        sys.exit(0 if check_fusion() else 1)
    if a[0] == "enum" and len(a) == 2:
        sw_enum(a[1])
    elif a[0] == "member" and len(a) == 3:
        sw_member(a[1], a[2])
    elif a[0] == "fsig" and len(a) == 3:
        fusion_sig(a[1], a[2])
    else:
        sys.exit(__doc__)
