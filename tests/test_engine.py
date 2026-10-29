"""Engine tests against mirrors of the real community packs.

Run: python -m pytest tests -q   (needs work/mirror from work/make_mirror.py)
"""
import shutil
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from skynx.audit import run_audit  # noqa: E402
from skynx.bsa import read_bsa  # noqa: E402
from skynx.fixes import apply  # noqa: E402
from skynx.history import list_history, undo  # noqa: E402
from skynx.pack import Pack  # noqa: E402

MIRROR = ROOT / "work" / "mirror"
ORIG_CCC = Path("private-test-data/outputs/skynx-fix/_respaldos/2026-10-23")
pytestmark = pytest.mark.skipif(not MIRROR.exists(), reason="no mirror")


def _copy(name, tmp_path):
    dst = tmp_path / name
    shutil.copytree(MIRROR / name, dst, symlinks=True)
    return dst


def _ccc(root):
    return next(root.rglob("Skyrim_aoc.ccc"))


def _set(path, data):
    path.unlink()
    path.write_bytes(data)


def test_drive_apostrophes_are_fixed(tmp_path):
    root = _copy("Avner ModPack Revised 2026", tmp_path)
    data = root / "Avner ModPack Revised 2026/01000A10041EA000/romfs/Data"
    for n in ("Ryn's Standing Stones.esp", "Ryn's Standing Stones.bsa"):
        (data / n).unlink()   # back to the state as downloaded from Drive
    _set(_ccc(root), (ORIG_CCC / "Avner ModPack Revised 2026/Avner ModPack Revised 2026/Skyrim_aoc.ccc").read_bytes())
    pack = Pack.open(root)
    res = run_audit(pack, deep=False)
    crit = [f for f in res.findings if f.code == "list-missing-near"]
    assert len(crit) == 5
    ryn = next(f for f in crit if f.subject == "Ryn's Standing Stones.esp")
    assert ryn.fix["kind"] == "rename_files"          # FaceGen depends on the name
    others = [f for f in crit if f is not ryn]
    assert all(f.fix["kind"] == "list_replace" for f in others)
    for f in crit:
        apply(pack, f.fix)
    res2 = run_audit(Pack.open(root), deep=False)
    assert not [f for f in res2.findings if f.code == "list-missing-near"]
    assert (data / "Ryn's Standing Stones.bsa").exists()
    assert len(list_history(root)) == 5


def test_master_order_fix(tmp_path):
    root = _copy("Avner ModPack Revised 2026", tmp_path)
    _set(_ccc(root), (ORIG_CCC / "Avner ModPack Revised 2026/Avner ModPack Revised 2026/Skyrim_aoc.ccc").read_bytes())
    pack = Pack.open(root)
    f = next(f for f in run_audit(pack, deep=False).findings if f.code == "master-order")
    assert "MysticismMagic.esp" in f.title
    apply(pack, f.fix)
    assert not [x for x in run_audit(Pack.open(root), deep=False).findings if x.code == "master-order"]


def test_auri_rename_detected_and_fixed(tmp_path):
    root = _copy("Vanilla+ Flowergirls (NSFW)", tmp_path)
    data = root / "contents/01000A10041EA000/romfs/Data"
    for ext in ("esp", "bsa"):
        src = data / f"018Auri.{ext}"
        real = src.resolve()
        src.unlink()
        shutil.copyfile(real, data / f"Auri.{ext}")
    ccc = _ccc(root)
    _set(ccc, ccc.read_bytes().replace(b"018Auri.esp", b"Auri.esp"))
    pack = Pack.open(root)
    f = next(f for f in run_audit(pack, deep=False).findings if f.code == "bsa-owner")
    # faces carry the old path inside their .nif, so only restoring the name is offered
    assert f.fix["kind"] == "rename_plugin" and f.fix["to"] == "018auri.esp"
    assert f.alt == []
    apply(pack, f.fix)
    assert (data / "018auri.esp").exists() and (data / "018auri.bsa").exists()
    assert b"018auri.esp" in ccc.read_bytes() and b"Auri.esp\r" not in ccc.read_bytes()
    after = run_audit(Pack.open(root), deep=False)
    assert not [x for x in after.findings if x.code in ("bsa-owner", "list-missing", "list-missing-near")]
    hist = list_history(root)[0]
    undo(root, hist["id"])
    assert (data / "Auri.esp").exists() and not (data / "018auri.esp").exists()


def test_voices_only_alternative(tmp_path):
    """A BSA with only voices under the old name can move them instead."""
    from skynx.bsa import rebuild_bsa
    root = _copy("Vanilla+ Flowergirls (NSFW)", tmp_path)
    data = root / "contents/01000A10041EA000/romfs/Data"
    real = (data / "018Auri.bsa").resolve()
    arc = read_bsa(real)
    drop = {e.path.lower() for e in arc.entries if "facegendata" in e.folder.lower()}
    (data / "018Auri.bsa").unlink()
    rebuild_bsa(arc, data / "Mia.bsa", drop=drop)
    shutil.copyfile((data / "018Auri.esp").resolve(), data / "Mia.esp")
    (data / "018Auri.esp").unlink()
    ccc = _ccc(root)
    _set(ccc, ccc.read_bytes().replace(b"018Auri.esp", b"Mia.esp"))
    pack = Pack.open(root)
    f = next(f for f in run_audit(pack, deep=False).findings if f.code == "bsa-owner")
    assert f.alt and f.alt[0]["kind"] == "bsa_move_voices"
    apply(pack, f.alt[0])
    folders = {e.folder for e in read_bsa(data / "Mia.bsa").entries}
    assert "sound\\voice\\mia.esp\\018aurivoice" in folders


