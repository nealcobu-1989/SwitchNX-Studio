"""What the mods of a pack need that the pack (or the console) doesn't have.

Checks, each returning finding-ready dicts ({code, severity, msg, subject,
params, items, fix}) for the audit's "requirements" category:

a. scripts attached to records (VMAD) with no .pex anywhere, and .pex files
   whose parent script ("extends X") is missing         needs vanilla, deep
b. models (MODL..MOD5) with no mesh anywhere              needs vanilla, deep
c. textures named by the meshes of loaded BSAs that don't exist
                                                          needs vanilla, deep
d. animations for SKSE frameworks Switch doesn't have (DAR, OAR, Nemesis,
   FNIS)                                                  always
e. behavior files (.hkx) in two loaded BSAs with different content: only
   the last one counts, and Switch has nothing to merge them      always

"Anywhere" means: a BSA the game loads (conflicts.load_order_bsas, plus any
BSA a language ini loads), loose files in Data, or the vanilla index
(vanilla.index). Without the vanilla index a-c are skipped with an info
finding, since every vanilla file would look missing.
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import struct
from pathlib import Path
from typing import Callable, Iterable

from . import knowledge as K
from . import nif as NIF
from . import pex as PEX
from . import records as REC
from .bsa import BsaArchive, read_bsa

SHOW = 20
FACETINT = "textures\\actors\\character\\facegendata\\facetint\\"

FRAMEWORKS = ("DAR", "OAR", "Nemesis", "FNIS")
_FNIS = re.compile(r"(^|\\)fnis_[^\\]*_(list\.txt|behavior\.hkx)$")


def _real_path(path: str) -> bool:
    """A model path that names a file: some plugins carry a damaged one
    ('meshes\\šè', no extension) that no BSA could ever have."""
    leaf = path.replace("/", "\\").rsplit("\\", 1)[-1]
    return "." in leaf.strip(".")


def pc_only_script(name: str) -> bool:
    """A script that only exists on PC: SkyUI's menu framework (SKI_*, the MCM)
    or an SKSE library. Mods keep them attached for their PC menu; on Switch
    that menu doesn't exist, and nothing else is lost."""
    from .skse import SKSE_SCRIPTS
    low = name.lower()
    return low.startswith("ski_") or low in SKSE_SCRIPTS or "mcm" in low   # a mod's own MCM script (VAER's)


_FRAGMENT = re.compile(r"^(qf|prkf|sf|tif|pf|scen|tf)_", re.I)
# Maps that only add detail: parallax relief, environment/shine masks,
# specular, glow, skin and rim. Without them the surface is flat or dull, never
# purple; the diffuse (_d or no suffix) and normal (_n) maps are the ones that matter.
_MINOR_MAPS = ("_p", "_m", "_em", "_s", "_g", "_sk", "_rim")
_MODEL_EXT = (".nif", ".hkx", ".egt", ".tri", ".btr", ".bto", ".kf")


def script_fragment(name: str) -> bool:
    """A script fragment (a quest stage, perk, scene or dialogue line's own
    script: QF_, PRKF_, SF_, TIF_...). When one is missing, the author's
    archive doesn't have it either, and it's the same on PC."""
    return bool(_FRAGMENT.match(name))


def minor_map(tex: str) -> bool:
    stem = tex.rsplit("\\", 1)[-1].rsplit(".", 1)[0].lower()
    return stem.endswith(_MINOR_MAPS)


def broken_path(path: str, model: bool = False) -> bool:
    """A path the mod's author typed wrong: a space next to a separator or
    before the extension, a double space, no extension, text after the
    extension, or a model that isn't
    a model (a .dds in a model field). No mod or game can ever provide it."""
    p = path.lower()
    leaf = p.rsplit("\\", 1)[-1]
    if " ." in leaf or "\\ " in p or " \\" in p or "  " in p or p != p.strip():
        return True
    if "." not in leaf.strip("."):
        return True
    # text after the extension: "eyecubemap.dds (eyecubemap.dds)" (Wyrmstooth NX)
    if any(ext + " " in leaf or ext + "(" in leaf for ext in (".dds", ".nif", ".tga", ".png", ".pex", ".hkx")):
        return True
    return model and not leaf.endswith(_MODEL_EXT)


