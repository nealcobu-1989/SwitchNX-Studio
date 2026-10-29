"""Requirements (missing scripts, meshes, textures; SKSE animation frameworks;
behavior conflicts), duplicates, records and the vanilla index.

Everything here is synthetic: plugins, BSAs, NIFs and scripts are built in
the test, so no real pack is needed.
"""
import json
import struct
import sys
import zlib
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from skynx import records as REC  # noqa: E402
from skynx import requirements as REQ  # noqa: E402
from skynx import vanilla as V  # noqa: E402
from skynx.audit import run_audit  # noqa: E402
from skynx.bsa import write_bsa  # noqa: E402
from skynx.builder import create_project  # noqa: E402
from skynx.duplicates import find_duplicates, merged_components  # noqa: E402
from skynx.fixes import apply  # noqa: E402
from skynx.ini import read_ini, set_archive_list  # noqa: E402
from skynx.pack import Pack  # noqa: E402

INIS = ROOT / "tests" / "fixtures" / "console-inis"
NEW_CATS = ("requirements", "duplicates")


# ------------------------------------------------------------------ builders
def sub(sig: str, payload: bytes) -> bytes:
    if len(payload) > 0xFFFF:
        return (struct.pack("<4sHI", b"XXXX", 4, len(payload))
                + struct.pack("<4sH", sig.encode(), 0) + payload)
    return struct.pack("<4sH", sig.encode(), len(payload)) + payload


def zs(s: str) -> bytes:
    return s.encode("cp1252") + b"\0"


def rec(typ: str, fid: int, subs: list[bytes], compressed: bool = False) -> bytes:
    data, flags = b"".join(subs), 0
    if compressed:
        data, flags = struct.pack("<I", len(data)) + zlib.compress(data), REC.COMPRESSED
    return struct.pack("<4sIIIIHH", typ.encode(), len(data), flags, fid, 0, 44, 0) + data


def grup(label: bytes, gtype: int, content: bytes) -> bytes:
    return struct.pack("<4sI4siHHHH", b"GRUP", 24 + len(content), label, gtype, 0, 0, 0, 0) + content


def plugin(path: Path, records: list[bytes], masters=("Skyrim.esm",), snam: str | None = None,
           nrec: int | None = None) -> Path:
    head = sub("HEDR", struct.pack("<fiI", 1.71, len(records) if nrec is None else nrec, 0x800))
    for m in masters:
        head += sub("MAST", zs(m)) + sub("DATA", b"\0" * 8)
    if snam is not None:
        head += sub("SNAM", zs(snam))
    body = b""
    by_type: dict[bytes, list[bytes]] = {}
    tops = []
    for r in records:
        if r[:4] == b"GRUP":
            tops.append(r)          # a ready-made top-level group (CELL...)
        else:
            by_type.setdefault(r[:4], []).append(r)
    for t, rs in by_type.items():
        body += grup(t, 0, b"".join(rs))
    body += b"".join(tops)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(struct.pack("<4sIIIHHHH", b"TES4", len(head), 0, 0, 0, 0, 44, 0) + head + body)
    return path


def wstr(s: str) -> bytes:
    b = s.encode("cp1252")
    return struct.pack("<H", len(b)) + b


OBJ = struct.pack("<HhI", 0, -1, 0x00000014)


def prop(name: str, ptype: int, value: bytes, ver: int = 5) -> bytes:
    return wstr(name) + bytes([ptype]) + (b"\x01" if ver >= 4 else b"") + value


def script(name: str, props=(), ver: int = 5) -> bytes:
    return wstr(name) + (b"\x00" if ver >= 4 else b"") + struct.pack("<H", len(props)) + b"".join(props)


def vmad(scripts, ver: int = 5, tail: bytes = b"") -> bytes:
    return struct.pack("<hhH", ver, 2, len(scripts)) + b"".join(scripts) + tail


def all_props(ver: int = 5) -> list[bytes]:
    return [
        prop("pObj", 1, OBJ, ver),
        prop("pStr", 2, wstr("hello"), ver),
        prop("pInt", 3, struct.pack("<i", -7), ver),
        prop("pFloat", 4, struct.pack("<f", 1.5), ver),
        prop("pBool", 5, b"\x01", ver),
        prop("aObj", 11, struct.pack("<I", 2) + OBJ * 2, ver),
        prop("aStr", 12, struct.pack("<I", 2) + wstr("a") + wstr("bc"), ver),
        prop("aInt", 13, struct.pack("<I3i", 3, 1, 2, 3), ver),
        prop("aFloat", 14, struct.pack("<If", 1, 2.0), ver),
        prop("aBool", 15, struct.pack("<I", 2) + b"\x01\x00", ver),
    ]


def quest_tail(fragment: str, alias_script: str) -> bytes:
    t = b"\x02" + struct.pack("<H", 1) + wstr(fragment)
    t += struct.pack("<HhiB", 10, 0, 0, 0) + wstr(fragment) + wstr("Fragment_0")
    t += struct.pack("<H", 1) + OBJ + struct.pack("<hhH", 5, 2, 1) + script(alias_script, all_props())
    return t


def pex(name: str, parent: str = "") -> bytes:
    strings = [name, parent]
    out = bytearray(b"\xfa\x57\xc0\xde" + bytes([3, 2]) + struct.pack(">H", 1) + b"\0" * 8)
    for s in ("x.psc", "u", "m"):
        out += struct.pack(">H", len(s)) + s.encode()
    out += struct.pack(">H", len(strings))
    for s in strings:
        out += struct.pack(">H", len(s)) + s.encode()
    out += b"\x00" + struct.pack(">H", 0) + struct.pack(">H", 1)
    out += struct.pack(">HIH", 0, 12, 1) + b"\0" * 10
    return bytes(out)


