"""Build a modpack from scratch: create the project, add and remove mods.

Mods are added as they come from the community (already converted for
Switch): a folder or a .7z/.zip with .esp/.esm/.esl and .bsa files.
- Plugins go into the load list right after their last master.
- BSAs whose name matches a plugin load by themselves.
- BSAs without a plugin (Koka's "Core - Animations.bsa" style) go into the
  ini archive lists: textures/voices to sResourceArchiveList2, the rest
  (animations included) to sResourceArchiveList. Nothing goes to
  sArchiveToLoadInMemoryList: KokaNX tested (Oct 2026) that animation BSAs
  load fine without it, and it only costs RAM.
Everything happens inside one history Transaction, so a whole "add mod"
can be undone in one step.
"""
from __future__ import annotations

import json
import shutil
import tempfile
import time
from dataclasses import dataclass, field
from pathlib import Path

from . import ccc as C
from . import knowledge as K
from .bsa import read_bsa
from .errors import SkynxError
from .history import Transaction
from .ini import ARCHIVE_LIST_LIMIT, parse_ini, set_archive_list
from .pack import Pack
from .plugin import read_header
from .textures import inspect as inspect_tex

PLUGIN_EXT = {".esp", ".esm", ".esl"}
ASSET_DIRS = {"meshes", "textures", "sound", "music", "scripts", "interface", "seq",
              "strings", "lodsettings", "grass", "shadersfx"}

CC_PRESETS = {
    "all": K.AE_CC_PLUGINS,
    "ussep": K.USSEP_CC_MASTERS,
    "none": [],
}


class BuildError(SkynxError):
    pass


@dataclass
class Report:
    added: list[str] = field(default_factory=list)
    list_added: list[str] = field(default_factory=list)
    ini_added: list[tuple[str, str]] = field(default_factory=list)
    notes: list[tuple[str, str]] = field(default_factory=list)   # (en, es)
    history: str | None = None
    mod_id: str | None = None

    def to_dict(self, lang: str = "en") -> dict:
        return {"added": self.added, "list_added": self.list_added,
                "ini_added": [{"key": k, "bsa": b} for k, b in self.ini_added],
                "notes": [es if lang == "es" else en for en, es in self.notes],
                "history": self.history}


# ---------------------------------------------------------------- new project
def find_base_files(base: Path) -> dict:
    """Locate Skyrim inis and Skyrim_aoc.ccc inside a folder (a clean dump or a pack)."""
    base = Path(base)
    out = {"inis": [], "ccc": None}
    for p in base.rglob("*"):
        if not p.is_file() or ".skynx" in p.parts:
            continue
        low = p.name.lower()
        if low == "skyrim.ini" or (low.startswith("skyrim_") and low.endswith(".ini") and low.count(".") == 1):
            if not any(q.name.lower() == low for q in out["inis"]):
                out["inis"].append(p)
        elif low == "skyrim_aoc.ccc" and out["ccc"] is None:
            out["ccc"] = p
    return out


def _vanilla_lists(raw: bytes) -> bytes:
    """Keep the ini's tweaks but drop mod BSAs and extra sTestFile plugins, so a
    pack's ini can serve as the base for a clean modpack."""
    from .ini import parse_ini as _p, set_value
    ini = _p(raw)
    for key in ("sResourceArchiveList", "sResourceArchiveList2", "sArchiveToLoadInMemoryList"):
        if ini.get("Archive", key) is not None:
            keep = [b for b in ini.archive_list(key)
                    if b.lower().startswith("skyrim - ") or "relicsofhyrule" in b.lower()]
            raw = set_archive_list(raw, key, keep)
    ini = _p(raw)
    vanilla = {m.lower() for m in K.VANILLA_MASTERS + K.SWITCH_MASTERS}
    for e in ini.entries:
        if e.section.lower() == "general" and e.key.lower().startswith("stestfile") \
                and e.value.lower() not in vanilla:
            raw = set_value(raw, "General", e.key, "")
    return raw


# The clean Skyrim_en.ini from the console (DBI dump, AE). Used when the base
# folder doesn't have one: in English this file replaces Skyrim.ini's
# sResourceArchiveList2, so a pack needs it to load texture BSAs from the ini.
VANILLA_EN_INI = (
    "[General]\r\nsLanguage=ENGLISH\r\n\r\n[Fonts]\r\nsFontConfigFile=Interface\\FontConfig.txt\r\n\r\n"
    "[Archive]\r\nsResourceArchiveList2=Skyrim - Voices_en0.bsa, Skyrim - Voices_en1.bsa, "
    "Skyrim - Textures0.bsa, Skyrim - Textures1.bsa, Skyrim - Textures2.bsa, Skyrim - Textures3.bsa, "
    "Skyrim - Textures4.bsa, Skyrim - Textures5.bsa")


