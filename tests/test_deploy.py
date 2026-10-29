"""Incremental copy to the SD (skynx.deploy) and BSA conflicts (skynx.conflicts)."""
import os
import shutil
import stat
import struct
import sys
import zipfile
import time
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from skynx import deploy as D  # noqa: E402
from skynx.bsa import write_bsa  # noqa: E402
from skynx.builder import create_project  # noqa: E402
from skynx.ccc import render  # noqa: E402
from skynx.conflicts import find_conflicts, load_order_bsas  # noqa: E402
from skynx.ini import read_ini, set_archive_list  # noqa: E402
from skynx.pack import Pack  # noqa: E402

MIRROR = ROOT / "work" / "mirror"
ASHIRO = ROOT / "work" / "ashiro"
BASE = "01000A10041EA000"
AOC = "01000A10041EB009"


# ---------------------------------------------------------------- helpers
def _w(p: Path, data: bytes | str, mtime: float | None = None):
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_bytes(data.encode() if isinstance(data, str) else data)
    if mtime is not None:
        os.utime(p, (mtime, mtime))
    return p


def _pack(tmp_path) -> Path:
    root = tmp_path / "pack"
    data = root / BASE / "romfs" / "Data"
    _w(root / BASE / "romfs" / "Skyrim.ini", "[Archive]\nsResourceArchiveList=Skyrim - Misc.bsa\n")
    _w(data / "Mod.esp", b"TES4" + b"\0" * 40)
    _w(data / "Mod.bsa", os.urandom(3000))
    _w(data / "Textures" / "Big" / "a.dds", os.urandom(5000))
    _w(data / "Textures" / "Big" / "b.dds", os.urandom(5000))
    _w(data / "meshes" / "x.nif", os.urandom(700))
    _w(data / "leftover.skynx-tmp", b"temp, never copied")
    _w(root / AOC / "romfs" / "Skyrim_aoc.ccc", "Mod.esp\r\n")
    _w(root / ".skynx" / "project.json", "{}")
    return root


def _sd(tmp_path) -> Path:
    sd = tmp_path / "sd"
    (sd / "atmosphere" / "contents").mkdir(parents=True)
    return sd


def _snap(sd: Path) -> dict:
    """Every file and folder under contents with content, mtime and write bit."""
    base = sd / "atmosphere" / "contents"
    out = {}
    for dirpath, dirnames, filenames in os.walk(base):
        for d in dirnames:
            out[(Path(dirpath) / d).relative_to(base).as_posix() + "/"] = None
        for f in filenames:
            p = Path(dirpath) / f
            st = p.stat()
            out[p.relative_to(base).as_posix()] = (p.read_bytes(), st.st_mtime_ns,
                                                   bool(st.st_mode & stat.S_IWRITE))
    return out


def _files(sd: Path) -> set[str]:
    return {k for k, v in _snap(sd).items() if v is not None}


# ---------------------------------------------------------------- sync
def test_first_copy_then_nothing(tmp_path):
    pack, sd = _pack(tmp_path), _sd(tmp_path)
    plan = D.plan_sync(pack, sd)
    assert len(plan.to_copy) == 7 and not plan.to_delete and plan.unchanged == 0
    assert plan.to_dict()["copy_bytes"] == plan.copy_bytes > 13000
    out = D.deploy(pack, sd)
    assert out["mode"] == "sync" and out["copied"] == 7 and out["deleted"] == 0
    assert out["backup"] is None                      # nothing was overwritten
    assert out["files"] == 7 and out["bytes"] == out["bytes_copied"]
    assert {"unchanged", "seconds", "target"} <= set(out)
    names = _files(sd)
    assert f"{BASE}/romfs/Data/Textures/Big/a.dds" in names
    assert not any("skynx" in n for n in names)       # no temp files, no .skynx
    again = D.deploy(pack, sd)
    assert again["copied"] == 0 and again["deleted"] == 0 and again["unchanged"] == 7
    assert again["backup"] is None
    assert D.plan_sync(pack, sd).empty


