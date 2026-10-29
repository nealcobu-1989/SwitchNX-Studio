"""Which mod is this, really? Names change on the way to the Switch (Google
Drive damage, shortened names, renames for the .ccc, merges), so a mod is
recognised from several clues, strongest first:

1. what the person confirmed before (kept per plugin file, by its SHA-1,
   so it follows the same plugin into other packs);
2. where the app got it (a Nexus download, recorded in the pack or in the
   Library's skynx-mod.json);
3. the LOOT masterlist, which links thousands of plugins to their Nexus page,
   asked with the name in the pack and with every original name the app knows
   (converter and Doctor renames), tolerating Drive's '_' for apostrophes;
4. a merged plugin: the mods it lists inside.

Nothing here goes online. Anniversary Edition mods live on Nexus' Skyrim
Special Edition pages, so links point there.
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import time
from pathlib import Path
from urllib.parse import quote

GAME = "skyrimspecialedition"
MOD_URL = "https://www.nexusmods.com/skyrimspecialedition/mods/{mod_id}"
SEARCH_URL = "https://www.nexusmods.com/games/skyrimspecialedition/search?keyword={q}"
_NEXUS = re.compile(r"^https?://(?:www\.)?nexusmods\.com/skyrimspecialedition/mods/(\d+)", re.I)
STORE = ".identities.json"
SMALL = 512        # header-only dummy plugins look alike byte for byte: match those by name too


def nexus_id(url: str) -> int | None:
    """The Skyrim SE mod id of a Nexus link (None for other sites or games)."""
    m = _NEXUS.match(str(url or "").strip())
    return int(m.group(1)) if m else None


def parse_input(text: str) -> int | None:
    """A Nexus link, or just the number."""
    t = str(text or "").strip()
    if t.isdigit():
        return int(t)
    return nexus_id(t)


def search_url(query: str) -> str:
    return SEARCH_URL.format(q=quote(query))


def query_for(name: str) -> str:
    """Words worth searching for: no extension, separators as spaces, Drive's '_'."""
    stem = re.sub(r"\.(esp|esm|esl|bsa)$", "", name, flags=re.I)
    stem = re.sub(r"\s*-\s*textures\d*$", "", stem, flags=re.I)
    stem = re.sub(r"(?<=[A-Za-z])_s(?=[_\s]|$)", "'s", stem)      # Drive turned Ryn's into Ryn_s
    stem = re.sub(r"[_\-.]+", " ", stem)
    stem = " ".join(re.sub(r"(?<=[a-z])(?=[A-Z])", " ", w) if len(w) > 3 else w   # CamelCase -> words
                    for w in stem.split())
    return re.sub(r"\s{2,}", " ", stem).strip()


def _sha1(path: Path) -> str | None:
    try:
        h = hashlib.sha1()
        with Path(path).open("rb") as f:
            for chunk in iter(lambda: f.read(1 << 20), b""):
                h.update(chunk)
        return h.hexdigest()
    except OSError:
        return None


# ------------------------------------------------------------------ what the person confirmed
def _small(path) -> dict:
    try:
        return {"small": True} if Path(path).stat().st_size < SMALL else {}
    except OSError:
        return {}


def _store_hit(store: dict, sha: str | None, name: str) -> dict | None:
    e = store.get("by_sha", {}).get(sha) if sha else None
    if e and e.get("small") and str(e.get("plugin") or "").lower() != name.lower():
        return None
    return e


def load_store(library_root: Path) -> dict:
    f = Path(library_root) / STORE
    try:
        d = json.loads(f.read_text(encoding="utf-8"))
        if isinstance(d, dict):
            d.setdefault("by_sha", {})
            d.setdefault("mods", {})
            return d
    except (OSError, ValueError):
        pass
    return {"by_sha": {}, "mods": {}}


