"""dev: distance from the start of CLASS's first instance data (after its NEW CLASS record) to the next landmark:
a NEW CLASS record or a `<class tag><node tag> FF FE FF` named-object start."""
import sys, collections, re, struct
import tryclass as T
def landmarks(d, node, classes):
    L = {x: nm for x, nm, s in classes}
    if node:
        for m in re.finditer(re.escape(struct.pack("<H", node)) + rb"\xff\xfe\xff", d):
            L.setdefault(m.start() - 2, "<named>")
    return sorted(L.items())
def gaps(cls, skip=0):
    g = collections.defaultdict(collections.Counter)
    for p, ver, d, node, classes in T.corpus():
        at = [o for o, nm, s in classes if nm == cls]
        if not at: continue
        s0 = at[0] + 6 + len(cls) + skip
        nxt = [(x, nm) for x, nm in landmarks(d, node, classes) if x >= s0]
        if not nxt: continue
        x, nm = nxt[0]
        g[ver][(x - s0, nm)] += 1
    for v in sorted(g): print(f"  {v:6d}", g[v].most_common(5))
if __name__ == "__main__":
    gaps(sys.argv[1])