def test_change_add_delete_and_partial_backup(tmp_path):
    pack, sd = _pack(tmp_path), _sd(tmp_path)
    D.deploy(pack, sd)
    data = pack / BASE / "romfs" / "Data"
    old_x = (sd / "atmosphere/contents" / BASE / "romfs/Data/meshes/x.nif").read_bytes()
    _w(data / "meshes" / "x.nif", os.urandom(900))           # changed
    _w(data / "meshes" / "new.nif", os.urandom(100))         # added
    (data / "Textures" / "Big" / "b.dds").unlink()           # deleted
    plan = D.plan_sync(pack, sd)
    assert sorted(c.rel.rsplit("/", 1)[1] for c in plan.to_copy) == ["new.nif", "x.nif"]
    assert [r for r, _ in plan.to_delete] == [f"{BASE}/romfs/Data/Textures/Big/b.dds"]
    out = D.deploy(pack, sd)
    assert (out["copied"], out["deleted"], out["unchanged"]) == (2, 1, 5)
    with zipfile.ZipFile(out["backup"]) as z:
        assert sorted(z.namelist()) == [f"{BASE}/romfs/Data/Textures/Big/b.dds",
                                        f"{BASE}/romfs/Data/meshes/x.nif"]
        assert z.read(f"{BASE}/romfs/Data/meshes/x.nif") == old_x
    assert Path(out["backup"]).parent == pack / ".skynx" / "sd-backups"
    c = sd / "atmosphere/contents" / BASE / "romfs/Data"
    assert (c / "meshes/x.nif").read_bytes() == (data / "meshes/x.nif").read_bytes()
    assert not (c / "Textures/Big/b.dds").exists()


def test_same_size_other_date_uses_hash(tmp_path):
    pack, sd = _pack(tmp_path), _sd(tmp_path)
    D.deploy(pack, sd)
    data = pack / BASE / "romfs" / "Data"
    sdd = sd / "atmosphere/contents" / BASE / "romfs/Data"
    os.utime(sdd / "Mod.bsa", (1e9, 1e9))                     # restored from a backup
    _w(data / "meshes" / "x.nif", os.urandom(700), 2e9)       # same size, new bytes
    plan = D.plan_sync(pack, sd)
    assert [c.rel.rsplit("/", 1)[1] for c in plan.to_copy] == ["x.nif"]
    assert plan.hashed == 2
    D.deploy(pack, sd)
    assert abs((sdd / "Mod.bsa").stat().st_mtime - (data / "Mod.bsa").stat().st_mtime) <= 2
    assert D.plan_sync(pack, sd).hashed == 0                  # dates aligned, no rehash


def test_empty_folders_are_removed(tmp_path):
    pack, sd = _pack(tmp_path), _sd(tmp_path)
    D.deploy(pack, sd)
    shutil.rmtree(pack / BASE / "romfs" / "Data" / "meshes")
    D.deploy(pack, sd)
    assert not (sd / "atmosphere/contents" / BASE / "romfs/Data/meshes").exists()
    assert (sd / "atmosphere/contents" / BASE / "romfs/Data").is_dir()


def test_case_only_renames(tmp_path):
    pack, sd = _pack(tmp_path), _sd(tmp_path)
    D.deploy(pack, sd)
    data = pack / BASE / "romfs" / "Data"
    os.rename(data / "Mod.esp", data / "MOD.esp")                     # file, same bytes
    os.rename(data / "Textures", data / "textures")                    # folder
    os.rename(data / "textures" / "Big", data / "textures" / "BIG")    # nested folder
    os.rename(data / "meshes" / "x.nif", data / "meshes" / "X.nif")    # file, new bytes
    _w(data / "meshes" / "X.nif", os.urandom(800))
    plan = D.plan_sync(pack, sd)
    assert len(plan.dir_renames) == 2 and len(plan.renames) == 1
    out = D.deploy(pack, sd)
    assert out["copied"] == 1 and out["deleted"] == 0 and out["renamed"] == 3
    with zipfile.ZipFile(out["backup"]) as z:
        assert z.namelist() == [f"{BASE}/romfs/Data/meshes/x.nif"]
    want = {f"{BASE}/romfs/Data/MOD.esp", f"{BASE}/romfs/Data/Mod.bsa",
            f"{BASE}/romfs/Data/textures/BIG/a.dds", f"{BASE}/romfs/Data/textures/BIG/b.dds",
            f"{BASE}/romfs/Data/meshes/X.nif", f"{BASE}/romfs/Skyrim.ini",
            f"{AOC}/romfs/Skyrim_aoc.ccc"}
    assert _files(sd) == want
    assert D.plan_sync(pack, sd).empty


