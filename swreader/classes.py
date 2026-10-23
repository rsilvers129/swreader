"""Field layouts of SolidWorks MFC classes, worked out from documents (see docs/FORMAT.md §4).

Every layout notes the document versions it was checked against. Field names ending in ``_u`` are not yet
understood; they are kept so the walk stays aligned.
"""
from __future__ import annotations

from .objects import layout


# -- containers ------------------------------------------------------------------------------------------------

@layout("su_CStringArray")
def _cstring_array(r, o):
    o["items"] = r.cstrings()


@layout("suObList", "suObArray")
def _oblist(r, o):
    o["items"] = r.objs()


# -- document header ------------------------------------------------------------------------------------------

@layout("moPart_c", "moAssembly_c", "moDrawing_c")
def _document(r, o):
    o["version"] = r.u32()
    r.version = o["version"]
    o["header"] = r.obj()


@layout("moHeader_c")
def _header(r, o):
    o["users"] = r.obj()                 # su_CStringArray of user names
    o["array2_u"] = r.obj()              # su_CStringArray
    o["logs"] = r.obj()                  # suObList of moLogs_c: creation/modification history per node
    o["created"] = r.u32()               # unix time
    o["next_id"] = r.u32()
    o["u1_u"] = r.u16()
    o["u2_u"] = r.u32()
    o["ext"] = r.obj()                   # moExtObject_c


@layout("moLogs_c")
def _logs(r, o):
    o["stamps"] = [r.obj() for _ in range(r.u16())]
    o["id"] = r.u32()
    o["name"] = r.cstring()


@layout("moStamp_c")
def _stamp(r, o):
    o["kind"] = r.u16()                  # 0 created, 1 modified, 2 deleted (follows the action text)
    o["user"] = r.u32()                  # index into the header's user list
    o["time"] = r.u32()                  # unix time
    o["action"] = r.cstring()


@layout("moCStringHandle_c")
def _cstring_handle(r, o):
    o["text"] = r.cstring()


@layout("moExtObject_c")
def _ext_object(r, o):
    """A document reference: this document's path/name (in the header) or a base part (derived parts)."""
    o["path"] = r.obj()                  # moCStringHandle_c
    o["name"] = r.obj()                  # moCStringHandle_c
    o["record"] = v = r.u16()
    r.u8()
    o["created"] = r.u32()
    r.u8()
    o["saved"] = r.u32()
    if v == 2:
        o["u1_u"], o["u2_u"], o["u3_u"] = r.u32(), r.u32(), r.i32()
        o["configuration"] = r.cstring()
        o["u4_u"], o["u5_u"] = r.i32(), r.u32()
        o["tag_u"] = r.raw(8)
        o["u6_u"], o["u7_u"] = r.u32(), r.u32()
        o["time1"] = r.u32()
        r.raw(22)
        o["time2"] = r.u32()
        o["list"] = r.obj()              # suObList (empty so far)
        r.raw(28)
        o["box_u"] = r.f64s(8)           # bounding box and extents (order not yet confirmed)
        o["u8_u"], o["u9_u"] = r.u32(), r.u32()
    elif v == 3:
        o["u1_u"], o["u2_u"], o["u3_u"] = r.u32(), r.u32(), r.u32()
        o["configuration"] = r.cstring()
        o["u4_u"], o["u5_u"] = r.i32(), r.u32()
        o["time1"], o["u6_u"] = r.u32(), r.u32()
        o["base"] = r.obj()              # nested moExtObject_c: the referenced document
    else:
        raise ValueError(f"moExtObject_c record version {v}")


@layout("moNodeName_c")
def _node_name(r, o):
    """The name part of every named node (feature, folder, plane, sketch, parameter ...)."""
    o["name"] = r.cstring()
    o["u0_u"] = r.u32()
    o["flags"] = r.u32()
    o["id"] = r.i32()                    # -1 for parameters
    o["u1_u"] = r.u32()
    if (r.version or 0) >= 10000:
        o["comment"] = r.cstring()
    o["u2_u"] = r.u16()
    o["links"] = [r.u16() for _ in range(r.u16())]


