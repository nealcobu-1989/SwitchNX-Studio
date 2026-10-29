"""The pack being created: exact copy, goes / doesn't go, rename, create the modpack."""
import os
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tests"))
from skynx import draft as DR  # noqa: E402
from skynx.builder import mods_view  # noqa: E402
from skynx.history import Transaction, list_history, undo  # noqa: E402
from skynx.ini import set_archive_list  # noqa: E402
from skynx.pack import Pack  # noqa: E402
from test_library import EMPTY_BSA, fake_plugin  # noqa: E402
from test_xtools import ae_pack  # noqa: E402


def snapshot(pack: Pack) -> dict:
    out = {}
    for d in (pack.base_dir, pack.aoc_dir):
        for p in sorted(d.rglob("*")):
            if p.is_file():
                out[p.relative_to(pack.root).as_posix()] = p.read_bytes()
    return out


def avner_like(tmp_path) -> Pack:
    pack = ae_pack(tmp_path)
    data = pack.data_dir
    fake_plugin(data / "Big Mod.esp", ["Skyrim.esm"])
    (data / "Big Mod.bsa").write_bytes(EMPTY_BSA)
    (data / "LooseT.bsa").write_bytes(EMPTY_BSA)          # loaded from the ini
    ccc = pack.list_path
    ccc.write_bytes(ccc.read_bytes() + b"Big Mod.esp\r\n")
    for ini in pack.ini_paths:
        raw = ini.read_bytes()
        from skynx.ini import parse_ini
        if parse_ini(raw).get("Archive", "sResourceArchiveList2") is not None:
            cur = parse_ini(raw).archive_list("sResourceArchiveList2")
            ini.write_bytes(set_archive_list(raw, "sResourceArchiveList2", cur + ["LooseT.bsa"]))
    return Pack.open(pack.root)


def test_start_from_pack_is_identical(tmp_path):
    src = avner_like(tmp_path / "src")
    before = snapshot(src)
    d = DR.start_from_pack(src, tmp_path / "lib" / "Drafts" / "Mine", "Mine")
    assert snapshot(d) == {k: v for k, v in before.items()}       # every file, byte for byte
    assert snapshot(src) == before                                 # source untouched
    assert DR.is_draft(d.root) and not DR.is_draft(src.root)
    with pytest.raises(DR.DraftError):                             # never on top of something
        DR.start_from_pack(src, tmp_path / "lib" / "Drafts" / "Mine", "Mine")


def test_doesnt_go_and_goes_back_byte_for_byte(tmp_path):
    src = avner_like(tmp_path / "src")
    d = DR.start_from_pack(src, tmp_path / "Drafts" / "Mine", "Mine")
    before = snapshot(d)
    row = next(r for r in mods_view(d) if r["id"] == "Big Mod.esp")
    with Transaction(d.root, "out") as tx:
        r = DR.exclude(d, row, tx)
    assert r["changed"]
    d = Pack.open(d.root)
    assert "Big Mod.esp" not in d.list_path.read_text()
    assert (d.data_dir / "Big Mod.esp").exists()                  # files stay while you decide
    v = DR.view(d, mods_view(d))
    gone = next(x for x in v["rows"] if x["id"] == "Big Mod.esp")
    assert gone["goes"] is False and v["goes"] == v["total"] - 1
    assert v["ccc_bytes"] == len(before[d.list_path.relative_to(d.root).as_posix()]) - len(b"Big Mod.esp\r\n")
    # an ini-loaded BSA
    row = next(r for r in mods_view(d) if r["id"] == "LooseT.bsa")
    with Transaction(d.root, "out2") as tx:
        DR.exclude(d, row, tx)
    d = Pack.open(d.root)
    assert all("looset.bsa" not in ", ".join(i.archive_list("sResourceArchiveList2")).lower()
               for i in d.inis if i.get("Archive", "sResourceArchiveList2") is not None)
    for rid in ("LooseT.bsa", "Big Mod.esp"):
        with Transaction(d.root, "in") as tx:
            DR.include(d, rid, tx)
        d = Pack.open(d.root)
    after = snapshot(d)
    assert after == before                                         # exactly as it was
    assert DR.load(d.root)["excluded"] == {}


def test_master_users_are_named(tmp_path):
    src = avner_like(tmp_path / "src")
    d = DR.start_from_pack(src, tmp_path / "Drafts" / "Mine", "Mine")
    row = next(r for r in mods_view(d) if r["id"] == "Tiny.esp")
    with Transaction(d.root, "x") as tx:
        r = DR.exclude(d, row, tx)
    assert r.get("refused") and r["users"] == ["Patch.esp"]


