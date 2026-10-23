"""Annotated dump of an object stream, for working out class layouts.

Marks new-class tags, UTF-16 CStrings, and 8-byte values that look like real-world doubles (lengths in metres,
angles in radians); everything else is shown as hex words. Pure heuristics: a reading aid, not a parser."""
from __future__ import annotations

import math
import struct

from .mfc import find_class_names


def _cstring_at(d, i):
    """A UTF-16 CString starting at i -> (text, end) or None."""
    if d[i:i + 3] != b"\xff\xfe\xff":
        return None
    n, p = d[i + 3], i + 4
    if n == 0xFF:
        if p + 2 > len(d):
            return None
        n, p = struct.unpack_from("<H", d, p)[0], p + 2
    end = p + 2 * n
    if end > len(d):
        return None
    try:
        s = d[p:end].decode("utf-16-le")
    except UnicodeDecodeError:
        return None
    return (s, end) if s.isprintable() else None


def nice_double(v: float) -> bool:
    if not math.isfinite(v) or v == 0:
        return v == 0.0
    a = abs(v)
    if not 1e-7 <= a <= 1e4:
        return False
    for scale in (1e3, 1e3 * 25.4 / 1e3 / 25.4):          # mm, then inches expressed in metres
        x = a * 1000.0
        if abs(x - round(x, 4)) < 1e-9 or abs(a / 0.0254 - round(a / 0.0254, 4)) < 1e-9:
            return True
    deg = math.degrees(a)
    return abs(deg - round(deg, 3)) < 1e-7


def dump(data: bytes, start: int = 0, end: int | None = None, width: int = 16) -> str:
    end = len(data) if end is None else end
    classes = {o: (n, s) for o, n, s in find_class_names(data)}
    out, hexbuf, i = [], [], start

    def flush():
        if hexbuf:
            out.append("      " + " ".join(hexbuf))
            hexbuf.clear()

    while i < end:
        if i in classes:
            flush()
            n, s = classes[i]
            out.append(f"{i:8d}  NEW CLASS {n} (schema {s})")
            i += 6 + len(n)
            continue
        cs = _cstring_at(data, i)
        if cs:
            flush()
            out.append(f"{i:8d}  STR {cs[0]!r}")
            i = cs[1]
            continue
        if i + 8 <= end:
            v = struct.unpack_from("<d", data, i)[0]
            if v != 0.0 and nice_double(v):
                flush()
                out.append(f"{i:8d}  F64 {v!r}" + (f"   ({v * 1000:g} mm / {v / 0.0254:g} in)" if abs(v) < 10 else ""))
                i += 8
                continue
        if not hexbuf:
            hexbuf.append(f"{i:d}:")
        hexbuf.append(data[i:i + 2].hex())
        i += 2
        if len(hexbuf) > width:
            flush()
    flush()
    return "\n".join(out)
