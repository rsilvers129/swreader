"""MFC CArchive primitives - the serialization SolidWorks uses for its object streams (feature tree, sketches,
drawing views and annotations ...).

Archive rules (standard MFC, documented by Microsoft):

* Object pointer: a WORD tag.
    ``0x0000``                 null pointer
    ``0xFFFF`` (wNewClassTag)  a class seen for the first time: ``WORD schema, WORD name length, ASCII name``,
                               then the new object's own data
    ``0x8000 | i`` (wClassTag) a new object of the already-seen class with map index ``i``, then its data
    ``0x7FFF`` (wBigObjectTag) followed by a DWORD tag with the same meaning, for archives with > 0x7FFE entries
    anything else              a reference to an already-loaded object with map index ``tag``
  Map indices start at 1 and are handed out, in order, to every new class *and* every new object.
* CString: ``0xFF 0xFFFE`` announces a UTF-16 string; then the length as BYTE, or ``0xFF`` + WORD, or
  ``0xFFFF`` + DWORD; then the characters. Without the ``0xFF 0xFFFE`` prefix the string is 8-bit.
* Counts (CObArray, CStringArray ...): WORD, or ``0xFFFF`` + DWORD.

What each class writes after its tag is up to that class; layouts are in :mod:`swreader.classes`.
"""
from __future__ import annotations

import struct

NULL_TAG, NEW_CLASS_TAG, BIG_OBJECT_TAG, CLASS_TAG = 0x0000, 0xFFFF, 0x7FFF, 0x8000
BIG_CLASS_TAG = 0x80000000


class ArchiveError(ValueError):
    pass


class Archive:
    """A read cursor over one object stream, with the archive's class/object map."""

    def __init__(self, data: bytes, pos: int = 0):
        self.data, self.pos = data, pos
        self.map: list = [None]               # index 0 = null; classes are stored as ("class", name, schema)
        self.classes: dict[str, int] = {}

    # -- primitives ----------------------------------------------------------------------------------------
    def _unpack(self, fmt):
        n = struct.calcsize(fmt)
        if self.pos + n > len(self.data):
            raise ArchiveError(f"read past end at {self.pos}")
        v = struct.unpack_from(fmt, self.data, self.pos)
        self.pos += n
        return v[0] if len(v) == 1 else v

    def u8(self):  return self._unpack("<B")
    def u16(self): return self._unpack("<H")
    def i16(self): return self._unpack("<h")
    def u32(self): return self._unpack("<I")
    def i32(self): return self._unpack("<i")
    def u64(self): return self._unpack("<Q")
    def f32(self): return self._unpack("<f")
    def f64(self): return self._unpack("<d")

    def raw(self, n):
        if self.pos + n > len(self.data):
            raise ArchiveError(f"read past end at {self.pos}")
        b = self.data[self.pos:self.pos + n]
        self.pos += n
        return b

    def peek(self, n=2):
        return self.data[self.pos:self.pos + n]

    def at_end(self):
        return self.pos >= len(self.data)

    def count(self):
        n = self.u16()
        return self.u32() if n == 0xFFFF else n

    def cstring(self) -> str:
        n = self.u8()
        wide = False
        if n == 0xFF:
            n = self.u16()
            if n == 0xFFFE:
                wide = True
                n = self.u8()
                if n == 0xFF:
                    n = self.u16()
            if n == 0xFFFF:
                n = self.u32()
        b = self.raw(2 * n if wide else n)
        return b.decode("utf-16-le", "replace") if wide else b.decode("cp1252", "replace")

    # -- object tags ---------------------------------------------------------------------------------------
    def tag(self):
        """Read an object tag. Returns ("null",), ("new", class_name, schema, index_of_object),
        ("ref", index, obj_or_class_entry)."""
        t = self.u16()
        if t == BIG_OBJECT_TAG:
            t32 = self.u32()
            if t32 & BIG_CLASS_TAG:
                return self._new_of(t32 & ~BIG_CLASS_TAG)
            return ("ref", t32, self._get(t32))
        if t == NULL_TAG:
            return ("null",)
        if t == NEW_CLASS_TAG:
            schema, ln = self.u16(), self.u16()
            name = self.raw(ln).decode("ascii", "replace")
            self.map.append(("class", name, schema))
            self.classes[name] = len(self.map) - 1
            return self._new_object(name, schema)
        if t & CLASS_TAG:
            return self._new_of(t & ~CLASS_TAG)
        return ("ref", t, self._get(t))

    def _new_of(self, ci):
        e = self._get(ci)
        if not (isinstance(e, tuple) and e and e[0] == "class"):
            raise ArchiveError(f"class tag points at non-class map entry {ci} at {self.pos}")
        return self._new_object(e[1], e[2])

    def _new_object(self, name, schema):
        self.map.append(("pending", name))
        return ("new", name, schema, len(self.map) - 1)

    def _get(self, i):
        if i >= len(self.map):
            raise ArchiveError(f"reference to map index {i} beyond {len(self.map) - 1} at {self.pos}")
        return self.map[i]


def find_class_names(data: bytes) -> list[tuple[int, str, int]]:
    """(offset, class name, schema) of every new-class tag in a stream - for exploration."""
    import re
    out = []
    for m in re.finditer(rb"\xff\xff(..)(..)", data, re.S):
        schema, ln = struct.unpack("<HH", m.group(1) + m.group(2))
        if not 3 <= ln <= 80:
            continue
        s = m.end()
        name = data[s:s + ln]
        if all(48 <= c < 123 and (chr(c).isalnum() or c == 95) for c in name):
            out.append((m.start(), name.decode(), schema))
    return out
