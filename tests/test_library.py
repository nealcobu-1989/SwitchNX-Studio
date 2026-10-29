"""Intake, Library and transfers between packs.

Run: python -m pytest -q tests   (real-pack tests need work/mirror and the
read-only originals under private-test-data/SkyNX)
"""
import shutil
import struct
import sys
import zipfile
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from skynx import library as L  # noqa: E402
from skynx.builder import create_project, load_mods  # noqa: E402
from skynx.ccc import parse_ccc  # noqa: E402
from skynx.history import list_history, undo  # noqa: E402
from skynx.ini import parse_ini, read_ini, set_archive_list  # noqa: E402
from skynx.intake import IntakeError, detect  # noqa: E402
from skynx.pack import Pack  # noqa: E402
from skynx.transfer import (TransferError, apply_transfer, list_pack_mods,  # noqa: E402
                            owner_for_bsa, plan_transfer)

MIRROR = ROOT / "work" / "mirror"
INIS = ROOT / "tests" / "fixtures" / "console-inis"
COMBAT = Path("private-test-data/SkyNX/Other converted mods/Combat Walk and Run Animations Pak NX")
AVNER = "Avner ModPack Revised 2026"
ASHIRO = "Ashiro_s Light Modlist"
need_mirror = pytest.mark.skipif(not MIRROR.exists(), reason="no mirror")
EMPTY_BSA = struct.pack("<4sIIIIIIIHH", b"BSA\x00", 105, 36, 3, 0, 0, 0, 0, 0, 0)


# ---------------------------------------------------------------- helpers
def fake_plugin(path: Path, masters=(), records=1, flags=0) -> Path:
    data = b"HEDR" + struct.pack("<H", 12) + struct.pack("<fiI", 1.7, records, 0x800)
    for m in masters:
        z = m.encode() + b"\0"
        data += b"MAST" + struct.pack("<H", len(z)) + z + b"DATA" + struct.pack("<H", 8) + b"\0" * 8
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(b"TES4" + struct.pack("<IIIHHHH", len(data), flags, 0, 0, 0, 44, 0) + data)
    return path


def pc_dds() -> bytes:
    h = bytearray(128)
    h[0:4] = b"DDS "
    struct.pack_into("<I", h, 4, 124)
    struct.pack_into("<II", h, 12, 256, 256)
    struct.pack_into("<I", h, 28, 1)
    h[84:88] = b"DXT5"
    return bytes(h) + b"\0" * 256 * 256


def zip_dir(folder: Path, dest: Path, prefix: str = "") -> Path:
    with zipfile.ZipFile(dest, "w") as z:
        for p in sorted(folder.rglob("*")):
            if p.is_file() and ".skynx" not in p.parts:
                z.write(p, prefix + p.relative_to(folder).as_posix())
    return dest


def mini_pack(where: Path) -> Path:
    root = create_project(where, "AE", INIS, "all")
    data = root / "01000A10041EA000/romfs/Data"
    fake_plugin(data / "Tiny.esp", ["Skyrim.esm"])
    (data / "Tiny.bsa").write_bytes(EMPTY_BSA)
    ccc = root / "01000A10041EB009/romfs/Skyrim_aoc.ccc"
    ccc.write_bytes(ccc.read_bytes() + b"Tiny.esp\r\n")
    return root


def avner_as_downloaded(tmp_path: Path) -> Path:
    """Avner Revised as it comes from Drive: the list says Ryn's, the files Ryn_s."""
    root = tmp_path / AVNER
    shutil.copytree(MIRROR / AVNER, root, symlinks=True)
    data = root / AVNER / "01000A10041EA000/romfs/Data"
    for n in ("Ryn's Standing Stones.esp", "Ryn's Standing Stones.bsa"):
        (data / n).unlink()
    return root


def state(root: Path) -> dict:
    out = {}
    for p in sorted(Path(root).rglob("*")):
        if p.is_file() and "history" not in p.parts and "papelera" not in p.parts and "trash" not in p.parts:
            out[str(p.relative_to(root))] = p.read_bytes()
    return out


