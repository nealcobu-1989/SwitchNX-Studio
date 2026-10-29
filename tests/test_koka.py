"""KokaNX's research (Oct 2026): in-memory list, HEDR 1.71 on SE, SEQ files,
USSEP placement, and the converter's packing / compression / size options."""
import shutil
import struct
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tests"))
from skynx import knowledge as K  # noqa: E402
from skynx import records as REC  # noqa: E402
from skynx.audit import run_audit  # noqa: E402
from skynx.bsa import read_bsa  # noqa: E402
from skynx.builder import add_mod, create_project  # noqa: E402
from skynx.ccc import read_ccc  # noqa: E402
from skynx.fixes import apply, preview  # noqa: E402
from skynx.history import list_history, undo  # noqa: E402
from skynx.ini import read_ini, set_archive_list  # noqa: E402
from skynx.pack import Pack  # noqa: E402
from skynx.plugin import read_header  # noqa: E402
from skynx.texplan import max_side, plan_texture, with_cap  # noqa: E402
from skynx.textures import TexInfo  # noqa: E402
from test_requirements import make_bsa, new_pack, plugin, rec, sub, zs  # noqa: E402

INIS = ROOT / "tests" / "fixtures" / "console-inis"
USSEP_FX = ROOT / "tests" / "fixtures" / "ussep"
MEM = "sArchiveToLoadInMemoryList"
USSEP = K.USSEP_PLUGIN


def codes(pack, code, deep=True):
    return [f for f in run_audit(Pack.open(pack.root), deep=deep).findings if f.code == code]


def snapshot(root: Path) -> dict:
    return {str(p.relative_to(root)): p.read_bytes() for p in sorted(Path(root).rglob("*"))
            if p.is_file() and ".skynx" not in p.parts}


def set_list(pack: Pack, ini: str, key: str, items: list[str]) -> None:
    p = pack.base_romfs / ini
    p.write_bytes(set_archive_list(p.read_bytes(), key, items))


def anim_bsa(path: Path) -> Path:
    return make_bsa(path, {"meshes\\actors\\character\\animations\\koka\\idle.hkx": b"\x57\xe0\xe0\x57" + b"\0" * 60})


# ------------------------------------------------------------------ 1. in-memory list
def test_builder_puts_animations_in_resource_list_only(tmp_path):
    pack = Pack.open(create_project(tmp_path / "p", "AE", INIS, "none"))
    m = tmp_path / "Core Anims"
    m.mkdir()
    anim_bsa(m / "Core - Animations.bsa")
    rep = add_mod(pack, m)
    assert rep.ini_added == [("sResourceArchiveList", "Core - Animations.bsa")]
    sky = read_ini(pack.base_romfs / "Skyrim.ini")
    assert "Core - Animations.bsa" in sky.archive_list("sResourceArchiveList")
    assert "Core - Animations.bsa" not in sky.archive_list(MEM)
    assert not codes(pack, "ini-memory-mods")


def test_mod_bsas_in_memory_list_finding_fix_undo(tmp_path):
    pack = Pack.open(create_project(tmp_path / "p", "AE", INIS, "none"))
    anim_bsa(pack.data_dir / "OnlyMem.bsa")           # only in the in-memory list
    anim_bsa(pack.data_dir / "Both.bsa")              # in both lists
    sky = read_ini(pack.base_romfs / "Skyrim.ini")
    set_list(pack, "Skyrim.ini", "sResourceArchiveList", sky.archive_list("sResourceArchiveList") + ["Both.bsa"])
    set_list(pack, "Skyrim.ini", MEM, ["Skyrim - Animations.bsa", "OnlyMem.bsa", "Both.bsa"])
    pack = Pack.open(pack.root)
    before = snapshot(pack.root)
    [f] = codes(pack, "ini-memory-mods", deep=False)
    assert f.severity == "ahorro" and f.items == ["OnlyMem.bsa", "Both.bsa"]
    assert f.fix["risk"] == "revisar"
    en, es = f.text("en"), f.text("es")
    assert "T-poses" in en[1] and "T-poses" in es[1] and "RAM" in en[1]
    assert "—" not in es[1] + es[0]
    pv = preview(pack, f.fix, "en")
    assert any("remove 'OnlyMem.bsa'" in c for c in pv["changes"])
    assert any("add 'OnlyMem.bsa' so it keeps loading" in c for c in pv["changes"])
    assert not any("add 'Both.bsa'" in c for c in pv["changes"])
    assert "T-poses" in pv["changes"][-1]
    assert preview(pack, f.fix, "es")["label"] == "Sacarlos de la lista en memoria"
    apply(pack, f.fix)
    sky = read_ini(pack.base_romfs / "Skyrim.ini")
    assert sky.archive_list(MEM) == ["Skyrim - Animations.bsa"]
    res = sky.archive_list("sResourceArchiveList")
    assert res.count("Both.bsa") == 1 and res.count("OnlyMem.bsa") == 1
    assert not codes(pack, "ini-memory-mods", deep=False)
    assert not [x for x in codes(pack, "bsa-unloaded", deep=False) if x.subject in ("OnlyMem.bsa", "Both.bsa")]
    undo(pack.root, list_history(pack.root)[0]["id"])
    assert snapshot(pack.root) == before


def test_vanilla_memory_entries_are_not_reported(tmp_path):
    pack = Pack.open(create_project(tmp_path / "p", "AE", INIS, "none"))
    set_list(pack, "Skyrim.ini", MEM, ["Skyrim - Animations.bsa", "RelicsofHyruleDragonborn - Animations.bsa"])
    assert not codes(pack, "ini-memory-mods", deep=False)


