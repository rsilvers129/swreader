# Roadmap

Two goals share one reader:

* **A. Interoperability** — let other CAD programs read SolidWorks documents (geometry, assemblies, drawings).
* **B. Design learning** — turn a library of real engineering models into data an LLM can learn from: not just the
  final shape but *how* it was built (feature sequence, sketches, dimensions, design intent, tolerances).

## Done (v0.1)
- [x] Both containers (2015+ obfuscated ZIP, pre-2015 OLE), CRC-validated sections, decoy rejection
- [x] Custom / configuration / system properties, units, mass properties, material
- [x] Configurations, assembly component tree
- [x] Preview PNGs (parts, assemblies, drawing sheet 0)
- [x] Parasolid partition extraction
- [x] `swread` CLI (`info`, `sections`, `extract`, `preview`, `parasolid`, `index`)

## Next
1. **Mesh export** (A) — decode `Contents/DisplayLists` → STL / glTF. Fast path to usable geometry.
2. **Serialized-object reader** (A+B) — generic parser for the `moXxx_c` object stream (class table, object
   references, field layout), with a dump tool for exploring unknown classes.
3. **Feature tree** (B) — features in order with type, parameters, sketch entities, constraints and dimensions,
   as JSON. This is the core of goal B.
4. **Drawings** (A+B) — views, dimensions with tolerances / fits, notes, title block, tables; check against the
   drawing's own PDF export.
5. **Parasolid → B-rep → STEP** (A) — parse the transmit file (Siemens XT format reference), build
   OpenCASCADE shapes, write STEP. Check against the document's own STEP export (volume, area, bounding box).
6. **Assembly placement** (A) — component transforms and mates → STEP assembly.
7. **Bindings** (A) — stable Python API, then a C ABI / FreeCAD importer.

## Goal B pipeline (after 3 and 4)
- Per document: properties + material + feature sequence + drawing dimensions/tolerances + preview images.
- Retrieval first: index for an LLM agent ("closest previous design", "how did I do X").
- Then training data: feature sequences rendered as CadQuery/build123d programs (or SolidWorks API macros) paired
  with descriptions, so a local model can learn to generate parametric models the way the engineer built them.
