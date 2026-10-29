"""The mod workshop: work on single mods, or join several into a suite, without
a modpack.

A bench is a small private pack in <Library>\\Workshop\\<name> (no Creation
Club lines, no USSEP) with a .skynx/bench.json. Everything that already works
on packs works on it: converting, renaming with all its references, BSA
extraction, xEdit, history and undo. When the work is done, save_mod() copies
the plugins and BSAs to <Library>\\Converted\\<name> with a skynx-mod.json, so
the Library and the Catalog see it as a mod ready for any pack.

merge_bsas() joins the BSAs of every mod on the bench into one (or a few, when
they are big) named after a plugin of the suite, so they load with it: fewer
archives for the Switch and shorter ini lists. Files are taken in load order,
so when two mods carry the same file the one that loads later wins, as in game.
Voice and FaceGen folders named after other plugins of the bench can be moved
to the anchor's name (needed after a plugin merge).
"""
from __future__ import annotations

import json
import os
import shutil
import tempfile
import time
from pathlib import Path

from . import ccc as C
from . import knowledge as K
from .bsa import read_bsa, write_bsa
from .builder import CONVERTED_INFO, add_mod, create_project, load_mods
from .errors import SkynxError
from .ini import parse_ini, set_archive_list
from .pack import PLUGIN_EXT, Pack
from .rename import NAME_FOLDERS

BENCH_FILE = "bench.json"
BSA_SPLIT = 1_900_000_000
ARCHIVE_KEYS = ("sResourceArchiveList", "sResourceArchiveList2", "sArchiveToLoadInMemoryList")
MINIMAL_INI = ("[General]\r\nsLanguage=ENGLISH\r\n[Archive]\r\nsResourceArchiveList=\r\n"
               "sResourceArchiveList2=\r\n")


class WorkshopError(SkynxError):
    pass


def _bad_name(name: str) -> bool:
    return not name.strip() or any(c in name for c in '<>:"/\\|?*') or name.strip(" .") != name.strip()


# ------------------------------------------------------------------ the bench
def load(root: Path) -> dict | None:
    f = Path(root) / ".skynx" / BENCH_FILE
    try:
        d = json.loads(f.read_text(encoding="utf-8"))
        return d if isinstance(d, dict) else None
    except (OSError, ValueError):
        return None


def is_bench(root: Path) -> bool:
    return load(root) is not None


def _write_info(root: Path, d: dict) -> None:
    f = Path(root) / ".skynx" / BENCH_FILE
    f.parent.mkdir(parents=True, exist_ok=True)
    f.write_text(json.dumps(d, indent=1, ensure_ascii=False), encoding="utf-8")


def new_bench(dest: Path, name: str, kind: str, edition: str = "AE", inis_dir: Path | None = None) -> Pack:
    """An empty bench. kind: "convert", "edit", "suite" or "merge" (only a
    label for the page). The console inis are used when there are some; else
    a minimal pair is written (a bench never goes to the console)."""
    dest = Path(dest)
    if dest.exists() and any(dest.iterdir()):
        raise WorkshopError(f"{dest} already exists.", f"{dest} ya existe.")
    edition = "SE" if str(edition).upper() == "SE" else "AE"
    base = Path(inis_dir) if inis_dir else None
    if base and base.is_dir() and any(p.name.lower() == "skyrim.ini" for p in base.iterdir()):
        create_project(dest, edition, base, "none")
    else:
        romfs = dest / K.TITLE_BASE / "romfs"
        (romfs / "Data").mkdir(parents=True)
        (romfs / "Skyrim.ini").write_text(MINIMAL_INI, encoding="utf-8")
        (romfs / "Skyrim_en.ini").write_text(MINIMAL_INI, encoding="utf-8")
        if edition == "AE":
            (dest / K.TITLE_AOC / "romfs").mkdir(parents=True)
            (dest / K.TITLE_AOC / "romfs" / "Skyrim_aoc.ccc").write_bytes(b"")
        else:
            (romfs / "Plugins").write_bytes(b"")
    _write_info(dest, {"name": name, "kind": kind, "edition": edition,
                       "created": time.strftime("%Y-%m-%d %H:%M:%S"), "sources": []})
    return Pack.open(dest)


def free_name(folder: Path, name: str) -> Path:
    folder = Path(folder)
    out, n = folder / name, 2
    while out.exists():
        out, n = folder / f"{name} ({n})", n + 1
    return out