def create_project(root: Path, edition: str, base: Path, cc_preset: str = "ussep",
                   lang: str = "en", ussep: str | None = None, ussep_dir: Path | None = None) -> Path:
    """New modpack. Only Skyrim.ini and the ini of the game language (English by
    default) are copied; other language inis would just be more lists to keep in sync."""
    root = Path(root)
    if root.exists() and any(root.iterdir()):
        raise BuildError("The folder for the new modpack must be empty",
                         "La carpeta del modpack nuevo tiene que estar vacía")
    found = find_base_files(base)
    if not any(p.name.lower() == "skyrim.ini" for p in found["inis"]):
        raise BuildError("I couldn't find a Skyrim.ini in the base folder. Dump the clean ones "
                         "from DBI (Installed games > Skyrim > Update > romfs) or point to a "
                         "modpack you trust.",
                         "No encontré Skyrim.ini en la carpeta base. Saca los limpios con DBI "
                         "(Juegos instalados > Skyrim > Update > romfs) o elige un modpack de "
                         "confianza.")
    if ussep:   # check before creating anything
        from .ussep import scan
        info = scan(ussep_dir)
        v = next((x for x in info["variants"] if x["id"] == ussep), None)
        if not v or not info["bsas"]:
            raise BuildError(f"The USSEP folder ({info['folder']}) has no {ussep} version with its BSAs.",
                             f"La carpeta de USSEP ({info['folder']}) no tiene la versión {ussep} con sus BSA.")
        if edition == "SE" and v["cc"]:
            raise BuildError("The SE version can't use Creation Club masters; pick USSEP No_CC.",
                             "La versión SE no puede usar masters del Creation Club; elige USSEP No_CC.")
    romfs = root / K.TITLE_BASE / "romfs"
    (romfs / "Data").mkdir(parents=True)
    want = {"skyrim.ini", f"skyrim_{lang}.ini"}
    for ini in found["inis"]:
        if ini.name.lower() in want:
            (romfs / ini.name).write_bytes(_vanilla_lists(ini.read_bytes()))
    if lang == "en" and not any(p.name.lower() == "skyrim_en.ini" for p in found["inis"]):
        (romfs / "Skyrim_en.ini").write_bytes(VANILLA_EN_INI.encode("utf-8"))
    if edition == "AE":
        aoc = root / K.TITLE_AOC / "romfs"
        aoc.mkdir(parents=True)
        if cc_preset == "base" and found["ccc"]:
            src = C.read_ccc(found["ccc"])
            entries = [e for e in src.entries if e.lower().startswith("cc")]
        else:
            entries = list(CC_PRESETS.get(cc_preset, K.USSEP_CC_MASTERS))
        (aoc / "Skyrim_aoc.ccc").write_bytes(C.render(entries, "CRLF", True))
    else:
        (romfs / "Plugins").write_bytes(b"")
    meta = root / ".skynx"
    meta.mkdir()
    (meta / "project.json").write_text(json.dumps({
        "edition": edition, "created": time.strftime("%Y-%m-%d %H:%M:%S"),
        "base": str(base), "cc_preset": cc_preset, "ussep": ussep}, indent=1), encoding="utf-8")
    if ussep:
        from .ussep import install
        install(Pack.open(root), ussep_dir, ussep)
    return root


# ---------------------------------------------------------------- mod records
def _mods_file(pack: Pack) -> Path:
    return Path(pack.root) / ".skynx" / "mods.json"


def load_mods(pack: Pack) -> dict:
    f = _mods_file(pack)
    if f.exists():
        try:
            return json.loads(f.read_text(encoding="utf-8"))
        except Exception:  # noqa: BLE001
            return {}
    return {}


def _save_mods(pack: Pack, tx: Transaction, mods: dict) -> None:
    f = _mods_file(pack)
    f.parent.mkdir(parents=True, exist_ok=True)
    tx.write_bytes(f, json.dumps(mods, indent=1, ensure_ascii=False).encode("utf-8"))


def _users_msg(users: list[str]) -> tuple[str, str]:
    s = ", ".join(users)
    if len(users) == 1:
        return f"Not removing it: {s} uses it as a master", f"No lo quito: {s} lo usa como master"
    return f"Not removing it: {s} use it as a master", f"No lo quito: {s} lo usan como master"


