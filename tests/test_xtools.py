"""xEdit workspace, external tools, BSA extraction and the plugin manager."""
import os
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tests"))
from skynx import xtools as X  # noqa: E402
from skynx.builder import create_project  # noqa: E402
from skynx.history import Transaction, list_history, undo  # noqa: E402
from skynx.pack import Pack  # noqa: E402
from test_library import EMPTY_BSA, INIS, fake_plugin  # noqa: E402
from test_requirements import make_bsa  # noqa: E402

FISH = "ccBGSSSE001-Fish.esm"
SURV = "ccQDRSSE001-SurvivalMode.esl"
LIST = [FISH, SURV, "Tiny.esp", "Patch.esp", "#Off.esp", "Ghost.esp"]


def ae_pack(tmp_path: Path, entries=LIST) -> Pack:
    root = create_project(tmp_path / "pack", "AE", INIS, "none")
    data = root / "01000A10041EA000/romfs/Data"
    fake_plugin(data / "Tiny.esp", ["Skyrim.esm"])
    fake_plugin(data / "Patch.esp", ["Skyrim.esm", "Tiny.esp", FISH])
    fake_plugin(data / "Off.esp", ["Skyrim.esm"])
    (data / "Tiny.bsa").write_bytes(EMPTY_BSA)
    ccc = root / "01000A10041EB009/romfs/Skyrim_aoc.ccc"
    ccc.write_bytes(b"".join(e.encode() + b"\r\n" for e in entries))
    return Pack.open(root)


def vanilla(tmp_path: Path, with_cc=True) -> Path:
    v = tmp_path / "Vanilla" / "BSAs"
    for m in ("Skyrim.esm", "Update.esm", "Dawnguard.esm", "HearthFires.esm", "Dragonborn.esm", "Hyrule.esm"):
        fake_plugin(v / m, [] if m == "Skyrim.esm" else ["Skyrim.esm"], flags=1)
    (v / "Skyrim - Textures0.bsa").write_bytes(EMPTY_BSA)
    (v / "Skyrim - Misc.bsa").write_bytes(EMPTY_BSA)
    if with_cc:
        fake_plugin(v / SURV, ["Skyrim.esm"], flags=0x201)
        (v / "ccQDRSSE001-SurvivalMode.bsa").write_bytes(EMPTY_BSA)
    return v


def lines(p) -> list[str]:
    return Path(p).read_bytes().decode("utf-8-sig").splitlines()


# ------------------------------------------------------------------ workspace
def test_workspace_layout_and_lists(tmp_path):
    pack = ae_pack(tmp_path)
    vanilla(tmp_path)
    ws = X.make_xedit_workspace(pack, tmp_path / "Vanilla", tmp_path / "ws")
    data = Path(ws["data"])
    for n in ("Skyrim.esm", "Hyrule.esm", "Tiny.esp", "Patch.esp", "Off.esp", "Tiny.bsa",
              "Skyrim - Textures0.bsa", SURV, "ccQDRSSE001-SurvivalMode.bsa"):
        assert (data / n).is_file(), n
    assert os.path.samefile(data / "Tiny.esp", pack.data_dir / "Tiny.esp")       # hardlink
    assert os.path.samefile(data / "Skyrim.esm", tmp_path / "Vanilla/BSAs/Skyrim.esm")
    assert ws["methods"]["copy"] == 0 and ws["methods"]["hardlink"] > 0

    pl = lines(ws["plugins_txt"])
    assert pl[0].startswith("#")
    assert pl[1:] == ["*Hyrule.esm", "*" + SURV, "*Tiny.esp", "*Patch.esp", "Off.esp"]
    assert lines(ws["ccc"]) == ["Hyrule.esm", SURV]
    lo = lines(ws["loadorder_txt"])
    assert lo[:6] == ["Skyrim.esm", "Update.esm", "Dawnguard.esm", "HearthFires.esm",
                      "Dragonborn.esm", "Hyrule.esm"]
    assert lo[6:] == [SURV, "Tiny.esp", "Patch.esp", "Off.esp"]
    assert Path(ws["plugins_txt"]).read_bytes().endswith(b"Off.esp\r\n")

    miss = {m["name"]: m for m in ws["missing"]}
    assert miss[FISH]["kind"] == "cc" and miss[FISH]["needed_by"] == ["Patch.esp"]
    assert miss["Ghost.esp"]["kind"] == "listed"
    assert "Skyrim.esm" not in miss

    ini = Path(ws["ini"]).read_text()
    assert "sLanguage=ENGLISH" in ini
    assert "Skyrim - Textures0.bsa" in ini and "Skyrim - Textures1.bsa" not in ini
    assert any(n["code"] == "ini-bsa-missing" for n in ws["notes"])
    assert Path(ws["manifest"]).is_file()


