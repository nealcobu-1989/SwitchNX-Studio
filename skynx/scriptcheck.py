"""Doctor checks on what the console actually runs: scripts and sounds.

Four questions the requirement checks don't answer (added after a modlist
whose main quest stalled at Farengar, Oct 2026):

* script-plugin-off: scripts that ask for a plugin by name (GetFormFromFile,
  IsPluginInstalled...) that isn't loaded. Usually an optional check, but after
  removing a mod it's how a leftover script loses what it was built around.
* script-replaces-game / script-replaces-ussep: mod scripts that take the place
  of the game's own or of USSEP's fix. On Switch a BSA in the ini wins over the
  game's and over BSAs that plugins load, whatever the load list says, so an
  older copy of a quest script wins silently.
* audio-broken: Switch voices and music read in full; a file cut short or with
  a wrong size table is what the audio thread trips on.
* script-load: which mods keep scripts running on their own (timers and
  frequent events), as a guide for script-heavy lists.

Script order (conflicts.py): BSAs loaded by plugins first, then the game's own
(first in the ini), then the rest of the ini; loose Data\\scripts last. The
last one that has a script is the one that runs.
"""
from __future__ import annotations

import json
import re
import struct
from collections import defaultdict
from pathlib import Path

from . import knowledge as K
from . import nxaudio as NXA
from . import pex as PEX
from .pack import Pack

PLUGIN_RE = re.compile(r"^[^\\/:*?\"<>|]+\.(esp|esm|esl)$", re.I)
CACHE_FILE = "audiocheck.json"
EXAMPLES = 40

# The base scripts SKSE ships for PC (its copy of the game's own, plus its
# additions). A mod that bundles them replaces the Switch's own base classes
# (Mihail's monster pack in a shared modpack did): the Switch's have functions
# PC's lack (amiibo), and SKSE's natives don't exist without SKSE.
SKSE_BASE = frozenset("""
activemagiceffect actor actorbase actorvalueinfo alias ammo apparatus armor armoraddon art
book camera cell colorcomponent colorform combatstyle constructibleobject defaultobjectmanager
enchantment equipslot faction flora form formlist formtype game gamedata headpart ingredient
input keyword leveledactor leveleditem leveledspell location magiceffect math modevent
netimmerse objectreference outfit perk potion quest race scroll shout skse soulgem sound
sounddescriptor spawnertask spell stringutil textureset treeobject ui uicallback utility
weapon weather wornobject""".split())

# string-table entries that say what a script does by itself
POLL = ("registerforupdate", "registerforupdategametime")
LOOP = ("registerforsingleupdate", "registerforsingleupdategametime")
EVENTS = ("onhit", "onmagiceffectapply", "onobjectequipped", "onobjectunequipped",
          "onitemadded", "onitemremoved", "onlocationchange", "oncellattach",
          "onanimationevent", "onplayerloadgame", "oncombatstatechanged")


def _ussep_bsas(pack: Pack) -> set[str]:
    out = set()
    for low, p in pack.bsas.items():
        if low.startswith("ussep") or low.startswith("unofficial skyrim special edition patch"):
            out.add(p.name.lower())
    for name in pack.plugins:
        if name.startswith("unofficial skyrim special edition patch") or name == "ussep.esp":
            out |= {b.name.lower() for b in pack.bsas_for_plugin(name)}
    return out


def _labels(pack: Pack) -> dict[str, str]:
    """BSA (lowercase) -> the mod it came with, for readable items."""
    from .builder import load_mods
    try:
        mods = load_mods(pack)
    except Exception:  # noqa: BLE001
        mods = {}
    out = {}
    for mid, rec in mods.items():
        if isinstance(rec, dict):
            for b in rec.get("bsas") or []:
                out.setdefault(b.lower(), mid)
    return out


def _label(labels: dict[str, str], bsa: str) -> str:
    m = labels.get(bsa.lower())
    return f"{m} ({bsa})" if m and m.lower() != Path(bsa).stem.lower() else bsa


