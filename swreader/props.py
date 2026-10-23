"""Document-level information: custom properties, mass properties, units, material, configurations and the
assembly component tree. Works for both container kinds (see container.py)."""
from __future__ import annotations

import os
import re
import xml.etree.ElementTree as ET

from . import keywords, propset
from .container import SwFile

VT = "{http://schemas.openxmlformats.org/officeDocument/2006/docPropsVTypes}"
SWNS = "{http://www.solidworks.com/sw2003/schema}"

DOC_TYPES = {".sldprt": "part", ".sldasm": "assembly", ".slddrw": "drawing"}

# SW-MassProp-Config-N: first six values, SI units. The remaining eight are not yet identified.
MASS_FIELDS = ["cx", "cy", "cz", "volume_m3", "area_m2", "mass_kg"]

LINEAR_UNITS = {0: "mm", 1: "cm", 2: "m", 3: "in", 4: "ft", 5: "ft-in", 6: "angstrom", 7: "nm", 8: "micron",
                9: "mil", 10: "microinch"}


def doc_type(sw: SwFile) -> str | None:
    t = DOC_TYPES.get(os.path.splitext(sw.path)[1].lower())
    if t:
        return t
    for name in ("swXmlContents/Features", "swXmlContents/COMPINSTANCETREE"):
        x = sw.read(name)
        m = x and re.search(rb'swDocType="([A-Z]+)"', x)
        if m:
            return m.group(1).decode().lower()
    return None


def _xml_props(data: bytes | None) -> dict:
    """User-defined properties from an OOXML-style custom-properties document."""
    if not data:
        return {}
    root = ET.fromstring(data)
    out = {}
    for sec in root.iter():
        if sec.tag.endswith("propertySection") and sec.get("name") != "UserDefinedProperties":
            continue
        for p in sec.iter():
            if not p.tag.endswith("property") or not p.get("name"):
                continue
            v = next(iter(p), None)
            if v is None:
                continue
            out[p.get("name")] = _vt(v)
    return out


def _vt(el):
    t, s = el.tag.replace(VT, ""), el.text or ""
    if t in ("i1", "i2", "i4", "i8", "int", "ui1", "ui2", "ui4", "ui8", "uint"):
        try:
            return int(s)
        except ValueError:
            return s
    if t in ("r4", "r8", "decimal"):
        try:
            return float(s)
        except ValueError:
            return s
    if t == "bool":
        return s.strip().lower() in ("1", "true", "yes", "-1")
    return s


def custom_properties(sw: SwFile) -> dict:
    """File-level custom properties (File > Properties > Custom)."""
    if sw.kind == "zip":
        return _xml_props(sw.read("docProps/custom.xml"))
    return propset.user_properties(sw.read("\x05DocumentSummaryInformation") or b"")


def config_properties(sw: SwFile) -> dict[str, dict]:
    """Configuration-specific properties, keyed by configuration index ("0", "1", ...)."""
    out = {}
    if sw.kind == "zip":
        for n in sw._cands:
            m = re.fullmatch(r"docProps/Config-(\d+)-Properties\.xml", n)
            if m:
                p = _xml_props(sw.read(n))
                if p:
                    out[m.group(1)] = p
    else:
        for n in sw.names():
            m = re.fullmatch(r"Config-(\d+)-Properties", n)
            if m:
                p = propset.user_properties(sw.read(n) or b"")
                if p:
                    out[m.group(1)] = p
    return out


def sw_information(sw: SwFile) -> dict:
    """The ``SW-*`` system properties (dates, author, units, mass properties per configuration)."""
    if sw.kind == "zip":
        return _xml_props(sw.read("docProps/ISolidWorksInformation.xml"))
    return propset.user_properties(sw.read("ISolidWorksInformation") or b"")


def mass_properties(info: dict) -> dict[str, dict]:
    out = {}
    for k, v in info.items():
        m = re.fullmatch(r"SW-MassProp-Config-(\d+)", k)
        if not m or not isinstance(v, str):
            continue
        try:
            nums = [float(x) for x in v.split(",")]
        except ValueError:
            continue
        d = dict(zip(MASS_FIELDS, nums))
        d["raw"] = nums
        out[m.group(1)] = d
    return out


