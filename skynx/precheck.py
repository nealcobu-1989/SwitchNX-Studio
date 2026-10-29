"""Quick check of a mod that is supposed to be already converted for Switch
(the kind shared on Discord) before it goes into a pack.

It answers: can it go in as it is, or should it pass through the converter
first (which fixes names and can shrink textures)? Nothing is written to the
pack here.
"""
from __future__ import annotations

import shutil
import tempfile
from pathlib import Path

from . import knowledge as K
from .audit import norm_name, plugin_owners
from .bsa import read_bsa
from .builder import scan_mod
from .converter import renamed_registry
from .pack import Pack
from .plugin import read_header
from .textures import inspect as inspect_tex
from .texplan import DEFAULT_PRESET  # noqa: E402


def _note(level: str, en: str, es: str) -> dict:
    return {"level": level, "en": en, "es": es}


def _mb(n: int) -> str:
    return f"{n / 1048576:.0f} MB"


def _pack_files(pack: Pack) -> set[str]:
    from .requirements import loose_files
    have: set[str] = set(loose_files(pack.data_dir))
    for b in pack.bsas.values():
        try:
            have.update(e.path.lower() for e in read_bsa(b).entries)
        except Exception:  # noqa: BLE001
            pass
    return have


def _asset_notes(pack, plugins, bsas, vanilla, others, cache_dir) -> list[dict]:
    from .requirements import mod_asset_gaps
    if not plugins:
        return []
    if vanilla is None:
        return [_note("info", "Set the Vanilla folder (console BSAs) in Settings and I'll also check whether "
                              "a BSA of this mod is missing.",
                      "Configura la carpeta Vanilla (los BSA de la consola) en Ajustes y también reviso si "
                      "le falta algún BSA a este mod.")]
    gaps = mod_asset_gaps(plugins, bsas, set(vanilla) | _pack_files(pack), others, cache_dir)
    n_m, n_s, n_t = len(gaps["meshes"]), len(gaps["scripts"]), len(gaps["textures"])
    if not (n_m or n_s or n_t):
        return []
    ex = (gaps["meshes"] + gaps["scripts"] + gaps["textures"])[:3]
    what_en = ", ".join(x for x in (f"{n_m} meshes" if n_m else "", f"{n_s} scripts" if n_s else "",
                                    f"{n_t} textures" if n_t else "") if x)
    what_es = ", ".join(x for x in (f"{n_m} meshes" if n_m else "", f"{n_s} scripts" if n_s else "",
                                    f"{n_t} texturas" if n_t else "") if x)
    tex_hint = n_t and not any(Path(b).stem.lower().endswith(" - textures") for b in bsas)
    out = [_note("warn",
                 f"It uses {what_en} that aren't in its BSAs, the pack or the base game (e.g. {', '.join(ex)}). "
                 "A BSA of this mod is probably missing" + (" (often 'Name - Textures.bsa')" if tex_hint else "") + ".",
                 f"Usa {what_es} que no están en sus BSA, ni en el pack ni en el juego base (p. ej. {', '.join(ex)}). "
                 "Probablemente le falta un BSA" + (" (muchas veces 'Nombre - Textures.bsa')" if tex_hint else "") + ".")]
    for name, n in sorted(gaps["found_in"].items(), key=lambda kv: -kv[1]):
        out.append(_note("info",
                         f"{n} of them are in {name}, next to it: they were probably consolidated there. Bring it too.",
                         f"{n} de ellos están en {name}, al lado: probablemente se consolidaron ahí. Tráelo también."))
    return out


