"""Read-only audit of a pack. Produces findings, each with an optional fix.

Severity:
  critico  something will not load, or can crash the game
  aviso    probably wrong, or wastes space the author likely didn't intend
  ahorro   works, but could use less RAM, .ccc bytes or SD space
  info     worth knowing; nothing to do
"""
from __future__ import annotations

import difflib
import re
from collections import Counter, defaultdict
from dataclasses import asdict, dataclass, field
from pathlib import Path

from . import i18n
from . import knowledge as K
from .audio import classify as classify_audio
from .bsa import BsaArchive, read_bsa
from .ccc import entry_bytes
from .ini import ARCHIVE_KEYS, ARCHIVE_LIST_LIMIT
from .pack import Pack
from .textures import inspect as inspect_tex
from .texplan import DEFAULT_PRESET  # noqa: E402

SEV_ORDER = {"critico": 0, "aviso": 1, "ahorro": 2, "info": 3}


@dataclass
class Finding:
    code: str
    severity: str
    category: str          # key in i18n.CATEGORIES
    msg: str               # key in i18n.MSG
    subject: str = ""
    params: dict = field(default_factory=dict)
    items: list[str] = field(default_factory=list)
    fix: dict | None = None
    alt: list[dict] = field(default_factory=list)

    @property
    def id(self) -> str:
        return f"{self.code}:{self.subject}"

    def text(self, lang: str = "en") -> tuple[str, str]:
        p = dict(self.params)
        p["guess"] = i18n.note("guess", lang, p.pop("_guess", False))
        p["note"] = i18n.note("archives-note", lang, p.pop("_note", False))
        p["faces"] = i18n.note("faces-note", lang, p.pop("_faces", False))
        cov = p.pop("_covered", None)
        p["covered"] = i18n.note(f"covered-{cov}", lang, True) if cov else ""
        return i18n.msg(self.msg, lang, **p)

    def to_dict(self, lang: str = "en") -> dict:
        title, detail = self.text(lang)
        d = {"id": self.id, "code": self.code, "severity": self.severity,
             "category": i18n.cat(self.category, lang), "title": title, "detail": detail,
             "subject": self.subject, "items": self.items}
        d["fix"] = _fix_out(self.fix, lang)
        d["alt"] = [_fix_out(a, lang) for a in self.alt]
        return d

    @property
    def title(self) -> str:
        return self.text("en")[0]


def _fix_out(fix: dict | None, lang: str) -> dict | None:
    if not fix:
        return None
    out = dict(fix)
    out["label"] = i18n.label(fix["label_key"], lang, **fix.get("label_args", {}))
    return out


def _cc_not_in_game(pack: Pack, add, vdata: dict) -> None:
    """Creation Club lines of the load list whose plugin and BSA the game
    doesn't have (the Switch's own list names five like that). Only when the
    game list has the Creation Club: an incomplete copy proves nothing."""
    plugins = {n.lower() for n in vdata.get("plugins", {})}
    bsas = {n.lower() for n in vdata.get("bsas", {})}
    if sum(1 for n in plugins if n.startswith("cc")) < 20:
        return
    gone = []
    for e in pack.list_entries:
        low = e.lower()
        if e.startswith("#") or not low.startswith("cc") or low in pack.plugins:
            continue
        if low in plugins or (low.rsplit(".", 1)[0] + ".bsa") in bsas:
            continue
        gone.append(e)
    if gone:
        n_bytes = sum(len(e.encode("utf-8")) + 2 for e in gone)
        add("cc-not-in-game", "ahorro", "list", "cc-not-in-game", "ccc",
            {"n": len(gone), "bytes": n_bytes}, gone,
            fix=F("list_remove_many", "fix-cc-not-in-game", "seguro", {"n": len(gone)}, entries=gone))


def _off_without_file(pack: Pack, add) -> None:
    """Lines switched off with '#' whose plugin isn't in the pack any more
    (removed before 0.9.16 left them behind). The game skips them, but they
    clutter the load order and the console's list. Creation Club and game
    plugins are left alone: their files live in the game, not in Data."""
    game = {m.lower() for m in K.VANILLA_MASTERS + K.SWITCH_MASTERS}
    gone = []
    for e in pack.list_entries:
        if not e.startswith("#"):
            continue
        name = e.lstrip("#").strip()
        low = name.lower()
        if not name or low.startswith("cc") or low in game or low in pack.plugins:
            continue
        if Path(low).suffix not in (".esp", ".esm", ".esl"):
            continue
        gone.append(e)
    if gone:
        add("off-without-file", "info", "list", "off-without-file", "ccc",
            {"n": len(gone), "names": ", ".join(x.lstrip("#") for x in gone[:6])}, gone,
            fix=F("list_remove_many", "fix-off-without-file", "seguro", {"n": len(gone)}, entries=gone))


def F(kind: str, label_key: str, risk: str, label_args: dict | None = None, **kw) -> dict:
    return {"kind": kind, "label_key": label_key, "label_args": label_args or {},
            "risk": risk, **kw}


@dataclass
class AuditResult:
    pack: Pack
    findings: list[Finding] = field(default_factory=list)
    stats: dict = field(default_factory=dict)
    mods: list[dict] = field(default_factory=list)

    def add(self, *a, **kw) -> Finding:
        f = Finding(*a, **kw)
        self.findings.append(f)
        return f

    def sorted(self) -> list[Finding]:
        return sorted(self.findings, key=lambda f: (SEV_ORDER[f.severity], f.category, f.subject.lower()))

    def to_dict(self, lang: str = "en") -> dict:
        return {"findings": [f.to_dict(lang) for f in self.sorted()], "stats": self.stats,
                "mods": self.mods}


def report_markdown(report: "Report", lang: str = "en", title: str = "", stats_lines=()) -> str:
    """The Doctor's findings as Markdown, every detail included (no "+N"),
    grouped by category in the Doctor's order: to save or paste somewhere."""
    head = {"en": ("Doctor report", "Severity", "Fix offered", "risk", "safe", "review"),
            "es": ("Informe del Doctor", "Gravedad", "Arreglo ofrecido", "riesgo", "seguro", "revisar")}[
        "es" if lang == "es" else "en"]
    out = [f"# {head[0]}{': ' + title if title else ''}", ""]
    out += [f"- {line}" for line in stats_lines]
    if stats_lines:
        out.append("")
    groups: dict[str, list[Finding]] = {}
    for f in report.sorted():
        groups.setdefault(i18n.cat(f.category, lang), []).append(f)
    for cat, fs in groups.items():
        out += [f"## {cat} ({len(fs)})", ""]
        for f in fs:
            t, d = f.text(lang)
            sev = i18n.severity(f.severity, lang)
            out.append(f"### {t}")
            out.append(f"*{head[1]}: {sev}* · `{f.code}`" + (f" · {f.subject}" if f.subject else ""))
            out += ["", d]
            items = f.params.get("_all") or f.items
            if items:
                out.append("")
                out += ["- " + " ".join(str(i).split()) if "\n" in str(i) or "\r" in str(i) else f"- {i}"
                        for i in items]
            for fx in [f.fix] + list(f.alt or []):
                if fx:
                    lab = i18n.label(fx["label_key"], lang, **fx.get("label_args", {}))
                    risk = head[4] if fx.get("risk") == "seguro" else head[5]
                    out += ["", f"{head[2]}: **{lab}** ({head[3]}: {risk})"]
            out.append("")
    return "\n".join(out).rstrip() + "\n"


def norm_name(s: str) -> str:
    s = s.lower().replace("’", "'").replace("'", "_")
    s = re.sub(r"\.+(?=(esp|esm|esl|bsa)$)", ".", s)
    s = re.sub(r"\s+", " ", s).strip()
    return s


def _safe_name(name: str) -> str:
    from .rename import safe_name
    return safe_name(name)


def _diet_guess(rel: str, info) -> tuple[int, int]:
    """Texture memory now and after the default diet, from the header only."""
    from .texplan import max_side, plan_texture
    if info.container == "DDS":
        p = plan_texture(rel, info, DEFAULT_PRESET, False)
        return p.before, p.after
    before = info.est_bytes
    after = before
    if info.fmt.startswith("RGBA8"):
        after = before // 4
    side = max_side(rel, DEFAULT_PRESET)
    if side and info.width * info.height > side * side:
        after = int(after * side * side / (info.width * info.height))
    return before, after