def test_workspace_without_vanilla_reports_masters(tmp_path):
    pack = ae_pack(tmp_path)
    ws = X.make_xedit_workspace(pack, None, tmp_path / "ws")
    kinds = {m["name"]: m["kind"] for m in ws["missing"]}
    assert kinds["Skyrim.esm"] == "vanilla" and kinds[SURV] == "cc"
    assert any(n["code"] == "no-vanilla" for n in ws["notes"])
    assert "*" + SURV not in lines(ws["plugins_txt"])


def test_workspace_copy_fallback(tmp_path, monkeypatch):
    pack = ae_pack(tmp_path)

    def nolink(*a, **k):
        raise OSError(18, "Invalid cross-device link")
    monkeypatch.setattr(X.os, "link", nolink)
    monkeypatch.setattr(X.os, "symlink", nolink)
    vanilla(tmp_path)
    ws = X.make_xedit_workspace(pack, tmp_path / "Vanilla", tmp_path / "ws")
    data = Path(ws["data"])
    assert (data / "Tiny.esp").read_bytes() == (pack.data_dir / "Tiny.esp").read_bytes()
    assert not os.path.samefile(data / "Tiny.esp", pack.data_dir / "Tiny.esp")
    assert (data / "Skyrim.esm").is_file()           # plugins are copied
    assert not (data / "Tiny.bsa").exists()          # BSAs are skipped
    assert "Tiny.bsa" in ws["skipped"]
    codes = {n["code"] for n in ws["notes"]}
    assert {"bsa-skipped", "copied"} <= codes


def test_workspace_symlink_fallback(tmp_path, monkeypatch):
    pack = ae_pack(tmp_path)
    vanilla(tmp_path)

    def nolink(*a, **k):
        raise OSError(18, "Invalid cross-device link")
    monkeypatch.setattr(X.os, "link", nolink)
    ws = X.make_xedit_workspace(pack, tmp_path / "Vanilla", tmp_path / "ws")
    assert (Path(ws["data"]) / "Tiny.bsa").is_symlink()
    assert ws["methods"]["symlink"] > 0 and ws["methods"]["copy"] == 0


def test_workspace_refuses_foreign_folder(tmp_path):
    pack = ae_pack(tmp_path)
    (tmp_path / "busy").mkdir()
    (tmp_path / "busy" / "keep.txt").write_text("x")
    with pytest.raises(X.XToolsError):
        X.make_xedit_workspace(pack, None, tmp_path / "busy")
    assert (tmp_path / "busy" / "keep.txt").exists()


def test_xedit_command(tmp_path):
    pack = ae_pack(tmp_path)
    vanilla(tmp_path)
    ws = X.make_xedit_workspace(pack, tmp_path / "Vanilla", tmp_path / "w s")
    cmd = X.xedit_command(Path("C:/Tools/SSEEdit64.exe"), ws, extra=["-autoload"])
    assert cmd[1:] == ["-SSE", f"-D:{ws['data']}", f"-P:{ws['plugins_txt']}", f"-I:{ws['ini']}",
                       f"-CustomIni:{ws['custom_ini']}", "-autoload"]
    assert X.xedit_command("x.exe", ws, game="sse")[1] == "-SSE"
    with pytest.raises(X.XToolsError):
        X.xedit_command("x.exe", ws, game="FO4")
    with pytest.raises(X.XToolsError):
        X.xedit_command("x.exe", ws, extra=["-AllowDirectSaves"])
    assert X.zedit_command("zEdit.exe", "SwitchNX") == ["zEdit.exe", "-profile:SwitchNX"]


