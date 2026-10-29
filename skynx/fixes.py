"""Apply the fixes proposed by the audit. Every change is recorded in history."""
from __future__ import annotations

from pathlib import Path

from . import ccc as C
from . import i18n
from .bsa import read_bsa, rebuild_bsa
from .errors import SkynxError
from .history import Transaction
from .ini import ARCHIVE_LIST_LIMIT, parse_ini, set_archive_list
from .pack import Pack
from .plugin import rename_master_bytes
from .texplan import DEFAULT_PRESET  # noqa: E402

FACE_ROOTS = ("meshes\\actors\\character\\facegendata\\facegeom\\",
              "textures\\actors\\character\\facegendata\\facetint\\")
VOICE_ROOT = "sound\\voice\\"


class FixError(SkynxError):
    pass


def _list_raw(pack: Pack) -> tuple[Path, bytes]:
    p = pack.list_path
    if not p or not p.exists():
        raise FixError("There is no load list to edit", "No hay lista de carga para editar")
    return p, p.read_bytes()


def _plugin_files(pack: Pack, plugin: str) -> list[Path]:
    p = pack.data_dir / plugin
    return ([p] if p.exists() else []) + pack.bsas_for_plugin(plugin)


def preview(pack: Pack, fix: dict, lang: str = "en") -> dict:
    """Describe exactly what would change, without touching anything."""
    kind = fix["kind"]
    ln = pack.list_path.name if pack.list_path else "list"
    t = lambda k, **kw: i18n.pv(k, lang, **kw)  # noqa: E731
    lines: list[str] = []
    if kind == "list_replace":
        lines.append(t("pv-replace", file=ln, old=fix["old"], new=fix["new"]))
    elif kind == "list_remove":
        lines.append(t("pv-remove", file=ln, name=fix["entry"]))
    elif kind == "list_remove_many":
        for e in fix["entries"]:
            lines.append(t("pv-remove", file=ln, name=e))
    elif kind == "list_dedupe":
        lines.append(t("pv-dedupe", file=ln, name=fix["entry"]))
    elif kind == "list_add":
        lines.append(t("pv-add", file=ln, name=fix["entry"]))
    elif kind == "list_insert_before":
        for e in fix.get("entries") or [fix["entry"]]:
            lines.append(t("pv-insert", file=ln, name=e, before=fix["before"]))
    elif kind == "list_move_after":
        lines.append(t("pv-move", file=ln, name=fix["entry"], after=fix["after"]))
    elif kind == "list_rewrite":
        lines.append(t("pv-rewrite", file=ln))
    elif kind == "rename_files":
        for r in fix["renames"]:
            lines.append(t("pv-rename", old=r["from"], new=r["to"]))
    elif kind == "rename_plugin":
        for f in _plugin_files(pack, fix["from"]):
            new = Path(fix["to"]).stem + f.name[len(Path(fix["from"]).stem):]
            lines.append(t("pv-rename", old=f.name, new=new))
        lines.append(t("pv-replace", file=ln, old=fix["from"], new=fix["to"]))
        for h in pack.plugins.values():
            if any(m.lower() == fix["from"].lower() for m in h.masters):
                lines.append(t("pv-master", file=h.name, new=fix["to"]))
    elif kind == "bsa_move_voices":
        lines.append(t("pv-voices", file=fix["bsa"], old=fix["old"], new=fix["new"]))
        lines.append(t("pv-rebuild"))
    elif kind == "archive_extract":
        from .archfix import plan
        pl = plan(pack, fix["name"])
        lines.append(t("pv-extract", name=fix["name"], files=", ".join(pl["plugins"] + pl["bsas"])))
        if pl["note"]:
            lines.append(pl["note"][1] if lang == "es" else pl["note"][0])
        if pl["unlisted"]:
            lines.append(t("pv-extract-list", file=ln, names=", ".join(pl["unlisted"])))
        if pl["loose"]:
            lines.append(t("pv-extract-loose", n=pl["loose"]))
        lines.append(t("pv-extract-trash", name=fix["name"]))
    elif kind == "esl_to_esp":
        if fix["to"] != fix["from"]:
            lines.append(t("pv-rename", old=fix["from"], new=fix["to"]))
        lines.append(t("pv-esl-flag", name=fix["to"]))
    elif kind == "trash_files":
        for n in fix["files"]:
            lines.append(t("pv-trash", name=n))
    elif kind == "ini_remove_archive":
        lines.append(t("pv-ini-remove", key=fix["key"], name=fix["item"]))
    elif kind == "bsa_drop_junk":
        lines.append(t("pv-drop-junk", file=fix["bsa"], n=len(fix["items"])))
        lines.append(t("pv-rebuild"))
    elif kind == "bsa_drop_skse":
        lines.append(t("pv-drop-skse", file=fix["bsa"], n=len(fix["items"])))
        lines.append(t("pv-rebuild"))
    elif kind == "fix_tints":
        for fx in fix["fixes"][:12]:
            lines.append(t("pv-tint", file=fix["bsa"], nif=fx["nif"].split("\\")[-1], old=fx["old"], new=fx["new"]))
        lines.append(t("pv-rebuild"))
    elif kind == "diet_bsa":
        lines.append(t("pv-diet", file=fix["bsa"], preset=fix.get("preset", DEFAULT_PRESET)))
        lines.append(t("pv-diet-how"))
    elif kind == "plugins_shorten":
        for a, b in fix["pairs"]:
            lines.append(t("pv-rename", old=a, new=b))
        lines.append(t("pv-list-shorten"))
    elif kind == "safe_rename":
        from .bsafix import rename_plan
        plan = rename_plan(pack, fix["from"], fix["to"])
        lines.append(t("pv-rename", old=fix["from"], new=fix["to"]))
        for a, b in plan["bsas_rename"]:
            lines.append(t("pv-rename", old=a, new=b))
        for b in plan["bsas_patch"]:
            lines.append(t("pv-inside", file=b, old=fix["from"], new=fix["to"]))
        for d in plan["dependents"]:
            lines.append(t("pv-master", file=d, new=fix["to"]))
        if plan["list"]:
            lines.append(t("pv-replace", file=ln, old=fix["from"], new=fix["to"]))
        lines.append(t("pv-saves"))
    elif kind == "ini_copy_to_lang":
        for n in fix["inis"]:
            for it in fix["items"]:
                lines.append(t("pv-ini-add-in", ini=n, key=fix["key"], name=it))
    elif kind == "dup_ignore":
        lines.append(t("pv-dup-keep"))
    elif kind == "dup_unignore":
        lines.append(t("pv-dup-unkeep", n=len(fix.get("ids") or [])))
    elif kind in ("dup_keep_only", "dup_delete_copy", "dup_take_out"):
        from .dupfix import _dependents, _own_bsas, loose_bsas
        names = fix["remove"] if kind == "dup_keep_only" else [fix["name"]]
        keep = [fix["keep"]] if kind == "dup_keep_only" else []
        if kind == "dup_take_out":
            deps = fix.get("deps") or []
            lines.append(t("pv-dup-placeholder", name=fix["name"],
                           deps=(f"; {', '.join(deps)} " + ("keep loading" if lang == "en" else "siguen cargando")) if deps else ""))
        else:
            entries = {e.lstrip("#").lower() for e in pack.list_entries}
            for n in names:
                if n.lower() in entries:
                    lines.append(t("pv-remove", file=ln, name=n))
                lines.append(t("pv-trash", name=n))
                from .dupfix import ini_listed
                in_ini = ini_listed(pack)
                for b in (_own_bsas(pack, n, keep) if keep else loose_bsas(pack, n)):
                    if b.name.lower() in in_ini:
                        continue
                    if keep and not pack.bsas_for_plugin(keep[0]):
                        lines.append(t("pv-rename", old=b.name, new=Path(keep[0]).stem + b.name[len(Path(n).stem):]))
                    else:
                        lines.append(t("pv-trash", name=b.name))
            if keep:
                from .dupfix import keep_only_problems
                low = {n.lower() for n in names}
                for h in _dependents(pack, low | {keep[0].lower()}):
                    if any(m.lower() in low for m in h.masters):
                        lines.append(t("pv-master", file=h.name, new=keep[0]))
                for en, es in keep_only_problems(pack, keep[0], names):
                    lines.append(es if lang == "es" else en)
    elif kind == "dup_drop_bsa":
        for n in fix["remove"]:
            lines.append(t("pv-ini-remove-any", name=n))
            lines.append(t("pv-trash", name=n))
    elif kind == "ini_shorten":
        for a, b in fix["renames"]:
            lines.append(t("pv-rename", old=a, new=b))
        lines.append(t("pv-ini-short", n=sum(len(a) - len(b) for a, b in fix["renames"])))
    elif kind == "ini_add_archives":
        for k, b in fix["items"]:
            lines.append(t("pv-ini-add", key=k, name=b))
    elif kind == "dummy_to_ini":
        lines.append(t("pv-remove", file=ln, name=fix["entry"]))
        for b in fix["bsas"]:
            lines.append(t("pv-ini-add", key=_archive_key(b), name=b))
    elif kind == "ini_memory_out":
        low = {i.lower() for i in fix["items"]}
        for ini in pack.inis:
            for it in ini.archive_list(MEMORY_KEY):
                if it.lower() in low:
                    lines.append(t("pv-ini-remove-in", ini=ini.path.name, key=MEMORY_KEY, name=it))
        for key, it in _memory_keep(pack, fix["items"]):
            for ini_path in pack.inis_for_key(key):
                lines.append(t("pv-ini-keep", ini=ini_path.name, key=key, name=it))
        lines.append(t("pv-memory-back"))
    elif kind == "font_loose":
        lines.append(t("pv-font-loose", bsa=fix["bsa"]))
    elif kind == "names_fix":
        lines.append(t("pv-names", file=fix["plugin"], n=len(fix["names"])))
        lines += [f"  {nm}" for _fid, nm in fix["names"][:12]] + (["  …"] if len(fix["names"]) > 12 else [])
    elif kind == "master_retarget":
        for old, new in fix["map"].items():
            lines.append(t("pv-master-retarget", file=fix["plugin"], old=old, new=new))
    elif kind == "plugin_hedr":
        lines.append(t("pv-hedr", file=fix["plugin"], old=f"{fix.get('old', 1.71):.2f}",
                       new=f"{fix.get('new', 1.70):.2f}"))
    elif kind in ("seq_add", "seq_rewrite"):
        from .bsafix import seq_path
        seq = seq_path(fix["plugin"]).split("\\", 1)[1]
        n = len(fix["formids"])
        if fix.get("loose"):
            lines.append(t("pv-seq-loose", seq=seq, n=n))
        elif kind == "seq_rewrite":
            lines += [t("pv-seq-replace", file=fix["bsa"], seq=seq, n=n), t("pv-rebuild")]
        elif (pack.data_dir / fix["bsa"]).exists():
            lines += [t("pv-seq-add", file=fix["bsa"], seq=seq, n=n), t("pv-rebuild")]
        else:
            lines.append(t("pv-seq-new", file=fix["bsa"], seq=seq, n=n, plugin=fix["plugin"]))
    elif kind == "ussep_ini_order":
        for pl in fix["places"]:
            lines.append(t("pv-ini-order", ini=pl["ini"], key=pl["key"], items=", ".join(pl["items"])))
    elif kind == "list_move_first":
        from .ussep import first_slot
        rest, slot = first_slot(pack, pack.list_entries, fix["entry"])
        lines.append(t("pv-move", file=ln, name=fix["entry"], after=rest[slot - 1]) if slot
                     else t("pv-move-first", file=ln, name=fix["entry"]))
    else:
        raise FixError(f"Unknown fix: {kind}", f"Arreglo desconocido: {kind}")
    return {"label": i18n.label(fix["label_key"], lang, **fix.get("label_args", {})),
            "changes": lines, "risk": fix.get("risk", "revisar")}


