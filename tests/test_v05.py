"""v0.5 additions: loose plugin/BSA intake, Library removal, API guards."""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "app"))
from skynx import library as L  # noqa: E402
from skynx.intake import bundle_to_folder, loose_bundle  # noqa: E402
from test_library import EMPTY_BSA, fake_plugin, mini_pack, zip_dir  # noqa: E402


def test_loose_bundle_takes_companions_only(tmp_path):
    d = tmp_path / "dl"
    fake_plugin(d / "Mod.esp", ["Skyrim.esm"])
    (d / "Mod.bsa").write_bytes(EMPTY_BSA)
    (d / "Mod - Textures.bsa").write_bytes(EMPTY_BSA)
    (d / "Modern.bsa").write_bytes(EMPTY_BSA)          # different mod, same prefix
    fake_plugin(d / "Other.esp", ["Skyrim.esm"])
    names = sorted(p.name for p in loose_bundle(d / "Mod.esp"))
    assert names == ["Mod - Textures.bsa", "Mod.bsa", "Mod.esp"]
    assert loose_bundle(d) == [] and loose_bundle(d / "nope.txt") == []
    out = bundle_to_folder(d / "Mod.esp", tmp_path / "staged")
    assert sorted(p.name for p in out.iterdir()) == names


def test_import_loose_plugin_and_remove(tmp_path):
    lib = tmp_path / "lib"
    d = tmp_path / "dl"
    fake_plugin(d / "Mod.esp", ["Skyrim.esm"])
    (d / "Mod.bsa").write_bytes(EMPTY_BSA)
    e = L.import_mod(d / "Mod.esp", lib)
    assert Path(e["path"]) == lib / "Mods" / "Mod"
    assert sorted(p.name for p in Path(e["path"]).iterdir()) == ["Mod.bsa", "Mod.esp"]
    rows = L.list_library(lib, health=False)
    row = next(r for r in rows if r["path"] == e["path"])
    assert row["owned"] is True
    # an owned copy is deleted (forgetting alone would let the listing find it again)
    assert L.remove(lib, Path(e["path"]))["deleted"] is True
    assert not Path(e["path"]).exists()
    assert all(r["path"] != e["path"] for r in L.list_library(lib, health=False))
    # an external folder only leaves the list
    L.add_external(lib, d, kind="mod")
    assert L.remove(lib, d)["deleted"] is False and d.exists()
    assert all(r["path"] != str(d) for r in L.list_library(lib, health=False))


def test_imported_pack_zip_is_owned_and_removable(tmp_path):
    lib = tmp_path / "lib"
    mp = mini_pack(tmp_path / "build" / "Tiny Pack")
    z = zip_dir(mp, tmp_path / "Tiny Pack.zip")
    e = L.import_pack(z, lib)
    assert L.owned(lib, Path(e["path"]))
    assert not L.owned(lib, lib) and not L.owned(lib, tmp_path)
    L.remove(lib, Path(e["path"]))
    assert not Path(e["path"]).exists() and z.exists()


def test_api_guards(tmp_path, monkeypatch):
    monkeypatch.setenv("APPDATA", str(tmp_path / "appdata"))
    monkeypatch.setenv("SKYNX_LIBRARY", str(tmp_path / "lib"))
    import importlib
    import api as A
    importlib.reload(A)
    api = A.Api()

    def run(method, *a):
        r = getattr(api, method)(*a)
        assert r.get("ok") is not False, r
        while api.progress()["busy"]:
            import time
            time.sleep(0.05)
        return api.progress()

    a = mini_pack(tmp_path / "A")
    b = mini_pack(tmp_path / "B")
    src = mini_pack(tmp_path / "S")
    fake_plugin(src / "01000A10041EA000/romfs/Data/Extra.esp", ["Skyrim.esm"])
    ccc = src / "01000A10041EB009/romfs/Skyrim_aoc.ccc"
    ccc.write_bytes(ccc.read_bytes() + b"Extra.esp\r\n")
    # opening a zip is refused instead of opening an empty fake pack
    z = zip_dir(a, tmp_path / "A.zip")
    p = run("open_pack", str(z))
    assert p["error"] and api._pack is None
    # a plan made for A is dropped when B is opened, so it can't land in A
    assert not run("open_pack", str(a))["error"]
    lst = run("transfer_list", str(src))["result"]
    uid = next(u["id"] for u in lst["units"] if u["name"] == "Extra.esp")
    plan = run("transfer_plan", str(src), [uid])["result"]
    assert plan["ok"]
    assert not run("open_pack", str(b))["error"]
    assert api._transfer is None
    out = run("transfer_apply")
    assert out["error"]
    assert not (a / "01000A10041EA000/romfs/Data/Extra.esp").exists()
    assert not (b / "01000A10041EA000/romfs/Data/Extra.esp").exists()
    # a loose plugin goes in through its companions
    d = tmp_path / "dl"
    fake_plugin(d / "Lone.esp", ["Skyrim.esm"])
    (d / "Lone.bsa").write_bytes(EMPTY_BSA)
    assert not run("precheck", str(d / "Lone.esp"))["error"]
    r = run("add_mod", str(d / "Lone.esp"))
    assert not r["error"], r
    data = b / "01000A10041EA000/romfs/Data"
    assert (data / "Lone.esp").exists() and (data / "Lone.bsa").exists()