def nif(textures: list[str]) -> bytes:
    out = b"Gamebryo File Format, Version 20.2.0.7\n" + struct.pack("<I", 0x14020007) + b"\x01"
    out += struct.pack("<III", 12, 1, 100)
    for s in (b"a", b"b", b"c"):
        out += bytes([len(s)]) + s
    t = b"BSShaderTextureSet"
    block = struct.pack("<I", len(textures)) + b"".join(
        struct.pack("<I", len(x)) + x.encode() for x in textures)
    out += struct.pack("<HI", 1, len(t)) + t + struct.pack("<H", 0) + struct.pack("<I", len(block))
    out += struct.pack("<III", 0, 0, 0) + block + struct.pack("<II", 1, 0)
    return out


def make_bsa(dest: Path, files: dict[str, bytes]) -> Path:
    tmp = dest.parent / (".src-" + dest.name)
    pairs = []
    for i, (p, data) in enumerate(files.items()):
        f = tmp / str(i)
        f.parent.mkdir(parents=True, exist_ok=True)
        f.write_bytes(data)
        pairs.append((p, f))
    dest.parent.mkdir(parents=True, exist_ok=True)
    write_bsa(pairs, dest)
    for _p, f in pairs:
        f.unlink()
    tmp.rmdir()
    return dest


def new_pack(tmp_path: Path, active: list[str]) -> Pack:
    root = create_project(tmp_path / "p", "AE", INIS, "all")
    ccc = root / "01000A10041EB009/romfs/Skyrim_aoc.ccc"
    raw = ccc.read_bytes()
    if not raw.endswith(b"\n"):
        raw += b"\r\n"
    ccc.write_bytes(raw + b"\r\n".join(a.encode() for a in active) + b"\r\n")
    return Pack.open(root)


def data(pack: Pack) -> Path:
    return pack.data_dir


def found(pack, code=None, deep=True, **kw):
    fs = [f for f in run_audit(pack, deep=deep, **kw).findings if f.category in NEW_CATS]
    return [f for f in fs if code is None or f.code == code]


# ------------------------------------------------------------------ records / VMAD
@pytest.mark.parametrize("ver", [5, 3])
def test_vmad_properties_of_every_type(ver):
    d = vmad([script("FirstScript", all_props(ver), ver), script("SecondScript", all_props(ver), ver)], ver)
    names, err = REC.parse_vmad(d, "ACTI")
    assert names == ["FirstScript", "SecondScript"] and err == 0


def test_vmad_fragments_and_aliases():
    d = vmad([script("MainQuestScript", all_props())], tail=quest_tail("QF_MyQuest_01000D62", "PlayerAliasScript"))
    names, err = REC.parse_vmad(d, "QUST")
    assert err == 0
    assert names == ["MainQuestScript", "QF_MyQuest_01000D62", "PlayerAliasScript"]
    info = vmad([], tail=b"\x02\x01" + wstr("TIF__01000D63") + b"\x00garbage")
    assert REC.parse_vmad(info, "INFO") == (["TIF__01000D63"], 0)
    # fragment data is ignored for types that don't have it
    assert REC.parse_vmad(info, "ACTI") == ([], 0)


def test_vmad_damaged_is_counted():
    good = vmad([script("Ok", all_props())])
    assert REC.parse_vmad(good[:-3], "ACTI") == ([], 1)
    bad_type = vmad([script("Ok", [prop("p", 99, b"")])])
    assert REC.parse_vmad(bad_type, "ACTI") == ([], 1)
    assert REC.parse_vmad(b"\x09\x00\x02\x00\x00\x00", "ACTI") == ([], 1)


def test_records_groups_compressed_and_xxxx(tmp_path):
    big = "X" * 70000
    p = plugin(tmp_path / "R.esp", [
        rec("ACTI", 0x01000801, [sub("EDID", zs("MyActi")), sub("VMAD", vmad([script("ActiScript")])),
                                 sub("MODL", zs("Data/Meshes/Mod/Acti.NIF"))]),
        rec("NPC_", 0x01000802, [sub("EDID", zs("MyNpc")), sub("VMAD", vmad([script("NpcScript", all_props())]))],
            compressed=True),
        rec("ARMO", 0x01000803, [sub("EDID", zs("MyArmor")), sub("MOD2", zs("mod\\armor_m.nif")),
                                 sub("MOD4", zs("mod\\armor_f.nif")), sub("INDX", b"\0\0\0\0"),
                                 sub("MODL", struct.pack("<I", 0x01000804))]),
        rec("ARMA", 0x01000804, [sub("EDID", zs("MyAA")), sub("MOD3", zs("mod\\aa_f.nif")),
                                 sub("MOD5", zs("mod\\1st_f.nif"))]),
        rec("BOOK", 0x01000805, [sub("EDID", zs("MyBook")), sub("DESC", zs(big)), sub("MODL", zs("clutter\\book.nif"))]),
    ] + [grup(b"CELL", 0, rec("CELL", 0x01000900, [sub("EDID", zs("MyCell"))]) + grup(
        struct.pack("<I", 0x01000900), 6, grup(struct.pack("<I", 0x01000900), 9,
                                              rec("REFR", 0x01000901, [sub("VMAD", vmad([script("RefScript")]))]))))])
    raw = p.read_bytes()
    assert sum(1 for _ in REC.iter_records(raw)) == 7
    types = [r.type for r in REC.iter_records(raw)]
    assert types[:5] == ["ACTI", "NPC_", "ARMO", "ARMA", "BOOK"] and "REFR" in types
    assert [r.type for r in REC.iter_records(raw, types=["REFR"])] == ["REFR"]
    npc = next(r for r in REC.iter_records(raw, types=["NPC_"]))
    t, fid, flags, subs = npc
    assert (t, fid) == ("NPC_", 0x01000802) and flags & REC.COMPRESSED
    assert [s for s, _ in subs] == ["EDID", "VMAD"]
    book = next(r for r in REC.iter_records(raw, types=["BOOK"]))
    assert len(dict(book.subrecords())["DESC"]) == 70001
    s = REC.scripts_attached(p)
    assert set(s) == {"actiscript", "npcscript", "refscript"} and s.unreadable == 0
    assert s["npcscript"] == ["MyNpc"] and s["refscript"] == ["REFR 01000901"]
    assert REC.models_used(p) == {"meshes\\mod\\acti.nif", "meshes\\mod\\armor_m.nif", "meshes\\mod\\armor_f.nif",
                                  "meshes\\mod\\aa_f.nif", "meshes\\mod\\1st_f.nif", "meshes\\clutter\\book.nif"}