def _f(code: str, severity: str, subject: str, params: dict | None = None,
       items: list[str] | None = None, fix: dict | None = None, msg: str | None = None) -> dict:
    return {"code": code, "severity": severity, "msg": msg or code, "subject": subject,
            "params": params or {}, "items": items or [], "fix": fix}


def _capped(items: list[str]) -> tuple[list[str], dict]:
    """The first SHOW items, plus a language-neutral "(+N)" line for the rest."""
    more = [f"(+{len(items) - SHOW})"] if len(items) > SHOW else []
    cap = {"n": len(items), "shown": min(len(items), SHOW)}
    if more:
        cap["_all"] = list(items)          # the whole list, for the exported report
    return items[:SHOW] + more, cap


# ------------------------------------------------------------------ d. frameworks
def framework_of(path: str) -> str | None:
    p = path.lower().replace("/", "\\").lstrip("\\")
    if p.startswith("data\\"):
        p = p[5:]
    if p.startswith("meshes\\") and "\\animations\\dynamicanimationreplacer\\" in p:
        return "DAR"
    if p.startswith("meshes\\") and "\\animations\\openanimationreplacer\\" in p:
        return "OAR"
    if p.startswith("nemesis_engine\\") or "\\nemesis_pcea\\" in "\\" + p:
        return "Nemesis"
    if p.startswith("tools\\generatefnis") or _FNIS.search(p):
        return "FNIS"
    return None


def frameworks_in(paths: Iterable[str]) -> dict[str, list[str]]:
    out: dict[str, list[str]] = {}
    for p in paths:
        k = framework_of(p)
        if k:
            out.setdefault(k, []).append(p)
    return out


def scan_tree(folder: Path) -> dict[str, list[str]]:
    """Framework -> relative paths, for a loose folder laid out like Data."""
    folder = Path(folder)
    rel = []
    for dirpath, _d, files in os.walk(folder):
        base = Path(dirpath).relative_to(folder)
        for f in files:
            rel.append(str(base / f).replace("/", "\\"))
    return frameworks_in(rel)


def scan_bsa(path: Path) -> dict[str, list[str]]:
    return frameworks_in(e.path for e in read_bsa(path).entries)


def _framework_finding(subject: str, found: dict[str, list[str]]) -> dict:
    kinds = [k for k in FRAMEWORKS if k in found]
    items = [f"{k}: {len(found[k])} ({found[k][0]})" for k in kinds]
    return _f("req-anim-framework", "aviso", subject,
              {"name": subject, "kinds": ", ".join(kinds), "n": sum(len(v) for v in found.values())},
              items)


# ------------------------------------------------------------------ e. behaviors
def is_behavior(path: str) -> bool:
    p = path.lower()
    if not (p.endswith(".hkx") and p.startswith("meshes\\actors\\")):
        return False
    segs = p.split("\\")
    name = segs[-1]
    if any(s.startswith("behaviors") or s.startswith("characters") for s in segs[2:-1]):
        return True
    return name in ("0_master.hkx", "defaultmale.hkx", "defaultfemale.hkx") or name.endswith("project.hkx")


