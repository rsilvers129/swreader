"""dev: search for the layout of a class the walks stop on.

For CLASS, try candidate layouts - feature base or bare node, then k raw bytes and/or a child list - and score each
by how many walks get past the class (they end complete, at a different class, or well beyond it). Prints the best
candidates per version.  usage: autotail.py CLASS [max_k] [files_per_version]
"""
import sys, collections, importlib
import tryclass as T
import swreader.classes as C, swreader.features as F, swreader.objects as O


def candidates(max_k):
    for base in ("feature", "node"):
        for k in range(0, max_k + 1):
            yield (base, k, None)
            yield (base, k, "objs")
            yield (base, k, "obj")
            yield (base, k, "objs-first")


def make(spec):
    base, k, kids = spec
    def fn(r, o):
        if base == "feature":
            C.feature(r, o)
        else:
            o["node"] = r.obj()
        if kids == "objs-first":
            o["items"] = r.objs()
        if k:
            r.raw(k)
        if kids == "objs":
            o["items"] = r.objs()
        elif kids == "obj":
            o["child"] = r.obj()
    return fn


def reached(err, r, d):
    """How far the walk got (bytes): the end of the stream when complete, else where it stopped."""
    if err is None:
        return len(d)
    if isinstance(err, O.UnknownClass):
        return err.pos
    good = [a for a, c, i in r.trace]
    return good[-2] if len(good) > 1 else 0         # a layout error: count only up to the last object before it


def run(cls, max_k=40, per_version=150):
    importlib.reload(C); importlib.reload(F)
    files = collections.defaultdict(list)
    for p, ver, d, node, classes in T.corpus():
        if len(files[ver]) >= per_version:
            continue
        objs, r, err = F.walk(d, ver)
        if isinstance(err, O.UnknownClass) and err.name == cls:
            files[ver].append((d, ver, err.pos))
    if not files:
        print("no walks stop at", cls); return
    print({v: len(x) for v, x in files.items()})
    saved = O.REGISTRY.get(cls)
    score = collections.defaultdict(dict)
    try:
        for spec in candidates(max_k):
            O.REGISTRY[cls] = make(spec)
            for ver, xs in files.items():
                n = gain = 0
                for d, v, at in xs:
                    try:
                        objs, r, err = F.walk(d, v)
                    except Exception:
                        continue
                    g = reached(err, r, d) - at
                    n += g > 0
                    gain += max(g, 0)
                score[ver][spec] = (n, gain)
    finally:
        if saved: O.REGISTRY[cls] = saved
        else: O.REGISTRY.pop(cls, None)
    for ver in sorted(score):
        if not files[ver]:
            continue
        best = sorted(score[ver].items(), key=lambda x: (-x[1][1], x[0][1]))[:5]
        print(f"  {ver:6d} of {len(files[ver])}: " + "  ".join(f"{s[0][0]}+{s[1]}{'+' + s[2] if s[2] else ''}={n[0]}/{n[1]}" for s, n in best))


if __name__ == "__main__":
    a = sys.argv[1:]
    run(a[0], int(a[1]) if len(a) > 1 else 40, int(a[2]) if len(a) > 2 else 150)
