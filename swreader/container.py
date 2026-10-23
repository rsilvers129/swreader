"""Read the sections (named streams) of a SolidWorks document without SolidWorks.

Two container formats exist:

* 2015 and later ("zip"): a ZIP-like archive. Each section has a local header
  ``<4 bytes> 00 00 00 04 <6 bytes> 14 00 06 00 08 00 <time> <date> <crc32> <csize> <usize> <namelen u32> <name>``
  followed by ``csize`` bytes of raw deflate. Every byte of the name is nibble-swapped (rotated left by 4).
  The file also contains decoy headers whose data does not decompress or fails the CRC, so a section is only
  accepted once its data inflates to ``usize`` bytes with a matching CRC-32.
* before 2015 ("ole"): an OLE2 compound document holding streams with the same names. Streams whose name ends in
  ``__ZLB`` (and the Parasolid partitions) carry a small header and a zlib stream; see :func:`unwrap`.

Only the file's bytes are examined; nothing here depends on SolidWorks itself.
"""
from __future__ import annotations

import re
import struct
import zlib
from dataclasses import dataclass, field

ZIP_MARK = b"\x14\x00\x06\x00\x08\x00"
OLE_MAGIC = b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1"
# GUID that starts the wrapper of compressed OLE streams and Parasolid partitions (stored little-endian)
WRAP_GUID = bytes.fromhex("231dd571da8148a2a85898b21b89ef99")


def nibble_swap(b: bytes) -> bytes:
    return bytes(((x << 4) | (x >> 4)) & 0xFF for x in b)


class FormatError(ValueError):
    pass


@dataclass
class _Candidate:
    offset: int          # start of the compressed data
    csize: int
    usize: int
    crc: int


@dataclass
class SwFile:
    """An opened SolidWorks document. ``names()`` lists sections; ``read(name)`` returns a section's bytes."""
    path: str
    kind: str                                   # "zip" or "ole"
    _data: bytes = field(repr=False, default=b"")
    _cands: dict = field(repr=False, default_factory=dict)
    _ole: object = field(repr=False, default=None)
    _cache: dict = field(repr=False, default_factory=dict)

    # -- listing -------------------------------------------------------------------------------------------
    def names(self) -> list[str]:
        if self.kind == "ole":
            return sorted({_ole_name(n) for n in self._ole_streams()})
        return [n for n in self._cands if self.read(n) is not None]

    def has(self, name: str) -> bool:
        return self.read(name) is not None

    # -- reading -------------------------------------------------------------------------------------------
    def read(self, name: str) -> bytes | None:
        """The section's uncompressed bytes, or None when the document has no valid section of that name."""
        if name in self._cache:
            return self._cache[name]
        out = self._read_ole(name) if self.kind == "ole" else self._read_zip(name)
        self._cache[name] = out
        return out

    def _read_zip(self, name):
        for c in reversed(self._cands.get(name, [])):        # the last valid copy wins
            try:
                u = zlib.decompressobj(-15).decompress(self._data[c.offset:c.offset + c.csize]) if c.csize else b""
            except zlib.error:
                continue
            if len(u) == c.usize and (zlib.crc32(u) & 0xFFFFFFFF) == c.crc:
                return u
        return None

    def _ole_streams(self):
        return ["/".join(p) for p in self._ole.listdir(streams=True)]

    def _read_ole(self, name):
        streams = self._ole_streams()
        for s in (name, name + "__ZLB"):
            if s in streams:
                raw = self._ole.openstream(s).read()
                return unwrap(raw) if s.endswith("__ZLB") else raw
        return None

    def close(self):
        if self._ole is not None:
            self._ole.close()

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        self.close()


def _ole_name(stream: str) -> str:
    return stream[:-5] if stream.endswith("__ZLB") else stream


def open_file(path: str) -> SwFile:
    with open(path, "rb") as f:
        data = f.read()
    if data[:8] == OLE_MAGIC:
        try:
            import olefile
        except ImportError as e:                                        # pragma: no cover
            raise FormatError("pre-2015 SolidWorks file: install 'olefile' to read it") from e
        return SwFile(path, "ole", _ole=olefile.OleFileIO(data))
    cands = scan_zip(data)
    if not cands:
        raise FormatError(f"{path}: not a SolidWorks document (no sections found)")
    return SwFile(path, "zip", _data=data, _cands=cands)


def scan_zip(data: bytes) -> dict[str, list[_Candidate]]:
    """Every plausible local header, by section name, in file order. Validation happens on read."""
    out: dict[str, list[_Candidate]] = {}
    n = len(data)
    for m in re.finditer(re.escape(ZIP_MARK), data):
        i = m.start()
        if i + 26 > n:
            continue
        crc, csize, usize, nlen = struct.unpack_from("<IIII", data, i + 10)
        start = i + 26 + nlen
        if not (0 < nlen < 512) or start + csize > n or usize > 1 << 32:
            continue
        name = nibble_swap(data[i + 26:start])
        try:
            s = name.decode("utf-8")
        except UnicodeDecodeError:
            continue
        if not s.isprintable():
            continue
        out.setdefault(s, []).append(_Candidate(start, csize, usize, crc))
    return out


def unwrap(raw: bytes) -> bytes:
    """Strip the GUID wrapper used by compressed OLE streams and by Parasolid partitions, and inflate the zlib
    stream behind it. Data without a wrapper is returned unchanged."""
    g = raw.find(WRAP_GUID, 0, 64)
    if g < 0:
        return raw
    if not raw[g + 16:].strip(b"\x00"):                  # empty stream: GUID + zero sizes only
        return b""
    for off in range(g + 16, min(len(raw), g + 48)):
        if raw[off] == 0x78 and (raw[off] << 8 | raw[off + 1]) % 31 == 0:
            try:
                return zlib.decompressobj().decompress(raw[off:])
            except zlib.error:
                continue
    raise FormatError("wrapped stream: no zlib data after the GUID")
