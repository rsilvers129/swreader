# Guide for AI agents working on swreader

You are helping build tools that get engineering data out of SolidWorks: a native file reader (`swreader`), a
SolidWorks-side batch exporter (`swexport`), and a Fusion add-in that rebuilds parts feature by feature
(`fusion/SwRebuild`). Work like a careful engineer who knows **both** SolidWorks and Fusion: look things up, change one
thing at a time, prove every change with numbers, and hand your work back for review.

Read this whole guide before you start. Then read the documents in **Step 1** before you write any code.

---

## Step 1 - read first (every session)

### 1.1 This repository
1. `README.md` - the three tools and the three goals.
2. `docs/ROADMAP.md` - what is done and what is next.
3. `docs/FORMAT.md` - what is known about the native SolidWorks file format (containers, MFC object streams).
4. `docs/EXPORT.md` - the JSON that swexport writes (and SwRebuild and `swread summary` read).
5. `HANDOFF.md` at the repository root if it exists - notes from the previous session.

### 1.2 The SolidWorks and Fusion documentation (`/reference/cad`)
The official documentation is mirrored as Markdown. **It is the only source of truth for API names, signatures and
enumeration values.** Your memory of these APIs is often wrong; the docs are not.

| what | where |
|---|---|
| how the mirror is organised | `/reference/cad/README.md` (read it) |
| page index (one line per page: path, title, breadcrumb) | `/reference/cad/solidworks/index.tsv`, `/reference/cad/fusion/index.tsv` |
| SolidWorks API: interfaces and members | `/reference/cad/solidworks/md/api/sldworksapi/` |
| SolidWorks enumerations (`swEndConditions_e` ...) | `/reference/cad/solidworks/md/api/swconst/` |
| SolidWorks API programming guide | `/reference/cad/solidworks/md/api/sldworksapiprogguide/` |
| SolidWorks user manual (features, sketches, end conditions) | `/reference/cad/solidworks/md/help/sldworks/` |
| **Fusion API - authoritative signatures** | `/reference/cad/fusion/api-stubs-*/python/fusion.py`, `core.py` |
| Fusion API pages, User's Manual (`*_UM.md`), samples (`*_Sample.md`) | `/reference/cad/fusion/md/Fusion-360-API/files/` |
| Fusion user manual (Model, Sketch, ...) | `/reference/cad/fusion/md/Fusion-*/` |

How to look something up:

```
grep -i "extrude feature data" /reference/cad/solidworks/index.tsv | head        # find pages by title
less /reference/cad/solidworks/md/api/sldworksapi/<page>.md                      # read one
python3 devtools/check_api.py member IExtrudeFeatureData2 GetDepth                # a SolidWorks signature
python3 devtools/check_api.py enum swEndConditions_e                              # enumeration values
python3 devtools/check_api.py fsig ExtrudeFeatureInput setOneSideExtent           # a Fusion signature + docs
grep -n "def addPerpendicular" /reference/cad/fusion/api-stubs-*/python/fusion.py # search the Fusion stubs
```

Pages to read once, early (find them with `grep -i '<title words>' index.tsv`):

* SolidWorks API guide: *Accessing Selections that Define Features*, units (the API uses **metres and radians**),
  traversing features (`IModelDoc2.FirstFeature`, `IFeature.GetNextFeature`, sub-features), `IFeature.GetDefinition`
  and the feature data objects (`IExtrudeFeatureData2`, `IRevolveFeatureData2`, `ISimpleFilletFeatureData2`, ...),
  `ISketch`, `ISketchSegment`, `ISketchRelationManager`, `IDisplayDimension`, `IDimension`, `IDimensionTolerance`.
* SolidWorks user manual: extrude end conditions, revolve, fillet, chamfer, Hole Wizard, linear/circular pattern,
  mirror, sketch relations - so you know what each parameter *means* to an engineer.
* Fusion API User's Manual: units (**Fusion's API uses centimetres**), sketches and profiles, the timeline and
  parametric design, B-rep (bodies, faces, edges), and the samples for extrude, revolve, fillet, chamfer, holes,
  patterns, mirror and sketch constraints/dimensions.
* Fusion user manual (Model and Sketch books): how a Fusion user builds the same features.

---

## Step 2 - rules (always)

1. **Never guess an API member or enumeration value.** Look it up (Step 1.2). Before committing changes to
   `swexport/` run `python3 devtools/check_api.py sw`; to `fusion/` run `python3 devtools/check_api.py fusion`.
   Both must report 0 problems.
