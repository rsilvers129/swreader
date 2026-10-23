# SolidWorks document format — working notes

Everything here was learned by examining document bytes only (no SolidWorks binaries were disassembled).
"Confirmed" means checked across documents saved by several SolidWorks versions; anything else is marked.

## 1. Containers

### 1.1 2015 and later — obfuscated ZIP-like archive (confirmed: files saved 2019–2026)

The document is a sequence of sections. Each section starts with a local header:

| bytes | meaning |
|---|---|
| 4 | varies per section (not yet identified) |
| 4 | `00 00 00 04` |
| 6 | varies (not yet identified) |
| 6 | `14 00 06 00 08 00` — ZIP "version 2.0, flags 6, method 8 (deflate)" |
| 2 + 2 | DOS time, date |
| 4 | CRC-32 of the uncompressed data |
| 4 | compressed size |
| 4 | uncompressed size |
| 4 | name length (u32, not u16 as in ZIP) |
| n | section name, **each byte nibble-swapped** (`(b << 4 \| b >> 4) & 0xff`) |
| csize | raw deflate (no zlib header) |

* The archive also contains **decoy headers**: same layout, plausible names (`Preview`, `PreviewPNG`,
  `Contents/Config-0-ResolvedFeatures`, …) but data that does not inflate or fails the CRC. A recurring decoy
  pattern is `crc = 4·k, csize = k, usize = 2·k`. Accept a section only when it inflates to `usize` bytes with the
  stated CRC. If several valid copies of a name exist, the last one is used.
* At the end there is a central directory: records with the same marker and sizes, 10 zero bytes after the name
  length, then a u32 offset, then the (swapped) name. It also lists decoys. `swreader` does not need it.

### 1.2 Before 2015 — OLE2 compound document (confirmed: a 2012 file)

Standard compound file (`D0 CF 11 E0 A1 B1 1A E1`) with the same stream names. Streams named `…__ZLB` are wrapped
(§1.3). Properties are OLE property sets ([MS-OLEPS]) in `\x05DocumentSummaryInformation`, `Config-N-Properties`
and `ISolidWorksInformation` instead of XML.

### 1.3 GUID wrapper (chained sections)

Compressed OLE streams and every Parasolid stream (both container kinds) are made of *chained sections*:

```
section := chain_len:u32  GUID 231dd571-da81-48a2-a858-98b21b89ef99 (stored as these bytes)  frame+  [zero padding]
frame   := usize:u32  zsize:u32  zlib[zsize]          (inflates to usize bytes)
```

`chain_len` counts from the GUID to the end of the section. The frames of one section concatenate into one payload;
large Parasolid bodies are split into 1 MiB frames (about 6% of the parts in a large library; reading only the first
frame cut them off). One stream can hold several sections; the next starts at `GUID offset + chain_len`.
`swreader.container.sections` returns them all, `unwrap` the first. Layout first described by cadmpeg's SLDPRT notes
(pre-2015) and OrchardCAD's notes (P. Gallogly; same in 2015+ files); confirmed on our corpus.

## 2. Sections

| section | contents | status |
|---|---|---|
| `PreviewPNG` | 640×480 PNG preview | confirmed |
| `Preview` | older preview (DIB) | seen |
| `Images/Sheet_N` (drawings) | 640×480 PNG of sheet N | confirmed for sheet 0 |
| `docProps/custom.xml` | file custom properties, OOXML custom-properties schema | confirmed |
| `docProps/Config-N-Properties.xml` | configuration-specific properties | confirmed |
| `docProps/ISolidWorksInformation.xml` | `SW-*` system properties, units, `SW-MassProp-Config-N` | confirmed |
| `swXmlContents/Features` | document type, configurations (XML) | confirmed |
| `swXmlContents/MATERIALTREE` | material (UTF-16 XML, `sldmaterials` schema) | confirmed |
| `swXmlContents/COMPINSTANCETREE` | assembly: referenced files, models, component instances, placements, bounding boxes (§2.2) | confirmed |
| `swXmlContents/CustomProperties` (drawings) | drawing property XML | seen |
| `Contents/Config-N-Partition` | Parasolid partition + deltas transmits (§3) | confirmed |
| `Config-N-FeatureBodies/LocalBodies` | bodies of imported features, one Parasolid part transmit per record (§3) | confirmed |
| `Contents/Config-N-StockBodies` | base bodies of derived parts (§3) | seen |
| `Contents/Config-N-Body` | pre-2004 documents (instead of `-Partition`): `u32 length` + data in an older, non-zlib compression | not decoded |
| `Contents/Config-N-GhostPartition` | smaller Parasolid partition (purpose unknown) | seen |
| `Contents/DisplayLists` | tessellated display data (mesh) | not decoded |
| `Contents/Config-N-ResolvedFeatures`, `Contents/Config-N` | feature tree, serialized objects (§4) | not decoded |
| `Contents/Definition` | document definition; for drawings: views, dimensions, notes, tables (§4) | not decoded |
| `Contents/VBLists`, `SectionBodies/View-N` (drawings) | view geometry | not decoded |
| `_MO_VERSION_N/Biography`, `History` | save history | not decoded |

