# Format-work tools

Scripts used to work out class layouts against a corpus of real documents (set `SWREADER_SAMPLES`).
Run from this directory.

| script | what it does |
|---|---|
| `tryclass.py` | test the registered layout of a class on its first instance in every document |
| `gap.py CLASS [NEXT]` | distance from the end of the feature base to the next new-class record, per version |
| `gap2.py CLASS` | distance from the start of a class's data to the next landmark (new class or named object) |
| `after.py CLASS [N] [LEN]` | annotated dump of what follows the feature base |
| `walkall.py` | walk every part's feature tree; tally where walks stop (the to-do list) |
| `frontier.py` | the same, per document version, with decoded-object totals |
| `why.py TEXT [N]` | examples of walks that stop with TEXT in the error: last objects decoded and a dump |
| `autotail.py CLASS [K] [N]` | search candidate layouts (feature/node + k bytes + children) for a stop class |

`SWREADER_SAMPLES` may list several roots (`:`-separated). Set `SWREADER_CACHE=/path/corpus.pkl` to keep the loaded
corpus between runs (first run writes it).
