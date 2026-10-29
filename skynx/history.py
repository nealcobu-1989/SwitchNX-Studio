"""Change history for a pack, without git.

Every change goes through a Transaction: before a file is modified or
created, its previous state is copied into
<pack root>/.skynx/history/<timestamp>-<n>-<slug>/ and recorded in
manifest.json. Files removed by a fix are moved to .skynx/trash (older entries may point to .skynx/papelera).

Undo is itself a Transaction (so it can be undone), and it refuses to run
when a file was changed again after the entry, unless forced.
"""
from __future__ import annotations

import hashlib
import json
import os
import shutil
import stat
import time
from dataclasses import dataclass, field
from pathlib import Path


from .errors import SkynxError


class HistoryError(SkynxError):
    pass


def _sha(p: Path) -> str:
    h = hashlib.sha1()
    with Path(p).open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def _slug(s: str) -> str:
    keep = "".join(c if c.isalnum() else "-" for c in s.lower())
    while "--" in keep:
        keep = keep.replace("--", "-")
    return keep.strip("-")[:24] or "cambio"      # short: Windows paths are limited


def _writable(p: Path) -> None:
    """Windows refuses to replace read-only files; clear that flag first."""
    try:
        if p.exists() and not os.access(p, os.W_OK):
            os.chmod(p, stat.S_IWRITE | stat.S_IREAD)
    except OSError:
        pass


def history_dir(root: Path) -> Path:
    return Path(root) / ".skynx" / "history"


def _next_seq(base: Path) -> int:
    f = base / ".seq"
    n = int(f.read_text()) + 1 if f.exists() else 1
    f.write_text(str(n))
    return n


def _same_file(a: Path, b: Path) -> bool:
    try:
        return os.path.samefile(a, b)
    except OSError:
        return False


@dataclass
class Transaction:
    root: Path
    title: str
    detail: str = ""
    dir: Path | None = None
    files: list[dict] = field(default_factory=list)
    seq: int = 0
    is_undo: bool = False

    def __enter__(self) -> "Transaction":
        base = history_dir(self.root)
        base.mkdir(parents=True, exist_ok=True)
        self.seq = _next_seq(base)
        stamp = time.strftime("%Y%m%d-%H%M%S")
        d = base / f"{stamp}-{self.seq:05d}-{_slug(self.title)}"
        d.mkdir()
        self.dir = d
        return self

    def _rel(self, p: Path) -> str:
        return str(Path(os.path.abspath(p)).relative_to(Path(os.path.abspath(self.root))))

    def before_change(self, path: Path) -> None:
        """Call before overwriting, renaming or deleting `path`."""
        path = Path(path)
        rel = self._rel(path)
        if any(f["path"].lower() == rel.lower() for f in self.files):
            return
        if path.exists():
            backup = self.dir / "files" / rel
            backup.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(path, backup)
            sha = _sha(path)
            if _sha(backup) != sha:
                raise HistoryError(f"The backup of {rel} isn't identical", f"El respaldo de {rel} no quedó idéntico")
            self.files.append({"path": rel, "existed": True, "sha_before": sha})
        else:
            self.files.append({"path": rel, "existed": False})
        self._journal()

    def write_bytes(self, path: Path, data: bytes) -> None:
        self.before_change(path)
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp = path.with_name(path.name + ".skynx-tmp")
        try:
            tmp.write_bytes(data)
            _writable(path)
            os.replace(tmp, path)
        finally:
            if tmp.exists():
                tmp.unlink()

    def copy_in(self, src: Path, dest: Path) -> None:
        """Copy an outside file into the pack (dest must not exist yet)."""
        dest = Path(dest)
        if dest.exists():
            raise HistoryError(f"{dest.name} already exists; I won't overwrite it",
                               f"Ya existe {dest.name}; no lo sobrescribo")
        self.before_change(dest)
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, dest)

    def replace_with(self, path: Path, new_file: Path) -> None:
        """Put an already-written file (e.g. a rebuilt BSA) in place of `path`."""
        self.before_change(path)
        _writable(Path(path))
        os.replace(new_file, path)

    def move(self, src: Path, dest: Path) -> None:
        """Rename within the pack. Handles names that differ only in case."""
        src, dest = Path(src), Path(dest)
        case_only = src.name.lower() == dest.name.lower() and src.parent == dest.parent
        if dest.exists() and not case_only:
            raise HistoryError(f"{dest.name} already exists; I won't overwrite it", f"Ya existe {dest.name}; no lo sobrescribo")
        self.before_change(src)
        if not case_only:
            self.before_change(dest)
        _writable(src)
        if case_only:
            self.files.append({"path": self._rel(dest), "existed": False, "case_of": self._rel(src)})
            self._journal()
            tmp = src.with_name(src.name + ".skynx-ren")
            os.rename(src, tmp)
            os.rename(tmp, dest)
        else:
            os.rename(src, dest)

    def trash(self, path: Path) -> Path:
        """Move a file into the project's trash without copying it. Undo moves it back."""
        path = Path(path)
        dest = Path(self.root) / ".skynx" / "trash" / self.dir.name / self._rel(path)
        dest.parent.mkdir(parents=True, exist_ok=True)
        _writable(path)
        self.files.append({"path": self._rel(path), "existed": True, "trashed_to": self._rel(dest)})
        self._journal()
        shutil.move(str(path), str(dest))
        return dest

    def __exit__(self, exc_type, exc, tb) -> bool:
        changed = False
        for f in self.files:
            if f.get("trashed_to") or f.get("case_of"):
                changed = True
                continue
            p = Path(self.root) / f["path"]
            f["exists_after"] = p.exists()
            if p.exists() and p.is_file():
                f["sha_after"] = _sha(p)
            if f.get("sha_after") != f.get("sha_before") or f["existed"] != f["exists_after"]:
                changed = True
        manifest = {"title": self.title, "detail": self.detail, "seq": self.seq,
                    "time": time.strftime("%Y-%m-%d %H:%M:%S"),
                    "ok": exc_type is None, "changed": changed, "is_undo": self.is_undo,
                    "files": self.files}
        self._write(manifest)
        if exc_type is not None and not self.files:
            shutil.rmtree(self.dir, ignore_errors=True)   # failed before touching anything
            return False
        if exc_type is not None:
            _restore(self.root, self.dir, manifest)
            manifest["undone"] = "revertido por un error"
            self._write(manifest)
        elif not changed:
            shutil.rmtree(self.dir, ignore_errors=True)   # nothing changed: no entry
        return False

    def _journal(self) -> None:
        """Write the list of touched files before each change, so a change cut
        short (the program closed or crashed) can be rolled back next time."""
        self._write({"title": self.title, "detail": self.detail, "seq": self.seq,
                     "time": time.strftime("%Y-%m-%d %H:%M:%S"), "pending": True,
                     "is_undo": self.is_undo, "files": self.files})

    def _write(self, manifest: dict) -> None:
        (self.dir / "manifest.json").write_text(
            json.dumps(manifest, indent=1, ensure_ascii=False), encoding="utf-8")

    @property
    def changed(self) -> bool:
        return self.dir is not None and self.dir.exists()


