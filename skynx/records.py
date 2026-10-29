"""Read-only walk over the records of a plugin (.esp/.esm/.esl).

Layout (Skyrim SE): a TES4 header record, then top-level GRUPs (one per
record type), with nested GRUPs for cells, worlds and dialogue. Every record
has a 24-byte header (type, data size, flags, FormID, ...); records with flag
0x00040000 store a u32 decompressed size followed by zlib data. Subrecords
are (type, u16 size, payload); an XXXX subrecord carries the u32 size of the
next one when it doesn't fit in 16 bits.

Speed: the file is read once; a `types` filter skips whole top-level groups
and leaves other records untouched (never decompressed). `has` skips
uncompressed records that don't contain any of the given byte strings, so a
scan for VMAD/MODL only looks inside the records that can have them.

Helpers for the requirement checks: scripts attached through VMAD (with
their quest/dialogue fragment and alias scripts) and the models named in
MODL..MOD5.
"""
from __future__ import annotations

import re
import struct
import zlib
from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterable, Iterator

COMPRESSED = 0x00040000
_HDR = struct.Struct("<4sIII")
_SUB = struct.Struct("<4sH")
_U16 = struct.Struct("<H")
_U32 = struct.Struct("<I")

# Record types that live inside nested groups of these top-level groups.
_CELL_KIDS = {b"CELL", b"REFR", b"ACHR", b"PGRE", b"PHZD", b"PMIS", b"PARW", b"PBAR",
              b"PBEA", b"PCON", b"PFLA", b"NAVM", b"LAND"}
CHILDREN = {b"CELL": _CELL_KIDS, b"WRLD": _CELL_KIDS | {b"WRLD"}, b"DIAL": {b"DIAL", b"INFO"}}

MODEL_SUBS = ("MODL", "MOD2", "MOD3", "MOD4", "MOD5")
# Big compressed records that never carry scripts or models.
NO_SCRIPTS_OR_MODELS = {"LAND", "NAVM", "NAVI", "PGRE", "PHZD"}
_IDENT = re.compile(r"^[A-Za-z0-9_]+$")


class RecordError(ValueError):
    pass


def _b4(t) -> bytes:
    return t if isinstance(t, bytes) else t.encode("latin-1")


class Record:
    __slots__ = ("type", "formid", "flags", "data", "error")

    def __init__(self, type_: str, formid: int, flags: int, data: bytes | None,
                 error: str | None = None):
        self.type, self.formid, self.flags, self.data, self.error = type_, formid, flags, data, error

    @property
    def compressed(self) -> bool:
        return bool(self.flags & COMPRESSED)

    def subrecords(self) -> Iterator[tuple[str, bytes]]:
        if self.data is None:
            return iter(())
        return iter_subrecords(self.data)

    def __iter__(self):
        """Unpacks as (type, formid, flags, subrecords iterator)."""
        return iter((self.type, self.formid, self.flags, self.subrecords()))

    def __repr__(self) -> str:
        return f"Record({self.type} {self.formid:08X})"


def iter_subrecords(data: bytes) -> Iterator[tuple[str, bytes]]:
    i, n, big = 0, len(data), None
    while i + 6 <= n:
        sig, size = _SUB.unpack_from(data, i)
        i += 6
        if big is not None:
            size, big = big, None
        if sig == b"XXXX":
            if size < 4 or i + 4 > n:
                raise RecordError("bad XXXX subrecord")
            big = _U32.unpack_from(data, i)[0]
            i += size
            continue
        if i + size > n:
            raise RecordError(f"subrecord {sig!r} runs past the record")
        yield sig.decode("latin-1"), data[i:i + size]
        i += size