def test_undo_restores_the_parked_state(tmp_path):
    src = avner_like(tmp_path / "src")
    d = DR.start_from_pack(src, tmp_path / "Drafts" / "Mine", "Mine")
    before = snapshot(d)
    row = next(r for r in mods_view(d) if r["id"] == "Big Mod.esp")
    with Transaction(d.root, "Doesn't go: Big Mod.esp") as tx:
        DR.exclude(d, row, tx)
    undo(d.root, list_history(d.root)[0]["id"])
    d = Pack.open(d.root)
    assert snapshot(d) == before and DR.load(d.root)["excluded"] == {}


def test_create_modpack_leaves_out_what_doesnt_go(tmp_path):
    src = avner_like(tmp_path / "src")
    d = DR.start_from_pack(src, tmp_path / "Drafts" / "Mine", "Mine")
    row = next(r for r in mods_view(d) if r["id"] == "Big Mod.esp")
    with Transaction(d.root, "out") as tx:
        DR.exclude(d, row, tx)
    d = Pack.open(d.root)
    out = DR.create_modpack(d, tmp_path / "Packs" / "Mine v1")
    final = Pack.open(Path(out["dest"]))
    names = {p.name for p in final.data_dir.iterdir()}
    assert "Big Mod.esp" not in names and "Big Mod.bsa" not in names and "Tiny.esp" in names
    assert final.list_path.read_bytes() == d.list_path.read_bytes()
    assert not (final.root / ".skynx" / "history").exists() and not DR.is_draft(final.root)
    assert (d.data_dir / "Big Mod.esp").exists()                    # the draft keeps it
    with pytest.raises(DR.DraftError):
        DR.create_modpack(d, tmp_path / "Packs" / "Mine v1")


def test_catalog_adds_into_the_open_pack(tmp_path):
    from skynx import catalog as CT
    from skynx import library as L
    lib = tmp_path / "lib"
    L.ensure(lib)
    (lib / "Packs").mkdir()                       # a Library from before projects
    other = avner_like(tmp_path / "x")
    os.rename(other.root, lib / "Packs" / "Other")
    d = DR.start_from_pack(Pack.open(lib / "Packs" / "Other"), lib / "Drafts" / "Mine", "Mine")
    # remove Big Mod from the draft so the catalog can bring it back
    from skynx.builder import remove_mod
    remove_mod(d, "Big Mod.esp")
    d = Pack.open(d.root)
    cat = CT.build_catalog(lib, cache_dir=tmp_path / "cache")
    assert all("Drafts" not in p["path"] for p in cat["packs"])      # drafts aren't sources
    e = next(x for x in cat["entries"] if x["name"].lower().startswith("big mod"))
    v = e["versions"][0]
    tiny = next(x for x in cat["entries"] if x["name"].lower().startswith("tiny"))
    picks = [{"key": e["key"], "pack_path": v["pack_path"], "unit_id": v["unit_id"]},
             {"key": tiny["key"], "pack_path": tiny["versions"][0]["pack_path"],
              "unit_id": tiny["versions"][0]["unit_id"]}]
    plan = CT.plan_build(cat, picks, {"into": str(d.root)})
    st = {i["name"]: i["status"] for i in plan["items"]}
    assert any(s == "present" for n, s in st.items() if n.lower().startswith("tiny"))
    out = CT.execute_build(cat, picks, {"into": str(d.root)}, None)
    assert out["dest"] == str(d.root)
    d = Pack.open(d.root)
    assert (d.data_dir / "Big Mod.esp").exists() and "Big Mod.esp" in d.list_path.read_text()


# ------------------------------------------------------------------ through the app
def _api(tmp_path, monkeypatch):
    import importlib
    import time
    monkeypatch.setenv("APPDATA", str(tmp_path / "appdata"))
    monkeypatch.setenv("SKYNX_LIBRARY", str(tmp_path / "lib"))
    sys.path.insert(0, str(ROOT / "app"))
    import api as A
    importlib.reload(A)
    api = A.Api()

    def run(method, *a):
        r = getattr(api, method)(*a)
        assert r.get("ok") is not False, r
        while api.progress()["busy"]:
            time.sleep(0.05)
        return api.progress()
    return api, run


