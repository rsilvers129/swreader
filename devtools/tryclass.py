"""dev: test a layout for CLASS on its first instance in every document of the corpus.
An instance passes when, after the layout, the next 2 bytes are a plausible object tag."""
import sys, os, re, random, collections, struct, importlib
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
from swreader import open_file
from swreader.mfc import find_class_names
import swreader.objects as O
import swreader.classes as C
import swreader.features as F

ROOT = os.environ.get("SWREADER_SAMPLES", ".")
_cache = {}

def corpus(section="Contents/Config-0-ResolvedFeatures", ext=".sldprt", limit=None):
    """[(path, version, stream, node tag, classes)] for every document under SWREADER_SAMPLES (os.pathsep-separated
    roots). The default section means "the feature tree" (lowest-numbered configuration that has one). With
    SWREADER_CACHE set, the list is pickled there and reused."""
    key = (section, ext)
    if key in _cache: return _cache[key]
    cache = os.environ.get("SWREADER_CACHE")
    if cache and section == "Contents/Config-0-ResolvedFeatures" and ext == ".sldprt" and os.path.exists(cache):
        import pickle
        out = pickle.load(open(cache, "rb"))
        _cache[key] = out[:limit] if limit else out
        return _cache[key]
    files = [os.path.join(r, f) for root in ROOT.split(os.pathsep) for r, _, fs in os.walk(root) for f in fs
             if f.lower().endswith(ext) and not f.startswith(("._", "~$"))]
    random.seed(7); random.shuffle(files)
    out = []
    for p in files[:limit]:
        if os.path.getsize(p) == 0: continue
        try:
            with open_file(p) as sw:
                mv = [n for n in sw.names() if n.startswith("_MO_VERSION_")]
                ver = int(mv[0].split("/")[0][12:]) if mv else 0
                if section == "Contents/Config-0-ResolvedFeatures":
                    fs = F.feature_stream(sw)
                    d = fs[1] if fs else None
                else:
                    d = sw.read(section)
        except Exception: continue
        if not d: continue
        c = collections.Counter(d[m.start()-2:m.start()] for m in re.finditer(rb"\xff\xfe\xff", d) if m.start() >= 2 and d[m.start()-1] & 0x80)
        node = struct.unpack("<H", c.most_common(1)[0][0])[0] if c else None
        out.append((p, ver, d, node, find_class_names(d)))
    if cache and not limit and section == "Contents/Config-0-ResolvedFeatures" and ext == ".sldprt":
        import pickle
        pickle.dump(out, open(cache, "wb"))
    _cache[key] = out
    return out

class Loose(O.Reader):
    """Reader for an isolated instance: knows the node-name class tag; classes defined in the stream resolve."""
    def __init__(self, d, pos, ver, node, classes):
        super().__init__(d, pos, version=ver)
        self.node = node
        self.newat = {o: (n, s) for o, n, s in classes}
    def tag(self):
        t = struct.unpack_from("<H", self.data, self.pos)[0]
        if t == self.node:
            self.pos += 2
            self.map.append(("pending", "moNodeName_c"))
            return ("new", "moNodeName_c", 1, len(self.map) - 1)
        if self.pos in self.newat:
            return super().tag()
        if t & 0x8000 and t != 0xFFFF:
            raise O.ArchiveError(f"class ref {t:#x} at {self.pos} (unknown in isolation)")
        if t == 0 or t == 0xFFFF:
            return super().tag()
        self.pos += 2
        return ("ref", t, None)

def plausible_next(d, i, classes_at):
    if i >= len(d): return True
    if i in classes_at: return True
    t = struct.unpack_from("<H", d, i)[0] if i + 2 <= len(d) else None
    return t is not None and (t == 0 or (t & 0x8000 and t != 0xFFFF and (t & 0x7FFF) < 0x4000))

def run(cls, section="Contents/Config-0-ResolvedFeatures", ext=".sldprt", show=3, versions=None, limit=None):
    importlib.reload(C)
    res = collections.defaultdict(collections.Counter); bad = collections.defaultdict(list)
    for p, ver, d, node, classes in corpus(section, ext, limit):
        if versions and ver not in versions: continue
        at = [o for o, n, s in classes if n == cls]
        if not at: continue
        o0 = at[0]; start = o0 + 6 + len(cls)
        r = Loose(d, start, ver, node, classes)
        obj = {"_c": cls}
        try:
            O.REGISTRY[cls](r, obj)
            ok = plausible_next(d, r.pos, {o for o, n, s in classes})
            res[ver]["ok" if ok else "bad-next"] += 1
            if not ok: bad[ver].append((p, d, start, r.pos, obj))
        except Exception as e:
            res[ver]["exc"] += 1
            bad[ver].append((p, d, start, r.pos, f"{type(e).__name__}: {e}"))
    for v in sorted(res): print(f"  {v:6d}: {dict(res[v])}")
    return bad
