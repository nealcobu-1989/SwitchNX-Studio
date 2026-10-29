"""Pack recipes: provenance in mods.json, build/save/history, Markdown export,
diff, verify and finding the downloads again."""
import hashlib
import json
import os
import shutil
import sys
import time
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(Path(__file__).resolve().parent))
from skynx import recipe as R  # noqa: E402
from skynx.builder import add_mod, create_project, load_mods, remove_mod  # noqa: E402
from skynx.ccc import parse_ccc, render  # noqa: E402
from skynx.pack import Pack  # noqa: E402
from skynx.transfer import apply_transfer, plan_transfer  # noqa: E402
from test_library import EMPTY_BSA, INIS, MIRROR, fake_plugin, mini_pack, zip_dir  # noqa: E402

USSEP_FX = ROOT / "tests" / "fixtures" / "ussep"
NX = {"mod_id": "12345", "file_id": 678, "version": "1.2.0", "name": "Cool Swords"}


def mod_folder(where: Path, name: str, plugin: str, bsa: bool = True, masters=("Skyrim.esm",)) -> Path:
    m = where / name
    fake_plugin(m / plugin, list(masters))
    if bsa:
        (m / (Path(plugin).stem + ".bsa")).write_bytes(EMPTY_BSA)
    return m


def md5(p: Path) -> str:
    return hashlib.md5(p.read_bytes()).hexdigest()


@pytest.fixture()
def pack(tmp_path):
    return Pack.open(mini_pack(tmp_path / "Pack"))


def with_mods(pack, tmp_path):
    """A pack with one Nexus archive and one folder mod."""
    dl = tmp_path / "downloads"
    dl.mkdir()
    z = zip_dir(mod_folder(tmp_path / "src", "Cool Swords", "CoolSwords.esp"), dl / "Cool Swords-12345-1-2-0.zip")
    add_mod(pack, z, nexus=NX)
    folder = mod_folder(tmp_path / "src", "Plain Folder Mod", "PlainFolder.esp")
    add_mod(pack, folder)
    return Pack.open(pack.root), z, folder


# ---------------------------------------------------------------- provenance
def test_provenance_archive_and_folder(pack, tmp_path):
    pack, z, folder = with_mods(pack, tmp_path)
    mods = load_mods(pack)
    a = mods["Cool Swords-12345-1-2-0"]["source"]
    assert a["kind"] == "nexus" and a["path"] == str(z) and a["file"] == z.name
    assert a["size"] == z.stat().st_size and a["md5"] == md5(z)
    assert a["nexus"] == {"mod_id": 12345, "file_id": 678, "version": "1.2.0", "name": "Cool Swords"}
    assert a["added"]
    f = mods["Plain Folder Mod"]["source"]
    assert f["kind"] == "folder" and f["file"] == "Plain Folder Mod" and "md5" not in f
    assert f["fingerprint"] == R.folder_fingerprint(folder)
    # same names and sizes elsewhere: same fingerprint; one byte more: another
    copy = shutil.copytree(folder, tmp_path / "elsewhere" / "Plain Folder Mod")
    assert R.folder_fingerprint(copy) == f["fingerprint"]
    (copy / "PlainFolder.bsa").write_bytes(EMPTY_BSA + b"x")
    assert R.folder_fingerprint(copy) != f["fingerprint"]
    # an archive without Nexus info is just an archive
    z2 = zip_dir(mod_folder(tmp_path / "src", "Other", "Other.esp"), tmp_path / "Other.zip")
    add_mod(Pack.open(pack.root), z2)
    assert load_mods(Pack.open(pack.root))["Other"]["source"]["kind"] == "archive"


def test_provenance_ussep(tmp_path):
    root = create_project(tmp_path / "p", "AE", INIS, "none", ussep="All_CC", ussep_dir=USSEP_FX)
    rec = load_mods(Pack.open(root))["USSEP (KokaNX, All_CC)"]
    s = rec["source"]
    assert rec["ussep"] == "All_CC"
    assert s["kind"] == "ussep" and s["variant"] == "All_CC" and s["path"] == str(USSEP_FX)
    files = [USSEP_FX / "All_CC" / "Unofficial Skyrim Special Edition Patch.esp"] + \
        sorted(USSEP_FX.glob("*.bsa"))
    assert s["fingerprint"] == R.folder_fingerprint(USSEP_FX, files)
    assert s["size"] == sum(p.stat().st_size for p in files)


