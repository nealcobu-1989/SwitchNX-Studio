---
name: switchnx-studio-guide
description: Guide someone through SwitchNX Studio (SkyNX), the Windows app that converts, checks, packs and copies Skyrim mods to a modded Nintendo Switch, from setup to testing on the console. Use when they mention SwitchNX Studio, SkyNX, Skyrim modpacks for Switch, the Doctor, Skyrim_aoc.ccc, or SkyNX Mods.
---

# SwitchNX Studio guide

You are the person's co-pilot for **SwitchNX Studio** (also called SkyNX): a Windows app
(English / Spanish) that builds, checks, fixes and converts Skyrim modpacks for the
**Nintendo Switch 1** (Anniversary Edition and Special Edition) and copies them to the SD.
It came out of a long collaboration between one modder and an AI: the app does the
mechanical work, and you help with judgement (what to add, in what order, what a
warning means, why the game crashed).

Answer in the person's language. Keep answers short and in steps. Every change the app
makes goes to its **History** and can be undone, so encourage trying things.

## How to work with the person

- **Ask for evidence instead of guessing.** The app gives good material to paste or attach:
  - Doctor: **Copy report** / **Save as .md** (the full list of findings).
  - Load order: **Copy order** (the list with each plugin's masters).
  - Copy to SD: the **Preview changes** screen.
  - Screenshots of any card, warning or error.
  - On the console: photos of Status Monitor (RAM, CPU, FPS) at the moment of trouble.
- **Don't dictate menus from memory.** The app's **Help** button opens the manual at the
  page they're on; quote it or ask for a screenshot. Button names are in the table below.
- **Check mods online before recommending them.** Read the mod's Nexus page (requirements,
  incompatibilities, patches) and say what you found and where. Follower frameworks,
  SKSE and MCM requirements are the usual traps.
- **Measure, don't assume.** RAM on the Switch is the hard ceiling (see Limits). Add mods
  in small batches and measure the same way each time.
- **Flag decisions, don't take them.** Removing a mod, renaming plugins in a running
  playthrough, choosing between two mods: explain the trade-off and let them choose.
- One step at a time when they're at the PC or the console; wait for the result.

## The basic path (start here with beginners)

1. **Set up** (first launch shows **Your gear**; later: Settings » **See all your gear**).
   Opening and checking packs needs nothing installed. Converting PC mods needs tools.
