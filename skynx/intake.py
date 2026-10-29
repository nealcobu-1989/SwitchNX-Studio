"""What is this thing? A first look at whatever the user drops on the app.

Users arrive with a mix of things: zips of whole community modpacks (Google
Drive, Discord), mods "already converted for Switch", and PC mods from Nexus,
some with FOMOD installers. `detect(path)` tells them apart cheaply:

- archives are listed, not extracted. Only a short sample is read: the first
  30 loose textures, 10 voices, 10 animations, and the headers of a few BSAs
  (a BSA inside an archive has to be extracted to read its directory);
- textures: DDS = PC, NVN (DFvN) = Switch (textures.inspect);
- voices: Switch FUZE carries Nintendo Opus (nxaudio.is_switch_fuz);
- animations: byte 18 of a 64-bit hkx is 1 on Switch (hkx.classify).

The archive helpers (`list_names`, `safe_extract`) are shared by the Library
and by transfers.
"""
from __future__ import annotations

import os
import re
import shutil
import stat
import tempfile
import zipfile
from dataclasses import dataclass, field
from pathlib import Path, PurePosixPath

from . import hkx as HKX
from . import knowledge as K
from .bsa import read_bsa
from .errors import SkynxError
from .nxaudio import is_switch_fuz
from .textures import inspect as inspect_tex

PLUGIN_EXT = {".esp", ".esm", ".esl"}
ARCHIVE_EXT = {".zip", ".7z"}
ASSET_DIRS = {"meshes", "textures", "sound", "music", "scripts", "interface", "seq", "strings",
              "lodsettings", "grass", "shadersfx", "video", "dialogueviews", "sky", "materials",
              "lightingtemplates", "terrain", "trees"}
TEX_SAMPLE, SND_SAMPLE, HKX_SAMPLE = 30, 10, 10
BSA_SAMPLE = 4                       # BSAs whose headers are read
BSA_EXTRACT_BUDGET = 600 * 2**20     # bytes of BSAs extracted from an archive to peek
KINDS = ("modpack", "fomod", "switch-mod", "pc-mod", "mixed", "unknown")
ACTIONS = {"modpack": "library", "fomod": "fomod", "switch-mod": "add", "pc-mod": "convert",
           "mixed": "convert", "unknown": None}


class IntakeError(SkynxError):
    pass


# ---------------------------------------------------------------- archives
@dataclass
class Member:
    name: str          # relative path with "/" separators, as stored
    size: int
    is_dir: bool
    is_link: bool = False


def archive_type(path: Path) -> str | None:
    low = Path(path).name.lower()
    if low.endswith(".zip"):
        return "zip"
    if low.endswith(".7z"):
        return "7z"
    if low.endswith(".rar"):
        return "rar"
    return None


# ------------------------------------------------------------------ .rar
# Python can't read RAR on its own. 7-Zip opens every kind; Windows 10/11 also
# ship tar.exe (libarchive), which reads RAR (RAR5 with recent Windows builds).
def rar_tool() -> list[str] | None:
    import shutil as _sh
    import sys as _sys
    cands = []
    for d in (Path(_sys.executable).parent, Path(r"C:\SkyNX\Tools"), Path(r"C:\Program Files\7-Zip"),
              Path(r"C:\Program Files (x86)\7-Zip")):
        for exe in ("7z.exe", "7za.exe"):
            if (d / exe).is_file():
                return [str(d / exe)]
    for name in ("7z", "7za", "7zz"):
        w = _sh.which(name)
        if w:
            return [w]
    sysroot = os.environ.get("SystemRoot") or r"C:\Windows"
    tar = Path(sysroot) / "System32" / "tar.exe"
    if tar.is_file():
        cands.append(str(tar))
    w = _sh.which("bsdtar")
    if w:
        cands.append(w)
    return [cands[0]] if cands else None


def _run_quiet(cmd: list[str], timeout: int = 3600) -> str:
    import subprocess
    kw = {"capture_output": True, "timeout": timeout, "stdin": subprocess.DEVNULL}   # never waits for a password
    if os.name == "nt":
        kw["creationflags"] = 0x08000000  # CREATE_NO_WINDOW
    r = subprocess.run(cmd, **kw)
    if r.returncode != 0:
        err = (r.stderr or r.stdout or b"").decode("utf-8", "replace").strip().splitlines()[-1:] or [""]
        raise IntakeError(f"Couldn't open the .rar ({err[0][:200]}). Extract it with 7-Zip or WinRAR and drop the folder.",
                          f"No pude abrir el .rar ({err[0][:200]}). Extráelo con 7-Zip o WinRAR y suelta la carpeta.")
    return r.stdout.decode("utf-8", "replace")


def _is_7z(tool: list[str]) -> bool:
    return Path(tool[0]).name.lower().startswith("7z")


