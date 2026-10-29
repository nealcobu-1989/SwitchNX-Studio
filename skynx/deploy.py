"""Copy a pack to the SD card, and import a pack from it.

Two ways to copy, both limited to the two Skyrim title folders inside
atmosphere/contents (01000A10041EA000 and 01000A10041EB009):

* ``mode="sync"`` (default): compare pack and SD file by file and copy only
  what changed. Before touching the SD, the files that will be overwritten or
  deleted (and only those) are zipped into the project's .skynx/sd-backups
  folder and the zip is checked. If anything fails halfway, the SD is put back
  exactly as it was: overwritten and deleted files come back from that zip with
  their dates and read-only flag, files this run created are removed, and
  case-only renames are undone.
* ``mode="full"``: the original behaviour. Zip both title folders whole,
  delete them, copy the pack's in their place; restore everything on failure.
  (Modded files have been lost this way when a HATS pack replaced the atmosphere folder.)

How "unchanged" is decided in sync mode:

* paths are compared case-insensitively, because FAT32/exFAT SD cards are
  case-insensitive; a file or folder whose name differs only in case is
  renamed so the SD ends up with the pack's spelling;
* same size and modification time within 2 s (FAT stores times in 2 s steps)
  means unchanged;
* same size but a different time: files under 8 MB are compared by content
  hash, so files restored from a backup aren't copied again (their SD date is
  then aligned with the pack's so the next run skips the hash); larger files
  are copied again.
"""
from __future__ import annotations

import hashlib
import os
import shutil
import stat
import time
import zipfile
from dataclasses import dataclass, field
from pathlib import Path

from . import knowledge as K
from .errors import SkynxError

TITLES = (K.TITLE_BASE, K.TITLE_AOC)
SKIP_DIRS = {".skynx"}
# .skynx-original: the first load list SkyNX Mods (the homebrew) saw, kept on the card
SKIP_SUFFIX = (".skynx-tmp", ".skynx-new", ".skynx-ren", ".tmp", ".skynx-original")

MTIME_TOLERANCE = 2.0               # seconds; FAT timestamps have 2 s resolution
FAT_EPOCH = 315792000               # 1980-01-05 UTC: FAT/exFAT can't date a file earlier than 1980-01-01
# The date given on the card to a file dated before 1980 (1980-01-02 12:00 UTC).
# Windows may refuse to set a 1970 date on exFAT and leave the copy dated "now";
# then every sync saw a different date and copied big files again (Music of
# Tamriel, Heavy Armory). With this one both sides read "before the card's first
# days" and the size decides.
FAT_STAMP = 315662400
CAP = 5000                          # files listed per kind on the SD page
HASH_LIMIT = 8 * 2**20              # same size, other date: hash files below this
FREE_MARGIN = 200 * 2**20           # keep this much free on the SD after copying
TMP_NEW = ".skynx-new"
TMP_REN = ".skynx-ren"


class DeployError(SkynxError):
    pass


def sd_contents(sd_root: Path) -> Path:
    sd_root = Path(sd_root)
    if sd_root.name.lower() == "contents":
        return sd_root
    if sd_root.name.lower() == "atmosphere":
        return sd_root / "contents"
    return sd_root / "atmosphere" / "contents"


SD_MARKS = ("nintendo", "switch", "bootloader", "hbmenu.nro", "atmosphere")


def looks_like_switch_sd(sd_root: Path) -> bool:
    """The folder is a Switch SD's root: it has Atmosphère's or the console's
    own folders. A fresh SD may have no atmosphere\\contents yet."""
    root = Path(sd_root)
    if root.name.lower() in ("contents", "atmosphere"):
        root = root.parent if root.name.lower() == "atmosphere" else root.parent.parent
    try:
        return root.is_dir() and any(c.name.lower() in SD_MARKS for c in root.iterdir())
    except OSError:
        return False


def sd_free_space(sd_root: Path) -> int:
    """Free bytes on the drive that holds the SD's atmosphere/contents folder."""
    contents = sd_contents(sd_root)
    for p in (contents, contents.parent, Path(sd_root)):
        if p.exists():
            return shutil.disk_usage(p).free
    raise DeployError(f"I can't find {sd_root}", f"No encuentro {sd_root}")


def _raise(err):
    raise err