def iter_records(src, types: Iterable[str] | None = None, has: Iterable | None = None,
                 exclude: Iterable[str] | None = None, header: bool = False) -> Iterator[Record]:
    """Yield the records of a plugin (Path or bytes), in file order.

    types    only these record types (others are skipped without decompressing)
    exclude  never these types
    has      byte strings; an uncompressed record that contains none of them is
             skipped, a compressed one is decompressed first and then checked
    header   also yield the TES4 record
    A record that can't be decompressed is yielded with data=None and .error set.
    """
    buf = src if isinstance(src, (bytes, bytearray, memoryview)) else Path(src).read_bytes()
    buf = bytes(buf) if not isinstance(buf, bytes) else buf
    want = {_b4(t) for t in types} if types is not None else None
    if want is not None and header:
        want.add(b"TES4")
    skip = {_b4(t) for t in exclude} if exclude else set()
    needles = [_b4(h) for h in has] if has else None
    n = len(buf)
    o = 0
    ends: list[int] = []
    find = buf.find
    while o + 24 <= n:
        while ends and o >= ends[-1]:
            ends.pop()
        typ, size, flags, fid = _HDR.unpack_from(buf, o)
        if typ == b"GRUP":
            gend = o + size
            if size < 24 or gend > n:
                raise RecordError(f"group at {o:#x} runs past the end of the file")
            if not ends and want is not None:
                label = buf[o + 8:o + 12]
                if not ((CHILDREN.get(label, set()) | {label}) & want):
                    o = gend
                    continue
            ends.append(gend)
            o += 24
            continue
        start = o + 24
        end = start + size
        if end > n:
            raise RecordError(f"record {typ!r} at {o:#x} runs past the end of the file")
        o = end
        if typ == b"TES4" and not header:
            continue
        if (want is not None and typ not in want) or typ in skip:
            continue
        ts = typ.decode("latin-1")
        if flags & COMPRESSED:
            try:
                raw = zlib.decompress(buf[start + 4:end])
            except zlib.error as e:
                yield Record(ts, fid, flags, None, f"zlib: {e}")
                continue
            if needles and not any(nd in raw for nd in needles):
                continue
            yield Record(ts, fid, flags, raw)
            continue
        if needles and not any(find(nd, start, end) >= 0 for nd in needles):
            continue
        yield Record(ts, fid, flags, buf[start:end])


# --------------------------------------------------------------------- VMAD
def _wstr(d: bytes, o: int) -> tuple[str, int]:
    if o + 2 > len(d):
        raise RecordError("string past the end")
    k = _U16.unpack_from(d, o)[0]
    o += 2
    if o + k > len(d):
        raise RecordError("string past the end")
    return d[o:o + k].decode("cp1252", "replace"), o + k


_FIXED = {1: 8, 3: 4, 4: 4, 5: 1}
_ARRAY = {11: 8, 13: 4, 14: 4, 15: 1}


def _skip_value(d: bytes, o: int, ptype: int) -> int:
    if ptype == 0:
        return o
    if ptype in _FIXED:
        return o + _FIXED[ptype]
    if ptype == 2:
        return _wstr(d, o)[1]
    if ptype in _ARRAY or ptype == 12:
        if o + 4 > len(d):
            raise RecordError("array past the end")
        cnt = _U32.unpack_from(d, o)[0]
        o += 4
        if ptype == 12:
            for _ in range(cnt):
                o = _wstr(d, o)[1]
            return o
        return o + cnt * _ARRAY[ptype]
    raise RecordError(f"unknown property type {ptype}")


def _scripts_block(d: bytes, o: int, ver: int) -> tuple[list[str], int]:
    if o + 2 > len(d):
        raise RecordError("script count past the end")
    count = _U16.unpack_from(d, o)[0]
    o += 2
    names = []
    for _ in range(count):
        name, o = _wstr(d, o)
        if ver >= 4:
            o += 1
        if o + 2 > len(d):
            raise RecordError("property count past the end")
        pc = _U16.unpack_from(d, o)[0]
        o += 2
        for _ in range(pc):
            _pn, o = _wstr(d, o)
            if o >= len(d):
                raise RecordError("property past the end")
            ptype = d[o]
            o += 1
            if ver >= 4:
                o += 1
            o = _skip_value(d, o, ptype)
        if o > len(d):
            raise RecordError("properties past the end")
        if name:
            names.append(name)
    return names, o


