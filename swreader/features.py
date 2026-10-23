"""The feature tree: walk ``Contents/Config-N-ResolvedFeatures``.

That stream continues the MFC archive of ``Contents/Config-N`` (one shared class/object map), but most of what
``Config-N`` holds (units, lights, views ...) is not needed for features. So the walk starts with a map whose
first ``base`` entries are opaque, and finds ``base`` itself:

* the node-name class (``moNodeName_c``) is defined in ``Config-N``; its index is the tag in front of the first
  name string of the stream;
* ``base`` is the number of map entries ``Config-N`` created. From format 8000 (SolidWorks 2008/2009) on, the stream
  starts with it as a u32. Older streams do not store it: it is unknown until the stream first refers back to a
  class it defined itself; each class defined so far gives one candidate, and the candidate that lets the walk
  get furthest wins.
"""
from __future__ import annotations

import re
import struct

from . import classes  # noqa: F401  (registers layouts)
from .mfc import ArchiveError
from .objects import Reader, UnknownClass


class NeedBase(ArchiveError):
    def __init__(self, index, local_classes):
        super().__init__(f"class index {index} before the map base is known")
        self.index, self.local_classes = index, local_classes


class StreamReader(Reader):
    def __init__(self, data, version, node_index, base=None):
        super().__init__(data, version=version)
        self.node_index, self.base = node_index, base
        self.local_classes: list[int] = []          # local map offsets (0-based after base) of classes defined here
        n = base if base is not None else node_index
        self.map = [None] + [("ext",)] * n
        self.map[node_index] = ("class", "moNodeName_c", 1)

    def tag(self):
        t = self.u16()
        if t == 0x7FFF:
            t = self.u32()
            big = True
        else:
            big = False
        cls_bit = 0x80000000 if big else 0x8000
        if t == 0:
            return ("null",)
        if not big and t == 0xFFFF:
            schema, ln = self.u16(), self.u16()
            name = self.raw(ln).decode("ascii", "replace")
            self.map.append(("class", name, schema))
            self.local_classes.append(len(self.map) - 1 - self._offset())
            return self._new_object(name, schema)
        if t & cls_bit:
            i = t & ~cls_bit
            if i == self.node_index:
                return self._new_object("moNodeName_c", 1)
            if self.base is None:
                raise NeedBase(i, list(self.local_classes))
            return self._new_of(i)
        if t < len(self.map):
            return ("ref", t, self.map[t])
        if self.base is None:
            return ("ref", t, None)                    # unresolved until the base is known
        raise ArchiveError(f"reference to map index {t} beyond {len(self.map) - 1} at {self.pos}")

    def _new_of(self, ci):
        e = self.map[ci] if ci < len(self.map) else None
        if e == ("ext",):
            return ("new", ("ext", ci), 1, self._new_object(("ext", ci), 1)[3])
        return super()._new_of(ci)

    def _offset(self):
        return (self.base if self.base is not None else self.node_index) + 1


def feature_stream(sw) -> tuple[str, bytes] | None:
    """(section name, data) of the feature tree of the lowest-numbered configuration that has one."""
    found = []
    for n in sw.names():
        m = re.fullmatch(r"Contents/Config-(\d+)-ResolvedFeatures", n)
        if m:
            found.append((int(m.group(1)), n))
    for _, n in sorted(found):
        d = sw.read(n)
        if d:
            return n, d
    return None


def _node_index(data: bytes) -> int | None:
    i = data.find(b"\xff\xfe\xff")
    if i < 2:
        return None
    t = struct.unpack_from("<H", data, i - 2)[0]
    return t & 0x7FFF if t & 0x8000 else None


STORED_BASE = 8000                                   # first format version whose stream starts with the map base


def walk(data: bytes, version: int, base: int | None = None):
    """Walk the stream. Returns (top-level objects, reader, error or None)."""
    node = _node_index(data)
    if node is None:
        raise ArchiveError("no named object in stream")
    if version >= STORED_BASE:
        # the stored value is the archive's map count, which includes the null entry 0
        return _walk_once(data, version, node, struct.unpack_from("<I", data, 0)[0] - 1, start=4)
    if base is None:
        objs, r, err = _walk_once(data, version, node, None)
        if not isinstance(err, NeedBase):
            return objs, r, err
        best = None
        for j in err.local_classes:
            cand = err.index - (j + 1)
            if cand < node:
                continue
            res = _walk_once(data, version, node, cand)
            if best is None or res[1].pos > best[1].pos:
                best = res
        return best if best else (objs, r, err)
    return _walk_once(data, version, node, base)


def _walk_once(data, version, node, base, start=0):
    r = StreamReader(data, version, node, base)
    r.pos = start
    objs = []
    try:
        n = r.count()
        for _ in range(n):
            o = r.obj()
            if o is None:
                raise ArchiveError(f"null item in the feature list at {r.pos}")
            objs.append(o)
        return objs, r, None
    except (ArchiveError, ValueError) as e:
        return objs, r, e