def _api(tmp_path, monkeypatch):
    monkeypatch.setenv("APPDATA", str(tmp_path / "appdata"))
    monkeypatch.setenv("SKYNX_LIBRARY", str(tmp_path / "lib"))
    import importlib
    import api as A
    importlib.reload(A)
    api = A.Api()

    def run(method, *a):
        r = getattr(api, method)(*a)
        assert r.get("ok") is not False, r
        import time
        while api.progress()["busy"]:
            time.sleep(0.05)
        return api.progress()
    return api, run, A


def test_transfer_gives_safe_names(tmp_path, monkeypatch):
    api, run, _A = _api(tmp_path, monkeypatch)
    dst = mini_pack(tmp_path / "D")
    src = mini_pack(tmp_path / "S")
    data = src / "01000A10041EA000/romfs/Data"
    fake_plugin(data / "Ryn's Thing.esp", ["Skyrim.esm"])
    (data / "Ryn's Thing.bsa").write_bytes(EMPTY_BSA)
    ccc = src / "01000A10041EB009/romfs/Skyrim_aoc.ccc"
    ccc.write_bytes(ccc.read_bytes() + "Ryn's Thing.esp\r\n".encode())
    assert not run("open_pack", str(dst))["error"]
    units = run("transfer_list", str(src))["result"]["units"]
    uid = next(u["id"] for u in units if u["name"] == "Ryn's Thing.esp")
    assert run("transfer_plan", str(src), [uid])["result"]["ok"]
    out = run("transfer_apply")
    assert not out["error"], out
    assert out["result"]["result"]["safe_renamed"] == [["Ryn's Thing.esp", "Ryns Thing.esp"]]
    d = dst / "01000A10041EA000/romfs/Data"
    assert (d / "Ryns Thing.esp").exists() and (d / "Ryns Thing.bsa").exists()
    assert not (d / "Ryn's Thing.esp").exists()
    assert b"Ryns Thing.esp" in (dst / "01000A10041EB009/romfs/Skyrim_aoc.ccc").read_bytes()
    # the mod record follows the new names, so the Mods page and Remove still work
    import json
    recs = json.loads((dst / ".skynx/mods.json").read_text(encoding="utf-8"))
    rec = next(r for r in recs.values() if "Ryns Thing.esp" in r.get("plugins", []))
    assert "Ryns Thing.bsa" in rec["bsas"]
    row = next(m for m in api.mods() if "Ryns Thing.esp" in m["plugins"])
    assert run("remove_mod", row["id"]) is not None
    assert not (d / "Ryns Thing.esp").exists()


def test_loot_classify_and_doctor_notes(tmp_path, monkeypatch):
    import shutil
    api, run, A = _api(tmp_path, monkeypatch)
    pack = mini_pack(tmp_path / "P")
    cache = A.settings_path().parent / "loot"
    cache.mkdir(parents=True, exist_ok=True)
    shutil.copy(ROOT / "tests/fixtures/loot/masterlist.yaml", cache / "masterlist.yaml")
    assert not run("open_pack", str(pack))["error"]
    codes = {f["code"] for f in api.current()["audit"]["findings"]}
    assert "loot-unknown" in codes                       # Tiny.esp isn't in the masterlist
    r = run("loot_classify", {"Tiny.esp": {"group": "Fixes"}})
    assert not r["error"], r
    v = r["result"]
    assert all(u["name"] != "Tiny.esp" for u in v["unknown"])
    assert v["chosen"]["Tiny.esp"]["group"] == "Fixes"
    assert v["friendly"] and v["all_groups"]
    # clearing the choice makes it unknown again
    v = run("loot_classify", {"Tiny.esp": {"group": ""}})["result"]
    assert any(u["name"] == "Tiny.esp" for u in v["unknown"])


