"""Texts a patch saved as "<Error: No strings file for lstring ID ...>" (textfix.py),
the count of mod files open from the SD, and what the Doctor leaves alone."""
import struct
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT), str(ROOT / "tests")]

from skynx import textfix as TF  # noqa: E402
from skynx.audit import run_audit, sd_open_files  # noqa: E402
from skynx.fixes import apply  # noqa: E402
from skynx.pack import Pack  # noqa: E402
from skynx.records import iter_records  # noqa: E402
from test_requirements import data, make_bsa, new_pack, plugin, rec, sub, zs  # noqa: E402

ERR = "<Error: No strings file for lstring ID {:08X}>"


def strings_file(table: dict[int, str]) -> bytes:
    ids, blob, offs = sorted(table), b"", []
    for i in ids:
        offs.append(len(blob))
        blob += table[i].encode("utf-8") + b"\0"
    head = struct.pack("<II", len(ids), len(blob))
    return head + b"".join(struct.pack("<II", i, o) for i, o in zip(ids, offs)) + blob


def localized(path: Path) -> Path:
    raw = bytearray(path.read_bytes())
    struct.pack_into("<I", raw, 8, struct.unpack_from("<I", raw, 8)[0] | 0x80)
    path.write_bytes(bytes(raw))
    return path


def setup(tmp_path, compressed=False):
    pack = new_pack(tmp_path, ["Patch.esp"])
    favor = 0x000CA439                              # a Skyrim.esm quest (index 0)
    plugin(data(pack) / "Patch.esp", [rec("QUST", favor, [
        sub("EDID", zs("Favor110")), sub("FULL", zs(ERR.format(0x3728))),
        sub("NNAM", zs(ERR.format(0x3729))), sub("NNAM", zs("Kept as it is"))], compressed=compressed)])
    van = tmp_path / "vanilla"
    van.mkdir()
    localized(plugin(van / "Skyrim.esm", [], masters=()))
    make_bsa(van / "Skyrim - Interface.bsa", {
        "strings\\skyrim_english.strings": strings_file({0x3728: "Rare Gifts", 0x3729: "Bring one tusk to Ysolda"})})
    return Pack.open(pack.root), van


def test_scan_finds_the_error_texts_and_the_game_gives_them_back(tmp_path):
    pack, van = setup(tmp_path)
    found = TF.scan(data(pack) / "Patch.esp")
    assert [(f["sig"], f["n"], f["sid"], f["master"]) for f in found] == [
        ("FULL", 0, 0x3728, "Skyrim.esm"), ("NNAM", 0, 0x3729, "Skyrim.esm")]
    back = TF.game_texts(found, {"skyrim.esm": van / "Skyrim.esm"}, "english", [van])
    assert back == {(0x000CA439, "FULL", 0): "Rare Gifts", (0x000CA439, "NNAM", 0): "Bring one tusk to Ysolda"}


def test_doctor_offers_the_fix_and_it_changes_only_those_texts(tmp_path):
    pack, van = setup(tmp_path)
    fs = [f for f in run_audit(pack, deep=False, vanilla_dir=van).findings if f.code == "text-baked-error"]
    assert len(fs) == 1 and fs[0].params["fixable"] == 2 and fs[0].fix
    apply(pack, fs[0].fix)
    subs = list(next(iter_records(data(pack) / "Patch.esp", types=["QUST"])).subrecords())
    assert subs == [("EDID", zs("Favor110")), ("FULL", zs("Rare Gifts")),
                    ("NNAM", zs("Bring one tusk to Ysolda")), ("NNAM", zs("Kept as it is"))]
    assert not [f for f in run_audit(Pack.open(pack.root), deep=False, vanilla_dir=van).findings
                if f.code == "text-baked-error"]


def test_a_compressed_record_is_found_by_the_deep_check(tmp_path):
    pack, _van = setup(tmp_path, compressed=True)
    assert TF.scan(data(pack) / "Patch.esp", deep=False) == []
    assert len(TF.scan(data(pack) / "Patch.esp", deep=True)) == 2


def test_sd_open_files_counts_mod_plugins_and_their_bsas(tmp_path):
    pack = new_pack(tmp_path, ["A.esp", "B.esp", "#C.esp"])
    for n in ("A", "B", "C"):
        plugin(data(pack) / f"{n}.esp", [])
        make_bsa(data(pack) / f"{n}.bsa", {"meshes\\x.nif": b"x"})
    make_bsa(data(pack) / "A - Textures.bsa", {"textures\\x.dds": b"x"})
    c = sd_open_files(Pack.open(pack.root))
    assert c == {"plugins": 2, "ini": 0, "plugin_bsas": 3, "total": 5}     # C is off: none of its files open
    fs = [f for f in run_audit(Pack.open(pack.root), deep=False).findings if f.code == "sd-open-files"]
    assert len(fs) == 1 and fs[0].severity == "info" and fs[0].params["n"] == 5


def test_doctor_leaves_mods_that_dont_go_alone(tmp_path):
    """A parked mod's BSA (Lucien's CC patch, renamed short) isn't "a BSA that
    doesn't load and should be renamed": it's out on purpose."""
    import json
    from skynx import draft as DR
    from skynx.builder import mods_view
    from skynx.history import Transaction
    pack = new_pack(tmp_path / "src", ["Lucien.esp", "LucienCCPatch.esp"])
    plugin(data(pack) / "Lucien.esp", [])
    plugin(data(pack) / "LucienCCPatch.esp", [], masters=("Skyrim.esm", "Lucien.esp"))
    make_bsa(data(pack) / "Lucien2.bsa", {"meshes\\x.nif": b"x"})
    (Path(pack.root) / ".skynx").mkdir(exist_ok=True)
    (Path(pack.root) / ".skynx" / "mods.json").write_text(json.dumps(
        {"Lucien CC patch": {"plugins": ["LucienCCPatch.esp"], "bsas": ["Lucien2.bsa"]}}))
    d = DR.start_from_pack(Pack.open(pack.root), tmp_path / "Drafts" / "Mine", "Mine")
    row = next(r for r in mods_view(d) if r["id"] == "Lucien CC patch")
    with Transaction(d.root, "out") as tx:
        DR.exclude(d, row, tx)
    codes = {(f.code, f.subject) for f in run_audit(Pack.open(d.root), deep=False).findings}
    assert not {c for c in codes if c[1] in ("Lucien2.bsa", "LucienCCPatch.esp")}
