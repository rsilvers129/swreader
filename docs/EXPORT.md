# swexport output format (format_version 1)

`swexport` (Windows, needs SolidWorks) converts a folder of SolidWorks documents into an **export tree**: the same
folder structure, with open-format files per document and a manifest.

```
<input>-export/
  manifest.jsonl                  one line per exported document (status, outputs, seconds, warnings)
  Bracket.SLDPRT.json             design data (this document)
  Bracket.step                    geometry (parts, assemblies)
  Bracket.stl                     with --stl (parts)
  Bracket.SLDDRW.json
  Bracket.pdf                     all sheets (drawings)
  Bracket-Sheet1.dxf              with --dxf, one per sheet (drawings)
```

The `swread` side of this repository reads export trees (`swreader.export`), so the design data can be searched,
summarised, and fed to an LLM, and the Fusion add-in (`fusion/`) rebuilds parts from it.

## Conventions

* **Units:** all lengths in **metres**, angles in **radians**, mass in kilograms (SolidWorks system units).
  `document.units.length` is the document's display unit (`in`, `mm` ...), for presentation only.
* **Coordinates:** model space unless stated. Sketch geometry is sketch space (z = 0 for 2D sketches).
* **Transforms:** SolidWorks MathTransform arrays (16 numbers): rotation 3x3 (row-major `[0..8]`), translation
  `[9..11]`, scale `[12]`, `[13..15]` unused. `sketch.model_to_sketch` maps model to sketch coordinates; component
  `transform` maps component to assembly coordinates.
* **Enumerations:** the raw SolidWorks value is always present (`type`); a readable `kind` is added where known.
* **Missing data:** keys whose value could not be read are omitted. Problems are listed in `errors`
  (`{"where", "message"}`); a document with errors is still exported (`manifest status: ok_with_warnings`).
* **Sketch entity ids:** `"a-b"` from SolidWorks' `GetID()`; unique within a sketch and used by relations and by
  dimension `attached` lists.

## Top level

```json
{
  "format": "swexport", "format_version": 1,
  "exporter": {"name": "swexport", "version": "1.0.1", "solidworks": "34.1.0", "exported_utc": "..."},
  "source": {"path": "...", "file": "Bracket.SLDPRT", "bytes": 123456, "modified_utc": "..."},
  "document": { ... },
  "part": { ... } | "assembly": { ... } | "drawing": { ... },
  "outputs": ["Bracket.step", "Bracket.SLDPRT.json"],
  "errors": []
}
```

### document

| key | |
|---|---|
| `type` | `part`, `assembly`, `drawing` |
| `title`, `active_configuration` | |
| `units` | `{values, length, decimals}` |
| `custom_properties` | `{name: {expression, value}}` (`value` only when it differs from the expression) |
| `configurations` | `[{name, description, comment, derived, parent, custom_properties}]` |
| `equations` | `[{equation, value, global_variable, suppressed}]` |

### part

| key | |
|---|---|
| `material` | `{name, database}` |
| `mass` | `{mass, volume, surface_area, density, center_of_mass[3], moments_of_inertia[9]}` |
| `bounding_box` | `[xmin, ymin, zmin, xmax, ymax, zmax]` |
| `bodies` | `[{name, faces, edges, box}]` |
| `features` | the feature tree in history order (below) |

### feature

```json
{
  "index": 12, "name": "Boss-Extrude1", "type": "Extrusion", "id": 25, "suppressed": false,
  "created": "...", "modified": "...", "owner": null,
  "parents": ["Sketch1"], "children": ["Fillet1"], "sub_features": ["Sketch1"],
  "dimensions": [ <dimension> ],
  "definition": { "end_condition": 0, "depth": 0.0254, ..., "selections": { ... } },
  "sketch": { ... },              // only for ProfileFeature / 3DProfileFeature
  "result_faces": [ <face> ]      // fillet, chamfer, shell, draft, hole: the faces the feature made
}
```

* `type` is SolidWorks' `GetTypeName2` (`ProfileFeature` = sketch, `Extrusion` = boss-extrude, `Cut`, `Revolution`,
  `RevCut`, `Fillet`, `Chamfer`, `HoleWzd`, `LPattern`, `CirPattern`, `MirrorPattern`, `Shell`, `Draft`, `Sweep`,
  `Blend` (loft), `Helix`, `RefPlane`, `RefAxis`, `CosmeticThread` ...).
