"""The same mod twice in one pack.

* One plugin under two names: identical bytes, or names that only differ by
  Google Drive's damage (audit.norm_name), with both copies loading. A copy
  that doesn't load is only reported as an info (it just takes space).
* Two loaded BSAs with the same content (same files with the same sizes),
  for example "Mod.bsa" next to a Koka-style short copy "ModM.bsa" listed in
  the ini. The earlier copy does nothing; when it comes from the ini, removing
  it from the ini changes nothing in game.
* A mod merged into a merged plugin and also loaded on its own. Merge Plugins
  writes the components in the TES4 description (SNAM):
  "Merged Plugin: \\r\\n  A.esp\\r\\n  B.esp". Components kept as empty
  placeholders (0 records, so masters and BSAs still resolve) are intentional
  and not reported.

Functions return finding-ready dicts like requirements.check.
"""
from __future__ import annotations

import hashlib
import struct
from collections import defaultdict
from pathlib import Path
from typing import Callable

from . import knowledge as K
from .audit import F, norm_name
from .bsa import BsaArchive, read_bsa
from .plugin import PluginHeader

MERGED_PREFIX = "merged plugin:"


def _f(code, severity, subject, params=None, items=None, fix=None, msg=None, alt=None) -> dict:
    return {"code": code, "severity": severity, "msg": msg or code, "subject": subject,
            "params": params or {}, "items": items or [], "fix": fix, "alt": alt or []}


# ---- choices offered for every duplicate (see dupfix.py)
def _keep(code: str, subject: str, n: int) -> dict:
    """Keep them all; the Doctor stops warning about this one."""
    return F("dup_ignore", "fix-dup-keep-both" if n <= 2 else "fix-dup-keep-all", "seguro",
             finding=f"{code}:{subject}")


def _keep_only_plugins(names: list[str]) -> list[dict]:
    return [F("dup_keep_only", "fix-dup-keep-only", "revisar", {"name": n}, keep=n,
              remove=[x for x in names if x != n]) for n in names]


def _keep_only_bsas(names: list[str]) -> list[dict]:
    return [F("dup_drop_bsa", "fix-dup-keep-only", "revisar", {"name": n}, keep=n,
              remove=[x for x in names if x != n]) for n in names]


def _mb(n: int) -> str:
    return f"{n / 2**20:.1f} MB"


def _snam(raw: bytes) -> str:
    """SNAM (description) of a TES4 record given the plugin's (first) bytes."""
    if raw[:4] != b"TES4" or len(raw) < 24:
        return ""
    size = struct.unpack_from("<I", raw, 4)[0]
    data = raw[24:24 + size]
    i, big = 0, None
    while i + 6 <= len(data):
        sig, ss = struct.unpack_from("<4sH", data, i)
        i += 6
        if big is not None:
            ss, big = big, None
        if sig == b"XXXX":
            big = struct.unpack_from("<I", data, i)[0]
            i += ss
            continue
        if sig == b"SNAM":
            return data[i:i + ss].split(b"\x00", 1)[0].decode("cp1252", "replace")
        i += ss
    return ""


def merged_components(header) -> list[str]:
    """Plugins a merged plugin says it contains. `header` is the plugin's
    bytes (at least its TES4 record) or its description text. [] when the
    description doesn't start with "Merged Plugin:"."""
    if isinstance(header, (bytes, bytearray, memoryview)):
        from .loot import merged_components as _loot_merged
        return _loot_merged(bytes(header))       # one parser for the Doctor and LOOT
    text = str(header or "")
    t = text.lstrip()
    if not t.lower().startswith(MERGED_PREFIX):
        return []
    out = []
    for line in t[len(MERGED_PREFIX):].replace("\r", "\n").split("\n"):
        line = line.strip()
        if line.lower().endswith((".esp", ".esm", ".esl")) and line not in out:
            out.append(line)
    return out


def _sha1(path: Path) -> str | None:
    h = hashlib.sha1()
    try:
        with Path(path).open("rb") as f:
            for chunk in iter(lambda: f.read(1 << 20), b""):
                h.update(chunk)
    except OSError:
        return None
    return h.hexdigest()


