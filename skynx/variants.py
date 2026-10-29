"""What to leave out of a mod download before using it.

- Junk that zip tools on a Mac add (``__MACOSX/``, ``._Name.esp``), ``.DS_Store``,
  ``Thumbs.db``: never a real file of the mod. A ``._Mod.esp`` copied into Data
  ends up in the load list and the game can't read it.
- Versions side by side: many Switch mods ship ``Mod_AE/`` and ``Mod_SE/`` (or
  "1K"/"2K") folders holding the same plugin or BSA (versions made only of loose
  files aren't told apart). Only one goes in. The one for the
  pack's edition is picked; without a clue, the first one, with a note.

Works on relative paths, so the same answer comes from an archive's member list
(nothing extracted) or from a folder.
"""
from __future__ import annotations

import re
from pathlib import Path, PurePosixPath

PLUGIN_EXT = (".esp", ".esm", ".esl")
JUNK_NAMES = {".ds_store", "thumbs.db", "desktop.ini"}
_AE = re.compile(r"(?:^|[^a-z0-9])(ae|anniversary(?:\s*edition)?)(?:[^a-z0-9]|$)")
_SE = re.compile(r"(?:^|[^a-z0-9])(se|sse|special\s*edition)(?:[^a-z0-9]|$)")


def is_junk(rel: str) -> bool:
    parts = [p for p in str(rel).replace("\\", "/").split("/") if p]
    if not parts:
        return False
    if any(p.lower() == "__macosx" for p in parts):
        return True
    name = parts[-1]
    return name.startswith("._") or name.lower() in JUNK_NAMES


def _mod_dirs(files: list[str]) -> dict[str, dict]:
    """Folders (relative, "" = top) that directly hold plugins or BSAs."""
    out: dict[str, dict] = {}
    for f in files:
        if is_junk(f):
            continue
        p = PurePosixPath(f.replace("\\", "/"))
        ext = p.suffix.lower()
        if ext not in PLUGIN_EXT and ext != ".bsa":
            continue
        d = str(p.parent) if str(p.parent) != "." else ""
        if d.count("/") > 4:
            continue
        e = out.setdefault(d, {"plugins": set(), "bsas": set()})
        e["plugins" if ext in PLUGIN_EXT else "bsas"].add(p.name.lower())
    return out


def _within(d: str, other: str) -> bool:
    return other == "" or d == other or d.startswith(other + "/")


FILES = "::files"     # a skip entry for the plugins/BSAs directly in a folder, not its subfolders


def _shared(a: dict, b: dict) -> bool:
    """Two folders hold versions of the same thing: a plugin with the same name
    (Mod.esl and Mod.esp count as the same), or a BSA with the same name."""
    pa = {n.rsplit(".", 1)[0] for n in a["plugins"]}
    pb = {n.rsplit(".", 1)[0] for n in b["plugins"]}
    return bool(pa & pb) or bool(a["bsas"] & b["bsas"])


def _edition_of(label: str) -> str | None:
    low = label.lower()
    ae, se = bool(_AE.search(low)), bool(_SE.search(low))
    return "AE" if ae and not se else "SE" if se and not ae else None


def _rel_label(d: str, others: list[str]) -> str:
    """The part of a folder's path that differs from the others' (so a parent
    folder called "Mod SE" doesn't count for both versions)."""
    parts = [x.split("/") for x in others + [d]]
    common = 0
    while all(len(p) > common for p in parts) and len({p[common] for p in parts}) == 1:
        common += 1
    return "/".join(d.split("/")[common:])


def _pick(opts: list[str], labels: dict[str, str], want: str) -> tuple[str, str]:
    eds = {d: _edition_of(labels[d]) for d in opts}
    ae = [d for d in opts if eds[d] == "AE"]
    se = [d for d in opts if eds[d] == "SE"]
    if want == "AE" and len(ae) == 1:
        return ae[0], "edition"
    if want == "SE" and len(se) == 1:
        return se[0], "edition"
    if want == "AE" and not ae and len(se) == 1:
        return se[0], "edition"              # SE builds load in AE
    if want == "SE" and not se:
        rest = [d for d in opts if eds[d] != "AE"]
        if len(rest) == 1 and ae:
            return rest[0], "edition"         # the one that isn't marked AE
    return opts[0], "first"


