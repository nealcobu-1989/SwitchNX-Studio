"""SkyNX Test Tools (extras/nxtest): the plugin, and the pack's quests in it.

A lesser power opens message-box menus (Switch has no console and no MCM):
teleport, spawn one or many enemies from the game's leveled lists, creatures from
mods (by plugin and form id), remove what was spawned, time of day, the tracked
quests (next stage, restart), player helpers (heal, perk point, gold, god mode,
no collision) and the weather.

The quest menu needs to know the pack's quests: which plugin and form id,
their stages, and their names (a script can't read a quest's name without
SKSE, so each quest gets a message with its name written in). That list is
written into NXTest.esp when the project is packed (`refresh`). Quests are
looked up with Game.GetFormFromFile, so NXTest.esp keeps Skyrim.esm as its only
master and a plugin switched off on the console is simply skipped.

Records copied from Skyrim.esm and changed, so their layout is the game's
own: the magic effect from TransmuteOreMineralEffect (a script effect, fire
and forget, self), the power from PowerKhajiitNightEye (a lesser power).
"""
from __future__ import annotations

import json
import struct
import zlib
from pathlib import Path

from .records import iter_records, iter_subrecords, _masters_of

NAME = "NXTest"
PLUGIN = "NXTest.esp"
ME = 0x01000000                    # one master (Skyrim.esm): our own records are 01xxxxxx
QUEST, POWER, EFFECT = ME | 0x800, ME | 0x801, ME | 0x802
MSG_MAIN, MSG_PLACE, MSG_SPAWN, MSG_COUNT, MSG_TIME = (ME | n for n in range(0x803, 0x808))
MSG_PLAYER, MSG_WEATHER, MSG_RESTART, MSG_NOQUEST = (ME | n for n in range(0x808, 0x80C))
MSG_MODSPAWN = ME | 0x80C        # creatures from mods (found with Game.GetFormFromFile)
MSG_QUEST0 = ME | 0x900            # one per quest of the pack
GAMEHOUR, GOLD = 0x38, 0xF
TEMPLATE_MGEF, TEMPLATE_SPEL = 0x109110, 0xAA01D
# A Papyrus array is only sure to hold 128 items: the data goes in chunks
# (the script, extras/nxtest/source/NXTestQuestScript.psc, has this many).
CHUNK, QCH, SCH = 128, 8, 48
MAX_QUESTS, MAX_STAGES = CHUNK * QCH, CHUNK * SCH * 2
BUILD = 3                          # bump when the records change: packs rebuild their plugin

PLACES = [  # (button, Skyrim.esm map marker): short, the buttons go in one row
    ("Whiterun", 0xC44AD),      # Dragonsreach
    ("WR gate", 0x162CE),       # Whiterun, outside the gate
    ("Solitude", 0xC44AB),      # Blue Palace
    ("Windhelm", 0xC44B3),      # Palace of the Kings
    ("Markarth", 0xC44AF),      # Understone Keep
    ("Riften", 0x1C390),
    ("Riverwood", 0x162A4),
    ("Falkreath", 0x17760),
    ("Embershard", 0xB6CDF),    # the mine
]
# A message box takes 10 buttons at most: 9 places and Back.
SPAWNS = [  # (button, Skyrim.esm leveled actor list)
    ("Bandit", 0x3DECD),        # LCharBanditMeleeAny
    ("Forsworn", 0x1E792),      # LCharForswornMelee1H
    ("Draugr", 0x55955),        # LCharDraugrMeleeAllMale
    ("Vampire", 0x33973),       # LCharVampire
    ("Wolf", 0xB83C2),          # LCharWolf
    ("Bear", 0x42266),          # LCharBearAll
    ("Sabre cat", 0xFE2D5),     # LCharSabrecat
    ("Giant", 0x30529),         # LCharGiant
    ("Dragon", 0x5EACF),        # LCharDragonAny
]
WEATHERS = [  # (button, Skyrim.esm weather)
    ("Clear", 0x81A),           # SkyrimClear
    ("Cloudy", 0x12F89),        # SkyrimCloudy
    ("Rain", 0xC821F),          # SkyrimOvercastRain
    ("Snow", 0xC8221),          # SkyrimStormSnow
    ("Fog", 0xC821E),           # SkyrimFog
]


class NXTestError(ValueError):
    pass


# ------------------------------------------------------------------ binary helpers
def sub(sig: str, data: bytes) -> bytes:
    return sig.encode() + struct.pack("<H", len(data)) + data