def test_nexus_download_to_recipe(tmp_path, monkeypatch):
    api, run, A = _api(tmp_path, monkeypatch)
    from skynx import nexus as NX
    src = tmp_path / "srcmod"
    fake_plugin(src / "Nexy.esp", ["Skyrim.esm"])
    (src / "Nexy.bsa").write_bytes(EMPTY_BSA)
    import zipfile
    blob = tmp_path / "blob.zip"
    with zipfile.ZipFile(blob, "w") as z:
        for f in src.iterdir():
            z.write(f, f.name)

    class FakeClient:
        def __init__(self, key, **kw):
            assert key == "K"
        def validate(self):
            return {"name": "alejo", "is_premium": False}
        def mod(self, mid):
            return {"name": "Nexy Mod", "version": "1.0"}
        def file(self, mid, fid):
            return {"file_name": "Nexy-123-1-0.zip", "version": "1.0", "category_name": "MAIN"}
        def download_links(self, link):
            return [{"name": "CDN", "short_name": "cdn", "url": "https://x/Nexy.zip"}]
        def md5_search(self, md5):
            return []

    def fake_download(url, dest, progress=None, filename=None, expected_md5=None, label=None, **kw):
        out = Path(dest) / filename
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_bytes(blob.read_bytes())
        return out
    monkeypatch.setattr(NX, "Client", FakeClient)
    monkeypatch.setattr(NX, "download", fake_download)
    calls = []
    monkeypatch.setattr(NX, "check_updates", lambda cl, mods: calls.append(mods) or [
        {"mod_id": m["mod_id"], "file_id": m["file_id"], "current": "1.0", "latest": "1.1",
         "latest_file_id": 999, "name": m["name"], "status": "update", "changed": True, "error": None}
        for m in mods])
    assert run("nexus_set_key", "K")["result"]["has_key"]
    pack = mini_pack(tmp_path / "P")
    assert not run("open_pack", str(pack))["error"]
    r = run("nexus_download", "nxm://skyrimspecialedition/mods/123/files/456?key=a&expires=9999999999&user_id=1")
    assert not r["error"], r
    path = r["result"]["path"]
    assert r["result"]["nexus"]["mod_id"] == 123 and Path(path + ".nexus.json").exists()
    assert not run("add_mod", path)["error"]
    import json
    recs = json.loads((pack / ".skynx/mods.json").read_text(encoding="utf-8"))
    rec = next(v for v in recs.values() if "Nexy.esp" in v.get("plugins", []))
    assert rec["source"]["nexus"]["mod_id"] == 123
    v = run("recipe_view")["result"]
    assert v["nexus"] == 1 and v["counts"]["mods"] >= 1
    up = run("nexus_updates")["result"]
    assert up["rows"][0]["status"] == "update" and calls[0][0]["mod_id"] == 123
    ex = run("recipe_export")["result"]
    md = Path(ex["path"]).read_text(encoding="utf-8")
    assert "nexusmods.com/skyrimspecialedition/mods/123" in md and str(tmp_path) not in md


def test_fix_safe_includes_deep_only_fixes(tmp_path, monkeypatch):
    """'Fix the safe ones' must also apply what only the deep check finds
    (FaceGen tints), as the single button does."""
    import shutil
    rev = Path("private-test-data/SkyNX/Other modpacks/Avner ModPack Revised 2026/"
               "Avner ModPack Revised 2026/01000A10041EA000/romfs/Data")
    if not (rev / "Cheat Room Fix.bsa").exists():
        import pytest
        pytest.skip("real files missing")
    api, run, _A = _api(tmp_path, monkeypatch)
    pack = mini_pack(tmp_path / "P")
    m = tmp_path / "cr"
    m.mkdir()
    for n in ("Cheat Room Fix.esp", "Cheat Room Fix.bsa"):
        shutil.copy(rev / n, m / n)
    assert not run("open_pack", str(pack))["error"]
    assert not run("add_mod", str(m))["error"]
    assert not run("reaudit", True)["error"]
    codes = [f["code"] for f in api.current()["audit"]["findings"]]
    assert "tint-broken" in codes
    out = run("apply_safe")
    assert not out["error"], out
    assert out["result"]["done"], out["result"]
    codes = [f["code"] for f in api.current()["audit"]["findings"]]
    assert "tint-broken" not in codes


