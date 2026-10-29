"""Convert a PC mod (Skyrim SE/AE) for Switch and add it to the modpack.

Two steps, so the window can show the budget before anything is written:

  analyze(pack, source)  -> Analysis: what's inside, what each texture will
                            cost before/after, plugin names, .ccc bytes, warnings.
  convert(pack, analysis, options) -> result: converts in a staging folder,
                            packs BSAs and adds the mod with builder.add_mod
                            (one history entry, undoable).

The user's files are never modified: archives are extracted and folders
copied into a temporary staging folder first.
"""
from __future__ import annotations

import os
import re
import shutil
import tempfile
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field
from pathlib import Path

from . import hkx as HKX
from . import knowledge as K
from . import nxaudio as NXA
from . import rename as RN
from .bsa import read_bsa, write_bsa
from .builder import CONVERTED_INFO, _extract, _order_new, add_mod, load_mods
from .errors import SkynxError
from .pack import Pack
from .plugin import clear_light_flag, read_header
from .texplan import (MAX_SIZES, NO_PRESET, PRESETS, TexPlan, check_max_size, plan_texture,
                      texconv_args, with_cap)
from .textures import inspect as inspect_tex, is_opaque
from .tools import Toolset, ToolError, run

PLUGIN_EXT = (".esp", ".esm", ".esl")
TOP_KEEP = {"meshes", "textures", "sound", "music", "scripts", "interface", "seq", "strings",
            "lodsettings", "grass", "shadersfx", "video", "dialogueviews", "sky", "materials",
            "lightingtemplates", "terrain", "trees"}
TOP_DROP = {"fomod", "skse", "source", "docs", "doc", "readme", "screenshots", "images",
            "optional", "optionals", "calientetools", "nemesis_engine", "netscriptframework",
            "tools", "bodyslide", "__macosx"}
JUNK_EXT = {".psc", ".bak", ".psd", ".xcf", ".log", ".md", ".pdf", ".url", ".html", ".htm",
            ".dll", ".exe", ".bat", ".7z", ".zip", ".rar", ".db", ".ini~"}
ROOT_KEEP_EXT = set(PLUGIN_EXT) | {".bsa"}
SOUND_EXT = {".xwm", ".wav", ".fuz", ".lip", ".mcadpcm"}
BSA_SPLIT = 1_900_000_000
# How the converted files are packed (Koka's NX Toolkit frontend offers these):
#   plugin  "<plugin>.bsa" + "<plugin> - Textures.bsa", loaded by the plugin's name
#   single  one "<plugin>.bsa" with everything, loaded by the plugin's name
#   ini     "<name>M.bsa" (meshes, scripts, animations...) in sResourceArchiveList
#           and "<name>T.bsa" (textures, voices) in sResourceArchiveList2 of every
#           ini that sets it; their names don't match the plugin, so they load
#           only through the inis (Koka's most stable way)
#   ini1    one "<name>.bsa" with everything, in the ini list with more room
#           (the default "Switch version"): Koka's ini loading with one name per
#           mod instead of two. Falls back to "single" when no ini list has room.
PACKINGS = ("ini1", "plugin", "single", "ini")
DEFAULT_PACKING = "ini1"
from .texplan import DEFAULT_PRESET  # noqa: E402


class ConvertError(SkynxError):
    pass


def _note(en: str, es: str, level: str = "info") -> dict:
    return {"en": en, "es": es, "level": level}


@dataclass
class Analysis:
    id: str
    source: str
    work: Path
    data: Path
    mode: str
    plugins: list[dict] = field(default_factory=list)
    textures: list[tuple[str, object]] = field(default_factory=list)   # (rel, TexInfo|None)
    sounds: dict[str, set] = field(default_factory=dict)              # base rel -> exts
    hkx: dict[str, int] = field(default_factory=dict)
    counts: dict[str, int] = field(default_factory=dict)
    notes: list[dict] = field(default_factory=list)
    dropped: list[str] = field(default_factory=list)
    masters_map: dict[str, str] = field(default_factory=dict)         # master -> name in pack
    created: float = field(default_factory=time.time)
    extra: dict = field(default_factory=dict)                          # recorded in mods.json
    aliases: dict[str, str] = field(default_factory=dict)              # plugin -> folder name its assets use
    skse: object = None
    bsa_names: list[str] = field(default_factory=list)                # the mod's own BSAs, as named

    def tex_plans(self, preset: str, sdk: bool, max_size: int | None = None) -> list[TexPlan]:
        plans = [plan_texture(rel, info, preset, sdk, max_size) for rel, info in self.textures]
        for p in plans:
            if p.skip == "switch":
                dp = self.nvn_plan(p.rel, with_cap(preset, max_size))
                if dp is not None and dp.changes:
                    p.after, p.tw, p.th, p.fmt = dp.after, dp.tw, dp.th, dp.fmt
                    p.skip = "switch-diet"
        return plans

    def nvn_plan(self, rel: str, preset: str, bc1: bool = False):
        """Diet plan for a texture that is already native Switch (DFvN)."""
        from . import diet
        key = (rel, preset, bc1)
        cache = self.__dict__.setdefault("_nvn_cache", {})
        if key not in cache:
            try:
                raw = self.data.joinpath(*rel.split("\\")).read_bytes()
                cache[key] = diet.plan_nvn(rel, raw, preset, bc1)
            except Exception:  # noqa: BLE001  (left alone if it can't be read)
                cache[key] = None
        return cache[key]

    def estimate(self, preset: str, sdk: bool, max_size: int | None = None) -> dict:
        plans = self.tex_plans(preset, sdk, max_size)
        return {"preset": preset, "sdk": sdk, "max_size": max_size,
                "before": sum(p.before for p in plans), "after": sum(p.after for p in plans),
                "convert": sum(1 for p in plans if p.texconv or (p.nvn and not p.skip)
                               or p.skip == "switch-diet"),
                "resize": sum(1 for p in plans if (p.tw, p.th) != (p.w, p.h)),
                "switch": sum(1 for p in plans if p.skip in ("switch", "switch-diet")),
                "switch_diet": sum(1 for p in plans if p.skip == "switch-diet"),
                "unknown": sum(1 for p in plans if p.skip == "unknown"),
                "biggest": [p.to_dict() for p in sorted(plans, key=lambda p: -p.before)[:8]]}

    def cleanup(self) -> None:
        shutil.rmtree(self.work, ignore_errors=True)


# ------------------------------------------------------------------ helpers
def _ci_lookup(names) -> dict[str, str]:
    return {n.lower(): n for n in names}


def renamed_registry(pack: Pack) -> dict[str, str]:
    """Original plugin name (lower) -> name it has in this pack, for plugins the
    converter renamed. Later mods that use the original name as a master are
    pointed at the new one automatically."""
    reg = {}
    sources = [rec.get("renamed") or {} for rec in load_mods(pack).values()]
    try:   # renames done by the Doctor ("name safe for Google Drive")
        from .bsafix import load_renames
        sources.append(load_renames(pack))
    except Exception:  # noqa: BLE001
        pass
    for src in sources:
        for new, orig in src.items():
            if pack.data_dir and (pack.data_dir / new).exists():
                reg[orig.lower()] = new
    return reg


def _norm(s: str) -> str:
    from .audit import norm_name
    return norm_name(s)


def _find_root(src: Path, leave_out=None) -> Path:
    leave_out = leave_out or (lambda p: False)

    def has_fomod(d: Path) -> bool:
        return any(c.is_dir() and c.name.lower() == "fomod" for c in d.iterdir())
    tops = [c for c in src.iterdir() if c.is_dir()]
    if has_fomod(src) or (len(tops) == 1 and has_fomod(tops[0])):
        raise ConvertError(
            "This mod has a FOMOD installer I couldn't open. Extract it and pick the folder of "
            "the option you want.",
            "Este mod trae un instalador FOMOD que no pude abrir. Extráelo y elige la carpeta de "
            "la opción que quieres.")
    best, best_depth = None, 99
    for d in [src, *[p for p in src.rglob("*") if p.is_dir() and not leave_out(p)]]:
        depth = len(d.relative_to(src).parts)
        if depth > 4:
            continue
        try:
            kids = [k for k in d.iterdir() if not leave_out(k)]
        except OSError:
            continue
        has = any((k.is_file() and k.suffix.lower() in ROOT_KEEP_EXT) or
                  (k.is_dir() and k.name.lower() in TOP_KEEP) for k in kids)
        if has and depth < best_depth:
            best, best_depth = d, depth
    if best is None:
        raise ConvertError("I didn't find plugins, BSAs or game folders (meshes, textures...) in it.",
                           "No encontré plugins, BSA ni carpetas del juego (meshes, textures...).")
    return best