def script_sources(pack: Pack, cache) -> list[tuple[str, dict[str, object]]]:
    """[(source, {script path: entry or Path})] in script order, first to last,
    without the game's BSAs and without ini BSAs the pack leaves out because
    every plugin they belong to is off."""
    from .conflicts import load_order_bsas
    from .console import ini_drops
    from .requirements import loose_files
    drops = ini_drops(pack)
    out = []
    for name, path, _src in load_order_bsas(pack, scripts=True):
        if name.lower() in drops:
            continue
        arc = cache.get(path)
        if arc is None:
            continue
        pex = {e.path.lower(): e for e in arc.entries
               if e.path.lower().endswith(".pex") and not e.path.lower().startswith("scripts\\source\\")}
        if pex:
            out.append((name, pex))
    loose = {p: fp for p, fp in loose_files(pack.data_dir).items()
             if p.startswith("scripts\\") and p.endswith(".pex")}
    if loose:
        out.append(("Data\\scripts", loose))
    return out


def _read(arc, fh, ref) -> bytes | None:
    try:
        if isinstance(ref, Path):
            return ref.read_bytes()
        return arc.read_file(ref, fh)
    except Exception:  # noqa: BLE001
        return None


def skse_base_in(paths) -> list[str]:
    """The SKSE base scripts among these paths (and their .psc sources), when
    they look like SKSE's set: skse.pex itself, or five or more of them."""
    hits = [p for p in paths if p.lower().startswith("scripts\\") and p.lower().endswith(".pex")
            and p.lower().count("\\") == 1 and p.lower()[8:-4] in SKSE_BASE]
    names = {p.lower()[8:-4] for p in hits}
    if "skse" not in names and len(names) < 5:
        return []
    src = [p for p in paths if p.lower().startswith("scripts\\source\\") and p.lower().endswith(".psc")
           and p.lower().rsplit("\\", 1)[-1][:-4] in names]
    return sorted(hits) + sorted(src)


