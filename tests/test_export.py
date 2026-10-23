import os

from swreader import export

DATA = os.path.join(os.path.dirname(__file__), "data")


def test_part_summary():
    doc = export.load(os.path.join(DATA, "Bracket.SLDPRT.json"))
    s = export.summary(doc)
    assert "Material: 6061-T6 (SS)" in s
    assert "Boss-Extrude1 (boss-extrude): depth 0.25 in" in s
    assert "radius 0.125 in on 2 edges" in s
    assert "D2=1 in ±0.005 in" in s
    assert "Comments" not in s                      # folders are not design features


def test_parameters_and_index():
    doc = export.load(os.path.join(DATA, "Bracket.SLDPRT.json"))
    p = export.parameters(doc)
    assert [x["name"] for x in p] == ["D1", "D2", "D1", "D1"]
    rec = export.index_record(doc)
    assert rec["material"] == "6061-T6 (SS)" and "Extrusion" in rec["feature_types"]


def test_drawing_summary():
    s = export.summary(export.load(os.path.join(DATA, "Bracket.SLDDRW.json")))
    assert "2X R0.125 in" in s and "gtol: 0.005 A" in s and "REV | DESCRIPTION | DATE" in s


def test_documents_walk():
    docs = list(export.documents(DATA))
    assert {d["document"]["type"] for d in docs} == {"part", "drawing"}


def test_rejects_other_json(tmp_path):
    p = tmp_path / "x.json"
    p.write_text('{"format": "other"}')
    try:
        export.load(str(p))
    except export.ExportError:
        pass
    else:
        raise AssertionError