def _rar_list(path: Path) -> list["Member"]:
    tool = rar_tool()
    if not tool:
        raise _rar_error()
    out: list[Member] = []
    if _is_7z(tool):
        cur: dict = {}
        for line in _run_quiet(tool + ["l", "-slt", "-ba", "-sccUTF-8", "-p-", str(path)]).splitlines() + [""]:
            line = line.strip()
            if not line:
                if cur.get("Path"):
                    out.append(Member(cur["Path"].replace("\\", "/"), int(cur.get("Size") or 0),
                                      "D" in (cur.get("Attributes") or "")[:1] or cur.get("Folder") == "+"))
                cur = {}
                continue
            k, _, v = line.partition(" = ")
            cur[k] = v
        return out
    for line in _run_quiet(tool + ["-tf", str(path)]).splitlines():
        name = line.strip().replace("\\", "/")
        if name:
            out.append(Member(name.rstrip("/"), 0, name.endswith("/")))
    return out


def _rar_extract(path: Path, dest: Path, names: list[str] | None) -> None:
    tool = rar_tool()
    if not tool:
        raise _rar_error()
    # always the whole archive (a list of names can pass Windows' command-line
    # limit); what isn't wanted is deleted right after
    if _is_7z(tool):
        _run_quiet(tool + ["x", "-y", "-p-", "-sccUTF-8", f"-o{dest}", str(path)])
    else:
        _run_quiet(tool + ["-xf", str(path), "-C", str(dest)])
    if names is not None:
        want = {n.replace("\\", "/").strip("/").lower() for n in names}
        for p in sorted(dest.rglob("*"), reverse=True):
            rel = p.relative_to(dest).as_posix().lower()
            if p.is_file() and rel not in want:
                p.unlink()
            elif p.is_dir() and not any(p.iterdir()):
                p.rmdir()


def _rar_error() -> IntakeError:
    return IntakeError("I can't open .rar files. Extract it with 7-Zip or WinRAR first and drop "
                       "the folder, or repack it as .zip or .7z.",
                       "No puedo abrir archivos .rar. Extráelo antes con 7-Zip o WinRAR y suelta "
                       "la carpeta, o vuelve a comprimirlo en .zip o .7z.")


def list_names(path: Path, limit: int = 200_000) -> list[Member]:
    """Members of a .zip/.7z, or files of a folder, without extracting anything."""
    path = Path(path)
    out: list[Member] = []
    if path.is_dir():
        for dirpath, dirnames, filenames in os.walk(path):
            dirnames[:] = [d for d in dirnames if not d.startswith(".skynx")]
            rel = Path(dirpath).relative_to(path)
            for d in dirnames:
                out.append(Member((rel / d).as_posix(), 0, True))
            for f in filenames:
                p = Path(dirpath) / f
                try:
                    size = p.stat().st_size
                except OSError:
                    size = 0
                out.append(Member((rel / f).as_posix(), size, False))
            if len(out) >= limit:
                break
        return out
    kind = archive_type(path)
    if kind == "zip":
        with zipfile.ZipFile(path) as z:
            for m in z.infolist():
                link = stat.S_ISLNK(m.external_attr >> 16)
                out.append(Member(m.filename.rstrip("/"), m.file_size, m.is_dir(), link))
        return out
    if kind == "7z":
        import py7zr  # type: ignore
        with py7zr.SevenZipFile(path) as z:
            for m in z.list():
                out.append(Member(m.filename.replace("\\", "/"), int(m.uncompressed or 0),
                                  bool(m.is_directory), bool(getattr(m, "is_symlink", False))))
        return out
    if kind == "rar":
        return _rar_list(path)
    raise IntakeError(f"{path.name} isn't a folder, .zip or .7z",
                      f"{path.name} no es una carpeta, ni un .zip o .7z")


def _inside(base: Path, name: str) -> Path:
    """Where `name` lands under base; raises when it would escape (zip-slip)."""
    clean = name.replace("\\", "/")
    target = (base / clean).resolve()
    root = base.resolve()
    if PurePosixPath(clean).is_absolute() or re.match(r"^[A-Za-z]:", clean) or \
            os.path.commonpath([str(root), str(target)]) != str(root):
        raise IntakeError(f"Unsafe path inside the archive: {name}",
                          f"Ruta insegura dentro del comprimido: {name}")
    return target


class _Tick:
    """py7zr progress callback that forwards file names to tick(text, i, n)."""

    def __init__(self, tick, n):
        self.tick, self.n, self.i = tick, n, 0

    def make(self):
        import py7zr.callbacks as cb  # type: ignore
        outer = self

        class CB(cb.ExtractCallback):
            def report_start_preparation(self): pass
            def report_start(self, path, nbytes):
                outer.i += 1
                outer.tick(Path(str(path)).name, outer.i, outer.n)
            def report_update(self, nbytes): pass
            def report_end(self, path, nbytes): pass
            def report_warning(self, message): pass
            def report_postprocess(self): pass
        return CB()


