"""New Doctor checks and fixes: Drive-safe rename, broken tints, junk, diet."""
import json
import shutil
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tests"))
from skynx import nif as NIF  # noqa: E402
from skynx import nvn  # noqa: E402
from skynx.audit import run_audit  # noqa: E402
from skynx.builder import add_mod, create_project  # noqa: E402
from skynx.bsa import read_bsa, write_bsa  # noqa: E402
from skynx.ccc import read_ccc  # noqa: E402
from skynx.fixes import apply, preview  # noqa: E402
from skynx.history import list_history, undo  # noqa: E402
from skynx.pack import Pack  # noqa: E402
from skynx.plugin import read_header  # noqa: E402
from test_convert import FAKE, plugin_bytes  # noqa: E402

INIS = ROOT / "tests" / "fixtures" / "console-inis"
SNAP = Path("private-test-data/SkyNX/Other modpacks")
REV = SNAP / "Avner ModPack Revised 2026/Avner ModPack Revised 2026/01000A10041EA000/romfs/Data"
need_real = pytest.mark.skipif(not (REV / "Cheat Room Fix.bsa").exists(), reason="real files missing")


def _pack(tmp_path):
    return Pack.open(create_project(tmp_path / "p", "AE", INIS, "all"))


def _find(pack, code, deep=False):
    return [f for f in run_audit(pack, deep=deep).findings if f.code == code]


@need_real
def test_safe_rename_reaches_inside(tmp_path):
    pack = _pack(tmp_path)
    m = tmp_path / "ryn"
    m.mkdir()
    shutil.copy(REV / "Ryn_s Standing Stones.esp", m / "Ryn's Standing Stones.esp")
    shutil.copy(REV / "Ryn_s Standing Stones.bsa", m / "Ryn's Standing Stones.bsa")
    (m / "Ryn Patch.esp").write_bytes(plugin_bytes(["Skyrim.esm", "Ryn's Standing Stones.esp"]))
    add_mod(pack, m)
    pack = Pack.open(pack.root)
    f = [x for x in _find(pack, "name-unsafe") if x.subject == "Ryn's Standing Stones.esp"][0]
    assert f.fix["to"] == "Ryns Standing Stones.esp"
    pv = preview(pack, f.fix)
    assert any("Ryn Patch.esp" in c for c in pv["changes"])
    apply(pack, f.fix)
    pack = Pack.open(pack.root)
    d = pack.data_dir
    assert (d / "Ryns Standing Stones.esp").exists() and (d / "Ryns Standing Stones.bsa").exists()
    assert not (d / "Ryn's Standing Stones.esp").exists()
    assert read_header(d / "Ryn Patch.esp").masters[-1] == "Ryns Standing Stones.esp"
    assert "Ryns Standing Stones.esp" in read_ccc(pack.ccc_path).entries
    arc = read_bsa(d / "Ryns Standing Stones.bsa")
    owners = {e.folder.split("\\")[-1] for e in arc.entries if "facegendata" in e.folder}
    assert owners == {"ryns standing stones.esp"}
    with (d / "Ryns Standing Stones.bsa").open("rb") as fh:
        for e in arc.entries:
            if e.name.endswith(".nif") and "facegeom" in e.folder:
                t = [x for x in NIF.texture_paths(NIF.parse(arc.read_file(e, fh))) if "facetint" in x.lower()]
                assert all("\\Ryns Standing Stones.esp\\" in x for x in t)
    assert json.loads((pack.root / ".skynx" / "renames.json").read_text()) == \
        {"Ryns Standing Stones.esp": "Ryn's Standing Stones.esp"}
    assert not [x for x in _find(pack, "name-unsafe") if "Ryn" in x.subject]
    undo(pack.root, list_history(pack.root)[0]["id"])
    pack = Pack.open(pack.root)
    assert (pack.data_dir / "Ryn's Standing Stones.esp").exists()
    assert read_header(pack.data_dir / "Ryn Patch.esp").masters[-1] == "Ryn's Standing Stones.esp"


