"""Which mod is it: confirmed by the person, downloaded, LOOT's links, merges."""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tests"))
from skynx import identify as ID  # noqa: E402
from skynx import loot  # noqa: E402
from skynx.plugin import read_header  # noqa: E402
from test_library import fake_plugin  # noqa: E402
from test_requirements import plugin, rec  # noqa: E402

ML = ROOT / "tests" / "fixtures" / "loot" / "masterlist.yaml"


def hdrs(*paths):
    return {Path(p).name.lower(): read_header(Path(p)) for p in paths}


def test_masterlist_keeps_urls():
    ml = loot.load_masterlist(ML)
    assert "https://www.nexusmods.com/skyrimspecialedition/mods/29434/" in ml.lookup("Butterflies.esp").urls


def test_links_and_search_words():
    assert ID.nexus_id("https://www.nexusmods.com/skyrimspecialedition/mods/266?tab=files") == 266
    assert ID.nexus_id("https://www.nexusmods.com/skyrim/mods/71214") is None          # Oldrim isn't AE
    assert ID.parse_input(" 12604 ") == 12604
    assert ID.query_for("Ryn_s Dragon Mounds AIO.esp") == "Ryn's Dragon Mounds AIO"
    assert ID.query_for("TrueStormsSE.esp") == "True Storms SE"
    assert ID.search_url("Ryn's Mod").endswith("keyword=Ryn%27s%20Mod")


def test_found_by_name_by_original_name_and_with_drive_damage(tmp_path):
    ml = loot.load_masterlist(ML)
    p = fake_plugin(tmp_path / "Butterflies.esp")
    r = ID.identify(["Butterflies.esp"], hdrs(p), masterlist=ml)
    assert r["status"] == "likely" and r["mod_id"] == 29434 and r["how"] == "loot"
    assert r["url"] == "https://www.nexusmods.com/skyrimspecialedition/mods/29434"
    # renamed in the pack: the original name the app recorded finds it
    q = fake_plugin(tmp_path / "Bflies.esp")
    r = ID.identify(["Bflies.esp"], hdrs(q), aliases={"Bflies.esp": "Butterflies.esp"}, masterlist=ml)
    assert r["mod_id"] == 29434 and r["originals"] == ["Butterflies.esp"]
    # renamed by the converter (recorded in the pack's mod record)
    r = ID.identify(["Bflies.esp"], hdrs(q), record={"converted": {"names": {"Butterflies.esp": "Bflies.esp"}}},
                    masterlist=ml)
    assert r["mod_id"] == 29434
    # unknown: no link, but a search
    z = fake_plugin(tmp_path / "Zzz Mystery.esp")
    r = ID.identify(["Zzz Mystery.esp"], hdrs(z), masterlist=ml)
    assert r["status"] == "unknown" and r["mod_id"] is None and "keyword=Zzz%20Mystery" in r["search"]


def test_download_and_confirmation_win(tmp_path):
    ml = loot.load_masterlist(ML)
    p = fake_plugin(tmp_path / "Butterflies.esp")
    p.write_bytes(p.read_bytes() + b"\0" * 600)          # real content (dummies are matched by name too)
    rec_ = {"source": {"kind": "nexus", "nexus": {"mod_id": 999, "game": "skyrimspecialedition"}}}
    r = ID.identify(["Butterflies.esp"], hdrs(p), record=rec_, masterlist=ml)
    assert r["status"] == "known" and r["mod_id"] == 999
    assert any(c["mod_id"] == 29434 for c in r["candidates"])
    lib = tmp_path / "lib"
    ID.remember(lib, p, 1234)
    ID.remember_details(lib, 1234, {"name": "Butterflies Plus", "version": "2.1", "author": "x"})
    store = ID.load_store(lib)
    r = ID.identify(["Butterflies.esp"], hdrs(p), record=rec_, masterlist=ml, store=store,
                    paths={"butterflies.esp": p})
    assert r["status"] == "confirmed" and r["mod_id"] == 1234 and r["details"]["name"] == "Butterflies Plus"
    # the same plugin under another name in another pack is still recognised (by content)
    other = tmp_path / "pack2" / "Renamed.esp"
    other.parent.mkdir()
    other.write_bytes(p.read_bytes())
    r = ID.identify(["Renamed.esp"], hdrs(other), store=store, paths={"renamed.esp": other})
    assert r["mod_id"] == 1234
    ID.remember(lib, p, None)
    assert ID.load_store(lib)["by_sha"] == {}
    # header-only dummies are all alike: those also need the same name
    dummy = fake_plugin(tmp_path / "d" / "Dummy A.esp")
    twin = fake_plugin(tmp_path / "d" / "Dummy B.esp")
    ID.remember(lib, dummy, 42)
    store = ID.load_store(lib)
    assert ID.identify(["Dummy A.esp"], {}, store=store, paths={"dummy a.esp": dummy})["mod_id"] == 42
    assert ID.identify(["Dummy B.esp"], {}, store=store, paths={"dummy b.esp": twin})["mod_id"] is None