# ---------------------------------------------------------------- add a mod
def _extract(src: Path, into: Path) -> Path:
    """Extract a .zip/.7z into into/<stem>. Delegates to intake.safe_extract,
    which refuses paths that escape the folder (checked per path component, so
    a sibling folder whose name merely starts the same way is caught too) and
    symbolic links inside .7z files."""
    from .intake import safe_extract
    return safe_extract(Path(src), Path(into) / Path(src).stem)


def scan_mod(folder: Path, skip: list[str] | None = None) -> dict:
    """Plugins, BSAs and loose asset folders of a mod folder. Mac junk and the
    version folders in `skip` (variants.choose) are left out."""
    from .variants import skipped
    plugins, bsas, loose, fomod = [], [], [], False
    for p in sorted(Path(folder).rglob("*")):
        rel = p.relative_to(folder).as_posix()
        if skipped(rel, skip or []):
            continue
        rel_parts = [x.lower() for x in p.relative_to(folder).parts]
        if "fomod" in rel_parts:
            fomod = True
            continue
        if p.is_dir():
            if p.name.lower() in ASSET_DIRS and not any(x in ASSET_DIRS for x in rel_parts[:-1]):
                loose.append(p)
            continue
        ext = p.suffix.lower()
        if ext in PLUGIN_EXT:
            plugins.append(p)
        elif ext == ".bsa":
            bsas.append(p)
    # a font mod's FontConfig.txt stays loose (fonts.py): an Interface folder
    # with only that file isn't "loose files to pack"
    from .fonts import find_fontconfig, only_fontconfig
    fontconfig = find_fontconfig(folder)
    if fontconfig is not None:
        loose = [d for d in loose if not (d.name.lower() == "interface" and only_fontconfig(d))]
    return {"plugins": plugins, "bsas": bsas, "loose": loose, "fomod": fomod, "fontconfig": fontconfig}


def _order_new(plugins: list[Path]) -> list[Path]:
    """Masters among the new plugins first."""
    heads = {p.name.lower(): read_header(p) for p in plugins}
    done, out = set(), []

    def visit(name, stack=()):
        if name in done or name in stack:
            return
        for m in heads[name].masters:
            if m.lower() in heads:
                visit(m.lower(), stack + (name,))
        done.add(name)
        out.append(next(p for p in plugins if p.name.lower() == name))
    for p in plugins:
        visit(p.name.lower())
    return out


def _archive_key_for(bsa: Path) -> list[str]:
    """Pick ini lists from what the BSA contains (names like 'OdnTs.bsa' say nothing).
    Textures and voices go to list 2, like the game's own Textures/Voices BSAs;
    everything else, animations included, to sResourceArchiveList. Animations
    don't go to the in-memory list: KokaNX tested (Oct 2026) that they don't
    need it, and it costs RAM (only worth it if T-poses or stutters show up)."""
    try:
        arc = read_bsa(bsa)
        n = max(1, len(arc.entries))
        tex = sum(e.name.lower().endswith(".dds") for e in arc.entries)
        voice = sum(e.folder.lower().startswith("sound\\voice") for e in arc.entries)
    except Exception:  # noqa: BLE001
        low = bsa.name.lower()
        tex = voice = 0
        n = 1
        if "texture" in low or "voice" in low:
            tex = 1
    if (tex + voice) / n > 0.5:
        return ["sResourceArchiveList2"]
    return ["sResourceArchiveList"]


def base_block_end(pack: Pack, entries: list[str]) -> int:
    """Index right after the leading run of Creation Club / vanilla lines
    (and '#' lines) of a load list: where a mod that must load first goes."""
    cc = {c.lower() for c in K.AE_CC_PLUGINS}
    vanilla = {m.lower() for m in K.VANILLA_MASTERS + K.SWITCH_MASTERS}
    i = 0
    for e in entries:
        low = e.lower()
        if e.startswith("#") or low in cc or low in vanilla or (pack.mode == "AE" and pack.is_cc(e)):
            i += 1
            continue
        break
    return i


CONVERTED_INFO = "skynx-mod.json"   # written next to a converted mod kept in Library\\Converted


def _is_cc(name: str) -> bool:
    from .edition import is_cc
    return is_cc(name)


