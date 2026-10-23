"""dev: walk ResolvedFeatures of every part; tally where walks stop."""
import sys, collections, importlib
import tryclass as T
import swreader.classes as C, swreader.features as F, swreader.objects as O
def main(versions=None, show=0):
    importlib.reload(C); importlib.reload(F)
    stop = collections.Counter(); done = collections.Counter(); per = collections.defaultdict(collections.Counter); ex = {}
    for p, ver, d, node, classes in T.corpus():
        if versions and ver not in versions: continue
        try:
            objs, r, err = F.walk(d, ver)
        except Exception as e:
            stop[f"setup {type(e).__name__}"] += 1; continue
        if err is None:
            done[ver] += 1; per[ver]["complete"] += 1; continue
        key = err.name if isinstance(err, O.UnknownClass) else f"{type(err).__name__}: {str(err)[:60]}"
        stop[key] += 1; per[ver][key] += 1
        ex.setdefault(key, (p, d, r, err))
    print("complete:", dict(done))
    for k, v in stop.most_common(25): print(f"{v:5d}  {k}")
    return ex
if __name__ == "__main__":
    main()