def test_a_merge_lists_its_mods(tmp_path):
    ml = loot.load_masterlist(ML)
    m = tmp_path / "Suite.esp"
    plugin(m, [rec("ARMO", 0x800, b"")], snam="Merged Plugin:\r\nButterflies.esp\r\nZzz Mystery.esp")
    r = ID.identify(["Suite.esp"], hdrs(m), masterlist=ml)
    assert r["status"] == "merge"
    inside = {c["plugin"]: c for c in r["merge"]}
    assert inside["Butterflies.esp"]["mod_id"] == 29434 and inside["Zzz Mystery.esp"]["mod_id"] is None
    assert "keyword=Zzz%20Mystery" in inside["Zzz Mystery.esp"]["search"]


def test_app_identify(tmp_path, monkeypatch):
    import importlib
    import shutil
    from test_draft import avner_like
    monkeypatch.setenv("APPDATA", str(tmp_path / "appdata"))
    monkeypatch.setenv("SKYNX_LIBRARY", str(tmp_path / "lib"))
    sys.path.insert(0, str(ROOT / "app"))
    import api as A
    importlib.reload(A)
    api = A.Api()
    d, ml_path, _u = api._loot_paths()
    d.mkdir(parents=True, exist_ok=True)
    shutil.copy(ML, ml_path)
    src = avner_like(tmp_path / "src")
    fake_plugin(src.data_dir / "Butterflies.esp", ["Skyrim.esm"])
    src.list_path.write_bytes(src.list_path.read_bytes() + b"Butterflies.esp\r\n")
    api.open_pack(str(src.root))
    import time
    while api.progress()["busy"]:
        time.sleep(0.05)
    r = api.identify_mods()
    assert r["ok"] and r["masterlist"]
    by = {x["id"]: x["ident"] for x in r["rows"]}
    assert by["Butterflies.esp"]["mod_id"] == 29434
    assert by["Tiny.esp"]["status"] == "unknown"
    assert api.identify_set("Tiny.esp", "https://www.nexusmods.com/skyrimspecialedition/mods/555")["ok"]
    assert not api.identify_set("Tiny.esp", "https://www.nexusmods.com/skyrim/mods/5")["ok"]
    by = {x["id"]: x["ident"] for x in api.identify_mods()["rows"]}
    assert by["Tiny.esp"]["status"] == "confirmed" and by["Tiny.esp"]["mod_id"] == 555
    # which version works on Switch, with a stand-in for Nexus
    from test_compat import PLAIN, WITH_DLL, FakeClient, f
    files = [dict(f(1, 100, "1.0"), content_preview_link="a"), dict(f(2, 200, "2.0"), content_preview_link="b")]
    monkeypatch.setattr(api, "_nexus_client", lambda: FakeClient(files, {"a": PLAIN, "b": WITH_DLL}))
    api._settings["lang"] = "es"

    def run(ids):
        j = api.nexus_compat(ids)
        assert j["ok"]
        while api.progress(j["job"])["busy"]:
            time.sleep(0.05)
        p = api.progress(j["job"]); assert not p.get("error"), p; return p["result"]
    res = run(["Tiny.esp"])
    m = res["mods"][0]
    assert m["status"] == "unknown_have" and m["best"]["file_id"] == 1 and m["latest"]["file_id"] == 2
    assert "SKSE" in m["latest"]["reasons"][0] and "Trae" in m["latest"]["reasons"][0]
    assert api.identify_installed("Tiny.esp", 555, 1, "1.0")["ok"]
    by = {x["id"]: x["ident"] for x in api.identify_mods()["rows"]}
    assert by["Tiny.esp"]["installed"]["file_id"] == 1 and by["Tiny.esp"]["status"] == "confirmed"
    assert run(["Tiny.esp"])["mods"][0]["status"] == "kept"
    assert {"Tiny.esp", "Butterflies.esp"} <= {x["id"] for x in run(None)["mods"]}
    # the queue and the Catalog: by name (LOOT) and by the plugin's SHA-1 (confirmed)
    tiny_sha = ID._sha1(src.data_dir / "Tiny.esp")
    lk = api.identify_lookup([{"key": "a", "plugins": ["Butterflies.esp"]},
                              {"key": "b", "plugins": ["Tiny.esp"], "hashes": ["0" * 40], "more_hashes": [[tiny_sha]]},
                              {"key": "c", "plugins": ["Nobody Knows.esp"]}])
    assert lk["ok"] and lk["rows"]["a"]["mod_id"] == 29434 and lk["rows"]["a"]["status"] == "likely"
    assert lk["rows"]["b"]["status"] == "confirmed" and lk["rows"]["b"]["mod_id"] == 555
    assert lk["rows"]["c"]["mod_id"] is None and "Nobody" in lk["rows"]["c"]["search"]
    # the shareable recipe carries the links
    j = api.recipe_export()
    while api.progress(j["job"])["busy"]:
        time.sleep(0.05)
    md = Path(api.progress(j["job"])["result"]["path"]).read_text(encoding="utf-8")
    assert "skyrimspecialedition/mods/29434" in md and "skyrimspecialedition/mods/555" in md
