"""LOOT-style sorting (skynx.loot), offline against tests/fixtures/loot/masterlist.yaml
(loot/skyrimse, branch v0.29, commit 4a3a51a of 2026-10-19).

Run: python -m pytest tests/test_loot.py -q
"""
import struct
import sys
from collections import Counter
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from skynx import knowledge as K  # noqa: E402
from skynx import loot  # noqa: E402
from skynx.ccc import parse_ccc, render, reorder  # noqa: E402
from skynx.errors import SkynxError  # noqa: E402
from skynx.pack import Pack  # noqa: E402
from skynx.plugin import FLAG_LIGHT, FLAG_MASTER, PluginHeader, read_header  # noqa: E402

FIX = ROOT / "tests" / "fixtures" / "loot" / "masterlist.yaml"
MIRROR = ROOT / "work" / "mirror"
PACKS = ["Ashiro_s Light Modlist", "Avner ModPack Revised 2026", "ModPack Avner 2026",
         "Simonrim Modpack for Switch", "Vanilla+ Flowergirls (NSFW)"]
# Moves each real pack gets with the fixture masterlist (see test_move_counts).
# Avner Revised: the merged EnaiRim_NR.esp moves to its components' latest group
# instead of its two empty placeholders (Imperious, Ordinator) moving.
EXPECTED_MOVES = {"Ashiro_s Light Modlist": 0, "Avner ModPack Revised 2026": 3,
                  "ModPack Avner 2026": 9, "Simonrim Modpack for Switch": 3,
                  "Vanilla+ Flowergirls (NSFW)": 7}
USSEP = "unofficial skyrim special edition patch.esp"
needs_mirror = pytest.mark.skipif(not MIRROR.exists(), reason="no mirror")


@pytest.fixture(scope="module")
def ml():
    return loot.load_masterlist(FIX)


def _fixed(pack, e):
    low = e.lower()
    return (low in {m.lower() for m in K.VANILLA_MASTERS + K.SWITCH_MASTERS}
            or (pack.mode == "AE" and (low in {c.lower() for c in K.AE_CC_PLUGINS}
                                       or pack.is_cc(e))))


def _master_violations(pack, order):
    pos = {e.lower(): i for i, e in enumerate(order) if not e.startswith("#")}
    bad = []
    for e in order:
        h = pack.plugins.get(e.lower())
        if e.startswith("#") or not h:
            continue
        for m in h.masters:
            if m.lower() in pos and pos[m.lower()] > pos[e.lower()]:
                bad.append((e, m))
    return bad


def _resort(pack, ml, s, aliases=None):
    """Apply the suggestion the way the UI will (ccc.reorder) and suggest again."""
    lst = pack.ccc if pack.mode == "AE" else pack.plugin_list
    raw = reorder(lst.raw, s.order)
    new = parse_ccc(raw)
    assert new.entries == s.order
    if pack.mode == "AE":
        pack.ccc = new
    else:
        pack.plugin_list = new
    return loot.suggest(pack, ml, aliases)


def _hdr(name, masters=(), flags=0, records=1, author="", desc=""):
    return PluginHeader(path=Path(name), name=name, size=100, flags=flags,
                        masters=list(masters), num_records=records, author=author,
                        description=desc)


def _pack(tmp_path, entries, headers, mode="SE"):
    p = Pack(root=tmp_path)
    p.mode = mode
    lst = parse_ccc(render(entries, "CRLF" if mode == "AE" else "LF"))
    if mode == "AE":
        p.ccc = lst
    else:
        p.plugin_list = lst
    p.plugins = {h.name.lower(): h for h in headers}
    p.data_files = {h.name.lower(): h.path for h in headers}
    return p


def _mini(tmp_path, plugins_yaml):
    text = (
        "common:\n"
        "  - &lateGroup 'Late Loaders'\n"
        "  - &stones 'Standing Stone Effects'\n"
        "  - &patchMsg\n"
        "    type: say\n"
        "    content: 'Use the patch for {0}.'\n"
        "groups:\n"
        "  - name: 'Early'\n"
        "  - name: 'default'\n"
        "    after: [ 'Early' ]\n"
        "  - name: 'Standing Stone Effects'\n"
        "    after: [ 'default' ]\n"
        "  - name: 'Late Loaders'\n"
        "    after: [ 'Standing Stone Effects' ]\n"
        "plugins:\n" + plugins_yaml)
    path = tmp_path / "masterlist.yaml"
    path.write_text(text, encoding="utf-8")
    return loot.load_masterlist(path)


# -- masterlist --------------------------------------------------------------------
def test_fixture_masterlist(ml):
    assert len(ml.exact) > 2000 and len(ml.regex) > 300 and not ml.bad_regex
    assert ml.groups["default"] == ["Underrides"]
    assert "Unofficial Patches" in ml.group_ancestors("default")
    assert ml.lookup(USSEP).group == "Unofficial Patches"
    assert ml.lookup("SkyUI_SE.esp").group == "Fixes"
    # regex entry (`Bashed Patch.*\.esp`)
    assert ml.lookup("Bashed Patch, 0.esp").group == "Dynamic Patches"
    # Drive / tool damage: underscores for apostrophes or spaces
    assert ml.lookup("Alternate_Start_-_Live_Another_Life.esp").group == "Alternate Start"
    assert ml.lookup("Ryn_s Farms.esp").name == "Ryn_s Farms.esp"
    assert ml.lookup("Not A Real Mod 12345.esp") is None


