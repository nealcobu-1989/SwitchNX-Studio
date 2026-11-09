"""Renaming a plugin also fixes script properties that hold its file name,
and reports what still names it."""
import struct

from skynx import rename as RN
from skynx.nxtest import prop_strs, wstr
from skynx.records import iter_records, rename_in_vmad, vmad_string_spans


def _prop_str(name, value):
    return wstr(name) + bytes([2, 1]) + wstr(value)


def _vmad(props):
    script = wstr("MyScript") + bytes([0]) + struct.pack("<H", len(props)) + b"".join(props)
    return struct.pack("<hhH", 5, 2, 1) + script


def _acti(fid, props):
    v = _vmad(props)
    subs = b"EDID" + struct.pack("<H", 4) + b"Act\0" + b"VMAD" + struct.pack("<H", len(v)) + v
    return b"ACTI" + struct.pack("<IIIHHHH", len(subs), 0, fid, 0, 0, 44, 0) + subs


def _esp(path, masters, records):
    hedr = b"HEDR" + struct.pack("<H", 12) + struct.pack("<fiI", 1.7, len(records), 0x800)
    mast = b"".join(b"MAST" + struct.pack("<H", len(m) + 1) + m.encode() + b"\0"
                    + b"DATA" + struct.pack("<H", 8) + bytes(8) for m in masters)
    tes4 = b"TES4" + struct.pack("<IIIHHHH", len(hedr) + len(mast), 0, 0, 0, 0, 44, 0) + hedr + mast
    body = b"".join(records)
    grup = b"GRUP" + struct.pack("<I", 24 + len(body)) + b"ACTI" + bytes(12) + body
    path.write_bytes(tes4 + grup)


def _props(path):
    out = []
    for r in iter_records(path, has=[b"VMAD"]):
        out += [t for _a, _b, t in vmad_string_spans(dict(r.subrecords())["VMAD"], r.type)]
    return out


def test_string_properties_are_renamed_and_the_rest_is_untouched(tmp_path):
    p = tmp_path / "User.esp"
    _esp(p, ["Skyrim.esm"], [_acti(0x800, [_prop_str("Plugin", "Old Mod.esp"),
                                             prop_strs("List", ["Skyrim.esm", "old mod.esp"]),
                                             _prop_str("Other", "Old Mod.esp.bak")])])
    raw = p.read_bytes()
    out, n = rename_in_vmad(raw, {"old mod.esp": "NewMod.esp"})
    assert n == 2
    p.write_bytes(out)
    assert _props(p) == ["NewMod.esp", "Skyrim.esm", "NewMod.esp", "Old Mod.esp.bak"]
    back, n2 = rename_in_vmad(out, {"newmod.esp": "Old Mod.esp"})
    assert n2 == 2


def test_nothing_to_rename_keeps_bytes(tmp_path):
    p = tmp_path / "User.esp"
    _esp(p, ["Skyrim.esm"], [_acti(0x800, [_prop_str("Plugin", "Skyrim.esm")])])
    raw = p.read_bytes()
    assert rename_in_vmad(raw, {"old mod.esp": "NewMod.esp"}) == (raw, 0)


def test_apply_counts_vmad_and_reports_leftovers(tmp_path):
    _esp(tmp_path / "Old Mod.esp", ["Skyrim.esm"], [])
    _esp(tmp_path / "User.esp", ["Skyrim.esm", "Old Mod.esp"],
         [_acti(0x800, [_prop_str("Plugin", "Old Mod.esp"),
                        _prop_str("Key", "Old Mod.esp|0x800")])])
    counts = RN.apply(tmp_path, {"Old Mod.esp": "NewMod.esp"})
    assert counts["plugins"] == 1 and counts["masters"] == 1 and counts["vmad"] == 1
    assert len(counts["left"]) == 1 and "Old Mod.esp|0x800" in counts["left"][0]


def test_a_longer_present_name_is_not_a_leftover(tmp_path):
    _esp(tmp_path / "Patch.esp", ["Skyrim.esm"], [])
    _esp(tmp_path / "Other - Patch.esp", ["Skyrim.esm"], [])
    (tmp_path / "cfg.json").write_text('{\n"a": "Other - Patch.esp",\n"b": "needs Patch.esp first"\n}')
    counts = RN.apply(tmp_path, {"Patch.esp": "PatchNX.esp"})
    assert (tmp_path / "PatchNX.esp").exists()
    assert all("Other - Patch.esp" not in x for x in counts["left"])
    assert counts["left"] == ['cfg.json: "b": "needs Patch.esp first"']


