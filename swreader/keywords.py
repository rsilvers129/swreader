"""The keyword index: ``swXmlContents/KeyWords``.

SolidWorks writes an XML index into every document it saves (seen from SolidWorks 2006 / format 4100 on): every
feature, sketch, reference plane, folder, configuration, drawing sheet, view, note and table cell, with its id, name
and type, and the displayed value of every driving dimension. It is not the full parametric definition (no sketch
geometry, no end conditions), but it is reliable, needs no class layouts, and covers every document version.

Two things to know when reading it:

* ``Type`` is the feature's *default name stem* in the language SolidWorks was running in when the file was saved
  ("Fase" for "Fase1" in German, "Chamfer" in English), not a fixed type code. :data:`CANONICAL` maps the stems
  seen so far to one English name (SolidWorks' ``GetTypeName2`` name where there is one); unknown stems are kept
  as stored. In assemblies a component instance appears as a ``Feature`` whose ``Type`` is the component name.
* Items are listed by element kind, then by id - not in feature-tree order. Feature ids grow as features are
  created, so sorting by id gives the creation order.

The document's ``Keywords`` element starts after one byte that is not part of the XML (0x86 or 0x85).
"""
from __future__ import annotations

import re
import xml.etree.ElementTree as ET

SECTION = "swXmlContents/KeyWords"

