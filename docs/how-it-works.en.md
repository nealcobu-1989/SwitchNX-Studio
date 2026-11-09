# How SwitchNX Studio works

What the app does to your files, one feature at a time: what goes in, the steps (with the module under `skynx/` that runs them), the external tool if any, and what comes out. The interface in `app/web` only calls these modules.

Two rules hold everywhere. **Source files are never modified:** a mod is extracted or copied into a temporary staging folder first, and archives the Doctor fixes are rebuilt as new files and swapped in. **Every change to a pack is recorded** and can be undone (section 11).

## External tools

The app looks for one tools folder, `tools` next to the program or `C:\SkyNX\Tools` (`skynx/tools.py`). Nothing is downloaded. Tools run without a console window, and a tool's error output goes into the report.

- **texconv:** PC texture format, size and mipmaps.
- **ffmpeg** and **VGAudioCli** (with VGAudio.dll): audio. Both are needed, or sounds stay as they came.
- **NvnTexpkg** (with its four DLLs): native Switch textures. It belongs to the Nintendo SDK; you supply it and the app never ships it. Without it, converted textures stay PC DDS.
- **HavokBehaviorPostProcess.exe** (Bethesda's Creation Kit) and **hkxc.exe** (serde-hkx): Havok files a byte patch can't convert.
- **Nemesis:** behavior generation for FNIS and Nemesis mods.

## 1. Converting a mod

**In:** a PC mod for Skyrim SE or AE (`.zip`, `.7z` or folder). **Out:** its plugins and Switch BSAs in the open pack, as one undoable step. Module: `skynx/converter.py`, in two calls.

**Analyze** writes nothing to the pack:

1. The mod is extracted into a temporary work folder (`skynx-conv-…`), refusing paths that escape it. A FOMOD installer is shown and your choices are installed there (`skynx/fomod.py`). When a download holds AE and SE versions side by side, the one for the pack's edition is used (`skynx/variants.py`).
2. The mod's root (the shallowest folder holding a plugin, a BSA or a game folder) is copied into a staging `data` folder. Plugins, BSAs and game folders (`meshes`, `textures`, `sound`, `music`, `scripts`, `interface`, `seq`, `strings`…) are kept. Folders such as `fomod`, `skse`, `source`, `docs` and `optional`, files such as `.psc`, `.bak`, `.psd`, `.dll` and `.exe`, Mac leftovers and root `.ini` files are dropped; SKSE plugins and mod inis get a warning, because the Switch runs neither. The mod's own BSAs are unpacked into staging, and a loose file with the same path wins, as on PC.
3. Voice leftovers the game never loads are removed: the Creation Kit's `processing` folder, old takes, empty voice files and voice folders of earlier plugin names.
4. Texture headers are read, Havok files classified and sounds grouped. A file name outside Windows-1252 stops the conversion, since a BSA can't store it. Copies of the game's own masters are dropped.
5. Plugin headers are read. Missing masters are reported, and a master this pack knows under a new name is mapped to it (section 6). HEDR below 1.0 (the 2011 game) gets a warning. A safe name and a short one are suggested; if the voice or FaceGen folders use another plugin name, that name is suggested instead.

**Convert:**

1. Final names are checked (extension, safe characters, 60 characters at most, not taken, no clash with the game's archives). In an AE pack the conversion stops before any work when `Skyrim_aoc.ccc` would pass 4096 bytes, unless you allow it.
2. Renames are applied in staging (section 6).
3. In an SE pack, `skynx/edition.py` clears the ESL flag (an `.esl` already got an `.esp` name) and sets HEDR 1.71 to 1.70 when the plugin has no own records below object ID 0x800; otherwise the version stays and the Doctor explains how to renumber. A plugin that needs Creation Club masters gets a warning and stays in `Data`, switched off.
4. Textures, Havok files and sounds are converted (sections 2, 3 and 4).
5. Files are packed into BSAs (section 7).
6. `builder.add_mod` copies plugins and BSAs into `Data`, appends the plugins to the load list, adds ini-loaded BSAs to the archive lists and records settings and source in `.skynx/mods.json`, in one history entry. By default a copy also goes to `Library\Converted` for other packs.

## 2. Textures

`skynx/texplan.py` plans each file, `skynx/converter.py` runs the plan, `skynx/diet.py` handles textures that are already Switch, and `skynx/nvn.py` reads and writes the native `DFvN` format.

**Size presets** work by area: a texture is halved until width × height fits in side × side. Nothing is enlarged, and `interface\` and `menus\` textures are never resized.

- **Switch 1 diet** (default): 1024; non-colour maps (`_n`, `_msn`, `_s`, `_m`, `_g`, `_e` and similar) and clutter, effects, plants and grass at 512.
- **Classic rules:** 1024; `actors\` at 2048.
- **Extreme:** 512; maps at 256; `actors\character` at 1024.
- **Original size:** no size rule.

An optional maximum size (256, 512, 1024, 2048 or 4096) then halves a texture until its largest side fits.

**Formats.** Without NvnTexpkg the result stays a PC DDS in BC3 (DXT5), and BC5 normal maps stay BC5. With NvnTexpkg, BC1 and R8 become BC1, BC4 and RG8 become BC5, BC2 and BC5 stay, and the rest becomes BC3. The option **BC1 for opaque textures** (only with NvnTexpkg) writes a texture as BC1, half the memory, when every pixel is opaque.

**Mipmaps.** The full chain is rebuilt, except water textures (`textures\water\`), which stop at 4 levels because the full chain draws artifacts on Switch water. Interface textures keep theirs.

**Per PC texture:** texconv runs only if format, size or mips change (`-dx9 -sepalpha -f <format>`, plus `-w`, `-h`, `-m`), and its output must be a DDS of the planned size. With the SDK, `NvnTexpkg -i <dds> -o <xtx>` follows and its output must start with `DFvN`; if it fails, the texture stays a PC DDS in BC3 and is listed. On any other failure the file goes back exactly as it came.

**Textures already native** (in conversion and in the Diet): uncompressed ones (RGBA8, R8, RG8; FaceGen tints are the usual case) become BC3, BC4 or BC5 (BC1 when opaque and the option is on) at the preset's size. Compressed ones bigger than the preset lose their largest mips when they have them, which is exact; otherwise texconv resizes them. The new native file comes from NvnTexpkg when present and from the app's own writer otherwise.

**Diet on an existing BSA** (`bsafix.diet`): every texture is planned, a new archive is written beside the original and swapped in through the history. A texture that fails stays byte-identical. The Doctor suggests it when the Switch 1 diet with BC1 saves 8 MB or more.

## 3. Audio

Modules: `converter._convert_sound`, `skynx/nxaudio.py`, `skynx/audio.py`. Files under `sound\` and `music\` are grouped by base name; a group is converted when it has an `.xwm` or `.wav`, or a `.fuz` with PC audio. Switch `.fuz` and `.mcadpcm` files are left alone.

- **Voices** (`sound\voice\`): a PC `.fuz` is split into lip data and audio. ffmpeg decodes to mono 48 kHz 16-bit PCM, VGAudioCli encodes Nintendo Opus, and `nxaudio.build_fuz` writes the Switch `FUZE` file with the lip data, the Skyrim Opus header and the stream.
- **Music and effects:** ffmpeg decodes to 44.1 kHz PCM (stereo at most) and VGAudioCli writes `.mcadpcm`, one DSP-ADPCM stream per channel.

The PC files of each converted group are removed; a failed sound stays as it came and is listed. The Doctor's deep check flags PC audio in BSAs and reads Switch voices and music in full to catch files cut short (`audio-broken`).

## 4. Animations and behaviors

**Havok files** (`skynx/hkx.py`, `skynx/havok.py`): byte 16 of the header gives the pointer size (4 for the 2011 game, 8 for 64-bit) and byte 18 the platform.

- 64-bit PC animations are converted in place with no tool: the platform byte is set and four header bytes move.
- Behavior graphs, skeletons, 32-bit and XML files are rewritten by HavokBehaviorPostProcess `--platformps4`; 64-bit ones go through `hkxc convert -v xml` first. The output must use the Switch layout rules (8-1-1-1).
- Without the tools these files stay as they came, and the report counts them.

**Generating behaviors** (`skynx/behaviors.py`): conversion keeps the PC originals generation needs (FNIS lists and their animations, the Nemesis patch) in `.skynx/behavior-sources/`. **Generate behaviors** (Mods page) builds a work folder with a copy of Nemesis, an empty `SkyrimSE.exe` so it treats the folder as Special Edition, the game's behavior files and every mod's sources. You press Update Engine and Launch in Nemesis. When its log says "Behavior generation complete", every changed file is collected, each `.hkx` made Switch-native, and all go into `SkyNXBehaviors.bsa`, added as the mod "SkyNX - Generated behaviors". A new run replaces the old set.

## 5. FaceGen face tints

Each face mesh (`…\facegendata\facegeom\<plugin>\`) names its tint texture (`…\facegendata\facetint\<plugin>\`) inside a `BSShaderTextureSet` block.

- **Renames:** both folders follow the new name, and `nif.replace_texture_folders` rewrites the tint paths, changing only path segments equal to the old name. `skynx/nif.py` refuses a mesh whose block sizes don't add up exactly; in conversion, an unreadable FaceGen mesh keeps the plugin's name.
- **Memory:** uncompressed tints are the diet's main target; the Doctor adds a Savings finding past 20 MB.
- **Broken paths** (deep check, `bsafix.scan_tints`): a tint missing from every archive of the pack is reported (`tint-broken`). When it exists under the folder of the mesh's own plugin, a safe fix (`bsafix.fix_tints`) rebuilds the BSA with the meshes pointing there.

## 6. Renaming plugins

A plugin's file name lives in many places, and a rename updates them together. `rename.safe_name` removes apostrophes, quotes, accents and symbols, which Google Drive damages.

**During conversion** (`rename.apply`, on staging): the plugin files; masters of every plugin; script properties (`VMAD`) whose whole value is an old name (`records.rename_in_vmad`); voice, `facegeom` and `facetint` folders; `seq\<plugin>.seq` and `strings\<plugin>_<language>.*strings`; FaceGen tint paths; Papyrus string-table entries equal to the old name, such as the file argument of `GetFormFromFile` (`pex.rename_plugins`); and text configs (`.json`, `.ini`, `.txt`, `.xml`…), only where the name stands as a whole value. Chains and case-only renames work because files move in two phases.

**In an existing pack** (`bsafix.rename_plan`, `bsafix.safe_rename`) a preview lists what will change; then, in one history entry, the app rebuilds the BSAs whose paths or scripts name the plugin, renames the plugin and the BSAs that load with it, updates masters and script properties in every plugin, the load list line (also when off with `#`), `sTestFile` entries and archive lists, and `.skynx/mods.json`. It also writes the renames registry `.skynx/renames.json`, which points later mods that use the original name as a master at the new one, answers FOMOD conditions and feeds `script-gone-name`. The Doctor offers this rename for names Google Drive would damage.

**What it can't change.** Only whole values are replaced. A name inside a longer text (a message, a property holding several values) stays as it is, because changing part of a text could break it. After a conversion rename, `rename.leftovers` searches script strings, script properties and config lines for the old name as a standalone word, and the result warns with the count, up to five "file: text" examples and the advice to test in game. In an existing pack, the deep check lists them.

## 7. BSA packing and compression

The converter writes version 105 archives with `bsa.write_bsa`, in one of four modes:

- **One BSA in the inis (Switch version, default):** one `<name>.bsa` in whichever ini archive list stays shorter. The name is the plugin's, compacted to 12 characters and never equal to a plugin name (it would load twice). With no room in any list, it becomes the next mode.
- **One BSA named after the plugin (no ini):** `<plugin>.bsa`.
- **BSAs named after the plugin (no ini):** `<plugin>.bsa` and `<plugin> - Textures.bsa`.
- **BSAs listed in the inis:** `<name>M.bsa` (meshes, scripts, animations) in `sResourceArchiveList` and `<name>T.bsa` (textures, voices) in `sResourceArchiveList2`.

Archives are split past 1.9 GB. **Compression** (on by default) applies only to `.nif`, `.hkx`, `.tri`, `.btr` and `.bto`, with LZ4 per file; textures and sounds are stored raw, as in the Switch packs examined. After writing, the archive is read back and every file compared with its source before it replaces the destination. When the Doctor only moves or renames files, `bsa.rebuild_bsa` reuses the stored data without compressing again.

## 8. The Doctor

`skynx/audit.py` and `skynx/scriptcheck.py` only read. Each finding has a severity (Serious, Check, Savings, Info) and may bring a fix, marked safe or "check before applying".

- **Quick check:** layout, load list format, plugin headers, masters and order, `.ccc` size, ini duplicates and list lengths, BSAs whose voice or FaceGen folders name another plugin, junk in BSAs.
- **Deep check** adds BSA contents (texture formats, PC textures and audio, files that are all zeros, 2011 meshes), FaceGen tints, SEQ files, requirements against the console's own BSAs when that folder is set, and script checks (plugins asked for by name that aren't loaded, scripts replacing the game's, `script-gone-name`). Opening a pack, **Check again** and every fix run it; undo and renames run the quick check.

**Fixes** (`skynx/fixes.py`): `preview` lists each change without touching anything. `apply` runs the whole fix in one history Transaction (list edits, renames, ini edits, BSA rebuilds written as `.skynx-new` and swapped in), so it undoes in one step, and a fix that fails halfway is rolled back at once. **Fix the safe ones** applies safe fixes one by one, re-checking in between.

## 9. Load list and inis

A pack holds `01000A10041EA000\romfs` (`Data`, inis and, for SE, the `Plugins` list) and, for AE, `01000A10041EB009\romfs\Skyrim_aoc.ccc`.

**Load list** (`skynx/ccc.py`): one plugin per line; edits keep untouched lines byte-identical, with their BOM and line endings. A line starting with `#` is off and Pack leaves it out. New plugins go at the end, after their masters. `knowledge.py` sets the AE ceiling at 4096 bytes, with a warning above 3900, and any write that would grow the list past it is refused.

**Inis** (`skynx/ini.py`): a tolerant reader (duplicate keys, `#` and `;` comments, keys with spaces) whose edits touch only one line. The language ini (`Skyrim_en.ini`…) replaces `sResourceArchiveList2` of `Skyrim.ini`, so entries go into every ini that sets the key. A BSA without a plugin goes to `sResourceArchiveList2` with textures or voices and to `sResourceArchiveList` otherwise. Each list holds 1024 characters at most, with a warning above 900.

## 10. Packing and copying to the SD

**Pack** (`project.build`) writes a project's `Switch\` folder: real copies of the two title folders, without the mods you left out, the `#` list lines or ini entries for BSAs whose plugins are all off. It refuses when a plugin that goes needs a master that doesn't, copies only what changed, and moves anything edited by hand to the project's trash.

**Copy to the SD** (`skynx/deploy.py`) touches only the two Skyrim folders under `atmosphere\contents`, checks the drive looks like a Switch SD and keeps 200 MB free. **Copy the changes** (sync, the default) compares paths ignoring case; same size and a time within 2 seconds means unchanged, and same size with another date means a hash check under 8 MB. Before touching the SD, every file to be overwritten or deleted is zipped into `.skynx\sd-backups` and verified; if anything fails, the SD is put back as it was. **Full copy instead** replaces both folders whole, with the same safety. **Moving mods between packs** (`skynx/transfer.py`) plans without writing, then copies files, list lines and ini entries in one history entry.

## 11. Undo and history

`skynx/history.py` wraps every change in a Transaction. Before a file is changed, created, renamed or deleted, its previous state is copied into `.skynx\history\<entry>\` and verified by SHA-1; `manifest.json` records each file's hash before and after. Deleted files go to `.skynx\trash`. A journal written before each change lets the app roll back an interrupted entry the next time the pack opens, and a change that fails is restored right away. **Undo** is refused when a file changed again afterwards (the message lists them), is recorded itself, and can't be undone in turn: apply the fix again instead.

## New in 1.0

- **Script properties follow a rename:** `VMAD` string properties holding the plugin's name are renamed in every plugin of the mod being converted, and in every plugin of the pack when you rename inside an existing pack.
- **Leftover warning:** after a conversion rename, the app lists places that still name the old plugin inside a longer text and leaves them as they are.
- **Doctor, `script-gone-name`** (deep check): scripts and script properties that still name a plugin this project renamed or merged.
- **Doctor, `mesh-le`** (deep check, Info): meshes from the 2011 game (NIF stream 83). Most work; if a model shows up invisible or stretched, resave them with Cathedral Assets Optimizer on "Full optimization".
- **Junk in BSAs** now also catches `.DS_Store`, `Thumbs.db`, `desktop.ini` and stray `.png` files outside `interface`.
