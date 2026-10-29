"""Projects: own folder, Mods/ and Base/ in step with the working pack, hand
edits brought in, Pack makes Switch/, nothing outside the project touched."""
import json
import os
import sys
import zipfile
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tests"))
from skynx import draft as DR  # noqa: E402
from skynx import project as P  # noqa: E402
from skynx.bsafix import safe_rename  # noqa: E402
from skynx.builder import mods_view, remove_mod  # noqa: E402
from skynx.history import Transaction, list_history, undo  # noqa: E402
from skynx.pack import Pack, is_project  # noqa: E402
from test_draft import avner_like, snapshot  # noqa: E402
from test_library import EMPTY_BSA, fake_plugin  # noqa: E402


def tree(root: Path, top: str) -> dict:
    d = Path(root) / top
    return {p.relative_to(d).as_posix(): p.read_bytes() for p in sorted(d.rglob("*")) if p.is_file()}


def work_snapshot(pack: Pack) -> dict:
    lr = pack.layout_root
    return {p.relative_to(lr).as_posix(): p.read_bytes() for p in sorted(lr.rglob("*"))
            if p.is_file() and ".skynx" not in p.relative_to(lr).parts}


def make(tmp_path, name="Mine"):
    src = avner_like(tmp_path / "src")
    before = snapshot(src)
    pk = P.from_pack(tmp_path / "lib", name, src.root)
    return src, before, pk


def test_from_pack_layout_and_source_untouched(tmp_path):
    src, before, pk = make(tmp_path)
    assert snapshot(Pack.open(src.root)) == before                # the source is never written
    assert is_project(pk.root) and pk.project and pk.layout_root == P.work_root(pk.root)
    assert pk.root == tmp_path / "lib" / "Projects" / "Mine"
    # the working pack is an exact copy
    src_rel = {k.split("/", 0)[0]: v for k, v in before.items()}
    assert work_snapshot(pk) == src_rel
    # one folder per mod, Base with the inis, the list and nothing else
    mods = tree(pk.root, "Mods")
    assert "Big Mod/Big Mod.esp" in mods and "Big Mod/Big Mod.bsa" in mods
    assert "LooseT/LooseT.bsa" in mods
    info = json.loads(mods["Big Mod/mod.json"])
    assert info["goes"] and info["plugins"] == ["Big Mod.esp"] and info["source"]["pack"] == src.root.name
    base = tree(pk.root, "Base")
    assert "Skyrim_aoc.ccc" in base and "Skyrim.ini" in base
    assert base["Skyrim_aoc.ccc"] == pk.list_path.read_bytes()
    # Mods/ shows the same files as the working pack (linked here)
    assert os.path.samefile(pk.root / "Mods" / "Big Mod" / "Big Mod.esp", pk.data_dir / "Big Mod.esp")
    # mods got stable records
    assert {r["id"] for r in mods_view(pk)} >= {"Big Mod", "LooseT"}
    with pytest.raises(P.ProjectError):                            # same name twice
        P.from_pack(tmp_path / "lib", "Mine", src.root)


def test_changes_show_in_mods_and_undo(tmp_path):
    src, before, pk = make(tmp_path)
    # a change through the history: rename the plugin
    with Transaction(pk.root, "Rename") as tx:
        safe_rename(pk, "Big Mod.esp", "BigMod.esp", tx)
    pk = Pack.open(pk.root)
    r = P.sync(pk)
    mods = tree(pk.root, "Mods")
    assert "Big Mod/BigMod.esp" in mods and "Big Mod/Big Mod.esp" not in mods   # same folder, new name
    assert "Big Mod/BigMod.bsa" in mods
    assert b"BigMod.esp" in tree(pk.root, "Base")["Skyrim_aoc.ccc"]
    assert r["removed"] >= 2
    # undo puts it back, Mods follows
    e = next(x for x in list_history(pk.root) if x["title"] == "Rename")
    undo(pk.root, e["id"])
    pk = Pack.open(pk.root)
    P.sync(pk)
    mods = tree(pk.root, "Mods")
    assert "Big Mod/Big Mod.esp" in mods and "Big Mod/BigMod.esp" not in mods
    assert snapshot(Pack.open(src.root)) == before


