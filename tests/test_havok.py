"""Havok files to Switch with HavokBehaviorPostProcess (+ serde-hkx's hkxc).

The real tools are Windows programs; tests use the stand-ins in fake_tools,
which behave like the real ones where it matters (what they can load, exit
code 0 without output on failure, the contents version they accept). The
fixtures are real files: vanilla staggerbehavior.hkx as PC SE (Nemesis'
copy) and as Switch (from a working Switch port), which the real tool
produced byte for byte (Oct 2026, see havok.py).
"""
import struct
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT), str(ROOT / "tests")]

from skynx import havok as HV  # noqa: E402
from skynx import hkx as HKX  # noqa: E402
from skynx.tools import Toolset, locate  # noqa: E402

FIX = ROOT / "tests" / "fixtures" / "havok"
FAKE = ROOT / "tests" / "fake_tools"
if not (FIX / "staggerbehavior_pc.hkx").exists():   # the game's own files: not in the public repository
    pytest.skip("needs tests/fixtures/havok (see tests/README.md)", allow_module_level=True)
PC = (FIX / "staggerbehavior_pc.hkx").read_bytes()
NX = (FIX / "staggerbehavior_nx.hkx").read_bytes()


def pc32_anim() -> bytes:
    """A 32-bit (Oldrim) packfile header."""
    head = bytearray(b"\x57\xe0\xe0\x57\x10\xc0\xc0\x10" + bytes(56))
    head[12] = 8
    head[16:20] = bytes([4, 1, 0, 1])
    head[40:54] = b"hk_2010.2.0-r1"
    return bytes(head) + b"hkaSplineCompressedAnimation" + bytes(64)


def test_real_files_and_rules():
    assert len(PC) == len(NX) == 25552
    assert HV.rules(PC) == (8, 1, 0, 1) and HV.rules(NX) == HV.SWITCH_RULES
    assert HV.is_switch(NX) and not HV.is_switch(PC)
    assert HV.needs_havok(PC) == "behavior" and HV.needs_havok(NX) is None
    assert HV.needs_havok(pc32_anim()) == "pc32"
    assert HV.needs_havok(b'<?xml version="1.0"?><hkpackfile/>') == "xml"
    assert HV.rules(b"<?xml") is None


def test_fix_xml_version():
    nemesis = b'<hkpackfile classversion="8" contentsversion="hk_2010.2.0 - r1" toplevelobject="#0027">'
    assert HV.fix_xml(nemesis) == b'<hkpackfile classversion="8" contentsversion="hk_2010.2.0-r1" toplevelobject="#0027">'
    good = b'contentsversion="hk_2010.2.0-r1"'
    assert HV.fix_xml(good) == good


def test_tools_are_found_in_a_subfolder():
    ts = locate(FAKE)
    assert ts.hbpp and ts.hbpp.name == "HavokBehaviorPostProcess.exe"
    assert ts.hkxc and ts.hkxc.parent.name == "serde-hkx"
    assert ts.can_havok and ts.status()["havok"] is True


def test_to_switch_paths(tmp_path):
    ts = locate(FAKE)
    # 64-bit PC behavior: hkxc to XML, version fixed, then --platformps4
    out = HV.to_switch(PC, ts, tmp_path / "a", "staggerbehavior.hkx")
    assert HV.is_switch(out) and out[20:] == PC[20:]
    # already Switch: untouched
    assert HV.to_switch(NX, ts, tmp_path / "b") is NX
    # 32-bit: straight to the tool
    out = HV.to_switch(pc32_anim(), ts, tmp_path / "c", "idle.hkx")
    assert HV.is_switch(out)
    # XML with Nemesis' version string
    xml = b'<?xml version="1.0"?>\n<hkpackfile contentsversion="hk_2010.2.0 - r1">\n<!--fake:' + PC.hex().encode() + b"-->"
    out = HV.to_switch(xml, ts, tmp_path / "d", "0_master.hkx")
    assert HV.is_switch(out)