def behavior_conflicts(loaded: list[tuple[str, BsaArchive]],
                       loose: dict[str, Path] | None = None) -> list[dict]:
    """[{path, winner, losers}] for behavior files present in two or more of
    the archives (first to last; loose files win over all) whose content differs."""
    owners: dict[str, list[tuple[int, object]]] = {}
    for i, (_n, arc) in enumerate(loaded):
        for e in arc.entries:
            p = e.path.lower()
            if is_behavior(p):
                owners.setdefault(p, []).append((i, e))
    names = [n for n, _ in loaded]
    if loose:
        for p, fp in loose.items():
            if is_behavior(p) and p in owners:
                owners[p].append((len(names), fp))
        names = names + ["Data"]
    out = []
    handles: dict[int, object] = {}

    def content(i, e):
        if isinstance(e, Path):
            return e.read_bytes()
        arc = loaded[i][1]
        if i not in handles:
            handles[i] = arc.path.open("rb")
        return arc.read_file(e, handles[i])
    try:
        for p, hits in owners.items():
            if len(hits) < 2:
                continue
            try:
                win = content(*hits[-1])
                losers = [names[i] for i, e in hits[:-1] if content(i, e) != win]
            except Exception:  # noqa: BLE001
                continue
            if losers:
                out.append({"path": p, "winner": names[hits[-1][0]], "losers": losers})
    finally:
        for h in handles.values():
            h.close()
    return out


# ------------------------------------------------------------------ pex
def pex_object(raw: bytes) -> tuple[str, str] | None:
    """(script name, parent name or '') of the first object in a .pex."""
    en, _s, o, items = PEX._layout(raw)
    strs = [s for _o, s in items]
    u16 = struct.Struct(en + "H")
    if raw[o]:
        o += 1 + 8
        nfun = u16.unpack_from(raw, o)[0]
        o += 2
        for _ in range(nfun):
            o += 2 + 2 + 2 + 1
            cnt = u16.unpack_from(raw, o)[0]
            o += 2 + 2 * cnt
    else:
        o += 1
    nflags = u16.unpack_from(raw, o)[0]
    o += 2 + 3 * nflags
    nobj = u16.unpack_from(raw, o)[0]
    o += 2
    if not nobj:
        return None
    name_i = u16.unpack_from(raw, o)[0]
    parent_i = u16.unpack_from(raw, o + 6)[0]
    if name_i >= len(strs) or parent_i >= len(strs):
        raise PEX.PexError("bad object table")
    return strs[name_i], strs[parent_i]


# ------------------------------------------------------------------ helpers
def loose_files(data_dir: Path | None) -> dict[str, Path]:
    """Relative lowercase path -> file, for files in Data's subfolders."""
    out: dict[str, Path] = {}
    if not data_dir or not Path(data_dir).is_dir():
        return out
    for d in Path(data_dir).iterdir():
        if not d.is_dir() or d.name.startswith(".skynx"):
            continue
        for dirpath, _dn, files in os.walk(d):
            for f in files:
                fp = Path(dirpath) / f
                out[str(fp.relative_to(data_dir)).replace("/", "\\").lower()] = fp
    return out


def _tex_norm(t: str) -> str:
    t = t.strip().lower().replace("/", "\\")
    while "\\\\" in t:
        t = t.replace("\\\\", "\\")
    if "textures\\" in t:
        i = t.index("textures\\")
        if i == 0 or t[i - 1] == "\\":
            return t[i:]
    return "textures\\" + t.lstrip("\\")


_TEX_CACHE: dict[tuple, list[tuple[str, str]]] = {}


def _disk_key(key: tuple, cache_dir) -> Path | None:
    if not cache_dir or not key:
        return None
    h = hashlib.sha1(repr(key).encode("utf-8", "replace")).hexdigest()[:16]
    return Path(cache_dir) / "nif-textures" / f"{h}.json"