MEMORY_KEY = "sArchiveToLoadInMemoryList"


def _memory_keep(pack: Pack, items: list[str]) -> list[tuple[str, str]]:
    """(key, BSA) to add so BSAs taken out of the in-memory list keep loading:
    only the ones in Data that no resource list has and no active plugin loads."""
    from .builder import _archive_key_for
    listed = {b.lower() for ini in pack.inis for k in ("sResourceArchiveList", "sResourceArchiveList2")
              for b in ini.archive_list(k)}
    stems = {Path(n).stem.lower() for n, _ in pack.load_order()}
    out = []
    for it in items:
        low = it.lower()
        stem = Path(low).stem
        if low in listed or low not in pack.bsas or stem in stems or \
                (stem.endswith(" - textures") and stem[:-11] in stems):
            continue
        out.append((_archive_key_for(pack.bsas[low])[0], pack.bsas[low].name))
    return out


def _archive_key(bsa: str) -> str:
    return "sResourceArchiveList2" if bsa.lower().endswith(" - textures.bsa") else "sResourceArchiveList"


def apply(pack: Pack, fix: dict, title: str | None = None, progress=None) -> dict:
    kind = fix["kind"]
    title = title or i18n.label(fix["label_key"], "en", **fix.get("label_args", {}))
    if kind == "archive_extract":
        # the same path as adding a mod (its own undoable step)
        from .archfix import apply as extract
        out = extract(pack, fix["name"], title=title)
        pack.reload()
        return {"ok": True, "history": out["history"], "changed": bool(out["history"])}
    with Transaction(pack.root, title, detail=str(fix)) as tx:
        if kind.startswith("list_"):
            _apply_list(pack, fix, tx)
        elif kind == "rename_files":
            for r in fix["renames"]:
                src, dst = pack.data_dir / r["from"], pack.data_dir / r["to"]
                if not src.exists():
                    raise FixError(f"{r['from']} doesn't exist", f"No existe {r['from']}")
                tx.move(src, dst)
        elif kind == "rename_plugin":
            _apply_rename_plugin(pack, fix, tx)
        elif kind == "ini_shorten":
            from .bsafix import rename_ini_bsas
            rename_ini_bsas(pack, [tuple(r) for r in fix["renames"]], tx)
        elif kind == "trash_files":
            for name in fix["files"]:
                p = pack.data_dir / name
                if p.exists():
                    tx.trash(p)
        elif kind == "bsa_move_voices":
            bpath = pack.data_dir / fix["bsa"]
            arc = read_bsa(bpath)
            tmp = bpath.with_name(bpath.name + ".skynx-new")
            try:
                rebuild_bsa(arc, tmp, rename_folder={VOICE_ROOT + fix["old"]: VOICE_ROOT + fix["new"]})
                tx.replace_with(bpath, tmp)
            finally:
                if tmp.exists():
                    tmp.unlink()
        elif kind in ("ini_remove_archive", "dummy_to_ini", "ini_copy_to_lang", "ini_add_archives"):
            _apply_ini(pack, fix, tx)
        elif kind in ("bsa_drop_junk", "bsa_drop_skse"):
            from .bsafix import drop_junk
            drop_junk(pack, fix["bsa"], fix["items"], tx)
        elif kind == "fix_tints":
            from .bsafix import fix_tints
            fix_tints(pack, fix["bsa"], fix["fixes"], tx)
        elif kind == "diet_bsa":
            from .bsafix import diet
            diet(pack, fix["bsa"], fix.get("preset", DEFAULT_PRESET), bool(fix.get("bc1")),
                 fix.get("tools_dir"), tx, progress=progress)
        elif kind == "safe_rename":
            from .bsafix import safe_rename
            safe_rename(pack, fix["from"], fix["to"], tx, progress=progress)
        elif kind == "plugins_shorten":
            # one plugin after another, in one undoable step; each rename patches
            # the masters of the ones that use it, so the pack is read again
            from .bsafix import safe_rename
            pairs = fix["pairs"]
            for i, (a, b) in enumerate(pairs):
                if progress:
                    progress(f"Renaming {a} → {b}", i, len(pairs))
                pack.reload()
                if a.lower() not in pack.plugins or (pack.data_dir / b).exists():
                    continue
                safe_rename(pack, a, b, tx,
                            progress=(lambda t, i=i: progress(f"{t} ({a} → {b})", i, len(pairs))) if progress else None)
            pack.reload()
            if progress:
                progress("Checking the pack again")
        elif kind == "esl_to_esp":
            from .bsafix import safe_rename
            from .edition import adapt_bytes_for_se
            if fix["to"].lower() != fix["from"].lower():
                safe_rename(pack, fix["from"], fix["to"], tx)   # voices, FaceGen, masters, list follow
            p = pack.data_dir / fix["to"]
            raw = p.read_bytes()
            tx.write_bytes(p, adapt_bytes_for_se(raw))
        elif kind == "ini_memory_out":
            _apply_memory_out(pack, fix, tx)
        elif kind == "font_loose":
            from . import fonts as FN
            b = pack.bsas.get(fix["bsa"].lower())
            if not b:
                raise FixError(f"{fix['bsa']} isn't in the pack", f"{fix['bsa']} no está en el pack")
            arc = read_bsa(b)
            e = next((e for e in arc.entries if e.path.lower() == "interface\\" + FN.NAME), None)
            if e is None:
                raise FixError(f"{fix['bsa']} has no FontConfig.txt", f"{fix['bsa']} no tiene FontConfig.txt")
            with b.open("rb") as fh:
                data = arc.read_file(e, fh)
            dest = pack.data_dir.joinpath(*FN.LOOSE_REL)
            dest.parent.mkdir(parents=True, exist_ok=True)
            tx.write_bytes(dest, data)
        elif kind == "names_fix":
            from .names import fix_names
            h = pack.plugins.get(fix["plugin"].lower())
            if not h:
                raise FixError(f"{fix['plugin']} isn't in the pack anymore", f"{fix['plugin']} ya no está en el pack")
            out, n = fix_names(h.path.read_bytes(), {int(f): nm for f, nm in fix["names"]})
            if n:
                tx.write_bytes(h.path, out)
        elif kind == "master_retarget":
            from .rename import rename_masters
            h = pack.plugins.get(fix["plugin"].lower())
            if not h:
                raise FixError(f"{fix['plugin']} isn't in the pack anymore", f"{fix['plugin']} ya no está en el pack")
            out, n = rename_masters(h.path.read_bytes(), {o.lower(): v for o, v in fix["map"].items()})
            if n:
                tx.write_bytes(h.path, out)
        elif kind == "plugin_hedr":
            from .records import RecordError, set_hedr_version
            p = pack.data_dir / fix["plugin"]
            if not p.exists():
                raise FixError(f"{fix['plugin']} doesn't exist", f"No existe {fix['plugin']}")
            raw = p.read_bytes()
            try:
                new = set_hedr_version(raw, float(fix.get("new", 1.70)))
            except RecordError as e:
                raise FixError(f"{fix['plugin']}: {e}", f"{fix['plugin']}: no tiene HEDR en el encabezado") from None
            if new == raw:
                raise FixError("The version is already 1.70", "La versión ya es 1.70")
            tx.write_bytes(p, new)
        elif kind in ("seq_add", "seq_rewrite"):
            from .bsafix import add_seq
            add_seq(pack, fix["plugin"], [int(i) for i in fix["formids"]], tx,
                    bsa=fix.get("bsa"), loose=bool(fix.get("loose")))
        elif kind == "ussep_ini_order":
            from . import knowledge as K
            from .ussep import is_ussep_bsa
            for pl in fix["places"]:
                ini_path = pack.base_romfs / pl["ini"]
                raw = ini_path.read_bytes()
                cur = parse_ini(raw).archive_list(pl["key"])
                new = K.after_vanilla(cur, [b for b in cur if is_ussep_bsa(b)])
                if new != cur:
                    tx.write_bytes(ini_path, set_archive_list(raw, pl["key"], new))
        elif kind.startswith("dup_"):
            from . import dupfix as D
            if kind == "dup_ignore":
                D.ignore(pack, fix["finding"], tx)
            elif kind == "dup_unignore":
                D.unignore(pack, fix.get("ids"), tx)
            elif kind == "dup_keep_only":
                D.keep_only(pack, fix["keep"], fix["remove"], tx)
            elif kind == "dup_delete_copy":
                D.delete_copy(pack, fix["name"], tx)
            elif kind == "dup_take_out":
                D.take_out_loose(pack, fix["name"], tx)
            elif kind == "dup_drop_bsa":
                for n in fix["remove"]:
                    D.drop_bsa(pack, n, tx)
            else:
                raise FixError(f"Unknown fix: {kind}", f"Arreglo desconocido: {kind}")
        else:
            raise FixError(f"Unknown fix: {kind}", f"Arreglo desconocido: {kind}")
    pack.reload()
    return {"ok": True, "history": tx.dir.name if tx.changed else None, "changed": tx.changed}