@need_real
def test_broken_tint_is_found_and_fixed(tmp_path):
    pack = _pack(tmp_path)
    m = tmp_path / "cr"
    m.mkdir()
    for n in ("Cheat Room Fix.esp", "Cheat Room Fix.bsa"):
        shutil.copy(REV / n, m / n)
    add_mod(pack, m)
    pack = Pack.open(pack.root)
    f = _find(pack, "tint-broken", deep=True)
    assert len(f) == 1 and f[0].fix["fixes"][0]["new"] == "cheat room fix.esp"
    apply(pack, f[0].fix)
    pack = Pack.open(pack.root)
    assert not _find(pack, "tint-broken", deep=True)


def test_junk_and_diet(tmp_path):
    pack = _pack(tmp_path)
    m = tmp_path / "j"
    m.mkdir()
    a, b = tmp_path / "a.pex", tmp_path / "a.psc"
    a.write_bytes(b"\xfa\x57\xc0\xde" + bytes(40))
    b.write_text("source")
    shutil.copy(ROOT / "tests/fixtures/ussep/USSEPT.bsa", m / "Junk - Textures.bsa")
    write_bsa([("scripts\\a.pex", a), ("scripts\\source\\a.psc", b)], m / "Junk.bsa")
    (m / "Junk.esp").write_bytes(plugin_bytes(["Skyrim.esm"]))
    add_mod(pack, m)
    pack = Pack.open(pack.root)
    f = _find(pack, "bsa-junk")
    assert len(f) == 1 and f[0].fix["kind"] == "bsa_drop_junk"
    apply(pack, f[0].fix)
    assert [e.path for e in read_bsa(Pack.open(pack.root).data_dir / "Junk.bsa").entries] == ["scripts\\a.pex"]
    fix = {"kind": "diet_bsa", "label_key": "fix-diet", "label_args": {"after": "?"}, "risk": "revisar",
           "bsa": "Junk - Textures.bsa", "preset": "koka", "bc1": True, "tools_dir": str(FAKE)}
    before = (pack.data_dir / "Junk - Textures.bsa").stat().st_size
    apply(Pack.open(pack.root), fix)
    p = Pack.open(pack.root).data_dir / "Junk - Textures.bsa"
    assert p.stat().st_size < before
    arc = read_bsa(p)
    with p.open("rb") as fh:
        assert all(nvn.parse(arc.read_file(e, fh)).name != "RGBA8" for e in arc.entries)


def test_stray_file_in_voice_root_is_not_a_plugin():
    """A .DS_Store right in sound\\voice (packed on a Mac) isn't a voice folder
    named '' (Lustful ArtistNX, Oct 2026)."""
    from skynx.audit import plugin_owners
    from skynx.bsa import BsaEntry

    class Arc:
        entries = [BsaEntry("sound\\voice", ".ds_store", 1, 0, False),
                   BsaEntry("sound\\voice\\mod.esp\\femaleyoungeager", "a.fuz", 1, 0, False)]
    assert plugin_owners(Arc()) == {"mod.esp": 1}


def test_dummy_moved_to_ini_is_not_reported_as_inactive(tmp_path):
    """Music of Tamriel: after 'Move its BSA to the ini' the empty plugin stays
    in Data, out of the list; that is the fix working, not an inactive mod."""
    pack = _pack(tmp_path)
    m = tmp_path / "Music"
    m.mkdir()
    (m / "Music.esp").write_bytes(plugin_bytes(["Skyrim.esm"], records=0))
    song = tmp_path / "song.xwm"
    song.write_bytes(b"RIFF" + bytes(32))
    write_bsa([("music\\explore\\song.xwm", song)], m / "Music.bsa")
    add_mod(pack, m)
    pack = Pack.open(pack.root)
    f = [x for x in _find(pack, "plugin-dummy") if x.subject == "Music.esp"][0]
    apply(pack, f.fix)
    pack = Pack.open(pack.root)
    assert "Music.esp" not in read_ccc(pack.ccc_path).entries
    assert any("music.bsa" in [b.lower() for b in v] for v in pack.archive_lists().values())
    assert not [x for x in _find(pack, "plugin-unlisted") if x.subject == "Music.esp"]
    # its BSA renamed short later (fix-ini-shorten): still nothing to report
    from skynx.bsafix import rename_ini_bsas
    from skynx.history import Transaction
    with Transaction(pack.root, "short") as tx:
        rename_ini_bsas(pack, [("Music.bsa", "MusicS.bsa")], tx)
    pack = Pack.open(pack.root)
    assert not [x for x in _find(pack, "plugin-unlisted") if x.subject == "Music.esp"]
    # a plain inactive plugin is still reported
    o = tmp_path / "Other"
    o.mkdir()
    (o / "Other.esp").write_bytes(plugin_bytes(["Skyrim.esm"]))
    add_mod(pack, o)
    pack = Pack.open(pack.root)
    from skynx import ccc as C
    path = pack.ccc_path
    path.write_bytes(C.edit_lines(path.read_bytes(), {"Other.esp": None}))
    assert [x for x in _find(Pack.open(pack.root), "plugin-unlisted") if x.subject == "Other.esp"]