# ------------------------------------------------------------------ sync back
def xedit_save(data: Path, name: str, new: bytes) -> None:
    """What xEdit does: write <name>.save.<ts>, then (on exit) move the
    original into "SSEEdit Backups" and rename the .save onto the name."""
    tmp = data / f"{name}.save.2026_10_24_10_00_00"
    tmp.write_bytes(new)
    return tmp


def xedit_close(data: Path, name: str) -> None:
    bk = data / "SSEEdit Backups"
    bk.mkdir(exist_ok=True)
    os.rename(data / name, bk / f"{name}.backup.2026_10_24_10_00_00")
    os.rename(data / f"{name}.save.2026_10_24_10_00_00", data / name)


def test_sync_back_and_undo(tmp_path):
    pack = ae_pack(tmp_path)
    vanilla(tmp_path)
    ws = X.make_xedit_workspace(pack, tmp_path / "Vanilla", tmp_path / "ws")
    data = Path(ws["data"])
    orig = (pack.data_dir / "Tiny.esp").read_bytes()
    edited = orig + b"GRUP" + b"\0" * 20
    xedit_save(data, "Tiny.esp", edited)
    assert X.sync_status(pack, ws)["pending_saves"] == ["Tiny.esp.save.2026_10_24_10_00_00"]
    with Transaction(pack.root, "sync") as tx, pytest.raises(X.XToolsError):
        X.sync_back(pack, ws, tx)
    xedit_close(data, "Tiny.esp")
    (data / "seq").mkdir()
    (data / "seq" / "Tiny.seq").write_bytes(b"\x01\x08\x00\x00")
    (data / "notes.txt").write_text("x")
    assert (pack.data_dir / "Tiny.esp").read_bytes() == orig        # the link was not written
    st = X.sync_status(pack, ws)
    assert st["changed"] == ["Tiny.esp"] and st["new"] == ["seq/Tiny.seq"]
    assert st["ignored"] == ["notes.txt"] and not st["pending_saves"]

    with Transaction(pack.root, "Bring back xEdit changes") as tx:
        done = X.sync_back(pack, ws, tx)
    assert sorted(done) == ["Tiny.esp", "seq/Tiny.seq"]
    assert (pack.data_dir / "Tiny.esp").read_bytes() == edited
    assert (pack.data_dir / "seq" / "Tiny.seq").exists()
    st = X.sync_status(pack, ws)
    assert not st["changed"] and not st["new"]

    entry = list_history(pack.root)[0]
    undo(pack.root, entry["id"])
    assert (pack.data_dir / "Tiny.esp").read_bytes() == orig
    assert not (pack.data_dir / "seq" / "Tiny.seq").exists()


def test_sync_conflict_in_place_and_rebuild(tmp_path):
    pack = ae_pack(tmp_path)
    vanilla(tmp_path)
    dest = tmp_path / "ws"
    ws = X.make_xedit_workspace(pack, tmp_path / "Vanilla", dest)
    data = Path(ws["data"])
    orig = (pack.data_dir / "Tiny.esp").read_bytes()
    xedit_save(data, "Tiny.esp", orig + b"A" * 8)
    xedit_close(data, "Tiny.esp")
    (pack.data_dir / "Tiny.esp").write_bytes(orig + b"B" * 8)     # the app changed it too (new inode not needed)
    st = X.sync_status(pack, ws)
    assert st["conflicts"] == ["Tiny.esp"] and not st["changed"]
    with Transaction(pack.root, "sync") as tx, pytest.raises(X.XToolsError):
        X.sync_back(pack, ws, tx)
    with pytest.raises(X.XToolsError):       # rebuilding would lose the edit
        X.make_xedit_workspace(pack, tmp_path / "Vanilla", dest)

    # a tool that writes through the link changes the pack directly
    with open(data / "Patch.esp", "r+b") as f:
        f.seek(0, 2)
        f.write(b"XX")
    assert X.sync_status(pack, ws)["in_place"] == ["Patch.esp"]

    with Transaction(pack.root, "sync") as tx:
        assert X.sync_back(pack, ws, tx, force=True) == ["Tiny.esp"]
    assert (pack.data_dir / "Tiny.esp").read_bytes() == orig + b"A" * 8
    ws2 = X.make_xedit_workspace(pack, tmp_path / "Vanilla", dest)
    assert not (Path(ws2["data"]) / "SSEEdit Backups").exists()
    assert (pack.data_dir / "Tiny.esp").exists()                  # rebuilding never touches the pack


