"""Bring mods from one modpack into another.

    list_pack_mods(src)                       -> [ModUnit]
    plan_transfer(src, dst, unit_ids)         -> TransferPlan (nothing written)
    apply_transfer(plan)                      -> report (one undoable history entry)

A "mod unit" is what a user thinks of as one mod inside a pack:
- a plugin plus the BSAs that load with it by name ("Name.bsa",
  "Name - Textures.bsa");
- plus BSAs listed in the inis that clearly belong to it. Koka-style short
  names are matched by stem: USSEP.bsa / USSEPA / USSEPT / USSEPV ->
  "Unofficial Skyrim Special Edition Patch.esp" (initials), OdnMs/OdnTs ->
  "Odin - Skyrim Magic Overhaul.esp" (letters of the first word), "PyP.bsa" ->
  "PyP_Legendary.esp" (prefix), "EnaiRim_NR - Misc.bsa" -> "EnaiRim_NR.esp".
  FaceGen/voice folders inside a BSA name their plugin and win over names.
  When two plugins fit equally (Odin and "Odin - Vokrii Compatibility Patch"),
  patches lose; when still unsure, the BSA is shown as its own unit;
- BSAs without a plugin (DemoniacMs.bsa + DemoniacTs.bsa) are one unit per stem;
- archives left inside Data (Ashiro's pack ships every mod as a .7z there) are
  one unit each; they are extracted when planned.
"""
from __future__ import annotations

import re
import shutil
import tempfile
import time
from dataclasses import dataclass, field
from pathlib import Path

from . import ccc as C
from . import knowledge as K
from .audit import norm_name, plugin_owners
from .bsa import read_bsa
from .builder import PLUGIN_EXT, _archive_key_for, _save_mods, load_mods
from .converter import renamed_registry
from .errors import SkynxError
from .history import Transaction
from .ini import ARCHIVE_KEYS, ARCHIVE_LIST_LIMIT, parse_ini, set_archive_list
from .intake import list_names, safe_extract
from .pack import Pack
from .plugin import read_header
from .rename import rename_masters
from .textures import inspect as inspect_tex

VANILLA = {m.lower() for m in K.VANILLA_MASTERS + K.SWITCH_MASTERS}
CC_LOWER = {c.lower(): c for c in K.AE_CC_PLUGINS}
PATCH_WORDS = ("patch", "compat", "fix", "addon", "add-on", "plugin")
LONG_SUFFIXES = (" - textures", " - meshes", " - animations", " - voices", " - sounds", " - misc",
                 " - scripts", " - main", "_textures", "_meshes", " textures", " meshes")
KOKA_SUFFIXES = ("Ms", "Ts", "As", "Vs", "Ss", "M", "T", "A", "V", "S")   # case sensitive

FLAGS = {
    "not-in-list": ("Not in the load list", "No está en la lista de carga"),
    "disabled": ("Switched off in the load list (#)", "Desactivado en la lista de carga (#)"),
    "drive-name": ("Name damaged by Google Drive; it's copied as {to}",
                   "Nombre dañado por Google Drive; se copia como {to}"),
    "list-name": ("The load list calls it {list}; the file is {file}, and that name is used",
                  "La lista de carga lo llama {list}; el archivo es {file}, y se usa ese nombre"),
    "drive-maybe": ("The name may have been damaged by Google Drive; nothing inside says what it "
                    "should be, so it keeps it",
                    "Puede que Google Drive haya dañado el nombre; nada adentro dice cuál debería "
                    "ser, así que se conserva"),
    "twin": ("Leftover copy of {of} with a Drive-damaged name",
             "Copia sobrante de {of} con el nombre dañado por Drive"),
    "bsa-only": ("BSA without a plugin, loaded from the ini", "BSA sin plugin, cargado desde el ini"),
    "not-loaded": ("Nothing loads {name} in this pack", "Nada carga {name} en este pack"),
    "unsure": ("I'm not sure which mod {name} belongs to, so it's shown on its own",
               "No estoy seguro de a qué mod pertenece {name}, así que se muestra aparte"),
    "esl": ("Light plugin (ESL): Anniversary Edition only", "Plugin ligero (ESL): solo Anniversary Edition"),
    "archive": ("Still packed as {name} inside Data; it's extracted when you bring it",
                "Sigue comprimido como {name} dentro de Data; se extrae al traerlo"),
    "dummy": ("Empty plugin whose only job is loading its BSAs",
              "Plugin vacío que solo sirve para cargar sus BSA"),
    "empty-bsa": ("{name} is empty", "{name} está vacío"),
    "unreadable": ("{name} can't be read", "{name} no se puede leer"),
    "stest": ("Loaded through sTestFile in the ini", "Se carga con sTestFile en el ini"),
}


class TransferError(SkynxError):
    pass


def _flag(code: str, **params) -> dict:
    return {"code": code, "params": params}


def _flag_text(f: dict, lang: str) -> str:
    en, es = FLAGS[f["code"]]
    return (es if lang == "es" else en).format(**f["params"])


def _pick(t, lang: str) -> str:
    return t[1] if lang == "es" else t[0]


# ---------------------------------------------------------------- BSA facts
_BSA_CACHE: dict[tuple, dict] = {}


def bsa_facts(path: Path, textures: bool = True) -> dict:
    """entries, owners (plugin-named folders), texture RAM. Cached by file state."""
    path = Path(path)
    try:
        st = path.stat()
    except OSError as e:
        return {"error": str(e), "entries": 0, "owners": {}, "tex": None}
    key = (str(path), st.st_mtime, st.st_size, textures)
    if key in _BSA_CACHE:
        return _BSA_CACHE[key]
    out = {"error": None, "entries": 0, "owners": {}, "tex": 0 if textures else None}
    try:
        arc = read_bsa(path)
        out["entries"] = len(arc.entries)
        out["owners"] = plugin_owners(arc)
        if textures:
            with path.open("rb") as f:
                for e in arc.entries:
                    if e.name.lower().endswith(".dds"):
                        info = inspect_tex(arc.read_head(e, 256, f))
                        if info:
                            out["tex"] += info.est_bytes
    except Exception as e:  # noqa: BLE001
        out["error"] = str(e)
        out["tex"] = None
    _BSA_CACHE[key] = out
    return out