def test_dummy_whose_files_would_change_winner_keeps_its_place(tmp_path):
    """Noble Skyrim: its textures win over mods that load before it. In the ini
    they would load first and lose, so the Doctor says to leave it and offers
    no fix; a dummy that shares nothing gets the fix as safe."""
    pack = _pack(tmp_path)
    tex = tmp_path / "t.dds"
    tex.write_bytes(b"DDS " + bytes(124))
    for name, files in (("Base", ["textures\\a.dds"]), ("Noble", ["textures\\a.dds", "textures\\b.dds"]),
                        ("Solo", ["textures\\solo.dds"])):
        m = tmp_path / name
        m.mkdir()
        (m / f"{name}.esp").write_bytes(plugin_bytes(["Skyrim.esm"], records=1 if name == "Base" else 0))
        write_bsa([(f, tex) for f in files], m / f"{name}.bsa")
        add_mod(pack, m)
    pack = Pack.open(pack.root)
    keep = [x for x in _find(pack, "plugin-dummy-keep") if x.subject == "Noble.esp"]
    assert keep and keep[0].fix is None and keep[0].severity == "info"
    assert keep[0].items == ["textures\\a.dds → Base.bsa"]
    assert not [x for x in _find(pack, "plugin-dummy") if x.subject == "Noble.esp"]
    solo = [x for x in _find(pack, "plugin-dummy") if x.subject == "Solo.esp"][0]
    assert solo.fix and solo.fix["risk"] == "seguro"


def _rename(pack, old, new):
    from skynx.bsafix import safe_rename
    from skynx.history import Transaction
    with Transaction(pack.root, "rename") as tx:
        safe_rename(pack, old, new, tx)
    return Pack.open(pack.root)


def test_patch_added_after_its_master_was_renamed(tmp_path):
    """SRCEO: the master got a short name; a patch added as it is (no
    conversion) still names the old one. Adding it points it at the new name,
    and one already in the pack gets a safe Doctor fix."""
    from skynx.plugin import read_header
    pack = _pack(tmp_path)
    m = tmp_path / "Master"
    m.mkdir()
    (m / "Skyrim Revamped - Long.esp").write_bytes(plugin_bytes(["Skyrim.esm"]))
    add_mod(pack, m)
    pack = _rename(Pack.open(pack.root), "Skyrim Revamped - Long.esp", "SRCEO.esp")
    p1 = tmp_path / "Patch"
    p1.mkdir()
    (p1 / "Patch.esp").write_bytes(plugin_bytes(["Skyrim.esm", "Skyrim Revamped - Long.esp"]))
    rep = add_mod(pack, p1)
    assert read_header(pack.data_dir / "Patch.esp").masters == ["Skyrim.esm", "SRCEO.esp"]
    assert any("SRCEO.esp" in n[0] for n in rep.notes)
    pack = Pack.open(pack.root)
    assert not [x for x in _find(pack, "master-missing") if x.subject.startswith("Patch.esp")]
    # one that went in before this version: the Doctor points it there
    (pack.data_dir / "Old.esp").write_bytes(plugin_bytes(["Skyrim.esm", "Skyrim Revamped - Long.esp"]))
    from skynx import ccc as C
    raw = pack.list_path.read_bytes()
    pack.list_path.write_bytes(raw + (b"" if raw.endswith(b"\n") else b"\r\n") + b"Old.esp\r\n")
    pack = Pack.open(pack.root)
    f = [x for x in _find(pack, "master-missing") if x.subject.startswith("Old.esp")][0]
    assert f.fix and f.fix["risk"] == "seguro" and f.fix["map"] == {"Skyrim Revamped - Long.esp": "SRCEO.esp"}
    apply(pack, f.fix)
    assert read_header(pack.data_dir / "Old.esp").masters == ["Skyrim.esm", "SRCEO.esp"]
    assert not [x for x in _find(Pack.open(pack.root), "master-missing")]


