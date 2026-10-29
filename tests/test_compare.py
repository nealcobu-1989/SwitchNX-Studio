"""Compare a converted mod with its PC original (skynx.compare).

Everything is synthetic: plugins, BSAs, textures, sounds and animations are
built in the test.
"""
import struct
import sys
import time
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tests"))
from skynx import nvn  # noqa: E402
from skynx.compare import compare, fold  # noqa: E402
from skynx.records import set_hedr_version  # noqa: E402
from test_requirements import make_bsa, plugin, rec, sub, vmad, script, zs  # noqa: E402


# ------------------------------------------------------------------ samples
def dds(w, h, seed=1):
    hd = bytearray(128)
    hd[0:4] = b"DDS "
    struct.pack_into("<IIIIIII", hd, 4, 124, 0x0002100F, h, w, 0, 0, 1)
    struct.pack_into("<II4s", hd, 76, 32, 4, b"DXT5")
    return bytes(hd) + bytes((i * seed + seed) % 251 for i in range(w * h))


def nvn_of(w, h, seed=1):
    return nvn.from_dds(dds(w, h, seed))


def hkx(switch: bool, body=b"anim"):
    head = bytearray(64)
    head[16], head[18] = 8, 1 if switch else 0
    return bytes(head) + body * 10


def wav():
    data = b"\x01\x00" * 400
    fmt = struct.pack("<HHIIHH", 1, 1, 44100, 88200, 2, 16)
    return (b"RIFF" + struct.pack("<I", 36 + len(data)) + b"WAVE" + b"fmt " + struct.pack("<I", 16)
            + fmt + b"data" + struct.pack("<I", len(data)) + data)


def mcadpcm():
    return struct.pack("<III", 1, 12, 8) + b"\0" * 8


def nif(tag=b"x", bs=100):
    return (b"Gamebryo File Format, Version 20.2.0.7\n" + struct.pack("<I", 0x14020007) + b"\x01"
            + struct.pack("<III", 12, 1, bs) + tag * 40)


def weap(fid, edid, model="weapons\\iron\\sword.nif", extra=()):
    return rec("WEAP", fid, [sub("EDID", zs(edid)), sub("MODL", zs(model)), *extra])


def quest(fid, edid, scr="MyQuestScript"):
    return rec("QUST", fid, [sub("EDID", zs(edid)), sub("VMAD", vmad([script(scr)])),
                             sub("DNAM", b"\x01\x00" + b"\0" * 10)])


def base_records():
    return [weap(0x01000800, "ModSword"), weap(0x01000801, "ModAxe", "weapons\\axe.nif"),
            quest(0x01000802, "ModQuest"), weap(0x00012EB7, "IronSword")]


def write(path: Path, raw: bytes) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(raw)
    return path


def make_pc(d: Path, records=None, name="Mod.esp", textures=None, extra_bsa=None, loose=None, **kw):
    plugin(d / name, records if records is not None else base_records(), **kw)
    stem = name[:-4]
    make_bsa(d / f"{stem}.bsa", extra_bsa or {"meshes\\mod\\sword.nif": nif(),
                                              "scripts\\myquestscript.pex": b"PEX1" * 20})
    if textures is not False:
        make_bsa(d / f"{stem} - Textures.bsa", textures or {"textures\\mod\\sword.dds": dds(64, 64),
                                                           "textures\\mod\\axe.dds": dds(128, 128, 3)})
    for rel, raw in (loose or {}).items():
        write(d / rel.replace("\\", "/"), raw)
    return d


def run(conv, orig, tmp):
    return compare(conv, orig, work_dir=tmp / "work")


# ------------------------------------------------------------------ tests
def test_identical_is_format_only(tmp_path):
    a = make_pc(tmp_path / "orig")
    b = make_pc(tmp_path / "conv")
    r = run(b, a, tmp_path)
    assert r["same_mod"] and r["verdict"]["kind"] == "format-only"
    assert r["verdict"]["en"] == "Identical to the original."
    p = r["plugins"][0]
    assert p["match"] == "name" and p["records"]["same"] == 4
    assert p["records"]["changed"] == p["records"]["added"] == p["records"]["removed"] == 0
    assert r["assets"]["same"] == 4
    assert not (tmp_path / "work").exists() or not any((tmp_path / "work").iterdir())