def _iter_files(base: Path, skip_temp: bool = False):
    for dirpath, dirnames, filenames in os.walk(base, onerror=_raise):
        dirnames[:] = [d for d in dirnames if d not in SKIP_DIRS]
        for f in filenames:
            if skip_temp and f.lower().endswith(SKIP_SUFFIX):
                continue
            yield Path(dirpath) / f


def _force_rmtree(path: Path):
    def onerror(func, p, _exc):
        os.chmod(p, stat.S_IWRITE)
        func(p)
    shutil.rmtree(path, onerror=onerror)


def _inside(a: Path, b: Path) -> bool:
    a, b = Path(os.path.abspath(a)), Path(os.path.abspath(b))
    try:
        a.relative_to(b)
        return True
    except ValueError:
        return False


def _make_writable(p: Path):
    try:
        mode = os.stat(p, follow_symlinks=False).st_mode
        if not mode & stat.S_IWRITE:
            os.chmod(p, mode | stat.S_IWRITE)
    except FileNotFoundError:
        pass


# Indirections so tests can simulate a failure halfway through.
def _copy_file(src: Path, dst: Path):
    shutil.copy2(src, dst)
    _flush(dst)
    _fat_date(src, dst)


def _fat_date(src: Path, dst: Path) -> None:
    """A file dated before 1980 gets FAT_STAMP on the card (see there)."""
    try:
        if src.stat().st_mtime < FAT_EPOCH:
            os.utime(dst, (FAT_STAMP, FAT_STAMP))
    except OSError:
        pass


def _flush(p: Path):
    """Make the OS write the file to the card now, before it's renamed into place,
    so a card pulled out early can't keep a half-written file under the real name."""
    try:
        with open(p, "rb+") as fh:
            os.fsync(fh.fileno())
    except OSError:
        pass


def _remove_file(p: Path):
    _make_writable(p)
    os.unlink(p)


def _backup_path(project_root: Path, tag: str = "") -> Path:
    dest = Path(project_root) / ".skynx" / "sd-backups"
    dest.mkdir(parents=True, exist_ok=True)
    stamp = time.strftime("%Y%m%d-%H%M%S")
    zpath = dest / f"sd-{stamp}{tag}.zip"
    n = 2
    while zpath.exists():
        zpath = dest / f"sd-{stamp}{tag}-{n}.zip"
        n += 1
    return zpath


def _zip_and_verify(zpath: Path, contents: Path, files: list[Path], progress=None):
    with zipfile.ZipFile(zpath, "w", zipfile.ZIP_STORED, allowZip64=True) as z:
        for i, f in enumerate(files):
            if progress:
                progress(f"Backing up {f.name}", i, len(files))
            z.write(f, f.relative_to(contents))
    # verify: every file present with the same size, and the stored data intact
    with zipfile.ZipFile(zpath) as z:
        sizes = {i.filename.replace("\\", "/"): i.file_size for i in z.infolist()}
        bad = z.testzip()
    if bad:
        raise DeployError(f"The backup is damaged ({bad}); I won't touch the SD",
                          f"El respaldo quedó dañado ({bad}); no toco la SD")
    for f in files:
        key = str(f.relative_to(contents)).replace("\\", "/")
        if sizes.get(key) != f.stat().st_size:
            raise DeployError(f"The backup is incomplete ({key}); I won't touch the SD",
                              f"El respaldo no quedó completo ({key}); no toco la SD")


def backup_sd(sd_root: Path, project_root: Path, progress=None) -> Path | None:
    """Zip both title folders whole (full mode)."""
    contents = sd_contents(sd_root)
    present = [contents / t for t in TITLES if (contents / t).exists()]
    if not present:
        return None
    zpath = _backup_path(project_root)
    files = [f for d in present for f in _iter_files(d)]
    _zip_and_verify(zpath, contents, files, progress)
    return zpath


def _title_dir(pack_root: Path, title: str) -> Path | None:
    from .pack import is_project
    if is_project(pack_root):
        pack_root = Path(pack_root) / "Switch"     # a project goes to the SD from what "Pack" made
        if not pack_root.is_dir():
            return None
    for dirpath, dirnames, _ in os.walk(pack_root):
        dirnames[:] = [d for d in dirnames if d not in SKIP_DIRS]
        for d in dirnames:
            if d.upper() == title:
                return Path(dirpath) / d
    return None