def test_records_skip_masters(tmp_path):
    p = plugin(tmp_path / "S.esp", [
        rec("ACTI", 0x01000801, [sub("VMAD", vmad([script("FishScript")])), sub("MODL", zs("cc\\fish.nif"))]),
        rec("ACTI", 0x02000802, [sub("VMAD", vmad([script("OwnScript")]))]),
    ], masters=("Skyrim.esm", "ccBGSSSE001-Fish.esm"))
    assert set(REC.scripts_attached(p, ["ccBGSSSE001-Fish.esm"])) == {"ownscript"}
    assert REC.models_used(p, ["ccbgssse001-fish.esm"]) == set()
    assert set(REC.scripts_attached(p)) == {"fishscript", "ownscript"}


def test_unreadable_record_counted(tmp_path):
    p = plugin(tmp_path / "U.esp", [
        rec("ACTI", 0x01000801, [sub("VMAD", b"\x05\x00\x02\x00\x05\x00junk")]),
        rec("ACTI", 0x01000802, [sub("VMAD", vmad([script("Fine")]))]),
    ])
    s = REC.scripts_attached(p)
    assert set(s) == {"fine"} and s.unreadable == 1


# ------------------------------------------------------------------ pex, NIF helpers
def test_pex_parent_and_nif_paths():
    assert REQ.pex_object(pex("MyMCM", "SKI_ConfigBase")) == ("MyMCM", "SKI_ConfigBase")
    assert REQ.pex_object(pex("Plain")) == ("Plain", "")
    from skynx import nif as NIF
    assert NIF.texture_paths(NIF.parse(nif(["textures\\a.dds", ""]))) == ["textures\\a.dds", ""]
    assert REQ._tex_norm("Data\\Textures\\Mod\\A.dds") == "textures\\mod\\a.dds"
    assert REQ._tex_norm("mod/a.dds") == "textures\\mod\\a.dds"


# ------------------------------------------------------------------ vanilla index
def test_vanilla_index_cache(tmp_path):
    vdir, cdir = tmp_path / "vanilla", tmp_path / "cache"
    assert V.status(None) == "unset" and V.status(tmp_path / "nope") == "missing"
    vdir.mkdir()
    assert V.status(vdir) == "empty"
    make_bsa(vdir / "Skyrim - Misc.bsa", {"scripts\\Quest.pex": pex("Quest")})
    (vdir / "meshes" / "loose").mkdir(parents=True)
    (vdir / "meshes" / "loose" / "L.nif").write_bytes(b"x")
    assert V.status(vdir) == "ok"
    idx = V.index(vdir, cdir)
    assert idx == {"scripts\\quest.pex", "meshes\\loose\\l.nif"}
    cache = list(cdir.glob("vanilla-index-*.json"))
    saved = json.loads(cache[0].read_text())["bsas"]
    assert len(cache) == 1 and list(saved) == ["Skyrim - Misc.bsa"] and saved["Skyrim - Misc.bsa"]["files"] == ["scripts\\quest.pex"]
    V._MEMO.clear()
    assert V.index(vdir, cdir) == idx           # from the JSON cache
    make_bsa(vdir / "Skyrim - Meshes0.bsa", {"meshes\\a.nif": b"n"})
    assert "meshes\\a.nif" in V.index(vdir, cdir)  # signature changed: rebuilt
    # a romfs folder works too
    romfs = tmp_path / "romfs"
    (romfs / "Data").mkdir(parents=True)
    make_bsa(romfs / "Data" / "Skyrim - Misc.bsa", {"scripts\\x.pex": b"p"})
    assert V.index(romfs) == {"scripts\\x.pex"}


def test_no_vanilla_folder_is_an_info(tmp_path):
    pack = new_pack(tmp_path, ["Mod.esp"])
    plugin(data(pack) / "Mod.esp", [rec("ACTI", 0x01000801, [sub("VMAD", vmad([script("GoneScript")]))])])
    pack = Pack.open(pack.root)
    fs = found(pack)
    assert [f.code for f in fs] == ["req-vanilla-unset"] and fs[0].severity == "info"
    es = fs[0].to_dict("es")
    assert es["category"] == "Requisitos" and "Ajustes" in es["detail"]
    assert [f.code for f in found(pack, vanilla_dir=tmp_path / "nowhere")] == ["req-vanilla-bad"]
    assert "nowhere" in found(pack, vanilla_dir=tmp_path / "nowhere")[0].to_dict()["detail"]
    assert found(pack, deep=False) == []