def stamps(r, o):
    """Version stamps at the start of a feature's own data (all versions)."""
    if (r.version or 0) >= 6000:
        o["u3_u"] = r.u32()
    o["u4_u"] = r.raw(12)
    o["number"] = r.u32()
    o["u5_u"] = r.u32()
    r.u8()
    o["created_in"] = (r.u32(), r.u32())         # (SolidWorks version, build)
    o["rebuilt_in"] = (r.u32(),)
    o["tolerance"] = r.f64()
    o["rebuilt_in"] += (r.u32(),)
    o["u6_u"] = r.u16()


def feature(r, o):
    """moFeature base: node name, stamps, description, state."""
    o["node"] = r.obj()
    stamps(r, o)
    o["description"] = r.cstring()
    r.u8()
    o["u7_u"] = r.u32()
    r.u8()
    o["u8_u"] = (r.i32(), r.i32())
    o["u9_u"] = r.f32()
    o["u10_u"] = r.raw(12)
    o["u11_u"] = r.u32()
    o["u12_u"] = r.raw(9)
    o["u13_u"] = r.i32()
    o["modified"] = (r.u32(), r.u32())           # FILETIME, high dword first
    o["u14_u"] = (r.u16(), r.u16(), r.u8())
    if (r.version or 0) >= 10000:
        o["u15_u"] = r.u32()
    if (r.version or 0) >= 14000:
        o["u16_u"] = r.raw(8)


@layout("moCommentsFolder_c", "moSensorFolder_c", "moDocsFolder_c", "moEqnFolder_c", "moConfigCommentsFolder_c")
def _folder(r, o):
    feature(r, o)


@layout("moFavoriteFolder_c")
def _favorites(r, o):
    feature(r, o)
    o["u20_u"] = r.raw(8 if (r.version or 0) >= 10000 else 2)


@layout("moNotesAreaFtrFolder_c")
def _notes_area(r, o):
    """Notes folder ("Notes"/"Hinweise") and its end marker ("<name>___EndTag___"), both in the annotations folder."""
    feature(r, o)
    name = o["node"].get("name", "") if isinstance(o.get("node"), dict) else ""
    if name.endswith("___EndTag___"):
        # two object indices (u32), then a second stamp block and feature tail; fixed size
        o["u20_u"] = r.raw(_by_version(r, [(0, 165), (14000, 183)]))


@layout("moSelectionSetFolder_c")
def _selection_sets(r, o):
    feature(r, o)
    o["u20_u"] = r.raw(6)                # checked 8000-19000 (empty folders)


@layout("moInkMarkupFolder_c")
def _ink_markup(r, o):
    feature(r, o)
    o["u20_u"] = r.raw(2)                # checked 14000-19000 (empty folders)


@layout("moSurfaceBodyFolder_c", "moSolidBodyFolder_c")
def _body_folder(r, o):
    feature(r, o)
    o["u20_u"] = r.raw(12 if (r.version or 0) >= 10000 else 10)


@layout("moDetailCabinet_c")
def _detail_cabinet(r, o):
    """Annotations folder. Before 2009 a full feature; from format 10000 only a name and its sub-folders."""
    if (r.version or 0) < 10000:
        feature(r, o)
        o["u20_u"] = r.u16()
        o["scale_u"] = (r.f64(), r.f64())
        o["u21_u"] = r.u16()
    else:
        o["node"] = r.obj()
        o["u20_u"] = r.u16()
        o["items"] = r.objs()            # notes folder, tables folder ...


@layout("moMaterialFolder_c")
def _material_folder(r, o):
    feature(r, o)
    o["material"] = r.cstring()
    if (r.version or 0) >= 6000:
        o["u20_u"] = r.u32()


@layout("moHistoryFolder_c")
def _history_folder(r, o):
    """History folder (2009+): recently changed features."""
    feature(r, o)
    o["items"] = r.objs()                # moHistoryFeatItemData_c


@layout("moHistoryFeatItemData_c")
def _history_item(r, o):
    o["u1_u"] = r.u16()
    o["u2_u"] = (r.u32(), r.u32(), r.i32(), r.u32())
    o["text_u"] = r.cstring()
    o["feature"] = r.obj()               # moCompFeature_c


@layout("moCompFeature_c")
def _comp_feature(r, o):
    """A reference to a feature by id (history items)."""
    o["ref"] = r.obj(expect="moFeatureRef_c")


