"""Put together the files for a GitHub release in release/.

    python extras/release/make_release.py [--skyrim-esm PATH] [--tools DIR]

What it takes (each part is skipped, with a note, when its input is missing):
  dist/SwitchNX Studio.exe            -> SwitchNX-Studio-<version>-windows.zip   (construir.bat)
  extras/nxmods/SkyNXMods.nro         -> SkyNXMods-<version>.zip                 (extras/nxmods/construir_nro.bat)
  extras/nxtest + your Skyrim.esm     -> SkyNX-TestTools-<version>.zip           (--skyrim-esm)
  extras/status-monitor/04.SkyNX.smd  -> StatusMonitor-SkyNX-mode.zip
  extras/skeleton/SkyNX               -> SkyNX-folders.zip
  extras/skill/switchnx-studio-guide  -> switchnx-studio-guide-skill.zip
  --tools: texconv.exe, VGAudioCli.exe and VGAudio.dll (the Skyrim NX Toolkit build) -> SkyNX-tools-MIT.zip
Nothing from the game and nothing from Nintendo's SDK goes in.
"""
from __future__ import annotations

import argparse
import re
import shutil
import subprocess
import sys
import tempfile
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "release"
FREE_TOOLS = ["texconv.exe", "VGAudioCli.exe", "VGAudio.dll"]   # MIT, see THIRD-PARTY-NOTICES.md


def zip_up(dest: Path, files: list[tuple[str, Path]]) -> None:
    with zipfile.ZipFile(dest, "w", zipfile.ZIP_DEFLATED) as z:
        for arc, src in files:
            z.write(src, arc)
    print(f"  {dest.name}  ({dest.stat().st_size // 1024} KB)")


def tree(base: Path, prefix: str) -> list[tuple[str, Path]]:
    return [(f"{prefix}/{p.relative_to(base).as_posix()}", p) for p in sorted(base.rglob("*")) if p.is_file()]


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--skyrim-esm", type=Path, help="Skyrim.esm from your console, to build the test tools")
    ap.add_argument("--tools", type=Path, help="folder with texconv.exe, VGAudioCli.exe and VGAudio.dll")
    a = ap.parse_args()
    OUT.mkdir(exist_ok=True)
    app_v = re.search(r'__version__ = "([^"]+)"', (ROOT / "skynx" / "__init__.py").read_text()).group(1)
    nro_v = re.search(r"APP_VERSION\s*:=\s*(\S+)", (ROOT / "extras/nxmods/Makefile.switch").read_text()).group(1)
    notices = [("LICENSE.txt", ROOT / "LICENSE"), ("THIRD-PARTY-NOTICES.md", ROOT / "THIRD-PARTY-NOTICES.md")]
    print(f"SwitchNX Studio {app_v}, SkyNX Mods {nro_v} -> {OUT}")

    exe = ROOT / "dist" / "SwitchNX Studio.exe"
    if exe.exists():
        zip_up(OUT / f"SwitchNX-Studio-{app_v}-windows.zip", [("SwitchNX Studio.exe", exe)] + notices)
    else:
        print("  (no dist\\SwitchNX Studio.exe: run construir.bat first)")

    nro = ROOT / "extras" / "nxmods" / "SkyNXMods.nro"
    if nro.exists():
        zip_up(OUT / f"SkyNXMods-{nro_v}.zip", [("switch/SkyNXMods.nro", nro)] + notices)
    else:
        print("  (no extras\\nxmods\\SkyNXMods.nro: run extras\\nxmods\\construir_nro.bat first)")

    if a.skyrim_esm and a.skyrim_esm.exists():
        with tempfile.TemporaryDirectory() as tmp:
            subprocess.run([sys.executable, str(ROOT / "extras/nxtest/build.py"), str(a.skyrim_esm),
                            str(ROOT / "extras/nxtest/pex"), tmp], check=True)
            zip_up(OUT / "SkyNX-TestTools-1.1.zip",
                   [("SkyNX Test Tools/NXTest.esp", Path(tmp) / "NXTest.esp"),
                    ("SkyNX Test Tools/NXTest.bsa", Path(tmp) / "NXTest.bsa"),
                    ("README.md", ROOT / "extras/nxtest/README.md")])
    else:
        print("  (test tools skipped: pass --skyrim-esm with your console's Skyrim.esm)")

    smd = ROOT / "extras/status-monitor"
    zip_up(OUT / "StatusMonitor-SkyNX-mode.zip",
           [("config/status-monitor-deux/modes/04.SkyNX.smd", smd / "04.SkyNX.smd"), ("README.md", smd / "README.md")])
    zip_up(OUT / "SkyNX-folders.zip", tree(ROOT / "extras/skeleton/SkyNX", "SkyNX"))
    zip_up(OUT / "switchnx-studio-guide-skill.zip",
           tree(ROOT / "extras/skill/switchnx-studio-guide", "switchnx-studio-guide"))

    if a.tools and all((a.tools / t).exists() for t in FREE_TOOLS):
        lic = ROOT / "extras/release/tool-licenses"
        zip_up(OUT / "SkyNX-tools-MIT.zip",
               [(f"Tools/{t}", a.tools / t) for t in FREE_TOOLS]
               + [(f"Tools/{p.name}", p) for p in sorted(lic.glob("*.txt"))]
               + [("Tools/LEEME-tools.txt", ROOT / "extras/skeleton/SkyNX/Tools/LEEME-tools.txt")])
    else:
        print("  (tools zip skipped: pass --tools with texconv.exe, VGAudioCli.exe and VGAudio.dll)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