LOOSE_EXT = (".esp", ".esm", ".esl", ".bsa")


def loose_bundle(path: Path) -> list[Path]:
    """A plugin or BSA picked on its own: that file plus the files next to it
    that belong to it (same name start: "Mod.esp", "Mod.bsa", "Mod - Textures.bsa").
    Empty when `path` isn't a loose plugin/BSA file."""
    path = Path(path)
    if not path.is_file() or path.suffix.lower() not in LOOSE_EXT:
        return []
    stem = path.stem.lower()
    out = [path]
    for p in sorted(path.parent.iterdir()):
        if p != path and p.is_file() and p.suffix.lower() in LOOSE_EXT:
            low = p.stem.lower()
            if low == stem or low.startswith(stem + " - "):
                out.append(p)
    return out


def bundle_to_folder(path: Path, dest: Path) -> Path:
    """Copy a loose plugin/BSA and its companions into dest (created)."""
    import shutil
    files = loose_bundle(path)
    if not files:
        raise IntakeError(f"{Path(path).name} isn't a plugin or BSA file.",
                          f"{Path(path).name} no es un plugin ni un BSA.")
    dest.mkdir(parents=True, exist_ok=True)
    for f in files:
        try:
            os.link(f, dest / f.name)      # same drive: instant, no extra space
        except OSError:
            shutil.copy2(f, dest / f.name)
    return dest


def plugin_for_bsa(path: Path) -> Path | None:
    """The plugin next to a loose BSA that loads it ("Mod.bsa", "Mod - Textures.bsa"
    → "Mod.esp/.esm/.esl"), or None."""
    path = Path(path)
    if path.suffix.lower() != ".bsa" or not path.parent.is_dir():
        return None
    low = path.stem.lower()
    for p in sorted(path.parent.iterdir()):
        if p.is_file() and p.suffix.lower() in (".esp", ".esm", ".esl"):
            st = p.stem.lower()
            if low == st or low.startswith(st + " - "):
                return p
    return None


def group_loose(paths: list) -> list[tuple[str, list[str]]]:
    """Loose plugins and BSAs picked together become one entry per mod:
    (main path, [files of the mod]). A BSA whose plugin sits next to it joins
    that plugin even if only the BSA was picked."""
    out: dict[str, list[str]] = {}
    order: list[str] = []
    for raw in paths:
        p = Path(raw)
        main = p
        if p.is_file() and p.suffix.lower() == ".bsa":
            main = plugin_for_bsa(p) or p
        files = [str(f) for f in loose_bundle(main)] if main.is_file() else []
        key = str(main)
        if key not in out:
            out[key] = files or [str(p)]
            order.append(key)
        elif str(p) not in out[key]:
            out[key].append(str(p))
    return [(k, out[k]) for k in order]


_WIN_BAD = set('<>:"|?*') | {chr(i) for i in range(32)}
_WIN_RESERVED = {"con", "prn", "aux", "nul", *(f"com{i}" for i in range(1, 10)), *(f"lpt{i}" for i in range(1, 10))}


def win_safe(member: str) -> str:
    """A member name as it can exist on Windows: characters Windows refuses
    (Praedy's Sky ships a folder named "Praedy's Sky AIO - SE : AE NX") become
    '_', trailing dots and spaces go, reserved names get a '_'. Names that
    are already fine come back unchanged."""
    parts = []
    for part in member.replace("\\", "/").split("/"):
        if not part:
            continue
        q = "".join("_" if c in _WIN_BAD else c for c in part).rstrip(" .") or "_"
        stem, dot, rest = q.partition(".")
        if stem.lower() in _WIN_RESERVED:
            q = stem + "_" + dot + rest
        parts.append(q)
    return "/".join(parts)


class _SafeFiles:
    """py7zr writer factory: each member goes to its Windows-safe path."""

    def __init__(self, dest: Path):
        self.dest, self.open = Path(dest), []

    def create(self, filename: str):
        from py7zr.io import Py7zIO  # type: ignore

        out = extracted_path(self.dest, filename)
        out.parent.mkdir(parents=True, exist_ok=True)
        fh = open(out, "wb+")
        self.open.append(fh)

        class _W(Py7zIO):
            def write(self, s):
                return fh.write(s)

            def read(self, size=None):
                return fh.read(size if size is not None else -1)

            def seek(self, offset, whence=0):
                return fh.seek(offset, whence)

            def flush(self):
                return fh.flush()

            def size(self):
                return os.fstat(fh.fileno()).st_size
        return _W()

    def close(self):
        for fh in self.open:
            fh.close()


def extracted_path(dest: Path, member: str) -> Path:
    """Where safe_extract put an archive member."""
    return Path(dest) / win_safe(member)