def test_transfer_drops_the_in_memory_list(tmp_path):
    from skynx.transfer import apply_transfer, list_pack_mods, plan_transfer
    src = Pack.open(create_project(tmp_path / "src", "AE", INIS, "none"))
    anim_bsa(src.data_dir / "CoreAnim.bsa")
    sky = read_ini(src.base_romfs / "Skyrim.ini")
    set_list(src, "Skyrim.ini", "sResourceArchiveList", sky.archive_list("sResourceArchiveList") + ["CoreAnim.bsa"])
    set_list(src, "Skyrim.ini", MEM, ["Skyrim - Animations.bsa", "CoreAnim.bsa"])
    src = Pack.open(src.root)
    dst = Pack.open(create_project(tmp_path / "dst", "AE", INIS, "none"))
    units = list_pack_mods(src)
    u = next(x for x in units if "CoreAnim.bsa" in x.bsas)
    plan = plan_transfer(src, dst, [u.id], units)
    assert plan.ok, plan.errors
    apply_transfer(plan)
    sky = read_ini(dst.base_romfs / "Skyrim.ini")
    assert "CoreAnim.bsa" in sky.archive_list("sResourceArchiveList")
    assert "CoreAnim.bsa" not in sky.archive_list(MEM)


# ------------------------------------------------------------------ 2. HEDR 1.71 on SE
def _plugin_mod(tmp_path, name, records=(), version=1.71):
    m = tmp_path / ("mod-" + Path(name).stem)
    plugin(m / name, list(records))
    if version != 1.71:
        p = m / name
        p.write_bytes(REC.set_hedr_version(p.read_bytes(), version))
    return m


def test_hedr_171_on_se_finding_fix_undo(tmp_path):
    pack = Pack.open(create_project(tmp_path / "p", "SE", INIS, "none"))
    low = rec("MISC", 0x01000123, [sub("EDID", zs("LowId"))])          # own record below 0x800
    add_mod(pack, _plugin_mod(tmp_path, "New.esp", [low]))
    add_mod(pack, _plugin_mod(tmp_path, "Old.esp", version=1.70))
    pack = Pack.open(pack.root)
    found = codes(pack, "plugin-hedr171-se", deep=False)
    assert [f.subject for f in found] == ["New.esp"]
    f = found[0]
    assert f.severity == "aviso" and f.fix["risk"] == "revisar"
    assert "0x800" in f.text("en")[1] and "0x800" in f.text("es")[1]
    pv = preview(pack, f.fix, "es")
    assert pv["changes"] == ["New.esp: versión del encabezado 1.71 → 1.70 (solo cambian esos 4 bytes)"]
    path = pack.data_dir / "New.esp"
    raw = path.read_bytes()
    apply(pack, f.fix)
    new = path.read_bytes()
    assert len(new) == len(raw) and sum(a != b for a, b in zip(raw, new)) <= 4
    assert read_header(path).hedr_version == 1.70
    assert not codes(pack, "plugin-hedr171-se", deep=False)
    undo(pack.root, list_history(pack.root)[0]["id"])
    assert path.read_bytes() == raw


def test_hedr_171_not_on_ae(tmp_path):
    pack = Pack.open(create_project(tmp_path / "p", "AE", INIS, "none"))
    add_mod(pack, _plugin_mod(tmp_path, "New.esp"))
    assert read_header(pack.data_dir / "New.esp").hedr_version == 1.71
    assert not codes(pack, "plugin-hedr171-se", deep=False)


def test_low_ids_on_ae_are_flagged(tmp_path):
    """HEDR 1.71 alone loads on Switch (Summermyst 4 in KokaNX's packs); IDs
    below 0x800 (extended ESL, PC 1.6.1130) probably don't: the Switch build
    is from 2022."""
    from skynx.precheck import precheck
    pack = Pack.open(create_project(tmp_path / "p", "AE", INIS, "none"))
    low = rec("MISC", 0x01000123, [sub("EDID", zs("LowId"))])
    ok = rec("MISC", 0x01000823, [sub("EDID", zs("HighId"))])
    m = _plugin_mod(tmp_path, "Low.esp", [low])
    notes = precheck(pack, m)["notes"]
    assert any("0x800" in n["es"] and "2022" in n["es"] for n in notes)
    add_mod(pack, m)
    add_mod(pack, _plugin_mod(tmp_path, "High.esp", [ok]))
    pack = Pack.open(pack.root)
    found = codes(pack, "plugin-lowid-nx", deep=False)
    assert [f.subject for f in found] == ["Low.esp"] and found[0].severity == "aviso"
    assert "1.6.1130" in found[0].text("es")[1]
    se = Pack.open(create_project(tmp_path / "se", "SE", INIS, "none"))
    add_mod(se, _plugin_mod(tmp_path / "x", "Low.esp", [low]))
    assert not codes(Pack.open(se.root), "plugin-lowid-nx", deep=False)    # SE has its own finding


# ------------------------------------------------------------------ 3. SEQ
def dnam(flags: int) -> bytes:
    return sub("DNAM", struct.pack("<HBB4sI", flags, 50, 0, b"\0" * 4, 0))


def quest(fid: int, flags: int, compressed: bool = False) -> bytes:
    return rec("QUST", fid, [sub("EDID", zs(f"Q{fid:08X}")), dnam(flags)], compressed)


