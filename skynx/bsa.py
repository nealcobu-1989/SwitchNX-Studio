"""Pure-Python BSA reader and writer (versions 103, 104, 105).

Reader: directory (folders, names, hashes, sizes, compression) plus file
extraction. Writer: rebuilds an archive from the stored blobs of an existing
one, so files can be renamed or moved between folders without recompressing
anything (the "Auri" fix). The writer never modifies the source archive.
"""
from __future__ import annotations

import os
import struct
import zlib
from dataclasses import dataclass, field
from pathlib import Path

ARCH_DIR_NAMES = 0x1
ARCH_FILE_NAMES = 0x2
ARCH_COMPRESSED = 0x4
ARCH_EMBED_NAMES = 0x100

FILEFLAG_NAMES = {0x1: "meshes", 0x2: "textures", 0x4: "menus", 0x8: "sounds",
                  0x10: "voices", 0x20: "shaders", 0x40: "trees", 0x80: "fonts",
                  0x100: "misc"}

SIZE_COMPRESS_TOGGLE = 0x40000000
MAX_BSA_BYTES = 0x7FFFFFFF  # offsets are signed 32-bit in practice


def tes_hash(name: str, is_folder: bool = False) -> int:
    """Bethesda's 64-bit hash for BSA folder and file names."""
    name = name.lower().replace("/", "\\")
    if is_folder:
        root, ext = name, ""
    else:
        dot = name.rfind(".")
        root, ext = (name[:dot], name[dot:]) if dot > 0 else (name, "")
    b = root.encode("cp1252", errors="replace")
    h1 = 0
    if b:
        h1 = (b[-1] | ((b[-2] if len(b) > 2 else 0) << 8) | (len(b) << 16) | (b[0] << 24))
    if ext == ".kf":
        h1 |= 0x80
    elif ext == ".nif":
        h1 |= 0x8000
    elif ext == ".dds":
        h1 |= 0x8080
    elif ext == ".wav":
        h1 |= 0x80000000
    h1 &= 0xFFFFFFFF
    h2 = 0
    for c in b[1:-2]:
        h2 = (h2 * 0x1003F + c) & 0xFFFFFFFF
    h3 = 0
    for c in ext.encode("cp1252", errors="replace"):
        h3 = (h3 * 0x1003F + c) & 0xFFFFFFFF
    return (((h2 + h3) & 0xFFFFFFFF) << 32) | h1


@dataclass
class BsaEntry:
    folder: str
    name: str
    size: int          # stored size in the archive (without the toggle bit)
    offset: int
    compressed: bool
    hash: int = 0
    folder_hash: int = 0

    @property
    def path(self) -> str:
        return f"{self.folder}\\{self.name}" if self.folder else self.name


@dataclass
class BsaArchive:
    path: Path
    version: int
    archive_flags: int
    file_flags: int
    entries: list[BsaEntry] = field(default_factory=list)

    @property
    def compressed_default(self) -> bool:
        return bool(self.archive_flags & ARCH_COMPRESSED)

    @property
    def embed_names(self) -> bool:
        return bool(self.archive_flags & ARCH_EMBED_NAMES) and self.version >= 104

    @property
    def content_types(self) -> list[str]:
        return [v for k, v in FILEFLAG_NAMES.items() if self.file_flags & k]

    def top_folders(self) -> dict[str, int]:
        out: dict[str, int] = {}
        for e in self.entries:
            top = e.folder.split("\\", 1)[0]
            out[top] = out.get(top, 0) + 1
        return out

    def folders(self) -> dict[str, int]:
        out: dict[str, int] = {}
        for e in self.entries:
            out[e.folder] = out.get(e.folder, 0) + 1
        return out

    # -- data access -------------------------------------------------------
    def read_blob(self, entry: BsaEntry, f=None) -> bytes:
        """Stored bytes of an entry, without the embedded name prefix."""
        own = f is None
        f = f or self.path.open("rb")
        try:
            f.seek(entry.offset)
            size = entry.size
            if self.embed_names:
                n = f.read(1)[0]
                f.read(n)
                size -= n + 1
            return f.read(size)
        finally:
            if own:
                f.close()

    def _decode(self, blob: bytes, compressed: bool) -> bytes:
        if not compressed:
            return blob
        orig = struct.unpack_from("<I", blob)[0]
        data = blob[4:]
        if self.version == 105:
            import lz4.frame  # type: ignore
            out = lz4.frame.decompress(data)
        else:
            out = zlib.decompress(data)
        if len(out) != orig:
            raise ValueError("decompressed size mismatch")
        return out

    def read_file(self, entry: BsaEntry, f=None) -> bytes:
        return self._decode(self.read_blob(entry, f), entry.compressed)

    def read_head(self, entry: BsaEntry, n: int = 256, f=None) -> bytes:
        """First n bytes of a file; cheap when the entry is stored uncompressed."""
        if entry.compressed:
            return self.read_file(entry, f)[:n]
        own = f is None
        f = f or self.path.open("rb")
        try:
            f.seek(entry.offset)
            if self.embed_names:
                k = f.read(1)[0]
                f.read(k)
            return f.read(min(n, entry.size))
        finally:
            if own:
                f.close()