# ---------------------------------------------------------------- intake
def test_intake_pc_mod(tmp_path):
    mod = tmp_path / "Pretty Swords"
    fake_plugin(mod / "Pretty Swords.esp", ["Skyrim.esm"])
    (mod / "textures/weapons").mkdir(parents=True)
    for i in range(3):
        (mod / f"textures/weapons/sword{i}.dds").write_bytes(pc_dds())
    (mod / "sound/fx").mkdir(parents=True)
    (mod / "sound/fx/swing.wav").write_bytes(b"RIFF0000WAVE")
    d = detect(mod)
    assert (d.kind, d.action) == ("pc-mod", "convert")
    assert d.evidence["textures"]["pc"] == 3 and d.evidence["textures"]["switch"] == 0
    assert d.evidence["sounds"]["pc"] == 1
    assert d.evidence["plugins"] == ["Pretty Swords.esp"]
    assert "PC" in d.summary[0] and "PC" in d.summary[1]
    dz = detect(zip_dir(mod, tmp_path / "Pretty Swords.zip", "Pretty Swords/"))
    assert dz.kind == "pc-mod" and dz.evidence["textures"]["pc"] == 3


@pytest.mark.skipif(not COMBAT.exists(), reason="no converted mods")
def test_intake_switch_mod_from_real_bsas(tmp_path):
    mod = tmp_path / "Combat NX"
    mod.mkdir()
    for b in COMBAT.glob("*.bsa"):
        shutil.copyfile(b, mod / b.name)
    fake_plugin(mod / "Combat.esp", ["Skyrim.esm"], records=0)
    for target in (mod, zip_dir(mod, tmp_path / "Combat NX.zip")):
        d = detect(target)
        assert (d.kind, d.action) == ("switch-mod", "add"), d.to_dict()
        assert d.evidence["animations"]["switch"] > 0 and d.evidence["animations"]["pc"] == 0
        assert d.evidence["bsas"] == ["Combat - Animations.bsa", "Combat - Meshes.bsa"]
    assert detect(COMBAT).kind == "switch-mod"     # read in place, never written


def test_intake_fomod_and_rar(tmp_path, monkeypatch):
    import skynx.intake as I
    monkeypatch.setattr(I, "rar_tool", lambda: None)      # no 7-Zip / tar.exe on this PC
    z = tmp_path / "Fancy Mod-1234-1-0.zip"
    with zipfile.ZipFile(z, "w") as zf:
        zf.writestr("Fancy Mod/fomod/ModuleConfig.xml", "<config/>")
        zf.writestr("Fancy Mod/fomod/info.xml", "<fomod/>")
        zf.writestr("Fancy Mod/00 Core/Fancy.esp", "x")
    d = detect(z)
    assert (d.kind, d.action) == ("fomod", "fomod")
    assert d.evidence["fomod_root"] == "Fancy Mod"
    r = tmp_path / "pack.rar"
    r.write_bytes(b"Rar!\x1a\x07\x00")
    d = detect(r)
    assert d.kind == "unknown" and not d.supported and ".rar" in d.summary[0]
    with pytest.raises(IntakeError):
        L.import_pack(r, tmp_path / "Lib")


def test_intake_modpack_zip(tmp_path):
    pack = mini_pack(tmp_path / "Mini")
    d = detect(zip_dir(pack, tmp_path / "Mini.zip", "Mini Pack/"))
    assert (d.kind, d.action) == ("modpack", "library")
    assert d.evidence["plugins"] == ["Tiny.esp"] and d.evidence["edition"] == "AE"
    d2 = detect(zip_dir(pack, tmp_path / "Atmo.zip", "SD/atmosphere/contents/"))
    assert d2.kind == "modpack" and "atmosphere" in d2.evidence["layout"]