def test_doesnt_go_and_remove(tmp_path):
    src, before, pk = make(tmp_path)
    row = next(r for r in mods_view(pk) if r["id"] == "Big Mod")
    with Transaction(pk.root, "out") as tx:
        DR.exclude(pk, row, tx)
    pk = Pack.open(pk.root)
    P.sync(pk)
    info = json.loads((pk.root / "Mods" / "Big Mod" / "mod.json").read_text())
    assert info["goes"] is False and (pk.root / "Mods" / "Big Mod" / "Big Mod.esp").exists()
    # packing leaves it out
    out = P.build(pk)
    sw = Pack.open(pk.root / "Switch")
    assert "big mod.esp" not in sw.plugins and "big mod.bsa" not in sw.bsas
    assert not (pk.root / "Switch" / ".skynx").exists()
    assert out["plugins"] == len(sw.plugins)
    # back in, then removed: its folder goes
    with Transaction(pk.root, "in") as tx:
        DR.include(pk, "Big Mod", tx)
    pk = Pack.open(pk.root)
    remove_mod(pk, "Big Mod")
    pk = Pack.open(pk.root)
    P.sync(pk)
    assert not (pk.root / "Mods" / "Big Mod").exists()
    assert snapshot(Pack.open(src.root)) == before


def test_hand_edits_come_in_with_history(tmp_path):
    src, before, pk = make(tmp_path)
    # an ini edited in Base/ by hand (saved as a new file, like most editors)
    ini = pk.root / "Base" / "Skyrim.ini"
    new = ini.read_bytes() + b"\r\n[Display]\r\nfShadowDistance=3000\r\n"
    tmp = ini.with_name("x.tmp")
    tmp.write_bytes(new)
    os.replace(tmp, ini)
    # a file dropped into a mod folder
    seq = pk.root / "Mods" / "Big Mod" / "seq" / "Big Mod.seq"
    seq.parent.mkdir(parents=True)
    seq.write_bytes(b"\x00" * 4)
    # a plugin dropped where no mod is: it ends in Base/Data
    fake_plugin(pk.root / "Mods" / "Nowhere" / "Stray.esp", ["Skyrim.esm"])
    r = P.sync(pk)
    pk = Pack.open(pk.root)
    assert any("Skyrim.ini" in x for x in r["pulled"])
    assert next(p for p in pk.ini_paths if p.name == "Skyrim.ini").read_bytes() == new
    assert (pk.data_dir / "seq" / "Big Mod.seq").read_bytes() == b"\x00" * 4
    assert (pk.data_dir / "Stray.esp").exists()
    assert (pk.root / "Mods" / "Big Mod" / "seq" / "Big Mod.seq").exists()   # owned by Big Mod
    assert not (pk.root / "Mods" / "Nowhere").exists()                       # moved to Base
    assert (pk.root / "Base" / "Data" / "Stray.esp").exists()
    e = next(x for x in list_history(pk.root) if x["title"] == "Changes made in the project folder")
    assert len(e["files"]) == 3
    # nothing pulled the second time
    assert P.sync(pk)["pulled"] == []
    # a file deleted by hand comes back (remove mods in the app)
    (pk.root / "Mods" / "LooseT" / "LooseT.bsa").unlink()
    r = P.sync(pk)
    assert "Mods/LooseT/LooseT.bsa" in r["restored"] and (pk.root / "Mods" / "LooseT" / "LooseT.bsa").exists()
    assert snapshot(Pack.open(src.root)) == before


