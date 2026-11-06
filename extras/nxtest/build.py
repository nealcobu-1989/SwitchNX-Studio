"""Build NXTest.esp + NXTest.bsa: a lesser power with menus to test a pack on
Switch (teleport, spawn one or many, remove what was spawned, time, heal,
tracked quests, player helpers, weather). The records are in skynx/nxtest.py.

This builds the plugin without any quests: SkyNX Studio writes the pack's
quests into it when the project is packed (skynx.nxtest.refresh).

Usage: python build.py <Skyrim.esm> <compiled .pex folder> <out folder>
The .pex come from source/*.psc (any Papyrus compiler with the game's headers);
source/NXTestQuestScript.psc is written by tools/gen_quest_script.py.
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from skynx.bsa import write_bsa  # noqa: E402
from skynx.nxtest import NAME, QUEST, build_esp, templates  # noqa: E402
from skynx.records import seq_bytes  # noqa: E402


def build(esm: Path, pex_dir: Path, out: Path) -> None:
    out.mkdir(parents=True, exist_ok=True)
    (out / f"{NAME}.esp").write_bytes(build_esp(templates(esm)))
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