def test_converted_textures_sounds_and_animations_are_format_only(tmp_path):
    loose_o = {"sound\\fx\\mod\\swing.wav": wav(), "meshes\\actors\\anim\\attack.hkx": hkx(False)}
    loose_c = {"sound\\fx\\mod\\swing.mcadpcm": mcadpcm(), "meshes\\actors\\anim\\attack.hkx": hkx(True)}
    a = make_pc(tmp_path / "orig", loose=loose_o)
    b = make_pc(tmp_path / "conv", loose=loose_c,
                textures={"textures\\mod\\sword.dds": nvn_of(64, 64),
                          "textures\\mod\\axe.dds": nvn_of(64, 64, 3)})       # 128 -> 64
    r = run(b, a, tmp_path)
    s = r["assets"]
    assert r["verdict"]["kind"] == "format-only", r["verdict"]
    assert s["converted_textures"] == 2 and s["downscaled"] == 1
    assert s["converted_audio"] == 1 and s["converted_anims"] == 1
    assert s["only_original"] == [] and s["only_converted"] == []
    assert r["verdict"]["en"] == ("Same as the original except for format conversion "
                                  "(2 textures (1 also downscaled), 1 sound, 1 animation).")
    assert "2 texturas" in r["verdict"]["es"] and "—" not in r["verdict"]["es"]


def test_changed_vmad_is_an_edit_naming_the_subrecord(tmp_path):
    a = make_pc(tmp_path / "orig")
    recs = base_records()
    recs[2] = quest(0x01000802, "ModQuest", scr="OtherScript")
    b = make_pc(tmp_path / "conv", records=recs)
    r = run(b, a, tmp_path)
    p = r["plugins"][0]["records"]
    assert r["verdict"]["kind"] == "edited"
    assert p["changed"] == 1 and p["same"] == 3
    assert p["by_type"] == {"QUST": {"changed": 1}}
    ex = p["examples"][0]
    assert ex["edid"] == "ModQuest" and ex["subs"] == ["VMAD"] and ex["formid"] == "01000802"
    assert r["verdict"]["en"] == "Edited beyond conversion: 1 record changed (1 VMAD)."
    assert r["verdict"]["es"] == "Editado más allá de la conversión: 1 registro cambiado (1 VMAD)."


def test_removed_record_and_removed_script(tmp_path):
    a = make_pc(tmp_path / "orig")
    b = make_pc(tmp_path / "conv", records=base_records()[:2] + base_records()[3:],
                extra_bsa={"meshes\\mod\\sword.nif": nif()})
    r = run(b, a, tmp_path)
    p = r["plugins"][0]["records"]
    assert p["removed"] == 1 and p["by_type"] == {"QUST": {"removed": 1}}
    assert p["examples"][0]["what"] == "removed" and p["examples"][0]["edid"] == "ModQuest"
    assert r["assets"]["scripts_removed"] == ["scripts\\myquestscript.pex"]
    assert r["verdict"]["kind"] == "edited"
    assert "1 record removed" in r["verdict"]["en"] and "1 script removed" in r["verdict"]["en"]
    assert "1 script quitado" in r["verdict"]["es"]


def test_hedr_downgrade_is_a_header_change(tmp_path):
    a = make_pc(tmp_path / "orig")
    b = make_pc(tmp_path / "conv")
    p = b / "Mod.esp"
    p.write_bytes(set_hedr_version(p.read_bytes(), 1.70))
    r = run(b, a, tmp_path)
    h = r["plugins"][0]["header"]
    assert h["hedr"] == [1.71, 1.7] and "hedr" in h["expected"] and not h["edits"]
    assert r["verdict"]["kind"] == "format-only"
    assert "Mod.esp header 1.71 → 1.70" in r["verdict"]["en"]


def test_drive_damaged_rename_still_matches_and_voices_follow(tmp_path):
    voice = b"FUZE" + b"\0" * 40
    a = make_pc(tmp_path / "orig", name="Ryn's Stones.esp", textures=False,
                loose={"sound\\voice\\ryn's stones.esp\\maleguard\\hi.fuz": voice})
    b = make_pc(tmp_path / "conv", name="Ryn_s Stones.esp", textures=False,
                loose={"sound\\voice\\ryn_s stones.esp\\maleguard\\hi.fuz": voice})
    r = run(b, a, tmp_path)
    p = r["plugins"][0]
    assert p["original"] == "Ryn's Stones.esp" and p["match"] == "folded"
    assert p["records"]["same"] == 4
    assert r["assets"]["renamed"] == 1 and r["assets"]["only_original"] == []
    assert r["verdict"]["kind"] == "format-only"
    assert fold("Ryn's Stones.esp") == fold("Ryn_s Stones.esp") == fold("RynsStones.esp")