def test_long_plugin_names_are_shortened_in_one_step(tmp_path, monkeypatch):
    """The .ccc nearly full before wave 4: the Doctor offers short names for the
    long ones, BSA style, and a patch that uses one as a master follows it."""
    from skynx import knowledge as K
    pack = _pack(tmp_path)
    tex = tmp_path / "t.dds"
    tex.write_bytes(b"DDS " + bytes(124))
    long_ = "Andromeda - Unique Standing Stones of Skyrim.esp"
    patch = "Apocalypse - Ordinator Compatibility Patch.esp"
    for folder, name, masters in (("A", long_, ["Skyrim.esm"]), ("P", patch, ["Skyrim.esm", long_]),
                                  ("S", "Short.esp", ["Skyrim.esm"])):
        m = tmp_path / folder
        m.mkdir()
        (m / name).write_bytes(plugin_bytes(masters))
        if folder == "A":
            write_bsa([("textures\\a.dds", tex)], m / (Path(name).stem + ".bsa"))
        add_mod(pack, m)
    pack = Pack.open(pack.root)
    monkeypatch.setattr(K, "CCC_BYTE_LIMIT", pack.list_bytes + 100)
    [f] = _find(pack, "ccc-shorten")
    assert f.fix and f.fix["risk"] == "revisar"
    pairs = dict(tuple(p) for p in f.fix["pairs"])
    assert set(pairs) == {long_, patch} and all(len(v) <= 14 for v in pairs.values())
    before = pack.list_bytes
    apply(pack, f.fix)
    pack = Pack.open(pack.root)
    new_long, new_patch = pairs[long_], pairs[patch]
    assert (pack.data_dir / new_long).exists() and not (pack.data_dir / long_).exists()
    assert read_header(pack.data_dir / new_patch).masters == ["Skyrim.esm", new_long]
    assert (pack.data_dir / (Path(new_long).stem + ".bsa")).exists()
    assert pack.list_bytes == before - (len(long_) - len(new_long)) - (len(patch) - len(new_patch))
    assert not _find(pack, "master-missing")


def test_shortening_says_what_it_is_doing(tmp_path, monkeypatch):
    from skynx import knowledge as K
    from skynx.i18n import progress_label
    pack = _pack(tmp_path)
    for folder, name in (("A", "Andromeda - Unique Standing Stones of Skyrim.esp"),
                         ("B", "Summermyst - Enchantments of Skyrim.esp")):
        m = tmp_path / folder
        m.mkdir()
        (m / name).write_bytes(plugin_bytes(["Skyrim.esm"]))
        add_mod(pack, m)
    pack = Pack.open(pack.root)
    monkeypatch.setattr(K, "CCC_BYTE_LIMIT", pack.list_bytes + 100)
    [f] = _find(pack, "ccc-shorten")
    seen = []
    apply(pack, f.fix, progress=lambda t, i=0, n=0: seen.append(t))
    assert seen[0].startswith("Renaming Andromeda - Unique Standing Stones of Skyrim.esp → ")
    assert seen[-1] == "Checking the pack again"
    assert progress_label(seen[0], "es").startswith("Renombrando Andromeda")