def _bzstring(f) -> str:
    n = f.read(1)[0]
    return f.read(n).rstrip(b"\x00").decode("cp1252", errors="replace")


def read_bsa(path: Path) -> BsaArchive:
    path = Path(path)
    with path.open("rb") as f:
        hdr = f.read(36)
        if len(hdr) < 36:
            raise ValueError(f"{path.name}: file too short")
        magic, ver, off, aflags, nfold, nfile, _lfold, lfile, fflags, _pad = struct.unpack(
            "<4sIIIIIIIHH", hdr)
        if magic != b"BSA\x00":
            raise ValueError(f"{path.name}: not a BSA (magic {magic!r})")
        if ver not in (103, 104, 105):
            raise ValueError(f"{path.name}: unsupported BSA version ({ver})")
        arc = BsaArchive(path, ver, aflags, fflags)
        f.seek(off)
        folders = []
        for _ in range(nfold):
            if ver == 105:
                h, cnt, _u, _foff = struct.unpack("<QIIQ", f.read(24))
            else:
                h, cnt, _foff = struct.unpack("<QII", f.read(16))
            folders.append((h, cnt))
        raw = []
        for fh, cnt in folders:
            fname = _bzstring(f) if aflags & ARCH_DIR_NAMES else ""
            for _ in range(cnt):
                h, size, foff = struct.unpack("<QII", f.read(16))
                raw.append((fname, fh, h, size, foff))
        names: list[str] = []
        if aflags & ARCH_FILE_NAMES:
            blob = f.read(lfile)
            names = [n.decode("cp1252", errors="replace") for n in blob.split(b"\x00")[:nfile]]
        for i, (fold, fh, h, size, foff) in enumerate(raw):
            toggle = bool(size & SIZE_COMPRESS_TOGGLE)
            comp = arc.compressed_default != toggle
            arc.entries.append(BsaEntry(fold, names[i] if i < len(names) else f"#{i}",
                                        size & 0x3FFFFFFF, foff, comp, h, fh))
    return arc


# ---------------------------------------------------------------------------
# Writer
# ---------------------------------------------------------------------------

@dataclass
class _Out:
    folder: str
    name: str
    entry: BsaEntry
    blob_size: int
    compressed: bool