# ---------------------------------------------------------------- stems
def _cores(stem: str) -> list[str]:
    out = [stem]
    low = stem.lower()
    for s in LONG_SUFFIXES:
        if low.endswith(s) and len(stem) - len(s) >= 3:
            out.append(stem[: -len(s)].rstrip(" -_"))
    for s in KOKA_SUFFIXES:
        if stem.endswith(s) and len(stem) - len(s) >= 3 and stem[-len(s) - 1].isalnum():
            out.append(stem[: -len(s)])
            break
    return out


def _words(stem: str) -> list[str]:
    return [w for w in re.split(r"[\s_\-.]+", stem) if w]


def _initials(stem: str) -> str:
    return "".join(w[0] for w in _words(stem) if w[0].isalnum()).lower()


def _subseq(c: str, w: str) -> bool:
    it = iter(w)
    return all(ch in it for ch in c)


def stem_score(core: str, plugin_stem: str) -> int:
    """How well a BSA name core points at a plugin. 0 = not at all."""
    c, p = core.lower(), plugin_stem.lower()
    if len(c) < 3:
        return 0
    if c == p:
        return 100
    if _initials(plugin_stem) == c:
        return 90
    if p.startswith(c) and (len(p) == len(c) or not p[len(c)].isalnum()):
        return 80
    words = _words(plugin_stem)
    w = words[0].lower() if words else ""
    if w.startswith(c):
        return 70
    if w[:1] == c[0] and _subseq(c, w) and len(c) >= 0.45 * len(w):
        return 60
    return 0


def owner_for_bsa(bsa_name: str, plugin_names: list[str]) -> tuple[str | None, int]:
    """Best plugin for an ini-loaded BSA by its name, or None when unsure."""
    best, cands = 0, []
    for core in _cores(Path(bsa_name).stem):
        for p in plugin_names:
            s = stem_score(core, Path(p).stem)
            if s > best:
                best, cands = s, [p]
            elif s == best and s and p not in cands:
                cands.append(p)
    if len(cands) > 1:
        main = [p for p in cands if not any(w in p.lower() for w in PATCH_WORDS)]
        cands = main if main else cands
    if best >= 60 and len(cands) == 1:
        return cands[0], best
    return None, best


def _respell(file_name: str, wanted_lower: str) -> str | None:
    """'Ryn_s X.esp' + "ryn's x.esp" -> "Ryn's X.esp" (keeps the file's case)."""
    if len(file_name) != len(wanted_lower):
        return None
    out = []
    for a, b in zip(file_name, wanted_lower):
        if a.lower() == b:
            out.append(a)
        elif a == "_" and b in "'’":
            out.append(b)
        else:
            return None
    return "".join(out)


# ---------------------------------------------------------------- units
@dataclass
class ModUnit:
    id: str
    kind: str                       # "plugin", "bsa" or "archive"
    name: str
    plugins: list[str] = field(default_factory=list)     # file names in the source
    bsas: list[str] = field(default_factory=list)
    files: dict[str, Path] = field(default_factory=dict)  # file name -> source path
    target: dict[str, str] = field(default_factory=dict)  # file name -> name in the destination
    ini: dict[str, list[str]] = field(default_factory=dict)  # source key -> file names
    masters: list[str] | None = field(default_factory=list)
    size: int = 0
    tex_bytes: int | None = 0
    light: bool = False
    position: int | None = None
    list_name: str | None = None
    grouped_by: dict[str, str] = field(default_factory=dict)  # bsa -> how it was grouped
    flags: list[dict] = field(default_factory=list)
    twin_of: str | None = None
    archive: Path | None = None
    renamed: dict[str, str] = field(default_factory=dict)  # converter renames (new -> original)
    meta: dict = field(default_factory=dict)               # copied from the source mods.json

    def has(self, code: str) -> bool:
        return any(f["code"] == code for f in self.flags)

    def to_dict(self, lang: str = "en") -> dict:
        return {"id": self.id, "kind": self.kind, "name": self.name, "plugins": self.plugins,
                "bsas": self.bsas, "target": self.target, "ini": self.ini,
                "masters": self.masters, "size": self.size, "tex_bytes": self.tex_bytes,
                "light": self.light, "position": self.position, "list_name": self.list_name,
                "grouped_by": self.grouped_by, "twin_of": self.twin_of,
                "flags": [{"code": f["code"], "text": _flag_text(f, lang)} for f in self.flags]}


def _ini_membership(pack: Pack) -> tuple[dict[str, list[str]], dict[str, str]]:
    """lower BSA name -> keys of every ini that lists it; norm name -> lower name."""
    keys: dict[str, list[str]] = {}
    for ini in pack.inis:
        for key in ARCHIVE_KEYS:
            if ini.get("Archive", key) is None:
                continue
            for b in ini.archive_list(key):
                lst = keys.setdefault(b.lower(), [])
                if key not in lst:
                    lst.append(key)
    return keys, {norm_name(k): k for k in keys}


def _src_records(pack: Pack) -> dict[str, dict]:
    """lower plugin/BSA name -> the mods.json record that added it."""
    out = {}
    for rec in load_mods(pack).values():
        for f in rec.get("plugins", []) + rec.get("bsas", []):
            out[f.lower()] = rec
    return out


