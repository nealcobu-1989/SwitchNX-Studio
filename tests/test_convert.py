"""Converter tests with a synthetic PC mod and stand-in tools (tests/fake_tools).

The stand-ins: texconv converts for real (Pillow + etcpak), NvnTexpkg and
VGAudioCli write files with the right magic numbers, ffmpeg is the real one.
Real Switch files from the community packs are used where available.
"""
import os
import shutil
import struct
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from skynx import nif as NIF  # noqa: E402
from skynx import nxaudio as NXA  # noqa: E402
from skynx import pex as PEX  # noqa: E402
from skynx import rename as RN  # noqa: E402
from skynx.bsa import read_bsa, write_bsa  # noqa: E402
from skynx.builder import create_project, load_mods  # noqa: E402
from skynx.ccc import read_ccc  # noqa: E402
from skynx.converter import analyze, convert  # noqa: E402
from skynx.history import list_history, undo  # noqa: E402
from skynx.pack import Pack  # noqa: E402
from skynx.plugin import read_header  # noqa: E402
from skynx.textures import inspect  # noqa: E402
from skynx.tools import locate  # noqa: E402

FAKE = ROOT / "tests" / "fake_tools"
BASE_INIS = ROOT / "tests" / "fixtures" / "base-inis"
PACKS = Path("private-test-data/SkyNX/Other modpacks")

etcpak = pytest.importorskip("etcpak")
pytest.importorskip("texture2ddecoder")
pytestmark = pytest.mark.skipif(not shutil.which("ffmpeg"), reason="needs ffmpeg")


# ------------------------------------------------------------------ fixtures
def plugin_bytes(masters=(), flags=0, records=1):
    sub = struct.pack("<4sHfiI", b"HEDR", 12, 1.71, records, 0x800)
    sub += struct.pack("<4sH", b"CNAM", 5) + b"test\0"
    for m in masters:
        enc = m.encode("cp1252") + b"\0"
        sub += struct.pack("<4sH", b"MAST", len(enc)) + enc
        sub += struct.pack("<4sHQ", b"DATA", 8, 0)
    return struct.pack("<4sIIIHHHH", b"TES4", len(sub), flags, 0, 0, 0, 44, 0) + sub


def dds(w, h, fmt="DXT5", alpha=255, mips=1):
    from PIL import Image
    img = Image.new("RGBA", (w, h), (120, 80, 40, alpha))
    for x in range(0, w, 8):
        img.putpixel((x, x % h), (255, 255, 255, alpha))
    hd = bytearray(128)
    hd[0:4] = b"DDS "
    struct.pack_into("<IIIIIII", hd, 4, 124, 0x0002100F, h, w, 0, 0, mips)
    if fmt == "BC7":
        struct.pack_into("<II4s", hd, 76, 32, 4, b"DX10")
        ext = struct.pack("<IIIII", 98, 3, 0, 1, 0)
        return bytes(hd) + ext + etcpak.compress_bc7(img.tobytes("raw", "BGRA"), w, h)
    struct.pack_into("<II4s", hd, 76, 32, 4, fmt.encode())
    enc = {"DXT5": etcpak.compress_bc3, "DXT1": etcpak.compress_bc1, "ATI2": etcpak.compress_bc5}[fmt]
    return bytes(hd) + enc(img.tobytes("raw", "BGRA"), w, h)