def test_renamed_plugin_matches_by_content(tmp_path):
    a = make_pc(tmp_path / "orig", name="Totally Original.esp", textures=False)
    b = make_pc(tmp_path / "conv", name="Something Else.esp", textures=False)
    r = run(b, a, tmp_path)
    assert r["plugins"][0]["match"] == "content"
    assert r["verdict"]["kind"] == "format-only"
    assert "renamed as Something Else.esp" in r["verdict"]["en"]


def _merge_sources(d: Path):
    plugin(d / "A.esp", [weap(0x01000800, "ASword"), weap(0x01000801, "AAxe"),
                         weap(0x00012EB7, "IronSword")])
    # B depends on A: its own records use index 2, A's use index 1
    ref = sub("CNAM", struct.pack("<I", 0x02000900))
    plugin(d / "B.esp", [weap(0x02000900, "BBow"), weap(0x02000901, "BDagger", extra=[ref]),
                         weap(0x01000801, "AAxe", "weapons\\better_axe.nif")],
           masters=("Skyrim.esm", "A.esp"))


def _merged(d: Path, snam=None):
    ref = sub("CNAM", struct.pack("<I", 0x01000900))
    return plugin(d / "Merged.esp", [weap(0x01000800, "ASword"),
                                      weap(0x01000801, "AAxe", "weapons\\better_axe.nif"),
                                      weap(0x00012EB7, "IronSword"),
                                      weap(0x01000900, "BBow"), weap(0x01000901, "BDagger", extra=[ref])],
                  snam=snam)


def test_merge_of_two_originals_by_content(tmp_path):
    _merge_sources(tmp_path / "orig")
    _merged(tmp_path / "conv")
    r = run(tmp_path / "conv", tmp_path / "orig", tmp_path)
    p = r["plugins"][0]
    assert p["merged_from"] == ["A.esp", "B.esp"] and p["merge_found_by"] == "content"
    assert p["records"]["same"] == 5 and p["records"]["changed"] == 0, p["records"]
    assert p["header"].get("masters_removed") is None
    assert r["verdict"]["kind"] == "edited"
    assert "Merged.esp is a merge of A.esp, B.esp" in r["verdict"]["en"]
    assert "es una fusión de A.esp, B.esp" in r["verdict"]["es"]


def test_merge_named_in_the_description(tmp_path):
    _merge_sources(tmp_path / "orig")
    _merged(tmp_path / "conv", snam="Merged Plugin:\n  A.esp\n  B.esp")
    r = run(tmp_path / "conv", tmp_path / "orig", tmp_path)
    p = r["plugins"][0]
    assert p["merged_from"] == ["A.esp", "B.esp"] and p["merge_found_by"] == "description"
    assert p["records"]["same"] == 5


def test_reordered_masters_compare_by_the_master_they_point_to(tmp_path):
    ref = lambda fid: sub("CNAM", struct.pack("<I", fid))  # noqa: E731
    plugin(tmp_path / "orig" / "P.esp", [weap(0x02000800, "Mine", extra=[ref(0x01000ABC)]),
                                         weap(0x01000ABC, "UpdThing")],
           masters=("Skyrim.esm", "Update.esm"))
    plugin(tmp_path / "conv" / "P.esp", [weap(0x02000800, "Mine", extra=[ref(0x00000ABC)]),
                                         weap(0x00000ABC, "UpdThing")],
           masters=("Update.esm", "Skyrim.esm"))
    r = run(tmp_path / "conv", tmp_path / "orig", tmp_path)
    p = r["plugins"][0]
    assert p["records"]["same"] == 2 and p["records"]["changed"] == 0
    assert p["header"]["masters_reordered"] and r["verdict"]["kind"] == "format-only"


def test_missing_texture_bsa_is_partial(tmp_path):
    a = make_pc(tmp_path / "orig")
    b = make_pc(tmp_path / "conv", textures=False)
    r = run(b, a, tmp_path)
    assert r["verdict"]["kind"] == "partial"
    assert r["assets"]["missing_bsas"][0]["name"] == "Mod - Textures.bsa"
    assert r["verdict"]["en"] == "Partial: Mod - Textures.bsa of the original is missing (all of its textures)."
    assert r["verdict"]["es"] == "Incompleto: falta Mod - Textures.bsa del original (todas sus texturas)."


def test_two_missing_bsas(tmp_path):
    a = make_pc(tmp_path / "orig")
    make_bsa(tmp_path / "orig" / "Mod - Textures2.bsa", {"textures\\mod\\bow.dds": dds(64, 64, 7)})
    b = make_pc(tmp_path / "conv", textures=False)
    r = run(b, a, tmp_path)
    assert r["verdict"]["en"] == "Partial: 2 BSAs of the original are missing (all of its textures)."
    assert r["verdict"]["es"] == "Incompleto: faltan 2 BSA del original (todas sus texturas)."