def choose(files: list[str], edition: str | None = None) -> dict:
    """files: relative paths of the mod's files. Returns
    {"skip": [folders left out], "groups": [{"options", "chosen", "how"}]}.
    how: "edition" (matched the pack's edition), "first" (no clue) or "option"
    (a folder inside the mod that would replace some of its files)."""
    dirs = _mod_dirs(files)
    names = sorted(dirs)
    want = (edition or "").upper()
    # folders that share a plugin (or, without plugins, a BSA) are versions of each other
    parent = {d: d for d in names}

    def find(x):
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x
    nested: list[tuple[str, str]] = []           # (inner folder, the folder it would overwrite)
    for i, a in enumerate(names):
        for b in names[i + 1:]:
            if not _shared(dirs[a], dirs[b]):
                continue
            if _within(a, b) or _within(b, a):
                inner, outer = (a, b) if _within(a, b) else (b, a)
                nested.append((inner, outer))
            else:
                parent[find(a)] = find(b)
    out = {"skip": [], "groups": []}
    for inner, outer in nested:
        if inner in out["skip"]:
            continue
        label = inner[len(outer):].lstrip("/") if outer else inner
        ed = _edition_of(label)
        if ed:
            # "Mod.esp" at the top and "SE Version/Mod.esp" inside: two editions
            top = (outer + FILES) if outer else FILES
            labels = {top: "AE" if ed == "SE" else "SE", inner: label}
            pick, how = _pick([top, inner], labels, want)
            if pick == top:
                out["skip"].append(inner)
            else:
                out["skip"].append(top)
            out["groups"].append({"options": [outer or "", inner], "chosen": outer if pick == top else inner,
                                  "how": how if how == "edition" else "first"})
        else:
            out["skip"].append(inner)
            out["groups"].append({"options": [outer, inner], "chosen": outer, "how": "option"})
    groups: dict[str, list[str]] = {}
    for d in names:
        if not any(d == s or d.startswith(s + "/") for s in out["skip"] if not s.endswith(FILES)):
            groups.setdefault(find(d), []).append(d)
    for opts in groups.values():
        if len(opts) < 2:
            continue
        opts = sorted(opts, key=str.lower)
        labels = {d: _rel_label(d, [o for o in opts if o != d]) for d in opts}
        pick, how = _pick(opts, labels, want)
        out["skip"] += [d for d in opts if d != pick]
        out["groups"].append({"options": opts, "chosen": pick, "how": how})
    return out


def skipped(rel: str, skip: list[str]) -> bool:
    """A file to leave out: junk, or inside a version folder not chosen."""
    if is_junk(rel):
        return True
    r = str(rel).replace("\\", "/")
    parent = r.rsplit("/", 1)[0] if "/" in r else ""
    for s in skip:
        if s.endswith(FILES):
            if parent == s[:-len(FILES)]:
                return True
        elif s and (r == s or r.startswith(s + "/")):
            return True
    return False


def note(res: dict) -> tuple[str, str] | None:
    """(en, es) note about the versions picked, or None."""
    if not res.get("groups"):
        return None
    en, es = [], []
    for g in res["groups"]:
        others = ", ".join(PurePosixPath(o).name or "(top)" for o in g["options"] if o != g["chosen"])
        name = PurePosixPath(g["chosen"]).name or "(top)"
        others_es = ", ".join(PurePosixPath(o).name or "la carpeta principal" for o in g["options"] if o != g["chosen"])
        name_es = PurePosixPath(g["chosen"]).name or "la carpeta principal"
        if g["how"] == "option":
            opt = PurePosixPath(g["options"][1]).name
            en.append(f"It has an optional folder that replaces some of its files ({opt}); I left it out. "
                      "If you want it, extract the archive and add that option by hand.")
            es.append(f"Trae una carpeta opcional que reemplaza archivos del mod ({opt}); la dejé por fuera. "
                      "Si la quieres, extrae el comprimido y agrega esa opción a mano.")
        elif g["how"] == "edition":
            en.append(f"It has several versions; I used the one for this edition ({name}) and left out {others}.")
            es.append(f"Trae varias versiones; usé la de esta edición ({name_es}) y dejé por fuera {others_es}.")
        else:
            en.append(f"It has several versions ({name}, {others}); I used {name}. If you wanted another, "
                      "extract the archive and add that folder.")
            es.append(f"Trae varias versiones ({name_es}, {others_es}); usé {name_es}. Si querías otra, extrae el "
                      "comprimido y agrega esa carpeta.")
    return " ".join(en), " ".join(es)


def files_of(folder: Path) -> list[str]:
    folder = Path(folder)
    return [p.relative_to(folder).as_posix() for p in folder.rglob("*") if p.is_file()]