# stored Type (case-insensitive, either language) -> canonical English type
_NAMES = {
    # modelling features
    "Extrusion": ["Boss-Extrude", "Aufsatz-Linear austragen", "Extrude"],
    "ExtrusionThin": ["Extrude-Thin", "Boss-Extrude-Thin", "Aufsatz-Linear-Austragen-Dünn"],
    "Cut": ["Cut-Extrude", "Schnitt-Linear austragen"],
    "CutThin": ["Cut-Extrude-Thin", "Schnitt-Linear-Austragen-Dünn"],
    "Revolution": ["Revolve", "Rotation", "Aufsatz-Rotation"],
    "RevolutionThin": ["Revolve-Thin", "Rotation-Dünn"],
    "RevCut": ["Cut-Revolve", "Schnitt-Rotation"],
    "RevCutThin": ["Cut-Revolve-Thin", "Schnitt-Rotation-Dünn"],
    "Sweep": ["Sweep", "Austragung", "Aufsatz-Austragung"],
    "SweepCut": ["Cut-Sweep", "Schnitt-Austragung"],
    "Blend": ["Loft", "Ausformung", "Aufsatz-Ausformung"],
    "BlendCut": ["Cut-Loft", "Schnitt-Ausformung"],
    "Fillet": ["Fillet", "Verrundung", "VarFillet", "Variable Verrundung", "Face Fillet", "Flächenverrundung"],
    "Chamfer": ["Chamfer", "Fase"],
    "Shell": ["Shell", "Wandung"],
    "Draft": ["Draft", "Formschräge"],
    "Rib": ["Rib", "Rippe"],
    "Wrap": ["Wrap", "Umwickeln"],
    "Dome": ["Dome", "Kuppel"],
    "HoleWzd": ["Hole Wizard", "Bohrungsassistent"],
    "AdvHoleWzd": ["Advanced Hole", "Erweiterte Bohrung"],
    "Thread": ["Thread", "Gewinde"],
    "CosmeticThread": ["Cosmetic Thread", "Gewindedarstellung"],
    "HoleThread": ["Hole Thread", "Bohrungsgewinde"],
    "LPattern": ["LPattern", "Lineares Muster"],
    "CirPattern": ["CirPattern", "Kreismuster"],
    "LocalLPattern": ["LocalLPattern", "Lokales lineares Muster"],
    "LocalCirPattern": ["LocalCirPattern", "Lokales Kreismuster"],
    "CurvePattern": ["Curve Driven Pattern", "Kurvenmuster"],
    "FillPattern": ["Fill Pattern", "Füllmuster"],
    "MirrorPattern": ["Mirror", "Spiegeln"],
    "MirrorComponent": ["MirrorComponent"],
    "Combine": ["Combine", "Kombinieren"],
    "Join": ["Join", "Vereinigen"],
    "MoveCopyBody": ["Body-Move/Copy", "Körper-Verschieben/Kopieren"],
    "BodyDelete": ["Body-Delete/Keep", "Körper-Löschen/Behalten"],
    "Split": ["Split", "Trennen"],
    "SplitLine": ["Split Line", "Trennlinie"],
    "MoveFace": ["Move Face", "Fläche verschieben"],
    "DeleteFace": ["DeleteFace", "Delete Face", "Fläche löschen"],
    "Imported": ["Imported", "Importiert", "Surface-Imported", "Oberfläche-Importiert", "Multi_CAD_Imported"],
    "Helix": ["Helix/Spiral", "Spirale/Helix"],
    "CompositeCurve": ["CompCurve", "ZusammengKurve"],
    "SurfaceOffset": ["Surface-Offset", "Oberfläche-Versatz"],
    "SurfaceKnit": ["Surface-Knit", "Oberfläche-Zusammenfügen"],
    "SurfaceCut": ["SurfaceCut", "Oberflächenschnitt"],
    "SurfaceExtrude": ["Surface-Extrude", "Oberfläche-Linear austragen"],
    "SurfaceRevolve": ["Surface-Revolve", "Oberfläche-Rotation"],
    "SurfaceSweep": ["Surface-Sweep", "Oberfläche-Austragung"],
    "SurfaceLoft": ["Surface-Loft", "Oberfläche-Ausformung"],
    "SurfaceFill": ["Surface-Fill", "Oberfläche-Füllen"],
    "SurfacePlane": ["Surface-Plane", "Oberfläche-Eben"],
    "Thicken": ["Thicken", "Aufdicken"],
    "ThickenCut": ["Cut-Thicken", "Schnitt-Aufdicken"],
    "ConvertSolid": ["Convert-Solid"],
    "SheetMetal": ["Sheet-Metal", "Blech"],
    "EdgeFlange": ["Edge-Flange", "Kantenlasche"],
    "EdgeBend": ["EdgeBend", "Kantenbiegung"],
    "BaseFlange": ["Base-Flange", "Basislasche"],
    "MirrorBend": ["MirrorBend"],
    "JogBend": ["JogBend", "Versatz"],
    "SketchBend": ["SketchBend", "Skizzierte Biegung"],
    "Flatten": ["Flatten"],
    "BaseBody": ["Basisteil", "Base-Part", "Base Part"],        # derived / inserted part
    "FreezeBar": ["Freeze"],
    "FlatPattern": ["Flat-Pattern", "Abwicklung"],
    "SketchPicture": ["Sketch Picture", "Skizzenbild"],
    "SketchTransform": ["Sketch Transformation"],
    # reference geometry
    "RefPlane": ["Plane", "Ebene"],
    "RefAxis": ["Axis", "Achse"],
    "RefPoint": ["Point", "Punkt"],
    "CoordSys": ["Coordinate System", "Koordinatensystem"],
    "RefCurve": ["Curve", "Kurve"],
    # tree folders and system items
    "OriginProfileFeature": ["Origin", "Ursprung"],
    "CommentsFolder": ["Comments", "Kommentare"],
    "DesignBinder": ["Design Binder", "Konstruktionsordner"],
    "SensorFolder": ["Sensors", "Sensoren"],
    "DetailCabinet": ["Annotations", "Beschriftungen", "Beschriftung"],
    "EqnFolder": ["Equations", "Gleichungen"],
    "MaterialFolder": ["SOLIDWORKS Materials", "SolidWorks Materials", "SOLIDWORKS Materialien",
                       "SolidWorks Materialien", "Material"],
    "FavoriteFolder": ["Favorites", "Favoriten"],
    "HistoryFolder": ["History", "Historie"],
    "SelectionSetFolder": ["Selection Sets", "Auswahlsätze"],
    "InkMarkupFolder": ["Markups", "Markierungen"],
    "NotesAreaFtrFolder": ["Notes", "Hinweise"],
    "TableFolder": ["Tables", "Tabellen"],
    "SolidBodyFolder": ["Solid Bodies", "Volumenkörper"],
    "SurfaceBodyFolder": ["Surface Bodies", "Oberflächenkörper"],
    "GraphicsBodyFolder": ["Graphics Bodies", "Grafikkörper"],
    "CurvesFolder": ["Curves", "Kurven"],
    "ExplodeFolder": ["Exploded Views", "Aufgelöste Ansichten"],
    "EnvFolder": ["Lights, Cameras and Scene", "Lights and Cameras", "Beleuchtung, Kameras und Bühne"],
    "AmbientLight": ["Ambient", "Umgebungslicht"],
    "DirectionLight": ["Directional", "Gerichtet"],
    "SpotLight": ["Spot"],
    "SheetMetalMaster": ["Sheet-Metal Master"],
    "LiveSectionFolder": ["Live Section Planes", "Aktivierte Schnittebenen"],
    "FtrFolder": ["Folder", "Ordner"],
    "DesignTable": ["Excel Design Table", "Excel-Konstruktionstabelle"],
    "ConfigTable": ["Configuration Table", "Konfigurationstabelle", "Config Table"],
    "ConfigCommentsFolder": ["Configuration Comments", "Konfigurationskommentare"],
    "AttributeDef": ["Attribute-Definition", "Attribut-Definition"],
    "Attribute": ["Attribute"],
    "Sensor": ["Masse", "Volumen", "Mass", "Volume"],
    "PlanesFolder": ["Planes", "Ebenen"],
    "AxesFolder": ["Axes", "Achsen"],
    "SketchesFolder": ["Sketches", "Skizzen"],
    "CutListFolder": ["Cut list", "Zuschnittsliste"],
    "CutListItem": ["Cut-List-Item"],
    # assemblies
    "MateGroup": ["Mates", "Verknüpfungen"],
    "MateCoincident": ["Coincident", "Deckungsgleich"],
    "MateConcentric": ["Concentric", "Konzentrisch"],
    "MateDistance": ["Distance", "Abstand", "LimitDistance"],
    "MateParallel": ["Parallel"],
    "MateTangent": ["Tangent", "Tangential"],
    "MateAngle": ["Angle", "Winkel"],
    "MateReferences": ["MateReferences"],
    "ExplodeStep": ["Explode Step", "Explosionsstufe"],
    "ExplodeView": ["ExplView", "Exploded View", "Explodierte Ansicht", "Explosionsansicht"],
    "InContextFeature": ["InContextFeature"],
    "Simulation": ["Simulation"],
    # drawings
    "DetailFolder": ["Detail Folder", "Detailordner"],
    "AlignGroup": ["AlignGroup", "AusrichtungGruppe"],
    "SectionLine": ["Section Line", "Schnittlinie"],
    "DetailCircle": ["Detail Circle", "Detailkreis"],
    "BreakLine": ["Break Line", "Bruchlinie"],
    "BrokenOutSection": ["Broken-out Section", "Ausbruch"],
    "ViewArrow": ["View Arrow", "Ansicht Pfeil"],
    "BomAnchor": ["Bill of Materials Anchor", "Verankerung Stückliste"],
    "HoleTableAnchor": ["Hole Table Anchor", "Verankerungspunkt für Bohrungstabelle"],
    "RevisionTableAnchor": ["Revision Table Anchor", "Verankerungspunkt für Versionstabelle"],
    "GeneralTableAnchor": ["General Table Anchor", "Verankerungspunkte für allgemeine Tabelle"],
    "WeldmentTableAnchor": ["Weldment Cut List Anchor", "Verankerungspunkt für Schweißkonstruktions-Zuschnittsliste"],
    "WeldTableAnchor": ["Weld Table Anchor", "Schweißnaht-Tabellenverankerungspunkt"],
    "BendTableAnchor": ["Bend Table Anchor", "Verankerungspunkt für Biegetabelle"],
    "PunchTableAnchor": ["Punch Table Anchor", "Verankerungspunkt für Stanztabelle"],
    "FamilyTableAnchor": ["Family Table Anchor"],
    "TitleBlockTable": ["Title Block Table"],
    "BomTable": ["Bill of Materials", "Stückliste"],
    "RevisionTable": ["Revision Table", "Versionstabelle"],
    "GeneralTable": ["Tabelle", "Table"],
    "Sheet": ["Sheet", "Blatt"],
    "SheetFormat": ["Sheet Format", "Blattformat"],
    "SectionView": ["Section", "Schnitt"],
    "Block": ["Block"],
    "Group": ["Group", "Gruppe"],
    "Chain": ["Chain", "Kette"],
    "Graphic": ["Graphic"],
    "PenSketch": ["Pen Sketch"],
}
CANONICAL: dict[str, str] = {}
for _canon, _stored in _NAMES.items():
    for _s in _stored:
        CANONICAL[_s.lower()] = _canon