def _apply_list(pack: Pack, fix: dict, tx: Transaction) -> None:
    kind = fix["kind"]
    path, raw = _list_raw(pack)
    parsed = C.parse_ccc(raw)
    entries = parsed.entries
    low = [e.lower() for e in entries]
    if kind == "list_replace":
        new = C.edit_lines(raw, {fix["old"]: fix["new"]})
    elif kind == "list_remove":
        new = C.edit_lines(raw, {fix["entry"]: None})
    elif kind == "list_remove_many":
        new = C.edit_lines(raw, {e: None for e in fix["entries"]})
    elif kind == "list_dedupe":
        seen, out = set(), []
        for e in entries:
            if e.lower() in seen and e.lower() == fix["entry"].lower():
                continue
            seen.add(e.lower())
            out.append(e)
        new = C.reorder(raw, out)
    elif kind == "list_rewrite":
        style = fix.get("newline") or ("LF" if parsed.newline == "LF" else "CRLF")
        new = C.render(entries, style, True)
    elif kind == "list_add":
        if fix["entry"].lower() in low:
            raise FixError("It's already in the list", "Ya está en la lista")
        h = pack.plugins.get(fix["entry"].lower())
        masters = {m.lower() for m in (h.masters if h else [])}
        idx = max([i for i, e in enumerate(low) if e in masters], default=len(entries) - 1)
        out = entries[:idx + 1] + [fix["entry"]] + entries[idx + 1:]
        new = C.reorder(raw, out)
    elif kind == "list_insert_before":
        idx = low.index(fix["before"].lower())
        add = [e for e in (fix.get("entries") or [fix["entry"]]) if e.lower() not in low]
        new = C.reorder(raw, entries[:idx] + add + entries[idx:])
    elif kind == "list_move_first":
        from .ussep import first_slot
        if fix["entry"].lower() not in low:
            raise FixError(f"{fix['entry']} isn't in the list", f"{fix['entry']} no está en la lista")
        name = entries[low.index(fix["entry"].lower())]
        rest, slot = first_slot(pack, entries, name)
        new = C.reorder(raw, rest[:slot] + [name] + rest[slot:])
    elif kind == "list_move_after":
        name = entries[low.index(fix["entry"].lower())]
        rest = [e for e in entries if e.lower() != fix["entry"].lower()]
        idx = [e.lower() for e in rest].index(fix["after"].lower())
        new = C.reorder(raw, rest[:idx + 1] + [name] + rest[idx + 1:])
    else:
        raise FixError(f"Unknown fix: {kind}", f"Arreglo desconocido: {kind}")
    if new == raw:
        raise FixError("This fix would change nothing; check the file by hand", "El arreglo no cambiaría nada; revisa el archivo a mano")
    _check_ccc_size(pack, raw, new)
    tx.write_bytes(path, new)


