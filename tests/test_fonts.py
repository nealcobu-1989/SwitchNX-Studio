"""Font mods: FontConfig.txt stays loose in Data\\Interface (fonts.py)."""
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT), str(ROOT / "tests")]

from skynx import fonts as FN  # noqa: E402
from skynx.bsa import read_bsa, write_bsa  # noqa: E402
from skynx.builder import add_mod, create_project, load_mods, remove_mod  # noqa: E402
from skynx.pack import Pack  # noqa: E402

BASE_INIS = ROOT / "tests" / "fixtures" / "base-inis"
CFG = ('fontlib "Interface\\fonts_console.swf"\nfontlib "Interface\\fonts_en.swf"\n'
       'fontlib "Interface\\fonts_sovngarde.swf"\n'
       'map "$EverywhereFont" = "Sovngarde" Normal\nmap "$ConsoleFont" = "SovngardeConsole" Normal\n')


def font_mod(tmp_path, name="Bold", lib="fonts_sovngarde.swf", cfg=CFG):
    m = tmp_path / name
    (m / "Interface").mkdir(parents=True)
    (m / "Interface" / "FontConfig.txt").write_text(cfg, encoding="utf-8")
    swf = tmp_path / f"{name}.swf"
    swf.write_bytes(b"FWS" + bytes(20))
    write_bsa([(f"interface\\{lib}", swf)], m / f"{name}.bsa")
    (m / "READ ME.txt").write_text("put FontConfig loose", encoding="utf-8")
    return m


def new_pack(tmp_path):
    return Pack.open(create_project(tmp_path / "pk", "AE", BASE_INIS, "none"))


def loose_fc(pack):
    d = pack.data_dir / "Interface"
    return next((p for p in d.iterdir() if p.name.lower() == "fontconfig.txt"), None) if d.is_dir() else None


def test_parse_and_label():
    fc = FN.parse(CFG)
    assert fc.libs == ["interface\\fonts_console.swf", "interface\\fonts_en.swf", "interface\\fonts_sovngarde.swf"]
    assert FN.label(fc) == "Sovngarde"


def test_detect_a_font_mod_as_addable(tmp_path):
    from skynx.intake import detect
    d = detect(font_mod(tmp_path))
    assert d.action == "add" and d.evidence.get("fontconfig")
    assert any("FontConfig.txt" in n[1] for n in d.notes)
    assert not d.evidence.get("loose_dirs")


def test_add_keeps_fontconfig_loose_and_remove_takes_it(tmp_path):
    from skynx.audit import run_audit
    pack = new_pack(tmp_path)
    rep = add_mod(pack, font_mod(tmp_path))
    pack = Pack.open(pack.root)
    f = loose_fc(pack)
    assert f is not None and f.read_text(encoding="utf-8") == CFG
    assert load_mods(pack)[rep.mod_id]["loose"] == ["Interface/FontConfig.txt"]
    assert any("Sovngarde" in es for _en, es in rep.notes)
    codes = {x.code for x in run_audit(pack, deep=False).findings}
    assert not {"data-loose", "font-missing-lib", "font-in-bsa"} & codes
    remove_mod(pack, rep.mod_id)
    assert loose_fc(Pack.open(pack.root)) is None


def test_a_second_font_replaces_the_first(tmp_path):
    pack = new_pack(tmp_path)
    r1 = add_mod(pack, font_mod(tmp_path / "a"))
    pack = Pack.open(pack.root)
    cfg2 = CFG.replace("fonts_sovngarde", "fonts_other").replace("Sovngarde", "Other")
    r2 = add_mod(pack, font_mod(tmp_path / "b", "Other", "fonts_other.swf", cfg2))
    pack = Pack.open(pack.root)
    assert "Other" in loose_fc(pack).read_text(encoding="utf-8")
    assert any("Sovngarde" in es and "Reemplaza" in es for _en, es in r2.notes)
    mods = load_mods(pack)
    assert "loose" not in mods[r1.mod_id] and mods[r2.mod_id]["loose"]
    remove_mod(pack, r1.mod_id)                      # the first one no longer owns it
    assert "Other" in loose_fc(Pack.open(pack.root)).read_text(encoding="utf-8")