def test_case_clash_in_pack_is_refused(tmp_path):
    pack, sd = _pack(tmp_path), _sd(tmp_path)
    _w(pack / BASE / "romfs" / "Data" / "mod.bsa", b"other")
    with pytest.raises(D.DeployError) as e:
        D.plan_sync(pack, sd)
    assert "case" in e.value.en and "mayúsculas" in e.value.es


def _older_sd(tmp_path):
    """SD with a previous version: some files to replace, one to delete, a
    read-only one, a case rename, and an unchanged one."""
    pack, sd = _pack(tmp_path), _sd(tmp_path)
    D.deploy(pack, sd)
    c = sd / "atmosphere/contents" / BASE / "romfs/Data"
    _w(c / "meshes" / "x.nif", b"old mesh", 1.5e9)
    _w(c / "Mod.bsa", b"old bsa", 1.5e9)
    _w(c / "gone.esp", b"to be deleted", 1.4e9)
    os.chmod(c / "gone.esp", stat.S_IREAD)
    os.chmod(c / "Mod.bsa", stat.S_IREAD)
    os.rename(c / "Textures", c / "TEXTURES")
    return pack, sd


@pytest.mark.parametrize("where", ["copy", "delete"])
def test_failure_restores_sd_exactly(tmp_path, monkeypatch, where):
    pack, sd = _older_sd(tmp_path)
    _w(pack / BASE / "romfs" / "Data" / "brand" / "new" / "z.nif", b"new")
    before = _snap(sd)
    calls = {"n": 0}
    real = D._copy_file if where == "copy" else D._remove_file

    def boom(*a):
        calls["n"] += 1
        if calls["n"] == (2 if where == "copy" else 1):
            raise OSError("SD pulled out")
        return real(*a)

    monkeypatch.setattr(D, "_copy_file" if where == "copy" else "_remove_file", boom)
    with pytest.raises(D.DeployError) as e:
        D.deploy(pack, sd)
    assert "SD pulled out" in e.value.en and "como estaba" in e.value.es
    assert _snap(sd) == before
    monkeypatch.undo()
    out = D.deploy(pack, sd)                                   # and it works afterwards
    assert out["deleted"] == 1 and D.plan_sync(pack, sd).empty


def test_read_only_files_are_replaced_and_deleted(tmp_path):
    pack, sd = _older_sd(tmp_path)
    out = D.deploy(pack, sd)
    c = sd / "atmosphere/contents" / BASE / "romfs/Data"
    assert not (c / "gone.esp").exists()
    assert (c / "Mod.bsa").read_bytes() == (pack / BASE / "romfs/Data/Mod.bsa").read_bytes()
    assert "Textures" in os.listdir(c)
    with zipfile.ZipFile(out["backup"]) as z:
        assert sorted(n.rsplit("/", 1)[1] for n in z.namelist()) == ["Mod.bsa", "gone.esp",
                                                                     "x.nif"]


def test_overlap_guard(tmp_path):
    sd = _sd(tmp_path)
    inside = sd / "atmosphere" / "contents"
    _w(inside / BASE / "romfs" / "Skyrim.ini", "[General]\n")
    with pytest.raises(D.DeployError) as e:
        D.plan_sync(sd / "atmosphere", sd)
    assert "same SD" in e.value.en and "misma SD" in e.value.es
    with pytest.raises(D.DeployError):
        D.deploy(sd / "atmosphere", sd)
    with pytest.raises(D.DeployError):
        D.deploy(sd / "atmosphere", sd, mode="full")
    # the other way round: the SD folder picked inside the pack
    pack = _pack(tmp_path)
    with pytest.raises(D.DeployError):
        D.deploy(pack, pack / BASE / "romfs")