def _mb(n: int) -> str:
    return f"{n / 2**20:.1f} MB"


def _near(target: str, pool: list[str]) -> tuple[str | None, bool]:
    """Best candidate for a misspelt name, and whether the match is exact after
    normalising (apostrophe vs underscore, repeated dots, spaces). Fuzzy matches
    are only suggestions: "Patch A" and "Patch B" look alike but aren't the same."""
    t = norm_name(target)
    for p in pool:
        if norm_name(p) == t:
            return p, True
    stem = Path(t).stem
    stems = {Path(norm_name(p)).stem: p for p in pool}
    if stem in stems:
        return stems[stem], False
    hit = difflib.get_close_matches(t, [norm_name(p) for p in pool], n=1, cutoff=0.92)
    if hit:
        for p in pool:
            if norm_name(p) == hit[0]:
                return p, False
    return None, False


class _BsaCache:
    def __init__(self):
        self.cache: dict[str, BsaArchive | Exception] = {}

    def get(self, path: Path) -> BsaArchive | None:
        k = str(path)
        if k not in self.cache:
            try:
                self.cache[k] = read_bsa(path)
            except Exception as e:  # noqa: BLE001
                self.cache[k] = e
        v = self.cache[k]
        return v if isinstance(v, BsaArchive) else None

    def error(self, path: Path) -> str | None:
        v = self.cache.get(str(path))
        return str(v) if isinstance(v, Exception) else None


# What's inside each BSA (texture headers, audio kinds) only changes when the
# file changes, so it's kept per (path, size, time): the quick check after a
# fix shows the same numbers as the last deep one without reading again.
_SCAN_CACHE: dict[tuple, dict] = {}


def _content_scan(bpath: Path, arc: BsaArchive, deep: bool) -> dict | None:
    try:
        st = bpath.stat()
        key = (str(bpath), st.st_size, st.st_mtime_ns)
    except OSError:
        return None
    if key in _SCAN_CACHE:
        return _SCAN_CACHE[key]
    if not deep:
        return None
    out = {"tex": 0, "tex_count": 0, "pc_dds": 0, "audio_pc": 0, "diet_before": 0, "diet_after": 0,
           "rgba_facetint": 0, "formats": Counter(), "audio": Counter()}
    with bpath.open("rb") as fh:
        for e in arc.entries:
            low = e.name.lower()
            if low.endswith(".dds"):
                try:
                    info = inspect_tex(arc.read_head(e, 256, fh))
                except Exception:  # noqa: BLE001
                    info = None
                if not info:
                    continue
                b, a = _diet_guess(e.path, info)
                out["diet_before"] += b
                out["diet_after"] += a
                out["tex"] += info.est_bytes
                out["tex_count"] += 1
                out["formats"][f"{info.container}|{info.fmt}"] += 1
                if info.container == "DDS":
                    out["pc_dds"] += 1
                if info.fmt.startswith("RGBA8") and "facetint" in e.folder.lower():
                    out["rgba_facetint"] += info.est_bytes
            elif low.endswith((".fuz", ".xwm", ".wav", ".mcadpcm")):
                try:
                    kind = classify_audio(low, arc.read_head(e, 32768, fh))
                except Exception:  # noqa: BLE001
                    kind = "?"
                out["audio"][kind] += 1
                if kind.startswith("pc-"):
                    out["audio_pc"] += 1
    for k in [k for k in _SCAN_CACHE if k[0] == key[0]]:
        del _SCAN_CACHE[k]
    _SCAN_CACHE[key] = out
    return out


def plugin_owners(arc: BsaArchive) -> dict[str, int]:
    owners: dict[str, int] = {}
    for e in arc.entries:
        folder = e.folder.lower() + "\\"
        for root in K.PLUGIN_FOLDER_ROOTS:
            if folder.startswith(root):
                o = folder[len(root):].split("\\", 1)[0]
                if o:           # a stray file right in sound\voice (.DS_Store from a Mac) isn't a plugin
                    owners[o] = owners.get(o, 0) + 1
    return owners