def _ident(name: str) -> str | None:
    return name if name and _IDENT.match(name) else None


def parse_vmad(d: bytes, rtype: str = "") -> tuple[list[str], int]:
    """Script names in a VMAD subrecord: attached scripts, then (for quests,
    dialogue, packages, perks and scenes) the fragment script and, for quests,
    the scripts on aliases. Returns (names, errors): errors is 1 when the
    attached-scripts list couldn't be read (nothing is returned then) or when
    the trailing fragment data couldn't be read (the scripts found are kept)."""
    if len(d) < 6:
        return [], 1
    ver, objfmt = struct.unpack_from("<hh", d, 0)
    if not 2 <= ver <= 6 or objfmt not in (1, 2):
        return [], 1
    try:
        names, o = _scripts_block(d, 4, ver)
    except (RecordError, struct.error, IndexError):
        return [], 1
    if rtype not in ("QUST", "INFO", "PACK", "SCEN", "PERK") or o >= len(d):
        return names, 0
    try:
        if rtype in ("INFO", "PACK", "SCEN"):
            f, o = _wstr(d, o + 2)
            if _ident(f):
                names.append(f)
        elif rtype == "PERK":
            f, o = _wstr(d, o + 1)
            if _ident(f):
                names.append(f)
        else:  # QUST: fragments, then aliases with their own scripts
            nfrag = _U16.unpack_from(d, o + 1)[0]
            f, o = _wstr(d, o + 3)
            if _ident(f):
                names.append(f)
            for _ in range(nfrag):
                o += 2 + 2 + 4 + 1
                s, o = _wstr(d, o)
                _fn, o = _wstr(d, o)
                if _ident(s) and s not in names:
                    names.append(s)
            nal = _U16.unpack_from(d, o)[0]
            o += 2
            for _ in range(nal):
                o += 8
                aver = struct.unpack_from("<h", d, o)[0]
                o += 4
                if not 2 <= aver <= 6:
                    raise RecordError("bad alias version")
                more, o = _scripts_block(d, o, aver)
                names += [m for m in more if m not in names]
    except (RecordError, struct.error, IndexError):
        return names, 1
    return names, 0


def _zstr(b: bytes) -> str:
    return b.split(b"\x00", 1)[0].decode("cp1252", "replace")


def norm_model(p: str) -> str:
    """'Weapons/Iron/Sword.nif' -> 'meshes\\weapons\\iron\\sword.nif'."""
    p = p.strip().replace("/", "\\").lower().lstrip("\\")
    while "\\\\" in p:
        p = p.replace("\\\\", "\\")
    if p.startswith("data\\"):
        p = p[5:]
    if not p.startswith("meshes\\"):
        p = "meshes\\" + p
    return p


# --------------------------------------------------------------------- scans
@dataclass
class PluginScan:
    scripts: dict[str, list[str]] = field(default_factory=dict)   # lower name -> record ids
    names: dict[str, str] = field(default_factory=dict)           # lower name -> spelling
    models: dict[str, list[str]] = field(default_factory=dict)    # norm path -> record ids
    masters: list[str] = field(default_factory=list)
    records: int = 0
    unreadable: int = 0
    error: str | None = None


class ScriptMap(dict):
    """dict[script lower, [record ids]] that also says how many records failed."""
    unreadable = 0


_SCAN_CACHE: dict[tuple, PluginScan] = {}


