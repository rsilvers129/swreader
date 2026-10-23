"""dev: distribution of the distance from the end of the base layout of CLASS to the next NEW CLASS record."""
import sys, collections
import tryclass as T
import swreader.classes as C
def gaps(cls, base=C.feature, want=None):
    g = collections.defaultdict(collections.Counter)
    for p, ver, d, node, classes in T.corpus():
        at = [o for o, nm, s in classes if nm == cls]
        if not at: continue
        r = T.Loose(d, at[0] + 6 + len(cls), ver, node, classes); o = {}
        try: base(r, o)
        except Exception: continue
        nxt = [(x, nm) for x, nm, s in classes if x >= r.pos]
        if not nxt: continue
        x, nm = min(nxt)
        if want and nm != want: g[ver]["other:" + nm] += 1; continue
        g[ver][x - r.pos] += 1
    for v in sorted(g): print(f"  {v:6d}", g[v].most_common(6))
if __name__ == "__main__":
    gaps(sys.argv[1], want=sys.argv[2] if len(sys.argv) > 2 else None)
