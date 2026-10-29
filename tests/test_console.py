"""What the app and SkyNX Mods (the homebrew) share on the SD: the side file,
the ini manifest, the console's on/off choices, and ini BSAs that follow
their plugins."""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tests"))
from skynx import ccc as C  # noqa: E402
from skynx import console as CON  # noqa: E402
from skynx import deploy as D  # noqa: E402
from skynx import project as P  # noqa: E402
from skynx.history import Transaction  # noqa: E402
from skynx.ini import parse_ini, read_ini, set_archive_list  # noqa: E402
from skynx.pack import Pack  # noqa: E402
from test_project import make  # noqa: E402

AOC = "01000A10041EB009"


def _with_ini_bsa(tmp_path):
    """A project whose Big Mod.esp also has its BSA listed in the ini."""
    _src, _b, pk = make(tmp_path)
    for ini in pk.ini_paths:
        raw = ini.read_bytes()
        if parse_ini(raw).get("Archive", "sResourceArchiveList") is not None:
            cur = parse_ini(raw).archive_list("sResourceArchiveList")
            ini.write_bytes(set_archive_list(raw, "sResourceArchiveList", cur + ["Big Mod.bsa"]))
    return Pack.open(pk.root)


def _switch(pk: Pack, name: str, on: bool) -> Pack:
    raw = pk.list_path.read_bytes()
    e = next(x for x in C.parse_ccc(raw).entries if x.lstrip("#") == name)
    pk.list_path.write_bytes(C.edit_lines(raw, {e: name if on else "#" + name}))
    return Pack.open(pk.root)


def _lists(pack_root: Path) -> list[str]:
    out = Pack.open(pack_root)
    return [b for ini in out.inis for k in ("sResourceArchiveList", "sResourceArchiveList2")
            for b in ini.archive_list(k)]


def test_owners_and_drops(tmp_path):
    pk = _with_ini_bsa(tmp_path)
    own = CON.ini_owners(pk)
    assert own["big mod.bsa"][1] == ["Big Mod.esp"]
    assert "looset.bsa" not in own                                        # no plugin of its own
    assert not any(k.startswith("skyrim - ") for k in own)
    assert CON.ini_drops(pk) == set()
    pk = _switch(pk, "Big Mod.esp", False)
    assert CON.ini_drops(pk) == {"big mod.bsa"}


def test_pack_leaves_out_ini_bsas_of_plugins_that_are_off(tmp_path):
    pk = _with_ini_bsa(tmp_path)
    P.build(pk)
    assert "Big Mod.bsa" in _lists(pk.root / "Switch")
    pk = _switch(pk, "Big Mod.esp", False)
    r = P.build(pk)
    lists = _lists(pk.root / "Switch")
    assert "Big Mod.bsa" not in lists and "LooseT.bsa" in lists        # a BSA with no plugin stays
    assert r["ini_off"] == ["big mod.bsa"]
    assert "Big Mod.bsa" in _lists(pk.root)                             # the project keeps it
    P.build(Pack.open(pk.root))                                         # again: nothing set aside
    assert not list((pk.root / ".skynx" / "trash").glob("Switch-*"))
    pk = _switch(Pack.open(pk.root), "Big Mod.esp", True)
    P.build(pk)
    assert "Big Mod.bsa" in _lists(pk.root / "Switch")


def _sd(tmp_path, pk: Pack) -> Path:
    sd = tmp_path / "sd"
    (sd / "atmosphere" / "contents").mkdir(parents=True)
    P.build(pk)
    D.deploy(pk.root, sd)
    CON.write_sd_files(pk, sd)
    return sd


def test_sd_files_and_the_manifest(tmp_path):
    pk = _switch(_with_ini_bsa(tmp_path), "Big Mod.esp", False)
    sd = _sd(tmp_path, pk)
    side = CON.side_path(sd).read_text()
    assert "#Big Mod.esp\n" in side
    man = CON.manifest_path(sd).read_text().splitlines()
    ini_lines = [l.split("\t") for l in man if l.startswith("ini\t")]
    assert any(k == "sResourceArchiveList" and "Big Mod.bsa" in v for _t, _f, k, v in ini_lines)
    assert "own\tBig Mod.bsa\tBig Mod.esp" in man
    # what SkyNX Mods would read: valid, and the same as the project
    con = CON.read_console(sd)
    assert ("Big Mod.esp", False) in con
    assert CON.console_changes(pk, sd) is None