def test_sync_rejects_other_pack(tmp_path):
    pack = ae_pack(tmp_path)
    ws = X.make_xedit_workspace(pack, None, tmp_path / "ws")
    other = ae_pack(tmp_path / "o")
    with pytest.raises(X.XToolsError):
        X.sync_status(other, ws)


# ------------------------------------------------------------------ tools
def test_tool_registry_and_find(tmp_path, monkeypatch):
    ids = {t["id"]: t for t in X.known_tools()}
    assert {"sseedit", "zedit", "nifskope", "bae", "cao", "other"} <= set(ids)
    for t in ids.values():
        assert t["kind"] in {"xedit", "zedit", "nifskope", "bsa", "other"}
        assert t["how"]["en"] and t["how"]["es"] and "\u2014" not in t["how"]["es"]
    monkeypatch.setattr(X, "DEFAULT_TOOL_DIRS", ())
    tools = tmp_path / "Tools"
    (tools / "SSEEdit 4.1.5f").mkdir(parents=True)
    (tools / "SSEEdit 4.1.5f" / "xEdit.exe").write_bytes(b"")
    (tools / "SSEEdit 4.1.5f" / "SSEEdit64.exe").write_bytes(b"")
    (tools / "nifskope.exe").write_bytes(b"")
    assert X.find_tool("sseedit", [tools]).name == "SSEEdit64.exe"
    assert X.find_tool("nifskope", [tools]).name == "nifskope.exe"
    assert X.find_tool("zedit", [tools]) is None
    assert X.find_tool("other", [tools]) is None


def test_launch_detached():
    seen = {}

    class FakeProc:
        pid = 4321

    def fake_popen(cmd, **kw):
        seen["cmd"], seen["kw"] = cmd, kw
        return FakeProc()
    assert X.launch([Path("a b/SSEEdit.exe"), "-SSE"], cwd="/tmp", popen=fake_popen) == 4321
    assert seen["cmd"] == [str(Path("a b/SSEEdit.exe")), "-SSE"]
    assert seen["kw"]["cwd"] == "/tmp"
    if os.name == "nt":
        assert seen["kw"]["creationflags"] & X.DETACHED_PROCESS
    else:
        assert seen["kw"]["start_new_session"] is True

    def broken(cmd, **kw):
        raise FileNotFoundError(2, "not found")
    with pytest.raises(X.XToolsError):
        X.launch(["nope.exe"], popen=broken)


# ------------------------------------------------------------------ BSA extraction
def test_extract_bsa(tmp_path):
    bsa = make_bsa(tmp_path / "Mod.bsa", {"meshes\\a\\b.nif": b"nif!", "textures\\t.dds": b"y" * 50,
                                          "scripts\\s.pex": b"pex"})
    out = tmp_path / "out"
    calls = []
    r = X.extract_bsa(bsa, out, progress=lambda *a: calls.append(a))
    assert r["files"] == 3 and r["bytes"] == 4 + 50 + 3
    assert (out / "meshes" / "a" / "b.nif").read_bytes() == b"nif!"
    assert calls[-1][0] == calls[-1][1] == 3

    again = X.extract_bsa(bsa, out)                       # identical files: nothing written
    assert again["files"] == 0 and again["same"] == 3
    (out / "meshes" / "a" / "b.nif").write_bytes(b"mine")
    r = X.extract_bsa(bsa, out, only=["meshes/"])
    assert r["total"] == 1 and r["renamed"] == ["meshes/a/b (2).nif"]
    assert (out / "meshes" / "a" / "b.nif").read_bytes() == b"mine"
    assert (out / "meshes" / "a" / "b (2).nif").read_bytes() == b"nif!"
    r = X.extract_bsa(bsa, out, only="*.nif", overwrite=True)
    assert r["overwritten"] == 1 and (out / "meshes" / "a" / "b.nif").read_bytes() == b"nif!"
    r = X.extract_bsa(bsa, tmp_path / "o2", only=["*.dds", "scripts"])
    assert r["files"] == 2