# ------------------------------------------------------------------ analyze
def open_source(source: Path) -> tuple[Path, Path]:
    """Temporary work folder and the folder with the mod's files in it."""
    source = Path(source)
    work = Path(tempfile.mkdtemp(prefix="skynx-conv-"))
    try:
        src = source if source.is_dir() else _extract(source, work / "src")
    except Exception:
        shutil.rmtree(work, ignore_errors=True)
        raise
    return work, src


def analyze(pack: Pack, source: Path, progress=None, work: Path | None = None,
            src: Path | None = None, mod_id: str | None = None,
            extra: dict | None = None) -> Analysis:
    source = Path(source)
    tick = progress or (lambda *a, **k: None)
    if not pack.data_dir:
        raise ConvertError("This modpack has no Data folder", "Este modpack no tiene carpeta Data")
    if work is None:
        work, src = open_source(source)
    mod_id = mod_id or (source.stem if source.is_file() else source.name)
    an = Analysis(mod_id, str(source), work, work / "data", pack.mode)
    an.extra = dict(extra or {})
    if an.data.exists():
        shutil.rmtree(an.data)
    an.data.mkdir()
    try:
        tick(source.name)
        from . import variants as VA
        vres = VA.choose(VA.files_of(src), pack.mode)

        def leave_out(p: Path) -> bool:
            return VA.skipped(Path(p).relative_to(src).as_posix(), vres["skip"])
        vn = VA.note(vres)
        if vn:
            an.notes.append(_note(vn[0], vn[1]))
        root = _find_root(src, leave_out)
        _stage(root, an, tick, leave_out)
        _voice_leftovers(an)
        _inventory(pack, an, tick)
        from .skse import scan_tree
        an.skse = scan_tree(an.data)
        an.notes.extend(an.skse.notes())
    except Exception:
        an.cleanup()
        raise
    return an


# ------------------------------------------------------------------ FOMOD
@dataclass
class FomodSession:
    source: str
    mod_id: str
    work: Path
    fm: object
    ctx: object

    def cleanup(self) -> None:
        shutil.rmtree(self.work, ignore_errors=True)


def fomod_context(pack: Pack):
    from . import fomod as FM
    active = [e for e in pack.list_entries if not e.startswith("#")]
    active += pack.stest_plugins() if hasattr(pack, "stest_plugins") else []
    active += K.VANILLA_MASTERS + K.SWITCH_MASTERS
    if pack.mode == "AE":
        active += K.AE_CC_PLUGINS
    # renamed by the converter: the installer asks for the original name
    reg = renamed_registry(pack)
    listed = {a.lower() for a in active}
    active += [orig for orig, new in reg.items() if new.lower() in listed]
    present = [h.name for h in pack.plugins.values()] + [orig for orig in reg]
    return FM.Context(set(active), set(present))


def start(pack: Pack, source: Path, progress=None):
    """Analysis for a plain mod, or a FomodSession when it has an installer."""
    from . import fomod as FM
    source = Path(source)
    tick = progress or (lambda *a, **k: None)
    tick(source.name)
    work, src = open_source(source)
    try:
        root = FM.find_root(src)
        if root is None and FM.has_script_installer(src):
            raise ConvertError("This mod uses an old script installer (script.cs) that I can't run. "
                               "Extract it and pick the option folder by hand.",
                               "Este mod usa un instalador antiguo con script (script.cs) que no puedo "
                               "ejecutar. Extráelo y elige a mano la carpeta de la opción.")
        if root is not None:
            fm = FM.load(root)
            mod_id = source.stem if source.is_file() else source.name
            return FomodSession(str(source), mod_id, work, fm, fomod_context(pack))
    except Exception:
        shutil.rmtree(work, ignore_errors=True)
        raise
    return analyze(pack, source, progress, work=work, src=src)


def fomod_finish(pack: Pack, sess: FomodSession, choices: dict, progress=None) -> Analysis:
    from . import fomod as FM
    ev = FM.evaluate(sess.fm, sess.ctx, choices or {})
    out = sess.work / "fomod-out"
    if out.exists():
        shutil.rmtree(out)
    n = FM.install(sess.fm, sess.ctx, ev, out)
    if not n:
        raise ConvertError("With these choices the installer doesn't install any file.",
                           "Con estas opciones el instalador no instala ningún archivo.")
    summary = FM.choices_summary(sess.fm, ev)
    an = analyze(pack, Path(sess.source), progress, work=sess.work, src=out, mod_id=sess.mod_id,
                 extra={"fomod": summary, "fomod_choices": choices or {},
                        "fomod_module": getattr(sess.fm, "name", None)})
    if ev.get("missing"):
        miss = ", ".join(ev["missing"][:5])
        an.notes.insert(0, _note(f"The installer points to files that aren't in the archive: {miss}.",
                                 f"El instalador apunta a archivos que no están en el comprimido: {miss}.",
                                 "warn"))
    if not ev.get("module_ok", True):
        an.notes.insert(0, _note("The installer says this mod needs other mods that aren't active in the pack.",
                                 "El instalador dice que este mod necesita otros mods que no están "
                                 "activos en el pack.", "warn"))
    return an


def _stage(root: Path, an: Analysis, tick, leave_out=None) -> None:
    data = an.data
    bsas = []
    skse = mod_ini = False
    unknown_tops = set()
    files = [p for p in root.rglob("*") if p.is_file() and not (leave_out and leave_out(p))]
    # Folders inside the mod that are mods themselves (their own plugin or BSA,
    # like an optional "NPC Overhaul" next to the main plugin): their files go
    # in as if they were at the top, instead of being packed under that name.
    nested: dict[Path, list[str]] = {}
    for p in files:
        rel = p.relative_to(root)
        if len(rel.parts) > 1 and (p.suffix.lower() in PLUGIN_EXT or p.suffix.lower() == ".bsa"):
            if rel.parts[0].lower() not in TOP_KEEP and rel.parts[0].lower() not in TOP_DROP:
                nested.setdefault(p.parent, []).append(p.name)
    if nested:
        s = "; ".join(f"{d.relative_to(root).as_posix()} ({', '.join(sorted(n)[:3])})" for d, n in nested.items())
        an.notes.append(_note(f"It has extra folders with their own plugins or BSAs, often optional parts: {s}. "
                              "I included them; if you don't want them, extract the archive and leave them out.",
                              f"Trae carpetas extra con sus propios plugins o BSA, muchas veces partes opcionales: "
                              f"{s}. Las incluí; si no las quieres, extrae el comprimido y déjalas por fuera."))
    for i, p in enumerate(files):
        if i % 200 == 0:
            tick(p.name, i, len(files))
        rel = p.relative_to(root)
        for d in sorted(nested, key=lambda x: -len(x.parts)):
            if d in p.parents:
                rel = p.relative_to(d)
                break
        parts = [x.lower() for x in rel.parts]
        ext = p.suffix.lower()
        if len(parts) == 1:
            if ext in PLUGIN_EXT:
                shutil.copy2(p, data / p.name)
            elif ext == ".bsa":
                bsas.append(p)
            elif ext == ".ini":
                mod_ini = True
                an.dropped.append(rel.as_posix())
            else:
                an.dropped.append(rel.as_posix())
            continue
        top = parts[0]
        if top == "nemesis_engine":          # a Nemesis patch: kept for behavior generation
            keep = an.work / "nemesis_src" / Path(*rel.parts[1:])
            keep.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(p, keep)
        if top in TOP_DROP or ext in JUNK_EXT or p.name.lower() in ("thumbs.db", "desktop.ini"):
            skse |= top == "skse" or ext == ".dll"
            an.dropped.append(rel.as_posix())
            continue
        if top not in TOP_KEEP:
            unknown_tops.add(rel.parts[0])
        dest = data.joinpath(*parts)
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(p, dest)
    an.bsa_names = [b.name for b in bsas]
    # Unpack the mod's own BSAs (PC or Switch); loose files win, like on PC.
    for b in bsas:
        try:
            arc = read_bsa(b)
        except Exception as e:  # noqa: BLE001
            an.notes.append(_note(f"I couldn't read {b.name} ({e}); it was left out.",
                                  f"No pude leer {b.name} ({e}); quedó por fuera.", "warn"))
            continue
        with b.open("rb") as f:
            for j, e in enumerate(arc.entries):
                if j % 200 == 0:
                    tick(b.name, j, len(arc.entries))
                parts = [x for x in e.path.lower().replace("/", "\\").split("\\")]
                if any(x in ("", ".", "..") or ":" in x for x in parts):
                    raise ConvertError(f"{b.name} has an unsafe path inside: {e.path}",
                                       f"{b.name} trae una ruta insegura dentro: {e.path}")
                dest = data.joinpath(*parts)
                if dest.exists():
                    continue
                dest.parent.mkdir(parents=True, exist_ok=True)
                dest.write_bytes(arc.read_file(e, f))
    if skse:
        an.notes.append(_note("It includes SKSE plugins (.dll). PC SKSE plugins don't run on "
                              "Switch; I left them out. Features that need them won't work.",
                              "Trae plugins de SKSE (.dll). Los de PC no corren en Switch; los "
                              "dejé por fuera. Lo que dependa de ellos no va a funcionar.", "warn"))
    if mod_ini:
        an.notes.append(_note("It has its own .ini. Switch doesn't read mod inis; if it has "
                              "settings you need, they go into Skyrim.ini by hand.",
                              "Trae su propio .ini. Switch no lee inis de mods; si trae ajustes "
                              "que necesitas, van a mano en Skyrim.ini.", "warn"))
    if unknown_tops:
        s = ", ".join(sorted(unknown_tops))
        an.notes.append(_note(f"Unusual folders packed as they are: {s}.",
                              f"Carpetas poco comunes empacadas tal cual: {s}."))