def test_no_room_on_sd(tmp_path, monkeypatch):
    pack, sd = _pack(tmp_path), _sd(tmp_path)
    monkeypatch.setattr(D, "sd_free_space", lambda _sd: 100 * 2**20)
    before = _snap(sd)
    with pytest.raises(D.DeployError) as e:
        D.deploy(pack, sd)
    assert "room" in e.value.en and "No cabe" in e.value.es
    assert _snap(sd) == before
    with pytest.raises(D.DeployError):
        D.deploy(pack, sd, mode="full")
    monkeypatch.undo()
    assert D.sd_free_space(sd) == shutil.disk_usage(sd).free


def test_full_mode_still_replaces_everything(tmp_path):
    pack, sd = _pack(tmp_path), _sd(tmp_path)
    _w(sd / "atmosphere/contents" / BASE / "romfs/viejo.txt", "lo de antes")
    out = D.deploy(pack, sd, mode="full")
    assert out["mode"] == "full" and out["copied"] == 7 and out["deleted"] == 1
    assert out["files"] == 7 and out["backup"]
    with zipfile.ZipFile(out["backup"]) as z:
        assert z.namelist() == [f"{BASE}/romfs/viejo.txt"]
    assert not (sd / "atmosphere/contents" / BASE / "romfs/viejo.txt").exists()
    assert D.plan_sync(pack, sd).empty      # full copy keeps dates: sync sees no change


# ---------------------------------------------------------------- conflicts
def _plugin(p: Path):
    _w(p, struct.pack("<4sIIIHHHH", b"TES4", 0, 0, 0, 0, 0, 44, 0))


def _bsa(dest: Path, files: dict[str, bytes], src: Path):
    pairs = []
    for i, (arc, data) in enumerate(files.items()):
        f = src / dest.stem / f"{i}.bin"
        _w(f, data)
        pairs.append((arc, f))
    write_bsa(pairs, dest)


def _conflict_project(tmp_path) -> Path:
    root = create_project(tmp_path / "proj", "AE", ROOT / "tests/fixtures/base-inis", "ussep")
    romfs = root / BASE / "romfs"
    data = romfs / "Data"
    src = tmp_path / "src"
    shared = b"S" * 4000
    other = b"O" * 4000                                       # same size, other bytes
    _bsa(data / "IniA.bsa", {"textures\\x\\shared.dds": other, "meshes\\a.nif": b"a" * 50}, src)
    _bsa(data / "IniHidden.bsa", {"textures\\x\\shared.dds": other}, src)
    _bsa(data / "IniC.bsa", {"textures\\x\\shared.dds": other, "meshes\\a.nif": b"c" * 60}, src)
    _bsa(data / "Dead.bsa", {"meshes\\dead\\1.nif": b"1" * 30, "meshes\\dead\\2.nif": b"2" * 30}, src)
    _bsa(data / "ModA.bsa", {"scripts\\s.pex": b"A" * 10}, src)
    _bsa(data / "ModA - Textures.bsa", {"textures\\x\\shared.dds": shared,
                                        "scripts\\s.pex": b"T" * 10}, src)
    _bsa(data / "ModB.bsa", {"textures\\x\\shared.dds": shared, "meshes\\dead\\1.nif": b"x" * 30,
                             "meshes\\dead\\2.nif": b"2" * 30}, src)
    _bsa(data / "Skyrim - Textures0.bsa", {"textures\\x\\shared.dds": other}, src)
    _bsa(data / "Orphan.bsa", {"textures\\x\\shared.dds": other}, src)
    for n in ("Dead.esp", "ModA.esp", "ModB.esp"):
        _plugin(data / n)
    ini = romfs / "Skyrim.ini"
    l1 = read_ini(ini).archive_list("sResourceArchiveList")
    l2 = read_ini(ini).archive_list("sResourceArchiveList2")
    raw = set_archive_list(ini.read_bytes(), "sResourceArchiveList", l1 + ["IniA.bsa"])
    raw = set_archive_list(raw, "sResourceArchiveList2", l2 + ["IniHidden.bsa"])
    ini.write_bytes(raw)
    en = romfs / "Skyrim_en.ini"
    l2en = read_ini(en).archive_list("sResourceArchiveList2")
    en.write_bytes(set_archive_list(en.read_bytes(), "sResourceArchiveList2", l2en + ["IniC.bsa"]))
    ccc = root / AOC / "romfs" / "Skyrim_aoc.ccc"
    from skynx.ccc import read_ccc
    ccc.write_bytes(render(read_ccc(ccc).entries + ["Dead.esp", "ModA.esp", "ModB.esp",
                                                     "Missing.esp"], "CRLF", True))
    return root


