"""Doctor checks on scripts and sounds the console runs (scriptcheck.py)."""
import struct
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tests"))
from skynx import nxaudio as NXA  # noqa: E402
from skynx import scriptcheck as SC  # noqa: E402
from skynx.audit import _BsaCache, run_audit  # noqa: E402
from skynx.bsa import read_bsa  # noqa: E402
from skynx.builder import add_mod, create_project  # noqa: E402
from skynx.ini import set_archive_list  # noqa: E402
from skynx.pack import Pack  # noqa: E402
from test_convert import plugin_bytes  # noqa: E402
from test_requirements import make_bsa  # noqa: E402

INIS = ROOT / "tests" / "fixtures" / "console-inis"
USSEPV = ROOT / "tests" / "fixtures" / "ussep" / "USSEPV.bsa"


def pex(name: str, *more: str) -> bytes:
    strings = [name, "", *more]
    out = bytearray(b"\xfa\x57\xc0\xde" + bytes([3, 2]) + struct.pack(">H", 1) + b"\0" * 8)
    for s in ("x.psc", "u", "m"):
        out += struct.pack(">H", len(s)) + s.encode()
    out += struct.pack(">H", len(strings))
    for s in strings:
        out += struct.pack(">H", len(s)) + s.encode()
    out += b"\x00" + struct.pack(">HH", 0, 1) + struct.pack(">HIH", 0, 12, 1) + b"\0" * 10
    return bytes(out)


def opus_stream(frames: list[bytes]) -> bytes:
    data = b"".join(struct.pack(">II", len(f), 0) + f for f in frames)
    head = struct.pack("<IIBBHIII", 0x80000001, 24, 0, 1, 8, 48000, 32, 0) + b"\0" * 8
    return head + struct.pack("<II", 0x80000004, len(data)) + data