def save_store(library_root: Path, d: dict) -> None:
    root = Path(library_root)
    root.mkdir(parents=True, exist_ok=True)
    f = root / STORE
    tmp = f.with_name(f.name + ".tmp")
    tmp.write_text(json.dumps(d, indent=1, ensure_ascii=False), encoding="utf-8")
    os.replace(tmp, f)


def remember(library_root: Path, plugin_path: Path, mod_id: int | None, name: str = "") -> dict:
    """Keep (or with mod_id None, forget) which Nexus mod a plugin file is."""
    d = load_store(library_root)
    sha = _sha1(plugin_path)
    if not sha:
        raise OSError(f"Can't read {plugin_path}")
    if mod_id is None:
        d["by_sha"].pop(sha, None)
    else:
        d["by_sha"][sha] = {"mod_id": int(mod_id), "plugin": name or Path(plugin_path).name,
                            "when": time.strftime("%Y-%m-%d %H:%M:%S"), **_small(plugin_path)}
    save_store(library_root, d)
    return d


def remember_installed(library_root: Path, plugin_path: Path, mod_id: int, file_id: int | None = None,
                       version: str | None = None, name: str = "") -> dict:
    """Which file of the Nexus mod this plugin is ("I have this one"). Also
    confirms the mod. file_id None and no version forgets the file only."""
    d = load_store(library_root)
    sha = _sha1(plugin_path)
    if not sha:
        raise OSError(f"Can't read {plugin_path}")
    e = d["by_sha"].get(sha)
    if not e or int(e.get("mod_id") or 0) != int(mod_id):
        e = {"mod_id": int(mod_id), "plugin": name or Path(plugin_path).name, **_small(plugin_path)}
    if file_id or version:
        e["installed"] = {k: v for k, v in (("file_id", int(file_id) if file_id else None),
                                            ("version", str(version) if version else None)) if v}
    else:
        e.pop("installed", None)
    e["when"] = time.strftime("%Y-%m-%d %H:%M:%S")
    d["by_sha"][sha] = e
    save_store(library_root, d)
    return d


def remember_details(library_root: Path, mod_id: int, info: dict) -> None:
    """Name, version and summary from Nexus (fetched with the person's key)."""
    d = load_store(library_root)
    keep = {k: info.get(k) for k in ("name", "version", "author", "summary", "picture_url", "updated_time")
            if info.get(k) is not None}
    keep["fetched"] = time.strftime("%Y-%m-%d %H:%M:%S")
    d["mods"][str(int(mod_id))] = keep
    save_store(library_root, d)


# ------------------------------------------------------------------ the clues
def _provenance_nx(src) -> dict | None:
    if not isinstance(src, dict):
        return None
    nx = src.get("nexus") or ((src.get("origin") or {}).get("nexus") if isinstance(src.get("origin"), dict) else None)
    if isinstance(nx, dict) and nx.get("mod_id") and (nx.get("game") or GAME) == GAME:
        return nx
    return None


def _provenance(src) -> int | None:
    nx = _provenance_nx(src)
    try:
        return int(nx["mod_id"]) if nx else None
    except (TypeError, ValueError):
        return None