# ------------------------------------------------------------------ a, b, c with a vanilla index
@pytest.fixture()
def req_pack(tmp_path):
    vdir = tmp_path / "vanilla"
    make_bsa(vdir / "Skyrim - Misc.bsa", {
        "scripts\\vanillascript.pex": pex("VanillaScript"),
        "scripts\\quest.pex": pex("Quest"),
        "scripts\\referencealias.pex": pex("ReferenceAlias"),
        "scripts\\refscript.pex": pex("RefScript"),
        "meshes\\vanilla\\thing.nif": nif([]),
        "textures\\vanilla\\v.dds": b"DDS ",
    })
    pack = new_pack(tmp_path, ["Mod.esp"])
    d = data(pack)
    quest = vmad([script("ModScript", all_props()), script("VanillaScript"), script("GoneScript"),
                  script("SKI_PlayerLoadGameAlias")],
                 tail=quest_tail("QF_ModQuest_02000D62", "AliasScript"))
    plugin(d / "Mod.esp", [
        rec("QUST", 0x02000D62, [sub("EDID", zs("ModQuest")), sub("VMAD", quest)]),
        rec("ACTI", 0x02000D63, [sub("EDID", zs("ModActi")), sub("MODL", zs("Mod\\Thing.nif"))]),
        rec("STAT", 0x02000D64, [sub("EDID", zs("ModStat")), sub("MODL", zs("Vanilla\\Thing.nif"))]),
        rec("MISC", 0x02000D65, [sub("EDID", zs("ModMisc")), sub("MODL", zs("Gone\\Missing.nif"))]),
        rec("ARMO", 0x02000D66, [sub("EDID", zs("ModArmor")), sub("MOD2", zs("mod\\thing.nif")),
                                 sub("MOD4", zs("gone\\female.nif")), sub("MODL", b"\x67\x0d\x00\x02")]),
        rec("NPC_", 0x02000D68, [sub("EDID", zs("ModNpc")), sub("VMAD", vmad([script("CompressedScript")]))],
            compressed=True),
        rec("ACTI", 0x01000801, [sub("EDID", zs("FishThing")), sub("VMAD", vmad([script("CCOnlyScript")])),
                                 sub("MODL", zs("cc\\fish.nif"))]),
    ] + [grup(b"CELL", 0, rec("CELL", 0x02000900, []) + grup(b"\0\0\0\0", 9,
             rec("REFR", 0x02000901, [sub("VMAD", vmad([script("RefScript")]))])))],
        masters=("Skyrim.esm", "ccBGSSSE001-Fish.esm"))
    make_bsa(d / "Mod.bsa", {
        "scripts\\modscript.pex": pex("ModScript", "Quest"),
        "scripts\\aliasscript.pex": pex("AliasScript", "ReferenceAlias"),
        "scripts\\modmcm.pex": pex("ModMCM", "SKI_ConfigBase"),
        "meshes\\mod\\thing.nif": nif(["textures\\mod\\t.dds", "Vanilla\\V.dds", "textures\\gone\\g.dds",
                                       "textures\\actors\\character\\facegendata\\facetint\\mod.esp\\00001.dds",
                                       ""]),
        "textures\\mod\\t.dds": b"DDS ",
    })
    return Pack.open(pack.root), vdir


def test_missing_scripts_meshes_textures(req_pack, tmp_path):
    pack, vdir = req_pack
    fs = {f.code: f for f in found(pack, vanilla_dir=vdir, cache_dir=tmp_path / "cache")}
    assert "req-vanilla-unset" not in fs
    sc = fs["req-script-missing"]
    assert sc.subject == "Mod.esp" and sc.severity == "aviso" and sc.params["n"] == 2
    names = sorted(i.split(" ")[0] for i in sc.items)
    assert names == ["CompressedScript", "GoneScript"]
    fr = fs["req-script-fragment"]                  # a fragment the author didn't ship
    assert fr.severity == "info" and [i.split(" ")[0] for i in fr.items] == ["QF_ModQuest_02000D62"]
    assert "GoneScript (ModQuest)" in sc.items
    me = fs["req-mesh-missing"]
    assert sorted(i.split(" ")[0] for i in me.items) == ["meshes\\gone\\female.nif", "meshes\\gone\\missing.nif"]
    pc = fs["req-script-pconly"]                    # SkyUI's menu scripts: expected on Switch
    assert pc.severity == "info" and pc.items == ["SKI_PlayerLoadGameAlias (ModQuest)"]
    pa = fs["req-script-parent"]
    assert pa.subject == "Mod.bsa" and pa.items == ["ModMCM extends SKI_ConfigBase"]
    assert pa.severity == "info"
    tx = fs["req-tex-missing"]
    assert tx.subject == "Mod.bsa" and tx.items == ["textures\\gone\\g.dds (thing.nif)"]
    assert run_audit(pack, deep=True, vanilla_dir=vdir).stats["vanilla"]["state"] == "ok"
    assert list((tmp_path / "cache" / "nif-textures").glob("*.json"))
    for f in fs.values():
        for lang in ("en", "es"):
            title, detail = f.text(lang)
            assert title and detail and "{" not in title + detail and "—" not in title + detail