def nif_textures(arc: BsaArchive, cache_dir=None) -> tuple[list[tuple[str, str]], int]:
    """[(nif path, texture path)] for every NIF in the archive; second value
    counts the NIFs that couldn't be read. Cached in memory by file size and
    time, and as JSON under cache_dir when one is given."""
    try:
        st = arc.path.stat()
        key = (str(arc.path), st.st_size, st.st_mtime)
    except OSError:
        key = None
    if key and key in _TEX_CACHE:
        return _TEX_CACHE[key]
    disk = _disk_key(key, cache_dir)
    if disk and disk.exists():
        try:
            data = json.loads(disk.read_text(encoding="utf-8"))
            if data.get("key") == list(key):
                refs = [tuple(r) for r in data["refs"]]
                _TEX_CACHE[key] = (refs, int(data.get("bad", 0)))
                return _TEX_CACHE[key]
        except (OSError, ValueError, KeyError, TypeError):
            pass
    refs: list[tuple[str, str]] = []
    bad = 0
    nifs = [e for e in arc.entries if e.name.lower().endswith(".nif")]
    if nifs:
        with arc.path.open("rb") as f:
            for e in nifs:
                try:
                    paths = NIF.texture_paths(NIF.parse(arc.read_file(e, f)))
                except Exception:  # noqa: BLE001
                    bad += 1
                    continue
                for t in paths:
                    if t.strip():
                        refs.append((e.path.lower(), _tex_norm(t)))
    if key:
        _TEX_CACHE[key] = (refs, bad)
        if disk:
            try:
                disk.parent.mkdir(parents=True, exist_ok=True)
                disk.write_text(json.dumps({"key": list(key), "refs": refs, "bad": bad}), encoding="utf-8")
            except OSError:
                pass
    return refs, bad