def run_audit(pack: Pack, deep: bool = True, progress=None, vanilla_dir=None,
              cache_dir=None) -> AuditResult:
    """vanilla_dir: folder with the console's vanilla BSAs (a setting the
    caller passes; None = not set). cache_dir: where to keep the vanilla
    index (defaults to vanilla_dir itself) and the textures each BSA's
    meshes use (memory only when None)."""
    R = AuditResult(pack)
    cache = _BsaCache()
    say = progress or (lambda *_: None)

    def add(code, sev, cat, msg, subject="", params=None, items=None, fix=None, alt=None):
        return R.add(code, sev, cat, msg, subject, params or {}, items or [], fix, alt or [])

    cc_missing: dict[str, list[str]] = {}     # plugin -> Creation Club masters not in the list

    # ------------------------------------------------------------------ layout
    if not pack.base_romfs:
        add("layout-base", "critico", "layout", "layout-base", params={"tid": K.TITLE_BASE})
        R.stats = {"mode": pack.mode, "root": str(pack.root)}
        return R
    if pack.mode == "?":
        add("layout-list", "critico", "layout", "layout-list", params={"aoc": K.TITLE_AOC})
    if pack.mode == "AE" and pack.plugin_list:
        add("layout-both", "info", "layout", "layout-both")
    for a in pack.archives:
        fx = None
        if a.suffix.lower() in (".zip", ".7z", ".rar"):
            fx = F("archive_extract", "fix-archive-extract", "revisar", {"name": a.name}, name=a.name)
        add("data-archive", "critico", "files", "data-archive", a.name, {"name": a.name}, fix=fx)
    from .fonts import only_fontconfig
    for d in pack.loose_dirs:
        if d.lower() == "interface" and only_fontconfig(pack.data_dir / d):
            continue            # a font's FontConfig.txt, loose on purpose (fonts.py)
        add("data-loose", "info", "files", "data-loose", d, {"name": d})
    for ini in pack.other_inis:
        add("ini-alt", "info", "inis", "ini-alt", ini.name, {"name": ini.name})

    entries = pack.list_entries
    lower_entries = [e.lower() for e in entries]
    plugin_names = {h.name.lower(): h.name for h in pack.plugins.values()}
    order = pack.load_order()
    pos = {}
    for i, (n, _src) in enumerate(order):
        pos.setdefault(n.lower(), i)
    active = set(pos)
    list_name = "Skyrim_aoc.ccc" if pack.mode == "AE" else "Plugins"
    archives = bool(pack.archives)

    # ------------------------------------------------------- list file format
    lst = pack.ccc if pack.mode == "AE" else pack.plugin_list
    if lst:
        if lst.has_bom:
            add("list-bom", "aviso", "list", "list-bom", list_name, {"list": list_name},
                fix=F("list_rewrite", "fix-bom", "seguro"))
        if lst.whitespace_issues:
            add("list-ws", "aviso", "list", "list-ws", list_name, items=lst.whitespace_issues,
                fix=F("list_rewrite", "fix-ws", "seguro"))
        if lst.newline == "mixed":
            add("list-nl", "info", "list", "list-nl", list_name,
                fix=F("list_rewrite", "fix-nl", "seguro"))
        if pack.mode == "SE" and lst.newline != "LF":
            add("list-se-nl", "aviso", "list", "list-se-nl", "Plugins",
                fix=F("list_rewrite", "fix-lf", "seguro", newline="LF"))
        for d in [k for k, v in Counter(lower_entries).items() if v > 1]:
            add("list-dup", "aviso", "list", "list-dup", d, {"name": d},
                fix=F("list_dedupe", "fix-dedupe", "seguro", entry=d))

    # ------------------------------------------------------- list vs files
    unlisted_plugins = [h.name for low, h in pack.plugins.items() if low not in active]
    active_norm = {norm_name(n): n for n, _ in order}
    leftovers = []
    for name in list(unlisted_plugins):
        twin = active_norm.get(norm_name(name))
        if twin and twin.lower() in pack.plugins:
            leftovers.append((name, twin))
            unlisted_plugins.remove(name)
    leftover_files = set()
    for name, twin in leftovers:
        files = [name]
        twin_stem, own_stem = Path(twin).stem, Path(name).stem
        for b in pack.bsas_for_plugin(name):
            twin_bsa = twin_stem + b.name[len(own_stem):]
            if twin_bsa.lower() in pack.bsas:
                files.append(b.name)
            else:
                add("bsa-unloaded-near", "critico", "bsa", "bsa-needs-rename", b.name,
                    {"name": b.name, "twin": twin, "want": twin_bsa},
                    fix=F("rename_files", "fix-rename-to", "seguro", {"to": twin_bsa},
                          renames=[{"from": b.name, "to": twin_bsa}]))
        leftover_files |= {b.name.lower() for b in pack.bsas_for_plugin(name)}
        leftover_files.add(name.lower())
        size = sum((pack.data_dir / f).stat().st_size for f in files)
        add("leftover", "aviso", "files", "leftover", name,
            {"name": name, "twin": twin, "size": _mb(size)}, items=files,
            fix=F("trash_files", "fix-trash", "seguro", files=files))
    for e in entries:
        low = e.lower()
        if low in plugin_names:
            if plugin_names[low] != e:
                add("list-case", "critico", "list", "list-case", e,
                    {"name": e, "file": plugin_names[low]},
                    fix=F("list_replace", "fix-write", "seguro", {"to": plugin_names[low]},
                          old=e, new=plugin_names[low]))
            continue
        if e.startswith("#"):
            add("list-disabled", "info", "list", "list-disabled", e, {"name": e[1:]})
            continue
        if pack.mode == "AE" and pack.is_cc(e):
            continue
        if e in K.VANILLA_MASTERS + K.SWITCH_MASTERS:
            continue
        cand, exact = _near(e, unlisted_plugins)
        risk = "seguro" if exact else "revisar"
        if cand:
            owners = set()
            for b in pack.bsas_for_plugin(cand):
                arc = cache.get(b)
                if arc:
                    owners |= set(plugin_owners(arc))
            params = {"name": e, "file": cand, "_guess": not exact}
            if e.lower() in owners:
                renames = [{"from": cand, "to": e}]
                for b in pack.bsas_for_plugin(cand):
                    renames.append({"from": b.name, "to": Path(e).stem + b.name[len(Path(cand).stem):]})
                add("list-missing-near", "critico", "list", "list-near-faces", e, params,
                    fix=F("rename_files", "fix-rename-files", risk, {"to": e}, renames=renames))
            else:
                add("list-missing-near", "critico", "list", "list-near", e, params,
                    fix=F("list_replace", "fix-write-list", risk, {"to": cand}, old=e, new=cand))
            unlisted_plugins.remove(cand)
            continue
        add("list-missing", "aviso", "list", "list-missing", e, {"name": e, "_note": archives},
            fix=F("list_remove", "fix-remove", "revisar" if archives else "seguro", entry=e))

    disabled = {e[1:].strip().lower() for e in entries if e.startswith("#")}
    ini_loaded = {b.lower() for v in pack.archive_lists().values() for b in v}
    for name in unlisted_plugins:
        if name.lower() in disabled:
            continue  # switched off on purpose with '#'
        h = pack.plugins[name.lower()]
        bsas = pack.bsas_for_plugin(name)
        if h.is_dummy and all(b.name.lower() in ini_loaded for b in bsas):
            # an empty plugin loads nothing by itself: its BSA was moved to the ini
            # (fix-dummy), maybe renamed short after that (fix-ini-shorten)
            continue
        size = h.size + sum(b.stat().st_size for b in bsas)
        add("plugin-unlisted", "aviso", "list", "plugin-unlisted", name,
            {"name": name, "list": list_name, "size": _mb(size)},
            fix=F("list_add", "fix-activate", "revisar", entry=name))

    for t in pack.stest_plugins():
        if t in K.VANILLA_MASTERS + K.SWITCH_MASTERS:
            continue
        if t.lower() not in pack.plugins:
            add("stest-missing", "aviso", "inis", "stest-missing", t, {"name": t})
        else:
            add("stest-extra", "info", "inis", "stest-extra", t, {"name": t})

    # ------------------------------------------------------- plugin headers
    hedr = Counter()
    from .converter import renamed_registry
    reg_names = renamed_registry(pack)
    for name, src in order:
        h = pack.plugins.get(name.lower())
        if not h:
            continue
        if h.error:
            add("plugin-bad", "critico", "plugins", "plugin-bad", h.name, {"name": h.name, "error": h.error})
            continue
        hedr[h.hedr_version] += 1
        if 0 < h.hedr_version < 1.0:
            add("plugin-oldrim", "aviso", "plugins", "plugin-oldrim", h.name,
                {"name": h.name, "ver": h.hedr_version})
        elif h.form_version and h.form_version < 44:
            add("plugin-form43", "info", "plugins", "plugin-form43", h.name,
                {"name": h.name, "ver": h.form_version})
        if h.name.lower() not in {m.lower() for m in K.VANILLA_MASTERS + K.SWITCH_MASTERS} \
                and not pack.is_cc(h.name) and _safe_name(h.name) != h.name:
            to = _safe_name(h.name)
            add("name-unsafe", "aviso", "plugins", "name-unsafe", h.name, {"name": h.name, "to": to},
                fix=None if (pack.data_dir / to).exists() else
                F("safe_rename", "fix-safe-name", "revisar", {"to": to}, **{"from": h.name, "to": to}))
        if pack.mode == "SE" and (h.extension == ".esl" or h.is_light_flag):
            to = h.name[:-4] + ".esp" if h.extension == ".esl" else h.name
            add("plugin-esl-se", "critico", "plugins", "plugin-esl-se", h.name, {"name": h.name},
                fix=None if to != h.name and (pack.data_dir / to).exists() else
                F("esl_to_esp", "fix-esl-esp", "revisar", {"to": to}, **{"from": h.name, "to": to}))
        if h.is_dummy and src == "lista":
            bsas = pack.bsas_for_plugin(h.name)
            used_as_master = any(h.name.lower() in {m.lower() for m in p.masters}
                                 for p in pack.plugins.values())
            if used_as_master or not pack.ini_for_key("sResourceArchiveList"):
                bsas = []
            changes = _dummy_move_changes(pack, cache, [b.name for b in bsas]) if bsas else []
            if changes:
                # moving it would change who wins some files (Noble Skyrim's
                # textures over the mods that load before it): leave it
                items, more = changes[:EXAMPLES_DUMMY], len(changes) - EXAMPLES_DUMMY
                add("plugin-dummy-keep", "info", "list", "plugin-dummy-keep", h.name,
                    {"name": h.name, "bytes": len(h.name) + 2, "n": len(changes)},
                    items=[f"{p} → {w}" for p, w in items] + ([f"(+{more})"] if more > 0 else []))
            else:
                add("plugin-dummy", "ahorro", "list", "plugin-dummy", h.name,
                    {"name": h.name, "bytes": len(h.name) + 2}, items=[b.name for b in bsas],
                    fix=F("dummy_to_ini", "fix-dummy", "seguro", entry=h.name,
                          bsas=[b.name for b in bsas]) if bsas else None)
        for m in h.masters:
            mp = pos.get(m.lower())
            sub = f"{h.name}>{m}"
            if mp is None:
                if pack.mode == "AE" and m.lower().startswith("cc"):
                    cc_missing.setdefault(h.name, []).append(m)
                else:
                    new = reg_names.get(m.lower())
                    add("master-missing", "critico", "masters", "master-missing", sub,
                        {"name": h.name, "master": m},
                        fix=F("master_retarget", "fix-master-retarget", "seguro", {"to": new},
                              plugin=h.name, map={m: new}) if new and new.lower() in pos else None)
            elif mp > pos[h.name.lower()] and src == "ini":
                add("master-order-ini", "info", "masters", "master-order-ini", sub,
                    {"name": h.name, "master": m})
            elif mp > pos[h.name.lower()]:
                add("master-order", "critico", "masters", "master-order", sub,
                    {"name": h.name, "master": m},
                    fix=F("list_move_after", "fix-move-after", "seguro",
                          {"name": h.name, "to": m}, entry=h.name, after=m)
                    if src == "lista" and order[mp][1] == "lista" else None)
    if pack.mode == "AE" and pack.ccc:
        used = pack.list_bytes
        sev = "critico" if used > K.CCC_BYTE_LIMIT else ("aviso" if used > K.CCC_BYTE_WARN else "info")
        add("ccc-bytes", sev, "list", "ccc-bytes", "ccc", {"used": used, "limit": K.CCC_BYTE_LIMIT})
        if used > K.CCC_BYTE_LIMIT - 600:
            from .bsafix import plan_list_shorten
            pairs = plan_list_shorten(pack)
            saved = sum(len(a) - len(b) for a, b in pairs)
            if pairs and saved >= 60:
                add("ccc-shorten", "ahorro", "list", "ccc-shorten", "ccc",
                    {"n": len(pairs), "saved": saved, "used": used},
                    items=[f"{a} → {b}" for a, b in pairs],
                    fix=F("plugins_shorten", "fix-list-shorten", "revisar", {"n": len(pairs), "saved": saved},
                          pairs=[list(x) for x in pairs]))

    # ------------------------------------------------------- inis
    lists = pack.archive_lists()
    ini_bsas = {b.lower() for v in lists.values() for b in v}
    for ini in pack.inis:
        for _s, k, lines in ini.duplicates():
            add("ini-dup", "info", "inis", "ini-dup", f"{ini.path.name}:{k}",
                {"ini": ini.path.name, "key": k, "lines": ", ".join(map(str, lines))})
        for key in ARCHIVE_KEYS:
            v = ini.get("Archive", key)
            if v is None:
                continue
            n = len(v)
            sub = f"{ini.path.name}:{key}"
            if n > 900 and key != "sArchiveToLoadInMemoryList":
                from .bsafix import plan_ini_shorten
                ren = plan_ini_shorten(pack, key)
                saved = sum(len(a) - len(b) for a, b in ren)
                fx = F("ini_shorten", "fix-ini-shorten", "revisar", {"n": len(ren), "saved": saved},
                       key=key, renames=[list(r) for r in ren]) if ren else None
            else:
                fx = None
            if n > ARCHIVE_LIST_LIMIT:
                add("ini-long", "critico", "inis", "ini-long", sub, {"key": key, "ini": ini.path.name, "n": n},
                    fix=fx)
            elif n > 900:
                add("ini-long", "aviso", "inis", "ini-nearly", sub, {"key": key, "ini": ini.path.name, "n": n},
                    fix=fx)
            if v.rstrip().endswith(","):
                add("ini-comma", "info", "inis", "ini-comma", sub, {"key": key, "ini": ini.path.name})
    # Language inis replace Skyrim.ini's lists on Switch (vanilla Skyrim_en.ini /
    # Skyrim_es.ini set sResourceArchiveList2 with their own voices; Ashiro's pack
    # lists its texture BSAs in Skyrim_en.ini).
    def _mods(items):
        return [b for b in items if not (b.lower().startswith("skyrim - ") or "relicsofhyrule" in b.lower())]
    main_ini = next((i for i in pack.inis if i.path.name.lower() == "skyrim.ini"), None)
    for key in ARCHIVE_KEYS:
        base_items = _mods(main_ini.archive_list(key)) if main_ini and main_ini.get("Archive", key) is not None else []
        langs = [i for i in pack.lang_inis if i.get("Archive", key) is not None]
        if not langs:
            if base_items and key == "sResourceArchiveList2" and not pack.lang_inis:
                add("lang-ini-missing", "aviso", "inis", "lang-ini-missing", key,
                    {"key": key, "items": ", ".join(base_items[:8])}, items=base_items)
            continue
        union = []
        for i in langs:
            for b in _mods(i.archive_list(key)):
                if b.lower() not in [u.lower() for u in union]:
                    union.append(b)
        for i in langs:
            have = {b.lower() for b in i.archive_list(key)}
            hidden = [b for b in base_items if b.lower() not in have]
            if hidden:
                add("lang-ini-hides", "critico", "inis", "lang-ini-hides", f"{i.path.name}:{key}",
                    {"ini": i.path.name, "key": key, "n": len(hidden), "items": ", ".join(hidden[:8])},
                    items=hidden,
                    fix=F("ini_copy_to_lang", "fix-lang-copy", "seguro", {"ini": i.path.name},
                          key=key, items=hidden, inis=[i.path.name]))
            missing = [b for b in union if b.lower() not in have and b not in hidden]
            if missing:
                add("lang-ini-differ", "aviso", "inis", "lang-ini-differ", f"{i.path.name}:{key}:differ",
                    {"key": key, "items": ", ".join(missing[:8])}, items=missing,
                    fix=F("ini_copy_to_lang", "fix-lang-copy", "seguro", {"ini": i.path.name},
                          key=key, items=missing, inis=[i.path.name]))
    lists = {k: v for k, v in lists.items()}
    for i in pack.lang_inis:   # count every BSA any language loads
        for key in ARCHIVE_KEYS:
            if i.get("Archive", key) is not None:
                cur = lists.setdefault(key, [])
                cur += [b for b in i.archive_list(key) if b.lower() not in [c.lower() for c in cur]]
    if main_ini:
        for key in ARCHIVE_KEYS:
            if main_ini.get("Archive", key) is not None:
                cur = lists.setdefault(key, [])
                cur += [b for b in main_ini.archive_list(key) if b.lower() not in [c.lower() for c in cur]]
    ini_bsas = {b.lower() for v in lists.values() for b in v}
    loaded_stems = {Path(n).stem.lower() for n, _ in order}
    for key, items in lists.items():
        for b in items:
            low = b.lower()
            if low.startswith("skyrim - ") or "relicsofhyrule" in low:
                continue
            if low not in pack.bsas:
                add("ini-bsa-missing", "aviso", "inis", "ini-bsa-missing", b,
                    {"name": b, "key": key, "_note": archives},
                    fix=F("ini_remove_archive", "fix-ini-remove",
                          "revisar" if archives else "seguro", key=key, item=b))
            else:
                stem = Path(low).stem
                if stem in loaded_stems or (stem.endswith(" - textures") and stem[:-11] in loaded_stems):
                    if _shares_with_ini(pack, cache, low, ini_bsas):
                        continue  # on purpose: in the ini it wins over another ini BSA (see conflicts.py)
                    add("ini-bsa-double", "info", "inis", "ini-bsa-double", b, {"name": b},
                        fix=F("ini_remove_archive", "fix-ini-remove", "revisar", key=key, item=b))

    disabled_stems = {Path(e[1:]).stem.lower() for e in entries if e.startswith("#")}
    for low, path in pack.bsas.items():
        stem = Path(low).stem
        auto = stem in loaded_stems or (stem.endswith(" - textures") and stem[:-11] in loaded_stems)
        if auto or low in ini_bsas or low in leftover_files:
            continue
        base = stem[:-11] if stem.endswith(" - textures") else stem
        if any(Path(n).stem == base for n in pack.plugins):
            continue  # reported with its plugin ("not active")
        if base in disabled_stems:
            add("bsa-disabled", "info", "bsa", "bsa-disabled", path.name, {"name": path.name})
            continue
        near, exact = _near(path.name, [Path(n).stem + ".bsa" for n, _ in order
                                        if not n.startswith("#")])
        if near and near.lower() in pack.bsas:
            add("leftover", "aviso", "files", "leftover-bsa", path.name,
                {"name": path.name, "twin": near}, items=[path.name],
                fix=F("trash_files", "fix-trash", "seguro", files=[path.name]))
        elif near:
            add("bsa-unloaded-near", "critico", "bsa", "bsa-unloaded-near", path.name,
                {"name": path.name, "near": near},
                fix=F("rename_files", "fix-rename-to", "seguro" if exact else "revisar",
                      {"to": near}, renames=[{"from": path.name, "to": near}]))
        else:
            add("bsa-unloaded", "aviso", "bsa", "bsa-unloaded", path.name,
                {"name": path.name, "size": _mb(path.stat().st_size)})

    # ------------------------------------------------------- inside BSAs
    deep_arcs: list = []
    tex_total = 0
    tex_by_mod: dict[str, int] = defaultdict(int)
    tex_counter: Counter = Counter()
    rgba_facetint = 0
    audio_counter: Counter = Counter()
    mods = []
    active_bsas = []
    for name, src in order:
        for b in pack.bsas_for_plugin(name):
            active_bsas.append((name, b))
    listed = {Path(n).stem.lower() for n, _ in order}
    for key, items in lists.items():
        for it in items:
            p = pack.bsas.get(it.lower())
            if p and Path(it).stem.lower() not in listed and (it, p) not in active_bsas:
                active_bsas.append((f"(ini) {it}", p))

    for i, (owner, bpath) in enumerate(active_bsas):
        say(bpath.name, i, len(active_bsas))
        arc = cache.get(bpath)
        if arc is None:
            add("bsa-bad", "critico", "bsa", "bsa-bad", bpath.name,
                {"name": bpath.name, "error": cache.error(bpath) or "?"})
            continue
        size = bpath.stat().st_size
        if size > 0x7FFFFFFF:
            add("bsa-big", "critico", "bsa", "bsa-big", bpath.name, {"name": bpath.name})
        mod = {"plugin": owner, "bsa": bpath.name, "size": size, "files": len(arc.entries),
               "tex": 0, "tex_count": 0, "pc_dds": 0, "audio_pc": 0}
        plugin = owner if not owner.startswith("(ini)") else None
        if plugin:
            owners = plugin_owners(arc)
            own = plugin.lower()
            orphans = {o: n for o, n in owners.items()
                       if o != own and o not in active and not o.startswith("cc")
                       and o not in {m.lower() for m in K.VANILLA_MASTERS + K.SWITCH_MASTERS}}
            if owners and own not in owners and orphans:
                def core(s): return "".join(c for c in Path(s).stem.lower() if c.isalpha())
                tgt = core(plugin)
                old = sorted(orphans.items(), key=lambda kv: (
                    tgt in core(kv[0]) or core(kv[0]) in tgt, kv[1]), reverse=True)[0][0]
                faces = any(e.folder.lower().startswith(r + old)
                            for e in arc.entries for r in (
                                "meshes\\actors\\character\\facegendata\\facegeom\\",
                                "textures\\actors\\character\\facegendata\\facetint\\"))
                taken = (pack.data_dir / old).exists()
                fix = None if taken else F("rename_plugin", "fix-restore-name", "seguro",
                                           {"to": old}, **{"from": plugin, "to": old})
                alt = [] if faces else [F("bsa_move_voices", "fix-move-voices", "revisar",
                                          {"to": own}, bsa=bpath.name, old=old, new=own)]
                add("bsa-owner", "critico", "bsa", "bsa-owner", bpath.name,
                    {"name": bpath.name, "plugin": plugin, "n": orphans[old], "old": old,
                     "cost": len(old) - len(plugin), "_faces": faces},
                    items=[f"{o} ({n})" for o, n in orphans.items()], fix=fix, alt=alt)
            elif orphans:
                add("bsa-dead", "info", "bsa", "bsa-dead", bpath.name, {"name": bpath.name},
                    items=[f"{o} ({n})" for o, n in orphans.items()])
        junk = [e.path for e in arc.entries if e.name.lower().endswith(K.JUNK_IN_BSA)
                and not e.folder.lower().startswith("interface")]
        if junk:
            add("bsa-junk", "ahorro", "bsa", "bsa-junk", bpath.name,
                {"name": bpath.name, "n": len(junk)}, items=junk[:30],
                fix=F("bsa_drop_junk", "fix-drop-junk", "seguro", {"n": len(junk)},
                      bsa=bpath.name, items=junk))
        diet_before = diet_after = 0
        if deep:
            deep_arcs.append((bpath, arc))
        scan = _content_scan(bpath, arc, deep)
        if scan:
            diet_before, diet_after = scan["diet_before"], scan["diet_after"]
            for k in ("tex", "tex_count", "pc_dds", "audio_pc"):
                mod[k] += scan[k]
            mod["diet_after"] = diet_after
            tex_counter.update({tuple(k.split("|", 1)): v for k, v in scan["formats"].items()})
            audio_counter.update(scan["audio"])
            rgba_facetint += scan["rgba_facetint"]
            mod["scanned"] = True
        tex_total += mod["tex"]
        tex_by_mod[bpath.name] += mod["tex"]
        mods.append(mod)
        if mod["pc_dds"]:
            add("tex-pc", "aviso", "textures", "tex-pc", bpath.name, {"name": bpath.name, "n": mod["pc_dds"]})
        if mod["audio_pc"]:
            add("audio-pc", "aviso", "audio", "audio-pc", bpath.name, {"name": bpath.name, "n": mod["audio_pc"]})
        if diet_before - diet_after >= 8 * 2**20:
            add("tex-diet", "ahorro", "textures", "tex-diet", bpath.name,
                {"name": bpath.name, "before": _mb(diet_before), "after": _mb(diet_after)},
                fix=F("diet_bsa", "fix-diet", "revisar", {"after": _mb(diet_after)},
                      bsa=bpath.name, preset=DEFAULT_PRESET, bc1=True))

    if rgba_facetint > 20 * 2**20 and not any(f.code == "tex-diet" for f in R.findings):
        add("tex-facetint", "ahorro", "textures", "tex-facetint", "facetint", {"size": _mb(rgba_facetint)})
    if deep and deep_arcs:
        from .bsafix import scan_tints
        say("FaceGen", 0, 0)
        for bname, broken in scan_tints(pack, deep_arcs).items():
            fixable = [b for b in broken if b["new"]]
            add("tint-broken", "aviso", "bsa", "tint-broken", bname,
                {"name": bname, "n": len(broken), "old": broken[0]["old"]},
                items=[f"{b['nif']} → {b['tint']}" for b in broken[:20]],
                fix=F("fix_tints", "fix-tints", "seguro", {"n": len(fixable)}, bsa=bname,
                      fixes=[{"nif": b["nif"], "old": b["old"], "new": b["new"]} for b in fixable])
                if fixable else None)
    _koka_checks(pack, add, order, entries, list_name, active_bsas, cache, deep)
    _font_checks(pack, add, active_bsas, cache)
    # ------------------------------------------------------- requirements, duplicates
    from . import duplicates as DUP
    from . import requirements as REQ
    from . import vanilla as V
    vcache = cache_dir or vanilla_dir
    vstate = V.status(vanilla_dir, vcache)
    vidx = None
    vrefs: set[str] = set()
    if deep and vstate == "ok":
        say("vanilla", 0, 0)
        try:
            vidx = V.index(vanilla_dir, vcache, progress=say) or None
            vrefs = V.game_refs(vanilla_dir, vcache) if vidx else set()
        except OSError:
            vidx = None
        if vidx is None:
            vstate = "empty"
        else:
            vsum = V.summary(vanilla_dir, vcache)
            if vsum.get("missing_core"):
                add("req-vanilla-partial", "info", "requirements", "req-vanilla-partial", "vanilla",
                    {"names": ", ".join(vsum["missing_core"]), "n": len(vsum["missing_core"])},
                    vsum["missing_core"])
    # the game's own scripts (its BSAs load from the ini): wanted by the BSA order
    # checks in the quick check too, so the index is read here when it's cached
    vpex: set[str] = set()
    if vstate == "ok":
        try:
            # only the BSAs the ini loads: the Creation Club's load by their plugins,
            # so USCCCP's fixes to CC scripts win over them as on PC
            vi = V.ini_files(vanilla_dir, vcache)
            vpex = {x for x in (vi or ()) if x.endswith(".pex")}
        except OSError:
            vpex = set()
    _ini_priority_checks(pack, add, cache, vpex)
    if vstate == "ok" and pack.mode == "AE":
        _cc_not_in_game(pack, add, V.load(vanilla_dir, vcache))
    _off_without_file(pack, add)
    if vpex:
        # "loads twice" is on purpose when the BSA is in the ini to win over the
        # game's own scripts (Quick Start's MQ101 fragment)
        R.findings = [f for f in R.findings if not (
            f.code == "ini-bsa-double" and f.subject.lower() in pack.bsas
            and _bsa_paths(cache, pack.bsas[f.subject.lower()]) & vpex)]
    extra = [b for _o, b in active_bsas]
    for r in REQ.check(pack, deep=deep, vanilla=vidx, get_arc=cache.get, extra_bsas=extra,
                       vanilla_refs=vrefs, vanilla_state=vstate, vanilla_dir=str(vanilla_dir or ""),
                       cache_dir=cache_dir, progress=say):
        add(r["code"], r["severity"], "requirements", r["msg"], r["subject"], r["params"],
            r["items"], r["fix"])
    if deep:
        _names_checks(pack, add, vanilla_dir)
        from . import scriptcheck as SC
        SC.check_scripts(pack, add, cache, vpex, active, say)
        SC.check_audio(pack, add, cache, say)
    # A BSA the ini asks for that isn't there: what matters is whether its files
    # are, not its name (converters often join several BSAs into one). With the
    # base game known, the requirement check just above looked for every script,
    # mesh and texture the plugins use in every loaded BSA.
    gone = [f for f in R.findings if f.code == "ini-bsa-missing"]
    if gone and deep:
        gaps = [f for f in R.findings if f.code in ("req-script-missing", "req-mesh-missing",
                                                    "req-tex-missing", "req-script-parent")]
        for f in gone:
            if vidx is None:
                f.params["_covered"] = "unknown"
            elif gaps:
                f.params["_covered"] = "gaps"
            else:
                f.params["_covered"] = "yes"
                f.severity = "info"
                if f.fix and not f.params.get("_note"):
                    f.fix = dict(f.fix, risk="seguro")
    # Creation Club masters missing from the list: one finding per plugin, with
    # what adding them costs in the .ccc (it has a hard size limit)
    if cc_missing:
        now = pack.list_bytes
        line_of = {e.lower(): e for e in pack.list_entries}
        for name, ms in cc_missing.items():
            cost = sum(len(m.encode("cp1252", "replace")) + 2 for m in ms)
            after = now + cost
            fits, near = after <= K.CCC_BYTE_LIMIT, after > K.CCC_BYTE_WARN
            entry = line_of.get(name.lower(), name)
            add("master-cc", "critico", "masters", "master-cc", name,
                {"name": name, "n": len(ms), "list": ", ".join(ms), "now": now, "after": after,
                 "limit": K.CCC_BYTE_LIMIT}, items=ms,
                fix=F("list_insert_before", "fix-add-cc" if len(ms) == 1 else "fix-add-cc-n",
                      "revisar" if near else "seguro", {"to": ms[0], "n": len(ms)},
                      entries=ms, before=name) if fits else None,
                alt=[F("list_remove", "fix-take-out", "revisar", {"name": name}, entry=entry)])

    for r in DUP.find_duplicates(pack, get_arc=cache.get, extra_bsas=extra):
        add(r["code"], r["severity"], "duplicates", r["msg"], r["subject"], r["params"],
            r["items"], r["fix"], r.get("alt"))

    # duplicates the user chose to keep
    from .dupfix import load_ignored
    ignored = load_ignored(pack)
    if ignored:
        hidden = [f for f in R.findings if f.id in ignored]
        if hidden:
            R.findings = [f for f in R.findings if f.id not in ignored]
            add("dup-ignored", "info", "duplicates", "dup-ignored", "", {"n": len(hidden)},
                [f.subject for f in hidden],
                F("dup_unignore", "fix-dup-unignore", "seguro", ids=[f.id for f in hidden]))

    big = sorted(tex_by_mod.items(), key=lambda kv: -kv[1])[:8]
    R.stats = {
        "mode": pack.mode,
        "root": str(pack.root),
        "list_name": list_name,
        "list_entries": len(entries),
        "list_bytes": pack.list_bytes,
        "list_limit": K.CCC_BYTE_LIMIT if pack.mode == "AE" else None,
        "cc_entries": sum(1 for e in entries if pack.mode == "AE" and pack.is_cc(e)),
        "plugins_active": sum(1 for n, s in order if n.lower() in pack.plugins),
        "plugins_total": len(pack.plugins),
        "bsas_total": len(pack.bsas),
        "data_bytes": pack.data_size(),
        "ini_lists": {k: {"chars": len(", ".join(v)), "items": len(v)} for k, v in lists.items()},
        "tex_bytes": tex_total,
        "tex_top": [{"bsa": k, "bytes": v} for k, v in big],
        "tex_formats": {f"{c} {f}": n for (c, f), n in tex_counter.most_common()},
        "audio": dict(audio_counter),
        "hedr": {str(k): v for k, v in hedr.items()},
        "counts": dict(Counter(f.severity for f in R.findings)),
        "vanilla": {"state": vstate, "files": len(vidx) if vidx else 0},
    }
    R.mods = sorted(mods, key=lambda m: -m["tex"])
    return R


