"""swread - read SolidWorks documents without SolidWorks.

  swread info FILE                 JSON summary (properties, mass, material, configurations, components)
  swread sections FILE             list the document's sections and their sizes
  swread extract FILE OUTDIR       write every section to OUTDIR (wrapped streams inflated)
  swread preview FILE [-o X.png]   the embedded 640x480 preview (for a drawing: the first sheet)
  swread parasolid FILE OUTDIR     each configuration's Parasolid partition as config-N.x_b
  swread index DIR [-o X.jsonl]    `info` for every document under DIR, one JSON line each
"""
from __future__ import annotations

import argparse
import json
import os
import sys

from . import parasolid, props
from .container import FormatError, open_file, unwrap

EXTS = (".sldprt", ".sldasm", ".slddrw")


def _safe(name: str) -> str:
    return "".join(c if c.isalnum() or c in "-_.[]" else "_" for c in name.replace("/", "__"))


def cmd_info(a):
    with open_file(a.file) as sw:
        json.dump(props.summary(sw), sys.stdout, indent=2, ensure_ascii=False, default=str)
        print()


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
        parts = parasolid.partitions(sw)
    if not parts:
        sys.exit("no Parasolid partition (drawings and assemblies keep geometry in the referenced parts)")
    for cfg, ps in sorted(parts.items(), key=lambda kv: int(kv[0])):
        p = os.path.join(a.outdir, f"config-{cfg}.x_b")
        with open(p, "wb") as f:
            f.write(ps)
        print(p, parasolid.header(ps))


def cmd_index(a):
    out = open(a.output, "w", encoding="utf-8") if a.output else sys.stdout
    n = bad = 0
    for root, _dirs, files in os.walk(a.dir):
        for fn in sorted(files):
            if not fn.lower().endswith(EXTS) or fn.startswith("~$"):
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


def main(argv=None):
    ap = argparse.ArgumentParser(prog="swread", description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    s = sub.add_parser("info"); s.add_argument("file"); s.set_defaults(fn=cmd_info)
    s = sub.add_parser("sections"); s.add_argument("file"); s.set_defaults(fn=cmd_sections)
    s = sub.add_parser("extract"); s.add_argument("file"); s.add_argument("outdir"); s.set_defaults(fn=cmd_extract)
    s = sub.add_parser("preview"); s.add_argument("file"); s.add_argument("-o", "--output"); s.set_defaults(fn=cmd_preview)
    s = sub.add_parser("parasolid"); s.add_argument("file"); s.add_argument("outdir"); s.set_defaults(fn=cmd_parasolid)
    s = sub.add_parser("index"); s.add_argument("dir"); s.add_argument("-o", "--output"); s.set_defaults(fn=cmd_index)
    a = ap.parse_args(argv)
    try:
        a.fn(a)
    except FormatError as e:
        sys.exit(str(e))


if __name__ == "__main__":
    main()