def test_seq_format_matches_xedit():
    assert REC.seq_bytes([0x01000801, 0x0100ABCD]) == bytes.fromhex("01080001CDAB0001")
    assert REC.parse_seq(bytes.fromhex("01080001CDAB0001")) == [0x01000801, 0x0100ABCD]
    with pytest.raises(REC.RecordError):
        REC.parse_seq(b"\0\0\0")


def test_seq_wanted_rules(tmp_path):
    d = tmp_path / "d"
    # Base.esp defines 0x01000900 (not SGE) and 0x01000901 (SGE)
    plugin(d / "Base.esp", [quest(0x01000900, 0), quest(0x01000901, 1)])
    plugin(d / "Patch.esp", [
        quest(0x02000801, 0x0001 | 0x0010, compressed=True),    # new, SGE (with other flags)
        quest(0x02000802, 0x0010),                              # new, not SGE
        quest(0x01000900, 1),                                   # turns SGE on for a master quest
        quest(0x01000901, 1),                                   # already SGE in its master
        quest(0x00012345, 1),                                   # Skyrim.esm quest: undecided
    ], masters=("Skyrim.esm", "Base.esp"))
    scans = {"base.esp": REC.quest_scan(d / "Base.esp")}
    want, unknown = REC.seq_wanted(d / "Patch.esp", lambda m: scans.get(m.lower()))
    assert want == [0x02000801, 0x01000900]
    assert unknown == [0x00012345]


def _seq_pack(tmp_path, own_bsa: bool):
    pack = new_pack(tmp_path, ["QuestMod.esp", "NoQuests.esp"])
    plugin(pack.data_dir / "QuestMod.esp", [quest(0x01000801, 1), quest(0x01000802, 0),
                                            quest(0x00012345, 1)])
    plugin(pack.data_dir / "NoQuests.esp", [quest(0x01000805, 0)])
    if own_bsa:
        make_bsa(pack.data_dir / "QuestMod.bsa", {"meshes\\qm\\a.nif": b"Gamebryo" * 20})
    return Pack.open(pack.root)


@pytest.mark.parametrize("own_bsa", [False, True])
def test_seq_missing_finding_fix_undo(tmp_path, own_bsa):
    pack = _seq_pack(tmp_path, own_bsa)
    assert not codes(pack, "seq-missing", deep=False)          # deep only
    before = snapshot(pack.root)
    [f] = codes(pack, "seq-missing")
    assert f.subject == "QuestMod.esp" and f.severity == "aviso" and f.items == ["01000801"]
    assert f.fix["risk"] == "revisar" and f.fix["bsa"] == "QuestMod.bsa"
    assert "questmod.seq" in f.text("es")[1]
    pv = preview(pack, f.fix, "en")["changes"]
    if own_bsa:
        assert pv[0] == "QuestMod.bsa: add seq\\questmod.seq with 1 quests"
    else:
        assert pv == ["Data: create 'QuestMod.bsa' with seq\\questmod.seq (1 quests); it loads with QuestMod.esp"]
    apply(pack, f.fix)
    arc = read_bsa(pack.data_dir / "QuestMod.bsa")
    got = {e.path: arc.read_file(e) for e in arc.entries}
    assert got["seq\\questmod.seq"] == struct.pack("<I", 0x01000801)
    if own_bsa:
        assert got["meshes\\qm\\a.nif"] == b"Gamebryo" * 20
    assert not codes(pack, "seq-missing") and not codes(pack, "seq-differ")
    undo(pack.root, list_history(pack.root)[0]["id"])
    assert snapshot(pack.root) == before


def test_seq_differ_and_rewrite(tmp_path):
    pack = _seq_pack(tmp_path, False)
    # an SEQ that misses the new quest and lists one that isn't SGE; the undecided
    # Skyrim.esm override it also lists is neither missing nor extra
    make_bsa(pack.data_dir / "QuestMod.bsa", {
        "seq\\questmod.seq": REC.seq_bytes([0x01000802, 0x00012345]),
        "meshes\\qm\\a.nif": b"Gamebryo"})
    pack = Pack.open(pack.root)
    assert not codes(pack, "seq-missing")
    [f] = codes(pack, "seq-differ")
    assert f.severity == "info" and f.fix["risk"] == "revisar"
    assert f.params["missing"] == "01000801" and f.params["extra"] == "01000802"
    assert preview(pack, f.fix, "es")["changes"][0] == \
        "QuestMod.bsa: reemplazar seq\\questmod.seq por uno con 2 misiones"
    apply(pack, f.fix)
    arc = read_bsa(pack.data_dir / "QuestMod.bsa")
    with (pack.data_dir / "QuestMod.bsa").open("rb") as fh:
        got = {e.path: arc.read_file(e, fh) for e in arc.entries}
    assert REC.parse_seq(got["seq\\questmod.seq"]) == [0x01000801, 0x00012345]
    assert got["meshes\\qm\\a.nif"] == b"Gamebryo"
    assert not codes(pack, "seq-differ")


def test_seq_loose_and_ini_bsa_count(tmp_path):
    pack = _seq_pack(tmp_path, False)
    (pack.data_dir / "seq").mkdir()
    (pack.data_dir / "seq" / "QuestMod.seq").write_bytes(REC.seq_bytes([0x01000801]))
    assert not codes(pack, "seq-missing") and not codes(pack, "seq-differ")
    shutil.rmtree(pack.data_dir / "seq")
    # an SEQ inside a BSA loaded from the ini (KokaNX's USSEP.bsa style) also counts
    make_bsa(pack.data_dir / "QM.bsa", {"seq\\questmod.seq": REC.seq_bytes([0x01000801])})
    sky = read_ini(pack.base_romfs / "Skyrim.ini")
    set_list(pack, "Skyrim.ini", "sResourceArchiveList", sky.archive_list("sResourceArchiveList") + ["QM.bsa"])
    assert not codes(pack, "seq-missing") and not codes(pack, "seq-differ")