def safe_extract(src: Path, dest: Path, progress=None, targets: list[str] | None = None) -> Path:
    """Extract a .zip/.7z into dest (created), refusing paths that escape it and
    symbolic links. `targets` limits extraction to those member names."""
    src, dest = Path(src), Path(dest)
    tick = progress or (lambda *a, **k: None)
    kind = archive_type(src)
    if kind == "rar" and not rar_tool():
        raise _rar_error()
    if kind not in ("zip", "7z", "rar"):
        raise IntakeError("I can open folders, .zip and .7z.",
                          "Puedo abrir carpetas, .zip y .7z.")
    dest.mkdir(parents=True, exist_ok=True)
    from .variants import is_junk
    members = list_names(src)
    want = set(targets) if targets is not None else None
    # Mac zip junk (__MACOSX/, ._Mod.esp) is never part of the mod
    chosen = [m for m in members if (want is None or m.name in want) and not is_junk(m.name)]
    for m in chosen:
        raw = m.name.replace("\\", "/")
        if ".." in raw.split("/") or raw.startswith("/") or re.match(r"^[A-Za-z]:", raw):
            _inside(dest, m.name)                # raises: escapes the folder
        _inside(dest, win_safe(m.name))
        if m.is_link:
            raise IntakeError(f"The archive has a link instead of a file: {m.name}. I won't extract it.",
                              f"El comprimido trae un enlace en vez de un archivo: {m.name}. No lo extraigo.")
    need = sum(m.size for m in chosen if not m.is_dir)
    try:
        free = shutil.disk_usage(dest).free
    except OSError:
        free = None
    if free is not None and need > free:
        gb = lambda n: f"{n / 2**30:.1f} GB"  # noqa: E731
        raise IntakeError(f"Not enough free space: it needs {gb(need)} and there are {gb(free)}.",
                          f"No hay espacio suficiente: necesita {gb(need)} y hay {gb(free)} libres.")
    files = [m for m in chosen if not m.is_dir]
    if kind == "rar":
        whole = want is None and len(chosen) == len(members)
        _rar_extract(src, dest, None if whole else [m.name for m in files])
    elif kind == "zip":
        with zipfile.ZipFile(src) as z:
            for i, m in enumerate(files):
                if i % 20 == 0:
                    tick(Path(m.name).name, i, len(files))
                out = extracted_path(dest, m.name)
                out.parent.mkdir(parents=True, exist_ok=True)
                with z.open(m.name) as fin, open(out, "wb") as fout:
                    shutil.copyfileobj(fin, fout, 1 << 20)
            for m in chosen:
                if m.is_dir:
                    extracted_path(dest, m.name).mkdir(parents=True, exist_ok=True)
    else:
        import py7zr  # type: ignore
        # names Windows refuses (':' and the like) are read one by one and
        # written under their safe name; the rest extract as usual
        odd = any(win_safe(m.name) != m.name.replace("\\", "/").strip("/") for m in files)
        with py7zr.SevenZipFile(src) as z:
            cb = _Tick(tick, len(files)).make()
            if odd:
                # names Windows refuses (':' and the like): py7zr writes each
                # file through a factory that opens it under its safe name
                fac = _SafeFiles(dest)
                try:
                    z.extract(targets=[m.name for m in files], callback=cb, factory=fac)
                finally:
                    fac.close()
            elif want is None and len(chosen) == len(members):
                z.extractall(dest, callback=cb)
            elif files:
                z.extract(dest, targets=[m.name for m in files], callback=cb)
        for m in chosen:
            if m.is_dir:
                extracted_path(dest, m.name).mkdir(parents=True, exist_ok=True)
    # a link created anyway (old py7zr) would point outside: drop it
    for p in dest.rglob("*"):
        if p.is_symlink():
            p.unlink()
    return dest


# ---------------------------------------------------------------- detection
@dataclass
class Detected:
    path: str
    kind: str                       # one of KINDS
    action: str | None              # "library", "fomod", "add", "convert" or None
    summary: tuple[str, str]        # (en, es) one line
    evidence: dict = field(default_factory=dict)
    notes: list[tuple[str, str]] = field(default_factory=list)
    supported: bool = True

    def to_dict(self, lang: str = "en") -> dict:
        pick = (lambda t: t[1] if lang == "es" else t[0])
        return {"path": self.path, "kind": self.kind, "action": self.action,
                "summary": pick(self.summary), "evidence": self.evidence,
                "notes": [pick(n) for n in self.notes], "supported": self.supported}


def _parts(name: str) -> list[str]:
    return [p for p in name.lower().split("/") if p]