def test_extract_refuses_unsafe_names(tmp_path, monkeypatch):
    from skynx import bsa as B
    real = B.read_bsa(make_bsa(tmp_path / "x.bsa", {"ok\\fine.txt": b"1"}))
    good = real.entries[0]
    bad = ["..\\evil.txt", "a\\..\\..\\evil.txt", "c:\\win.txt", "con\\x.txt", "a\\nul.txt",
           "a\\b?.txt", "a\\trail.\\x.txt", "\\root.txt"]
    real.entries = [good] + [B.BsaEntry(*p.rsplit("\\", 1), good.size, good.offset, good.compressed)
                             if "\\" in p[1:] else B.BsaEntry("", p, good.size, good.offset, good.compressed)
                             for p in bad]
    monkeypatch.setattr(B, "read_bsa", lambda p: real)
    out = tmp_path / "out"
    r = X.extract_bsa(tmp_path / "x.bsa", out)
    assert r["files"] == 1 and len(r["refused"]) == len(bad)
    assert not (tmp_path / "evil.txt").exists()
    assert [p.relative_to(out).as_posix() for p in out.rglob("*") if p.is_file()] == ["ok/fine.txt"]
    assert X.safe_rel_parts("meshes\\x.nif") == ["meshes", "x.nif"]


def test_extract_pack_bsas(tmp_path):
    pack = ae_pack(tmp_path)
    make_bsa(pack.data_dir / "Big.bsa", {"meshes\\m.nif": b"m"})
    pack.reload()
    r = X.extract_pack_bsas(pack, ["big.bsa", "Nope.bsa"], tmp_path / "x")
    assert r["files"] == 1 and r["missing"] == ["Nope.bsa"]
    assert (tmp_path / "x" / "Big" / "meshes" / "m.nif").exists()


# ------------------------------------------------------------------ plugin manager
def test_set_plugin_active(tmp_path):
    pack = ae_pack(tmp_path)
    before = pack.ccc_path.read_bytes()
    with Transaction(pack.root, "off") as tx:
        r = X.set_plugin_active(pack, "tiny.esp", False, tx)
    assert r["refused"] and r["users"] == ["Patch.esp"] and not r["changed"]
    assert pack.ccc_path.read_bytes() == before
    assert not list_history(pack.root)

    with Transaction(pack.root, "off") as tx:
        r = X.set_plugin_active(pack, "Tiny.esp", False, tx, force=True)
    assert r["changed"] and not r["active"]
    assert pack.ccc_path.read_bytes() == before.replace(b"\r\nTiny.esp\r\n", b"\r\n#Tiny.esp\r\n")
    assert "#Tiny.esp" in pack.list_entries

    with Transaction(pack.root, "on") as tx:
        r = X.set_plugin_active(pack, "Off.esp", True, tx)
    assert r["changed"] and r["missing_masters"] == []
    assert "Off.esp" in pack.list_entries and "#Off.esp" not in pack.list_entries
    with Transaction(pack.root, "on") as tx:
        r = X.set_plugin_active(pack, "Patch.esp", True, tx)
    assert not r["changed"] and r["missing_masters"] == ["Tiny.esp"]

    for e in list_history(pack.root):
        undo(pack.root, e["id"])
    assert pack.ccc_path.read_bytes() == before

    with Transaction(pack.root, "x") as tx:
        with pytest.raises(X.XToolsError):
            X.set_plugin_active(pack, "Skyrim.esm", False, tx)
        with pytest.raises(X.XToolsError):
            X.set_plugin_active(pack, "Absent.esp", True, tx)


def test_set_plugin_active_se(tmp_path):
    root = create_project(tmp_path / "se", "SE", INIS, "none")
    data = root / "01000A10041EA000/romfs/Data"
    fake_plugin(data / "A.esp", ["Skyrim.esm"])
    (root / "01000A10041EA000/romfs/Plugins").write_bytes(b"A.esp\nB.esp")
    pack = Pack.open(root)
    assert pack.mode == "SE"
    with Transaction(pack.root, "off") as tx:
        X.set_plugin_active(pack, "B.esp", False, tx)
    assert pack.plugins_path.read_bytes() == b"A.esp\n#B.esp"