def test_changed_mesh_and_extra_file(tmp_path):
    a = make_pc(tmp_path / "orig")
    b = make_pc(tmp_path / "conv", extra_bsa={"meshes\\mod\\sword.nif": nif(b"y"),
                                              "scripts\\myquestscript.pex": b"PEX1" * 20,
                                              "meshes\\mod\\new.nif": nif()})
    r = run(b, a, tmp_path)
    s = r["assets"]
    assert s["meshes_changed"] == ["meshes\\mod\\sword.nif"]
    assert s["only_converted"] == ["meshes\\mod\\new.nif"]
    assert r["verdict"]["en"] == "Edited beyond conversion: 1 mesh changed, 1 extra file."


def test_fomod_original_is_the_union_of_its_options(tmp_path):
    z = tmp_path / "Mod-FOMOD.zip"
    plugin(tmp_path / "src" / "Mod.esp", base_records())
    plugin(tmp_path / "src" / "Mod-alt.esp", base_records() + [weap(0x01000810, "Extra")])
    with zipfile.ZipFile(z, "w") as zf:
        zf.writestr("fomod/ModuleConfig.xml", "<config/>")
        zf.writestr("fomod/info.xml", "<fomod/>")
        zf.write(tmp_path / "src" / "Mod.esp", "00 Core/Mod.esp")
        zf.write(tmp_path / "src" / "Mod-alt.esp", "20 Extra/Mod.esp")
        zf.writestr("00 Core/meshes/mod/sword.nif", nif())
        zf.writestr("10 2K/textures/mod/sword.dds", dds(64, 64))
        zf.writestr("10 4K/textures/mod/sword.dds", dds(128, 128))
        zf.writestr("20 Extra/meshes/mod/extra.nif", nif(b"e"))
    conv = tmp_path / "conv"
    plugin(conv / "Mod.esp", base_records())
    write(conv / "meshes" / "mod" / "sword.nif", nif())
    write(conv / "textures" / "mod" / "sword.dds", nvn_of(64, 64))
    r = run(conv, z, tmp_path)
    assert r["fomod"] and r["verdict"]["kind"] == "format-only", r["verdict"]
    p = r["plugins"][0]
    assert p["records"]["same"] == 4 and p["records"]["added"] == 0
    assert len(r["plugins"]) == 1                        # the other option's copy isn't "missing"
    assert r["assets"]["fomod_unused"] == 1 and r["assets"]["converted_textures"] == 1
    assert any("FOMOD" in n["en"] for n in r["notes"])


def test_different_mod(tmp_path):
    a = make_pc(tmp_path / "orig")
    plugin(tmp_path / "conv" / "Other.esp", [weap(0x01000900, "Elsewhere"), weap(0x01000901, "Nope")])
    make_bsa(tmp_path / "conv" / "Other.bsa", {"meshes\\other\\x.nif": nif(b"z")})
    r = run(tmp_path / "conv", a, tmp_path)
    assert not r["same_mod"] and r["verdict"]["kind"] == "different-mod"
    assert r["verdict"]["es"] == "Parece otro mod."


def test_zip_and_loose_plugin_inputs(tmp_path):
    a = make_pc(tmp_path / "orig")
    b = make_pc(tmp_path / "conv")
    z = tmp_path / "conv.zip"
    with zipfile.ZipFile(z, "w") as zf:
        for f in b.rglob("*"):
            if f.is_file():
                zf.write(f, "Mod Folder/" + f.relative_to(b).as_posix())
    r = run(z, a / "Mod.esp", tmp_path)
    assert r["verdict"]["kind"] == "format-only" and r["assets"]["same"] == 4


def test_big_plugin_is_fast(tmp_path):
    n = 30000
    recs = [weap(0x01000800 + i, f"Item{i}", extra=[sub("DATA", struct.pack("<IIf", i, 10, 1.5))])
            for i in range(n)]
    plugin(tmp_path / "orig" / "Big.esp", recs)
    recs[5] = weap(0x01000805, "Item5", extra=[sub("DATA", struct.pack("<IIf", 5, 99, 1.5))])
    plugin(tmp_path / "conv" / "Big.esp", recs)
    t = time.time()
    r = run(tmp_path / "conv", tmp_path / "orig", tmp_path)
    took = time.time() - t
    p = r["plugins"][0]["records"]
    assert p["same"] == n - 1 and p["changed"] == 1 and p["examples"][0]["subs"] == ["DATA"]
    assert took < 10, took