def test_yaml_anchors_and_merge_keys(tmp_path):
    m = _mini(tmp_path, (
        "  - name: 'A.esp'\n"
        "    group: *lateGroup\n"
        "    msg:\n"
        "      - <<: *patchMsg\n"
        "        subs: [ 'B' ]\n"))
    meta = m.lookup("a.esp")
    assert meta.group == "Late Loaders"
    assert meta.msg[0].en == "Use the patch for B."


def test_conditions(tmp_path, ml):
    p = _pack(tmp_path, ["A.esp", "#B.esp"], [_hdr("A.esp"), _hdr("B.esp")])
    s = loot.suggest(p, ml)          # builds the context; use the evaluator directly
    units = [loot._Unit(0, 0, [0, 1], "A.esp", "A.esp")]
    c = loot._Cond(loot._Ctx(p, units, set()))
    assert c('active("A.esp")') is True
    assert c('active("B.esp")') is False                 # disabled
    assert c('file("B.esp")') is True                    # present in Data
    assert c('active("a\\.es[pm]")') is True             # regex
    assert c('not file("../SkyrimSE.exe")') is True      # no PC executables on Switch
    assert c('file("SKSE/Plugins/x.dll")') is False      # no SKSE on Switch
    assert c('active("A.esp") and version("A.esp", <, "1.2")') is None
    assert c('active("Z.esp") and checksum("Z.esp", FF60C24A)') is False
    assert c('(active("Z.esp") or active("A.esp")) and not many("A\\.esp")') is True
    assert c('garbage((') is None
    assert not s.changed


# -- real packs --------------------------------------------------------------------
@needs_mirror
@pytest.mark.parametrize("name", PACKS)
def test_real_pack_order_is_valid(name, ml):
    pack = Pack.open(MIRROR / name)
    old = list(pack.list_entries)
    s = loot.suggest(pack, ml)
    assert Counter(s.order) == Counter(old)
    assert not _master_violations(pack, s.order)
    for i, e in enumerate(old):
        if not e.startswith("#") and _fixed(pack, e):
            assert s.order[i] == e, f"fixed entry {e} moved"
        if e.startswith("#") and i:
            # a disabled line still follows the line it followed
            assert s.order[s.order.index(e) - 1] == old[i - 1]
    assert s.changed == (s.order != old)
    assert [m for m in s.moves if m.reason_key not in loot.REASONS] == []
    for m in s.moves:
        en, es = loot.describe(m)
        assert en and es and "{" not in en and "{" not in es
        assert s.order[m.new_index] == m.name and old[m.old_index] == m.name
    again = _resort(pack, ml, s)
    assert not again.changed and again.moves == [] and again.order == s.order


@needs_mirror
def test_move_counts(ml, capsys):
    got = {}
    for name in PACKS:
        s = loot.suggest(Pack.open(MIRROR / name), ml)
        got[name] = len(s.moves)
        kinds = Counter(m.reason_key for m in s.moves)
        with capsys.disabled():
            print(f"\n  loot: {name}: {len(s.moves)} moves {dict(kinds)}", end="")
    assert got == EXPECTED_MOVES


@needs_mirror
@pytest.mark.parametrize("name", PACKS[1:])
def test_real_pack_sanity(name, ml):
    pack = Pack.open(MIRROR / name)
    s = loot.suggest(pack, ml)
    pos = {e.lower(): i for i, e in enumerate(s.order)}
    movable = [e for e in s.order if e.lower() in pack.plugins and not _fixed(pack, e)]
    # USSEP (group 'Unofficial Patches', ESM flag) is the first mod
    assert movable[0].lower() == USSEP
    assert s.groups[movable[0]] == "Unofficial Patches"
    # patches after their targets
    for patch, targets in [("odin - ordinator compatibility patch.esp",
                            ["odin - skyrim magic overhaul.esp", "ordinator - perks of skyrim.esp"]),
                           ("ecco - imperious patch.esp", ["imperious - races of skyrim.esp"]),
                           ("mysticordinator.esp", ["ordinator - perks of skyrim.esp"])]:
        if patch in pos:
            assert all(pos[t] < pos[patch] for t in targets if t in pos)
    # LOOT groups: Skills & Perks (Ordinator) loads after Races & Classes (Imperious)
    if "imperious - races of skyrim.esp" in pos and "ordinator - perks of skyrim.esp" in pos:
        assert pos["imperious - races of skyrim.esp"] < pos["ordinator - perks of skyrim.esp"]
    # every master-flagged plugin before every regular one, among movable plugins
    flags = [pack.plugins[e.lower()].is_master_flag or e.lower().endswith((".esm", ".esl"))
             for e in movable]
    assert flags == sorted(flags, reverse=True)
    assert any("aren't in the LOOT masterlist" in w[0] for w in s.warnings)


@needs_mirror
def test_masterlist_notes_on_real_pack(ml):
    s = loot.suggest(Pack.open(MIRROR / "Vanilla+ Flowergirls (NSFW)"), ml)
    smilo = s.notes["Smilodon - Combat of Skyrim.esp"]
    assert any(n.level == "error" and "Smilodon or Wildcat" in n.en for n in smilo)
    for notes in s.notes.values():
        for n in notes:
            assert n.level in ("say", "warn", "error") and n.en and n.es
            assert "**" not in n.en and len(n.en) <= 300


@needs_mirror
def test_ashiro_missing_entries_stay(ml):
    # Ashiro's plugins are still inside .7z archives: every entry is missing.
    pack = Pack.open(MIRROR / "Ashiro_s Light Modlist")
    s = loot.suggest(pack, ml)
    assert s.order == pack.list_entries and not s.changed and not s.moves


