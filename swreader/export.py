"""Read swexport output (docs/EXPORT.md): design-data JSON per document, plus an export tree with manifest.jsonl.

  load(path)              one document's JSON, format-checked
  documents(root)         every exported document under an export tree
  summary(doc)            a readable design summary (what an engineer would say about the part / drawing)
  parameters(doc)         every dimension with its feature, value in document units and tolerance
  index_record(doc)       a compact search record (for retrieval by an LLM)
"""
from __future__ import annotations

import json
import math
import os

FORMAT = "swexport"
SUPPORTED = {1}

TO_UNIT = {"mm": 1000.0, "cm": 100.0, "m": 1.0, "in": 1 / 0.0254, "ft": 1 / 0.3048, "ft-in": 1 / 0.0254,
           "micron": 1e6, "mil": 1 / 0.0000254, "nm": 1e9}

FEATURE_WORDS = {
    "ProfileFeature": "sketch", "3DProfileFeature": "3D sketch", "Extrusion": "boss-extrude", "Cut": "cut-extrude",
    "Revolution": "revolve", "RevCut": "cut-revolve", "Fillet": "fillet", "VarFillet": "variable fillet",
    "Chamfer": "chamfer", "HoleWzd": "hole (wizard)", "AdvHoleWzd": "advanced hole", "LPattern": "linear pattern",
    "CirPattern": "circular pattern", "MirrorPattern": "mirror", "MirrorSolid": "mirror body", "Shell": "shell",
    "Draft": "draft", "Sweep": "sweep", "SweepCut": "swept cut", "Blend": "loft", "BlendCut": "lofted cut",
    "Helix": "helix", "RefPlane": "plane", "RefAxis": "axis", "RefPoint": "point", "CoordSys": "coordinate system",
    "CosmeticThread": "cosmetic thread", "Thread": "thread",
}

SKIP_TYPES = {"CommentsFolder", "FavoriteFolder", "HistoryFolder", "SelectionSetFolder", "SensorFolder", "DocsFolder",
              "DetailCabinet", "SurfaceBodyFolder", "SolidBodyFolder", "EqnFolder", "MaterialFolder", "InkMarkupFolder",
              "NotesAreaFtrFolder", "OriginProfileFeature", "MateGroup", "Reference"}


class ExportError(ValueError):
    pass


def load(path: str) -> dict:
    with open(path, encoding="utf-8") as f:
        doc = json.load(f)
    if doc.get("format") != FORMAT:
        raise ExportError(f"{path}: not swexport output")
    if doc.get("format_version") not in SUPPORTED:
        raise ExportError(f"{path}: format_version {doc.get('format_version')} not supported (have {sorted(SUPPORTED)})")
    doc["_json_path"] = path
    return doc


def documents(root: str):
    """Yield every exported document (dict) under an export tree, in manifest order when there is a manifest."""
    seen = set()
    man = os.path.join(root, "manifest.jsonl")
    paths = []
    if os.path.exists(man):
        with open(man, encoding="utf-8") as f:
            for line in f:
                try:
                    rec = json.loads(line)
                except ValueError:
                    continue
                for o in rec.get("outputs") or []:
                    if o.endswith(".json"):
                        p = os.path.join(root, os.path.dirname(rec.get("source", "")), o)
                        if p not in seen:
                            seen.add(p)
                            paths.append(p)
    for r, _, fs in os.walk(root):
        for fn in sorted(fs):
            p = os.path.join(r, fn)
            if fn.lower().endswith((".sldprt.json", ".sldasm.json", ".slddrw.json")) and p not in seen:
                seen.add(p)
                paths.append(p)
    for p in paths:
        if os.path.exists(p):
            yield load(p)


# -- units -------------------------------------------------------------------------------------------------------

def unit(doc) -> str:
    return ((doc.get("document") or {}).get("units") or {}).get("length") or "mm"


def fmt_length(v, u):
    if v is None:
        return "?"
    x = v * TO_UNIT.get(u, 1000.0)
    return f"{x:.4f}".rstrip("0").rstrip(".") + (" " + u if u not in ("ft-in",) else " in")


def fmt_angle(v):
    return "?" if v is None else f"{math.degrees(v):.3f}".rstrip("0").rstrip(".") + "°"