def _title_layout(members: list[Member]) -> dict | None:
    base, aoc = K.TITLE_BASE.lower(), K.TITLE_AOC.lower()
    found: dict = {}
    for m in members:
        ps = _parts(m.name)
        for i, p in enumerate(ps):
            if p in (base, aoc) and (m.is_dir or i < len(ps) - 1):
                key = "base" if p == base else "aoc"
                prefix = "/".join(m.name.replace("\\", "/").split("/")[:i])
                cur = found.get(key)
                if cur is None or prefix.count("/") < cur.count("/") or (cur and not prefix):
                    found[key] = prefix
                break
        if "atmosphere" in ps:
            i = ps.index("atmosphere")
            if i + 2 < len(ps) and ps[i + 1] == "contents" and re.fullmatch(r"[0-9a-f]{16}", ps[i + 2]):
                found.setdefault("atmosphere", "/".join(m.name.split("/")[:i + 1]))
    if not found:
        return None
    if "base" not in found and "aoc" not in found:
        # an atmosphere/contents tree for other titles only (cheats, other games)
        return None
    return found


def _fomod_root(members: list[Member]) -> str | None:
    for m in members:
        ps = _parts(m.name)
        if len(ps) in (2, 3) and ps[-1] == "moduleconfig.xml" and ps[-2] == "fomod":
            return "/".join(m.name.split("/")[:len(ps) - 2])
    return None


def _fomod_script(members: list[Member]) -> bool:
    return any(len(_parts(m.name)) in (2, 3) and _parts(m.name)[-1] == "script.cs"
               and _parts(m.name)[-2] == "fomod" for m in members)


class _Reader:
    """Reads the first bytes of members of a folder or an archive."""

    def __init__(self, path: Path, members: list[Member]):
        self.path = Path(path)
        self.members = {m.name: m for m in members}
        self.kind = None if self.path.is_dir() else archive_type(self.path)
        self.tmp: Path | None = None
        self._zip = zipfile.ZipFile(self.path) if self.kind == "zip" else None

    def close(self):
        if self._zip:
            self._zip.close()
        if self.tmp:
            shutil.rmtree(self.tmp, ignore_errors=True)

    def heads(self, names: list[str], n: int) -> dict[str, bytes]:
        out = {}
        if not names:
            return out
        if self.kind is None:
            for name in names:
                try:
                    with (self.path / name).open("rb") as f:
                        out[name] = f.read(n)
                except OSError:
                    pass
        elif self.kind == "zip":
            for name in names:
                try:
                    with self._zip.open(name) as f:
                        out[name] = f.read(n)
                except (KeyError, OSError, zipfile.BadZipFile):
                    pass
        else:
            for name, p in self.files(names).items():
                with p.open("rb") as f:
                    out[name] = f.read(n)
        return out

    def files(self, names: list[str]) -> dict[str, Path]:
        """Real paths for members (extracting them from an archive if needed)."""
        if self.kind is None:
            return {n: self.path / n for n in names}
        if self.tmp is None:
            self.tmp = Path(tempfile.mkdtemp(prefix="skynx-peek-"))
        safe_extract(self.path, self.tmp, targets=names)
        return {n: extracted_path(self.tmp, n) for n in names if extracted_path(self.tmp, n).is_file()}


def _sample_bsa(path: Path, ev: dict) -> None:
    arc = read_bsa(path)
    tex = [e for e in arc.entries if e.name.lower().endswith(".dds")]
    fuz = [e for e in arc.entries if e.name.lower().endswith(".fuz")]
    hk = [e for e in arc.entries if e.name.lower().endswith(".hkx")]
    pcsnd = sum(e.name.lower().endswith((".xwm", ".wav")) for e in arc.entries)
    nxsnd = sum(e.name.lower().endswith(".mcadpcm") for e in arc.entries)
    ev["sounds"]["pc"] += pcsnd
    ev["sounds"]["switch"] += nxsnd
    ev["textures"]["total"] += len(tex)
    with path.open("rb") as f:
        for e in tex[:TEX_SAMPLE]:
            _count_tex(arc.read_head(e, 256, f), ev)
        for e in fuz[:SND_SAMPLE]:
            _count_fuz(arc.read_head(e, 64 * 1024, f), ev)
        for e in hk[:HKX_SAMPLE]:
            _count_hkx(arc.read_head(e, 32, f), ev)


def _count_tex(head: bytes, ev: dict) -> None:
    info = inspect_tex(head)
    k = "unknown" if info is None else ("switch" if info.container == "NVN" else "pc")
    ev["textures"][k] += 1
    ev["textures"]["sampled"] += 1


def _count_fuz(head: bytes, ev: dict) -> None:
    ev["sounds"]["switch" if is_switch_fuz(head) else "pc"] += 1


def _count_hkx(head: bytes, ev: dict) -> None:
    kind = HKX.classify(head)
    if kind == HKX.NX_64:
        ev["animations"]["switch"] += 1
    elif kind in (HKX.PC_64, HKX.PC_32, HKX.XML):
        ev["animations"]["pc"] += 1