def _jobs(pack_root: Path, sd_root: Path) -> tuple[Path, list[tuple[str, Path, Path]]]:
    contents = sd_contents(sd_root)
    if not contents.parent.exists() and not looks_like_switch_sd(sd_root):
        raise DeployError(f"No atmosphere folder in {sd_root}, and it doesn't look like a Switch SD "
                          f"(no Nintendo, switch or bootloader folder either). Pick the SD's drive.",
                          f"No encontré la carpeta atmosphere en {sd_root}, y no parece una SD de "
                          f"Switch (tampoco tiene Nintendo, switch ni bootloader). Elige la unidad de la SD.")
    jobs = []
    for t in TITLES:
        src = _title_dir(Path(pack_root), t)
        if src:
            dst = contents / t
            if _inside(src, dst) or _inside(dst, src):
                raise DeployError("The open modpack is on the same SD you want to copy to. "
                                  "Import it to the PC first.",
                                  "El modpack abierto está en la misma SD a la que quieres "
                                  "copiar. Impórtalo primero al PC.")
            jobs.append((t, src, dst))
    if not jobs:
        raise DeployError("The modpack has no Skyrim folders to copy",
                          "El modpack no tiene carpetas de Skyrim para copiar")
    return contents, jobs


def _check_space(sd_root: Path, needed: int):
    free = sd_free_space(sd_root)
    if needed + FREE_MARGIN > free:
        mb = lambda n: f"{n / 2**20:,.0f} MB"  # noqa: E731
        raise DeployError(
            f"The SD doesn't have room: the copy needs {mb(needed)} more and only "
            f"{mb(free)} are free (I keep {mb(FREE_MARGIN)} spare). Free up space on the SD "
            f"or make the modpack smaller.",
            f"No cabe en la SD: la copia necesita {mb(needed)} más y solo hay {mb(free)} "
            f"libres (dejo {mb(FREE_MARGIN)} de margen). Libera espacio en la SD o aligera "
            f"el modpack.")


# ---------------------------------------------------------------------------
# Sync: plan
# ---------------------------------------------------------------------------

@dataclass
class _F:
    rel: str            # path relative to contents, "/" separated, real case
    path: Path
    size: int
    mtime: float
    mode: int = 0
    mtime_ns: int = 0


@dataclass
class CopyItem:
    src: Path
    rel: str                    # destination, pack's case, relative to contents
    size: int
    old_rel: str | None = None  # SD file being replaced (its current spelling), or None if new
    old_size: int = 0