def test_game_list_outlives_its_bsas(tmp_path):
    """The BSAs are needed once: after the list is built they can be deleted."""
    vdir, cdir = tmp_path / "vanilla", tmp_path / "cache"
    make_bsa(vdir / "Skyrim - Misc.bsa", {"scripts\\quest.pex": pex("Quest")})
    make_bsa(vdir / "Skyrim - Meshes0.bsa", {"meshes\\a.nif": nif(["textures\\a_d.dds", "textures\\gone_n.dds"])})
    # the game's own plugin asks for a model no BSA has (vanilla races' .egt)
    plugin(vdir / "Skyrim.esm", [rec("RACE", 0x00000800, [sub("EDID", zs("NordRace")),
                                  sub("MODL", zs("Actors\\Character\\UpperBodyHumanMale.egt"))])], masters=())
    assert V.index(vdir, cdir) == {"scripts\\quest.pex", "meshes\\a.nif"}
    refs = V.game_refs(vdir, cdir)
    assert "meshes\\actors\\character\\upperbodyhumanmale.egt" in refs
    assert {"textures\\a_d.dds", "textures\\gone_n.dds"} <= refs
    sm = V.summary(vdir, cdir)
    assert sm["files"] == 2 and sm["bsas"] == 2 and sm["plugins"] == 1 and sm["kept"] == []
    assert "Skyrim - Animations.bsa" in sm["missing_core"] and "Skyrim - Misc.bsa" not in sm["missing_core"]
    # delete every BSA: the list keeps what they had
    for b in vdir.glob("*.bsa"):
        b.unlink()
    V._MEMO.clear()
    assert V.status(vdir) == "empty" and V.status(vdir, cdir) == "ok"
    assert V.index(vdir, cdir) == {"scripts\\quest.pex", "meshes\\a.nif"}
    assert V.summary(vdir, cdir)["kept"] == ["Skyrim - Meshes0.bsa", "Skyrim - Misc.bsa"]
    # a game update: the same BSA copied back with other content is read again
    make_bsa(vdir / "Skyrim - Misc.bsa", {"scripts\\quest.pex": pex("Quest"), "scripts\\new.pex": pex("New")})
    assert "scripts\\new.pex" in V.index(vdir, cdir)
    assert V.summary(vdir, cdir)["kept"] == ["Skyrim - Meshes0.bsa"]
    assert V.forget_kept(vdir, cdir) == 1
    assert V.index(vdir, cdir) == {"scripts\\quest.pex", "scripts\\new.pex"}


def test_what_the_game_asks_for_and_author_mistakes(tmp_path):
    vdir = tmp_path / "vanilla"
    make_bsa(vdir / "Skyrim - Misc.bsa", {"scripts\\quest.pex": pex("Quest")})
    plugin(vdir / "Skyrim.esm", [rec("RACE", 0x00000800, [sub("EDID", zs("NordRace")),
                                  sub("MODL", zs("Actors\\Character\\UpperBodyHumanMale.egt"))])], masters=())
    pack = new_pack(tmp_path, ["Mod.esp"])
    d = data(pack)
    plugin(d / "Mod.esp", [
        rec("RACE", 0x00000800, [sub("EDID", zs("NordRace")),              # an override of the game's race
                                 sub("MODL", zs("actors\\character\\upperbodyhumanmale.egt"))]),
        rec("SPEL", 0x01000801, [sub("EDID", zs("Shock")), sub("MODL", zs("magic\\explosionshock01.dds"))]),
        rec("STAT", 0x01000802, [sub("EDID", zs("Real")), sub("MODL", zs("gone\\real.nif"))]),
    ])
    make_bsa(d / "Mod.bsa", {"meshes\\m.nif": nif(["textures\\m\\wall_p.dds", "textures\\m\\beam_n .dds",
                                                    "textures\\m\\wall_d.dds"])})
    fs = {f.code: f for f in found(Pack.open(pack.root), vanilla_dir=vdir, cache_dir=tmp_path / "c")}
    assert [i.split(" ")[0] for i in fs["req-mesh-missing"].items] == ["meshes\\gone\\real.nif"]
    assert fs["req-tex-missing"].items == ["textures\\m\\wall_d.dds (m.nif)"]
    assert fs["req-tex-minor"].severity == "info" and fs["req-tex-minor"].items == ["textures\\m\\wall_p.dds (m.nif · Mod.bsa)"]
    br = fs["req-path-broken"]
    assert br.severity == "info" and sorted(br.items) == ["meshes\\magic\\explosionshock01.dds (Mod.esp)",
                                                         "textures\\m\\beam_n .dds (m.nif · Mod.bsa)"]
    assert fs["req-vanilla-partial"].severity == "info"
    for f in fs.values():
        for lang in ("en", "es"):
            title, detail = f.text(lang)
            assert title and detail and "{" not in title + detail and "—" not in title + detail


def test_items_are_capped(tmp_path):
    vdir = tmp_path / "vanilla"
    make_bsa(vdir / "Skyrim - Misc.bsa", {"scripts\\quest.pex": pex("Quest")})
    pack = new_pack(tmp_path, ["Many.esp"])
    plugin(data(pack) / "Many.esp", [rec("STAT", 0x01000800 + i, [sub("MODL", zs(f"gone\\m{i:02}.nif"))])
                                     for i in range(25)])
    f = found(Pack.open(pack.root), "req-mesh-missing", vanilla_dir=vdir)[0]
    assert {k: v for k, v in f.params.items() if k != "_all"} == {"name": "Many.esp", "n": 25, "shown": 20}
    assert len(f.params["_all"]) == 25                 # the whole list, for the exported report
    assert len(f.items) == 21 and f.items[-1] == "(+5)"