def test_masters_view(tmp_path):
    pack = ae_pack(tmp_path)
    fake_plugin(pack.data_dir / "Loose.esp", ["Skyrim.esm"])
    pack.reload()
    rows = {r["name"]: r for r in X.masters_view(pack)}
    assert rows["Skyrim.esm"]["where"] == "game" and rows["Skyrim.esm"]["active"]
    assert rows[FISH]["where"] == "cc" and rows[FISH]["used_by"] == ["Patch.esp"]
    assert rows["Ghost.esp"]["where"] == "missing" and not rows["Ghost.esp"]["present"]
    assert rows["Off.esp"]["active"] is False
    assert rows["Loose.esp"]["listed"] is False and rows["Loose.esp"]["source"] == "data"
    patch = {m["name"]: m for m in rows["Patch.esp"]["masters"]}
    assert patch["Tiny.esp"] == {"name": "Tiny.esp", "present": True, "active": True, "before": True}
    assert patch[FISH]["present"] and patch[FISH]["before"]
    assert rows["Tiny.esp"]["used_by"] == ["Patch.esp"]
    assert rows["Tiny.esp"]["active_users"] == ["Patch.esp"]
    assert rows["Skyrim.esm"]["used_by"].count("Patch.esp") == 1
    names = [r["name"] for r in X.masters_view(pack)]
    assert names.index("Hyrule.esm") < names.index(FISH) < names.index("Tiny.esp") < names.index("Loose.esp")


# ------------------------------------------------------------------ xEdit sessions
def test_discard_workspace_keeps_originals(tmp_path):
    pack = ae_pack(tmp_path)
    v = vanilla(tmp_path)
    ws = X.make_xedit_workspace(pack, tmp_path / "Vanilla", tmp_path / "ws")
    X.discard_workspace(ws)
    assert not (tmp_path / "ws").exists()
    assert (pack.data_dir / "Tiny.esp").is_file() and (pack.data_dir / "Tiny.bsa").is_file()
    assert (v / "Skyrim.esm").is_file()
    other = tmp_path / "other"
    other.mkdir()
    (other / "keep.txt").write_text("x")
    with pytest.raises(X.XToolsError):
        X.discard_workspace(other)
    assert (other / "keep.txt").exists()


def test_open_existing_workspace(tmp_path):
    pack = ae_pack(tmp_path)
    ws = X.make_xedit_workspace(pack, None, tmp_path / "ws")
    again = X.open_existing_workspace(tmp_path / "ws")
    for k in ("data", "plugins_txt", "ini", "custom_ini"):
        assert again[k] == ws[k]
    with pytest.raises(X.XToolsError):
        X.open_existing_workspace(tmp_path)


def test_launch_calls_back_on_exit(tmp_path):
    import threading
    hit = threading.Event()
    codes = []
    X.launch([sys.executable, "-c", "import sys; sys.exit(3)"], on_exit=lambda c: (codes.append(c), hit.set()))
    assert hit.wait(10) and codes == [3]


FAKE_XEDIT = r'''
import os, sys
from pathlib import Path
data = next(Path(a[3:]) for a in sys.argv[1:] if a.startswith("-D:"))
if os.environ.get("FAKE_XEDIT_EDIT"):
    p = data / "Tiny.esp"
    new = p.read_bytes() + b"GRUP" + b"\0" * 20
    (data / "Tiny.esp.save.1").write_bytes(new)
    os.replace(data / "Tiny.esp.save.1", p)   # breaks the hardlink like xEdit's rename does
'''


def _api(tmp_path, monkeypatch, edit: bool):
    import importlib
    import time
    monkeypatch.setenv("APPDATA", str(tmp_path / "appdata"))
    monkeypatch.setenv("SKYNX_LIBRARY", str(tmp_path / "lib"))
    if edit:
        monkeypatch.setenv("FAKE_XEDIT_EDIT", "1")
    else:
        monkeypatch.delenv("FAKE_XEDIT_EDIT", raising=False)
    sys.path.insert(0, str(ROOT / "app"))
    import api as A
    importlib.reload(A)
    api = A.Api()
    pack = ae_pack(tmp_path)
    vanilla(tmp_path)
    script = tmp_path / "fake_xedit.py"
    script.write_text(FAKE_XEDIT)
    exe = tmp_path / "SSEEdit.sh"
    exe.write_text(f"#!/bin/sh\nexec {sys.executable} {script} \"$@\"\n")
    exe.chmod(0o755)
    api._settings["ext_tools"] = {"sseedit": str(exe)}
    api._settings["workspace_dir"] = str(tmp_path / "Workspace")
    api._settings["vanilla_dir"] = str(tmp_path / "Vanilla")

    def wait():
        while api.progress()["busy"]:
            time.sleep(0.05)
        return api.progress()
    api.open_pack(str(pack.root))
    wait()

    def closed():
        for _ in range(200):
            s = api.xedit_session()["session"]
            if s and not s["running"]:
                return s
            time.sleep(0.05)
        raise AssertionError("xEdit session never closed")
    return api, pack, wait, closed


