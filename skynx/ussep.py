"""USSEP builds for Switch (Koka's "KokaNX" conversion) for new packs.

The folder the user keeps (default C:\\SkyNX\\Base Mods\\USSEP) holds one plugin per
variant and the four BSAs all variants share:

  All_CC/        masters: the base game + Fish, Survival Mode, Curios, Saints & Seducers
  SurvivalMode/  masters: the base game + Survival Mode
  No_CC/         masters: the base game only (SE packs, or AE without Creation Club)
  USSEP.bsa      meshes and scripts         -> sResourceArchiveList
  USSEPA.bsa     animations                 -> sResourceArchiveList
  USSEPT.bsa     textures                   -> sResourceArchiveList2
  USSEPV.bsa     voices                     -> sResourceArchiveList2

The BSAs don't share the plugin's name, so they load through the inis
(the way Ashiro's pack does it). As KokaNX advises, they go right after the
game's own BSAs in each list, and the plugin goes first in the load list,
right after the Creation Club entries (AE) or at the top of Plugins (SE).
Nothing goes to sArchiveToLoadInMemoryList (Koka, Oct 2026: animations
don't need it). The plugin keeps its exact name: its voices
live under sound\\voice\\unofficial skyrim special edition patch.esp.
"""
from __future__ import annotations

from pathlib import Path

from . import ccc as C
from . import knowledge as K
from .builder import BuildError, add_mod
from .history import Transaction
from .pack import Pack
from .plugin import read_header

PLUGIN = K.USSEP_PLUGIN
VARIANTS = ("All_CC", "SurvivalMode", "No_CC")
DEFAULT_DIR = Path(r"C:\SkyNX\Base Mods\USSEP")


def _child(folder: Path, name: str) -> Path | None:
    if not folder.is_dir():
        return None
    for c in folder.iterdir():
        if c.name.lower() == name.lower():
            return c
    return None


def scan(folder: Path | str | None) -> dict:
    """Variants available in the folder, with their masters."""
    folder = Path(folder or DEFAULT_DIR)
    out = {"folder": str(folder), "exists": folder.is_dir(), "variants": [], "bsas": []}
    if not folder.is_dir():
        return out
    out["bsas"] = sorted(p.name for p in folder.iterdir()
                         if p.is_file() and p.suffix.lower() == ".bsa")
    for v in VARIANTS:
        d = _child(folder, v)
        plug = _child(d, PLUGIN) if d else None
        if not plug:
            continue
        h = read_header(plug)
        out["variants"].append({
            "id": v, "plugin": str(plug), "size": plug.stat().st_size,
            "cc": [m for m in h.masters if m not in K.VANILLA_MASTERS + K.SWITCH_MASTERS]})
    return out


def install(pack: Pack, folder: Path | str | None, variant: str) -> dict:
    """Add the chosen USSEP variant to a pack: missing Creation Club masters
    first (AE), then the plugin and its four BSAs through builder.add_mod,
    placed before every other mod."""
    info = scan(folder)
    v = next((x for x in info["variants"] if x["id"] == variant), None)
    if not v:
        raise BuildError(f"The USSEP folder has no {variant} version ({info['folder']}).",
                         f"La carpeta de USSEP no tiene la versión {variant} ({info['folder']}).")
    if not info["bsas"]:
        raise BuildError("The USSEP folder has no BSA files.", "La carpeta de USSEP no tiene archivos BSA.")
    if pack.mode == "SE" and v["cc"]:
        raise BuildError("The SE version can't use Creation Club masters; pick No_CC.",
                         "La versión SE no puede usar masters del Creation Club; elige No_CC.")
    notes = []
    if pack.mode == "AE" and v["cc"]:
        raw = pack.list_path.read_bytes()
        entries = C.parse_ccc(raw).entries
        have = {e.lower() for e in entries}
        need = [m for m in v["cc"] if m.lower() not in have]
        if need:
            # Creation Club entries go before the first mod.
            cc = {c.lower() for c in K.AE_CC_PLUGINS}
            first_mod = next((i for i, e in enumerate(entries) if e.lower() not in cc), len(entries))
            new = entries[:first_mod] + need + entries[first_mod:]
            cur = C.parse_ccc(raw)
            nl = cur.newline if cur.newline in ("CRLF", "LF") else "CRLF"
            out = C.render(new, nl, cur.trailing_newline or not entries)
            size = C.over_limit(pack, raw, out)
            if size:
                raise BuildError(*C.limit_message(size))
            with Transaction(pack.root, "Add Creation Club masters for USSEP") as tx:
                tx.write_bytes(pack.list_path, out)
            pack.reload()
            notes.append((f"Added the Creation Club masters USSEP needs: {', '.join(need)}.",
                          f"Agregué los masters del Creation Club que pide USSEP: {', '.join(need)}."))
    folder = Path(info["folder"])
    files = [Path(v["plugin"])] + [folder / b for b in info["bsas"]]
    from .recipe import source_block
    prov = source_block(folder, kind="ussep", files=files, variant=variant)
    rep = add_mod(pack, folder, mod_id=f"USSEP (KokaNX, {variant})",
                  meta={"ussep": variant, "source": prov}, files=files, first=True)
    rep.notes[:0] = notes
    return rep


def is_ussep_bsa(name: str) -> bool:
    """KokaNX's names (USSEP.bsa, USSEPA, USSEPT, USSEPV) or the plugin's own BSAs."""
    low = name.strip().lower()
    stem = Path(PLUGIN).stem.lower()
    return low in {b.lower() for b in K.USSEP_KOKA_BSAS} or low in (stem + ".bsa", stem + " - textures.bsa")


def first_slot(pack: Pack, entries: list[str], plugin: str = PLUGIN) -> tuple[list[str], int]:
    """Where a mod that must load first goes: the list without it, and the
    index right after the Creation Club / vanilla lines (and after its own
    masters, if one of them is listed further down)."""
    from .builder import base_block_end
    rest = [e for e in entries if e.lower() != plugin.lower()]
    at = base_block_end(pack, rest)
    h = pack.plugins.get(plugin.lower())
    masters = {m.lower() for m in (h.masters if h else [])}
    last = max((i + 1 for i, e in enumerate(rest) if e.lower() in masters), default=0)
    return rest, max(at, last)


def ussep_bsas(pack: Pack) -> list[str]:
    """USSEP's BSAs in this pack: the plugin's own ones and KokaNX's names."""
    names = {b.lower() for b in K.USSEP_KOKA_BSAS}
    out = [p.name for low, p in sorted(pack.bsas.items()) if low in names]
    out += [b.name for b in pack.bsas_for_plugin(PLUGIN) if b.name not in out]
    return out