@dataclass
class SyncPlan:
    pack_root: Path
    sd_root: Path
    contents: Path
    titles: list[str] = field(default_factory=list)
    to_copy: list[CopyItem] = field(default_factory=list)
    to_delete: list[tuple[str, int]] = field(default_factory=list)   # (rel, size)
    renames: list[tuple[str, str]] = field(default_factory=list)     # files, case only
    dir_renames: list[tuple[str, str]] = field(default_factory=list)  # folders, case only
    touch: list[tuple[str, float]] = field(default_factory=list)     # same content, align date
    moves: list[tuple[str, str]] = field(default_factory=list)       # same file, new name: (sd rel, pack rel)
    unchanged: int = 0
    unchanged_bytes: int = 0
    hashed: int = 0
    _sd: dict = field(default_factory=dict, repr=False)               # rel -> _F (SD side)

    @property
    def copy_bytes(self) -> int:
        return sum(c.size for c in self.to_copy)

    @property
    def delete_bytes(self) -> int:
        return sum(s for _, s in self.to_delete)

    @property
    def overwrite(self) -> list[CopyItem]:
        return [c for c in self.to_copy if c.old_rel]

    @property
    def backup_files(self) -> list[str]:
        """SD files (current spelling) the backup has to hold."""
        return [c.old_rel for c in self.overwrite] + [r for r, _ in self.to_delete]

    @property
    def backup_bytes(self) -> int:
        return sum(c.old_size for c in self.overwrite) + self.delete_bytes

    @property
    def space_needed(self) -> int:
        """Extra SD space needed at the worst moment of the copy. Deletions run
        after the copies, so they don't help; each replaced file briefly
        exists twice (temp copy + old one)."""
        new = sum(c.size for c in self.to_copy if not c.old_rel)
        grow = sum(max(0, c.size - c.old_size) for c in self.overwrite)
        peak = max((min(c.size, c.old_size) for c in self.overwrite), default=0)
        return new + grow + peak

    @property
    def first(self) -> bool:
        """The SD has no Skyrim title folders yet: a first copy, everything is new."""
        return not any((self.contents / t).exists() for t in TITLES)

    @property
    def empty(self) -> bool:
        return not (self.to_copy or self.to_delete or self.renames or self.dir_renames or self.moves)

    def to_dict(self) -> dict:
        try:
            free = sd_free_space(self.sd_root)
        except (OSError, DeployError):
            free = None
        return {"titles": self.titles, "target": str(self.contents), "first": self.first,
                "free": free, "margin": FREE_MARGIN,
                "fits": None if free is None else self.space_needed + FREE_MARGIN <= free,
                "copy": len(self.to_copy), "copy_bytes": self.copy_bytes,
                "new": sum(1 for c in self.to_copy if not c.old_rel),
                "replace": len(self.overwrite),
                "delete": len(self.to_delete), "delete_bytes": self.delete_bytes,
                "rename": len(self.renames) + len(self.dir_renames),
                "move": len(self.moves),
                "unchanged": self.unchanged, "unchanged_bytes": self.unchanged_bytes,
                "backup_files": len(self.backup_files), "backup_bytes": self.backup_bytes,
                "space_needed": self.space_needed,
                # every file, so the lists on the page are complete (a cap only
                # against a pathological first copy)
                "examples": {"copy": [c.rel for c in self.to_copy if not c.old_rel][:CAP],
                             "replace": [c.rel for c in self.overwrite[:CAP]],
                             "delete": [r for r, _ in self.to_delete[:CAP]],
                             "move": [f"{a.rsplit('/', 1)[-1]} → {b.rsplit('/', 1)[-1]}" for a, b in self.moves[:CAP]],
                             "rename": [f"{a} → {b.rsplit('/', 1)[-1]}" for a, b in (self.dir_renames + self.renames)[:CAP]],
                             "backup": self.backup_files[:CAP]},
                # Atmosphère's cache of the mods' file list; it builds it again
                # when the game starts, so removing it with the old files is right
                "metadata": sum(1 for r, _ in self.to_delete if r.lower().endswith("romfs_metadata.bin"))}


def _scan(base: Path, prefix: str, skip_temp: bool):
    """Files and folders under base: {lower rel: _F}, {lower rel: rel}, collisions."""
    files: dict[str, _F] = {}
    dirs: dict[str, str] = {}
    clashes: list[tuple[str, str]] = []
    if not base.is_dir():
        return files, dirs, clashes
    for dirpath, dirnames, filenames in os.walk(base, onerror=_raise):
        dirnames[:] = [d for d in dirnames if d not in SKIP_DIRS
                       and not d.lower().endswith(SKIP_SUFFIX)]
        here = Path(dirpath).relative_to(base).as_posix()
        here = prefix if here == "." else f"{prefix}/{here}"
        for d in dirnames:
            rel = f"{here}/{d}"
            if rel.lower() in dirs:
                clashes.append((dirs[rel.lower()], rel))
            else:
                dirs[rel.lower()] = rel
        for f in filenames:
            if skip_temp and f.lower().endswith(SKIP_SUFFIX):
                continue
            p = Path(dirpath) / f
            st = p.stat()
            rel = f"{here}/{f}"
            if rel.lower() in files:
                clashes.append((files[rel.lower()].rel, rel))
                continue
            files[rel.lower()] = _F(rel, p, st.st_size, st.st_mtime, st.st_mode, st.st_mtime_ns)
    return files, dirs, clashes


def _digest(p: Path) -> bytes:
    h = hashlib.blake2b(digest_size=20)
    with p.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.digest()


