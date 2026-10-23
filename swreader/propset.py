"""Minimal reader for OLE property sets ([MS-OLEPS]) as stored by pre-2015 SolidWorks documents
(``\\x05DocumentSummaryInformation``, ``Config-0-Properties``, ``ISolidWorksInformation``)."""
from __future__ import annotations

import datetime
import struct

USER_DEFINED = bytes.fromhex("05d5cdd59c2e1b10939708002b2cf9ae")   # {D5CDD505-2E9C-101B-9397-08002B2CF9AE}

VT_I2, VT_I4, VT_R4, VT_R8, VT_BOOL, VT_UI4, VT_LPSTR, VT_LPWSTR, VT_FILETIME = 2, 3, 4, 5, 11, 19, 30, 31, 64


def parse(data: bytes) -> list[dict]:
    """All sections: [{"fmtid": bytes, "props": {name_or_pid: value}}]."""
    if len(data) < 28 or data[:2] != b"\xfe\xff":
        return []
    (count,) = struct.unpack_from("<I", data, 24)
    out = []
    for k in range(count):
        fmtid = data[28 + 20 * k:44 + 20 * k]
        (off,) = struct.unpack_from("<I", data, 44 + 20 * k)
        out.append({"fmtid": fmtid, "props": _section(data, off)})
    return out


def user_properties(data: bytes) -> dict:
    """The user-defined (custom) properties, by name."""
    for s in parse(data):
        if s["fmtid"] == USER_DEFINED:
            return {k: v for k, v in s["props"].items() if isinstance(k, str)}
    return {}


def _section(data, base):
    _size, n = struct.unpack_from("<II", data, base)
    pids = [struct.unpack_from("<II", data, base + 8 + 8 * i) for i in range(n)]
    raw = {pid: base + off for pid, off in pids}
    codepage = 1252
    if 1 in raw:
        codepage = struct.unpack_from("<h", data, raw[1] + 4)[0] & 0xFFFF
    enc = {65001: "utf-8", 1200: "utf-16-le"}.get(codepage, f"cp{codepage}")
    names = _dictionary(data, raw[0], enc) if 0 in raw else {}
    props = {}
    for pid, at in raw.items():
        if pid in (0, 1):
            continue
        try:
            props[names.get(pid, pid)] = _value(data, at, enc)
        except (struct.error, LookupError, UnicodeDecodeError):
            continue
    return props


def _dictionary(data, at, enc):
    (n,) = struct.unpack_from("<I", data, at)
    p, out = at + 4, {}
    for _ in range(n):
        pid, ln = struct.unpack_from("<II", data, p)
        p += 8
        if enc == "utf-16-le":
            s = data[p:p + 2 * ln].decode(enc)
            p += 2 * ln
            p += (-p) % 4
        else:
            s = data[p:p + ln].decode(enc, "replace")
            p += ln
        out[pid] = s.rstrip("\x00")
    return out


def _value(data, at, enc):
    (vt,) = struct.unpack_from("<I", data, at)
    p = at + 4
    if vt == VT_I2:
        return struct.unpack_from("<h", data, p)[0]
    if vt in (VT_I4,):
        return struct.unpack_from("<i", data, p)[0]
    if vt == VT_UI4:
        return struct.unpack_from("<I", data, p)[0]
    if vt == VT_R4:
        return struct.unpack_from("<f", data, p)[0]
    if vt == VT_R8:
        return struct.unpack_from("<d", data, p)[0]
    if vt == VT_BOOL:
        return struct.unpack_from("<h", data, p)[0] != 0
    if vt == VT_LPSTR:
        (ln,) = struct.unpack_from("<I", data, p)
        return data[p + 4:p + 4 + ln].decode(enc, "replace").rstrip("\x00")
    if vt == VT_LPWSTR:
        (ln,) = struct.unpack_from("<I", data, p)
        return data[p + 4:p + 4 + 2 * ln].decode("utf-16-le", "replace").rstrip("\x00")
    if vt == VT_FILETIME:
        (ft,) = struct.unpack_from("<Q", data, p)
        return (datetime.datetime(1601, 1, 1) + datetime.timedelta(microseconds=ft // 10)).isoformat() if ft else None
    raise LookupError(vt)