# -- synthetic cases ------------------------------------------------------------------
def test_alias_keeps_masterlist_group(tmp_path):
    m = _mini(tmp_path, (
        "  - name: \"Ryn's Standing Stones.esp\"\n"
        "    group: *stones\n"))
    entries = ["Ryns Standing Stones.esp", "Other.esp"]
    p = _pack(tmp_path, entries, [_hdr(e) for e in entries])
    s = loot.suggest(p, m, aliases={"Ryns Standing Stones.esp": "Ryn's Standing Stones.esp"})
    assert s.groups["Ryns Standing Stones.esp"] == "Standing Stone Effects"
    assert s.order == ["Other.esp", "Ryns Standing Stones.esp"]
    (mv,) = s.moves
    assert mv.name == "Ryns Standing Stones.esp" and mv.reason_key == "group"
    assert loot.describe(mv)[0] == ("LOOT group 'Standing Stone Effects' loads after "
                                    "group 'default' (Other.esp)")
    # Drive damage (' -> _) and a dropped apostrophe are folded without an alias
    for name in ("Ryn_s Standing Stones.esp", "Ryns Standing Stones.esp"):
        p = _pack(tmp_path, [name, "Other.esp"], [_hdr(name), _hdr("Other.esp")])
        assert loot.suggest(p, m).groups[name] == "Standing Stone Effects"
    # a real rename needs the alias
    p = _pack(tmp_path, ["RSS.esp", "Other.esp"], [_hdr("RSS.esp"), _hdr("Other.esp")])
    assert loot.suggest(p, m).groups["RSS.esp"] == "default"
    s = loot.suggest(p, m, aliases={"rss.esp": "Ryn's Standing Stones.esp"})
    assert s.groups["RSS.esp"] == "Standing Stone Effects" and s.order[-1] == "RSS.esp"


def test_alias_in_conditions_with_real_masterlist(tmp_path, ml):
    # Ryn's Farms has a message that fires when Ryn's Standing Stones is active
    # and its patch isn't. Both names are damaged here.
    entries = ["Ryn_s Farms.esp", "Ryns Standing Stones.esp"]
    p = _pack(tmp_path, entries, [_hdr(e) for e in entries])
    assert "Ryn_s Farms.esp" not in loot.suggest(p, ml).notes
    s = loot.suggest(p, ml, aliases={"Ryns Standing Stones.esp": "Ryn's Standing Stones.esp"})
    (note,) = s.notes["Ryn_s Farms.esp"]
    assert "Ryn's Standing Stones" in note.en and "nexusmods.com" in note.en


def test_after_rule_cycle_is_ignored_and_reported(tmp_path):
    m = _mini(tmp_path, (
        "  - name: 'A.esp'\n"
        "    after: [ 'B.esp' ]\n"           # but B has A as master
        "  - name: 'C.esp'\n"
        "    group: 'Early'\n"
        "    after: [ 'D.esp' ]\n"           # D is in 'default', after 'Early'
        "  - name: 'E.esp'\n"
        "    after: [ 'F.esp' ]\n"))         # a normal rule
    entries = ["A.esp", "B.esp", "D.esp", "C.esp", "E.esp", "F.esp"]
    hdrs = [_hdr("A.esp"), _hdr("B.esp", ["A.esp"]), _hdr("C.esp"), _hdr("D.esp"),
            _hdr("E.esp"), _hdr("F.esp")]
    p = _pack(tmp_path, entries, hdrs)
    s = loot.suggest(p, m)
    assert s.order == ["C.esp", "A.esp", "B.esp", "D.esp", "F.esp", "E.esp"]
    ignored = [w for w in s.warnings if w[0].startswith("Ignored LOOT rule")]
    assert len(ignored) == 2
    assert "'A.esp after B.esp'" in ignored[0][0] and "master" in ignored[0][0]
    assert "'C.esp after D.esp'" in ignored[1][0] and "groups" in ignored[1][0]
    assert all(w[1].startswith("Se ignoró") for w in ignored)
    assert {mv.name: mv.reason_key for mv in s.moves} == {"C.esp": "group_before", "E.esp": "after"}
    assert not _resort(p, m, s).changed


def test_after_beats_groups_switch(tmp_path, monkeypatch):
    m = _mini(tmp_path, (
        "  - name: 'C.esp'\n"
        "    group: 'Early'\n"
        "    after: [ 'D.esp' ]\n"))
    entries = ["D.esp", "C.esp"]
    p = _pack(tmp_path, entries, [_hdr(e) for e in entries])
    assert loot.suggest(p, m).order == ["C.esp", "D.esp"]
    monkeypatch.setattr(loot, "AFTER_BEATS_GROUPS", True)     # real LOOT priority
    s = loot.suggest(p, m)
    assert s.order == ["D.esp", "C.esp"] and not s.changed
    assert any("can't load after" in w[0] or "group order skipped" in w[0] for w in s.warnings)


def test_masters_flags_and_passengers(tmp_path, ml):
    entries = ["Patch.esp", "#Old.esp", "Missing.esp", "Base.esp", "Big.esm", "Light.esp"]
    hdrs = [_hdr("Patch.esp", ["Skyrim.esm", "Base.esp"]), _hdr("Base.esp", ["Skyrim.esm"]),
            _hdr("Big.esm", flags=FLAG_MASTER), _hdr("Light.esp", flags=FLAG_LIGHT),
            _hdr("Old.esp")]
    p = _pack(tmp_path, entries, hdrs)
    s = loot.suggest(p, ml)
    # Big.esm first (master), Base before its dependant; the disabled and the
    # missing line travel with Patch.esp; the ESL-flagged .esp is a regular plugin.
    assert s.order == ["Big.esm", "Base.esp", "Patch.esp", "#Old.esp", "Missing.esp", "Light.esp"]
    assert len(s.moves) == 2 and all(mv.reason_key in loot.REASONS for mv in s.moves)
    assert not _resort(p, ml, s).changed
    # the simplest case reads well in both languages
    p = _pack(tmp_path, ["Patch.esp", "Base.esp"], hdrs[:2])
    (mv,) = loot.suggest(p, ml).moves
    assert (mv.name, mv.old_index, mv.new_index) == ("Patch.esp", 0, 1)
    assert loot.describe(mv) == ("after its master Base.esp", "después de su master Base.esp")
    assert not _resort(p, ml, s).changed