def plan_sync(pack_root: Path, sd_root: Path, progress=None) -> SyncPlan:
    """What a sync would do, without touching anything (it only reads; files
    under 8 MB with the same size and another date are hashed on both sides)."""
    contents, jobs = _jobs(pack_root, sd_root)
    plan = SyncPlan(Path(pack_root), Path(sd_root), contents, [t for t, _, _ in jobs])
    pack_files: dict[str, _F] = {}
    sd_files: dict[str, _F] = {}
    pack_dirs: dict[str, str] = {}
    sd_dirs: dict[str, str] = {}
    sd_extra: list[_F] = []
    for t, src, dst in jobs:
        pf, pd, clash = _scan(src, t, skip_temp=True)
        if clash:
            a, b = clash[0]
            raise DeployError(
                f"The modpack has two names that differ only in case ({a} / {b}). The SD "
                f"can't tell them apart; delete or rename one.",
                f"El modpack tiene dos nombres que solo cambian en mayúsculas ({a} / {b}). La "
                f"SD no los distingue; borra o renombra uno.")
        sf, sdd, sclash = _scan(dst, t, skip_temp=True)
        for _a, b in sclash:     # only possible on a case-sensitive copy of the SD
            low = b.lower()
            if low in sf and sf[low].rel != b:
                st = (dst.parent / b).stat()
                sd_extra.append(_F(b, dst.parent / b, st.st_size, st.st_mtime, st.st_mode,
                                   st.st_mtime_ns))
        pack_files.update(pf); pack_dirs.update(pd)
        sd_files.update(sf); sd_dirs.update(sdd)

    def final_rel(rel: str) -> str:
        """Spelling an SD path will have once folder case renames are done."""
        parts = rel.split("/")
        out = [parts[0]]
        for i in range(1, len(parts)):
            key = "/".join(parts[: i + 1]).lower()
            name = parts[i]
            if i < len(parts) - 1 and key in pack_dirs and key in sd_dirs:
                name = pack_dirs[key].rsplit("/", 1)[1]
            out.append(name)
        return "/".join(out)

    for key in sorted(set(pack_dirs) & set(sd_dirs), key=lambda k: k.count("/")):
        new, old = pack_dirs[key], sd_dirs[key]
        if new.rsplit("/", 1)[1] != old.rsplit("/", 1)[1]:
            parent = final_rel(old.rsplit("/", 1)[0] + "/x").rsplit("/", 1)[0]
            plan.dir_renames.append((f"{parent}/{old.rsplit('/', 1)[1]}", new))

    todo = sorted(pack_files.items())
    for i, (key, pf) in enumerate(todo):
        if progress and i % 200 == 0:
            progress(f"Comparing {pf.path.name}", i, len(todo))
        sf = sd_files.get(key)
        if sf is None:
            plan.to_copy.append(CopyItem(pf.path, pf.rel, pf.size))
            continue
        cur = final_rel(sf.rel)
        same = False
        if sf.size == pf.size:
            if abs(sf.mtime - pf.mtime) <= MTIME_TOLERANCE:
                same = True
            elif pf.mtime < FAT_EPOCH and sf.mtime < FAT_EPOCH:
                # a file dated before 1980 (some packs ship them dated 1970): the
                # card can't store that date and keeps 1980 instead, so the two
                # dates never match; both being "before the card's first day"
                # with the same size is the same file the last copy wrote.
                same = True
            elif pf.size < HASH_LIMIT or pf.mtime < FAT_EPOCH:
                # small files, and any file dated before 1980 whose copy got
                # another date (see FAT_STAMP): compare the content once, then
                # fix the card's date so next time it's quick
                plan.hashed += 1
                if _digest(pf.path) == _digest(sf.path):
                    same = True
                    plan.touch.append((pf.rel, pf.mtime))
        if same:
            plan.unchanged += 1
            plan.unchanged_bytes += pf.size
            if cur != pf.rel:
                plan.renames.append((cur, pf.rel))
        else:
            plan.to_copy.append(CopyItem(pf.path, pf.rel, pf.size, cur, sf.size))
    for key, sf in sorted(sd_files.items()):
        if key not in pack_files:
            plan.to_delete.append((final_rel(sf.rel), sf.size))
    for sf in sd_extra:
        plan.to_delete.append((final_rel(sf.rel), sf.size))
    plan._sd = {final_rel(f.rel): f for f in list(sd_files.values()) + sd_extra}
    _pair_moves(plan, pack_files)
    return plan


