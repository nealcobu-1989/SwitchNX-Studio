"""Resolving duplicates from the Doctor: keep them, or take one copy out."""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tests"))
from skynx import fixes  # noqa: E402
from skynx.audit import run_audit  # noqa: E402
from skynx.history import list_history, undo  # noqa: E402
from skynx.pack import Pack  # noqa: E402
from skynx.plugin import read_header  # noqa: E402
from test_requirements import make_bsa, new_pack, plugin, rec, sub, zs  # noqa: E402


def weap(fid, edid):
    return rec("WEAP", fid, [sub("EDID", zs(edid))])


def finding(pack, code):
    res = run_audit(Pack.open(pack.root), deep=False)
    return [f for f in res.findings if f.code == code], res


def apply_alt(pack, f, label_key, **match):
    for a in f.alt:
        if a["label_key"] == label_key and all(a.get(k) == v for k, v in match.items()):
            return fixes.apply(Pack.open(pack.root), a)
    raise AssertionError(f"no alternative {label_key} {match}: {[x['label_key'] for x in f.alt]}")


def snapshot(root: Path) -> dict:
    return {str(p.relative_to(root)): p.read_bytes() for p in sorted(root.rglob("*"))
            if p.is_file() and ".skynx" not in p.parts}


def test_drive_twins_keep_one_and_repoint_patch(tmp_path):
    pack = new_pack(tmp_path, ["Ryn's Stones.esp", "Ryn_s Stones.esp", "Stones Patch.esp"])
    d = pack.data_dir
    for n in ("Ryn's Stones", "Ryn_s Stones"):
        plugin(d / f"{n}.esp", [weap(0x800, "RynStone")])
        make_bsa(d / f"{n}.bsa", {"meshes\\ryn\\stone.nif": b"x" * 10})
    plugin(d / "Stones Patch.esp", [weap(0x801, "P")], masters=("Skyrim.esm", "Ryn_s Stones.esp"))
    before = snapshot(pack.root)
    fs, _ = finding(pack, "dup-plugin-same")
    assert len(fs) == 1
    labels = {a["label_key"] for a in fs[0].alt}
    assert {"fix-dup-keep-only", "fix-dup-keep-both"} <= labels
    pv = fixes.preview(Pack.open(pack.root), next(a for a in fs[0].alt if a.get("keep") == "Ryn's Stones.esp"))
    assert any("Stones Patch.esp" in line for line in pv["changes"])
    apply_alt(pack, fs[0], "fix-dup-keep-only", keep="Ryn's Stones.esp")
    p = Pack.open(pack.root)
    assert not (d / "Ryn_s Stones.esp").exists() and not (d / "Ryn_s Stones.bsa").exists()
    assert (d / "Ryn's Stones.bsa").exists()
    assert "Ryn_s Stones.esp" not in p.list_entries and "Ryn's Stones.esp" in p.list_entries
    assert read_header(d / "Stones Patch.esp").masters == ["Skyrim.esm", "Ryn's Stones.esp"]
    assert not finding(p, "dup-plugin-same")[0]
    # one step in the history, and undo puts everything back
    undo(pack.root, list_history(pack.root)[0]["id"])
    assert snapshot(pack.root) == before


def test_keep_the_copy_that_wasnt_in_the_list(tmp_path):
    pack = new_pack(tmp_path, ["A.esp", "B.esp"])
    d = pack.data_dir
    plugin(d / "A.esp", [weap(0x800, "Same")])
    plugin(d / "B.esp", [weap(0x800, "Same")])
    fs, _ = finding(pack, "dup-plugin-same")
    apply_alt(pack, fs[0], "fix-dup-keep-only", keep="B.esp")
    p = Pack.open(pack.root)
    assert "A.esp" not in p.list_entries and "B.esp" in p.list_entries
    assert not (d / "A.esp").exists()


