"""FOMOD installers (fomod/ModuleConfig.xml, schema 5.0).

The same rules mod managers follow, from the official schema
(github.com/GandaG/fomod-schema):
- steps, groups and options are sorted by name unless order="Explicit"
  (the default order is "Ascending");
- a step only shows when its <visible> conditions hold for the flags set by
  the options chosen in earlier steps;
- an option's type (Required, Recommended, Optional, NotUsable,
  CouldBeUsable) can depend on flags and on which plugins are active;
- files and folders have a priority: higher wins, and at the same priority the
  one installed later wins; a missing destination means "same as source",
  an empty one means the Data root;
- conditionalFileInstalls are checked at the end with the final flags.

"Active" here means the plugin is in the pack's load list (or is part of the
game, or the converter renamed it and the pack has it under its new name).
That's how the assistant avoids installing patches for mods you don't have.
"""
from __future__ import annotations

import base64
import mimetypes
import re
import shutil
import xml.etree.ElementTree as ET
from dataclasses import dataclass, field
from pathlib import Path

from .errors import SkynxError

TYPES = ("Required", "Recommended", "Optional", "CouldBeUsable", "NotUsable")
IMAGE_MAX = 2_500_000


class FomodError(SkynxError):
    pass


# ------------------------------------------------------------------ model
@dataclass
class FileItem:
    source: str
    dest: str
    folder: bool
    priority: int = 0
    always: bool = False
    if_usable: bool = False


@dataclass
class Option:
    name: str
    description: str = ""
    image: str | None = None
    files: list[FileItem] = field(default_factory=list)
    flags: dict[str, str] = field(default_factory=dict)
    type_default: str = "Optional"
    type_patterns: list[tuple[ET.Element, str]] = field(default_factory=list)


@dataclass
class Group:
    name: str
    type: str
    options: list[Option] = field(default_factory=list)


@dataclass
class Step:
    name: str
    visible: ET.Element | None
    groups: list[Group] = field(default_factory=list)


@dataclass
class Fomod:
    root: Path                      # folder that holds the "fomod" folder
    name: str
    image: str | None
    module_deps: ET.Element | None
    required: list[FileItem]
    steps: list[Step]
    conditional: list[tuple[ET.Element, list[FileItem]]]
    index: dict[str, Path]          # lowercase relative path -> real path


# ------------------------------------------------------------------ parsing
def _strip_ns(el: ET.Element) -> None:
    for e in el.iter():
        if isinstance(e.tag, str) and "}" in e.tag:
            e.tag = e.tag.split("}", 1)[1]


def _read_xml(path: Path) -> ET.Element:
    raw = path.read_bytes()
    try:
        root = ET.fromstring(raw)
    except ET.ParseError:
        # The declared encoding often doesn't match the bytes (UTF-16 declared,
        # UTF-8 saved, or the other way round): go by the BOM instead.
        if raw[:2] in (b"\xff\xfe", b"\xfe\xff"):
            encs = ("utf-16",)
        elif raw[:3] == b"\xef\xbb\xbf":
            encs = ("utf-8-sig",)
        else:
            encs = ("utf-8", "cp1252")
        text = None
        for enc in encs:
            try:
                text = raw.decode(enc)
                break
            except UnicodeDecodeError:
                continue
        if text is None:
            raise FomodError("I can't read ModuleConfig.xml", "No pude leer ModuleConfig.xml")
        text = re.sub(r"^\s*<\?xml[^>]*\?>", "", text)
        try:
            root = ET.fromstring(text)
        except ET.ParseError as e:
            raise FomodError(f"ModuleConfig.xml is broken: {e}", f"ModuleConfig.xml está dañado: {e}") from e
    _strip_ns(root)
    return root


def _ordered(items: list, order: str | None, key) -> list:
    if order == "Explicit":
        return items
    s = sorted(items, key=lambda x: key(x).lower())
    return list(reversed(s)) if order == "Descending" else s