# ------------------------------------------------------------------ main entry
def check(pack, deep: bool = True, vanilla: set[str] | None = None,
          get_arc: Callable[[Path], BsaArchive | None] | None = None,
          extra_bsas: Iterable[Path] = (), vanilla_refs: set[str] | None = None,
          vanilla_state: str = "ok",
          vanilla_dir: str | None = None, cache_dir=None, progress=None) -> list[dict]:
    """All requirement findings for a pack. `vanilla` is the vanilla index
    (None when unknown); `vanilla_refs` what the game's own content asks for
    (vanilla.game_refs), which never counts as missing; `vanilla_state` is
    vanilla.status() of the setting."""
    from .conflicts import load_order_bsas
    say = progress or (lambda *_: None)
    get = get_arc or _reader()
    out: list[dict] = []

    # loaded archives, first to last
    order: list[tuple[str, Path]] = [(n, p) for n, p, _s in load_order_bsas(pack)]
    seen = {str(p) for _n, p in order}
    for p in extra_bsas:
        if str(p) not in seen:
            seen.add(str(p))
            order.append((p.name, p))
    loaded: list[tuple[str, BsaArchive]] = []
    for n, p in order:
        arc = get(p)
        if arc is not None:
            loaded.append((n, arc))
    loose = loose_files(pack.data_dir)

    # d. frameworks (cheap)
    for n, arc in loaded:
        found = frameworks_in(e.path for e in arc.entries)
        if found:
            out.append(_framework_finding(n, found))
    found = frameworks_in(loose)
    if found:
        out.append(_framework_finding("Data", found))

    # e. behaviors (cheap: directories, plus the few files that collide)
    by_winner: dict[str, list[dict]] = {}
    for c in behavior_conflicts(loaded, loose):
        by_winner.setdefault(c["winner"], []).append(c)
    for w, cs in by_winner.items():
        others = sorted({l for c in cs for l in c["losers"]})
        items, cap = _capped([f"{c['path']} ({', '.join(c['losers'])})" for c in cs])
        out.append(_f("req-behavior-conflict", "aviso", w,
                      {"name": w, "others": ", ".join(others), **cap}, items))

    if not deep:
        return out
    if vanilla is None:
        if vanilla_state in ("unset", None):
            out.append(_f("req-vanilla-unset", "info", "vanilla"))
        else:
            out.append(_f("req-vanilla-bad", "info", "vanilla",
                          {"path": vanilla_dir or "", "state": vanilla_state},
                          msg=f"req-vanilla-{vanilla_state}"))
        return out

    have = set(vanilla)
    game_asks = set(vanilla_refs or ())
    broken: list[str] = []          # "path (who)" typed wrong by the author
    minor: list[str] = []           # detail maps
    for _n, arc in loaded:
        have.update(e.path.lower() for e in arc.entries)
    have.update(loose)

    # a. scripts attached to records, b. models
    active = []
    present = {low for low in pack.plugins}
    for name, src in pack.load_order():
        if src == "juego" or name.startswith("#"):
            continue
        h = pack.plugins.get(name.lower())
        if h and not h.error and not h.is_dummy:
            active.append(h)
    loaded_names = {n.lower() for n, _s in pack.load_order() if n.lower() in present}
    loaded_names |= {m.lower() for m in K.VANILLA_MASTERS + K.SWITCH_MASTERS}
    for i, h in enumerate(active):
        say(h.name, i, len(active))
        # records of content the pack can't check: Creation Club and masters
        # that aren't loaded (reported as missing masters elsewhere)
        skip = [m for m in h.masters if m.lower() not in loaded_names]
        scan = REC.scan_plugin(h.path, skip)
        if scan.error or scan.unreadable:
            out.append(_f("req-records-unreadable", "info", h.name,
                          {"name": h.name, "n": scan.unreadable, "error": scan.error or ""}))
        miss = sorted(s for s in scan.scripts if f"scripts\\{s}.pex" not in have
                      and f"scripts\\{s}.pex" not in game_asks)
        pc = [s for s in miss if pc_only_script(s)]
        frag = [s for s in miss if s not in pc and script_fragment(s)]
        miss = [s for s in miss if s not in pc and s not in frag]
        if frag:
            items, cap = _capped([f"{scan.names.get(s, s)} ({', '.join(scan.scripts[s][:3])})"
                                  for s in frag])
            out.append(_f("req-script-fragment", "info", h.name, {"name": h.name, **cap}, items))
        if miss:
            items, cap = _capped([f"{scan.names.get(s, s)} ({', '.join(scan.scripts[s][:3])})"
                                  for s in miss])
            out.append(_f("req-script-missing", "aviso", h.name, {"name": h.name, **cap}, items))
        if pc:
            items, cap = _capped([f"{scan.names.get(s, s)} ({', '.join(scan.scripts[s][:3])})"
                                  for s in pc])
            out.append(_f("req-script-pconly", "info", h.name, {"name": h.name, **cap}, items))
        miss = sorted(m for m in scan.models if m not in have and m not in game_asks and _real_path(m))
        broken += [f"{m} ({h.name})" for m in miss if broken_path(m, model=True)]
        miss = [m for m in miss if not broken_path(m, model=True)]
        if miss:
            items, cap = _capped([f"{m} ({', '.join(scan.models[m][:3])})" for m in miss])
            out.append(_f("req-mesh-missing", "aviso", h.name, {"name": h.name, **cap}, items))

    # a2. scripts whose parent is missing
    def parents(name: str, entries: list[tuple[str, bytes]]):
        bad = []
        for path, raw in entries:
            try:
                obj = pex_object(raw)
            except Exception:  # noqa: BLE001
                continue
            if obj and obj[1] and f"scripts\\{obj[1].lower()}.pex" not in have:
                bad.append((obj[0], obj[1]))
        if bad:
            items, cap = _capped([f"{c} extends {p}" for c, p in sorted(bad)])
            sev = "info" if all(pc_only_script(p) for _c, p in bad) else "aviso"   # an MCM on PC only
            out.append(_f("req-script-parent", sev, name,
                          {"name": name, "parents": ", ".join(sorted({p for _c, p in bad})[:6]), **cap},
                          items))
    for n, arc in loaded:
        pexes = [e for e in arc.entries if e.name.lower().endswith(".pex")]
        if not pexes:
            continue
        with arc.path.open("rb") as f:
            blobs = []
            for e in pexes:
                try:
                    blobs.append((e.path, arc.read_file(e, f)))
                except Exception:  # noqa: BLE001
                    continue
        parents(n, blobs)
    lp = [(p, fp.read_bytes()) for p, fp in loose.items() if p.endswith(".pex")]
    if lp:
        parents("Data", lp)

    # c. textures named by meshes
    for i, (n, arc) in enumerate(loaded):
        say(n, i, len(loaded))
        refs, _bad = nif_textures(arc, cache_dir)
        miss: dict[str, str] = {}
        for nif, t in refs:
            if t.startswith(FACETINT) or t in have or t in miss or t in game_asks:
                continue
            miss[t] = nif
        leaf = lambda t: miss[t].rsplit(chr(92), 1)[-1]   # noqa: E731
        broken += [f"{t} ({leaf(t)} · {n})" for t in sorted(miss) if broken_path(t)]
        minor += [f"{t} ({leaf(t)} · {n})" for t in sorted(miss) if not broken_path(t) and minor_map(t)]
        miss = {t: v for t, v in miss.items() if not broken_path(t) and not minor_map(t)}
        if miss:
            items, cap = _capped([f"{t} ({miss[t].rsplit(chr(92), 1)[-1]})" for t in sorted(miss)])
            out.append(_f("req-tex-missing", "aviso", n, {"name": n, **cap}, items))
    if minor:
        items, cap = _capped(minor)
        out.append(_f("req-tex-minor", "info", "textures", cap, items))
    if broken:
        items, cap = _capped(broken)
        out.append(_f("req-path-broken", "info", "paths", cap, items))
    return out