def is_angle(d) -> bool:
    # swDimensionType_e: 2 = angular (linear 1? ordinate ...). Fall back to the name/text when unsure.
    if d.get("dimension_type") in (2,):
        return True
    t = " ".join((d.get("text") or {}).values())
    return "°" in t


def fmt_dim(d, u):
    v = d.get("value")
    s = fmt_angle(v) if is_angle(d) else fmt_length(v, u)
    tol = d.get("tolerance")
    if tol:
        k = tol.get("kind")
        if k in ("bilateral", "symmetric", "limit") and tol.get("min") is not None:
            lo, hi = tol.get("min"), tol.get("max")
            if k == "symmetric":
                s += f" ±{fmt_length(abs(hi or 0), u)}"
            else:
                s += f" +{fmt_length(hi or 0, u)}/{fmt_length(lo or 0, u)}"
        elif k and k.startswith("fit"):
            s += " " + " ".join(x for x in (tol.get("hole_fit"), tol.get("shaft_fit")) if x)
        elif k == "basic":
            s = f"[{s}] basic"
    text = d.get("text") or {}
    pre, post = text.get("prefix", ""), text.get("suffix", "")
    return f"{pre}{s}{post}".strip()


# -- accessors ---------------------------------------------------------------------------------------------------

def body(doc) -> dict:
    return doc.get("part") or doc.get("assembly") or doc.get("drawing") or {}


def features(doc) -> list[dict]:
    return [f for f in body(doc).get("features") or [] if f.get("type") not in SKIP_TYPES]


def parameters(doc) -> list[dict]:
    """Every dimension: feature, name, value (document units), tolerance."""
    u, out = unit(doc), []
    for f in features(doc):
        for d in f.get("dimensions") or []:
            out.append({"feature": f.get("name"), "feature_type": f.get("type"), "name": d.get("name"),
                        "full_name": d.get("full_name"), "value": d.get("value"), "text": fmt_dim(d, u),
                        "tolerance": d.get("tolerance")})
    return out


# -- summaries ---------------------------------------------------------------------------------------------------

def _sketch_words(sk) -> str:
    kinds = {}
    for s in sk.get("segments") or []:
        k = s.get("kind", "?")
        if s.get("construction"):
            k = "construction " + k
        if k == "arc" and s.get("circle"):
            k = "circle"
        kinds[k] = kinds.get(k, 0) + 1
    parts = [f"{n} {k}{'s' if n > 1 else ''}" for k, n in sorted(kinds.items())]
    rel = len(sk.get("relations") or [])
    return ", ".join(parts) + (f"; {rel} relations" if rel else "")


def _feature_line(f, u) -> str:
    t = f.get("type") or "?"
    word = FEATURE_WORDS.get(t, t)
    line = f"{f.get('name')} ({word})"
    if f.get("suppressed"):
        line += " [suppressed]"
    d = f.get("definition") or {}
    bits = []
    if t in ("Extrusion", "Cut"):
        if d.get("depth") is not None:
            bits.append("depth " + fmt_length(d["depth"], u))
        if d.get("both_directions"):
            bits.append("both directions")
    if t in ("Revolution", "RevCut") and d.get("angle") is not None:
        bits.append("angle " + fmt_angle(d["angle"]))
    if t in ("Fillet", "VarFillet") and d.get("radius"):
        n = len((d.get("selections") or {}).get("items") or [])
        bits.append("radius " + fmt_length(d["radius"], u) + (f" on {n} edges" if n else ""))
    if t in ("LPattern",) and d.get("count_1"):
        bits.append(f"{d['count_1']} x " + fmt_length(d.get("spacing_1"), u))
    if t in ("CirPattern",) and d.get("count"):
        bits.append(f"{d['count']} instances")
    if t in ("HoleWzd", "AdvHoleWzd"):
        bits.append(" ".join(str(x) for x in (d.get("standard"), d.get("fastener_size")) if x))
    if f.get("sketch"):
        bits.append(_sketch_words(f["sketch"]))
    if f.get("parents") and t not in ("ProfileFeature",):
        bits.append("from " + ", ".join(f["parents"]))
    dims = [f"{x.get('name')}={fmt_dim(x, u)}" for x in f.get("dimensions") or []]
    if dims:
        bits.append("dims " + ", ".join(dims))
    return line + (": " + "; ".join(b for b in bits if b) if bits else "")


