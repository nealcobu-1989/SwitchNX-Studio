"""Things found trying the app on real downloads and real packs (Oct 2026)."""
import sys
import zipfile
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tests"))
from skynx import variants as VA  # noqa: E402
from skynx.audit import run_audit  # noqa: E402
from skynx.builder import add_mod  # noqa: E402
from skynx.ccc import parse_ccc  # noqa: E402
from skynx.fixes import FixError, apply  # noqa: E402
from skynx.intake import detect  # noqa: E402
from skynx.pack import Pack  # noqa: E402
from test_draft import ae_pack  # noqa: E402
from test_library import EMPTY_BSA, fake_plugin  # noqa: E402


def zipped(tmp_path: Path, name: str, files: dict) -> Path:
    z = tmp_path / name
    with zipfile.ZipFile(z, "w") as zf:
        for rel, data in files.items():
            zf.writestr(rel, data)
    return z


def plugin_bytes(tmp_path, masters=("Skyrim.esm",)) -> bytes:
    return fake_plugin(tmp_path / "_p.esp", list(masters)).read_bytes()


def test_versions_and_mac_junk_are_told_apart():
    files = ["Mod_AE/Mod.esp", "Mod_AE/Mod.bsa", "Mod_SE/Mod.esp", "Mod_SE/Mod - Textures.bsa",
             "__MACOSX/Mod_AE/._Mod.esp", "Mod_AE/._Mod.bsa", "Mod_AE/.DS_Store"]
    ae = VA.choose(files, "AE")
    assert ae["skip"] == ["Mod_SE"] and ae["groups"][0]["how"] == "edition"
    assert VA.choose(files, "SE")["skip"] == ["Mod_AE"]
    assert VA.skipped("__MACOSX/Mod_AE/._Mod.esp", []) and VA.skipped("Mod_AE/._Mod.bsa", [])
    assert not VA.skipped("Mod_AE/Mod.esp", ae["skip"]) and VA.skipped("Mod_SE/Mod.esp", ae["skip"])
    # different mods side by side (a race and its framework) are not versions
    both = ["Pack/Half Dragon for SSE/half.esp", "Pack/RaceCompat/RaceCompatibility.esm"]
    assert VA.choose(both, "AE") == {"skip": [], "groups": []}
    # no clue in the names: the first one, said in a note
    tex = VA.choose(["1K/Mod.esp", "2K/Mod.esp"], "AE")
    assert tex["skip"] == ["2K"] and tex["groups"][0]["how"] == "first" and "2K" in VA.note(tex)[1]


def test_add_mod_takes_the_right_version_and_no_junk(tmp_path):
    pack = ae_pack(tmp_path / "p")
    pb = plugin_bytes(tmp_path)
    z = zipped(tmp_path, "College.zip", {
        "College_256_AE/College.esp": pb, "College_256_AE/College.bsa": EMPTY_BSA,
        "College_256_SE/College.esp": pb, "College_256_SE/College - Meshes.bsa": EMPTY_BSA,
        "__MACOSX/College_256_AE/._College.esp": b"\0\5\x16\7junk", "._College.bsa": b"junk"})
    d = detect(z)
    assert d.kind == "switch-mod" and d.evidence["plugins"] == ["College.esp"]
    assert any("versiones" in str(n) for n in d.to_dict("es")["notes"])
    rep = add_mod(pack, z)
    pack = Pack.open(pack.root)
    names = sorted(p.name for p in pack.data_dir.iterdir())
    assert "College.esp" in names and "College.bsa" in names and "College - Meshes.bsa" not in names
    assert not [n for n in names if n.startswith("._")]
    assert [e for e in pack.list_entries if e.lower().startswith("._")] == []
    assert any("College_256_AE" in es for _en, es in rep.notes)


