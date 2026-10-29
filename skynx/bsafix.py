"""Doctor fixes that rewrite archives: plugin renames that reach inside BSAs,
broken FaceGen tint paths, junk files, and the texture diet.

Every function here writes new files next to the originals and hands them to
the history Transaction, so each fix can be undone like the others.
"""
from __future__ import annotations

import json
import re
import shutil
import tempfile
from pathlib import Path

from . import ccc as C
from . import knowledge as K
from . import nif as NIF
from . import pex as PEX
from .bsa import read_bsa, rebuild_bsa, write_bsa
from .errors import SkynxError
from .history import Transaction
from .ini import parse_ini, set_archive_list, set_value
from .pack import Pack
from .rename import NAME_FOLDERS, rename_masters

FACEGEOM = "meshes\\actors\\character\\facegendata\\facegeom\\"
FACETINT = "textures\\actors\\character\\facegendata\\facetint\\"
GAME_OWNERS = {m.lower() for m in K.VANILLA_MASTERS + K.SWITCH_MASTERS + K.AE_CC_PLUGINS}


class BsaFixError(SkynxError):
    pass


# ------------------------------------------------------------------ helpers
def transform_bsa(src: Path, dest: Path, fn, extra: dict[str, bytes] | None = None) -> int:
    """Write `dest` with every file of `src` passed through fn(path, data),
    which returns (new_path, new_data) or None to drop the file.
    extra: {archive path: data} to add (an existing file with that path is
    replaced). Returns how many files changed. The source is never modified."""
    src, dest = Path(src), Path(dest)
    arc = read_bsa(src)
    extra = {k.replace("/", "\\").lower(): v for k, v in (extra or {}).items()}
    tmp = Path(tempfile.mkdtemp(prefix="skynx-bsa-", dir=str(dest.parent)))
    changed = 0
    try:
        files = []
        with src.open("rb") as f:
            for i, e in enumerate(arc.entries):
                data = arc.read_file(e, f)
                res = fn(e.path.lower(), data)
                if res is None:
                    changed += 1
                    continue
                path, new = res
                if path in extra:
                    new = extra.pop(path)
                if path != e.path.lower() or new != data:
                    changed += 1
                p = tmp / str(i)
                p.write_bytes(new)
                files.append((path, p))
        for j, (path, new) in enumerate(extra.items()):
            p = tmp / f"x{j}"
            p.write_bytes(new)
            files.append((path, p))
            changed += 1
        if changed:
            write_bsa(files, dest, ver=arc.version, compress=arc.compressed_default)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    return changed


def _staged(tx: Transaction, target: Path, writer) -> bool:
    """Run writer(tmp) and put tmp in place of target through history."""
    tmp = target.with_name(target.name + ".skynx-new")
    try:
        if writer(tmp) and tmp.exists():
            tx.replace_with(target, tmp)
            return True
        return False
    finally:
        if tmp.exists():
            tmp.unlink()


def renames_file(pack: Pack) -> Path:
    return Path(pack.root) / ".skynx" / "renames.json"


def load_renames(pack: Pack) -> dict:
    f = renames_file(pack)
    try:
        return json.loads(f.read_text(encoding="utf-8")) if f.exists() else {}
    except (OSError, ValueError):
        return {}


# ------------------------------------------------------------------ junk
def drop_junk(pack: Pack, bsa: str, items: list[str], tx: Transaction) -> None:
    bpath = pack.data_dir / bsa
    arc = read_bsa(bpath)
    drop = {i.lower() for i in items}
    _staged(tx, bpath, lambda tmp: rebuild_bsa(arc, tmp, drop=drop))


