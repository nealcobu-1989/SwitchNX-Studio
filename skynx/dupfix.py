"""Resolving duplicates the Doctor finds: keep them, or take one copy out.

Every action goes through the history Transaction, so it can be undone.

- keep_only(pack, keep, remove, tx): several copies of the same plugin (same
  bytes, or the same name before and after Google Drive's damage). The others
  leave the load list (the kept one takes the first copy's line if it wasn't in
  the list), plugins that use them as a master are pointed at the kept one,
  their own BSAs leave the inis, and their files go to the project trash.
- take_out_loose(pack, name, tx): a mod that is also inside a merged plugin.
  With no plugin depending on it, it's removed like above. If other plugins use
  it as a master, it becomes an empty placeholder (header and masters only),
  the way merged packs usually ship, so those patches keep loading.
- delete_copy(pack, name, tx): a copy that isn't in the load list: its files
  go to the trash.
- drop_bsa(pack, name, tx): one of two BSAs with the same content: out of the
  inis and into the trash.
- ignore / unignore: "keep both"; the Doctor stops warning about that finding.
"""
from __future__ import annotations

import json
import struct
from pathlib import Path

from . import ccc as C
from .errors import SkynxError
from .history import Transaction
from .ini import parse_ini, set_archive_list
from .pack import Pack
from .rename import rename_masters

ARCHIVE_KEYS = ("sResourceArchiveList", "sResourceArchiveList2", "sArchiveToLoadInMemoryList")


class DupFixError(SkynxError):
    pass


# ---------------------------------------------------------------- "keep both"
def ignore_file(pack: Pack) -> Path:
    return Path(pack.root) / ".skynx" / "doctor-ignore.json"


def load_ignored(pack: Pack) -> set[str]:
    f = ignore_file(pack)
    try:
        data = json.loads(f.read_text(encoding="utf-8")) if f.exists() else {}
    except (OSError, ValueError):
        return set()
    return {str(x) for x in data.get("ids", [])} if isinstance(data, dict) else set()


def _save_ignored(pack: Pack, ids: set[str], tx: Transaction) -> None:
    f = ignore_file(pack)
    f.parent.mkdir(parents=True, exist_ok=True)
    tx.write_bytes(f, json.dumps({"ids": sorted(ids)}, indent=1, ensure_ascii=False).encode("utf-8"))


def ignore(pack: Pack, finding_id: str, tx: Transaction) -> None:
    ids = load_ignored(pack)
    ids.add(finding_id)
    _save_ignored(pack, ids, tx)


def unignore(pack: Pack, finding_ids: list[str] | None, tx: Transaction) -> None:
    ids = load_ignored(pack)
    ids = set() if finding_ids is None else ids - set(finding_ids)
    _save_ignored(pack, ids, tx)


# ---------------------------------------------------------------- helpers
def _plugin(pack: Pack, name: str):
    h = pack.plugins.get(name.lower())
    if h is None:
        raise DupFixError(f"{name} isn't in Data anymore.", f"{name} ya no está en Data.")
    return h


def _own_bsas(pack: Pack, name: str, keep: list[str]) -> list[Path]:
    """BSAs that load with `name` and not with any of the kept plugins."""
    kept = {b.name.lower() for k in keep for b in pack.bsas_for_plugin(k)}
    return [b for b in pack.bsas_for_plugin(name) if b.name.lower() not in kept]


def ini_listed(pack: Pack) -> set[str]:
    """BSAs some ini loads on their own (they may carry files other plugins,
    such as a merge, rely on), lowercase."""
    return {b.lower() for v in pack.archive_lists().values() for b in v}


def loose_bsas(pack: Pack, name: str) -> list[Path]:
    """BSAs that would go with a removed loose copy: its own ones, except
    those an ini loads independently."""
    keep = ini_listed(pack)
    return [b for b in pack.bsas_for_plugin(name) if b.name.lower() not in keep]


def _dependents(pack: Pack, names: set[str]) -> list:
    return [h for h in pack.plugins.values()
            if h.name.lower() not in names and any(m.lower() in names for m in h.masters)]


