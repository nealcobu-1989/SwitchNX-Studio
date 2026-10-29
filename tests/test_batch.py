"""Convert several mods in one go."""
import shutil
import sys
import time
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tests"))
pytest.importorskip("etcpak")
pytestmark = pytest.mark.skipif(not shutil.which("ffmpeg"), reason="needs ffmpeg")

from skynx import batch as B  # noqa: E402
from skynx.builder import create_project  # noqa: E402
from skynx.pack import Pack  # noqa: E402
from skynx.plugin import read_header  # noqa: E402
from test_convert import BASE_INIS, FAKE, dds, make_fomod_zip, plugin_bytes  # noqa: E402


def mod(root: Path, name: str, plugins: dict) -> Path:
    m = root / name
    (m / "textures" / name.lower().replace(" ", "")).mkdir(parents=True)
    for p, masters in plugins.items():
        (m / p).write_bytes(plugin_bytes(masters))
    (m / "textures" / name.lower().replace(" ", "") / "a.dds").write_bytes(dds(256, 256))
    return m


def api_for(tmp_path, monkeypatch):
    import importlib
    monkeypatch.setenv("APPDATA", str(tmp_path / "appdata"))
    monkeypatch.setenv("SKYNX_LIBRARY", str(tmp_path / "lib"))
    sys.path.insert(0, str(ROOT / "app"))
    import api as A
    importlib.reload(A)
    api = A.Api()
    api._settings["tools_dir"] = str(FAKE)
    root = create_project(tmp_path / "pack", "AE", BASE_INIS, "ussep")
    api.open_pack(str(root))
    wait(api)
    return api, root


def wait(api, j=None):
    while api.progress(j)["busy"] if j else api.progress()["busy"]:
        time.sleep(0.05)
    p = api.progress(j) if j else api.progress()
    assert not p.get("error"), p
    return p.get("result")


def run(api, method, *args):
    r = getattr(api, method)(*args)
    assert r.get("ok"), r
    return wait(api, r["job"])


def test_order_and_masters():
    class An:
        def __init__(self, plugins):
            self.plugins = plugins
            self.masters_map = {}
            self.mode = "AE"
    base = An([{"name": "Base.esp", "missing": [], "suggested": "Base.esp"}])
    addon = An([{"name": "Addon.esp", "missing": ["Base.esp"], "suggested": "Addon.esp"}])
    assert B.order([("2", addon), ("1", base)]) == ["1", "2"]
    assert B.point_masters(addon, {"base.esp": "BaseX.esp"}) == ["Base.esp"]
    assert addon.masters_map == {"Base.esp": "BaseX.esp"} and addon.plugins[0]["missing"] == []
    same = An([{"name": "Addon.esp", "missing": ["Base.esp"], "suggested": "Addon.esp"}])
    assert B.point_masters(same, {"base.esp": "Base.esp"}) == [] and same.plugins[0]["missing"] == []


def test_batch_converts_each_with_its_options(tmp_path, monkeypatch):
    api, root = api_for(tmp_path, monkeypatch)
    src = tmp_path / "src"
    base = mod(src, "Base Mod", {"Base Mod.esp": ["Skyrim.esm"]})
    addon = mod(src, "Addon Mod", {"Addon.esp": ["Skyrim.esm", "Base Mod.esp"]})
    other = mod(src, "Other Mod", {"Other.esp": ["Skyrim.esm"]})
    fz = make_fomod_zip(tmp_path)
    v = run(api, "batch_add", [str(addon), str(base), str(other), str(fz), str(tmp_path / "nope")])
    kinds = {Path(i["source"]).name: i["kind"] for i in v["items"]}
    assert kinds == {"Addon Mod": "ready", "Base Mod": "ready", "Other Mod": "ready",
                     fz.name: "fomod", "nope": "error"}
    assert v["budget"]["ccc_limit"] == 4096
    ids = {Path(i["source"]).name: i["id"] for i in v["items"]}
    # the same source twice is read once
    assert len(run(api, "batch_add", [str(base)])["items"]) == 5
    # the installer, inside the batch
    f = api.batch_fomod_start(ids[fz.name])
    assert f["ok"] and f["name"] == "My FOMOD Mod"
    it = run(api, "batch_fomod_finish", ids[fz.name], {})
    assert it["kind"] == "ready" and {p["name"] for p in it["view"]["plugins"]} >= {"MyMod.esp"}
    est = api.batch_estimate(ids["Base Mod"], "extreme", False, 256)
    assert est["ok"] and est["preset"] == "extreme" and est["max_size"] == 256
    api.batch_remove(ids["nope"])
    # repeated names inside the batch are refused before anything runs
    bad = api.batch_run([{"id": ids["Base Mod"], "options": {"names": {"Base Mod.esp": "Same.esp"}}},
                         {"id": ids["Other Mod"], "options": {"names": {"Other.esp": "Same.esp"}}}])
    assert not bad["ok"] and bad["problems"][0]["id"] == ids["Other Mod"]
    # the addon goes first in the plan; its master is converted first and renamed
    res = run(api, "batch_run", [
        {"id": ids["Addon Mod"], "options": {"preset": "koka", "sdk": False}},
        {"id": ids["Base Mod"], "options": {"preset": "diet", "sdk": False, "names": {"Base Mod.esp": "BaseX.esp"}}},
        {"id": ids["Other Mod"], "options": {"preset": "koka", "sdk": False, "packing": "single"}},
        {"id": ids[fz.name], "options": {"sdk": False}}])
    out = res["results"]
    assert [r["name"] for r in out][:2] == ["Base Mod", "Addon Mod"] and all(r["ok"] for r in out), out
    assert out[1]["pointed"] == ["Base Mod.esp"]
    pack = Pack.open(root)
    assert read_header(pack.data_dir / "Addon.esp").masters == ["Skyrim.esm", "BaseX.esp"]
    lst = [e.lower() for e in pack.list_entries]
    assert lst.index("basex.esp") < lst.index("addon.esp") and "mymod.esp" in lst
    assert next(r for r in out if r["name"] == "Other Mod")["bsas"] == ["Other.bsa"]
    assert api.batch_view()["items"] == []                   # converted ones leave the batch
    assert (tmp_path / "lib" / "Converted").is_dir()


