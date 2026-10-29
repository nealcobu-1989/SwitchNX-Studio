"""Size choices wherever textures are converted: the "none" (original size)
rule with a maximum size, in the converter view and in the Diet of a BSA."""
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT), str(ROOT / "app"), str(ROOT / "tests")]

from skynx import nvn  # noqa: E402
from skynx.bsa import read_bsa  # noqa: E402
from skynx.builder import add_mod  # noqa: E402
from skynx.pack import Pack  # noqa: E402
from test_convert import plugin_bytes  # noqa: E402
from test_library import mini_pack  # noqa: E402
from test_v05 import _api  # noqa: E402

FAKE = ROOT / "tests" / "fake_tools"
USSEPT = ROOT / "tests" / "fixtures" / "ussep" / "USSEPT.bsa"


def test_convert_view_offers_the_original_size(tmp_path):
    import test_convert as TC
    from skynx.builder import create_project
    from skynx.converter import NO_PRESET, analysis_view, analyze
    from skynx.tools import locate
    pack = Pack.open(create_project(tmp_path / "p", "AE", TC.BASE_INIS, "none"))
    an = analyze(pack, TC.make_pc_mod(tmp_path))
    try:
        v = analysis_view(pack, an, locate(FAKE))
        assert set(v["estimates"]) == {"diet", "koka", "extreme", NO_PRESET}
        assert v["options"]["preset"] == "diet" and v["options"]["packing"] == "ini1"
        full = an.estimate(NO_PRESET, False)
        capped = an.estimate(NO_PRESET, False, 256)
        assert capped["after"] < full["after"] and capped["resize"] > full["resize"] == 0
    finally:
        an.cleanup()


def test_diet_dialog_estimate_and_apply(tmp_path, monkeypatch):
    api, run, _A = _api(tmp_path, monkeypatch)
    root = mini_pack(tmp_path / "P")
    m = tmp_path / "mod"
    m.mkdir()
    shutil.copy(USSEPT, m / "Tints - Textures.bsa")
    (m / "Tints.esp").write_bytes(plugin_bytes(["Skyrim.esm"]))
    add_mod(Pack.open(root), m)
    api._settings["tools_dir"] = str(FAKE)
    assert not run("open_pack", str(root))["error"]
    est = {}
    for rule, cap in (("none", None), ("none", 2048), ("none", 256), ("diet", None), ("koka", None)):
        r = api.diet_estimate("Tints - Textures.bsa", rule, cap, True)
        assert r["ok"], r
        est[(rule, cap)] = r["after"]
    assert est[("none", 256)] < est[("none", 2048)] <= est[("none", None)]
    assert not api.diet_estimate("Nope.bsa", "diet")["ok"]
    assert not api.diet_estimate("Tints - Textures.bsa", "huge")["ok"]
    assert not api.diet_estimate("Tints - Textures.bsa", "diet", 3000)["ok"]
    res = run("diet_bsa", "Tints - Textures.bsa", "none", 256, True)
    assert not res.get("error"), res
    p = Pack.open(root).data_dir / "Tints - Textures.bsa"
    arc = read_bsa(p)
    with p.open("rb") as fh:
        sides = [max(t.width, t.height) for t in (nvn.parse(arc.read_file(e, fh)) for e in arc.entries
                                                  if e.path.endswith(".dds")) if t.supported]
    assert sides and max(sides) <= 256
    h = api.history()
    top = (h.get("entries") if isinstance(h, dict) else h)[0]
    assert "none · 256 px" in str(top)