def precheck(pack: Pack, source: Path, progress=None, vanilla: set[str] | None = None,
             origin: Path | None = None, cache_dir=None) -> dict:
    """origin: where a loose plugin/BSA was picked (its neighbours may hold
    files of the mod consolidated into another BSA)."""
    from .intake import safe_extract
    from .skse import SkseReport, scan_bsa
    from .diet import estimate_bsa
    source = Path(source)
    tick = progress or (lambda *a, **k: None)
    work = None
    try:
        from .intake import bundle_to_folder, loose_bundle
        if source.is_dir():
            folder = source
        elif loose_bundle(source):
            work = Path(tempfile.mkdtemp(prefix="skynx-mod-"))
            folder = bundle_to_folder(source, work / source.stem)
            origin = origin or source
        else:
            work = Path(tempfile.mkdtemp(prefix="skynx-mod-"))
            folder = safe_extract(source, work / "src", progress)
        from . import variants as VA
        vres = VA.choose(VA.files_of(folder), pack.mode)
        found = scan_mod(folder, vres["skip"])
        notes: list[dict] = []
        vn = VA.note(vres)
        if vn:
            notes.append(_note("info", vn[0], vn[1]))
        convert = False
        plugins = found["plugins"]
        bsas = found["bsas"]
        names = {p.name.lower() for p in plugins}
        game = {m.lower() for m in K.VANILLA_MASTERS + K.SWITCH_MASTERS +
                (K.AE_CC_PLUGINS if pack.mode != "SE" else [])}
        in_pack = {e.lstrip("#").lower() for e in pack.list_entries} | set(pack.plugins)
        reg = renamed_registry(pack)
        norm_pack = {norm_name(n) for n in in_pack}
        if found["fomod"]:
            notes.append(_note("warn", "It has a FOMOD installer: open it from Convert mods to choose its options.",
                               "Trae instalador FOMOD: ábrelo desde Convertir mods para elegir sus opciones."))
            convert = True
        if found["loose"]:
            notes.append(_note("warn", "It has loose folders; they need packing into a BSA (Convert does it).",
                               "Trae carpetas sueltas; hay que empacarlas en un BSA (Convertir lo hace)."))
            convert = True
        # plugins: masters, ESL, unsafe names
        for p in plugins:
            h = read_header(p)
            miss = [m for m in h.masters if m.lower() not in game | names | in_pack
                    and m.lower() not in reg and norm_name(m) not in norm_pack]
            if miss:
                notes.append(_note("warn", f"{p.name} needs {', '.join(miss)}, which isn't in the pack.",
                                   f"{p.name} necesita {', '.join(miss)}, que no está en el pack."))
            if round(h.hedr_version or 0, 2) >= 1.71:
                from .records import own_low_formids
                try:
                    low = own_low_formids(p)
                except Exception:  # noqa: BLE001
                    low = 0
                if low:
                    notes.append(_note("warn",
                        f"{p.name} uses {low} record IDs below 0x800 (extended ESL range, Skyrim PC 1.6.1130 from "
                        "December 2023). The Switch version came out in 2022 and probably can't load them; test it "
                        "on the console, or use a version of the mod from before December 2023.",
                        f"{p.name} usa {low} IDs de registro por debajo de 0x800 (rango ESL extendido, Skyrim PC "
                        "1.6.1130 de diciembre de 2023). La versión de Switch salió en 2022 y probablemente no los "
                        "carga; pruébalo en la consola o usa una versión del mod anterior a diciembre de 2023."))
            if pack.mode == "SE":
                from .edition import cc_masters, cc_note, se_needs
                need = se_needs(h)
                if p.suffix.lower() == ".esl":
                    notes.append(_note("warn", f"{p.name} is an ESL; SE can't load it (Convert turns it into an ESP).",
                                       f"{p.name} es ESL; SE no lo carga (Convertir lo pasa a ESP)."))
                    convert = True
                elif need["esl"]:
                    notes.append(_note("info", f"{p.name} has the ESL flag (Anniversary); when it goes in I clear it so SE loads it.",
                                       f"{p.name} trae la marca ESL (Anniversary); al agregarlo se la quito para que SE lo cargue."))
                if need["hedr"]:
                    notes.append(_note("info", f"{p.name} is saved as HEDR 1.71; when it goes in I set it to 1.70 so SE loads it.",
                                       f"{p.name} está guardado como HEDR 1.71; al agregarlo lo dejo en 1.70 para que SE lo cargue."))
                if need["cc"]:
                    en, es = cc_note(p.name, need["cc"])
                    notes.append(_note("crit", en, es))
            from .rename import safe_name
            if safe_name(p.name) != p.name:
                notes.append(_note("info", f"{p.name} has characters Google Drive changes; Convert can give it a safe name.",
                                   f"{p.name} tiene caracteres que Google Drive cambia; Convertir le puede dar un nombre seguro.",))
        # inside the BSAs: orphan voice/FaceGen folders, PC formats, SKSE, diet
        sk = SkseReport()
        pc_tex = pc_snd = 0
        before = after = 0
        for i, b in enumerate(bsas):
            tick(b.name, i, len(bsas))
            try:
                arc = read_bsa(b)
            except Exception as e:  # noqa: BLE001
                notes.append(_note("crit", f"{b.name} can't be read ({e}).", f"No pude leer {b.name} ({e})."))
                continue
            owners = plugin_owners(arc)
            orphans = [o for o in owners if o not in names and o not in game and o not in in_pack]
            if orphans and plugins:
                notes.append(_note("warn",
                    f"{b.name} keeps voices/faces under '{orphans[0]}', which isn't the plugin's name. "
                    "They won't play or show as it is; Convert restores the right name.",
                    f"{b.name} guarda voces/caras como '{orphans[0]}', que no es el nombre del plugin. "
                    "Así no suenan ni se ven; Convertir le devuelve el nombre correcto."))
                convert = True
            with b.open("rb") as f:
                for e in arc.entries[:4000]:
                    n = e.name.lower()
                    if n.endswith(".dds"):
                        info = inspect_tex(arc.read_head(e, 256, f))
                        if info and info.container == "DDS":
                            pc_tex += 1
                    elif n.endswith((".xwm", ".wav")):
                        pc_snd += 1
            scan_bsa(b, sk)
            try:
                est = estimate_bsa(b, DEFAULT_PRESET, bc1=True)
                before += est["before"]
                after += est["after"]
            except Exception:  # noqa: BLE001
                pass
        if pc_tex or pc_snd:
            notes.append(_note("warn",
                f"It still has PC files ({pc_tex} textures, {pc_snd} sounds). Convert finishes the job.",
                f"Todavía trae archivos de PC ({pc_tex} texturas, {pc_snd} sonidos). Convertir termina el trabajo."))
            convert = True
        for n in sk.notes():
            notes.append(n)
        if before - after >= 8 * 2**20:
            notes.append(_note("info",
                f"Its textures could go from {_mb(before)} to about {_mb(after)} with the diet (Convert).",
                f"Sus texturas podrían bajar de {_mb(before)} a unos {_mb(after)} con la dieta (Convertir)."))
        if not plugins and not bsas:
            notes.append(_note("crit", "There's no plugin or BSA in it.", "No trae ningún plugin ni BSA."))
        others = []
        if origin is not None and Path(origin).is_file():
            mine = {b.name.lower() for b in bsas}
            others = [p for p in Path(origin).parent.iterdir()
                      if p.is_file() and p.suffix.lower() == ".bsa" and p.name.lower() not in mine]
        try:
            notes += _asset_notes(pack, plugins, bsas, vanilla, others, cache_dir)
        except Exception:  # noqa: BLE001
            pass
        return {"plugins": [p.name for p in plugins], "bsas": [b.name for b in bsas],
                "notes": notes, "recommend": "convert" if convert else "add",
                "tex_before": before, "tex_after": after,
                "ok": not any(n["level"] == "crit" for n in notes)}
    finally:
        if work:
            shutil.rmtree(work, ignore_errors=True)