def test_typos_and_case(tmp_path):
    root = _copy("Vanilla+ Flowergirls (NSFW)", tmp_path)
    _set(_ccc(root), Path("private-test-data/outputs/skynx-fix2/_respaldos/2026-10-23-b/"
                          "Vanilla+ Flowergirls (NSFW)/contents/Skyrim_aoc.ccc").read_bytes())
    pack = Pack.open(root)
    res = run_audit(pack, deep=False)
    by = {f.subject: f for f in res.findings if f.code in ("list-missing-near", "list-case")}
    assert by["Sexlab.esm"].fix["risk"] == "seguro"
    # approximate matches are suggestions, never applied automatically
    assert by["Andromeda - Unique Standing Stone of Skyrim.esp"].fix["risk"] == "revisar"
    assert by["XPMSE.exp"].fix["risk"] == "revisar"
    for f in by.values():
        apply(pack, f.fix)
    after = run_audit(Pack.open(root), deep=False)
    assert not [f for f in after.findings if f.code in ("list-missing-near", "list-case")]


def test_fuzzy_is_not_safe(tmp_path):
    from skynx.audit import _near
    assert _near("Patch A.esp", ["Patch B.esp"])[1] is False
    assert _near("Mod v1.esp", ["Mod v2.esp"])[1] is False
    assert _near("Foo.esm", ["Foo.esp"]) == ("Foo.esp", False)
    assert _near("Ryn's X.esp", ["Ryn_s X.esp"]) == ("Ryn_s X.esp", True)
    assert _near("dD - A LITE.esp", ["dD - A LITE..esp"]) == ("dD - A LITE..esp", True)


def test_bom_fix_does_not_loop(tmp_path):
    root = _copy("Simonrim Modpack for Switch", tmp_path)
    ccc = _ccc(root)
    _set(ccc, b"\xef\xbb\xbf" + ccc.read_bytes())
    pack = Pack.open(root)
    f = next(f for f in run_audit(pack, deep=False).findings if f.code == "list-bom")
    apply(pack, f.fix)
    assert not ccc.read_bytes().startswith(b"\xef\xbb\xbf")
    assert not [x for x in run_audit(Pack.open(root), deep=False).findings if x.code == "list-bom"]


def test_cp1252_names_survive_ini_edit():
    from skynx.ini import parse_ini, set_archive_list
    raw = b"[Archive]\r\nsResourceArchiveList=Skyrim - Misc.bsa, Caf\xe9.bsa, Gone.bsa\r\n"
    cur = [c for c in parse_ini(raw).archive_list("sResourceArchiveList") if c != "Gone.bsa"]
    out = set_archive_list(raw, "sResourceArchiveList", cur)
    assert out == b"[Archive]\r\nsResourceArchiveList=Skyrim - Misc.bsa, Caf\xe9.bsa\r\n"


def test_list_edits_keep_other_lines():
    from skynx.ccc import edit_lines, reorder
    raw = b"A.esp\r\nB.esp\nC\xe9.esp\r\nD.esp"
    assert edit_lines(raw, {"B.esp": "Bb.esp"}) == b"A.esp\r\nBb.esp\nC\xe9.esp\r\nD.esp"
    out = reorder(raw, ["D.esp", "A.esp", "B.esp", "C\udce9.esp"])
    assert b"C\xe9.esp" in out and out.count(b"\n") == 3


def test_leftover_keeps_only_bsa(tmp_path):
    root = _copy("Avner ModPack Revised 2026", tmp_path)
    data = root / "Avner ModPack Revised 2026/01000A10041EA000/romfs/Data"
    (data / "Ryn's Standing Stones.bsa").unlink()
    pack = Pack.open(root)
    res = run_audit(pack, deep=False)
    left = next(f for f in res.findings if f.code == "leftover")
    assert left.fix["files"] == ["Ryn_s Standing Stones.esp"]
    ren = next(f for f in res.findings if f.code == "bsa-unloaded-near")
    assert ren.fix["renames"] == [{"from": "Ryn_s Standing Stones.bsa", "to": "Ryn's Standing Stones.bsa"}]