def _mb(n: int) -> str:
    return f"{n / 2**20:.0f} MB" if n >= 2**20 else f"{n / 1024:.0f} KB"


def detect(path: Path, progress=None, deep: bool = True) -> Detected:
    """deep=False never extracts anything from an archive (BSA headers inside a
    .zip/.7z are skipped); folders are always read directly."""
    path = Path(path)
    tick = progress or (lambda *a, **k: None)
    tick(path.name)
    if not path.exists():
        raise IntakeError(f"{path} doesn't exist", f"{path} no existe")
    if not path.is_dir() and archive_type(path) == "rar" and not rar_tool():
        return Detected(str(path), "unknown", None,
                        ("A .rar file: I can't open those. Extract it first, or repack it as .zip or .7z.",
                         "Un .rar: no puedo abrirlos. Extráelo antes o vuelve a comprimirlo en .zip o .7z."),
                        {"format": "rar"}, supported=False)
    if not path.is_dir() and archive_type(path) is None:
        ext = path.suffix.lower()
        if ext in PLUGIN_EXT or ext == ".bsa":
            # a lone plugin or BSA dropped on its own: look at its folder's copy of itself
            members = [Member(path.name, path.stat().st_size, False)]
            return _classify(path.parent, members, tick, single=path, deep=deep)
        return Detected(str(path), "unknown", None,
                        (f"{path.name} isn't a mod, a modpack or an archive I can open.",
                         f"{path.name} no es un mod, un modpack ni un comprimido que pueda abrir."),
                        {"format": ext.lstrip(".")}, supported=False)
    try:
        members = list_names(path)
    except (zipfile.BadZipFile, OSError, EOFError) as e:
        raise IntakeError(f"I couldn't read {path.name}; it may be damaged or incomplete ({e}).",
                          f"No pude leer {path.name}; puede estar dañado o incompleto ({e}).") from e
    except Exception as e:  # noqa: BLE001  (py7zr raises its own types)
        if isinstance(e, SkynxError):
            raise
        raise IntakeError(f"I couldn't read {path.name}; it may be damaged or incomplete ({e}).",
                          f"No pude leer {path.name}; puede estar dañado o incompleto ({e}).") from e
    return _classify(path, members, tick, deep=deep)