@pytest.mark.skipif(os.name == "nt", reason="uses a POSIX shell script as a fake xEdit")
def test_api_xedit_copy_then_bring(tmp_path, monkeypatch):
    api, pack, wait, closed = _api(tmp_path, monkeypatch, edit=True)
    orig = (pack.data_dir / "Tiny.esp").read_bytes()
    assert api.xedit_open("sseedit", "copy")["ok"]
    assert wait()["error"] is None
    s = closed()
    assert s["mode"] == "copy" and s["changed"] == ["Tiny.esp"]
    assert (pack.data_dir / "Tiny.esp").read_bytes() == orig          # nothing yet
    r = api.xedit_finish("bring")
    assert r["ok"] and r["files"] == ["Tiny.esp"]
    assert (pack.data_dir / "Tiny.esp").read_bytes() != orig
    assert not (tmp_path / "Workspace" / pack.root.name).exists()
    assert api.xedit_session()["session"] is None


@pytest.mark.skipif(os.name == "nt", reason="uses a POSIX shell script as a fake xEdit")
def test_api_xedit_copy_keep_reuse_then_discard(tmp_path, monkeypatch):
    api, pack, wait, closed = _api(tmp_path, monkeypatch, edit=True)
    orig = (pack.data_dir / "Tiny.esp").read_bytes()
    api.xedit_open("sseedit", "copy")
    wait()
    closed()
    assert api.xedit_finish("keep")["ok"]
    ws = tmp_path / "Workspace" / pack.root.name
    assert ws.is_dir() and api.xedit_status()["changed"] == ["Tiny.esp"]
    # opening again without saying what to do with the kept edits is refused
    api.xedit_open("sseedit", "copy")
    assert wait()["error"]
    monkeypatch.delenv("FAKE_XEDIT_EDIT")
    api.xedit_open("sseedit", "copy", "reuse")
    assert wait()["error"] is None
    closed()
    assert api.xedit_status()["changed"] == ["Tiny.esp"]               # kept edits survived
    assert api.xedit_finish("discard")["ok"]
    assert not ws.exists() and (pack.data_dir / "Tiny.esp").read_bytes() == orig


@pytest.mark.skipif(os.name == "nt", reason="uses a POSIX shell script as a fake xEdit")
def test_api_xedit_direct_mode_reports_mode(tmp_path, monkeypatch):
    api, pack, wait, closed = _api(tmp_path, monkeypatch, edit=True)
    api.xedit_open("sseedit", "direct")
    assert wait()["result"]["mode"] == "direct"
    assert closed()["mode"] == "direct"
    r = api.xedit_finish("bring")                   # what the page does by itself in direct mode
    assert r["ok"] and r["files"] == ["Tiny.esp"] and r["audit"]
    assert any(h.get("title") == "Changes from SSEEdit" for h in list_history(pack.root))


# ------------------------------------------------------------------ review fixes
@pytest.mark.skipif(os.name == "nt", reason="uses a POSIX shell script as a fake xEdit")
def test_conflict_is_brought_not_lost(tmp_path, monkeypatch):
    api, pack, wait, closed = _api(tmp_path, monkeypatch, edit=True)
    api.xedit_open("sseedit", "copy")
    assert wait()["error"] is None
    closed()
    ws = tmp_path / "Workspace" / pack.root.name
    edited = (ws / "Data" / "Tiny.esp").read_bytes()
    p = pack.data_dir / "Tiny.esp"
    with Transaction(pack.root, "a Doctor fix meanwhile") as tx:
        tx.write_bytes(p, p.read_bytes() + b"Z" * 4)
    s = api.xedit_session()["session"]
    assert s["conflicts"] == ["Tiny.esp"] and not s["changed"]
    r = api.xedit_finish("bring")
    assert r["ok"] and r["files"] == ["Tiny.esp"] and not r["left"]
    assert p.read_bytes() == edited and not ws.exists()
    undo(pack.root, list_history(pack.root)[0]["id"])          # the pack's own change comes back
    assert p.read_bytes().endswith(b"Z" * 4)


