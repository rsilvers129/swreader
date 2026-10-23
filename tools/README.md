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