def test_provenance_transfer_keeps_origin(pack, tmp_path):
    src, z, _f = with_mods(pack, tmp_path)
    dst_root = create_project(tmp_path / "Mine", "AE", INIS, "all")
    plan = plan_transfer(src, Pack.open(dst_root), ["plugin:CoolSwords.esp"])
    assert plan.ok, plan.errors
    apply_transfer(plan)
    rec = load_mods(Pack.open(dst_root))["CoolSwords"]
    s = rec["source"]
    assert rec["from_pack"] == "Pack" and s["kind"] == "pack" and s["pack"] == "Pack"
    assert s["unit"] == "plugin:CoolSwords.esp" and s["path"] == str(src.root)
    assert s["origin"]["md5"] == md5(z) and s["origin"]["kind"] == "nexus"
    assert s["nexus"]["mod_id"] == 12345            # Nexus info travels with the mod
    r = R.build(Pack.open(dst_root))
    assert "nexusmods.com/skyrimspecialedition/mods/12345" in R.export_markdown(r)
    # missing_sources looks for the original download
    found = {x["mod"]: x for x in R.missing_sources(r, [z.parent])}
    assert found["CoolSwords"]["found"] == str(z) and found["CoolSwords"]["by"] == "md5"


def test_provenance_converted_fomod(tmp_path):
    tc = pytest.importorskip("test_convert")
    if not shutil.which("ffmpeg"):
        pytest.skip("needs ffmpeg")
    from skynx.converter import FomodSession, convert, fomod_finish, start
    pack = Pack.open(create_project(tmp_path / "pack", "AE", tc.BASE_INIS, "ussep"))
    z = tc.make_fomod_zip(tmp_path)
    sess = start(pack, z)
    assert isinstance(sess, FomodSession)
    choices = {"0": {"0": [0]}}                       # Alpha 2K: the patches step hides
    an = fomod_finish(pack, sess, choices)
    convert(pack, an, {"preset": "diet", "sdk": True, "names": {"MyMod.esp": "MyMod.esp"}},
            tc.tools(), nexus={"mod_id": 99, "file_id": 5, "version": "1.0", "name": "My FOMOD Mod"})
    an.cleanup()
    pack = Pack.open(pack.root)
    rec = load_mods(pack)[an.id]
    s = rec["source"]
    assert s["kind"] == "nexus" and s["md5"] == md5(z) and s["file"] == z.name
    assert s["nexus"] == {"mod_id": 99, "file_id": 5, "version": "1.0", "name": "My FOMOD Mod"}
    assert rec["fomod"] == {"Main": {"Texture size": ["Alpha 2K"]}}
    assert rec["fomod_choices"] == choices and rec["fomod_module"] == "My FOMOD Mod"
    conv = rec["converted"]
    assert conv["preset"] == "diet" and conv["sdk"] is True and conv["bc1"] is False
    assert conv["names"] == {"MyMod.esp": "MyMod.esp"} and conv["chosen"] == {"MyMod.esp": "MyMod.esp"}
    r = R.build(pack)
    m = next(x for x in r["mods"] if x["id"] == an.id)
    assert m["fomod_choices"] == choices and m["converted"]["preset"] == "diet"
    md = R.export_markdown(r, "es")
    assert "Texture size: Alpha 2K" in md and "diet, SDK" in md
    assert "nexusmods.com/skyrimspecialedition/mods/99" in md


def test_old_string_source_still_reads(pack, tmp_path):
    meta = Path(pack.root) / ".skynx" / "mods.json"
    meta.write_text(json.dumps({
        "Old Mod": {"source": "C:\\Mods\\Old Mod-1-2.7z", "added": "2026-01-01 10:00:00",
                    "plugins": ["Tiny.esp"], "bsas": ["Tiny.bsa"], "ini": []},
        "Brought": {"source": "D:\\Packs\\Avner", "from_pack": "Avner", "plugins": [], "bsas": []},
    }), encoding="utf-8")
    r = R.build(Pack.open(pack.root))
    mods = {m["id"]: m for m in r["mods"]}
    s = mods["Old Mod"]["source"]
    assert s == {"kind": "archive", "path": "C:\\Mods\\Old Mod-1-2.7z", "file": "Old Mod-1-2.7z",
                 "legacy": True, "added": "2026-01-01 10:00:00"}
    assert mods["Brought"]["source"]["kind"] == "pack" and mods["Brought"]["from_pack"] == "Avner"
    assert not r["unowned"]                            # Tiny.esp/.bsa belong to "Old Mod"
    md = R.export_markdown(r)
    assert "Old Mod-1-2.7z" in md and "C:\\" not in md and "D:\\" not in md
    # recognised (LOOT / by hand) links go in too
    link = {"status": "likely", "mod_id": 777, "url": "https://www.nexusmods.com/skyrimspecialedition/mods/777",
            "title": "Old Mod SE"}
    md = R.export_markdown(r, "es", links={"Old Mod": link})
    assert "[Nexus: Old Mod SE](https://www.nexusmods.com/skyrimspecialedition/mods/777) (reconocido por la lista de LOOT)" in md
    assert "Old Mod-1-2.7z" in md
    # a renamed archive with the same name is found by name only (no md5 recorded)
    dl = tmp_path / "dl"
    dl.mkdir()
    (dl / "Old Mod-1-2.7z").write_bytes(b"7z")
    found = {x["mod"]: x for x in R.missing_sources(r, [dl])}
    assert found["Old Mod"]["by"] == "name" and found["Brought"]["found"] is None