def _classify(path: Path, members: list[Member], tick, single: Path | None = None,
              deep: bool = True) -> Detected:
    from . import variants as VA
    members = [m for m in members if not VA.is_junk(m.name)]
    vres = VA.choose([m.name for m in members if not m.is_dir])
    if vres["skip"]:
        members = [m for m in members if not VA.skipped(m.name, vres["skip"])]
    files = [m for m in members if not m.is_dir]
    ev: dict = {"format": "folder" if path.is_dir() and single is None else
                (archive_type(path) or "file"),
                "files": len(files), "bytes": sum(m.size for m in files),
                "plugins": [], "bsas": [], "loose_dirs": [], "archives": [],
                "textures": {"pc": 0, "switch": 0, "unknown": 0, "sampled": 0, "total": 0},
                "sounds": {"pc": 0, "switch": 0}, "animations": {"pc": 0, "switch": 0}}
    notes: list[tuple[str, str]] = []
    src = str(single or path)
    if vres["groups"]:
        opts = "; ".join(" / ".join(PurePosixPath(o).name for o in g["options"]) for g in vres["groups"])
        notes.append((f"It has several versions ({opts}). When it goes into a pack, the one for the pack's "
                      "edition (AE or SE) is used.",
                      f"Trae varias versiones ({opts}). Al meterlo a un pack se usa la de la edición del "
                      "pack (AE o SE)."))

    # ---- a whole modpack
    layout = _title_layout(members)
    if layout:
        data_files = [m for m in files if "romfs/data/" in m.name.lower().replace("\\", "/")]
        ev["layout"] = layout
        ev["plugins"] = sorted(Path(m.name).name for m in data_files
                               if Path(m.name).suffix.lower() in PLUGIN_EXT)
        ev["bsas"] = sorted(Path(m.name).name for m in data_files if m.name.lower().endswith(".bsa"))
        ev["archives"] = sorted(Path(m.name).name for m in data_files
                                if Path(m.name).suffix.lower() in ARCHIVE_EXT | {".rar"})
        has_aoc = "aoc" in layout
        ev["edition"] = "AE" if has_aoc else "SE?"
        n_p, n_b = len(ev["plugins"]), len(ev["bsas"])
        if ev["archives"]:
            notes.append((f"{len(ev['archives'])} mods are still packed (.7z/.zip) inside Data; the "
                          "Switch can't read them there.",
                          f"{len(ev['archives'])} mods siguen comprimidos (.7z/.zip) dentro de Data; "
                          "la Switch no los lee ahí."))
        if "base" not in layout:
            notes.append((f"It only has {K.TITLE_AOC} (the load list); the Data folder is missing.",
                          f"Solo trae {K.TITLE_AOC} (la lista de carga); falta la carpeta Data."))
        return Detected(src, "modpack", "library",
                        (f"A whole modpack ({n_p} plugins, {n_b} BSAs, {_mb(ev['bytes'])}). Put it in "
                         "the Library to play it or to take mods from it.",
                         f"Un modpack completo ({n_p} plugins, {n_b} BSA, {_mb(ev['bytes'])}). "
                         "Ponlo en la Biblioteca para jugarlo o sacarle mods."),
                        ev, notes)

    # ---- FOMOD installer
    root = _fomod_root(members)
    if root is not None:
        ev["fomod_root"] = root
        return Detected(src, "fomod", "fomod",
                        ("A mod with a FOMOD installer. The assistant walks you through its options, "
                         "then converts it.",
                         "Un mod con instalador FOMOD. El asistente te lleva por sus opciones y luego "
                         "lo convierte."), ev, notes)
    if _fomod_script(members):
        ev["fomod_root"] = None
        notes.append(("It uses an old script installer (script.cs) that I can't run; pick the option "
                      "folder by hand.",
                      "Usa un instalador antiguo con script (script.cs) que no puedo ejecutar; elige "
                      "a mano la carpeta de la opción."))
        return Detected(src, "fomod", "fomod",
                        ("A mod with an old script installer. Extract it and choose the folder of the "
                         "option you want.",
                         "Un mod con instalador antiguo por script. Extráelo y elige la carpeta de la "
                         "opción que quieres."), ev, notes)

    # ---- plain mod: inventory
    plugins, bsas, tex, fuz, hk = [], [], [], [], []
    loose = set()
    for m in files:
        ps = _parts(m.name)
        ext = Path(ps[-1]).suffix
        if ext in PLUGIN_EXT:
            plugins.append(m)
        elif ext == ".bsa":
            bsas.append(m)
        elif ext in ARCHIVE_EXT | {".rar"}:
            ev["archives"].append(Path(m.name).name)
        asset_i = next((i for i, p in enumerate(ps[:-1]) if p in ASSET_DIRS and i <= 3), None)
        if asset_i is not None and ps[asset_i:] == ["interface", "fontconfig.txt"]:
            ev["fontconfig"] = True       # a font mod's config: it stays loose (fonts.py)
            asset_i = None
        if asset_i is not None:
            loose.add(ps[asset_i])
            if ext == ".dds":
                tex.append(m.name)
            elif ext == ".fuz":
                fuz.append(m.name)
            elif ext == ".hkx":
                hk.append(m.name)
            elif ext in (".xwm", ".wav"):
                ev["sounds"]["pc"] += 1
            elif ext == ".mcadpcm":
                ev["sounds"]["switch"] += 1
        if ext == ".dll":
            ev.setdefault("dlls", []).append(Path(m.name).name)
    ev["plugins"] = sorted(Path(m.name).name for m in plugins)
    ev["bsas"] = sorted(Path(m.name).name for m in bsas)
    ev["loose_dirs"] = sorted(loose)
    ev["textures"]["total"] += len(tex)
    reader = _Reader(path, members)
    try:
        tick(path.name)
        n_tex, n_snd = (TEX_SAMPLE, SND_SAMPLE) if deep or reader.kind != "7z" else (0, 0)
        for name, head in reader.heads(sorted(tex)[:n_tex], 256).items():
            _count_tex(head, ev)
        for name, head in reader.heads(sorted(fuz)[:n_snd], 64 * 1024).items():
            _count_fuz(head, ev)
        for name, head in reader.heads(sorted(hk)[:n_snd and HKX_SAMPLE], 32).items():
            _count_hkx(head, ev)
        # BSAs: smallest first, within a size budget when they must be extracted
        pick, budget = [], 0
        for m in sorted(bsas, key=lambda m: m.size):
            if len(pick) >= BSA_SAMPLE or (reader.kind and not deep):
                break
            if reader.kind and pick and budget + m.size > BSA_EXTRACT_BUDGET:
                break
            pick.append(m.name)
            budget += m.size
        if len(pick) < len(bsas):
            ev["bsas_sampled"] = len(pick)
        for name, p in reader.files(pick).items() if pick else []:
            tick(Path(name).name)
            try:
                _sample_bsa(p, ev)
            except Exception:  # noqa: BLE001
                notes.append((f"I couldn't read {Path(name).name}; it may not be a Skyrim SE BSA.",
                              f"No pude leer {Path(name).name}; puede que no sea un BSA de Skyrim SE."))
    finally:
        reader.close()

    t, s, a = ev["textures"], ev["sounds"], ev["animations"]
    sw = t["switch"] + s["switch"] + a["switch"]
    pc = t["pc"] + s["pc"] + a["pc"]
    ev["switch_evidence"], ev["pc_evidence"] = sw, pc
    if ev["archives"]:
        notes.append(("It has other archives inside (" + ", ".join(ev["archives"][:4]) +
                      "). Add each one on its own.",
                      "Trae otros comprimidos adentro (" + ", ".join(ev["archives"][:4]) +
                      "). Agrega cada uno por separado."))
    if ev.get("dlls"):
        notes.append(("It has SKSE plugins (.dll). They don't run on Switch; the parts that need "
                      "them won't work.",
                      "Trae plugins de SKSE (.dll). No funcionan en Switch; lo que dependa de ellos "
                      "no va a funcionar."))
    if not plugins and not bsas and not loose:
        if ev["archives"]:
            return Detected(src, "unknown", None,
                            ("A bundle of other archives. Open each one on its own.",
                             "Un paquete de otros comprimidos. Abre cada uno por separado."), ev, notes)
        return Detected(src, "unknown", None,
                        ("I didn't find plugins, BSAs or game folders (meshes, textures...) in it.",
                         "No encontré plugins, BSA ni carpetas del juego (meshes, textures...)."),
                        ev, notes)
    what = _what(ev)
    if sw and pc:
        kind = "mixed"
        summary = (f"A mod with both Switch and PC files ({what}). Convert it: what's already for "
                   "Switch is kept.",
                   f"Un mod con archivos de Switch y de PC ({_what(ev, 'es')}). Conviértelo: lo que "
                   "ya es de Switch se conserva.")
    elif sw:
        kind = "switch-mod"
        summary = (f"Already converted for Switch ({what}). It can be added as it is.",
                   f"Ya convertido para Switch ({_what(ev, 'es')}). Se puede agregar tal cual.")
    elif pc or loose:
        kind = "pc-mod"
        summary = (f"A PC mod ({what}). It needs converting for Switch.",
                   f"Un mod de PC ({_what(ev, 'es')}). Hay que convertirlo para Switch.")
    else:
        kind = "switch-mod"
        ev["platform"] = "neutral"
        summary = (f"Nothing in it is platform specific ({what}). It can be added as it is.",
                   f"No trae nada específico de una plataforma ({_what(ev, 'es')}). Se puede "
                   "agregar tal cual.")
    action = ACTIONS[kind]
    if ev.get("fontconfig"):
        notes.append(("A font mod: its FontConfig.txt stays loose in Data\\Interface, the way fonts load.",
                      "Mod de fuente: su FontConfig.txt queda suelto en Data\\Interface, que es como cargan las fuentes."))
    if loose:
        action = "convert"
        if kind == "switch-mod":
            notes.append(("Its files are loose (" + ", ".join(sorted(loose)) + "); converting packs "
                          "them into BSAs and keeps what's already for Switch.",
                          "Sus archivos están sueltos (" + ", ".join(sorted(loose)) + "); convertir "
                          "los empaca en BSA y conserva lo que ya es de Switch."))
    return Detected(src, kind, action, summary, ev, notes)


