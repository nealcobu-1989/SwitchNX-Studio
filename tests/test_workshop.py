"""The mod workshop: bench, save to the Library, join BSAs, bring a plugin merge."""
import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tests"))
from skynx import workshop as W  # noqa: E402
from skynx.bsa import read_bsa  # noqa: E402
from skynx.builder import CONVERTED_INFO, add_mod, create_project  # noqa: E402
from skynx.history import Transaction, list_history, undo  # noqa: E402
from skynx.pack import Pack  # noqa: E402
from test_library import fake_plugin  # noqa: E402
from test_requirements import make_bsa, plugin, rec  # noqa: E402

INIS = ROOT / "tests" / "fixtures" / "console-inis"


def files_of(bsa: Path) -> dict[str, bytes]:
    arc = read_bsa(bsa)
    with bsa.open("rb") as f:
        return {e.path.lower(): arc.read_file(e, f) for e in arc.entries}


def mod(folder: Path, name: str, files: dict[str, bytes], tex: dict[str, bytes] | None = None,
        masters=("Skyrim.esm",)) -> Path:
    folder.mkdir(parents=True, exist_ok=True)
    fake_plugin(folder / f"{name}.esp", list(masters))
    make_bsa(folder / f"{name}.bsa", files)
    if tex:
        make_bsa(folder / f"{name} - Textures.bsa", tex)
    return folder


@pytest.fixture()
def bench(tmp_path):
    return W.new_bench(tmp_path / "lib" / "Workshop" / "Suite", "Suite", "suite", "AE", INIS)


def test_bench_is_empty_and_marked(bench):
    assert W.is_bench(bench.root) and bench.mode == "AE"
    assert not bench.plugins and bench.list_path.read_bytes() == b""


def test_bench_without_console_inis(tmp_path):
    b = W.new_bench(tmp_path / "w", "X", "edit", "SE", None)
    assert b.mode == "SE" and b.data_dir.is_dir() and b.inis


def test_save_mod_round_trip(tmp_path, bench):
    m = mod(tmp_path / "src" / "A", "Alpha", {"meshes\\a.nif": b"A"}, {"textures\\a.dds": b"T"})
    rep = W.bring(bench, [m])
    assert rep[0]["ok"]
    out = W.save_mod(Pack.open(bench.root), tmp_path / "lib" / "Converted", "Alpha")
    dest = Path(out["dest"])
    assert sorted(p.name for p in dest.iterdir()) == sorted(["Alpha.esp", "Alpha.bsa", "Alpha - Textures.bsa", CONVERTED_INFO])
    info = json.loads((dest / CONVERTED_INFO).read_text())
    assert info["plugins"] == ["Alpha.esp"] and info["source"]
    # saving again never overwrites: a second copy
    again = W.save_mod(Pack.open(bench.root), tmp_path / "lib" / "Converted", "Alpha")
    assert Path(again["dest"]).name == "Alpha (2)"
    # replace puts the old one in the trash
    rep2 = W.save_mod(Pack.open(bench.root), tmp_path / "lib" / "Converted", "Alpha", replace=dest,
                      trash_root=tmp_path / "lib" / ".trash")
    assert Path(rep2["dest"]) == dest and any((tmp_path / "lib" / ".trash").iterdir())
    with pytest.raises(W.WorkshopError):
        W.save_mod(Pack.open(bench.root), tmp_path / "lib" / "Converted", "bad/name")