# ---------------------------------------------------------------- build / save
def test_build_contents(pack, tmp_path):
    pack, z, folder = with_mods(pack, tmp_path)
    # a Doctor rename, a kept duplicate, a disabled line and a LOOT choice
    (Path(pack.root) / ".skynx" / "renames.json").write_text(json.dumps({"CoolSwords.esp": "Cool Swords.esp"}))
    (Path(pack.root) / ".skynx" / "doctor-ignore.json").write_text(json.dumps({"ids": ["dup:a|b"]}))
    raw = pack.ccc_path.read_bytes()
    pack.ccc_path.write_bytes(raw + b"#Gone.esp\r\n")
    ul = tmp_path / "userlist.json"
    ul.write_text(json.dumps({"version": 1, "plugins": {
        "coolswords.esp": {"name": "CoolSwords.esp", "group": "Late", "after": ["Tiny.esp"], "note": ""},
        "elsewhere.esp": {"name": "Elsewhere.esp", "group": "Early"}}}))
    r = R.build(Pack.open(pack.root), userlist_path=ul)
    assert r["version"] == R.RECIPE_VERSION and r["pack"]["edition"] == "AE"
    assert r["pack"]["list_file"] == "Skyrim_aoc.ccc" and r["app"]
    assert r["load_order"][-1] == "#Gone.esp" and r["counts"]["disabled"] == 1
    assert r["counts"]["cc"] > 0 and any(e.lower().startswith("cc") for e in r["load_order"])
    assert [m["id"] for m in r["mods"]] == ["Cool Swords-12345-1-2-0", "Plain Folder Mod"]
    assert {u["name"] for u in r["unowned"]} == {"Tiny.esp", "Tiny.bsa"}
    assert all(u["source"] == {"kind": "unknown"} and u["loaded"] for u in r["unowned"])
    md = R.export_markdown(r, links={"tiny.esp": {"status": "confirmed", "mod_id": 5,
                                                  "url": "https://www.nexusmods.com/skyrimspecialedition/mods/5"}})
    assert "- `Tiny.esp` + Tiny.bsa · [Nexus: Tiny](https://www.nexusmods.com/skyrimspecialedition/mods/5) (confirmed by hand)" in md
    assert r["renames"] == {"CoolSwords.esp": "Cool Swords.esp"} and r["kept_duplicates"] == ["dup:a|b"]
    assert set(r["loot"]) == {"coolswords.esp"}
    f = r["files"]
    assert f["CoolSwords.esp"]["sha1"] == hashlib.sha1((pack.data_dir / "CoolSwords.esp").read_bytes()).hexdigest()
    assert "sha1" not in f["CoolSwords.bsa"] and f["CoolSwords.bsa"]["size"] == len(EMPTY_BSA)
    assert "sha1" in R.build(Pack.open(pack.root), full=True)["files"]["CoolSwords.bsa"]
    names = {i["name"] for i in r["inis"]}
    assert "Skyrim.ini" in names and all(len(i["sha1"]) == 40 for i in r["inis"])
    assert any("sResourceArchiveList" in i["archives"] for i in r["inis"])
    json.dumps(r)                                      # plain JSON


