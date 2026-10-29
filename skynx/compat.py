"""Which version of a Nexus mod works on the Switch.

The newest file isn't always the right one: the Switch has no SKSE, so a mod
that starts shipping SKSE plugins (.dll), or needs Address Library, Papyrus
Extender, PapyrusUtil, JContainers, MCM Helper and the like, stops working.
For each file of a mod this reads what Nexus says about it (the list of files
inside the archive, its description and changelog) and gives a verdict:

  no      ships SKSE plugins (.dll / SKSE\\Plugins) in the main install
  warn    mentions SKSE or a SKSE-based framework, or has an installer option
          with SKSE plugins (pick the option without them)
  ok      only plugins, BSAs and game files; nothing about SKSE
  unknown nothing to read

Then it picks, among the files you can download (main, update and old
versions), the newest that isn't "no": the best for the Switch.
"""
from __future__ import annotations

import re

from .nexus import category_of

CANDIDATE_CATEGORIES = ("MAIN", "UPDATE", "OLD_VERSION")
FILE_PAGE = "https://www.nexusmods.com/skyrimspecialedition/mods/{mod_id}?tab=files&file_id={file_id}"

# needs the PC script extender (or something built on it)
_SKSE = re.compile(
    r"\b(skse(?:64)?|script\s*extender|address\s*library|commonlib(?:sse|ng)?|papyrus\s*extender|po3|powerofthree|"
    r"papyrusutil|jcontainers|mcm\s*helper|engine\s*fixes|\.dll|spid|spell\s*perk\s*item\s*distributor|"
    r"keyword\s*item\s*distributor|base\s*object\s*swapper|dynamic\s*animation\s*replacer|open\s*animation\s*replacer|"
    r"skyui)\b", re.I)
# runtime-specific builds (a warning, not a no: plugins and BSAs don't care)
# "no SKSE needed", "doesn't require SKSE", "SKSE not required"...
_NO_SKSE = re.compile(r"\b(?:no|without|doesn'?t\s+(?:need|require)|does\s+not\s+(?:need|require)|not\s+requir\w*)\b"
                      r"[^.;]{0,25}\bskse\b|\bskse\b[^.;]{0,15}\b(?:not|isn'?t)\s+(?:required|needed)\b", re.I)
_RUNTIME = re.compile(r"\b(1\.6\.\d{3,4}|1\.5\.97|runtime)\b", re.I)


def _strip_html(s: str) -> str:
    return re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", s or "")).strip()


def preview_paths(data) -> list[str] | None:
    """Every file path in a content_preview JSON (nested children lists).
    None when it can't be read."""
    if not isinstance(data, (dict, list)):
        return None
    out: list[str] = []

    def walk(node, prefix=""):
        if isinstance(node, list):
            for x in node:
                walk(x, prefix)
            return
        if not isinstance(node, dict):
            return
        name = str(node.get("name") or "")
        path = str(node.get("path") or (prefix + "/" + name if prefix else name)).replace("\\", "/")
        kids = node.get("children")
        if kids:
            walk(kids, path)
        elif str(node.get("type", "file")).lower() != "directory" and name:
            out.append(path)
    walk(data.get("children", data) if isinstance(data, dict) else data)
    return out


def assess(f: dict, paths: list[str] | None) -> dict:
    """Verdict for one Nexus file: {"verdict", "reasons": [[en, es], ...]}."""
    reasons: list[list[str]] = []
    verdict = "unknown"
    if paths is not None:
        low = [p.lower() for p in paths]
        dlls = [p for p in paths if p.lower().endswith(".dll")]
        installer = any(p.endswith("fomod/moduleconfig.xml") for p in low)
        if dlls:
            names = ", ".join(sorted({p.replace("\\", "/").rsplit("/", 1)[-1] for p in dlls}, key=str.lower)[:4])
            if installer:
                verdict = "warn"
                reasons.append(["It has installer options with SKSE plugins (.dll); on Switch pick the option without them.",
                                "Tiene opciones del instalador con plugins de SKSE (.dll); en Switch elige la opción sin ellos."])
            else:
                verdict = "no"
                reasons.append(["It ships SKSE plugins (.dll), which don't run on Switch: " + names,
                                "Trae plugins de SKSE (.dll), que no funcionan en Switch: " + names])
        else:
            verdict = "ok"
            reasons.append(["Only plugins, BSAs and game files: nothing that needs SKSE.",
                            "Solo plugins, BSA y archivos del juego: nada que necesite SKSE."])
    text = " ".join([str(f.get("name") or ""), _strip_html(str(f.get("description") or "")),
                     _strip_html(str(f.get("changelog_html") or ""))])
    if _NO_SKSE.search(text):
        reasons.append(["It says it works without SKSE.", "Dice que funciona sin SKSE."])
        text = _NO_SKSE.sub(" ", text)
    hits = sorted({m.group(0).strip() for m in _SKSE.finditer(text)}, key=str.lower)
    if hits and verdict != "no":
        verdict = "warn"
        reasons.append([f"Its description or changelog mentions {', '.join(hits[:4])}: check it doesn't need SKSE.",
                        f"Su descripción o changelog menciona {', '.join(hits[:4])}: revisa que no necesite SKSE."])
    rt = sorted({m.group(0) for m in _RUNTIME.finditer(text)})
    if rt:
        reasons.append([f"Mentions game runtime {', '.join(rt[:3])}.", f"Menciona la versión del juego {', '.join(rt[:3])}."])
    return {"verdict": verdict, "reasons": reasons}