def test_copies_when_links_fail(tmp_path, monkeypatch):
    def no_link(*a, **k):
        raise OSError("no links here")
    monkeypatch.setattr(os, "link", no_link)
    src, before, pk = make(tmp_path)
    a = pk.root / "Mods" / "Big Mod" / "Big Mod.esp"
    assert a.exists() and not os.path.samefile(a, pk.data_dir / "Big Mod.esp")
    r = P.sync(pk)
    assert (r["pulled"], r["conflicts"], r["placed"], r["removed"]) == ([], [], 0, 0)
    # a change in the working pack is copied over
    with Transaction(pk.root, "list") as tx:
        tx.write_bytes(pk.list_path, pk.list_path.read_bytes() + b"Extra.esp\r\n")
    pk = Pack.open(pk.root)
    r = P.sync(pk)
    assert r["placed"] == 1 and r["pulled"] == []
    assert tree(pk.root, "Base")["Skyrim_aoc.ccc"].endswith(b"Extra.esp\r\n")


def test_both_sides_changed_keeps_the_hand_edit_aside(tmp_path, monkeypatch):
    monkeypatch.setattr(os, "link", lambda *a, **k: (_ for _ in ()).throw(OSError("x")))
    src, before, pk = make(tmp_path)
    base_ccc = pk.root / "Base" / "Skyrim_aoc.ccc"
    base_ccc.write_bytes(b"hand\r\n")
    with Transaction(pk.root, "list") as tx:
        tx.write_bytes(pk.list_path, pk.list_path.read_bytes() + b"Extra.esp\r\n")
    pk = Pack.open(pk.root)
    r = P.sync(pk)
    assert r["conflicts"] == ["Base/Skyrim_aoc.ccc"]
    assert base_ccc.read_bytes() == pk.list_path.read_bytes()
    kept = list((pk.root / ".skynx" / "mirror-conflicts").rglob("Skyrim_aoc.ccc"))
    assert kept and kept[0].read_bytes() == b"hand\r\n"


def test_build_replaces_only_its_own_output(tmp_path):
    src, before, pk = make(tmp_path)
    (pk.root / "Switch").mkdir()
    (pk.root / "Switch" / "mine.txt").write_text("not the app's")
    P.build(pk)
    assert (pk.root / "Switch" / P.BUILD_MARK).is_file()
    assert list((pk.root / ".skynx" / "trash").glob("Switch-*/mine.txt"))   # kept, not deleted
    first = snapshot(Pack.open(pk.root / "Switch"))
    P.build(pk)                                                            # again: same result
    assert snapshot(Pack.open(pk.root / "Switch")) == first
    # what goes to the SD is Switch/
    from skynx.deploy import _title_dir
    assert _title_dir(pk.root, "01000A10041EA000") == pk.root / "Switch" / "01000A10041EA000"


def test_from_zip_and_from_draft_and_listing(tmp_path):
    src = avner_like(tmp_path / "src")
    z = tmp_path / "Shared Pack.zip"
    with zipfile.ZipFile(z, "w") as zf:
        for p in sorted(src.root.rglob("*")):
            if p.is_file() and ".skynx" not in p.parts:
                zf.write(p, "Shared Pack/atmosphere/contents/" + p.relative_to(src.root).as_posix())
    pk = P.from_pack(tmp_path / "lib", "From zip", z)
    assert len(pk.plugins) == len(src.plugins) and (pk.root / "Mods" / "Big Mod").is_dir()
    assert z.exists() and not (pk.root / ".skynx" / "import").exists()
    # a pack being created keeps what doesn't go
    d = DR.start_from_pack(src, tmp_path / "lib" / "Drafts" / "Old", "Old")
    row = next(r for r in mods_view(d) if r["id"] == "Big Mod.esp")
    with Transaction(d.root, "out") as tx:
        DR.exclude(d, row, tx)
    leg = P.legacy(tmp_path / "lib")
    assert [x["kind"] for x in leg if x["name"] == "Old"] == ["draft"]
    pk2 = P.from_pack(tmp_path / "lib", "Old project", d.root)
    assert "Big Mod.esp" in DR.load(pk2.root)["excluded"]
    assert json.loads((pk2.root / "Mods" / "Big Mod" / "mod.json").read_text())["goes"] is False
    assert any(x["done"] for x in P.legacy(tmp_path / "lib") if x["name"] == "Old")
    names = [p["name"] for p in P.list_projects(tmp_path / "lib")]
    assert sorted(names) == ["From zip", "Old project"]
    s = P.summary(pk2.root)
    assert s["edition"] == "AE" and s["off"] == 1 and s["mods"] >= 2
    # a failed creation leaves nothing behind
    with pytest.raises(P.ProjectError):
        P.from_pack(tmp_path / "lib", "Broken", tmp_path / "src" / "nothing-here")
    assert not (tmp_path / "lib" / "Projects" / "Broken").exists()
    # deleting goes to the Library trash
    gone = P.delete(tmp_path / "lib", pk.root)
    assert not pk.root.exists() and gone.is_dir()