def _files(el: ET.Element | None) -> list[FileItem]:
    out = []
    if el is None:
        return out
    for f in el:
        if f.tag not in ("file", "folder"):
            continue
        src = (f.get("source") or "").replace("/", "\\").strip("\\")
        dest = f.get("destination")
        dest = src if dest is None else dest
        out.append(FileItem(src, dest.replace("/", "\\").strip("\\"), f.tag == "folder",
                            int(f.get("priority") or 0),
                            (f.get("alwaysInstall") or "").lower() == "true",
                            (f.get("installIfUsable") or "").lower() == "true"))
    return out


def find_root(folder: Path) -> Path | None:
    """The folder that holds fomod/ModuleConfig.xml (the archive root or the
    single folder inside it)."""
    cands = [folder] + [c for c in folder.iterdir() if c.is_dir()]
    for c in cands:
        for d in c.iterdir():
            if d.is_dir() and d.name.lower() == "fomod":
                if any(f.name.lower() == "moduleconfig.xml" for f in d.iterdir()):
                    return c
    return None


def has_script_installer(folder: Path) -> bool:
    for c in [folder] + [c for c in folder.iterdir() if c.is_dir()]:
        for d in c.iterdir():
            if d.is_dir() and d.name.lower() == "fomod":
                return any(f.name.lower() == "script.cs" for f in d.iterdir())
    return False


def load(root: Path) -> Fomod:
    root = Path(root)
    fdir = next(d for d in root.iterdir() if d.is_dir() and d.name.lower() == "fomod")
    cfg = next(f for f in fdir.iterdir() if f.name.lower() == "moduleconfig.xml")
    x = _read_xml(cfg)
    index = {}
    for p in root.rglob("*"):
        index[str(p.relative_to(root)).replace("/", "\\").lower()] = p
    steps = []
    st_el = x.find("installSteps")
    if st_el is not None:
        for s in _ordered(list(st_el.findall("installStep")), st_el.get("order"), lambda e: e.get("name", "")):
            groups = []
            og = s.find("optionalFileGroups")
            if og is not None:
                for g in _ordered(list(og.findall("group")), og.get("order"), lambda e: e.get("name", "")):
                    opts = []
                    pl = g.find("plugins")
                    if pl is not None:
                        for o in _ordered(list(pl.findall("plugin")), pl.get("order"), lambda e: e.get("name", "")):
                            opt = Option(o.get("name", ""), (o.findtext("description") or "").strip())
                            img = o.find("image")
                            opt.image = img.get("path") if img is not None else None
                            opt.files = _files(o.find("files"))
                            cf = o.find("conditionFlags")
                            if cf is not None:
                                opt.flags = {f.get("name", ""): (f.text or "") for f in cf.findall("flag")}
                            td = o.find("typeDescriptor")
                            if td is not None:
                                t = td.find("type")
                                if t is not None:
                                    opt.type_default = t.get("name", "Optional")
                                dt = td.find("dependencyType")
                                if dt is not None:
                                    d0 = dt.find("defaultType")
                                    if d0 is not None:
                                        opt.type_default = d0.get("name", "Optional")
                                    for pat in dt.findall("patterns/pattern"):
                                        dep, ty = pat.find("dependencies"), pat.find("type")
                                        if dep is not None and ty is not None:
                                            opt.type_patterns.append((dep, ty.get("name", "Optional")))
                            opts.append(opt)
                    groups.append(Group(g.get("name", ""), g.get("type", "SelectAny"), opts))
            steps.append(Step(s.get("name", ""), s.find("visible"), groups))
    cond = []
    for pat in x.findall("conditionalFileInstalls/patterns/pattern"):
        cond.append((pat.find("dependencies"), _files(pat.find("files"))))
    img = x.find("moduleImage")
    return Fomod(root, (x.findtext("moduleName") or root.name).strip(),
                 img.get("path") if img is not None else None,
                 x.find("moduleDependencies"), _files(x.find("requiredInstallFiles")),
                 steps, cond, index)