def test_doctor_font_in_bsa_and_missing_lib(tmp_path):
    from skynx.audit import run_audit
    from skynx.fixes import apply
    pack = new_pack(tmp_path)
    m = tmp_path / "Packed"
    m.mkdir()
    cfg = tmp_path / "fc.txt"
    cfg.write_text(CFG, encoding="utf-8")
    swf = tmp_path / "s.swf"
    swf.write_bytes(b"FWS" + bytes(8))
    write_bsa([("interface\\fontconfig.txt", cfg), ("interface\\fonts_sovngarde.swf", swf)], m / "Packed.bsa")
    add_mod(pack, m)
    pack = Pack.open(pack.root)
    res = run_audit(pack, deep=False)
    f = next(x for x in res.findings if x.code == "font-in-bsa")
    apply(pack, f.fix)
    pack = Pack.open(pack.root)
    assert loose_fc(pack) is not None
    codes = {x.code for x in run_audit(pack, deep=False).findings}
    assert "font-in-bsa" not in codes and "font-missing-lib" not in codes
    # a config that names a library nobody has
    loose_fc(pack).write_text(CFG + 'fontlib "Interface\\fonts_gone.swf"\n', encoding="utf-8")
    g = next(x for x in run_audit(Pack.open(pack.root), deep=False).findings if x.code == "font-missing-lib")
    assert g.severity == "critico" and "fonts_gone.swf" in g.items


def test_converter_leaves_fontconfig_loose(tmp_path):
    tc = pytest.importorskip("test_convert")
    from skynx.converter import analyze, convert
    from skynx.tools import locate
    pack = Pack.open(create_project(tmp_path / "pk", "AE", tc.BASE_INIS, "none"))
    m = tmp_path / "PC Font"
    (m / "Interface").mkdir(parents=True)
    (m / "Interface" / "fontconfig.txt").write_text(CFG, encoding="utf-8")
    (m / "Interface" / "fonts_sovngarde.swf").write_bytes(b"FWS" + bytes(20))
    an = analyze(pack, m)
    try:
        convert(pack, an, {"sdk": False}, locate(ROOT / "tests" / "fake_tools"))
    finally:
        an.cleanup()
    pack = Pack.open(pack.root)
    assert loose_fc(pack).read_text(encoding="utf-8") == CFG
    inside = {e.path for b in pack.bsas.values() for e in read_bsa(b).entries}
    assert "interface\\fonts_sovngarde.swf" in inside and "interface\\fontconfig.txt" not in inside


def test_zip_with_names_windows_refuses(tmp_path):
    """Praedy's Sky AIO's zip has a folder "Praedy's Sky AIO - SE : AE NX":
    the ':' becomes '_' so it extracts on Windows."""
    import zipfile
    from skynx.intake import extracted_path, safe_extract, win_safe
    z = tmp_path / "sky.zip"
    with zipfile.ZipFile(z, "w") as f:
        f.writestr("Praedy's Sky AIO - SE : AE NX/MoonGlowSize.esp", b"TES4")
        f.writestr("Praedy's Sky AIO - SE : AE NX/", b"")
        f.writestr("ok/con.txt", b"x")
    out = safe_extract(z, tmp_path / "out")
    assert (out / "Praedy's Sky AIO - SE _ AE NX" / "MoonGlowSize.esp").read_bytes() == b"TES4"
    assert (out / "ok" / "con_.txt").exists()
    assert win_safe("a/b.esp") == "a/b.esp" and win_safe("x. /y") == "x/y"
    assert extracted_path(out, "Praedy's Sky AIO - SE : AE NX/MoonGlowSize.esp").is_file()
    with pytest.raises(Exception):
        bad = tmp_path / "bad.zip"
        with zipfile.ZipFile(bad, "w") as f:
            f.writestr("../evil.esp", b"x")
        safe_extract(bad, tmp_path / "out2")


def test_7z_with_names_windows_refuses(tmp_path):
    py7zr = pytest.importorskip("py7zr")
    from skynx.intake import safe_extract
    src = tmp_path / "s"
    (src / "Sky : AE").mkdir(parents=True)
    (src / "Sky : AE" / "Moon.esp").write_bytes(b"TES4")
    (src / "ok.txt").write_bytes(b"ok")
    arc = tmp_path / "sky.7z"
    with py7zr.SevenZipFile(arc, "w") as z:
        z.write(src / "Sky : AE" / "Moon.esp", "Sky : AE/Moon.esp")
        z.write(src / "ok.txt", "ok.txt")
    out = safe_extract(arc, tmp_path / "out")
    assert (out / "Sky _ AE" / "Moon.esp").read_bytes() == b"TES4"
    assert (out / "ok.txt").read_bytes() == b"ok"
