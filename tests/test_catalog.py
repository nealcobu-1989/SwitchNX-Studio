"""The Catalog: all mods of all packs in the Library, and building a new pack
from a selection. Synthetic packs; the real ones (work/mirror) only for a
read-only grouping check."""
import hashlib
import shutil
import sys
import time
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tests"))
from skynx import catalog as CAT  # noqa: E402
from skynx import library as L  # noqa: E402
from skynx.audit import run_audit  # noqa: E402
from skynx.builder import create_project, load_mods  # noqa: E402
from skynx.history import list_history  # noqa: E402
from skynx.ini import read_ini, set_archive_list  # noqa: E402
from skynx.pack import Pack  # noqa: E402
from test_library import EMPTY_BSA, fake_plugin  # noqa: E402
from test_requirements import make_bsa, plugin, rec, sub, zs  # noqa: E402

INIS = ROOT / "tests" / "fixtures" / "console-inis"
USSEP_DIR = ROOT / "tests" / "fixtures" / "ussep"
MASTERLIST = ROOT / "tests" / "fixtures" / "loot" / "masterlist.yaml"
MIRROR = ROOT / "work" / "mirror"
DATA = "01000A10041EA000/romfs/Data"
CCC = "01000A10041EB009/romfs/Skyrim_aoc.ccc"
ORD = "Ordinator - Perks of Skyrim.esp"


# ---------------------------------------------------------------- builders
def recs(typ: str, n: int, start: int = 0x01000800) -> list[bytes]:
    return [rec(typ, start + i, [sub("EDID", zs(f"{typ}{i}"))]) for i in range(n)]


def new_pack(lib: Path, name: str, cc: str = "all", edition: str = "AE") -> Path:
    return create_project(lib / "Packs" / name, edition, INIS, cc)


def add_list(root: Path, *names: str) -> None:
    ccc = root / CCC
    raw = ccc.read_bytes()
    if raw and not raw.endswith(b"\n"):
        raw += b"\r\n"
    ccc.write_bytes(raw + b"".join(n.encode() + b"\r\n" for n in names))


def add_ini(root: Path, key: str, *bsas: str, ini: str = "Skyrim.ini") -> None:
    p = root / "01000A10041EA000/romfs" / ini
    raw = p.read_bytes()
    cur = read_ini(p).archive_list(key)
    p.write_bytes(set_archive_list(raw, key, cur + list(bsas)))


def snapshot(root: Path) -> dict:
    out = {}
    for p in sorted(Path(root).rglob("*")):
        if p.is_file():
            out[str(p.relative_to(root))] = hashlib.sha1(p.read_bytes()).hexdigest()
    return out


