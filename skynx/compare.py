"""Compare a mod "already converted for Switch" with its PC original.

People share converted mods. The question is whether the shared copy is only
a format conversion of the Nexus original or whether someone also edited it
(xEdit record edits, removed scripts, merged plugins, changed meshes).

    compare(converted, original) -> dict      (see `compare` for the shape)

Each side may be a folder, a .zip/.7z, or a loose plugin/BSA (with the BSAs
next to it). The original may be a FOMOD installer: then the converted mod is
compared against the union of every file in the archive.

Assets: every file of a side, loose or inside its BSAs, keyed by its Data
path (lowercase, backslashes). Loose files win over BSAs, like on PC. Sizes
come from the directories; content is hashed (streamed, or decompressed once
for compressed BSA entries) only when a path exists on both sides with the
same size. Expected conversion changes are recognised and not counted as
edits: DDS -> NVN textures (and downscaled ones), PC sounds -> Switch sounds,
64-bit PC animations -> Switch, LE meshes resaved for SE, voice/FaceGen/SEQ/
strings paths that follow a plugin rename, and scripts/meshes/text files whose
only change is the plugin's new name.

Plugins: matched by name, then by a folded name (Google Drive damage,
safe_name/compact_name renames), then by content (shared FormIDs/EDIDs).
Merges are found from the TES4 description ("Merged Plugin: ...") or from
records of several originals showing up in one converted plugin. Records are
keyed by (owning master, object id) using each file's own master list, so
plugins whose master lists differ still line up; record data is compared
decompressed and the header's version-control fields are ignored. When the
master lists differ, a byte that differs only because a FormID's file index
points at the same master under another index is not a difference.
"""
from __future__ import annotations

import hashlib
import re
import shutil
import struct
import tempfile
import unicodedata
import zlib
from collections import Counter
from pathlib import Path

from . import hkx as HKX
from . import rename as RN
from .bsa import read_bsa
from .errors import SkynxError
from .nxaudio import is_switch_fuz
from .plugin import FLAG_LIGHT, FLAG_MASTER, read_header
from .records import COMPRESSED, RecordError, iter_subrecords
from .textures import inspect as inspect_tex

try:  # used to compare records whose FormID file indexes differ
    import numpy as np
except ImportError:  # pragma: no cover
    np = None

CAP = 50
PLUGIN_EXT = (".esp", ".esm", ".esl")
SOUND_EXT = {".xwm", ".wav", ".fuz", ".lip", ".mcadpcm"}
DELETED = 0x20
ASSET_DIRS = {"meshes", "textures", "sound", "music", "scripts", "interface", "seq", "strings",
              "lodsettings", "grass", "shadersfx", "video", "dialogueviews", "sky", "materials",
              "lightingtemplates", "terrain", "trees"}
# What the converter leaves out of a PC mod (converter.TOP_DROP / JUNK_EXT).
TOP_DROP = {"fomod", "skse", "source", "docs", "doc", "readme", "screenshots", "images",
            "optional", "optionals", "calientetools", "nemesis_engine", "netscriptframework",
            "tools", "bodyslide", "__macosx"}
JUNK_EXT = {".psc", ".bak", ".psd", ".xcf", ".log", ".md", ".pdf", ".url", ".html", ".htm",
            ".dll", ".exe", ".bat", ".7z", ".zip", ".rar", ".db", ".ini~"}
TEXT_EXT = set(RN.TEXT_EXT)
_HDR = struct.Struct("<4sIII")
_U16 = struct.Struct("<H")
_U32 = struct.Struct("<I")
_CHUNK = 1 << 20


class CompareError(SkynxError):
    pass


def _note(level: str, en: str, es: str) -> dict:
    return {"level": level, "en": en, "es": es}


def _tick(progress):
    return progress or (lambda *a, **k: None)


# ------------------------------------------------------------------ names
def fold(name: str) -> str:
    """Plugin name reduced to its letters and digits, without extension:
    "Ryn's Standing Stones.esp", "Ryn_s Standing Stones.esp" (Google Drive) and
    "RynsStandingStones.esp" (compact_name) all give "rynsstandingstones"."""
    n = name.lower().replace("’", "'")
    if n[-4:] in PLUGIN_EXT:
        n = n[:-4]
    n = unicodedata.normalize("NFKD", n).encode("ascii", "ignore").decode()
    return re.sub(r"[^a-z0-9]", "", n)


def _norm(name: str) -> str:
    from .audit import norm_name
    return norm_name(name)


def _folded_match(conv: str, orig: str) -> bool:
    if _norm(conv) == _norm(orig) or RN.safe_name(orig).lower() == conv.lower() \
            or RN.compact_name(orig).lower() == conv.lower():
        return True
    fc, fo = fold(conv), fold(orig)
    if not fc or not fo:
        return False
    if fc == fo or re.sub(r"\d+$", "", fc) == fo:          # RN.unique adds digits
        return True
    return len(fc) >= 12 and fo.startswith(fc)               # compact_name cuts at 24


# ------------------------------------------------------------------ assets
class Asset:
    """One file of a side: loose (path) or inside a BSA (arc, entry)."""
    __slots__ = ("rel", "origin", "path", "arc", "entry", "_size", "_sha", "_head")

    def __init__(self, rel: str, origin: str, path: Path | None = None, arc=None, entry=None):
        self.rel, self.origin, self.path, self.arc, self.entry = rel, origin, path, arc, entry
        self._size = self._sha = self._head = None

    @property
    def ext(self) -> str:
        i = self.rel.rfind(".")
        return self.rel[i:] if i > self.rel.rfind("\\") else ""