# ------------------------------------------------------------------ tints
def fix_tints(pack: Pack, bsa: str, fixes: list[dict], tx: Transaction) -> None:
    """fixes: [{"nif": path, "old": tint folder, "new": tint folder}]"""
    by_nif: dict[str, dict] = {}
    for fx in fixes:
        by_nif.setdefault(fx["nif"].lower(), {})[fx["old"].lower()] = fx["new"]
    bpath = pack.data_dir / bsa

    def fn(path, data):
        m = by_nif.get(path)
        if m:
            data, _n = NIF.replace_texture_folders(data, m)
        return path, data
    if not _staged(tx, bpath, lambda tmp: transform_bsa(bpath, tmp, fn)):
        raise BsaFixError("Nothing to change in that BSA anymore.", "Ya no hay nada que cambiar en ese BSA.")


# ------------------------------------------------------------------ diet
def diet(pack: Pack, bsa: str, preset: str, bc1: bool, tools_dir, tx: Transaction, progress=None) -> dict:
    from . import diet as D
    from .tools import locate
    tools = locate(tools_dir)
    if not tools.texconv:
        raise BsaFixError("texconv.exe is missing from the tools folder.",
                          "Falta texconv.exe en la carpeta de herramientas.")
    bpath = pack.data_dir / bsa
    stats = {}

    def writer(tmp):
        stats.update(D.diet_bsa(bpath, tmp, preset, tools, bc1=bc1, progress=progress))
        return stats.get("changed", 0) > 0
    _staged(tx, bpath, writer)
    return stats


# ------------------------------------------------------------------ safe rename
_SEQ = re.compile(r"^seq\\([^\\]+)\.seq$")
_STR = re.compile(r"^strings\\([^\\]+)_([a-z]+)\.(strings|dlstrings|ilstrings)$")


def rename_plan(pack: Pack, old: str, new: str) -> dict:
    """What a full plugin rename touches in this pack (for the preview)."""
    low_old = old.lower()
    stem_old = Path(old).stem.lower()
    needle = low_old.encode("cp1252", "replace")
    plan = {"plugin": None, "bsas_rename": [], "bsas_patch": [], "dependents": [], "list": False,
            "inis": []}
    p = next((f for n, f in pack.data_files.items() if n == low_old), None)
    plan["plugin"] = p.name if p else None
    for b in pack.bsas_for_plugin(old):
        bstem = b.stem
        suffix = bstem[len(Path(old).stem):]
        plan["bsas_rename"].append((b.name, Path(new).stem + suffix + b.suffix))
    for b in pack.bsas.values():
        try:
            arc = read_bsa(b)
        except Exception:  # noqa: BLE001
            continue
        hit = False
        for e in arc.entries:
            folder = e.folder.lower()
            if any(folder.startswith(r + "\\" + low_old) or folder == r + "\\" + low_old
                   for r in NAME_FOLDERS):
                hit = True
                break
            path = e.path.lower()
            m = _SEQ.match(path) or _STR.match(path)
            if m and m.group(1) == stem_old:
                hit = True
                break
        if not hit:
            with b.open("rb") as f:
                for e in arc.entries:
                    n = e.name.lower()
                    if n.endswith(".pex") or (n.endswith(".nif") and e.folder.lower().startswith(FACEGEOM)):
                        if needle in arc.read_file(e, f).lower():
                            hit = True
                            break
        if hit:
            plan["bsas_patch"].append(b.name)
    for h in pack.plugins.values():
        if any(m.lower() == low_old for m in h.masters):
            plan["dependents"].append(h.name)
    plan["list"] = any(e.lstrip("#").lower() == low_old for e in pack.list_entries)
    for ini in pack.inis:
        if any(e.value.lower() == low_old for e in ini.entries if e.key.lower().startswith("stestfile")):
            plan["inis"].append(ini.path.name)
    return plan