def rebuild_bsa(src: BsaArchive, dest: Path, rename_folder: dict[str, str] | None = None,
                rename_file: dict[str, str] | None = None,
                drop: set[str] | None = None) -> Path:
    """Write a new archive with the same stored data as `src`.

    rename_folder maps old folder paths (lowercase, backslashes) to new ones,
    matching whole path segments as a prefix. rename_file maps full old paths
    to full new paths. drop lists full paths to leave out.
    Writes to a temporary file first, verifies it, then moves it into place.
    """
    rename_folder = {k.lower(): v.lower() for k, v in (rename_folder or {}).items()}
    rename_file = {k.lower(): v.lower() for k, v in (rename_file or {}).items()}
    drop = {d.lower() for d in (drop or set())}
    dest = Path(dest)

    outs: list[_Out] = []
    if True:
        for e in src.entries:
            full = e.path.lower()
            if full in drop:
                continue
            folder, name = e.folder.lower(), e.name.lower()
            if full in rename_file:
                nf = rename_file[full]
                folder, name = (nf.rsplit("\\", 1) if "\\" in nf else ("", nf))
            else:
                for old, new in rename_folder.items():
                    if folder == old or folder.startswith(old + "\\"):
                        folder = new + folder[len(old):]
                        break
            blob_size = e.size
            if src.embed_names:
                blob_size -= 1 + len(e.path.encode("cp1252", errors="replace"))
            if len(name.encode("cp1252", errors="replace")) > 254 or len(folder.encode("cp1252", errors="replace")) > 254:
                raise ValueError(f"Name too long for a BSA: {folder}\\{name}")
            outs.append(_Out(folder, name, e, blob_size, e.compressed))

    seen = set()
    for o in outs:
        key = (o.folder, o.name)
        if key in seen:
            raise ValueError(f"Duplicate path while rebuilding: {o.folder}\\{o.name}")
        seen.add(key)

    by_folder: dict[str, list[_Out]] = {}
    for o in outs:
        by_folder.setdefault(o.folder, []).append(o)
    folder_list = sorted(by_folder, key=lambda d: tes_hash(d, True))
    for d in folder_list:
        by_folder[d].sort(key=lambda o: tes_hash(o.name))

    ver = src.version
    aflags = src.archive_flags | ARCH_DIR_NAMES | ARCH_FILE_NAMES
    embed = bool(aflags & ARCH_EMBED_NAMES) and ver >= 104
    comp_default = bool(aflags & ARCH_COMPRESSED)
    folder_rec = 24 if ver == 105 else 16
    nfile = len(outs)
    total_folder_names = sum(len(d.encode("cp1252")) + 1 for d in folder_list)
    total_file_names = sum(len(o.name.encode("cp1252")) + 1 for o in outs)

    off = 36
    file_block_start = off + folder_rec * len(folder_list)
    file_block_size = sum(1 + len(d.encode("cp1252")) + 1 + 16 * len(by_folder[d])
                          for d in folder_list)
    data_start = file_block_start + file_block_size + total_file_names

    tmp = dest.with_name(dest.name + ".tmp")
    try:
        with src.path.open("rb") as rf:
            _write(tmp, ver, aflags, src.file_flags, folder_list, by_folder, nfile,
                   total_folder_names, total_file_names, file_block_start, data_start, embed,
                   comp_default, lambda o: src.read_blob(o.entry, rf))
        check = read_bsa(tmp)
        if len(check.entries) != nfile:
            raise ValueError("Verification failed: file count mismatch")
        for o, e in zip(sorted(outs, key=lambda o: (o.folder, o.name)),
                        sorted(check.entries, key=lambda e: (e.folder, e.name))):
            if (o.folder, o.name) != (e.folder, e.name) or o.compressed != e.compressed:
                raise ValueError(f"Verification failed at {e.path}")
        os.replace(tmp, dest)
    finally:
        if tmp.exists():
            tmp.unlink()
    return dest


def _write(tmp, ver, aflags, file_flags, folder_list, by_folder, nfile, total_folder_names,
           total_file_names, file_block_start, data_start, embed, comp_default, blob_of):
    with tmp.open("wb") as w:
        w.write(struct.pack("<4sIIIIIIIHH", b"BSA\x00", ver, 36, aflags, len(folder_list),
                            nfile, total_folder_names, total_file_names, file_flags, 0))
        # folder records
        cursor = file_block_start
        for d in folder_list:
            rec_off = cursor + total_file_names
            if ver == 105:
                w.write(struct.pack("<QIIQ", tes_hash(d, True), len(by_folder[d]), 0, rec_off))
            else:
                w.write(struct.pack("<QII", tes_hash(d, True), len(by_folder[d]), rec_off))
            cursor += 1 + len(d.encode("cp1252")) + 1 + 16 * len(by_folder[d])
        # file record blocks
        data_cursor = data_start
        for d in folder_list:
            db = d.encode("cp1252")
            w.write(bytes([len(db) + 1]) + db + b"\x00")
            for o in by_folder[d]:
                stored = o.blob_size
                if embed:
                    full = (f"{d}\\{o.name}" if d else o.name).encode("cp1252")
                    stored += 1 + len(full)
                size = stored | (SIZE_COMPRESS_TOGGLE if o.compressed != comp_default else 0)
                w.write(struct.pack("<QII", tes_hash(o.name), size, data_cursor))
                data_cursor += stored
        if data_cursor > MAX_BSA_BYTES:
            raise ValueError("The rebuilt BSA would exceed 2 GB; it must be split.")
        # file names
        for d in folder_list:
            for o in by_folder[d]:
                w.write(o.name.encode("cp1252") + b"\x00")
        # data
        for d in folder_list:
            for o in by_folder[d]:
                if embed:
                    full = (f"{d}\\{o.name}" if d else o.name).encode("cp1252")
                    w.write(bytes([len(full)]) + full)
                blob = blob_of(o)
                if len(blob) != o.blob_size:
                    raise ValueError(f"Unexpected size at {o.folder}\\{o.name}")
                w.write(blob)


# ---------------------------------------------------------------------------
# New archives from loose files
# ---------------------------------------------------------------------------
FILEFLAG_BY_TOP = {"meshes": 0x1, "textures": 0x2, "interface": 0x4, "sound": 0x8,
                   "music": 0x8, "shadersfx": 0x20, "trees": 0x40, "fonts": 0x80}
# Compress only what the Switch packs we checked store compressed (meshes and
# animations); textures and sounds are stored raw so they stream directly.
COMPRESS_EXT = {".nif", ".hkx", ".tri", ".btr", ".bto"}