def test_seq_goes_into_a_converted_mods_ini_bsa(tmp_path):
    """Convert names a mod's one BSA so it can't load by the plugin's name
    (Tonal.esp + TonalB.bsa, loaded from the ini): the SEQ goes in there."""
    pack = Pack.open(create_project(tmp_path / "pk", "AE", INIS, "none"))
    m = _plugin_mod(tmp_path, "Tonal.esp", [quest(0x01000801, 1)])
    make_bsa(m / "TonalB.bsa", {"meshes\\tonal\\a.nif": b"Gamebryo" * 20})
    add_mod(pack, m)
    pack = Pack.open(pack.root)
    assert any("tonalb.bsa" in [b.lower() for b in v] for v in pack.archive_lists().values())
    [f] = [x for x in codes(pack, "seq-missing") if x.subject == "Tonal.esp"]
    assert f.fix["bsa"] == "TonalB.bsa" and not f.fix.get("create")
    apply(pack, f.fix)
    pack = Pack.open(pack.root)
    assert not (pack.data_dir / "Tonal.bsa").exists()
    names = {e.path for e in read_bsa(pack.data_dir / "TonalB.bsa").entries}
    assert {"seq\\tonal.seq", "meshes\\tonal\\a.nif"} <= names
    assert not [x for x in codes(pack, "seq-missing") if x.subject == "Tonal.esp"]


# ------------------------------------------------------------------ 4. USSEP placement
def _other_mod(tmp_path):
    m = tmp_path / "Other"
    plugin(m / "Other.esp", [])
    anim_bsa(m / "OtherAnim.bsa")
    make_bsa(m / "OtherTex.bsa", {"textures\\other\\a.dds": b"DDS " + b"\0" * 124})
    return m


def test_ussep_install_goes_first(tmp_path):
    from skynx.ussep import install
    pack = Pack.open(create_project(tmp_path / "p", "AE", INIS, "all"))
    add_mod(pack, _other_mod(tmp_path))
    install(Pack.open(pack.root), USSEP_FX, "All_CC")
    pack = Pack.open(pack.root)
    entries = pack.list_entries
    i = entries.index(USSEP)
    assert entries.index("Other.esp") == i + 1 and all(e.lower().startswith("cc") for e in entries[:i])
    for ini in pack.inis:
        for key in ("sResourceArchiveList", "sResourceArchiveList2"):
            cur = ini.archive_list(key)
            us = [b for b in cur if b.lower().startswith("ussep")]
            if not us:
                continue
            at = max(n for n, b in enumerate(cur) if K.is_vanilla_bsa(b)) + 1
            assert cur[at:at + len(us)] == us, (ini.path.name, key, cur)
    sky = read_ini(pack.base_romfs / "Skyrim.ini")
    assert {"USSEP.bsa", "USSEPA.bsa"} <= set(sky.archive_list("sResourceArchiveList"))
    assert not [b for b in sky.archive_list(MEM) if not K.is_vanilla_bsa(b)]
    res = run_audit(pack, deep=False)
    assert not [f for f in res.findings if f.code in ("ussep-first", "ussep-bsa-order", "ini-memory-mods")]


def test_ussep_out_of_place_findings_fix_undo(tmp_path):
    pack = Pack.open(create_project(tmp_path / "p", "AE", INIS, "all", ussep="All_CC", ussep_dir=USSEP_FX))
    add_mod(pack, _other_mod(tmp_path))
    pack = Pack.open(pack.root)
    # move USSEP after Other.esp, and its BSAs after the other mod's
    ccc = pack.ccc_path
    entries = [e for e in read_ccc(ccc).entries if e != USSEP] + [USSEP]
    ccc.write_bytes("\r\n".join(entries).encode() + b"\r\n")
    for ini in pack.inis:
        for key in ("sResourceArchiveList", "sResourceArchiveList2"):
            cur = ini.archive_list(key)
            us = [b for b in cur if b.lower().startswith("ussep")]
            if us:
                set_list(pack, ini.path.name, key, [b for b in cur if b not in us] + us)
    pack = Pack.open(pack.root)
    before = snapshot(pack.root)
    [first] = codes(pack, "ussep-first", deep=False)
    assert first.severity == "aviso" and first.fix["risk"] == "revisar"
    assert first.params["n"] == 1 and first.params["before"] == "Other.esp"
    assert "Creation Club" in first.text("es")[1]
    pv = preview(pack, first.fix, "en")["changes"]
    assert pv == [f"Skyrim_aoc.ccc: move '{USSEP}' right after '{entries[-3]}'"]
    [order] = codes(pack, "ussep-bsa-order", deep=False)
    assert order.severity == "aviso" and order.fix["risk"] == "revisar"
    assert "Skyrim.ini sResourceArchiveList" in order.params["where"]
    assert set(order.items) == {"USSEP.bsa", "USSEPA.bsa", "USSEPT.bsa", "USSEPV.bsa"}
    apply(pack, first.fix)
    pack = Pack.open(pack.root)
    ent = pack.list_entries
    assert ent.index(USSEP) == ent.index("Other.esp") - 1
    apply(pack, order.fix)
    pack = Pack.open(pack.root)
    assert not codes(pack, "ussep-first", deep=False) and not codes(pack, "ussep-bsa-order", deep=False)
    sky = read_ini(pack.base_romfs / "Skyrim.ini").archive_list("sResourceArchiveList")
    assert sky.index("USSEP.bsa") < sky.index("OtherAnim.bsa")
    crit = [f for f in run_audit(pack, deep=False).findings if f.severity == "critico"]
    assert not crit, [f.code for f in crit]
    for h in list_history(pack.root)[:2]:
        undo(pack.root, h["id"])
    assert snapshot(pack.root) == before


