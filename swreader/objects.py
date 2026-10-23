"""Object-stream parser: walks an MFC archive, decoding each object with the layout registered for its class.

Layouts live in :mod:`swreader.classes` and are registered with :func:`layout`. Each layout is a function
``fn(r, o)`` that reads the class's fields from reader ``r`` into dict ``o``. Base-class parts are shared helpers.

Unknown classes stop the walk with :class:`UnknownClass` (the position and class name tell what to decode next).
"""
from __future__ import annotations

from .mfc import Archive, ArchiveError

REGISTRY: dict[str, callable] = {}


def layout(*names):
    def deco(fn):
        for n in names:
            REGISTRY[n] = fn
        return fn
    return deco


class UnknownClass(ArchiveError):
    def __init__(self, name, pos, index):
        super().__init__(f"no layout for class {name} (object at {pos}, map index {index})")
        self.name, self.pos, self.index = name, pos, index


class Ref:
    """A reference to an object loaded earlier in the archive."""
    __slots__ = ("index", "target")

    def __init__(self, index, target):
        self.index, self.target = index, target

    def __repr__(self):
        t = self.target
        c = t.get("_c") if isinstance(t, dict) else None
        return f"<ref {self.index}{' ' + c if c else ''}>"


class Reader(Archive):
    def __init__(self, data: bytes, pos: int = 0, version: int | None = None):
        super().__init__(data, pos)
        self.version = version          # document version (moPart_c/moAssembly_c/moDrawing_c first field)
        self.trace: list = []           # (pos, class, index) of every new object - for debugging layouts

    def feed(self, data: bytes):
        """Continue with the next stream of the same archive (the map is shared)."""
        self.data, self.pos = data, 0

    def obj(self):
        start = self.pos
        t = self.tag()
        if t[0] == "null":
            return None
        if t[0] == "ref":
            return Ref(t[1], t[2])
        _, name, schema, idx = t
        fn = REGISTRY.get(name)
        if fn is None:
            raise UnknownClass(name, start, idx)
        o = {"_c": name, "_i": idx}
        self.map[idx] = o
        self.trace.append((start, name, idx))
        fn(self, o)
        return o

    def objs(self, n=None):
        n = self.count() if n is None else n
        return [self.obj() for _ in range(n)]

    def cstrings(self, n=None):
        n = self.count() if n is None else n
        return [self.cstring() for _ in range(n)]

    def f64s(self, n):
        return [self.f64() for _ in range(n)]

    def u32s(self, n):
        return [self.u32() for _ in range(n)]