def test_app_flow_start_toggle_rename_create(tmp_path, monkeypatch):
    api, run = _api(tmp_path, monkeypatch)
    src = avner_like(tmp_path / "src")
    p = run("draft_start", str(src.root), "Mine")
    assert p["error"] is None and p["result"]["pack"]["draft"]["name"] == "Mine"
    assert Path(p["result"]["pack"]["root"]) == tmp_path / "lib" / "Drafts" / "Mine"
    v = api.draft_view()["draft"]
    assert v["goes"] == v["total"]
    # doesn't go: the Doctor stays quiet about it and says why
    r = api.draft_toggle("Big Mod.esp", False)
    assert r["ok"] and r["draft"]["goes"] == v["total"] - 1
    subjects = [f["subject"] for f in r["audit"]["findings"]]
    assert "Big Mod.esp" not in subjects and "Big Mod.bsa" not in subjects
    assert any(f["code"] == "draft-parked" for f in r["audit"]["findings"])
    # a master can't leave alone
    r = api.draft_toggle("Tiny.esp", False)
    assert not r["ok"] and r["users"] == ["Patch.esp"]
    # rename with preview: .ccc bytes and the BSA follow
    pv = api.rename_preview("Patch.esp", "Ryn's Patch")
    assert pv["new"] == "Ryn's Patch.esp" and pv["ccc_delta"] == len("Ryn's Patch.esp") - len("Patch.esp")
    assert pv["safe"] == "Ryns Patch.esp" and pv["problems"]
    r = api.rename_plugin("Patch.esp", "Short")
    assert r["ok"] and r["new"] == "Short.esp"
    d = Pack.open(tmp_path / "lib" / "Drafts" / "Mine")
    assert (d.data_dir / "Short.esp").exists() and "Short.esp" in d.list_path.read_text()
    assert not api.rename_plugin("Short.esp", "Tiny")["ok"]          # already exists
    # create the modpack
    p = run("draft_create", "Mine v1", "")
    c = p["result"]["created"]
    assert Path(c["dest"]) == tmp_path / "lib" / "Packs" / "Mine v1"
    names = {x.name for x in Pack.open(Path(c["dest"])).data_dir.iterdir()}
    assert "Big Mod.esp" not in names and "Short.esp" in names
    # the Library shows the draft as being created
    from skynx import library as L
    rows = {r["name"]: r for r in L.list_library(tmp_path / "lib", health=False)}
    assert rows["Mine"]["draft"] and not rows["Mine v1"].get("draft")


def test_parked_row_keeps_its_place(tmp_path):
    src = avner_like(tmp_path / "src")
    d = DR.start_from_pack(src, tmp_path / "Drafts" / "Mine", "Mine")
    ids = [r["id"] for r in mods_view(d)]
    row = next(r for r in mods_view(d) if r["id"] == "Big Mod.esp")
    with Transaction(d.root, "out") as tx:
        DR.exclude(d, row, tx)
    d = Pack.open(d.root)
    assert [r["id"] for r in DR.view(d, mods_view(d))["rows"]] == ids


# ------------------------------------------------------------------ review fixes
def test_added_mod_row_is_not_duplicated(tmp_path):
    from skynx.builder import add_mod
    p = ae_pack(tmp_path / "src")
    m = tmp_path / "m" / "Cool"
    fake_plugin(m / "Cool.esp", ["Skyrim.esm"])
    (m / "Cool.bsa").write_bytes(EMPTY_BSA)
    add_mod(p, m)
    d = DR.start_from_pack(Pack.open(p.root), tmp_path / "Drafts" / "D", "D")
    n = len(DR.view(d, mods_view(d))["rows"])
    row = next(r for r in mods_view(d) if r["id"] == "Cool")
    with Transaction(d.root, "x") as tx:
        DR.exclude(d, row, tx)
    d = Pack.open(d.root)
    v = DR.view(d, mods_view(d))
    assert [(r["id"], r["goes"]) for r in v["rows"] if r["id"] == "Cool"] == [("Cool", False)]
    assert v["total"] == n and v["goes"] == n - 1


def test_putting_back_in_any_order_keeps_the_order(tmp_path):
    p = ae_pack(tmp_path / "src")
    for n in ("A", "B", "C"):
        fake_plugin(p.data_dir / f"{n}.esp", ["Skyrim.esm"])
    p.list_path.write_bytes(p.list_path.read_bytes() + b"A.esp\r\nB.esp\r\nC.esp\r\n")
    d = DR.start_from_pack(Pack.open(p.root), tmp_path / "Drafts" / "D", "D")
    before = d.list_path.read_bytes()
    for rid in ("A.esp", "B.esp", "C.esp"):
        row = next(r for r in mods_view(d) if r["id"] == rid)
        with Transaction(d.root, "x") as tx:
            DR.exclude(d, row, tx)
        d = Pack.open(d.root)
    import itertools
    base = snapshot(d)
    for perm in itertools.permutations(("A.esp", "B.esp", "C.esp")):
        for rid in perm:
            with Transaction(d.root, "y") as tx:
                DR.include(d, rid, tx)
            d = Pack.open(d.root)
        assert d.list_path.read_bytes() == before, perm
        for rid in ("A.esp", "B.esp", "C.esp"):          # park them again for the next order
            row = next(r for r in mods_view(d) if r["id"] == rid)
            with Transaction(d.root, "x") as tx:
                DR.exclude(d, row, tx)
            d = Pack.open(d.root)
        assert snapshot(d) == base