* `owner`: the feature that absorbed this one (a sketch absorbed by its extrude).
* `definition`: parameters read from the feature's definition object; which keys appear depends on the type
  (see `swexport/src/Definitions.cs`). Driving values are always also in `dimensions`.
* `definition.selections`: the entities the feature uses (revolve axis, filleted edges, pattern direction, mirror
  plane, up-to surface ...), each an [entity](#entity).
* `RefPlane` / `CoordSys`: `definition.transform`; `RefAxis`: `definition.axis` (start xyz, end xyz).

### dimension

```json
{
  "name": "D1", "full_name": "D1@Sketch1@Bracket.SLDPRT", "value": 0.0254, "display_value": 1.0,
  "dimension_type": 2, "driven_state": 2, "read_only": false,
  "tolerance": {"type": 2, "kind": "bilateral", "min": -0.0001, "max": 0.0001, "hole_fit": "H7"},
  "text": {"prefix": "2X ", "callout_below": "THRU"},
  "attached": [ <entity>, <entity> ],
  "position": [x, y, z],          // drawings: annotation position on the sheet
  "by_configuration": {"Default": 0.0254, "Long": 0.0508}    // with --all-configs
}
```

### sketch

```json
{
  "is_3d": false, "model_to_sketch": [16 numbers],
  "plane": <entity>, "plane_entity_type": 4,
  "points":   [{"id": "1-2", "xyz": [x, y, z]}],
  "segments": [{"id": "2-7", "kind": "line", "type": 0, "construction": false, "length": 0.01,
                "start": <point>, "end": <point>}],
  "relations": [{"type": 4, "kind": "horizontal", "entities": [<entity>], "entity_types": [1]}]
}
```

Segment kinds: `line` (start, end), `arc` (center, start, end, radius, circle, direction: 1 = CCW, -1 = CW),
`ellipse` (center, major, minor, start, end), `spline` (points, params), `text` (text), `parabola` (focus, apex,
start, end).

### entity

A reference to geometry, described so it can be found again in another CAD system:

| kind | fields |
|---|---|
| `sketch_point`, `sketch_segment` | `id` |
| `edge` | `curve` (`line`, `circle`, `ellipse`, `other`), `start`, `end`, `mid`; circles: `center`, `axis`, `radius` |
| `face` | `surface` (`plane`, `cylinder`, `cone`, ...), `box`, `point` (on the face), `normal` (planes), `axis_origin`/`axis`/`radius` (cylinders), `area` |
| `vertex` | `point` |
| `feature` | `name`, `type` (a plane, axis or other feature used as a reference) |

### assembly

| key | |
|---|---|
| `components` | tree: `[{name, path, configuration, suppressed, hidden, fixed, virtual, envelope, exclude_from_bom, transform, children}]` |
| `mates` | `[{name, feature_type, type, kind, alignment, suppressed, dimensions, entities: [{component, reference_type, params, entity}]}]` |
| `mass` | as for parts |
| `features` | assembly-level features (planes, sketches, assembly cuts, patterns) |

### drawing

```json
{"sheets": [{
  "name": "Sheet1", "template": "...", "scale": [1, 2], "first_angle": false, "size": [0.432, 0.279],
  "views": [{
    "name": "Drawing View1", "role": "view", "type": 7, "kind": "named",
    "scale": [1, 1], "position": [x, y], "outline": [x1, y1, x2, y2], "orientation": "*Front",
    "model": "C:\\...\\Bracket.SLDPRT", "configuration": "Default", "base_view": null,
    "annotations": [
      {"kind": "dimension", "type": 4, "position": [...], "text": [...], "dimension": <dimension>},
      {"kind": "note", "text": [...], "note": {"text": "BREAK ALL EDGES", "balloon": false}},
      {"kind": "gtol", "gtol": {"frames": [{"values": [...], "symbols": [...]}]}},
      {"kind": "datum_tag", "datum": "A"}
    ],
    "tables": [{"type": 2, "title": null, "rows": 5, "columns": 4, "cells": [["ITEM NO.", "PART NUMBER", ...], ...]}]
  }]
}]}
```

The first view of every sheet has `role: "sheet"`: it holds the sheet-format annotations (title block notes).
