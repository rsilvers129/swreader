"""dev: show examples of walks that stop with a given error/class (substring match): trace tail + dump at the stop."""
import sys, re, importlib
import tryclass as T
import swreader.classes as C, swreader.features as F, swreader.objects as O
from swreader.explore import dump
def why(key, n=2, before=200, after=300, versions=None):
    k = 0
    for p, ver, d, node, classes in T.corpus():
        if versions and ver not in versions: continue
        objs, r, err = F.walk(d, ver)
        if err is None: continue
        s = err.name if isinstance(err, O.UnknownClass) else f"{type(err).__name__}: {err}"
        if key not in s: continue
        print(f"===== {ver} {p}\n  {s}\n  trace: {[(a, c) for a, c, i in r.trace[-6:]]}")
        start = r.trace[-1][0] if r.trace else 0
        at = err.pos if isinstance(err, O.UnknownClass) else r.pos
        print(dump(d, max(start, at - before), min(len(d), at + after)))
        k += 1
        if k >= n: break
if __name__ == "__main__":
    a = sys.argv[1:]
    why(a[0], n=int(a[1]) if len(a) > 1 else 2)