def z(s: str) -> bytes:
    return s.encode("cp1252", "replace") + b"\0"


def u32(n: int) -> bytes:
    return struct.pack("<I", n)


def wstr(s: str) -> bytes:
    b = s.encode("cp1252", "replace")
    return struct.pack("<H", len(b)) + b


def record(typ: str, fid: int, subs: list[bytes], flags: int = 0) -> bytes:
    data = b"".join(subs)
    return typ.encode() + struct.pack("<IIIHHHH", len(data), flags, fid, 0, 0, 44, 0) + data


def group(typ: str, records: list[bytes]) -> bytes:
    body = b"".join(records)
    return b"GRUP" + struct.pack("<I", 24 + len(body)) + typ.encode() + struct.pack("<IHHHH", 0, 0, 0, 0, 0) + body


# VMAD, version 5, object format 2 (unused u16, alias i16, form id)
def obj(fid: int) -> bytes:
    return struct.pack("<HhI", 0, -1, fid)


def prop_obj(name: str, fid: int) -> bytes:
    return wstr(name) + bytes([1, 1]) + obj(fid)


def prop_int(name: str, n: int) -> bytes:
    return wstr(name) + bytes([3, 1]) + struct.pack("<i", n)


def prop_objs(name: str, fids: list[int]) -> bytes:
    return wstr(name) + bytes([11, 1]) + u32(len(fids)) + b"".join(obj(f) for f in fids)


def prop_strs(name: str, items: list[str]) -> bytes:
    return wstr(name) + bytes([12, 1]) + u32(len(items)) + b"".join(wstr(s) for s in items)


def prop_ints(name: str, items: list[int]) -> bytes:
    return wstr(name) + bytes([13, 1]) + u32(len(items)) + b"".join(struct.pack("<i", n) for n in items)


def vmad(script: str, props: list[bytes]) -> bytes:
    return struct.pack("<hhH", 5, 2, 1) + wstr(script) + b"\0" + struct.pack("<H", len(props)) + b"".join(props)


def message(fid: int, edid: str, text: str, buttons: list[str]) -> bytes:
    subs = [sub("EDID", z(edid)), sub("DESC", z(text)), sub("FULL", z("SkyNX test tools")),
            sub("INAM", u32(0)), sub("DNAM", u32(1))]          # 1 = message box
    subs += [sub("ITXT", z(b)) for b in buttons]
    return record("MESG", fid, subs)


# ------------------------------------------------------------------ the pack's quests
def _strings(plugin: str, lang: str, places: list[Path]) -> dict[int, str]:
    """The plugin's .strings in this language: loose, in a BSA named after it,
    or in the game's interface/patch archives (where the game keeps its own)."""
    from .bsa import read_bsa
    from .names import parse_strings
    stem = Path(plugin).stem
    want = f"strings\\{stem.lower()}_{lang}.strings"
    names = [f"{stem}.bsa", f"{stem} - Main.bsa", "Skyrim - Interface.bsa", "Skyrim - Patch.bsa"]
    for folder in places:
        loose = Path(folder) / "strings" / f"{stem}_{lang}.strings"
        if loose.is_file():
            return parse_strings(loose.read_bytes())
    for folder in places:
        for n in names:
            b = Path(folder) / n
            if not b.is_file():
                continue
            try:
                arc = read_bsa(b)
                e = next((e for e in arc.entries if e.path.lower() == want), None)
                if e is not None:
                    return parse_strings(arc.read_file(e))
            except Exception:  # noqa: BLE001
                continue
    return {}


def _plugin_quests(path: Path, name: str) -> tuple[bool, list[dict]]:
    raw = path.read_bytes()
    localized = len(raw) > 12 and bool(struct.unpack_from("<I", raw, 8)[0] & 0x80)
    masters = _masters_of(path)
    out = []
    for r in iter_records(raw, types=["QUST"]):
        if r.data is None:
            continue
        i = r.formid >> 24
        owner = masters[i] if i < len(masters) else name
        full, stages, objs = None, [], 0
        for sig, d in r.subrecords():
            if sig == "FULL":
                full = d
            elif sig == "INDX" and len(d) >= 2:
                stages.append(struct.unpack_from("<h", d)[0])
            elif sig == "QOBJ":
                objs += 1
        out.append({"owner": owner, "local": r.formid & 0xFFFFFF, "full": full,
                    "stages": sorted({s for s in stages if s >= 0}), "objs": objs})
    return localized, out