# ------------------------------------------------------------------ conditions
class Context:
    """What conditions are checked against: plugin states and flags."""

    def __init__(self, active: set[str], present: set[str]):
        self.active = {a.lower() for a in active}
        self.present = {p.lower() for p in present}
        self.unknown: set[str] = set()

    def file_state(self, name: str) -> str:
        n = name.lower()
        if n in self.active:
            return "Active"
        if n in self.present:
            return "Inactive"
        return "Missing"


def check(el: ET.Element | None, ctx: Context, flags: dict[str, str]) -> bool:
    if el is None:
        return True
    # <visible> may wrap a single <dependencies> (older files) or list
    # dependencies directly (schema 5.0).
    op = (el.get("operator") or "And").lower()
    results = []
    for c in el:
        if c.tag == "fileDependency":
            results.append(ctx.file_state(c.get("file", "")) == c.get("state", "Active"))
        elif c.tag == "flagDependency":
            results.append(flags.get(c.get("flag", ""), "") == (c.get("value") or ""))
        elif c.tag == "dependencies":
            results.append(check(c, ctx, flags))
        elif c.tag in ("gameDependency", "fommDependency"):
            results.append(True)
        else:
            ctx.unknown.add(c.tag)
            results.append(False)
    if not results:
        return True
    return all(results) if op == "and" else any(results)


def option_type(opt: Option, ctx: Context, flags: dict[str, str]) -> str:
    for dep, ty in opt.type_patterns:
        if check(dep, ctx, flags):
            return ty
    return opt.type_default


# ------------------------------------------------------------------ session
def _image(fm: Fomod, rel: str | None) -> str | None:
    if not rel:
        return None
    p = fm.index.get(rel.replace("/", "\\").strip("\\").lower())
    if not p or not p.is_file() or p.stat().st_size > IMAGE_MAX:
        return None
    mime = mimetypes.guess_type(p.name)[0] or "image/png"
    return f"data:{mime};base64," + base64.b64encode(p.read_bytes()).decode()


def evaluate(fm: Fomod, ctx: Context, choices: dict, upto: int | None = None) -> dict:
    """Walk the steps with the user's choices (step index -> group index ->
    list of option indexes), applying defaults where nothing was chosen.
    Returns the view for the window plus the final flags and selection."""
    flags: dict[str, str] = {}
    view_steps, selected = [], {}
    for si, step in enumerate(fm.steps):
        visible = check(step.visible, ctx, flags)
        st = {"index": si, "name": step.name, "visible": visible, "groups": []}
        if not visible:
            view_steps.append(st)
            continue
        for gi, g in enumerate(step.groups):
            types = [option_type(o, ctx, flags) for o in g.options]
            chosen = (choices.get(str(si)) or choices.get(si) or {})
            chosen = chosen.get(str(gi), chosen.get(gi))
            sel = _resolve(g.type, types, chosen)
            selected[(si, gi)] = sel
            for oi in sel:
                flags.update(g.options[oi].flags)
            st["groups"].append({
                "index": gi, "name": g.name, "type": g.type, "selected": sel,
                "options": [{"index": oi, "name": o.name, "description": o.description,
                             "type": types[oi], "has_image": bool(o.image),
                             "files": len(o.files)} for oi, o in enumerate(g.options)]})
        view_steps.append(st)
    return {"name": fm.name, "steps": view_steps, "flags": flags, "selected": selected,
            "unknown": sorted(ctx.unknown),
            "module_ok": check(fm.module_deps, ctx, {})}


def _resolve(gtype: str, types: list[str], chosen) -> list[int]:
    n = len(types)
    usable = [i for i in range(n) if types[i] != "NotUsable"]
    required = [i for i in range(n) if types[i] == "Required"]
    if gtype == "SelectAll":
        return list(range(n))
    if chosen is None:
        rec = [i for i in usable if types[i] == "Recommended"]
        if gtype in ("SelectExactlyOne", "SelectAtMostOne"):
            pick = required[:1] or rec[:1]
            if not pick and gtype == "SelectExactlyOne":
                pick = usable[:1]
            return pick
        base = sorted(set(required + rec))
        if gtype == "SelectAtLeastOne" and not base and usable:
            base = usable[:1]
        return base
    sel = [int(i) for i in chosen if 0 <= int(i) < n and types[int(i)] != "NotUsable"]
    if gtype in ("SelectExactlyOne", "SelectAtMostOne"):
        sel = (required or sel)[:1]
        if not sel and gtype == "SelectExactlyOne" and usable:
            sel = usable[:1]
        return sel
    sel = sorted(set(sel) | set(required))
    if gtype == "SelectAtLeastOne" and not sel and usable:
        sel = usable[:1]
    return sel