def test_ussep_first_on_se(tmp_path):
    pack = Pack.open(create_project(tmp_path / "p", "SE", INIS, "none", ussep="No_CC", ussep_dir=USSEP_FX))
    add_mod(pack, _other_mod(tmp_path))
    pack = Pack.open(pack.root)
    assert pack.list_entries[0] == USSEP
    assert not codes(pack, "ussep-first", deep=False)
    pack.plugins_path.write_bytes(b"Other.esp\n" + USSEP.encode() + b"\n")
    [f] = codes(pack, "ussep-first", deep=False)
    assert preview(Pack.open(pack.root), f.fix, "en")["changes"] == [f"Plugins: move '{USSEP}' to the first line"]
    apply(Pack.open(pack.root), f.fix)
    assert Pack.open(pack.root).list_entries == [USSEP, "Other.esp"]


def test_ussep_master_listed_late_stays_before(tmp_path):
    """If one of USSEP's Creation Club masters is listed after other mods,
    USSEP only moves up to right after it."""
    pack = Pack.open(create_project(tmp_path / "p", "AE", INIS, "none", ussep="All_CC", ussep_dir=USSEP_FX))
    add_mod(pack, _other_mod(tmp_path))
    pack = Pack.open(pack.root)
    ent = read_ccc(pack.ccc_path).entries
    late = "ccBGSSSE025-AdvDSGS.esm"
    ent = [e for e in ent if e not in (late, USSEP)]
    ent = ent + [late, "Mod2.esp", USSEP]
    plugin(pack.data_dir / "Mod2.esp", [])
    pack.ccc_path.write_bytes("\r\n".join(ent).encode() + b"\r\n")
    pack = Pack.open(pack.root)
    [f] = codes(pack, "ussep-first", deep=False)
    assert f.params["before"] == "Mod2.esp" and f.params["n"] == 1
    apply(pack, f.fix)
    e = Pack.open(pack.root).list_entries
    assert e.index(USSEP) == e.index(late) + 1
    assert not [x for x in codes(pack, "master-order", deep=False) if x.subject.startswith(USSEP)]


# ------------------------------------------------------------------ 6. texture size
def tex(w, h, fmt="BC3", mips=None):
    from skynx.texplan import full_mips
    return TexInfo("DDS", fmt, w, h, mips or full_mips(w, h), False, 0)


def test_max_size_caps_the_largest_side():
    # koka: 1024 by area; a cap goes on top
    assert (plan_texture("textures\\a\\b.dds", tex(2048, 2048), "koka", False).tw) == 1024
    p = plan_texture("textures\\a\\b.dds", tex(2048, 2048), "koka", False, 512)
    assert (p.tw, p.th) == (512, 512)
    p = plan_texture("textures\\a\\b.dds", tex(4096, 1024), "none", False, 2048)
    assert (p.tw, p.th) == (2048, 512)
    p = plan_texture("textures\\actors\\b.dds", tex(4096, 4096), "koka", False, 4096)
    assert (p.tw, p.th) == (2048, 2048)          # the preset is smaller than the cap
    p = plan_texture("textures\\a\\small.dds", tex(256, 256), "none", False, 1024)
    assert (p.tw, p.th) == (256, 256)            # never enlarged
    p = plan_texture("interface\\a\\icon.dds", tex(2048, 64, mips=1), "koka", False, 256)
    assert (p.tw, p.th, p.tmips) == (2048, 64, 1)  # user interface left alone
    p = plan_texture("textures\\a\\b.dds", tex(2048, 2048), "none", False)
    assert (p.tw, p.th) == (2048, 2048) and not p.texconv
    # the same cap, for code that only passes a preset name (diet.py)
    assert max_side("textures\\a\\b.dds", with_cap("koka", 512)) == 512
    assert max_side("textures\\a\\b.dds", with_cap("none", 2048)) == 2048
    assert max_side("textures\\a\\b.dds", "none") is None
    assert max_side("interface\\b.dds", with_cap("koka", 512)) is None
    assert max_side("textures\\actors\\b.dds", "koka") == 2048     # presets unchanged


# ------------------------------------------------------------------ 5. converter options
needs_tools = pytest.mark.skipif(not shutil.which("ffmpeg"), reason="needs ffmpeg")
# the sample mod borrows a real FaceGen mesh from modpacks that aren't in the repository
needs_meshes = pytest.mark.skipif(not (Path(__file__).resolve().parents[1] / "private-test-data").exists()
                                  and not Path("private-test-data").exists(),
                                  reason="needs private-test-data (see tests/README.md)")


def _tc():
    return pytest.importorskip("test_convert")