def merged_pack(tmp_path, with_patch: bool):
    active = ["Enai Merge.esp", "Wintersun.esp"] + (["Wintersun Patch.esp"] if with_patch else [])
    pack = new_pack(tmp_path, active)
    d = pack.data_dir
    plugin(d / "Enai Merge.esp", [weap(0x800, "W1"), weap(0x801, "O1")],
           snam="Merged Plugin: \r\n  Wintersun.esp\r\n  Ordinator.esp")
    plugin(d / "Wintersun.esp", [weap(0x800, "W1")])
    make_bsa(d / "Wintersun.bsa", {"scripts\\wsun.pex": b"p" * 8})
    if with_patch:
        plugin(d / "Wintersun Patch.esp", [weap(0x802, "WP")], masters=("Skyrim.esm", "Wintersun.esp"))
    return pack


def test_merged_component_becomes_placeholder_and_keeps_its_bsa(tmp_path):
    pack = merged_pack(tmp_path, with_patch=False)
    fs, _ = finding(pack, "dup-merged")
    assert len(fs) == 1
    apply_alt(pack, fs[0], "fix-dup-empty-loose")
    p = Pack.open(pack.root)
    h = read_header(pack.data_dir / "Wintersun.esp")
    assert h.num_records == 0 and "Wintersun.esp" in p.list_entries
    assert (pack.data_dir / "Wintersun.bsa").exists()          # merges usually don't repack assets
    assert not finding(p, "dup-merged")[0]


def test_merged_component_with_patch_becomes_placeholder(tmp_path):
    pack = merged_pack(tmp_path, with_patch=True)
    fs, _ = finding(pack, "dup-merged")
    assert any(a["label_key"] == "fix-dup-empty-loose" for a in fs[0].alt)
    apply_alt(pack, fs[0], "fix-dup-empty-loose")
    p = Pack.open(pack.root)
    h = read_header(pack.data_dir / "Wintersun.esp")
    assert h.num_records == 0 and h.masters == ["Skyrim.esm"] and not h.error
    assert "Wintersun.esp" in p.list_entries                   # the patch still finds its master
    assert not finding(p, "dup-merged")[0]                       # placeholders aren't duplicates


def test_keep_both_hides_it_and_can_show_it_again(tmp_path):
    pack = merged_pack(tmp_path, with_patch=False)
    fs, _ = finding(pack, "dup-merged")
    apply_alt(pack, fs[0], "fix-dup-keep-both")
    ign, res = finding(pack, "dup-ignored")
    assert not [f for f in res.findings if f.code == "dup-merged"]
    assert len(ign) == 1 and ign[0].fix["kind"] == "dup_unignore"
    assert (pack.data_dir / "Wintersun.esp").exists()
    fixes.apply(Pack.open(pack.root), ign[0].fix)
    assert finding(pack, "dup-merged")[0] and not finding(pack, "dup-ignored")[0]


def test_inactive_copy_deleted(tmp_path):
    pack = merged_pack(tmp_path, with_patch=False)
    ccc = pack.list_path
    ccc.write_bytes(ccc.read_bytes().replace(b"Wintersun.esp\r\n", b""))
    fs, _ = finding(pack, "dup-merged-copy")
    assert len(fs) == 1
    apply_alt(pack, fs[0], "fix-dup-delete-copy")
    assert not (pack.data_dir / "Wintersun.esp").exists()
    assert not (pack.data_dir / "Wintersun.bsa").exists()


def test_same_bsa_twice_keep_one(tmp_path):
    pack = new_pack(tmp_path, [])
    d = pack.data_dir
    files = {"textures\\x\\a.dds": b"a" * 64, "meshes\\x\\b.nif": b"b" * 32}
    make_bsa(d / "Pack A.bsa", files)
    make_bsa(d / "Pack B.bsa", files)
    from skynx.ini import read_ini, set_archive_list
    ini = next(p for p in pack.ini_paths if p.name.lower() == "skyrim.ini")
    cur = read_ini(ini).archive_list("sResourceArchiveList")
    ini.write_bytes(set_archive_list(ini.read_bytes(), "sResourceArchiveList", cur + ["Pack A.bsa", "Pack B.bsa"]))
    fs, _ = finding(pack, "dup-bsa")
    assert len(fs) == 1
    apply_alt(pack, fs[0], "fix-dup-keep-only", keep="Pack A.bsa")
    p = Pack.open(pack.root)
    assert not (d / "Pack B.bsa").exists() and (d / "Pack A.bsa").exists()
    lists = " ".join(", ".join(v) for v in p.archive_lists().values())
    assert "Pack B.bsa" not in lists and "Pack A.bsa" in lists