def _pair_moves(plan: SyncPlan, pack_files: dict) -> None:
    """A file the pack renamed (a BSA given a short name) shows up as one new
    file and one to remove, with the same size and date: rename it on the SD
    instead of copying it again. Files under 8 MB are also compared by content."""
    gone: dict[tuple[str, int], list[str]] = {}
    for rel, size in plan.to_delete:
        gone.setdefault((rel.split("/", 1)[0].upper(), size), []).append(rel)
    keep = []
    for item in plan.to_copy:
        pf = pack_files.get(item.rel.lower())
        cands = gone.get((item.rel.split("/", 1)[0].upper(), item.size)) if not item.old_rel and pf else None
        hit = None
        for rel in cands or []:
            sf = plan._sd.get(rel)
            if sf is None:
                continue
            same_date = abs(sf.mtime - pf.mtime) <= MTIME_TOLERANCE or \
                (pf.mtime < FAT_EPOCH and sf.mtime < FAT_EPOCH)
            if item.size < HASH_LIMIT:
                # small: the content decides, whatever the dates (plugins dated
                # 1970 got the card's 1980 date and never matched by date)
                if _digest(pf.path) != _digest(sf.path):
                    continue
            elif not same_date:
                continue
            hit = rel
            break
        if hit:
            cands.remove(hit)
            plan.moves.append((hit, item.rel))
            if abs(plan._sd[hit].mtime - pf.mtime) > MTIME_TOLERANCE:
                plan.touch.append((item.rel, pf.mtime))
        else:
            keep.append(item)
    if plan.moves:
        moved = {a for a, _b in plan.moves}
        plan.to_copy = keep
        plan.to_delete = [(r, n) for r, n in plan.to_delete if r not in moved]


# ---------------------------------------------------------------------------
# Sync: apply
# ---------------------------------------------------------------------------

def _case_rename(a: Path, b: Path):
    """Rename that works on case-insensitive file systems (via a temp name)."""
    tmp = a.with_name(a.name + TMP_REN)
    os.replace(a, tmp)
    try:
        os.replace(tmp, b)
    except BaseException:
        os.replace(tmp, a)
        raise


class _Undo:
    def __init__(self):
        self.created_files: list[Path] = []
        self.created_dirs: list[Path] = []
        self.removed_dirs: list[Path] = []
        self.renames: list[tuple[Path, Path]] = []
        self.dir_renames: list[tuple[Path, Path]] = []
        self.touched: list[tuple[Path, int]] = []
        self.moves: list[tuple[Path, Path]] = []
        self.tmp: Path | None = None


def _mkdirs(d: Path, undo: _Undo):
    missing = []
    p = d
    while not p.exists():
        missing.append(p)
        p = p.parent
    for m in reversed(missing):
        m.mkdir()
        undo.created_dirs.append(m)


def _rollback(plan: SyncPlan, undo: _Undo, backup: Path | None):
    c = plan.contents
    errors = []

    def attempt(fn, *a):
        try:
            fn(*a)
        except FileNotFoundError:
            pass
        except Exception as e:  # noqa: BLE001
            errors.append(f"{a[0] if a else ''}: {e}")

    if undo.tmp is not None:
        attempt(_remove_file, undo.tmp)
    for p in reversed(undo.created_files):
        attempt(_remove_file, p)
    for old, new in reversed(undo.moves):
        attempt(lambda a, b: (b.parent.mkdir(parents=True, exist_ok=True), os.replace(a, b)), new, old)
    for d in reversed(undo.removed_dirs):
        attempt(lambda x: x.mkdir(parents=True, exist_ok=True), d)
    for d in sorted(undo.created_dirs, key=lambda p: -len(p.parts)):
        attempt(os.rmdir, d)
    for p, ns in undo.touched:
        attempt(lambda x, t=ns: os.utime(x, ns=(t, t)), p)
    for old, new in reversed(undo.renames):
        attempt(_case_rename, new, old)
    for old, new in reversed(undo.dir_renames):
        attempt(_case_rename, new, old)
    if backup:
        orig_by_rel = {f.rel: f for f in plan._sd.values()}
        with zipfile.ZipFile(backup) as z:
            for info in z.infolist():
                rel = info.filename.replace("\\", "/")
                out = c / rel
                try:
                    _make_writable(out)
                    out.parent.mkdir(parents=True, exist_ok=True)
                    with z.open(info) as r, open(out, "wb") as w:
                        shutil.copyfileobj(r, w, 1 << 20)
                    orig = orig_by_rel.get(rel)
                    if orig:
                        os.utime(out, ns=(orig.mtime_ns, orig.mtime_ns))
                        os.chmod(out, stat.S_IMODE(orig.mode))
                except Exception as e:  # noqa: BLE001
                    errors.append(f"{rel}: {e}")
    return errors