class Side:
    def __init__(self, label: str):
        self.label = label
        self.fomod = False
        self.files: dict[str, list[Asset]] = {}
        self.plugins: list[Path] = []
        self.bsas: list[Path] = []
        self.bsa_files: dict[str, list[str]] = {}
        self.notes: list[dict] = []
        self.ignored = 0
        self.dlls = 0
        self._fh: dict[str, object] = {}

    def add(self, a: Asset, loose_wins: bool) -> None:
        cur = self.files.get(a.rel)
        if cur is None:
            self.files[a.rel] = [a]
        elif not loose_wins:
            cur.append(a)                    # FOMOD: every option's copy is a variant

    def fh(self, arc):
        key = str(arc.path)
        f = self._fh.get(key)
        if f is None:
            f = self._fh[key] = arc.path.open("rb")
        return f

    def close(self) -> None:
        for f in self._fh.values():
            try:
                f.close()
            except OSError:
                pass
        self._fh.clear()

    # -- content access: each BSA entry is decompressed at most once
    def _bsa_prefix(self, a: Asset, f) -> int:
        f.seek(a.entry.offset)
        if a.arc.embed_names:
            n = f.read(1)[0]
            f.seek(n, 1)
            return n + 1
        return 0

    def size(self, a: Asset) -> int:
        if a._size is None:
            if a.path is not None:
                a._size = a.path.stat().st_size
            else:
                f = self.fh(a.arc)
                pre = self._bsa_prefix(a, f)
                if a.entry.compressed:
                    a._size = _U32.unpack(f.read(4))[0]
                else:
                    a._size = a.entry.size - pre
        return a._size

    def _load_bsa(self, a: Asset) -> bytes:
        raw = a.arc.read_file(a.entry, self.fh(a.arc))
        a._sha = hashlib.sha1(raw).digest()
        a._size = len(raw)
        a._head = raw[:64 * 1024]
        return raw

    def data(self, a: Asset) -> bytes:
        if a.path is not None:
            return a.path.read_bytes()
        return self._load_bsa(a)

    def head(self, a: Asset, n: int = 256) -> bytes:
        if a._head is not None and (len(a._head) >= n or a._size is not None and len(a._head) >= a._size):
            return a._head[:n]
        if a.path is not None:
            with a.path.open("rb") as f:
                a._head = f.read(n)
        elif a.entry.compressed:
            self._load_bsa(a)
        else:
            a._head = a.arc.read_head(a.entry, n, self.fh(a.arc))
        return a._head[:n]

    def sha(self, a: Asset) -> bytes:
        if a._sha is None:
            if a.path is not None:
                h = hashlib.sha1()
                with a.path.open("rb") as f:
                    for chunk in iter(lambda: f.read(_CHUNK), b""):
                        h.update(chunk)
                a._sha = h.digest()
            else:
                self._load_bsa(a)
        return a._sha

    def same(self, a: Asset, other: "Side", b: Asset) -> bool:
        try:
            return self.size(a) == other.size(b) and self.sha(a) == other.sha(b)
        except (OSError, ValueError, zlib.error, RuntimeError, ImportError):
            return False


def _open_side(path: Path, work: Path, label: str, tick) -> Path:
    path = Path(path)
    if not path.exists():
        raise CompareError(f"{path} doesn't exist", f"{path} no existe")
    if path.is_dir():
        return path
    from .intake import archive_type, bundle_to_folder, loose_bundle, safe_extract
    kind = archive_type(path)
    if kind:
        tick(path.name)
        return safe_extract(path, work / label, progress=tick)
    if loose_bundle(path):
        return bundle_to_folder(path, work / label)
    raise CompareError(f"{path.name} isn't a folder, a .zip/.7z, a plugin or a BSA.",
                       f"{path.name} no es una carpeta, un .zip/.7z, un plugin ni un BSA.")


def _data_root(folder: Path) -> Path:
    """The shallowest folder that holds plugins, BSAs or game folders."""
    best, best_depth = folder, 99
    dirs = [folder] + [d for d in folder.rglob("*") if d.is_dir()]
    for d in dirs:
        rel = d.relative_to(folder).parts
        if len(rel) > 6 or any(p.lower() in ("fomod", "__macosx") for p in rel):
            continue
        try:
            kids = list(d.iterdir())
        except OSError:
            continue
        has = any((k.is_file() and k.suffix.lower() in PLUGIN_EXT + (".bsa",)) or
                  (k.is_dir() and k.name.lower() in ASSET_DIRS) for k in kids)
        if has and len(rel) < best_depth:
            best, best_depth = d, len(rel)
    return best


def _inventory(side: Side, folder: Path, tick) -> None:
    from . import fomod as FM
    try:
        side.fomod = FM.find_root(folder) is not None or FM.has_script_installer(folder)
    except OSError:
        side.fomod = False
    root = folder if side.fomod else _data_root(folder)
    files = sorted(p for p in root.rglob("*") if p.is_file())
    for i, p in enumerate(files):
        if i % 500 == 0:
            tick(p.name, i, len(files))
        parts = [x.lower() for x in p.relative_to(root).parts]
        ext = p.suffix.lower()
        if ext == ".dll":
            side.dlls += 1
        if any(x in ("fomod", "__macosx") for x in parts[:-1]):
            continue
        if side.fomod:
            if ext in PLUGIN_EXT:
                side.plugins.append(p)
                continue
            if ext == ".bsa":
                side.bsas.append(p)
                continue
            k = next((j for j, x in enumerate(parts[:-1]) if x in ASSET_DIRS), None)
            if k is None:
                side.ignored += 1
                continue
            parts = parts[k:]
        else:
            if len(parts) == 1:
                if ext in PLUGIN_EXT:
                    side.plugins.append(p)
                elif ext == ".bsa":
                    side.bsas.append(p)
                else:
                    side.ignored += 1
                continue
            if parts[0] in TOP_DROP:
                side.ignored += 1
                continue
        rel = "\\".join(parts)
        side.add(Asset(rel, "loose", path=p), loose_wins=not side.fomod)
    for b in sorted(side.bsas, key=lambda p: p.name.lower()):
        tick(b.name)
        try:
            arc = read_bsa(b)
        except Exception as e:  # noqa: BLE001
            side.notes.append(_note("warn", f"I couldn't read {b.name} ({e}); it was left out of the comparison.",
                                    f"No pude leer {b.name} ({e}); quedó por fuera de la comparación."))
            continue
        rels = []
        for e in arc.entries:
            rel = e.path.lower().replace("/", "\\").strip("\\")
            rels.append(rel)
            side.add(Asset(rel, b.name, arc=arc, entry=e), loose_wins=not side.fomod)
        side.bsa_files[b.name] = rels