def scan_plugin(path: Path, skip_masters: Iterable[str] = (), max_ids: int = 5) -> PluginScan:
    """Scripts (VMAD) and models (MODL..MOD5) of every record, in one pass.
    Records that belong to a master in `skip_masters` (by FormID) are ignored,
    which keeps overrides of content the pack can't check (Creation Club)
    out of the results. Cached by file size and time."""
    path = Path(path)
    skip = {s.lower() for s in skip_masters}
    try:
        st = path.stat()
    except OSError as e:
        return PluginScan(error=str(e))
    key = (str(path), st.st_size, st.st_mtime, frozenset(skip), max_ids)
    if key in _SCAN_CACHE:
        return _SCAN_CACHE[key]
    out = PluginScan()
    model_subs = set(MODEL_SUBS)
    try:
        it = iter_records(path, has=(b"VMAD", b"MOD", b"MAST"), exclude=NO_SCRIPTS_OR_MODELS,
                          header=True)
        skip_idx: set[int] = set()
        for rec in it:
            if rec.type == "TES4":
                try:
                    out.masters = [_zstr(p) for s, p in rec.subrecords() if s == "MAST"]
                except RecordError:
                    pass
                skip_idx = {i for i, m in enumerate(out.masters) if m.lower() in skip}
                continue
            out.records += 1
            if rec.data is None:
                out.unreadable += 1
                continue
            if (rec.formid >> 24) in skip_idx:
                continue
            rid = None
            vmad = None
            models = []
            try:
                for sig, payload in iter_subrecords(rec.data):
                    if sig == "EDID":
                        rid = _zstr(payload)
                    elif sig == "VMAD":
                        vmad = payload
                    elif sig in model_subs and not (sig == "MODL" and rec.type == "ARMO"):
                        # (an ARMO's MODL is the FormID of an armature, not a path)
                        m = _zstr(payload)
                        if m.strip() and m.isprintable():
                            models.append(m)
            except RecordError:
                out.unreadable += 1
                continue
            rid = rid or f"{rec.type} {rec.formid:08X}"
            if vmad is not None:
                names, err = parse_vmad(vmad, rec.type)
                out.unreadable += err
                for nm in names:
                    low = nm.lower()
                    out.names.setdefault(low, nm)
                    ids = out.scripts.setdefault(low, [])
                    if len(ids) < max_ids and rid not in ids:
                        ids.append(rid)
            for m in models:
                ids = out.models.setdefault(norm_model(m), [])
                if len(ids) < max_ids and rid not in ids:
                    ids.append(rid)
    except (RecordError, OSError, struct.error) as e:
        out.error = str(e)
    _SCAN_CACHE[key] = out
    return out


def scripts_attached(path: Path, skip_masters: Iterable[str] = ()) -> ScriptMap:
    """Script names (lowercase) attached through VMAD -> EDIDs (or 'TYPE FORMID')
    of the records that use them. `.unreadable` counts records that failed."""
    s = scan_plugin(path, skip_masters)
    out = ScriptMap(s.scripts)
    out.unreadable = s.unreadable
    return out


def models_used(path: Path, skip_masters: Iterable[str] = ()) -> set[str]:
    """Model paths from MODL/MOD2..MOD5, as 'meshes\\...' lowercase."""
    return set(scan_plugin(path, skip_masters).models)


# --------------------------------------------------------------------- TES4 HEDR
def hedr_offset(raw: bytes) -> int | None:
    """File offset of the HEDR version float in a plugin's TES4 header."""
    if raw[:4] != b"TES4" or len(raw) < 24:
        return None
    dsize = _U32.unpack_from(raw, 4)[0]
    i, end = 24, min(len(raw), 24 + dsize)
    while i + 6 <= end:
        sig, size = _SUB.unpack_from(raw, i)
        if sig == b"XXXX":
            big = _U32.unpack_from(raw, i + 6)[0]
            i += 6 + size + 6 + big
            continue
        if sig == b"HEDR":
            return i + 6 if size >= 4 and i + 10 <= end else None
        i += 6 + size
    return None


def set_hedr_version(raw: bytes, version: float) -> bytes:
    """Same plugin with only the 4 bytes of the HEDR version changed."""
    o = hedr_offset(raw)
    if o is None:
        raise RecordError("no HEDR in the TES4 header")
    return raw[:o] + struct.pack("<f", version) + raw[o + 4:]


