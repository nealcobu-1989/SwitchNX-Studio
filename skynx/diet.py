"""Texture diet for archives that are already converted for Switch.

A Switch BSA can hold two kinds of textures: PC DDS files (left as DDS by
Koka's rule when there was no SDK) and native Switch textures (DFvN, see
nvn.py). This module shrinks both without touching anything else.

Per texture:
  Native, uncompressed (RGBA8, R8, RG8): converted to BC3 (BC1 when every
      pixel is opaque and the BC1 option is on), BC4 or BC5, and resized to
      the preset's size. The FaceGen tints in USSEPT.bsa are the main case.
  Native, block-compressed and bigger than the preset allows: the largest
      mips are dropped when the texture has them, which is exact (no
      re-encoding, no generation loss); otherwise texconv resizes it.
  Native, block-compressed and within the preset: left untouched.
  PC DDS: the converter's rules (texplan.plan_texture).
New native files come from NvnTexpkg when the SDK is there (its output is
checked) and from nvn.build otherwise. A texture that fails in any way stays
byte-identical to the original and is counted. Other files are copied with
the same contents. The source archive is never modified.
"""
from __future__ import annotations

import os
import shutil
import tempfile
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field
from pathlib import Path

from . import nvn
from .bsa import BsaArchive, read_bsa, write_bsa
from .errors import SkynxError
from .texplan import PRESETS, TEXCONV_FMT, est_bytes, full_mips, max_side, plan_texture
from .textures import inspect, is_opaque as dds_is_opaque
from .tools import Toolset, ToolError, run

UNCOMPRESSED_TARGET = {"RGBA8": "BC3", "R8": "BC4", "RG8": "BC5"}
TEXCONV_NAMES = dict(TEXCONV_FMT, BC4="BC4_UNORM")
# Re-encoding a BC2 texture gives BC3 (same size, smoother alpha).
REENCODE_AS = {"BC2": "BC3"}


@dataclass
class DietPlan:
    rel: str
    kind: str                 # "nvn", "dds" or "other" (not a texture we know)
    src_fmt: str
    w: int
    h: int
    mips: int
    fmt: str                  # target format
    tw: int
    th: int
    tmips: int
    action: str               # "keep", "drop_mips" (exact), "texconv", or
                              # "nvntexpkg" (PC DDS only made native)
    before: int               # estimated memory now
    after: int                # estimated memory after the diet
    skip: str = ""            # why it is kept ("small", "unsupported", "srgb"...)
    nvn_out: bool = False     # result is a native Switch texture
    opaque: bool | None = None

    @property
    def changes(self) -> bool:
        return self.action != "keep"

    def to_dict(self) -> dict:
        return {k: getattr(self, k) for k in (
            "rel", "kind", "src_fmt", "w", "h", "mips", "fmt", "tw", "th", "tmips", "action",
            "before", "after", "skip", "nvn_out", "opaque")}