def recover_interrupted(root: Path) -> list[str]:
    """Roll back changes that were cut short (manifest still 'pending').
    Returns their titles."""
    out = []
    base = history_dir(root)
    if not base.exists():
        return out
    for d in sorted(base.iterdir()):
        m_path = d / "manifest.json"
        if not (d.is_dir() and m_path.exists()):
            continue
        try:
            m = json.loads(m_path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        if not m.get("pending"):
            continue
        _restore(root, d, m)
        m.update(pending=False, ok=False, changed=True,
                 undone=time.strftime("%Y-%m-%d %H:%M:%S") + " (interrumpido)")
        m_path.write_text(json.dumps(m, indent=1, ensure_ascii=False), encoding="utf-8")
        out.append(m.get("title", d.name))
    return out


def list_history(root: Path) -> list[dict]:
    out = []
    base = history_dir(root)
    if not base.exists():
        return out
    for d in base.iterdir():
        m = d / "manifest.json"
        if d.is_dir() and m.exists():
            data = json.loads(m.read_text(encoding="utf-8"))
            data["id"] = d.name
            out.append(data)
    out.sort(key=lambda e: e.get("seq", 0), reverse=True)
    return out


def conflicts(root: Path, entry_id: str) -> list[str]:
    """Files that changed again after this entry (undo would overwrite them)."""
    m = json.loads((history_dir(root) / entry_id / "manifest.json").read_text(encoding="utf-8"))
    out = []
    for f in m["files"]:
        p = Path(root) / f["path"]
        if f.get("trashed_to"):
            if p.exists():
                out.append(f["path"])
            continue
        if f.get("case_of"):
            continue
        now = _sha(p) if p.exists() and p.is_file() else None
        if now != f.get("sha_after"):
            out.append(f["path"])
    return out


def _restore(root: Path, d: Path, m: dict) -> list[str]:
    restored = []
    for f in reversed(m["files"]):
        target = Path(root) / f["path"]
        if f.get("trashed_to"):
            src = Path(root) / f["trashed_to"]
            if src.exists() and not target.exists():
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.move(str(src), str(target))
                restored.append(f["path"])
            continue
        if f.get("case_of"):
            orig = Path(root) / f["case_of"]
            if target.exists():
                tmp = target.with_name(target.name + ".skynx-ren")
                os.rename(target, tmp)
                os.rename(tmp, orig)
                restored.append(f["case_of"])
            continue
        if f["existed"]:
            target.parent.mkdir(parents=True, exist_ok=True)
            _writable(target)
            # a new file swapped in: never write into the old one, which may be a
            # hard link shared with another pack
            tmp = target.with_name(target.name + ".skynx-undo")
            shutil.copy2(d / "files" / f["path"], tmp)
            os.replace(tmp, target)
            restored.append(f["path"])
        elif target.exists() and not any(
                g.get("case_of") and (Path(root) / g["case_of"]) == target for g in m["files"]):
            _writable(target)
            target.unlink()
            restored.append(f["path"] + " (eliminado)")
    return restored


def undo(root: Path, entry_id: str, force: bool = False) -> list[str]:
    d = history_dir(root) / entry_id
    m = json.loads((d / "manifest.json").read_text(encoding="utf-8"))
    if m.get("undone"):
        raise HistoryError("This change was already undone", "Este cambio ya se deshizo")
    if m.get("is_undo"):
        raise HistoryError("This was an undo. To get that state back, apply the fix again.", "Esto fue un deshacer. Para recuperar ese estado, vuelve a aplicar el arreglo.")
    clash = conflicts(root, entry_id)
    if clash and not force:
        raise HistoryError("These files changed again afterwards. Undo the newer changes first: "
                           + ", ".join(clash),
                           "Estos archivos cambiaron después de ese cambio. Deshaz primero los "
                           "más recientes: " + ", ".join(clash))
    with Transaction(root, f"Undo: {m['title']}", is_undo=True) as tx:
        for f in m["files"]:
            p = Path(root) / f["path"]
            tx.before_change(p)
            if f.get("case_of"):
                tx.before_change(Path(root) / f["case_of"])
        restored = _restore(root, d, m)
    m["undone"] = time.strftime("%Y-%m-%d %H:%M:%S")
    (d / "manifest.json").write_text(json.dumps(m, indent=1, ensure_ascii=False),
                                     encoding="utf-8")
    return restored