def units(info: dict) -> dict:
    u = {}
    if isinstance(info.get("SW_UnitsLinear"), int):
        u["linear"] = LINEAR_UNITS.get(info["SW_UnitsLinear"], info["SW_UnitsLinear"])
    if isinstance(info.get("SW_UnitsLinearDecimalPlaces"), int):
        u["decimals"] = info["SW_UnitsLinearDecimalPlaces"]
    if "SW_UnitSystem" in info:
        u["system"] = info["SW_UnitSystem"]
    return u


def materials(sw: SwFile) -> list[dict]:
    raw = sw.read("swXmlContents/MATERIALTREE")
    if not raw:
        return []
    text = raw.decode("utf-16") if raw[:2] in (b"\xff\xfe", b"\xfe\xff") else raw.decode("utf-8", "replace")
    try:
        root = ET.fromstring(text.encode("utf-8").replace(b'encoding="UTF-16"', b""))
    except ET.ParseError:
        return []
    out = []
    for cls in root.iter("classification"):
        for mat in cls.iter("material"):
            phys = {}
            pp = mat.find("physicalproperties")
            for e in (pp if pp is not None else []):
                try:
                    phys[e.tag] = float(e.get("value"))
                except (TypeError, ValueError):
                    pass
            out.append({"classification": cls.get("name"), "name": mat.get("name"), "physical": phys})
    return out


def configurations(sw: SwFile) -> list[dict]:
    for name in ("swXmlContents/Features", "swXmlContents/COMPINSTANCETREE"):
        x = sw.read(name)
        if not x:
            continue
        root = ET.fromstring(x)
        cfgs = [{"name": c.get("swName"), "id": c.get("swID")} for c in root.iter(SWNS + "swConfiguration")]
        if cfgs:
            return cfgs
    return []


def component_tree(sw: SwFile) -> dict | None:
    """Referenced documents and component instances of an assembly (from swXmlContents/COMPINSTANCETREE)."""
    x = sw.read("swXmlContents/COMPINSTANCETREE")
    if not x:
        return None
    root = ET.fromstring(x)
    files = {f.get("id"): {"type": (f.get("swDocType") or "").lower(), "path": f.get("swPath")}
             for f in root.iter(SWNS + "swFile")}
    models = {}
    for m in root.iter(SWNS + "swModel"):
        f = files.get(m.get("swFileRef"), {})
        models[m.get("id")] = {"name": m.get("swName"), "configuration": m.get("swConfigurationName"),
                               "file": f.get("path"), "type": f.get("type"),
                               "bbox": [float(v) for v in m.get("swBoundingBox").split()]
                               if m.get("swBoundingBox") else None,
                               "components": []}
    for m in root.iter(SWNS + "swModel"):
        for r in m.iter(SWNS + "swReference"):
            models[m.get("id")]["components"].append({
                "name": r.get("swComponentName"), "model": models.get(r.get("swModelRef"), {}).get("name"),
                "configuration": r.get("swConfigurationName"),
                "suppressed": r.get("swSuppressed") == "YES", "hidden": r.get("swHidden") == "YES",
                "exclude_from_bom": r.get("swExcludeFromBOM") == "YES"})
    return {"files": list(files.values()), "models": list(models.values())}


def summary(sw: SwFile) -> dict:
    """Everything above in one JSON-ready dict."""
    info = sw_information(sw)
    return {
        "path": sw.path,
        "container": sw.kind,
        "type": doc_type(sw),
        "custom_properties": custom_properties(sw),
        "configuration_properties": config_properties(sw),
        "configurations": configurations(sw),
        "units": units(info),
        "mass_properties": mass_properties(info),
        "materials": materials(sw),
        "components": component_tree(sw),
        "sw_information": {k: v for k, v in info.items() if not k.startswith("SW-MassProp")},
        "has_preview": sw.has("PreviewPNG"),
        "has_parasolid": any(n.endswith("-Partition") and "Ghost" not in n for n in sw.names()),
        "features": _keyword_summary(sw),
    }


def _keyword_summary(sw: SwFile) -> dict | None:
    try:
        kw = keywords.read(sw)
    except ET.ParseError:
        return None
    return keywords.summary(kw) if kw else None