def test_batch_on_a_bench_keeps_each_mod(tmp_path, monkeypatch):
    api, _root = api_for(tmp_path, monkeypatch)
    run(api, "workshop_new", "convert", "Lote", "AE", [])
    src = tmp_path / "src"
    a = mod(src, "Alpha Mod", {"Alpha.esp": ["Skyrim.esm"]})
    b = mod(src, "Beta Mod", {"Beta.esp": ["Skyrim.esm"]})
    v = run(api, "batch_add", [str(a), str(b)])
    res = run(api, "batch_run", [{"id": i["id"], "options": {"sdk": False}} for i in v["items"]])
    assert all(r["ok"] and r["kept"] for r in res["results"]), res
    conv = tmp_path / "lib" / "Converted"
    assert {p.name for p in conv.iterdir()} >= {"Alpha Mod", "Beta Mod"}


def test_a_failed_mod_must_be_read_again(tmp_path, monkeypatch):
    api, _root = api_for(tmp_path, monkeypatch)
    from skynx import converter as CV
    a = mod(tmp_path / "src", "Alpha Mod", {"Alpha.esp": ["Skyrim.esm"]})
    v = run(api, "batch_add", [str(a)])
    real = CV.convert

    def boom(*args, **kw):
        raise CV.ConvertError("broken", "roto")
    monkeypatch.setattr(CV, "convert", boom)
    res = run(api, "batch_run", [{"id": v["items"][0]["id"], "options": {"sdk": False}}])
    assert not res["results"][0]["ok"]
    left = api.batch_view()["items"]
    assert left[0]["kind"] == "error" and left[0]["source"] == str(a)
    monkeypatch.setattr(CV, "convert", real)
    api.batch_remove(left[0]["id"])
    assert run(api, "batch_add", [str(a)])["items"][0]["kind"] == "ready"


def test_real_shapes_optional_folder_and_history(tmp_path, monkeypatch):
    api, root = api_for(tmp_path, monkeypatch)
    src = tmp_path / "src"
    # Auri-like: main plugin plus an optional folder with its own plugin
    auri = mod(src, "Auri", {"018Auri.esp": ["Skyrim.esm"]})
    (auri / "Auri NPC Overhaul").mkdir()
    (auri / "Auri NPC Overhaul" / "AuriReplacer.esp").write_bytes(plugin_bytes(["Skyrim.esm"]))
    v0 = run(api, "batch_add", [str(mod(tmp_path / "b", "First", {"First.esp": ["Skyrim.esm"]}))])
    run(api, "batch_run", [{"id": v0["items"][0]["id"], "options": {"sdk": False, "keep": False}}])
    v = run(api, "batch_add", [str(auri)])
    it = v["items"][0]
    assert sorted(p["name"] for p in it["view"]["plugins"]) == ["018Auri.esp", "AuriReplacer.esp"]
    assert any("Auri NPC Overhaul" in n["text"] for n in it["view"]["notes"])
    api._settings["lang"] = "es"
    h = api.history()
    assert h and h[0]["title"].startswith("Agregar mod: ")
