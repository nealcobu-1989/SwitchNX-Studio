# Third-party notices

This repository's own code, texts and art are MIT (see `LICENSE`). These parts come from
others and keep their own licenses.

## In this repository

| What | Where | License |
| --- | --- | --- |
| Barlow Condensed and Cinzel fonts | `app/web/fonts`, `extras/nxmods/romfs/fonts` | SIL Open Font License 1.1 (texts next to the fonts) |
| LOOT's Skyrim SE masterlist (test fixture) | `tests/fixtures/loot/masterlist.yaml` | The LOOT team's masterlist license (https://github.com/loot/skyrimse) |
| Sound container layouts and the animation conversion method | described in `skynx/nxaudio.py`, `skynx/havok.py` | Learned from the Skyrim NX Toolkit, MIT, Antony Marshall and Zappastuff |
| Texture size rules ("Koka" preset) | `skynx/diet.py` | Credited to KokaNX in the app |

## In the release files

| What | License |
| --- | --- |
| `SwitchNX Studio.exe` (PyInstaller bundle) | Contains Python (PSF License), pywebview (BSD-3-Clause), lz4 (BSD-3-Clause), py7zr (LGPL-2.1-or-later), texture2ddecoder (MIT), PyYAML (MIT), NumPy (BSD-3-Clause). Their sources are on PyPI; `requirements.txt` lists them. |
| `SkyNXMods.nro` | Built with devkitPro's libnx (ISC), SDL2, SDL2_ttf and SDL2_image (zlib), FreeType (FTL), libpng (libpng license), HarfBuzz (MIT), libjpeg-turbo and zlib (BSD-style / zlib). |
| `SkyNX-tools-MIT.zip` | texconv (DirectXTex, MIT, Microsoft); VGAudioCli and VGAudio.dll (VGAudio, MIT, Alex Barney, in the Skyrim NX Toolkit's build, MIT, Antony Marshall). License texts inside the zip. |
| `StatusMonitor-SkyNX-mode.zip` | Our mode file (MIT) for Status Monitor Deux by masagrator (GPL-2.0), which isn't included: https://github.com/masagrator/Status-Monitor-Deux |

## Not included, on purpose

- **Game files.** No BSA, plugin, ini, script or asset from Skyrim, the Creation Club or the
  Nintendo Switch version. The app works with the files of your own copy.
- **Nintendo's SDK tools** (NvnTexpkg and its DLLs). The app can use them if you have them;
  it works without them.
- **Bethesda's Creation Kit tools** (HavokBehaviorPostProcess). Get them from the Creation Kit.
- **Other people's mods**, USSEP included. Share Pack recipes (links to Nexus), not files,
  unless a mod's permissions allow it.

## Trademarks

The Elder Scrolls, Skyrim and their logos belong to Bethesda Softworks / ZeniMax Media.
Nintendo Switch belongs to Nintendo. This is an unofficial fan project, not made, endorsed
or supported by either. The emblem in this repository is original art.