def _encode_blob(data: bytes, compress: bool, ver: int) -> bytes:
    if not compress:
        return data
    if ver == 105:
        import lz4.frame  # type: ignore
        packed = lz4.frame.compress(data)
    else:
        packed = zlib.compress(data, 9)
    return struct.pack("<I", len(data)) + packed


def write_bsa(files: list[tuple[str, Path]], dest: Path, ver: int = 105,
              compress: bool = True) -> Path:
    """Write a new archive from (archive path, source file) pairs.

    Archive paths use backslashes and are stored lowercase, like the game's
    own archives. Meshes and animations are LZ4-compressed per file; every
    other file is stored as is. compress=False stores every file as is (an
    uncompressed BSA, one of the options of Koka's NX Toolkit frontend). The result is read back and every file is
    compared with its source before it replaces `dest`.
    """
    dest = Path(dest)
    outs: list[_Out] = []
    srcs: dict[tuple[str, str], Path] = {}
    blobs: dict[tuple[str, str], bytes] = {}
    fflags = 0
    any_comp = False
    for arc_path, src in files:
        p = arc_path.replace("/", "\\").strip("\\").lower()
        folder, name = p.rsplit("\\", 1) if "\\" in p else ("", p)
        if len(name.encode("cp1252", errors="replace")) > 254 or len(folder.encode("cp1252", errors="replace")) > 254:
            raise ValueError(f"Name too long for a BSA: {p}")
        try:
            name.encode("cp1252"); folder.encode("cp1252")
        except UnicodeEncodeError:
            raise ValueError(f"Name can't be stored in a BSA (non-Western characters): {p}")
        key = (folder, name)
        if key in srcs:
            raise ValueError(f"Duplicate path in the archive: {p}")
        srcs[key] = Path(src)
        top = folder.split("\\", 1)[0]
        if folder.startswith("sound\\voice"):
            fflags |= 0x10
        else:
            fflags |= FILEFLAG_BY_TOP.get(top, 0x100)
        comp = compress and Path(name).suffix in COMPRESS_EXT
        any_comp |= comp
        size = Path(src).stat().st_size
        if comp:
            blobs[key] = _encode_blob(Path(src).read_bytes(), True, ver)
            size = len(blobs[key])
        if size > 0x3FFFFFFF:
            raise ValueError(f"File too large for a BSA: {p}")
        outs.append(_Out(folder, name, None, size, comp))  # type: ignore[arg-type]

    by_folder: dict[str, list[_Out]] = {}
    for o in outs:
        by_folder.setdefault(o.folder, []).append(o)
    folder_list = sorted(by_folder, key=lambda d: tes_hash(d, True))
    for d in folder_list:
        by_folder[d].sort(key=lambda o: tes_hash(o.name))
    aflags = ARCH_DIR_NAMES | ARCH_FILE_NAMES
    tops = {o.folder.split("\\", 1)[0] for o in outs}
    if fflags & 0x1:
        aflags |= 0x80  # "retain strings during startup", set by bsarch for meshes
    if tops & {"sound", "music", "seq", "scripts", "grass"}:
        aflags |= 0x10  # "retain file names", set by bsarch for these folders
    comp_default = False
    folder_rec = 24 if ver == 105 else 16
    total_folder_names = sum(len(d.encode("cp1252")) + 1 for d in folder_list)
    total_file_names = sum(len(o.name.encode("cp1252")) + 1 for o in outs)
    file_block_start = 36 + folder_rec * len(folder_list)
    file_block_size = sum(1 + len(d.encode("cp1252")) + 1 + 16 * len(by_folder[d])
                          for d in folder_list)
    data_start = file_block_start + file_block_size + total_file_names
    if data_start + sum(o.blob_size for o in outs) > MAX_BSA_BYTES:
        raise ValueError("The BSA would exceed 2 GB; it must be split.")

    def blob_of(o: _Out) -> bytes:
        key = (o.folder, o.name)
        return blobs[key] if key in blobs else srcs[key].read_bytes()

    tmp = dest.with_name(dest.name + ".tmp")
    try:
        _write(tmp, ver, aflags, fflags, folder_list, by_folder, len(outs), total_folder_names,
               total_file_names, file_block_start, data_start, False, comp_default, blob_of)
        check = read_bsa(tmp)
        if len(check.entries) != len(outs):
            raise ValueError("Verification failed: file count mismatch")
        with tmp.open("rb") as f:
            for e in check.entries:
                src = srcs.get((e.folder, e.name))
                if src is None or check.read_file(e, f) != src.read_bytes():
                    raise ValueError(f"Verification failed at {e.path}")
        os.replace(tmp, dest)
    finally:
        if tmp.exists():
            tmp.unlink()
    return dest
