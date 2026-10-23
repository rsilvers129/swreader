# swreader

Read SolidWorks documents (`.SLDPRT`, `.SLDASM`, `.SLDDRW`) without SolidWorks — in Python, on any OS.

```
pip install -e .
swread info part.SLDPRT              # properties, mass, material, configurations, components (JSON)
swread sections part.SLDPRT          # what is inside the file
swread preview part.SLDPRT -o p.png  # embedded preview image
swread parasolid part.SLDPRT out/    # B-rep geometry as Parasolid transmit files
swread index /path/to/library -o library.jsonl
```

```python
from swreader import open_file
from swreader import props, parasolid

with open_file("part.SLDPRT") as sw:
    print(props.summary(sw)["custom_properties"])
    png = sw.read("PreviewPNG")
```

**Supports** documents saved by SolidWorks 2015+ (obfuscated ZIP container) and earlier (OLE2 compound file).
**Reads today:** custom, configuration and system properties; units; mass properties; material; configurations;
assembly component tree; preview images; Parasolid geometry partitions.
**Not yet:** feature tree, drawing dimensions, mesh and STEP export — see [docs/ROADMAP.md](docs/ROADMAP.md).
The format notes are in [docs/FORMAT.md](docs/FORMAT.md).

## Tests

```
pip install -e '.[test]'
pytest                                       # synthetic documents
SWREADER_SAMPLES=/path/to/documents pytest   # also check every real document in a folder
```

No SolidWorks documents, exports or data derived from them are kept in this repository (see `.gitignore`);
real-file tests read them from a local folder.

## How this was built

The format was worked out by examining the bytes of documents only, for interoperability. No SolidWorks software
was disassembled or decompiled. SolidWorks is a trademark of Dassault Systèmes; this project is not affiliated with it.
