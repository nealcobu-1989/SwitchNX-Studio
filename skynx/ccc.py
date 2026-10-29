"""Read and write load lists: Skyrim_aoc.ccc (AE) and the SE `Plugins` file.

One plugin filename per line. Bytes that aren't valid UTF-8 (cp1252 names)
survive a round trip thanks to surrogateescape. Edits keep every untouched
line byte-identical.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

ENC, ERR = "utf-8", "surrogateescape"
BOM = b"\xef\xbb\xbf"


@dataclass
class CccFile:
    path: Path
    raw: bytes
    entries: list[str]
    newline: str            # "CRLF", "LF" or "mixed"
    has_bom: bool
    trailing_newline: bool
    blank_lines: int
    whitespace_issues: list[str]

    @property
    def size(self) -> int:
        return len(self.raw)


def parse_ccc(raw: bytes, path: Path | None = None) -> CccFile:
    has_bom = raw.startswith(BOM)
    body = raw[3:] if has_bom else raw
    crlf = body.count(b"\r\n")
    lf = body.count(b"\n")
    newline = "CRLF" if crlf and crlf == lf else ("LF" if crlf == 0 else "mixed")
    text = body.decode(ENC, ERR)
    lines = text.replace("\r\n", "\n").split("\n")
    trailing = text.endswith("\n")
    if trailing:
        lines = lines[:-1]
    entries, blanks, ws = [], 0, []
    for ln in lines:
        if ln.strip() == "":
            blanks += 1
            continue
        if ln != ln.strip():
            ws.append(ln)
        entries.append(ln.strip())
    return CccFile(Path(path or ""), raw, entries, newline, has_bom, trailing, blanks, ws)


def packed(raw: bytes) -> bytes:
    """The list as Pack writes it for the console: lines switched off with '#'
    are left out (the game skips them, but they'd still cost .ccc bytes)."""
    bom, lines = _lines(raw)
    if not any(k.startswith("#") for k, _c, _e in lines):
        return raw
    return bom + b"".join(c + e for k, c, e in lines if not k.startswith("#"))


def read_ccc(path: Path) -> CccFile:
    path = Path(path)
    return parse_ccc(path.read_bytes(), path)


def entry_bytes(entries: list[str], newline: str = "CRLF") -> int:
    nl = 1 if newline == "LF" else 2
    return sum(len(e.encode(ENC, ERR)) + nl for e in entries)


def render(entries: list[str], newline: str = "CRLF", trailing: bool = True) -> bytes:
    nl = "\n" if newline == "LF" else "\r\n"
    body = nl.join(entries)
    if trailing and entries:
        body += nl
    return body.encode(ENC, ERR)


def _lines(raw: bytes) -> tuple[bytes, list[tuple[str, bytes, bytes]]]:
    """(bom, [(stripped key, content bytes, line ending)])."""
    bom = BOM if raw.startswith(BOM) else b""
    out = []
    for line in raw[len(bom):].splitlines(keepends=True):
        content = line.rstrip(b"\r\n")
        out.append((content.decode(ENC, ERR).strip(), content, line[len(content):]))
    return bom, out


def edit_lines(raw: bytes, mapping: dict[str, str | None]) -> bytes:
    """Replace or delete exact lines (by stripped content), keeping line endings.

    mapping: old line -> new line, or None to delete it.
    """
    bom, lines = _lines(raw)
    out = [bom]
    for key, content, ending in lines:
        if key in mapping:
            new = mapping[key]
            if new is None:
                continue
            out.append(new.encode(ENC, ERR) + ending)
        else:
            out.append(content + ending)
    return b"".join(out)


def reorder(raw: bytes, new_order: list[str], insert: dict[str, str] | None = None) -> bytes:
    """Put lines in new_order, reusing each line's original bytes.

    Entries in new_order that don't exist yet are created with the file's
    dominant newline. Blank lines are kept at the end. Duplicates in the
    original are consumed one by one, so dropping a name from new_order
    drops one occurrence.
    """
    bom, lines = _lines(raw)
    parsed = parse_ccc(raw)
    nl = b"\n" if parsed.newline == "LF" else b"\r\n"
    pool: dict[str, list[tuple[bytes, bytes]]] = {}
    blanks = []
    for key, content, ending in lines:
        if key == "":
            blanks.append(content + ending)
        else:
            pool.setdefault(key, []).append((content, ending))
    out = [bom]
    for i, name in enumerate(new_order):
        if pool.get(name):
            content, ending = pool[name].pop(0)
        else:
            content, ending = name.encode(ENC, ERR), nl
        if not ending:          # was the last line without newline; it's not last anymore
            ending = nl if i < len(new_order) - 1 else b""
        elif i == len(new_order) - 1 and not parsed.trailing_newline:
            ending = b""
        out.append(content + ending)
    if blanks and new_order and not out[-1].endswith((b"\n",)):
        out[-1] += nl
    out.extend(blanks)
    return b"".join(out)


def over_limit(pack, old: bytes, new: bytes) -> int | None:
    """The new size when a write would push an AE .ccc past the 4096-byte limit
    (and grow it); None when it's fine. Shrinking an already-long list is allowed."""
    from .knowledge import CCC_BYTE_LIMIT
    if getattr(pack, "mode", None) == "AE" and pack.list_path and pack.list_path.name.lower().endswith(".ccc"):
        if getattr(pack, "project", False):
            # Pack leaves the lines switched off with '#' out of the console's list:
            # mods kept off in a project cost nothing there
            old, new = packed(old), packed(new)
        if len(new) > CCC_BYTE_LIMIT and len(new) > len(old):
            return len(new)
    return None


def limit_message(size: int) -> tuple[str, str]:
    from .knowledge import CCC_BYTE_LIMIT
    return (f"The .ccc would reach {size} bytes, over the {CCC_BYTE_LIMIT} limit. "
            "Free some space first (shorter names, or leave a mod out).",
            f"El .ccc llegaría a {size} bytes, por encima del límite de {CCC_BYTE_LIMIT}. "
            "Libera espacio antes (nombres más cortos, o deja un mod por fuera).")