# ------------------------------------------------------------------ plugins
class PluginData:
    __slots__ = ("path", "name", "header", "masters", "folds", "recs", "edids", "self_edids",
                 "error", "unreadable")

    def __init__(self, path: Path):
        self.path, self.name = path, path.name
        self.header = read_header(path)
        self.masters = list(self.header.masters)
        self.folds = [fold(m) for m in self.masters]
        self.recs: dict[tuple[str, int], tuple] = {}   # key -> (type, flags, edid, data, raw fid)
        self.edids: set[str] = set()
        self.self_edids: set[str] = set()
        self.error: str | None = self.header.error or None
        self.unreadable = 0
        if not self.error:
            try:
                self._scan(path.read_bytes())
            except (RecordError, OSError, struct.error) as e:
                self.error = str(e)

    def _scan(self, buf: bytes) -> None:
        n, o = len(buf), 0
        folds, nm = self.folds, len(self.folds)
        recs = self.recs
        while o + 24 <= n:
            typ, size, flags, fid = _HDR.unpack_from(buf, o)
            if typ == b"GRUP":
                if size < 24:
                    raise RecordError(f"group at {o:#x} is too small")
                o += 24
                continue
            start, end = o + 24, o + 24 + size
            if end > n:
                raise RecordError(f"record {typ!r} at {o:#x} runs past the end of the file")
            o = end
            if typ == b"TES4":
                continue
            if flags & COMPRESSED:
                try:
                    data = zlib.decompress(buf[start + 4:end])
                except zlib.error:
                    data = None
                    self.unreadable += 1
            else:
                data = buf[start:end]
            idx = fid >> 24
            owner = folds[idx] if idx < nm else ""
            edid = None
            if data is not None and data[:4] == b"EDID" and len(data) >= 6:
                k = _U16.unpack_from(data, 4)[0]
                edid = data[6:6 + k].split(b"\0", 1)[0].decode("cp1252", "replace") or None
                if edid:
                    low = edid.lower()
                    self.edids.add(low)
                    if not owner:
                        self.self_edids.add(low)
            recs[(owner, fid & 0xFFFFFF)] = (typ.decode("latin-1"), flags & ~COMPRESSED, edid, data, fid)

    @property
    def light(self) -> bool:
        return bool(self.header.flags & FLAG_LIGHT) or self.name.lower().endswith(".esl")

    @property
    def master_flag(self) -> bool:
        return bool(self.header.flags & FLAG_MASTER) or self.name.lower().endswith(".esm")

    def merged_list(self) -> list[str]:
        desc = self.header.description or ""
        i = desc.lower().find("merged plugin")
        if i < 0 or ":" not in desc[i:]:
            return []
        tail = desc[i:].split(":", 1)[1]
        return [t.strip() for t in re.split(r"[\r\n,;]+", tail)
                if t.strip().lower().endswith(PLUGIN_EXT)]


def _similarity(c: PluginData, o: PluginData) -> float:
    kc, ko = c.recs.keys(), o.recs.keys()
    sk = len(kc & ko) / max(1, len(kc | ko)) if (kc or ko) else 1.0
    se = len(c.edids & o.edids) / max(1, len(c.edids | o.edids)) if (c.edids or o.edids) else 0.0
    return max(sk, se)


def _equal_records(c: PluginData, o: PluginData) -> int:
    n = 0
    get = o.recs.get
    for k, r in c.recs.items():
        q = get(k)
        if q is not None and q[3] == r[3]:
            n += 1
    return n


def _best(c: PluginData, cands: list[PluginData]) -> PluginData | None:
    if not cands:
        return None
    if len(cands) == 1:
        return cands[0]
    return max(cands, key=lambda o: (_equal_records(c, o), _similarity(c, o)))


def _load_order(plist: list[PluginData]) -> list[PluginData]:
    by = {p.name.lower(): p for p in plist}
    done, out = set(), []

    def visit(p, stack=()):
        key = p.name.lower()
        if key in done or key in stack:
            return
        for m in p.masters:
            if m.lower() in by:
                visit(by[m.lower()], stack + (key,))
        done.add(key)
        out.append(p)
    for p in plist:
        visit(p)
    return out


class Pair:
    def __init__(self, conv: PluginData | None, origs: list[PluginData], how: str | None):
        self.conv, self.origs, self.how = conv, origs, how
        self.merge_how: str | None = None


def _match_plugins(convs: list[PluginData], origs: list[PluginData], fomod: bool) -> tuple[list[Pair], list[PluginData]]:
    """Pairs (converted, [originals], how) and the originals left unmatched."""
    free = list(origs)
    pairs: list[Pair] = []

    def take(o):
        # FOMOD: other options' copies of the same plugin are alternatives, not missing
        for x in list(free):
            if x is o or (fomod and x.name.lower() == o.name.lower()):
                free.remove(x)

    todo = []
    for c in convs:
        o = _best(c, [o for o in free if o.name.lower() == c.name.lower()])
        if o is not None:
            take(o)
            pairs.append(Pair(c, [o], "name"))
        else:
            todo.append(c)
    rest = []
    for c in todo:
        o = _best(c, [o for o in free if _folded_match(c.name, o.name)])
        if o is not None:
            take(o)
            pairs.append(Pair(c, [o], "folded"))
        else:
            rest.append(c)
    for c in rest:
        scored = sorted(((_similarity(c, o), o) for o in free), key=lambda t: -t[0])
        if scored and scored[0][0] >= 0.5:
            take(scored[0][1])
            pairs.append(Pair(c, [scored[0][1]], "content"))
        else:
            pairs.append(Pair(c, [], None))
    # merges named in the TES4 description
    for p in pairs:
        for nm in p.conv.merged_list():
            o = next((o for o in free if o.name.lower() == nm.lower()), None) or \
                next((o for o in free if _folded_match(nm, o.name)), None)
            if o is not None:
                take(o)
                p.origs.append(o)
                p.merge_how = "description"
    # merges found from content: an original whose own records show up in a
    # converted plugin that its match (if any) doesn't explain
    for o in list(free):
        best, best_cov = None, 0.0
        for p in pairs:
            cov = _merge_evidence(p, o)
            if cov > best_cov:
                best, best_cov = p, cov
        if best is not None and best_cov >= 0.5:
            take(o)
            if best.how is None:
                best.how = "content"
            best.origs.append(o)
            best.merge_how = best.merge_how or "content"
    return pairs, free


def _merge_evidence(p: Pair, o: PluginData) -> float:
    c = p.conv
    if not o.recs:
        return 0.0
    prim_edids = set().union(*(x.edids for x in p.origs)) if p.origs else set()
    mine = o.self_edids - prim_edids
    hits = len(mine & c.edids)
    # overrides that the converted plugin carries in this original's version
    folds_in = {fold(x.name) for x in p.origs} | {fold(o.name)}
    remap = {f: "" for f in folds_in}
    prim = {}
    for x in p.origs:
        rm = {f: "" for f in folds_in}
        for (ow, loc), r in x.recs.items():
            prim[(rm.get(ow, ow), loc)] = r[3]
    for (ow, loc), r in o.recs.items():
        if not ow:
            continue
        k = (remap.get(ow, ow), loc)
        rc = c.recs.get(k)
        if rc is not None and rc[3] == r[3] and prim.get(k) != r[3]:
            hits += 1
    return hits / len(o.recs)


