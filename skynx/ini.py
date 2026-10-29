"""Tolerant Skyrim ini reader with line-level editing.

Skyrim inis are not strict: duplicate keys, '#' and ';' comments, keys with
spaces ("uExterior Cell Buffer"). Every occurrence is kept so duplicates can
be reported, and edits touch only the line they target.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

ARCHIVE_KEYS = ("sResourceArchiveList", "sResourceArchiveList2",
                "sArchiveToLoadInMemoryList")
ARCHIVE_LIST_LIMIT = 1024


@dataclass
class IniEntry:
    section: str
    key: str
    value: str
    line: int


@dataclass
class IniFile:
    path: Path
    raw: bytes = b""
    entries: list[IniEntry] = field(default_factory=list)
    newline: str = "LF"

    def get_all(self, section: str, key: str) -> list[IniEntry]:
        s, k = section.lower(), key.lower()
        return [e for e in self.entries if e.section.lower() == s and e.key.lower() == k]

    def get(self, section: str, key: str) -> str | None:
        found = self.get_all(section, key)
        return found[-1].value if found else None

    def duplicates(self) -> list[tuple[str, str, list[int]]]:
        seen: dict[tuple[str, str], list[int]] = {}
        for e in self.entries:
            seen.setdefault((e.section.lower(), e.key.lower()), []).append(e.line)
        return [(s, k, lines) for (s, k), lines in seen.items() if len(lines) > 1]

    def archive_list(self, key: str) -> list[str]:
        v = self.get("Archive", key)
        if v is None:
            return []
        return [x.strip() for x in v.split(",") if x.strip()]


def parse_ini(raw: bytes, path: Path | None = None) -> IniFile:
    text = raw.decode("utf-8", "surrogateescape")
    if text.startswith("\ufeff"):
        text = text[1:]
    ini = IniFile(path=Path(path or ""), raw=raw,
                  newline="CRLF" if "\r\n" in text else "LF")
    section = ""
    for n, line in enumerate(text.replace("\r\n", "\n").split("\n"), start=1):
        s = line.strip()
        if not s or s[0] in ";#":
            continue
        if s.startswith("[") and "]" in s:
            section = s[1:s.index("]")].strip()
            continue
        if "=" in s:
            k, v = s.split("=", 1)
            ini.entries.append(IniEntry(section, k.strip(), v.strip(), n))
    return ini


def read_ini(path: Path) -> IniFile:
    path = Path(path)
    return parse_ini(path.read_bytes(), path)


def set_value(raw: bytes, section: str, key: str, value: str) -> bytes:
    """Set key=value in section. Edits the last occurrence; appends if missing."""
    ini = parse_ini(raw)
    nl = b"\r\n" if ini.newline == "CRLF" else b"\n"
    lines = raw.split(b"\n")
    found = ini.get_all(section, key)
    if found:
        idx = found[-1].line - 1
        cr = lines[idx].endswith(b"\r")
        lines[idx] = f"{found[-1].key}={value}".encode("utf-8", "surrogateescape") + (b"\r" if cr else b"")
        return b"\n".join(lines)
    # append inside the section, or create it
    text_lines = [l.rstrip(b"\r") for l in lines]
    sec_idx = None
    for i, l in enumerate(text_lines):
        s = l.strip()
        if s.startswith(b"[") and s[1:].split(b"]")[0].strip().lower() == section.lower().encode():
            sec_idx = i
    new_line = f"{key}={value}".encode("utf-8", "surrogateescape")
    if sec_idx is None:
        body = raw.rstrip(b"\r\n") + nl + nl + f"[{section}]".encode() + nl + new_line + nl
        return body
    insert = sec_idx + 1
    while insert < len(text_lines) and not text_lines[insert].strip().startswith(b"["):
        insert += 1
    while insert - 1 > sec_idx and text_lines[insert - 1].strip() == b"":
        insert -= 1
    cr = b"\r" if ini.newline == "CRLF" else b""
    lines.insert(insert, new_line + cr)
    return b"\n".join(lines)


def set_archive_list(raw: bytes, key: str, items: list[str]) -> bytes:
    return set_value(raw, "Archive", key, ", ".join(items))