# ------------------------------------------------------------------ d. frameworks
def test_framework_patterns(tmp_path):
    fo = REQ.framework_of
    assert fo("meshes\\actors\\character\\animations\\DynamicAnimationReplacer\\_CustomConditions\\1\\a.hkx") == "DAR"
    assert fo("Meshes/Actors/Wolf/Animations/OpenAnimationReplacer/Mod/config.json") == "OAR"
    assert fo("Nemesis_Engine\\mod\\abcd\\info.ini") == "Nemesis"
    assert fo("meshes\\actors\\character\\animations\\nemesis_pcea\\x.hkx") == "Nemesis"
    assert fo("meshes\\actors\\character\\animations\\MyMod\\FNIS_MyMod_List.txt") == "FNIS"
    assert fo("meshes\\actors\\character\\behaviors\\FNIS_MyMod_Behavior.hkx") == "FNIS"
    assert fo("tools\\GenerateFNIS_for_Users\\GenerateFNISforUsers.exe") == "FNIS"
    assert fo("meshes\\actors\\character\\animations\\mt_idle.hkx") is None
    loose = tmp_path / "mod"
    (loose / "Nemesis_Engine" / "mod" / "x").mkdir(parents=True)
    (loose / "Nemesis_Engine" / "mod" / "x" / "info.ini").write_text("a")
    assert REQ.scan_tree(loose) == {"Nemesis": ["Nemesis_Engine\\mod\\x\\info.ini"]}
    b = make_bsa(tmp_path / "x.bsa", {"meshes\\actors\\character\\animations\\fnis_x_list.txt": b"x"})
    assert list(REQ.scan_bsa(b)) == ["FNIS"]


def test_frameworks_in_audit_without_deep(tmp_path):
    pack = new_pack(tmp_path, ["Anim.esp"])
    d = data(pack)
    plugin(d / "Anim.esp", [rec("STAT", 0x01000800, [])])
    make_bsa(d / "Anim.bsa", {
        "meshes\\actors\\character\\animations\\dynamicanimationreplacer\\_customconditions\\100\\mt_idle.hkx": b"h",
        "meshes\\actors\\character\\animations\\dynamicanimationreplacer\\_customconditions\\100\\_conditions.txt": b"c",
    })
    oar = d / "meshes" / "actors" / "character" / "animations" / "OpenAnimationReplacer" / "Mod"
    oar.mkdir(parents=True)
    (oar / "config.json").write_text("{}")
    fs = {f.subject: f for f in found(Pack.open(pack.root), "req-anim-framework", deep=False)}
    assert fs["Anim.bsa"].params["kinds"] == "DAR" and fs["Anim.bsa"].params["n"] == 2
    assert fs["Data"].params["kinds"] == "OAR"
    assert "SKSE" in fs["Anim.bsa"].to_dict("es")["detail"]


# ------------------------------------------------------------------ e. behaviors
def test_behavior_conflict(tmp_path):
    pack = new_pack(tmp_path, ["A.esp", "B.esp"])
    d = data(pack)
    beh = "meshes\\actors\\character\\behaviors\\"
    for n, master in (("A", b"A" * 300), ("B", b"B" * 300)):
        plugin(d / f"{n}.esp", [rec("STAT", 0x01000800, [])])
        make_bsa(d / f"{n}.bsa", {beh + "0_master.hkx": master, beh + "same.hkx": b"S" * 100,
                                  "meshes\\actors\\character\\animations\\walk.hkx": n.encode() * 50})
    fs = found(Pack.open(pack.root), "req-behavior-conflict", deep=False)
    assert len(fs) == 1
    f = fs[0]
    assert f.subject == "B.bsa" and f.params["others"] == "A.bsa" and f.params["n"] == 1
    assert f.items == [beh + "0_master.hkx (A.bsa)"]
    assert REQ.is_behavior("meshes\\actors\\character\\characters female\\defaultfemale.hkx")
    assert REQ.is_behavior("meshes\\actors\\dragon\\dragonproject.hkx")
    assert not REQ.is_behavior("meshes\\actors\\character\\animations\\walk.hkx")


# ------------------------------------------------------------------ duplicates
def test_merged_components():
    text = "Merged Plugin: \r\n  A.esp\r\n  B - Thing.esm\r\n  A.esp\r\n"
    assert merged_components(text) == ["A.esp", "B - Thing.esm"]
    assert merged_components("A mod that merged all optional files. Requires Dragonborn") == []
    head = sub("HEDR", struct.pack("<fiI", 1.7, 1, 0)) + sub("SNAM", zs("Merged Plugin:\n  X.esp"))
    raw = struct.pack("<4sIIIHHHH", b"TES4", len(head), 0, 0, 0, 0, 44, 0) + head
    assert merged_components(raw) == ["X.esp"]
    assert merged_components(b"not a plugin") == []