# ---------------------------------------------------------------- library
def test_import_pack_layouts_and_no_overwrite(tmp_path):
    pack = mini_pack(tmp_path / "Mini")
    lib = tmp_path / "Library"
    atmo = zip_dir(pack, tmp_path / "Mini Pack-20261020T151515Z-001.zip", "Mini Pack/atmosphere/contents/")
    with zipfile.ZipFile(atmo, "a") as z:
        z.writestr("Mini Pack/readme.txt", "read me")
    e = L.import_pack(atmo, lib)
    assert e["name"] == "Mini Pack" and not e["external"]
    p = Pack.open(Path(e["path"]))
    assert p.mode == "AE" and "tiny.esp" in p.plugins and "Tiny.esp" in p.list_entries
    assert (Path(e["path"]) / "01000A10041EA000").is_dir()          # moved to the top
    assert (Path(e["path"]) / "extras/Mini Pack/readme.txt").exists()
    # just the two title folders, same name: never overwrites
    e2 = L.import_pack(zip_dir(pack, tmp_path / "Mini Pack.zip"), lib)
    assert e2["name"] == "Mini Pack (2)"
    assert Pack.open(Path(e2["path"])).plugins.keys() == p.plugins.keys()
    # a folder is registered in place
    e3 = L.import_pack(pack, lib)
    assert e3["external"] and e3["path"] == str(pack)
    assert sorted(x.name for x in (lib / "Packs").iterdir()) == ["Mini Pack", "Mini Pack (2)"]
    # zip-slip
    evil = tmp_path / "evil.zip"
    with zipfile.ZipFile(evil, "w") as z:
        z.writestr("01000A10041EA000/romfs/Skyrim.ini", "[Archive]\n")
        z.writestr("../../outside.txt", "nope")
    with pytest.raises(IntakeError):
        L.import_pack(evil, lib)
    assert not (tmp_path / "outside.txt").exists()
    assert sorted(x.name for x in (lib / "Packs").iterdir()) == ["Mini Pack", "Mini Pack (2)"]
    with pytest.raises(L.LibraryError):
        L.import_pack(zip_dir(tmp_path / "Mini/01000A10041EA000/romfs/Data", tmp_path / "m.zip"), lib)


def test_list_library_health_cache(tmp_path, monkeypatch):
    lib = tmp_path / "Library"
    L.import_pack(zip_dir(mini_pack(tmp_path / "Mini"), tmp_path / "Mini.zip"), lib)
    ext = mini_pack(tmp_path / "Elsewhere" / "My Pack")
    L.add_external(lib, ext)
    mod = tmp_path / "loose.zip"
    with zipfile.ZipFile(mod, "w") as z:
        z.writestr("Loose.esp", "x")
    L.import_mod(mod, lib)
    rows = L.list_library(lib)
    assert [(r["kind"], r["name"]) for r in rows] == [("pack", "Mini"), ("pack", "My Pack"),
                                                       ("mod", "loose.zip")]
    mine = rows[1]
    assert mine["external"] and mine["path"] == str(ext) and mine["size"] > 0
    assert mine["health"]["mode"] == "AE" and set(mine["health"]["severity"]) == \
        {"critico", "aviso", "ahorro", "info"}
    assert rows[2]["health"]["kind"] == "switch-mod"
    assert (lib / ".library.json").exists()
    calls = []
    import skynx.audit as A
    real = A.run_audit
    monkeypatch.setattr(A, "run_audit", lambda *a, **k: calls.append(1) or real(*a, **k))
    L.list_library(lib)
    assert calls == []                       # cached by path + mtime
    data = ext / "01000A10041EA000/romfs/Data"
    fake_plugin(data / "Stray.esp", ["Skyrim.esm"])
    row = next(r for r in L.list_library(lib) if r["name"] == "My Pack")
    assert calls == [1]
    assert row["health"]["severity"]["aviso"] >= 1          # Stray.esp isn't in the list
    shutil.rmtree(ext)
    assert next(r for r in L.list_library(lib) if r["name"] == "My Pack")["missing"]


