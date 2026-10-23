"""swread - read SolidWorks documents without SolidWorks.

  swread info FILE                 JSON summary (properties, mass, material, configurations, components)
  swread sections FILE             list the document's sections and their sizes
  swread extract FILE OUTDIR       write every section to OUTDIR (wrapped streams inflated)
  swread preview FILE [-o X.png]   the embedded 640x480 preview (for a drawing: the first sheet)
  swread parasolid FILE OUTDIR     each configuration's bodies as config-N.x_b (imported bodies: config-N-i.x_b)
  swread features FILE [--all] [--json]   features and sketches in creation order, with dimensions
                                   (from the keyword index; --all includes folders, lights, anchors ...)
  swread index DIR [-o X.jsonl]    `info` for every document under DIR, one JSON line each
  swread classes FILE [SECTION]    MFC classes defined in each object stream (or one section)
  swread dump FILE SECTION [--start N --end N]   annotated dump of an object stream (format work)

swexport output (docs/EXPORT.md):
  swread summary FILE.json         readable design summary of an exported document
  swread params FILE.json          every dimension: feature, name, value, tolerance
  swread library EXPORT-DIR [-o X.jsonl]   search records for every exported document
"""
from __future__ import annotations

import argparse
import json
import os
import sys

from . import explore, export, keywords, parasolid, props
from .container import FormatError, open_file, unwrap
from .mfc import find_class_names

EXTS = (".sldprt", ".sldasm", ".slddrw")


def _safe(name: str) -> str:
    return "".join(c if c.isalnum() or c in "-_.[]" else "_" for c in name.replace("/", "__"))


def cmd_info(a):
    with open_file(a.file) as sw:
        json.dump(props.summary(sw), sys.stdout, indent=2, ensure_ascii=False, default=str)
        print()


def cmd_features(a):
    with open_file(a.file) as sw:
        kw = keywords.read(sw)
    if kw is None:
        sys.exit("this document has no keyword index")
    items = keywords.features(kw, modelling_only=not a.all)
    if a.json:
        json.dump({"configurations": kw["configurations"], "features": items, "summary": keywords.summary(kw)},
                  sys.stdout, indent=2, ensure_ascii=False)
        print()
        return
    for c in kw["configurations"]:
        print(f"configuration {c.get('name')!r}" + (f"  material {c['material']!r}" if c.get("material") else ""))
    for it in items:
        dims = "  ".join(f"{d['name']}={d['display']}" for d in it.get("dimensions", []))
        print(f"{it['id']:>6}  {it.get('canonical') or it.get('type') or it['kind']:<20} {it.get('name') or '':<32} {dims}")
    s = keywords.summary(kw)
    print(f"-- {s['modelling_features']} features, {s['sketches']} sketches, {s['dimensions']} dimensions")


def cmd_sections(a):
    with open_file(a.file) as sw:
        print(f"# {sw.kind} container")
        for n in sw.names():
            print(f"{len(sw.read(n)):>12,}  {n}")


def cmd_extract(a):
    os.makedirs(a.outdir, exist_ok=True)
    with open_file(a.file) as sw:
        for n in sw.names():
            data = sw.read(n)
            if n.endswith("-Partition"):
                data = unwrap(data)
            with open(os.path.join(a.outdir, _safe(n)), "wb") as f:
                f.write(data)
            print(f"{len(data):>12,}  {n}")


def cmd_preview(a):
    with open_file(a.file) as sw:
        png = sw.read("PreviewPNG") or sw.read("Images/Sheet_0")
    if not png:
        sys.exit("no PNG preview in this document")
    out = a.output or os.path.splitext(os.path.basename(a.file))[0] + ".png"
    with open(out, "wb") as f:
        f.write(png)
    print(out)


def cmd_parasolid(a):
    os.makedirs(a.outdir, exist_ok=True)
    with open_file(a.file) as sw:
        configs = sorted({t["config"] for t in parasolid.transmits(sw)}, key=int)
        bodies = {c: parasolid.model(sw, c) for c in configs}
    if not any(bodies.values()):
        sys.exit("no Parasolid bodies (drawings and assemblies keep geometry in the referenced parts)")
    for cfg, ts in bodies.items():
        for i, t in enumerate(ts):
            p = os.path.join(a.outdir, f"config-{cfg}.x_b" if len(ts) == 1 else f"config-{cfg}-{i + 1}.x_b")
            with open(p, "wb") as f:
                f.write(t["data"])
            print(p, t["name"] or "", parasolid.header(t["data"]))