def test_undo_refuses_when_newer_changes(tmp_path):
    from skynx.history import HistoryError
    root = _copy("Avner ModPack Revised 2026", tmp_path)
    ccc = _ccc(root)
    original = (ORIG_CCC / "Avner ModPack Revised 2026/Avner ModPack Revised 2026/Skyrim_aoc.ccc").read_bytes()
    _set(ccc, original)
    pack = Pack.open(root)
    fs = [f for f in run_audit(pack, deep=False).findings if f.code == "list-missing-near"
          and f.fix["kind"] == "list_replace"][:2]
    apply(pack, fs[0].fix)
    apply(pack, fs[1].fix)
    newest, older = list_history(root)[:2]
    with pytest.raises(HistoryError):
        undo(root, older["id"])
    undo(root, newest["id"])
    undo(root, older["id"])
    assert ccc.read_bytes() == original
    with pytest.raises(HistoryError):
        undo(root, older["id"])


def test_ashiro_archives_make_removals_manual(tmp_path):
    pack = Pack.open(MIRROR / "Ashiro_s Light Modlist")
    res = run_audit(pack, deep=False)
    risky = [f for f in res.findings if f.code in ("list-missing", "ini-bsa-missing")]
    assert risky and all(f.fix["risk"] == "revisar" for f in risky)


def test_deploy_backup_and_overlap(tmp_path):
    from skynx.deploy import DeployError, deploy
    import zipfile
    pack_root = _copy("Simonrim Modpack for Switch", tmp_path)
    sd = tmp_path / "sd"
    old = sd / "atmosphere/contents/01000A10041EA000/romfs"
    old.mkdir(parents=True)
    (old / "viejo.txt").write_text("lo de antes")
    out = deploy(pack_root, sd)
    assert not (old / "viejo.txt").exists()
    assert (sd / "atmosphere/contents/01000A10041EB009/romfs/Skyrim_aoc.ccc").exists()
    with zipfile.ZipFile(out["backup"]) as z:
        assert "01000A10041EA000/romfs/viejo.txt" in z.namelist()
    with pytest.raises(DeployError):
        deploy(sd / "atmosphere", sd)


def test_trash_and_undo(tmp_path):
    root = _copy("Simonrim Modpack for Switch", tmp_path)
    pack = Pack.open(root)
    f = next(f for f in run_audit(pack, deep=False).findings if f.code == "leftover")
    apply(pack, f.fix)
    data = root / "01000A10041EA000/romfs/Data"
    assert not (data / "dD - Enhanced Blood Main LITE..esp").exists()
    undo(root, list_history(root)[0]["id"])
    assert (data / "dD - Enhanced Blood Main LITE..esp").exists()


def test_new_modpack_from_scratch(tmp_path):
    from skynx.builder import add_mod, create_project, mods_view, remove_mod, BuildError
    root = tmp_path / "nuevo"
    create_project(root, "AE", MIRROR / "Vanilla+ Flowergirls (NSFW)", "ussep")
    pack = Pack.open(root)
    assert pack.mode == "AE" and len(pack.list_entries) == 4
    lists = pack.archive_lists()
    assert all(b.lower().startswith("skyrim - ") for b in lists["sResourceArchiveList"])
    assert "unofficial skyrim special edition patch.esp" not in [t.lower() for t in pack.stest_plugins()]
    ash = Path("private-test-data/SkyNX/Other modpacks/Ashiro_s Light Modlist/atmosphere/contents/01000A10041EA000/romfs/Data")
    for m in ("USSEP 4.2.9 No CC - Koka NX.7z", "Odin 2.0.1 NX.7z"):
        add_mod(pack, ash / m)
    koka = Path("private-test-data/SkyNX/Other converted mods/Combat Walk and Run Animations Pak NX")
    rep = add_mod(pack, koka)
    # KokaNX (Oct 2026): animations only need sResourceArchiveList
    assert ("sResourceArchiveList", "Combat - Animations.bsa") in rep.ini_added
    assert not [k for k, _b in rep.ini_added if k == "sArchiveToLoadInMemoryList"]
    lists = pack.archive_lists()
    assert "OdnTs.bsa" in lists["sResourceArchiveList2"]          # textures by content
    assert pack.list_entries[-1] == "Odin - Skyrim Magic Overhaul.esp"
    res = run_audit(pack, deep=False)
    assert not [f for f in res.findings if f.severity == "critico"]
    with pytest.raises(BuildError):
        add_mod(pack, koka)                                        # already there
    remove_mod(pack, "Odin 2.0.1 NX")
    assert "OdnTs.bsa" not in pack.archive_lists()["sResourceArchiveList2"]
    assert [m["name"] for m in mods_view(pack)] == ["USSEP 4.2.9 No CC - Koka NX",
                                                   "Combat Walk and Run Animations Pak NX"]
    undo(root, list_history(root)[0]["id"])
    assert "OdnTs.bsa" in Pack.open(root).archive_lists()["sResourceArchiveList2"]


def test_messages_in_both_languages(tmp_path):
    from skynx import i18n
    for key, langs in i18n.MSG.items():
        assert set(langs) == {"en", "es"}, key
    pack = Pack.open(MIRROR / "Simonrim Modpack for Switch")
    res = run_audit(pack, deep=False)
    en = res.to_dict("en")["findings"]
    es = res.to_dict("es")["findings"]
    assert len(en) == len(es) and en[0]["title"] != "" and es[0]["title"] != ""