def test_mod_records_follow(tmp_path):
    pack = new_pack(tmp_path, ["A.esp", "B.esp"])
    d = pack.data_dir
    plugin(d / "A.esp", [weap(0x800, "Same")])
    plugin(d / "B.esp", [weap(0x800, "Same")])
    (pack.root / ".skynx").mkdir(exist_ok=True)
    (pack.root / ".skynx/mods.json").write_text(json.dumps({
        "Mod A": {"plugins": ["A.esp"], "bsas": []}, "Mod B": {"plugins": ["B.esp"], "bsas": []}}))
    fs, _ = finding(pack, "dup-plugin-same")
    apply_alt(pack, fs[0], "fix-dup-keep-only", keep="B.esp")
    recs = json.loads((pack.root / ".skynx/mods.json").read_text())
    assert "Mod A" not in recs and recs["Mod B"]["plugins"] == ["B.esp"]


def test_bsa_an_ini_loads_stays(tmp_path):
    pack = merged_pack(tmp_path, with_patch=False)
    from skynx.ini import read_ini, set_archive_list
    ini = next(p for p in pack.ini_paths if p.name.lower() == "skyrim.ini")
    cur = read_ini(ini).archive_list("sResourceArchiveList")
    ini.write_bytes(set_archive_list(ini.read_bytes(), "sResourceArchiveList", cur + ["Wintersun.bsa"]))
    fs, _ = finding(pack, "dup-merged")
    apply_alt(pack, fs[0], "fix-dup-empty-loose")
    assert read_header(pack.data_dir / "Wintersun.esp").num_records == 0
    assert (pack.data_dir / "Wintersun.bsa").exists()          # the merge may need its files
    assert "Wintersun.bsa" in read_ini(ini).archive_list("sResourceArchiveList")


def test_keep_the_later_copy_keeps_patch_order(tmp_path):
    pack = new_pack(tmp_path, ["Ryn_s Stones.esp", "Stones Patch.esp", "Ryn's Stones.esp"])
    d = pack.data_dir
    for n in ("Ryn's Stones", "Ryn_s Stones"):
        plugin(d / f"{n}.esp", [weap(0x800, "RynStone")])
    plugin(d / "Stones Patch.esp", [weap(0x801, "P")], masters=("Skyrim.esm", "Ryn_s Stones.esp"))
    fs, _ = finding(pack, "dup-plugin-same")
    apply_alt(pack, fs[0], "fix-dup-keep-only", keep="Ryn's Stones.esp")
    p = Pack.open(pack.root)
    e = [x.lower() for x in p.list_entries]
    assert e.index("ryn's stones.esp") < e.index("stones patch.esp")
    assert e.count("ryn's stones.esp") == 1
    res = run_audit(p, deep=False)
    assert not [f for f in res.findings if f.code.startswith("master")]


def test_keep_only_moves_or_keeps_bsas(tmp_path):
    # the kept copy has no BSA: the removed copy's BSA is renamed to go with it
    pack = new_pack(tmp_path, ["Ryn's Stones.esp", "Ryn_s Stones.esp"])
    d = pack.data_dir
    for n in ("Ryn's Stones", "Ryn_s Stones"):
        plugin(d / f"{n}.esp", [weap(0x800, "RynStone")])
    make_bsa(d / "Ryn_s Stones.bsa", {"meshes\\ryn\\stone.nif": b"x" * 10})
    fs, _ = finding(pack, "dup-plugin-same")
    apply_alt(pack, fs[0], "fix-dup-keep-only", keep="Ryn's Stones.esp")
    assert (d / "Ryn's Stones.bsa").exists() and not (d / "Ryn_s Stones.bsa").exists()


