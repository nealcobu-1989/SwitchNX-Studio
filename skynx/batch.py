"""Convert several mods in one go.

Each mod is read on its own (an Analysis, or a FomodSession until its
installer options are chosen) and keeps its own options. Before converting:
the final plugin names must not repeat inside the batch and the .ccc must fit
with all of them. Mods that are masters of others in the batch go first, and
the later ones point at the name their master finally got.
"""
from __future__ import annotations

from pathlib import Path

from . import knowledge as K
from . import rename as RN


def final_names(an, options: dict) -> list[tuple[str, str]]:
    """[(original, final)] as convert() will pick them (before pack checks)."""
    names = (options or {}).get("names") or {}
    out = []
    for pl in an.plugins:
        old = pl["name"]
        new = old if pl.get("locked") else (names.get(old) or pl["suggested"]).strip()
        if an.mode == "SE" and new.lower().endswith(".esl") and not pl.get("locked"):
            new = new[:-4] + ".esp"
        out.append((old, new))
    return out


def order(items: list[tuple[str, object]]) -> list[str]:
    """Item ids, masters first. items: [(id, Analysis)]; keeps the given order otherwise."""
    owns = {}
    for iid, an in items:
        for pl in an.plugins:
            owns.setdefault(pl["name"].lower(), iid)
    deps = {iid: {owns[m.lower()] for pl in an.plugins for m in pl.get("missing") or []
                  if m.lower() in owns and owns[m.lower()] != iid}
            for iid, an in items}
    done: list[str] = []
    left = [iid for iid, _ in items]
    while left:
        ready = [i for i in left if deps[i] <= set(done)]
        nxt = ready[0] if ready else left[0]         # a loop: keep the given order
        done.append(nxt)
        left.remove(nxt)
    return done


def check(pack, plan: list[tuple[str, object, dict]]) -> list[dict]:
    """Problems that would stop the batch: [{id, en, es}] (id None = the whole batch).
    plan: [(id, Analysis, options)]."""
    problems = []
    seen: dict[str, str] = {}
    total_add = 0
    lst = pack.ccc if pack.mode == "AE" else pack.plugin_list
    nl = 1 if (lst and lst.newline == "LF") or pack.mode == "SE" else 2
    game = [m.lower() for m in K.VANILLA_MASTERS + K.SWITCH_MASTERS + K.AE_CC_PLUGINS]
    taken = set(pack.data_files) | {e.lower() for e in pack.list_entries} | set(game)
    game_stems = {Path(m).stem.lower() for m in K.VANILLA_MASTERS + K.SWITCH_MASTERS}
    for iid, an, opts in plan:
        for old, new in final_names(an, opts):
            low = new.lower()
            stem = Path(low).stem
            locked = any(pl.get("locked") for pl in an.plugins if pl["name"] == old)
            why = None if locked else RN.check_name(new)
            if why:
                problems.append({"id": iid, "en": f"'{new}' isn't a valid plugin name ({why}).",
                                 "es": f"'{new}' no sirve como nombre de plugin ({why})."})
            if locked and an.mode == "SE" and low.endswith(".esl"):
                problems.append({"id": iid, "en": f"{new} is an ESL that can't be renamed safely, and SE can't load ESL.",
                                 "es": f"{new} es un ESL que no se puede renombrar sin riesgo, y SE no carga ESL."})
            if stem in game_stems or stem.startswith("skyrim - "):
                problems.append({"id": iid, "en": f"{new} would collide with the game's own files. Pick another name.",
                                 "es": f"{new} chocaría con los archivos del propio juego. Elige otro nombre."})
            for b in (f"{stem}.bsa", f"{stem} - textures.bsa"):
                if b in pack.data_files:
                    problems.append({"id": iid, "en": f"{b} already exists in the pack. Pick another plugin name.",
                                     "es": f"{b} ya existe en el pack. Elige otro nombre de plugin."})
            if low in seen and seen[low] != iid:
                problems.append({"id": iid, "en": f"{new} is also the name of a plugin in {seen[low]}.",
                                 "es": f"{new} también es el nombre de un plugin de {seen[low]}."})
            elif low in taken:
                problems.append({"id": iid, "en": f"{new} already exists in the pack. Pick another name.",
                                 "es": f"{new} ya existe en el pack. Elige otro nombre."})
            seen.setdefault(low, iid)
            total_add += len(new.encode("utf-8")) + nl
    if pack.mode == "AE" and pack.ccc:
        raw = pack.list_path.read_bytes() if pack.list_path else b""
        total = pack.list_bytes + total_add + (nl if raw and not raw.endswith(b"\n") else 0)
        if total > K.CCC_BYTE_LIMIT:
            problems.append({"id": None,
                             "en": f"With all of them the .ccc would reach {total} bytes, over the "
                                   f"{K.CCC_BYTE_LIMIT} limit. Shorten names or leave a mod out.",
                             "es": f"Con todos, el .ccc llegaría a {total} bytes, por encima del límite de "
                                   f"{K.CCC_BYTE_LIMIT}. Acorta nombres o deja un mod por fuera."})
    return problems


def point_masters(an, produced: dict[str, str]) -> list[str]:
    """Masters this mod lacks that an earlier mod of the batch provides:
    point them at the final name. produced: original lower -> final name.
    Returns the ones that changed name."""
    fixed = []
    for pl in an.plugins:
        still = []
        for m in pl.get("missing") or []:
            final = produced.get(m.lower())
            if final is None:
                still.append(m)
                continue
            if final != m:
                an.masters_map[m] = final
                fixed.append(m)
        pl["missing"] = still
    return fixed


def source_name(source: str) -> str:
    p = Path(source)
    return p.stem if p.suffix.lower() in (".zip", ".7z", ".rar") else p.name