# ---------------------------------------------------------------- KokaNX (Oct 2026)
MEMORY_KEY = "sArchiveToLoadInMemoryList"


def _hex(ids) -> str:
    return ", ".join(f"{i:08X}" for i in ids) or "-"


def _names_checks(pack: Pack, add, vanilla_dir) -> None:
    """Names in another language (names.py): Russian NPC names from a translated
    The Ordinary Women. The fix puts back the game's names where it can read them."""
    from . import names as NM
    from . import vanilla as V
    codes = [i.path.stem.lower().split("_", 1)[1] for i in pack.lang_inis if "_" in i.path.stem]
    lang = NM.LATIN_LANGS.get(codes[0] if codes else "en")
    if not lang:
        return                                   # a game in Russian or Japanese: nothing is foreign
    masters: dict[str, Path] = {}
    places: list[Path] = []
    if vanilla_dir and Path(vanilla_dir).is_dir():
        vf = V.bsa_folder(Path(vanilla_dir))
        places.append(vf)
        for p in vf.iterdir():
            if p.suffix.lower() in (".esm", ".esl", ".esp"):
                masters[p.name.lower()] = p
    for h in pack.plugins.values():
        masters[h.name.lower()] = h.path
    if pack.data_dir:
        places.append(pack.data_dir)
    for name, src in pack.load_order():
        h = pack.plugins.get(name.lower())
        if src == "juego" or name.startswith("#") or not h or h.error:
            continue
        try:
            found = NM.scan(h.path)
        except Exception:  # noqa: BLE001
            continue
        if not found:
            continue
        back = NM.game_names(found, masters, lang, places)
        items = [f"{f['edid'] or hex(f['formid'])}: {f['name']}" + (f" → {back[f['formid']]}" if f["formid"] in back else "")
                 for f in found]
        add("names-foreign", "aviso", "plugins", "names-foreign", h.name,
            {"name": h.name, "n": len(found), "fixable": len(back), "example": found[0]["name"],
             "_all": items},
            items=items[:20] + ([f"(+{len(items) - 20})"] if len(items) > 20 else []),
            fix=F("names_fix", "fix-names", "seguro", {"n": len(back)}, plugin=h.name,
                  names=[[fid, nm] for fid, nm in sorted(back.items())]) if back else None)