def bring(bench: Pack, sources: list, progress=None) -> list[dict]:
    """Put mods (folders or archives of Switch mods) on the bench, in order.
    Returns one report per source: added files, or the reason it couldn't."""
    tick = progress or (lambda *a, **k: None)
    out = []
    info = load(bench.root) or {}
    for i, src in enumerate(sources):
        src = Path(src)
        tick(src.name, i, len(sources))
        try:
            rep = add_mod(bench, src)
            out.append({"source": str(src), "ok": True, "mod_id": rep.mod_id, "added": rep.added,
                        "notes": [list(x) for x in rep.notes]})
            info.setdefault("sources", []).append(str(src))
        except SkynxError as e:
            out.append({"source": str(src), "ok": False, "text": [e.en, e.es]})
        bench = Pack.open(bench.root)
    _write_info(bench.root, info)
    return out


# ------------------------------------------------------------------ save to the Library
def _ini_keys(pack: Pack, bsas: list[str]) -> dict[str, str]:
    low = {b.lower(): b for b in bsas}
    out = {}
    for ini in pack.inis:
        for key in ARCHIVE_KEYS:
            if key == "sArchiveToLoadInMemoryList" or ini.get("Archive", key) is None:
                continue
            for b in ini.archive_list(key):
                if b.lower() in low:
                    out.setdefault(low[b.lower()], key)
    return out


def save_mod(bench: Pack, dest_root: Path, name: str, replace: Path | None = None,
             trash_root: Path | None = None) -> dict:
    """Copy the bench's plugins and BSAs to dest_root/<name> with a
    skynx-mod.json. replace: an existing mod folder to put this in place of
    (the old one goes to trash_root, never deleted)."""
    if _bad_name(name):
        raise WorkshopError("The name can't be empty or have < > : \" / \\ | ? *",
                            "El nombre no puede estar vacío ni tener < > : \" / \\ | ? *")
    bench = Pack.open(bench.root)
    if not bench.data_dir:
        raise WorkshopError("The bench has no Data folder.", "La mesa no tiene carpeta Data.")
    order = [e.lstrip("#").strip() for e, _src in bench.load_order()]
    plugins = sorted((h.name for h in bench.plugins.values()),
                     key=lambda n: order.index(n) if n in order else 10_000)
    bsas = sorted(p.name for p in bench.bsas.values())
    if not plugins and not bsas:
        raise WorkshopError("There's nothing on the bench to save.", "No hay nada en la mesa para guardar.")
    loose = list(bench.loose_dirs)
    records = load_mods(bench)
    comps = [{"name": k, "source": r.get("source"), "converted": r.get("converted")} for k, r in records.items()]
    info = {"name": name, "plugins": plugins, "bsas": bsas, "ini_keys": _ini_keys(bench, bsas),
            "mode": bench.mode, "saved": time.strftime("%Y-%m-%d %H:%M:%S")}
    if len(comps) == 1:
        if comps[0]["converted"]:
            info["converted"] = comps[0]["converted"]
        if isinstance(comps[0]["source"], dict):
            info["source"] = comps[0]["source"]
    elif comps:
        info["suite"] = [{"name": c["name"], "source": c["source"]} for c in comps]
        info["source"] = {"kind": "suite", "components": [c["name"] for c in comps]}
    b = load(bench.root) or {}
    if b.get("merged"):
        info["merged"] = b["merged"]
    dest_root = Path(dest_root)
    dest_root.mkdir(parents=True, exist_ok=True)
    tmp = Path(tempfile.mkdtemp(prefix=".skynx-save-", dir=str(dest_root)))
    try:
        for f in plugins + bsas:
            shutil.copy2(bench.data_dir / f, tmp / f)
        (tmp / CONVERTED_INFO).write_text(json.dumps(info, indent=1, ensure_ascii=False), encoding="utf-8")
        parked = None
        if replace is not None:
            replace = Path(replace)
            if replace.exists():
                tr = Path(trash_root or dest_root / ".trash")
                tr.mkdir(parents=True, exist_ok=True)
                parked = free_name(tr, time.strftime("%Y%m%d-%H%M%S-") + replace.name)
                os.replace(replace, parked)
            dest = replace
        else:
            dest = free_name(dest_root, name)
        try:
            os.replace(tmp, dest)
        except OSError:
            if parked is not None and not dest.exists():
                os.replace(parked, dest)            # put the old one back where it was
            raise
    except Exception:
        shutil.rmtree(tmp, ignore_errors=True)
        raise
    return {"dest": str(dest), "plugins": plugins, "bsas": bsas, "loose_left": loose,
            "size": sum((dest / f).stat().st_size for f in plugins + bsas)}