def _convert(tmp_path, options):
    tc = _tc()
    from skynx.converter import analyze, convert
    pack = Pack.open(create_project(tmp_path / "pack", "AE", tc.BASE_INIS, "none"))
    mod = tc.make_pc_mod(tmp_path)
    an = analyze(pack, mod)
    try:
        res = convert(pack, an, options, tc.tools())
    finally:
        an.cleanup()
    return Pack.open(pack.root), res


def _entries(pack, name):
    arc = read_bsa(pack.data_dir / name)
    return {e.path: e for e in arc.entries}


@needs_tools
@needs_meshes
def test_packing_plugin(tmp_path):
    pack, res = _convert(tmp_path, {"sdk": False, "packing": "plugin", "preset": "koka"})
    assert set(res["bsas"]) == {"Ryns Test.bsa", "Ryns Test - Textures.bsa"}
    conv = next(iter(__import__("skynx.builder", fromlist=["x"]).load_mods(pack).values()))["converted"]
    assert conv["packing"] == "plugin" and conv["compress"] is True and conv["max_size"] is None
    nif = [e for p, e in _entries(pack, "Ryns Test.bsa").items() if p.endswith(".nif")]
    assert nif and all(e.compressed for e in nif)


@needs_tools
@needs_meshes
def test_default_is_the_switch_version(tmp_path):
    """No options: the diet sizes and one BSA listed in the ini (not loaded by
    the plugin's name), in the list that ends up shortest."""
    pack, res = _convert(tmp_path, {"sdk": False})
    assert res["bsas"] == ["RynsTest.bsa"]
    conv = next(iter(__import__("skynx.builder", fromlist=["x"]).load_mods(pack).values()))["converted"]
    assert conv["packing"] == "ini1" and conv["preset"] == "diet"
    stems = {Path(p).stem.lower() for p in pack.plugins}
    assert "rynstest" not in stems
    paths = set(_entries(pack, "RynsTest.bsa"))
    assert any(p.startswith("textures\\") for p in paths) and any(p.endswith(".nif") for p in paths)
    assert any(p.startswith("sound\\voice\\") for p in paths)
    where = [(i.path.name, k) for i in pack.inis for k in ("sResourceArchiveList", "sResourceArchiveList2")
             if "RynsTest.bsa" in i.archive_list(k)]
    assert where, "the BSA is in no ini list"
    keys = {k for _n, k in where}
    assert len(keys) == 1
    for p in pack.inis_for_key(keys.pop()):
        assert "RynsTest.bsa" in read_ini(p).archive_list(where[0][1]), p.name
    res_audit = run_audit(pack, deep=False)
    bad = [f for f in res_audit.findings if f.severity == "critico" or f.code in ("ini-bsa-double", "lang-ini-hides")]
    assert not bad, [(f.code, f.subject) for f in bad]


@needs_tools
def test_ini1_uses_the_list_with_room_and_falls_back(tmp_path):
    tc = _tc()
    from skynx.converter import analyze, convert
    pack = Pack.open(create_project(tmp_path / "pack", "AE", tc.BASE_INIS, "none"))

    def fill(name, key):
        cur = read_ini(name).archive_list(key)
        filler = [f"F{i:03d}.bsa" for i in range(200)]
        while len(", ".join(cur + filler)) > 990:
            filler.pop()
        filler.append("P" * (1016 - len(", ".join(cur + filler)) - 2 - 4) + ".bsa")
        assert len(", ".join(cur + filler)) == 1016
        set_list(pack, name.name, key, cur + filler)
    for p in pack.inis_for_key("sResourceArchiveList2"):
        fill(p, "sResourceArchiveList2")
    pack = Pack.open(pack.root)
    an = analyze(pack, tc.make_pc_mod(tmp_path))
    try:
        res = convert(pack, an, {"sdk": False}, tc.tools())
    finally:
        an.cleanup()
    pack = Pack.open(pack.root)
    assert res["bsas"] == ["RynsTest.bsa"]
    assert "RynsTest.bsa" in read_ini(pack.base_romfs / "Skyrim.ini").archive_list("sResourceArchiveList")
    # both lists full: one BSA named after the plugin, and a note says why
    for p in pack.inis_for_key("sResourceArchiveList"):
        fill(p, "sResourceArchiveList")
    pack = Pack.open(pack.root)
    (tmp_path / "two").mkdir()
    mod2 = tc.make_pc_mod(tmp_path / "two")
    an = analyze(pack, mod2)
    try:
        names = {"Ryn's Test.esp": "Other Test.esp", "Ryn's Test - Patch.esp": "Other Test - Patch.esp"}
        res = convert(pack, an, {"sdk": False, "names": names}, tc.tools())
    finally:
        an.cleanup()
    assert res["bsas"] == ["Other Test.bsa"]
    assert any("room" in n["en"] for n in res["notes"])


@needs_tools
def test_packing_single(tmp_path):
    tc = _tc()
    pack0 = Pack.open(create_project(tmp_path / "ref", "AE", tc.BASE_INIS, "none"))
    inis_before = {p.name: p.read_bytes() for p in pack0.ini_paths}
    pack, res = _convert(tmp_path, {"sdk": False, "packing": "single"})
    assert res["bsas"] == ["Ryns Test.bsa"]
    paths = set(_entries(pack, "Ryns Test.bsa"))
    assert any(p.startswith("textures\\") for p in paths) and any(p.startswith("sound\\voice\\") for p in paths)
    assert {p.name: p.read_bytes() for p in pack.ini_paths} == inis_before     # no ini change