def check_scripts(pack: Pack, add, cache, vanilla_pex: set[str], active: set[str], progress=None) -> None:
    say = progress or (lambda *_: None)
    sources = script_sources(pack, cache)
    if not sources:
        return
    labels = _labels(pack)
    from .audit import F
    for name, pex in sources:
        bpath = pack.bsas.get(name.lower())
        arc = cache.get(bpath) if bpath else None
        paths = [e.path for e in arc.entries] if arc else list(pex)
        found = skse_base_in(paths)
        if not found:
            continue
        n = sum(1 for p in found if p.lower().endswith(".pex"))
        add("script-skse-base", "critico", "requirements", "script-skse-base", name,
            {"name": _label(labels, name), "n": n},
            [Path(p.replace("\\", "/")).name for p in found if p.lower().endswith(".pex")],
            fix=F("bsa_drop_skse", "fix-drop-skse", "seguro", {"n": n}, bsa=bpath.name, items=found)
            if arc else None)
    ussep = _ussep_bsas(pack)
    # who has each script, in order; the game's own go first among the ini ones
    from .conflicts import load_order_bsas
    from .console import ini_drops
    drops = ini_drops(pack)
    ini_names = {n.lower() for n, _p, s in load_order_bsas(pack, scripts=True)
                 if s.startswith("ini:") and n.lower() not in drops}
    holders: dict[str, list[str]] = defaultdict(list)
    first_ini = True
    for name, pex in sources:
        if first_ini and name.lower() in ini_names:
            for v in vanilla_pex:
                holders[v].append("(game)")
            first_ini = False
        for p in pex:
            holders[p].append(name)
    if first_ini:
        for v in vanilla_pex:
            holders[v].append("(game)")

    # --- scripts that take the place of the game's or USSEP's
    over_game: dict[str, list[str]] = defaultdict(list)
    over_ussep: dict[str, list[str]] = defaultdict(list)
    for path, who in holders.items():
        if "(game)" not in who and not any(w.lower() in ussep for w in who):
            continue
        winner = who[-1]
        if winner == "(game)" or winner.lower() in ussep:
            continue
        script = Path(path.replace("\\", "/")).stem
        if any(w.lower() in ussep for w in who):
            over_ussep[winner].append(script)
        else:
            over_game[winner].append(script)
    if over_ussep:
        items = [f"{_label(labels, b)}: {', '.join(sorted(s)[:12])}" + (f" (+{len(s) - 12})" if len(s) > 12 else "")
                 for b, s in sorted(over_ussep.items())]
        add("script-replaces-ussep", "aviso", "requirements", "script-replaces-ussep", "scripts-ussep",
            {"n": sum(len(s) for s in over_ussep.values()), "mods": ", ".join(sorted(over_ussep)[:6])}, items)
    if over_game:
        items = [f"{_label(labels, b)}: {', '.join(sorted(s)[:12])}" + (f" (+{len(s) - 12})" if len(s) > 12 else "")
                 for b, s in sorted(over_game.items(), key=lambda kv: -len(kv[1]))]
        add("script-replaces-game", "info", "requirements", "script-replaces-game", "scripts-game",
            {"n": sum(len(s) for s in over_game.values()), "mods": len(over_game)}, items)

    # --- what the running scripts ask for, and how much they do by themselves
    wanted: dict[str, list[str]] = defaultdict(list)   # missing plugin -> "script (source)"
    weight: dict[str, list[int]] = {}
    known = {a for a in active if not a.startswith("#")}
    known |= {m.lower() for m in K.VANILLA_MASTERS + K.SWITCH_MASTERS}
    for i, (name, pex) in enumerate(sources):
        say(name, i, len(sources))
        w = [0, 0, 0, 0]          # scripts, repeating timers, single timers, events
        bpath = pack.bsas.get(name.lower())
        arc = cache.get(bpath) if bpath else None
        fh = bpath.open("rb") if arc else None
        try:
            for path, ref in pex.items():
                if holders[path][-1] != name:
                    continue          # another copy wins: this one never runs
                raw = _read(arc, fh, ref)
                if not raw:
                    continue
                try:
                    strs = PEX.strings(raw)
                except Exception:  # noqa: BLE001
                    continue
                low = {s.lower() for s in strs}
                w[0] += 1
                w[1] += any(k in low for k in POLL)
                w[2] += any(k in low for k in LOOP)
                w[3] += sum(1 for k in EVENTS if k in low)
                script = Path(path.replace("\\", "/")).stem
                for s in strs:
                    if PLUGIN_RE.match(s) and s.lower() not in known:
                        wanted[s.lower()].append(f"{script} ({name})")
        finally:
            if fh:
                fh.close()
        if w[1] or w[2] or w[3]:
            weight[name] = w

    if wanted:
        names = {h.name.lower(): h.name for h in pack.plugins.values()}
        items = []
        for low, who in sorted(wanted.items(), key=lambda kv: -len(kv[1])):
            state = "off" if low in names else "gone"
            shown = names.get(low, low)
            items.append(f"{shown} [{state}]: {len(who)} · {', '.join(sorted(set(who))[:4])}"
                         + (" …" if len(set(who)) > 4 else ""))
        add("script-plugin-off", "info", "requirements", "script-plugin-off", "scripts-plugins",
            {"n": len(wanted), "list": ", ".join(names.get(k, k) for k in list(wanted)[:6])}, items[:EXAMPLES])

    if weight:
        def score(w):
            return 4 * w[1] + 2 * w[2] + w[3]
        ranked = sorted(weight.items(), key=lambda kv: -score(kv[1]))
        items = [f"{_label(labels, n)}: {w[0]} scripts · {w[1]} repeating · {w[2]} single · {w[3]} events"
                 for n, w in ranked[:15]]
        add("script-load", "info", "requirements", "script-load", "scripts-load",
            {"top": ", ".join(_label(labels, n) for n, _w in ranked[:3])}, items)


# ------------------------------------------------------------------ audio
def check_opus_fuz(raw: bytes) -> None:
    """Raise AudioFormatError unless a Switch FUZ is complete, frame by frame."""
    d = NXA.parse_nx_fuz(raw)
    o = d["opus"]
    if len(o) < 32 or o[:4] != NXA.NX_OPUS_MAGIC:
        raise NXA.AudioFormatError("no Nintendo Opus header")
    doff, = struct.unpack_from("<I", o, 16)
    if doff + 8 > len(o):
        raise NXA.AudioFormatError("data offset past the end")
    tag, size = struct.unpack_from("<II", o, doff)
    if tag != 0x80000004:
        raise NXA.AudioFormatError("no Opus data chunk")
    end = doff + 8 + size
    if end > len(o):
        raise NXA.AudioFormatError(f"cut short: {len(o) - doff - 8} of {size} bytes")
    p = doff + 8
    while p < end:
        if p + 8 > end:
            raise NXA.AudioFormatError("frame header cut short")
        n, = struct.unpack_from(">I", o, p)
        p += 8 + n
    if p != end:
        raise NXA.AudioFormatError("frames don't add up to the data size")