def _font_checks(pack: Pack, add, active_bsas, cache) -> None:
    """Font mods (fonts.py): FontConfig.txt has to be loose, and every font
    library it names has to be somewhere."""
    from . import fonts as FN
    idir = pack.data_dir / "Interface" if pack.data_dir else None
    loose_fc = next((p for p in (idir.iterdir() if idir and idir.is_dir() else []) if p.name.lower() == FN.NAME), None)
    have = set()
    in_bsa = []
    for _owner, bpath in active_bsas:
        arc = cache.get(bpath)
        if arc is None:
            continue
        for e in arc.entries:
            low = e.path.lower()
            if low.startswith("interface\\"):
                have.add(low)
                if low == "interface\\" + FN.NAME:
                    in_bsa.append(bpath.name)
    if idir and idir.is_dir():
        for p in idir.rglob("*"):
            if p.is_file():
                have.add("interface\\" + str(p.relative_to(idir)).replace("/", "\\").lower())
    if in_bsa and loose_fc is None:
        add("font-in-bsa", "aviso", "bsa", "font-in-bsa", in_bsa[0], {"bsa": in_bsa[0]},
            fix=F("font_loose", "fix-font-loose", "seguro", bsa=in_bsa[0]))
    if loose_fc is not None:
        try:
            fc = FN.read(loose_fc)
        except OSError:
            return
        missing = [lib for lib in fc.libs if lib not in have and lib not in FN.VANILLA_LIBS]
        if missing:
            add("font-missing-lib", "critico", "bsa", "font-missing-lib", "FontConfig.txt",
                {"n": len(missing), "items": ", ".join(m.rsplit("\\", 1)[-1] for m in missing[:5])},
                items=[m.rsplit("\\", 1)[-1] for m in missing])