def quest_table(pack, vanilla_dir: Path | None, lang: str | None = None) -> dict:
    """The quests a player can track in this pack, as the script needs them:
    {files, quests: [[file index, local id, name, stages]], version, left_out}.
    The last plugin that edits a quest decides its name and stages."""
    from . import vanilla as V
    from . import names as NM
    if lang is None:
        codes = [i.path.stem.lower().split("_", 1)[1] for i in pack.lang_inis if "_" in i.path.stem]
        lang = NM.LATIN_LANGS.get(codes[0] if codes else "en") or "english"
    places: list[Path] = []
    game: dict[str, Path] = {}
    if vanilla_dir and Path(vanilla_dir).is_dir():
        vf = V.bsa_folder(Path(vanilla_dir))
        places.append(vf)
        for p in vf.iterdir():
            if p.suffix.lower() in (".esm", ".esl", ".esp"):
                game[p.name.lower()] = p
    if pack.data_dir:
        places.insert(0, pack.data_dir)
    win: dict[tuple, dict] = {}
    for name, _src in pack.load_order():
        if name.startswith("#") or name.lower() == PLUGIN.lower():
            continue
        h = pack.plugins.get(name.lower())
        path = h.path if h and not h.error else game.get(name.lower())
        if not path or not Path(path).is_file():
            continue
        try:
            localized, qs = _plugin_quests(Path(path), name)
        except Exception:  # noqa: BLE001
            continue
        strings = None
        for q in qs:
            name_txt = None
            if q["full"]:
                if localized and len(q["full"]) == 4:
                    if strings is None:
                        strings = _strings(name, lang, places)
                    name_txt = strings.get(struct.unpack("<I", q["full"])[0])
                else:
                    raw = q["full"].rstrip(b"\0")
                    try:
                        name_txt = raw.decode("utf-8")
                    except UnicodeDecodeError:
                        name_txt = raw.decode("cp1252", "replace")
            key = (q["owner"].lower(), q["local"])
            win[key] = {"owner": q["owner"], "local": q["local"], "name": name_txt,
                        "stages": q["stages"], "objs": q["objs"]}
    files: list[str] = []
    quests, stages_total, left = [], 0, 0
    for q in win.values():
        if not q["name"] or not q["objs"] or not q["stages"]:
            continue
        if len(quests) >= MAX_QUESTS or stages_total + len(q["stages"]) > MAX_STAGES or len(q["stages"]) > 255:
            left += 1
            continue
        if q["owner"] not in files:
            if len(files) >= 127:
                left += 1
                continue
            files.append(q["owner"])
        quests.append([files.index(q["owner"]), q["local"], q["name"], q["stages"]])
        stages_total += len(q["stages"])
    version = zlib.crc32(json.dumps([BUILD, files, quests], ensure_ascii=False).encode("utf-8")) & 0x7FFFFFFF
    return {"files": files, "quests": quests, "version": version, "left_out": left}


# ------------------------------------------------------------------ the plugin
def _template(src: Path, typ: str, fid: int) -> list[tuple[str, bytes]]:
    for r in iter_records(src, types=[typ]):
        if r.formid == fid and r.data is not None:
            return list(iter_subrecords(r.data))
    raise NXTestError(f"{typ} {fid:#x} isn't in {Path(src).name}", f"{typ} {fid:#x} no está en {Path(src).name}")


def templates(esm: Path | None = None, current: Path | None = None) -> dict:
    """The effect and power records to start from: the game's own (Skyrim.esm),
    or the ones already in NXTest.esp (made from them)."""
    if current and Path(current).is_file():
        try:
            return {"MGEF": _template(current, "MGEF", EFFECT), "SPEL": _template(current, "SPEL", POWER)}
        except NXTestError:
            pass
    if not esm:
        raise NXTestError("Skyrim.esm is needed to build the test tools",
                          "Hace falta Skyrim.esm para construir las herramientas de prueba")
    return {"MGEF": _template(esm, "MGEF", TEMPLATE_MGEF), "SPEL": _template(esm, "SPEL", TEMPLATE_SPEL)}


def _chunks(items: list, n: int) -> list[list]:
    return [items[i * CHUNK:(i + 1) * CHUNK] for i in range(n)]


