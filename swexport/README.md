# swexport

Batch-convert SolidWorks documents to open formats, using SolidWorks itself (Windows).

| document | outputs |
|---|---|
| part | `Name.step`, `Name.SLDPRT.json` (+ `Name.stl` with `--stl`) |
| assembly | `Name.step`, `Name.SLDASM.json` |
| drawing | `Name.pdf` (all sheets), `Name.SLDDRW.json` (+ `Name-Sheet1.dxf`... with `--dxf`) |

The JSON holds the design data: feature tree in history order, sketches (geometry, relations), every dimension with
tolerance and what it is attached to, feature parameters and selections, configurations, custom properties,
equations, material, mass; assemblies' component tree, placements and mates; drawings' sheets, views, dimensions,
notes, GD&T, datums and tables. Format: [../docs/EXPORT.md](../docs/EXPORT.md).

## Get it

Download `swexport.exe` from the repository's Releases, or build it (below). It is a single small .exe; .NET
Framework 4.8 is part of Windows 10/11.

## Run it - start small

1. **Save your work and close SolidWorks.** swexport starts its own SolidWorks and refuses to run while
   SolidWorks is open (it closes every document it opens).
2. Try **one small folder** first and check the results before converting a library:

```
swexport "C:\Designs\Test" --out "C:\Designs\Test-export"
```

3. Look at `manifest.jsonl` (one line per document: status, outputs, seconds, warnings) and open a few outputs.
   `ok_with_warnings` means some data could not be read; the JSON's `errors` list says what.

Options:

```
  -o, --out DIR        output folder (default: <folder>-export next to the input)
  --no-recurse         only the top folder
  --types LIST         part,assembly,drawing (default: all)
  --no-json / --no-step / --no-pdf
  --stl                also STL for parts
  --dxf                also one DXF per drawing sheet
  --all-configs        record dimension values for every configuration
  --force              re-export even when outputs are up to date
  --visible            show the SolidWorks window
```

Re-running continues where it stopped: documents whose outputs are newer than the source are skipped. Parts are
exported before assemblies and drawings. If SolidWorks crashes on a document, swexport restarts it (only the instance
it started) and carries on.

Export to a network folder works too, e.g. `--out \\server\share\library-export`.

## Build

No SolidWorks assemblies are needed (the tool calls SolidWorks through late-bound COM, so one build works with any
SolidWorks version):

```
dotnet build -c Release            # .NET SDK 6+; output in bin\Release\net48\swexport.exe
```

## Notes

* Read-only: documents are opened read-only and never saved.
* Values in the JSON are SI (metres, radians, kg); the document's display units are recorded alongside.
* Members of the SolidWorks API that do not exist in an older SolidWorks version are skipped, not fatal.