# ------------------------------------------------------------------ record diff
def _allowed(conv: PluginData, orig: PluginData, remap: dict[str, str]):
    """(converted index byte, original index byte) pairs that name the same
    master, as a 256x256 table; None when both lists line up."""
    mc = conv.folds + [""]
    mo = [remap.get(f, f) for f in orig.folds] + [""]
    if mc == mo:
        return None
    if np is None:
        return {(k, j) for k, a in enumerate(mc) for j, b in enumerate(mo) if a == b and k != j}
    t = np.zeros((256, 256), dtype=bool)
    for k, a in enumerate(mc[:256]):
        for j, b in enumerate(mo[:256]):
            if a == b and k != j:
                t[k, j] = True
    return t


def _same(a: bytes | None, b: bytes | None, allowed) -> bool:
    if a is None or b is None:
        return False
    if a == b:
        return True
    if allowed is None or len(a) != len(b):
        return False
    if np is None or isinstance(allowed, set):
        return all(x == y or (x, y) in allowed for x, y in zip(a, b))
    x = np.frombuffer(a, dtype=np.uint8)
    y = np.frombuffer(b, dtype=np.uint8)
    m = x != y
    return bool(allowed[x[m], y[m]].all())


def _sub_diff(a: bytes | None, b: bytes | None, allowed) -> list[str]:
    if a is None or b is None:
        return []
    try:
        sa, sb = list(iter_subrecords(a)), list(iter_subrecords(b))
    except RecordError:
        return ["?"]
    ga: dict[str, list[bytes]] = {}
    gb: dict[str, list[bytes]] = {}
    order: list[str] = []
    for s, pl in sa:
        ga.setdefault(s, []).append(pl)
        if s not in order:
            order.append(s)
    for s, pl in sb:
        gb.setdefault(s, []).append(pl)
        if s not in order:
            order.append(s)
    out = []
    for s in order:
        la, lb = ga.get(s, []), gb.get(s, [])
        if len(la) != len(lb) or not all(_same(x, y, allowed) for x, y in zip(la, lb)):
            out.append(s)
    if not out and [s for s, _ in sa] != [s for s, _ in sb]:
        out.append("order")
    return out


def _owner_name(plugin: PluginData, fid: int) -> str:
    idx = fid >> 24
    return plugin.masters[idx] if idx < len(plugin.masters) else plugin.name


def _diff_records(c: PluginData, origs: list[PluginData], remaps: dict[int, dict]) -> dict:
    union: dict[tuple, tuple] = {}
    for o in origs:
        rm = remaps[id(o)]
        al = _allowed(c, o, rm)
        for (ow, loc), r in o.recs.items():
            union[(rm.get(ow, ow), loc)] = (r, al, o)
    res = {"added": 0, "removed": 0, "changed": 0, "same": 0, "renumbered": 0,
           "by_type": {}, "subs": Counter(), "examples": []}
    ex = res["examples"]
    bt = res["by_type"]

    def bump(typ, what):
        d = bt.setdefault(typ, {})
        d[what] = d.get(what, 0) + 1

    def example(r, what, subs, plugin):
        if len(ex) < CAP:
            ex.append({"edid": r[2], "formid": f"{r[4]:08X}", "owner": _owner_name(plugin, r[4]),
                       "type": r[0], "what": what, "subs": subs})

    def cmp(rc, ro, al):
        same_data = _same(rc[3], ro[3], al)
        if same_data and rc[1] == ro[1]:
            res["same"] += 1
            return
        res["changed"] += 1
        bump(rc[0], "changed")
        subs = [] if same_data else _sub_diff(rc[3], ro[3], al)
        if rc[3] is None or ro[3] is None:
            what = "unreadable"
        elif rc[1] & DELETED and not ro[1] & DELETED:
            what = "deleted"
        elif rc[1] != ro[1] and same_data:
            what = "flags"
        else:
            what = "changed"
        if rc[1] != ro[1] and what == "changed":
            subs = subs + ["flags"]
        res["subs"].update(set(subs))
        example(rc, what, subs, c)

    added = []
    for k, rc in c.recs.items():
        u = union.pop(k, None)
        if u is None:
            added.append(rc)
        else:
            cmp(rc, u[0], u[1])
    # same EDID and type under another FormID: renumbered (compacted, merged)
    by_edid = {}
    for k, (r, al, o) in union.items():
        if r[2]:
            by_edid.setdefault((r[0], r[2].lower()), k)
    for rc in added:
        k = by_edid.pop((rc[0], rc[2].lower()), None) if rc[2] else None
        if k is not None and k in union:
            ro, al, _o = union.pop(k)
            res["renumbered"] += 1
            bump(rc[0], "renumbered")
            cmp(rc, ro, al)
            continue
        res["added"] += 1
        bump(rc[0], "added")
        example(rc, "added", [], c)
    for k, (r, al, o) in union.items():
        res["removed"] += 1
        bump(r[0], "removed")
        example(r, "removed", [], o)
    res["subs"] = dict(res["subs"].most_common())
    return res


def _header_diff(c: PluginData, origs: list[PluginData], remaps: dict[int, dict]) -> dict:
    o = origs[0]
    hc, ho = c.header, o.header
    out: dict = {"expected": [], "edits": []}
    if hc.hedr_version != ho.hedr_version:
        out["hedr"] = [ho.hedr_version, hc.hedr_version]
        out["expected"].append("hedr")
    if c.light != o.light:
        out["esl"] = [o.light, c.light]
        out["expected" if o.light else "edits"].append("esl")
    if c.master_flag != o.master_flag:
        out["esm"] = [o.master_flag, c.master_flag]
        out["edits"].append("esm")
    if hc.num_records != sum(x.header.num_records for x in origs):
        out["num_records"] = [sum(x.header.num_records for x in origs), hc.num_records]
    conv_m = {f: m for f, m in zip(c.folds, c.masters)}
    orig_m: dict[str, str] = {}
    for x in origs:
        rm = remaps[id(x)]
        for f, m in zip(x.folds, x.masters):
            f2 = rm.get(f, f)
            if f2:
                orig_m.setdefault(f2, m)
    added = [m for f, m in conv_m.items() if f not in orig_m]
    removed = [m for f, m in orig_m.items() if f not in conv_m]
    renamed = [[orig_m[f], m] for f, m in conv_m.items() if f in orig_m and orig_m[f] != m]
    if added:
        out["masters_added"] = added
        out["edits"].append("masters_added")
    if removed:
        out["masters_removed"] = removed
        out["edits"].append("masters_removed")
    if renamed:
        out["masters_renamed"] = renamed
        out["expected"].append("masters_renamed")
    common_c = [f for f in c.folds if f in orig_m]
    common_o = [f for f in orig_m if f in conv_m]
    if len(origs) == 1 and common_c != common_o:
        out["masters_reordered"] = True
        out["expected"].append("masters_reordered")
    return out