def add_mod(pack: Pack, source: Path, progress=None, mod_id: str | None = None,
            meta: dict | None = None, files: list[Path] | None = None,
            nexus: dict | None = None, first: bool = False,
            ini_keys: dict[str, str] | None = None, title: str | None = None,
            also=None) -> Report:
    """Add a converted mod. `files` (plugins and BSAs) skips scanning `source`.

    ini_keys: {BSA name: archive key} for BSAs without a plugin whose list is
    already known (the converter's "ini" packing); others go by their content.

    first: the mod must load before every other mod (USSEP, Koka's advice):
    its plugins go right after the Creation Club / vanilla lines of the list
    and its ini BSAs right after the game's own BSAs.

    The record gets a provenance block (recipe.source_block) under "source":
    from meta["source"] when the caller passes one (a dict is used as it is,
    a path is where the mod really came from), else from `source`. `nexus`
    is what the Nexus code knows about the download (mod_id, file_id, version, name)."""
    source = Path(source)
    rep = Report()
    meta = dict(meta or {})
    from .recipe import norm_nexus, source_block
    nexus = nexus or meta.pop("nexus", None)
    given = meta.pop("source", None)
    if not pack.data_dir:
        raise BuildError("This modpack has no Data folder", "Este modpack no tiene carpeta Data")
    tmpdir = Path(tempfile.mkdtemp(prefix="skynx-mod-"))
    try:
        if files is not None:
            found = {"plugins": [Path(f) for f in files if Path(f).suffix.lower() in PLUGIN_EXT],
                     "bsas": [Path(f) for f in files if Path(f).suffix.lower() == ".bsa"],
                     "loose": [], "fomod": False, "fontconfig": None}
        else:
            folder = source if source.is_dir() else _extract(source, tmpdir)
            from . import variants as VA
            vres = VA.choose(VA.files_of(folder), pack.mode)
            found = scan_mod(folder, vres["skip"])
            vnote = VA.note(vres)
            if vnote:
                rep.notes.append(vnote)
            info_f = folder / CONVERTED_INFO
            if info_f.is_file():
                # a mod this app converted earlier: keep its ini lists, settings and origin
                try:
                    info = json.loads(info_f.read_text(encoding="utf-8"))
                except (OSError, ValueError):
                    info = {}
                if ini_keys is None and isinstance(info.get("ini_keys"), dict):
                    ini_keys = info["ini_keys"] or None
                if "converted" not in meta and isinstance(info.get("converted"), dict):
                    meta["converted"] = info["converted"]
                if given is None and isinstance(info.get("source"), dict):
                    given = info["source"]
                if mod_id is None and info.get("name"):
                    mod_id = str(info["name"])
        if not found["plugins"] and not found["bsas"]:
            if found["fomod"]:
                raise BuildError("This mod has a FOMOD installer. Open it from Convert mods: the "
                                 "assistant walks you through its options.",
                                 "Este mod trae instalador FOMOD. Ábrelo desde Convertir mods: el "
                                 "asistente te lleva por sus opciones.")
            raise BuildError("I didn't find any .esp/.esm/.esl or .bsa in it",
                             "No encontré ningún .esp/.esm/.esl ni .bsa")
        if found["fomod"]:
            rep.notes.append(("It has a FOMOD folder; I only copied the plugins and BSAs I found. "
                              "Check that you got the option you wanted.",
                              "Trae carpeta FOMOD; solo copié los plugins y BSA que encontré. "
                              "Revisa que sea la opción que querías."))
        if found["loose"]:
            rep.notes.append(("It has loose folders (" + ", ".join(p.name for p in found["loose"]) +
                              "). Loose files aren't confirmed to work on Switch; open the mod from Convert mods "
                              "to pack them into a BSA.",
                              "Trae carpetas sueltas (" + ", ".join(p.name for p in found["loose"]) +
                              "). No está confirmado que los archivos sueltos funcionen en Switch; "
                              "ábrelo desde Convertir mods para empacarlos en un BSA."))
        if pack.mode == "SE":
            from .edition import se_needs
            # an .esl file has to be renamed (and its voices/FaceGen folders with it):
            # that's Convert's job. A flagged .esp/.esm only loses the flag (below).
            esl = [p.name for p in found["plugins"] if p.suffix.lower() == ".esl"]
            if esl:
                raise BuildError(
                    f"{', '.join(esl)} is made for the Anniversary Edition (ESL) and this pack is SE. "
                    "Open it from Convert mods: it turns it into an .esp that SE can load.",
                    f"{', '.join(esl)} está hecho para la Anniversary (ESL) y este pack es SE. "
                    "Ábrelo desde Convertir mods: lo convierto en un .esp que SE sí carga.")
        names = [p.name for p in found["plugins"] + found["bsas"]]
        dup = [n for n in names if (pack.data_dir / n).exists()]
        if dup:
            raise BuildError("These files are already in Data: " + ", ".join(dup) +
                             ". Remove the old mod first.",
                             "Estos archivos ya están en Data: " + ", ".join(dup) +
                             ". Quita primero el mod viejo.")
        # PC-format check on a sample of textures
        pc = 0
        for b in found["bsas"]:
            try:
                arc = read_bsa(b)
                with b.open("rb") as fh:
                    for e in [e for e in arc.entries if e.name.lower().endswith(".dds")][:40]:
                        info = inspect_tex(arc.read_head(e, 256, fh))
                        if info and info.container == "DDS":
                            pc += 1
            except Exception:  # noqa: BLE001
                rep.notes.append((f"I couldn't read {b.name}; check that it's a Skyrim SE BSA.",
                                  f"No pude leer {b.name}; revisa que sea un BSA de Skyrim SE."))
        if pc and not (meta or {}).get("converted"):
            rep.notes.append(("Some textures are in PC format (not converted for Switch). They "
                              "may work as DXT5; if they look purple or black, convert the mod.",
                              "Algunas texturas están en formato de PC (sin convertir para Switch). "
                              "Pueden funcionar en DXT5; si se ven moradas o negras, hay que "
                              "convertir el mod."))
        if isinstance(given, dict):
            prov = dict(given)
            if norm_nexus(nexus) and not prov.get("nexus"):
                prov["nexus"] = norm_nexus(nexus)
        else:   # md5 of the archive / fingerprint of the folder, before anything is written
            prov = source_block(Path(given) if given else source, nexus=nexus,
                                files=files if not given and source.is_dir() else None)
        loose_out = []
        fc_src = found.get("fontconfig")
        with Transaction(pack.root, title or f"Add mod: {source.name}") as tx:
            for f in found["plugins"] + found["bsas"]:
                tx.copy_in(f, pack.data_dir / f.name)
                rep.added.append(f.name)
            if fc_src is not None:
                loose_out.append(_install_fontconfig(pack, tx, fc_src, rep))
            # load list
            new_plugins = _order_new(found["plugins"])
            if new_plugins:
                path = pack.list_path
                if not path:
                    raise BuildError("This modpack has no load list", "Este modpack no tiene lista de carga")
                raw = path.read_bytes()
                entries = C.parse_ccc(raw).entries
                at = base_block_end(pack, entries) if first else None
                from .converter import renamed_registry
                from .rename import rename_masters
                reg = renamed_registry(pack)
                for p in new_plugins:
                    h = read_header(pack.data_dir / p.name)
                    # a master the converter (or Rename) gave a new name in this pack:
                    # point the plugin at that name, as converting it would
                    have = {e.lower().lstrip("#") for e in entries}
                    olds = [m for m in h.masters if m.lower() not in have and m.lower() in reg]
                    remap = {m.lower(): reg[m.lower()] for m in olds}
                    if remap:
                        dest = pack.data_dir / p.name
                        out, n = rename_masters(dest.read_bytes(), remap)
                        if n:
                            tx.write_bytes(dest, out)
                            h = read_header(dest)
                            done = [f"{m} → {remap[m.lower()]}" for m in olds]
                            rep.notes.append((f"{p.name} uses masters that have another name in this pack; "
                                              f"I pointed it at them: {', '.join(done)}.",
                                              f"{p.name} usa masters que en este pack tienen otro nombre; "
                                              f"lo apunté a ellos: {', '.join(done)}."))
                    if pack.mode == "SE":
                        from .edition import adapt_bytes_for_se, cc_masters, cc_note
                        if h.is_light_flag:
                            rep.notes.append((f"{p.name} had the ESL flag (Anniversary); I cleared it so SE loads it.",
                                              f"{p.name} traía la marca ESL (Anniversary); se la quité para que SE lo cargue."))
                        if h.is_light_flag or round(h.hedr_version, 2) >= 1.71:
                            dest = pack.data_dir / p.name
                            fixed = adapt_bytes_for_se(dest.read_bytes())
                            tx.write_bytes(dest, fixed)
                            if round(h.hedr_version, 2) >= 1.71:
                                from .records import hedr_offset
                                import struct as _st
                                now = round(_st.unpack_from("<f", fixed, hedr_offset(fixed))[0], 2)
                                rep.notes.append(
                                    (f"{p.name} was saved for a newer game version (HEDR 1.71); "
                                     "I set it to 1.70 so SE loads it.",
                                     f"{p.name} venía guardado para una versión más nueva del juego "
                                     "(HEDR 1.71); lo dejé en 1.70 para que SE lo cargue.") if now < 1.71 else
                                    (f"{p.name} is HEDR 1.71 and has records below 0x800, so I didn't change it: "
                                     "the Doctor explains what to do.",
                                     f"{p.name} es HEDR 1.71 y tiene registros por debajo de 0x800, así que no lo "
                                     "cambié: el Doctor explica qué hacer."))
                        ccm = cc_masters(h.masters)
                        if ccm:          # it can't load on SE: in Data, but not switched on
                            en, es = cc_note(p.name, ccm)
                            rep.notes.append((en + " I left it in Data without activating it.",
                                              es + " Lo dejé en Data sin activarlo."))
                            continue
                    missing = [m for m in h.masters if m.lower() not in {e.lower() for e in entries}
                               and m not in K.VANILLA_MASTERS + K.SWITCH_MASTERS
                               and not (pack.mode == "SE" and _is_cc(m))]
                    if missing:
                        rep.notes.append((f"{p.name} needs {', '.join(missing)}, which isn't in "
                                          "the modpack yet.",
                                          f"{p.name} necesita {', '.join(missing)}, que todavía "
                                          "no está en el modpack."))
                    if p.name.lower() in {e.lower().lstrip("#") for e in entries}:
                        continue                 # already in the list: it keeps its place
                    if at is None:
                        entries.append(p.name)   # after everything, so its masters come first
                    else:
                        entries.insert(at, p.name)
                        at += 1
                    rep.list_added.append(p.name)
                out = C.reorder(raw, entries)
                size = C.over_limit(pack, raw, out)
                if size:
                    raise BuildError(*C.limit_message(size))
                tx.write_bytes(path, out)
            # BSAs without a plugin go to the ini
            stems = {Path(p.name).stem.lower() for p in found["plugins"]}
            stems |= {Path(e).stem.lower() for e in pack.list_entries}
            loose_bsas = []
            placed: list[str] = []
            for b in found["bsas"]:
                s = Path(b.name).stem.lower()
                base = s[:-11] if s.endswith(" - textures") else s
                if base not in stems:
                    loose_bsas.append(b)
            for b in loose_bsas:
                name = b.name
                keys = [ini_keys[name]] if ini_keys and name in ini_keys else \
                    _archive_key_for(pack.data_dir / name)
                for key in keys:
                    paths = pack.inis_for_key(key)
                    if not paths:
                        raise BuildError(f"No ini has {key}", f"Ningún ini tiene {key}")
                    added = False
                    for ini_path in paths:
                        raw = ini_path.read_bytes()
                        cur = parse_ini(raw).archive_list(key)
                        if name.lower() in [c.lower() for c in cur]:
                            continue
                        cur.append(name)
                        if first:
                            cur = K.after_vanilla(cur, placed + [name])
                        if len(", ".join(cur)) > ARCHIVE_LIST_LIMIT:
                            raise BuildError(
                                f"{key} in {ini_path.name} would go over 1024 characters. Shorten "
                                "BSA names (Koka's tip: 'Mod - Meshes.bsa' → '1M.bsa').",
                                f"{key} en {ini_path.name} pasaría de 1024 caracteres. Acorta "
                                "nombres de BSA (consejo de Koka: 'Mod - Meshes.bsa' → '1M.bsa').")
                        tx.write_bytes(ini_path, set_archive_list(raw, key, cur))
                        added = True
                    if added:
                        rep.ini_added.append((key, name))
                        placed.append(name)
                    if key == "sResourceArchiveList2" and not pack.lang_inis:
                        rep.notes.append((
                            f"{name} went to Skyrim.ini, but the pack has no language ini "
                            "(Skyrim_en.ini, Skyrim_es.ini...). The console's own one replaces that "
                            "list, so add yours from the clean dump.",
                            f"{name} quedó en Skyrim.ini, pero el pack no tiene ini de idioma "
                            "(Skyrim_en.ini, Skyrim_es.ini...). El de la consola reemplaza esa lista; "
                            "agrega el tuyo desde los inis limpios."))
            mods = load_mods(pack)
            if loose_out:      # the FontConfig.txt now belongs to this mod, not to an earlier font mod
                for rec in mods.values():
                    if rec.get("loose"):
                        rec["loose"] = [x for x in rec["loose"] if x.lower() not in {y.lower() for y in loose_out}]
                        if not rec["loose"]:
                            del rec["loose"]
            mod_id = mod_id or (source.stem if source.is_file() else source.name)
            base_id, n = mod_id, 2
            while mod_id in mods:
                mod_id, n = f"{base_id} ({n})", n + 1
            mods[mod_id] = {"added": time.strftime("%Y-%m-%d %H:%M:%S"),
                            "plugins": [p.name for p in new_plugins],
                            "bsas": [b.name for b in found["bsas"]],
                            "ini": [{"key": k, "bsa": b} for k, b in rep.ini_added],
                            **({"loose": loose_out} if loose_out else {}),
                            **meta, "source": prov}
            _save_mods(pack, tx, mods)
            rep.mod_id = mod_id
            if also:
                also(tx)          # more changes that belong to the same step (one undo)
        rep.history = tx.dir.name if tx.changed else None
        if files is None and (folder / "behavior-sources.zip").is_file():
            from .behaviors import store_zip
            store_zip(pack, rep.mod_id, folder / "behavior-sources.zip")
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)
    pack.reload()
    return rep


