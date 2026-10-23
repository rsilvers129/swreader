"""The B-rep geometry of a part: each configuration's ``Contents/Config-N-Partition`` section is a GUID-wrapped,
zlib-compressed standard Parasolid binary transmit file (it begins ``PS\\0\\0\\0?: TRANSMIT FILE (partition)``).

It is a *partition* transmit file (it can hold rollback marks, not only the final bodies); whether Parasolid-based
tools accept it as a plain ``.x_b`` is untested. Decoding it into STEP is future work (see docs/ROADMAP.md)."""
from __future__ import annotations

import re

from .container import FormatError, SwFile, unwrap

PS_MAGIC = b"PS\x00\x00\x00"


def partitions(sw: SwFile) -> dict[str, bytes]:
    """{configuration index: Parasolid transmit bytes} for every non-ghost partition in the document."""
    out = {}
    for n in sw.names():
        m = re.fullmatch(r"Contents/Config-(\d+)-Partition", n)
        if not m:
            continue
        raw = sw.read(n)
        ps = unwrap(raw)
        if not ps.startswith(PS_MAGIC):
            raise FormatError(f"{n}: not a Parasolid transmit file")
        out[m.group(1)] = ps
    return out


def header(ps: bytes) -> dict:
    """Modeller version and schema from the transmit file's text header."""
    m = re.search(rb"created by modeller version (\d+)", ps[:200])
    s = re.search(rb"(SCH_[0-9_]+)", ps[:200])
    return {"modeller_version": int(m.group(1)) if m else None, "schema": s.group(1).decode() if s else None,
            "bytes": len(ps)}