def test_console_choices_come_back_to_the_project(tmp_path):
    pk = _with_ini_bsa(tmp_path)
    sd = _sd(tmp_path, pk)
    # SkyNX Mods turns Big Mod off: out of the .ccc, '#' in the side file
    ccc = sd / "atmosphere" / "contents" / AOC / "romfs" / "Skyrim_aoc.ccc"
    raw = ccc.read_bytes()
    ccc.write_bytes(C.edit_lines(raw, {"Big Mod.esp": None}))
    side = CON.side_path(sd)
    side.write_text(side.read_text().replace("Big Mod.esp\n", "#Big Mod.esp\n"))
    assert CON.console_changes(pk, sd) == {"off": ["Big Mod.esp"], "on": []}
    with Transaction(pk.root, "Console") as tx:
        CON.use_console(pk, sd, tx)
    pk = Pack.open(pk.root)
    assert "#Big Mod.esp" in pk.list_entries
    assert CON.console_changes(pk, sd) is None
    # the card's .ccc changed by someone else: the side file no longer counts
    ccc.write_bytes(raw)
    assert CON.read_console(sd) is None


def test_what_each_plugin_is(tmp_path):
    pk = _with_ini_bsa(tmp_path)
    with Transaction(pk.root, "Describe") as tx:
        CON.set_description(pk, "Big Mod", "  A big   mod\tfor testing  ", tx)
    rows = {i["plugin"]: i for i in CON.plugin_info(pk, {"Tiny": {"title": "Tiny Nexus Name", "desc": "From Nexus"}})}
    big = rows["Big Mod.esp"]
    assert big["desc_en"] == "A big mod for testing" and big["kind"] == "mod" and "Big Mod.bsa" in big["files"]
    assert rows["Tiny.esp"]["title"] == "Tiny Nexus Name" and rows["Tiny.esp"]["desc_es"] == "From Nexus"
    cc = rows["ccBGSSSE001-Fish.esm"]
    assert cc["kind"] == "cc" and cc["title"] == "Fishing" and "pesca" in cc["desc_es"]
    sd = _sd(tmp_path, pk)
    CON.write_sd_files(pk, sd)
    lines = CON.info_path(sd).read_text(encoding="utf-8").splitlines()
    big_line = next(l for l in lines if l.startswith("p\tBig Mod.esp\t")).split("\t")
    assert len(big_line) == 8 and big_line[3] == "mod" and big_line[6] == "Big Mod.bsa"
    assert big_line[7].count(":") == 4


def test_how_heavy_each_plugin_is(tmp_path):
    from skynx.bsa import write_bsa
    pk = _with_ini_bsa(tmp_path)
    src = tmp_path / "loose"
    src.mkdir()
    (src / "a.dds").write_bytes(b"DDS " + b"\0" * 300_000)
    (src / "a.nif").write_bytes(b"x" * 50_000)
    (src / "a.fuz").write_bytes(b"y" * 20_000)
    write_bsa([("textures\\big\\a.dds", src / "a.dds"), ("meshes\\big\\a.nif", src / "a.nif"),
               ("sound\\voice\\big.esp\\a.fuz", src / "a.fuz")], pk.bsas["big mod.bsa"])
    parts = CON.bsa_parts(pk.bsas["big mod.bsa"])
    assert parts["tex"] == 300_004 and parts["mesh"] == 50_000 and parts["audio"] == 20_000
    sd = _sd(tmp_path, pk)
    CON.write_sd_files(pk, sd)
    line = next(l for l in CON.info_path(sd).read_text(encoding="utf-8").splitlines()
                if l.startswith("p\tBig Mod.esp\t")).split("\t")
    rec, tex, mesh, audio, other = (int(x) for x in line[7].split(":"))
    assert rec >= 1 and tex == 293 and mesh == 49 and audio == 20
    assert (pk.root / ".skynx" / CON.WEIGHTS_FILE).exists()
    # cached by size and date: the second time reads nothing new
    assert CON.bsa_weights(pk, ["Big Mod.bsa"])["big mod.bsa"]["tex"] == 300_004
    assert CON.pc_path(sd).read_text() == CON.side_path(sd).read_text()


def test_clean_mod_names():
    c = CON.clean_mod_name
    assert c("Madmen A Forsworn Overhaul NX 313 2.0.2 2026-06-14T12-34Z eXDeLpzqt") == "Madmen A Forsworn Overhaul NX"
    assert c("Tonal Architect 1.0.0-51199-1-0-0-1623873919") == "Tonal Architect"
    assert c("Bold-244-Final-1672646516") == "Bold"
    assert c("Wintersun - Faiths of Skyrim") == "Wintersun - Faiths of Skyrim"
    assert c("SkyHUD.esp") == "SkyHUD"
    assert c("Mortal Enemies SE-4881-1-05") == "Mortal Enemies SE"