# ---------------------------------------------------------------- remove a mod
def _install_fontconfig(pack: Pack, tx: Transaction, src: Path, rep: Report) -> str:
    """A font mod's FontConfig.txt, loose in Data\\Interface (fonts.py)."""
    from . import fonts as FN
    dest = pack.data_dir.joinpath(*FN.LOOSE_REL)
    # an existing one in any case (fontconfig.txt / FontConfig.txt) is the one the game reads
    old = next((p for p in (dest.parent.iterdir() if dest.parent.is_dir() else [])
                if p.name.lower() == FN.NAME), None)
    new_fc = FN.read(src)
    if old is not None:
        prev = FN.label(FN.read(old)) or old.name
        tx.trash(old)
        rep.notes.append((f"It replaces the font that was active ({prev}): only one FontConfig.txt can be. "
                          "Undoing this step brings it back.",
                          f"Reemplaza la fuente que estaba activa ({prev}): solo puede haber un FontConfig.txt. "
                          "Deshacer este paso la devuelve."))
    tx.copy_in(src, dest)
    name = FN.label(new_fc)
    rep.notes.append(((f"Font {name}: " if name else "Font mod: ") +
                      "its FontConfig.txt went loose to Data\\Interface (fonts only load that way).",
                      (f"Fuente {name}: " if name else "Mod de fuente: ") +
                      "su FontConfig.txt quedó suelto en Data\\Interface (las fuentes solo cargan así)."))
    rep.added.append("Interface\\FontConfig.txt")
    return "Interface/FontConfig.txt"


