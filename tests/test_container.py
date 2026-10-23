"""Unit tests on synthetic documents (no SolidWorks files are kept in this repository).

Set SWREADER_SAMPLES=/path/to/a/folder/of/documents to also run the checks in test_samples.py on real files."""
import struct
import zlib

import pytest

from swreader import FormatError, open_file, unwrap
from swreader.container import WRAP_GUID, ZIP_MARK, nibble_swap, sections
from swreader import props


def section(name: str, payload: bytes, crc=None) -> bytes:
    """One local header + raw-deflate data, laid out like a 2015+ document."""
    c = zlib.compressobj(9, zlib.DEFLATED, -15)
    comp = c.compress(payload) + c.flush()
    n = name.encode()
    crc = zlib.crc32(payload) & 0xFFFFFFFF if crc is None else crc
    return (b"\x01\x02\x03\x04\x00\x00\x00\x04" + b"\x55" * 6 + ZIP_MARK + b"\x00\x00\x00\x00"
            + struct.pack("<IIII", crc, len(comp), len(payload), len(n)) + nibble_swap(n) + comp)


def decoy(name: str) -> bytes:
    """A header whose sizes look plausible but whose data is noise - real documents contain these."""
    n = name.encode()
    return (b"\x09\x09\x09\x09\x00\x00\x00\x04" + b"\x55" * 6 + ZIP_MARK + b"\x00\x00\x00\x00"
            + struct.pack("<IIII", 1020, 20, 510, len(n)) + nibble_swap(n) + bytes(range(7, 27)))


CUSTOM = b"""<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Properties xmlns="http://schemas.openxmlformats.org/officeDocument/2006/custom-properties"
 xmlns:vt="http://schemas.openxmlformats.org/officeDocument/2006/docPropsVTypes">
<propertySection xmlns="" name="UserDefinedProperties" fmtid="{D5CDD505-2E9C-101B-9397-08002B2CF9AE}">
<property name="" pid="1"><vt:i2>65001</vt:i2></property>
<property name="Description" pid="2"><vt:lpstr>Test bushing</vt:lpstr></property>
<property name="Revision" pid="3"><vt:lpstr>B</vt:lpstr></property>
</propertySection></Properties>"""

INFO = CUSTOM.replace(b"Description", b"SW-MassProp-Config-0").replace(
    b"Test bushing", b"0.001, 0.002, 0.003, 0.0000125, 0.0042, 0.0975, 0.1, 0.2, 0.3, 0, 0, 0, 1, 0").replace(
    b"Revision", b"SW_UnitsLinear").replace(b"<vt:lpstr>B</vt:lpstr>", b"<vt:i4>3</vt:i4>")


@pytest.fixture
def doc(tmp_path):
    p = tmp_path / "bushing.SLDPRT"
    p.write_bytes(decoy("PreviewPNG") + section("docProps/custom.xml", CUSTOM) + decoy("docProps/custom.xml")
                  + section("PreviewPNG", b"\x89PNG\r\n\x1a\nfake") + section("docProps/ISolidWorksInformation.xml", INFO)
                  + section("Contents/Broken", b"payload", crc=1))
    return str(p)


def test_names_skip_decoys_and_bad_crc(doc):
    with open_file(doc) as sw:
        assert sw.kind == "zip"
        assert sorted(sw.names()) == ["PreviewPNG", "docProps/ISolidWorksInformation.xml", "docProps/custom.xml"]
        assert sw.read("PreviewPNG").startswith(b"\x89PNG")
        assert sw.read("Contents/Broken") is None
        assert sw.read("missing") is None


def test_properties(doc):
    with open_file(doc) as sw:
        s = props.summary(sw)
    assert s["type"] == "part"
    assert s["custom_properties"] == {"Description": "Test bushing", "Revision": "B"}
    assert s["mass_properties"]["0"]["mass_kg"] == pytest.approx(0.0975)
    assert s["units"]["linear"] == "in"
    assert s["has_preview"]


def test_not_solidworks(tmp_path):
    p = tmp_path / "x.SLDPRT"
    p.write_bytes(b"hello world" * 10)
    with pytest.raises(FormatError):
        open_file(str(p))


def test_unwrap():
    payload = b"PS\x00\x00\x00?: TRANSMIT FILE (partition) created by modeller version 2900201" + b"x" * 1000
    z = zlib.compress(payload)
    wrapped = struct.pack("<I", len(z) + 20) + WRAP_GUID + struct.pack("<II", len(payload), len(z)) + z
    assert unwrap(wrapped) == payload
    assert unwrap(b"plain data") == b"plain data"


def _section(payload, frame=1000):
    """A chained section: chain_len, GUID, then one usize/zsize/zlib frame per `frame` bytes of payload."""
    body = WRAP_GUID
    for i in range(0, len(payload), frame):
        z = zlib.compress(payload[i:i + frame])
        body += struct.pack("<II", len(payload[i:i + frame]), len(z)) + z
    return struct.pack("<I", len(body)) + body


def test_sections_multi_frame_and_chained():
    part = b"PS\x00\x00\x00?: TRANSMIT FILE (partition)" + bytes(range(256)) * 20
    deltas = b"PS\x00\x00\x00?: TRANSMIT FILE (deltas)" + b"d" * 300
    raw = b"\0" * 8 + _section(part) + b"\0" * 5 + _section(deltas)
    assert [d for _, d in sections(raw)] == [part, deltas]
    assert unwrap(raw) == part                      # all frames of the first section, not just the first frame


def test_nibble_swap_roundtrip():
    assert nibble_swap(b"Contents") == bytes.fromhex("34f6e64756e64737")
    assert nibble_swap(nibble_swap(b"any bytes")) == b"any bytes"