def test_new_empty_project(tmp_path):
    base = ROOT / "tests" / "fixtures" / "console-inis"
    pk = P.new_empty(tmp_path / "lib", "Fresh", "AE", base, "ussep",
                     ussep="All_CC", ussep_dir=ROOT / "tests" / "fixtures" / "ussep")
    assert pk.project and pk.mode == "AE"
    assert not (P.work_root(pk.root) / ".skynx").exists()
    mods = tree(pk.root, "Mods")
    assert any(k.endswith("Unofficial Skyrim Special Edition Patch.esp") for k in mods)
    assert "Skyrim_aoc.ccc" in tree(pk.root, "Base")
    assert P.summary(pk.root)["edition"] == "AE"


def test_api_project_flow(tmp_path, monkeypatch):
    from test_library import mini_pack, zip_dir
    from test_v05 import _fresh_api
    api, run = _fresh_api(tmp_path, monkeypatch)
    src = mini_pack(tmp_path / "Shared" / "Tiny Pack")
    z = zip_dir(src, tmp_path / "Tiny Pack.zip")
    p = run("project_new", "pack", "Tiny", {"src": str(z)})
    assert p["error"] is None, p
    root = tmp_path / "lib" / "Projects" / "Tiny"
    assert p["result"]["pack"]["project"]["name"] == "Tiny" and p["result"]["pack"]["name"] == "Tiny"
    assert [x["name"] for x in api.projects()["projects"]] == ["Tiny"]
    assert (root / "Mods" / "Tiny" / "Tiny.esp").exists() and z.exists()
    # mods from another modpack, straight from its zip
    other = mini_pack(tmp_path / "Other" / "Other Pack")
    data = other / "01000A10041EA000/romfs/Data"
    (data / "Tiny.esp").rename(data / "Other.esp")
    (data / "Tiny.bsa").rename(data / "Other.bsa")
    ccc = other / "01000A10041EB009/romfs/Skyrim_aoc.ccc"
    ccc.write_bytes(ccc.read_bytes().replace(b"Tiny.esp", b"Other.esp"))
    zo = zip_dir(other, tmp_path / "Other.zip")
    units = run("transfer_list", str(zo))["result"]["units"]
    ids = [u["id"] for u in units if "Other.esp" in u["id"]]
    assert ids
    run("transfer_plan", str(zo), ids)
    run("transfer_apply")
    found = [p for p in (root / "Mods").rglob("Other.esp")]
    assert len(found) == 1 and found[0].parent.parent == root / "Mods"
    assert json.loads((found[0].parent / "mod.json").read_text())["goes"]
    # Pack, then the SD gets what Pack made
    sd = tmp_path / "SD"
    (sd / "atmosphere" / "contents").mkdir(parents=True)
    run("project_build")
    assert (root / "Switch" / "01000A10041EA000" / "romfs" / "Data" / "Other.esp").exists()
    run("sd_plan", str(sd))
    run("deploy", str(sd), "sync")
    assert (sd / "atmosphere/contents/01000A10041EA000/romfs/Data/Other.esp").exists()
    assert not (sd / "atmosphere/contents/Mods").exists()
    assert P.read_info(root)["last_sd"]
    # the list for SkyNX Mods (the homebrew) is on the card; a choice made there comes back
    side = sd / "switch" / "SkyNXMods" / "skyrim.txt"
    assert "Other.esp" in side.read_text()
    accc = sd / "atmosphere/contents/01000A10041EB009/romfs/Skyrim_aoc.ccc"
    accc.write_bytes(accc.read_bytes().replace(b"Other.esp\r\n", b""))
    side.write_text(side.read_text().replace("Other.esp", "#Other.esp"))
    plan = run("sd_plan", str(sd))["result"]
    assert plan["console"] == {"off": ["Other.esp"], "on": []}
    r = run("sd_use_console", str(sd))
    assert r["error"] is None and "#Other.esp" in api._pack.list_entries
    assert run("sd_plan", str(sd))["result"]["console"] is None
    # an edit by hand in Mods/ comes in when the project is checked again
    ini = root / "Base" / "Skyrim.ini"
    t = ini.with_name("t.tmp")
    t.write_bytes(ini.read_bytes() + b"\r\n; mine\r\n")
    os.replace(t, ini)
    run("reaudit", False)
    assert any(h["title"].startswith(("Changes made", "Cambios hechos")) for h in api.history())
    # the import cache goes when the project closes; delete goes to the trash
    api.close_pack()
    assert not list((tmp_path / "lib" / ".import-cache").glob("*/pack")) if (tmp_path / "lib" / ".import-cache").exists() else True
    r = api.project_delete(str(root))
    assert r["ok"] and not root.exists() and Path(r["trash"]).is_dir()