def iter_headers(src) -> Iterator[tuple[str, int, int]]:
    """(type, FormID, flags) of every record, TES4 included, without reading
    or decompressing any record data."""
    buf = src if isinstance(src, (bytes, bytearray)) else Path(src).read_bytes()
    n, o = len(buf), 0
    while o + 24 <= n:
        typ, size, flags, fid = _HDR.unpack_from(buf, o)
        if typ == b"GRUP":
            if size < 24:
                raise RecordError(f"group at {o:#x} is too small")
            o += 24
            continue
        yield typ.decode("latin-1"), fid, flags
        o += 24 + size


def own_low_formids(path: Path) -> int:
    """How many of the plugin's own records use object IDs below 0x800 (only
    allowed with HEDR 1.71, CK 1.6.1130+). Overrides of masters don't count."""
    nm = None
    count = 0
    for typ, fid, _fl in iter_headers(path):
        if typ == "TES4":
            continue
        if nm is None:
            nm = len(_masters_of(path))
        if (fid >> 24) >= nm and (fid & 0xFFFFFF) < 0x800:
            count += 1
    return count


def _masters_of(path: Path) -> list[str]:
    for rec in iter_records(path, types=(), header=True):
        if rec.type == "TES4" and rec.data is not None:
            return [_zstr(p) for s, p in rec.subrecords() if s == "MAST"]
    return []


# --------------------------------------------------------------------- SEQ
# seq\<plugin stem>.seq is a flat array of little-endian uint32 FormIDs (as
# stored in the plugin) of its Start Game Enabled quests. Source: xEdit's
# "Create SEQ File" (xEdit/xeMainForm.pas, GenerateSEQFileForFile) and the
# QUST DNAM definition (Core/wbDefinitionsTES5.pas: Flags uint16, bit 0 =
# Start Game Enabled, then Priority u8, Form Version u8, 4 bytes, Type u32).
SGE = 0x0001


@dataclass
class QuestScan:
    masters: list[str] = field(default_factory=list)
    own: list[int] = field(default_factory=list)          # new SGE quests, in file order
    overrides: list[int] = field(default_factory=list)    # SGE overrides of master quests
    flags: dict[int, int] = field(default_factory=dict)   # FormID -> DNAM flags, every quest
    sge: list[int] = field(default_factory=list)          # own + overrides, in file order
    error: str | None = None


_QUEST_CACHE: dict[tuple, QuestScan] = {}


def quest_scan(path: Path) -> QuestScan:
    """Quests of a plugin and their DNAM flags (decompressing when needed).
    FormIDs are normalised like xEdit's FixedFormID: a file index past the
    master list means the plugin itself."""
    path = Path(path)
    try:
        st = path.stat()
    except OSError as e:
        return QuestScan(error=str(e))
    key = (str(path), st.st_size, st.st_mtime_ns)
    if key in _QUEST_CACHE:
        return _QUEST_CACHE[key]
    out = QuestScan()
    try:
        for rec in iter_records(path, types=("QUST",), header=True):
            if rec.type == "TES4":
                out.masters = [_zstr(p) for s, p in rec.subrecords() if s == "MAST"]
                continue
            if rec.data is None:
                continue
            flags = None
            for sig, payload in rec.subrecords():
                if sig == "DNAM" and len(payload) >= 2:
                    flags = _U16.unpack_from(payload, 0)[0]
                    break
            if flags is None:
                continue
            fid = rec.formid
            nm = len(out.masters)
            if (fid >> 24) > nm:
                fid = (nm << 24) | (fid & 0xFFFFFF)
            out.flags[fid] = flags
            if flags & SGE:
                (out.own if (fid >> 24) == nm else out.overrides).append(fid)
                out.sge.append(fid)
    except (RecordError, OSError, struct.error) as e:
        out.error = str(e)
    for k in [k for k in _QUEST_CACHE if k[0] == key[0]]:
        del _QUEST_CACHE[k]
    _QUEST_CACHE[key] = out
    return out