def _koka_checks(pack: Pack, add, order, entries, list_name, active_bsas, cache, deep) -> None:
    """KokaNX's tests and advice: mod BSAs in the in-memory list, HEDR 1.71 on
    SE, missing SEQ files, and where USSEP goes."""
    from .ussep import PLUGIN as USSEP, first_slot, is_ussep_bsa
    game = {m.lower() for m in K.VANILLA_MASTERS + K.SWITCH_MASTERS + K.AE_CC_PLUGINS}

    # 1. mod BSAs kept in memory (the game's own entries stay)
    items, inis = [], []
    for ini in pack.inis:
        if ini.get("Archive", MEMORY_KEY) is None:
            continue
        mods = [b for b in ini.archive_list(MEMORY_KEY) if not K.is_vanilla_bsa(b)]
        if mods:
            inis.append(ini.path.name)
            items += [b for b in mods if b.lower() not in {i.lower() for i in items}]
    if items:
        size = sum(pack.bsas[b.lower()].stat().st_size for b in items if b.lower() in pack.bsas)
        add("ini-memory-mods", "ahorro", "inis", "ini-memory-mods", MEMORY_KEY,
            {"n": len(items), "inis": ", ".join(inis), "items": ", ".join(items[:8]), "size": _mb(size),
             "size_en": f" (about {_mb(size)})" if size else "", "size_es": f" (unos {_mb(size)})" if size else ""},
            items=items, fix=F("ini_memory_out", "fix-memory-out", "revisar", items=items, inis=inis))

    # 2. HEDR 1.71 on SE
    if pack.mode == "SE":
        from .records import own_low_formids
        for name, _src in order:
            h = pack.plugins.get(name.lower())
            if not h or h.error or name.lower() in game or round(h.hedr_version, 2) != 1.71:
                continue
            try:
                low = own_low_formids(h.path)
            except Exception:  # noqa: BLE001
                low = 0
            add("plugin-hedr171-se", "aviso", "plugins", "plugin-hedr171-se", h.name,
                {"name": h.name, "low_en": i18n.msg("hedr-low", "en", k=low)[1] if low else "",
                 "low_es": i18n.msg("hedr-low", "es", k=low)[1] if low else ""},
                fix=F("plugin_hedr", "fix-hedr-170", "revisar", plugin=h.name, old=1.71,
                      new=K.HEDR_SE))

    # 2b. any edition: record IDs below 0x800 (extended ESL range, PC 1.6.1130+);
    # the Switch build is from 2022 (HEDR 1.71 alone loads fine: KokaNX's packs
    # carry Summermyst 4 that way)
    if pack.mode != "SE":
        from .records import own_low_formids
        for name, _src in order:
            h = pack.plugins.get(name.lower())
            if not h or h.error or name.lower() in game or round(h.hedr_version, 2) < 1.71:
                continue
            try:
                low = own_low_formids(h.path)
            except Exception:  # noqa: BLE001
                low = 0
            if low:
                add("plugin-lowid-nx", "aviso", "plugins", "plugin-lowid-nx", h.name, {"name": h.name, "n": low})

    # 3. SEQ files (deep: reads the quests of every plugin)
    if deep:
        _seq_checks(pack, add, order, active_bsas, cache, game)

    # 4. USSEP first: its BSAs right after the game's in every list, its plugin
    # right after the Creation Club lines (AE) or at the top (SE)
    out_of_place, moved = [], []
    for ini in pack.inis:
        for key in ("sResourceArchiveList", "sResourceArchiveList2"):
            if ini.get("Archive", key) is None:
                continue
            cur = ini.archive_list(key)
            us = [b for b in cur if is_ussep_bsa(b)]
            if us and K.after_vanilla(cur, us) != cur:
                out_of_place.append({"ini": ini.path.name, "key": key, "items": us})
                moved += [b for b in us if b not in moved]
    if out_of_place:
        add("ussep-bsa-order", "aviso", "inis", "ussep-bsa-order", "ussep-bsas",
            {"where": "; ".join(f"{p['ini']} {p['key']}" for p in out_of_place)}, items=moved,
            fix=F("ussep_ini_order", "fix-ussep-bsas", "revisar", places=out_of_place))
    low = [e.lower() for e in entries]
    if USSEP.lower() in low:
        idx = low.index(USSEP.lower())
        rest, slot = first_slot(pack, entries)
        cc = {c.lower() for c in K.AE_CC_PLUGINS}
        before = [e for e in rest[slot:idx] if not e.startswith("#") and e.lower() not in cc
                  and e.lower() not in game and not (pack.mode == "AE" and pack.is_cc(e))]
        if idx > slot and before:
            add("ussep-first", "aviso", "list", "ussep-first", entries[idx],
                {"list": list_name, "name": entries[idx], "n": len(before), "before": before[0]},
                items=before,
                fix=F("list_move_first", "fix-move-first", "revisar", {"name": entries[idx]},
                      entry=entries[idx]))