def _sync(plan: SyncPlan, progress=None) -> dict:
    t0 = time.time()
    c = plan.contents
    _check_space(plan.sd_root, plan.space_needed)
    backup = None
    if plan.backup_files:
        backup = _backup_path(plan.pack_root, "-sync")
        try:
            # plan paths use the spelling after case renames; the backup is taken
            # before them, so it stores each file under its current SD name.
            _zip_and_verify(backup, c, [plan._sd[r].path for r in plan.backup_files], progress)
        except DeployError:
            backup.unlink(missing_ok=True)
            raise
        except Exception as e:
            backup.unlink(missing_ok=True)
            raise DeployError(f"I couldn't make the backup ({e}); I didn't touch the SD",
                              f"No pude hacer el respaldo ({e}); no toqué la SD") from e
    undo = _Undo()
    copied = deleted = total = 0
    try:
        for old, new in plan.dir_renames:
            _case_rename(c / old, c / new)
            undo.dir_renames.append((c / old, c / new))
        for old, new in plan.renames:
            _make_writable(c / old)
            _case_rename(c / old, c / new)
            undo.renames.append((c / old, c / new))
        moved = 0
        for old, new in plan.moves:
            dst = c / new
            _mkdirs(dst.parent, undo)
            _make_writable(c / old)
            os.replace(c / old, dst)
            undo.moves.append((c / old, dst))
            moved += 1
        n = len(plan.to_copy)
        for i, item in enumerate(plan.to_copy):
            out = c / item.rel
            if progress:
                progress(f"Copying {item.rel.split('/', 1)[-1]}", i, n)
            _mkdirs(out.parent, undo)
            tmp = out.with_name(out.name + TMP_NEW)
            undo.tmp = tmp
            _copy_file(item.src, tmp)
            if item.old_rel:
                old = c / item.old_rel
                _make_writable(old)
                if item.old_rel != item.rel:
                    # case-only change of a replaced file: drop the old spelling
                    # first (it's in the backup) so the new one is used.
                    os.unlink(old)
                    undo.created_files.append(out)
            else:
                undo.created_files.append(out)
            os.replace(tmp, out)
            undo.tmp = None
            copied += 1
            total += item.size
        for rel, mtime in plan.touch:
            p = c / rel
            try:
                before = p.stat().st_mtime_ns
                t = FAT_STAMP if mtime < FAT_EPOCH else mtime
                os.utime(p, (t, t))
                undo.touched.append((p, before))
            except OSError:
                pass   # only an optimisation for the next run
        for i, (rel, _size) in enumerate(plan.to_delete):
            if progress:
                progress(f"Removing {rel.split('/', 1)[-1]}", i, len(plan.to_delete))
            _remove_file(c / rel)
            deleted += 1
        for t in plan.titles:
            base = c / t
            if not base.is_dir():
                continue
            for dirpath, dirnames, filenames in os.walk(base, topdown=False):
                d = Path(dirpath)
                if d == base or any(part in SKIP_DIRS for part in d.relative_to(base).parts):
                    continue
                if not os.listdir(d):
                    _make_writable(d)
                    os.rmdir(d)
                    undo.removed_dirs.append(d)
    except BaseException as e:
        errors = _rollback(plan, undo, backup)
        if not isinstance(e, Exception):
            raise
        where = f" Backup: {backup}" if backup else ""
        donde = f" Respaldo: {backup}" if backup else ""
        if errors:
            raise DeployError(
                f"Copy failed ({e}) and I couldn't undo everything: {'; '.join(errors[:3])}."
                f"{where}",
                f"Falló la copia ({e}) y no pude deshacer todo: {'; '.join(errors[:3])}."
                f"{donde}") from e
        raise DeployError(f"Copy failed ({e}). I put the SD back as it was.{where}",
                          f"Falló la copia ({e}). Dejé la SD como estaba.{donde}") from e
    return {"mode": "sync", "copied": copied, "deleted": deleted, "unchanged": plan.unchanged,
            "renamed": len(plan.renames) + len(plan.dir_renames), "moved": moved,
            "bytes_copied": total, "backup": str(backup) if backup else None,
            "seconds": round(time.time() - t0, 2),
            "files": copied, "bytes": total, "target": str(c)}