@pytest.fixture
def lib(tmp_path):
    lib = tmp_path / "Library"
    L.ensure(lib)
    # --- Alpha
    a = new_pack(lib, "Alpha")
    d = a / DATA
    plugin(d / ORD, recs("PERK", 30) + recs("SPEL", 4, 0x01000900))
    make_bsa(d / "Ordinator - Perks of Skyrim.bsa", {"textures\\shared\\a.dds": b"x" * 64,
                                                       "textures\\ord\\b.dds": b"y" * 64})
    plugin(d / "Lands Mod.esp", recs("WRLD", 1) + recs("STAT", 3, 0x01000a00))
    fake_plugin(d / "Patch AB.esp", ["Skyrim.esm", ORD, "Lands Mod.esp"])
    plugin(d / "MergedStuff.esp", recs("ARMO", 6), snam="Merged Plugin:\r\nArmor Pack.esp\r\nQuest Mod.esp")
    add_list(a, ORD, "Lands Mod.esp", "Patch AB.esp", "MergedStuff.esp")
    # --- Beta
    b = new_pack(lib, "Beta")
    d = b / DATA
    shutil.copy2(a / DATA / ORD, d / ORD)                         # the same mod, same bytes
    shutil.copy2(a / DATA / "Ordinator - Perks of Skyrim.bsa", d / "Ordinator - Perks of Skyrim.bsa")
    plugin(d / "Armor Pack.esp", recs("ARMO", 20) + recs("WEAP", 10, 0x01000900))
    plugin(d / "Ryn_s Thing.esp", recs("MISC", 2))
    plugin(d / "Follower Bob.esp", recs("NPC_", 1))
    fake_plugin(d / "Tiny Light.esl", ["Skyrim.esm"], flags=0x200)
    make_bsa(d / "Sounds.bsa", {"sound\\fx\\boom.wav": b"z" * 32, "sound\\fx\\bang.wav": b"w" * 32})
    add_list(b, ORD, "Armor Pack.esp", "Ryn's Thing.esp", "Follower Bob.esp", "Tiny Light.esl")
    add_ini(b, "sResourceArchiveList", "Sounds.bsa")
    # --- Gamma
    g = new_pack(lib, "Gamma")
    d = g / DATA
    plugin(d / "Ryn's Thing.esp", recs("MISC", 5))                # same mod, other bytes
    make_bsa(d / "Ryn's Thing.bsa", {"textures\\shared\\a.dds": b"q" * 64})
    shutil.copy2(b / DATA / "Armor Pack.esp", d / "ArmorPackNX.esp")   # renamed copy
    fake_plugin(d / "Needs Missing.esp", ["Skyrim.esm", "Nowhere.esp"])
    fake_plugin(d / "Needs Lands.esp", ["Skyrim.esm", "Lands Mod.esp"])
    shutil.copy2(USSEP_DIR / "No_CC" / "Unofficial Skyrim Special Edition Patch.esp",
                 d / "Unofficial Skyrim Special Edition Patch.esp")
    plugin(d / "Quest Mod.esp", recs("QUST", 2) + recs("INFO", 25, 0x01000900))
    add_list(g, "Ryn's Thing.esp", "ArmorPackNX.esp", "Needs Missing.esp", "Needs Lands.esp",
             "Unofficial Skyrim Special Edition Patch.esp", "Quest Mod.esp")
    # --- a loose Switch mod in Library\Mods
    m = lib / "Mods" / "Cool Sword NX"
    plugin(m / "Cool Sword.esp", recs("WEAP", 3))
    (m / "Cool Sword.bsa").write_bytes(EMPTY_BSA)
    return lib


def entry(cat, name):
    hits = [e for e in cat["entries"] if e["name"] == name]
    assert hits, [e["name"] for e in cat["entries"]]
    return hits[0]


def pick(cat, name, pack):
    e = entry(cat, name)
    v = next(v for v in e["versions"] if v["pack"] == pack)
    return {"key": e["key"], "pack_path": v["pack_path"], "unit_id": v["unit_id"]}


BASE = {"edition": "AE", "inis_dir": str(INIS), "cc_preset": "all", "ussep": None,
        "ussep_dir": str(USSEP_DIR)}


# ---------------------------------------------------------------- catalog
def test_grouping_merges_and_categories(lib):
    cat = CAT.build_catalog(lib, masterlist=MASTERLIST)
    assert {p["name"] for p in cat["packs"]} == {"Alpha", "Beta", "Gamma", "Cool Sword NX"}
    ordi = entry(cat, "Ordinator - Perks of Skyrim")
    assert ordi["packs"] == ["Alpha", "Beta"] and ordi["identical"]
    v = ordi["versions"][0]
    assert v["bsas"] == ["Ordinator - Perks of Skyrim.bsa"] and v["hash"] and v["ccc_bytes"] == len(ORD) + 2
    assert ordi["category"] == "gameplay" and "Skills & Perks" in ordi["category_why"][0]
    ryn = entry(cat, "Ryn's Thing")                              # Drive damage folded
    assert ryn["packs"] == ["Beta", "Gamma"] and not ryn["identical"]
    armor = entry(cat, "Armor Pack")                             # linked by bytes
    assert armor["packs"] == ["Beta", "Gamma"] and armor["identical"]
    assert armor["category"] == "items"
    assert armor["inside_merges"] == [{"pack": "Alpha", "pack_path": str(lib / "Packs" / "Alpha"),
                                       "merge": "MergedStuff.esp", "unit_id": "plugin:MergedStuff.esp"}]
    assert entry(cat, "MergedStuff")["merge_of"] == ["Armor Pack.esp", "Quest Mod.esp"]
    assert entry(cat, "Quest Mod")["inside_merges"][0]["merge"] == "MergedStuff.esp"
    cats = {e["name"]: e["category"] for e in cat["entries"]}
    assert cats["Lands Mod"] == "lands"
    assert cats["Patch AB"] == "patches"
    assert cats["Follower Bob"] == "followers"
    assert cats["Quest Mod"] == "quests"
    assert cats["Unofficial Skyrim Special Edition Patch"] == "fixes"
    assert cats["Sounds.bsa"] == "audio"
    assert cats["Cool Sword"] == "items"
    sword = entry(cat, "Cool Sword")["versions"][0]
    assert sword["source_kind"] == "mod" and sword["unit_id"] == "mod:Cool Sword NX"
    for e in cat["entries"]:
        assert e["category"] in CAT.CATEGORY_IDS and all(e["category_why"])
        for v in e["versions"]:
            assert not any(k.startswith("_") for k in v)
    assert cat["counts"]["gameplay"] >= 1 and cat["stats"]["shared"] == 3
    labels = {c["id"]: c for c in CAT.CATEGORIES}
    assert labels["lands"]["es"] and "—" not in "".join(c["es"] for c in CAT.CATEGORIES)


