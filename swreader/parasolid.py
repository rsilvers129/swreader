"""The B-rep geometry of a part, stored as standard Parasolid binary transmit files (``PS\\0\\0\\0?: TRANSMIT FILE``).

Where the bodies are (layout notes from OrchardCAD, P. Gallogly; checked on our own corpus):

* ``Contents/Config-N-Partition`` - the bodies of configuration N, as a *partition* transmit, usually followed in the
  same stream by a *deltas* transmit (rollback marks). It can be an empty partition (~300 bytes): when the part's body
  comes from an imported feature, the bodies are in
* ``Config-N-FeatureBodies/LocalBodies`` (no ``Contents/``) - ``count:u32`` records of a UTF-16 CString name (the
  feature, e.g. ``part.step<1>``), a few words, then one chained section holding a plain *part* transmit;
* ``Contents/Config-N-StockBodies`` - base bodies of derived parts.

``Config-N-GhostPartition`` is never the model. Decoding a transmit into STEP is future work (docs/ROADMAP.md).
"""
from __future__ import annotations

import re

from .container import FormatError, SwFile, sections

PS_MAGIC = b"PS\x00\x00\x00"
EMPTY_PARTITION = 400        # an empty partition transmit is ~300 bytes; any real body is far larger


def _guise(ps: bytes) -> str:
    head = ps[:200]
    return "partition" if b"(partition)" in head else "deltas" if b"(deltas)" in head else "part"


def transmits(sw: SwFile) -> list[dict]:
    """Every Parasolid transmit in the document: {stream, config, guise, name, data}. ``name`` is the feature name for
    FeatureBodies records, else None."""
    out = []
    for n in sw.names():
        m = re.fullmatch(r"(?:Contents/)?Config-(\d+)-(Partition|StockBodies|FeatureBodies/.+)", n)
        if not m:
            continue
        raw = sw.read(n) or b""
        names = _record_names(raw) if m.group(2).startswith("FeatureBodies") else []
        for i, (g, ps) in enumerate(sections(raw)):
            if not ps:
                continue
            if not ps.startswith(PS_MAGIC):
                raise FormatError(f"{n}: section at {g} is not a Parasolid transmit file")
            out.append({"stream": n, "config": m.group(1), "guise": _guise(ps),
                        "name": names[i] if i < len(names) else None, "data": ps})
    return out


def _record_names(raw: bytes) -> list[str]:
    """Feature names of the FeatureBodies records: the last UTF-16 CString (``FF FE FF len``) before each GUID."""
    names, pos = [], 0
    for g, _ in sections(raw):
        s = raw.rfind(b"\xff\xfe\xff", pos, g)
        if s < 0:
            names.append(None)
            continue
        n = raw[s + 3]
        names.append(raw[s + 4:s + 4 + 2 * n].decode("utf-16-le", "replace"))
        pos = g + 16
    return names


def partitions(sw: SwFile) -> dict[str, bytes]:
    """{configuration index: partition transmit bytes} for every non-ghost partition in the document."""
    return {t["config"]: t["data"] for t in transmits(sw)
            if t["guise"] == "partition" and re.fullmatch(r"Contents/Config-\d+-Partition", t["stream"])}


def model(sw: SwFile, config: str | None = None) -> list[dict]:
    """The transmits that hold the bodies of one configuration (default: the lowest-numbered one): the partition if
    it is not empty, else the imported (FeatureBodies) or stock bodies."""
    ts = [t for t in transmits(sw) if t["guise"] != "deltas"]
    if config is None:
        cs = sorted({t["config"] for t in ts}, key=int)
        if not cs:
            return []
        config = cs[0]
    ts = [t for t in ts if t["config"] == config]
    full = [t for t in ts if t["guise"] == "partition" and len(t["data"]) > EMPTY_PARTITION]
    return full or [t for t in ts if t["guise"] == "part"]


def header(ps: bytes) -> dict:
    """Modeller version and schema from the transmit file's text header."""
    m = re.search(rb"created by modeller version (\d+)", ps[:200])
    s = re.search(rb"(SCH_[0-9_]+)", ps[:200])
    return {"modeller_version": int(m.group(1)) if m else None, "schema": s.group(1).decode() if s else None,
            "guise": _guise(ps), "bytes": len(ps)}