def build_esp(tpl: dict, table: dict | None = None) -> bytes:
    table = table or {"files": [], "quests": [], "version": 0}
    quests = table["quests"]
    mg = []
    for sig, d in tpl["MGEF"]:
        if sig == "EDID":
            d = z("NXTestMenuMGEF")
        elif sig == "VMAD":
            d = vmad("NXTestMenuEffect", [
                prop_obj("Tools", QUEST), prop_obj("MainMenu", MSG_MAIN), prop_obj("PlaceMenu", MSG_PLACE),
                prop_obj("SpawnMenu", MSG_SPAWN), prop_obj("CountMenu", MSG_COUNT),
                prop_obj("TimeMenu", MSG_TIME), prop_obj("PlayerMenu", MSG_PLAYER),
                prop_obj("WeatherMenu", MSG_WEATHER), prop_obj("ModSpawnMenu", MSG_MODSPAWN),
                prop_obj("GameHour", GAMEHOUR), prop_obj("Gold", GOLD),
                prop_objs("Places", [f for _b, f in PLACES]),
                prop_objs("Spawns", [f for _b, f in SPAWNS]),
                prop_objs("Weathers", [f for _b, f in WEATHERS])])
        elif sig == "FULL":
            d = z("SkyNX test tools")
        elif sig == "DNAM":
            d = z("")
        mg.append(sub(sig, d))
    sp = []
    for sig, d in tpl["SPEL"]:
        if sig == "EDID":
            d = z("NXTestPower")
        elif sig == "FULL":
            d = z("SkyNX Test Tools")
        elif sig == "DESC":
            d = z("Teleport, spawn enemies, time, weather, quests: for testing the pack.")
        elif sig == "EFID":
            d = u32(EFFECT)
        elif sig == "EFIT":
            d = struct.pack("<fII", 0.0, 0, 5)     # magnitude, area, 5 s (the menus pause the game)
        sp.append(sub(sig, d))
    # the quest's data: id word, stage pointer, packed stages, one message each
    qa, qb, packed, flat = [], [], [], []
    for fi, local, _name, stages in quests:
        qa.append(fi * 0x1000000 + local)
        qb.append(len(flat) * 256 + len(stages))
        flat.extend(stages)
    for i in range(0, len(flat), 2):
        b = flat[i + 1] if i + 1 < len(flat) else 0
        packed.append(flat[i] + b * 65536)
    props = [prop_obj("NXTestPower", POWER), prop_strs("Files", table["files"]),
             prop_int("QuestCount", len(quests)), prop_int("DataVersion", table["version"]),
             prop_obj("RestartConfirm", MSG_RESTART), prop_obj("NoQuestMsg", MSG_NOQUEST)]
    for c, part in enumerate(_chunks(qa, QCH)):
        if part:
            props.append(prop_ints(f"QA{c}", part))
    for c, part in enumerate(_chunks(qb, QCH)):
        if part:
            props.append(prop_ints(f"QB{c}", part))
    for c, part in enumerate(_chunks(packed, SCH)):
        if part:
            props.append(prop_ints(f"S{c}", part))
    msg_ids = [MSG_QUEST0 + i for i in range(len(quests))]
    for c, part in enumerate(_chunks(msg_ids, QCH)):
        if part:
            props.append(prop_objs(f"M{c}", part))
    qu = [sub("EDID", z("NXTestQuest")),
          sub("VMAD", vmad("NXTestQuestScript", props)),
          sub("FULL", z("SkyNX test tools")),
          sub("DNAM", struct.pack("<HBBII", 0x0011, 0, 0, 0, 0)),   # start game enabled, as the game's own
          sub("NEXT", b""), sub("ANAM", u32(0))]
    msgs = [
        message(MSG_MAIN, "NXTestMainMenu", "SkyNX test tools\n\nSpawned and tracked: %.0f",
                ["Teleport", "Spawn one", "Spawn many", "Remove spawned", "Time of day", "Mod creatures",
                 "Quests", "Player", "Weather", "Close"]),
        message(MSG_PLACE, "NXTestPlaceMenu", "Where to?", [b for b, _f in PLACES] + ["Back"]),
        message(MSG_SPAWN, "NXTestSpawnMenu", "What should appear? (in front of you)",
                [b for b, _f in SPAWNS] + ["Back"]),
        message(MSG_COUNT, "NXTestCountMenu", "How many?", ["5", "10", "20", "40", "Back"]),
        message(MSG_TIME, "NXTestTimeMenu", "Set the time", ["Dawn (6:00)", "Noon (12:00)", "Dusk (18:00)",
                                                              "Midnight (0:00)", "Back"]),
        message(MSG_PLAYER, "NXTestPlayerMenu",
                "Player\n\nNo collision walks through walls to get out of a stuck spot: "
                "use it again to switch it back.",
                ["+1 perk point", "+1000 gold", "God mode on", "God mode off", "No collision", "Heal", "Back"]),
        message(MSG_MODSPAWN, "NXTestModSpawnMenu",
                "Creatures from mods (in front of you). A mod that isn't in the pack is skipped.\n\n"
                "Mihail mix: one of 14 different Mihail creatures at once, to test memory.",
                ["Harkon (combat form)", "Karstaag", "Werebear", "Mihail mix", "Back"]),
        message(MSG_WEATHER, "NXTestWeatherMenu", "Weather (it stays until Normal weather)",
                [b for b, _f in WEATHERS] + ["Normal weather", "Back"]),
        message(MSG_RESTART, "NXTestRestartConfirm",
                "Restart this quest from the beginning?\n\nIts progress is lost, and a long quest can "
                "break. Save first.", ["Restart", "Cancel"]),
        message(MSG_NOQUEST, "NXTestNoQuest",
                "No tracked quest found.\n\nIn the Journal, mark the quest as active (it shows a check), "
                "then open this menu again.", ["OK"]),
    ]
    for i, (fi, _local, name, _stages) in enumerate(quests):
        msgs.append(message(MSG_QUEST0 + i, f"NXTestQ{i:04d}",
                            f"{name}\n({table['files'][fi]})\n\nStage now: %.0f\nNext stage: %.0f "
                            "(-1: none left)\n\nSkipping stages can leave things undone. Save first.",
                            ["Next stage", "Restart quest", "Other tracked quest", "Close"]))
    nrec = 3 + len(msgs) + 4                     # records and groups, as xEdit counts them
    tes4 = record("TES4", 0, [sub("HEDR", struct.pack("<fiI", 1.70, nrec, 0x800 + 0x100 + len(quests))),
                              sub("CNAM", z("SkyNX Studio")),
                              sub("SNAM", z(f"Test tools for Switch packs: teleport, spawn, time, weather, quests. "
                                            f"Quest list {table['version']:08x}, {len(quests)} quests.")),
                              sub("MAST", z("Skyrim.esm")), sub("DATA", bytes(8))])
    return tes4 + group("MGEF", [record("MGEF", EFFECT, mg)]) + group("SPEL", [record("SPEL", POWER, sp)]) \
        + group("QUST", [record("QUST", QUEST, qu)]) + group("MESG", msgs)


