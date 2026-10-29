# SwitchNX Studio 0.8

Build, check and fix Skyrim modpacks for Nintendo Switch, then copy them to the SD with a backup.
Works with Anniversary Edition (Skyrim_aoc.ccc) and Special Edition (Plugins file). English and Spanish.

## Build the .exe

1. Install Python 3.12 from python.org (tick "Add python.exe to PATH").
2. Double-click `construir.bat`. The first run takes a few minutes.
3. The app is `dist\SwitchNX Studio.exe`. It runs on its own; move it anywhere.

`abrir-sin-exe.bat` runs it from the source without rebuilding.
If the app window can't open (WebView2 missing), the same interface opens in the browser.

## External tools

Everything goes in one folder: `C:\SkyNX\tools` (or a `tools` folder next to the .exe).

- `texconv.exe` (textures), `ffmpeg.exe` (reads PC audio).
- `VGAudioCli.exe` + `VGAudio.dll`, the Skyrim NX Toolkit build (writes Switch Opus and .mcadpcm).
- Optional: `NvnTexpkg.exe` with `NvnTexpkg.dll`, `NvnImage.dll`, `DdsLoader.dll`, `TgaLoader.dll` for native Switch textures.

## What it does

- **Start from scratch**: creates the folders, inis and load list. The base inis come from your console
  (dump them with DBI) or from a modpack you trust; its tweaks stay and its mods are removed.
- **Convert PC mods**: reads the mod, shows the budget (.ccc bytes and texture memory before and after) and converts it.
  - Textures follow Koka's rules or the lighter "Switch 1" and "Extreme" diets. With NvnTexpkg they become
    native Switch textures, and opaque ones can drop to BC1. Without it they stay DXT5 DDS, as Koka does.
  - Voices become Switch Opus in FUZE with their lip data; music and effects become .mcadpcm.
  - SE 64-bit animations are converted with the Toolkit's method.
  - Safe plugin renames update the plugin, its BSAs, voice and FaceGen folders, tint paths inside meshes,
    SEQ, strings, .pex scripts, json/ini configs and dependents' masters.
  - Packs `Name.bsa` and `Name - Textures.bsa` and adds the mod in one undoable step.
- **FOMOD assistant**: installers are shown step by step with images and descriptions, following the official
  schema (ordering, steps shown by earlier choices, file priorities, conditional installs). Patches for mods that
  aren't active in the pack show as not available, including mods the converter renamed. Choices are recorded.
- **English**: packs are built in English. Starting from scratch copies Skyrim.ini and Skyrim_en.ini (writing the
  console's original if it's missing). On Switch Skyrim_en.ini replaces Skyrim.ini's texture list, so BSAs loaded
  through the ini go into both, and the Doctor warns when one is hidden.
- **Mods**: add mods already converted for Switch from a folder, .7z or .zip. Plugins go into the load list
  after their masters; BSAs without a plugin go into the ini lists by what they contain
  (textures and voices to list 2, animations also to the in-memory list). Remove a mod in one click.
- **Doctor**: checks the load list, masters, BSAs, inis, textures and audio, explains each problem and shows
  exactly what a fix will change before applying it.
- **History**: every change keeps a copy of what was there before, in the modpack's `.skynx` folder. Anything can be undone.
- **Load order**: drag and drop, with live warnings for missing or misplaced masters.
- **Textures and audio**: reads headers inside each BSA (PC DDS and Switch DFvN) and estimates each mod's weight.
- **Copy to SD**: compares the pack with the SD and copies only what changed (same size and date counts as
  unchanged). It shows the plan first: what's copied, replaced, removed and backed up, and whether it fits.
  Everything replaced or removed goes into a checked .zip in the pack's `.skynx\respaldos-sd` first; if the copy
  fails, the SD is restored. A full copy is still available.

## New in 0.8