# canonical types that are tree folders, lights, anchors and other bookkeeping - not modelling steps
NON_MODELLING = {
    "OriginProfileFeature", "CommentsFolder", "DesignBinder", "SensorFolder", "DetailCabinet", "EqnFolder",
    "MaterialFolder", "FavoriteFolder", "HistoryFolder", "SelectionSetFolder", "InkMarkupFolder",
    "NotesAreaFtrFolder", "TableFolder", "SolidBodyFolder", "SurfaceBodyFolder", "GraphicsBodyFolder",
    "CurvesFolder", "ExplodeFolder", "EnvFolder", "AmbientLight", "DirectionLight", "SpotLight",
    "SheetMetalMaster", "LiveSectionFolder", "FtrFolder", "ConfigCommentsFolder", "AttributeDef", "Attribute",
    "Sensor", "PlanesFolder", "AxesFolder", "SketchesFolder", "CutListFolder", "CutListItem", "MateGroup",
    "DetailFolder", "AlignGroup", "BomAnchor", "HoleTableAnchor", "RevisionTableAnchor", "GeneralTableAnchor",
    "WeldmentTableAnchor", "WeldTableAnchor", "BendTableAnchor", "PunchTableAnchor", "FamilyTableAnchor",
    "Group", "Graphic", "DesignTable", "ConfigTable", "Simulation",
}