def test_non_master_needed_by_a_master_goes_with_masters(tmp_path, ml):
    entries = ["X.esp", "Lib.esp", "Big.esm"]
    hdrs = [_hdr("X.esp"), _hdr("Lib.esp"), _hdr("Big.esm", ["Lib.esp"], FLAG_MASTER)]
    s = loot.suggest(_pack(tmp_path, entries, hdrs), ml)
    assert s.order == ["Lib.esp", "Big.esm", "X.esp"]


def test_ae_fixed_cc_block_and_master_below(tmp_path, ml):
    cc = ["ccBGSSSE001-Fish.esm", "ccQDRSSE001-SurvivalMode.esl"]
    entries = [cc[0], "Mod.esp", "NeedsSurvival.esp", cc[1], "Late.esp"]
    hdrs = [_hdr("Mod.esp"), _hdr("Late.esp"),
            _hdr("NeedsSurvival.esp", ["Skyrim.esm", cc[1]])]
    p = _pack(tmp_path, entries, hdrs, mode="AE")
    s = loot.suggest(p, ml)
    assert s.order[0] == cc[0] and s.order[3] == cc[1]       # fixed lines keep their index
    assert s.order.index("NeedsSurvival.esp") > 3             # moved below its CC master
    assert not _master_violations(p, s.order)
    assert not _resort(p, ml, s).changed


def test_fixed_master_further_down_is_reported(tmp_path, ml):
    cc = "ccQDRSSE001-SurvivalMode.esl"
    entries = ["A.esp", "B.esp", cc]
    hdrs = [_hdr("A.esp", [cc]), _hdr("B.esp", [cc])]
    s = loot.suggest(_pack(tmp_path, entries, hdrs, mode="AE"), ml)
    assert s.order[2] == cc
    assert sum("fixed entry further down" in w[0] for w in s.warnings) == 2


def test_req_and_inc_notes(tmp_path):
    m = _mini(tmp_path, (
        "  - name: 'A.esp'\n"
        "    req:\n"
        "      - name: 'Lib.esp'\n"
        "        display: '[Lib Mod](https://example.org/lib)'\n"
        "      - 'SKSE/Plugins/thing.dll'\n"
        "    inc: [ 'B.esp', 'Gone.esp' ]\n"
        "    msg:\n"
        "      - type: warn\n"
        "        content:\n"
        "          - lang: en\n"
        "            text: 'English **text**.'\n"
        "          - lang: es\n"
        "            text: 'Texto en español.'\n"
        "      - type: say\n"
        "        content: 'Only with C.'\n"
        "        condition: 'active(\"C.esp\")'\n"))
    entries = ["A.esp", "B.esp"]
    p = _pack(tmp_path, entries, [_hdr(e) for e in entries])
    notes = loot.suggest(p, m).notes["A.esp"]
    assert notes[0] == loot.Note("warn", "English text.", "Texto en español.")
    texts = [n.en for n in notes[1:]]
    assert texts == ["Requires Lib Mod (https://example.org/lib), which the pack doesn't load.",
                     "Requires SKSE/Plugins/thing.dll, which the pack doesn't load.",
                     "Incompatible with B.esp."]


def test_deterministic(tmp_path, ml):
    entries = [f"M{i:02}.esp" for i in range(20)]
    hdrs = [_hdr(e, [entries[(i * 7) % 20]] if i % 3 == 0 and (i * 7) % 20 != i else [])
            for i, e in enumerate(entries)]
    p = _pack(tmp_path, entries, hdrs)
    a, b = loot.suggest(p, ml), loot.suggest(p, ml)
    assert a == b


# -- download -------------------------------------------------------------------------
class _Resp:
    def __init__(self, data):
        self.data = data

    def read(self):
        return self.data

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False


def test_fetch_masterlist(tmp_path, monkeypatch):
    seen = {}

    def ok(req, timeout):
        seen["ua"], seen["timeout"] = req.get_header("User-agent"), timeout
        return _Resp(FIX.read_bytes())

    def fail(req, timeout):
        raise OSError("offline")

    monkeypatch.setattr(loot.urllib.request, "urlopen", fail)
    with pytest.raises(SkynxError) as e:
        loot.fetch_masterlist(tmp_path / "c")
    assert e.value.es.startswith("No se pudo")

    monkeypatch.setattr(loot.urllib.request, "urlopen", ok)
    path = loot.fetch_masterlist(tmp_path / "c")
    assert path.read_bytes() == FIX.read_bytes()
    assert seen == {"ua": "SwitchNX Studio", "timeout": 30}

    monkeypatch.setattr(loot.urllib.request, "urlopen", fail)
    assert loot.fetch_masterlist(tmp_path / "c") == path     # old copy kept
    monkeypatch.setattr(loot.urllib.request, "urlopen", lambda r, timeout: _Resp(b"<html>"))
    assert loot.fetch_masterlist(tmp_path / "c").read_bytes() == FIX.read_bytes()
    assert not list((tmp_path / "c").glob("*.part"))