# ------------------------------------------------------------------ asset diff
def _nif_bs(head: bytes) -> tuple | None:
    i = head.find(b"\n", 0, 64)
    if i < 0 or not head.startswith(b"Gamebryo"):
        return None
    try:
        ver = _U32.unpack_from(head, i + 1)[0]
        user, _nb = struct.unpack_from("<II", head, i + 6)
        bs = _U32.unpack_from(head, i + 14)[0] if user >= 3 else 0
    except struct.error:
        return None
    return ver, user, bs


def _rename_rel(rel: str, names: dict[str, str], names_fold: dict[str, str], stems: dict[str, str]) -> str | None:
    """The path an original file gets when its plugin is renamed (voices,
    FaceGen, SEQ, strings), or None."""
    for base in RN.NAME_FOLDERS:
        if rel.startswith(base + "\\"):
            seg, sep, tail = rel[len(base) + 1:].partition("\\")
            if sep and seg.endswith(PLUGIN_EXT):
                new = names.get(seg) or names_fold.get(fold(seg))
                if new and new != seg:
                    return f"{base}\\{new}\\{tail}"
            return None
    if rel.startswith("seq\\") and rel.endswith(".seq"):
        stem = rel[4:-4]
        new = stems.get(stem)
        return f"seq\\{new}.seq" if new and new != stem else None
    if rel.startswith("strings\\"):
        m = re.match(r"strings\\(.+)_([a-z]+)\.(strings|dlstrings|ilstrings)$", rel)
        if m:
            new = stems.get(m.group(1))
            if new and new != m.group(1):
                return f"strings\\{new}_{m.group(2)}.{m.group(3)}"
    return None


def _top(rel: str) -> str:
    return rel.split("\\", 1)[0]


def _diff_assets(conv: Side, orig: Side, mapping: dict[str, str], tick) -> dict:
    """mapping: original plugin name (lower) -> converted plugin name (lower)."""
    out = {k: 0 for k in ("same", "converted_textures", "downscaled", "converted_audio",
                          "converted_anims", "converted_meshes", "renamed", "patched_for_rename",
                          "dropped_junk", "fomod_unused")}
    lists = {k: [] for k in ("meshes_changed", "scripts_changed", "scripts_removed", "textures_changed",
                             "other_changed", "only_converted", "only_original")}
    names_fold = {fold(k): v for k, v in mapping.items()}
    stems = {k[:-4]: v[:-4] for k, v in mapping.items()}
    renames = [(k.encode("cp1252", "replace"), v.encode("cp1252", "replace"))
               for k, v in mapping.items() if k != v]
    # original paths as they'd be after the plugin renames
    opaths: dict[str, list[Asset]] = {}
    origin_of: dict[str, str] = {}           # new rel -> original rel
    for rel, assets in orig.files.items():
        new = rel
        if rel not in conv.files:
            r2 = _rename_rel(rel, mapping, names_fold, stems)
            if r2 and r2 in conv.files:
                new = r2
                out["renamed"] += 1
        opaths.setdefault(new, []).extend(assets)
        origin_of[new] = rel
    done_o: set[str] = set()
    done_c: set[str] = set()

    # sounds: a PC sound becomes .mcadpcm (or a Switch .fuz) under the same base
    def bases(paths):
        d: dict[str, dict[str, str]] = {}
        for rel in paths:
            if rel.startswith(("sound\\", "music\\")):
                i = rel.rfind(".")
                if i > 0 and rel[i:] in SOUND_EXT:
                    d.setdefault(rel[:i], {})[rel[i:]] = rel
        return d
    bo, bc = bases(opaths), bases(conv.files)
    for base, eo in bo.items():
        ec = bc.get(base)
        if not ec:
            continue
        pc = bool(set(eo) & {".xwm", ".wav"})
        if not pc and ".fuz" in eo:
            pc = not is_switch_fuz(orig.head(opaths[eo[".fuz"]][0], 64 * 1024))
        nx = ".mcadpcm" in ec
        if not nx and ".fuz" in ec:
            nx = is_switch_fuz(conv.head(conv.files[ec[".fuz"]][0], 64 * 1024))
        if pc and nx and not all(e in ec and conv.same(conv.files[ec[e]][0], orig, opaths[r][0])
                                 for e, r in eo.items()):
            out["converted_audio"] += 1
            done_o.update(eo.values())
            done_c.update(ec.values())

    both = [r for r in conv.files if r in opaths and r not in done_c]
    for i, rel in enumerate(both):
        if i % 500 == 0:
            tick(rel.rsplit("\\", 1)[-1], i, len(both))
        a = conv.files[rel][0]
        variants = opaths[rel]
        done_o.add(rel)
        done_c.add(rel)
        if any(conv.same(a, orig, b) for b in variants):
            out["same"] += 1
            continue
        b = variants[0]
        ext = a.ext
        try:
            kind = _classify_change(conv, a, orig, b, ext, rel, origin_of.get(rel, rel) != rel, renames)
        except (OSError, ValueError, zlib.error, RuntimeError, ImportError):
            kind = "other_changed"
        if kind == "downscaled":
            out["converted_textures"] += 1
            out["downscaled"] += 1
        elif kind in out:
            out[kind] += 1
        else:
            lists[kind].append(rel)

    for rel in conv.files:
        if rel not in done_c and rel not in opaths:
            lists["only_converted"].append(rel)
    for rel in opaths:
        if rel in done_o:
            continue
        ext = rel[rel.rfind("."):] if "." in rel.rsplit("\\", 1)[-1] else ""
        if ext in JUNK_EXT:
            out["dropped_junk"] += 1
        elif orig.fomod:
            out["fomod_unused"] += 1
            lists["only_original"].append(rel)
        elif ext == ".pex":
            lists["scripts_removed"].append(rel)
        else:
            lists["only_original"].append(rel)

    # original BSAs whose every file is missing
    missing = set(lists["only_original"]) if not orig.fomod else set()
    missing_bsas = []
    renamed_back = {v: k for k, v in origin_of.items()}
    for name, rels in orig.bsa_files.items():
        rels2 = [renamed_back.get(r, r) for r in rels]
        real = [r for r in rels2 if not r.endswith(tuple(JUNK_EXT))]
        if real and all(r in missing for r in real):
            missing_bsas.append({"name": name, "files": len(real),
                                 "tops": sorted(Counter(_top(r) for r in real))})
    tops_all = Counter(_top(r) for r in opaths)
    tops_missing = Counter(_top(r) for r in missing)
    for k, v in lists.items():
        out.setdefault("counts", {})[k] = len(v)
        out[k] = sorted(v)[:CAP]
    out["missing_bsas"] = missing_bsas
    out["_missing_tops"] = {t: (tops_missing[t], tops_all[t]) for t in tops_missing}
    out["_overlap"] = (len(both) + out["converted_audio"], len(opaths), len(conv.files))
    return out


