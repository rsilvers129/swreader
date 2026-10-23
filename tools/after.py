"""dev: run the base `feature` layout on CLASS's first instance and dump what follows (per version)."""
import sys, collections
import tryclass as T
from swreader.explore import dump
import swreader.classes as C
def show(cls, versions=(4700, 5000, 6000, 10000, 16000), n=2, length=400, base=C.feature):
    for want in versions:
        k = 0
        for p, ver, d, node, classes in T.corpus():
            if ver != want: continue
            at = [o for o, nm, s in classes if nm == cls]
            if not at: continue
            r = T.Loose(d, at[0] + 6 + len(cls), ver, node, classes); o = {}
            try: base(r, o)
            except Exception as e: continue
            nxt = sorted(x for x, nm, s in classes if x > r.pos)
            print(f"===== {ver} {p[-45:]}  next class at {nxt[:1]} -> {[nm for x, nm, s in classes if nxt and x == nxt[0]]}")
            print(dump(d, r.pos, min(len(d), r.pos + length)))
            k += 1
            if k >= n: break
if __name__ == "__main__":
    show(sys.argv[1], n=int(sys.argv[2]) if len(sys.argv) > 2 else 2, length=int(sys.argv[3]) if len(sys.argv) > 3 else 400)