def list_pack_mods(src_pack: Pack, textures: bool = True, progress=None) -> list[ModUnit]:
    pack = src_pack
    tick = progress or (lambda *a, **k: None)
    if not pack.data_dir:
        raise TransferError("This modpack has no Data folder", "Este modpack no tiene carpeta Data")
    ini_keys, ini_norm = _ini_membership(pack)
    records = _src_records(pack)
    reg_new = {v.lower(): k for k, v in renamed_registry(pack).items()}   # new lower -> orig lower
    plugins = pack.plugins
    order = pack.load_order()

    # --- load list -> files
    pos: dict[str, tuple[int, str, bool, str]] = {}   # file lower -> (index, spelling, disabled, src)
    norm_files: dict[str, list[str]] = {}
    for low in plugins:
        norm_files.setdefault(norm_name(low), []).append(low)
    for i, (e, src) in enumerate(order):
        disabled = e.startswith("#")
        name = e[1:].strip() if disabled else e
        low = name.lower()
        if low in VANILLA:
            continue
        if low in plugins:
            pos.setdefault(low, (i, name, disabled, src))
            continue
        cands = [f for f in norm_files.get(norm_name(low), []) if f not in pos]
        if len(cands) == 1:
            pos.setdefault(cands[0], (i, name, disabled, src))

    # --- twins: same name once Drive's damage is folded
    twin_of: dict[str, str] = {}
    for n, group in norm_files.items():
        if len(group) < 2:
            continue
        exact = [g for g in group if g in pos and pos[g][1].lower() == g]
        primary = exact[0] if exact else min(group, key=lambda g: pos.get(g, (10**9,))[0])
        for g in group:
            if g != primary:
                twin_of[g] = primary

    # --- BSAs by name, then by folded name
    assigned: dict[str, tuple[str, str]] = {}      # bsa lower -> (plugin lower, how)
    for low, h in plugins.items():
        for b in pack.bsas_for_plugin(h.name):
            assigned[b.name.lower()] = (low, "name")
    norm_stem = {}
    for low in plugins:
        if low not in twin_of:
            norm_stem[norm_name(Path(low).stem)] = low
    for blow in pack.bsas:
        if blow in assigned:
            continue
        s = norm_name(Path(blow).stem)
        base = s[:-11] if s.endswith(" - textures") else s
        if base in norm_stem:
            assigned[blow] = (norm_stem[base], "name")
    # --- ini-loaded BSAs: plugin-named folders inside, then stems
    pool = [plugins[low].name for low in plugins if low not in twin_of]
    unsure: set[str] = set()
    facts: dict[str, dict] = {}
    for i, (blow, bp) in enumerate(sorted(pack.bsas.items())):
        if i % 10 == 0:
            tick(bp.name, i, len(pack.bsas))
        facts[blow] = bsa_facts(bp, textures)
    for blow, bp in sorted(pack.bsas.items()):
        if blow in assigned:
            continue
        if blow not in ini_keys and norm_name(blow) not in ini_norm:
            continue
        owners = facts[blow]["owners"]
        hits = {norm_stem.get(norm_name(Path(o).stem)) for o in owners} - {None}
        if len(hits) == 1:
            assigned[blow] = (hits.pop(), "owner")
            continue
        p, score = owner_for_bsa(bp.name, pool)
        if p:
            assigned[blow] = (p.lower(), "ini-stem")
        elif score:
            unsure.add(blow)

    def keys_of(name: str) -> list[str]:
        low = name.lower()
        if low in ini_keys:
            return ini_keys[low]
        alt = ini_norm.get(norm_name(low))
        return ini_keys.get(alt, []) if alt else []

    units: list[ModUnit] = []
    # --- plugin units
    for low, h in plugins.items():
        u = ModUnit(id=f"plugin:{h.name}", kind="plugin", name=h.name, plugins=[h.name])
        u.bsas = sorted(pack.bsas[b].name for b, (p, _) in assigned.items() if p == low)
        u.grouped_by = {pack.bsas[b].name: how for b, (p, how) in assigned.items() if p == low}
        u.files = {f: pack.data_dir / f for f in u.plugins + u.bsas}
        u.masters = list(h.masters)
        u.light = h.extension == ".esl" or h.is_light_flag
        if low in pos:
            u.position, u.list_name, disabled, src = pos[low]
            if disabled:
                u.flags.append(_flag("disabled"))
            if src == "ini":
                u.flags.append(_flag("stest"))
        elif low in twin_of:
            u.twin_of = plugins[twin_of[low]].name
            u.flags.append(_flag("twin", of=u.twin_of))
            u.flags.append(_flag("not-in-list"))
        else:
            u.flags.append(_flag("not-in-list"))
        if u.light:
            u.flags.append(_flag("esl"))
        if h.is_dummy and u.bsas:
            u.flags.append(_flag("dummy"))
        if low in reg_new:
            u.renamed = {h.name: reg_new[low]}
        rec = records.get(low)
        if rec:
            u.meta = {k: rec[k] for k in ("converted", "fomod", "fomod_choices", "fomod_module", "source")
                      if k in rec}
        _name_fix(u, h.name, pack, facts, twin_of)
        units.append(u)
    # --- BSA units (no plugin)
    groups: dict[str, list[str]] = {}
    for blow, bp in sorted(pack.bsas.items()):
        if blow in assigned:
            continue
        core = _cores(Path(bp.name).stem)[-1].lower()
        groups.setdefault(core, []).append(bp.name)
    for core, names in groups.items():
        loaded = [n for n in names if keys_of(n)]
        label = names[0] if len(names) == 1 else _cores(Path(names[0]).stem)[-1]
        u = ModUnit(id=f"bsa:{label}", kind="bsa", name=label, bsas=sorted(names))
        u.files = {n: pack.data_dir / n for n in names}
        u.grouped_by = {n: ("alone" if len(names) == 1 else "stem") for n in names}
        u.masters = []
        u.flags.append(_flag("bsa-only"))
        for n in names:
            if n not in loaded:
                u.flags.append(_flag("not-loaded", name=n))
            if n.lower() in unsure:
                u.flags.append(_flag("unsure", name=n))
        u.target = {n: n for n in names}
        units.append(u)
    # --- shared bits
    for u in units:
        u.ini = {}
        for n in u.bsas:
            for k in keys_of(n):
                u.ini.setdefault(k, []).append(n)
            f = facts.get(n.lower()) or {}
            if f.get("error"):
                u.flags.append(_flag("unreadable", name=n))
            elif f.get("entries") == 0:
                u.flags.append(_flag("empty-bsa", name=n))
        u.size = sum(p.stat().st_size for p in u.files.values() if p.exists())
        texs = [(facts.get(n.lower()) or {}).get("tex") for n in u.bsas]
        u.tex_bytes = sum(texs) if textures and None not in texs else None
    # --- archives left in Data
    for a in sorted(pack.archives, key=lambda p: p.name.lower()):
        if a.suffix.lower() not in (".7z", ".zip"):
            continue
        try:
            inner = [m for m in list_names(a) if not m.is_dir]
        except Exception:  # noqa: BLE001
            continue
        u = ModUnit(id=f"archive:{a.name}", kind="archive", name=a.stem, archive=a)
        u.plugins = sorted(Path(m.name).name for m in inner if Path(m.name).suffix.lower() in PLUGIN_EXT)
        u.bsas = sorted(Path(m.name).name for m in inner if m.name.lower().endswith(".bsa"))
        u.masters, u.tex_bytes, u.size = None, None, a.stat().st_size
        u.flags.append(_flag("archive", name=a.name))
        idx = [i for i, (e, _s) in enumerate(order)
               if e.lower() in {p.lower() for p in u.plugins}]
        u.position = min(idx) if idx else None
        for n in u.bsas:
            for k in keys_of(n):
                u.ini.setdefault(k, []).append(n)
        u.grouped_by = {n: "archive" for n in u.bsas}
        units.append(u)
    units.sort(key=lambda u: (u.position is None, u.position if u.position is not None else 0,
                              u.kind != "plugin", u.name.lower()))
    return units