def stored_version(path: Path) -> int | None:
    """The quest list version written in the plugin's description, if any."""
    try:
        for r in iter_records(Path(path), types=["TES4"], header=True):
            for sig, d in r.subrecords():
                if sig == "SNAM":
                    t = d.rstrip(b"\0").decode("cp1252", "replace")
                    if "Quest list " in t:
                        return int(t.split("Quest list ", 1)[1].split(",", 1)[0], 16)
            break
    except Exception:  # noqa: BLE001
        return None
    return None


def pending(pack, vanilla_dir: Path | None, progress=None) -> dict | None:
    """When the pack has NXTest.esp on and its quest list is out of date: the new
    plugin to write ({path, data, quests, files, left_out}). None otherwise."""
    h = pack.plugins.get(PLUGIN.lower())
    if not h or h.error:
        return None
    if not any(e.lower() == PLUGIN.lower() for e in pack.list_entries):
        return None                              # off (#) or not in the list
    if progress:
        progress(PLUGIN)
    table = quest_table(pack, vanilla_dir)
    if stored_version(h.path) == table["version"]:
        return None
    esm = None
    if vanilla_dir:
        from . import vanilla as V
        cand = V.bsa_folder(Path(vanilla_dir)) / "Skyrim.esm"
        esm = cand if cand.is_file() else None
    return {"path": h.path, "data": build_esp(templates(esm, h.path), table), "quests": len(table["quests"]),
            "files": len(table["files"]), "left_out": table["left_out"]}


def refresh(pack, vanilla_dir: Path | None, root: Path, progress=None) -> dict | None:
    """Writes the pack's quests into NXTest.esp when they changed (one undoable
    change in the History). Returns what was written, or None."""
    from .history import Transaction
    job = pending(pack, vanilla_dir, progress)
    if not job:
        return None
    with Transaction(root, "Test tools: the pack's quests",
                     detail=json.dumps({k: job[k] for k in ("quests", "files", "left_out")})) as tx:
        tx.write_bytes(job["path"], job["data"])
    return {k: job[k] for k in ("quests", "files", "left_out")}
