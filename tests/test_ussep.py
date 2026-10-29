"""USSEP (KokaNX) in new packs."""
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from skynx.builder import BuildError, create_project, load_mods  # noqa: E402
from skynx.ccc import read_ccc  # noqa: E402
from skynx.ini import parse_ini  # noqa: E402
from skynx.pack import Pack  # noqa: E402
from skynx.ussep import scan  # noqa: E402
from skynx.audit import run_audit  # noqa: E402

FX = ROOT / "tests" / "fixtures" / "ussep"
INIS = ROOT / "tests" / "fixtures" / "console-inis"


def test_scan_variants():
    info = scan(FX)
    ids = {v["id"]: v["cc"] for v in info["variants"]}
    assert set(ids) == {"All_CC", "SurvivalMode", "No_CC"}
    assert ids["No_CC"] == [] and ids["SurvivalMode"] == ["ccQDRSSE001-SurvivalMode.esl"]
    assert len(ids["All_CC"]) == 4
    assert info["bsas"] == ["USSEP.bsa", "USSEPA.bsa", "USSEPT.bsa", "USSEPV.bsa"]


def test_new_pack_with_ussep_all_cc(tmp_path):
    root = create_project(tmp_path / "p", "AE", INIS, "none", ussep="All_CC", ussep_dir=FX)
    pack = Pack.open(root)
    entries = read_ccc(pack.ccc_path).entries
    assert entries[-1] == "Unofficial Skyrim Special Edition Patch.esp"
    assert len(entries) == 5            # 4 CC masters added before it
    for f in ("Unofficial Skyrim Special Edition Patch.esp", "USSEP.bsa", "USSEPA.bsa", "USSEPT.bsa", "USSEPV.bsa"):
        assert (pack.data_dir / f).exists()
    for ini in pack.ini_paths:
        p = parse_ini(ini.read_bytes())
        l2 = p.archive_list("sResourceArchiveList2")
        assert "USSEPT.bsa" in l2 and "USSEPV.bsa" in l2
    main = parse_ini((pack.base_romfs / "Skyrim.ini").read_bytes())
    assert {"USSEP.bsa", "USSEPA.bsa"} <= set(main.archive_list("sResourceArchiveList"))
    assert "USSEPA.bsa" not in main.archive_list("sArchiveToLoadInMemoryList")   # KokaNX, Oct 2026
    assert "USSEP (KokaNX, All_CC)" in load_mods(pack)
    crit = [f for f in run_audit(pack, deep=False).findings if f.severity == "critico"]
    assert not crit, [f.code for f in crit]


def test_se_needs_no_cc(tmp_path):
    with pytest.raises(BuildError):
        create_project(tmp_path / "a", "SE", INIS, "none", ussep="All_CC", ussep_dir=FX)
    assert not (tmp_path / "a").exists()
    root = create_project(tmp_path / "b", "SE", INIS, "none", ussep="No_CC", ussep_dir=FX)
    assert "Unofficial Skyrim Special Edition Patch.esp" in Pack.open(root).list_entries