def test_conflict_load_order(tmp_path):
    pack = Pack.open(_conflict_project(tmp_path))
    names = [n for n, _p, _s in load_order_bsas(pack)]
    # Skyrim_en.ini replaces Skyrim.ini's sResourceArchiveList2, so IniHidden doesn't load
    assert names == ["IniA.bsa", "IniC.bsa", "Dead.bsa", "ModA.bsa", "ModA - Textures.bsa",
                     "ModB.bsa"]


def test_conflicts_pairs_duplicates_and_dead(tmp_path):
    rep = find_conflicts(Pack.open(_conflict_project(tmp_path)))
    pairs = {(p.winner, p.loser): p for p in rep.pairs}
    assert set(pairs) == {("ModB.bsa", "IniA.bsa"), ("ModB.bsa", "IniC.bsa"),
                          ("ModB.bsa", "ModA - Textures.bsa"), ("ModB.bsa", "Dead.bsa"),
                          ("IniC.bsa", "IniA.bsa"), ("ModA - Textures.bsa", "ModA.bsa")}
    assert pairs[("ModB.bsa", "IniA.bsa")].examples == ["textures\\x\\shared.dds"]
    assert pairs[("ModB.bsa", "IniA.bsa")].bytes == 4000
    assert pairs[("ModB.bsa", "IniA.bsa")].identical == 0          # same size, other bytes
    assert pairs[("ModB.bsa", "ModA - Textures.bsa")].identical == 1
    assert pairs[("ModB.bsa", "Dead.bsa")].count == 2
    assert pairs[("ModB.bsa", "Dead.bsa")].identical == 1          # 2.nif equal, 1.nif not
    assert pairs[("IniC.bsa", "IniA.bsa")].count == 1                # shared.dds is ModB's
    assert rep.pairs[0].count >= rep.pairs[-1].count
    dead = {d.bsa: d for d in rep.dead}             # every file replaced by later BSAs
    assert set(dead) == {"IniA.bsa", "Dead.bsa", "ModA.bsa"}
    assert dead["Dead.bsa"].winners == ["ModB.bsa"]
    assert set(dead["IniA.bsa"].winners) == {"ModB.bsa", "IniC.bsa"}
    assert "ModA - Textures.bsa" not in dead and "ModB.bsa" not in dead
    assert sorted(rep.unloaded) == ["IniHidden.bsa", "Orphan.bsa"]  # vanilla not listed
    assert rep.stats["conflicting_paths"] == 5
    assert rep.stats["bytes_read"] > 0
    d = rep.to_dict()
    assert d["pairs"][0]["winner"] and isinstance(d["order"][0]["path"], str)
    capped = find_conflicts(Pack.open(tmp_path / "proj"), max_read=0)
    assert capped.stats["identical"] == 0 and capped.stats["unchecked"] == 7   # every same-size pair
    assert capped.stats["bytes_read"] == 0