def _classify_change(conv: Side, a: Asset, orig: Side, b: Asset, ext: str, rel: str,
                     moved: bool, renames: list[tuple[bytes, bytes]]) -> str:
    if ext == ".dds":
        ic, io = inspect_tex(conv.head(a, 256)), inspect_tex(orig.head(b, 256))
        if ic is None or io is None:
            return "textures_changed"
        if ic.width * ic.height < io.width * io.height:
            return "downscaled"
        if (ic.container, ic.fmt, ic.width, ic.height, ic.mips) != (io.container, io.fmt, io.width,
                                                                       io.height, io.mips):
            return "converted_textures"
        return "textures_changed"
    if ext == ".hkx":
        kc, ko = HKX.classify(conv.head(a, 32)), HKX.classify(orig.head(b, 32))
        if kc == HKX.NX_64 and ko in (HKX.PC_64, HKX.PC_32, HKX.XML):
            return "converted_anims"
        return "other_changed"
    if ext in SOUND_EXT and rel.startswith(("sound\\", "music\\")):
        hc, ho = conv.head(a, 64 * 1024), orig.head(b, 64 * 1024)
        if ext == ".fuz" and is_switch_fuz(hc) and not is_switch_fuz(ho):
            return "converted_audio"
        return "other_changed"
    if ext == ".nif":
        vc, vo = _nif_bs(conv.head(a, 128)), _nif_bs(orig.head(b, 128))
        if vc and vo and vc != vo:
            return "converted_meshes"          # an LE mesh resaved for SE
    if moved and ext == ".nif":
        return "renamed"
    if renames and ext in {".nif", ".pex"} | TEXT_EXT:
        dc, do = conv.data(a).lower(), orig.data(b).lower()
        if any(old.lower() in do and new.lower() in dc for old, new in renames):
            return "patched_for_rename"
    if ext == ".nif":
        return "meshes_changed"
    if ext == ".pex":
        return "scripts_changed"
    return "other_changed"


# ------------------------------------------------------------------ wording
def _pl(n: int, one: str, many: str) -> str:
    return f"{n} {one if n == 1 else many}"


_CAT = {"textures": ("textures", "texturas", "all of its textures", "todas sus texturas"),
        "meshes": ("meshes", "meshes", "all of its meshes", "todos sus meshes"),
        "sound": ("sounds", "sonidos", "all of its sounds", "todos sus sonidos"),
        "music": ("music", "música", "all of its music", "toda su música"),
        "scripts": ("scripts", "scripts", "all of its scripts", "todos sus scripts"),
        "interface": ("interface files", "archivos de interfaz", "all of its interface files",
                      "todos sus archivos de interfaz")}


def _cats(tops: list[str], missing_tops: dict) -> tuple[str, str]:
    en, es = [], []
    for t in tops:
        e1, s1, e2, s2 = _CAT.get(t, (f"{t} files", f"archivos de {t}", f"all of its {t} files",
                                      f"todos sus archivos de {t}"))
        miss, total = missing_tops.get(t, (0, 1))
        full = miss >= total
        en.append(e2 if full else e1)
        es.append(s2 if full else s1)
    return " and ".join(en), " y ".join(es)