def test_loose_files_group_into_one_mod(tmp_path):
    from skynx.intake import group_loose
    d = tmp_path / "Data"
    fake_plugin(d / "Auri.esp", ["Skyrim.esm"])
    (d / "Auri.bsa").write_bytes(EMPTY_BSA)
    (d / "Auri - Textures.bsa").write_bytes(EMPTY_BSA)
    (d / "Lonely.bsa").write_bytes(EMPTY_BSA)
    g = group_loose([str(d / "Auri.bsa"), str(d / "Auri.esp"), str(d / "Lonely.bsa")])
    assert len(g) == 2
    main, files = g[0]
    assert Path(main).name == "Auri.esp"
    assert sorted(Path(f).name for f in files) == ["Auri - Textures.bsa", "Auri.bsa", "Auri.esp"]
    assert Path(g[1][0]).name == "Lonely.bsa"


def test_precheck_finds_missing_bsa_and_where_it_went(tmp_path):
    from test_requirements import make_bsa, plugin, rec, sub, zs
    from skynx.precheck import precheck
    from skynx.pack import Pack
    pack = Pack.open(mini_pack(tmp_path / "P"))
    d = tmp_path / "src"
    stat = rec("STAT", 0x800, [sub("EDID", zs("Rock")), sub("MODL", zs("auri\\rock.nif"))])
    plugin(d / "Auri.esp", [stat])
    make_bsa(d / "Auri.bsa", {"scripts\\other.pex": b"x"})
    make_bsa(d / "Merged.bsa", {"meshes\\auri\\rock.nif": b"n" * 10})   # consolidated elsewhere
    r = precheck(pack, d / "Auri.esp", vanilla=set(), origin=d / "Auri.esp")
    text = " ".join(n["en"] for n in r["notes"])
    assert "A BSA of this mod is probably missing" in text and "meshes\\auri\\rock.nif" in text
    assert "Merged.bsa" in text
    # without the vanilla index it only says how to enable the check
    r = precheck(pack, d / "Auri.esp", vanilla=None, origin=d / "Auri.esp")
    assert any("Vanilla folder" in n["en"] for n in r["notes"])


def _fresh_api(tmp_path, monkeypatch):
    import importlib
    monkeypatch.setenv("APPDATA", str(tmp_path / "appdata"))
    monkeypatch.setenv("SKYNX_LIBRARY", str(tmp_path / "lib"))
    import api as A
    importlib.reload(A)
    api = A.Api()

    def run(method, *a):
        import time
        r = getattr(api, method)(*a)
        assert r.get("ok") is not False, r
        while api.progress()["busy"]:
            time.sleep(0.05)
        return api.progress()
    return api, run


def test_open_moved_pack_finds_it_in_library(tmp_path, monkeypatch):
    import shutil
    api, run = _fresh_api(tmp_path, monkeypatch)
    old = mini_pack(tmp_path / "Old place" / "My Pack")
    run("open_pack", str(old))
    assert api.state()["recent"][0] == str(old)
    new = tmp_path / "lib" / "Packs" / "My Pack"
    new.parent.mkdir(parents=True, exist_ok=True)
    shutil.move(str(old), str(new))
    p = run("open_pack", str(old))
    assert p["error"] is None and p["result"]["moved"] == {"from": str(old), "to": str(new)}
    assert api.state()["recent"] == [str(new)]
    # gone for good: a clear error, and it leaves the recent list
    api._settings["recent"] = [str(tmp_path / "Nowhere" / "Lost Pack")]
    p = run("open_pack", str(tmp_path / "Nowhere" / "Lost Pack"))
    assert "Lost Pack" in p["error"] and api.state()["recent"] == []


def test_setup_status_and_splash_pref(tmp_path, monkeypatch):
    api, run = _fresh_api(tmp_path, monkeypatch)
    items = {i["id"]: i for i in api.setup_status()["items"]}
    for k in ("texconv", "ffmpeg", "vgaudio", "nvntexpkg", "inis", "vanilla", "ussep", "library",
              "sseedit", "zedit", "loot", "nexus"):
        assert k in items, k
        assert items[k]["need"] in ("convert", "new", "optional", "always")
        assert len(items[k]["what"]) == 2
    assert items["library"]["ok"] and not items["nexus"]["ok"]
    assert "rar" in items
    for k, i in items.items():                    # every missing item says what stops working
        assert len(i["lose"]) == 2
        if k != "library":
            assert i["lose"][0] and i["lose"][1], k
    assert api.ui_prefs()["intro_seen"] is False
    api.set_ui_pref("intro_seen", True)
    assert api.ui_prefs()["intro_seen"] is True
    assert api.ui_prefs()["splash_hide"] is False
    api.set_ui_pref("splash_hide", True)
    api.set_ui_pref("nexus_key", "x")                  # not a UI pref: ignored
    import importlib
    import api as A
    importlib.reload(A)
    again = A.Api()
    assert again.ui_prefs()["splash_hide"] is True and not again._settings.get("nexus_key")