_OLD_TAKE = re.compile(r"-old\d*$")


def _common_prefix(a: str, b: str) -> int:
    n = 0
    for x, y in zip(a, b):
        if x != y:
            break
        n += 1
    return n


def _voice_leftovers(an: Analysis) -> None:
    """Voice files a porter left behind that the game never loads, and voice
    lines whose conversion was left half done (The Tempest Isle NX):

    * sound\\voice\\processing: the Creation Kit's lip-sync work folder;
    * old takes ("..._1-old1.fuz");
    * "<line>.temp.wav": the source of a line whose .fuz is empty or missing
      becomes "<line>.wav", so Convert makes the .fuz from it; when the .fuz
      is fine, the temp copy goes;
    * empty voice files (a 0-byte .fuz isn't a voice);
    * voice folders of the mod's earlier plugin names (TempestIsle.esp next to
      TempestIsleVacMerge.esp): voices are found by the plugin's name, so a
      folder for a name the mod no longer has is never read."""
    vroot = an.data / "sound" / "voice"
    if not vroot.is_dir():
        return
    plugins = [p.name.lower() for p in an.data.iterdir()
               if p.is_file() and p.suffix.lower() in PLUGIN_EXT]
    old_dirs = []
    stems = [Path(p).stem for p in plugins]
    if any((vroot / p).is_dir() for p in plugins):
        for d in vroot.iterdir():
            n = d.name.lower()
            if (d.is_dir() and n.endswith((".esp", ".esm", ".esl")) and n not in plugins
                    and any(_common_prefix(Path(n).stem, st) >= 6 for st in stems)):
                cnt = sum(1 for f in d.rglob("*") if f.is_file())
                shutil.rmtree(d)
                old_dirs.append(f"{d.name} ({cnt})")
    gone = {"processing": 0, "old": 0, "temp": 0, "empty": 0}
    recovered = 0
    proc = vroot / "processing"
    if proc.is_dir():
        gone["processing"] = sum(1 for f in proc.rglob("*") if f.is_file())
        shutil.rmtree(proc)
    for f in [f for f in vroot.rglob("*") if f.is_file()]:
        name = f.name.lower()
        if _OLD_TAKE.search(Path(name).stem):
            f.unlink()
            gone["old"] += 1
        elif name.endswith(".temp.wav"):
            base = f.name[: -len(".temp.wav")]
            fuz = f.with_name(base + ".fuz")
            wav = f.with_name(base + ".wav")
            if (fuz.exists() and fuz.stat().st_size > 0) or wav.exists():
                f.unlink()
                gone["temp"] += 1
            else:
                fuz.unlink(missing_ok=True)
                f.rename(wav)
                recovered += 1
    for f in [f for f in vroot.rglob("*") if f.is_file()]:
        if f.stat().st_size == 0 and f.suffix.lower() in (".fuz", ".xwm", ".wav", ".lip"):
            f.unlink()
            gone["empty"] += 1
    if recovered:
        an.notes.append(_note(
            f"{recovered} voice lines were left unconverted by whoever ported it (an empty .fuz next to "
            "a .temp.wav). Convert makes them from that .wav.",
            f"{recovered} líneas de voz quedaron sin convertir por quien lo portó (un .fuz vacío al lado "
            "de un .temp.wav). Convertir las hace a partir de ese .wav.", "warn"))
    if old_dirs:
        an.notes.append(_note(
            "Voices of earlier names of the plugin, never loaded, left out: " + ", ".join(old_dirs) + ".",
            "Voces de nombres anteriores del plugin, que nunca cargan, quedan por fuera: " +
            ", ".join(old_dirs) + "."))
    parts_en = [f"{gone['old']} old takes" if gone["old"] else "",
                f"{gone['temp']} temporary copies" if gone["temp"] else "",
                f"{gone['empty']} empty files" if gone["empty"] else "",
                f"the Creation Kit's lip-sync folder ({gone['processing']})" if gone["processing"] else ""]
    parts_es = [f"{gone['old']} tomas viejas" if gone["old"] else "",
                f"{gone['temp']} copias temporales" if gone["temp"] else "",
                f"{gone['empty']} archivos vacíos" if gone["empty"] else "",
                f"la carpeta de lip-sync del Creation Kit ({gone['processing']})" if gone["processing"] else ""]
    if any(parts_en):
        an.notes.append(_note("Voice leftovers the game never loads, left out: " +
                              ", ".join(x for x in parts_en if x) + ".",
                              "Restos de voces que el juego nunca carga, quedan por fuera: " +
                              ", ".join(x for x in parts_es if x) + "."))


