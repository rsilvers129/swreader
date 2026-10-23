"""dev: walk every part's feature tree; tally where walks stop, per version (the to-do list, version-aware)."""
import sys, collections, importlib, re
import tryclass as T
import swreader.classes as C, swreader.features as F, swreader.objects as O
def main(top=30):
    importlib.reload(C); importlib.reload(F)
    stop = collections.Counter(); per = collections.defaultdict(collections.Counter); done = collections.Counter()
    nobj = 0
    for p, ver, d, node, classes in T.corpus():
        try:
            objs, r, err = F.walk(d, ver)
        except Exception as e:
            stop[("setup", type(e).__name__)] += 1; continue
        nobj += len(r.trace)
        if err is None:
            done[ver] += 1; continue
        key = err.name if isinstance(err, O.UnknownClass) else re.sub(r"\d+", "N", f"{type(err).__name__}: {str(err)[:50]}")
        stop[key] += 1; per[key][ver] += 1
    print("complete:", dict(done), " objects decoded:", nobj)
    for k, v in stop.most_common(top): print(f"{v:5d}  {k}  {dict(per[k])}")
if __name__ == "__main__":
    main()