def test_load_masterlist_errors(tmp_path):
    bad = tmp_path / "bad.yaml"
    bad.write_text("plugins: [unclosed", encoding="utf-8")
    with pytest.raises(SkynxError):
        loot.load_masterlist(bad)
    with pytest.raises(SkynxError):
        loot.load_masterlist(tmp_path / "nope.yaml")


# -- merged plugins, placeholders, unknown plugins, user choices ----------------------
def _sub(t: bytes, b: bytes) -> bytes:
    return t + struct.pack("<H", len(b)) + b


def _plugin_file(path, masters=("Skyrim.esm",), records=(), author="", desc="", flags=0):
    """A real plugin file: TES4 (HEDR, CNAM, SNAM, MAST) then one top-level GRUP
    per (type, count, new) in `records`. New records use the plugin's own index."""
    n = sum(c for _t, c, _n in records)
    data = _sub(b"HEDR", struct.pack("<fiI", 1.7, n, 0x800))
    if author:
        data += _sub(b"CNAM", author.encode("cp1252") + b"\0")
    if desc:
        data += _sub(b"SNAM", desc.encode("cp1252") + b"\0")
    for m in masters:
        data += _sub(b"MAST", m.encode("cp1252") + b"\0") + _sub(b"DATA", b"\0" * 8)
    out = b"TES4" + struct.pack("<IIIHHHH", len(data), flags, 0, 0, 0, 44, 0) + data
    fid = 0x800
    for typ, count, new in records:
        recs = b""
        for _ in range(count):
            fid += 1
            body = _sub(b"EDID", b"x\0")
            index = len(masters) if new else 0
            recs += typ.encode() + struct.pack("<IIIHHHH", len(body), 0, (index << 24) | fid,
                                               0, 0, 44, 0) + body
        out += (b"GRUP" + struct.pack("<I", 24 + len(recs)) + typ.encode()
                + struct.pack("<iHHHH", 0, 0, 0, 0, 0) + recs)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(out)
    return read_header(path)


MERGE_ML = (
    "  - name: 'A.esp'\n"
    "    group: *lateGroup\n"
    "    after: [ 'Q.esp' ]\n"
    "    inc: [ 'B.esp' ]\n"
    "    msg:\n"
    "      - type: warn\n"
    "        content: 'Read the A docs.'\n"
    "  - name: 'E.esp'\n"
    "    group: 'Early'\n"
    "  - name: 'C.esp'\n"
    "    after: [ 'Q.esp' ]\n"
    "  - name: 'P.esp'\n"
    "    after: [ 'C.esp' ]\n"
    "    msg:\n"
    "      - type: say\n"
    "        content: 'C is loaded.'\n"
    "        condition: 'active(\"C.esp\")'\n"
    "  - name: 'Z.esp'\n"
    "    group: *stones\n")


def _merge_hdr(name, comps, records=100):
    desc = "Merged Plugin: \r\n" + "".join(f"  {c}\r\n" for c in comps).rstrip("\r\n")
    return _hdr(name, records=records, author="Merge Plugins v2.3.1.0", desc=desc)


def test_merged_components_parsing(tmp_path):
    mc = loot.merged_components
    crlf = "Merged Plugin: \r\n  Thunderchild - Epic Shout Package.esp\r\n  Wintersun - Faiths of Skyrim.esp"
    assert mc(_hdr("M.esp", author="Merge Plugins v2.3.1.0", desc=crlf)) == [
        "Thunderchild - Epic Shout Package.esp", "Wintersun - Faiths of Skyrim.esp"]
    assert mc(_hdr("M.esp", desc="Merged Plugin:\n  A.esp\n  B.esm\n  C.esl\n")) == ["A.esp", "B.esm", "C.esl"]
    assert mc(_hdr("M.esp", desc="merged plugins: A.esp, B.esp; C.esp")) == ["A.esp", "B.esp", "C.esp"]
    # free text after the list ends it; the merge itself and repeats are dropped
    assert mc(_hdr("M.esp", desc="Merged Plugin:\r\n  A.esp\r\n  M.esp\r\n  a.esp\r\n\r\nMade by me.")) == ["A.esp"]
    # a name with commas stays whole
    assert mc(_hdr("M.esp", desc="Merged Plugin:\n  Weapons, Armor & Fixes.esp\n  B.esp")) == [
        "Weapons, Armor & Fixes.esp", "B.esp"]
    # no marker: a merge tool as author and a bare list
    assert mc(_hdr("M.esp", author="zMerge", desc="A.esp\nB.esp")) == ["A.esp", "B.esp"]
    assert mc(_hdr("M.esp", author="zMerge", desc="Needs A.esp to work.\nB.esp")) == []
    assert mc(_hdr("M.esp", author="Merge Plugins v2.3.1.0", desc="New Vominheim SE v2.30")) == []
    assert mc(_hdr("M.esp", author="Someone", desc="Requires A.esp and B.esp")) == []
    # from a file and from bytes (cp1252)
    h = _plugin_file(tmp_path / "Merged.esp", author="Merge Plugins v2.3.1.0",
                     desc="Merged Plugin: \r\n  Café.esp\r\n  Other.esp")
    assert mc(h.path) == ["Café.esp", "Other.esp"] == mc(h.path.read_bytes())
    assert mc(tmp_path / "missing.esp") == [] and mc(b"not a plugin") == []