def _inventory(pack: Pack, an: Analysis, tick) -> None:
    data = an.data
    counts = {"files": 0, "nif": 0, "pex": 0, "dds": 0, "hkx": 0, "sound": 0, "other": 0}
    files = [p for p in data.rglob("*") if p.is_file() and p.parent != data]
    for i, p in enumerate(files):
        if i % 300 == 0:
            tick(p.name, i, len(files))
        rel = str(p.relative_to(data)).replace("/", "\\")
        ext = p.suffix.lower()
        counts["files"] += 1
        if ext == ".dds":
            counts["dds"] += 1
            with p.open("rb") as f:
                an.textures.append((rel, inspect_tex(f.read(256))))
        elif ext == ".hkx":
            counts["hkx"] += 1
            raw = p.read_bytes()
            kind = HKX.classify(raw[:32])
            if kind == HKX.PC_64 and HKX.blocker(raw):
                kind = "pc64-" + HKX.blocker(raw)
            an.hkx[kind] = an.hkx.get(kind, 0) + 1
        elif ext in SOUND_EXT and (rel.startswith("sound\\") or rel.startswith("music\\")):
            counts["sound"] += 1
            an.sounds.setdefault(rel[: -len(ext)], set()).add(ext)
        elif ext == ".nif":
            counts["nif"] += 1
        elif ext == ".pex":
            counts["pex"] += 1
        else:
            counts["other"] += 1
    an.counts = counts
    bad = []
    for p in files:
        rel = str(p.relative_to(data))
        try:
            rel.encode("cp1252")
        except UnicodeEncodeError:
            bad.append(rel)
    if bad:
        raise ConvertError("These file names use characters a BSA can't store: " + ", ".join(bad[:5]),
                           "Estos nombres usan caracteres que un BSA no puede guardar: " + ", ".join(bad[:5]))
    longest = max((len(str(p)) for p in files), default=0)
    if os.name == "nt" and longest > 240:
        an.notes.append(_note("Some paths are very long; if a tool fails, move the mod to a shorter folder.",
                              "Algunas rutas son muy largas; si una herramienta falla, mueve el mod a una "
                              "carpeta más corta.", "warn"))
    # plugins
    taken = set(pack.data_files) if pack.data_files else set()
    taken |= {e.lower() for e in pack.list_entries}
    taken |= {m.lower() for m in K.VANILLA_MASTERS + K.SWITCH_MASTERS + K.AE_CC_PLUGINS}
    sugg: set[str] = {p.name.lower() for p in data.iterdir()
                      if p.is_file() and p.suffix.lower() in PLUGIN_EXT and RN.safe_name(p.name) == p.name}
    reg = renamed_registry(pack)
    in_pack = _ci_lookup(list(pack.list_entries) + [h.name for h in pack.plugins.values()])
    mine = _ci_lookup([p.name for p in data.iterdir() if p.is_file()])
    known = {m.lower() for m in K.VANILLA_MASTERS + K.SWITCH_MASTERS +
             (K.AE_CC_PLUGINS if pack.mode != "SE" else [])}
    norm_pack = {_norm(n): n for n in in_pack.values()}
    game = {m.lower() for m in K.VANILLA_MASTERS + K.SWITCH_MASTERS}
    if an.mode == "AE":
        game |= {m.lower() for m in K.AE_CC_PLUGINS}
    for p in [p for p in data.iterdir() if p.is_file() and p.name.lower() in game]:
        p.unlink()
        an.dropped.append(p.name)
        an.notes.append(_note(f"It ships {p.name}, a file of the game itself; I left it out so it "
                              "can't replace the original.",
                              f"Trae {p.name}, que es un archivo del propio juego; lo dejé por "
                              "fuera para que no reemplace el original.", "warn"))
    plugin_files = [p for p in data.iterdir() if p.is_file() and p.suffix.lower() in PLUGIN_EXT]
    orphans = _orphan_folders(data, [p.name for p in plugin_files],
                              set(known) | set(in_pack) | set(reg))
    for p in (_order_new(sorted(plugin_files)) if plugin_files else []):
        h = read_header(p)
        want = p.name
        reasons = []
        has_own = any((data.joinpath(*base.split("\\")) / p.name.lower()).is_dir() or
                      (data.joinpath(*base.split("\\")) / p.name).is_dir() for base in RN.NAME_FOLDERS)
        alias = _owner_for(p.name, orphans, len(plugin_files), has_own)
        if alias:
            # Its voices/FaceGen use another name (renamed plugin, Drive damage):
            # suggest that name and point those folders at whatever name it gets.
            an.aliases[p.name] = alias
            want = _case_like(alias, p.name)
            reasons.append("orphan")
            an.notes.append(_note(
                f"{p.name}: its voices/FaceGen are stored under '{alias}', so that was its original "
                "name. I suggest it (made safe) and update those folders to the final name.",
                f"{p.name}: sus voces/FaceGen están guardadas como '{alias}', así que ese era su "
                "nombre original. Lo sugiero (en versión segura) y actualizo esas carpetas al nombre final.",
                "info"))
        if an.mode == "SE" and (h.extension == ".esl" or h.is_light_flag):
            want = p.name[:-4] + ".esp"
            reasons.append("esl")
        safe = RN.safe_name(want)
        if safe != want:
            reasons.append("chars")
        for r in RN.blockers(data, p.name):
            reasons.append("blocked")
            an.notes.append(_note(f"{p.name}: {r} can't be patched, so the plugin keeps its name.",
                                  f"{p.name}: {r} no se puede parchar; el plugin conserva su nombre.",
                                  "warn"))
            break
        missing = []
        for m in h.masters:
            low = m.lower()
            if low in known or low in mine or low in in_pack:
                continue
            if low in reg:
                an.masters_map[m] = reg[low]
            elif _norm(m) in norm_pack:
                an.masters_map[m] = norm_pack[_norm(m)]
            else:
                missing.append(m)
        if h.hedr_version and h.hedr_version < 1.0:
            an.notes.append(_note(f"{p.name} is an Oldrim (LE) plugin. It has to be resaved for SE "
                                  "in the Creation Kit or it may crash.",
                                  f"{p.name} es un plugin de Oldrim (LE). Hay que guardarlo para SE "
                                  "en el Creation Kit o puede cerrar el juego.", "warn"))
        an.plugins.append({
            "name": p.name, "masters": h.masters, "missing": missing,
            "records": h.num_records, "light": h.is_light_flag or h.extension == ".esl",
            "localized": h.is_localized, "reasons": reasons,
            "suggested": p.name if "blocked" in reasons else RN.unique(safe, taken | (sugg - {p.name.lower()})),
            "compact": p.name if "blocked" in reasons else RN.unique(RN.compact_name(want), taken | (sugg - {p.name.lower()})),
            "locked": "blocked" in reasons})
        sugg.add(an.plugins[-1]["suggested"].lower())
    for m, n in an.masters_map.items():
        an.notes.append(_note(f"Uses {m} as a master; in this pack it's called {n}. I'll point it there.",
                              f"Usa {m} como master; en este pack se llama {n}. Lo apunto ahí."))
    for pl in an.plugins:
        if pl["missing"]:
            s = ", ".join(pl["missing"])
            an.notes.append(_note(f"{pl['name']} needs {s}, which isn't in the pack yet.",
                                  f"{pl['name']} necesita {s}, que todavía no está en el pack.", "warn"))
    # animations
    if an.hkx.get(HKX.PC_32) or an.hkx.get(HKX.XML):
        n = an.hkx.get(HKX.PC_32, 0) + an.hkx.get(HKX.XML, 0)
        an.notes.append(_note(f"{n} Havok files are Oldrim (32-bit) or XML. They're converted with "
                              "HavokBehaviorPostProcess.exe (Creation Kit) when it's in the tools folder.",
                              f"{n} archivos de Havok son de Oldrim (32 bits) o XML. Se convierten con "
                              "HavokBehaviorPostProcess.exe (Creation Kit) si está en la carpeta de "
                              "herramientas."))
    blocked = sum(v for k, v in an.hkx.items() if k.startswith("pc64-"))
    if blocked:
        an.notes.append(_note(f"{blocked} skeleton or behavior files are converted with "
                              "HavokBehaviorPostProcess.exe and hkxc.exe (serde-hkx) when both are in the "
                              "tools folder.",
                              f"{blocked} archivos de esqueleto o de comportamiento se convierten con "
                              "HavokBehaviorPostProcess.exe y hkxc.exe (serde-hkx) si los dos están en la "
                              "carpeta de herramientas."))
    if not an.plugins and not files:
        raise ConvertError("There's nothing to convert in it.", "No hay nada que convertir.")


def _rescan_assets(an: Analysis) -> None:
    an.textures, an.sounds = [], {}
    for p in an.data.rglob("*"):
        if not p.is_file() or p.parent == an.data:
            continue
        rel = str(p.relative_to(an.data)).replace("/", "\\")
        ext = p.suffix.lower()
        if ext == ".dds":
            with p.open("rb") as f:
                an.textures.append((rel, inspect_tex(f.read(256))))
        elif ext in SOUND_EXT and (rel.startswith("sound\\") or rel.startswith("music\\")):
            an.sounds.setdefault(rel[: -len(ext)], set()).add(ext)


def _orphan_folders(data: Path, plugins: list[str], known: set[str]) -> dict[str, int]:
    """Plugin-named folders (voices, FaceGen) that no plugin of the mod, the
    game or the pack owns: folder name (lower) -> files inside."""
    mine = {p.lower() for p in plugins}
    out: dict[str, int] = {}
    for base in RN.NAME_FOLDERS:
        d = data.joinpath(*base.split("\\"))
        if not d.is_dir():
            continue
        for sub in d.iterdir():
            n = sub.name.lower()
            if sub.is_dir() and n.endswith((".esp", ".esm", ".esl")) and n not in mine and n not in known:
                out[n] = out.get(n, 0) + sum(1 for f in sub.rglob("*") if f.is_file())
    return out


def _owner_for(plugin: str, orphans: dict[str, int], n_plugins: int, has_own: bool = False) -> str | None:
    """The orphan folder that belongs to this plugin: a Drive-damaged twin
    (apostrophes as "_") or, when the mod has a single plugin, the only orphan."""
    if not orphans:
        return None
    norm = _norm(plugin)
    for o in orphans:
        if _norm(o) == norm:
            return o
    if n_plugins == 1 and len(orphans) == 1 and not has_own:
        return next(iter(orphans))
    return None


def _case_like(name: str, model: str) -> str:
    """'ryn's standing stones.esp' cased like 'Ryn_s Standing Stones.esp'."""
    letters = [c for c in model if c.isalnum()]
    out, i = [], 0
    for c in name:
        if c.isalnum() and i < len(letters) and letters[i].lower() == c.lower():
            out.append(letters[i])
            i += 1
        else:
            out.append(c)
    return "".join(out)


# ------------------------------------------------------------------ budget
_TEX_CACHE: dict[tuple, int] = {}