def candidates(files: list[dict]) -> list[dict]:
    """Downloadable files that can be "the mod" (no optional add-ons), newest first."""
    pool = [f for f in files if isinstance(f, dict) and category_of(f) in CANDIDATE_CATEGORIES]
    return sorted(pool, key=lambda f: (f.get("uploaded_timestamp") or 0, f.get("file_id") or 0), reverse=True)


def choose(mod_id: int, files: list[dict], assessed: dict[int, dict], installed: dict | None = None) -> dict:
    """installed: {"file_id"} or {"version"} when known. Returns the rows
    (newest first, with verdicts), which one you have, the latest and the best
    for the Switch."""
    rows = []
    for f in candidates(files):
        fid = f.get("file_id")
        a = assessed.get(fid) or {"verdict": "unknown", "reasons": []}
        rows.append({"file_id": fid, "name": f.get("name") or f.get("file_name"), "version": f.get("version") or f.get("mod_version") or "",
                     "category": category_of(f), "uploaded": f.get("uploaded_time") or "", "ts": f.get("uploaded_timestamp") or 0,
                     "verdict": a["verdict"], "reasons": a["reasons"], "page": FILE_PAGE.format(mod_id=mod_id, file_id=fid)})
    have = None
    if installed:
        if installed.get("file_id"):
            have = next((r for r in rows if r["file_id"] == int(installed["file_id"])), None)
        if have is None and installed.get("version"):
            v = str(installed["version"]).strip().lower().lstrip("v")
            have = next((r for r in rows if str(r["version"]).strip().lower().lstrip("v") == v), None)
    mains = [r for r in rows if r["category"] in ("MAIN", "UPDATE")]
    latest = mains[0] if mains else (rows[0] if rows else None)
    # the newest one that surely works; else the newest to check by hand; else the latest (unverified)
    best = next((r for r in rows if r["verdict"] == "ok"), None) or \
        next((r for r in rows if r["verdict"] == "warn"), None)
    if best is None and latest is not None and latest["verdict"] == "unknown":
        best = latest
    if latest is None:
        status = "none"
    elif best is None:
        status = "all_skse"                 # every version needs SKSE
    elif have is None:
        status = "unknown_have"             # we don't know which one you have
    elif have["verdict"] == "no":
        status = "have_skse"                # yours ships SKSE plugins
    elif have["ts"] >= best["ts"]:
        status = "best" if best is latest else "kept"   # kept: the newer ones need SKSE
    else:
        status = "update"                   # a newer one that works on Switch
    return {"mod_id": mod_id, "rows": rows, "have": have, "latest": latest, "best": best, "status": status}


def check(client, mod_id: int, installed: dict | None = None, *, max_previews: int = 4) -> dict:
    """Ask Nexus for the mod's files and look inside the newest ones (their
    content listing) until one works on Switch. client: nexus.Client."""
    files = (client.files(mod_id) or {}).get("files") or []
    pool = candidates(files)
    assessed: dict[int, dict] = {}
    want = set()
    if installed and installed.get("file_id"):
        want.add(int(installed["file_id"]))
    looked = 0
    found_good = False
    for f in pool:
        fid = f.get("file_id")
        must = fid in want
        if found_good and not must:
            continue
        paths = None
        link = f.get("content_preview_link")
        if link and (looked < max_previews or must):
            looked += 1
            try:
                paths = preview_paths(client.preview(link))
            except Exception:  # noqa: BLE001  - the listing is a bonus; judge by the text
                paths = None
        assessed[fid] = assess(f, paths)
        if assessed[fid]["verdict"] == "ok":
            found_good = True
    return choose(mod_id, files, assessed, installed)