@pytest.mark.skipif(not MIRROR.exists(), reason="no mirror")
def test_conflicts_on_real_mirrors():
    for d in sorted(MIRROR.iterdir()):
        rep = find_conflicts(Pack.open(d))
        assert not rep.stats["errors"], d.name
        assert rep.stats["bytes_read"] <= 256 * 2**20
        assert all(p.count >= q.count for p, q in zip(rep.pairs, rep.pairs[1:]))
        for b in rep.order:
            assert not b.name.lower().startswith("skyrim - ")


@pytest.mark.skipif(not (ASHIRO.exists() and MIRROR.exists()), reason="no extracted Ashiro mods")
def test_conflicts_on_ashiro_extracted(tmp_path):
    """Ashiro's list ships its mods as .7z; work/ashiro holds them extracted."""
    src = MIRROR / "Ashiro_s Light Modlist" / "atmosphere" / "contents"
    root = tmp_path / "ashiro"
    data = root / BASE / "romfs" / "Data"
    data.mkdir(parents=True)
    (root / AOC / "romfs").mkdir(parents=True)
    for ini in (src / BASE / "romfs").glob("*.ini"):
        os.symlink(ini.resolve(), root / BASE / "romfs" / ini.name)
    os.symlink((src / AOC / "romfs" / "Skyrim_aoc.ccc").resolve(),
               root / AOC / "romfs" / "Skyrim_aoc.ccc")
    for f in ASHIRO.rglob("*"):
        if f.suffix.lower() in (".esp", ".bsa") and not (data / f.name).exists():
            os.symlink(f.resolve(), data / f.name)
    rep = find_conflicts(Pack.open(root))
    pairs = {(p.winner, p.loser): p for p in rep.pairs}
    if ("Scrlg.bsa", "USSEP.bsa") not in pairs:
        pytest.skip("extracted mods differ from the ones this test was written against")
    assert pairs[("Scrlg.bsa", "USSEP.bsa")].identical == 0      # Sacrilege really overrides USSEP
    assert pairs[("SmystMs.bsa", "OdnMs.bsa")].identical == pairs[("SmystMs.bsa", "OdnMs.bsa")].count
    assert not rep.stats["errors"]


# ---------------------------------------------------------------- first copy
def test_first_copy_on_a_fresh_sd(tmp_path):
    """A new SD (Atmosphère without Skyrim, or not even atmosphere\\contents
    yet) is a first copy: everything is new, nothing to back up."""
    pack = _pack(tmp_path)
    sd = _sd(tmp_path)
    plan = D.plan_sync(pack, sd).to_dict()
    assert plan["first"] and plan["delete"] == 0 and plan["backup_files"] == 0
    assert plan["new"] == plan["copy"] > 0
    D.deploy(pack, sd)
    assert D.plan_sync(pack, sd).to_dict()["first"] is False

    bare = tmp_path / "bare"
    (bare / "Nintendo").mkdir(parents=True)                  # no atmosphere folder yet
    assert D.plan_sync(pack, bare).to_dict()["first"]
    r = D.deploy(pack, bare)
    assert r["copied"] > 0
    assert (bare / "atmosphere" / "contents" / BASE / "romfs" / "Data" / "Mod.esp").exists()


def test_a_folder_that_isnt_an_sd_is_refused(tmp_path):
    pack = _pack(tmp_path)
    other = tmp_path / "Documents"
    (other / "stuff").mkdir(parents=True)
    with pytest.raises(D.DeployError, match="Switch SD"):
        D.plan_sync(pack, other)
    assert not (other / "atmosphere").exists()


def test_progress_follows_the_interface_language(tmp_path):
    from skynx.i18n import progress_label
    seen = []
    pack, sd = _pack(tmp_path), _sd(tmp_path)
    D.deploy(pack, sd, progress=lambda t, i=0, n=0: seen.append(t))
    assert seen and all(not t.startswith(("Copiando", "Respaldando", "Comparando", "Borrando")) for t in seen)
    assert progress_label("Copying Mod.bsa", "es") == "Copiando Mod.bsa"
    assert progress_label("Copying Mod.bsa", "en") == "Copying Mod.bsa"
    assert progress_label("textures", "es") == "texturas"
    assert progress_label("Mod.esp", "es") == "Mod.esp"