def test_join_bsas_in_load_order(tmp_path, bench):
    a = mod(tmp_path / "src" / "A", "Alpha", {"meshes\\shared.nif": b"from A", "meshes\\a.nif": b"A"},
            {"textures\\a.dds": b"TA"})
    b = mod(tmp_path / "src" / "B", "Beta", {"meshes\\shared.nif": b"from B", "meshes\\b.nif": b"B"},
            {"textures\\b.dds": b"TB"})
    W.bring(bench, [a, b])
    bench = Pack.open(bench.root)
    plan = W.merge_plan(bench)
    assert plan["anchor"] == "Alpha.esp" and plan["result"] == ["Alpha.bsa", "Alpha - Textures.bsa"]
    assert plan["overlaps"] == [{"path": "meshes\\shared.nif", "in": ["Alpha.bsa", "Beta.bsa"], "wins": "Beta.bsa"}]
    before = {p.name: p.read_bytes() for p in bench.data_dir.iterdir() if p.is_file()}
    with Transaction(bench.root, "Join BSAs") as tx:
        r = W.merge_bsas(bench, tx)
    bench = Pack.open(bench.root)
    assert sorted(p.name for p in bench.bsas.values()) == ["Alpha - Textures.bsa", "Alpha.bsa"]
    main = files_of(bench.data_dir / "Alpha.bsa")
    assert main["meshes\\shared.nif"] == b"from B"                  # the later mod wins, as in game
    assert set(main) == {"meshes\\shared.nif", "meshes\\a.nif", "meshes\\b.nif"}
    assert set(files_of(bench.data_dir / "Alpha - Textures.bsa")) == {"textures\\a.dds", "textures\\b.dds"}
    assert r["files"] == 5
    # both plugins still there; undo gives back the four archives byte for byte
    assert {"alpha.esp", "beta.esp"} <= set(bench.plugins)
    undo(bench.root, list_history(bench.root)[0]["id"])
    bench = Pack.open(bench.root)
    assert {p.name: p.read_bytes() for p in bench.data_dir.iterdir() if p.is_file()} == before


def test_join_without_plugins_goes_to_the_ini(tmp_path, bench):
    for n, data in (("One", b"1"), ("Two", b"2")):
        d = tmp_path / "src" / n
        make_bsa(d / f"{n}T.bsa", {f"textures\\{n}.dds": data})
        add_mod(bench, d, ini_keys={f"{n}T.bsa": "sResourceArchiveList2"})
        bench = Pack.open(bench.root)
    with Transaction(bench.root, "Join") as tx:
        r = W.merge_bsas(bench, tx, anchor=None, name="Pack")
    bench = Pack.open(bench.root)
    assert r["into"] == ["PackT.bsa"]
    lists = [i.archive_list("sResourceArchiveList2") for i in bench.inis if i.get("Archive", "sResourceArchiveList2") is not None]
    assert all("PackT.bsa" in l and "OneT.bsa" not in l for l in lists)
    out = W.save_mod(bench, tmp_path / "lib" / "Converted", "Pack")
    info = json.loads((Path(out["dest"]) / CONVERTED_INFO).read_text())
    assert info["ini_keys"] == {"PackT.bsa": "sResourceArchiveList2"} and len(info["suite"]) == 2


def test_bring_a_plugin_merge_and_follow_voices(tmp_path, bench):
    a = mod(tmp_path / "src" / "A", "Alpha", {"sound\\voice\\alpha.esp\\npc\\hi.fuz": b"V"})
    b = mod(tmp_path / "src" / "B", "Beta", {"meshes\\b.nif": b"B"})
    W.bring(bench, [a, b])
    bench = Pack.open(bench.root)
    out = tmp_path / "zmerge" / "Suite"
    out.mkdir(parents=True)
    plugin(out / "Suite.esp", [rec("ARMO", 0x800, b"")], snam="Merged Plugin:\r\nAlpha.esp\r\nBeta.esp")
    (out / "seq").mkdir()
    (out / "seq" / "Suite.seq").write_bytes(b"\x00\x08\x00\x00")
    with Transaction(bench.root, "Bring merge") as tx:
        r = W.bring_merge(bench, out, tx)
    bench = Pack.open(bench.root)
    assert r["inside"] == ["Alpha.esp", "Beta.esp"] and set(bench.plugins) == {"suite.esp"}
    assert bench.list_path.read_text().strip() == "Suite.esp"
    assert (bench.data_dir / "seq" / "Suite.seq").exists()
    # the BSAs of the merged plugins now load with nothing: join them under the merge
    plan = W.merge_plan(bench, retarget={"alpha.esp": "Suite.esp"})
    assert plan["anchor"] == "Suite.esp"
    with Transaction(bench.root, "Join") as tx:
        W.merge_bsas(bench, tx, retarget={"alpha.esp": "Suite.esp", "beta.esp": "Suite.esp"})
    bench = Pack.open(bench.root)
    assert set(files_of(bench.data_dir / "Suite.bsa")) == {"sound\\voice\\suite.esp\\npc\\hi.fuz", "meshes\\b.nif"}


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
    api._settings["inis_dir"] = str(INIS)

    def run(method, *a):
        r = getattr(api, method)(*a)
        assert r.get("ok") is not False, r
        while api.progress()["busy"]:
            time.sleep(0.05)
        return api.progress()
    return api, run