def _record_of(mods: dict, plugin: str) -> str | None:
    low = plugin.lower()
    for mod_id, rec in mods.items():
        if any(p.lower() == low for p in rec.get("plugins", [])):
            return mod_id
    return None


def removal_users(pack: Pack, name: str) -> list[dict]:
    """Plugins that use what removing `name` takes away as a master, and the
    ones that use those, as [{plugin, mod, whole}]: `mod` is the mod they belong to
    (None for a loose plugin) and `whole` says the whole mod goes with them
    (False: only that plugin leaves its mod, the rest stays)."""
    mods = load_mods(pack)
    if name in mods:
        start = {p.lower() for p in mods[name].get("plugins", [])}
    elif Path(name.lower()).suffix in PLUGIN_EXT:
        start = {name.lower()}
    else:
        return []
    gone, out, todo = set(start), [], list(start)
    while todo:
        cur = todo.pop()
        for h in pack.plugins.values():
            low = h.name.lower()
            if low not in gone and any(m.lower() == cur for m in h.masters):
                gone.add(low)
                todo.append(low)
                out.append(h.name)
    rows = []
    for u in out:
        mod_id = _record_of(mods, u)
        whole = bool(mod_id) and mod_id != name and all(p.lower() in gone for p in mods[mod_id].get("plugins", []))
        rows.append({"plugin": u, "mod": mod_id, "whole": whole})
    return rows


