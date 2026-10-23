"""Checks against real documents. Skipped unless SWREADER_SAMPLES points to a folder of SolidWorks files.
Nothing about those files (names, values) is written into the repository."""
import os

import pytest

from swreader import open_file
from swreader import parasolid, props

ROOT = os.environ.get("SWREADER_SAMPLES")
EXTS = (".sldprt", ".sldasm", ".slddrw")


def documents():
    if not ROOT:
        return []
    return sorted(os.path.join(r, f) for r, _, fs in os.walk(ROOT) for f in fs if f.lower().endswith(EXTS))


pytestmark = pytest.mark.skipif(not ROOT, reason="set SWREADER_SAMPLES to a folder of SolidWorks documents")


@pytest.mark.parametrize("path", documents(), ids=lambda p: os.path.relpath(p, ROOT))
def test_document(path):
    with open_file(path) as sw:
        s = props.summary(sw)
        assert s["type"] in ("part", "assembly", "drawing")
        assert s["has_preview"]
        assert sw.read("PreviewPNG") is None or sw.read("PreviewPNG").startswith(b"\x89PNG")
        if s["type"] == "part":
            parts = parasolid.partitions(sw)
            assert parts, "a part should carry a Parasolid partition"
            for ps in parts.values():
                assert parasolid.header(ps)["schema"].startswith("SCH_")
