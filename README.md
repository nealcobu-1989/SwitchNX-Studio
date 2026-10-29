<p align="center"><img src="app/web/img/emblem.png" width="120" alt=""></p>

# SwitchNX Studio

Build, check, fix and convert **Skyrim modpacks for the Nintendo Switch 1**, then copy them to the SD.
A Windows app in English and Spanish, plus a homebrew to switch mods on and off on the console itself.

*Leer en español: [LEEME.md](LEEME.md)*

> Unofficial fan project. You need your own copy of the game and a Switch running custom firmware
> (Atmosphère, with LayeredFS). No game files, no Nintendo SDK tools and no other people's mods are
> included or ever will be.

## What's in here

| Part | What it is | Folder |
| --- | --- | --- |
| **SwitchNX Studio** | The Windows app: projects, mod conversion, the Doctor, load order, copy to SD | `app/`, `skynx/` |
| **SkyNX Mods** | Homebrew (`.nro`) to switch mods on and off on the Switch, see what each one weighs, and read Skyrim's crash reports | `extras/nxmods/` |
| **SkyNX Test Tools** | A small mod: a lesser power with menus to teleport, spawn enemies, change the time and heal, for testing packs | `extras/nxtest/` |
| **SkyNX overlay mode** | A one-line mode for Status Monitor Deux: game RAM, peak, CPU, GPU, FPS, SD reads | `extras/status-monitor/` |
| **Folder skeleton** | The `C:\SkyNX` folders the app expects, each with a note on what goes inside | `extras/skeleton/` |
| **Claude skill** | A guide so Claude can walk someone through the app | `extras/skill/` |

## Download

Get the latest files from **[Releases](../../releases)**:

| File | What to do with it |
| --- | --- |
| `SwitchNX-Studio-<version>-windows.zip` | The app. Put `SwitchNX Studio.exe` in `C:\SkyNX`. |
| `SkyNX-folders.zip` | Unzip to `C:\` so you get `C:\SkyNX\Tools`, `Vanilla`, `Library`... |
| `SkyNX-tools-MIT.zip` | texconv and the Skyrim NX Toolkit's VGAudio: unzip into `C:\SkyNX`. |
| `SkyNXMods-<version>.zip` | Copy `switch/SkyNXMods.nro` to the SD's `switch` folder. |
| `SkyNX-TestTools-1.1.zip` | Add the `SkyNX Test Tools` folder to a project (Add mods » Add as it is). |
| `StatusMonitor-SkyNX-mode.zip` | Copy its `config` folder to the SD root (needs Status Monitor Deux). |
| `switchnx-studio-guide-skill.zip` | Upload it as a skill in Claude to get a guide that knows the app. |

## Getting started

You need Windows 10 or 11 (with Microsoft Edge WebView2, which Windows already has), a Switch 1
with Atmosphère, and Skyrim Anniversary Edition or Special Edition.

1. **Folders.** Unzip `SkyNX-folders.zip` to `C:\` and put the app in `C:\SkyNX`.
2. **Tools.** Unzip `SkyNX-tools-MIT.zip` into `C:\SkyNX`. For PC mods with sounds also get
   `ffmpeg.exe`. `C:\SkyNX\Tools\LEEME-tools.txt` lists every optional tool and where it comes from.
3. **Your console's files.** From your own copy of the game (for example with DBI), put the inis
   (`Skyrim.ini`, `Skyrim_en.ini`, `Skyrim_aoc.ccc`) in `C:\SkyNX\Vanilla\INIs` and the game's
   BSAs and plugins from `romfs\Data` in `C:\SkyNX\Vanilla\BSAs`. They let the app start projects
   from scratch and tell a missing file from one the game already has. Opening and checking a
   shared modpack works without them.
4. **Open the app.** The first screen, **Your gear**, shows what it found and what each tool is for.
5. **Start a project** from scratch, from a modpack someone shared, or from your SD.
6. **Add mods** by dropping files on the window. Each card says what it is: Switch mods are added
   as they are; PC mods and FOMOD installers go through **Convert**.
7. **Doctor » Check again.** Fix what's *Serious* first. Every fix shows what it will change, and
   every change can be undone from the History.
8. **Load order » Suggest order (LOOT) » Use this order » Save order.**
9. **Pack**, then **Copy to SD** (the SD needs a drive letter: a card reader, or hekate » Tools »
   USB Tools » SD Card). **Preview changes** shows the plan before anything is written.
10. Start the game. The first start after a copy is slower while Atmosphère rebuilds its file cache.

The **Help** button opens the full manual at the page you're on (`docs/manual.en.md`).

## What the app does

- **Projects**: each modpack in a folder of its own, with its mods, its history and what goes to
  the Switch. Start from scratch, from a modpack (folder, zip, 7z, rar) or from the SD.
- **Convert PC mods**: textures (with size "diets" for the Switch's memory), voices and sounds to the
  Switch formats, 64-bit behaviors and animations, FOMOD installers step by step, safe plugin
  renames that follow everything that uses the name (BSAs, voices, FaceGen, scripts, masters).
- **The Doctor**: checks the load list (and its 4096-byte limit), masters, BSAs, inis, textures,
  audio, missing scripts and meshes, scripts that replace the game's or USSEP's, SKSE files that
  don't work on Switch, and more. Each finding explains what happens in the game and how to fix it.
- **Load order** with LOOT's masterlist, **file conflicts**, **texture and audio weight** per mod.
- **Copy to SD** copies only what changed and keeps a backup of everything it replaces.
- **SkyNX Mods** on the console reads the info the app writes to the SD: what each mod is, what it
  weighs, who needs it. Changes made on the console can be brought back into the project.

## Limits worth knowing

| Limit | Value |
| --- | --- |
| Load list `Skyrim_aoc.ccc` (AE) | 4096 bytes; the game stops reading after that |
| Ini archive lists | 1024 characters each; `Skyrim_en.ini` wins over `Skyrim.ini` |
| Scripts in BSAs | A BSA listed in the ini wins over one loaded by its plugin (the reverse of PC) |
| Game memory ("Application" in Status Monitor) | About 3285 MB in total; crashes were seen from about 2.8 GB |
| SKSE, its `.dll` plugins and MCM menus | Don't exist on Switch |

## Building from source

**The app** (Windows, Python 3.12 from python.org with "Add python.exe to PATH"):

    construir.bat          builds dist\SwitchNX Studio.exe (the first run takes a few minutes)
    abrir-sin-exe.bat      runs the app from the source, without building

**SkyNX Mods** (devkitPro with "Switch Development" in `C:\devkitPro`):

    extras\nxmods\construir_nro.bat          builds extras\nxmods\SkyNXMods.nro

On Linux, `make -f Makefile.linux` in `extras/nxmods` builds a desktop version (SDL2) for
testing, and `make -f Makefile.linux test_modlist && ./test_modlist` runs its tests.

**SkyNX Test Tools**: `python extras/nxtest/build.py <your Skyrim.esm> extras/nxtest/pex out`.

**A release**: after the two builds above, `preparar_release.bat "C:\SkyNX\Vanilla\BSAs\Skyrim.esm" "C:\SkyNX\Tools"`
puts every zip of the table above in `release\`.

**Tests**: `python -m pytest -q`. Some tests need files that can't be shared and skip themselves;
see `tests/README.md`.

## Repository layout

    app/                  the window (pywebview) and the interface (app/web)
    skynx/                the engine: BSA, plugins, Doctor, converter, LOOT, SD copy...
    docs/                 the in-app manual (EN and ES) and older release notes
    extras/nxmods/        SkyNX Mods, the Switch homebrew (C++, SDL2)
    extras/nxtest/        SkyNX Test Tools (Papyrus sources, compiled scripts, builder)
    extras/status-monitor/  the overlay mode
    extras/skeleton/      the C:\SkyNX folder skeleton
    extras/skill/         the Claude skill
    extras/release/       the release script and the licenses of the tools it bundles
    tests/                pytest suite and small fake tools

## Contributing

Issues and pull requests are welcome. When something goes wrong in a pack, the most useful things
to attach are the Doctor's report (**Copy report**), the load order (**Copy order**) and, for
crashes, the report from `atmosphere/crash_reports` (SkyNX Mods shows them on the console).

Please never attach or commit game files, Nintendo SDK files or other people's mods.
To share a whole pack, use **Pack recipe**: it lists the mods with their Nexus links.

## Credits

Made by **nealcobu**, with a lot of help from Claude (Anthropic).

A huge thank you to **KokaNX**, whose work on Skyrim for Switch (the memory and `.ccc` limits,
how BSAs load, behaviors, USSEP for Switch) is behind many of the app's rules. Thanks also to
Antony Marshall and Zappastuff (Skyrim NX Toolkit), ElminsterAU and the xEdit team, Mator (zEdit),
the LOOT team, Arthmoor and the USSEP team, masagrator (Status Monitor Deux), Microsoft (texconv),
Alex Barney (VGAudio), the FFmpeg project, and everyone who converts, tests and shares modpacks.

## License

MIT for this repository's code and art (`LICENSE`). Third-party parts keep their own licenses:
see `THIRD-PARTY-NOTICES.md`.

The Elder Scrolls and Skyrim belong to Bethesda Softworks / ZeniMax Media, and the Nintendo
Switch to Nintendo. This project isn't made or endorsed by either.