def test_files_dated_1970_are_not_copied_every_time(tmp_path):
    """Vanilla+ ships its files dated 1970; the SD stores 1980 at the earliest,
    so the dates never matched and big files were copied on every sync."""
    pack, sd = _pack(tmp_path), _sd(tmp_path)
    big = pack / BASE / "romfs" / "Data" / "Mod.bsa"
    os.utime(big, (0, 0))
    D.deploy(pack, sd)
    on_sd = sd / "atmosphere" / "contents" / BASE / "romfs" / "Data" / "Mod.bsa"
    fat = 315532800 + 18000                              # what the card keeps: 1980-01-01 local time
    os.utime(on_sd, (fat, fat))
    monkey = D.HASH_LIMIT
    try:
        D.HASH_LIMIT = 0                                 # as if it were a big file: no hashing
        assert D.plan_sync(pack, sd).to_dict()["copy"] == 0
        on_sd.write_bytes(os.urandom(on_sd.stat().st_size))   # same size, other content, still old
        os.utime(on_sd, (fat, fat))
        assert D.plan_sync(pack, sd).to_dict()["copy"] == 0   # the known limit: size and age only
    finally:
        D.HASH_LIMIT = monkey


def test_a_renamed_file_is_renamed_on_the_sd(tmp_path, monkeypatch):
    """Shortening BSA names renames them in the pack: the SD renames them too
    instead of copying them again (Music of Tamriel is 332 MB)."""
    pack, sd = _pack(tmp_path), _sd(tmp_path)
    D.deploy(pack, sd)
    data = pack / BASE / "romfs" / "Data"
    os.replace(data / "Mod.bsa", data / "ModS.bsa")
    big = data / "Textures" / "Big" / "a.dds"
    os.replace(big, data / "Textures" / "a.dds")                       # moved to another folder
    plan = D.plan_sync(pack, sd).to_dict()
    assert plan["move"] == 2 and plan["copy"] == 0 and plan["delete"] == 0 and plan["backup_files"] == 0
    assert any("ModS.bsa" in x for x in plan["examples"]["move"])
    before = (sd / "atmosphere/contents" / BASE / "romfs/Data/Mod.bsa").read_bytes()
    r = D.deploy(pack, sd)
    assert r["moved"] == 2 and r["copied"] == 0
    c = sd / "atmosphere/contents" / BASE / "romfs/Data"
    assert (c / "ModS.bsa").read_bytes() == before and not (c / "Mod.bsa").exists()
    assert (c / "Textures" / "a.dds").exists() and not (c / "Textures" / "Big" / "a.dds").exists()
    assert D.plan_sync(pack, sd).empty


def test_a_renamed_plugin_dated_1970_is_renamed_on_the_sd(tmp_path):
    """Plugins shipped dated 1970 get the card's 1980 date, so after a rename
    the dates never match: small files are paired by content instead."""
    pack, sd = _pack(tmp_path), _sd(tmp_path)
    data = pack / BASE / "romfs" / "Data"
    _w(data / "Long Name - Of A Mod.esp", b"TES4" + b"x" * 300, mtime=0)
    D.deploy(pack, sd)
    c = sd / "atmosphere/contents" / BASE / "romfs/Data"
    os.utime(c / "Long Name - Of A Mod.esp", (D.FAT_STAMP, D.FAT_STAMP))   # what exFAT keeps
    os.replace(data / "Long Name - Of A Mod.esp", data / "LongNOAM.esp")
    plan = D.plan_sync(pack, sd).to_dict()
    assert plan["move"] == 1 and plan["copy"] == 0 and plan["delete"] == 0
    r = D.deploy(pack, sd)
    assert r["moved"] == 1 and (c / "LongNOAM.esp").exists() and not (c / "Long Name - Of A Mod.esp").exists()
    assert D.plan_sync(pack, sd).empty


