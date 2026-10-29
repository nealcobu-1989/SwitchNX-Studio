"""Build NXTest.esp + NXTest.bsa: a lesser power with menus to test a pack on
Switch (teleport, spawn one or many, remove what was spawned, time, heal).

Switch has no console and no MCM, so it works like the game's own settings
menus: message boxes with buttons. The power's script only shows menus; the
spawning runs on a quest script, which also gives the power when a game loads.

Records copied from Skyrim.esm and changed, so their binary layout is the
game's own: the magic effect from TransmuteOreMineralEffect (a script effect,
fire and forget, self), the power from PowerKhajiitNightEye (a lesser power).
The leveled lists to spawn and the map markers to teleport to are Skyrim.esm's,
so the spawns follow whatever the pack's mods put in those lists.

Usage: python build.py <Skyrim.esm> <compiled .pex folder> <out folder>
The .pex come from source/*.psc (any Papyrus compiler with the game's headers).
"""
from __future__ import annotations

import struct
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from skynx.bsa import write_bsa  # noqa: E402
from skynx.records import iter_records, iter_subrecords, seq_bytes  # noqa: E402

NAME = "NXTest"
ME = 0x01000000                    # one master (Skyrim.esm): our own records are 01xxxxxx
QUEST, POWER, EFFECT = ME | 0x800, ME | 0x801, ME | 0x802
MSG_MAIN, MSG_PLACE, MSG_SPAWN, MSG_COUNT, MSG_TIME = (ME | n for n in range(0x803, 0x808))
GAMEHOUR = 0x38

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


# ------------------------------------------------------------------ binary helpers
def sub(sig: str, data: bytes) -> bytes:
    return sig.encode() + struct.pack("<H", len(data)) + data


def z(s: str) -> bytes:
    return s.encode("cp1252") + b"\0"


def u32(n: int) -> bytes:
    return struct.pack("<I", n)


def wstr(s: str) -> bytes:
    b = s.encode("cp1252")
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


def prop_objs(name: str, fids: list[int]) -> bytes:
    return wstr(name) + bytes([11, 1]) + u32(len(fids)) + b"".join(obj(f) for f in fids)


def vmad(script: str, props: list[bytes]) -> bytes:
    return struct.pack("<hhH", 5, 2, 1) + wstr(script) + b"\0" + struct.pack("<H", len(props)) + b"".join(props)


# ------------------------------------------------------------------ records
def template(esm: Path, typ: str, fid: int) -> list[tuple[str, bytes]]:
    for r in iter_records(esm, types=[typ]):
        if r.formid == fid:
            return list(iter_subrecords(r.data))
    raise SystemExit(f"{typ} {fid:#x} not found in {esm}")


def message(fid: int, edid: str, text: str, buttons: list[str]) -> bytes:
    subs = [sub("EDID", z(edid)), sub("DESC", z(text)), sub("FULL", z("SkyNX test tools")),
            sub("INAM", u32(0)), sub("DNAM", u32(1))]          # 1 = message box
    subs += [sub("ITXT", z(b)) for b in buttons]
    return record("MESG", fid, subs)


def build(esm: Path, pex_dir: Path, out: Path) -> None:
    out.mkdir(parents=True, exist_ok=True)
    # magic effect: the game's own script effect, with our script
    mg = []
    for sig, d in template(esm, "MGEF", 0x109110):
        if sig == "EDID":
            d = z("NXTestMenuMGEF")
        elif sig == "VMAD":
            d = vmad("NXTestMenuEffect", [
                prop_obj("Tools", QUEST), prop_obj("MainMenu", MSG_MAIN), prop_obj("PlaceMenu", MSG_PLACE),
                prop_obj("SpawnMenu", MSG_SPAWN), prop_obj("CountMenu", MSG_COUNT),
                prop_obj("TimeMenu", MSG_TIME), prop_obj("GameHour", GAMEHOUR),
                prop_objs("Places", [f for _b, f in PLACES]),
                prop_objs("Spawns", [f for _b, f in SPAWNS])])
        elif sig == "FULL":
            d = z("SkyNX test tools")
        elif sig == "DNAM":
            d = z("")
        mg.append(sub(sig, d))
    # the power: the game's own lesser power, pointing at our effect
    sp = []
    for sig, d in template(esm, "SPEL", 0xAA01D):
        if sig == "EDID":
            d = z("NXTestPower")
        elif sig == "FULL":
            d = z("SkyNX Test Tools")
        elif sig == "DESC":
            d = z("Teleport, spawn enemies, change the time: for testing the pack.")
        elif sig == "EFID":
            d = u32(EFFECT)
        elif sig == "EFIT":
            d = struct.pack("<fII", 0.0, 0, 5)     # magnitude, area, 5 s (the menus pause the game)
        sp.append(sub(sig, d))
    # the quest: starts with the game, gives the power, runs the spawning
    qu = [sub("EDID", z("NXTestQuest")),
          sub("VMAD", vmad("NXTestQuestScript", [prop_obj("NXTestPower", POWER)])),
          sub("FULL", z("SkyNX test tools")),
          sub("DNAM", struct.pack("<HBBII", 0x0011, 0, 0, 0, 0)),   # start game enabled, as the game's own
          sub("NEXT", b""), sub("ANAM", u32(0))]
    msgs = [
        message(MSG_MAIN, "NXTestMainMenu", "SkyNX test tools\n\nSpawned and tracked: %.0f",
                ["Teleport", "Spawn one", "Spawn many", "Remove spawned", "Time of day", "Heal", "Close"]),
        message(MSG_PLACE, "NXTestPlaceMenu", "Where to?", [b for b, _f in PLACES] + ["Back"]),
        message(MSG_SPAWN, "NXTestSpawnMenu", "What should appear? (in front of you)",
                [b for b, _f in SPAWNS] + ["Back"]),
        message(MSG_COUNT, "NXTestCountMenu", "How many?", ["5", "10", "20", "40", "Back"]),
        message(MSG_TIME, "NXTestTimeMenu", "Set the time", ["Dawn (6:00)", "Noon (12:00)", "Dusk (18:00)",
                                                              "Midnight (0:00)", "Back"]),
    ]
    nrec = 3 + len(msgs) + 4                     # records and groups, as xEdit counts them
    tes4 = record("TES4", 0, [sub("HEDR", struct.pack("<fiI", 1.70, nrec, 0x808)),
                              sub("CNAM", z("SkyNX Studio")),
                              sub("SNAM", z("Test tools for Switch packs: teleport, spawn, time, heal.")),
                              sub("MAST", z("Skyrim.esm")), sub("DATA", bytes(8))])
    esp = tes4 + group("MGEF", [record("MGEF", EFFECT, mg)]) + group("SPEL", [record("SPEL", POWER, sp)]) \
        + group("QUST", [record("QUST", QUEST, qu)]) + group("MESG", msgs)
    (out / f"{NAME}.esp").write_bytes(esp)
    # BSA: the scripts and the SEQ (the quest starts with the game)
    stage = out / ".stage"
    stage.mkdir(exist_ok=True)
    (stage / f"{NAME}.seq").write_bytes(seq_bytes([QUEST]))
    files = [(f"scripts\\{p.name}", p) for p in sorted(Path(pex_dir).glob("NXTest*.pex"))]
    files.append((f"seq\\{NAME}.seq", stage / f"{NAME}.seq"))
    write_bsa(files, out / f"{NAME}.bsa")
    for p in stage.iterdir():
        p.unlink()
    stage.rmdir()


if __name__ == "__main__":
    build(Path(sys.argv[1]), Path(sys.argv[2]), Path(sys.argv[3]))