def _shrink(w: int, h: int, side: int | None) -> tuple[int, int]:
    """Same rule as the converter: halve until the area fits side x side."""
    tw, th = w, h
    if side:
        while tw * th > side * side and min(tw, th) > 4:
            tw, th = max(1, tw // 2), max(1, th // 2)
    return tw, th


def _nvn_bytes(fmt_name: str, w: int, h: int, mips: int, layers: int = 1) -> int:
    f = nvn.BY_NAME[fmt_name]
    return nvn.plan_layout(f.nvn, w, h, mips, layers).data_size


def _keep(rel, kind, fmt, w, h, mips, size, skip) -> DietPlan:
    return DietPlan(rel, kind, fmt, w, h, mips, fmt, w, h, mips, "keep", size, size, skip,
                    kind == "nvn")


def plan_nvn(rel: str, raw: bytes, preset: str, bc1: bool = False,
             tex: nvn.NvnTexture | None = None) -> DietPlan:
    tex = tex or nvn.parse(raw)
    name, w, h, mips = tex.name, tex.width, tex.height, tex.mips
    before = tex.data_size
    if not tex.supported:
        return _keep(rel, "nvn", name, w, h, mips, before, "unsupported")
    tw, th = _shrink(w, h, max_side(rel, preset))
    drop = (w // tw).bit_length() - 1 if (tw, th) != (w, h) else 0
    layers = tex.layers
    if name in UNCOMPRESSED_TARGET:
        fmt = UNCOMPRESSED_TARGET[name]
        opaque = None
        if bc1 and fmt == "BC3":
            opaque = nvn.is_opaque(nvn.deswizzle(tex))
            fmt = "BC1" if opaque else fmt
        tmips = 1 if mips == 1 else full_mips(tw, th)
        after = _nvn_bytes(fmt, tw, th, tmips, layers)
        return DietPlan(rel, "nvn", name, w, h, mips, fmt, tw, th, tmips, "texconv", before,
                        after, "", True, opaque)
    if name not in nvn.BY_NAME or not name.startswith("BC") or name.endswith("S"):
        return _keep(rel, "nvn", name, w, h, mips, before, "format")
    if not drop:
        return _keep(rel, "nvn", name, w, h, mips, before, "small")
    if mips > drop:
        tmips = mips - drop
        return DietPlan(rel, "nvn", name, w, h, mips, name, tw, th, tmips, "drop_mips", before,
                        _nvn_bytes(name, tw, th, tmips, layers), "", True)
    fmt = REENCODE_AS.get(name, name)
    opaque = None
    if bc1 and fmt == "BC3":
        opaque = nvn.is_opaque(nvn.deswizzle(tex))
        fmt = "BC1" if opaque else fmt
    tmips = 1 if mips == 1 else full_mips(tw, th)
    return DietPlan(rel, "nvn", name, w, h, mips, fmt, tw, th, tmips, "texconv", before,
                    _nvn_bytes(fmt, tw, th, tmips, layers), "", True, opaque)


def plan_dds(rel: str, raw: bytes, preset: str, sdk: bool, bc1: bool = False) -> DietPlan:
    info = inspect(raw[:256])
    p = plan_texture(rel, info, preset, sdk)
    if p.skip or info is None:
        return _keep(rel, "dds", p.src_fmt, p.w, p.h, p.mips, p.before, p.skip or "unknown")
    opaque = None
    # As in the converter, a PC DDS only drops to BC1 when NvnTexpkg makes it native.
    if bc1 and sdk and p.fmt == "BC3" and p.src_fmt in ("BC3", "BC7", "BC2", "RGBA8", "BGRA8"):
        opaque = dds_is_opaque(raw)
        if opaque:
            p.fmt, p.texconv = "BC1", True
            p.after = est_bytes("BC1", p.tw, p.th, p.tmips, p.cube)
    if not p.texconv and not p.nvn:
        return _keep(rel, "dds", p.src_fmt, p.w, p.h, p.mips, p.before, "small")
    return DietPlan(rel, "dds", p.src_fmt, p.w, p.h, p.mips, p.fmt, p.tw, p.th, p.tmips,
                    "texconv" if p.texconv else "nvntexpkg", p.before, p.after, "", p.nvn,
                    opaque)


def plan_entry(rel: str, raw: bytes, preset: str, sdk: bool, bc1: bool = False) -> DietPlan:
    if not rel.lower().endswith(".dds"):
        return _keep(rel, "other", "", 0, 0, 0, 0, "not a texture")
    try:
        if nvn.is_nvn(raw):
            return plan_nvn(rel, raw, preset, bc1)
        if raw[:4] == b"DDS ":
            return plan_dds(rel, raw, preset, sdk, bc1)
    except Exception:  # noqa: BLE001  (a broken file is simply left alone)
        pass
    return _keep(rel, "other", "?", 0, 0, 0, 0, "unknown")


def _check_preset(preset: str) -> None:
    """A preset name, or "none", optionally with a ":N" size cap ("koka:1024")."""
    from .texplan import NO_PRESET, split_preset
    if split_preset(preset)[0] not in (*PRESETS, NO_PRESET) or str(preset).count(":") > 1:
        raise SkynxError(f"Unknown size preset: {preset}", f"Tamaño desconocido: {preset}")


def plan_bsa(path, preset: str, sdk: bool, bc1: bool = False) -> list[DietPlan]:
    """One plan per texture (.dds entry) of the archive, in archive order."""
    _check_preset(preset)
    arc = read_bsa(Path(path))
    out = []
    with arc.path.open("rb") as f:
        for e in arc.entries:
            if e.name.lower().endswith(".dds"):
                out.append(plan_entry(e.path, arc.read_file(e, f), preset, sdk, bc1))
    return out


def estimate_bsa(path, preset: str, bc1: bool = False) -> dict:
    """Savings estimate for the UI, without any external tool.

    before/after are estimated texture memory in bytes, count the textures
    that would change, nvn_rgba the native uncompressed RGBA8 textures.
    """
    plans = plan_bsa(path, preset, sdk=False, bc1=bc1)
    return {"before": sum(p.before for p in plans), "after": sum(p.after for p in plans),
            "count": sum(p.changes for p in plans),
            "nvn_rgba": sum(p.kind == "nvn" and p.src_fmt.startswith("RGBA8") for p in plans)}


# --------------------------------------------------------------------------
# Running the plans
# --------------------------------------------------------------------------
def _texconv(tools: Toolset, src: Path, out_dir: Path, plan: DietPlan) -> nvn.Surface:
    if not tools.texconv:
        raise ToolError("texconv.exe is missing")
    args = [tools.texconv, "-nologo", "-y", "-dx9", "-sepalpha", "-f", TEXCONV_NAMES[plan.fmt]]
    if (plan.tw, plan.th) != (plan.w, plan.h):
        args += ["-w", str(plan.tw), "-h", str(plan.th)]
    args += ["-m", str(0 if plan.tmips == full_mips(plan.tw, plan.th) else plan.tmips)]
    args += ["-o", out_dir, src]
    run(args)
    res = out_dir / src.name
    if not res.exists():
        cands = [p for p in out_dir.glob("*") if p.suffix.lower() == ".dds" and p != src]
        if not cands:
            raise ToolError("texconv produced no file")
        res = cands[0]
    surf = nvn.read_dds(res.read_bytes())
    if (surf.width, surf.height) != (plan.tw, plan.th) or surf.info.name != plan.fmt:
        raise ToolError("texconv produced an unexpected file")
    return surf


def _native(tools: Toolset, surf: nvn.Surface, work: Path) -> tuple[bytes, str]:
    """DFvN bytes for a linear surface: NvnTexpkg when present, else our writer."""
    if tools.sdk:
        src, xtx = work / "nvn_in.dds", work / "nvn_out.xtx"
        src.write_bytes(nvn.write_dds(surf))
        try:
            run([tools.nvntexpkg, "-i", src, "-o", xtx])
            out = xtx.read_bytes() if xtx.exists() else b""
            tex = nvn.parse(out)
            if (tex.fmt, tex.width, tex.height, tex.mips) == \
                    (surf.fmt, surf.width, surf.height, surf.mips) and tex.supported:
                return out, "nvntexpkg"
        except (ToolError, nvn.NvnError, OSError):
            pass
        return nvn.build(surf), "fallback"
    return nvn.build(surf), "own"


def diet_texture(raw: bytes, plan: DietPlan, tools: Toolset, work: Path) -> tuple[bytes, str]:
    """New bytes for one texture and how they were made. Raises on failure."""
    work.mkdir(parents=True, exist_ok=True)
    name = Path(plan.rel.replace("\\", "/")).name or "tex.dds"
    if plan.kind == "nvn":
        surf = nvn.deswizzle(nvn.parse(raw))
        if plan.action == "drop_mips":
            new = nvn.drop_mips(surf, plan.mips - plan.tmips)
        else:
            src = work / name
            src.write_bytes(nvn.write_dds(surf))
            out_dir = work / "out"
            out_dir.mkdir(exist_ok=True)
            new = _texconv(tools, src, out_dir, plan)
        out, how = _native(tools, new, work)
        tex = nvn.parse(out)
        if (tex.width, tex.height, tex.name) != (plan.tw, plan.th, plan.fmt):
            raise ToolError("the new Switch texture doesn't match the plan")
        return out, how
    # PC DDS, converter rules
    src = work / name
    src.write_bytes(raw)
    data = raw
    if plan.action == "texconv":
        out_dir = work / "out"
        out_dir.mkdir(exist_ok=True)
        _texconv(tools, src, out_dir, plan)
        res = out_dir / src.name
        data = res.read_bytes() if res.exists() else next(out_dir.glob("*")).read_bytes()
        info = inspect(data[:256])
        if not info or info.container != "DDS" or (info.width, info.height) != (plan.tw, plan.th):
            raise ToolError("texconv produced an unexpected file")
    if plan.nvn_out:
        if not tools.sdk:
            raise ToolError("NvnTexpkg is missing")
        src.write_bytes(data)
        xtx = work / "out.xtx"
        run([tools.nvntexpkg, "-i", src, "-o", xtx])
        out = xtx.read_bytes() if xtx.exists() else b""
        if out[:4] != nvn.FILE_MAGIC:
            raise ToolError("NvnTexpkg produced no DFvN file")
        return out, "nvntexpkg"
    return data, "dds"


def diet_bsa(src_bsa, dest_bsa, preset: str, tools: Toolset, bc1: bool = False,
             progress=None, work: Path | None = None) -> dict:
    """Write a slimmer copy of `src_bsa` to `dest_bsa`. The source is never modified.

    progress(stage, done, total) is called with stage "textures", then
    progress("BSA") while the archive is written. Returns statistics; "errors" lists the textures left as they were
    because something failed.
    """
    _check_preset(preset)
    tick = progress or (lambda *a, **k: None)
    src, dest = Path(src_bsa), Path(dest_bsa)
    if dest.exists() and dest.resolve() == src.resolve():
        raise SkynxError("The diet can't overwrite its own source archive.",
                         "La dieta no puede sobrescribir el archivo BSA de origen.")
    t0 = time.time()
    arc: BsaArchive = read_bsa(src)
    stats = {"textures": 0, "changed": 0, "kept": 0, "failed": 0, "before": 0, "after": 0,
             "nvn_own": 0, "nvntexpkg": 0, "nvn_fallback": 0, "bc1": 0, "drop_mips": 0,
             "other_files": 0, "errors": [], "bytes_in": src.stat().st_size, "bytes_out": 0}
    workers = max(2, (os.cpu_count() or 4) - 1)
    tmp_parent = Path(work) if work else dest.parent
    tmp_parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="skynx-diet-", dir=tmp_parent) as tmpd:
        tmp = Path(tmpd)
        files_dir = tmp / "files"
        files_dir.mkdir()
        entries = list(arc.entries)
        n = len(entries)

        def one(i: int):
            e = entries[i]
            raw = arc.read_file(e)
            path = files_dir / f"{i:06d}.bin"
            if not e.name.lower().endswith(".dds"):
                path.write_bytes(raw)
                return "other", None, None, None
            plan = plan_entry(e.path, raw, preset, tools.sdk, bc1)
            if not plan.changes:
                path.write_bytes(raw)
                return "kept", plan, None, None
            wdir = tmp / f"w{i}"
            try:
                out, how = diet_texture(raw, plan, tools, wdir)
                if plan.kind == "nvn" and len(out) >= len(raw):
                    path.write_bytes(raw)
                    return "kept", plan, None, None
                path.write_bytes(out)
                return "changed", plan, how, None
            except Exception as ex:  # noqa: BLE001
                path.write_bytes(raw)
                return "failed", plan, None, f"{e.path}: {ex}"
            finally:
                shutil.rmtree(wdir, ignore_errors=True)

        with ThreadPoolExecutor(workers) as ex:
            futs = [ex.submit(one, i) for i in range(n)]
            for k, fut in enumerate(as_completed(futs)):
                kind, plan, how, err = fut.result()
                tick("textures", k + 1, n)
                if kind == "other":
                    stats["other_files"] += 1
                    continue
                stats["textures"] += 1
                stats["before"] += plan.before
                if kind == "changed":
                    stats["changed"] += 1
                    stats["after"] += plan.after
                    stats["drop_mips"] += plan.action == "drop_mips"
                    stats["bc1"] += plan.fmt == "BC1" and plan.src_fmt != "BC1"
                    if how == "own":
                        stats["nvn_own"] += 1
                    elif how == "fallback":
                        stats["nvn_fallback"] += 1
                    elif how == "nvntexpkg":
                        stats["nvntexpkg"] += 1
                else:
                    stats["after"] += plan.before
                    stats["kept" if kind == "kept" else "failed"] += 1
                    if err:
                        stats["errors"].append(err)
        tick("BSA")
        pairs = [(e.path, files_dir / f"{i:06d}.bin") for i, e in enumerate(entries)]
        write_bsa(pairs, dest, ver=arc.version)
    stats["bytes_out"] = dest.stat().st_size
    stats["seconds"] = round(time.time() - t0, 1)
    return stats