def wav_bytes(seconds=0.3, rate=44100, ch=2):
    n = int(seconds * rate)
    data = b"".join(struct.pack("<h", int(3000 * ((i // 50) % 2 * 2 - 1))) * ch for i in range(n))
    fmt = struct.pack("<HHIIHH", 1, ch, rate, rate * 2 * ch, 2 * ch, 16)
    return (b"RIFF" + struct.pack("<I", 36 + len(data)) + b"WAVE" + b"fmt " + struct.pack("<I", 16) +
            fmt + b"data" + struct.pack("<I", len(data)) + data)


def pex_bytes(strings):
    out = bytearray(b"\xfa\x57\xc0\xde" + bytes([3, 2]) + struct.pack(">H", 1) + b"\0" * 8)
    for s in ("x.psc", "u", "m"):
        out += struct.pack(">H", len(s)) + s.encode()
    out += struct.pack(">H", len(strings))
    for s in strings:
        out += struct.pack(">H", len(s)) + s.encode("cp1252")
    out += b"\x01\x02\x03tail"
    return bytes(out)


def real_facegen_nif():
    for p in PACKS.rglob("*.bsa"):
        if "ryn" in p.name.lower():
            arc = read_bsa(p)
            for e in arc.entries:
                if e.name.endswith(".nif") and "facegeom" in e.folder:
                    return arc.read_file(e), e.folder.split("\\")[-1]
    return None, None


def real_nx_hkx():
    for p in PACKS.rglob("*.bsa"):
        arc = read_bsa(p)
        for e in arc.entries:
            if e.name.endswith(".hkx"):
                raw = arc.read_file(e)
                if b"hkaSkeleton" not in raw and b"hkbBehavior" not in raw and len(raw) > 200:
                    return raw
    return None


@pytest.fixture()
def project(tmp_path):
    root = create_project(tmp_path / "pack", "AE", BASE_INIS, "ussep")
    return Pack.open(root)


@pytest.fixture()
def pc_mod(tmp_path):
    return make_pc_mod(tmp_path)


def make_pc_mod(tmp_path):
    m = tmp_path / "Ryns Test Mod"
    m.mkdir()
    (m / "Ryn's Test.esp").write_bytes(plugin_bytes(["Skyrim.esm"]))
    (m / "Ryn's Test - Patch.esp").write_bytes(plugin_bytes(["Skyrim.esm", "Ryn's Test.esp"]))
    t = m / "textures" / "ryn"
    t.mkdir(parents=True)
    (t / "big.dds").write_bytes(dds(2048, 2048, "DXT5", alpha=255))
    (t / "big_n.dds").write_bytes(dds(1024, 1024, "ATI2"))
    (t / "cloak.dds").write_bytes(dds(512, 512, "DXT5", alpha=100))
    (t / "gem.dds").write_bytes(dds(256, 256, "BC7"))
    ui = m / "interface" / "ryn"
    ui.mkdir(parents=True)
    (ui / "icon.dds").write_bytes(dds(2048, 64, "DXT5"))
    voice = m / "sound" / "voice" / "ryn's test.esp" / "maleeventoned"
    voice.mkdir(parents=True)
    lip = b"LIPDATA" * 3
    w = wav_bytes(0.4, 22050, 1)
    (voice / "hello_1.fuz").write_bytes(b"FUZE" + struct.pack("<II", 1, len(lip)) + lip + w)
    music = m / "music" / "ryn"
    music.mkdir(parents=True)
    (music / "theme.wav").write_bytes(wav_bytes(0.5))
    raw, folder = real_facegen_nif()
    if raw:
        fg = m / "meshes" / "actors" / "character" / "facegendata" / "facegeom" / "Ryn's Test.esp"
        fg.mkdir(parents=True)
        seg = [t for t in NIF.texture_paths(NIF.parse(raw)) if "facetint" in t.lower()][0].split("\\")[-2]
        new, _ = NIF.replace_texture_folder(raw, seg, "Ryn's Test.esp")
        (fg / "00000a5d.nif").write_bytes(new)
    sc = m / "scripts"
    sc.mkdir()
    (sc / "rynquest.pex").write_bytes(pex_bytes(["GetFormFromFile", "Ryn's Test.esp", "x"]))
    (sc / "rynquest.psc").write_text("source")
    (m / "seq").mkdir()
    (m / "seq" / "Ryn's Test.seq").write_bytes(b"\0\1\2\3")
    hk = real_nx_hkx()
    if hk:
        an = m / "meshes" / "actors" / "character" / "animations" / "ryn"
        an.mkdir(parents=True)
        pc = bytearray(hk)
        pc[18] = 0
        (an / "idle.hkx").write_bytes(bytes(pc))
    (m / "readme.txt").write_text("hi")
    (m / "skse" / "plugins").mkdir(parents=True)
    (m / "skse" / "plugins" / "x.dll").write_bytes(b"MZ")
    return m


def tools():
    return locate(FAKE)


# ------------------------------------------------------------------ unit
def test_safe_names():
    assert RN.safe_name("Ryn's Standing Stones.esp") == "Ryns Standing Stones.esp"
    assert RN.safe_name("dD - Enhanced Blood Main LITE..esp") == "dD - Enhanced Blood Main LITE.esp"
    assert RN.safe_name("Città.esm") == "Citta.esm"
    assert RN.compact_name("Ryn's Standing Stones.esp") == "RynsStandingStones.esp"
    assert RN.check_name("Ok Name.esp") is None
    assert RN.check_name("Bad'Name.esp") == "chars"


def test_write_bsa_roundtrip(tmp_path):
    files = []
    for i, (rel, data) in enumerate([("meshes\\a\\x.nif", b"Gamebryo" * 100),
                                     ("textures\\a\\x.dds", b"DDS " + b"\1" * 300),
                                     ("sound\\voice\\m.esp\\v\\a.fuz", b"FUZE" + b"\2" * 50)]):
        p = tmp_path / f"f{i}"
        p.write_bytes(data)
        files.append((rel, p))
    out = write_bsa(files, tmp_path / "t.bsa")
    arc = read_bsa(out)
    got = {e.path: arc.read_file(e) for e in arc.entries}
    assert got == {r: p.read_bytes() for r, p in files}
    nif = next(e for e in arc.entries if e.name == "x.nif")
    assert nif.compressed and not next(e for e in arc.entries if e.name == "x.dds").compressed


def test_pex_rename():
    raw = pex_bytes(["Foo", "Ryn's Test.esp", "bar"])
    new, n = PEX.rename_plugin(raw, "ryn's test.esp", "RynsTest.esp")
    assert n == 1 and PEX.strings(new) == ["Foo", "RynsTest.esp", "bar"]
    assert new.endswith(b"\x01\x02\x03tail")


# ------------------------------------------------------------------ end to end
def test_convert_end_to_end(project, pc_mod):
    ts = tools()
    assert ts.sdk and ts.can_audio and ts.can_textures
    an = analyze(project, pc_mod)
    names = {p["name"]: p for p in an.plugins}
    assert names["Ryn's Test.esp"]["suggested"] == "Ryns Test.esp"
    assert "chars" in names["Ryn's Test.esp"]["reasons"]
    assert any("SKSE" in n["en"] for n in an.notes)
    est = an.estimate("koka", True)
    assert est["after"] < est["before"]
    ccc_before = project.ccc.size
    res = convert(project, an, {"packing": "plugin", "preset": "diet", "sdk": True, "bc1": True,
                                "names": {"Ryn's Test.esp": "RynsTest.esp"}}, ts)
    an.cleanup()
    pack = Pack.open(project.root)
    data = pack.data_dir
    assert (data / "RynsTest.esp").exists()
    assert res["renamed"]["RynsTest.esp"] == "Ryn's Test.esp"
    patch = read_header(data / "Ryns Test - Patch.esp")
    assert patch.masters == ["Skyrim.esm", "RynsTest.esp"]
    entries = read_ccc(pack.ccc_path).entries
    assert entries.index("RynsTest.esp") < entries.index("Ryns Test - Patch.esp")
    assert pack.ccc.size > ccc_before
    # BSAs named after the master plugin, so they load by themselves
    assert set(res["bsas"]) == {"RynsTest.bsa", "RynsTest - Textures.bsa"}
    main = read_bsa(data / "RynsTest.bsa")
    tex = read_bsa(data / "RynsTest - Textures.bsa")
    paths = {e.path for e in main.entries}
    assert not any(p.endswith(".psc") for p in paths)
    assert "seq\\rynstest.seq" in paths
    assert any(p.startswith("sound\\voice\\rynstest.esp\\") and p.endswith(".fuz") for p in paths)
    assert "music\\ryn\\theme.mcadpcm" in paths
    with (data / "RynsTest.bsa").open("rb") as f:
        for e in main.entries:
            raw = main.read_file(e, f)
            if e.name.endswith(".fuz"):
                fz = NXA.parse_nx_fuz(raw)
                assert fz["lip"] == b"LIPDATA" * 3 and fz["channels"] == 1 and fz["duration_ms"] > 300
            if e.name.endswith(".pex"):
                assert "RynsTest.esp" in PEX.strings(raw)
            if e.name.endswith(".hkx"):
                # synthetic PC file (a Switch file with the flag cleared): the
                # Toolkit's section header isn't there, so it goes through
                # HavokBehaviorPostProcess (the fake one here)
                assert raw[18] == (1 if res["stats"]["hkx_ok"] or res["stats"]["hkx_havok"] else 0)
            if e.name.endswith(".nif") and "facegeom" in e.folder:
                tints = [t for t in NIF.texture_paths(NIF.parse(raw)) if "facetint" in t.lower()]
                assert tints and all("\\RynsTest.esp\\" in t for t in tints)
    # textures went through NvnTexpkg (fake writes DFvN)
    with (data / "RynsTest - Textures.bsa").open("rb") as f:
        heads = {e.name: tex.read_head(e, 4, f) for e in tex.entries}
    assert all(h == b"DFvN" for h in heads.values()), heads
    assert res["stats"]["hkx_ok"] + res["stats"]["hkx_fail"] + res["stats"]["hkx_havok"] == (1 if real_nx_hkx() else 0)
    assert res["stats"]["tex_bc1"] >= 1          # the opaque 2048 BC3 went to BC1
    assert res["stats"]["after"] < res["stats"]["before"]
    # records + undo
    rec = next(iter(load_mods(pack).values()))
    assert rec["renamed"] == {"RynsTest.esp": "Ryn's Test.esp", "Ryns Test - Patch.esp": "Ryn's Test - Patch.esp"}
    hist = list_history(pack.root)
    undo(pack.root, hist[0]["id"])
    pack = Pack.open(project.root)
    assert not (pack.data_dir / "RynsTest.esp").exists()
    assert "RynsTest.esp" not in read_ccc(pack.ccc_path).entries


def test_pc_dds_mode_and_texture_sizes(project, pc_mod, tmp_path):
    ts = tools()
    an = analyze(project, pc_mod)
    res = convert(project, an, {"packing": "plugin", "preset": "diet", "sdk": False}, ts)
    an.cleanup()
    pack = Pack.open(project.root)
    info = {}
    for name in res["bsas"]:
        arc = read_bsa(pack.data_dir / name)
        with (pack.data_dir / name).open("rb") as f:
            info.update({e.name: inspect(arc.read_head(e, 256, f)) for e in arc.entries
                         if e.name.endswith(".dds")})
    assert info["big.dds"].fmt == "BC3" and info["big.dds"].width == 1024     # diet: 1024
    assert info["big_n.dds"].fmt == "BC5" and info["big_n.dds"].width == 512  # maps: 512
    assert info["gem.dds"].fmt == "BC3"                                       # BC7 -> DXT5
    assert info["cloak.dds"].fmt == "BC3"
    assert (info["icon.dds"].width, info["icon.dds"].height) == (2048, 64)    # UI never resized
    assert all(i.mips > 1 for n, i in info.items() if n != "icon.dds")


def test_registry_points_later_mods_at_new_name(project, pc_mod, tmp_path):
    ts = tools()
    an = analyze(project, pc_mod)
    convert(project, an, {"packing": "plugin", "preset": "koka", "names": {"Ryn's Test.esp": "RynsTest.esp"}}, ts)
    an.cleanup()
    pack = Pack.open(project.root)
    addon = tmp_path / "Addon"
    addon.mkdir()
    (addon / "Ryn Addon.esp").write_bytes(plugin_bytes(["Skyrim.esm", "Ryn's Test.esp"]))
    v = addon / "sound" / "voice" / "ryn's test.esp" / "x"
    v.mkdir(parents=True)
    (v / "a_1.wav").write_bytes(wav_bytes(0.2, 48000, 1))
    an2 = analyze(pack, addon)
    assert an2.masters_map == {"Ryn's Test.esp": "RynsTest.esp"}
    res = convert(pack, an2, {"packing": "plugin", "preset": "koka"}, ts)
    an2.cleanup()
    pack = Pack.open(project.root)
    assert read_header(pack.data_dir / "Ryn Addon.esp").masters[-1] == "RynsTest.esp"
    arc = read_bsa(pack.data_dir / res["bsas"][0])
    assert any(e.folder.startswith("sound\\voice\\rynstest.esp") for e in arc.entries)


def test_nvn_failure_falls_back_to_dxt5(project, pc_mod, monkeypatch):
    monkeypatch.setenv("FAKE_NVN_FAIL", "1")
    ts = tools()
    an = analyze(project, pc_mod)
    res = convert(project, an, {"packing": "plugin", "preset": "koka", "sdk": True}, ts)
    an.cleanup()
    pack = Pack.open(project.root)
    name = [b for b in res["bsas"] if "Textures" in b][0]
    tex = read_bsa(pack.data_dir / name)
    with (pack.data_dir / name).open("rb") as f:
        fmts = {inspect(tex.read_head(e, 256, f)).fmt for e in tex.entries}
    assert fmts <= {"BC3", "BC5"}
    assert any(n["level"] == "warn" for n in res["notes"])


def test_fomod_is_refused(project, tmp_path):
    m = tmp_path / "F"
    (m / "fomod").mkdir(parents=True)
    (m / "fomod" / "ModuleConfig.xml").write_text("<x/>")
    (m / "00 Core" / "textures").mkdir(parents=True)
    with pytest.raises(Exception) as e:
        analyze(project, m)
    assert "FOMOD" in str(e.value.args)


# ------------------------------------------------------------------ review cases
def _tree(tmp_path, files: dict):
    t = tmp_path / "t"
    for rel, data in files.items():
        p = t.joinpath(*rel.split("/"))
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_bytes(data if isinstance(data, bytes) else data.encode())
    return t


def test_rename_strings_exact_and_chain(tmp_path):
    t = _tree(tmp_path, {
        "Foo's.esp": plugin_bytes(), "Foos.esp": plugin_bytes(),
        "Bar.esp": plugin_bytes(["Foo's.esp", "Foos.esp"]),
        "strings/foo's_english.strings": b"a", "strings/foo's_patch_english.strings": b"b",
        "seq/foos.seq": b"s",
        "sound/voice/foo's.esp/x/a.fuz": b"1", "sound/voice/foos.esp/x/b.fuz": b"2",
        "meshes/oar/config.json": '{"a": "Foo\'s.esp", "b": "Foos.esp", "c": "Other Foos.esp"}',
        "x.ini": "plugin = Foo's.esp\nother=My Foos.esp\n".encode("cp1252") + "configuración".encode("cp1252"),
    })
    RN.apply(t, {"Foo's.esp": "Foos.esp", "Foos.esp": "Foos2.esp"})
    names = sorted(p.name for p in t.iterdir() if p.is_file())
    assert names == ["Bar.esp", "Foos.esp", "Foos2.esp", "x.ini"]
    assert read_header(t / "Bar.esp").masters == ["Foos.esp", "Foos2.esp"]
    s = sorted(p.name for p in (t / "strings").iterdir())
    assert s == ["foo's_patch_english.strings", "foos_english.strings"]
    assert (t / "seq" / "foos2.seq").exists()
    assert (t / "sound/voice/foos.esp/x/a.fuz").read_bytes() == b"1"
    assert (t / "sound/voice/foos2.esp/x/b.fuz").read_bytes() == b"2"
    assert (t / "meshes/oar/config.json").read_text() == '{"a": "Foos.esp", "b": "Foos2.esp", "c": "Other Foos.esp"}'
    ini = (t / "x.ini").read_bytes().decode("cp1252")
    assert "plugin = Foos.esp" in ini and "other=My Foos.esp" in ini and "configuración" in ini


def test_rename_case_only_keeps_voices(tmp_path):
    t = _tree(tmp_path, {"mymod.esp": plugin_bytes(), "sound/voice/mymod.esp/x/a.lip": b"L"})
    RN.apply(t, {"mymod.esp": "Mymod.esp"})
    assert (t / "Mymod.esp").exists()
    assert list((t / "sound/voice").rglob("a.lip"))[0].read_bytes() == b"L"


def test_pex_with_foreign_bytes(tmp_path):
    raw = pex_bytes(["Mod's.esp"])[:-7]
    raw += struct.pack(">H", 3) + "あ".encode("utf-8") + b"\x01\x02\x03tail"
    # adjust count: rebuild with an extra Shift-JIS/UTF-8 string
    raw = bytearray(pex_bytes(["Mod's.esp", "x"]))
    i = raw.find(b"\x00\x01x")
    raw[i:i + 3] = struct.pack(">H", 3) + "あ".encode("utf-8")
    new, n = PEX.rename_plugin(bytes(raw), "mod's.esp", "Mods.esp")
    assert n == 1 and "あ".encode("utf-8") in new
    t = _tree(tmp_path, {"Mod's.esp": plugin_bytes(), "scripts/other.pex": b"\xfa\x57\xc0\xde\x03" + bytes(5)})
    RN.apply(t, {"Mod's.esp": "Mods.esp"})   # an unrelated broken script doesn't stop the rename
    assert (t / "Mods.esp").exists()


def test_interrupted_change_is_rolled_back(project, tmp_path):
    from skynx.history import recover_interrupted
    data = project.data_dir
    ccc = project.ccc_path
    before = ccc.read_bytes()
    src = tmp_path / "A.esp"
    src.write_bytes(plugin_bytes())
    code = f"""
import os, sys
sys.path.insert(0, {str(ROOT)!r})
from pathlib import Path
from skynx.history import Transaction
with Transaction(Path({str(project.root)!r}), "Add mod: A") as tx:
    tx.copy_in(Path({str(src)!r}), Path({str(data / 'A.esp')!r}))
    tx.write_bytes(Path({str(ccc)!r}), b"broken")
    os._exit(1)
"""
    subprocess.run([sys.executable, "-c", code])
    assert (data / "A.esp").exists() and ccc.read_bytes() == b"broken"
    assert recover_interrupted(project.root) == ["Add mod: A"]
    assert not (data / "A.esp").exists() and ccc.read_bytes() == before
    assert recover_interrupted(project.root) == []


# ------------------------------------------------------------------ language inis
CONSOLE_INIS = ROOT / "tests" / "fixtures" / "console-inis"


def test_console_base_and_language_ini(tmp_path):
    from skynx.audit import run_audit
    from skynx.builder import add_mod
    from skynx.fixes import apply
    from skynx.ini import parse_ini
    root = create_project(tmp_path / "p", "AE", CONSOLE_INIS, "base")
    pack = Pack.open(root)
    assert [p.name for p in pack.ini_paths] == ["Skyrim.ini", "Skyrim_en.ini"]
    assert len(read_ccc(pack.ccc_path).entries) == 80
    # a texture-only BSA without plugin goes to List2 of BOTH inis
    m = tmp_path / "Tex"
    m.mkdir()
    f = tmp_path / "x.dds"
    f.write_bytes(dds(64, 64))
    write_bsa([("textures\\a\\x.dds", f)], m / "TexOnly.bsa")
    add_mod(pack, m)
    pack = Pack.open(root)
    for ini in pack.ini_paths:
        assert "TexOnly.bsa" in parse_ini(ini.read_bytes()).archive_list("sResourceArchiveList2")
    assert not [x for x in run_audit(pack, deep=False).findings if x.code.startswith("lang-")]
    # an entry only in Skyrim.ini is hidden by Skyrim_es.ini: reported and fixable
    from skynx.ini import set_archive_list
    es = pack.base_romfs / "Skyrim_en.ini"
    raw = es.read_bytes()
    es.write_bytes(set_archive_list(raw, "sResourceArchiveList2",
                                    [b for b in parse_ini(raw).archive_list("sResourceArchiveList2") if b != "TexOnly.bsa"]))
    pack = Pack.open(root)
    hides = [x for x in run_audit(pack, deep=False).findings if x.code == "lang-ini-hides"]
    assert len(hides) == 1 and hides[0].items == ["TexOnly.bsa"]
    apply(pack, hides[0].fix)
    pack = Pack.open(root)
    assert "TexOnly.bsa" in parse_ini(es.read_bytes()).archive_list("sResourceArchiveList2")


# ------------------------------------------------------------------ FOMOD
FOMOD_XML = """<?xml version="1.0" encoding="UTF-16"?>
<config xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" xsi:noNamespaceSchemaLocation="http://qconsulting.ca/fo3/ModConfig5.0.xsd">
  <moduleName>My FOMOD Mod</moduleName>
  <moduleImage path="fomod\\images\\head.png"/>
  <requiredInstallFiles>
    <folder source="00 core" destination=""/>
  </requiredInstallFiles>
  <installSteps order="Explicit">
    <installStep name="Main">
      <optionalFileGroups>
        <group name="Texture size" type="SelectExactlyOne">
          <plugins>
            <plugin name="Zeta 1K">
              <description>Smaller.</description>
              <image path="fomod/images/1k.png"/>
              <files><folder source="Tex 1K" destination="textures\\mymod" priority="1"/></files>
              <conditionFlags><flag name="tex">1k</flag></conditionFlags>
              <typeDescriptor><type name="Recommended"/></typeDescriptor>
            </plugin>
            <plugin name="Alpha 2K">
              <description>Bigger.</description>
              <files><folder source="Tex 2K" destination="textures\\mymod" priority="1"/></files>
              <conditionFlags><flag name="tex">2k</flag></conditionFlags>
              <typeDescriptor><type name="Optional"/></typeDescriptor>
            </plugin>
          </plugins>
        </group>
      </optionalFileGroups>
    </installStep>
    <installStep name="Patches">
      <visible><flagDependency flag="tex" value="1k"/></visible>
      <optionalFileGroups>
        <group name="Patches" type="SelectAny">
          <plugins>
            <plugin name="USSEP patch">
              <description>Needs USSEP.</description>
              <files><file source="patches/MyMod - USSEP.esp" destination="MyMod - USSEP.esp"/></files>
              <typeDescriptor><dependencyType><defaultType name="NotUsable"/>
                <patterns><pattern><dependencies operator="And">
                  <fileDependency file="Unofficial Skyrim Special Edition Patch.esp" state="Active"/>
                </dependencies><type name="Recommended"/></pattern></patterns>
              </dependencyType></typeDescriptor>
            </plugin>
            <plugin name="Ryn patch">
              <description>Needs Ryn's.</description>
              <files><file source="patches/MyMod - Ryn.esp" destination="MyMod - Ryn.esp"/></files>
              <typeDescriptor><dependencyType><defaultType name="NotUsable"/>
                <patterns><pattern><dependencies>
                  <fileDependency file="Ryn's Test.esp" state="Active"/>
                </dependencies><type name="Recommended"/></pattern></patterns>
              </dependencyType></typeDescriptor>
            </plugin>
          </plugins>
        </group>
      </optionalFileGroups>
    </installStep>
  </installSteps>
  <conditionalFileInstalls><patterns>
    <pattern><dependencies><flagDependency flag="tex" value="1k"/></dependencies>
      <files><folder source="Cond" destination=""/></files></pattern>
  </patterns></conditionalFileInstalls>
</config>
"""


def make_fomod_zip(tmp_path):
    import zipfile
    from PIL import Image
    z = tmp_path / "My FOMOD Mod-123-1-0.zip"
    img = tmp_path / "i.png"
    Image.new("RGB", (32, 16), (200, 150, 40)).save(img)
    with zipfile.ZipFile(z, "w") as zf:
        zf.writestr("fomod/ModuleConfig.xml", b"\xff\xfe" + FOMOD_XML.encode("utf-16-le"))
        zf.write(img, "fomod/images/1k.png")
        zf.write(img, "fomod/images/head.png")
        zf.writestr("00 Core/MyMod.esp", plugin_bytes(["Skyrim.esm"]))
        zf.writestr("00 Core/textures/mymod/a.dds", dds(64, 64))
        zf.writestr("00 Core/meshes/mymod/a.nif", b"x")
        zf.writestr("Tex 1K/a.dds", dds(32, 32))
        zf.writestr("Tex 2K/a.dds", dds(128, 128))
        zf.writestr("patches/MyMod - USSEP.esp", plugin_bytes(["MyMod.esp", "Unofficial Skyrim Special Edition Patch.esp"]))
        zf.writestr("patches/MyMod - Ryn.esp", plugin_bytes(["MyMod.esp", "Ryn's Test.esp"]))
        zf.writestr("Cond/meshes/mymod/cond.nif", b"y")
    return z


def test_fomod_rules(project, tmp_path):
    from skynx import fomod as FM
    from skynx.converter import FomodSession, start
    sess = start(project, make_fomod_zip(tmp_path))
    assert isinstance(sess, FomodSession)
    fm = sess.fm
    assert fm.name == "My FOMOD Mod"
    assert [s.name for s in fm.steps] == ["Main", "Patches"]                      # Explicit
    assert [o.name for o in fm.steps[0].groups[0].options] == ["Alpha 2K", "Zeta 1K"]  # Ascending
    ev = FM.evaluate(fm, sess.ctx, {})
    assert ev["steps"][0]["groups"][0]["selected"] == [1]          # the recommended one
    assert ev["steps"][1]["visible"]
    types = [o["type"] for o in ev["steps"][1]["groups"][0]["options"]]
    assert types == ["NotUsable", "NotUsable"]                      # no USSEP, no Ryn in the pack
    files = dict((r.lower(), p) for r, p in FM.plan_files(fm, sess.ctx, ev))
    assert files["textures\\mymod\\a.dds"].parent.name == "Tex 1K"  # priority 1 beats 0
    assert "meshes\\mymod\\cond.nif" in files                        # conditional install
    assert "mymod.esp" in files and "mymod - ussep.esp" not in files
    # choosing 2K hides the patches step and drops the conditional files
    ev2 = FM.evaluate(fm, sess.ctx, {"0": {"0": [0]}})
    assert not ev2["steps"][1]["visible"]
    files2 = dict((r.lower(), p) for r, p in FM.plan_files(fm, sess.ctx, ev2))
    assert files2["textures\\mymod\\a.dds"].parent.name == "Tex 2K" and "meshes\\mymod\\cond.nif" not in files2
    # NotUsable can't be forced on
    ev3 = FM.evaluate(fm, sess.ctx, {"1": {"0": [0, 1]}})
    assert ev3["steps"][1]["groups"][0]["selected"] == []
    assert FM.step_images(fm, 0)["0:1"].startswith("data:image/png;base64,")
    sess.cleanup()


def test_fomod_patch_follows_renamed_master(project, pc_mod, tmp_path):
    from skynx import fomod as FM
    from skynx.converter import fomod_finish, start
    ts = tools()
    an = analyze(project, pc_mod)
    convert(project, an, {"packing": "plugin", "preset": "koka", "names": {"Ryn's Test.esp": "RynsTest.esp"}}, ts)
    an.cleanup()
    pack = Pack.open(project.root)
    sess = start(pack, make_fomod_zip(tmp_path))
    ev = FM.evaluate(sess.fm, sess.ctx, {})
    types = [o["type"] for o in ev["steps"][1]["groups"][0]["options"]]
    assert types == ["Recommended", "NotUsable"]        # sorted: Ryn patch, USSEP patch
    an2 = fomod_finish(pack, sess, {})
    names = sorted(p["name"] for p in an2.plugins)
    assert names == ["MyMod - Ryn.esp", "MyMod.esp"]
    assert an2.masters_map == {"Ryn's Test.esp": "RynsTest.esp"}
    res = convert(pack, an2, {"packing": "plugin", "preset": "koka"}, ts)
    an2.cleanup()
    pack = Pack.open(project.root)
    assert read_header(pack.data_dir / "MyMod - Ryn.esp").masters == ["MyMod.esp", "RynsTest.esp"]
    rec = load_mods(pack)[an2.id]
    assert rec["fomod"] == {"Main": {"Texture size": ["Zeta 1K"]}, "Patches": {"Patches": ["Ryn patch"]}}
    assert set(res["bsas"]) == {"MyMod.bsa", "MyMod - Textures.bsa"}


# ------------------------------------------------------------------ Switch mods through the converter
RYN = Path("private-test-data/SkyNX/Other modpacks/Avner ModPack Revised 2026/Avner ModPack Revised 2026/01000A10041EA000/romfs/Data")


@pytest.mark.skipif(not (RYN / "Ryn_s Standing Stones.bsa").exists(), reason="real files missing")
def test_drive_damaged_switch_mod_gets_safe_name(project, tmp_path):
    m = tmp_path / "Ryn"
    m.mkdir()
    for f in ("Ryn_s Standing Stones.esp", "Ryn_s Standing Stones.bsa"):
        shutil.copy(RYN / f, m / f)
    an = analyze(project, m)
    pl = an.plugins[0]
    assert "orphan" in pl["reasons"] and pl["suggested"] == "Ryns Standing Stones.esp"
    res = convert(project, an, {"packing": "plugin", "preset": "koka", "sdk": False}, tools())
    an.cleanup()
    pack = Pack.open(project.root)
    arc = read_bsa(pack.data_dir / "Ryns Standing Stones.bsa")
    owners = {e.folder.split("\\")[-1] for e in arc.entries if "facegendata" in e.folder}
    assert owners == {"ryns standing stones.esp"}
    with (pack.data_dir / "Ryns Standing Stones.bsa").open("rb") as f:
        for e in arc.entries:
            if e.name.endswith(".nif") and "facegeom" in e.folder:
                tints = [t for t in NIF.texture_paths(NIF.parse(arc.read_file(e, f))) if "facetint" in t.lower()]
                assert all("\\Ryns Standing Stones.esp\\" in t for t in tints), tints
    assert res["renamed"]["Ryns Standing Stones.esp"] == "Ryn_s Standing Stones.esp"


USSEPT = ROOT / "tests" / "fixtures" / "ussep" / "USSEPT.bsa"


def test_switch_textures_get_the_diet(project, tmp_path):
    from skynx import nvn
    m = tmp_path / "Tints"
    m.mkdir()
    (m / "Tints.esp").write_bytes(plugin_bytes(["Skyrim.esm"]))
    shutil.copy(USSEPT, m / "Tints - Textures.bsa")
    an = analyze(project, m)
    est = an.estimate("diet", True)
    assert est["switch_diet"] >= 1 and est["after"] < est["before"]
    res = convert(project, an, {"packing": "plugin", "preset": "diet", "sdk": True, "bc1": True}, tools())
    an.cleanup()
    pack = Pack.open(project.root)
    arc = read_bsa(pack.data_dir / "Tints - Textures.bsa")
    with (pack.data_dir / "Tints - Textures.bsa").open("rb") as f:
        for e in arc.entries:
            raw = arc.read_file(e, f)
            assert nvn.is_nvn(raw)
            assert nvn.parse(raw).name != "RGBA8"
    assert res["stats"]["after"] < res["stats"]["before"]


# ------------------------------------------------------------------ Library\Converted
def test_converted_copy_is_kept_and_reusable(project, pc_mod, tmp_path):
    import json
    from skynx import library as L
    from skynx.builder import CONVERTED_INFO, add_mod, create_project as cp
    lib = tmp_path / "lib"
    L.ensure(lib)
    ts = tools()
    an = analyze(project, pc_mod)
    res = convert(project, an, {"preset": "koka", "packing": "ini", "ini_name": "RynT",
                                "keep_to": str(lib / "Converted")}, ts)
    an.cleanup()
    kept = Path(res["kept"])
    assert kept.parent == lib / "Converted"
    names = sorted(p.name for p in kept.iterdir())
    assert CONVERTED_INFO in names and set(res["bsas"]) <= set(names) and set(res["plugins"]) <= set(names)
    info = json.loads((kept / CONVERTED_INFO).read_text(encoding="utf-8"))
    assert info["ini_keys"] and info["converted"]["packing"] == "ini" and info["source"]
    # the Library lists it as a converted mod it owns
    row = next(r for r in L.list_library(lib, health=False) if r["path"] == str(kept))
    assert row["kind"] == "mod" and row["converted"] and row["owned"]
    # a second pack takes it as it is: ini lists, settings and origin come from skynx-mod.json
    other = Pack.open(cp(tmp_path / "other", "AE", BASE_INIS, "none"))
    rep = add_mod(other, kept)
    rec = load_mods(Pack.open(other.root))[rep.mod_id]
    assert rec["converted"]["packing"] == "ini"
    assert sorted(b for _, b in rep.ini_added) == sorted(info["ini_keys"])
    assert CONVERTED_INFO not in {p.name for p in Pack.open(other.root).data_dir.iterdir()}
    # converting the same mod again keeps both copies
    an = analyze(other, pc_mod)
    res2 = convert(other, an, {"packing": "plugin", "preset": "koka", "names": {"Ryn's Test.esp": "Ryn2.esp",
                                                           "Ryn's Test - Patch.esp": "Ryn2 - Patch.esp"},
                               "keep_to": str(lib / "Converted")}, ts)
    an.cleanup()
    assert Path(res2["kept"]) != kept and Path(res2["kept"]).is_dir()


def test_no_copy_without_keep_to(project, pc_mod):
    an = analyze(project, pc_mod)
    res = convert(project, an, {"packing": "plugin", "preset": "koka"}, tools())
    an.cleanup()
    assert res["kept"] is None


def test_voice_leftovers_of_a_half_done_port(tmp_path):
    """The Tempest Isle NX: voices of earlier plugin names, old takes, the CK's
    lip-sync folder and lines left as an empty .fuz next to a .temp.wav."""
    from skynx import converter as CV
    data = tmp_path / "data"
    v = data / "sound" / "voice"
    (data).mkdir(parents=True)
    (data / "StormIsleMerge.esp").write_bytes(b"TES4")
    good = v / "stormislemerge.esp" / "npcvoice"
    good.mkdir(parents=True)
    (good / "a_1.fuz").write_bytes(b"FUZE" + b"x" * 40)
    (good / "a_1.temp.wav").write_bytes(b"RIFF" + b"y" * 40)          # its fuz is fine: copy goes
    (good / "b_1.fuz").write_bytes(b"")                                 # empty, source next to it
    (good / "b_1.temp.wav").write_bytes(b"RIFF" + b"z" * 40)
    (good / "c_1.fuz").write_bytes(b"")                                 # empty, nothing to make it from
    (good / "a_1-old1.fuz").write_bytes(b"FUZE" + b"o" * 40)
    old = v / "stormisle.esp" / "npcvoice"
    old.mkdir(parents=True)
    (old / "a_1.fuz").write_bytes(b"FUZE" + b"x" * 40)
    other = v / "follower.esp" / "npcvoice"                             # not an earlier name: kept
    other.mkdir(parents=True)
    (other / "q_1.fuz").write_bytes(b"FUZE" + b"x" * 40)
    (v / "processing").mkdir()
    (v / "processing" / "fonixdata.cdf").write_bytes(b"x")
    an = CV.Analysis("Isle", str(tmp_path), tmp_path, data, "AE")
    CV._voice_leftovers(an)
    left = sorted(p.relative_to(v).as_posix() for p in v.rglob("*") if p.is_file())
    assert left == ["follower.esp/npcvoice/q_1.fuz", "stormislemerge.esp/npcvoice/a_1.fuz",
                    "stormislemerge.esp/npcvoice/b_1.wav"]
    text = " ".join(n["en"] for n in an.notes)
    assert "1 voice lines were left unconverted" in text and "stormisle.esp (1)" in text
    assert "1 old takes" in text and "1 temporary copies" in text and "1 empty files" in text