def mcadpcm(rate=32000, nibbles=200, cut=0) -> bytes:
    dsp = struct.pack("<III", 160, nibbles, rate) + b"\0" * (0x60 - 12) + b"\x11" * ((nibbles + 1) // 2)
    dsp = dsp[:len(dsp) - cut]
    return struct.pack("<III", 1, 12, len(dsp)) + dsp


def _project(tmp_path):
    pack = Pack.open(create_project(tmp_path / "p", "AE", INIS, "all"))
    for name, plugin, files in (
            ("USSEP", "Unofficial Skyrim Special Edition Patch.esp",
             {"scripts\\qf_mq102_0004e50d.pex": pex("QF_MQ102_0004E50D")}),
            ("Quest Fix", "QF.esp",
             {"scripts\\qf_mq102_0004e50d.pex": pex("QF_MQ102_0004E50D"),
              "scripts\\qf_mq101_0003372b.pex": pex("QF_MQ101_0003372B"),
              "scripts\\qfhelper.pex": pex("QFHelper", "Gone.esp", "Skyrim.esm",
                                           "RegisterForUpdate", "OnHit"),
              "sound\\voice\\qf.esp\\maleeventoned\\hi_1.fuz":
                  NXA.build_fuz(b"", opus_stream([b"a" * 30, b"b" * 20]), 1, 100),
              "sound\\voice\\qf.esp\\maleeventoned\\cut_1.fuz":
                  NXA.build_fuz(b"", opus_stream([b"a" * 30, b"b" * 20]), 1, 100)[:-12],
              "music\\qf\\theme.mcadpcm": mcadpcm(),
              "music\\qf\\broken.mcadpcm": mcadpcm(rate=0)})):
        m = tmp_path / name
        m.mkdir()
        (m / plugin).write_bytes(plugin_bytes(["Skyrim.esm"]))
        make_bsa(m / (Path(plugin).stem + ".bsa"), files)
        add_mod(pack, m)
    pack = Pack.open(pack.root)
    # both in the ini, after the game's, as on the console
    ini = next(i for i in pack.inis if i.path.name.lower() == "skyrim.ini")
    items = ini.archive_list("sResourceArchiveList") + ["Unofficial Skyrim Special Edition Patch.bsa", "QF.bsa"]
    ini.path.write_bytes(set_archive_list(ini.path.read_bytes(), "sResourceArchiveList", items))
    return Pack.open(pack.root)


def _run(pack, vanilla=frozenset()):
    out = []

    def add(code, sev, cat, msg, subject="", params=None, items=None, fix=None, alt=None):
        out.append((code, sev, subject, params or {}, items or []))
    active = {n.lower() for n, _s in pack.load_order()}
    cache = _BsaCache()
    SC.check_scripts(pack, add, cache, set(vanilla), active)
    SC.check_audio(pack, add, cache)
    return {c: (sev, subj, p, items) for c, sev, subj, p, items in out}


def test_scripts_that_replace_ussep_and_the_game(tmp_path):
    pack = _project(tmp_path)
    got = _run(pack, {"scripts\\qf_mq101_0003372b.pex", "scripts\\qf_mq102_0004e50d.pex"})
    sev, _s, p, items = got["script-replaces-ussep"]
    assert sev == "aviso" and p["n"] == 1 and "qf_mq102_0004e50d" in items[0] and "QF" in items[0]
    sev, _s, p, items = got["script-replaces-game"]
    assert sev == "info" and "qf_mq101_0003372b" in items[0]


def test_scripts_asking_for_plugins_and_their_weight(tmp_path):
    pack = _project(tmp_path)
    got = _run(pack)
    _sev, _s, p, items = got["script-plugin-off"]
    assert p["n"] == 1 and items[0].startswith("gone.esp [gone]") and "qfhelper" in items[0]
    _sev, _s, _p, items = got["script-load"]
    assert items[0].endswith("3 scripts · 1 repeating · 0 single · 1 events")


def test_damaged_sounds(tmp_path):
    pack = _project(tmp_path)
    got = _run(pack)
    sev, subj, p, items = got["audio-broken"]
    assert sev == "aviso" and subj == "QF.bsa" and p["n"] == 2
    assert any("cut_1.fuz" in i for i in items) and any("broken.mcadpcm" in i for i in items)
    assert not any("hi_1.fuz" in i or "theme.mcadpcm" in i for i in items)
    # the second check reads nothing new and says the same
    assert (pack.root / ".skynx" / SC.CACHE_FILE).exists()
    assert _run(pack)["audio-broken"][2]["n"] == 2


def test_real_switch_voices_pass():
    arc = read_bsa(USSEPV)
    for e in arc.entries:
        assert SC._audio_problem(e.name, arc.read_file(e)) is None
        assert SC._audio_problem(e.name, arc.read_file(e)[:-40]) is not None


def test_the_doctor_runs_them(tmp_path):
    pack = _project(tmp_path)
    codes = {f.code for f in run_audit(pack, deep=True).findings}
    assert {"script-plugin-off", "script-load", "audio-broken"} <= codes


def test_skse_base_scripts_bundled_in_a_mod(tmp_path):
    """Mihail's monster pack from a shared modpack carried SKSE's PC copy of
    Quest, Actor, Game... in its BSA, in the ini: they replaced the Switch's."""
    from skynx.fixes import apply, preview
    pack = Pack.open(create_project(tmp_path / "p", "AE", INIS, "all"))
    m = tmp_path / "Monsters"
    m.mkdir()
    (m / "MMAAPack.esp").write_bytes(plugin_bytes(["Skyrim.esm"]))
    files = {f"scripts\\{n}.pex": pex(n) for n in ("skse", "quest", "actor", "game", "form")}
    files["scripts\\source\\quest.psc"] = b"Scriptname Quest extends Form Hidden"
    files["meshes\\mihail\\troll.nif"] = b"nif"
    make_bsa(m / "MMAAPack.bsa", files)
    add_mod(pack, m)
    pack = Pack.open(pack.root)
    f = [x for x in run_audit(pack, deep=True).findings if x.code == "script-skse-base"]
    assert len(f) == 1 and f[0].severity == "critico" and f[0].params["n"] == 5
    assert "quest.pex" in f[0].items and f[0].fix["kind"] == "bsa_drop_skse"
    assert any("SKSE" in line for line in preview(pack, f[0].fix)["changes"])
    apply(pack, f[0].fix)
    pack = Pack.open(pack.root)
    left = {e.path.lower() for e in read_bsa(pack.bsas["mmaapack.bsa"]).entries}
    assert left == {"meshes\\mihail\\troll.nif"}
    assert not [x for x in run_audit(pack, deep=True).findings if x.code == "script-skse-base"]


def test_a_few_base_scripts_are_not_skse():
    assert SC.skse_base_in(["scripts\\quest.pex", "scripts\\actor.pex", "scripts\\mymod.pex"]) == []
    assert SC.skse_base_in(["scripts\\skse.pex", "scripts\\mymod.pex"]) == ["scripts\\skse.pex"]


def test_creation_club_off_when_nothing_uses_it(tmp_path):
    """Each Creation Club entry is a BSA the game keeps open: the ones no
    active plugin uses as a master go off in one step; with the unofficial
    patch, it goes first and what only it used follows."""
    from skynx import ccc as C
    from skynx import xtools as X
    from skynx.history import Transaction
    pack = Pack.open(create_project(tmp_path / "p", "AE", INIS, "all"))
    cc = [e for e in pack.list_entries if pack.is_cc(e)]
    assert len(cc) >= 3
    keep, patched = cc[0], cc[1]
    m = tmp_path / "Mods"
    m.mkdir()
    (m / "Uses.esp").write_bytes(plugin_bytes(["Skyrim.esm", keep]))
    (m / "unofficial skyrim creation club content patch.esl").write_bytes(plugin_bytes(["Skyrim.esm", patched]))
    add_mod(pack, m)
    pack = Pack.open(pack.root)
    with Transaction(pack.root, "t") as tx:
        off = X.cc_off_unneeded(pack, tx)
    on = {e.lower() for e in Pack.open(pack.root).list_entries if not e.startswith("#")}
    assert keep.lower() in on and patched.lower() in on and len(off) == len(cc) - 2
    with Transaction(pack.root, "t") as tx:
        off = X.cc_off_unneeded(Pack.open(pack.root), tx, the_patch=True)
    assert [o.lower() for o in off] == ["unofficial skyrim creation club content patch.esl", patched.lower()]
    on = {e.lower() for e in Pack.open(pack.root).list_entries if not e.startswith("#")}
    assert keep.lower() in on and patched.lower() not in on


def test_console_info_has_the_creation_club_bsas(tmp_path):
    from skynx import ccinfo
    from skynx import console as CN
    pack = Pack.open(create_project(tmp_path / "p", "AE", INIS, "all"))
    cc = next(e for e in pack.list_entries if pack.is_cc(e) and ccinfo.info(e))
    van = tmp_path / "vanilla"
    make_bsa(van / (Path(cc).stem + ".bsa"), {"textures\\cc\\a.dds": b"DDS " + bytes(200)})
    (van / cc).write_bytes(plugin_bytes(["Skyrim.esm"]))
    text = CN.info_text(pack, vanilla_dir=van)
    line = next(l for l in text.splitlines() if l.startswith("p\t" + cc + "\t"))
    f = line.split("\t")
    assert f[6] == Path(cc).stem + ".bsa" and f[7].split(":")[0] != "0"


def test_off_lines_dont_count_toward_the_ccc_limit():
    """Pack leaves '#' lines out of the console's list, so a project can keep
    many mods switched off without hitting the 4096 bytes."""
    from types import SimpleNamespace
    from skynx import ccc as C
    on = "".join(f"Mod{i:03d} with a long name.esp\r\n" for i in range(120)).encode()
    off = "".join(f"#Off{i:03d} with a long name.esp\r\n" for i in range(60)).encode()
    proj = SimpleNamespace(mode="AE", list_path=Path("Skyrim_aoc.ccc"), project=True)
    loose = SimpleNamespace(mode="AE", list_path=Path("Skyrim_aoc.ccc"), project=False)
    assert len(on) < 4096 < len(on + off)
    assert C.over_limit(proj, on, on + off) is None
    assert C.over_limit(loose, on, on + off) == len(on + off)
    more = "".join(f"New{i:03d} with a long name.esp\r\n" for i in range(30)).encode()
    assert C.over_limit(proj, on + off, on + more + off) == len(on + more)