def pack_texture_bytes(pack: Pack) -> int:
    """Estimated texture memory of everything the pack has in Data."""
    total = 0
    for p in pack.bsas.values():
        try:
            st = p.stat()
        except OSError:
            continue
        key = (str(p), st.st_mtime, st.st_size)
        if key not in _TEX_CACHE:
            n = 0
            try:
                arc = read_bsa(p)
                with p.open("rb") as f:
                    for e in arc.entries:
                        if e.name.lower().endswith(".dds"):
                            info = inspect_tex(arc.read_head(e, 256, f))
                            if info:
                                n += info.est_bytes
            except Exception:  # noqa: BLE001
                n = 0
            _TEX_CACHE[key] = n
        total += _TEX_CACHE[key]
    return total


def budget(pack: Pack, an: Analysis, names: dict[str, str] | None = None) -> dict:
    names = names or {}
    lst = pack.ccc if pack.mode == "AE" else pack.plugin_list
    nl = 1 if (lst and lst.newline == "LF") or pack.mode == "SE" else 2
    now = pack.list_bytes
    added = sum(len(names.get(p["name"], p["suggested"]).encode("utf-8")) + nl for p in an.plugins)
    return {"ccc_now": now, "ccc_add": added, "nl": nl,
            "ccc_limit": K.CCC_BYTE_LIMIT if pack.mode == "AE" else None,
            "ccc_warn": K.CCC_BYTE_WARN if pack.mode == "AE" else None,
            "tex_pack": pack_texture_bytes(pack)}


def analysis_view(pack: Pack, an: Analysis, tools: Toolset, lang: str = "en") -> dict:
    return {
        "id": an.id, "source": an.source, "mode": an.mode,
        "plugins": an.plugins, "counts": an.counts, "hkx": an.hkx,
        "sounds": len(an.sounds),
        "sounds_pc": sum(1 for b, ex in an.sounds.items() if ex & {".xwm", ".wav"} or
                         (".fuz" in ex and not _is_switch_fuz(an.data, b))),
        "dropped": len(an.dropped),
        "notes": [{"text": n[lang] if lang in n else n["en"], "level": n["level"]} for n in an.notes],
        "estimates": {p: {"pc": an.estimate(p, False), "sdk": an.estimate(p, True)}
                      for p in (*PRESETS, NO_PRESET)},
        # convert() options besides preset/sdk/bc1 (an.estimate(preset, sdk,
        # max_size) gives the numbers for a chosen max_size)
        "options": {"max_sizes": list(MAX_SIZES), "packings": list(PACKINGS),
                    "packing": DEFAULT_PACKING, "preset": DEFAULT_PRESET, "compress": True,
                    "no_preset": NO_PRESET},
        "budget": budget(pack, an),
        "tools": tools.status(),
    }


def _is_switch_fuz(data: Path, base: str) -> bool:
    p = data / (base.replace("\\", os.sep) + ".fuz")
    try:
        with p.open("rb") as f:
            return NXA.is_switch_fuz(f.read(64 * 1024))
    except OSError:
        return False