def find_duplicates(pack, get_arc: Callable[[Path], BsaArchive | None] | None = None,
                    extra_bsas=()) -> list[dict]:
    from .conflicts import load_order_bsas
    get = get_arc or (lambda p: _read(p))
    out: list[dict] = []
    order = [(n, src) for n, src in pack.load_order() if src != "juego" and not n.startswith("#")]
    active = [pack.plugins[n.lower()] for n, _ in order if n.lower() in pack.plugins]
    active_low = {h.name.lower() for h in active}
    pos = {h.name.lower(): i for i, h in enumerate(active)}
    game = {m.lower() for m in K.VANILLA_MASTERS + K.SWITCH_MASTERS}

    # ---- plugins: identical bytes (dummies are alike by design: skip them)
    by_size: dict[int, list[PluginHeader]] = defaultdict(list)
    for h in pack.plugins.values():
        if not h.error and h.num_records > 0 and h.name.lower() not in game:
            by_size[h.size].append(h)
    reported: set[frozenset] = set()
    for group in by_size.values():
        if len(group) < 2:
            continue
        by_hash: dict[str, list[PluginHeader]] = defaultdict(list)
        for h in group:
            d = _sha1(h.path)
            if d:
                by_hash[d].append(h)
        for same in by_hash.values():
            if len(same) < 2:
                continue
            on = sorted([h for h in same if h.name.lower() in active_low], key=lambda h: pos[h.name.lower()])
            off = [h for h in same if h.name.lower() not in active_low]
            if len(on) >= 2:
                reported.add(frozenset(h.name.lower() for h in on))
                names = [h.name for h in on]
                out.append(_f("dup-plugin-same", "aviso", on[-1].name,
                              {"name": on[-1].name, "other": ", ".join(h.name for h in on[:-1])},
                              names, alt=_keep_only_plugins(names) + [_keep("dup-plugin-same", on[-1].name, len(names))]))
            if on:
                for h in off:
                    if norm_name(h.name) == norm_name(on[0].name):
                        continue   # the audit's "leftover" already covers it
                    size = h.size + sum(b.stat().st_size for b in pack.bsas_for_plugin(h.name))
                    out.append(_f("dup-plugin-copy", "info", h.name,
                                  {"name": h.name, "other": on[0].name, "size": _mb(size)},
                                  [h.name], alt=[F("dup_delete_copy", "fix-dup-delete-copy", "revisar",
                                                   {"name": h.name}, name=h.name),
                                                 _keep("dup-plugin-copy", h.name, 2)]))

    # ---- plugins: same name once Drive's damage is folded, both loading
    by_norm: dict[str, list[PluginHeader]] = defaultdict(list)
    for h in active:
        by_norm[norm_name(h.name)].append(h)
    for group in by_norm.values():
        if len(group) < 2 or frozenset(h.name.lower() for h in group) in reported:
            continue
        names = [h.name for h in group]
        out.append(_f("dup-plugin-name", "aviso", group[-1].name,
                      {"name": group[-1].name, "other": ", ".join(h.name for h in group[:-1])},
                      names, alt=_keep_only_plugins(names) + [_keep("dup-plugin-name", group[-1].name, len(names))]))

    # ---- BSAs with the same content, both loading
    loaded = list(load_order_bsas(pack))
    seen = {str(p) for _n, p, _s in loaded}
    for p in extra_bsas:
        if str(p) not in seen:
            seen.add(str(p))
            loaded.append((p.name, p, "ini:?"))
    sigs: dict[tuple, list[tuple[int, str, str]]] = defaultdict(list)
    for i, (n, p, src) in enumerate(loaded):
        arc = get(p)
        if arc is None or not arc.entries:
            continue
        sig = tuple(sorted((e.path.lower(), e.size) for e in arc.entries))
        sigs[sig].append((i, n, src))
    for sig, copies in sigs.items():
        if len(copies) < 2:
            continue
        copies.sort()
        last = copies[-1]
        first = copies[0]
        fix = None
        auto = {b.name.lower() for h in active for b in pack.bsas_for_plugin(h.name)}
        ini_only = [c for c in copies if c[2].startswith("ini:") and c[2] != "ini:?"
                    and c[1].lower() not in auto]
        if len(copies) == 2 and len(ini_only) == 1:
            # one copy only loads from the ini: dropping it leaves the same files
            # loading from the other copy. On Switch the ini copy is the later
            # one (conflicts.py), so if it also wins over another ini BSA,
            # dropping it changes who wins there: then it's for the user to look.
            drop = ini_only[0]
            mine = {e.path.lower() for e in get(loaded[drop[0]][1]).entries}
            clash = any(n.lower() != drop[1].lower() and src.startswith("ini:") and get(pth) is not None
                        and mine & {e.path.lower() for e in get(pth).entries}
                        for n, pth, src in loaded if not any(n == c[1] for c in copies))
            fix = F("ini_remove_archive", "fix-ini-remove", "revisar" if clash else "seguro",
                    key=drop[2][4:], item=drop[1])
        names = [c[1] for c in copies]
        out.append(_f("dup-bsa", "aviso", last[1],
                      {"name": last[1], "other": ", ".join(c[1] for c in copies[:-1]),
                       "files": len(sig)},
                      names, fix=fix, alt=_keep_only_bsas(names) + [_keep("dup-bsa", last[1], len(names))]))

    # ---- merged plugins whose components also load on their own
    for m in active:
        comps = merged_components(m.description)
        if not comps:
            continue
        for c in comps:
            low = c.lower()
            h = pack.plugins.get(low)
            if h is None:
                h = next((x for x in active if norm_name(x.name) == norm_name(c)), None)
            if h is None or h.name.lower() == m.name.lower():
                continue
            if h.error or h.num_records == 0:
                continue   # placeholder kept on purpose
            if h.name.lower() not in active_low:
                size = h.size + sum(b.stat().st_size for b in pack.bsas_for_plugin(h.name))
                out.append(_f("dup-merged-copy", "info", f"{m.name}>{h.name}",
                              {"name": h.name, "merged": m.name, "size": _mb(size)}, [h.name],
                              alt=[F("dup_delete_copy", "fix-dup-delete-copy", "revisar",
                                     {"name": h.name}, name=h.name),
                                   _keep("dup-merged-copy", f"{m.name}>{h.name}", 2)]))
                continue
            deps = [d.name for d in active if any(x.lower() == h.name.lower() for x in d.masters)]
            out.append(_f("dup-merged", "aviso", f"{m.name}>{h.name}",
                          {"name": h.name, "merged": m.name, "records": h.num_records},
                          [h.name], alt=[F("dup_take_out", "fix-dup-empty-loose", "revisar", {"name": h.name},
                                           name=h.name, deps=deps),
                                         _keep("dup-merged", f"{m.name}>{h.name}", 2)]))
    return out


def _read(p: Path):
    try:
        return read_bsa(p)
    except Exception:  # noqa: BLE001
        return None