def safe_rename(pack: Pack, old: str, new: str, tx: Transaction, progress=None) -> dict:
    data = pack.data_dir
    if (data / new).exists() and new.lower() != old.lower():
        raise BsaFixError(f"{new} already exists.", f"{new} ya existe.")
    plan = rename_plan(pack, old, new)
    if not plan["plugin"]:
        raise BsaFixError(f"{old} isn't in Data.", f"{old} no está en Data.")
    low = {old.lower(): new}
    stem_old, stem_new = Path(old).stem.lower(), Path(new).stem.lower()
    seg_old = old.lower()

    def fn(path, data_):
        parts = path.split("\\")
        for root in NAME_FOLDERS:
            rp = root.split("\\")
            if parts[:len(rp)] == rp and len(parts) > len(rp) and parts[len(rp)] == seg_old:
                parts[len(rp)] = new.lower()
        path2 = "\\".join(parts)
        m = _SEQ.match(path2)
        if m and m.group(1) == stem_old:
            path2 = f"seq\\{stem_new}.seq"
        m = _STR.match(path2)
        if m and m.group(1) == stem_old:
            path2 = f"strings\\{stem_new}_{m.group(2)}.{m.group(3)}"
        if path2.endswith(".nif") and path2.startswith(FACEGEOM):
            try:
                data_, _n = NIF.replace_texture_folders(data_, low)
            except NIF.NifError:
                pass
        elif path2.endswith(".pex") and seg_old.encode("cp1252", "replace") in data_.lower():
            data_, _n = PEX.rename_plugins(data_, low)
        return path2, data_

    # 1. archives with content that names the plugin
    for b in plan["bsas_patch"]:
        bpath = data / b
        if progress:
            progress(f"Updating {b}")
        _staged(tx, bpath, lambda tmp, bp=bpath: transform_bsa(bp, tmp, fn))
    # 2. archives and plugin that carry the name
    for a, b in plan["bsas_rename"]:
        tx.move(data / a, data / b)
    tx.move(data / plan["plugin"], data / new)
    # 3. masters of the plugins that use it
    for dep in plan["dependents"]:
        p = data / (new if dep.lower() == old.lower() else dep)
        out, n = rename_masters(p.read_bytes(), low)
        if n:
            tx.write_bytes(p, out)
    # 4. load list, sTestFile and ini archive lists
    if pack.list_path:
        raw = pack.list_path.read_bytes()
        keys = {e: new for e in C.parse_ccc(raw).entries if e.lower() == old.lower()}
        keys.update({e: "#" + new for e in C.parse_ccc(raw).entries if e.lower() == "#" + old.lower()})
        if keys:
            tx.write_bytes(pack.list_path, C.edit_lines(raw, keys))
    bsa_map = {a.lower(): b for a, b in plan["bsas_rename"]}
    for ini in pack.inis:
        raw = ini.path.read_bytes()
        out = raw
        for e in ini.entries:
            if e.section.lower() == "general" and e.key.lower().startswith("stestfile") \
                    and e.value.lower() == old.lower():
                out = set_value(out, "General", e.key, new)
        for key in ("sResourceArchiveList", "sResourceArchiveList2", "sArchiveToLoadInMemoryList"):
            if parse_ini(out).get("Archive", key) is None:
                continue
            cur = parse_ini(out).archive_list(key)
            if any(c.lower() in bsa_map for c in cur):
                out = set_archive_list(out, key, [bsa_map.get(c.lower(), c) for c in cur])
        if out != raw:
            tx.write_bytes(ini.path, out)
    # 5. the pack's mod records (Mods page, remove, transfers) follow the new names
    from .builder import _save_mods, load_mods
    mods = load_mods(pack)
    touched = False
    for rec in mods.values():
        if not isinstance(rec, dict):
            continue
        pl = rec.get("plugins") or []
        if any(x.lower() == old.lower() for x in pl):
            rec["plugins"] = [new if x.lower() == old.lower() else x for x in pl]
            ren = rec.get("renamed")
            if isinstance(ren, dict):
                ren[new] = ren.pop(old, None) or ren.pop(next((k for k in ren if k.lower() == old.lower()), ""), None) or old
            touched = True
        bs = rec.get("bsas") or []
        if any(b.lower() in bsa_map for b in bs):
            rec["bsas"] = [bsa_map.get(b.lower(), b) for b in bs]
            touched = True
        for e in rec.get("ini") or []:
            if isinstance(e, dict) and str(e.get("bsa", "")).lower() in bsa_map:
                e["bsa"] = bsa_map[e["bsa"].lower()]
                touched = True
    if touched:
        _save_mods(pack, tx, mods)
    # 6. remember the original name (LOOT, converter, FOMOD conditions)
    reg = load_renames(pack)
    orig = reg.pop(old, None) or old
    reg[new] = orig
    tx.write_bytes(renames_file(pack), json.dumps(reg, indent=1, ensure_ascii=False).encode("utf-8"))
    return plan


