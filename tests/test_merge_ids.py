"""Merges that renumber records: zMerge's map applied to file names, FaceGen
tint paths and scripts that look a merged plugin up by name."""
import json
import struct

from skynx import pex as PX
from skynx import workshop as WS
from skynx import behaviors as BH


def _pex(calls, e=">"):
    """A minimal compiled script with GetFormFromFile(id, plugin) calls."""
    strings = ["src", "user", "pc", "Obj", "", "OnInit", "game", "GetFormFromFile", "::temp0", "None"]
    for _i, plugin in calls:
        if plugin not in strings:
            strings.append(plugin)
    ix = {s: n for n, s in enumerate(strings)}
    w = lambda s: struct.pack(e + "H", len(s)) + s.encode("latin-1")   # noqa: E731
    out = bytes.fromhex("FA57C0DE") if e == ">" else bytes.fromhex("DEC057FA")
    out += struct.pack(e + "BBHQ", 3, 2, 1, 0) + w("src") + w("user") + w("pc")
    out += struct.pack(e + "H", len(strings)) + b"".join(w(s) for s in strings)
    out += b"\x00" + struct.pack(e + "H", 0)                       # no debug info, no user flags
    out += struct.pack(e + "H", 1)                                  # one object
    out += struct.pack(e + "HIHHIH", ix["Obj"], 0, ix[""], ix[""], 0, ix[""])
    out += struct.pack(e + "HH", 0, 0)                              # no variables, no properties
    out += struct.pack(e + "H", 1) + struct.pack(e + "HH", ix[""], 1)   # one state, one function
    out += struct.pack(e + "HHHIB", ix["OnInit"], ix["None"], ix[""], 0, 0) + struct.pack(e + "HH", 0, 0)
    out += struct.pack(e + "H", len(calls))
    for fid, plugin in calls:
        out += bytes([25]) + b"\x01" + struct.pack(e + "H", ix["game"]) + b"\x01" + struct.pack(e + "H", ix["GetFormFromFile"])
        out += b"\x01" + struct.pack(e + "H", ix["::temp0"]) + b"\x03" + struct.pack(e + "i", 2)
        out += b"\x03" + struct.pack(e + "i", fid) + b"\x02" + struct.pack(e + "H", ix[plugin])
    return out


def test_patch_formids_only_the_named_plugin():
    raw = _pex([(0x800, "Sel.esp"), (0x80C, "Sel.esp"), (0x800, "Other.esp")])
    new, done = PX.patch_formids(raw, "sel.esp", {0x800: 0x9C5, 0x80C: 0x9D1})
    assert sorted(done) == [(0x800, 0x9C5), (0x80C, 0x9D1)]
    assert len(new) == len(raw)
    assert struct.pack(">i", 0x9C5) in new and struct.pack(">i", 0x9D1) in new
    assert new.count(struct.pack(">i", 0x800)) == 1          # Other.esp's call untouched


def test_patch_formids_little_endian():
    raw = _pex([(0x801, "A.esp")], e="<")
    new, done = PX.patch_formids(raw, "A.esp", {0x801: 0x855})
    assert done == [(0x801, 0x855)] and struct.pack("<i", 0x855) in new


def test_fix_scripts_renumbers_then_renames():
    raw = _pex([(0x800, "Sel.esp")])
    out = WS._fix_scripts(raw, {"sel.esp": "Merged.esp"}, {"sel.esp": {0x800: 0x9C5}})
    assert "Merged.esp" in PX.strings(out) and "Sel.esp" not in PX.strings(out)
    assert struct.pack(">i", 0x9C5) in out


def test_retarget_renumbers_voice_and_facegen_names():
    ren, ids = {"a.esp": "M.esp"}, {"a.esp": {0x801: 0x9C5}}
    assert WS._retarget("sound\\voice\\a.esp\\vt\\top_info_00000801_1.fuz", ren, ids) == \
        "sound\\voice\\m.esp\\vt\\top_info_000009c5_1.fuz"
    assert WS._retarget("sound\\voice\\a.esp\\vt\\top_info_00000802_1.fuz", ren, ids).endswith("_00000802_1.fuz")
    assert WS._retarget("meshes\\actors\\character\\facegendata\\facegeom\\a.esp\\00000801.nif", ren, ids) == \
        "meshes\\actors\\character\\facegendata\\facegeom\\m.esp\\000009c5.nif"
    assert WS._retarget_texture("Actors\\Character\\FaceGenData\\FaceTint\\A.esp\\00000801.dds", ren, ids) == \
        "Actors\\Character\\FaceGenData\\FaceTint\\M.esp\\000009c5.dds"


def test_zmerge_ids_reads_the_map(tmp_path):
    d = tmp_path / "merge - Mine"
    d.mkdir()
    (d / "map.json").write_text(json.dumps({"A.esp": {"000800": "0009C5"}, "B.esp": {}}))
    assert WS.zmerge_ids(tmp_path) == {"a.esp": {0x800: 0x9C5}}
    assert WS.merge_ids({"merged": {"ids": {"A.esp": {"000800": "0009C5"}}}}) == {"a.esp": {0x800: 0x9C5}}


def test_unused_nemesis_template_is_left_out(tmp_path):
    data = tmp_path / "Data"
    beh = data / "meshes" / "actors" / "character" / "behaviors"
    beh.mkdir(parents=True)
    (beh / "Nemesis_AttackBehavior.xml").write_text("x")
    (beh / "Nemesis_0_master.xml").write_text("x")
    src = tmp_path / "mod"
    (src / "meshes").mkdir(parents=True)
    assert BH._drop_unused_templates(data, [{"dir": src}]) == ["Nemesis_AttackBehavior.xml"]
    assert (beh / "Nemesis_0_master.xml").exists()
    (beh / "Nemesis_AttackBehavior.xml").write_text("x")
    (src / "attackbehavior.hkx").write_bytes(b"x")              # a combat mod that brings it keeps it
    assert BH._drop_unused_templates(data, [{"dir": src}]) == []