@needs_tools
@needs_meshes
def test_packing_ini_uncompressed(tmp_path):
    pack, res = _convert(tmp_path, {"sdk": False, "packing": "ini", "compress": False})
    assert res["bsas"] == ["RynsTestM.bsa", "RynsTestT.bsa"]
    stems = {Path(p).stem.lower() for p in pack.plugins}
    assert not {Path(b).stem.lower() for b in res["bsas"]} & stems
    main, texv = _entries(pack, "RynsTestM.bsa"), _entries(pack, "RynsTestT.bsa")
    assert "seq\\ryns test.seq" in main and any(p.endswith(".nif") for p in main)
    assert all(p.startswith(("textures\\", "sound\\voice\\")) for p in texv)
    assert any(p.startswith("sound\\voice\\") for p in texv)
    assert not any(e.compressed for e in list(main.values()) + list(texv.values()))
    sky = read_ini(pack.base_romfs / "Skyrim.ini")
    assert "RynsTestM.bsa" in sky.archive_list("sResourceArchiveList")
    assert "RynsTestM.bsa" not in sky.archive_list(MEM)
    for p in pack.inis_for_key("sResourceArchiveList2"):
        assert "RynsTestT.bsa" in read_ini(p).archive_list("sResourceArchiveList2"), p.name
    assert any(i.path.name != "Skyrim.ini" for i in pack.inis)      # a language ini got it too
    res_audit = run_audit(pack, deep=False)
    bad = [f for f in res_audit.findings if f.severity == "critico" or f.code in ("ini-bsa-double", "lang-ini-hides")]
    assert not bad, [(f.code, f.subject) for f in bad]
    undo(pack.root, list_history(pack.root)[0]["id"])
    assert not (pack.data_dir / "RynsTestM.bsa").exists()
    assert "RynsTestM.bsa" not in read_ini(pack.base_romfs / "Skyrim.ini").archive_list("sResourceArchiveList")


@needs_tools
def test_packing_ini_respects_the_1024_limit(tmp_path):
    tc = _tc()
    from skynx.converter import ConvertError, analyze, convert
    pack = Pack.open(create_project(tmp_path / "pack", "AE", tc.BASE_INIS, "none"))
    sky = read_ini(pack.base_romfs / "Skyrim.ini").archive_list("sResourceArchiveList")
    filler = [f"Filler{i:03d}.bsa" for i in range(60)]
    while len(", ".join(sky + filler)) > 990:
        filler.pop()
    pad = 1012 - len(", ".join(sky + filler)) - 2 - 4
    filler.append("P" * pad + ".bsa")
    assert len(", ".join(sky + filler)) == 1012
    set_list(pack, "Skyrim.ini", "sResourceArchiveList", sky + filler)
    pack = Pack.open(pack.root)
    an = analyze(pack, tc.make_pc_mod(tmp_path))
    try:
        with pytest.raises(ConvertError) as e:
            convert(pack, an, {"sdk": False, "packing": "ini"}, tc.tools())
        assert "1024" in e.value.en and "1024" in e.value.es and "límite" in e.value.es
        with pytest.raises(ConvertError):
            convert(pack, an, {"packing": "zip"}, tc.tools())
        with pytest.raises(ConvertError):
            convert(pack, an, {"max_size": 3000}, tc.tools())
    finally:
        an.cleanup()
    assert not list_history(pack.root)


@needs_tools
def test_convert_max_size(tmp_path):
    from skynx.textures import inspect
    tc = _tc()
    from skynx.converter import analyze
    pack0 = Pack.open(create_project(tmp_path / "est", "AE", tc.BASE_INIS, "none"))
    (tmp_path / "a").mkdir()
    an = analyze(pack0, tc.make_pc_mod(tmp_path / "a"))
    try:
        e_none, e_512 = an.estimate("none", False), an.estimate("none", False, 512)
        assert e_512["after"] < e_none["after"] and e_512["max_size"] == 512
    finally:
        an.cleanup()
    pack, res = _convert(tmp_path, {"sdk": False, "preset": "none", "max_size": 512})
    info = {}
    for name in res["bsas"]:
        arc = read_bsa(pack.data_dir / name)
        with (pack.data_dir / name).open("rb") as f:
            info.update({e.name: inspect(arc.read_head(e, 256, f)) for e in arc.entries if e.name.endswith(".dds")})
    assert info["big.dds"].width == 512 and info["big_n.dds"].width == 512
    assert info["cloak.dds"].width == 512 and info["gem.dds"].width == 256
    assert (info["icon.dds"].width, info["icon.dds"].height) == (2048, 64)