def test_doctor_safe_rename_fixes_script_properties_and_undo_restores(tmp_path):
    import sys
    from pathlib import Path
    sys.path.insert(0, str(Path(__file__).parent))
    from test_doctor2 import _find, _pack
    from skynx.builder import add_mod
    from skynx.fixes import apply, preview
    from skynx.history import list_history, undo
    from skynx.pack import Pack

    pack = _pack(tmp_path)
    m = tmp_path / "mod"
    m.mkdir()
    _esp(m / "Ryn's Stones.esp", ["Skyrim.esm"], [])
    _esp(m / "Ryn Addon.esp", ["Skyrim.esm"], [_acti(0x800, [_prop_str("Needs", "Ryn's Stones.esp")])])
    add_mod(pack, m)
    pack = Pack.open(pack.root)
    f = [x for x in _find(pack, "name-unsafe") if x.subject == "Ryn's Stones.esp"][0]
    pv = preview(pack, f.fix)
    assert any("Ryn Addon.esp" in c and "Ryn's Stones.esp" in c and f.fix["to"] in c for c in pv["changes"])
    apply(pack, f.fix)
    pack = Pack.open(pack.root)
    assert _props(pack.data_dir / "Ryn Addon.esp") == [f.fix["to"]]
    undo(pack.root, list_history(pack.root)[0]["id"])
    assert _props(Pack.open(pack.root).data_dir / "Ryn Addon.esp") == ["Ryn's Stones.esp"]


def _nif_head(stream, user=12):
    return (b"Gamebryo File Format, Version 20.2.0.7\n" + struct.pack("<I", 0x14020007) + b"\x01"
            + struct.pack("<III", user, 5, stream) + bytes(40))


def test_nif_stream_tells_le_from_se():
    from skynx.audit import _nif_stream
    assert _nif_stream(_nif_head(83)) == 83
    assert _nif_stream(_nif_head(100)) == 100
    assert _nif_stream(_nif_head(83, user=11)) is None
    assert _nif_stream(b"not a nif") is None


def test_doctor_reports_scripts_that_name_a_renamed_plugin(tmp_path):
    import json
    import sys
    from pathlib import Path
    sys.path.insert(0, str(Path(__file__).parent))
    from test_doctor2 import _pack
    from skynx import scriptcheck as SC
    from skynx.audit import _BsaCache
    from skynx.builder import add_mod
    from skynx.pack import Pack

    pack = _pack(tmp_path)
    m = tmp_path / "mod"
    m.mkdir()
    _esp(m / "Addon.esp", ["Skyrim.esm"], [_acti(0x800, [_prop_str("Key", "Old Mod.esp|0x800"),
                                                          _prop_str("Plain", "Old Mod.esp")])])
    add_mod(pack, m)
    (pack.root / ".skynx" / "renames.json").write_text(json.dumps({"NewMod.esp": "Old Mod.esp"}))
    pack = Pack.open(pack.root)
    assert SC.gone_names(pack) == ["Old Mod.esp"]
    found = []
    SC.check_gone_names(pack, lambda *a, **kw: found.append((a, kw)), _BsaCache())
    assert len(found) == 1
    a, kw = found[0]
    assert a[0] == "script-gone-name" and a[5]["n"] == 2


def test_chained_rename_leaves_no_false_leftovers(tmp_path):
    _esp(tmp_path / "A.esp", ["Skyrim.esm"], [])
    _esp(tmp_path / "B.esp", ["Skyrim.esm"], [])
    _esp(tmp_path / "U.esp", ["Skyrim.esm", "A.esp", "B.esp"],
         [_acti(0x800, [_prop_str("x", "A.esp"), _prop_str("y", "B.esp")])])
    counts = RN.apply(tmp_path, {"A.esp": "B.esp", "B.esp": "C.esp"})
    assert counts["vmad"] == 2 and counts["left"] == []
    assert _props(tmp_path / "U.esp") == ["B.esp", "C.esp"]


def _compressed(rec: bytes) -> bytes:
    import zlib
    data = rec[24:]
    body = struct.pack("<I", len(data)) + zlib.compress(data)
    flags = struct.unpack_from("<I", rec, 8)[0] | 0x00040000
    return rec[:4] + struct.pack("<II", len(body), flags) + rec[12:24] + body


def test_names_inside_compressed_records_are_found_and_renamed(tmp_path):
    from skynx.records import may_name
    p = tmp_path / "U.esp"
    _esp(p, ["Skyrim.esm"], [_compressed(_acti(0x800, [_prop_str("x", "Old.esp")]))])
    raw = p.read_bytes()
    assert b"old.esp" not in raw.lower() and may_name(raw, ["Old.esp"])
    out, n = rename_in_vmad(raw, {"old.esp": "New.esp"})
    assert n == 1
    p.write_bytes(out)
    assert _props(p) == ["New.esp"]


def test_a_damaged_plugin_doesnt_stop_the_rename(tmp_path):
    _esp(tmp_path / "Old.esp", ["Skyrim.esm"], [])
    bad = bytearray(_compressed(_acti(0x800, [_prop_str("x", "Old.esp")])))
    bad[30:40] = b"\0" * 10                       # broken zlib data
    _esp(tmp_path / "U.esp", ["Skyrim.esm", "Old.esp"], [bytes(bad)])
    counts = RN.apply(tmp_path, {"Old.esp": "New.esp"})
    assert counts["plugins"] == 1 and counts["masters"] == 1
    assert any("U.esp" in x and "couldn't be read" in x for x in counts["left"])


def test_a_name_scripts_cant_hold_is_left_alone(tmp_path):
    p = tmp_path / "U.esp"
    _esp(p, ["Skyrim.esm"], [_acti(0x800, [_prop_str("x", "Old.esp")])])
    raw = p.read_bytes()
    assert rename_in_vmad(raw, {"old.esp": "Новый.esp"}) == (raw, 0)
