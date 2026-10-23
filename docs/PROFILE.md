# Company profile (`profile.json`)

A company's conventions - what its custom properties mean, which material library it uses, its sheet formats and
drawing templates - are not in any single SolidWorks file, and an agent or tool cannot guess them. They are written
down once in a **company profile**, kept with the company's data (never in this repository), and read by SwRebuild
(and by agents, see AGENT-GUIDE.md).

```json
{
  "format": "swreader-company-profile", "version": 1,
  "company": "Example Co",
  "general_tolerance": "ISO 2768-m",
  "drafting_standard": {"solidworks": "Example.sldstd", "fusion": "ISO"},
  "properties": {
    "PartNo":      {"label": "Part Number", "fusion": "component.partNumber"},
    "Description": {"label": "Description", "fusion": "component.description"},
    "Material":    {"label": "Material",    "fusion": "material (see materials) + attribute"},
    "DrawnBy":     {"label": "Drawn By",    "fusion": "attribute"}
  },
  "materials": {"Example|6061-T6": "Aluminum 6061"},
  "sheet_formats": {"A3 Example": {"size": "A3"}},
  "drawing_templates": {"Example A3": {"sheet_format": "A3 Example", "fusion_template": null}},
  "title_block_fields": ["PartNo", "Description", "Revision", "DrawnBy"]
}
```

* `properties.<SolidWorks name>.fusion`: `component.partNumber`, `component.description`, or `attribute`. Fusion's API
  cannot create custom properties, so everything else is kept as a Fusion attribute (group `SolidWorks`) - every
  SolidWorks property is stored that way in any case, so nothing is lost.
* `materials`: SolidWorks material name -> Fusion material name (as shown in Fusion's material browser); `null` =
  not mapped yet (the name is still kept as an attribute).
* Keys starting with `_` are notes. Values containing `TO CONFIRM` are drafts the owner still has to check.

SwRebuild asks for the profile the first time and remembers its location in `profile_path.txt` next to the add-in.