def _drop_from_inis(pack: Pack, bsas: set[str], tx: Transaction) -> None:
    if not bsas:
        return
    for ini in pack.ini_paths:
        raw = ini.read_bytes()
        new = raw
        for key in ARCHIVE_KEYS:
            if parse_ini(new).get("Archive", key) is None:
                continue
            cur = parse_ini(new).archive_list(key)
            if any(c.lower() in bsas for c in cur):
                new = set_archive_list(new, key, [c for c in cur if c.lower() not in bsas])
        if new != raw:
            tx.write_bytes(ini, new)


def _forget_in_records(pack: Pack, files: set[str], tx: Transaction) -> None:
    from .builder import _save_mods, load_mods
    mods = load_mods(pack)
    changed = False
    for key in list(mods):
        rec = mods[key]
        if not isinstance(rec, dict):
            continue
        pl = [p for p in rec.get("plugins") or [] if p.lower() not in files]
        bs = [b for b in rec.get("bsas") or [] if b.lower() not in files]
        if pl != (rec.get("plugins") or []) or bs != (rec.get("bsas") or []):
            changed = True
            if not pl and not bs:
                del mods[key]
            else:
                rec["plugins"], rec["bsas"] = pl, bs
                rec["ini"] = [e for e in rec.get("ini") or []
                              if not (isinstance(e, dict) and str(e.get("bsa", "")).lower() in files)]
    if changed:
        _save_mods(pack, tx, mods)


def placeholder_bytes(raw: bytes) -> bytes:
    """The plugin's own header record (TES4: flags, masters, description) with
    its record count set to 0 and nothing after it."""
    if raw[:4] != b"TES4" or len(raw) < 24:
        raise DupFixError("That plugin's header can't be read.", "No se puede leer el encabezado de ese plugin.")
    size = struct.unpack_from("<I", raw, 4)[0]
    rec = bytearray(raw[:24 + size])
    i = 24
    while i + 6 <= len(rec):
        sig = bytes(rec[i:i + 4])
        ss = struct.unpack_from("<H", rec, i + 4)[0]
        if sig == b"HEDR" and ss >= 8:
            struct.pack_into("<i", rec, i + 6 + 4, 0)
            break
        i += 6 + ss
    return bytes(rec)


# ---------------------------------------------------------------- actions
def keep_only_problems(pack: Pack, keep: str, remove: list[str]) -> list[tuple[str, str]]:
    """Reasons keep_only can't be done safely (en, es); empty when it can."""
    low = {r.lower() for r in remove if r.lower() != keep.lower()}
    out = []
    for h in pack.plugins.values():
        ms = [m.lower() for m in h.masters]
        hits = [m for m in ms if m in low] + ([keep.lower()] if keep.lower() in ms else [])
        if len(hits) > 1 and h.name.lower() not in low:
            out.append((f"{h.name} uses more than one of these copies as masters; it has to be fixed by hand "
                        "(xEdit) before keeping only one.",
                        f"{h.name} usa más de una de estas copias como master; hay que arreglarlo a mano "
                        "(xEdit) antes de dejar solo una."))
    return out