# ------------------------------------------------------------------ join BSAs
def _bsa_order(pack: Pack) -> list[str]:
    """BSAs in the order the game reads them: ini lists first (in list order),
    then the ones loaded by plugins, in plugin order. Later ones win."""
    out: list[str] = []
    have = {k: p.name for k, p in pack.bsas.items()}
    lists = pack.archive_lists()                # the language ini's list is the one that counts
    for key in ("sResourceArchiveList", "sResourceArchiveList2"):
        for b in lists.get(key, []):
            n = have.get(b.lower())
            if n and n not in out:
                out.append(n)
    merged = (load(pack.root) or {}).get("merged") or {}

    def by_stem(stem: str) -> list[str]:
        stem = stem.lower()
        return sorted((n for k, n in have.items() if Path(k).stem in (stem, stem + " - textures")),
                      key=lambda x: (" - textures" in x.lower(), x.lower()))
    for e, _src in pack.load_order():
        if e.startswith("#"):
            continue
        names = []
        if merged.get("plugin") and e.lower() == merged["plugin"].lower():
            for c in merged.get("components", []):          # the merged plugins' BSAs, in their order
                names += by_stem(Path(c).stem)
        names += [p.name for p in sorted(pack.bsas_for_plugin(e), key=lambda x: (" - textures" in x.name.lower(), x.name.lower()))]
        for n in names:
            if n not in out:
                out.append(n)
    out += sorted(n for n in have.values() if n not in out)      # loaded by nothing: last, still kept
    return out


def _retarget(path: str, renames: dict[str, str]) -> str:
    """Voice / FaceGen folders named after a plugin that was merged."""
    if not renames:
        return path
    parts = path.split("\\")
    for root in NAME_FOLDERS:
        rp = root.split("\\")
        if parts[:len(rp)] == rp and len(parts) > len(rp) and parts[len(rp)] in renames:
            parts[len(rp)] = renames[parts[len(rp)]].lower()
    return "\\".join(parts)


def merge_plan(bench: Pack, anchor: str | None = None, retarget: dict[str, str] | None = None) -> dict:
    """What joining the BSAs would do, without doing it. anchor: a plugin of
    the bench, None for the default (the merged plugin, else the first one),
    or "" for none (the joined BSAs are listed in the ini)."""
    order = _bsa_order(bench)
    active = [e for e, _ in bench.load_order() if not e.startswith("#") and e.lower() in bench.plugins]
    ini = anchor == ""                 # "": no plugin, the result is listed in the ini
    anchor = None if ini else anchor
    if anchor is None and active and not ini:
        merged = ((load(bench.root) or {}).get("merged") or {}).get("plugin")
        anchor = merged if merged and merged.lower() in bench.plugins else active[0]
    if anchor is not None and anchor.lower() not in bench.plugins:
        raise WorkshopError(f"{anchor} isn't on the bench.", f"{anchor} no está en la mesa.")
    ren = {k.lower(): v for k, v in (retarget or {}).items()}
    seen: dict[str, str] = {}
    overlaps: dict[str, list[str]] = {}
    files = 0
    size = 0
    tex = 0
    for name in order:
        arc = read_bsa(bench.data_dir / name)
        for e in arc.entries:
            p = _retarget(e.path.lower(), ren)
            if p in seen and seen[p] != name:
                overlaps.setdefault(p, [seen[p]]).append(name)
            else:
                files += 1
            seen[p] = name
            size += e.size
            if p.startswith("textures\\"):
                tex += e.size
    stem = Path(anchor).stem if anchor else None
    return {"order": order, "anchor": anchor, "plugins": active, "files": files, "size": size,
            "textures": tex, "overlaps": [{"path": k, "in": v, "wins": v[-1]} for k, v in sorted(overlaps.items())],
            "result": ([stem + ".bsa", stem + " - Textures.bsa"] if stem else []),
            "ini_loaded": anchor is None}