def summary(doc) -> str:
    """A readable summary of the document, for people and for LLM retrieval."""
    info, u = doc.get("document") or {}, unit(doc)
    src = (doc.get("source") or {}).get("file") or ""
    cfg = info.get("active_configuration")
    lines = [f"{(info.get('type') or 'document').upper()} {src}  (units {u}" + (f", configuration {cfg}" if cfg else "") + ")"]
    props = info.get("custom_properties") or {}
    if props:
        lines.append("Properties: " + "; ".join(f"{k}={v.get('value', v.get('expression'))}"
                                                for k, v in props.items() if (v.get("value") or v.get("expression"))))
    part = doc.get("part")
    if part:
        m = part.get("material") or {}
        mass = part.get("mass") or {}
        if m.get("name"):
            lines.append(f"Material: {m['name']}")
        if mass.get("mass"):
            lines.append(f"Mass: {mass['mass'] * 1000:.2f} g, volume {mass.get('volume', 0) * 1e6:.3f} cm³")
        bb = part.get("bounding_box")
        if bb and len(bb) == 6:
            lines.append("Size: " + " x ".join(fmt_length(abs(bb[i + 3] - bb[i]), u) for i in range(3)))
    for e in info.get("equations") or []:
        lines.append(f"Equation: {e.get('equation')}")
    feats = features(doc)
    if feats:
        lines.append("Features (in order):")
        lines += [f"  {i + 1}. " + _feature_line(f, u) for i, f in enumerate(feats)]
    asm = doc.get("assembly")
    if asm:
        def walk(cs, depth):
            for c in cs:
                yield depth, c
                yield from walk(c.get("children") or [], depth + 1)
        comps = list(walk(asm.get("components") or [], 0))
        lines.append(f"Components ({len(comps)}):")
        lines += ["  " + "  " * d + f"{c.get('name')}" + (" [suppressed]" if c.get("suppressed") else "")
                  for d, c in comps[:200]]
        mates = asm.get("mates") or []
        if mates:
            lines.append(f"Mates ({len(mates)}): " + ", ".join(
                f"{m.get('kind') or m.get('feature_type')} {'/'.join(e.get('component') or '?' for e in m.get('entities') or [])}"
                for m in mates[:60]))
    drw = doc.get("drawing")
    if drw:
        for sh in drw.get("sheets") or []:
            lines.append(f"Sheet {sh.get('name')} scale {':'.join(str(int(x)) for x in sh.get('scale') or [])}")
            for v in sh.get("views") or []:
                anns = v.get("annotations") or []
                dims = [a["dimension"] for a in anns if a.get("dimension")]
                notes = [(a.get("note") or {}).get("text") for a in anns if a.get("kind") == "note"]
                if v.get("role") == "view":
                    lines.append(f"  View {v.get('name')} ({v.get('kind') or v.get('type')}, {v.get('orientation') or ''}) "
                                 f"of {os.path.basename((v.get('model') or '').replace(chr(92), '/'))}")
                if dims:
                    lines.append("    dims: " + "; ".join(fmt_dim(d, u) for d in dims))
                for a in anns:
                    if a.get("kind") == "gtol":
                        lines.append("    gtol: " + " | ".join(" ".join(map(str, fr.get("values") or []))
                                                         for fr in (a.get("gtol") or {}).get("frames") or []))
                for n in notes:
                    if n and n.strip():
                        lines.append("    note: " + " ".join(n.split()))
                for t in v.get("tables") or []:
                    lines.append(f"    table ({t.get('rows')}x{t.get('columns')}): " +
                                 " / ".join(" | ".join(r) for r in (t.get("cells") or [])[:12]))
    if doc.get("errors"):
        lines.append(f"(export warnings: {len(doc['errors'])})")
    return "\n".join(lines)


def index_record(doc) -> dict:
    """A compact record for a search index."""
    info = doc.get("document") or {}
    part = doc.get("part") or {}
    return {
        "source": (doc.get("source") or {}).get("path"),
        "json": doc.get("_json_path"),
        "type": info.get("type"),
        "title": info.get("title"),
        "units": unit(doc),
        "material": (part.get("material") or {}).get("name"),
        "mass_kg": (part.get("mass") or {}).get("mass"),
        "properties": {k: v.get("value", v.get("expression")) for k, v in (info.get("custom_properties") or {}).items()},
        "feature_types": sorted({f.get("type") for f in features(doc) if f.get("type")}),
        "summary": summary(doc),
    }