def remove_mod(pack: Pack, name: str, with_users: bool = False) -> str | None:
    """Remove a mod added with add_mod (by its id), or a single plugin with its
    BSAs, or a single ini-loaded BSA. Files go to the project trash.

    Plugins that use it as a master stop it (BuildError with `.users`), unless
    with_users: then they go too, in the same step. A plugin that shares its
    mod with others leaves that mod alone, with the BSAs named after it; the
    rest of the mod stays."""
    mods = load_mods(pack)
    if name in mods:
        rec = mods[name]
        plugins, bsas = list(rec.get("plugins", [])), list(rec.get("bsas", []))
    elif Path(name.lower()).suffix in PLUGIN_EXT:
        plugins, bsas = [name], [b.name for b in pack.bsas_for_plugin(name)]
    else:
        plugins, bsas = [], [name]
    users = removal_users(pack, name)
    if users and not with_users:
        err = BuildError(*_users_msg([u["plugin"] for u in users]))
        err.users = users
        raise err
    drop_records = [name] if name in mods else []
    loose: list[str] = list(mods[name].get("loose", [])) if name in mods else []
    edit_records: dict[str, list[str]] = {}       # mod id -> plugins leaving it
    if name not in mods and plugins:
        rid = _record_of(mods, plugins[0])
        if rid:
            edit_records.setdefault(rid, []).append(plugins[0])
    for u in users:
        if u["whole"]:
            if u["mod"] not in drop_records:
                drop_records.append(u["mod"])
                r = mods[u["mod"]]
                plugins += [p for p in r.get("plugins", []) if p not in plugins]
                bsas += [b for b in r.get("bsas", []) if b not in bsas]
                loose += r.get("loose", [])
        else:
            plugins.append(u["plugin"])
            bsas += [b.name for b in pack.bsas_for_plugin(u["plugin"]) if b.name not in bsas]
            if u["mod"]:
                edit_records.setdefault(u["mod"], []).append(u["plugin"])
    gone = {p.lower() for p in plugins}
    label = name if not users else f"{name} + {', '.join(u['plugin'] for u in users)}"
    with Transaction(pack.root, f"Remove mod: {label}") as tx:
        path = pack.list_path
        if path and plugins:
            raw = path.read_bytes()
            # off lines ('#') too: a plugin that's gone leaves no trace in the list
            keys = {e for e in C.parse_ccc(raw).entries if e.lstrip("#").strip().lower() in gone}
            if keys:
                tx.write_bytes(path, C.edit_lines(raw, {k: None for k in keys}))
        bsa_names = {b.lower() for b in bsas}
        for ini in pack.ini_paths:
            raw = ini.read_bytes()
            new = raw
            for key in ("sResourceArchiveList", "sResourceArchiveList2", "sArchiveToLoadInMemoryList"):
                if parse_ini(new).get("Archive", key) is None:
                    continue
                cur = parse_ini(new).archive_list(key)
                if any(c.lower() in bsa_names for c in cur):
                    new = set_archive_list(new, key, [c for c in cur if c.lower() not in bsa_names])
            if new != raw:
                tx.write_bytes(ini, new)
        for f in plugins + bsas:
            p = pack.data_dir / f
            if p.exists():
                tx.trash(p)
        for rel in loose:
            p = pack.data_dir.joinpath(*rel.replace("\\", "/").split("/"))
            if p.exists():
                tx.trash(p)
        changed = False
        for rid in drop_records:
            if rid in mods:
                del mods[rid]
                changed = True
        for rid, leaving in edit_records.items():
            if rid in mods and rid not in drop_records:
                out = {x.lower() for x in leaving}
                gone_bsas = {b.lower() for b in bsas}
                r = mods[rid]
                r["plugins"] = [x for x in r.get("plugins", []) if x.lower() not in out]
                r["bsas"] = [x for x in r.get("bsas", []) if x.lower() not in gone_bsas]
                changed = True
        if changed:
            _save_mods(pack, tx, mods)
    pack.reload()
    return tx.dir.name if tx.changed else None