### 2.1 `SW-MassProp-Config-N`

14 comma-separated numbers, SI units. Confirmed: `[0..2]` centre of mass (m), `[3]` volume (m³), `[4]` surface
area (m²), `[5]` mass (kg). `[6..13]` not yet identified (probably inertia terms).

### 2.2 `COMPINSTANCETREE` placements

Every assembly model in the file (the document and each sub-assembly) is an `swModel` whose children are its direct
`swReference` instances; `swModelRef` points at the referenced model, which has its own references (nesting).
`swTransform` = 16 numbers, a column-major 4x4 matrix, local -> parent, translation in metres at indices 12-14.
`swConfigurationId` selects the referenced part's `Config-N-*` streams. `swIsVirtualComponent="YES"` (names with `^`)
are components stored inside the assembly. (OrchardCAD's notes; transform layout checked on our corpus.)

## 3. Geometry — Parasolid

Each section (§1.3) of a Parasolid stream is a standard Parasolid binary transmit (x_b): it begins
`PS\0\0\0?: TRANSMIT FILE (<guise>) created by modeller version <v>` followed by a schema name
`SCH_<v>_<n>_<base>`. Siemens publishes the XT format reference.

* `Contents/Config-N-Partition` holds two sections: the *partition* transmit with the configuration's bodies, then a
  *deltas* transmit (rollback marks). The partition can be **empty (~300 bytes)**: when the body comes from an
  imported feature (e.g. a STEP import) it is stored in
* `Config-N-FeatureBodies/LocalBodies` (no `Contents/` prefix): `count:u32`, then per record a UTF-16 CString (the
  feature name, e.g. `<file>.step<1>`), a few u32s, and one section holding a plain *part* transmit (no guise word).
  A multi-body import has one record per body.
* `Contents/Config-N-StockBodies`: base bodies of derived parts.
* `Contents/Config-N-GhostPartition`: never the model.

In a large library about 8% of the parts had an empty partition and their bodies in FeatureBodies.
`swreader.parasolid.model()` picks the right transmits.

## 4. Serialized objects (MFC CArchive)

Feature-tree, sketch and drawing data (`Contents/Config-N`, `Contents/Config-N-ResolvedFeatures`, `Contents/CMgr`,
`Contents/Definition`, …) are **MFC CArchive** streams (confirmed; reader primitives in `swreader/mfc.py`):

* object tag (WORD): `0x0000` null; `0xFFFF` new class (`WORD schema, WORD name length, ASCII name`) followed by the
  new object's data; `0x8000|i` new object of the class at map index `i`; `0x7FFF` + DWORD for big archives;
  any other value = reference to an already-loaded object at that map index. Map indices start at 1 and are given,
  in order, to every new class and every new object.
* CString: `FF FE FF` + length (BYTE, or `FF` + WORD, or `FFFF` + DWORD) + UTF-16LE characters.
* counts: WORD, or `FFFF` + DWORD.

**The map is shared across streams of one configuration**: `Config-N-ResolvedFeatures` refers to classes first
defined in `Config-N` (e.g. the node-name class), so `Config-N` must be read first.

* **Stored map count (format 8000 / SolidWorks 2009 and later).** `Config-N-ResolvedFeatures` starts with a u32: the
  archive's map count at the end of `Config-N` (null entry included), then the WORD count of top-level tree items.
  Local map indices therefore start at that value, and the walker needs no guessing. Older streams start directly
  with the item count; their base is found by trying candidates (`swreader/features.py`).
* **Classes defined in `Config-N`** appear in the feature stream only as `0x8000|i` with `i` below the stored count.
  Their names are not visible there. Rebuilding `Config-N`'s map from its bytes does not work: new-class records
  (+2) and new-object tags (+1) account for only part of the count (e.g. 337 of 1343) - the rest are entries that
  leave no bytes (consistent with MFC `MapObject`) or objects whose tags are only found by decoding every layout.
  What is known: index 1 precedes `moPart_c`, the node-name class is 4 in every 2009+ part, and between the
  node-name class and the units table there are 3 such hidden entries. Layouts that know what class they hold name
  the entry themselves (`Reader.obj(expect=...)`, e.g. `moCompFeature_c` -> `moFeatureRef_c`).
* Many 2009+ parts define the sketch classes (`sgSketch`, `sg*Handle`, dimensions) in the feature stream itself;
  in others they come from `Config-N` and are, for now, unreadable without the map.

### 4.2 The keyword index (`swXmlContents/KeyWords`)

Every document (seen from format 4100 on) carries an XML index after one non-XML byte (0x86 or 0x85): `Feature`,
`Sketch`, `Extrusion`, `Cut`, `HoleWizard`, `Block`, `Reference` (assembly components, drawing references),
`Configuration` (with `Material`), and in drawings `Sheet` (paper size, scale, sheet-format path, `View` children with
their model file), `View`, `Note`, `Table`/`Cell` and title-block `Attribute` texts. Items carry `id`, `Name`, `Type`
and `Dimension` children whose text is the displayed value (`<MOD-DIAM>` = Ø, `R` radius, `°` angle, `( )` driven).
`Type` is the localized default name stem (German "Fase" = Chamfer), not a type code; `swreader/keywords.py` maps the
stems seen in 17,000 documents to English names. Sorting features by id gives the creation order. Read with
`swread features`.

### 4.3 Sketches (`sgSketch`, partly decoded)

Checked on 6,466 parts, formats 4700-19000 (the origin sketch of each; 2012 user sketches by hand):

* `sgSketch` data starts with arrays of entity records, each array `u32 count` then per record `u16, u32` and the
  record. Points first, then lines, then 13 more arrays (empty in the origin and in line-only sketches; arcs and the
  other curve types are in these), then a WORD-counted object list of dimensions and relations (`sgPntPntDist`,
  `sgLLDist`, `sgAnglDim`, ... each with its `moLengthParameter_c` / `moAngleParameter_c`) - not yet decoded.
* Entity record start (`sk_entity`): `u32 id`, 17 constant bytes `FF FF 07 00 01 FF*8 00 00 80 BF`, `u8, u32, u8`,
  4 WORDs, `f32 -1`, an object (null, or `sgExtEnt_c` when the entity is projected from outside the sketch), WORD,
  9 bytes, `f64`, and from format 16000 8 more bytes.
* Point: `u16` flags (0x1E, 0x1F for the origin), `f64 x, f64 y` (metres, sketch space), two WORDs, two handle
  objects (the entities ending at the point, or null), `u16, i32 -2`, 36 bytes.
* Line: `u16 start, u16 end` (point indices), `u32`, `f64`, `u32`.
* `sgPointHandle` / `sgLineHandle` / `sgArcHandle` / `sgEntHandle`: `u16 index, i32` - references into the arrays.
* The origin feature: feature base, 10 bytes (6 from format 14000), then its `sgSketch` (one point); after the 13
  empty arrays comes a block (`01 00 00 00 ... 11 00 00 00 02 00 00 00`, 2 bytes longer from 10000, 4 from 18000),
  the origin's `sgPointHandle`, a version-dependent block, and `moCompRefPlane_c` (fixed 119 / 159 / 163 bytes by
  version: a reference to the sketch plane).