def check_mcadpcm_full(raw: bytes) -> None:
    ch = NXA.check_mcadpcm(raw)
    for i in range(ch):
        off, size = struct.unpack_from("<II", raw, 4 + 8 * i)
        if size < 0x60:
            raise NXA.AudioFormatError("channel without a DSP header")
        _samples, nibbles, rate = struct.unpack_from("<III", raw, off)
        if not 4000 <= rate <= 96000:
            raise NXA.AudioFormatError(f"channel {i}: sample rate {rate}")
        if 0x60 + (nibbles + 1) // 2 > size + 8:
            raise NXA.AudioFormatError(f"channel {i}: data cut short")


def _audio_problem(name: str, raw: bytes) -> str | None:
    low = name.lower()
    try:
        if low.endswith(".mcadpcm"):
            check_mcadpcm_full(raw)
        elif low.endswith(".fuz"):
            if raw[:4] != NXA.FUZE:
                return "not a FUZ file"
            if NXA.is_switch_fuz(raw):
                check_opus_fuz(raw)
            # a PC FUZ is reported as PC audio elsewhere
        elif low.endswith(".xwm"):
            if raw[:4] != b"RIFF" or raw[8:12] != b"XWMA":
                return "not an xWMA file"
            size, = struct.unpack_from("<I", raw, 4)
            if size + 8 > len(raw):
                return f"cut short: {len(raw)} of {size + 8} bytes"
        elif low.endswith(".wav"):
            if raw[:4] != b"RIFF":
                return "not a WAV file"
            size, = struct.unpack_from("<I", raw, 4)
            if size + 8 > len(raw):
                return f"cut short: {len(raw)} of {size + 8} bytes"
            NXA.wav_info(raw)
    except (NXA.AudioFormatError, struct.error) as e:
        return str(e) or "unreadable"
    return None


AUDIO_EXT = (".fuz", ".mcadpcm", ".xwm", ".wav")


def _audio_cache(pack: Pack) -> tuple[Path, dict]:
    f = pack.root / ".skynx" / CACHE_FILE
    try:
        return f, json.loads(f.read_text(encoding="utf-8"))
    except Exception:  # noqa: BLE001
        return f, {}


def check_audio(pack: Pack, add, cache, progress=None) -> None:
    """Read every sound the mods bring, in full. Results are kept per BSA
    (size and time) so the next check only reads what changed."""
    from .conflicts import load_order_bsas
    from .requirements import loose_files
    say = progress or (lambda *_: None)
    labels = _labels(pack)
    cf, saved = _audio_cache(pack)
    fresh: dict[str, dict] = {}
    bad: list[tuple[str, str, str]] = []      # (source, file, problem)
    from .console import ini_drops
    drops = ini_drops(pack)
    bsas = [(n, p) for n, p, _s in load_order_bsas(pack) if n.lower() not in drops]
    for i, (name, path) in enumerate(bsas):
        arc = cache.get(path)
        if arc is None:
            continue
        files = [e for e in arc.entries if e.name.lower().endswith(AUDIO_EXT)]
        if not files:
            continue
        st = path.stat()
        key = f"{st.st_size}:{st.st_mtime_ns}"
        prev = saved.get(name.lower())
        if prev and prev.get("key") == key:
            fresh[name.lower()] = prev
            bad += [(name, f, p) for f, p in prev.get("bad", [])]
            continue
        say(name, i, len(bsas))
        found = []
        with path.open("rb") as fh:
            for e in files:
                try:
                    raw = arc.read_file(e, fh)
                except Exception as ex:  # noqa: BLE001
                    found.append([e.path, f"can't be read: {ex}"])
                    continue
                p = _audio_problem(e.name, raw)
                if p:
                    found.append([e.path, p])
        fresh[name.lower()] = {"key": key, "n": len(files), "bad": found}
        bad += [(name, f, p) for f, p in found]
    for p, fp in loose_files(pack.data_dir).items():
        if p.startswith(("sound\\", "music\\")) and p.endswith(AUDIO_EXT):
            try:
                prob = _audio_problem(p, fp.read_bytes())
            except OSError as ex:
                prob = f"can't be read: {ex}"
            if prob:
                bad.append(("Data", p, prob))
    try:
        cf.parent.mkdir(parents=True, exist_ok=True)
        cf.write_text(json.dumps(fresh, indent=1), encoding="utf-8")
    except OSError:
        pass
    if not bad:
        return
    by_src: dict[str, list[str]] = defaultdict(list)
    for src, f, p in bad:
        by_src[src].append(f"{f}: {p}")
    for src, items in by_src.items():
        add("audio-broken", "aviso", "audio", "audio-broken", src,
            {"name": _label(labels, src), "n": len(items)}, items[:EXAMPLES])
