"""Which Nexus version works on the Switch."""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from skynx import compat as CP  # noqa: E402

PLAIN = {"children": [{"name": "Data", "type": "directory", "children": [
    {"name": "Mod.esp", "type": "file"}, {"name": "Mod.bsa", "type": "file"}]}]}
WITH_DLL = {"children": [{"name": "SKSE", "type": "directory", "children": [
    {"name": "Plugins", "type": "directory", "children": [{"name": "Mod.dll", "type": "file"}]}]},
    {"name": "Mod.esp", "type": "file"}]}
FOMOD_DLL = {"children": [{"name": "fomod", "type": "directory", "children": [{"name": "ModuleConfig.xml", "type": "file"}]},
                          {"name": "Option SKSE", "type": "directory", "children": [{"name": "x.dll", "type": "file"}]}]}


def f(fid, ts, version, cat="MAIN", desc="", changelog=""):
    return {"file_id": fid, "uploaded_timestamp": ts, "version": version, "category_name": cat,
            "name": f"Mod {version}", "description": desc, "changelog_html": changelog}


def test_preview_paths_and_verdicts():
    assert CP.preview_paths(PLAIN) == ["Data/Mod.esp", "Data/Mod.bsa"]
    assert CP.assess(f(1, 1, "1"), CP.preview_paths(PLAIN))["verdict"] == "ok"
    v = CP.assess(f(1, 1, "1"), CP.preview_paths(WITH_DLL))
    assert v["verdict"] == "no" and "Mod.dll" in v["reasons"][0][1]
    assert CP.assess(f(1, 1, "1"), CP.preview_paths(FOMOD_DLL))["verdict"] == "warn"
    # text only
    assert CP.assess(f(1, 1, "1", desc="Requires <b>Address Library</b> and SKSE64"), None)["verdict"] == "warn"
    ok = CP.assess(f(1, 1, "1", desc="No SKSE required. Pure esp."), CP.preview_paths(PLAIN))
    assert ok["verdict"] == "ok" and any("sin SKSE" in r[1] for r in ok["reasons"])
    assert CP.preview_paths("nope") is None


def test_best_for_switch_is_the_newest_without_skse():
    files = [f(10, 100, "1.0", "OLD_VERSION"), f(20, 200, "2.0"), f(30, 300, "3.0", changelog="Now an SKSE plugin"),
             f(31, 310, "3.1"), {"file_id": 40, "category_name": "OPTIONAL", "uploaded_timestamp": 400}]
    assessed = {10: CP.assess(files[0], CP.preview_paths(PLAIN)), 20: CP.assess(files[1], CP.preview_paths(PLAIN)),
                30: CP.assess(files[2], CP.preview_paths(WITH_DLL)), 31: CP.assess(files[3], CP.preview_paths(WITH_DLL))}
    r = CP.choose(5, files, assessed, {"file_id": 10})
    assert [x["file_id"] for x in r["rows"]] == [31, 30, 20, 10]          # optional files aren't "the mod"
    assert r["latest"]["file_id"] == 31 and r["best"]["file_id"] == 20 and r["status"] == "update"
    assert "file_id=20" in r["best"]["page"]
    assert CP.choose(5, files, assessed, {"version": "v2.0"})["status"] == "kept"   # newer ones need SKSE
    assert CP.choose(5, files, assessed, {"file_id": 31})["status"] == "have_skse"
    assert CP.choose(5, files, assessed, None)["status"] == "unknown_have"
    only_dll = {k: CP.assess(fl, CP.preview_paths(WITH_DLL)) for k, fl in zip((10, 20, 30, 31), files[:4])}
    assert CP.choose(5, files, only_dll, None)["status"] == "all_skse"
    plain = {k: CP.assess(fl, CP.preview_paths(PLAIN)) for k, fl in zip((10, 20, 30, 31), files[:4])}
    assert CP.choose(5, files, plain, {"file_id": 31})["status"] == "best"


class FakeClient:
    def __init__(self, files, previews, fail=()):
        self._files, self._previews, self._fail = files, previews, set(fail)
        self.looked = []

    def files(self, mod_id):
        return {"files": self._files}

    def preview(self, url):
        self.looked.append(url)
        if url in self._fail:
            raise RuntimeError("down")
        return self._previews[url]


def test_check_looks_inside_until_one_works():
    files = [dict(f(10, 100, "1.0", "OLD_VERSION"), content_preview_link="p10"),
             dict(f(20, 200, "2.0"), content_preview_link="p20"),
             dict(f(30, 300, "3.0"), content_preview_link="p30")]
    cl = FakeClient(files, {"p10": PLAIN, "p20": PLAIN, "p30": WITH_DLL})
    r = CP.check(cl, 7, {"file_id": 10})
    assert r["best"]["file_id"] == 20 and r["latest"]["file_id"] == 30 and r["status"] == "update"
    assert cl.looked == ["p30", "p20", "p10"]       # 10 because it's the one you have
    cl2 = FakeClient(files, {"p20": PLAIN, "p30": WITH_DLL})
    assert CP.check(cl2, 7, None)["status"] == "unknown_have" and cl2.looked == ["p30", "p20"]
    # the listing fails: judged by the text only
    cl3 = FakeClient([dict(f(30, 300, "3.0", desc="SKSE plugin"), content_preview_link="p30")], {}, fail={"p30"})
    r3 = CP.check(cl3, 7, {"version": "3.0"})
    assert r3["rows"][0]["verdict"] == "warn" and r3["status"] == "best"


def test_a_sure_one_beats_a_doubtful_newer_one():
    files = [dict(f(1, 100, "1.0"), content_preview_link="a"), dict(f(2, 200, "2.0", changelog="needs Address Library"))]
    cl = FakeClient(files, {"a": PLAIN})
    r = CP.check(cl, 3, {"file_id": 1})
    assert r["latest"]["verdict"] == "warn" and r["best"]["file_id"] == 1 and r["status"] == "kept"
    assert cl.looked == ["a"]