# ---------------------------------------------------------------- mod units
def test_units_group_koka_short_names(tmp_path):
    """Ashiro's pack, extracted: Koka-style BSA names listed in the inis."""
    if not (MIRROR / ASHIRO).exists():
        pytest.skip("no mirror")
    src = Pack.open(MIRROR / ASHIRO)
    root = create_project(tmp_path / "ashiro", "AE", INIS, "all")
    romfs = root / "01000A10041EA000/romfs"
    for ini in src.ini_paths:
        (romfs / ini.name).write_bytes(ini.read_bytes())
    data = romfs / "Data"
    plugins = {
        "Unofficial Skyrim Special Edition Patch.esp": ["USSEP.bsa", "USSEPA.bsa", "USSEPT.bsa", "USSEPV.bsa"],
        "Odin - Skyrim Magic Overhaul.esp": ["Odn.bsa", "OdnMs.bsa", "OdnTs.bsa"],
        "Odin - Vokrii Compatibility Patch.esp": [],
        "Vokrii - Minimalistic Perks of Skyrim.esp": ["Vkr.bsa", "VkrMs.bsa", "VkrTs.bsa"],
        "Summermyst - Enchantments of Skyrim.esp": ["Smyst.bsa", "SmystMs.bsa", "SmystTs.bsa"],
        "PyP_Legendary.esp": ["PyP.bsa"],
        "Andromeda - Unique Standing Stones of Skyrim.esp": ["And.bsa", "AndMs.bsa", "AndTs.bsa"],
        "Morningstar - Minimalistic Races of Skyrim.esp": ["Morn.bsa"],
        "Sacrilege - Minimalistic Vampires of Skyrim.esp": ["Scrlg.bsa", "ScrlgMs.bsa", "ScrlgTs.bsa"],
        "Humble Quick Start.esp": ["Humble Quick Start.bsa"],
    }
    for p, bsas in plugins.items():
        fake_plugin(data / p, ["Skyrim.esm"])
        for b in bsas:
            (data / b).write_bytes(EMPTY_BSA)
    for b in ("DemoniacMs.bsa", "DemoniacTs.bsa", "Orphan.bsa"):
        (data / b).write_bytes(EMPTY_BSA)
    units = {u.id: u for u in list_pack_mods(Pack.open(root))}
    for p, bsas in plugins.items():
        assert units[f"plugin:{p}"].bsas == sorted(bsas), p
    ussep = units["plugin:Unofficial Skyrim Special Edition Patch.esp"]
    assert ussep.ini == {"sResourceArchiveList": ["USSEP.bsa", "USSEPA.bsa"],
                         "sArchiveToLoadInMemoryList": ["USSEPA.bsa"],
                         "sResourceArchiveList2": ["USSEPT.bsa", "USSEPV.bsa"]}
    assert ussep.grouped_by["USSEPT.bsa"] == "ini-stem"
    demo = units["bsa:Demoniac"]
    assert demo.bsas == ["DemoniacMs.bsa", "DemoniacTs.bsa"] and demo.has("bsa-only")
    assert units["bsa:Orphan.bsa"].has("not-loaded")
    assert owner_for_bsa("skyui.bsa", ["SpaghettiSkyrimFullAIO.esp", "SkyHUD.esp"])[0] is None