def merge_bsas(bench: Pack, tx, anchor: str | None = None, name: str | None = None,
               retarget: dict[str, str] | None = None, compress: bool | None = None, progress=None) -> dict:
    """Join every BSA on the bench into <anchor>.bsa and <anchor> - Textures.bsa
    (more numbered parts when they pass ~1.9 GB). Without a plugin, the result
    is loaded from the ini as <name>M.bsa / <name>T.bsa. The old archives go to
    the bench's trash through tx (undoable)."""
    tick = progress or (lambda *a, **k: None)
    plan = merge_plan(bench, anchor, retarget)
    order, anchor = plan["order"], plan["anchor"]
    if len(order) < 2 and not retarget:
        raise WorkshopError("There's only one BSA; nothing to join.", "Solo hay un BSA; no hay nada que juntar.")
    if anchor is None:
        base = (name or (load(bench.root) or {}).get("name") or "Suite").strip()
        if not base or any(c in base for c in '\\/:*?"<>|,') or base.lower().startswith("skyrim"):
            raise WorkshopError(f"'{base}' can't be a BSA name for the ini (no commas or symbols, not starting with Skyrim).",
                                f"'{base}' no sirve como nombre de BSA en el ini (sin comas ni símbolos, sin empezar por Skyrim).")
        main_name, tex_name = base + "M", base + "T"
    else:
        main_name, tex_name = Path(anchor).stem, Path(anchor).stem + " - Textures"
    ren = {k.lower(): v for k, v in (retarget or {}).items()}
    work = Path(tempfile.mkdtemp(prefix="skynx-join-", dir=str(bench.root)))
    try:
        latest: dict[str, tuple[str, Path]] = {}      # archive path -> (spelling, temp file)
        any_compressed = False
        n = 0
        for i, bname in enumerate(order):
            tick(bname, i, len(order))
            src = bench.data_dir / bname
            arc = read_bsa(src)
            any_compressed |= arc.compressed_default
            with src.open("rb") as f:
                for e in arc.entries:
                    path = _retarget(e.path.lower(), ren)
                    data = arc.read_file(e, f)
                    if path.endswith(".nif") and path.startswith("meshes\\actors\\character\\facegendata\\facegeom\\") and ren:
                        from . import nif as NIF
                        try:
                            data, _k = NIF.replace_texture_folders(data, ren)
                        except NIF.NifError:
                            pass
                    tmpf = work / f"{n}"
                    n += 1
                    tmpf.write_bytes(data)
                    old = latest.get(path)
                    if old:
                        old[1].unlink(missing_ok=True)
                    latest[path] = (path, tmpf)
        tex = [(p, f) for p, f in latest.values() if p.startswith("textures\\")]
        other = [(p, f) for p, f in latest.values() if not p.startswith("textures\\")]
        comp = any_compressed if compress is None else bool(compress)
        written: list[str] = []

        def chunks(items):
            out, cur, size = [], [], 0
            for rel, p in sorted(items):
                s = p.stat().st_size
                if cur and size + s > BSA_SPLIT:
                    out.append(cur)
                    cur, size = [], 0
                cur.append((rel, p))
                size += s
            if cur:
                out.append(cur)
            return out
        staged = []
        for items, base in ((other, main_name), (tex, tex_name)):
            for k, ch in enumerate(chunks(items)):
                fname = f"{base}{k + 1 if k else ''}.bsa"
                outp = work / ("out-" + fname)
                write_bsa(ch, outp, compress=comp)
                staged.append((fname, outp))
        # parts 2, 3... can't load by the plugin's name: they go in the ini lists (checked first)
        from .ini import ARCHIVE_LIST_LIMIT
        need_ini = [f for f, _ in staged] if anchor is None else \
            [f for f, _ in staged if Path(f).stem.lower() not in (main_name.lower(), tex_name.lower())]
        old_low = {b.lower() for b in order}
        new_lists: dict[str, bytes] = {}
        for ini in bench.inis:
            raw = ini.path.read_bytes()
            out = raw
            for key in ("sResourceArchiveList", "sResourceArchiveList2"):
                if parse_ini(out).get("Archive", key) is None:
                    continue
                cur = [c for c in parse_ini(out).archive_list(key) if c.lower() not in old_low]
                want = [w for w in need_ini if (w.startswith(tex_name) if key.endswith("2") else not w.startswith(tex_name))]
                cur += [w for w in want if w.lower() not in {c.lower() for c in cur}]
                if len(", ".join(cur)) > ARCHIVE_LIST_LIMIT:
                    raise WorkshopError(f"{key} in {ini.path.name} would pass {ARCHIVE_LIST_LIMIT} characters.",
                                        f"{key} en {ini.path.name} pasaría de {ARCHIVE_LIST_LIMIT} caracteres.")
                out = set_archive_list(out, key, cur)
            if out != raw:
                new_lists[ini.path.name] = out
        # old archives out (history keeps them), new ones in; same name: replaced in place
        new_low = {f.lower() for f, _ in staged}
        for bname in order:
            if bname.lower() not in new_low:
                tx.trash(bench.data_dir / bname)
        for fname, outp in staged:
            target = bench.data_dir / fname
            if target.exists():
                tx.replace_with(target, outp)
            else:
                tx.copy_in(outp, target)
            written.append(fname)
        # ini lists: old names out, new parts in (computed and checked above)
        for ini in bench.inis:
            if ini.path.name in new_lists:
                tx.write_bytes(ini.path, new_lists[ini.path.name])
        info = load(bench.root) or {}
        info["joined"] = {"from": order, "into": written, "anchor": anchor,
                          "overlaps": len(plan["overlaps"]), "when": time.strftime("%Y-%m-%d %H:%M:%S")}
        tx.write_bytes(bench.root / ".skynx" / BENCH_FILE, json.dumps(info, indent=1, ensure_ascii=False).encode("utf-8"))
    finally:
        shutil.rmtree(work, ignore_errors=True)
    return {"from": order, "into": written, "anchor": anchor, "overlaps": plan["overlaps"],
            "files": len(latest)}