def _verdict(pairs_out: list[dict], extra_c: list[str], missing_p: list[str], assets: dict,
             orig: Side, different: bool) -> dict:
    if different:
        return {"kind": "different-mod", "en": "This looks like a different mod.",
                "es": "Parece otro mod."}
    fmt_en, fmt_es = [], []
    if assets["converted_textures"]:
        n, d = assets["converted_textures"], assets["downscaled"]
        fmt_en.append(_pl(n, "texture", "textures") + (f" ({d} also downscaled)" if d else ""))
        fmt_es.append(_pl(n, "textura", "texturas") + (f" ({d} también reducidas)" if d else ""))
    if assets["converted_audio"]:
        n = assets["converted_audio"]
        fmt_en.append(_pl(n, "sound", "sounds"))
        fmt_es.append(_pl(n, "sonido", "sonidos"))
    if assets["converted_anims"]:
        n = assets["converted_anims"]
        fmt_en.append(_pl(n, "animation", "animations"))
        fmt_es.append(_pl(n, "animación", "animaciones"))
    if assets["converted_meshes"]:
        n = assets["converted_meshes"]
        fmt_en.append(_pl(n, "mesh resaved for SE", "meshes resaved for SE"))
        fmt_es.append(_pl(n, "mesh guardado para SE", "meshes guardados para SE"))
    ed_en, ed_es = [], []
    rec = Counter()
    subs = Counter()
    for p in pairs_out:
        h = p.get("header") or {}
        if "hedr" in h:
            a, b = h["hedr"]
            fmt_en.append(f"{p['converted']} header {a:.2f} → {b:.2f}")
            fmt_es.append(f"cabecera de {p['converted']} {a:.2f} → {b:.2f}")
        if "esl" in h.get("expected", []):
            fmt_en.append(f"ESL flag removed from {p['converted']}")
            fmt_es.append(f"marca ESL quitada en {p['converted']}")
        if p["original"] and p["converted"].lower() != p["original"].lower() and not p.get("merged_from"):
            fmt_en.append(f"{p['original']} renamed as {p['converted']}")
            fmt_es.append(f"{p['original']} renombrado como {p['converted']}")
        if "masters_added" in h:
            ed_en.append(f"{p['converted']} has new masters ({', '.join(h['masters_added'][:3])})")
            ed_es.append(f"{p['converted']} tiene masters nuevos ({', '.join(h['masters_added'][:3])})")
        if "masters_removed" in h:
            ed_en.append(f"{p['converted']} lost masters ({', '.join(h['masters_removed'][:3])})")
            ed_es.append(f"{p['converted']} perdió masters ({', '.join(h['masters_removed'][:3])})")
        if "esm" in h:
            ed_en.append(f"{p['converted']} changed its ESM flag")
            ed_es.append(f"{p['converted']} cambió su marca ESM")
        if "esl" in h.get("edits", []):
            ed_en.append(f"{p['converted']} was flagged ESL")
            ed_es.append(f"{p['converted']} quedó marcado como ESL")
        if p.get("merged_from"):
            ed_en.append(f"{p['converted']} is a merge of {', '.join(p['merged_from'])}")
            ed_es.append(f"{p['converted']} es una fusión de {', '.join(p['merged_from'])}")
        r = p.get("records") or {}
        for k in ("changed", "added", "removed", "renumbered"):
            rec[k] += r.get(k, 0)
        subs.update(r.get("subs", {}))
    if rec["changed"]:
        top = ", ".join(f"{n} {s}" for s, n in subs.most_common(4))
        tail = f" ({top})" if top else ""
        ed_en.append(_pl(rec["changed"], "record changed", "records changed") + tail)
        ed_es.append(_pl(rec["changed"], "registro cambiado", "registros cambiados") + tail)
    for k, en1, enn, es1, esn in (("added", "record added", "records added", "registro agregado", "registros agregados"),
                                  ("removed", "record removed", "records removed", "registro quitado", "registros quitados"),
                                  ("renumbered", "record renumbered", "records renumbered",
                                   "registro con otro FormID", "registros con otro FormID")):
        if rec[k]:
            ed_en.append(_pl(rec[k], en1, enn))
            ed_es.append(_pl(rec[k], es1, esn))
    c = assets["counts"]
    for k, en1, enn, es1, esn in (
            ("meshes_changed", "mesh changed", "meshes changed", "mesh cambiado", "meshes cambiados"),
            ("textures_changed", "texture changed", "textures changed", "textura cambiada", "texturas cambiadas"),
            ("scripts_changed", "script changed", "scripts changed", "script cambiado", "scripts cambiados"),
            ("scripts_removed", "script removed", "scripts removed", "script quitado", "scripts quitados"),
            ("other_changed", "other file changed", "other files changed", "otro archivo cambiado",
             "otros archivos cambiados"),
            ("only_converted", "extra file", "extra files", "archivo de más", "archivos de más")):
        if orig.fomod and k == "scripts_removed":
            continue
        if c.get(k):
            ed_en.append(_pl(c[k], en1, enn))
            ed_es.append(_pl(c[k], es1, esn))
    if extra_c:
        ed_en.append(_pl(len(extra_c), "extra plugin", "extra plugins") + f" ({', '.join(extra_c[:3])})")
        ed_es.append(_pl(len(extra_c), "plugin de más", "plugins de más") + f" ({', '.join(extra_c[:3])})")
    # missing content
    miss_en, miss_es = [], []
    mb = assets["missing_bsas"]
    in_bsas = sum(b["files"] for b in mb)
    loose_missing = (0 if orig.fomod else c.get("only_original", 0)) - in_bsas
    if mb:
        tops = sorted({t for b in mb for t in b["tops"]})
        ce, cs = _cats(tops, assets["_missing_tops"])
        if len(mb) == 1:
            miss_en.append(f"{mb[0]['name']} of the original is missing ({ce})")
            miss_es.append(f"falta {mb[0]['name']} del original ({cs})")
        else:
            miss_en.append(f"{len(mb)} BSAs of the original are missing ({ce})")
            miss_es.append(f"faltan {len(mb)} BSA del original ({cs})")
    if loose_missing > 0:
        more = " more" if mb else ""
        miss_en.append(_pl(loose_missing, f"file{more} of the original is missing",
                           f"files{more} of the original are missing"))
        es_more = " más" if mb else ""
        miss_es.append(f"falta 1 archivo{es_more} del original" if loose_missing == 1 else
                       f"faltan {loose_missing} archivos{es_more} del original")
    if missing_p:
        miss_en.append(_pl(len(missing_p), "plugin of the original is missing",
                           "plugins of the original are missing") + f" ({', '.join(missing_p[:3])})")
        miss_es.append(("falta 1 plugin del original" if len(missing_p) == 1 else
                        f"faltan {len(missing_p)} plugins del original") + f" ({', '.join(missing_p[:3])})")
    if ed_en:
        en = "Edited beyond conversion: " + ", ".join(ed_en) + "."
        es = "Editado más allá de la conversión: " + ", ".join(ed_es) + "."
        if miss_en:
            en += " Also, " + "; ".join(miss_en) + "."
            es += " Además, " + "; ".join(miss_es) + "."
        return {"kind": "edited", "en": en, "es": es}
    if miss_en:
        return {"kind": "partial", "en": "Partial: " + "; ".join(miss_en) + ".",
                "es": "Incompleto: " + "; ".join(miss_es) + "."}
    if fmt_en:
        return {"kind": "format-only",
                "en": "Same as the original except for format conversion (" + ", ".join(fmt_en) + ").",
                "es": "Igual al original salvo la conversión de formato (" + ", ".join(fmt_es) + ")."}
    return {"kind": "format-only", "en": "Identical to the original.", "es": "Idéntico al original."}


# ------------------------------------------------------------------ main
def compare(converted: Path, original: Path, progress=None, work_dir: Path | None = None) -> dict:
    """Differences between a converted mod and its original PC mod.

    Returns {"same_mod", "plugins": [{"converted", "original", "match",
    "merged_from"?, "header", "records"}], "assets": {...}, "verdict": {"kind",
    "en", "es"}, "notes": [{"level", "en", "es"}]}. verdict kind is
    "format-only", "edited", "partial" or "different-mod". Lists hold at most
    50 items; assets["counts"] and the record counters give the totals.
    """
    tick = _tick(progress)
    base = Path(work_dir) if work_dir else None
    if base is not None:
        base.mkdir(parents=True, exist_ok=True)
    work = Path(tempfile.mkdtemp(prefix="skynx-compare-", dir=str(base) if base else None))
    conv, orig = Side("converted"), Side("original")
    try:
        tick(Path(converted).name)
        _inventory(conv, _open_side(converted, work, "converted", tick), tick)
        tick(Path(original).name)
        _inventory(orig, _open_side(original, work, "original", tick), tick)
        return _compare(conv, orig, tick)
    finally:
        conv.close()
        orig.close()
        shutil.rmtree(work, ignore_errors=True)


