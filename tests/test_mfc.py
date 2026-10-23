import struct

from swreader.mfc import Archive, find_class_names


def wide(s):
    return b"\xff\xfe\xff" + bytes([len(s)]) + s.encode("utf-16-le")


def test_cstring_variants():
    long = "x" * 300
    data = wide("Sketch1") + b"\x03abc" + b"\xff\xfe\xff\xff" + struct.pack("<H", 300) + long.encode("utf-16-le")
    a = Archive(data)
    assert a.cstring() == "Sketch1"
    assert a.cstring() == "abc"
    assert a.cstring() == long
    assert a.at_end()


def test_tags_and_map():
    data = (b"\xff\xff\x01\x00\x08\x00moPart_c"      # new class (index 1), new object (index 2)
            + b"\x01\x80"                             # new object of class 1 (index 3)
            + b"\x02\x00"                             # reference to object 2
            + b"\x00\x00")                            # null
    a = Archive(data)
    assert a.tag() == ("new", "moPart_c", 1, 2)
    assert a.tag() == ("new", "moPart_c", 1, 3)
    assert a.tag()[:2] == ("ref", 2)
    assert a.tag() == ("null",)


def test_find_class_names():
    data = b"\x00\x00\xff\xff\x01\x00\x0a\x00moHeader_c\x01\x02"
    assert find_class_names(data) == [(2, "moHeader_c", 1)]