def test_archives_left_in_data_can_be_extracted(tmp_path):
    pack = ae_pack(tmp_path / "p")
    pb = plugin_bytes(tmp_path)
    import py7zr
    src = tmp_path / "src"
    (src / "USSEP 4.2.9 NX").mkdir(parents=True)
    (src / "USSEP 4.2.9 NX" / "Patchy.esp").write_bytes(pb)
    (src / "USSEP 4.2.9 NX" / "PatchyT.bsa").write_bytes(EMPTY_BSA)
    with py7zr.SevenZipFile(pack.data_dir / "Patchy 1.0 NX.7z", "w") as z:
        z.writeall(src / "USSEP 4.2.9 NX", "USSEP 4.2.9 NX")
    zipped(pack.data_dir, "Loose Only.zip", {"meshes/a.nif": b"x"})
    pack = Pack.open(pack.root)
    R = run_audit(pack)
    f = next(x for x in R.findings if x.code == "data-archive" and x.subject == "Patchy 1.0 NX.7z")
    assert f.fix and f.fix["kind"] == "archive_extract"
    from skynx.fixes import preview
    pv = preview(pack, f.fix, "es")
    assert any("Patchy.esp" in line for line in pv["changes"]) and any("activar Patchy.esp" in line for line in pv["changes"])
    apply(pack, f.fix)
    pack = Pack.open(pack.root)
    assert (pack.data_dir / "Patchy.esp").exists() and (pack.data_dir / "PatchyT.bsa").exists()
    assert not (pack.data_dir / "Patchy 1.0 NX.7z").exists()
    assert "Patchy.esp" in pack.list_entries
    loose = next(x for x in run_audit(pack).findings if x.code == "data-archive")
    with pytest.raises(Exception):
        apply(pack, loose.fix)             # only loose files: that one goes through Convert


def test_fixes_never_push_the_ccc_over_the_limit(tmp_path):
    pack = ae_pack(tmp_path / "p")
    raw = pack.list_path.read_bytes()
    filler = []
    n = 0
    while len(raw) + sum(len(x) + 2 for x in filler) < 4080:
        filler.append(f"Filler Plugin Number {n:04d}.esp")
        n += 1
    for name in filler:
        fake_plugin(pack.data_dir / name, ["Skyrim.esm"])
    pack.list_path.write_bytes(raw + "".join(x + "\r\n" for x in filler).encode())
    fake_plugin(pack.data_dir / "One More Plugin With A Long Name.esp", ["Skyrim.esm"])
    pack = Pack.open(pack.root)
    assert len(pack.list_path.read_bytes()) <= 4096
    with pytest.raises(FixError):
        apply(pack, {"kind": "list_add", "label_key": "fix-activate", "entry": "One More Plugin With A Long Name.esp"})
    assert "One More Plugin With A Long Name.esp" not in parse_ccc(pack.list_path.read_bytes()).entries
    m = tmp_path / "m"
    m.mkdir()
    fake_plugin(m / "Another Long Plugin Name Here.esp", ["Skyrim.esm"])
    with pytest.raises(Exception, match="4096"):
        add_mod(pack, m)


def test_rar_goes_through_7zip_or_tar(tmp_path, monkeypatch):
    from skynx import intake as I
    calls = []
    out7 = ("Path = Mod\nFolder = +\nSize = 0\nAttributes = D\n\n"
            "Path = Mod\\Mod.esp\nFolder = -\nSize = 120\nAttributes = A\n\n"
            "Path = Mod\\Mod.bsa\nFolder = -\nSize = 999\nAttributes = A\n")
    monkeypatch.setattr(I, "rar_tool", lambda: ["C:/Program Files/7-Zip/7z.exe"])
    monkeypatch.setattr(I, "_run_quiet", lambda cmd, timeout=3600: calls.append(cmd) or out7)
    rar = tmp_path / "Mod.rar"
    rar.write_bytes(b"Rar!")
    ms = I.list_names(rar)
    assert [(m.name, m.size, m.is_dir) for m in ms] == [("Mod", 0, True), ("Mod/Mod.esp", 120, False), ("Mod/Mod.bsa", 999, False)]
    I.safe_extract(rar, tmp_path / "x", targets=["Mod/Mod.esp"])
    assert calls[-1][:3] == ["C:/Program Files/7-Zip/7z.exe", "x", "-y"] and "-p-" in calls[-1]
    monkeypatch.setattr(I, "rar_tool", lambda: ["C:/Windows/System32/tar.exe"])
    monkeypatch.setattr(I, "_run_quiet", lambda cmd, timeout=3600: calls.append(cmd) or "Mod/\nMod/Mod.esp\n")
    assert [m.name for m in I.list_names(rar)] == ["Mod", "Mod/Mod.esp"]
    monkeypatch.setattr(I, "rar_tool", lambda: None)
    assert detect(rar).kind == "unknown"