def cmd_index(a):
    out = open(a.output, "w", encoding="utf-8") if a.output else sys.stdout
    n = bad = 0
    for root, _dirs, files in os.walk(a.dir):
        for fn in sorted(files):
            if not fn.lower().endswith(EXTS) or fn.startswith(("~$", "._")):
                continue
            p = os.path.join(root, fn)
            try:
                with open_file(p) as sw:
                    rec = props.summary(sw)
            except Exception as e:                       # keep going: one bad file must not stop an index run
                rec, bad = {"path": p, "error": f"{type(e).__name__}: {e}"}, bad + 1
            out.write(json.dumps(rec, ensure_ascii=False, default=str) + "\n")
            n += 1
    if a.output:
        out.close()
    print(f"{n} documents, {bad} unreadable", file=sys.stderr)


def _object_streams(sw, only=None):
    for n in sw.names():
        if only and n != only:
            continue
        d = sw.read(n)
        if d and (only or find_class_names(d)):
            yield n, d


def cmd_classes(a):
    with open_file(a.file) as sw:
        for n, d in _object_streams(sw, a.section):
            names = find_class_names(d)
            print(f"{n}  ({len(d):,} bytes, {len(names)} classes)")
            for off, c, schema in names:
                print(f"  {off:>10,}  {c}" + (f"  schema {schema}" if schema != 1 else ""))


def cmd_dump(a):
    with open_file(a.file) as sw:
        d = sw.read(a.section)
    if d is None:
        sys.exit(f"no section {a.section!r}")
    print(explore.dump(d, a.start, a.end))


def cmd_summary(a):
    print(export.summary(export.load(a.file)))


def cmd_params(a):
    for p in export.parameters(export.load(a.file)):
        print(f"{p['feature']:<28} {p['name'] or '':<8} {p['text']}")


def cmd_library(a):
    out = open(a.output, "w", encoding="utf-8") if a.output else sys.stdout
    n = 0
    for doc in export.documents(a.dir):
        out.write(json.dumps(export.index_record(doc), ensure_ascii=False) + "\n")
        n += 1
    if a.output:
        out.close()
    print(f"{n} documents", file=sys.stderr)


def main(argv=None):
    ap = argparse.ArgumentParser(prog="swread", description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    s = sub.add_parser("info"); s.add_argument("file"); s.set_defaults(fn=cmd_info)
    s = sub.add_parser("sections"); s.add_argument("file"); s.set_defaults(fn=cmd_sections)
    s = sub.add_parser("extract"); s.add_argument("file"); s.add_argument("outdir"); s.set_defaults(fn=cmd_extract)
    s = sub.add_parser("preview"); s.add_argument("file"); s.add_argument("-o", "--output"); s.set_defaults(fn=cmd_preview)
    s = sub.add_parser("parasolid"); s.add_argument("file"); s.add_argument("outdir"); s.set_defaults(fn=cmd_parasolid)
    s = sub.add_parser("features"); s.add_argument("file"); s.add_argument("--all", action="store_true")
    s.add_argument("--json", action="store_true"); s.set_defaults(fn=cmd_features)
    s = sub.add_parser("index"); s.add_argument("dir"); s.add_argument("-o", "--output"); s.set_defaults(fn=cmd_index)
    s = sub.add_parser("classes"); s.add_argument("file"); s.add_argument("section", nargs="?"); s.set_defaults(fn=cmd_classes)
    s = sub.add_parser("dump"); s.add_argument("file"); s.add_argument("section")
    s.add_argument("--start", type=int, default=0); s.add_argument("--end", type=int); s.set_defaults(fn=cmd_dump)
    s = sub.add_parser("summary"); s.add_argument("file"); s.set_defaults(fn=cmd_summary)
    s = sub.add_parser("params"); s.add_argument("file"); s.set_defaults(fn=cmd_params)
    s = sub.add_parser("library"); s.add_argument("dir"); s.add_argument("-o", "--output"); s.set_defaults(fn=cmd_library)
    a = ap.parse_args(argv)
    try:
        a.fn(a)
    except FormatError as e:
        sys.exit(str(e))


if __name__ == "__main__":
    main()
