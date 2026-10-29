# SkyNX Mods (homebrew)

Turns the mods of a Skyrim pack on and off on the Switch itself, with the
look of SkyNX Studio. It edits `Skyrim_aoc.ccc` on the SD:

- A plugin that's off is left out of the `.ccc` (lines with `#` still count
  toward the 4096-byte limit). The full list, with the ones that are off, is
  kept in `sdmc:/switch/SkyNXMods/skyrim.txt`.
- Turning off a plugin others use as a master offers to turn those off too;
  turning on one whose masters are off offers to turn them on.
- The first `.ccc` it saves over is kept as `Skyrim_aoc.ccc.skynx-original`.
- Saving deletes Atmosphère's `romfs_metadata.bin` of both titles, which the
  console makes again at the next start.
- Copying the pack again from the PC wins: when the `.ccc` no longer matches
  the side file, the list starts over from the `.ccc`.
- What each mod is: SkyNX Studio writes `skyrim-info.txt` (each plugin's
  name, description and BSAs) when it copies the pack, and the screen shows
  it on the right with the size on the SD, masters, who uses it and its ini
  BSAs. Creation Club entries have their own titles and descriptions.
- Estimated load of each mod: its records (the plugin, in memory all the
  time it's on) and its textures, meshes and audio (textures and meshes only
  while on screen). Light, medium or heavy: heavy is 10 MB of records or
  250 MB of textures and meshes; medium, 1.5 MB or 40 MB. SkyNX Studio
  0.9.15+ measures the BSAs by kind when it copies the pack; without that,
  it's a guess from file sizes. The top shows the records of what's on and
  how many heavy mods are on.
- Views: load order, alphabetical or heaviest first (ZR, or − More). The
  load order the game uses, the one LOOT gave, never changes; each row shows
  its place in it (#12). ZL: all, only on, only off.
- Skyrim's crash reports: Atmosphère writes a report and a screenshot of
  every game crash in `atmosphere/crash_reports`. − More lists Skyrim's,
  newest first: the screenshot, when, what kind of fault in plain words,
  where in the game's code, and how many crashes happened at that same spot.
  The footer shows the last one.
- The top also shows about how many BSAs the game will open with the list as it is (the
  inis' lists, the plugins' own and one per Creation Club entry): each is a file the game
  keeps open, and a long list may run out of them.
- Saved lists (− More): five slots for mini lists while testing. Save keeps which
  plugins are on (and the BSA count); load puts them back. In `switch/SkyNXMods/lists`.
- Creation Club in bulk (− More): switch off what nothing that's on uses as a master, the same
  with its unofficial patch first, or switch it all back on.
- − (More): views; crashes; switch off every mod but the game, the Creation
  Club and the unofficial patches (a clean base to switch groups back on when
  looking for a culprit); go back to the list the PC copied (`skyrim-pc.txt`)
  or to the one before SkyNX Mods first saved; mode and SD space.
- Opened from the Album (applet mode) or over a game (title mode), both work.
  If Skyrim is suspended in the background it says so: close it before saving.
- English or Spanish, by the console's language.
- Touch screen: tap a row to pick it and again (or on its box) to turn it on or off; drag
  the list to scroll; tap the buttons, menu items and the last crash in the footer; swipe
  left or right between crashes.

- BSAs listed in the inis (`sResourceArchiveList`, `sResourceArchiveList2`)
  load whatever the `.ccc` says. SkyNX Studio writes
  `sdmc:/switch/SkyNXMods/skyrim-ini.txt` when it copies the pack (the full
  lists and which plugins each BSA belongs to), and saving leaves a BSA out
  of its ini when all its plugins are off. An ini changed since the PC copied
  it is left alone. Without that file (a pack copied by other means), only
  the `.ccc` changes and such mods stay half on.
- The app's SD page notices choices made here and offers to bring them into
  the project, so the next copy doesn't undo them.

## Build

Windows: run `construir_nro.bat` (needs devkitPro in `C:\devkitPro`).
Elsewhere: `make -f Makefile.switch` in a devkitPro shell with `switch-sdl2`, `switch-sdl2_ttf`
and `switch-sdl2_image` installed.

Desktop test build (SDL2 dev libraries): `make -f Makefile.linux`, then
`./skynxmods <folder with atmosphere/...>`; arrows, Enter, Esc, X, Y, PgUp/PgDn, Tab (ZR), ` (ZL).
`--keys down,a,x --shot out.png [--lang es]` plays presses and saves a picture.
`make -f Makefile.linux test_modlist && ./test_modlist` runs the list tests.

Fonts: Barlow Condensed and Cinzel (SIL Open Font License, texts in `romfs/fonts`).