def _what(ev: dict, lang: str = "en") -> str:
    es = lang == "es"
    bits = []
    if ev["plugins"]:
        n = len(ev["plugins"])
        bits.append(f"{n} plugin" + ("s" if n != 1 else ""))
    if ev["bsas"]:
        n = len(ev["bsas"])
        bits.append(f"{n} BSA" + ("" if es or n == 1 else "s"))
    t = ev["textures"]
    if t["sampled"]:
        if t["switch"] and not t["pc"]:
            bits.append("texturas NVN" if es else "NVN textures")
        elif t["pc"] and not t["switch"]:
            bits.append("texturas DDS de PC" if es else "PC DDS textures")
        else:
            bits.append("texturas mezcladas" if es else "mixed textures")
    s = ev["sounds"]
    if s["switch"] or s["pc"]:
        if s["switch"] and not s["pc"]:
            bits.append("voces Opus de Switch" if es else "Switch Opus voices")
        elif s["pc"] and not s["switch"]:
            bits.append("sonido de PC" if es else "PC audio")
        else:
            bits.append("sonido mezclado" if es else "mixed audio")
    a = ev["animations"]
    if a["switch"] or a["pc"]:
        if a["switch"] and not a["pc"]:
            bits.append("animaciones de Switch" if es else "Switch animations")
        elif a["pc"] and not a["switch"]:
            bits.append("animaciones de PC" if es else "PC animations")
        else:
            bits.append("animaciones mezcladas" if es else "mixed animations")
    if ev["loose_dirs"] and not ev["bsas"]:
        bits.append("archivos sueltos" if es else "loose files")
    return ", ".join(bits) or ("sin contenido reconocible" if es else "nothing recognisable")
