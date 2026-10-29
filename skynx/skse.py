"""Does a mod need SKSE? Read its scripts and find out.

PC mods often rely on SKSE (the PC Script Extender) or on SkyUI's MCM menu,
which is built on SKSE. Their compiled scripts (.pex) name the script
types and functions they call in their string table, so a cheap scan of
that table tells us, before converting anything:

- MCM: a script that extends SKI_ConfigBase (SkyUI's menu base).
- SKSE: calls to scripts that only exist with SKSE or SKSE plugins
  (UI, Input, StringUtil, ModEvent, PapyrusUtil, JContainers, ...) or to
  functions SKSE adds to the game's own scripts (GetSKSEVersion,
  RegisterForKey, RegisterForModEvent, ...).
- Native SKSE plugins: .dll files under SKSE\\Plugins.

The lists are deliberately conservative (names that only exist with SKSE),
so a hit is a strong sign; no hit doesn't prove the mod is SKSE-free.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from . import pex as PEX

MCM_BASES = {"ski_configbase"}
SKSE_SCRIPTS = {
    "skse", "stringutil", "modevent", "netimmerse", "uicallback", "wornobject",
    "actorvalueinfo", "papyrusutil", "storageutil", "jsonutil", "miscutil", "jcontainers",
    "jmap", "jarray", "jvalue", "jdb", "jformmap", "jstring", "nioverride", "racemenu",
    "po3_sksefunctions", "po3_events_alias", "po3_events_form", "consoleutil",
    "dbmiscfunctions", "mfgconsolefunc", "fissfactory", "fissinterface", "spe_actor",
    "spe_objectref", "spe_utility", "ostim", "sexlab", "skymessage", "extendedvanillamenus",
}
SKSE_FUNCTIONS = {
    "getsksereleaseversion", "getskseversion", "getskseversionminor", "getskseversionbeta",
    "getskseversionrelease", "getscriptversionrelease", "registerforkey", "registerforcontrol",
    "registerformodevent", "registerformenu", "sendmodevent", "registerforcamerastate",
    "registerforcrosshairref", "registerforactoraction", "getmappedkey", "iskeypressed",
    "unregisterforallkeys", "getnumitems", "getnthform", "getwornform", "setgamesettingfloat",
    "getmodbyname", "getmodcount", "invokestring", "invokeint", "invokebool", "invokefloat",
    "invokeform", "invokestringa", "ismenuopen", "opencustommenu",
}


@dataclass
class SkseReport:
    scripts: int = 0
    mcm: list[str] = field(default_factory=list)          # scripts that build an MCM menu
    skse: list[str] = field(default_factory=list)         # scripts that call SKSE
    examples: list[str] = field(default_factory=list)     # names found, for the message
    dlls: list[str] = field(default_factory=list)
    unreadable: int = 0

    @property
    def needs_skse(self) -> bool:
        return bool(self.skse or self.dlls or self.mcm)

    def notes(self) -> list[dict]:
        out = []
        if self.mcm:
            out.append({"level": "warn",
                        "en": f"It has an MCM menu ({len(self.mcm)} script). MCM needs SkyUI and SKSE; "
                              "on Switch the menu won't appear, so its options keep their defaults.",
                        "es": f"Trae menú MCM ({len(self.mcm)} script). El MCM necesita SkyUI y SKSE; "
                              "en Switch el menú no aparece y sus opciones quedan por defecto."})
        strong = [e for e in self.examples if e != "skse"]
        if self.skse and not strong and not self.dlls:
            out.append({"level": "info",
                        "en": f"{len(self.skse)} scripts check whether SKSE is installed. That's "
                              "usually an optional extra; the rest of the mod works without it.",
                        "es": f"{len(self.skse)} scripts revisan si SKSE está instalado. Suele ser un "
                              "extra opcional; el resto del mod funciona sin él."})
        elif self.skse or self.dlls:
            ex = ", ".join(strong[:5])
            what = f"{len(self.skse)} scripts call SKSE" + (f" ({ex})" if ex else "")
            what_es = f"{len(self.skse)} scripts usan SKSE" + (f" ({ex})" if ex else "")
            if self.dlls:
                what += f"; {len(self.dlls)} PC SKSE plugins (.dll)"
                what_es += f"; {len(self.dlls)} plugins de SKSE de PC (.dll)"
            out.append({"level": "warn",
                        "en": f"It uses SKSE: {what}. The parts that depend on it won't work on Switch.",
                        "es": f"Usa SKSE: {what_es}. Lo que dependa de eso no va a funcionar en Switch."})
        return out


def scan_strings(names: list[str], rep: SkseReport, label: str) -> None:
    low = {s.lower() for s in names}
    if low & MCM_BASES:
        rep.mcm.append(label)
    hits = (low & SKSE_SCRIPTS) | (low & SKSE_FUNCTIONS)
    if hits:
        rep.skse.append(label)
        for h in sorted(hits):
            if h not in rep.examples:
                rep.examples.append(h)


def scan_tree(folder: Path) -> SkseReport:
    """Scripts and SKSE dlls in a loose folder (a staged mod)."""
    rep = SkseReport()
    folder = Path(folder)
    for p in folder.rglob("*"):
        if not p.is_file():
            continue
        ext = p.suffix.lower()
        if ext == ".pex":
            rep.scripts += 1
            try:
                scan_strings(PEX.strings(p.read_bytes()), rep, p.stem)
            except Exception:  # noqa: BLE001
                rep.unreadable += 1
        elif ext == ".dll" and "skse" in [x.lower() for x in p.parts]:
            rep.dlls.append(p.name)
    return rep


def scan_bsa(path: Path, rep: SkseReport | None = None) -> SkseReport:
    """Scripts inside a BSA (Switch mods keep them packed)."""
    from .bsa import read_bsa
    rep = rep or SkseReport()
    arc = read_bsa(Path(path))
    with arc.path.open("rb") as f:
        for e in arc.entries:
            if e.name.lower().endswith(".pex"):
                rep.scripts += 1
                try:
                    scan_strings(PEX.strings(arc.read_file(e, f)), rep, e.name[:-4])
                except Exception:  # noqa: BLE001
                    rep.unreadable += 1
    return rep