# ------------------------------------------------------------------ plugin merges (zMerge)
def merged_components(plugin_path: Path) -> list[str]:
    from .loot import merged_components as mc
    try:
        return list(mc(Path(plugin_path)))
    except Exception:  # noqa: BLE001
        return []


def bring_merge(bench: Pack, folder: Path, tx) -> dict:
    """Take a zMerge / Merge Plugins result (a folder with the merged plugin
    and whatever it produced) onto the bench. The plugins it says it contains
    leave the bench (their files go to the trash through tx); their voice and
    FaceGen folders can then follow the merged name when the BSAs are joined."""
    folder = Path(folder)
    if not folder.is_dir():
        raise WorkshopError(f"{folder} isn't a folder.", f"{folder} no es una carpeta.")
    cands = [p for p in folder.iterdir() if p.is_file() and p.suffix.lower() in PLUGIN_EXT]
    merged = [(p, merged_components(p)) for p in cands]
    merged = [m for m in merged if m[1]] or [(p, []) for p in cands]
    if len(merged) != 1:
        raise WorkshopError("I expected one merged plugin in that folder; found: " + ", ".join(p.name for p in cands),
                            "Esperaba un plugin fusionado en esa carpeta; encontré: " + ", ".join(p.name for p in cands))
    plugin, comps = merged[0]
    if (bench.data_dir / plugin.name).exists():
        raise WorkshopError(f"{plugin.name} is already on the bench.", f"{plugin.name} ya está en la mesa.")
    on_bench = {k: h.name for k, h in bench.plugins.items()}
    inside = [on_bench[c.lower()] for c in comps if c.lower() in on_bench]
    # 1. the merged plugin and the extra files the merge produced
    extras = []
    tx.copy_in(plugin, bench.data_dir / plugin.name)
    for p in folder.rglob("*"):
        if not p.is_file() or p == plugin:
            continue
        rel = p.relative_to(folder)
        top = rel.parts[0].lower()
        if p.suffix.lower() == ".bsa" and len(rel.parts) == 1:
            tx.copy_in(p, bench.data_dir / p.name)
            extras.append(p.name)
        elif top in ("seq", "strings") and len(rel.parts) == 2:
            tx.copy_in(p, bench.data_dir / rel)
            extras.append(str(rel))
    # 2. the components leave the load list and the bench (their BSAs stay to be joined)
    path = bench.list_path
    if path:
        raw = path.read_bytes()
        entries = [e for e in C.parse_ccc(raw).entries if e.lstrip("#").strip().lower() not in {i.lower() for i in inside}]
        entries.append(plugin.name)
        tx.write_bytes(path, C.reorder(raw, entries))
    for name in inside:
        tx.trash(bench.data_dir / name)
    info = load(bench.root) or {}
    info["merged"] = {"plugin": plugin.name, "components": comps, "inside": inside, "extras": extras,
                      "from": str(folder), "when": time.strftime("%Y-%m-%d %H:%M:%S")}
    tx.write_bytes(bench.root / ".skynx" / BENCH_FILE, json.dumps(info, indent=1, ensure_ascii=False).encode("utf-8"))
    return {"plugin": plugin.name, "components": comps, "inside": inside, "extras": extras,
            "missing": [c for c in comps if c.lower() not in on_bench]}