def test_plugin_bsa_losing_to_an_ini_bsa(tmp_path):
    """Seen on the console: KokaNX's USSEP.bsa (ini) beat Growl.bsa (loaded by
    its plugin) and Growl showed its integrity message. The fix puts Growl.bsa
    in the ini after it, and the Doctor doesn't offer to take it out again."""
    pack = Pack.open(create_project(tmp_path / "pk", "AE", INIS, "none"))
    u = tmp_path / "us"
    u.mkdir()
    make_bsa(u / "USSEPX.bsa", {"scripts\\playerwerewolfchangescript.pex": b"U" * 40,
                                "scripts\\source\\other.psc": b"src"})
    add_mod(pack, u)
    g = _plugin_mod(tmp_path, "Growl.esp", [])
    make_bsa(g / "Growl.bsa", {"scripts\\playerwerewolfchangescript.pex": b"G" * 40,
                               "scripts\\growlonly.pex": b"g"})
    add_mod(pack, g)
    o = _plugin_mod(tmp_path, "Other.esp", [])
    make_bsa(o / "Other.bsa", {"scripts\\source\\other.psc": b"src2", "meshes\\o.nif": b"o"})
    add_mod(pack, o)                                   # only shares a script source: no finding
    pack = Pack.open(pack.root)
    [f] = codes(pack, "bsa-loses-to-ini", deep=False)
    assert f.params["list"] == "Growl.bsa" and "1 scripts" in f.items[0]
    assert f.fix["items"] == [["sResourceArchiveList", "Growl.bsa"]]
    assert "Growl.bsa" in " ".join(preview(pack, f.fix, "en")["changes"])
    apply(pack, f.fix)
    pack = Pack.open(pack.root)
    lst = pack.archive_lists()["sResourceArchiveList"]
    assert lst.index("Growl.bsa") > lst.index("USSEPX.bsa")
    assert not codes(pack, "bsa-loses-to-ini", deep=False)
    assert not [x for x in codes(pack, "ini-bsa-double", deep=False) if x.subject == "Growl.bsa"]


def test_plugin_bsa_losing_its_scripts_to_the_game(tmp_path):
    """Quick Start's MQ101 fragment lost to the game's own (Skyrim - Misc.bsa
    loads from the ini): with the game's BSAs known, the Doctor says so, and
    doesn't offer to take a BSA that is in the ini for that reason out of it."""
    vdir = tmp_path / "vanilla"
    make_bsa(vdir / "Skyrim - Misc.bsa", {"scripts\\qf_mq101_0003372b.pex": b"V" * 30,
                                         "textures\\v\\a.dds": b"DDS " + bytes(20)})
    # a Creation Club BSA loads by its plugin's name, not from the ini: USCCCP's
    # fixes to its scripts win over it, as on PC
    make_bsa(vdir / "ccQDRSSE001-SurvivalMode.bsa", {"scripts\\survival_x.pex": b"C" * 30})
    pack = Pack.open(create_project(tmp_path / "pk", "AE", INIS, "none"))
    u = _plugin_mod(tmp_path, "Patch CC.esp", [])
    make_bsa(u / "Patch CC.bsa", {"scripts\\survival_x.pex": b"U" * 30})
    add_mod(pack, u)
    q = _plugin_mod(tmp_path, "Quick.esp", [])
    make_bsa(q / "Quick.bsa", {"scripts\\qf_mq101_0003372b.pex": b"Q" * 30})
    add_mod(pack, q)
    t = _plugin_mod(tmp_path, "Tex.esp", [])
    make_bsa(t / "Tex.bsa", {"textures\\v\\a.dds": b"DDS " + bytes(30)})   # textures: not judged
    add_mod(pack, t)
    pack = Pack.open(pack.root)
    def find(code):
        return [f for f in run_audit(pack, deep=False, vanilla_dir=vdir, cache_dir=tmp_path / "c").findings
                if f.code == code]
    assert not [f for f in run_audit(pack, deep=False).findings if f.code == "bsa-loses-to-ini"]
    [f] = find("bsa-loses-to-ini")
    assert f.params["list"] == "Quick.bsa" and "Skyrim - Misc.bsa" in f.items[0]
    apply(pack, f.fix)
    pack = Pack.open(pack.root)
    assert not find("bsa-loses-to-ini")
    assert not [x for x in find("ini-bsa-double") if x.subject == "Quick.bsa"]   # on purpose


def test_shorten_long_bsa_names_in_a_full_ini(tmp_path):
    """sResourceArchiveList near 1024 characters: the BSAs listed there get
    short names (they load from the ini, so their name matters nowhere else)."""
    from skynx.builder import load_mods
    pack = Pack.open(create_project(tmp_path / "pk", "AE", INIS, "none"))
    longs = []
    for i in range(16):
        stem = f"Andromeda {i} - Unique Standing Stones of Skyrim Extra"
        m = _plugin_mod(tmp_path / f"m{i}", f"{stem}.esp", [])
        make_bsa(m / f"{stem}.bsa", {f"meshes\\\\a{i}.nif": b"x" * 10})
        add_mod(pack, m)
        longs.append(f"{stem}.bsa")
    pack = Pack.open(pack.root)
    sky = read_ini(pack.base_romfs / "Skyrim.ini")
    set_list(pack, "Skyrim.ini", "sResourceArchiveList", sky.archive_list("sResourceArchiveList") + longs)
    pack = Pack.open(pack.root)
    [f] = [x for x in run_audit(pack, deep=False).findings if x.code == "ini-long"]
    assert f.fix and f.fix["kind"] == "ini_shorten" and len(f.fix["renames"]) == 16
    news = [b for _a, b in f.fix["renames"]]
    assert len(set(n.lower() for n in news)) == 16 and all(len(n) <= 14 for n in news)
    assert "ini: " in preview(pack, f.fix, "en")["changes"][-1]
    apply(pack, f.fix)
    pack = Pack.open(pack.root)
    lst = pack.archive_lists()["sResourceArchiveList"]
    assert not any(b in lst for b in longs) and all(n in lst for n in news)
    assert all((pack.data_dir / n).exists() for n in news)
    assert not [x for x in run_audit(pack, deep=False).findings if x.code == "ini-long"]
    recs = [b for r in load_mods(pack).values() for b in r.get("bsas", [])]
    assert all(n in recs for n in news)
    undo(pack.root, list_history(pack.root)[0]["id"])
    assert all((Pack.open(pack.root).data_dir / b).exists() for b in longs)