def _compare(conv: Side, orig: Side, tick) -> dict:
    notes: list[dict] = conv.notes + orig.notes
    from . import knowledge as K
    game = {m.lower() for m in K.VANILLA_MASTERS + K.SWITCH_MASTERS}
    cps, ops = [], []
    for side, out in ((conv, cps), (orig, ops)):
        for p in side.plugins:
            if p.name.lower() in game:
                continue
            tick(p.name)
            pd = PluginData(p)
            if pd.error:
                notes.append(_note("warn", f"I couldn't read every record of {p.name} ({pd.error}).",
                                   f"No pude leer todos los registros de {p.name} ({pd.error})."))
            out.append(pd)
    pairs, free = _match_plugins(cps, ops, orig.fomod)
    # where each original plugin went
    mapping: dict[str, str] = {}
    owner_to: dict[str, str] = {}
    for p in pairs:
        for o in p.origs:
            mapping[o.name.lower()] = p.conv.name.lower()
            owner_to[fold(o.name)] = fold(p.conv.name)
    plugins_out = []
    extra_c, related = [], 0
    for p in pairs:
        if not p.origs:
            extra_c.append(p.conv.name)
            plugins_out.append({"converted": p.conv.name, "original": None, "match": None,
                                "header": None, "records": None})
            continue
        tick(p.conv.name)
        mine = {fold(o.name) for o in p.origs}
        remap = {f: ("" if f in mine else t) for f, t in owner_to.items()}
        remaps = {id(o): remap for o in p.origs}
        origs = _load_order(p.origs)
        records = _diff_records(p.conv, origs, remaps)
        header = _header_diff(p.conv, origs, remaps)
        entry = {"converted": p.conv.name, "original": p.origs[0].name, "match": p.how,
                 "header": header, "records": records}
        if len(p.origs) > 1:
            entry["merged_from"] = [o.name for o in origs]
            entry["merge_found_by"] = p.merge_how
        plugins_out.append(entry)
        total = max(len(p.conv.recs), sum(len(o.recs) for o in p.origs))
        if total == 0 or (records["same"] + records["changed"]) / total >= 0.2:
            related += 1
        if records["renumbered"]:
            notes.append(_note("info", f"{p.conv.name}: {records['renumbered']} records have other FormIDs "
                                       "(compacted or renumbered), matched by their Editor ID.",
                               f"{p.conv.name}: {records['renumbered']} registros tienen otro FormID "
                               "(compactados o renumerados); los emparejé por su Editor ID."))
    missing_p = []
    for o in free:
        if orig.fomod:
            continue
        missing_p.append(o.name)
        plugins_out.append({"converted": None, "original": o.name, "match": None,
                            "header": None, "records": None})

    tick("assets")
    assets = _diff_assets(conv, orig, mapping, tick)
    shared, n_o, n_c = assets.pop("_overlap")
    overlap = shared / max(1, min(n_o, n_c)) if (n_o and n_c) else (1.0 if not n_o and not n_c else 0.0)
    if cps and ops:
        different = related == 0 and overlap < 0.5
    else:
        different = bool(n_o or n_c) and overlap < 0.2
    verdict = _verdict([p for p in plugins_out if p["records"] is not None], extra_c, missing_p,
                       assets, orig, different)
    assets.pop("_missing_tops", None)

    if orig.fomod:
        notes.append(_note("info", "The original is a FOMOD installer: I compared against every file of "
                                   "all its options together. Files of options that weren't chosen don't "
                                   "count as missing.",
                           "El original es un instalador FOMOD: comparé contra todos los archivos de "
                           "todas sus opciones juntas. Los archivos de opciones no elegidas no cuentan "
                           "como faltantes."))
    if assets["renamed"]:
        notes.append(_note("info", f"{assets['renamed']} voice/FaceGen/SEQ/strings files moved with the plugin's "
                                   "new name; that's part of the conversion.",
                           f"{assets['renamed']} archivos de voces/FaceGen/SEQ/strings se movieron con el "
                           "nuevo nombre del plugin; eso es parte de la conversión."))
    if assets["patched_for_rename"]:
        notes.append(_note("info", f"{assets['patched_for_rename']} files only changed the plugin's name "
                                   "inside them.",
                           f"{assets['patched_for_rename']} archivos solo cambiaron el nombre del plugin "
                           "por dentro."))
    if assets["dropped_junk"]:
        notes.append(_note("info", f"{assets['dropped_junk']} files that don't go on Switch (script sources, "
                                   "docs, DLLs) were left out, as the conversion does.",
                           f"{assets['dropped_junk']} archivos que no van en Switch (fuentes de scripts, "
                           "documentos, DLL) quedaron por fuera, como hace la conversión."))
    if orig.dlls and not conv.dlls:
        notes.append(_note("warn", "The original has SKSE plugins (.dll). They don't run on Switch, so "
                                   "whatever depends on them won't work in either copy.",
                           "El original trae plugins de SKSE (.dll). No funcionan en Switch, así que lo que "
                           "dependa de ellos no va a funcionar en ninguna de las dos copias."))
    for p in plugins_out:
        h = p.get("header") or {}
        if h.get("masters_reordered"):
            notes.append(_note("info", f"{p['converted']}: the masters are in another order; references "
                                       "were compared by the master they point to.",
                               f"{p['converted']}: los masters están en otro orden; las referencias se "
                               "compararon por el master al que apuntan."))
    for p in plugins_out:
        if p.get("merged_from"):
            notes.append(_note("warn", f"{p['converted']} merges {', '.join(p['merged_from'])} into one plugin.",
                               f"{p['converted']} junta {', '.join(p['merged_from'])} en un solo plugin."))
    tick("…")
    return {"same_mod": verdict["kind"] != "different-mod", "plugins": plugins_out, "assets": assets,
            "verdict": verdict, "notes": notes, "fomod": orig.fomod}
