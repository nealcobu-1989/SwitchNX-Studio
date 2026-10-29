"""File conflicts between mods: the same path (texture, mesh...) in two BSAs.

When two archives contain the same file path, the game uses only one copy.
This module finds those paths and says which BSA wins. On Switch it depends on
the kind of file, as seen on the console (Oct 2026):

* Scripts (.pex): a BSA from the ini wins over one a plugin loads by its name.
  KokaNX's USSEP.bsa (in sResourceArchiveList) took Growl's and Sacrosanct's
  scripts, and the game's own Skyrim - Misc.bsa took Quick Start's MQ101
  fragment; with those mods' BSAs moved into the ini, after the others, every
  one of them worked. Order: the plugins' BSAs, then the ini lists.
* Everything else (textures, meshes...): as on PC. Noble Skyrim's BSA, loaded
  by its empty plugin, shows its textures over the game's own (which load
  from the ini). Order: the ini lists, then the plugins' BSAs.

In both orders:

* plugins' BSAs ("Name.bsa", then "Name - Textures.bsa", next to "Name.esp")
  follow the plugin load order (Pack.load_order); a plugin that is listed but
  not in Data doesn't load, so neither do its BSAs;
* ini BSAs follow the lists, sResourceArchiveList then sResourceArchiveList2.
  The lists are the effective ones: Skyrim.ini, with each key replaced by the
  language ini when that ini sets it (on Switch, Skyrim_en.ini / Skyrim_es.ini...
  load after Skyrim.ini and replace sResourceArchiveList2; see
  Pack.archive_lists and the "lang-ini-hides" check in audit.py). With several
  language inis, the one for `lang` (English by default) is used;
* a BSA that comes later wins over every earlier one.

Assumptions worth showing the user:

* A BSA named in an ini list and also attached to a plugin is counted once,
  at its ini position: putting a plugin's BSA in the ini, after another ini
  BSA, is how its scripts win over that one's.
* Vanilla archives ("Skyrim - *.bsa") are not in the pack and are ignored, so
  mods overriding vanilla files are not reported, only mod vs mod.
* Loose files in Data win over every BSA; they are not considered here.
* sArchiveToLoadInMemoryList only keeps archives in memory; it doesn't change
  the order and is ignored.

Speed: only the archive directories are read. File data is read only to tell
whether two copies are identical (a harmless waste of space), only when their
stored sizes match, and never more than `max_read` bytes in total.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
from pathlib import Path

from .bsa import BsaArchive, BsaEntry, read_bsa
from .pack import Pack

ORDER_KEYS = ("sResourceArchiveList", "sResourceArchiveList2")
EXAMPLES = 5
MAX_READ = 256 * 2**20


@dataclass
class LoadedBsa:
    name: str
    path: Path
    source: str            # "ini:sResourceArchiveList", "plugin:Name.esp"
    position: int
    files: int = 0
    bytes: int = 0
    overridden: int = 0    # files of this BSA that a later BSA replaces
    overridden_bytes: int = 0
    error: str | None = None


@dataclass
class ConflictPair:
    winner: str
    loser: str
    count: int = 0
    bytes: int = 0                     # stored bytes of the loser's copies (wasted)
    examples: list[str] = field(default_factory=list)
    identical: int = 0                 # same size and same stored bytes
    identical_bytes: int = 0
    unchecked: int = 0                 # same size, not compared (read cap reached)


@dataclass
class DeadBsa:
    bsa: str
    files: int
    bytes: int
    winners: list[str]                 # BSAs that replace its files, most files first


@dataclass
class ConflictReport:
    lang: str
    order: list[LoadedBsa] = field(default_factory=list)
    pairs: list[ConflictPair] = field(default_factory=list)
    dead: list[DeadBsa] = field(default_factory=list)
    unloaded: list[str] = field(default_factory=list)   # BSAs in Data nothing loads
    stats: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        out = asdict(self)
        for b in out["order"]:
            b["path"] = str(b["path"])
        return out


def _lists(pack: Pack, lang: str) -> dict[str, list[str]]:
    langs = pack.lang_inis
    if len(langs) <= 1:
        return pack.archive_lists()
    out: dict[str, list[str]] = {}
    main = [i for i in pack.inis if i.path.name.lower() == "skyrim.ini"]
    pick = next((i for i in langs if i.path.name.lower() == f"skyrim_{lang.lower()}.ini"),
                langs[0])
    for ini in main + [pick]:
        for key in ORDER_KEYS:
            if ini.get("Archive", key) is not None:
                out[key] = ini.archive_list(key)
    return out


def load_order_bsas(pack: Pack, lang: str = "en", scripts: bool = False) -> list[tuple[str, Path, str]]:
    """(name, path, source) for every pack BSA the game loads, first to last:
    the order that decides textures, meshes and the rest, or with scripts=True
    the one that decides scripts (see the module notes)."""
    out: list[tuple[str, Path, str]] = []
    seen: set[str] = set()

    def add(name: str, source: str):
        low = name.lower()
        if low in seen or low.startswith("skyrim - ") or low not in pack.bsas:
            return
        seen.add(low)
        out.append((pack.bsas[low].name, pack.bsas[low], source))

    lists = _lists(pack, lang)
    in_ini = {b.lower() for key in ORDER_KEYS for b in lists.get(key, [])}

    def ini():
        for key in ORDER_KEYS:
            for b in lists.get(key, []):
                add(b, f"ini:{key}")

    def plugins():
        for plugin, src in pack.load_order():
            if plugin.startswith("#"):
                continue
            if src != "juego" and plugin.lower() not in pack.plugins:
                continue
            stem = Path(plugin).stem
            for b in sorted(pack.bsas_for_plugin(plugin),
                            key=lambda p: p.stem.lower() != stem.lower()):
                if b.name.lower() not in in_ini:       # counted at its ini position
                    add(b.name, f"plugin:{plugin}")
    if scripts:
        plugins()
        ini()
    else:
        ini()
        plugins()
    return out


class _Reader:
    """Compares stored blobs, keeping a few archives open and counting bytes."""

    def __init__(self, cap: int):
        self.cap, self.read = cap, 0
        self.handles: dict[str, object] = {}

    def _fh(self, arc: BsaArchive):
        k = str(arc.path)
        if k not in self.handles:
            if len(self.handles) >= 32:
                old = next(iter(self.handles))
                self.handles.pop(old).close()
            self.handles[k] = arc.path.open("rb")
        return self.handles[k]

    @staticmethod
    def blob_size(arc: BsaArchive, e: BsaEntry) -> int:
        if arc.embed_names:
            return e.size - 1 - len(e.path.encode("cp1252", errors="replace"))
        return e.size

    def _start(self, arc: BsaArchive, e: BsaEntry) -> int:
        """File offset where the entry's stored bytes begin."""
        if not arc.embed_names:
            return e.offset
        f = self._fh(arc)
        f.seek(e.offset)
        return e.offset + 1 + f.read(1)[0]

    def same(self, a: BsaArchive, ea: BsaEntry, b: BsaArchive, eb: BsaEntry) -> bool | None:
        """True/False, or None when the read cap doesn't allow comparing."""
        size = self.blob_size(a, ea)
        if self.read + 2 * size > self.cap:
            return None
        pa, pb = self._start(a, ea), self._start(b, eb)
        done = 0
        while done < size:
            n = min(size - done, 1 << 20)
            fa = self._fh(a); fa.seek(pa + done); x = fa.read(n)
            fb = self._fh(b); fb.seek(pb + done); y = fb.read(n)
            self.read += len(x) + len(y)
            if x != y or len(x) != n:
                return False
            done += n
        return True

    def close(self):
        for f in self.handles.values():
            f.close()
        self.handles.clear()