# ------------------------------------------------------------------ scans for the audit
def scan_tints(pack: Pack, arcs: list[tuple[Path, object]]) -> dict[str, list[dict]]:
    """FaceGen meshes whose tint texture doesn't exist in any archive of the
    pack. Returns {bsa name: [{"nif", "old", "new" or None, "tint"}]}."""
    tints: set[str] = set()
    for _p, arc in arcs:
        for e in arc.entries:
            if e.folder.lower().startswith(FACETINT):
                tints.add(e.path.lower())
    out: dict[str, list[dict]] = {}
    for p, arc in arcs:
        nifs = [e for e in arc.entries if e.name.lower().endswith(".nif")
                and e.folder.lower().startswith(FACEGEOM)]
        if not nifs:
            continue
        with p.open("rb") as f:
            for e in nifs:
                try:
                    paths = NIF.texture_paths(NIF.parse(arc.read_file(e, f)))
                except Exception:  # noqa: BLE001
                    continue
                owner = e.folder.lower()[len(FACEGEOM):].split("\\")[0]
                for t in paths:
                    tl = t.lower().replace("/", "\\")
                    if "facetint\\" not in tl:
                        continue
                    rel = tl[tl.index("textures\\"):] if "textures\\" in tl else "textures\\" + tl
                    seg = rel[len(FACETINT):].split("\\")[0] if rel.startswith(FACETINT) else ""
                    if not seg or seg in GAME_OWNERS or rel in tints:
                        continue
                    alt = FACETINT + owner + "\\" + rel.split("\\")[-1]
                    out.setdefault(p.name, []).append({
                        "nif": e.path, "old": seg, "tint": rel,
                        "new": owner if (alt in tints and owner != seg) else None})
    return out


# ------------------------------------------------------------------ SEQ files
def seq_path(plugin: str) -> str:
    return f"seq\\{Path(plugin).stem.lower()}.seq"


def add_seq(pack: Pack, plugin: str, formids: list[int], tx: Transaction,
            bsa: str | None = None, loose: bool = False) -> None:
    """Write seq\\<plugin>.seq with these quest FormIDs: into the BSA `bsa`
    (rebuilt with the extra file, or created when it doesn't exist yet; a BSA
    named like the plugin loads with it), or loose in Data\\seq."""
    from .records import seq_bytes
    data = seq_bytes(formids)
    rel = seq_path(plugin)
    if loose:
        d = next((p for p in pack.data_dir.iterdir() if p.is_dir() and p.name.lower() == "seq"),
                 pack.data_dir / "seq")
        f = next((p for p in d.iterdir() if p.name.lower() == rel[4:]), d / rel[4:]) if d.is_dir() else d / rel[4:]
        tx.write_bytes(f, data)
        return
    if not bsa:
        raise BsaFixError("No BSA was chosen for the SEQ file.", "No se eligió un BSA para el archivo SEQ.")
    target = pack.data_dir / bsa
    if target.exists():
        ok = _staged(tx, target, lambda tmp: transform_bsa(target, tmp, lambda p, d: (p, d), {rel: data}))
        if not ok:
            raise BsaFixError("That BSA already has this SEQ file.", "Ese BSA ya tiene este archivo SEQ.")
    else:
        src = Path(tempfile.mkdtemp(prefix="skynx-seq-"))
        try:
            (src / "seq").write_bytes(data)
            _staged(tx, target, lambda tmp: write_bsa([(rel, src / "seq")], tmp))
        finally:
            shutil.rmtree(src, ignore_errors=True)
        # the pack's mod record keeps its files together (Mods page, remove)
        from .builder import _save_mods, load_mods
        mods = load_mods(pack)
        for rec in mods.values():
            if isinstance(rec, dict) and any(x.lower() == plugin.lower() for x in rec.get("plugins") or []):
                rec.setdefault("bsas", []).append(bsa)
                _save_mods(pack, tx, mods)
                break