def test_cache_reuse_and_invalidation(lib, tmp_path):
    cache = tmp_path / "cache"
    first = CAT.build_catalog(lib, cache_dir=cache)
    assert first["stats"]["cached_packs"] == 0 and len(list(cache.glob("*.json"))) == 4
    t = time.time()
    again = CAT.build_catalog(lib, cache_dir=cache)
    assert time.time() - t < 2
    assert again["stats"]["cached_packs"] == 4
    strip = lambda c: [(e["key"], e["category"], len(e["versions"])) for e in c["entries"]]  # noqa: E731
    assert strip(again) == strip(first)
    fake_plugin(lib / "Packs" / "Gamma" / DATA / "Brand New.esp", ["Skyrim.esm"])
    third = CAT.build_catalog(lib, cache_dir=cache)
    assert third["stats"]["cached_packs"] == 3
    assert {p["name"]: p["cached"] for p in third["packs"]}["Gamma"] is False
    assert entry(third, "Brand New")["versions"][0]["flags"][0]["code"] == "not-in-list"


# ---------------------------------------------------------------- planning
def test_plan_masters_order_and_clashes(lib):
    cat = CAT.build_catalog(lib)
    picks = [pick(cat, "Patch AB", "Alpha"), pick(cat, "Ordinator - Perks of Skyrim", "Beta"),
             pick(cat, "Ryn's Thing", "Gamma"), pick(cat, "MergedStuff", "Alpha"),
             pick(cat, "Armor Pack", "Beta"), pick(cat, "Ryn's Thing", "Beta")]
    plan = CAT.plan_build(cat, picks, BASE)
    rows = {(m["plugin"], m["master"]): m for m in plan["masters"]}
    assert rows[("Patch AB.esp", ORD)]["from"] == "pick"
    assert rows[("Patch AB.esp", ORD)]["source"]["pack"] == "Beta"
    assert rows[("Patch AB.esp", "Lands Mod.esp")]["from"] == "auto"
    assert rows[("Patch AB.esp", "Skyrim.esm")]["from"] == "game"
    auto = [i for i in plan["items"] if i["reason"] == "master"]
    assert [(i["name"], i["needed_by"]) for i in auto] == [("Lands Mod", ["Patch AB.esp"])]
    # Beta brings Ordinator, which Alpha's patch needs: Beta goes first
    assert [o["pack"] for o in plan["order"]] == ["Beta", "Alpha", "Gamma"]
    kinds = {c["kind"] for c in plan["clashes"]}
    assert {"same-mod", "in-merge", "bsa-overlap"} <= kinds
    dup = next(c for c in plan["clashes"] if c["kind"] == "same-mod")
    assert [p["pack"] for p in dup["picks"]] == ["Gamma", "Beta"]
    assert next(s for s in plan["skipped"] if s["pack"] == "Beta" and s["unit_id"].startswith("plugin:Ryn"))
    ov = next(c for c in plan["clashes"] if c["kind"] == "bsa-overlap")
    assert ov["count"] == 1 and ov["examples"] == ["textures\\shared\\a.dds"]
    assert plan["ok"] and not plan["missing"]
    b = plan["budget"]
    assert b["ccc"]["limit"] == 4096 and b["ccc"]["cc_lines"] == 80
    names = ["Patch AB.esp", ORD, "Ryn's Thing.esp", "MergedStuff.esp", "Armor Pack.esp", "Lands Mod.esp"]
    assert b["ccc"]["bytes"] == b["ccc"]["base_bytes"] + sum(len(n) + 2 for n in names)
    assert b["bsas"] == 2 and b["plugins"] == 6
    assert b["ram"]["status"] == "ok" and b["ram"]["free_min"] == 500 * 2**20
    assert all(r["chars"] <= r["limit"] for r in b["inis"])