def find_conflicts(pack: Pack, progress=None, lang: str = "en",
                   max_read: int = MAX_READ) -> ConflictReport:
    rep = ConflictReport(lang)
    say = progress or (lambda *_: None)
    loaded = load_order_bsas(pack, lang)
    archives: list[BsaArchive | None] = []
    for i, (name, path, source) in enumerate(loaded):
        say(name, i, len(loaded))
        lb = LoadedBsa(name, path, source, i)
        try:
            arc = read_bsa(path)
        except Exception as e:  # noqa: BLE001
            lb.error = str(e)
            arc = None
        if arc:
            lb.files = len(arc.entries)
            lb.bytes = sum(e.size for e in arc.entries)
        rep.order.append(lb)
        archives.append(arc)
    names = {b.name.lower() for b in rep.order}
    rep.unloaded = sorted(p.name for low, p in pack.bsas.items()
                          if low not in names and not low.startswith("skyrim - "))

    # path -> [(archive index, entry)] in load order
    owners: dict[str, list[tuple[int, BsaEntry]]] = {}
    for i, arc in enumerate(archives):
        if not arc:
            continue
        seen: set[str] = set()
        for e in arc.entries:
            key = e.path.lower().replace("/", "\\")
            if key in seen:
                continue
            seen.add(key)
            owners.setdefault(key, []).append((i, e))

    # scripts follow the other order (the module notes): rank each BSA in it
    srank = {n.lower(): k for k, (n, _p, _s) in enumerate(load_order_bsas(pack, lang, scripts=True))}
    for key, hits in owners.items():
        if key.endswith(".pex") and len(hits) > 1:
            hits.sort(key=lambda h: srank.get(rep.order[h[0]].name.lower(), h[0]))

    pairs: dict[tuple[int, int], ConflictPair] = {}
    beaten_by: dict[int, dict[int, int]] = {}
    reader = _Reader(max_read)
    conflicting = 0
    try:
        for key, hits in owners.items():
            if len(hits) < 2:
                continue
            conflicting += 1
            wi, we = hits[-1]
            warc = archives[wi]
            for li, le in hits[:-1]:
                larc = archives[li]
                pr = pairs.get((wi, li))
                if pr is None:
                    pr = pairs[(wi, li)] = ConflictPair(rep.order[wi].name, rep.order[li].name)
                pr.count += 1
                pr.bytes += le.size
                if len(pr.examples) < EXAMPLES:
                    pr.examples.append(le.path)
                lb = rep.order[li]
                lb.overridden += 1
                lb.overridden_bytes += le.size
                beaten_by.setdefault(li, {}).setdefault(wi, 0)
                beaten_by[li][wi] += 1
                if (le.compressed == we.compressed
                        and reader.blob_size(larc, le) == reader.blob_size(warc, we)):
                    same = reader.same(larc, le, warc, we)
                    if same is None:
                        pr.unchecked += 1
                    elif same:
                        pr.identical += 1
                        pr.identical_bytes += le.size
    finally:
        reader.close()

    rep.pairs = sorted(pairs.values(), key=lambda p: (-p.count, -p.bytes, p.winner, p.loser))
    for li, by in beaten_by.items():
        lb = rep.order[li]
        if lb.files and lb.overridden == lb.files:
            rep.dead.append(DeadBsa(lb.name, lb.files, lb.bytes,
                                    [rep.order[w].name for w, _ in
                                     sorted(by.items(), key=lambda kv: -kv[1])]))
    rep.dead.sort(key=lambda d: -d.bytes)
    rep.stats = {
        "bsas": len(rep.order),
        "files": sum(b.files for b in rep.order),
        "conflicting_paths": conflicting,
        "pairs": len(rep.pairs),
        "overridden_bytes": sum(p.bytes for p in rep.pairs),
        "identical": sum(p.identical for p in rep.pairs),
        "identical_bytes": sum(p.identical_bytes for p in rep.pairs),
        "unchecked": sum(p.unchecked for p in rep.pairs),
        "bytes_read": reader.read,
        "errors": [b.name for b in rep.order if b.error],
    }
    return rep