def test_the_homebrew_backup_on_the_sd_is_left_alone(tmp_path):
    pack, sd = _pack(tmp_path), _sd(tmp_path)
    D.deploy(pack, sd)
    keep = _w(sd / "atmosphere/contents" / AOC / "romfs" / "Skyrim_aoc.ccc.skynx-original", "a\r\n")
    plan = D.plan_sync(pack, sd)
    assert plan.empty and keep.exists()


def test_a_failed_copy_puts_moved_files_back(tmp_path, monkeypatch):
    pack, sd = _pack(tmp_path), _sd(tmp_path)
    D.deploy(pack, sd)
    before = _snap(sd)
    data = pack / BASE / "romfs" / "Data"
    os.replace(data / "Mod.bsa", data / "ModS.bsa")
    _w(data / "new.nif", os.urandom(100))
    def boom(src, dst):
        raise OSError("card pulled out")
    monkeypatch.setattr(D, "_copy_file", boom)
    with pytest.raises(D.DeployError):
        D.deploy(pack, sd)
    assert _snap(sd) == before


def test_scripts_follow_the_switch_order(tmp_path):
    """On Switch a script in an ini BSA wins over the same script in a plugin's
    BSA (Growl vs KokaNX's USSEP.bsa); textures keep the PC order (Noble)."""
    pack = Pack.open(_conflict_project(tmp_path))
    names = [n for n, _p, _s in load_order_bsas(pack, scripts=True)]
    assert names == ["Dead.bsa", "ModA.bsa", "ModA - Textures.bsa", "ModB.bsa", "IniA.bsa", "IniC.bsa"]
    root = tmp_path / "proj" / BASE / "romfs"
    _bsa(root / "Data" / "IniS.bsa", {"scripts\\s.pex": b"I" * 10}, tmp_path / "src2")
    ini = root / "Skyrim.ini"
    l1 = read_ini(ini).archive_list("sResourceArchiveList")
    ini.write_bytes(set_archive_list(ini.read_bytes(), "sResourceArchiveList", l1 + ["IniS.bsa"]))
    rep = find_conflicts(Pack.open(tmp_path / "proj"))
    pairs = {(p.winner, p.loser) for p in rep.pairs}
    assert ("IniS.bsa", "ModA - Textures.bsa") in pairs and ("IniS.bsa", "ModA.bsa") in pairs   # the script
    assert ("ModB.bsa", "IniA.bsa") in pairs                                                 # a texture


def test_a_1970_file_whose_copy_got_todays_date(tmp_path):
    """Music of Tamriel and Heavy Armory (dated 1970, over 8 MB) were copied on
    every sync: Windows wouldn't put a 1970 date on the exFAT card, so the copy
    kept the day it was written. Now the copy gets a 1980 date the card can
    store, and one that already has another date is compared by content once."""
    pack, sd = _pack(tmp_path), _sd(tmp_path)
    big = pack / BASE / "romfs" / "Data" / "Mod.bsa"
    os.utime(big, (0, 0))
    D.deploy(pack, sd)
    on_sd = sd / "atmosphere" / "contents" / BASE / "romfs" / "Data" / "Mod.bsa"
    assert int(on_sd.stat().st_mtime) == D.FAT_STAMP           # a date the card can store
    now = time.time()
    os.utime(on_sd, (now, now))                                  # what the card kept before
    monkey = D.HASH_LIMIT
    try:
        D.HASH_LIMIT = 0                                         # as if it were big
        assert D.plan_sync(pack, sd).to_dict()["copy"] == 0      # same content: not copied again
        r = D.deploy(pack, sd)
        assert r["copied"] == 0 and int(on_sd.stat().st_mtime) == D.FAT_STAMP   # and its date fixed
        on_sd.write_bytes(os.urandom(on_sd.stat().st_size))
        os.utime(on_sd, (now, now))
        assert D.plan_sync(pack, sd).to_dict()["copy"] == 1      # other content: copied
    finally:
        D.HASH_LIMIT = monkey