EXAMPLES_DUMMY = 8


def _dummy_move_changes(pack: Pack, cache, names: list[str]) -> list[tuple[str, str]]:
    """What would change if these plugin-loaded BSAs moved to the ini (the
    dummy_to_ini fix): [(path, who wins it afterwards)] for every file of
    theirs whose winner changes. Textures and meshes: the ini loads first and
    plugin BSAs win, so the moved BSA would lose to plugin BSAs loading before
    its plugin. Scripts: the ini wins, so it would start winning over them."""
    from .conflicts import ORDER_KEYS, _lists, load_order_bsas
    from .fixes import _archive_key
    moving = [n.lower() for n in names]
    lists = _lists(pack, "en")

    def after(scripts: bool) -> list[str]:
        ini: list[str] = []
        for k in ORDER_KEYS:
            ini += [b.lower() for b in lists.get(k, [])] + [b for b in moving if _archive_key(b) == k]
        ini = [b for b in ini if b in pack.bsas and not b.startswith("skyrim - ")]
        rest = [n.lower() for n, _p, _s in load_order_bsas(pack, scripts=scripts)]
        plug = [b for b in rest if b not in ini]
        order = plug + ini if scripts else ini + plug
        seen: set[str] = set()
        return [b for b in order if not (b in seen or seen.add(b))]

    known: dict[str, set[str]] = {}

    def files(o: str) -> set[str]:
        if o not in known:
            known[o] = _bsa_paths(cache, pack.bsas[o]) if o in pack.bsas else set()
        return known[o]

    out: list[tuple[str, str]] = []
    for scripts in (False, True):
        before = [n.lower() for n, _p, _s in load_order_bsas(pack, scripts=scripts)]
        later = after(scripts)
        for b in moving:
            mine = {x for x in files(b) if x.endswith(".pex") == scripts}
            sharing = [o for o in dict.fromkeys(before + later) if o != b and files(o) & mine]
            for path in sorted(mine):
                holders = {b} | {o for o in sharing if path in files(o)}
                if len(holders) == 1:
                    continue
                w0 = [o for o in before if o in holders][-1:]
                w1 = [o for o in later if o in holders][-1:]
                if w0 != w1 and b in (w0 + w1):
                    out.append((path, pack.bsas[w1[0]].name if w1 and w1[0] in pack.bsas else ""))
    return out


def _bsa_paths(cache, path) -> set[str]:
    """The files a BSA gives the game (script sources left out)."""
    arc = cache.get(path)
    if arc is None:
        return set()
    return {e.path.lower() for e in arc.entries if not e.path.lower().startswith("scripts\\source\\")}


def _shares_with_ini(pack: Pack, cache, low: str, ini_bsas: set[str]) -> bool:
    mine = _bsa_paths(cache, pack.bsas[low])
    return bool(mine) and any(o != low and o in pack.bsas and mine & _bsa_paths(cache, pack.bsas[o])
                              for o in ini_bsas)