def _name_fix(u: ModUnit, fname: str, pack: Pack, facts: dict, twin_of: dict) -> None:
    """Pick the destination name of a plugin (and its by-name BSAs)."""
    want = None
    if fname.lower() not in twin_of:
        for b in u.bsas:
            for o in (facts.get(b.lower()) or {}).get("owners", {}):
                if o != fname.lower() and norm_name(o) == norm_name(fname):
                    want = want or _respell(fname, o)
        if not want:
            for h in pack.plugins.values():
                for m in h.masters:
                    if m.lower() != fname.lower() and norm_name(m) == norm_name(fname):
                        want = want or m
    target = want or fname
    old_stem, new_stem = Path(fname).stem, Path(target).stem
    u.target = {fname: target}
    for b in u.bsas:
        by_name = u.grouped_by.get(b) == "name" and b.lower().startswith(old_stem.lower())
        u.target[b] = (new_stem + b[len(old_stem):]) if by_name and want else b
    if want:
        u.flags.append(_flag("drive-name", to=target))
    elif u.list_name and u.list_name != fname and u.list_name.lower() != fname.lower():
        u.flags.append(_flag("list-name", list=u.list_name, file=fname))
    elif re.search(r"[A-Za-z]_s(?![a-z])", Path(fname).stem) and not u.twin_of:
        u.flags.append(_flag("drive-maybe"))


# ---------------------------------------------------------------- planning
@dataclass
class TransferPlan:
    src: Pack
    dst: Pack
    src_name: str
    units: list[dict] = field(default_factory=list)     # brought: {"unit", "reason", "needed_by"}
    skipped: list[dict] = field(default_factory=list)   # {"id", "name", "reason": (en, es)}
    refused: list[dict] = field(default_factory=list)
    missing_masters: list[dict] = field(default_factory=list)   # {"plugin", "master"}
    cc_added: list[str] = field(default_factory=list)
    copies: list[tuple[Path, str, str]] = field(default_factory=list)  # (src, dst name, unit id)
    patch_masters: dict[str, dict[str, str]] = field(default_factory=dict)
    list_before: bytes = b""
    list_after: bytes = b""
    list_added: list[str] = field(default_factory=list)
    ini_before: dict[Path, bytes] = field(default_factory=dict)
    ini_after: dict[Path, bytes] = field(default_factory=dict)
    ini_added: list[tuple[str, str, str]] = field(default_factory=list)   # (ini, key, bsa)
    budget: dict = field(default_factory=dict)
    notes: list[tuple[str, str]] = field(default_factory=list)
    errors: list[tuple[str, str]] = field(default_factory=list)   # block apply
    work: Path | None = None

    @property
    def ok(self) -> bool:
        return not self.errors and bool(self.copies or self.list_added or self.ini_added)

    def cleanup(self) -> None:
        if self.work:
            shutil.rmtree(self.work, ignore_errors=True)
            self.work = None

    def to_dict(self, lang: str = "en") -> dict:
        return {
            "src": self.src_name, "dst": self.dst.root.name, "ok": self.ok,
            "units": [{**b["unit"].to_dict(lang), "reason": b["reason"], "needed_by": b["needed_by"],
                       "reason_text": _pick(b["reason_text"], lang) if b.get("reason_text") else None}
                      for b in self.units],
            "skipped": [{"id": s["id"], "name": s["name"], "reason": _pick(s["reason"], lang)}
                        for s in self.skipped],
            "refused": [{"id": s["id"], "name": s["name"], "reason": _pick(s["reason"], lang)}
                        for s in self.refused],
            "missing_masters": self.missing_masters, "cc_added": self.cc_added,
            "copies": [{"from": str(s), "to": d, "unit": u} for s, d, u in self.copies],
            "patch_masters": self.patch_masters, "list_added": self.list_added,
            "ini_added": [{"ini": i, "key": k, "bsa": b} for i, k, b in self.ini_added],
            "budget": self.budget,
            "notes": [_pick(n, lang) for n in self.notes],
            "errors": [_pick(e, lang) for e in self.errors]}


def _expand_archive(u: ModUnit, plan: TransferPlan, tick, edition: str | None = None) -> None:
    if u.files or u.archive is None:
        return
    if plan.work is None:
        plan.work = Path(tempfile.mkdtemp(prefix="skynx-transfer-"))
    out = plan.work / f"{len(list(plan.work.iterdir())):03d}"
    tick(u.archive.name)
    safe_extract(u.archive, out, tick)
    from . import variants as VA
    vres = VA.choose(VA.files_of(out), edition)        # the destination's AE or SE build
    vn = VA.note(vres)
    if vn:
        plan.notes.append((f"{u.archive.name}: {vn[0]}", f"{u.archive.name}: {vn[1]}"))
    found: dict[str, Path] = {}
    for p in sorted(out.rglob("*")):
        if VA.skipped(p.relative_to(out).as_posix(), vres["skip"]):
            continue
        if p.is_file() and (p.suffix.lower() in PLUGIN_EXT or p.suffix.lower() == ".bsa"):
            if p.name.lower() in {k.lower() for k in found}:
                plan.notes.append((f"{u.archive.name} has two files named {p.name}; I took the first.",
                                   f"{u.archive.name} trae dos archivos llamados {p.name}; tomé el primero."))
                continue
            found[p.name] = p
    u.files = found
    u.plugins = sorted(n for n in found if Path(n).suffix.lower() in PLUGIN_EXT)
    u.bsas = sorted(n for n in found if n.lower().endswith(".bsa"))
    u.target = {n: n for n in found}
    u.masters = []
    for n in u.plugins:
        h = read_header(found[n])
        u.light = u.light or h.extension == ".esl" or h.is_light_flag
        for m in h.masters:
            if m not in u.masters:
                u.masters.append(m)
    texs = [bsa_facts(found[n]).get("tex") for n in u.bsas]
    u.tex_bytes = sum(t or 0 for t in texs)
    u.size = sum(p.stat().st_size for p in found.values())