def test_creation_club_lines_the_game_doesnt_have(tmp_path):
    """The Switch's own load list names five CC plugins the game has neither
    the plugin nor the BSA of: their lines go, the others stay."""
    from skynx import knowledge as K
    from test_library import EMPTY_BSA, fake_plugin
    pack = _pack(tmp_path)
    gone = {"ccbgssse026-goldensaint.esl", "ccbgssse029-nerveshatter.esl"}
    only_bsa = "ccBGSSSE002-ExoticArrows.esl"           # its BSA is there: not proof enough
    vdir = tmp_path / "vanilla"
    vdir.mkdir()
    tex = tmp_path / "a.dds"
    tex.write_bytes(b"DDS " + bytes(124))
    write_bsa([("textures\\a.dds", tex)], vdir / "Skyrim - Misc.bsa")
    for cc in K.AE_CC_PLUGINS:
        if cc.lower() in gone:
            continue
        (vdir / (cc.rsplit(".", 1)[0] + ".bsa")).write_bytes(EMPTY_BSA)
        if cc != only_bsa:
            fake_plugin(vdir / cc, ["Skyrim.esm"])
    listed = {e.lower() for e in pack.list_entries}
    assert gone <= listed
    fs = [f for f in run_audit(pack, deep=True, vanilla_dir=vdir, cache_dir=tmp_path / "c").findings
          if f.code == "cc-not-in-game"]
    assert len(fs) == 1 and {x.lower() for x in fs[0].items} == gone
    before = pack.list_bytes
    apply(pack, fs[0].fix)
    pack = Pack.open(pack.root)
    left = {e.lower() for e in pack.list_entries}
    assert not (gone & left) and only_bsa.lower() in left
    assert pack.list_bytes == before - fs[0].params["bytes"]


def test_remove_takes_its_users_and_leaves_no_off_lines(tmp_path):
    """Wyrmstooth case: a patch that uses it as a master shares a FOMOD mod
    with another patch. Remove names who uses it; with_users takes that one
    plugin out of its mod (the other stays) and no '#' line is left behind."""
    from skynx import ccc as C
    from skynx.builder import BuildError, load_mods, remove_mod
    pack = _pack(tmp_path)
    land = tmp_path / "Land"
    land.mkdir()
    (land / "Land.esp").write_bytes(plugin_bytes(["Skyrim.esm"]))
    add_mod(pack, land)
    pats = tmp_path / "Patches"
    pats.mkdir()
    (pats / "PatchLand.esp").write_bytes(plugin_bytes(["Skyrim.esm", "Land.esp"]))
    (pats / "PatchOther.esp").write_bytes(plugin_bytes(["Skyrim.esm"]))
    add_mod(pack, pats)
    pack = Pack.open(pack.root)
    raw = pack.list_path.read_bytes()
    pack.list_path.write_bytes(C.edit_lines(raw, {"Land.esp": "#Land.esp", "PatchLand.esp": "#PatchLand.esp"}))
    pack = Pack.open(pack.root)
    with pytest.raises(BuildError) as ei:
        remove_mod(pack, "Land")
    assert ei.value.users == [{"plugin": "PatchLand.esp", "mod": "Patches", "whole": False}]
    remove_mod(pack, "Land", with_users=True)
    pack = Pack.open(pack.root)
    names = {e.lstrip("#").lower() for e in pack.list_entries}
    assert "land.esp" not in names and "patchland.esp" not in names and "patchother.esp" in names
    assert not (pack.data_dir / "PatchLand.esp").exists() and (pack.data_dir / "PatchOther.esp").exists()
    mods = load_mods(pack)
    assert "Land" not in mods and mods["Patches"]["plugins"] == ["PatchOther.esp"]
    # one step in the history undoes both
    undo(pack.root, list_history(pack.root)[0]["id"])
    pack = Pack.open(pack.root)
    assert (pack.data_dir / "Land.esp").exists() and (pack.data_dir / "PatchLand.esp").exists()


def test_off_lines_of_plugins_that_are_gone(tmp_path):
    from skynx import ccc as C
    pack = _pack(tmp_path)
    raw = pack.list_path.read_bytes()
    entries = C.parse_ccc(raw).entries
    pack.list_path.write_bytes(C.reorder(raw, entries + ["#Ghost.esp", "#ccBGSSSE001-Fish.esm"]))
    pack = Pack.open(pack.root)
    [f] = _find(pack, "off-without-file")
    assert f.items == ["#Ghost.esp"]
    apply(pack, f.fix)
    pack = Pack.open(pack.root)
    assert "#Ghost.esp" not in pack.list_entries
    assert not _find(pack, "off-without-file")