# element kinds that are themselves the type (the Type attribute, when present, is a name stem)
_KIND_TYPES = {"Extrusion": "Extrusion", "Cut": "Cut", "HoleWizard": "HoleWzd", "Sketch": "ProfileFeature",
               "Block": "Block", "Table": "GeneralTable", "Sheet": "Sheet", "Configuration": "Configuration",
               "Reference": "Reference"}


def canonical(kind: str, stored: str | None) -> str | None:
    """English type for an item: from its stored Type (either language), else from its element kind."""
    if stored:
        c = _lookup(stored)
        if c:
            return c
        if kind == "Extrusion" and stored.lower().startswith(("schnitt", "cut")):
            return "Cut"
    return _KIND_TYPES.get(kind)


_NUM = re.compile(r"[-+]?\d+(?:[.,]\d+)?(?:[eE][-+]?\d+)?")


def dimension(name: str, text: str | None) -> dict:
    """{name, text, value, kind} for one dimension's displayed text ('R2', '<MOD-DIAM>62', '45°', '(16)')."""
    t = (text or "").strip()
    out = {"name": name, "text": t, "display": t.replace("<MOD-DIAM>", "Ø")}
    s = t
    if s.startswith("(") and s.endswith(")"):
        out["reference"] = True                       # a driven (reference) dimension
        s = s[1:-1]
    kind = "length"
    if "<MOD-DIAM>" in s:
        kind, s = "diameter", s.replace("<MOD-DIAM>", "")
    elif re.match(r"^R\s*\d", s):
        kind, s = "radius", s[1:]
    if "°" in s:
        kind = "angle"
    m = _NUM.search(s)
    if m:
        out["value"] = float(m.group(0).replace(",", "."))
    out["kind"] = kind
    return out