# ---------------------------------------------------------------- transfers
@need_mirror
def test_transfer_from_avner_into_new_project(tmp_path):
    src = Pack.open(avner_as_downloaded(tmp_path))
    dst_root = create_project(tmp_path / "Mine", "AE", INIS, "all")
    dst = Pack.open(dst_root)
    before = state(dst_root)
    units = {u.id: u for u in list_pack_mods(src)}
    ryn = units["plugin:Ryn_s Standing Stones.esp"]
    assert ryn.list_name == "Ryn's Standing Stones.esp" and ryn.has("drive-name")
    assert ryn.target == {"Ryn_s Standing Stones.esp": "Ryn's Standing Stones.esp",
                          "Ryn_s Standing Stones.bsa": "Ryn's Standing Stones.bsa"}
    ashiro = units["plugin:Ashiro_s Animation Pack.esp"]      # no FaceGen inside: keeps its name
    assert ashiro.has("drive-maybe") and ashiro.target["Ashiro_s Animation Pack.esp"] == ashiro.name
    assert units["plugin:EnaiRim_NR.esp"].bsas == ["EnaiRim_NR - Misc.bsa", "EnaiRim_NR.bsa"]
    assert units["bsa:Light.bsa"].has("bsa-only")
    ids = ["plugin:Ryn_s Standing Stones.esp", "plugin:ECCO - Imperious Patch.esp",
           "plugin:Staves - Mysticism Consistency.esp", "plugin:EnaiRim_NR.esp"]
    plan = plan_transfer(src, dst, ids, list(units.values()))
    brought = {b["unit"].id: b for b in plan.units}
    for m in ("Extended Character Creation Options.esp", "Imperious - Races of Skyrim.esp"):
        assert brought[f"plugin:{m}"]["reason"] == "master"
        assert brought[f"plugin:{m}"]["needed_by"] == ["ECCO - Imperious Patch.esp"]
    assert brought["plugin:MysticismMagic.esp"]["reason"] == "master"
    assert not plan.missing_masters and plan.ok
    assert plan.budget["ccc_before"] == 2197 and plan.budget["ccc_limit"] == 4096
    assert plan.budget["ccc_after"] == len(plan.list_after) > 2197
    assert plan.budget["tex_added"] > 0
    rep = apply_transfer(plan)

    dst = Pack.open(dst_root)
    data = dst.data_dir
    for f in ("Ryn's Standing Stones.esp", "Ryn's Standing Stones.bsa", "ECCO - Imperious Patch.esp",
              "MysticismMagic.esp", "MysticismMagic.bsa", "EnaiRim_NR - Misc.bsa"):
        assert (data / f).is_file() and not (data / f).is_symlink(), f
    assert not (data / "Ryn_s Standing Stones.esp").exists()
    real = (MIRROR / AVNER / AVNER / "01000A10041EA000/romfs/Data/Ryn_s Standing Stones.bsa").read_bytes()
    assert (data / "Ryn's Standing Stones.bsa").read_bytes() == real
    entries = dst.list_entries
    assert entries[:80] == parse_ccc(before["01000A10041EB009/romfs/Skyrim_aoc.ccc"]).entries
    new = entries[80:]
    assert set(new) == {"Ryn's Standing Stones.esp", "Extended Character Creation Options.esp",
                        "Imperious - Races of Skyrim.esp", "MysticismMagic.esp",
                        "Staves - Mysticism Consistency.esp", "EnaiRim_NR.esp", "ECCO - Imperious Patch.esp"}
    # masters first; otherwise the source's order (Avner had Staves before its master)
    assert new.index("MysticismMagic.esp") < new.index("Staves - Mysticism Consistency.esp")
    assert new.index("Imperious - Races of Skyrim.esp") < new.index("ECCO - Imperious Patch.esp")
    assert new.index("Ryn's Standing Stones.esp") < new.index("EnaiRim_NR.esp")
    old_raw = before["01000A10041EB009/romfs/Skyrim_aoc.ccc"]
    assert dst.ccc_path.read_bytes().startswith(old_raw)              # existing lines untouched
    sky = read_ini(dst.base_romfs / "Skyrim.ini")
    assert sky.archive_list("sResourceArchiveList")[-1] == "EnaiRim_NR - Misc.bsa"
    mods = load_mods(dst)
    rec = mods["Ryn's Standing Stones"]
    assert rec["from_pack"] == AVNER and rec["plugins"] == ["Ryn's Standing Stones.esp"]
    assert rec["name_fixed"]["Ryn's Standing Stones.esp"] == "Ryn_s Standing Stones.esp"
    assert mods["MysticismMagic"]["reason"] == "master"
    assert mods["EnaiRim_NR"]["ini"] == [{"key": "sResourceArchiveList", "bsa": "EnaiRim_NR - Misc.bsa"}]
    assert list_history(dst_root)[0]["title"] == "Bring 7 mods from " + AVNER

    # the same again: everything is already there
    again = plan_transfer(Pack.open(src.root), Pack.open(dst_root), ids)
    assert not again.units and len(again.skipped) == 4 and not again.ok
    undo(dst_root, rep["history"])
    assert state(dst_root) == before