def _unit_masters(u: ModUnit) -> dict[str, list[str]]:
    """plugin file name -> its masters."""
    out = {}
    for p in u.plugins:
        path = u.files.get(p)
        out[p] = read_header(path).masters if path and path.exists() else []
    return out


def _sizes_equal(a: Path, b: Path) -> bool:
    try:
        return a.stat().st_size == b.stat().st_size
    except OSError:
        return False


def plan_transfer(src_pack: Pack, dst_pack: Pack, unit_ids: list[str],
                  units: list[ModUnit] | None = None, progress=None) -> TransferPlan:
    src, dst = src_pack, dst_pack
    tick = progress or (lambda *a, **k: None)
    if Path(src.root).resolve() == Path(dst.root).resolve():
        raise TransferError("The source and the destination are the same modpack",
                            "El origen y el destino son el mismo modpack")
    if not dst.data_dir:
        raise TransferError("The destination modpack has no Data folder",
                            "El modpack de destino no tiene carpeta Data")
    if dst.mode not in ("AE", "SE") or not dst.list_path:
        raise TransferError("The destination modpack has no load list (Skyrim_aoc.ccc or Plugins)",
                            "El modpack de destino no tiene lista de carga (Skyrim_aoc.ccc o Plugins)")
    units = units if units is not None else list_pack_mods(src, progress=tick)
    by_id = {u.id: u for u in units}
    bad = [i for i in unit_ids if i not in by_id]
    if bad:
        raise TransferError("These mods aren't in the source pack: " + ", ".join(bad),
                            "Estos mods no están en el pack de origen: " + ", ".join(bad))
    plan = TransferPlan(src, dst, src.root.name)
    try:
        _plan(plan, units, by_id, unit_ids, tick)
    except BaseException:
        plan.cleanup()
        raise
    return plan