def test_a_plugin_cant_go_without_its_master(tmp_path, monkeypatch):
    api, run = _api(tmp_path, monkeypatch)
    src = avner_like(tmp_path / "src")
    run("draft_start", str(src.root), "Mine")
    assert api.draft_toggle("Patch.esp", False)["ok"]
    assert api.draft_toggle("Tiny.esp", False)["ok"]
    r = api.draft_toggle("Patch.esp", True)
    assert not r["ok"] and r["needs"] == ["Tiny.esp"] and r["parked"] == ["Tiny.esp"]
    # forcing it shows the Doctor's master finding (not hidden as "parked")
    r = api.draft_toggle("Patch.esp", True, True)
    assert r["ok"] and any(f["subject"].startswith("Patch.esp") and "master" in f["code"] for f in r["audit"]["findings"])
    # and Create modpack refuses
    p = run("draft_create", "Out", "")
    assert p["error"] and "Tiny.esp" in p["error"]
    # the catalog doesn't count a parked plugin as present
    from skynx import catalog as CT
    st = CT._pack_state(Path(api._pack.root), {})
    assert "tiny.esp" not in {x.lower() for x in st["have"]}


def test_create_refuses_inside_the_draft(tmp_path):
    src = avner_like(tmp_path / "src")
    d = DR.start_from_pack(src, tmp_path / "Drafts" / "D", "D")
    with pytest.raises(DR.DraftError):
        DR.create_modpack(d, d.root / "out")


# ------------------------------------------------------------------ hard links
def test_draft_files_are_linked_and_changes_dont_reach_the_source(tmp_path):
    from skynx.bsafix import safe_rename
    src = avner_like(tmp_path / "src")
    before = snapshot(src)
    d = DR.start_from_pack(src, tmp_path / "Drafts" / "D", "D")
    assert os.path.samefile(d.data_dir / "Big Mod.bsa", src.data_dir / "Big Mod.bsa")
    assert DR.load(d.root)["files"]["linked"] > 0
    # every kind of change the app makes in the draft
    row = next(r for r in mods_view(d) if r["id"] == "LooseT.bsa")
    with Transaction(d.root, "out") as tx:
        DR.exclude(d, row, tx)
    d = Pack.open(d.root)
    with Transaction(d.root, "rename") as tx:
        safe_rename(d, "Big Mod.esp", "Other.esp", tx)
    d = Pack.open(d.root)
    with Transaction(d.root, "edit") as tx:
        tx.write_bytes(d.data_dir / "Tiny.esp", (d.data_dir / "Tiny.esp").read_bytes() + b"X")
    assert snapshot(src) == before                                  # the source pack never changed
    # the created modpack links to the draft; changing the final one doesn't touch the draft
    out = DR.create_modpack(Pack.open(d.root), tmp_path / "Packs" / "Final")
    assert out["linked"] > 0
    fin = Pack.open(Path(out["dest"]))
    assert os.path.samefile(fin.data_dir / "Tiny.esp", d.data_dir / "Tiny.esp")
    draft_tiny = (d.data_dir / "Tiny.esp").read_bytes()
    with Transaction(fin.root, "edit") as tx:
        tx.write_bytes(fin.data_dir / "Tiny.esp", b"changed")
    assert (d.data_dir / "Tiny.esp").read_bytes() == draft_tiny
    assert snapshot(src) == before


def test_without_links_or_when_linking_fails_it_copies(tmp_path, monkeypatch):
    src = avner_like(tmp_path / "src")
    d = DR.start_from_pack(src, tmp_path / "Drafts" / "A", "A", link=False)
    assert not os.path.samefile(d.data_dir / "Tiny.esp", src.data_dir / "Tiny.esp")

    def no_link(*a, **k):
        raise OSError("different drive")
    monkeypatch.setattr(os, "link", no_link)
    d2 = DR.start_from_pack(src, tmp_path / "Drafts" / "B", "B")
    assert DR.load(d2.root)["files"] == {"linked": 0, "copied": DR.load(d2.root)["files"]["copied"]}
    assert snapshot(d2) == snapshot(src)


def test_undo_never_writes_into_a_linked_file(tmp_path):
    src = avner_like(tmp_path / "src")
    before = snapshot(src)
    d = DR.start_from_pack(src, tmp_path / "Drafts" / "D", "D")
    target = d.data_dir / "Tiny.esp"
    # a change that fails after the backup but before the swap: the rollback restores
    # a file that is still the linked one
    with pytest.raises(RuntimeError), Transaction(d.root, "interrupted") as tx:
        tx.before_change(target)
        raise RuntimeError("boom")
    assert snapshot(src) == before
    assert not os.path.samefile(target, src.data_dir / "Tiny.esp")    # it got its own file