@needs_mirror
def test_real_merge_header():
    p = MIRROR / ("Avner ModPack Revised 2026/Avner ModPack Revised 2026/01000A10041EA000/"
                  "romfs/Data/EnaiRim_NR.esp")
    comps = loot.merged_components(p)
    assert len(comps) == 11 and comps[0] == "Thunderchild - Epic Shout Package.esp"
    assert "Ordinator - Perks of Skyrim.esp" in comps and "Imperious - Races of Skyrim.esp" in comps


def test_merge_group_is_latest_component_group(tmp_path):
    m = _mini(tmp_path, MERGE_ML)
    entries = ["M.esp", "Other.esp", "Q.esp"]
    hdrs = [_merge_hdr("M.esp", ["E.esp", "A.esp", "Unknown.esp"]), _hdr("Other.esp"), _hdr("Q.esp")]
    s = loot.suggest(_pack(tmp_path, entries, hdrs), m)
    assert s.merges == {"M.esp": ["E.esp", "A.esp", "Unknown.esp"]}
    assert s.groups["M.esp"] == "Late Loaders"
    assert s.order == ["Other.esp", "Q.esp", "M.esp"]
    (mv,) = s.moves
    assert mv.reason_key == "merge_group"
    assert loot.describe(mv) == (
        "LOOT group 'Late Loaders' (from A.esp, inside M.esp) loads after group 'default' (Q.esp)",
        "el grupo de LOOT 'Late Loaders' (de A.esp, dentro de M.esp) carga después del grupo "
        "'default' (Q.esp)")
    assert [u["name"] for u in s.unknown] == ["Other.esp", "Q.esp"]
    assert not any("M.esp" in w[0] for w in s.warnings if "aren't in" in w[0])


def test_merge_in_branching_groups_loads_after_every_component_group(tmp_path):
    path = tmp_path / "branches.yaml"
    path.write_text(
        "groups:\n"
        "  - name: 'default'\n"
        "  - name: 'X'\n    after: [ 'default' ]\n"
        "  - name: 'Y'\n    after: [ 'default' ]\n"
        "plugins:\n"
        "  - name: 'InX.esp'\n    group: 'X'\n"
        "  - name: 'InY.esp'\n    group: 'Y'\n"
        "  - name: 'OtherX.esp'\n    group: 'X'\n", encoding="utf-8")
    m = loot.load_masterlist(path)
    assert loot.all_groups(m) == ["default", "X", "Y"]
    entries = ["M.esp", "OtherX.esp"]
    hdrs = [_merge_hdr("M.esp", ["InX.esp", "InY.esp"]), _hdr("OtherX.esp")]
    s = loot.suggest(_pack(tmp_path, entries, hdrs), m)
    # Y is the latest group, and M still loads after X (InX's group)
    assert s.groups["M.esp"] == "Y" and s.order == ["OtherX.esp", "M.esp"]


def test_rules_about_a_component_apply_to_the_merge(tmp_path):
    m = _mini(tmp_path, MERGE_ML)
    n = _merge_hdr("N.esp", ["C.esp"])
    # P.esp: LOOT says 'after C.esp'; C is inside N
    s = loot.suggest(_pack(tmp_path, ["P.esp", "N.esp"], [_hdr("P.esp"), n]), m)
    assert s.order == ["N.esp", "P.esp"]
    (mv,) = s.moves
    assert {mv.reason_key} <= {"after_in", "after_in_of"}
    assert "inside" in loot.describe(mv)[0] and "dentro de" in loot.describe(mv)[1]
    # the condition active("C.esp") is true: C's content is loaded through N
    assert s.notes["P.esp"] == [loot.Note("say", "C is loaded.", "C is loaded.")]
    # C.esp's own rule 'after Q.esp' now belongs to N
    s = loot.suggest(_pack(tmp_path, ["N.esp", "Q.esp"], [n, _hdr("Q.esp")]), m)
    assert s.order == ["Q.esp", "N.esp"]
    (mv,) = s.moves
    assert mv.reason_key in ("merge_after", "merge_after_of")
    assert "rule of C.esp" in loot.describe(mv)[0] and "regla de C.esp" in loot.describe(mv)[1]
    # a patch whose master was merged loads after the merge, not only after the placeholder
    entries = ["Patch.esp", "C.esp", "N.esp"]
    hdrs = [_hdr("Patch.esp", ["Skyrim.esm", "C.esp"]), _hdr("C.esp", records=0), n]
    s = loot.suggest(_pack(tmp_path, entries, hdrs), m)
    assert s.order == ["C.esp", "N.esp", "Patch.esp"]
    assert s.dummies == {"C.esp": "N.esp"}
    (mv,) = [x for x in s.moves if x.name == "Patch.esp"]
    assert loot.describe(mv) == ("after its master C.esp, which is inside N.esp",
                                 "después de su master C.esp, que está dentro de N.esp")
    p = _pack(tmp_path, entries, hdrs)
    assert not _resort(p, m, s).changed


def test_placeholder_gets_no_notes(tmp_path):
    m = _mini(tmp_path, MERGE_ML)
    entries = ["A.esp", "M.esp", "B.esp", "Z.esp"]
    hdrs = [_hdr("A.esp", records=0), _merge_hdr("M.esp", ["A.esp"]), _hdr("B.esp"),
            _hdr("Z.esp", records=0)]
    s = loot.suggest(_pack(tmp_path, entries, hdrs), m)
    assert s.dummies == {"A.esp": "M.esp", "Z.esp": ""}
    assert "A.esp" not in s.notes and "Z.esp" not in s.notes
    assert s.groups["A.esp"] == "default" and s.groups["Z.esp"] == "default"
    assert s.notes["M.esp"] == [
        loot.Note("warn", "A.esp (inside M.esp): Read the A docs.",
                  "A.esp (dentro de M.esp): Read the A docs."),
        loot.Note("error", "A.esp (inside M.esp): Incompatible with B.esp.",
                  "A.esp (dentro de M.esp): Incompatible con B.esp.")]
    assert [u["name"] for u in s.unknown] == ["B.esp"]
    assert s.duplicates == []
    (nf,) = [w for w in s.warnings if "aren't in" in w[0]]
    assert nf[0].endswith(": B.esp")