2. **Never commit CAD data** or anything derived from real documents (no `.SLDPRT/.SLDASM/.SLDDRW`, STEP, PDF,
   images, exports, extracted sections, part names or dimension values from real files). `.gitignore` blocks most of
   it; you are responsible for the rest. Tests use the hand-written examples in `tests/data/` only.
3. **Tests must pass** before every commit:
   `.venv/bin/pytest -q` and `SWREADER_SAMPLES=/solidworks/samples .venv/bin/pytest -q`.
4. **Prove every change with numbers.** "It works" is not a result; "walkall: 1306 -> 1412 parts reach sgPointHandle,
   0 regressions" is.
5. **One change at a time**, one commit per change, with a message that says what and why. Commit locally only -
   **do not push**; the owner reviews and pushes.
6. **Do not edit the real documents** (`/solidworks` is read-only anyway) and do not delete anything you did not
   create.
7. When you are stuck for more than ~30 minutes on one thing, stop: write what you tried and what you saw into
   `HANDOFF.md` and move to the next item.
8. End every session by updating `HANDOFF.md` (what you did, the numbers, what is next, open questions). It is not
   committed.

---

## Step 3 - set up (once)

```
cd /work/swreader
python3 -m venv .venv && .venv/bin/pip install -e '.[test]'
.venv/bin/pytest -q
SWREADER_SAMPLES=/solidworks/samples .venv/bin/pytest -q      # ~3000 real documents, ~10 s
```

`/solidworks/samples` holds real SolidWorks documents (read-only) from versions 2001 to 2026; `THIS-ONE-LVAW` is a
large 2011-2014 project and the main corpus.

---

## Workflow A - decode the native format (main task)

The feature tree, sketches and dimensions live in MFC object streams (`docs/FORMAT.md` §4). Each class's field
layout has to be worked out from the bytes, per SolidWorks version, and written into `swreader/classes.py`.

### A.1 Background you need
* **MFC CArchive** (FORMAT.md §4): every object starts with a tag - `FF FF` + schema + name = a new class;
  `0x8000|i` = a new object of an already-seen class; other values = a reference to an earlier object. Map
  indices count every new class **and** every new object, in order. One byte wrong anywhere breaks everything after.
* **Versions**: the document version is the `_MO_VERSION_<n>` section name (4400, 4700, 5000, 6000, 7000, 10000,
  16000, 18000 ...). Layouts differ by version - always gate with `r.version` (see `_by_version` and `stamps()`).
* **Shared feature base** (`classes.feature`): node name (`moNodeName_c`), version stamps (SolidWorks version + build
  that created / rebuilt the feature), description, state. Every feature class starts with it; only what follows is
  class-specific.
* **The map base** (`swreader/features.py`): `ResolvedFeatures` continues `Config-0`'s map; the walker finds the
  offset itself. Do not change that logic unless walkall proves the change.

### A.2 The loop
Run the tools from `devtools/` (they read `SWREADER_SAMPLES`):

```
cd /work/swreader/devtools
export SWREADER_SAMPLES=/solidworks/samples
../.venv/bin/python walkall.py                # 1. where do walks stop? the top line is your next class
../.venv/bin/python after.py CLASS 2 600      # 2. dump what follows the feature base, per version
../.venv/bin/python gap.py CLASS [NEXTCLASS]  # 3. bytes from the base to the next new-class record, per version
../.venv/bin/python gap2.py CLASS             # 3b. from the start of a class's data to the next landmark
swread dump FILE SECTION --start N --end M    # 4. annotated dump of any stretch of a stream
# 5. write / change the layout in swreader/classes.py (version-gated)
../.venv/bin/python -c "import tryclass as T; T.run('CLASS')"   # 6. first instance of CLASS in every document
../.venv/bin/python walkall.py                # 7. the stop moved past CLASS? nothing else got worse?
```

* `gap.py` / `gap2.py` give the **length** of a class's data per version - if it is constant, the layout is a fixed
  sequence of fields; if it varies, look for counts, strings (`FF FE FF` + length) and nested objects.
* `swread dump` marks strings (`STR`), new classes and plausible doubles (`F64`, with mm/in conversions). Real
  dimensions show up as clean inch or mm values; angles as clean degrees.