- **Projects.** Each modpack you build or maintain is a project in a folder of its own
  (`Library\Projects\<name>`): `Mods\` with each mod's files and a `mod.json` (version, origin, conversion,
  whether it goes), `Base\` with the inis and the load list, and `Switch\`, made by **Pack**, with the two folders
  for the console. A project starts from scratch, from a modpack (folder, zip/7z/rar, another project) or from the SD;
  the source is copied and never written. Files changed or added by hand in `Mods\` or `Base\` come into the project
  as one undoable change. Copy to SD always packs first and sends exactly what's in `Switch\`.
- **Modpacks aren't kept in the Library anymore.** A modpack becomes a project, or a source you bring mods from
  (Mods » From a modpack…, straight from its zip). Packs and packs being created from before are listed on Home with
  **Turn into a project**; the originals stay until you delete them.
- **Home in three parts:** Projects, the Workshop (quick jobs on single mods, unchanged) and the Mod Library (mods and
  the Catalog, which now reads your projects).
- **Safety review** of the new code: projects copy their source by default (linking is a setting, off), `Switch\` is
  real copies built incrementally, files the app didn't make are moved to the trash instead of deleted, two hand
  files for the same place are both kept aside, and Mods/Base are left alone if the working pack goes missing.

## New in 0.7

- **Home in four paths**: Work on one mod, Work on many mods, Create your modpack, Use a pre-made modpack. Below
  them, single tasks (check and fix, resize textures, shrink a pack, join BSAs, file conflicts, load order, rename,
  Switch versions, copy to SD, undo); with no pack open the app asks which one.
- **Help**: the manual inside the app (top bar » Help), English and Spanish, with contents and search. It opens at the
  part about the page you're on. Sources: `docs/manual.en.md` and `docs/manual.es.md`; after editing them run
  `python docs/build_manual.py`.
- **First run**: credits and what the app does, then Your setup: every tool and folder, whether it was found, and what
  stays off without it. The home screen keeps a short list of what's missing.
- **Catalog** (Library > Catalog): every pack and mod in your Library becomes one shelf. Filter by pack or category,
  tick the mods you want (30 from one pack, 10 from another), and the side panel plans the new pack: edition, CC,
  USSEP, base inis, .ccc and ini budget, missing masters. "Create pack" builds it and opens it, ready for extras.
- **Compare with the original**: a converted mod in Add mods can be compared with its PC version (records, files,
  textures, sizes), to see what someone else's conversion changed.
- **KokaNX checks in the Doctor**: animations kept out of the in-memory list, HEDR 1.71 on SE, missing or stale
  `.seq` files for start-enabled quests, USSEP BSAs right after the vanilla ones and USSEP first after the CC.
- **Converter options**: maximum texture size with an estimate, packing (one BSA per plugin, one single BSA, or
  ini-loaded) and BSA compression.
- **External tools**: SSEEdit opens either on the pack (what you save goes into the pack by itself when you close it,
  undoable) or on a copy (when it closes you choose: bring the changes, keep the copy for later, or delete it). Load order rows have an on/off box and show each plugin's masters. Mods can be extracted from their BSA.
- **Three spaces**: the start screen opens Modpacks (dark oak and brass), the Mod workshop (cherry and copper) and the
  Library (walnut and verdigris); the frame, menu and buttons change wood so you always know where you are. Packs,
  benches, mods and the Library have "Open folder" links to the Explorer.
- **Mod workshop**: a bench is a private workspace for mods, no pack needed. Convert a PC mod, edit a mod (rename with
  everything that follows, extract, SSEEdit), join several mods into a suite (their BSAs become one, in game load order,
  later files win) or merge plugins with zMerge step by step (the app prepares the zEdit folder, brings the merge,
  takes the merged plugins out and joins their BSAs under the merge). Save puts the result in Library\\Converted.
- **Which mod is it (Nexus)**: every mod on the Mods page and on a bench shows its Nexus page when the app can tell:
  what you confirmed (remembered per plugin file, so it follows the plugin into other packs), a Nexus download, or
  LOOT's masterlist, asked with the name in the pack and with the original names the app recorded (renames, Drive's
  '_'). Merges list the mods inside. For the rest: search Nexus with the plugin's words, or paste the link. With the API
  key it fetches names and versions. Links go to the Skyrim Special Edition pages, where the Anniversary mods live.
  The same chip shows on the Add mods cards and the Catalog rows, and the exported recipe carries those links (saying
  whether LOOT recognised them or you confirmed them).
- **Tried on real downloads and packs**: Mac zip junk (`__MACOSX`, `._Mod.esp`) never reaches Data or the list; mods
  with `_AE` and `_SE` folders use the pack's edition; optional folders with their own plugin go in as part of the mod;
  a BSA-only mod keeps its BSA's name; the Doctor offers to extract mods a pack ships compressed (Ashiro's list);
  `.rar` opens through 7-Zip or Windows' `tar.exe`; no fix, added mod or "goes" pushes the .ccc past 4096 bytes; the
  History shows in the app's language.
- **AE and SE mods in either pack**: an SE mod goes into an AE pack as it is. Into an SE pack, a mod made for AE is
  adapted on the way in (Add mods, Convert, batch, Bring from another pack, the Catalog): the ESL flag of its `.esp` is
  cleared (SE would ignore it) and HEDR 1.71 drops to 1.70 when no record of its own uses the low form IDs that only
  1.71 allows (otherwise it stays and the Doctor explains). A real `.esl` goes through Convert or the Doctor fix "Turn it
  into .esp for SE". Plugins that need Creation Club content stay in Data but off the list, because SE has no CC. Each case
  leaves a note on the card.
- **Convert several at once**: Convert mods, "Several at once" tab (or "Convert several mods" on the main menu, or
  "Convert all PC mods" in Add mods). Each mod gets a narrow card with its diet, largest size, packing, native format and
  plugin names; "For all" sets them on every card. FOMODs are chosen inside the batch, and their patches for other mods
  of the batch become usable. The .ccc and texture meters add everything up. Before starting it checks that no name
  repeats and the .ccc fits; then it converts the mods others need first and points them at the final name. If one
  fails the rest go on, and the failed one stays to be read again. Each mod is also kept in Library\Converted (when the
  box is ticked).
- **Versions for Switch**: "Versions for Switch" (Nexus bar on Mods, "Check for updates on Nexus", or a mod's card)
  looks inside each mod's files on Nexus (the content list Nexus publishes) plus their description and changelog. A
  version that ships SKSE plugins (.dll) doesn't work on Switch; one that names SKSE, Address Library, PapyrusUtil, SPID
  and the like is marked for checking. It shows the one you have, the latest and the best for Switch (the newest that
  works), linked to its file. When the app doesn't know your version, "I have this one" remembers it. Needs the API key.
- **The pack being created**: start a pack as an exact copy of another (Library > "Start a pack from this one": same
  files, same .ccc bytes, same inis) or from the Catalog. On its Mods page each mod has a box: untick it and it leaves the
  load list and the inis (the .ccc and ini numbers update), tick it and it goes back where it was. Rename any plugin
  with a preview of everything that follows the name and the .ccc bytes it costs. "Bring from the Catalog" adds mods
  from other packs into it. "Create modpack" writes a clean copy (only what goes, no history) to a folder you name,
  then offers to copy it to the SD. On the same drive both are hard links (no extra space); the app never writes
  into a file in place, so the pack a copy came from never changes (Settings can turn links off).
- **Library\\Converted**: every mod you convert also leaves a copy there (plugins, BSAs and how it was converted).
  It shows up in the Library and the Catalog, so it goes into other packs without converting again.
- **A pack that moved**: opening it from the recent list finds it in the Library by name.
- **Credits and Your gear**: a welcome screen with the credits (with "don't show again") and a page listing what the
  app can use on this PC, what's there and what's missing.
- **Tavern look**: wooden wall, parchment pages, oak and brass buttons, and the app icon.
- **Duplicates you decide on**: every duplicate in the Doctor offers to keep them or keep only one copy. Keeping one
  puts it where the first copy was, points patches at it, and keeps (or renames) the BSAs it needs. A mod that is
  also inside a merge is emptied (records out, BSAs still loading). "Keep both" hides the warning until you show it
  again. Everything is undoable.
- **Nexus**: paste your personal API key in Settings. The site's Mod Manager Download button can send files here
  (they download into the Library and appear in Add mods; works with a free account; Vortex or Mod Organizer can
  take the button back). Downloaded files remember their Nexus mod and version; others can be found on Nexus by MD5.
  "Check Nexus for updates" on the Mods page compares your versions, only when you press it.
- **Pack recipe**: every mod added from now on records where it came from (Nexus, archive, folder, another pack,
  USSEP), its FOMOD options and conversion settings. The Mods page shows the recipe, what changed since it was
  saved, and exports a shareable .md with Nexus links and no paths from your PC.

## New in 0.6

- **LOOT and merged plugins**: a merge (Merge Plugins / zMerge, like Avner's EnaiRim_NR.esp) is read from its own
  header and treated as the mods inside it: it takes the latest of their LOOT groups and inherits their rules,
  requirements and patch messages. Empty placeholder plugins kept for patches are recognized, and a mod that is
  both merged and loose is reported.
- **Plugins LOOT doesn't know**: each one gets a suggested category from what it contains (new lands and items,
  patches, races, perks...), with the reason. You confirm or pick another one; choices are saved for every pack.
- **Requirements in the Doctor**: LOOT requirements, incompatibilities and patch messages (PC-only tools like SKSE
  plugins are left out), animations that need DAR, OAR, Nemesis or FNIS, and behavior files that override each
  other. With the console's vanilla BSAs set in Settings it also finds missing scripts, meshes and textures.
- **Duplicates in the Doctor**: the same plugin under two names, the same BSA loaded twice, a mod inside a merge
  and loose too.
- **Bringing mods from another pack** gives them a name Google Drive won't damage, in the same step.

## New in 0.5

- **Add mods**: drop zips, 7z, folders or a lone .esp/.bsa on the window (or pick them). Each one is identified:
  modpacks go to the Library, mods already converted for Switch get a quick check and go straight in,
  PC mods and FOMOD installers open in Convert.
- **Check before adding** (Switch mods from Discord and the like): voices or faces stored under another plugin
  name, PC files left inside, unsafe names, missing masters, ESL on SE, SKSE use, and how much the texture
  diet would save. It recommends adding as it is or going through Convert.
- **Library** (`C:\SkyNX\Library`, with `Packs` and `Mods`; changeable in Settings): import modpack zips
  (Drive's split zips included), keep mods, see each pack's health at a glance.
- **Bring mods from another pack**: pick mods from any pack in the Library; their masters come along, what the
  pack already has is left out, and the plan shows the .ccc and texture budget before anything is copied.
- **USSEP for new packs**: pick the KokaNX version (All_CC, Survival Mode, No CC, or none). Missing Creation
  Club masters are added to the list.
- **First steps** on the welcome page: tools, console inis, USSEP and Library, each with what to do.
- **LOOT order**: suggests an order from the official LOOT masterlist (downloaded and cached), with the reason
  for every move, keeping your order where nothing says otherwise.
- **File conflicts**: which BSAs replace files of others, and archives that end up fully replaced.
- **Doctor additions**: FaceGen tints pointing at the wrong plugin (Cheat Room), Drive-unsafe names with a full
  safe rename (Ryn's Standing Stones), texture diet for Switch textures already converted (USSEP's tints),
  junk files inside BSAs (.psc sources), and SKSE / MCM warnings.

## Verified with real packs

- BSA name hashes match on 9,815 of 9,815 real files.
- Rebuilding a BSA without changes gives a byte-identical file (including a 177 MB one).
- The FUZE voice container rebuilds identically for all 995 voices in the packs; all 146 meshes and
  786 scripts parse completely, and a tint path rename round-trips byte for byte.
- 28 tests built from the community packs: Drive's apostrophes, the Auri rename, master order, typos, undo,
  SD deploy, and a modpack built from scratch with USSEP, Odin and Koka's animation pack.

Not confirmed yet: the exact .ccc limit (4096 bytes fits the evidence), the order the game uses for
plugins loaded through `sTestFile`, and whether loose files in Data work on Switch.

Credits: sound formats and the animation method come from the Skyrim NX Toolkit (Antony Marshall and
Zappastuff, MIT licence); texture rules from Koka.
Fonts: Barlow Condensed and Cinzel, SIL Open Font License (see `app/web/fonts`).