def step_images(fm: Fomod, si: int) -> dict:
    out = {}
    if 0 <= si < len(fm.steps):
        for gi, g in enumerate(fm.steps[si].groups):
            for oi, o in enumerate(g.options):
                img = _image(fm, o.image)
                if img:
                    out[f"{gi}:{oi}"] = img
    return out


def choices_summary(fm: Fomod, ev: dict) -> dict:
    out = {}
    for (si, gi), sel in ev["selected"].items():
        st = fm.steps[si]
        g = st.groups[gi]
        out.setdefault(st.name, {})[g.name] = [g.options[i].name for i in sel]
    return out


# ------------------------------------------------------------------ install
def _safe_rel(rel: str) -> list[str]:
    parts = [p for p in rel.replace("/", "\\").split("\\") if p not in ("", ".")]
    if any(p == ".." or ":" in p for p in parts):
        raise FomodError(f"Unsafe path in the installer: {rel}", f"Ruta insegura en el instalador: {rel}")
    return parts


def plan_files(fm: Fomod, ctx: Context, ev: dict) -> list[tuple[str, Path]]:
    """(destination relative to Data, source file) for everything to install,
    after applying priorities."""
    items: list[FileItem] = list(fm.required)
    for si, step in enumerate(fm.steps):
        if not ev["steps"][si]["visible"]:
            continue
        for gi, g in enumerate(step.groups):
            sel = set(ev["selected"].get((si, gi), []))
            types = [o["type"] for o in ev["steps"][si]["groups"][gi]["options"]]
            for oi, o in enumerate(g.options):
                for f in o.files:
                    if oi in sel or f.always or (f.if_usable and types[oi] != "NotUsable"):
                        items.append(f)
    for dep, files in fm.conditional:
        if check(dep, ctx, ev["flags"]):
            items.extend(files)
    chosen: dict[str, tuple[int, int, str, Path]] = {}
    missing = []
    for seq, it in enumerate(items):
        src_parts = _safe_rel(it.source)
        dest_parts = _safe_rel(it.dest)
        src = fm.root if not src_parts else fm.index.get("\\".join(src_parts).lower())
        if src is None:
            missing.append(it.source)
            continue
        if it.folder:
            if not src.is_dir():
                missing.append(it.source)
                continue
            for p in src.rglob("*"):
                if p.is_file() and not (src == fm.root and p.relative_to(src).parts[0].lower() == "fomod"):
                    rel = "\\".join(dest_parts + list(p.relative_to(src).parts))
                    _offer(chosen, rel, it.priority, seq, p)
        else:
            if not src.is_file():
                missing.append(it.source)
                continue
            rel = "\\".join(dest_parts) if dest_parts else src.name
            _offer(chosen, rel, it.priority, seq, src)
    if missing:
        ev.setdefault("missing", []).extend(missing)
    return [(v[2], v[3]) for v in chosen.values()]


def _offer(chosen: dict, rel: str, prio: int, seq: int, src: Path) -> None:
    key = rel.lower()
    cur = chosen.get(key)
    if cur is None or (prio, seq) >= (cur[0], cur[1]):
        chosen[key] = (prio, seq, rel, src)


def install(fm: Fomod, ctx: Context, ev: dict, dest: Path) -> int:
    files = plan_files(fm, ctx, ev)
    dest.mkdir(parents=True, exist_ok=True)
    for rel, src in files:
        out = dest.joinpath(*rel.split("\\"))
        out.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, out)
    return len(files)