def seq_wanted(path: Path, master_scan) -> tuple[list[int], list[int]]:
    """The FormIDs xEdit's Create SEQ File would write for this plugin, and
    the ones it can't decide here.

    xEdit (GenerateSEQFileForFile) takes every QUST with DNAM Flags bit 0
    (Start Game Enabled) that is new in the plugin, or that overrides a
    master quest whose own record doesn't have the flag. master_scan(name)
    returns the QuestScan of a master, or None when that master can't be
    read (the game's own .esm files are on the console, not in the pack):
    overrides of those quests are returned as undecided."""
    qs = quest_scan(path)
    wanted, unknown = list(qs.own), []
    for fid in qs.overrides:
        idx = fid >> 24
        m = qs.masters[idx] if idx < len(qs.masters) else None
        ms = master_scan(m) if m else None
        if ms is None or ms.error:
            unknown.append(fid)
            continue
        mfid = (len(ms.masters) << 24) | (fid & 0xFFFFFF)
        if not ms.flags.get(mfid, 0) & SGE:
            wanted.append(fid)
    order = {f: i for i, f in enumerate(qs.sge)}
    wanted.sort(key=lambda f: order.get(f, 0))
    return wanted, unknown


def seq_bytes(formids: Iterable[int]) -> bytes:
    ids = list(formids)
    return struct.pack(f"<{len(ids)}I", *ids)


def parse_seq(raw: bytes) -> list[int]:
    if len(raw) % 4:
        raise RecordError("a SEQ file is a list of 4-byte FormIDs")
    return list(struct.unpack(f"<{len(raw) // 4}I", raw))


# --------------------------------------------------------------------- rewriting
def rewrite_records(raw: bytes, edit) -> tuple[bytes, int]:
    """A copy of a plugin with some records' data replaced, groups resized.

    edit(type, formid, data) gets each record's (decompressed) data and returns
    new data, or None to keep the record as it is. A compressed record is
    compressed again. Returns (new bytes, records changed)."""
    out = bytearray()
    changed = 0

    def walk(o: int, end: int) -> int:
        nonlocal changed
        while o + 24 <= end:
            typ, size, flags, fid = _HDR.unpack_from(raw, o)
            if typ == b"GRUP":
                gend = o + size
                if size < 24 or gend > end:
                    raise RecordError(f"group at {o:#x} runs past its end")
                at = len(out)
                out.extend(raw[o:o + 24])
                walk(o + 24, gend)
                struct.pack_into("<I", out, at + 4, len(out) - at)
                o = gend
                continue
            start, rend = o + 24, o + 24 + size
            if rend > end:
                raise RecordError(f"record {typ!r} at {o:#x} runs past its end")
            body = raw[start:rend]
            new = None
            if typ != b"TES4":
                data = zlib.decompress(body[4:]) if flags & COMPRESSED else body
                new = edit(typ.decode("latin-1"), fid, data)
            if new is None:
                out.extend(raw[o:rend])
            else:
                changed += 1
                if flags & COMPRESSED:
                    new = struct.pack("<I", len(new)) + zlib.compress(new)
                hdr = bytearray(raw[o:o + 24])
                struct.pack_into("<I", hdr, 4, len(new))
                out.extend(hdr)
                out.extend(new)
            o = rend
        return o

    walk(0, len(raw))
    return bytes(out), changed


def replace_subrecord(data: bytes, sig: str, value: bytes) -> bytes:
    """Record data with the first `sig` subrecord's payload replaced (sizes
    over 64 KB aren't expected for the names this is used for)."""
    out, o, done = bytearray(), 0, False
    want = sig.encode("latin-1")
    while o + 6 <= len(data):
        s, n = _SUB.unpack_from(data, o)
        if s == b"XXXX":                      # the next subrecord's real size; kept as is
            big = _U32.unpack_from(data, o + 6)[0]
            out.extend(data[o:o + 16 + big])
            o += 16 + big
            continue
        if s == want and not done:
            out.extend(s + struct.pack("<H", len(value)) + value)
            done = True
        else:
            out.extend(data[o:o + 6 + n])
        o += 6 + n
    return bytes(out)
