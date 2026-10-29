"""External tools: where they are and how to run them.

Everything lives in one "tools" folder (by default C:\\SkyNX\\tools, or a
"tools" folder next to the program). Nothing is downloaded behind the
user's back.

  texconv.exe     DirectXTex (Microsoft, MIT): texture format, size, mipmaps.
  ffmpeg.exe      decodes PC audio (.xwm, .wav) to plain PCM.
  VGAudioCli.exe  + VGAudio.dll, the Skyrim NX Toolkit build (MIT): Nintendo
                  Opus and DSP-ADPCM (.mcadpcm).
  NvnTexpkg.exe   optional, Nintendo SDK: native Switch textures (DFvN). It
                  loads NvnTexpkg.dll, NvnImage.dll, DdsLoader.dll and
                  TgaLoader.dll from its own folder.
  HavokBehaviorPostProcess.exe  optional, Bethesda's Creation Kit: writes
                  Havok files (behaviors, skeletons, 32-bit animations) in
                  the Switch layout (see havok.py).
  Nemesis         optional, Nemesis Unlimited Behavior Engine unpacked in its
                  own folder (tools\\Nemesis\\Nemesis_Engine\\...): generates the
                  behavior files for FNIS / Nemesis mods (behaviors.py).
  hkxc.exe        optional, serde-hkx (open source): 64-bit PC hkx to XML,
                  which HavokBehaviorPostProcess can read. Can sit in a
                  subfolder (tools\\serde-hkx\\hkxc.exe).
"""
from __future__ import annotations

import os
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

NVN_DLLS = ("NvnTexpkg.dll", "NvnImage.dll", "DdsLoader.dll", "TgaLoader.dll")
TOOL_FILES = ("texconv.exe", "ffmpeg.exe", "VGAudioCli.exe", "NvnTexpkg.exe",
              "HavokBehaviorPostProcess.exe", "hkxc.exe")


def default_dirs() -> list[Path]:
    out = []
    exe_dir = Path(sys.executable).parent if getattr(sys, "frozen", False) else Path(__file__).resolve().parents[1]
    out.append(exe_dir / "tools")
    out.append(Path(r"C:\SkyNX\Tools"))
    return out


@dataclass
class Toolset:
    folder: Path | None
    texconv: Path | None = None
    ffmpeg: Path | None = None
    vgaudio: Path | None = None
    nvntexpkg: Path | None = None
    nvn_missing: tuple[str, ...] = ()
    vgaudio_is_toolkit: bool = False
    hbpp: Path | None = None
    hkxc: Path | None = None
    nemesis: Path | None = None        # its Nemesis_Engine folder

    @property
    def can_textures(self) -> bool:
        return self.texconv is not None

    @property
    def can_audio(self) -> bool:
        return self.ffmpeg is not None and self.vgaudio is not None

    @property
    def can_havok(self) -> bool:
        """Behaviors, skeletons and 32-bit animations to Switch (both tools)."""
        return self.hbpp is not None and self.hkxc is not None

    @property
    def sdk(self) -> bool:
        return self.nvntexpkg is not None and not self.nvn_missing

    def status(self) -> dict:
        return {"folder": str(self.folder) if self.folder else None,
                "texconv": bool(self.texconv), "ffmpeg": bool(self.ffmpeg),
                "vgaudio": bool(self.vgaudio), "vgaudio_toolkit": self.vgaudio_is_toolkit,
                "nvntexpkg": bool(self.nvntexpkg), "nvn_missing": list(self.nvn_missing),
                "sdk": self.sdk, "hbpp": bool(self.hbpp), "hkxc": bool(self.hkxc),
                "havok": self.can_havok, "nemesis": bool(self.nemesis)}


def _find(folder: Path, name: str) -> Path | None:
    p = folder / name
    if p.is_file():
        return p
    # Tolerate one level of subfolders (tools\SDK\NvnTexpkg.exe).
    try:
        for sub in folder.iterdir():
            q = sub / name
            if sub.is_dir() and q.is_file():
                return q
    except OSError:
        pass
    return None


def locate(preferred: str | Path | None = None) -> Toolset:
    dirs = []
    for d in ([Path(preferred)] if preferred else []) + default_dirs():
        # A folder that holds a "tools" folder (C:\SkyNX) means that one.
        dirs += [d / "tools", d] if d.name.lower() != "tools" else [d]
    folder = next((d for d in dirs if d.is_dir() and any(_find(d, t) for t in TOOL_FILES)), None)
    if folder is None:
        return Toolset(None)
    ts = Toolset(folder, _find(folder, "texconv.exe"), _find(folder, "ffmpeg.exe"),
                 _find(folder, "VGAudioCli.exe"), _find(folder, "NvnTexpkg.exe"))
    ts.hbpp = _find(folder, "HavokBehaviorPostProcess.exe")
    ts.hkxc = _find(folder, "hkxc.exe")
    ts.nemesis = find_nemesis(folder)
    if ts.nvntexpkg:
        ts.nvn_missing = tuple(d for d in NVN_DLLS if not (ts.nvntexpkg.parent / d).is_file())
    if ts.vgaudio:
        # The Toolkit build ships VGAudio.dll next to a small exe; the official
        # release is a single ~300 KB exe without the Skyrim/MCADPCM writers.
        ts.vgaudio_is_toolkit = (ts.vgaudio.parent / "VGAudio.dll").is_file() and \
            ts.vgaudio.stat().st_size < 200_000
    return ts


NEMESIS_EXE = "Nemesis Unlimited Behavior Engine.exe"


def find_nemesis(folder: Path) -> Path | None:
    """The Nemesis_Engine folder: tools\\Nemesis_Engine or tools\\<any>\\Nemesis_Engine
    (Nemesis' download unpacked in its own folder)."""
    for cand in [folder / "Nemesis_Engine"] + ([d / "Nemesis_Engine" for d in sorted(folder.iterdir()) if d.is_dir()]
                                              if folder.is_dir() else []):
        if (cand / NEMESIS_EXE).is_file():
            return cand
    return None


class ToolError(RuntimeError):
    pass


def run(cmd: list, timeout: int = 600) -> str:
    """Run a tool without a console window; raise with its output on failure."""
    kw = {}
    if os.name == "nt":
        kw["creationflags"] = 0x08000000  # CREATE_NO_WINDOW
    try:
        p = subprocess.run([str(c) for c in cmd], capture_output=True, timeout=timeout, **kw)
    except subprocess.TimeoutExpired as e:
        raise ToolError(f"{Path(str(cmd[0])).name} took too long") from e
    except OSError as e:
        raise ToolError(f"{Path(str(cmd[0])).name}: {e}") from e
    out = (p.stdout or b"").decode("utf-8", "replace") + (p.stderr or b"").decode("utf-8", "replace")
    if p.returncode != 0:
        raise ToolError(f"{Path(str(cmd[0])).name} failed ({p.returncode}): {out.strip()[-400:]}")
    return out