def test_duplicate_detection(tmp_path):
    m = _mini(tmp_path, MERGE_ML)
    entries = ["A.esp", "M.esp"]
    s = loot.suggest(_pack(tmp_path, entries, [_hdr("A.esp", records=5),
                                               _merge_hdr("M.esp", ["A.esp", "C.esp"])]), m)
    assert s.duplicates == [("A.esp", "M.esp")] and s.dummies == {}
    assert any("twice" in w[0] and "dos veces" in w[1] for w in s.warnings)
    assert "A.esp" in s.notes                      # the real plugin keeps its own notes


def test_unknown_plugins_and_guesses(tmp_path, ml):
    d = tmp_path / "Data"
    V = ("Skyrim.esm", "Update.esm")
    hdrs = [
        _plugin_file(d / "Lands.esp", V, [("WRLD", 1, True), ("CELL", 40, True), ("NPC_", 10, True)]),
        _plugin_file(d / "Swords.esp", V + ("Lands.esp",), [("WEAP", 30, True)]),
        _plugin_file(d / "Bridge.esp", V + ("Lands.esp", "Swords.esp"), [("WEAP", 3, False)]),
        _plugin_file(d / "MyRaces.esp", V, [("RACE", 10, False), ("HDPT", 5, True)]),
        _plugin_file(d / "MyPerks.esp", V, [("PERK", 30, False), ("SPEL", 10, True)]),
        _plugin_file(d / "Clutter.esp", V, [("CELL", 20, False), ("REFR", 200, True)]),
        _plugin_file(d / "Tweaks.esp", V, [("GMST", 4, False)]),
        _plugin_file(d / "Changes.esp", V, [("NPC_", 40, False), ("ARMO", 5, True)]),
        _plugin_file(d / "Textures.esp", V, []),
        _plugin_file(d / "Lib.esm", V, [("QUST", 20, True), ("GLOB", 10, True)], flags=FLAG_MASTER),
        _plugin_file(d / "UsesLib.esp", V + ("Lib.esm",), [("QUST", 2, True)]),
        _plugin_file(d / "SkyUI_SE.esp", V, [("QUST", 1, True)]),           # LOOT knows it
    ]
    p = _pack(tmp_path, [h.name for h in hdrs], hdrs)
    p.bsas = {"textures.bsa": d / "Textures.bsa"}
    s = loot.suggest(p, ml)
    got = {u["name"]: u for u in s.unknown}
    assert "SkyUI_SE.esp" not in got
    assert {n: u["guess"] for n, u in got.items()} == {
        "Lands.esp": "New Content", "Swords.esp": "default", "Bridge.esp": "default",
        "MyRaces.esp": "Races & Classes", "MyPerks.esp": "Skills & Perks", "Clutter.esp": "default",
        "Tweaks.esp": "default", "Changes.esp": "default", "Textures.esp": "default",
        "Lib.esm": "Resources & Frameworks", "UsesLib.esp": "default"}
    assert got["Bridge.esp"]["masters"] == ["Skyrim.esm", "Update.esm", "Lands.esp", "Swords.esp"]
    assert "Lands.esp and Swords.esp" in got["Bridge.esp"]["why"][0]
    assert "Uses Lands.esp as a master" in got["Swords.esp"]["why"][0]
    assert "Textures.bsa" in got["Textures.esp"]["why"][0]
    assert "existing places" in got["Clutter.esp"]["why"][0]
    assert "Small plugin (4 records)" in got["Tweaks.esp"]["why"][0]
    for u in s.unknown:
        en, es = u["why"]
        assert en and es and "{" not in en + es and "—" not in en + es
        assert u["guess"] in ml.groups
    # the function works on its own too, also without a pack
    assert loot.guess_group(d / "Lands.esp")[0] == "New Content"
    assert loot.guess_group(tmp_path / "nope.esp")[0] == "default"