def test_save_rotation_and_history(pack):
    r = R.build(pack)
    for i in range(23):
        r = dict(r, created=time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(1_800_000_000 + i)))
        out = R.save(pack, r)
    assert out == Path(pack.root) / ".skynx" / "recipe.json"
    h = R.history(pack)
    assert len(h) == R.KEEP and h[0]["created"] == r["created"]
    assert h[0]["mods"] == len(r["mods"]) and Path(h[0]["path"]).parent.name == "recipes"
    assert R.load(out)["created"] == r["created"] == R.current(pack)["created"]
    # two saves in the same second keep both, newest first
    R.save(pack, r)
    h = R.history(pack)
    assert Path(h[0]["path"]).name.endswith("-2.json") and len(h) == R.KEEP
    with pytest.raises(Exception):
        R.load(Path(pack.root) / ".skynx" / "mods.json.missing")


# ---------------------------------------------------------------- markdown
def test_markdown_shareable(pack, tmp_path):
    pack, z, folder = with_mods(pack, tmp_path)
    r = R.build(pack)
    for lang in ("en", "es"):
        md = R.export_markdown(r, lang)
        assert str(tmp_path) not in md and "/tmp" not in md and ":\\" not in md
        assert "[Nexus: Cool Swords](https://www.nexusmods.com/skyrimspecialedition/mods/12345)" in md
        assert "| 1.2.0 |" in md and "`Plain Folder Mod`" in md
        assert "`Cool Swords-12345-1-2-0.zip`" in md
        assert "—" not in md                           # no em-dashes
    es = R.export_markdown(r, "es")
    assert "## Orden de carga" in es and "Archivos sin origen conocido" in es
    assert str(tmp_path) not in json.dumps(R.shareable(r))


# ---------------------------------------------------------------- diff
def test_diff_add_remove_reorder(pack, tmp_path):
    pack, z, folder = with_mods(pack, tmp_path)
    r1 = R.build(pack)
    add_mod(pack, mod_folder(tmp_path / "src", "Third", "Third.esp"))
    pack = Pack.open(pack.root)
    r2 = R.build(pack)
    d = R.diff(r1, r2)
    assert d["mods"]["added"] == ["Third"] and not d["mods"]["removed"]
    assert d["load_order"]["added"] == ["Third.esp"]
    assert "Mod added: Third" in R.diff_text(d)
    # remove one, move one, and a new version of another
    remove_mod(pack, "Plain Folder Mod")
    pack = Pack.open(pack.root)
    raw = pack.ccc_path.read_bytes()
    e = parse_ccc(raw).entries
    e.remove("Third.esp")
    e.insert(0, "Third.esp")
    pack.ccc_path.write_bytes(render(e, "CRLF"))
    mods = load_mods(pack)
    mods["Cool Swords-12345-1-2-0"]["source"]["nexus"]["version"] = "1.3.0"
    (Path(pack.root) / ".skynx" / "mods.json").write_text(json.dumps(mods))
    r3 = R.build(Pack.open(pack.root))
    d = R.diff(r2, r3)
    assert d["mods"]["removed"] == ["Plain Folder Mod"]
    assert d["load_order"]["removed"] == ["PlainFolder.esp"]
    assert d["load_order"]["moved"] == [{"name": "Third.esp", "from": len(r2["load_order"]), "to": 1}]
    ch = {c["id"]: c["changes"] for c in d["mods"]["changed"]}
    assert ch["Cool Swords-12345-1-2-0"] == [{"field": "version", "old": "1.2.0", "new": "1.3.0"}]
    keys = [k for i in d["inis"] for k, v in i["keys"].items() if "PlainFolder.bsa" in v["removed"]]
    assert keys or not any("PlainFolder.bsa" in b for v in r2["archive_lists"].values() for b in v)
    lines = R.diff_text(d, "es")
    assert "Mod quitado: Plain Folder Mod" in lines
    assert any("Third.esp" in ln and "→ 1" in ln for ln in lines)
    assert any("versión 1.2.0 → 1.3.0" in ln for ln in lines)
    assert R.diff_text(R.diff(r3, r3)) == ["Nothing changed."]
    assert not any("—" in ln for ln in lines)


def test_diff_ini_lists(pack, tmp_path):
    r1 = R.build(pack)
    # a BSA with no plugin goes to the inis
    m = tmp_path / "src" / "Loose"
    m.mkdir(parents=True)
    (m / "LooseStuff.bsa").write_bytes(EMPTY_BSA)
    add_mod(pack, m)
    r2 = R.build(Pack.open(pack.root))
    d = R.diff(r1, r2)
    added = [b for i in d["inis"] for v in i["keys"].values() for b in v["added"]]
    assert "LooseStuff.bsa" in added
    assert any("LooseStuff.bsa" in ln for ln in R.diff_text(d))