def test_to_switch_errors(tmp_path, monkeypatch):
    ts = locate(FAKE)
    only_hbpp = Toolset(ts.folder, hbpp=ts.hbpp)
    with pytest.raises(HV.HavokError) as e:
        HV.to_switch(PC, only_hbpp, tmp_path / "a")
    assert "hkxc" in e.value.en and "hkxc" in e.value.es
    with pytest.raises(HV.HavokError) as e:
        HV.to_switch(PC, Toolset(None), tmp_path / "b")
    assert "HavokBehaviorPostProcess" in e.value.en
    assert HV.is_switch(HV.to_switch(pc32_anim(), only_hbpp, tmp_path / "c"))   # 32-bit needs only hbpp
    monkeypatch.setenv("FAKE_HBPP_FAIL", "1")       # the real tool exits 0 and writes nothing
    with pytest.raises(HV.HavokError) as e:
        HV.to_switch(PC, ts, tmp_path / "d", "stagger.hkx")
    assert "didn't write" in e.value.en
    monkeypatch.delenv("FAKE_HBPP_FAIL")
    monkeypatch.setenv("FAKE_HKXC_FAIL", "1")
    with pytest.raises(HV.HavokError):
        HV.to_switch(PC, ts, tmp_path / "e", "stagger.hkx")


def test_can_convert():
    ts = locate(FAKE)
    assert HV.can_convert(ts, None) and HV.can_convert(ts, "behavior")
    only = Toolset(ts.folder, hbpp=ts.hbpp)
    assert HV.can_convert(only, "pc32") and HV.can_convert(only, "xml")
    assert not HV.can_convert(only, "skeleton") and not HV.can_convert(Toolset(None), "pc32")


def _mod_with_behaviors(tmp_path):
    tc = pytest.importorskip("test_convert")
    mod = tc.make_pc_mod(tmp_path)
    beh = mod / "meshes" / "actors" / "character" / "behaviors"
    beh.mkdir(parents=True)
    (beh / "FNIS_RynTest_Behavior.hkx").write_bytes(PC)
    anims = mod / "meshes" / "actors" / "character" / "animations" / "ryn"
    anims.mkdir(parents=True, exist_ok=True)
    (anims / "old_idle.hkx").write_bytes(pc32_anim())
    return tc, mod


def _convert(tmp_path, tools):
    from skynx.builder import create_project
    from skynx.converter import analyze, convert
    from skynx.pack import Pack
    tc, mod = _mod_with_behaviors(tmp_path)
    pack = Pack.open(create_project(tmp_path / "pack", "AE", tc.BASE_INIS, "none"))
    an = analyze(pack, mod)
    try:
        notes = [n["en"] for n in an.notes]
        res = convert(pack, an, {"sdk": False, "packing": "plugin"}, tools)
    finally:
        an.cleanup()
    return Pack.open(pack.root), res, notes


def _entries(pack, bsa):
    from skynx.bsa import read_bsa
    arc = read_bsa(pack.data_dir / bsa)
    with arc.path.open("rb") as f:
        return {e.path: arc.read_file(e, f) for e in arc.entries}


def test_converter_makes_behaviors_switch_native(tmp_path):
    pack, res, notes = _convert(tmp_path, locate(FAKE))
    assert any("behavior files are converted with" in n for n in notes)
    assert res["stats"]["hkx_havok"] >= 2 and res["stats"]["hkx_fail"] == 0
    files = _entries(pack, "Ryns Test.bsa")
    beh = files["meshes\\actors\\character\\behaviors\\fnis_ryntest_behavior.hkx"]
    old = files["meshes\\actors\\character\\animations\\ryn\\old_idle.hkx"]
    assert HV.is_switch(beh) and HV.is_switch(old)
    assert not any("stayed as they are" in n["en"] for n in res["notes"])


def test_converter_without_the_tools_says_so(tmp_path):
    ts = locate(FAKE)
    no_havok = Toolset(ts.folder, texconv=ts.texconv, ffmpeg=ts.ffmpeg, vgaudio=ts.vgaudio,
                       vgaudio_is_toolkit=ts.vgaudio_is_toolkit)
    pack, res, _notes = _convert(tmp_path, no_havok)
    assert res["stats"]["hkx_havok"] == 0
    files = _entries(pack, "Ryns Test.bsa")
    assert files["meshes\\actors\\character\\behaviors\\fnis_ryntest_behavior.hkx"] == PC   # left as it was
    msg = next(n for n in res["notes"] if "stayed as they are" in n["en"])
    assert "Havok files" in msg["en"] and "hkxc.exe" in msg["es"]