def mods_view(pack: Pack) -> list[dict]:
    """One row per mod. Mods added here keep their files together; anything
    else is shown as a plugin with its BSAs, or a BSA loaded from the ini."""
    lists = pack.archive_lists()
    ini_items = {b.lower() for v in lists.values() for b in v}
    order = [n.lower() for n, _ in pack.load_order()]
    rows, used = [], set()
    for mod_id, rec in load_mods(pack).items():
        files = rec.get("plugins", []) + rec.get("bsas", [])
        present = [f for f in files if (pack.data_dir / f).exists()]
        if not present:
            continue
        used |= {f.lower() for f in present}
        first = min([order.index(p.lower()) for p in rec.get("plugins", []) if p.lower() in order]
                    or [10_000])
        low_present = {f.lower() for f in present}
        rows.append({"id": mod_id, "name": mod_id, "kind": "mod",
                     "plugins": [f for f in rec.get("plugins", []) if f.lower() in low_present],
                     "bsas": [f for f in rec.get("bsas", []) if f.lower() in low_present], "pos": first,
                     "size": sum((pack.data_dir / f).stat().st_size for f in present)})
    for i, (name, src) in enumerate(pack.load_order()):
        h = pack.plugins.get(name.lower())
        if not h or h.name.lower() in used:
            continue
        bs = [b for b in pack.bsas_for_plugin(name) if b.name.lower() not in used]
        used |= {b.name.lower() for b in bs} | {h.name.lower()}
        rows.append({"id": h.name, "name": h.name, "kind": "plugin", "plugins": [h.name],
                     "bsas": [b.name for b in bs], "pos": i,
                     "size": h.size + sum(b.stat().st_size for b in bs)})
    for low, p in pack.bsas.items():
        if low in used or low not in ini_items:
            continue
        rows.append({"id": p.name, "name": p.name, "kind": "bsa", "plugins": [], "bsas": [p.name],
                     "pos": 20_000, "size": p.stat().st_size})
    rows.sort(key=lambda r: r["pos"])
    return rows