# ------------------------------------------------------------------ short BSA names for the ini
SHORT_OVER = 12          # names longer than this (with .bsa) get a short one


def short_bsa_name(stem: str, taken: set[str]) -> str:
    """'Andromeda - Unique Standing Stones of Skyrim' -> 'AndromUSSoS.bsa' style:
    the first word (6 letters) and the initials of the rest, at most 10
    characters, never a plugin's name (it would load twice) nor a taken one."""
    words = [w for w in re.split(r"[^A-Za-z0-9]+", stem) if w]
    base = ((words[0][:6] if words else "Mod") + "".join(w[0] for w in words[1:]))[:10] or "Mod"
    cand, n = base, 2
    while cand.lower() in taken:
        cand, n = f"{base[:9]}{n}", n + 1
    return cand + ".bsa"


LIST_SHORT_OVER = 22          # plugin names longer than this are worth shortening
# Names other mods' patches and Koka's packs expect as they are
LIST_KEEP = {"unofficial skyrim special edition patch.esp",
             "unofficial skyrim creation club content patch.esl"}


def _words(stem: str) -> list[str]:
    """Words of a name, CamelCase split too: 'AmazingFollowerTweaks' -> 3 words."""
    out = []
    for w in re.split(r"[^A-Za-z0-9]+", stem):
        out += re.findall(r"[A-Z]+(?![a-z])|[A-Z]?[a-z0-9]+|[A-Z]", w) or ([w] if w else [])
    return [w for w in out if w]


GAME_STEMS = {"skyrim", "update", "dawnguard", "dragonborn", "hearthfires", "hyrule"}


def short_plugin_name(name: str, taken: set[str]) -> str:
    """'Wintersun - Faiths of Skyrim.esp' -> 'Wintersun.esp' (the name before the
    dash, Enai style); otherwise, or when that one is taken, first word and
    initials ('OdinOCP.esp', 'AmazingFT.esp', 'LanternsOSI.esm'). Never a name a plugin or BSA has: a plugin named like a
    BSA would load it by name (twice, if the ini loads it too)."""
    ext = Path(name).suffix
    words = _words(Path(name).stem) or ["Mod"]
    first = words[0]
    initials = "".join(w[0].upper() for w in words[1:])[:6]

    def free(stem: str) -> bool:
        low = stem.lower()
        return low not in taken and f"{low} - textures" not in taken

    cands = []
    brand = Path(name).stem.split(" - ", 1)[0].strip()
    if " - " in Path(name).stem and 4 <= len(brand) <= 12 and re.fullmatch(r"[A-Za-z0-9]+", brand) \
            and brand.lower() not in GAME_STEMS:
        cands.append(brand)                       # Enai style: 'Wintersun - Faiths of Skyrim'
    if first.lower() in GAME_STEMS and len(words) > 1:   # 'Skyrim Flora Overhaul' -> 'FloraO'
        words = words[1:]
        first = words[0]
    initials = "".join(w[0].upper() for w in words[1:])[:6]
    cands += [first[:10] + initials, first[:6] + initials]
    for c in cands:
        if c and free(c):
            return c + ext
    base, n = (first[:6] + initials)[:10], 2
    while not free(f"{base}{n}"):
        n += 1
    return f"{base}{n}{ext}"