# ------------------------------------------------------------------ convert
def convert(pack: Pack, an: Analysis, options: dict, tools: Toolset, progress=None,
            nexus: dict | None = None) -> dict:
    """`nexus` (or options["nexus"]): what the Nexus code knows about the
    download (mod_id, file_id, version, name); recorded in the mod's source block.

    options:
      preset    "diet" (default), "koka", "extreme", or "none" (no preset sizes)
      max_size  256/512/1024/2048/4096 or None: largest side any texture keeps
                (user interface ones excepted), on top of the preset; never enlarges
      packing   "ini1" (default), "plugin", "single" or "ini" (see PACKINGS)
      ini_name  short base name for the "ini"/"ini1" BSAs (default: from the plugin)
      compress  True (default); False writes uncompressed BSAs
      sdk, bc1, names, over_limit, nexus: as before"""
    tick = progress or (lambda *a, **k: None)
    preset = options.get("preset") or DEFAULT_PRESET
    if preset not in PRESETS and preset != NO_PRESET:
        preset = DEFAULT_PRESET
    try:
        max_size = check_max_size(options.get("max_size"))
    except ValueError:
        raise ConvertError(f"Texture size {options.get('max_size')!r} isn't one of "
                           f"{', '.join(map(str, MAX_SIZES))}.",
                           f"El tamaño de textura {options.get('max_size')!r} no es uno de "
                           f"{', '.join(map(str, MAX_SIZES))}.") from None
    tex_preset = with_cap(preset, max_size)      # for the native Switch textures (diet.py)
    packing = options.get("packing") or DEFAULT_PACKING
    if packing not in PACKINGS:
        raise ConvertError(f"Unknown packing '{packing}' (use ini1, plugin, single or ini).",
                           f"Empaque desconocido '{packing}' (usa ini1, plugin, single o ini).")
    compress = options.get("compress", True) is not False
    use_sdk = bool(options.get("sdk", True)) and tools.sdk
    bc1 = bool(options.get("bc1")) and use_sdk
    names: dict[str, str] = options.get("names") or {}
    stats = {"tex_ok": 0, "tex_fail": 0, "tex_nvn": 0, "tex_bc1": 0, "tex_skip": 0,
             "snd_ok": 0, "snd_fail": 0, "snd_skip": 0, "hkx_ok": 0, "hkx_fail": 0, "hkx_havok": 0,
             "before": 0, "after": 0}
    notes: list[dict] = []
    data = an.data
    # what behavior generation (FNIS / Nemesis) needs, as the original PC files
    from . import behaviors as BH
    bsrc = an.work / "behavior-src"
    if bsrc.exists():
        shutil.rmtree(bsrc)
    n_bsrc = BH.capture(data, an.work / "nemesis_src", bsrc)

    # 1. names --------------------------------------------------------------
    taken = set(pack.data_files) | {e.lower() for e in pack.list_entries}
    taken |= {m.lower() for m in K.VANILLA_MASTERS + K.SWITCH_MASTERS + K.AE_CC_PLUGINS}
    mapping, renamed = {}, {}
    final_names = []
    for pl in an.plugins:
        old = pl["name"]
        new = (names.get(old) or pl["suggested"]).strip()
        if pl["locked"]:
            new = old
            if an.mode == "SE" and old.lower().endswith(".esl"):
                raise ConvertError(f"{old} is an ESL and can't be renamed safely, and SE can't load ESL.",
                                   f"{old} es ESL y no se puede renombrar sin riesgo; SE no carga ESL.")
        elif an.mode == "SE" and new.lower().endswith(".esl"):
            new = new[:-4] + ".esp"
        why = None if pl["locked"] else RN.check_name(new)
        if why:
            raise ConvertError(f"'{new}' isn't a valid plugin name ({why}).",
                               f"'{new}' no sirve como nombre de plugin ({why}).")
        if new.lower() in taken or new.lower() in {n.lower() for n in final_names}:
            raise ConvertError(f"{new} already exists in the pack. Pick another name.",
                               f"{new} ya existe en el pack. Elige otro nombre.")
        stem = Path(new).stem.lower()
        if stem in {Path(m).stem.lower() for m in K.VANILLA_MASTERS + K.SWITCH_MASTERS} or \
                stem.startswith("skyrim - "):
            raise ConvertError(f"{new} would collide with the game's own archives. Pick another name.",
                               f"{new} chocaría con los archivos del propio juego. Elige otro nombre.")
        for b in (f"{stem}.bsa", f"{stem} - textures.bsa"):
            if b in taken:
                raise ConvertError(f"{b} already exists in the pack. Pick another plugin name.",
                                   f"{b} ya existe en el pack. Elige otro nombre de plugin.")
        final_names.append(new)
        if new != old:
            mapping[old] = new
            renamed[new] = old
    if pack.mode == "AE" and pack.ccc:
        nl = 1 if pack.ccc.newline == "LF" else 2
        total = pack.list_bytes + sum(len(n.encode("utf-8")) + nl for n in final_names)
        if total > K.CCC_BYTE_LIMIT and not options.get("over_limit"):
            raise ConvertError(
                f"The .ccc would reach {total} bytes, over the {K.CCC_BYTE_LIMIT} limit. Shorten names "
                "or remove a mod first.",
                f"El .ccc llegaría a {total} bytes, por encima del límite de {K.CCC_BYTE_LIMIT}. "
                "Acorta nombres o quita un mod antes.")
    tick("…")
    folder_map = {}
    for old, alias in an.aliases.items():
        final = mapping.get(old, old)
        if alias.lower() != final.lower():
            folder_map[alias] = final
            renamed.setdefault(final, old)
    if RN.apply(data, {**an.masters_map, **folder_map, **mapping})["folders"]:
        _rescan_assets(an)   # voice/FaceGen folders moved: refresh their paths
    if an.mode == "SE":
        from .edition import adapt_bytes_for_se, cc_masters, cc_note
        for n in final_names:
            p = data / n
            raw = p.read_bytes()
            fixed = adapt_bytes_for_se(raw)          # no ESL flag, HEDR 1.70
            if fixed != raw:
                p.write_bytes(fixed)
            ccm = cc_masters(read_header(p).masters)
            if ccm:
                notes.append(_note(*cc_note(n, ccm), "warn"))
    order = _order_new([data / n for n in final_names]) if final_names else []
    if order:
        stem = order[0].stem
    elif an.bsa_names:      # a BSA-only mod keeps its BSA's name ("Bold.bsa", not the download's name)
        import re as _re
        base = _re.sub(r"\s*-\s*(textures|meshes|sounds|voices|misc|animations)\d*$", "",
                       Path(an.bsa_names[0]).stem, flags=_re.I) or Path(an.bsa_names[0]).stem
        stem = Path(RN.compact_name(base + ".esp")).stem
    else:
        stem = Path(RN.compact_name(an.id + ".esp")).stem
    if not order and (stem.lower() in {Path(m).stem.lower() for m in K.VANILLA_MASTERS + K.SWITCH_MASTERS}
                      or stem.lower().startswith("skyrim")):
        stem = "Mod" + stem
    ini_names = {}
    if packing == "ini":
        ini_names = _ini_names(pack, an, options, stem, final_names, notes)
    elif packing == "ini1":
        ini_names = _ini1_name(pack, options, stem, final_names, notes)
        if not ini_names:
            packing = "single"

    workers = max(2, (os.cpu_count() or 4) - 1)

    # 2. textures -----------------------------------------------------------
    plans = [pl for pl in an.tex_plans(preset, use_sdk, max_size)]
    if any(p.texconv for p in plans) and not tools.texconv:
        raise ConvertError("texconv.exe is missing from the tools folder.",
                           "Falta texconv.exe en la carpeta de herramientas.")
    tmp_tex = an.work / "tex"
    tmp_tex.mkdir(exist_ok=True)

    def do_tex(i: int, plan: TexPlan):
        path = data.joinpath(*plan.rel.split("\\"))
        if plan.skip == "switch-diet":
            # Already native Switch: shrink it (the USSEP tints are the classic case).
            from . import diet
            out_dir = tmp_tex / str(i)
            try:
                raw = path.read_bytes()
                dp = diet.plan_nvn(plan.rel, raw, tex_preset, bc1)
                if not dp.changes:
                    return "skip", plan, None
                new, how = diet.diet_texture(raw, dp, tools, out_dir)
                path.write_bytes(new)
                plan.after = dp.after
                plan.fmt = dp.fmt
                return ("nvn" if how in ("nvntexpkg", "own", "fallback") else "ok"), plan, None
            except Exception as e:  # noqa: BLE001  (kept exactly as it came)
                return "fail", plan, f"{plan.rel}: {e}"
            finally:
                shutil.rmtree(out_dir, ignore_errors=True)
        if plan.skip:
            return "skip", plan, None
        out_dir = tmp_tex / str(i)
        out_dir.mkdir()
        orig = out_dir / "orig.bin"
        shutil.copy2(path, orig)
        try:
            if bc1 and plan.fmt == "BC3" and plan.src_fmt in ("BC3", "BC7", "BC2", "RGBA8", "BGRA8"):
                if is_opaque(path.read_bytes()):
                    plan.fmt, plan.texconv = "BC1", True
                    from .texplan import est_bytes
                    plan.after = est_bytes("BC1", plan.tw, plan.th, plan.tmips, plan.cube)
            if plan.texconv:
                run(texconv_args(tools.texconv, path, out_dir, plan))
                res = out_dir / path.name
                if not res.exists():
                    cands = list(out_dir.glob("*.dds")) + list(out_dir.glob("*.DDS"))
                    res = cands[0] if cands else res
                info = inspect_tex(res.read_bytes()[:256]) if res.exists() else None
                if not info or info.container != "DDS" or (info.width, info.height) != (plan.tw, plan.th):
                    raise ToolError("texconv produced an unexpected file")
                os.replace(res, path)
            if plan.nvn:
                xtx = out_dir / "out.xtx"
                try:
                    run([tools.nvntexpkg, "-i", path, "-o", xtx])
                    head = xtx.read_bytes()[:4] if xtx.exists() else b""
                    if head != b"DFvN":
                        raise ToolError("NvnTexpkg produced no DFvN file")
                    os.replace(xtx, path)
                    return "nvn", plan, None
                except ToolError as e:
                    # Fall back to Koka's PC rule: a PC DDS has to be DXT5 (or BC5).
                    plan.nvn = False
                    if plan.fmt not in ("BC3", "BC5"):
                        if not tools.texconv:
                            raise
                        plan.fmt = "BC3"
                        run(texconv_args(tools.texconv, path, out_dir, plan))
                        os.replace(out_dir / path.name, path)
                    return "ok", plan, f"{plan.rel}: NvnTexpkg ({e}); kept as PC DDS"
            return "ok", plan, None
        except Exception as e:  # noqa: BLE001
            try:
                os.replace(orig, path)   # back to the file as it came in the mod
            except OSError:
                pass
            return "fail", plan, f"{plan.rel}: {e}"
        finally:
            shutil.rmtree(out_dir, ignore_errors=True)

    tex_fail, tex_fallback = [], []
    with ThreadPoolExecutor(workers) as ex:
        futs = [ex.submit(do_tex, i, p) for i, p in enumerate(plans)]
        for k, fut in enumerate(as_completed(futs)):
            kind, plan, err = fut.result()
            tick("textures", k + 1, len(futs))
            stats["before"] += plan.before
            if kind == "skip":
                stats["tex_skip"] += 1
                stats["after"] += plan.after
            elif kind == "fail":
                stats["tex_fail"] += 1
                stats["after"] += plan.before
                tex_fail.append(err)
            else:
                stats["tex_ok"] += 1
                stats["after"] += plan.after
                stats["tex_nvn"] += kind == "nvn"
                stats["tex_bc1"] += plan.fmt == "BC1" and plan.src_fmt != "BC1"
                if err:
                    tex_fallback.append(err)

    # 3. animations, behaviors, skeletons ----------------------------------
    from . import havok as HV
    hkx_left: dict[str, int] = {}
    hkx_err: list[str] = []
    tmp_hkx = an.work / "hkx"
    for p in sorted(data.rglob("*.hkx")):
        raw = p.read_bytes()
        rel = str(p.relative_to(data)).replace("/", "\\")
        why = HV.needs_havok(raw)
        if HKX.classify(raw[:32]) == HKX.PC_64 and not why:
            try:
                p.write_bytes(HKX.convert_pc64(raw))
                stats["hkx_ok"] += 1
                continue
            except ValueError:
                why = "pc64"
        if not why:
            continue                                  # already Switch, or not a Havok file we know
        need = why if why in ("xml", "pc32") else "pc64"
        if not HV.can_convert(tools, why if why != "pc64" else "behavior"):
            hkx_left[need] = hkx_left.get(need, 0) + 1
            continue
        tick(p.name)
        try:
            p.write_bytes(HV.to_switch(raw, tools, tmp_hkx, p.name))
            stats["hkx_havok"] += 1
        except HV.HavokError as e:
            stats["hkx_fail"] += 1
            hkx_err.append(f"{rel} ({e.en})")

    # 4. sounds -------------------------------------------------------------
    todo = {b: ex for b, ex in an.sounds.items()
            if ex & {".xwm", ".wav"} or (".fuz" in ex and not _is_switch_fuz(data, b))}
    if todo and not tools.can_audio:
        notes.append(_note("Sounds were left as they are: ffmpeg.exe or VGAudioCli.exe is missing "
                           "from the tools folder. PC sounds don't play on Switch.",
                           "Los sonidos quedaron tal cual: falta ffmpeg.exe o VGAudioCli.exe en la "
                           "carpeta de herramientas. Los sonidos de PC no suenan en Switch.", "warn"))
        todo = {}
    tmp_snd = an.work / "snd"
    tmp_snd.mkdir(exist_ok=True)
    snd_fail = []

    def do_snd(i: int, base: str, exts: set):
        return _convert_sound(data, base, exts, tools, tmp_snd / str(i))

    with ThreadPoolExecutor(workers) as ex:
        futs = [ex.submit(do_snd, i, b, e) for i, (b, e) in enumerate(todo.items())]
        for k, fut in enumerate(as_completed(futs)):
            tick("sounds", k + 1, len(futs))
            ok, err = fut.result()
            if ok:
                stats["snd_ok"] += 1
            else:
                stats["snd_fail"] += 1
                snd_fail.append(err)
    stats["snd_skip"] = len(an.sounds) - len(todo)

    # 5. pack ---------------------------------------------------------------
    tick("BSA")
    out = an.work / "out"
    out.mkdir(exist_ok=True)
    plugin_paths = [data / n for n in final_names]
    for p in plugin_paths:
        shutil.copy2(p, out / p.name)
    tex_files, other_files = [], []
    for p in sorted(data.rglob("*")):
        if not p.is_file() or p.parent == data:
            continue
        rel = str(p.relative_to(data)).replace("/", "\\")
        low = rel.lower()
        if low == "interface\\fontconfig.txt":      # a font mod's config stays loose (fonts.py)
            (out / "Interface").mkdir(exist_ok=True)
            shutil.copy2(p, out / "Interface" / "FontConfig.txt")
            continue
        if packing in ("single", "ini1"):
            other_files.append((rel, p))
        elif packing == "ini":
            (tex_files if low.startswith(("textures\\", "sound\\voice\\")) else other_files).append((rel, p))
        else:
            (tex_files if low.startswith("textures\\") else other_files).append((rel, p))
    if packing == "ini":
        groups = ((other_files, ini_names["main"]), (tex_files, ini_names["tex"]))
    elif packing == "ini1":
        groups = ((other_files, ini_names["one"]),)
    else:
        groups = ((other_files, stem), (tex_files, stem + " - Textures"))
    bsas, ini_keys = [], {}
    for files, base in groups:
        for k, chunk in enumerate(_chunks(files)):
            name = f"{base}{k + 1 if k else ''}.bsa"
            if (pack.data_dir / name).exists():
                raise ConvertError(f"{name} already exists in the pack.", f"{name} ya existe en el pack.")
            write_bsa(chunk, out / name, compress=compress)
            bsas.append(name)
            if packing == "ini":
                ini_keys[name] = ("sResourceArchiveList2" if base == ini_names["tex"]
                                  else "sResourceArchiveList")
            elif packing == "ini1":
                ini_keys[name] = ini_names["key"]

    # 6. add to the pack ----------------------------------------------------
    tick("…")
    extra = dict(an.extra)
    nexus = nexus or options.get("nexus") or extra.pop("nexus", None)
    extra.pop("nexus", None)
    conv = {"preset": preset, "sdk": use_sdk, "bc1": bc1, "max_size": max_size,
            "packing": packing, "compress": compress,
            "date": time.strftime("%Y-%m-%d %H:%M:%S"),
            "names": {pl["name"]: final for pl, final in zip(an.plugins, final_names)}}
    if options.get("names"):
        conv["chosen"] = dict(names)          # what the user typed, before checks
    if options.get("sdk") is not None and bool(options.get("sdk")) != use_sdk:
        conv["sdk_requested"] = bool(options.get("sdk"))
    if options.get("over_limit"):
        conv["over_limit"] = True
    # "source" is the path the user picked; add_mod turns it into the provenance block
    meta = {"converted": conv, "renamed": renamed, **extra, "source": an.source}
    rep = add_mod(pack, out, mod_id=an.id, meta=meta, nexus=nexus, ini_keys=ini_keys or None)
    if n_bsrc and BH.store(pack, rep.mod_id or an.id, bsrc):
        notes.append(_note("It brings new animations (FNIS or Nemesis). Its behaviors are generated for the whole "
                           "pack with Generate behaviors (Mods page).",
                           "Trae animaciones nuevas (FNIS o Nemesis). Sus comportamientos se generan para todo el "
                           "pack con Generar comportamientos (página Mods)."))
    kept = None
    if options.get("keep_to"):
        try:
            rec = load_mods(pack).get(rep.mod_id or an.id) or {}
            if n_bsrc:
                BH.make_zip(bsrc, out / "behavior-sources.zip")
            kept = keep_converted(out, Path(options["keep_to"]), rep.mod_id or an.id, {
                "name": rep.mod_id or an.id, "plugins": list(final_names), "bsas": list(bsas),
                "ini_keys": ini_keys or {}, "mode": pack.mode, "converted": conv,
                "source": rec.get("source"), "fomod": extra.get("fomod"),
                "first_pack": pack.root.name})
        except Exception as e:  # noqa: BLE001
            notes.append(_note(f"The mod is in the pack, but I couldn't keep a copy in the Library: {e}",
                               f"El mod quedó en el pack, pero no pude guardar la copia en la Biblioteca: {e}",
                               "warn"))
    if tex_fail:
        notes.append(_note(f"Textures with problems, kept as they were ({len(tex_fail)}): " +
                           "; ".join(tex_fail[:5]),
                           f"Texturas con problemas, quedaron como estaban ({len(tex_fail)}): " +
                           "; ".join(tex_fail[:5]), "warn"))
    if tex_fallback:
        notes.append(_note(f"NvnTexpkg failed on some textures; they stayed as PC DDS in DXT5 "
                           f"({len(tex_fallback)}): " + "; ".join(tex_fallback[:3]),
                           f"NvnTexpkg falló con algunas texturas; quedaron como DDS de PC en DXT5 "
                           f"({len(tex_fallback)}): " + "; ".join(tex_fallback[:3]), "warn"))
    if snd_fail:
        notes.append(_note(f"Sounds not converted ({len(snd_fail)}): " + "; ".join(snd_fail[:5]),
                           f"Sonidos sin convertir ({len(snd_fail)}): " + "; ".join(snd_fail[:5]),
                           "warn"))
    if stats["hkx_fail"]:
        notes.append(_note(f"Havok files left as PC files ({stats['hkx_fail']}); they may not play on Switch: "
                           + "; ".join(hkx_err[:4]),
                           f"Archivos de Havok que quedaron como de PC ({stats['hkx_fail']}); puede que no "
                           "funcionen en Switch: " + "; ".join(hkx_err[:4]), "warn"))
    if hkx_left:
        n = sum(hkx_left.values())
        notes.append(_note(f"{n} Havok files (behaviors, skeletons or Oldrim animations) stayed as they are: "
                           "converting them needs HavokBehaviorPostProcess.exe (Creation Kit) and, for 64-bit "
                           "ones, hkxc.exe (serde-hkx) in the tools folder.",
                           f"{n} archivos de Havok (comportamientos, esqueletos o animaciones de Oldrim) quedaron "
                           "tal cual: para convertirlos hacen falta HavokBehaviorPostProcess.exe (Creation Kit) y, "
                           "para los de 64 bits, hkxc.exe (serde-hkx) en la carpeta de herramientas.", "warn"))
    return {"stats": stats, "bsas": bsas, "plugins": final_names, "renamed": renamed,
            "notes": notes, "report": rep, "kept": str(kept) if kept else None}