def test_duplicates(tmp_path):
    active = ["Same.esp", "Same Copy.esp", "Alone.esp", "Ryn's Stones.esp", "Ryn_s Stones.esp",
              "Big.esp", "Merged.esp", "PartA.esp", "PartB.esp", "Dummy1.esp", "Dummy2.esp"]
    pack = new_pack(tmp_path, active)
    d = data(pack)
    same = plugin(d / "Same.esp", [rec("STAT", 0x01000800, [sub("EDID", zs("SameStat"))])])
    (d / "Same Copy.esp").write_bytes(same.read_bytes())
    alone = plugin(d / "Alone.esp", [rec("STAT", 0x01000800, [sub("EDID", zs("AloneStat"))])])
    (d / "Alone - Copy.esp").write_bytes(alone.read_bytes())          # not in the list
    plugin(d / "Ryn's Stones.esp", [rec("STAT", 0x01000800, [sub("EDID", zs("Ryn1"))])])
    plugin(d / "Ryn_s Stones.esp", [rec("STAT", 0x01000800, [sub("EDID", zs("Ryn2"))])])
    plugin(d / "Big.esp", [rec("STAT", 0x01000800, [sub("EDID", zs("BigStat"))])])
    files = {"meshes\\big\\a.nif": b"a" * 50, "textures\\big\\a.dds": b"t" * 80}
    make_bsa(d / "Big.bsa", files)
    make_bsa(d / "BigM.bsa", files)                                    # Koka-style short copy
    plugin(d / "Merged.esp", [rec("STAT", 0x01000800, [sub("EDID", zs("M"))])],
           snam="Merged Plugin: \r\n  PartA.esp\r\n  PartB.esp\r\n  PartC.esp")
    plugin(d / "PartA.esp", [], nrec=0)                                # placeholder: fine
    plugin(d / "PartB.esp", [rec("STAT", 0x01000800, [sub("EDID", zs("B"))])])
    plugin(d / "PartC.esp", [rec("STAT", 0x01000800, [sub("EDID", zs("C"))])])  # not active
    plugin(d / "Dummy1.esp", [], nrec=0)
    plugin(d / "Dummy2.esp", [], nrec=0)
    ini = pack.base_romfs / "Skyrim.ini"
    lst = read_ini(ini).archive_list("sResourceArchiveList")
    ini.write_bytes(set_archive_list(ini.read_bytes(), "sResourceArchiveList", lst + ["BigM.bsa"]))
    pack = Pack.open(pack.root)

    fs = found(pack, deep=False)
    by = {}
    for f in fs:
        by.setdefault(f.code, []).append(f)
    assert {f.category for f in fs} == {"duplicates"}
    s = by["dup-plugin-same"]
    assert len(s) == 1 and s[0].subject == "Same Copy.esp" and s[0].params["other"] == "Same.esp"
    c = by["dup-plugin-copy"]
    assert [f.subject for f in c] == ["Alone - Copy.esp"] and c[0].severity == "info"
    n = by["dup-plugin-name"]
    assert len(n) == 1 and set(n[0].items) == {"Ryn's Stones.esp", "Ryn_s Stones.esp"}
    b = by["dup-bsa"]
    assert len(b) == 1 and b[0].subject == "Big.bsa" and b[0].params == {"name": "Big.bsa", "other": "BigM.bsa", "files": 2}
    assert b[0].fix["kind"] == "ini_remove_archive" and b[0].fix["item"] == "BigM.bsa"
    assert b[0].fix["key"] == "sResourceArchiveList" and b[0].fix["risk"] == "seguro"
    m = by["dup-merged"]
    assert [f.subject for f in m] == ["Merged.esp>PartB.esp"] and m[0].severity == "aviso"
    assert [f.subject for f in by["dup-merged-copy"]] == ["Merged.esp>PartC.esp"]
    for f in fs:
        for lang in ("en", "es"):
            title, detail = f.text(lang)
            assert "{" not in title + detail and "—" not in title + detail

    apply(pack, b[0].fix)
    pack = Pack.open(pack.root)
    assert "BigM.bsa" not in pack.archive_lists()["sResourceArchiveList"]
    assert not [f for f in found(pack, deep=False) if f.code == "dup-bsa"]


def test_empty_bsas_are_not_duplicates(tmp_path):
    pack = new_pack(tmp_path, ["E1.esp", "E2.esp"])
    d = data(pack)
    for n in ("E1", "E2"):
        plugin(d / f"{n}.esp", [rec("STAT", 0x01000800, [sub("EDID", zs(n))])])
        (d / f"{n}.bsa").write_bytes(struct.pack("<4sIIIIIIIHH", b"BSA\x00", 105, 36, 3, 0, 0, 0, 0, 0, 0))
    assert find_duplicates(Pack.open(pack.root)) == []


def test_a_missing_ini_bsa_is_judged_by_its_files(tmp_path):
    """Converters often join several BSAs into one and leave the old names in
    the ini: what matters is whether the files are there, not the name."""
    from skynx.ini import parse_ini, set_archive_list
    vdir = tmp_path / "vanilla"
    make_bsa(vdir / "Skyrim - Misc.bsa", {"scripts\\quest.pex": pex("Quest")})
    pack = new_pack(tmp_path, ["Joined.esp"])
    plugin(data(pack) / "Joined.esp", [rec("STAT", 0x01000800, [sub("MODL", zs("joined\\a.nif"))])])
    make_bsa(data(pack) / "Joined.bsa", {"meshes\\joined\\a.nif": nif(["textures\\joined\\a.dds"]),
                                         "textures\\joined\\a.dds": b"DDS "})
    for ini in pack.ini_paths:
        raw = ini.read_bytes()
        cur = parse_ini(raw).archive_list("sResourceArchiveList")
        if cur:
            ini.write_bytes(set_archive_list(raw, "sResourceArchiveList", cur + ["Joined - Meshes.bsa"]))
    pack = Pack.open(pack.root)
    f = next(x for x in run_audit(pack, deep=True, vanilla_dir=vdir).findings if x.code == "ini-bsa-missing")
    assert f.severity == "info" and f.fix["risk"] == "seguro"
    assert "quedaron dentro de otro BSA" in f.text("es")[1]
    # without the base game it can't tell
    f = next(x for x in run_audit(pack, deep=True, vanilla_dir=tmp_path / "nowhere").findings
             if x.code == "ini-bsa-missing")
    assert f.severity == "aviso" and "juego base" in f.text("es")[1]
    # a mesh the plugin needs is gone: it may have been in that BSA
    plugin(data(pack) / "Joined.esp", [rec("STAT", 0x01000800, [sub("MODL", zs("joined\\gone.nif"))])])
    f = next(x for x in run_audit(Pack.open(pack.root), deep=True, vanilla_dir=vdir).findings
             if x.code == "ini-bsa-missing")
    assert f.severity == "aviso" and "Requisitos" in f.text("es")[1]