def test_review_cases(tmp_path):
    """What a safety review found: in-place edits, two hand files for one place,
    a hand edit of a mod removed meanwhile, user files in Switch/, a missing
    working pack, readmes next to a mod."""
    src, before, pk = make(tmp_path)
    # the source is copied, never linked: nothing in the project can reach it
    assert not os.path.samefile(src.data_dir / "Big Mod.esp", pk.data_dir / "Big Mod.esp")
    # an ini edited in place (how most editors save) comes in with history
    ini = pk.root / "Base" / "Skyrim.ini"
    with open(ini, "r+b") as f:
        f.seek(0, 2)
        f.write(b"\r\n; in place\r\n")
    r = P.sync(pk)
    assert r["pulled"] == ["Base/Skyrim.ini"]
    # a plugin in Mods edited in place: in the project, reported, the source untouched
    with open(pk.root / "Mods" / "Big Mod" / "Big Mod.esp", "r+b") as f:
        f.seek(0, 2)
        f.write(b"\x00")
    r = P.sync(Pack.open(pk.root))
    assert r["inplace"] == ["Mods/Big Mod/Big Mod.esp"]
    assert snapshot(Pack.open(src.root)) == before
    # two hand files for one place: neither goes in, both are kept
    for m, b in (("Big Mod", b"AAAA"), ("LooseT", b"BBBB")):
        f = pk.root / "Mods" / m / "textures" / "shared" / "x.dds"
        f.parent.mkdir(parents=True)
        f.write_bytes(b)
    pk = Pack.open(pk.root)
    r = P.sync(pk)
    assert len(r["conflicts"]) == 2 and not (pk.data_dir / "textures" / "shared" / "x.dds").exists()
    kept = sorted(p.read_bytes() for p in (pk.root / ".skynx" / "mirror-conflicts").rglob("x.dds"))
    assert kept == [b"AAAA", b"BBBB"]
    # a readme next to a mod stays where it is and doesn't go to the game
    (pk.root / "Mods" / "LooseT" / "readme.txt").write_text("notes")
    r = P.sync(pk)
    assert "Mods/LooseT/readme.txt" in r["ignored"] and not (pk.data_dir / "readme.txt").exists()
    assert (pk.root / "Mods" / "LooseT" / "readme.txt").exists()
    # a hand edit of a mod that's removed meanwhile doesn't bring it back
    esp = pk.root / "Mods" / "Big Mod" / "Big Mod.esp"
    t = esp.with_name("t.tmp")
    t.write_bytes(esp.read_bytes() + b"\x01")
    os.replace(t, esp)
    remove_mod(pk, "Big Mod")
    pk = Pack.open(pk.root)
    r = P.sync(pk)
    assert not (pk.data_dir / "Big Mod.esp").exists() and "Mods/Big Mod/Big Mod.esp" in r["conflicts"]
    assert list((pk.root / ".skynx" / "mirror-conflicts").rglob("Big Mod.esp"))
    # Switch/: files the app didn't make go to the trash, not away
    P.build(pk)
    mine = pk.root / "Switch" / "01000A10041EA000" / "romfs" / "Data" / "my-test.esp"
    mine.write_bytes(b"mine")
    (pk.root / "Switch" / "README-mine.txt").write_text("x")
    out = P.build(pk)
    assert sorted(out["set_aside"]) == ["01000A10041EA000/romfs/Data/my-test.esp", "README-mine.txt"]
    assert not mine.exists() and list((pk.root / ".skynx" / "trash").rglob("my-test.esp"))
    assert out["copied"] == 0 and out["kept"] > 0              # nothing else copied again
    # Switch/ holds copies: editing it can't reach the project
    sw = pk.root / "Switch" / "01000A10041EA000" / "romfs" / "Data" / "LooseT.bsa"
    assert not os.path.samefile(sw, pk.data_dir / "LooseT.bsa")
    # the working pack gone: Mods and Base are left alone
    import shutil
    shutil.rmtree(pk.data_dir)
    n = len(list((pk.root / "Mods").rglob("*")))
    r = P.sync(Pack.open(pk.root))
    assert r["held"] and len(list((pk.root / "Mods").rglob("*"))) == n