def test_keep_only_leaves_ini_loaded_bsa(tmp_path):
    pack = new_pack(tmp_path, ["Ryn's Stones.esp", "Ryn_s Stones.esp"])
    d = pack.data_dir
    for n in ("Ryn's Stones", "Ryn_s Stones"):
        plugin(d / f"{n}.esp", [weap(0x800, "RynStone")])
    make_bsa(d / "Ryn_s Stones.bsa", {"meshes\\ryn\\stone.nif": b"x" * 10})
    from skynx.ini import read_ini, set_archive_list
    ini = next(p for p in pack.ini_paths if p.name.lower() == "skyrim.ini")
    cur = read_ini(ini).archive_list("sResourceArchiveList")
    ini.write_bytes(set_archive_list(ini.read_bytes(), "sResourceArchiveList", cur + ["Ryn_s Stones.bsa"]))
    fs, _ = finding(pack, "dup-plugin-same")
    apply_alt(pack, fs[0], "fix-dup-keep-only", keep="Ryn's Stones.esp")
    assert (d / "Ryn_s Stones.bsa").exists()
    assert "Ryn_s Stones.bsa" in read_ini(ini).archive_list("sResourceArchiveList")


def test_keep_only_refuses_double_master(tmp_path):
    import pytest
    pack = new_pack(tmp_path, ["A.esp", "B.esp", "P.esp"])
    d = pack.data_dir
    plugin(d / "A.esp", [weap(0x800, "Same")])
    plugin(d / "B.esp", [weap(0x800, "Same")])
    plugin(d / "P.esp", [weap(0x801, "P")], masters=("Skyrim.esm", "A.esp", "B.esp"))
    fs, _ = finding(pack, "dup-plugin-same")
    a = next(x for x in fs[0].alt if x.get("keep") == "B.esp")
    pv = fixes.preview(Pack.open(pack.root), a)
    assert any("xEdit" in line for line in pv["changes"])
    with pytest.raises(Exception):
        fixes.apply(Pack.open(pack.root), a)
    assert (d / "A.esp").exists() and read_header(d / "P.esp").masters == ["Skyrim.esm", "A.esp", "B.esp"]


def test_missing_cc_masters_one_finding_with_cost(tmp_path):
    from skynx import knowledge as K
    pack = new_pack(tmp_path, ["CC Patch.esl"])
    d = pack.data_dir
    ccs = [c for c in K.AE_CC_PLUGINS][:3]
    raw = pack.list_path.read_bytes()
    for c in ccs:                     # make sure they're not in the list
        raw = b"\r\n".join(x for x in raw.split(b"\r\n") if x.decode().lower() != c.lower())
    pack.list_path.write_bytes(raw)
    plugin(d / "CC Patch.esl", [weap(0x800, "P")], masters=["Skyrim.esm"] + ccs)
    fs, _ = finding(pack, "master-cc")
    assert len(fs) == 1 and fs[0].items == ccs
    assert fs[0].fix["entries"] == ccs and fs[0].alt[0]["kind"] == "list_remove"
    fixes.apply(Pack.open(pack.root), fs[0].fix)
    p = Pack.open(pack.root)
    e = [x.lower() for x in p.list_entries]
    assert all(e.index(c.lower()) < e.index("cc patch.esl") for c in ccs)
    assert not finding(p, "master-cc")[0]


def test_missing_cc_masters_over_limit_offers_only_take_out(tmp_path):
    from skynx import knowledge as K
    pack = new_pack(tmp_path, ["CC Patch.esl"])
    d = pack.data_dir
    ccs = [c for c in K.AE_CC_PLUGINS][:3]
    raw = pack.list_path.read_bytes()
    for c in ccs:
        raw = b"\r\n".join(x for x in raw.split(b"\r\n") if x.decode().lower() != c.lower())
    filler = []
    i = 0
    while len(raw) + sum(len(f) + 2 for f in filler) < K.CCC_BYTE_LIMIT - 20:
        filler.append(f"Filler Plugin Number {i:03d}.esp")
        i += 1
    for f in filler:
        plugin(d / f, [weap(0x800, "F")])
    pack.list_path.write_bytes(raw + b"\r\n" + "\r\n".join(filler).encode())
    plugin(d / "CC Patch.esl", [weap(0x800, "P")], masters=["Skyrim.esm"] + ccs)
    pack.list_path.write_bytes(pack.list_path.read_bytes() + b"\r\nCC Patch.esl")
    fs, _ = finding(pack, "master-cc")
    assert len(fs) == 1 and fs[0].fix is None and fs[0].alt[0]["kind"] == "list_remove"
    fixes.apply(Pack.open(pack.root), fs[0].alt[0])
    assert "CC Patch.esl" not in Pack.open(pack.root).list_entries