# ---------------------------------------------------------------------------
# Full replace (the original behaviour)
# ---------------------------------------------------------------------------

def _deploy_full(pack_root: Path, sd_root: Path, progress=None) -> dict:
    t0 = time.time()
    contents, jobs3 = _jobs(pack_root, sd_root)
    jobs = [(s, d) for _t, s, d in jobs3]
    all_files = [(s, d, f) for s, d in jobs for f in _iter_files(s, skip_temp=True)]
    pack_bytes = sum(f.stat().st_size for _s, _d, f in all_files)
    pack_keys = {(d.name.upper(), f.relative_to(s).as_posix().lower()) for s, d, f in all_files}
    old = [(d, f) for _s, d in jobs if d.exists() for f in _iter_files(d)]
    old_bytes = sum(f.stat().st_size for _d, f in old)
    gone = sum(1 for d, f in old if (d.name.upper(), f.relative_to(d).as_posix().lower())
               not in pack_keys)
    _check_space(sd_root, max(0, pack_bytes - old_bytes))
    backup = backup_sd(sd_root, pack_root, progress)
    try:
        for s, d in jobs:
            if d.exists():
                _force_rmtree(d)
        copied = total = 0
        for i, (s, d, f) in enumerate(all_files):
            rel = f.relative_to(s)
            out = d / rel
            out.parent.mkdir(parents=True, exist_ok=True)
            if progress:
                progress(f"Copying {rel}", i, len(all_files))
            _copy_file(f, out)
            copied += 1
            total += f.stat().st_size
    except Exception as e:
        for s, d in jobs:
            if d.exists():
                _force_rmtree(d)
        if backup:
            with zipfile.ZipFile(backup) as z:
                z.extractall(contents)
        raise DeployError(f"Copy failed ({e}). I put the SD back as it was from the backup.",
                          f"Falló la copia ({e}). Dejé la SD como estaba con el respaldo.") from e
    return {"mode": "full", "copied": copied, "deleted": gone, "unchanged": 0, "renamed": 0,
            "bytes_copied": total, "backup": str(backup) if backup else None,
            "seconds": round(time.time() - t0, 2),
            "files": copied, "bytes": total, "target": str(contents)}


def deploy(pack_root: Path, sd_root: Path, progress=None, mode: str = "sync") -> dict:
    """Copy the pack's title folders to the SD.

    mode="sync" copies only what changed (see the module docstring);
    mode="full" replaces both folders whole. Returns
    {mode, copied, deleted, unchanged, renamed, bytes_copied, backup, seconds,
     files, bytes, target}; files/bytes are the same as copied/bytes_copied."""
    if mode == "full":
        return _deploy_full(Path(pack_root), Path(sd_root), progress)
    if mode != "sync":
        raise ValueError(f"unknown deploy mode {mode!r}")
    plan = plan_sync(pack_root, sd_root, progress)
    return _sync(plan, progress)


def import_from_sd(sd_root: Path, project_root: Path, progress=None) -> dict:
    contents = sd_contents(sd_root)
    project_root = Path(project_root)
    if project_root.exists() and any(project_root.iterdir()):
        raise DeployError("The destination folder isn't empty; pick a new one", "La carpeta de destino no está vacía; elige una nueva")
    files = []
    for t in TITLES:
        d = contents / t
        if d.exists():
            files += [(d, f) for f in _iter_files(d)]
    if not files:
        raise DeployError("There are no Skyrim folders on that SD", "No hay carpetas de Skyrim en esa SD")
    for i, (d, f) in enumerate(files):
        out = project_root / d.name / f.relative_to(d)
        out.parent.mkdir(parents=True, exist_ok=True)
        if progress:
            progress(f"Copying {f.name}", i, len(files))
        shutil.copy2(f, out)
    return {"files": len(files), "project": str(project_root)}
