"""Behavior generation (behaviors.py): sources kept on conversion, Nemesis'
work folder, and its output made Switch-native and added as one mod.

Nemesis itself is a Windows program the person drives by hand, so these
tests write what it writes (PatchLog with "Behavior generation complete",
64-bit PC hkx under meshes, the animation data txt) into the work folder.
"""
import json
import sys
from dataclasses import replace
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT), str(ROOT / "tests")]

from skynx import behaviors as BH  # noqa: E402
from skynx import havok as HV  # noqa: E402
from skynx.tools import locate  # noqa: E402

FAKE = ROOT / "tests" / "fake_tools"
_PC = ROOT / "tests" / "fixtures" / "havok" / "staggerbehavior_pc.hkx"
if not _PC.exists():   # the game's own behavior file: not in the public repository
    pytest.skip("needs tests/fixtures/havok (see tests/README.md)", allow_module_level=True)
PC = _PC.read_bytes()
ANIMS = ("meshes", "actors", "character", "animations", "FlowerTest")
STAGED = tuple(x.lower() for x in ANIMS)      # conversion stages paths in lower case


def pc_anim() -> bytes:
    """A 64-bit PC SE animation header (the byte patch converts these)."""
    head = bytearray(b"\x57\xe0\xe0\x57\x10\xc0\xc0\x10" + bytes(56))
    head[12] = 8
    head[16:20] = bytes([8, 1, 0, 1])
    head[40:54] = b"hk_2010.2.0-r1"
    return bytes(head) + b"hkaSplineCompressedAnimation" + bytes(64)


def fnis_mod(tmp_path, nemesis_patch=True):
    tc = pytest.importorskip("test_convert")
    m = tmp_path / "Flower Test"
    a = m.joinpath(*ANIMS)
    a.mkdir(parents=True)
    (m / "FlowerTest.esp").write_bytes(tc.plugin_bytes(["Skyrim.esm"]))
    (a / "FNIS_FlowerTest_List.txt").write_text("b -a,LI idle_a idle_a.hkx\n", encoding="utf-8")
    (a / "idle_a.hkx").write_bytes(pc_anim())
    other = m / "meshes" / "actors" / "character" / "animations" / "elsewhere"
    other.mkdir(parents=True)
    (other / "unrelated.hkx").write_bytes(pc_anim())
    if nemesis_patch:
        p = m / "Nemesis_Engine" / "mod" / "fltt"
        p.mkdir(parents=True)
        (p / "info.ini").write_text("name=Flower Test\n", encoding="utf-8")
    return tc, m


def tools_with_nemesis(tmp_path):
    eng = tmp_path / "NemesisDL" / "Nemesis_Engine"
    eng.mkdir(parents=True)
    (eng / BH.NEMESIS_EXE).write_bytes(b"MZ")
    (eng / "nemesis.ini").write_text("SkyrimDataDirectory=C:\\old\\\nlanguage=english\n", encoding="utf-8")
    (eng / "PatchLog.txt").write_text("old run", encoding="utf-8")
    (eng.parent / "scripts").mkdir()
    (eng.parent / "scripts" / "FNIS.pex").write_bytes(b"pex")
    return replace(locate(FAKE), nemesis=eng)


def project_with(tmp_path, tc, mod):
    from skynx.builder import create_project
    from skynx.converter import analyze, convert
    from skynx.pack import Pack
    pack = Pack.open(create_project(tmp_path / "pack", "AE", tc.BASE_INIS, "none"))
    an = analyze(pack, mod)
    try:
        res = convert(pack, an, {"sdk": False}, locate(FAKE))
    finally:
        an.cleanup()
    return Pack.open(pack.root), res


def fake_nemesis_run(pack, done=True):
    data = BH.work_dir(pack) / "Data"
    beh = data / "meshes" / "actors" / "character" / "behaviors"
    beh.mkdir(parents=True, exist_ok=True)
    (beh / "0_master.hkx").write_bytes(PC)
    (beh / "FNIS_FlowerTest_Behavior.hkx").write_bytes(PC)
    (data / "meshes" / "animationdatasinglefile.txt").write_text("generated\n", encoding="utf-8")
    eng = data / "Nemesis_Engine"
    (eng / "cache").mkdir(exist_ok=True)
    (eng / "cache" / "nemesis_defaultmale.xml").write_text("<x/>", encoding="utf-8")
    (data / "nemesis_engine_cache.xml").write_text("<x/>", encoding="utf-8")
    log = "Patching...\n" + (BH.DONE_MARK + "\n" if done else "")
    (eng / "PatchLog.txt").write_text(log, encoding="utf-8")


