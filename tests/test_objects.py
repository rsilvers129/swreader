import struct

from swreader.objects import Reader, Ref, UnknownClass
import swreader.classes  # noqa: F401  (registers layouts)


def wide(s):
    return b"\xff\xfe\xff" + bytes([len(s)]) + s.encode("utf-16-le")


def test_logs_and_stamps():
    data = (b"\xff\xff\x01\x00\x08\x00moLogs_c" + struct.pack("<H", 1)
            + b"\xff\xff\x01\x00\x09\x00moStamp_c" + struct.pack("<HII", 0, 0, 1342447064) + wide("Created")
            + struct.pack("<I", 7) + wide("Sketch1")
            + b"\x01\x80" + struct.pack("<H", 0) + struct.pack("<I", 8) + wide("Boss-Extrude1")   # 2nd log: class 1
            + b"\x02\x00")                                                                     # ref to first log
    r = Reader(data)
    log = r.obj()
    assert log["name"] == "Sketch1" and log["id"] == 7
    assert log["stamps"][0]["time"] == 1342447064 and log["stamps"][0]["action"] == "Created"
    log2 = r.obj()
    assert log2["name"] == "Boss-Extrude1" and log2["_i"] == 5
    ref = r.obj()
    assert isinstance(ref, Ref) and ref.target is log
    assert r.at_end()


def test_unknown_class():
    r = Reader(b"\xff\xff\x01\x00\x0a\x00moMystery_c")
    try:
        r.obj()
    except UnknownClass as e:
        assert e.name == "moMystery_c"
    else:
        raise AssertionError("expected UnknownClass")