def _reader():
    cache: dict[str, BsaArchive | None] = {}

    def get(p: Path):
        k = str(p)
        if k not in cache:
            try:
                cache[k] = read_bsa(p)
            except Exception:  # noqa: BLE001
                cache[k] = None
        return cache[k]
    return get


# --------------------------------------------------------------------- one mod
def mod_asset_gaps(plugins: list[Path], bsas: list[Path], available: set[str],
                   others: list[Path] = (), cache_dir=None) -> dict:
    """Assets a mod asks for that none of its BSAs, the pack nor the base game
    has: a sign that one of its BSAs is missing.

    plugins/bsas: the mod's own files. available: lowercase paths the pack and
    the base game already provide. others: BSAs lying next to the mod that
    aren't part of it (where its files may have been consolidated).
    Returns {"meshes", "scripts", "textures": [missing paths], "found_in": {bsa: n}}."""
    from . import records as REC
    have = set(available)
    arcs = []
    for b in bsas:
        try:
            arc = read_bsa(b)
        except Exception:  # noqa: BLE001
            continue
        arcs.append(arc)
        have.update(e.path.lower() for e in arc.entries)
    meshes: set[str] = set()
    scripts: set[str] = set()
    for p in plugins:
        try:
            meshes |= REC.models_used(p)
            scripts |= {f"scripts\\{s}.pex" for s in REC.scripts_attached(p)}
        except Exception:  # noqa: BLE001
            continue
    meshes = {m for m in meshes if _real_path(m) and not broken_path(m, model=True)}
    scripts = {s for s in scripts if not script_fragment(s[8:-4]) and not pc_only_script(s[8:-4])}
    textures: set[str] = set()
    for arc in arcs:
        try:
            refs, _bad = nif_textures(arc, cache_dir)
        except Exception:  # noqa: BLE001
            continue
        textures |= {t for _n, t in refs if "facetint\\" not in t and t != "textures\\"
                     and not broken_path(t) and not minor_map(t)}
    miss = {"meshes": sorted(m for m in meshes if m not in have),
            "scripts": sorted(s for s in scripts if s not in have),
            "textures": sorted(t for t in textures if t not in have)}
    found_in: dict[str, int] = {}
    wanted = set(miss["meshes"]) | set(miss["scripts"]) | set(miss["textures"])
    if wanted:
        for o in others:
            try:
                arc = read_bsa(o)
            except Exception:  # noqa: BLE001
                continue
            n = sum(1 for e in arc.entries if e.path.lower() in wanted)
            if n:
                found_in[o.name] = n
    miss["found_in"] = found_in
    return miss