def test_userlist_overrides_group_and_after(tmp_path):
    m = _mini(tmp_path, (
        "  - name: 'C.esp'\n"
        "    group: 'Early'\n"
        "    after: [ 'D.esp' ]\n"))
    entries = ["X.esp", "Other.esp", "C.esp", "D.esp"]
    p = _pack(tmp_path, entries, [_hdr(e) for e in entries])
    base = loot.suggest(p, m)
    assert base.order == ["C.esp", "X.esp", "Other.esp", "D.esp"]   # LOOT's after rule loses to groups
    assert "X.esp" in [u["name"] for u in base.unknown]
    ul = loot.userlist_set({}, "X.esp", group="Late Loaders", note="Keep me last.")
    ul = loot.userlist_set(ul, "C.esp", after=["D.esp"])
    s = loot.suggest(p, m, userlist=ul)
    assert s.groups["X.esp"] == "Late Loaders" and s.groups["C.esp"] == "Early"
    # the user's rule wins over groups: C (Early) after D (default), Other still after C
    assert s.order == ["D.esp", "C.esp", "Other.esp", "X.esp"]
    assert "X.esp" not in [u["name"] for u in s.unknown]
    assert loot.Note("say", "Keep me last.", "Keep me last.") in s.notes["X.esp"]
    why = {mv.name: loot.describe(mv) for mv in s.moves}
    assert why["X.esp"][0].startswith("your choice: group 'Late Loaders'")
    assert why["X.esp"][1].startswith("tu elección: grupo 'Late Loaders'")
    p1 = _pack(tmp_path, ["C.esp", "D.esp"], [_hdr("C.esp"), _hdr("D.esp")])
    s1 = loot.suggest(p1, m, userlist=loot.userlist_set({}, "C.esp", after=["D.esp"]))
    assert s1.order == ["D.esp", "C.esp"]
    assert [loot.describe(mv) for mv in s1.moves] == [("your choice: after D.esp",
                                                       "tu elección: después de D.esp")]
    assert any("group order skipped" in w[0] for w in s.warnings)
    lst = parse_ccc(reorder(p.plugin_list.raw, s.order))
    p.plugin_list = lst
    assert not loot.suggest(p, m, userlist=ul).changed
    # renamed plugin: the userlist entry under its original name still applies
    p2 = _pack(tmp_path, ["RSS.esp", "Other.esp"], [_hdr("RSS.esp"), _hdr("Other.esp")])
    ul2 = loot.userlist_set({}, "Ryn's Standing Stones.esp", group="Late Loaders")
    s2 = loot.suggest(p2, m, aliases={"RSS.esp": "Ryn's Standing Stones.esp"}, userlist=ul2)
    assert s2.groups["RSS.esp"] == "Late Loaders" and s2.order == ["Other.esp", "RSS.esp"]
    # bad choices are reported, not fatal
    s3 = loot.suggest(p, m, userlist=loot.userlist_set({}, "X.esp", group="Nope", after=["Gone.esp"]))
    assert any("your group 'Nope'" in w[0] for w in s3.warnings)
    assert any("Gone.esp isn't in the load order" in w[0] for w in s3.warnings)
    # a user rule can't beat masters
    p4 = _pack(tmp_path, ["A.esp", "B.esp"], [_hdr("A.esp"), _hdr("B.esp", ["A.esp"])])
    s4 = loot.suggest(p4, m, userlist=loot.userlist_set({}, "A.esp", after=["B.esp"]))
    assert s4.order == ["A.esp", "B.esp"]
    assert any(w[0].startswith("Ignored your rule 'A.esp after B.esp'") for w in s4.warnings)


def test_userlist_persistence(tmp_path):
    path = tmp_path / "cfg" / "userlist.json"
    assert loot.load_userlist(path) == {"version": 1, "plugins": {}}
    data = loot.userlist_set({}, "My Mod.esp", group="New Content", after=["A.esp", "a.esp"])
    data = loot.userlist_set(data, "Other.esp", note="Checked by hand.")
    written = loot.save_userlist(path, data)
    assert written == loot.load_userlist(path) == {"version": 1, "plugins": {
        "my mod.esp": {"name": "My Mod.esp", "group": "New Content", "after": ["A.esp"], "note": ""},
        "other.esp": {"name": "Other.esp", "group": "", "after": [], "note": "Checked by hand."}}}
    assert not list(path.parent.glob("*.part"))
    # clearing everything removes the entry
    data = loot.userlist_set(written, "other.esp", note="")
    assert list(data["plugins"]) == ["my mod.esp"]
    path.write_text("{broken", encoding="utf-8")
    with pytest.raises(SkynxError) as e:
        loot.load_userlist(path)
    assert e.value.es.startswith("No se pueden leer")


def test_friendly_and_all_groups(ml):
    order = loot.all_groups(ml)
    assert sorted(order) == sorted(ml.groups) and len(order) == len(set(order))
    pos = {g: i for i, g in enumerate(order)}
    for g, after in ml.groups.items():
        assert all(pos[a] < pos[g] for a in after if a in pos)
    assert order[0] == "Main Plugins" and order.index("default") < order.index("Races & Classes")
    names = [f["group"] for f in loot.FRIENDLY_GROUPS]
    assert len(names) == 8 and "default" in names and all(g in ml.groups for g in names)
    for f in loot.FRIENDLY_GROUPS:
        assert all(f[k] for k in ("en", "es", "en_help", "es_help"))
        assert "—" not in f["es"] + f["es_help"]


@needs_mirror
def test_real_merged_pack(ml):
    pack = Pack.open(MIRROR / "Avner ModPack Revised 2026")
    s = loot.suggest(pack, ml)
    assert list(s.merges) == ["EnaiRim_NR.esp"] and len(s.merges["EnaiRim_NR.esp"]) == 11
    assert s.dummies == {"Imperious - Races of Skyrim.esp": "EnaiRim_NR.esp",
                         "Ordinator - Perks of Skyrim.esp": "EnaiRim_NR.esp"}
    assert s.duplicates == []
    assert s.groups["EnaiRim_NR.esp"] == "Vampire Gameplay Overhauls"
    for d in s.dummies:
        assert d not in s.notes and s.groups[d] == "default"
    pos = {e: i for i, e in enumerate(s.order)}
    for patch in ("ECCO - Imperious Patch.esp", "MysticOrdinator.esp"):
        assert pos["EnaiRim_NR.esp"] < pos[patch]
    assert any(n.en.startswith("Ordinator - Perks of Skyrim.esp (inside EnaiRim_NR.esp): ")
               for n in s.notes["EnaiRim_NR.esp"])
    unknown = {u["name"]: u["guess"] for u in s.unknown}
    assert unknown["ECCO - Imperious Patch.esp"] == "default"
    assert "EnaiRim_NR.esp" not in unknown and "Ordinator - Perks of Skyrim.esp" not in unknown
