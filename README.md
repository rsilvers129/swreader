# swreader

Tools for getting engineering data **out of SolidWorks** and into open formats, other CAD systems, and LLMs.

| piece | runs on | needs SolidWorks | what it does |
|---|---|---|---|
| [`swexport/`](swexport/) | Windows | yes | batch-converts a folder of parts, assemblies and drawings to **STEP / PDF / STL / DXF** plus **design-data JSON** (feature tree, sketches, dimensions with tolerances, relations, drawings' views, annotations and tables) |
| [`swreader`](swreader/) + `swread` | anywhere (Python) | no | reads native `.SLDPRT/.SLDASM/.SLDDRW` files directly, and reads swexport output (summaries, parameter lists, search index) |
| [`fusion/SwRebuild`](fusion/) | Fusion (add-in) | no | rebuilds a part in Fusion from its JSON **feature by feature, with parametric history**: same sketch planes, geometry, relations, named driving dimensions, then the features in order |

```
SolidWorks files ──swexport──► export tree: *.step *.pdf *.json manifest.jsonl
       │                                   │
       └──swread (native, no SolidWorks)   ├──swread summary / params / library ──► search index, LLM context
                                           └──Fusion: SwRebuild ──► parametric Fusion design
```

## Goals

1. **Interoperability** - a general reader so other CAD programs can use SolidWorks data.
2. **Design learning** - capture *how* parts were built (feature order, sketches, dimensions, tolerances) so a
   model can learn to design the way an experienced engineer does.
3. **Remodelling** - rebuild SolidWorks parts in Fusion with full parametric history, one feature at a time.

## Quick start

```
pip install -e .                                   # swread
swread info part.SLDPRT                            # native: properties, mass, material, configurations
swread summary export/Bracket.SLDPRT.json          # from swexport: the design in words
swread library export/ -o library.jsonl            # search records for every exported document
```

`swexport` and `SwRebuild` have their own READMEs. Formats: [docs/EXPORT.md](docs/EXPORT.md) (swexport JSON),
[docs/FORMAT.md](docs/FORMAT.md) (native file format notes), [docs/ROADMAP.md](docs/ROADMAP.md).

## Native reader (`swread`)

```
swread info part.SLDPRT              # properties, mass, material, configurations, components (JSON)
swread sections part.SLDPRT          # what is inside the file
swread preview part.SLDPRT -o p.png  # embedded preview image
swread parasolid part.SLDPRT out/    # B-rep geometry as Parasolid transmit files
swread features part.SLDPRT          # features and sketches in creation order, with dimension values
swread index /path/to/library -o library.jsonl
swread classes / dump                # format-work tools for the object streams
```

Reads documents saved by SolidWorks 2001-2026 (both container formats). `swread features` lists every feature and
sketch with its displayed dimension values for any document, from the keyword index SolidWorks embeds (no sketch
geometry or end conditions). The binary feature tree is being decoded class by class (docs/FORMAT.md); until that is
complete, swexport is the route to the full design data.

## Tests

```
pip install -e '.[test]'
pytest                                       # synthetic documents and example exports
SWREADER_SAMPLES=/path/to/documents pytest   # also check every real document in a folder
```

No SolidWorks documents, exports or data derived from them are kept in this repository (see `.gitignore`);
`tests/data` holds small hand-written examples only.

## How the native format was worked out

By examining the bytes of documents only, for interoperability. No SolidWorks software was disassembled or
decompiled. SolidWorks is a trademark of Dassault Systèmes and Fusion of Autodesk; this project is not affiliated
with either.