def test_plan_missing_masters_and_suggestions(lib):
    cat = CAT.build_catalog(lib)
    plan = CAT.plan_build(cat, [pick(cat, "Needs Missing", "Gamma"), pick(cat, "Needs Lands", "Gamma")], BASE)
    assert not plan["ok"]
    miss = {m["master"]: m for m in plan["missing"]}
    assert miss["Nowhere.esp"]["from"] == "missing" and not miss["Nowhere.esp"]["suggestions"]
    assert miss["Lands Mod.esp"]["from"] == "other-pack"
    assert miss["Lands Mod.esp"]["suggestions"][0]["pack"] == "Alpha"
    codes = [s["code"] for s in plan["suggestions"]]
    assert "add-master" in codes and "remove-needer" in codes
    add = next(s for s in plan["suggestions"] if s["code"] == "add-master")
    # following the suggestion fixes it
    plan2 = CAT.plan_build(cat, [pick(cat, "Needs Lands", "Gamma")] + add["add"], BASE)
    assert plan2["ok"] and [o["pack"] for o in plan2["order"]] == ["Alpha", "Gamma"]
    for p in plan["problems"]:
        assert len(p["text"]) == 2 and all(p["text"])


def test_plan_ussep_se_and_limits(lib):
    cat = CAT.build_catalog(lib)
    base = dict(BASE, ussep="All_CC", cc_preset="ussep")
    plan = CAT.plan_build(cat, [pick(cat, "Unofficial Skyrim Special Edition Patch", "Gamma"),
                                pick(cat, "Tiny Light", "Beta")], base)
    item = {i["name"]: i for i in plan["items"]}
    assert item["Unofficial Skyrim Special Edition Patch"]["status"] == "covered"
    assert item["Tiny Light"]["status"] == "bring"
    assert plan["budget"]["bsas"] == 4 and plan["ussep"]["variant"] == "All_CC"
    sky = next(r for r in plan["budget"]["inis"] if r["ini"] == "Skyrim.ini" and r["key"] == "sResourceArchiveList")
    assert sky["entries"] >= 3
    se = CAT.plan_build(cat, [pick(cat, "Tiny Light", "Beta")], dict(BASE, edition="SE"))
    assert se["items"][0]["status"] == "refused" and "ESL" in se["skipped"][0]["reason"][1]
    # too many plugins for the load list
    d = lib / "Packs" / "Alpha" / DATA
    for i in range(22):
        fake_plugin(d / (f"{i:02d} " + "x" * 90 + ".esp"), ["Skyrim.esm"])
    cat = CAT.build_catalog(lib)
    many = [pick(cat, e["name"], "Alpha") for e in cat["entries"] if e["name"].endswith("x" * 20)]
    plan = CAT.plan_build(cat, many, BASE)
    assert not plan["ok"] and plan["budget"]["ccc"]["status"] == "over"
    assert any(p["code"] == "ccc-over" for p in plan["problems"])
    assert any(s["code"] == "cc-preset" for s in plan["suggestions"])
    assert CAT.plan_build(cat, many, dict(BASE, cc_preset="ussep"))["ok"]
    with pytest.raises(CAT.CatalogError):
        CAT.execute_build(cat, many, BASE, lib.parent / "never")
    assert not (lib.parent / "never").exists()