def keep_only(pack: Pack, keep: str, remove: list[str], tx: Transaction) -> dict:
    kh = _plugin(pack, keep)
    gone = [_plugin(pack, r).name for r in remove if r.lower() != kh.name.lower()]
    if not gone:
        raise DupFixError("Nothing to remove.", "No hay nada que quitar.")
    bad = keep_only_problems(pack, kh.name, gone)
    if bad:
        raise DupFixError(bad[0][0], bad[0][1])
    low = {g.lower() for g in gone}
    out = {"kept": kh.name, "removed": gone, "masters": [], "bsas": [], "renamed": []}
    # 1. load list: the kept plugin takes the place of the FIRST copy, so
    #    patches that load after any copy still load after it
    if pack.list_path:
        raw = pack.list_path.read_bytes()
        entries = C.parse_ccc(raw).entries
        copies = [e for e in entries if e.lstrip("#").lower() in low | {kh.name.lower()}]
        mapping: dict[str, str | None] = {}
        if copies:
            first = copies[0]
            active = any(not e.startswith("#") for e in copies)
            for e in copies:
                mapping[e] = None
            mapping[first] = ("" if active else "#") + kh.name
        if mapping:
            tx.write_bytes(pack.list_path, C.edit_lines(raw, mapping))
    # 2. plugins that used a removed copy as master now use the kept one
    for h in _dependents(pack, low | {kh.name.lower()}):
        new, n = rename_masters(h.path.read_bytes(), {g: kh.name for g in low})
        if n:
            tx.write_bytes(h.path, new)
            out["masters"].append(h.name)
    # 3. the removed copies' own BSAs: an ini-loaded one stays as it is; one the
    #    kept plugin lacks is renamed to go with it; the rest go to the trash
    in_ini = ini_listed(pack)
    keep_stem = Path(kh.name).stem
    kept_names = {b.name.lower() for b in pack.bsas_for_plugin(kh.name)}
    for g in gone:
        g_stem = Path(g).stem
        for b in _own_bsas(pack, g, [kh.name]):
            if b.name.lower() in in_ini or not b.exists():
                continue
            target = keep_stem + b.name[len(g_stem):]
            if target.lower() not in kept_names and not (pack.data_dir / target).exists():
                tx.move(b, pack.data_dir / target)
                kept_names.add(target.lower())
                out["renamed"].append([b.name, target])
            else:
                tx.trash(b)
                out["bsas"].append(b.name)
        tx.trash(pack.data_dir / pack.plugins[g.lower()].path.name)
    _forget_in_records(pack, low | {b.lower() for b in out["bsas"]}, tx)
    return out


def take_out_loose(pack: Pack, name: str, tx: Transaction) -> dict:
    """The loose copy of a mod that's also inside a merge becomes an empty
    placeholder: its records stop loading twice, while its BSAs keep loading
    with it (merges usually don't repack assets) and patches keep finding it
    as a master."""
    h = _plugin(pack, name)
    deps = _dependents(pack, {h.name.lower()})
    tx.write_bytes(h.path, placeholder_bytes(h.path.read_bytes()))
    return {"placeholder": h.name, "dependents": [d.name for d in deps]}


def _remove_loose(pack: Pack, name: str, tx: Transaction) -> dict:
    h = _plugin(pack, name)
    if pack.list_path:
        raw = pack.list_path.read_bytes()
        mapping = {e: None for e in C.parse_ccc(raw).entries if e.lstrip("#").lower() == h.name.lower()}
        if mapping:
            tx.write_bytes(pack.list_path, C.edit_lines(raw, mapping))
    bsas = loose_bsas(pack, h.name)
    tx.trash(h.path)
    for b in bsas:
        if b.exists():
            tx.trash(b)
    _forget_in_records(pack, {h.name.lower()} | {b.name.lower() for b in bsas}, tx)
    return {"removed": h.name, "bsas": [b.name for b in bsas]}


def delete_copy(pack: Pack, name: str, tx: Transaction) -> dict:
    h = _plugin(pack, name)
    active = {e.lstrip("#").lower() for e in pack.list_entries if not e.startswith("#")}
    if h.name.lower() in active:
        raise DupFixError(f"{h.name} is in the load list; it isn't a spare copy.",
                          f"{h.name} está en la lista de carga; no es una copia sobrante.")
    deps = [d.name for d in _dependents(pack, {h.name.lower()}) if d.name.lower() in active]
    if deps:
        raise DupFixError(f"{', '.join(deps)} use {h.name} as a master.",
                          f"{', '.join(deps)} usan {h.name} como master.")
    bsas = loose_bsas(pack, h.name)
    tx.trash(h.path)
    for b in bsas:
        if b.exists():
            tx.trash(b)
    _forget_in_records(pack, {h.name.lower()} | {b.name.lower() for b in bsas}, tx)
    return {"removed": h.name, "bsas": [b.name for b in bsas]}


def drop_bsa(pack: Pack, name: str, tx: Transaction) -> dict:
    p = pack.bsas.get(name.lower())
    if p is None:
        raise DupFixError(f"{name} isn't in Data anymore.", f"{name} ya no está en Data.")
    _drop_from_inis(pack, {p.name.lower()}, tx)
    tx.trash(p)
    _forget_in_records(pack, {p.name.lower()}, tx)
    return {"removed": p.name}
