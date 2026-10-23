"""Keyword index (swXmlContents/KeyWords) parsing, on a synthetic index shaped like real ones."""
from swreader import keywords as K

XML = """\x86<?xml version="1.0" encoding="UTF-8"?>
<Keywords id="1585118392" Name="Bracket"><Configuration id="0" Name="Standard" Type="ConfigurationManager" Material="AISI 1020"/>
<Extrusion id="20" Name="Boss-Extrude1" Dissectable="true" DissectableChildren="19" DissectableRoot="true"><Dimension Name="D1">10</Dimension></Extrusion>
<Extrusion id="30" Name="Schnitt-Linear austragen1"/>
<Feature id="-1" Name="" Type="Sheet-Metal Master"/>
<Feature id="1" Name="Beschriftungen" Type="Beschriftungen"/>
<Feature id="2" Name="X-Y" Type="Ebene"/><Feature id="3" Name="X-Z" Type="Ebene"/><Feature id="4" Name="Y-Z" Type="Ebene"/>
<Feature id="25" Name="Ebene1" Type="Ebene"/>
<Feature id="40" Name="Fase1" Type="Fase"><Dimension Name="D1">0.5</Dimension><Dimension Name="D2">45°</Dimension></Feature>
<Feature id="41" Name="Verrundung1" Type="Verrundung"><Dimension Name="D1">R2</Dimension></Feature>
<Feature id="50" Name="Mystery1" Type="Mystery"/>
<Sketch id="5" Name="Ursprung" Type="Ursprung"/>
<Sketch id="19" Name="Skizze1" Dissectable="true"><Dimension Name="D1">&lt;MOD-DIAM&gt;62</Dimension><Dimension Name="D2">(16)</Dimension></Sketch>
</Keywords>""".encode("utf-8")


def test_parse_and_canonical_types():
    kw = K.parse(XML)
    assert kw["name"] == "Bracket"
    assert kw["configurations"] == [{"id": 0, "name": "Standard", "material": "AISI 1020"}]
    by_id = {it.get("id"): it for it in kw["items"]}
    assert by_id[20]["canonical"] == "Extrusion"
    assert by_id[30]["canonical"] == "Cut"                 # no Type: the name stem decides
    assert by_id[40]["canonical"] == "Chamfer"
    assert by_id[41]["canonical"] == "Fillet"
    assert by_id[19]["canonical"] == "ProfileFeature"
    assert by_id[5]["canonical"] == "OriginProfileFeature"
    assert "canonical" not in by_id[50]                     # unknown stems stay as stored
    assert by_id[50]["type"] == "Mystery"


def test_dimensions():
    d = {x["name"]: x for x in K.parse(XML)["items"][-1]["dimensions"]}
    assert d["D1"]["kind"] == "diameter" and d["D1"]["value"] == 62 and d["D1"]["display"] == "Ø62"
    assert d["D2"]["reference"] is True and d["D2"]["value"] == 16
    assert K.dimension("D1", "R2")["kind"] == "radius"
    assert K.dimension("D1", "45°") == {"name": "D1", "text": "45°", "display": "45°", "value": 45.0,
                                             "kind": "angle"}
    assert K.dimension("D1", "12,5")["value"] == 12.5


def test_features_in_creation_order():
    kw = K.parse(XML)
    ids = [it["id"] for it in K.features(kw, modelling_only=True)]
    assert ids == [19, 20, 25, 30, 40, 41, 50]              # default planes 2-4 (before the origin) left out
    assert [it["id"] for it in K.features(kw)][:4] == [1, 2, 3, 4]
    s = K.summary(kw)
    assert s["sketches"] == 1 and s["modelling_features"] == 6 and s["dimensions"] == 6