@pytest.mark.skipif(os.name == "nt", reason="uses a POSIX shell script as a fake xEdit")
def test_launch_failure_does_not_leave_a_session(tmp_path, monkeypatch):
    api, pack, wait, closed = _api(tmp_path, monkeypatch, edit=False)
    good = api._settings["ext_tools"]["sseedit"]
    api._settings["ext_tools"] = {"sseedit": str(tmp_path / "gone" / "SSEEdit.exe")}
    api.xedit_open("sseedit", "copy")
    assert wait()["error"]
    assert api.xedit_session()["session"] is None
    api._settings["ext_tools"] = {"sseedit": good}
    api.xedit_open("sseedit", "copy", "rebuild")
    assert wait()["error"] is None


@pytest.mark.skipif(os.name == "nt", reason="uses a POSIX shell script as a fake xEdit")
def test_kept_copy_follows_a_moved_pack(tmp_path, monkeypatch):
    import shutil
    api, pack, wait, closed = _api(tmp_path, monkeypatch, edit=True)
    api.xedit_open("sseedit", "copy")
    wait()
    closed()
    assert api.xedit_finish("keep")["ok"]
    ws = tmp_path / "Workspace" / pack.root.name
    edited = (ws / "Data" / "Tiny.esp").read_bytes()
    new_root = tmp_path / "moved" / pack.root.name
    new_root.parent.mkdir()
    shutil.move(str(pack.root), str(new_root))
    api.open_pack(str(new_root))
    wait()
    st = api.xedit_status()
    assert st["ok"] and st["changed"] == ["Tiny.esp"]               # relinked, edit still there
    # opening again without choosing is refused instead of wiping the edit
    monkeypatch.delenv("FAKE_XEDIT_EDIT")
    api.xedit_open("sseedit", "copy", "")
    assert wait()["error"]
    assert (ws / "Data" / "Tiny.esp").read_bytes() == edited
    r = api.xedit_sync(False)
    assert r["ok"] and r["files"] == ["Tiny.esp"]
    assert (new_root / "01000A10041EA000/romfs/Data/Tiny.esp").read_bytes() == edited


def test_rebuild_refuses_when_edits_are_only_gone(tmp_path):
    pack = ae_pack(tmp_path)
    ws = X.make_xedit_workspace(pack, None, tmp_path / "ws")
    data = Path(ws["data"])
    new = (data / "Tiny.esp").read_bytes() + b"GRUP" + b"\0" * 20
    (data / "Tiny.esp.save.1").write_bytes(new)
    os.replace(data / "Tiny.esp.save.1", data / "Tiny.esp")
    (pack.data_dir / "Tiny.esp").unlink()                            # renamed away in the pack
    assert X.sync_status(pack, ws)["gone"] == ["Tiny.esp"]
    with pytest.raises(X.XToolsError):
        X.make_xedit_workspace(Pack.open(pack.root), None, tmp_path / "ws")
    assert (data / "Tiny.esp").read_bytes() == new


def test_relink_refuses_another_pack_with_same_name(tmp_path):
    a = ae_pack(tmp_path / "a")
    b = ae_pack(tmp_path / "b")
    ws = X.make_xedit_workspace(a, None, tmp_path / "ws")
    with pytest.raises(X.XToolsError):
        X.relink_workspace(ws, b)


def test_plugin_toggle_waits_for_running_job(tmp_path, monkeypatch):
    import threading
    api, pack, wait, closed = _api(tmp_path, monkeypatch, edit=False)
    gate = threading.Event()
    api._run("slow", lambda tick: gate.wait(5))
    r = api.plugin_active("Patch.esp", False)
    assert r.get("busy") and r["ok"] is False
    gate.set()
    wait()
    assert api.plugin_active("Patch.esp", False)["ok"]