# ---------------------------------------------------------------- building
def test_execute_build_makes_a_working_pack(lib, tmp_path):
    cat = CAT.build_catalog(lib)
    before = {n: snapshot(lib / "Packs" / n) for n in ("Alpha", "Beta", "Gamma")}
    before["mod"] = snapshot(lib / "Mods")
    picks = [pick(cat, "Ordinator - Perks of Skyrim", "Beta"), pick(cat, "Patch AB", "Alpha"),
             pick(cat, "Ryn's Thing", "Gamma"), pick(cat, "Sounds.bsa", "Beta"),
             pick(cat, "Unofficial Skyrim Special Edition Patch", "Gamma"),
             pick(cat, "Cool Sword", "Cool Sword NX"), pick(cat, "Armor Pack", "Beta")]
    base = dict(BASE, ussep="All_CC", cc_preset="ussep")
    dest = tmp_path / "New Pack"
    rep = CAT.execute_build(cat, picks, base, dest)
    assert rep["ok"], rep["errors"]
    assert rep["order"] == ["Beta", "Alpha", "Gamma", "Cool Sword NX"]
    got = {(b["pack"], b["name"]) for b in rep["brought"]}
    assert ("Alpha", "Lands Mod") in got and ("Alpha", "Patch AB") in got
    assert ("Beta", "Sounds.bsa") in got and ("Gamma", "Ryn's Thing") in got
    assert any(s["reason"][0].startswith("The new pack already gets USSEP") for s in rep["skipped"])
    pk = Pack.open(dest)
    for f in (ORD, "Ordinator - Perks of Skyrim.bsa", "Patch AB.esp", "Lands Mod.esp", "Ryn's Thing.esp",
              "Ryn's Thing.bsa", "Sounds.bsa", "Cool Sword.esp", "Armor Pack.esp",
              "Unofficial Skyrim Special Edition Patch.esp", "USSEPT.bsa"):
        assert (pk.data_dir / f).is_file(), f
    entries = pk.list_entries
    assert entries.index(K_USSEP) < entries.index(ORD) < entries.index("Patch AB.esp")
    assert entries.index("Lands Mod.esp") < entries.index("Patch AB.esp")
    assert "Sounds.bsa" in read_ini(pk.base_romfs / "Skyrim.ini").archive_list("sResourceArchiveList")
    crit = [f for f in run_audit(pk, deep=False).findings if f.severity == "critico"]
    assert not crit, [(f.code, f.subject) for f in crit]
    titles = [h["title"] for h in list_history(dest)]
    assert sum(t.startswith("Bring") for t in titles) == 3          # one per source pack
    mods = load_mods(pk)
    assert mods["Lands Mod"]["reason"] == "master" and mods["Lands Mod"]["from_pack"] == "Alpha"
    assert rep["budget"]["ccc"]["bytes"] == pk.ccc_path.stat().st_size
    for n in ("Alpha", "Beta", "Gamma"):
        assert snapshot(lib / "Packs" / n) == before[n], n
    assert snapshot(lib / "Mods") == before["mod"]
    # the new pack can go into the Library and shows up in the catalog
    L.add_external(lib, dest, kind="pack")
    cat2 = CAT.build_catalog(lib)
    assert "New Pack" in entry(cat2, "Patch AB")["packs"]


K_USSEP = "Unofficial Skyrim Special Edition Patch.esp"


# ---------------------------------------------------------------- real packs
@pytest.mark.skipif(not MIRROR.exists(), reason="no mirror")
def test_real_packs_group_across_packs(tmp_path):
    lib = tmp_path / "Library"
    for p in sorted(MIRROR.iterdir()):
        L.add_external(lib, p, kind="pack")
    before = {str(p): p.lstat().st_mtime_ns for p in MIRROR.rglob("*")}
    cat = CAT.build_catalog(lib, masterlist=MASTERLIST)
    assert len(cat["packs"]) == 5 and not any(p["error"] for p in cat["packs"])
    ussep = entry(cat, "Unofficial Skyrim Special Edition Patch")
    assert len(ussep["packs"]) >= 4 and ussep["category"] == "fixes"
    assert len(entry(cat, "Ordinator - Perks of Skyrim")["packs"]) >= 2
    assert len(entry(cat, "Imperious - Races of Skyrim")["packs"]) >= 2
    assert cat["stats"]["shared"] >= 40
    again = CAT.build_catalog(lib, masterlist=MASTERLIST)
    assert again["stats"]["cached_packs"] == 5
    assert {str(p): p.lstat().st_mtime_ns for p in MIRROR.rglob("*")} == before