def _ini_priority_checks(pack: Pack, add, cache, vanilla_pex: set[str] = frozenset()) -> None:
    """On Switch a BSA from the ini wins over one a plugin loads by its name
    (conflicts.py). A plugin's BSA that shares files with an ini BSA loses them,
    the other way round from PC, where the mod was made to win: Growl's and
    Sacrosanct's scripts lost to KokaNX's USSEP.bsa. Putting the plugin's BSA in
    the ini, after the others, gives back the PC result."""
    from .conflicts import load_order_bsas
    order = load_order_bsas(pack, scripts=True)
    ini = [(n, pth) for n, pth, src in order if src.startswith("ini:")]
    # Only scripts: for them the ini wins on Switch (Growl, Sacrosanct, Quick
    # Start). Textures and meshes follow the PC order (Noble Skyrim's showed).
    ini_paths = [(n, {x for x in _bsa_paths(cache, pth) if x.endswith(".pex")}) for n, pth in ini]
    if vanilla_pex:
        # proven on the console for scripts (Growl, Quick Start); textures and
        # meshes against the game's own BSAs aren't known yet, so only scripts
        ini_paths.insert(0, ("Skyrim - Misc.bsa", vanilla_pex))
    if not ini_paths:
        return
    losers, items = [], []
    for n, pth, src in order:
        if not src.startswith("plugin:"):
            continue
        mine = {x for x in _bsa_paths(cache, pth) if x.endswith(".pex")}
        if not mine:
            continue
        lost: dict[str, set[str]] = {}
        for w, theirs in ini_paths:
            hit = mine & theirs
            if hit:
                lost[w] = hit
        if not lost:
            continue
        files = set().union(*lost.values())
        scripts = sum(1 for f in files if f.endswith(".pex"))
        losers.append(n)
        what = (f"{scripts} scripts" if scripts else f"{len(files)} files")
        items.append(f"{n}: {len(files)} ({', '.join(sorted(lost))})"
                     + (f" · {what}" if scripts else ""))
    if not losers:
        return
    add("bsa-loses-to-ini", "aviso", "bsa", "bsa-loses-to-ini", "ini-priority",
        {"n": len(losers), "list": ", ".join(losers[:6])}, items=items,
        fix=F("ini_add_archives", "fix-ini-add-after", "revisar", {"n": len(losers)},
              items=[[("sResourceArchiveList2" if b.lower().endswith(" - textures.bsa")
                       else "sResourceArchiveList"), b] for b in losers]))


def _mod_ini_bsa(pack: Pack, plugin: str):
    """The BSA a converted mod loads through the ini (TonalB.bsa for Tonal.esp),
    taken from the mod's own record: the SEQ goes in there instead of a new BSA."""
    from .builder import load_mods
    try:
        mods = load_mods(pack)
    except Exception:  # noqa: BLE001
        return None
    in_ini = {b.lower() for v in pack.archive_lists().values() for b in v}
    for rec in mods.values():
        if not isinstance(rec, dict) or not any(x.lower() == plugin.lower() for x in rec.get("plugins") or []):
            continue
        cands = [pack.bsas.get(b.lower()) for b in rec.get("bsas") or [] if b.lower() in in_ini]
        cands = [c for c in cands if c is not None and not c.stem.lower().endswith(" - textures")]
        return cands[0] if len(cands) == 1 else None
    return None


def _seq_checks(pack: Pack, add, order, active_bsas, cache, game) -> None:
    from .bsafix import seq_path
    from .records import parse_seq, quest_scan, seq_wanted
    # every seq\*.seq that loads: ini BSAs first, then the plugins' own, loose last (it wins)
    found: dict[str, tuple[str, bytes | None, object, object]] = {}
    for owner, bpath in sorted(active_bsas, key=lambda ob: not ob[0].startswith("(ini)")):
        arc = cache.get(bpath)
        if arc is None:
            continue
        for e in arc.entries:
            if e.folder.lower() == "seq" and e.name.lower().endswith(".seq"):
                found[e.name.lower()] = (bpath.name, None, arc, e)
    loose = next((p for p in pack.data_dir.iterdir() if p.is_dir() and p.name.lower() == "seq"), None) \
        if pack.data_dir else None
    if loose:
        for f in loose.iterdir():
            if f.is_file() and f.suffix.lower() == ".seq":
                found[f.name.lower()] = ("Data\\seq", f.read_bytes(), None, None)

    def master_scan(m: str):
        h = pack.plugins.get(m.lower())
        return quest_scan(h.path) if h else None

    for name, _src in order:
        h = pack.plugins.get(name.lower())
        if not h or h.error or h.is_dummy or name.lower() in game:
            continue
        qs = quest_scan(h.path)
        if qs.error:
            continue
        want, unknown = seq_wanted(h.path, master_scan)
        rel = seq_path(h.name)
        key = rel.split("\\", 1)[1]
        have = found.get(key)
        stem = Path(h.name).stem
        if have is None:
            if not want:
                continue
            own = next((b for b in pack.bsas_for_plugin(h.name) if b.name.lower() == stem.lower() + ".bsa"),
                       None) or _mod_ini_bsa(pack, h.name)
            target = own.name if own else stem + ".bsa"
            add("seq-missing", "aviso", "plugins", "seq-missing", h.name,
                {"name": h.name, "n": len(want), "seq": key}, items=[f"{i:08X}" for i in want],
                fix=F("seq_add", "fix-seq-add", "revisar", {"bsa": target}, plugin=h.name,
                      formids=want, bsa=target, create=own is None))
            continue
        where, raw, arc, e = have
        try:
            if raw is None:
                with arc.path.open("rb") as fh:
                    raw = arc.read_file(e, fh)
            listed = parse_seq(raw)
        except Exception:  # noqa: BLE001
            listed = None
        if listed is None:
            continue
        missing = [i for i in want if i not in listed]
        extra = [i for i in listed if i not in want and i not in unknown]
        if not missing and not extra:
            continue
        keep = want + [i for i in listed if i in unknown and i not in want]
        add("seq-differ", "info", "plugins", "seq-differ", h.name,
            {"name": h.name, "seq": key, "where": where, "have": len(listed), "want": len(want),
             "missing": _hex(missing), "extra": _hex(extra)},
            items=[f"+{i:08X}" for i in missing] + [f"-{i:08X}" for i in extra],
            fix=F("seq_rewrite", "fix-seq-rewrite", "revisar", plugin=h.name, formids=keep,
                  bsa=None if where == "Data\\seq" else where, loose=where == "Data\\seq")
            if keep else None)


# ---------------------------------------------------------------- LOOT notes in the Doctor
# LOOT recommends PC-only tools (SKSE plugins, xEdit cleaning...) that don't
# exist on Switch; those messages would only be noise in the Doctor.
PC_ONLY = re.compile(r"skse|engine fixes|bug fixes sse|address library|powerofthree|papyrus ?util|"
                     r"\.dll\b|xedit|sseedit|bashed patch|smashed patch|synthesis|nemesis|fnis|"
                     r"\bdar\b|open animation replacer", re.I)


def add_loot_findings(R: "AuditResult", pack: Pack, masterlist, aliases=None, userlist=None) -> None:
    """Requirements, incompatibilities and patch messages from the LOOT
    masterlist (already downloaded; nothing is fetched here), merges, and the
    count of plugins LOOT doesn't know."""
    from . import loot
    try:
        sg = loot.suggest(pack, masterlist, aliases=aliases, userlist=userlist)
    except Exception:  # noqa: BLE001
        return
    sev_of = {"error": "aviso", "warn": "info"}
    for plugin, notes in sg.notes.items():
        for i, n in enumerate(notes):
            sev = sev_of.get(n.level)
            if not sev or PC_ONLY.search(n.en or ""):
                continue
            R.add("loot-note", sev, "requirements", "loot-note", f"{plugin}#{i}",
                  {"plugin": plugin, "text_en": n.en, "text_es": n.es or n.en})
    for merged, comps in sg.merges.items():
        d = [k for k, v in sg.dummies.items() if v.lower() == merged.lower()]
        R.add("loot-merge", "info", "requirements", "loot-merge", merged,
              {"plugin": merged, "n": len(comps), "list": ", ".join(comps),
               "dummies_en": (f" Kept empty so patches still find their masters: {', '.join(d)}.") if d else "",
               "dummies_es": (f" Se dejan vacíos para que los parches encuentren sus masters: {', '.join(d)}.") if d else ""})
    if sg.unknown:
        R.add("loot-unknown", "info", "requirements", "loot-unknown", "",
              {"n": len(sg.unknown)}, items=[u["name"] for u in sg.unknown])