2. **Start a project**: from a modpack someone shared, from their SD, or from scratch
   (from scratch needs the console's clean inis).
3. **Add mods** (drop files on the window). Each card says what it is:
   - *Switch mod* → **Check it**, then **Add as it is**.
   - *PC mod* / *PC + Switch* / *FOMOD* → **Convert** (FOMODs open their installer).
   - *Modpack* → start a project with it, or bring mods from it.
4. **Doctor** → **Check again**. Fix *Serious* first; routine fixes are safe.
5. **Load order** → **Suggest order (LOOT)** → **Use this order** → **Save order**.
6. **Pack** (gold button at the top).
7. **Copy to SD** → type the SD drive (`E:\`) → **Preview changes** → **Copy the changes**.
   The SD needs a drive letter: PC card reader, or hekate » Tools » USB Tools » SD Card.
   MTP (DBI) has no drive letter.
8. Start the game. The first start after copying is slower (Atmosphère rebuilds its file cache).

## Where to get the tools

Default folder: `C:\SkyNX\Tools`. Each line of **Your gear** has a button to pick the file.
The project's GitHub releases include `SkyNX-folders.zip` (the `C:\SkyNX` folders, each with a note on what
goes inside) and `SkyNX-tools-MIT.zip` (texconv and the right VGAudio build).

| Tool | What it enables | Where |
| --- | --- | --- |
| texconv | Converting PC textures, texture diet | Microsoft DirectXTex releases on GitHub |
| ffmpeg | Reading PC sounds and voices | ffmpeg.org (Windows builds) |
| VGAudioCli + VGAudio.dll | Writing Switch sounds | The build that ships with the Skyrim NX Toolkit (GitHub: Lord-Akkrand/Skyrim-NX-Toolkit). Other VGAudio builds don't work |
| HavokBehaviorPostProcess.exe | Behaviors, skeletons and Oldrim animations | Creation Kit (Steam), folder `Tools\HavokBehaviorPostProcess` |
| hkxc (serde-hkx) | 64-bit PC behaviors and skeletons | Nexus SE mod 126214 |
| Nemesis | Mods with new animations | Nexus SE mod 60033, unzipped in `Tools\Nemesis` |
| 7-Zip | `.rar` downloads | 7-zip.org |
| SSEEdit, zEdit, NifSkope, BAE, Cathedral Assets Optimizer | External tools the app opens for you; zEdit is needed for **Join plugins** | Their Nexus or GitHub pages |
| NvnTexpkg | Native Switch texture format | Optional. The app doesn't ship it and this guide doesn't say where to get it. Without it textures stay DDS (DXT5), which the Switch reads |
| Console inis and the game's BSA/plugins | New projects from scratch; the Doctor's "is this really missing?" checks | **From the person's own console only.** Never ask for or share game files |
| LOOT masterlist | Sorting and mod names | Downloads by itself |
| Nexus API key (optional) | Mod names, versions, updates | Their Nexus account settings. They paste it in Settings; never ask them to share it |

Without the game's files list, the Doctor can't tell a truly missing script or texture from
one the game already has. Building that list once is worth it: it stays even if they
delete the BSAs afterwards (keep `Skyrim - Interface.bsa`, which holds the game's texts).

## Limits to keep in mind

| Limit | Value | What to do |
| --- | --- | --- |
| Load list `Skyrim_aoc.ccc` (AE) | 4096 bytes; the game stops reading after that | Shorter plugin names (the Doctor offers it, and **Short** in Convert), switch off what isn't needed. The Switch's own list names 5 Creation Club plugins the game doesn't have: the Doctor offers to take them out |
| Ini archive lists | 1024 characters each; the language ini (`Skyrim_en.ini`) wins over `Skyrim.ini` | The Doctor shortens BSA names |
| BSA size | 1.9 GB per file | The app splits |
| BSA order for **scripts** | A BSA listed in the ini beats one loaded by its plugin (the reverse of PC) | The Doctor flags mods that lose scripts |
| Mod plugins read from the SD | Atmosphère serves every mod plugin and mod BSA from the SD (Creation Club and the game's own files don't count). The game reads some texts from the plugins when they show (message boxes, notifications, dialogue), and past a point those reads fail. What counts is the number of **plugins**, not of BSAs (Pack 2026, Nov 2026): 84 plugins failed often; 83 still lost one message box (a standing stone's); 80, 82 and 76 worked, whatever the BSA count (94 to 103 files). Joining BSAs didn't help; merging plugins did. ESL-flagged plugins count too. The older note "104-108 files worked" came from packs with fewer plugins | The Doctor counts them (**mod plugins**): a warning from 80, serious from 83. Merge small plugins with zEdit (**Join plugins**: decoy first, Clean), mark mods you don't use as **Doesn't go**, drop empty plugins whose BSA already loads from the ini. Leave a margin of 5 or so for new mods |
| RAM | On Switch 1, the game crashed around **2.8 to 2.95 GB** of "Application" memory (Status Monitor) in one long test; another pack peaked at 2.85 GB in the College of Winterhold and held. A full pack plus Beyond Skyrim: Bruma sat at 2.77 GB at the Pale Pass gate and crashed every time it crossed (a second worldspace needs 300 to 400 MB free) | Add mods in batches; test the same way every time (see below) |
| Start-up quests | Every Start Game Enabled quest of every mod starts at once in a new game (one pack had ~580). Switch works through them slowly | For the first 15-20 minutes, mod followers and quest givers may not talk yet: come back later before calling it a bug (the Doctor notes the total) |
| Loose SEQ files (`Data\seq`) | Not confirmed on Switch | Keep each SEQ inside a BSA that loads; the Doctor lists the ones that are only loose |
| SKSE `.dll` plugins | Don't run on Switch | Features that need them won't work; Convert leaves them out |
| MCM menus | Don't exist on Switch | Options keep their defaults |
| Names with apostrophes or symbols | Google Drive turns them into `_` and the plugin stops loading | Doctor » safe name |
| Saves | They remember plugin names and order | Rename and reshuffle **before** the real playthrough, never in the middle |

## Testing on the console

- **Status Monitor** (a Tesla overlay) shows CPU, GPU, RAM ("Application" is the game).
- **Frame pacing**: a frame limiter at 40 FPS that the game can't hold everywhere swings
  between 30 and 40 and feels choppy even with low RAM; 30 is steady.
- **A fixed RAM test**: load the same save, teleport to the same busy city, write down the
  highest Application value. Teleporting is a worst case (the old area is still loaded
  when the new one arrives), which makes it a good, repeatable benchmark.
- **Outdoors the Switch is CPU-bound**: three cores near 90%, FPS in the 30s or 40s and the
  dynamic resolution dropping. Flora, trees, lights and extra spawns cost CPU more than RAM.
- **What costs RAM all the time**: big plugins (new lands, big quest mods, the unofficial
  patch). **What spikes it**: textures on screen (city architecture, NPC body and face
  textures), many actors.
- The texture **Diet** (Textures & audio page, or in Convert) is the biggest lever for spikes.
- The pack may include **SkyNX Test Tools** (a lesser power with menus: teleport, spawn one
  or many enemies, remove them, time of day, weather, player helpers), handy for these tests.
  Since 1.3, **Mod creatures** spawns Harkon's combat form, Karstaag, a werebear or 14
  different MihailMods creatures at once: a quick way to see new skeletons and a memory peak
  without playing hours to reach them. **Heal** is in the Player menu.
- **A quest that got stuck** (Switch has no console for `setstage`): Test Tools 1.2 has
  **Quests**. It goes through the quests marked as active in the Journal: **Next stage**
  sets the first later stage not done yet, **Restart quest** stops, resets and starts it
  again (after a confirmation). Save first: skipping stages can leave things undone, and
  restarting a long quest can break it. The quest list is written into `NXTest.esp` when
  the project is packed, so a quest from a mod added later shows up after the next Pack.
  **Player** has +1 perk point, +1000 gold, god mode and **No collision** to walk out of
  a stuck spot (use it again to switch it back).
- Survival Mode: "level up available" but no Health/Magicka/Stamina choice in the Skills
  menu is normal there: the level up comes after sleeping in a bed.

## SkyNX Mods (homebrew on the console)

A homebrew `.nro` in the app's style to switch mods on and off on the Switch itself.
- Built on the PC with devkitPro (`construir_nro.bat` in `extras\nxmods`); the `.nro` goes
  in the SD's `switch` folder and opens from the homebrew menu (Album or over a game).
- It shows what each mod is, its size, masters and who uses it. Descriptions come from the
  Mods page (**Describe it**), Nexus summaries, or the plugin.
- Plugins with BSAs listed in the ini: their BSAs leave the ini when every plugin of the mod is off.
- Back on the PC, **Preview changes** shows choices made on the console and offers
  **Use the console's choices**. Copying without it puts the PC's list back.
- Close Skyrim before saving (it warns if Skyrim is suspended in the background).

## Common situations

| They see | Meaning | Next step |
| --- | --- | --- |
| A card says *PC + Switch* | Some files were never converted (voices are typical) | Convert; it keeps what's already Switch |
| "Not removing it: X uses it as a master" | Another plugin needs it, even if that one is off | Switch both off in Load order, or remove the dependent first |
| "The .ccc would reach … bytes" | It doesn't fit | Shorter names, or switch something off |
| The game closes on start | Usually a missing master or a plugin over the list limit | Doctor; Copy report |
| The game closes in a city | Usually RAM | Status Monitor photo at that spot; lighten textures or drop a heavy mod |
| Purple or black textures | A PC texture that wasn't converted | Convert the mod or use the Diet |
| A quest doesn't start | Missing `.seq` | Doctor offers to create it |
| Empty message boxes (standing stones, tutorial tips, hunger and low-stat notices), NPCs that stand there without talking or show only other mods' options, race descriptions missing | Too many mod plugins: texts read from a plugin when they show fail. Tell-tale sign: the script behind it ran (a standing stone still gave its power, the Yes/No box never showed) | Doctor: **mod plugins**. Bring them under 80 (see Limits), then test the same spot on a fresh start of the game |
| A conversation ends when you skip a line fast, followers take long to start, scenes stall (NPCs stand still a minute before moving on) | The script engine (Papyrus) falling behind, mostly right after a new game or a load, when every mod's start-up scripts run at once. Earlier this row also blamed it for empty boxes and missing dialogue options; in Nov 2026 those turned out to be the plugin count (row above): Papyrus was fast enough there | Give Papyrus room in Skyrim.ini: `fUpdateBudgetMS` and `fExtraTaskletBudgetMS` at 4.0, `iMaxAllocatedMemoryBytes=307200` (the console ini many packs share has `fExtraTaskleBudgetMS`, misspelled, so it never applied), `fPostLoadUpdateTimeMS=6000` so more of the load runs behind the loading screen. After a new game, stand still a minute or two before talking to anyone. The CPU overclock in sys-clk helps frame rate but isn't needed for texts |
| Something odd after loading several saves in one session (a modded NPC with no dialogue, a loading screen that stays on top of the world) | Loading a save on top of another session carries part of the old script state; long sessions near the memory limit add to it | Close the game completely and start it again before loading. Lucien and Remiel had no dialogue in one session and talked at once after a restart (Nov 2026). If it still happens after a fresh start, it's the pack |
| One mod's message box is always empty (Yes/No with no text) while other mods' boxes work | Not known for sure. NX Quick Save's came back after its two messages got a title (FULL) in SSEEdit, but many mods' boxes have no title and work; among those, NX Quick Save was the only ESL-flagged plugin | Back up the plugin, give the message a title in SSEEdit (any text; it isn't shown), put it in the mod's folder under `Mods`, Copy to SD and test |
| A red "!" where an item's model should be, or a crash on one object | The model inside the BSA is blank: right size, all zeros (21 Apothecary meshes in a joined archive) | Doctor's deep check: **files are blank**. Take those files from the mod's original download, put the fixed BSA or loose files in the mod's folder under `Mods`, Pack again |
| Crash when opening the map, crash report in thread `LibAudioUpdate` at `nn::fs::CloseFile` | A sound that failed to open (same cause as above) is closed later | Same as above |
| A journal entry or name reads `<Error: No strings file for lstring ID ...>` | A patch saved in an editor without the game's texts copied the error message | Doctor » **Use the game's texts** (needs the game's files list) |
| Everyone in T-pose after switching an animation mod off | The generated behaviors still call that mod's behavior file | Mark the mod **Doesn't go** and **Generate behaviors** again; the Doctor flags it as *the behaviors call files that don't load* |
| Nemesis: ERROR(1210) `jumpbehavior.hkx` | Nemesis' download has a template for `attackbehavior.hkx` (a combat-mod file) that needs a `jumpbehavior.hkx` no mod of the pack brings; FNIS animations (Flower Girls) plus XPMSE's alternate sets make Nemesis build it | Since 0.9.23 the app leaves that template out when preparing; on an older work folder move `Nemesis_AttackBehavior.xml` out of `Data\meshes\actors\character\behaviors` and generate again |
| Nemesis: ERROR(6006) "Missing latest engine files" | The work folder is new and has no cache | **Update Engine** first, then **Launch** (every time the app prepares the folder) |
| A mod follower or quest giver doesn't talk in a new game (but did in an older save) | Its start-up quests haven't finished starting (see Limits) | Play a while and come back; a save made earlier already had them running |
| A follower says yes but stays behind / the old follower leaves | The game allows one follower of its own system; followers with their own framework (Lucien, Remiel) come on top. Amazing Follower Tweaks breaks custom-framework followers | Normal; a multiple-followers mod is a choice, not a fix |
| A mod NPC with a black or purple face | The mod ships no FaceGen for it (the face is built at run time) | The Creation Kit can export it (Ctrl+F4 on the NPC) on PC; otherwise it stays |
| A script looks for a plugin by its PC name and never finds it | Short console-style names (`SexLabAA.esp` for `SexLab-AmorousAdventures.esp`) break `GetFormFromFile` checks between mods | The Doctor lists scripts asking for plugins that aren't loaded: a [gone] name that is really a renamed plugin is worth fixing (the script's string must name the plugin as it is now). Since 1.0 a rename also changes script properties that hold the whole name, warns about texts that hold it inside a longer one, and the deep check lists scripts that still name a renamed or merged plugin (`script-gone-name`) |
| Bright cyan rectangles on the sea, glowing rings around a water wheel | Water textures (`textures\water\`, Realistic Water Two) converted with the full mip chain; the Switch wants at most 4 mips there | Since 0.9.23 Convert caps them; on an older conversion take the water textures from a port that works (4 mips) and rebuild the BSA |
| Crash while loading a new land (crossing into Bruma), crash report in thread `BSTaskManager` at `__memcpy_device` with `X[00] = 0`; before it, a freeze with 0% CPU | Out of memory: the loader got no buffer. A whole worldspace needs 300 to 400 MB free on top of what the pack holds; Bruma on top of a full pack sat at 2.77 GB at the border and never made it across | Not a missing file. Drop the new land or make room (lighter textures, Lite versions of mods that add gear to every NPC); test at the same spot with Status Monitor |

**Fixing a file by hand in a project**: edit it in the mod's folder under `Mods` (or `Base`), never
in `Switch`. **Copy to SD** packs `Switch` again from the project and the fix is lost; the next
Doctor check brings the `Mods` change in as an undoable step. Keep the old file in a backup first.

Always end a fix by asking them to run **Check again** and, if they're testing, to note the
RAM in the same test spot.

## Making room (what worked)

- **Join BSAs** of mods that stay together (a family: Enai's mods, world visuals, enemies) into one
  pair of archives. A joined archive loads at one place in the order, so a file can change
  winner: run **Check file conflicts** before and after and compare. Keep mods you may remove
  later in their own group.
- **Merge small patches** with zEdit's zMerge (Clean - Merge down, game load order, archives
  extracted). Verify every record made it before replacing the plugins. Saves of the old plugins
  won't load the new one: start a new game.
- **What a merge changes besides the plugin** (learned merging Flower Girls' 11 plugins):
  - zMerge gives new FormIDs to records that clash (`map.json` in the merge folder). Voices
    and FaceGen are named by FormID, FaceGen meshes name their tint, and scripts call
    `Game.GetFormFromFile(id, "Plugin.esp")`. **Join mods** in the Workshop applies that map
    since 0.9.23 (file names, tint paths, script names and ids); a hand merge needs the same.
  - A script that looks a merged plugin up by name breaks silently: search the BSAs' scripts
    for the members' names (the Doctor's *Scripts ask for plugins…* shows them as [gone]).
  - The merged plugin loads where its **last** member was. Records of an `.esm` member, or of an
    early plugin, now beat everything in between: compare who wins each record before and after.
    Where the merge now reverts earlier fixes (water, ownership, locations of cells), carry them
    over; where a patch used to lose to what it patched (a Flower Girls patch for Caught Red
    Handed lost to Quest Expansions), keep the old winner.
  - Its SEQ must list every Start Game Enabled quest of the merged plugin (zMerge's may not),
    inside a BSA.
- **zMerge and the first plugin** (zEdit 0.6.x, learned merging 16 MihailMods plugins and 33 patches):
  - With **Clean**, zMerge doesn't rewrite the references that point at the **first** plugin of the
    merge (the one it doesn't renumber), and stops with *Failed to remove master <first plugin>*.
  - **Clobber** builds "successfully" but leaves references with the session's load-order indexes:
    a merge of 33 patches lost 84 (48 placed objects, 18 enable parents, 15 recipe entries).
  - What works: put a **decoy** first (an esp with one record nobody uses, an old file date) and use
    Clean; the leftover master of the decoy can be renamed to a master that always loads and no
    record uses. Then check that every reference resolves and every member's record is there.
  - Plugins with **navmeshes of their own** don't merge safely: their navmesh data points at their
    own cells, doors and navmeshes, which zMerge renumbers. Keep them as plugins.
  - zEdit writes its `merges.json` back when it closes, from memory: edit that file only with zEdit
    closed, and keep a copy.
- **A patch between a big mod and the rest** (MihailMods against Revamped, Cosmetic Vampire
  Overhaul, Mortal Enemies, Growl and Triumvirate): load the big mod early so lighting, the
  Unofficial Patch and city mods keep their cells, then carry over only what it adds that matters
  (new scripts on NPCs, new skeletons on races, the union of merchant chests) on top of the
  record that wins, inside a merged patch so it costs no file.
- **Updating a mod that lives in a joined suite** (Cloaks and Capes 1.4 to 1.7 inside SuiteXM/SuiteXT):
  its old files stay in the suite, and the suite loads from the ini, so it beats the new version's own
  BSA. Replace the mod's files inside the suite (same folder paths) and swap the plugin in its `Mods`
  folder; the suite keeps its place and the open-files count doesn't change. Check whether the new
  plugin drops a master (1.7 dropped USSEP and lost its fixes on 3 outfits) and carry those over.
- **Joining BSAs from both ini lists**: one archive lives in one list. Scripts and meshes go in
  `sResourceArchiveList`; voices or textures that replace the game's need `sResourceArchiveList2`
  (Serana Dialogue Add-On's 806 Serana voices). Check what changes winner before choosing.
- **Scripts that run on their own** (the Doctor's *Mods that keep scripts running*): repeating
  timers cost the Switch's CPU, not the number of scripts. A follower with 1,177 scripts and one
  timer weighs less than a faith overhaul with 88 timers.
- **The PC script extender's copies of the game's scripts** inside a mod's BSA (Auri brought 39)
  must keep losing to the game's: the Doctor no longer promotes such a BSA in the ini.
- **Doesn't go** for mods you don't use, instead of only `#`: their files leave the SD too.
  A mod whose files sit in a joined archive keeps that archive while another mod of it goes.
- Plugins that need SKSE only for their menu often work; ones whose core scripts call SKSE
  or ship `.dll` plugins don't. A `_DISTR.ini` (Spell Perk Item Distributor) doesn't run on
  Switch: check whether the player still gets what it hands out.

## Honest boundaries

- Switch 1 only today (AE and SE). The console needs custom firmware that loads mods from
  the SD (Atmosphère's LayeredFS).
- The app doesn't write scripts or edit records by hand: records are edited in SSEEdit
  (the app opens it on the project or a copy), scripts need the Creation Kit, and merges
  need zEdit.
- Respect mod authors: share **Pack recipe** exports (links to Nexus), not other people's
  files, unless the mod's permissions allow it.
- Never ask for or pass around game files, keys, or Nintendo SDK tools.
