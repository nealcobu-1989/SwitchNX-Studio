"""The pack being created ("pack en creación").

A draft is an ordinary pack folder (it opens, the Doctor checks it, mods are
added, renamed and reordered as usual) with a .skynx/draft.json that says so.
Two things only a draft has:

* Mods can be marked "doesn't go" without deleting them. Their plugins leave
  the load list and their BSAs leave the ini lists (so the .ccc bytes and the
  ini lengths shown are the real ones), and where they were is remembered so
  "goes" puts them back in the same place. Their files stay in Data.
* "Create modpack" copies the draft to a new folder without the files of the
  mods that don't go and without .skynx (history, trash, workspace notes).

A draft starts either as an exact copy of another pack (same files, same
.ccc bytes, same inis) or from the Catalog.
"""
from __future__ import annotations

import json
import os
import shutil
import time
from pathlib import Path

from . import ccc as C
from . import knowledge as K
from .errors import SkynxError
from .ini import parse_ini, set_archive_list
from .pack import Pack

DRAFT_FILE = "draft.json"
ARCHIVE_KEYS = ("sResourceArchiveList", "sResourceArchiveList2", "sArchiveToLoadInMemoryList")
KEEP_RECORDS = ("mods.json", "renames.json")      # .skynx files that travel with a copy


class DraftError(SkynxError):
    pass


# ------------------------------------------------------------------ state
def _file(pack_root: Path) -> Path:
    return Path(pack_root) / ".skynx" / DRAFT_FILE