def _plan(plan: TransferPlan, units: list[ModUnit], by_id: dict, unit_ids: list[str], tick) -> None:
    src, dst = plan.src, plan.dst
    dst_reg = renamed_registry(dst)                                 # orig lower -> new
    dst_list = [e for e in dst.list_entries if not e.startswith("#")]
    dst_names = {h.name.lower(): h.name for h in dst.plugins.values()}
    dst_names.update({e.lower(): e for e in dst_list})
    dst_norm = {norm_name(n): n for n in dst_names.values()}
    src_reg = renamed_registry(src)                                 # orig lower -> new lower-case-ish

    # who provides a plugin name inside the source
    def provider(m: str) -> ModUnit | None:
        ml = m.lower()
        if ml in src_reg:
            ml = src_reg[ml].lower()
        for u in units:
            names = {p.lower() for p in u.plugins} | {u.target.get(p, p).lower() for p in u.plugins}
            if ml in names and not u.twin_of:
                return u
        for u in units:
            if any(norm_name(p) == norm_name(ml) for p in u.plugins) and not u.twin_of:
                return u
        return None

    bring: dict[str, dict] = {}
    done: set[str] = set()
    provided: dict[str, str] = {}          # lower plugin name (any spelling) -> final name
    queue = [(i, "selected", None) for i in unit_ids]
    while queue:
        uid, reason, needer = queue.pop(0)
        u = by_id[uid]
        if uid in bring:
            if needer and needer not in bring[uid]["needed_by"]:
                bring[uid]["needed_by"].append(needer)
            continue
        if uid in done:
            continue
        done.add(uid)
        if u.kind == "archive":
            _expand_archive(u, plan, tick, dst.mode)
        if u.twin_of and f"plugin:{u.twin_of}" in [q[0] for q in queue] + list(bring) + list(unit_ids):
            plan.skipped.append({"id": uid, "name": u.name, "reason": (
                f"Same mod as {u.twin_of}, which is coming already",
                f"Es el mismo mod que {u.twin_of}, que ya viene")})
            continue
        if dst.mode == "SE" and u.light and any(p.lower().endswith(".esl") for p in u.plugins):
            plan.refused.append({"id": uid, "name": u.name, "reason": (
                "It's an ESL (light plugin); the SE version can't load it. Extract it and open it "
                "from Convert mods, which turns it into an .esp",
                "Es un ESL (plugin ligero); la versión SE no lo carga. Extráelo y ábrelo desde "
                "Convertir mods, que lo pasa a .esp")})
            continue
        if dst.mode == "SE":
            from .edition import cc_masters, low_formids
            se_notes, cc = [], []
            for pn in u.plugins:
                fp = u.files.get(pn)
                if fp is None:
                    continue
                h = read_header(Path(fp))
                cc += cc_masters(h.masters)
                if h.is_light_flag:
                    se_notes.append((f"{pn} loses its ESL flag so SE loads it.",
                                     f"{pn} pierde la marca ESL para que SE lo cargue."))
                if round(h.hedr_version, 2) >= 1.71:
                    if low_formids(Path(fp).read_bytes()) == 0:
                        se_notes.append((f"{pn} goes from HEDR 1.71 to 1.70 so SE loads it.",
                                         f"{pn} pasa de HEDR 1.71 a 1.70 para que SE lo cargue."))
                    else:
                        se_notes.append((f"{pn} is HEDR 1.71 with records below 0x800: it stays 1.71 and SE may "
                                         "ignore it; the Doctor explains how to fix it.",
                                         f"{pn} es HEDR 1.71 con registros por debajo de 0x800: queda en 1.71 y SE "
                                         "puede ignorarlo; el Doctor explica cómo arreglarlo."))
            if cc:
                plan.refused.append({"id": uid, "name": u.name, "reason": (
                    f"It needs Creation Club content ({', '.join(sorted(set(cc))[:3])}), which the SE version doesn't have",
                    f"Necesita contenido del Creation Club ({', '.join(sorted(set(cc))[:3])}), que la versión SE no tiene")})
                continue
            plan.notes += se_notes
        # what's already in the destination
        same, clash = [], []
        for f, path in u.files.items():
            t = u.target.get(f, f)
            there = dst.data_files.get(t.lower())
            if there is None:
                twin = next((n for n in dst.data_files if norm_name(n) == norm_name(t)), None)
                there = dst.data_files.get(twin) if twin else None
            if there is not None:
                (same if _sizes_equal(path, there) else clash).append((f, there.name))
        renamed_there = [dst_reg[p.lower()] for p in u.plugins if p.lower() in dst_reg] + \
            [dst_reg[o.lower()] for o in u.renamed.values() if o.lower() in dst_reg]
        if clash:
            plan.refused.append({"id": uid, "name": u.name, "reason": (
                "The destination already has a different " + ", ".join(c[1] for c in clash) +
                ". Remove it there first.",
                "El destino ya tiene otro " + ", ".join(c[1] for c in clash) +
                ". Quítalo allá primero.")})
            continue
        if renamed_there or (u.files and len(same) == len(u.files)):
            names = renamed_there or [s[1] for s in same]
            plan.skipped.append({"id": uid, "name": u.name, "reason": (
                "Already in the destination (" + ", ".join(names) + ")",
                "Ya está en el destino (" + ", ".join(names) + ")")})
            for p in u.plugins:
                provided[p.lower()] = dst_names.get(u.target.get(p, p).lower(), u.target.get(p, p))
            continue
        entry = {"unit": u, "reason": reason, "needed_by": [needer] if needer else [],
                 "same": {f for f, _ in same}}
        if reason == "master":
            entry["reason_text"] = (f"Added because {needer} needs it", f"Se agrega porque {needer} lo necesita")
        bring[uid] = entry
        for p in u.plugins:
            final = u.target.get(p, p)
            provided[p.lower()] = provided[final.lower()] = final
            for o in u.renamed.values():
                provided[o.lower()] = final
        # masters
        for p, masters in _unit_masters(u).items():
            final_p = u.target.get(p, p)
            for m in masters:
                ml = m.lower()
                if ml in VANILLA or ml in {q.lower() for q in u.plugins}:
                    continue
                if ml in dst_names:
                    continue
                if ml in dst_reg:
                    plan.patch_masters.setdefault(final_p, {})[ml] = dst_reg[ml]
                    continue
                if norm_name(ml) in dst_norm:
                    plan.patch_masters.setdefault(final_p, {})[ml] = dst_norm[norm_name(ml)]
                    continue
                if ml.startswith("cc") and ml in CC_LOWER:
                    if dst.mode == "AE":
                        if CC_LOWER[ml] not in plan.cc_added:
                            plan.cc_added.append(CC_LOWER[ml])
                            plan.notes.append((f"{CC_LOWER[ml]} added to the load list because "
                                               f"{final_p} needs it",
                                               f"{CC_LOWER[ml]} se agrega a la lista de carga porque "
                                               f"{final_p} lo necesita"))
                    else:
                        plan.missing_masters.append({"plugin": final_p, "master": m})
                    continue
                prov = provider(m)
                if prov is not None and prov.id != uid:
                    queue.append((prov.id, "master", final_p))
                    continue
                plan.missing_masters.append({"plugin": final_p, "master": m})
    # masters whose name changed on the way (Drive fixes, converter renames)
    for entry in bring.values():
        u = entry["unit"]
        for p, masters in _unit_masters(u).items():
            final_p = u.target.get(p, p)
            for m in masters:
                if m.lower() in dst_names or m.lower() in VANILLA:
                    continue
                new = provided.get(m.lower())
                if new is None:
                    alt = next((v for k, v in provided.items() if norm_name(k) == norm_name(m)), None)
                    new = alt
                if new and new.lower() != m.lower():
                    plan.patch_masters.setdefault(final_p, {})[m.lower()] = new
    # a master that later turned out refused is missing after all
    refused_names = {p.lower() for r in plan.refused for p in by_id[r["id"]].plugins}
    for entry in bring.values():
        for p, masters in _unit_masters(entry["unit"]).items():
            for m in masters:
                if m.lower() in refused_names and m.lower() not in dst_names:
                    plan.missing_masters.append({"plugin": entry["unit"].target.get(p, p), "master": m})
    plan.units = sorted(bring.values(), key=lambda b: (b["unit"].position is None,
                                                         b["unit"].position or 0, b["unit"].name.lower()))
    # files to copy
    taken: dict[str, str] = {}
    for b in plan.units:
        u = b["unit"]
        for f, path in u.files.items():
            if f in b["same"]:
                continue
            t = u.target.get(f, f)
            if t.lower() in taken:
                plan.errors.append((f"Two mods want to write {t} ({taken[t.lower()]} and {u.name})",
                                    f"Dos mods quieren escribir {t} ({taken[t.lower()]} y {u.name})"))
                continue
            taken[t.lower()] = u.name
            plan.copies.append((path, t, u.id))
        if u.has("disabled"):
            plan.notes.append((f"{u.name} was switched off (#) in {plan.src_name}; it comes switched on.",
                               f"{u.name} estaba desactivado (#) en {plan.src_name}; llega activado."))
    _plan_list(plan)
    _plan_inis(plan)
    _plan_budget(plan)
    for mm in plan.missing_masters:
        plan.notes.append((f"{mm['plugin']} needs {mm['master']}, which neither pack has",
                           f"{mm['plugin']} necesita {mm['master']}, que no tiene ninguno de los dos packs"))