def test_nif_with_bytes_after_the_footer():
    """The Creation Kit's FaceGen export leaves padding or the tail of an older,
    longer save after the footer (Skyrim Revamped). The game stops at the
    footer, so the file is fine and a rename can patch it."""
    from skynx import nif as NIF
    raw = nif(["textures\\a.dds"])
    for tail in (b"\0\0", b"t\0v\0s\0" * 50 + b"MaleBrow1_n.dds\0\0\xff\xff"):
        f = NIF.parse(raw + tail)
        assert NIF.texture_paths(f) == ["textures\\a.dds"]
        new, n = NIF.replace_texture_folder(raw + tail, "textures", "tex2")
        assert n == 1 and new.endswith(tail) and NIF.texture_paths(NIF.parse(new)) == ["tex2\\a.dds"]
    with pytest.raises(NIF.NifError):
        NIF.parse(raw[:-3])


def test_doctor_report_markdown_has_every_item(tmp_path):
    from skynx.audit import report_markdown
    vdir = tmp_path / "vanilla"
    make_bsa(vdir / "Skyrim - Misc.bsa", {"scripts\\quest.pex": pex("Quest")})
    pack = new_pack(tmp_path, ["Many.esp"])
    plugin(data(pack) / "Many.esp", [rec("STAT", 0x01000800 + i, [sub("MODL", zs(f"gone\\m{i:02}.nif"))])
                                     for i in range(25)])
    rep = run_audit(Pack.open(pack.root), deep=True, vanilla_dir=vdir)
    for lang in ("en", "es"):
        md = report_markdown(rep, lang, "Test", ["Mode: AE"])
        assert md.startswith("# ") and "## " in md and "- Mode: AE" in md
        assert "meshes\\gone\\m24.nif" in md and "(+5)" not in md


def _strings(entries: dict[int, str]) -> bytes:
    data, dirs = b"", b""
    for sid, text in entries.items():
        dirs += struct.pack("<II", sid, len(data))
        data += text.encode("utf-8") + b"\0"
    return struct.pack("<II", len(entries), len(data)) + dirs + data


def test_names_in_another_language(tmp_path):
    """The Ordinary Women came from a Russian upload: Gerdur showed as Гердур.
    The Doctor finds names in another script and puts back the game's own,
    read from Skyrim.esm (localized) and its strings in Skyrim - Interface.bsa."""
    from skynx import names as NM
    vdir = tmp_path / "vanilla"
    make_bsa(vdir / "Skyrim - Misc.bsa", {"scripts\\quest.pex": pex("Quest")})
    make_bsa(vdir / "Skyrim - Interface.bsa", {"strings\\skyrim_english.strings": _strings({0x1A2B: "Gerdur"})})
    esm = plugin(vdir / "Skyrim.esm", [rec("NPC_", 0x00013BBC, [sub("EDID", zs("Gerdur")),
                                                                 sub("FULL", struct.pack("<I", 0x1A2B))])], masters=())
    raw = bytearray(esm.read_bytes())
    struct.pack_into("<I", raw, 8, 0x81)                    # master, localized
    esm.write_bytes(bytes(raw))
    pack = new_pack(tmp_path, ["Women.esp"])
    plugin(data(pack) / "Women.esp", [
        rec("NPC_", 0x00013BBC, [sub("EDID", zs("Gerdur")), sub("FULL", "Гердур".encode() + b"\0")],
            compressed=True),
        rec("NPC_", 0x01000801, [sub("EDID", zs("NewWoman")), sub("FULL", "Новая".encode() + b"\0")]),
        rec("NPC_", 0x01000802, [sub("EDID", zs("Plain")), sub("FULL", zs("Lydia"))]),
    ])
    pack = Pack.open(pack.root)
    [f] = [x for x in run_audit(pack, deep=True, vanilla_dir=vdir, cache_dir=tmp_path / "c").findings
           if x.code == "names-foreign"]
    assert f.subject == "Women.esp" and f.params["n"] == 2 and f.params["fixable"] == 1
    assert "Gerdur: Гердур → Gerdur" in f.items and "NewWoman: Новая" in f.items
    assert f.fix["risk"] == "seguro"
    for lang in ("en", "es"):
        title, detail = f.text(lang)
        assert "{" not in title + detail and "—" not in title + detail
    apply(pack, f.fix)
    pack = Pack.open(pack.root)
    left = NM.scan(data(pack) / "Women.esp")
    assert [x["edid"] for x in left] == ["NewWoman"]          # its own record keeps its name
    names = {r.formid: dict(REC.iter_subrecords(r.data)).get("FULL") for r in REC.iter_records(data(pack) / "Women.esp")}
    assert names[0x00013BBC] == b"Gerdur\0" and names[0x01000802] == b"Lydia\0"
    # cp1251 bytes (a Russian Windows upload) count too; accented Latin doesn't
    assert NM.foreign("Гердур".encode("cp1251")) and not NM.foreign("Érdi Hélène".encode("cp1252"))


def test_broken_paths_typed_by_authors():
    from skynx.requirements import broken_path
    assert broken_path("textures\\cubemaps\\eyecubemap.dds (eyecubemap.dds)")   # Wyrmstooth NX
    assert broken_path("textures\\armor\\a .dds") and broken_path("textures\\ armor\\a.dds")
    assert broken_path("meshes\\x\\noext", model=True)
    assert not broken_path("textures\\cubemaps\\eyecubemap.dds")
    assert not broken_path("textures\\my mod (v2)\\a.dds")