def identify(plugins: list[str], headers: dict, *, record: dict | None = None, aliases: dict | None = None,
             masterlist=None, store: dict | None = None, paths: dict | None = None,
             shas: dict | None = None) -> dict:
    """One mod (its plugins). headers: lower name -> PluginHeader (author,
    description, masters). aliases: name now -> original name. paths: lower
    name -> file, for the confirmed-by-you lookup."""
    store = store or {"by_sha": {}, "mods": {}}
    aliases = {k.lower(): v for k, v in (aliases or {}).items()}
    out = {"status": "unknown", "mod_id": None, "how": None, "matched": None, "candidates": [],
           "originals": [], "hints": {}, "query": query_for(plugins[0]) if plugins else ""}
    # 1. confirmed before
    for p in plugins:
        f = (paths or {}).get(p.lower())
        sha = (shas or {}).get(p.lower()) or (_sha1(f) if f else None)
        e = _store_hit(store, sha, p)
        if e:
            out.update(status="confirmed", mod_id=e["mod_id"], how="you", matched=p)
            if e.get("installed"):
                out["installed"] = dict(e["installed"], how="you")
            break
    # 2. where it came from
    if out["mod_id"] is None:
        mid = _provenance((record or {}).get("source"))
        if mid:
            out.update(status="known", mod_id=mid, how="download")
    # names to ask about: as it is now, and as it was originally
    names: list[str] = []
    for p in plugins:
        names.append(p)
        orig = aliases.get(p.lower())
        if orig and orig.lower() != p.lower():
            names.append(orig)
            out["originals"].append(orig)
    conv = ((record or {}).get("converted") or {}).get("names") or {}
    for orig, final in conv.items():
        if final.lower() in {p.lower() for p in plugins} and orig.lower() not in {n.lower() for n in names}:
            names.append(orig)
            out["originals"].append(orig)
    # 3. the LOOT masterlist
    found: dict[int, str] = {}
    titles: dict[int, str] = {}
    if masterlist is not None:
        for n in names:
            meta = masterlist.lookup(n)
            for u in (meta.urls if meta else []):
                mid = nexus_id(u)
                if mid and mid not in found:
                    found[mid] = n
                    if meta.url_names.get(u):
                        titles[mid] = re.sub(r"\s*\((?:Nexus Mods|Nexus)\)\s*$", "", meta.url_names[u]).strip()
    if out["mod_id"] is None and found:
        mid, n = next(iter(found.items()))      # LOOT lists the main page first
        out.update(status="likely", mod_id=mid, how="loot", matched=n)
    out["candidates"] = [{"mod_id": m, "via": n, "url": MOD_URL.format(mod_id=m), "title": titles.get(m)}
                         for m, n in found.items() if m != out["mod_id"]]
    # 4. a merge: the mods it lists inside
    for p in plugins:
        h = headers.get(p.lower())
        if h is None:
            continue
        if h.author:
            out["hints"]["author"] = h.author.strip()[:120]
        if h.description:
            out["hints"]["description"] = h.description.strip().splitlines()[0][:200]
        from .loot import merged_components
        comps = merged_components(h)
        if comps:
            inside = []
            for c in comps:
                meta = masterlist.lookup(c) if masterlist is not None else None
                ids = [nexus_id(u) for u in (meta.urls if meta else [])]
                ids = [i for i in ids if i]
                inside.append({"plugin": c, "mod_id": ids[0] if ids else None,
                               "url": MOD_URL.format(mod_id=ids[0]) if ids else None,
                               "search": search_url(query_for(c))})
            out["merge"] = inside
            if out["mod_id"] is None:
                out["status"] = "merge"
    if out["mod_id"] is not None and not out.get("installed"):
        nx = _provenance_nx((record or {}).get("source"))       # the file it was downloaded as
        try:
            if nx and int(nx["mod_id"]) == int(out["mod_id"]) and (nx.get("file_id") or nx.get("version")):
                out["installed"] = {k: nx.get(k) for k in ("file_id", "version") if nx.get(k)}
                out["installed"]["how"] = "download"
        except (TypeError, ValueError):
            pass
    if out["mod_id"] is not None:
        out["url"] = MOD_URL.format(mod_id=out["mod_id"])
        det = store.get("mods", {}).get(str(out["mod_id"]))
        if det:
            out["details"] = det
        elif titles.get(out["mod_id"]):
            out["title"] = titles[out["mod_id"]]          # the mod's name as LOOT writes it
    out["search"] = search_url(out["query"]) if out["query"] else None
    return out


def brief(d: dict) -> dict:
    """What a chip needs."""
    return {"status": d.get("status"), "mod_id": d.get("mod_id"), "url": d.get("url"), "search": d.get("search"),
            "title": (d.get("details") or {}).get("name") or d.get("title"), "query": d.get("query"),
            "merge": bool(d.get("merge"))}