# ------------------------------------------------------------------ capture
def test_capture_keeps_what_generation_needs(tmp_path):
    _tc, mod = fnis_mod(tmp_path, nemesis_patch=False)
    dest = tmp_path / "src"
    n = BH.capture(mod, None, dest)
    got = sorted(p.relative_to(dest).as_posix() for p in dest.rglob("*") if p.is_file())
    base = "/".join(ANIMS)
    assert got == [f"{base}/FNIS_FlowerTest_List.txt", f"{base}/idle_a.hkx"] and n == 2
    # with a Nemesis patch every animation goes, and the patch too
    _tc, mod2 = fnis_mod(tmp_path / "b")
    dest2 = tmp_path / "src2"
    BH.capture(mod2, mod2 / "Nemesis_Engine", dest2)
    assert (dest2 / "Nemesis_Engine" / "mod" / "fltt" / "info.ini").is_file()
    assert (dest2 / "meshes" / "actors" / "character" / "animations" / "elsewhere" / "unrelated.hkx").is_file()
    (tmp_path / "empty").mkdir()
    assert BH.capture(tmp_path / "empty", None, tmp_path / "none") == 0


def test_conversion_keeps_sources_and_status(tmp_path):
    tc, mod = fnis_mod(tmp_path)
    pack, _res = project_with(tmp_path, tc, mod)
    mods = BH.mods_with_sources(pack)
    assert len(mods) == 1 and mods[0]["lists"] == 1 and mods[0]["nemesis"]
    src = mods[0]["dir"]
    assert (src.joinpath(*STAGED) / "idle_a.hkx").read_bytes() == pc_anim()       # the PC original, not converted
    st = BH.status(pack, locate(FAKE))
    assert st["needed"] and st["state"] == "never" and not st["nemesis"] and st["havok"]
    assert "dir" not in st["mods"][0]
    # Nemesis' files don't end up in the mod's BSA or loose in Data
    assert not any("nemesis_engine" in str(p).lower() for p in pack.data_dir.rglob("*"))


def test_zip_round_trip(tmp_path):
    from skynx.pack import Pack
    from skynx.builder import create_project
    tc = pytest.importorskip("test_convert")
    _tc, mod = fnis_mod(tmp_path)
    src = tmp_path / "src"
    BH.capture(mod, mod / "Nemesis_Engine", src)
    BH.make_zip(src, tmp_path / "behavior-sources.zip")
    pack = Pack.open(create_project(tmp_path / "pack", "AE", tc.BASE_INIS, "none"))
    assert BH.store_zip(pack, "Flower Test", tmp_path / "behavior-sources.zip")
    a = sorted(p.relative_to(src).as_posix() for p in src.rglob("*") if p.is_file())
    d = BH.sources_dir(pack, "Flower Test")
    b = sorted(p.relative_to(d).as_posix() for p in d.rglob("*") if p.is_file())
    assert a == b and len(a) == 4
    assert not BH.store_zip(pack, "x", tmp_path / "missing.zip")
    assert not BH.store(pack, "x", tmp_path / "nothing")


# ------------------------------------------------------------------ the work folder
def test_prepare_makes_the_work_folder(tmp_path):
    tc, mod = fnis_mod(tmp_path)
    pack, _ = project_with(tmp_path, tc, mod)
    tools = tools_with_nemesis(tmp_path)
    with pytest.raises(BH.BehaviorError):
        BH.prepare(pack, locate(FAKE))                       # no Nemesis
    info = BH.prepare(pack, tools)
    ws = Path(info["work"])
    data = ws / "Data"
    assert (ws / "SkyrimSE.exe").read_bytes() == b""
    ini = (data / "Nemesis_Engine" / "nemesis.ini").read_text(encoding="utf-8")
    assert ini.splitlines()[0] == f"SkyrimDataDirectory={data}\\" and "C:\\old" not in ini and "language=english" in ini
    assert not (data / "Nemesis_Engine" / "PatchLog.txt").exists()          # an old log would read as done
    assert (data / "scripts" / "FNIS.pex").is_file()                       # the rest of Nemesis' download
    assert (data.joinpath(*STAGED) / "fnis_flowertest_list.txt").is_file()
    assert (data / "Nemesis_Engine" / "mod" / "fltt" / "info.ini").is_file()
    assert info["patches"] == ["fltt"] and info["mods"] == ["Flower Test"]
    assert Path(info["exe"]).name == BH.NEMESIS_EXE
    assert (tools.nemesis / "nemesis.ini").read_text(encoding="utf-8").startswith("SkyrimDataDirectory=C:\\old")
    assert BH.nemesis_log(pack) == {"exists": False, "done": False, "errors": []}
    assert BH.changed_files(pack) == []