def test_app_suite_flow(tmp_path, monkeypatch):
    api, run = _api(tmp_path, monkeypatch)
    a = mod(tmp_path / "src" / "A", "Alpha", {"meshes\\shared.nif": b"A"}, {"textures\\a.dds": b"T"})
    b = mod(tmp_path / "src" / "B", "Beta", {"meshes\\shared.nif": b"B"})
    p = run("workshop_new", "suite", "Mi Suite", "AE", [str(a), str(b)])
    assert p["error"] is None
    res = p["result"]
    assert res["pack"]["bench"]["name"] == "Mi Suite" and all(r["ok"] for r in res["reports"])
    assert Path(res["pack"]["root"]).parent == tmp_path / "lib" / "Workshop"
    v = api.workshop_view()
    assert v["ok"] and v["join"]["anchor"] == "Alpha.esp" and v["join"]["n_overlaps"] == 1
    assert api.workshop_join_plan("")["plan"]["anchor"] is None              # none: listed in the ini
    assert api.workshop_join_plan(None)["plan"]["anchor"] == "Alpha.esp"
    p = run("workshop_join", "Alpha.esp", "")
    assert p["error"] is None and p["result"]["join"]["into"] == ["Alpha.bsa", "Alpha - Textures.bsa"]
    p = run("workshop_save", "Mi Suite", False)
    saved = Path(p["result"]["saved"]["dest"])
    assert saved == tmp_path / "lib" / "Converted" / "Mi Suite"
    info = json.loads((saved / CONVERTED_INFO).read_text())
    assert [c["name"] for c in info["suite"]] == ["A", "B"]
    # the bench is listed, and discarding it leaves the saved suite alone
    assert api.workshop_list()["benches"][0]["name"] == "Mi Suite"
    assert api.workshop_discard()["ok"] and saved.exists()
    assert api.workshop_list()["benches"] == []
    # the Library lists the suite as converted, and the picker sees it
    assert any(r["path"] == str(saved) for r in api.library_mods()["rows"])


def test_app_edit_replace_goes_to_trash(tmp_path, monkeypatch):
    api, run = _api(tmp_path, monkeypatch)
    conv = tmp_path / "lib" / "Converted" / "Alpha"
    mod(conv, "Alpha", {"meshes\\a.nif": b"A"})
    run("workshop_new", "edit", "Alpha", "AE", [str(conv)])
    r = api.rename_plugin("Alpha.esp", "Alfa")
    assert r["ok"]
    p = run("workshop_save", "Alpha", True)
    assert Path(p["result"]["saved"]["dest"]) == conv
    assert sorted(x.name for x in conv.iterdir()) == ["Alfa.bsa", "Alfa.esp", CONVERTED_INFO]
    trash = tmp_path / "lib" / ".trash"
    assert any("Alpha" in x.name for x in trash.iterdir())
    # converting on a bench doesn't leave an automatic copy: saving is explicit
    assert not (tmp_path / "lib" / "Converted" / "Alpha (2)").exists()


def test_close_pack_forgets_the_open_one(tmp_path, monkeypatch):
    api, run = _api(tmp_path, monkeypatch)
    run("workshop_new", "convert", "Convert", "SE", [])
    assert api.current() is not None
    assert api.close_pack()["ok"] and api.current() is None