# ---------------------------------------------------------------- verify
def test_verify(pack, tmp_path):
    pack, z, folder = with_mods(pack, tmp_path)
    r = R.build(pack)
    assert R.verify(pack, r) == []
    p = pack.data_dir / "CoolSwords.esp"
    raw = bytearray(p.read_bytes())
    raw[-1] ^= 0xFF                                    # same size, other bytes
    st = p.stat()
    p.write_bytes(bytes(raw))
    os.utime(p, (st.st_atime, st.st_mtime))
    (pack.data_dir / "PlainFolder.bsa").unlink()
    fake_plugin(pack.data_dir / "Sneaky.esp", ["Skyrim.esm"])
    b = pack.data_dir / "CoolSwords.bsa"
    os.utime(b, (st.st_atime, st.st_mtime + 100))     # newer date, same size
    v = R.verify(Pack.open(pack.root), r)
    got = {(x["kind"], x["file"]) for x in v}
    assert ("changed", "CoolSwords.esp") in got and ("missing", "PlainFolder.bsa") in got
    assert ("extra", "Sneaky.esp") in got and ("touched", "CoolSwords.bsa") in got
    ch = next(x for x in v if x["file"] == "CoolSwords.esp")
    assert ch["mod"] == "Cool Swords-12345-1-2-0" and ch["how"] == "sha1" and ch["es"]
    # a changed load list and ini
    pack = Pack.open(pack.root)
    pack.ccc_path.write_bytes(pack.ccc_path.read_bytes() + b"Sneaky.esp\r\n")
    ini = pack.ini_paths[0]
    ini.write_bytes(ini.read_bytes() + b"\r\n[Display]\r\nfGamma=1.0\r\n")
    kinds = {x["kind"] for x in R.verify(Pack.open(pack.root), r)}
    assert {"order", "ini"} <= kinds


# ---------------------------------------------------------------- missing sources
def test_missing_sources_by_md5_after_rename(pack, tmp_path):
    pack, z, folder = with_mods(pack, tmp_path)
    r = R.build(pack)
    other = tmp_path / "new downloads" / "sub"
    other.mkdir(parents=True)
    moved = other / "renamed download.zip"
    shutil.move(str(z), moved)
    (other / "Cool Swords-12345-1-2-0.zip").write_bytes(b"not the same" * 10)   # same name, other bytes
    folder2 = shutil.copytree(folder, tmp_path / "new downloads" / "Plain Folder Mod")
    shutil.rmtree(folder)
    res = {x["mod"]: x for x in R.missing_sources(r, [tmp_path / "new downloads"])}
    assert res["Cool Swords-12345-1-2-0"] == {"mod": "Cool Swords-12345-1-2-0", "kind": "nexus",
                                              "file": "Cool Swords-12345-1-2-0.zip",
                                              "found": str(moved), "by": "md5"}
    assert res["Plain Folder Mod"]["found"] == str(folder2) and res["Plain Folder Mod"]["by"] == "fingerprint"
    none = {x["mod"]: x for x in R.missing_sources(r, [tmp_path / "nowhere"])}
    assert none["Cool Swords-12345-1-2-0"]["found"] is None and none["Cool Swords-12345-1-2-0"]["by"] is None


# ---------------------------------------------------------------- real packs
@pytest.mark.skipif(not MIRROR.exists(), reason="no mirror")
def test_real_packs(tmp_path, capsys):
    for src in sorted(p for p in MIRROR.iterdir() if p.is_dir()):
        copy = tmp_path / src.name
        shutil.copytree(src, copy, symlinks=True)       # files stay symlinks to the read-only originals
        t = time.time()
        pack = Pack.open(copy)
        r = R.build(pack)
        took = time.time() - t
        out = R.save(pack, r)
        md = R.export_markdown(r, "es")
        assert str(copy) not in md and str(MIRROR) not in md
        assert R.verify(pack, r) == []
        assert r["counts"]["plugins"] == len(pack.plugins)
        with capsys.disabled():
            print(f"\n  recipe: {src.name}: {r['counts']['plugins']} plugins, {r['counts']['bsas']} BSAs, "
                  f"{r['counts']['load_order']} lines, {len(r['unowned'])} unowned, "
                  f"{took:.2f}s, json {out.stat().st_size // 1024} KB, md {len(md) // 1024} KB")
