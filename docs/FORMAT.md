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

### 1.3 GUID wrapper

Compressed OLE streams and every Parasolid partition (both container kinds) are wrapped:
`[u32]? GUID 231dd571-da81-48a2-a858-98b21b89ef99 (stored as these bytes) u32 u32 [u32] zlib-stream`.
The u32s are sizes; `swreader.unwrap` locates the zlib header after the GUID.

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
| `swXmlContents/COMPINSTANCETREE` | assembly: referenced files, models, component instances, bounding boxes | confirmed |
| `swXmlContents/CustomProperties` (drawings) | drawing property XML | seen |
| `Contents/Config-N-Partition` | Parasolid transmit file (§3) | confirmed |
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

## 3. Geometry — Parasolid

`Contents/Config-N-Partition`, unwrapped (§1.3), begins
`PS\0\0\0?: TRANSMIT FILE (partition) created by modeller version <v>` followed by a schema name
`SCH_<v>_<n>_<base>` — a standard Parasolid binary transmit (x_b) partition. Siemens publishes the XT format reference.

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

Class names are descriptive: parts use `moPart_c`, `moRefPlane_c`, `moProfileFeature_c`, `sgSketch` (sketch),
`sgLineHandle`, `sgArcHandle`, `sgPointHandle`, `sgPntPntDist` / `sgPntLineDist` / `sgCircleDim` / `sgAnglDim`
(sketch dimensions), `moLengthParameter_c` / `moAngleParameter_c` (dimension values), `moExtrusion_c`,
`moICE_c`, `moRevolution_c`, `moRevCut_c`, `Fillet_c`, `Chamfer_c`, `moHoleWzd_c`, `moLPattern_c`, `moCirPattern_c`,
`moMirrorPattern_c`, `moSweep_c`, `moHelix_c`, …; drawings use `moView_c`, `moDisplayDistanceDim_c`,
`moDimTolerance_c`, `moDisplayNote_c`, `moAnnotationTable_c`, …

### 4.1 Named nodes (partly decoded)

Every feature, folder, plane, sketch and parameter starts with a node-name object (its own class, defined in
`Config-N`): `CString name`, `u32 0`, `u32 flags` (`0x40000000`, `0xC0000000` seen), `u32 id`, then a block whose
layout depends on a version word (`0x65`, `0x67` seen in 2012-era files). For `moLengthParameter_c` /
`moAngleParameter_c` the value (metres / radians, f64) follows the name block; a parameter's name is the dimension
name (`D1`, `D2`, …).

Decoding the per-class layouts is the main open work item; `swread dump` and `swread classes` are the tools.