def _stem(name: str | None) -> str | None:
    """'Schnitt-Linear austragen12' -> 'Schnitt-Linear austragen' (default feature names end in a number)."""
    if not name:
        return None
    m = re.fullmatch(r"(.*?\D)\d+", name.strip())
    return m.group(1) if m else None


def _lookup(stored: str) -> str | None:
    s = stored.strip().lower()
    if s in CANONICAL:
        return CANONICAL[s]
    s = re.sub(r"[-<].*$", "", s).rstrip("*").strip()      # 'Flatten-<Kantenbiegung2>', 'Freeze***'
    return CANONICAL.get(s)


def _item(e) -> dict:
    a = dict(e.attrib)
    it = {"kind": e.tag}
    if "id" in a:
        v = a.pop("id")
        try:
            it["id"] = int(v)
        except ValueError:
            it["id"] = v or None
    for k in ("Name", "Type", "Description"):
        if k in a:
            it[k.lower()] = a.pop(k)
    c = canonical(e.tag, it.get("type") or _stem(it.get("name")))
    if c:
        it["canonical"] = c
    if a:
        it["attributes"] = a
    text = (e.text or "").strip()
    if text:
        it["text"] = e.text
    dims, kids = [], []
    for ch in e:
        if ch.tag == "Dimension":
            dims.append(dimension(ch.get("Name", ""), ch.text))
        else:
            kids.append(_item(ch))
    if dims:
        it["dimensions"] = dims
    if kids:
        it["children"] = kids
    return it


def parse(data: bytes) -> dict:
    """Parse the section's bytes."""
    i = data.find(b"<?xml")
    root = ET.fromstring(data[i if i >= 0 else 0:])
    out = {"id": root.get("id"), "name": root.get("Name"), "configurations": [], "items": []}
    for e in root:
        if e.tag == "Configuration":
            c = {k.lower(): v for k, v in e.attrib.items() if k != "Type"}
            if "id" in c:
                try:
                    c["id"] = int(c["id"])
                except ValueError:
                    pass
            out["configurations"].append(c)
        else:
            out["items"].append(_item(e))
    return out


def read(sw) -> dict | None:
    """The keyword index of an open document, or None when it has none."""
    d = sw.read(SECTION)
    return parse(d) if d else None


def features(kw: dict, modelling_only: bool = False) -> list[dict]:
    """Features and sketches in creation (id) order. With modelling_only: without folders, lights, anchors,
    attributes, the origin and the default planes (the planes created before the origin, whatever their names)."""
    origin = min((it["id"] for it in kw["items"] if it.get("canonical") == "OriginProfileFeature"
                  and isinstance(it.get("id"), int) and it["id"] >= 0), default=None)
    out = []
    for it in kw["items"]:
        if it["kind"] not in ("Feature", "Sketch", "Extrusion", "Cut", "HoleWizard", "Block"):
            continue
        if not isinstance(it.get("id"), int) or it["id"] < 0:
            continue
        if modelling_only:
            c = it.get("canonical")
            if c in NON_MODELLING or c == "OriginProfileFeature":
                continue
            if c == "RefPlane" and origin is not None and it["id"] < origin:
                continue
        out.append(it)
    return sorted(out, key=lambda x: x["id"])


def summary(kw: dict) -> dict:
    """Counts for an index: items per canonical type, modelling features, sketches, dimensions."""
    import collections
    types = collections.Counter()
    for it in features(kw, modelling_only=True):
        types[it.get("canonical") or it.get("type") or it["kind"]] += 1
    n_dims = sum(len(it.get("dimensions", [])) for it in kw["items"])
    return {"modelling_features": sum(v for k, v in types.items() if k != "ProfileFeature"),
            "sketches": types.get("ProfileFeature", 0), "dimensions": n_dims, "types": dict(types.most_common())}