def keep_converted(out: Path, dest_root: Path, name: str, info: dict) -> Path:
    """Copy a converted mod (its plugins and BSAs) to dest_root/<name>, with
    skynx-mod.json describing it, so it can go into other packs later without
    converting again. Never overwrites: a second copy gets " (2)"."""
    import json
    safe = "".join("_" if c in '<>:"/\\|?*' or ord(c) < 32 else c for c in str(name)).strip(" .") or "mod"
    dest_root = Path(dest_root)
    dest_root.mkdir(parents=True, exist_ok=True)
    dest, n = dest_root / safe, 2
    while dest.exists():
        dest, n = dest_root / f"{safe} ({n})", n + 1
    tmp = dest_root / f".{dest.name}.part"
    if tmp.exists():
        shutil.rmtree(tmp, ignore_errors=True)
    tmp.mkdir()
    try:
        for f in sorted(Path(out).iterdir()):
            if f.is_file():
                shutil.copy2(f, tmp / f.name)
        info = dict(info, kept=time.strftime("%Y-%m-%d %H:%M:%S"))
        (tmp / CONVERTED_INFO).write_text(json.dumps(info, indent=1, ensure_ascii=False), encoding="utf-8")
        os.replace(tmp, dest)
    except Exception:
        shutil.rmtree(tmp, ignore_errors=True)
        raise
    return dest