def test_collect_adds_switch_behaviors_as_a_mod(tmp_path):
    from skynx.builder import load_mods, remove_mod
    from skynx.bsa import read_bsa
    from skynx.pack import Pack
    tc, mod = fnis_mod(tmp_path)
    pack, _ = project_with(tmp_path, tc, mod)
    tools = tools_with_nemesis(tmp_path)
    BH.prepare(pack, tools)
    fake_nemesis_run(pack, done=False)
    with pytest.raises(BH.BehaviorError) as e:
        BH.collect(pack, tools)
    assert "Behavior generation complete" in e.value.en
    fake_nemesis_run(pack)
    assert BH.nemesis_log(pack)["done"]
    changed = BH.changed_files(pack)
    assert "meshes/actors/character/behaviors/0_master.hkx" in changed
    assert not any(c.rsplit("/", 1)[-1].startswith("nemesis_") for c in changed)
    out = BH.collect(pack, tools)
    assert out["hkx"] == 2 and out["files"] == 3 and out["mod_id"] == BH.GEN_ID
    pack = Pack.open(pack.root)
    assert BH.GEN_ID in load_mods(pack)
    arc = read_bsa(pack.data_dir / BH.GEN_BSA)
    with arc.path.open("rb") as f:
        files = {e.path: arc.read_file(e, f) for e in arc.entries}
    master = files["meshes\\actors\\character\\behaviors\\0_master.hkx"]
    assert HV.is_switch(master) and master[20:] == PC[20:]
    assert files["meshes\\animationdatasinglefile.txt"] == b"generated\n"
    def per_ini(pk):
        return [sum(ini.archive_list(k).count(BH.GEN_BSA) for k in ("sResourceArchiveList", "sResourceArchiveList2"))
                for ini in pk.inis if ini.archive_list("sResourceArchiveList")]
    assert per_ini(pack) and set(per_ini(pack)) == {1}
    st = BH.status(pack, tools)
    assert st["state"] == "ok" and st["files"] == 3
    assert not BH.work_dir(pack).exists()                                  # its copy of Nemesis is gone
    assert BH.DONE_MARK in Path(pack.root).joinpath(*BH.LOG).read_text(encoding="utf-8")
    # a second run replaces the set instead of adding another
    BH.prepare(pack, tools)
    fake_nemesis_run(pack)
    BH.collect(pack, tools)
    pack = Pack.open(pack.root)
    assert list(load_mods(pack)).count(BH.GEN_ID) == 1
    assert set(per_ini(pack)) == {1}
    # the inputs change: stale
    lst = BH.sources_dir(pack, "Flower Test").joinpath(*STAGED) / "fnis_flowertest_list.txt"
    lst.write_text(lst.read_text(encoding="utf-8") + "b -a,LI idle_b idle_b.hkx\n", encoding="utf-8")
    assert BH.status(pack, tools)["state"] == "stale"
    # the generated set alone, with its source mod gone: stale too
    remove_mod(pack, "Flower Test")
    pack = Pack.open(pack.root)
    assert BH.mods_with_sources(pack) == [] and BH.status(pack, tools)["state"] == "stale"


def test_collect_needs_the_havok_tools(tmp_path):
    from skynx.tools import Toolset
    tc, mod = fnis_mod(tmp_path)
    pack, _ = project_with(tmp_path, tc, mod)
    tools = tools_with_nemesis(tmp_path)
    BH.prepare(pack, tools)
    fake_nemesis_run(pack)
    with pytest.raises(BH.BehaviorError) as e:
        BH.collect(pack, Toolset(None, nemesis=tools.nemesis))
    assert "HavokBehaviorPostProcess" in e.value.en and "hkxc" in e.value.es


def test_sources_travel_with_the_library_copy(tmp_path):
    from skynx.builder import add_mod, create_project
    from skynx.converter import analyze, convert
    from skynx.pack import Pack
    tc, mod = fnis_mod(tmp_path)
    pack = Pack.open(create_project(tmp_path / "pack", "AE", tc.BASE_INIS, "none"))
    an = analyze(pack, mod)
    try:
        convert(pack, an, {"sdk": False, "keep_to": str(tmp_path / "lib")}, locate(FAKE))
    finally:
        an.cleanup()
    zips = list((tmp_path / "lib").rglob("behavior-sources.zip"))
    assert len(zips) == 1
    other = Pack.open(create_project(tmp_path / "other", "AE", tc.BASE_INIS, "none"))
    rep = add_mod(other, zips[0].parent)
    other = Pack.open(other.root)
    mods = BH.mods_with_sources(other)
    assert [m["id"] for m in mods] == [rep.mod_id] and mods[0]["nemesis"] and mods[0]["lists"] == 1
    assert not list(other.data_dir.rglob("behavior-sources*"))            # not a loose file of the mod