@layout("moFeatureRef_c")
def _feature_ref(r, o):
    """Name not seen yet (defined in Config-N): a feature id and its last-change time."""
    o["u1_u"] = r.raw(79)
    o["feature_id"] = r.u32()
    o["time"] = r.u32()                  # unix time


# -- sketches ---------------------------------------------------------------------------------------------------

def sk_entity(r, o):
    """The part every sketch entity record starts with."""
    o["id"] = r.u32()
    o["sig_u"] = r.raw(17)
    o["u1_u"] = r.u8()
    o["u2_u"] = r.u32()
    o["u3_u"] = r.u8()
    o["u4_u"] = (r.u16(), r.u16(), r.u16(), r.u16())
    o["u5_u"] = r.f32()
    o["external"] = r.obj()              # sgExtEnt_c: the entity is projected from outside the sketch
    o["u6_u"] = r.u16()
    o["u7_u"] = r.raw(9)
    o["u8_u"] = r.f64()
    if (r.version or 0) >= 16000:
        o["u9_u"] = r.raw(8)


def sk_point(r, o):
    sk_entity(r, o)
    o["flags_u"] = r.u16()
    o["x"], o["y"] = r.f64(), r.f64()    # sketch coordinates, metres
    o["u10_u"] = (r.u16(), r.u16())
    o["handles"] = [r.obj(), r.obj()]    # sg*Handle of the entities that end here (or null)
    o["u11_u"] = (r.u16(), r.i32())
    o["u12_u"] = r.raw(36)


def sk_line(r, o):
    sk_entity(r, o)
    o["start"], o["end"] = r.u16(), r.u16()   # point indices
    o["u10_u"] = r.u32()
    o["u11_u"] = r.f64()
    o["u12_u"] = r.u32()


def sk_records(r, fn):
    out = []
    for _ in range(r.u32()):
        x = {"pre_u": (r.u16(), r.u32())}
        fn(r, x)
        out.append(x)
    return out


@layout("sgSketch")
def _sketch(r, o):
    o["points"] = sk_records(r, sk_point)
    o["lines"] = sk_records(r, sk_line)
    raise ValueError(f"sgSketch: rest not decoded (at {r.pos})")


@layout("sgPointHandle", "sgLineHandle", "sgArcHandle", "sgEntHandle", "sgEllipseHandle", "sgSplineHandle",
        "sgParabolaHandle")
def _sk_handle(r, o):
    """A reference to a sketch entity: its index in the sketch's array."""
    o["index"] = r.u16()
    o["u1_u"] = r.i32()


@layout("moOriginProfileFeature_c")
def _origin_profile(r, o):
    """The origin: a sketch feature holding one point."""
    feature(r, o)
    o["u20_u"] = r.raw(_by_version(r, [(0, 10), (14000, 6)]))
    o["sketch"] = r.obj(expect="sgSketch")


def _by_version(r, table):
    """Pick a per-version value: table = [(min_version, value), ...] in ascending order."""
    v = r.version or 0
    out = table[0][1]
    for mv, val in table:
        if v >= mv:
            out = val
    return out


# -- reference geometry -----------------------------------------------------------------------------------------

@layout("moRefPlane_c")
def _ref_plane(r, o):
    feature(r, o)
    o["body_u"] = r.raw(_by_version(r, [(0, 140), (6000, 142), (7000, 146)]))
    o["data"] = r.obj()                  # mo*RefPlnData_c: how the plane is defined


def transform(r):
    """A placement: optional 3x3 rotation, translation, scale."""
    t = {"rotation": r.f64s(9) if r.u8() else None}
    t["translation"] = r.f64s(3)
    t["scale"] = r.f64()
    return t


@layout("moDefaultRefPlnData_c")
def _default_ref_plane_data(r, o):
    """Front/Top/Right: fixed planes."""
    o["origin"] = r.f64s(3)
    o["normal"] = r.f64s(3)
    o["transform"] = transform(r)
    r.u8()
    o["display_box"] = r.f64s(4)
    o["u1_u"] = r.raw(6)
    o["u2_u"] = (r.i32(), r.i32())
    r.u8()
    o["offsets_u"] = r.f64s(3)
    o["u3_u"] = r.raw(_by_version(r, [(0, 8), (7000, 10), (16000, 16)]))