* `tryclass.py` is **lenient** (a `00 00` null tag always looks plausible). Only `walkall.py` is the real test.
* A class is **done** when walkall gets past it in every version where it occurs, with no regressions, and the
  decoded values make sense (compare with the document's drawing PDF or STEP when one exists in the samples).
* Name fields you understand; keep the rest as `raw(n)` or `name_u` (unknown) so the walk stays aligned.
* Write what you learn into `docs/FORMAT.md` (layouts, meaning, which versions you checked).

### A.3 Worked example (how the folders and planes were done)
1. walkall showed most walks stopping at offset ~1072 inside a folder. `gap.py moSurfaceBodyFolder_c` gave a constant
   10 bytes after the base for versions < 10000 and 12 for >= 10000; the bytes were all zero, so the layout became
   `feature(r, o); raw(12 if version >= 10000 else 10)`.
2. walkall moved on to `moRefPlane_c`; `gap.py moRefPlane_c moDefaultRefPlnData_c` gave 140 / 142 / 146 bytes by version
   -> `raw(_by_version(...))` then the nested object.
3. The plane data (`moDefaultRefPlnData_c`) varied in length between Front and Top plane. Dumping both side by side
   showed origin (3 doubles), normal (3 doubles: Front = 0,0,1, Top = 0,1,0), then a 1-byte flag followed by a 3x3
   rotation only when the flag is 1 - that explained the 72-byte difference. Decoded fields are named; the rest kept
   raw.
4. Each step: walkall before and after, numbers written down.

### A.4 Where the frontier is
`moOriginProfileFeature_c` -> `sgSketch` -> sketch entities. Notes so far:
* every sketch entity starts with a common header `FF FF 1F 00 01 FF FF FF FF FF FF FF FF 00 00 80 BF ...`;
* sketch points carry a type word `0x1E` followed by x, y (doubles, metres, sketch space);
* lines refer to their end points through small `sgPointHandle` objects;
* dimension parameters (`moLengthParameter_c`, `moAngleParameter_c`) are named nodes (`D1`, `D2` ...) whose value
  (metres / radians) follows the name block.
Once swexport output for the same documents exists, use it as the answer key: the export lists every sketch entity
and dimension value the native decoder should find.

---

## Workflow B - swexport (C#, runs with SolidWorks on Windows)

* You cannot build or run it here (no .NET SDK, no SolidWorks). Keep changes small and reviewable.
* It is late-bound COM (`swexport/src/Com.cs`): every call is `Com.Try(obj, "Member", args)`. Member names and
  argument lists must match the SolidWorks API reference exactly - check with `devtools/check_api.py`.
* Enumeration values go in `SwConst.cs` only after checking them with `check_api.py enum`.
* JSON changes must also go into `docs/EXPORT.md` and, if consumers need them, `swreader/export.py` and SwRebuild.

## Workflow C - SwRebuild (Fusion add-in, Python)

* You cannot run Fusion here. Pure geometry belongs in `fusion/SwRebuild/lib/geom.py` with unit tests in
  `tests/test_fusion_geom.py` (those you can run); Fusion calls go in `lib/rebuild.py`.
* Every Fusion call must exist in the installed stubs: `check_api.py fusion` must report 0 problems; look up
  signatures with `check_api.py fsig CLASS MEMBER` and read the matching `*_Sample.md` page.
* Units: SolidWorks JSON is metres/radians; Fusion's API is centimetres (`geom.CM`).
* Think like the engineer remodelling the part: same sketch plane or face, same geometry, same relations, same
  named driving dimensions, then the same feature in Fusion with the same intent (end condition, direction,
  operation).

### Drawings in Fusion
Fusion's drawing API (`adsk.drawing`, stubs `drawing.py`) can create a drawing with automatic views, add sheets,
auto-dimension, draw sketch geometry, and add tables/images - but cannot place specific views or add specific
dimensions, tolerances, GD&T or notes. Do not promise or fake a faithful drawing conversion; see ROADMAP for the plan.
Re-check `drawing.py` in newer stubs before assuming anything changed.

## Workflow D - reviewing swexport output (when exports exist)

For each exported document: `swread summary FILE.json`, `swread params FILE.json`, the `errors` list, and
`manifest.jsonl`. Check that values make engineering sense (dimensions are clean inch/mm values, tolerances match
the drawing PDF), compare with what the native reader finds in the same document, and write discrepancies into
`HANDOFF.md` with the document path and the JSON key.

---

## Handing work back

* Local commits only, each with tests passing and (for swexport/SwRebuild) `check_api.py` clean.
* `HANDOFF.md`: what changed (commit ids), the before/after numbers, what is next, questions for the owner.