Class names are descriptive: parts use `moPart_c`, `moRefPlane_c`, `moProfileFeature_c`, `sgSketch` (sketch),
`sgLineHandle`, `sgArcHandle`, `sgPointHandle`, `sgPntPntDist` / `sgPntLineDist` / `sgCircleDim` / `sgAnglDim`
(sketch dimensions), `moLengthParameter_c` / `moAngleParameter_c` (dimension values), `moExtrusion_c`,
`moICE_c`, `moRevolution_c`, `moRevCut_c`, `Fillet_c`, `Chamfer_c`, `moHoleWzd_c`, `moLPattern_c`, `moCirPattern_c`,
`moMirrorPattern_c`, `moSweep_c`, `moHelix_c`, …; drawings use `moView_c`, `moDisplayDistanceDim_c`,
`moDimTolerance_c`, `moDisplayNote_c`, `moAnnotationTable_c`, …

### 4.1 Named nodes and features (partly decoded)

Every feature, folder, plane, sketch and parameter starts with a node-name object (its own class, defined in
`Config-N`): `CString name`, `u32 0`, `u32 flags` (`0x40000000`, `0xC0000000` seen), `u32 id`, then a block whose
layout depends on a version word (`0x65`, `0x67` seen in 2012-era files). For `moLengthParameter_c` /
`moAngleParameter_c` the value (metres / radians, f64) follows the name block; a parameter's name is the dimension
name (`D1`, `D2`, …).

Decoding the per-class layouts is the main open work item; `swread dump` and `swread classes` are the tools.