def _check_ccc_size(pack: Pack, old: bytes, new: bytes) -> None:
    """Never let a fix push the .ccc past its limit (the game stops reading it there)."""
    size = C.over_limit(pack, old, new)
    if size:
        raise FixError(*C.limit_message(size))


def _apply_rename_plugin(pack: Pack, fix: dict, tx: Transaction) -> None:
    old, new = fix["from"], fix["to"]
    old_stem, new_stem = Path(old).stem, Path(new).stem
    for f in _plugin_files(pack, old):
        dest = f.with_name(new_stem + f.name[len(old_stem):])
        tx.move(f, dest)
    # dependents: patch their MAST
    for h in list(pack.plugins.values()):
        if h.path.name.lower() == old.lower():
            continue
        if any(m.lower() == old.lower() for m in h.masters):
            data = rename_master_bytes(h.path.read_bytes(), old, new)
            if data:
                tx.write_bytes(h.path, data)
    path, raw = _list_raw(pack)
    keys = {e for e in C.parse_ccc(raw).entries if e.lower() == old.lower()}
    if keys:
        out = C.edit_lines(raw, {k: new for k in keys})
        _check_ccc_size(pack, raw, out)
        tx.write_bytes(path, out)


def _apply_memory_out(pack: Pack, fix: dict, tx: Transaction) -> None:
    """Take mod BSAs out of sArchiveToLoadInMemoryList (the game's own entries
    stay) and make sure each one still loads from a resource list."""
    low = {i.lower() for i in fix["items"]}
    keep = _memory_keep(pack, fix["items"])
    for ini_path in pack.inis_for_key(MEMORY_KEY):
        raw = ini_path.read_bytes()
        cur = parse_ini(raw).archive_list(MEMORY_KEY)
        new = [c for c in cur if c.lower() not in low]
        if new != cur:
            tx.write_bytes(ini_path, set_archive_list(raw, MEMORY_KEY, new))
    for key, item in keep:
        paths = pack.inis_for_key(key)
        if not paths:
            raise FixError(f"No ini has {key}, so {item} would stop loading",
                           f"Ningún ini tiene {key}, así que {item} dejaría de cargar")
        for ini_path in paths:
            raw = ini_path.read_bytes()
            cur = parse_ini(raw).archive_list(key)
            if item.lower() in [c.lower() for c in cur]:
                continue
            cur.append(item)
            if len(", ".join(cur)) > ARCHIVE_LIST_LIMIT:
                raise FixError(f"{key} in {ini_path.name} would go over {ARCHIVE_LIST_LIMIT} characters",
                               f"{key} en {ini_path.name} pasaría de {ARCHIVE_LIST_LIMIT} caracteres")
            tx.write_bytes(ini_path, set_archive_list(raw, key, cur))