def _ini_names(pack: Pack, an: Analysis, options: dict, stem: str, final_names: list[str],
               notes: list[dict]) -> dict:
    """Names of the two "ini" BSAs, checked before any work: they can't load
    by a plugin's name (they'd load twice) and the ini lists must stay within
    ARCHIVE_LIST_LIMIT characters."""
    from .ini import ARCHIVE_LIST_LIMIT
    base = (options.get("ini_name") or "").strip() or Path(RN.compact_name(stem + ".esp", 12)).stem
    if not base or any(c in base for c in '\\/:*?"<>|,') or base.lower().startswith("skyrim"):
        raise ConvertError(f"'{base}' can't be used as a BSA name.", f"'{base}' no sirve como nombre de BSA.")
    names = {"main": base + "M", "tex": base + "T"}
    stems = {Path(n).stem.lower() for n in final_names}
    stems |= {Path(e.lstrip("#")).stem.lower() for e in pack.list_entries}
    stems |= {Path(h.name).stem.lower() for h in pack.plugins.values()}
    for n in names.values():
        low = n.lower()
        if low in stems or (low.endswith(" - textures") and low[:-11] in stems):
            raise ConvertError(f"{n}.bsa would also load by a plugin's name. Pick another BSA name.",
                               f"{n}.bsa también cargaría por el nombre de un plugin. Elige otro "
                               "nombre de BSA.")
        if (low + ".bsa") in pack.data_files:
            raise ConvertError(f"{n}.bsa already exists in the pack. Pick another BSA name.",
                               f"{n}.bsa ya existe en el pack. Elige otro nombre de BSA.")
    for key, n in (("sResourceArchiveList", names["main"]), ("sResourceArchiveList2", names["tex"])):
        paths = pack.inis_for_key(key)
        if not paths:
            raise ConvertError(f"No ini of the pack has {key}, so {n}.bsa wouldn't load.",
                               f"Ningún ini del pack tiene {key}, así que {n}.bsa no cargaría.")
        for ini in pack.inis:
            if ini.path not in paths:
                continue
            cur = ini.archive_list(key)
            total = len(", ".join(cur + [n + ".bsa"]))
            if total > ARCHIVE_LIST_LIMIT:
                raise ConvertError(
                    f"{key} in {ini.path.name} would reach {total} characters, over the "
                    f"{ARCHIVE_LIST_LIMIT} limit. Use a shorter BSA name or pack it named after the plugin.",
                    f"{key} en {ini.path.name} llegaría a {total} caracteres, por encima del límite de "
                    f"{ARCHIVE_LIST_LIMIT}. Usa un nombre de BSA más corto o empácalo con el nombre del plugin.")
            if total > 900:
                notes.append(_note(f"{key} in {ini.path.name} will be at {total} of {ARCHIVE_LIST_LIMIT} characters.",
                                   f"{key} en {ini.path.name} va a quedar en {total} de {ARCHIVE_LIST_LIMIT} caracteres.",
                                   "warn"))
    return names


def _load_stems(pack: Pack, final_names: list[str]) -> set[str]:
    """Names a BSA must not have: it would also load by a plugin's name."""
    stems = {Path(n).stem.lower() for n in final_names}
    stems |= {Path(e.lstrip("#")).stem.lower() for e in pack.list_entries}
    stems |= {Path(h.name).stem.lower() for h in pack.plugins.values()}
    return stems


def _ini1_name(pack: Pack, options: dict, stem: str, final_names: list[str],
               notes: list[dict]) -> dict:
    """Name and list of the one "ini1" BSA: {"one": name, "key": archive key},
    or {} when no ini list has room (the caller packs it as "single").
    The name can't load by a plugin's name and must be new in the pack; the
    list is the one that ends up shortest, so both lists fill evenly."""
    from .ini import ARCHIVE_LIST_LIMIT
    asked = (options.get("ini_name") or "").strip()
    base = asked or Path(RN.compact_name(stem + ".esp", 12)).stem
    if not base or any(c in base for c in '\\/:*?"<>|,') or base.lower().startswith("skyrim"):
        raise ConvertError(f"'{base}' can't be used as a BSA name.", f"'{base}' no sirve como nombre de BSA.")
    stems = _load_stems(pack, final_names)

    def free(n: str) -> bool:
        low = n.lower()
        return not (low in stems or (low.endswith(" - textures") and low[:-11] in stems)
                    or (low + ".bsa") in pack.data_files)
    name = base
    if not free(name):
        if asked:
            raise ConvertError(f"{name}.bsa would load by a plugin's name or already exists. Pick another BSA name.",
                               f"{name}.bsa cargaría por el nombre de un plugin o ya existe. Elige otro nombre de BSA.")
        name = next((base + suf for suf in ("B", "A", *map(str, range(1, 100))) if free(base + suf)), None)
        if not name:
            raise ConvertError(f"No free BSA name for {stem}. Pick one.", f"No hay un nombre de BSA libre para {stem}. Elige uno.")
    best, any_list = None, False
    for key in ("sResourceArchiveList2", "sResourceArchiveList"):
        paths = pack.inis_for_key(key)
        if not paths:
            continue
        any_list = True
        worst = max(len(", ".join(ini.archive_list(key) + [name + ".bsa"]))
                    for ini in pack.inis if ini.path in paths)
        if worst <= ARCHIVE_LIST_LIMIT and (best is None or worst < best[1]):
            best = (key, worst)
    if best is None:
        if any_list:
            notes.append(_note("No ini list has room for another BSA, so it was packed in one BSA named after the plugin.",
                               "Ninguna lista del ini tiene espacio para otro BSA, así que quedó en un solo BSA con el "
                               "nombre del plugin.", "warn"))
        else:
            notes.append(_note("There's no ini with archive lists here, so it was packed in one BSA named after the plugin.",
                               "Aquí no hay un ini con listas de archivos, así que quedó en un solo BSA con el nombre "
                               "del plugin."))
        return {}
    if best[1] > 900:
        notes.append(_note(f"{best[0]} will be at {best[1]} of {ARCHIVE_LIST_LIMIT} characters.",
                           f"{best[0]} va a quedar en {best[1]} de {ARCHIVE_LIST_LIMIT} caracteres.", "warn"))
    return {"one": name, "key": best[0]}


def _chunks(files: list[tuple[str, Path]]):
    if not files:
        return []
    chunks, cur, size = [], [], 0
    for rel, p in files:
        s = p.stat().st_size
        if cur and size + s > BSA_SPLIT:
            chunks.append(cur)
            cur, size = [], 0
        cur.append((rel, p))
        size += s
    chunks.append(cur)
    return chunks


def _convert_sound(data: Path, base: str, exts: set, tools: Toolset, tmp: Path):
    """One sound (all files that share a base name) -> .fuz (voices) or .mcadpcm."""
    tmp.mkdir(parents=True, exist_ok=True)
    src_base = data.joinpath(*base.split("\\"))
    is_voice = base.lower().startswith("sound\\voice\\")
    lip = b""
    try:
        if ".fuz" in exts:
            raw = src_base.with_name(src_base.name + ".fuz").read_bytes()
            lip, audio, kind = NXA.split_pc_fuz(raw)
            src = tmp / f"in.{kind}"
            src.write_bytes(audio)
        elif ".xwm" in exts:
            src = src_base.with_name(src_base.name + ".xwm")
        else:
            src = src_base.with_name(src_base.name + ".wav")
        if not lip and ".lip" in exts:
            lip = src_base.with_name(src_base.name + ".lip").read_bytes()
        wav = tmp / "norm.wav"
        if is_voice:
            run([tools.ffmpeg, "-hide_banner", "-loglevel", "error", "-y", "-i", src,
                 "-ac", "1", "-ar", "48000", "-c:a", "pcm_s16le", wav])
        else:
            run([tools.ffmpeg, "-hide_banner", "-loglevel", "error", "-y", "-i", src,
                 "-ar", "44100", "-c:a", "pcm_s16le", wav])
            if NXA.wav_info(wav.read_bytes()[:4096] + b"")["channels"] > 2:
                run([tools.ffmpeg, "-hide_banner", "-loglevel", "error", "-y", "-i", src,
                     "-ac", "2", "-ar", "44100", "-c:a", "pcm_s16le", wav])
        info = NXA.wav_info(wav.read_bytes())
        if is_voice:
            opus = tmp / "out.lopus"
            run([tools.vgaudio, "-c", "--opusheader", "Standard", "-i:0", wav, opus])
            result = NXA.build_fuz(lip, opus.read_bytes(), 1, info["duration_ms"])
            final = src_base.with_name(src_base.name + ".fuz")
        else:
            mc = tmp / "out.mcadpcm"
            run([tools.vgaudio, "-c", wav, mc])
            result = mc.read_bytes()
            NXA.check_mcadpcm(result)
            final = src_base.with_name(src_base.name + ".mcadpcm")
        staged = final.with_name(final.name + ".skynx-new")
        staged.write_bytes(result)
        os.replace(staged, final)
        for e in (".xwm", ".wav", ".fuz", ".lip"):
            other = src_base.with_name(src_base.name + e)
            if e in exts and other != final:
                other.unlink(missing_ok=True)
        return True, None
    except Exception as e:  # noqa: BLE001
        return False, f"{base}: {e}"
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