def plan_list_shorten(pack: Pack) -> list[tuple[str, str]]:
    """(old, new) for the active plugins with long names: every name costs its
    length in the .ccc. Same style as the BSA names (first word and initials),
    never a name a plugin or BSA already has (a plugin named like an ini BSA
    would load it twice)."""
    from . import ccc as C
    raw = pack.list_path.read_bytes() if pack.list_path else b""
    taken = {Path(n).stem.lower() for n in pack.data_files} | {Path(n).stem.lower() for n in pack.plugins}
    out = []
    for e in C.parse_ccc(raw).entries:
        low = e.lower()
        h = pack.plugins.get(low)
        if e.startswith("#") or not h or h.error or len(e) <= LIST_SHORT_OVER or low in LIST_KEEP \
                or pack.is_cc(e) or low.startswith("cc"):
            continue
        new = short_plugin_name(h.name, taken)
        taken.add(Path(new).stem.lower())
        out.append((h.name, new))
    return out


def plan_ini_shorten(pack: Pack, key: str) -> list[tuple[str, str]]:
    """(old, new) for every mod BSA with a long name in this ini list. The
    file is only named in the ini (a BSA in the list loads at its place there,
    by name of plugin or not), so the rename touches nothing else."""
    items: list[str] = []
    for path in pack.inis_for_key(key):
        for b in parse_ini(path.read_bytes()).archive_list(key):
            if b.lower() not in [i.lower() for i in items]:
                items.append(b)
    taken = {Path(n).stem.lower() for n in pack.data_files} | {Path(n).stem.lower() for n in pack.plugins}
    out = []
    for b in items:
        low = b.lower()
        if len(b) <= SHORT_OVER or low.startswith("skyrim - ") or low not in pack.bsas:
            continue
        new = short_bsa_name(Path(b).stem, taken)
        taken.add(Path(new).stem.lower())
        out.append((pack.bsas[low].name, new))
    return out


def rename_ini_bsas(pack: Pack, renames: list[tuple[str, str]], tx: Transaction) -> None:
    """Rename BSA files and every ini list and mod record that names them."""
    data = pack.data_dir
    bsa_map = {}
    for old, new in renames:
        if not (data / old).exists():
            raise BsaFixError(f"{old} isn't in Data.", f"{old} no está en Data.")
        if (data / new).exists():
            raise BsaFixError(f"{new} already exists.", f"{new} ya existe.")
        bsa_map[old.lower()] = new
    for old, new in renames:
        tx.move(data / old, data / new)
    for ini in pack.inis:
        raw = ini.path.read_bytes()
        out = raw
        for key in ("sResourceArchiveList", "sResourceArchiveList2", "sArchiveToLoadInMemoryList"):
            if parse_ini(out).get("Archive", key) is None:
                continue
            cur = parse_ini(out).archive_list(key)
            if any(c.lower() in bsa_map for c in cur):
                out = set_archive_list(out, key, [bsa_map.get(c.lower(), c) for c in cur])
        if out != raw:
            tx.write_bytes(ini.path, out)
    from .builder import _save_mods, load_mods
    mods = load_mods(pack)
    touched = False
    for rec in mods.values():
        if not isinstance(rec, dict):
            continue
        bs = rec.get("bsas") or []
        if any(b.lower() in bsa_map for b in bs):
            rec["bsas"] = [bsa_map.get(b.lower(), b) for b in bs]
            touched = True
        for e in rec.get("ini") or []:
            if isinstance(e, dict) and str(e.get("bsa", "")).lower() in bsa_map:
                e["bsa"] = bsa_map[e["bsa"].lower()]
                touched = True
    if touched:
        _save_mods(pack, tx, mods)