def _apply_ini(pack: Pack, fix: dict, tx: Transaction) -> None:
    adds, removes = [], []
    if fix["kind"] == "dummy_to_ini":
        h = pack.plugins.get(fix["entry"].lower())
        users = [p.name for p in pack.plugins.values()
                 if any(m.lower() == fix["entry"].lower() for m in p.masters)]
        if users:
            raise FixError(f"Not removing it: {', '.join(users)} uses it as a master", f"No lo quito: {', '.join(users)} lo usa como master")
        adds = [(_archive_key(b), b) for b in fix["bsas"]]
    elif fix["kind"] == "ini_remove_archive":
        removes = [(fix["key"], fix["item"])]
    elif fix["kind"] == "ini_add_archives":
        adds = [(k, b) for k, b in fix["items"]]
    if fix["kind"] == "ini_copy_to_lang":
        targets = [pack.base_romfs / n for n in fix["inis"]]
        adds = [(fix["key"], it) for it in fix["items"]]
    else:
        targets = None
    for key, item in adds + removes:
        paths = targets or pack.inis_for_key(key)
        if not paths:
            raise FixError(f"No ini has {key}; I won't create the list from scratch because it "
                           "would leave out the game's own BSAs",
                           f"Ningún ini tiene {key}; no creo la lista desde cero porque "
                           "dejaría fuera los BSA del juego")
        for ini_path in paths:
            raw = ini_path.read_bytes()
            cur = parse_ini(raw).archive_list(key)
            if (key, item) in adds:
                if item.lower() in [c.lower() for c in cur]:
                    continue
                cur.append(item)
            else:
                if item.lower() not in [c.lower() for c in cur]:
                    continue
                cur = [c for c in cur if c.lower() != item.lower()]
            if len(", ".join(cur)) > ARCHIVE_LIST_LIMIT:
                raise FixError(f"{key} in {ini_path.name} would go over {ARCHIVE_LIST_LIMIT} characters",
                               f"{key} en {ini_path.name} pasaría de {ARCHIVE_LIST_LIMIT} caracteres")
            tx.write_bytes(ini_path, set_archive_list(raw, key, cur))
    if fix["kind"] == "dummy_to_ini":
        path, raw = _list_raw(pack)
        tx.write_bytes(path, C.edit_lines(raw, {fix["entry"]: None}))