def test_removing_many_files_isnt_held(tmp_path):
    from skynx.history import Transaction
    src, before, pk = make(tmp_path)
    for i in range(80):
        f = pk.root / "Mods" / "Big Mod" / "textures" / "big" / f"t{i}.dds"
        f.parent.mkdir(parents=True, exist_ok=True)
        f.write_bytes(b"D" + bytes([i]))
    assert len(P.sync(pk)["pulled"]) == 80
    pk = Pack.open(pk.root)
    with Transaction(pk.root, "drop textures") as tx:
        for p in sorted((pk.data_dir / "textures" / "big").iterdir()):
            tx.trash(p)
    r = P.sync(Pack.open(pk.root))
    assert not r["held"] and r["removed"] == 80
    assert not (pk.root / "Mods" / "Big Mod" / "textures").exists()
    # a working pack emptied by accident (a small one too) is held, every time
    import shutil
    for p in pk.data_dir.iterdir():
        shutil.rmtree(p) if p.is_dir() else p.unlink()
    n = sorted(p.name for p in (pk.root / "Mods").rglob("*"))
    for _ in range(2):
        r = P.sync(Pack.open(pk.root))
        assert r["held"] and sorted(p.name for p in (pk.root / "Mods").rglob("*")) == n


def test_switched_off_lines_dont_go_to_the_console(tmp_path):
    """A plugin switched off in Load order ('#Name.esp') stays in the project's
    list, but Pack leaves the line out: it costs no .ccc bytes on the console."""
    from skynx import ccc as C
    src, before, pk = make(tmp_path)
    raw = pk.list_path.read_bytes()
    entries = C.parse_ccc(raw).entries
    name = next(e for e in entries if not e.lower().startswith("cc"))
    pk.list_path.write_bytes(C.edit_lines(raw, {name: "#" + name}))
    pk = Pack.open(pk.root)
    off = [e for e in pk.ccc.entries if e.startswith("#")]
    assert "#" + name in off and pk.list_bytes == pk.ccc.size - sum(len(e) + 2 for e in off)
    P.build(pk)
    out = Pack.open(pk.root / "Switch")
    assert "#" + name not in out.list_entries and name not in out.list_entries
    assert out.ccc.size == pk.list_bytes
    P.build(Pack.open(pk.root))                    # again: nothing changes, nothing set aside
    assert not list((pk.root / ".skynx" / "trash").glob("Switch-*"))