def _plan_list(plan: TransferPlan) -> None:
    dst = plan.dst
    raw = dst.list_path.read_bytes() if dst.list_path.exists() else b""
    plan.list_before = raw
    existing = C.parse_ccc(raw).entries
    have = {e.lower() for e in existing}
    new: list[tuple[str, list[str]]] = []
    for b in plan.units:
        u = b["unit"]
        ms = _unit_masters(u)
        for p in u.plugins:
            t = u.target.get(p, p)
            if t.lower() in have:
                plan.notes.append((f"{t} was already in the load list; it keeps its place.",
                                   f"{t} ya estaba en la lista de carga; conserva su lugar."))
                continue
            masters = [plan.patch_masters.get(t, {}).get(m.lower(), m) for m in ms.get(p, [])]
            new.append((t, masters))
            have.add(t.lower())
    # masters first, otherwise the source's order
    names = {n.lower(): n for n, _ in new}
    deps = {n.lower(): [m.lower() for m in ms if m.lower() in names] for n, ms in new}
    out, seen = [], set()

    def visit(n, stack=()):
        if n in seen or n in stack:
            return
        for m in deps[n]:
            visit(m, stack + (n,))
        seen.add(n)
        out.append(names[n])
    for n, _ in new:
        visit(n.lower())
    cc = [c for c in plan.cc_added if c.lower() not in {e.lower() for e in existing}]
    plan.cc_added = cc
    last_cc = max((i for i, e in enumerate(existing) if e.lower().startswith("cc")), default=None)
    at = len(existing) if last_cc is None else last_cc + 1
    final = existing[:at] + cc + existing[at:] + out
    plan.list_added = cc + out
    plan.list_after = C.reorder(raw, final) if plan.list_added else raw


def _plan_inis(plan: TransferPlan) -> None:
    dst = plan.dst
    current: dict[Path, bytes] = {p: p.read_bytes() for p in dst.ini_paths if p.exists()}
    plan.ini_before = dict(current)
    want: list[tuple[str, str]] = []           # (key, bsa) in order
    for b in plan.units:
        u = b["unit"]
        targets = {f: u.target.get(f, f) for f in u.bsas}
        listed = set()
        for key, names in u.ini.items():
            for n in names:
                if n in targets:
                    # The in-memory list only costs RAM (KokaNX, Oct 2026): the
                    # BSA comes over in its resource list and not in that one.
                    if key != "sArchiveToLoadInMemoryList":
                        want.append((key, targets[n]))
                        listed.add(n)
        if u.kind == "bsa":
            for n in u.bsas:
                if n in listed or n not in u.files:
                    continue
                keys = _archive_key_for(u.files[n])
                for key in keys:
                    want.append((key, targets[n]))
                plan.notes.append((f"Nothing loaded {n} in {plan.src_name}; I'll add it to "
                                   f"{', '.join(keys)} by what it contains.",
                                   f"Nada cargaba {n} en {plan.src_name}; lo agrego a "
                                   f"{', '.join(keys)} según lo que trae."))
        if u.kind == "archive":
            plugin_stems = {Path(p).stem.lower() for p in u.plugins}
            for n in u.bsas:
                s = Path(n).stem.lower()
                if n in listed or s in plugin_stems or (s.endswith(" - textures") and s[:-11] in plugin_stems):
                    continue
                for key in _archive_key_for(u.files[n]):
                    want.append((key, targets[n]))
    warned = set()
    for key, bsa in want:
        paths = [p for p in dst.inis_for_key(key) if p in current]
        if not paths:
            if key not in warned and key == "sArchiveToLoadInMemoryList":
                warned.add(key)
                plan.notes.append((f"No ini in {dst.root.name} has {key}; {bsa} still loads, just "
                                   "not kept in memory.",
                                   f"Ningún ini de {dst.root.name} tiene {key}; {bsa} igual carga, "
                                   "solo que no queda en memoria."))
            elif key not in warned:
                warned.add(key)
                plan.errors.append((f"No ini in {dst.root.name} has {key}, so {bsa} wouldn't load.",
                                    f"Ningún ini de {dst.root.name} tiene {key}, así que {bsa} no "
                                    "cargaría."))
            continue
        for p in paths:
            cur = parse_ini(current[p]).archive_list(key)
            if bsa.lower() in {c.lower() for c in cur}:
                continue
            cur.append(bsa)
            if len(", ".join(cur)) > ARCHIVE_LIST_LIMIT:
                raise TransferError(
                    f"{key} in {p.name} would go over {ARCHIVE_LIST_LIMIT} characters with {bsa}. "
                    "Bring fewer mods, or shorten BSA names (Koka's tip: 'Mod - Meshes.bsa' → '1M.bsa').",
                    f"{key} en {p.name} pasaría de {ARCHIVE_LIST_LIMIT} caracteres con {bsa}. "
                    "Trae menos mods o acorta nombres de BSA (consejo de Koka: 'Mod - Meshes.bsa' → "
                    "'1M.bsa').")
            current[p] = set_archive_list(current[p], key, cur)
            plan.ini_added.append((p.name, key, bsa))
        if key == "sResourceArchiveList2" and not dst.lang_inis and ("lang", bsa) not in warned:
            warned.add(("lang", bsa))
            plan.notes.append((f"{bsa} goes to Skyrim.ini, but {dst.root.name} has no language ini "
                               "(Skyrim_en.ini...). The console's own one replaces that list.",
                               f"{bsa} queda en Skyrim.ini, pero {dst.root.name} no tiene ini de idioma "
                               "(Skyrim_en.ini...). El de la consola reemplaza esa lista."))
    plan.ini_after = {p: v for p, v in current.items() if v != plan.ini_before.get(p)}