def load(pack_root: Path) -> dict | None:
    f = _file(pack_root)
    if not f.is_file():
        return None
    try:
        d = json.loads(f.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    if not isinstance(d, dict):
        return None
    d.setdefault("excluded", {})
    return d


def is_draft(pack_root: Path) -> bool:
    return load(pack_root) is not None


def _save(pack_root: Path, d: dict, tx=None) -> None:
    f = _file(pack_root)
    data = json.dumps(d, indent=1, ensure_ascii=False).encode("utf-8")
    if tx is not None:
        tx.write_bytes(f, data)
    else:
        f.parent.mkdir(parents=True, exist_ok=True)
        f.write_bytes(data)


def mark(pack_root: Path, name: str, origin: dict | None = None) -> dict:
    d = {"name": name, "created": time.strftime("%Y-%m-%d %H:%M:%S"), "origin": origin or {}, "excluded": {}}
    _save(pack_root, d)
    return d


def excluded_files(pack_root: Path) -> set[str]:
    """Lower-case names of the plugins and BSAs of mods marked "doesn't go"."""
    d = load(pack_root) or {}
    out = set()
    for rec in d.get("excluded", {}).values():
        out |= {x.lower() for x in rec.get("plugins", []) + rec.get("bsas", [])}
    return out


# ------------------------------------------------------------------ copy of a pack
def _put(src: Path, dst: Path, link: bool, stats: dict | None) -> None:
    """A hard link when it can (same drive, NTFS): the file isn't stored twice.
    Safe because nothing in the app writes into a file in place; every change
    writes a new file and replaces the old name, which leaves the other copy
    as it was. Falls back to a real copy."""
    if link:
        try:
            os.link(src, dst)
            if stats is not None:
                stats["linked"] = stats.get("linked", 0) + 1
            return
        except OSError:
            pass
    shutil.copy2(src, dst)
    if stats is not None:
        stats["copied"] = stats.get("copied", 0) + 1


def _copy_tree(src: Path, dst: Path, skip=lambda p: False, tick=None, done=None, total=None,
               link: bool = False, stats: dict | None = None) -> None:
    for dirpath, dirnames, filenames in os.walk(src):
        d = Path(dirpath)
        rel = d.relative_to(src)
        dirnames[:] = [x for x in dirnames if not skip(d / x)]
        (dst / rel).mkdir(parents=True, exist_ok=True)
        for fn in filenames:
            p = d / fn
            if skip(p):
                continue
            _put(p, dst / rel / fn, link, stats)
            if done is not None:
                done[0] += p.stat().st_size
                if tick:
                    tick(fn, done[0], total)


def _title_dirs(pack: Pack) -> list[Path]:
    out = []
    for d in (pack.base_dir, pack.aoc_dir):
        if d is not None and d.is_dir():
            out.append(d)
    return out


def _size(paths) -> int:
    n = 0
    for root in paths:
        for dirpath, _dirs, files in os.walk(root):
            for fn in files:
                try:
                    n += (Path(dirpath) / fn).stat().st_size
                except OSError:
                    pass
    return n


def _fresh_dest(dest: Path) -> Path:
    dest = Path(dest)
    if dest.exists() and any(dest.iterdir()):
        raise DraftError(f"{dest} already exists and isn't empty.", f"{dest} ya existe y no está vacía.")
    dest.mkdir(parents=True, exist_ok=True)
    return dest


def _copy_pack(pack: Pack, dest: Path, skip_files: set[str], progress=None, link: bool = False,
               records: bool = True) -> dict:
    """Copy the two title folders of `pack` into `dest`, keeping the layout
    below the pack root, leaving out Data files named in skip_files."""
    tick = progress or (lambda *a, **k: None)
    data = pack.data_dir.resolve() if pack.data_dir else None

    def skip(p: Path) -> bool:
        return bool(data and p.parent.resolve() == data and p.name.lower() in skip_files)
    dirs = _title_dirs(pack)
    total = _size(dirs)
    done = [0]
    stats = {"linked": 0, "copied": 0}
    for d in dirs:
        rel = d.relative_to(pack.layout_root or pack.root)
        _copy_tree(d, dest / rel, skip, tick, done, total, link, stats)
    sk = pack.root / ".skynx"
    for name in (KEEP_RECORDS if records else ()):
        if (sk / name).is_file():
            (dest / ".skynx").mkdir(parents=True, exist_ok=True)
            shutil.copy2(sk / name, dest / ".skynx" / name)      # records are always real copies
    return stats


def start_from_pack(src: Pack, dest: Path, name: str, progress=None, link: bool = True) -> Pack:
    """A new draft that is an exact copy of `src` (files, load list and inis
    byte for byte). The source pack is not touched."""
    if not src.base_dir:
        raise DraftError("That folder isn't a modpack.", "Esa carpeta no es un modpack.")
    dest = _fresh_dest(dest)
    try:
        stats = _copy_pack(src, dest, set(), progress, link)
    except Exception:
        shutil.rmtree(dest, ignore_errors=True)
        raise
    d = mark(dest, name, {"kind": "pack", "path": str(src.root), "name": src.root.name})
    d["files"] = stats
    _save(dest, d)
    return Pack.open(dest)


# ------------------------------------------------------------------ goes / doesn't go
def _ini_positions(pack: Pack, bsas: list[str]) -> list[dict]:
    low = {b.lower() for b in bsas}
    out = []
    for ini in pack.inis:
        for key in ARCHIVE_KEYS:
            if ini.get("Archive", key) is None:
                continue
            cur = ini.archive_list(key)
            for i, b in enumerate(cur):
                if b.lower() in low:
                    out.append({"ini": ini.path.name, "key": key, "bsa": b, "index": i,
                                "after": cur[i - 1] if i else None})
    return out


def _list_positions(pack: Pack, plugins: list[str]) -> list[dict]:
    if not pack.list_path:
        return []
    entries = C.parse_ccc(pack.list_path.read_bytes()).entries
    low = {p.lower() for p in plugins}
    out = []
    for i, e in enumerate(entries):
        if e.lstrip("#").strip().lower() in low:
            out.append({"line": e, "index": i, "after": entries[i - 1] if i else None})
    return out


def users_of(pack: Pack, plugins: list[str]) -> list[str]:
    """Plugins that load and use any of `plugins` as a master."""
    low = {p.lower() for p in plugins}
    on = {e.lower() for e, _ in pack.load_order() if not e.startswith("#")}
    return sorted(h.name for h in pack.plugins.values()
                  if h.name.lower() not in low and h.name.lower() in on
                  and any(m.lower() in low for m in h.masters))


def _full_list(d: dict, entries: list[str]) -> list[str]:
    """The load list with every mod already parked put back in its place:
    the order a new parking must remember, so mods can come back in any order."""
    out = list(entries)
    for rec in d.get("excluded", {}).values():
        for x in rec.get("list", []):
            out = _reinsert(out, x["line"], x["index"], x["after"], rec.get("list_snapshot"))
    return out


def _full_ini(d: dict, ini_name: str, key: str, cur: list[str]) -> list[str]:
    out = list(cur)
    for rec in d.get("excluded", {}).values():
        snap = (rec.get("ini_snapshot") or {}).get(f"{ini_name}|{key}")
        for x in rec.get("ini", []):
            if x["ini"] == ini_name and x["key"] == key:
                out = _reinsert(out, x["bsa"], x["index"], x["after"], snap)
    return out


def exclude(pack: Pack, row: dict, tx, force: bool = False) -> dict:
    """Mark a mod (a Mods-page row: id, name, plugins, bsas) as "doesn't go"."""
    d = load(pack.root)
    if d is None:
        raise DraftError("This pack isn't being created here.", "Este pack no está en creación.")
    rid = row["id"]
    if rid in d["excluded"]:
        return {"changed": False, "users": []}
    plugins, bsas = list(row.get("plugins") or []), list(row.get("bsas") or [])
    users = users_of(pack, plugins)
    if users and not force:
        return {"changed": False, "refused": True, "users": users}
    rec = {"name": row.get("name") or rid, "kind": row.get("kind"), "plugins": plugins, "bsas": bsas,
           "size": row.get("size") or 0, "list": _list_positions(pack, plugins),
           "ini": _ini_positions(pack, bsas), "when": time.strftime("%Y-%m-%d %H:%M:%S"),
           # the whole order as it was, so putting mods back in any order keeps it
           "list_snapshot": _full_list(d, C.parse_ccc(pack.list_path.read_bytes()).entries) if pack.list_path else [],
           "ini_snapshot": {f"{i.path.name}|{k}": _full_ini(d, i.path.name, k, i.archive_list(k))
                            for i in pack.inis for k in ARCHIVE_KEYS if i.get("Archive", k) is not None}}
    if pack.list_path and rec["list"]:
        raw = pack.list_path.read_bytes()
        tx.write_bytes(pack.list_path, C.edit_lines(raw, {x["line"]: None for x in rec["list"]}))
    by_ini: dict[str, list[dict]] = {}
    for x in rec["ini"]:
        by_ini.setdefault(x["ini"], []).append(x)
    for ini in pack.inis:
        rows = by_ini.get(ini.path.name)
        if not rows:
            continue
        raw = ini.path.read_bytes()
        out = raw
        for key in {x["key"] for x in rows}:
            gone = {x["bsa"].lower() for x in rows if x["key"] == key}
            cur = parse_ini(out).archive_list(key)
            out = set_archive_list(out, key, [c for c in cur if c.lower() not in gone])
        if out != raw:
            tx.write_bytes(ini.path, out)
    d["excluded"][rid] = rec
    _save(pack.root, d, tx)
    pack.reload()
    return {"changed": True, "users": users}


def _key(x: str) -> str:
    return x.lstrip("#").strip().lower()


def _reinsert(cur: list[str], item: str, index: int, after: str | None,
              snapshot: list[str] | None = None) -> list[str]:
    if any(c.lower() == item.lower() for c in cur):
        return cur
    out = list(cur)
    if snapshot:
        keys = [_key(x) for x in snapshot]
        if _key(item) in keys:
            at = keys.index(_key(item))
            now = [_key(c) for c in out]
            for j in range(at - 1, -1, -1):           # the nearest earlier neighbour that is there now
                if keys[j] in now:
                    out.insert(now.index(keys[j]) + 1, item)
                    return out
            for j in range(at + 1, len(keys)):        # else before the nearest later one
                if keys[j] in now:
                    out.insert(now.index(keys[j]), item)
                    return out
    if after is not None:
        for i, c in enumerate(out):
            if c.lower() == after.lower():
                out.insert(i + 1, item)
                return out
    out.insert(max(0, min(index, len(out))), item)
    return out


def masters_needed(pack: Pack, plugins: list[str], also_on: set[str] | None = None) -> list[str]:
    """Masters of `plugins` that don't load (not in the load order as active)."""
    on = {_key(e) for e, _ in pack.load_order() if not e.startswith("#")} | {p.lower() for p in plugins} \
        | set(also_on or ())
    out = []
    for p in plugins:
        h = pack.plugins.get(p.lower())
        for m in (h.masters if h else []):
            if m.lower() not in on and m not in out:
                out.append(m)
    return out


def include(pack: Pack, row_id: str, tx, force: bool = False) -> dict:
    """Put a mod marked "doesn't go" back where it was. Refused when one of
    its masters is parked too (refused=True, needs=[masters], parked=[ids])."""
    d = load(pack.root)
    if d is None or row_id not in d["excluded"]:
        return {"changed": False, "missing": []}
    rec = d["excluded"][row_id]
    needs = masters_needed(pack, rec["plugins"])
    parked = [k for k, r in d["excluded"].items() if k != row_id and any(p.lower() in {n.lower() for n in needs}
                                                                         for p in r.get("plugins", []))]
    if parked and not force:
        return {"changed": False, "refused": True, "needs": needs, "parked": parked}
    missing = [f for f in rec["plugins"] + rec["bsas"] if not (pack.data_dir / f).exists()]
    if pack.list_path and rec["list"]:
        raw = pack.list_path.read_bytes()
        entries = C.parse_ccc(raw).entries
        for x in rec["list"]:
            entries = _reinsert(entries, x["line"], x["index"], x["after"], rec.get("list_snapshot"))
        if entries != C.parse_ccc(raw).entries:
            out = C.reorder(raw, entries)
            size = C.over_limit(pack, raw, out)
            if size:
                raise DraftError(*C.limit_message(size))
            tx.write_bytes(pack.list_path, out)
    by_ini: dict[str, list[dict]] = {}
    for x in rec["ini"]:
        by_ini.setdefault(x["ini"], []).append(x)
    for ini in pack.inis:
        rows = by_ini.get(ini.path.name)
        if not rows:
            continue
        raw = ini.path.read_bytes()
        out = raw
        for x in rows:
            if parse_ini(out).get("Archive", x["key"]) is None:
                continue
            cur = parse_ini(out).archive_list(x["key"])
            snap = (rec.get("ini_snapshot") or {}).get(f"{ini.path.name}|{x['key']}")
            out = set_archive_list(out, x["key"], _reinsert(cur, x["bsa"], x["index"], x["after"], snap))
        if out != raw:
            tx.write_bytes(ini.path, out)
    del d["excluded"][row_id]
    _save(pack.root, d, tx)
    pack.reload()
    return {"changed": True, "missing": missing, "masters_missing": needs}


# ------------------------------------------------------------------ the view
def view(pack: Pack, rows: list[dict]) -> dict:
    """The Mods-page rows of a draft, with the mods that don't go put back
    where they were (unticked), and what the finished modpack would weigh."""
    d = load(pack.root) or {"excluded": {}}
    parked_files = excluded_files(pack.root)
    out = [dict(r, goes=True) for r in rows
           if r["id"] not in d["excluded"]
           and not ({f.lower() for f in r.get("plugins", []) + r.get("bsas", [])} <= parked_files
                    and (r.get("plugins") or r.get("bsas")))]
    lo = [e.lstrip("#").strip().lower() for e, _src in pack.load_order()]
    for rid, rec in d["excluded"].items():
        pos = 20_000
        for x in rec.get("list", [])[:1]:
            after = (x.get("after") or "").lstrip("#").strip().lower()
            pos = lo.index(after) + 0.5 if after in lo else x["index"]
        out.append({"id": rid, "name": rec.get("name") or rid, "kind": rec.get("kind") or "mod",
                    "plugins": rec.get("plugins", []), "bsas": rec.get("bsas", []),
                    "size": sum((pack.data_dir / f).stat().st_size for f in rec.get("plugins", []) + rec.get("bsas", [])
                                if (pack.data_dir / f).exists()),
                    "pos": pos, "goes": False})
    out.sort(key=lambda r: r.get("pos", 20_000))
    skip = excluded_files(pack.root)
    size = sum(p.stat().st_size for p in pack.data_dir.iterdir()
               if p.is_file() and p.name.lower() not in skip) if pack.data_dir else 0
    raw = pack.list_path.read_bytes() if pack.list_path and pack.list_path.exists() else b""
    inis = []
    for ini in pack.inis:
        for key in ARCHIVE_KEYS:
            if ini.get("Archive", key) is not None:
                inis.append({"ini": ini.path.name, "key": key, "chars": len(", ".join(ini.archive_list(key)))})
    top = max(inis, key=lambda x: x["chars"]) if inis else None
    return {"name": d.get("name"), "origin": d.get("origin") or {}, "rows": out,
            "goes": sum(1 for r in out if r["goes"]), "total": len(out),
            "ccc_bytes": pack.list_bytes if raw else 0, "ccc_limit": K.CCC_BYTE_LIMIT if pack.mode == "AE" else None,
            "ini_top": top, "ini_limit": 1024, "data_size": size,
            "plugins": len([n for n in pack.plugins if n not in skip])}


# ------------------------------------------------------------------ create the modpack
def check_masters(pack: Pack) -> set[str]:
    """Refuse when a plugin that goes needs a master that doesn't. Returns the
    lower-case names of the files that don't go."""
    skip = excluded_files(pack.root)
    active = [_key(e) for e, _ in pack.load_order() if not e.startswith("#")]
    broken = []
    for low in active:
        if low in skip:
            continue
        need = [m for m in masters_needed(pack, [pack.plugins[low].name]) if m.lower() in skip] \
            if low in pack.plugins else []
        if need:
            broken.append(f"{pack.plugins[low].name} → {', '.join(need)}")
    if broken:
        raise DraftError("These go but their masters don't: " + "; ".join(broken),
                         "Estos van pero sus masters no: " + "; ".join(broken))
    return skip


def create_modpack(pack: Pack, dest: Path, progress=None, link: bool = True, records: bool = True,
                   inside_ok: bool = False) -> dict:
    """Copy the draft to `dest` without the mods that don't go and without
    .skynx history. The draft stays as it is, ready for the next version.
    inside_ok: a project packs into its own Switch folder (project.build)."""
    dest_abs = Path(os.path.abspath(dest))
    root_abs = Path(os.path.abspath(pack.root))
    if not inside_ok and (dest_abs == root_abs or root_abs in dest_abs.parents):
        raise DraftError("The modpack can't go inside the pack being created.",
                         "El modpack no puede quedar dentro del pack en creación.")
    skip = check_masters(pack)
    dest = _fresh_dest(dest)
    try:
        stats = _copy_pack(pack, dest, skip, progress, link, records)
    except Exception:
        shutil.rmtree(dest, ignore_errors=True)
        raise
    out = Pack.open(dest)
    raw = out.list_path.read_bytes() if out.list_path and out.list_path.exists() else b""
    return {"dest": str(dest), "left_out": sorted(skip), "ccc_bytes": len(raw),
            "plugins": len(out.plugins), "bsas": len(out.bsas), "size": out.data_size(),
            "linked": stats.get("linked", 0), "copied": stats.get("copied", 0)}