@need_mirror
def test_transfer_archive_units_fill_both_inis(tmp_path):
    """Ashiro ships its mods as .7z inside Data; textures go to list 2 in both inis."""
    src = Pack.open(MIRROR / ASHIRO)
    dst_root = create_project(tmp_path / "Mine", "AE", INIS, "all")
    before = state(dst_root)
    plan = plan_transfer(src, Pack.open(dst_root), ["archive:Andromeda 1.1.2 NX.7z"])
    assert plan.work and plan.ok
    rep = apply_transfer(plan)
    assert plan.work is None                                      # extracted copy cleaned up
    dst = Pack.open(dst_root)
    assert "Andromeda - Unique Standing Stones of Skyrim.esp" in dst.list_entries
    sky, en = (read_ini(dst.base_romfs / n) for n in ("Skyrim.ini", "Skyrim_en.ini"))
    assert sky.archive_list("sResourceArchiveList")[-2:] == ["And.bsa", "AndMs.bsa"]
    assert sky.archive_list("sResourceArchiveList2")[-1] == "AndTs.bsa"
    assert en.archive_list("sResourceArchiveList2")[-1] == "AndTs.bsa"
    assert en.get("Archive", "sResourceArchiveList") is None
    rec = load_mods(dst)["Andromeda 1.1.2 NX"]
    assert sorted(rec["bsas"]) == ["And.bsa", "AndMs.bsa", "AndTs.bsa"]
    assert {"key": "sResourceArchiveList2", "bsa": "AndTs.bsa"} in rec["ini"]
    undo(dst_root, rep["history"])
    assert state(dst_root) == before


@need_mirror
def test_transfer_refusals_and_limits(tmp_path):
    src = Pack.open(MIRROR / AVNER)
    se_root = create_project(tmp_path / "SE", "SE", INIS, "all")
    plan = plan_transfer(src, Pack.open(se_root), ["plugin:VendorGoldScaling.esl", "bsa:Light.bsa"])
    assert [r["id"] for r in plan.refused] == ["plugin:VendorGoldScaling.esl"]
    assert "ESL" in plan.refused[0]["reason"][0] and "ESL" in plan.refused[0]["reason"][1]
    assert [b["unit"].id for b in plan.units] == ["bsa:Light.bsa"]
    # the 1024-character ini limit stops everything before anything is written
    ae_root = create_project(tmp_path / "AE", "AE", INIS, "all")
    ini = ae_root / "01000A10041EA000/romfs/Skyrim.ini"
    raw = ini.read_bytes()
    cur = parse_ini(raw).archive_list("sResourceArchiveList")
    filler = [f"Filler{i:03d}.bsa" for i in range(80)]
    while len(", ".join(cur + filler)) > 1020:
        filler.pop()
    ini.write_bytes(set_archive_list(raw, "sResourceArchiveList", cur + filler))
    before = state(ae_root)
    with pytest.raises(TransferError) as e:
        plan_transfer(src, Pack.open(ae_root), ["plugin:EnaiRim_NR.esp"])
    assert "1024" in e.value.en and "1024" in e.value.es
    assert state(ae_root) == before and not list_history(ae_root)
    with pytest.raises(TransferError):
        plan_transfer(src, Pack.open(ae_root), ["plugin:Nope.esp"])