def _plan_budget(plan: TransferPlan) -> None:
    from .converter import pack_texture_bytes
    dst = plan.dst
    ae = dst.mode == "AE"
    after = len(plan.list_after)
    plan.budget = {
        "ccc_before": len(plan.list_before), "ccc_after": after,
        "ccc_limit": K.CCC_BYTE_LIMIT if ae else None, "ccc_warn": K.CCC_BYTE_WARN if ae else None,
        "ccc_over": bool(ae and after > K.CCC_BYTE_LIMIT),
        "tex_added": sum(b["unit"].tex_bytes or 0 for b in plan.units),
        "tex_unknown": [b["unit"].name for b in plan.units if b["unit"].tex_bytes is None],
        "tex_dst": pack_texture_bytes(dst),
        "bytes_added": sum(Path(s).stat().st_size for s, _d, _u in plan.copies),
    }
    if plan.budget["ccc_over"]:
        plan.errors.append((f"The load list would be {after} bytes; the limit is about "
                            f"{K.CCC_BYTE_LIMIT}. Bring fewer plugins or shorten names.",
                            f"La lista de carga quedaría en {after} bytes; el límite es de unos "
                            f"{K.CCC_BYTE_LIMIT}. Trae menos plugins o acorta nombres."))


# ---------------------------------------------------------------- apply
def _provenance(u: ModUnit, plan: TransferPlan) -> dict:
    """Source block for a mod brought from another pack: kind "pack", the
    source pack, and (as "origin") the block the mod had there, so its Nexus
    info and download md5 travel with it. Archives left in Data get their md5."""
    from .recipe import nexus_of, source_block, source_of
    origin = source_of(u.meta) if u.meta.get("source") else None
    blk = source_block(u.archive if u.archive else None, kind="pack",
                       pack=plan.src_name, unit=u.id)
    if not u.archive:
        blk["path"], blk["file"] = str(plan.src.root), plan.src_name
    if origin:
        blk["origin"] = origin
        if nexus_of(origin):
            blk["nexus"] = nexus_of(origin)
    return blk


def apply_transfer(plan: TransferPlan, progress=None) -> dict:
    tick = progress or (lambda *a, **k: None)
    dst = plan.dst
    try:
        if plan.errors:
            raise TransferError(*plan.errors[0])
        if not plan.units:
            raise TransferError("There's nothing to bring", "No hay nada que traer")
        # the destination must still be what the plan saw
        stale = []
        if dst.list_path.exists() and dst.list_path.read_bytes() != plan.list_before:
            stale.append(dst.list_path.name)
        for p, raw in plan.ini_before.items():
            if not p.exists() or p.read_bytes() != raw:
                stale.append(p.name)
        stale += [d for _s, d, _u in plan.copies if (dst.data_dir / d).exists()]
        if stale:
            raise TransferError("The destination changed since this was prepared (" + ", ".join(stale) +
                                "). Prepare it again.",
                                "El destino cambió desde que se preparó esto (" + ", ".join(stale) +
                                "). Vuelve a prepararlo.")
        n = len(plan.units)
        title = f"Bring {n} mod{'s' if n != 1 else ''} from {plan.src_name}"
        prov = {b["unit"].id: _provenance(b["unit"], plan) for b in plan.units}   # hashed before writing
        staging = Path(tempfile.mkdtemp(prefix="skynx-bring-"))
        try:
            with Transaction(dst.root, title) as tx:
                for i, (srcp, name, _uid) in enumerate(plan.copies):
                    tick(name, i, len(plan.copies))
                    if name in plan.patch_masters:
                        raw, _n = rename_masters(Path(srcp).read_bytes(), plan.patch_masters[name])
                        tmp = staging / name
                        tmp.write_bytes(raw)
                        srcp = tmp
                    if dst.mode == "SE" and name.lower().endswith((".esp", ".esm")):
                        from .edition import adapt_bytes_for_se
                        raw = Path(srcp).read_bytes()
                        fixed = adapt_bytes_for_se(raw)          # HEDR 1.71 -> 1.70
                        if fixed != raw:
                            tmp = staging / ("se-" + name)
                            tmp.write_bytes(fixed)
                            srcp = tmp
                    tx.copy_in(srcp, dst.data_dir / name)
                if plan.list_after != plan.list_before:
                    tx.write_bytes(dst.list_path, plan.list_after)
                for p, raw in plan.ini_after.items():
                    tx.write_bytes(p, raw)
                mods = load_mods(dst)
                copied = {(u, d) for _s, d, u in plan.copies}
                for b in plan.units:
                    u = b["unit"]
                    files = [d for (uid, d) in copied if uid == u.id]
                    plugs = [u.target.get(p, p) for p in u.plugins if u.target.get(p, p) in files]
                    bsas = [u.target.get(f, f) for f in u.bsas if u.target.get(f, f) in files]
                    ini = [{"key": k, "bsa": bb} for (_i, k, bb) in plan.ini_added if bb in bsas]
                    ini = [dict(t) for t in {tuple(sorted(x.items())) for x in ini}]
                    mod_id = Path(plugs[0]).stem if plugs and u.kind == "plugin" else u.name
                    base_id, k = mod_id, 2
                    while mod_id in mods:
                        mod_id, k = f"{base_id} ({k})", k + 1
                    rec = {**{k: v for k, v in u.meta.items() if k != "source"},
                           "source": prov[u.id], "from_pack": plan.src_name,
                           "from_unit": u.id, "added": time.strftime("%Y-%m-%d %H:%M:%S"),
                           "plugins": plugs, "bsas": bsas, "ini": ini, "reason": b["reason"]}
                    if b["needed_by"]:
                        rec["needed_by"] = b["needed_by"]
                    fixed = {v: k2 for k2, v in u.target.items() if v != k2}
                    if fixed:
                        rec["name_fixed"] = fixed
                    if u.renamed:
                        rec["renamed"] = u.renamed
                    pm = {p: plan.patch_masters[p] for p in plugs if p in plan.patch_masters}
                    if pm:
                        rec["masters_patched"] = pm
                    mods[mod_id] = rec
                _save_mods(dst, tx, mods)
        finally:
            shutil.rmtree(staging, ignore_errors=True)
        dst.reload()
        return {"history": tx.dir.name if tx.changed else None,
                "added": [d for _s, d, _u in plan.copies], "list_added": plan.list_added,
                "ini_added": [{"ini": i, "key": k, "bsa": b} for i, k, b in plan.ini_added],
                "units": [b["unit"].id for b in plan.units],
                "notes": list(plan.notes)}
    finally:
        plan.cleanup()


def units_view(units: list[ModUnit], lang: str = "en") -> list[dict]:
    return [u.to_dict(lang) for u in units]