# ------------------------------------------------------------------ review fixes
def test_split_parts_load_from_the_ini(tmp_path, bench, monkeypatch):
    a = mod(tmp_path / "src" / "A", "Alpha", {"meshes\\a.nif": b"A" * 100})
    b = mod(tmp_path / "src" / "B", "Beta", {"meshes\\b.nif": b"B" * 100})
    W.bring(bench, [a, b])
    bench = Pack.open(bench.root)
    monkeypatch.setattr(W, "BSA_SPLIT", 150)
    with Transaction(bench.root, "J") as tx:
        r = W.merge_bsas(bench, tx)
    bench = Pack.open(bench.root)
    assert r["into"] == ["Alpha.bsa", "Alpha2.bsa"]
    assert "Alpha2.bsa" in bench.archive_lists()["sResourceArchiveList"]


def test_merged_components_keep_their_order(tmp_path, bench):
    z = mod(tmp_path / "src" / "Z", "Zeta", {"meshes\\s.nif": b"Z"})
    a = mod(tmp_path / "src" / "A", "Alpha", {"meshes\\s.nif": b"A"})
    W.bring(bench, [z, a])
    bench = Pack.open(bench.root)
    assert W.merge_plan(bench)["overlaps"][0]["wins"] == "Alpha.bsa"
    out = tmp_path / "zm" / "M"
    out.mkdir(parents=True)
    plugin(out / "M.esp", [rec("ARMO", 0x800, b"")], snam="Merged Plugin:\r\nZeta.esp\r\nAlpha.esp")
    with Transaction(bench.root, "bm") as tx:
        W.bring_merge(bench, out, tx)
    bench = Pack.open(bench.root)
    plan = W.merge_plan(bench, retarget={"zeta.esp": "M.esp", "alpha.esp": "M.esp"})
    assert plan["overlaps"][0]["wins"] == "Alpha.bsa" and plan["anchor"] == "M.esp"


def test_ini_name_with_comma_is_refused(tmp_path):
    bench = W.new_bench(tmp_path / "lib" / "Workshop" / "S", "Arms, Armor", "suite", "AE", INIS)
    for n in ("One", "Two"):
        d = tmp_path / "src" / n
        make_bsa(d / f"{n}T.bsa", {f"textures\\{n}.dds": b"x"})
        add_mod(bench, d, ini_keys={f"{n}T.bsa": "sResourceArchiveList2"})
        bench = Pack.open(bench.root)
    with Transaction(bench.root, "J") as tx, pytest.raises(W.WorkshopError):
        W.merge_bsas(bench, tx, anchor=None)


def test_a_new_app_version_reopens_the_last_pack(tmp_path, monkeypatch):
    """The user replaces the .exe and opens it: it goes back to the pack that
    was open, unless he closed it on purpose or turned the option off."""
    api, run = _api(tmp_path, monkeypatch)
    pk = create_project(tmp_path / "pk", "AE", INIS, "none")
    run("open_pack", str(pk))
    assert api.ui_prefs()["reopen"] == str(pk)
    api2, _ = _api(tmp_path, monkeypatch)            # a fresh start reads the saved settings
    assert api2.ui_prefs()["reopen"] == str(pk) and api2.current() is None
    api2.set_ui_pref("reopen_last", False)
    assert api2.ui_prefs()["reopen"] is None
    api2.set_ui_pref("reopen_last", True)
    assert api2.close_pack()["ok"]
    assert api2.ui_prefs()["reopen"] is None         # closed on purpose


def test_reminders_before_packing(tmp_path, monkeypatch):
    """Pack says what the usual routine hasn't done: here LOOT never ran."""
    api, run = _api(tmp_path, monkeypatch)
    pk = create_project(tmp_path / "pk", "AE", INIS, "none")
    run("open_pack", str(pk))
    r = run("pack_reminders")["result"]
    kinds = [i["kind"] for i in r["items"]]
    assert "loot_never" in kinds and "critico" not in kinds and "audit" in r


def test_doctor_report_and_game_list_in_settings(tmp_path, monkeypatch):
    api, run = _api(tmp_path, monkeypatch)
    pk = create_project(tmp_path / "pk", "AE", INIS, "none")
    run("open_pack", str(pk))
    r = api.doctor_report()
    assert r["ok"] and r["md"].startswith("# Doctor report: ") and r["name"].endswith(" - Doctor.md")
    st = api.state()
    assert "vanilla_list" in st and st["vanilla_status"] in ("unset", "missing", "empty", "ok")
    assert api.vanilla_forget()["n"] == 0
