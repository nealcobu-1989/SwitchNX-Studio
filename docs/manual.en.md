## Getting started {#start}

SwitchNX Studio builds, checks, fixes and converts Skyrim modpacks for the Nintendo Switch, for both Anniversary Edition (AE) and Special Edition (SE). Nothing it does is final: every change goes to the History and can be undone.

The home screen has three parts:

| Part | What it's for |
| --- | --- |
| **Projects** | Each modpack you build or maintain, in a folder of its own: its mods, its history, and what goes to the Switch. Start one from scratch, from a modpack someone shared, or from your SD. |
| **Workshop** | Quick jobs on single mods, without a project: convert a PC mod, convert several, edit a Switch mod, join mods into one BSA, join plugins. The result goes to the Mod Library. |
| **Mod Library** | The mods you keep at hand (converted, downloaded or added) and the Catalog, with every mod of every project. |

**Always at hand.** The top bar has **Library**, **Help** (this manual; it opens at the part about the page you're on) and **EN / ES** for the language. Inside a project it also has **Pack** and **Projects** (back to the list). You can drop mods or modpacks on the window at any moment: they go to [Add mods](#h-add).

**Where you are.** Three woods tell the spaces apart: oak for projects, cherry and copper for the workshop, walnut for the Mod Library.

> New here? Check [Your setup](#h-setup) first: it tells you what's missing on this PC and what stays off without it.

## Your setup {#setup}

The first time the app opens it shows the credits, what it does, and then **Your setup**: every tool and folder it can use, whether it found it, and what you can't do without it. Each line has a button to choose its folder or .exe. You can come back any time from **Settings » See all your gear**, and the home screen shows a short version at the bottom.

Opening, checking and fixing projects works with nothing installed. The rest depends on these:

| Item | What it's for | Without it |
| --- | --- | --- |
| texconv | Converts PC textures | PC mods with textures can't be converted, and the texture diet can't run on a project. |
| ffmpeg | Reads PC sounds | PC mods with sounds or voices can't be converted. |
| VGAudioCli + VGAudio.dll (Skyrim NX Toolkit build) | Writes Switch sounds | Same as ffmpeg: sounds can't be converted. Another VGAudio build doesn't work. |
| NvnTexpkg and its DLLs | The Switch's native texture format | Converted textures stay DDS (the PC format the Switch also reads). |
| HavokBehaviorPostProcess.exe (Creation Kit, Steam) | Writes behaviors, skeletons and Oldrim (32-bit) animations in the Switch's layout | Those files from PC mods are packed as they are and may not work on Switch. |
| hkxc.exe (serde-hkx, Nexus SE mod 126214) | Reads 64-bit PC behaviors and skeletons so HavokBehaviorPostProcess can convert them | 64-bit PC behaviors and skeletons stay as they are. It can sit in its own subfolder (`Tools\serde-hkx`). |
| Nemesis (Nexus SE mod 60033), unpacked in `Tools\Nemesis` | Generates the behaviors for mods with new animations (FNIS lists, Nemesis patches) | Those animations don't play in game. Needs HavokBehaviorPostProcess and hkxc too. |
| 7-Zip | Opens `.rar` downloads | Only rars that Windows' `tar.exe` can read will open; extract the rest by hand. |
| Console inis | Clean `Skyrim.ini`, `Skyrim_en.ini`, `Skyrim_aoc.ccc` | You can't start a project from scratch (from a modpack or the SD still works). |
| Game BSAs and .esm | The base game's files | The Doctor can't tell whether scripts, meshes and textures are missing, and SSEEdit can't open a project. |
| USSEP (KokaNX) | The unofficial patch for new projects | New projects start without it. |
| SSEEdit, zEdit, NifSkope, BAE, Cathedral Assets Optimizer | External tools the app opens for you | Their buttons stay off. zEdit is needed for **Join plugins**. |
| LOOT masterlist | Load order rules and mod names | No **Suggest order (LOOT)**; fewer mods get their Nexus page. It downloads itself the first time. |
| Nexus API key | Names, versions and updates from Nexus | No Nexus names or update checks, and no Mod Manager Download button. |

The usual place for the tools is `C:\SkyNX\Tools`; see [Folders on disk](#h-folders) for the rest.

## Projects {#projects}

A project is a modpack you build or maintain, kept in a folder of its own inside the Library (`Library\Projects\<name>`). Modpacks aren't stored in the Library anymore: a modpack someone shares becomes a project, or a source you bring mods from.

| In the project folder | What it holds |
| --- | --- |
| `Mods\<mod>\` | Each mod's files, laid out as inside Data, and a `mod.json` with its name, version, where it came from, how it was converted, and whether it goes. |
| `Base\` | The inis, the load list (`Skyrim_aoc.ccc` or `Plugins`), and Data files no mod owns. |
| `Switch\` | Made by **Pack**: the two folders that go to the console (`01000A10041EA000` and `01000A10041EB009`). |
| `skynx-project.json` | What the project is: name, where it started, last pack, last SD copy. |
| `.skynx\` | History, trash and records, and the working copy the tools use. |

**Start one.** Home » **New project**, give it a name, and choose where it starts:

- **Scratch**: the console's clean inis, the edition, Creation Club and USSEP. You add the mods.
- **A modpack**: a folder, a `.zip`/`.7z`/`.rar` someone shared (split Google Drive downloads are joined), or another project. It's copied into the project; the original isn't touched.
- **The SD**: what's on your SD now. The SD is only read.

Dropping a modpack on the window offers **New project with it** too.

**Open one.** Click its card on the home screen. Each card shows the edition, how many mods it has and how many don't go, what the Doctor found, and when it was last packed and copied to the SD. **Delete** moves the project to the Library's trash (`.trash\Projects`), where you can get it back.

**Modpacks from before.** Packs and packs being created that were in the Library before projects are listed on the home screen with **Turn into a project**. The project starts as an exact copy (a pack being created keeps which mods don't go). The originals stay where they are: delete them yourself when you no longer need them.

> Nothing outside the project is ever written: a project copies its source, so whatever you do in it can't reach the original. To save space you can turn on **Link files with their origin** in Settings: on the same drive the project then shares the files with the original. The app never writes into a shared file, but another program that saves a file in place would change the original too.

## Working in a project {#pack}

With a project open, the menu on the left has:

| Page | What it's for |
| --- | --- |
| Summary | Edition, active plugins, Data size, heaviest textures and how many problems of each kind. |
| Doctor | Every problem found, with its explanation and its fix. |
| Add mods | The queue: drop zips, 7z, rar or folders and the app says what each one is. |
| Mods | The project's mods: what goes, each mod's folder, Nexus page, rename, extract, remove, recipe, Switch versions and file conflicts. |
| Load order | The list with arrows, LOOT and SSEEdit. |
| Textures & audio | Texture weight per BSA, formats and the Diet. |
| History | Every change, with **Undo**. |
| Copy to SD | Packs the project and copies only what changed to the SD. |
| Convert mods | One PC mod or several at once into this project. |
| Library | The Mod Library and the Catalog. |
| Settings | Language, folders, Nexus, external tools and credits. |

**The bottom bar** is always in view: on the left the bytes of the `.ccc` load list (limit 4096), in the middle the serious problems, on the right the longest ini archive list (limit 1024 characters).

**History and undo.** Every change keeps a copy of what was there before in the project's `.skynx` folder. **Undo** puts those files back. If something goes wrong halfway through a change, the project returns to how it was.

**Editing by hand.** `Mods\` and `Base\` always show the project as it is. If you change or add a file there with another program (an ini, a texture, a plugin dropped into a mod's folder), it comes into the project the next time the app checks it, as one change in the History ("Changes made in the project folder"). A file you delete there by hand comes back: to take a mod out, untick it or remove it in Mods. If the same file changed both by hand and in the app, or two files you added would land in the same place, the app's version stays and yours are kept in `.skynx\mirror-conflicts`. Readmes and pictures you leave next to a mod stay there and don't go to the game.

The files in `Mods\` are the project's own (linked, not copied, to save space). A program that saves a file in place there changes the project directly: the app notices and tells you, but that change can't be undone from the History. The inis and the load list in `Base\` are real copies, so editing them is always undoable.

## Mods in a project {#mods}

Each mod of the project has a row and a folder in `Mods\`. On each row:

- The box: untick it and the mod **doesn't go**. Its plugins leave the load list and its BSAs leave the inis (the numbers above update), but its files stay in the project, and ticking it again puts it back where it was. If another mod uses it as a master, the app offers to leave them out together.
- **Folder** opens the mod's folder in `Mods\`.
- **Rename** shows how many `.ccc` bytes you gain or lose and changes plugin, BSA, voices, FaceGen, masters and list at once. The mod keeps its folder.
- **Extract** copies its BSAs' files to a folder you choose.
- **Remove** takes it out of the list and the inis and moves its files to the project's trash (undoable). If other plugins use it as a master, it names them and offers to remove them in the same step; a plugin that shares its mod with others (patches from one FOMOD) leaves that mod alone and the rest stays.
- The Nexus tag, when the mod is recognised (see [Nexus and LOOT](#h-nexus)).

At the top: **Pack**, the **Mods folder**, and the ways to add:

- **Add mods**: the queue, for downloads and Switch mods ([Add mods](#h-add)).
- **From a modpack…**: pick a modpack's folder, its `.zip`/`.7z`/`.rar`, or another of your projects; tick the mods you want and the app brings them with the masters they need, leaving behind what the project already has. An archive is extracted once while the project is open; the source is only read. The list sorts by name, as in the pack or by size.
- **Bring from the Catalog**: mods from any project or the Mod Library ([Mod Library and Catalog](#h-library)).

Also at the top: **Check file conflicts** (every file more than one BSA carries, and which one wins by load order), **Pack recipe** (where each mod came from, its FOMOD and conversion options, and what changed; **Export to share (.md)** writes it with Nexus links and without paths from your PC) and the Nexus bar.

### Behaviors (FNIS / Nemesis)

Mods with new animations (Flower Girls, pose mods, combat mods) don't bring the game's behavior files: they bring a list (`FNIS_<mod>_List.txt`) or a Nemesis patch, and a generator writes `0_master.hkx`, `defaultmale.hkx` and the rest for the whole pack. Without that step those animations don't play.

When a PC mod is converted, the app keeps what generation needs (lists, animations, Nemesis patch, as the PC originals). When the project has such mods, the Mods page shows the **Behaviors** box with their state: not generated, out of date (those mods changed) or up to date.

**Generate behaviors**:

1. The app makes a work folder with a copy of Nemesis and of those files (your Skyrim isn't touched) and opens Nemesis.
2. In Nemesis: **Update Engine**, tick the patches the app names, **Launch Nemesis Behavior Engine**, and close it when it says *Behavior generation complete*.
3. In the app: **Done**. The files Nemesis wrote are made Switch files and go into the project as one more mod, "SkyNX - Generated behaviors", in a BSA of the ini list with more room. Generating again replaces that mod.

It needs Nemesis, HavokBehaviorPostProcess and hkxc in the tools folder ([Your setup](#h-setup)). When packing, the app warns if they're not generated or out of date. Mods that need SKSE (SexLab, for example) don't work on Switch even with their behaviors generated.

## Add mods {#add}

Drop files or folders on the window, or use **Add to the list**. Each one gets a card that says what it is and what to do:

| The app says | What to do |
| --- | --- |
| Switch mod | **Check it** and **Add as it is**. It goes straight into the project. |
| PC mod | **Convert**: it moves to Convert mods. |
| Mixed | Has Switch and PC parts: convert it. |
| FOMOD | Has an installer: Convert mods opens the assistant. |
| Modpack | **New project with it**, or **Bring mods from it** into the open project. |

Each card also shows the Nexus tag when the mod is recognised. With two or more PC mods in the queue, **Convert all PC mods** sends them together to Convert several mods. A Switch mod's card has **Compare with the original**: point it at the PC version and the app compares records and files.

When reading an archive, the app leaves out Mac junk (`__MACOSX`, `._Mod.esp`). If the mod ships versions side by side (for example `Mod_AE` and `Mod_SE`), it uses the one for the project's edition and says so in a note. `.rar` files open with 7-Zip or Windows' `tar.exe`; if neither can, the card says so and you can extract it and drop the folder.

**Fonts** (Sovngarde and the like): a font mod's `Interface\FontConfig.txt` stays loose in `Data\Interface`, since fonts only load that way; its libraries (`fonts_*.swf`) go into the BSA as usual. Only one font can be active: the last one you add replaces the previous one, and undoing that step brings it back. The Doctor warns when a `FontConfig.txt` ended up inside a BSA (and puts it loose) or when it asks for a library the pack doesn't have.

**Renamed masters.** If a mod uses as a master a plugin that has another name in this project (you shortened it when converting or with Rename), adding it points it at the new name, as converting does. If one already went in pointing at the old name, the Doctor reports the missing master and offers **Point it at …**, which is safe.

**Plugin names.** In Convert mods the name is typed without its extension, as in Rename: the extension sits next to it and stays on its own.

## The Doctor {#doctor}

Each problem has a severity: **Serious** (something won't load or the game may close), **Check** (it probably fails or looks wrong), **Savings** (memory can be gained) and **Info**. The filters at the top show one kind at a time.

Every fix button first shows exactly what will change. **Fix the safe ones** applies at once the fixes marked safe; the rest go one by one after their preview. **Check again** reads the project again. Mods that don't go are left out of the Doctor on purpose.

Common fixes: rename files Google Drive damaged (`Ryn_s` back to `Ryn's`), activate plugins that are in Data but not in the list, take missing BSAs out of the ini, create the SEQ file of a plugin with start-up quests, extract mods left compressed inside Data, turn an `.esl` into an `.esp` on SE, and move leftover copies to the trash. No fix leaves the `.ccc` over 4096 bytes: if it doesn't fit, the app says so and changes nothing.

With the game's BSAs set up, the Doctor also checks whether the scripts, meshes and textures each plugin needs are really there. A BSA the ini names but that doesn't exist is judged by its files: if nothing is missing (a converter joined several BSAs into one), it becomes Info and removing it from the ini is safe.

**The game list.** For that the app builds a list of everything the game has: every file inside its BSAs, plus what the game's own plugins ask for (`Skyrim.esm`, the DLC and the Creation Club) and the textures their meshes name. It's built once from the game files folder and saved: afterwards you can delete the BSAs from that folder and the list stays the same. Copy a BSA back (a game update) and it's read again. Keep the `.esm` and `.esl` files, xEdit needs them. Settings shows how many files it has, whether one of the game's basic BSAs is missing from it and which ones are no longer in the folder.

**What isn't missing.** Some things the Doctor no longer reports as missing, or shows as Info:
- **What the game itself asks for.** The game's race records name `upperbodyhumanmale.egt`, which no BSA has; a mod that copies that race (Mortal Enemies, USSEP) has no problem.
- **Script fragments** (`QF_`, `PRKF_`, `SF_`, `TIF_`…): the small scripts of a quest stage, a perk, a scene or a line of dialogue. When they're missing the author didn't include them, and it's the same on PC.
- **Detail maps** (`_p` relief, `_m`/`_em`/`_s` shine, `_g` glow, `_sk` skin): without them the surface looks flat or dull, never purple.
- **Paths the author typed wrong**: a space before the extension or next to a folder, no extension, or a texture where a model goes. No mod can provide such a file.

**Scripts and sounds that run on the console.** In the full check the Doctor also looks at what actually runs (for each script, the copy that wins on Switch):
- **SKSE's base scripts inside a mod** (Serious): the PC copy of `Quest`, `Actor`, `Game` and the other base scripts, slipped in when a mod was packed. On Switch it replaces the game's own. The fix takes them out of the BSA and leaves the rest of the mod.
- **Scripts USSEP fixes that another mod replaces** (Check): the other mod's copy is the one that runs, and if it wasn't built on USSEP its fixes are lost. If a base-game quest stalls, look here first.
- **Game scripts the mods replace** (Info): many mods work this way; the list says which, so you have suspects.
- **Scripts that ask for plugins that aren't loaded** (Info): `[off]` is in the pack but switched off, `[gone]` isn't in it. Usually an optional check; it matters after removing a mod.
- **Mods that keep scripts running on their own** (Info): how many scripts run, how many repeat on a timer and how many react to frequent events. A guide for lists with many scripts.
- **Damaged sounds** (Check): voices and music are read in full and the ones cut short or that don't add up are listed. What was read is kept per BSA, so the next check only reads what changed.

**Empty plugin with its BSA.** Moving the BSA to the ini frees `.ccc` bytes, but the ini loads first. Before offering it, the Doctor checks file by file who would win afterwards. If any file changes winner (Noble Skyrim's textures win over the mods that load before its plugin; in the ini they would lose), it says to leave it, lists each file and offers no fix. If nothing changes, the fix is safe.

**Long plugin names.** When the `.ccc` goes past about 3,500 bytes, the Doctor offers to **Shorten the names** of the active plugins with long names, all in one step you can undo: the name before the dash, Enai style (`Wintersun - Faiths of Skyrim.esp` → `Wintersun.esp`), or the first word and initials (`AmazingFollowerTweaks.esp` → `AmazingFT.esp`). Never a name a plugin or BSA already has, nor USSEP's and USCCCP's. Everything that uses each name follows it. Saves remember the names: do it before the real playthrough.

**Names in another language.** Some ports come from a translated upload: in The Ordinary Women, 61 women had their names in Russian (Gerdur showed as "Гердур"). When the game is in a language with the Latin alphabet, the Doctor reports names in another alphabet and offers **Use the game's names**, which puts back the original name (read from the `.esm` and the game's texts in `Skyrim - Interface.bsa`, which is why that BSA should stay in the folder). Only the names change. The mod's own new records have no game name to go back to; those are only listed.

**Copy report** and **Save as .md** give every finding with all its details (no "+N") as Markdown, to paste in a chat or keep.

## Load order {#order}

The list of plugins with arrows (or drag them). Masters must sit above whoever uses them; red rows say what's wrong. **Save order** writes it (undoable).

- **Suggest order (LOOT)** sorts by masters, LOOT rules and groups, keeping your order where nothing says otherwise. Creation Club and game files don't move. Plugins LOOT doesn't know can get a category; your choice is remembered for every project.
- **Open in SSEEdit** asks whether to work on the project or on a copy. On a copy, when SSEEdit closes the app asks what to do: bring the changes (they go to the History), keep the copy for later, or delete it. **Bring SSEEdit changes** does it by hand.
- **Show the Creation Club** shows the CC entries of the list.

**Copy order** copies the list as it is on screen (unsaved moves and each plugin's masters included), to paste in a chat or a note.

Creation Club entries show their name (Fishing, Survival Mode…) next to the file. When the game list has the Creation Club, the Doctor flags CC lines the game doesn't have (neither plugin nor BSA; the Switch's own list has five like that) and offers to take them out: they free .ccc bytes and change nothing in the game.

The box on each plugin **switches it on or off** without taking it out of the project (it stays in the list with a `#`). Pack leaves switched-off lines out, and also that mod's BSAs listed in the inis (`sResourceArchiveList`...), since those load even without the plugin: a BSA leaves the ini when every plugin of its mod is off.

## Textures & audio {#textures}

The weight of the active textures per BSA, the formats in use (NVN is the Switch's own; DDS is PC) and how many mods still have PC textures or sounds. The **With diet** column shows what each BSA would take with the Switch 1 diet. **Diet** (on every BSA with textures) asks for the size rule and maximum size, shows the estimate, and applies it (undoable). The total adds up every texture; the game only loads what's near you, so use it to compare mods and projects.

If the textures haven't been read yet, **Check again** reads them.

## Pack and copy to the SD {#sd}

**Pack** (the gold button at the top, on the Summary or on the Mods page). First the app says if something of the routine is left: plugins LOOT would still move, serious Doctor problems or routine fixes (SEQ, BSAs losing scripts, a full ini list). You can go fix them or pack anyway. Pack makes the project's `Switch\` folder: the two folders for the console, with every mod that goes and without the ones that don't, the history or the app's records. It checks first that every plugin that goes has its masters. `Switch\` holds real copies, and each Pack only copies what changed since the last one. Anything in `Switch\` the app didn't put there, or that was changed by hand, is moved to the project's trash (`.skynx\trash`), never deleted. After packing you can copy it to the SD, open the folder, or close.

**Copy to SD.** Type the SD drive (for example `E:\`) or its `atmosphere\contents` folder and press **Preview changes**. A project is always packed first, so what goes to the SD is exactly what's in `Switch\`. The app only touches `01000A10041EA000` and `01000A10041EB009`: it copies what's new or changed, removes what the project no longer has, and first saves a backup of what it replaces in `.skynx\sd-backups`. It checks the free space before copying. **Full copy instead** copies everything again, for SDs edited by hand. If the SD doesn't have Skyrim's folders yet (a new SD, or one without `atmosphere\contents` yet), it's a **first copy**: everything goes in new, there's nothing to back up and the app creates the folders. So the wrong drive isn't used, it only does that when the folder looks like a Switch SD's root (it has `Nintendo`, `switch`, `bootloader` or `atmosphere`). Each file is written under another name, flushed to the card, and only then takes its real name; if the copy fails halfway, the SD goes back to how it was. Remove the SD with Windows' **Eject**. The SD needs a drive letter: put it in the PC's reader or use hekate, Tools, USB Tools, SD Card; MTP (DBI) gives no drive letter. A file that only changed name in the pack (shortened BSA names, for example) is renamed on the SD instead of copied again.

**SkyNX Mods on the console.** SkyNX Mods is this project's homebrew to switch mods on and off from the Switch (it's in `extras\nxmods`; `construir_nro.bat` builds it and `SkyNXMods.nro` goes in the SD's `switch` folder). Every copy to the SD leaves in `switch\SkyNXMods` the project's full list (switched-off ones included) and which ini BSAs belong to which plugin, so SkyNX Mods takes those BSAs out and puts them back too. If you switched something on or off on the console, **Preview changes** shows it at the top and offers **Use the console's choices**, which brings it into the project (it goes to the History). Copying without it puts the project's list back on the console.

It also leaves `skyrim-info.txt`: what each plugin is (name, description and BSAs), so SkyNX Mods shows it with its size on the SD. The description comes from what you write on the Mods page (**Describe it**), from the Nexus summary if you already fetched it, or from the plugin itself; the Creation Club ones come with the app.

It also measures what each mod weighs: the plugin's records (in memory all the time it's on) and, inside its BSAs, how much is textures, meshes and audio. SkyNX Mods 1.3 shows it as a light, medium or heavy load, with the records of what's on at the top. It's an estimate: textures and meshes only take memory while their things are on screen, and audio is read from the SD as it plays. The first copy after adding mods takes a little longer while it measures the new BSAs; then it's kept in the project.

SkyNX Mods 1.3 also reads the crash reports Atmosphère leaves in `atmosphere\crash_reports` (a report and a screenshot of every time the game closes on an error): **− More**, **Skyrim crashes**.

## The workshop {#workshop}

The workshop is for single mods, without a project: for when you only want to convert a mod and be done. Each job is a **bench**: a private workspace in `Library\Workshop\<name>` that never goes to the SD. When you're done, **Save** puts the result in `Library\Converted`, ready for any project and for the Catalog.

| Home » Workshop | What it does |
| --- | --- |
| Convert a PC mod | Asks the edition and opens Convert mods on an empty bench ([one mod](#h-one-mod)). |
| Convert several mods | The same, several at once, each saved on its own ([several mods](#h-many-mods)). |
| Edit a Switch mod | Brings a mod to the bench to rename, extract BSAs, open in SSEEdit and save. |
| Join mods into one BSA | Several mods under one plugin, their BSAs joined. |
| Join plugins (merge) | A merge with zEdit's zMerge, guided. |

On a bench the menu changes to: Bench, Convert mods, Join BSAs, Join plugins, History and All benches. **Saved benches** on the home screen reopens them. **Discard this bench** deletes it; what you already saved to the Library stays.

## Convert or edit one mod {#one-mod}

Convert mods » **One mod** (from the workshop, or inside a project, where the mod goes straight in).

1. Pick the mod's folder or archive (`.zip`, `.7z`, `.rar`) and press **Read the mod**. Nothing is written yet.
2. Choose the **Texture diet**: **Switch 1 diet** (the default: 1K, maps and clutter at 512), **Koka's rules** (1K in general, 2K for actors), **Extreme** (512, for packs with many mods) or **Original size** (no size rule). On top of any of them, **Maximum size** caps the largest side at 256, 512, 1K, 2K or 4K. For 2K textures everywhere, pick Original size and 2K. Textures are never enlarged.
3. Choose the format: **Native Switch format (NvnTexpkg)**, and **BC1** for opaque textures (half the memory). Without NvnTexpkg textures stay DDS forced to DXT5, as Koka does.
4. Choose the **Packing**. The default, **One BSA in the inis**, puts everything in one short-named BSA and lists it in whichever ini list has more room: Koka's stable way of loading, with one name per mod instead of two, so more mods fit in the ini. If neither list has room, the mod is packed in one BSA named after the plugin and the app tells you. The other choices: BSAs named after the plugin, one BSA named after the plugin, or two BSAs listed in the inis (meshes and textures apart, as Koka does).
5. Check the plugin names. The app proposes names Google Drive won't damage, and **Short** saves `.ccc` bytes.
6. Press **Convert and add to the pack**. The top of the page shows the `.ccc` and the texture memory with the mod included.

The result goes into the project (or the bench) and a copy into `Library\Converted`. What a Switch mod can't use (readmes, sources, SKSE `.dll` plugins) is left out and listed.

**Half-ported voices.** Some ports carry leftovers the game never reads: voices stored under earlier plugin names, old takes (`-old1`), the Creation Kit's lip-sync folder and `.temp.wav` copies. They're left out and listed. When a line was left as an empty `.fuz` with its `.temp.wav` next to it (The Tempest Isle NX), the app converts it from that `.wav`.

**FOMOD installers.** A mod with an installer opens the FOMOD assistant first: its steps, options, pictures and descriptions, like a mod manager. Patches for mods that aren't in your project are hidden. **Install these options and continue** goes on to the conversion options.

**Edit a Switch mod.** Workshop » **Edit a Switch mod**. On the bench you can rename its plugins (voices, FaceGen, BSAs and masters follow the name), extract its BSAs, open it in SSEEdit, and **Save** it to `Library\Converted`.

## Several mods at once {#many-mods}

**Convert several mods**: Workshop » Convert several mods, the **Several at once** tab in Convert mods, or **Convert all PC mods** in Add mods. Each mod gets a narrow card with its diet, size cap, packing, native format and plugin names; **More options** shows the rest. **For all** sets the same on every card. FOMODs are chosen inside the batch with **Choose options**. The top shows the `.ccc` and texture memory with everything added up. Before starting, the app checks that no name repeats and that the `.ccc` fits; it converts first the mods others need and points them to the final names. If one fails, the rest go on, the mods that needed it stop with the reason, and the failed one stays with **Read it again**.

**Join mods into one BSA.** Pick the mods in the order they should load. Their BSAs become one, or a few when they pass 1.9 GB, named after one plugin so they load with it. The plugins stay separate, so the `.ccc` doesn't change, but the ini lists and the number of archives go down.

**Join plugins (merge).** The merge itself is done by zMerge (inside zEdit); the app prepares and tidies:

1. Add the plugins to merge to the bench.
2. **Prepare and open zEdit**. The first time, make a Skyrim SE profile in zEdit with the folder the app shows as the game path.
3. In zMerge, make a merge with the bench's plugins and build it.
4. **Bring** the folder zMerge made. The merged plugins leave the bench.
5. Join the BSAs under the merge, then save the suite to the Library.

## Mod Library and Catalog {#library}

The Mod Library (top bar » **Library**) has two tabs.

**Mods.** The mods you keep at hand: converted here (`Library\Converted`), downloaded with Nexus' button, or imported from a zip or folder. Each with the Doctor's quick opinion and its buttons: **Add to the current project**, **Edit in the workshop**, open folder and Delete. Modpacks aren't kept here: a modpack becomes a project (if you import one here, the app says so).

**Catalog.** Every mod of every project and of the Mod Library, once each, with its category and Nexus tag. When a mod is in several projects, you choose the version. Tick mods and choose: a **New project**, or **Add to** the open project (mods it already has are skipped and listed with the reason). Before creating, the side panel shows the `.ccc`, the ini and the textures.

## Nexus and LOOT {#nexus}

The app recognises mods even when they've been renamed and links their page on Nexus (Skyrim Special Edition, where Anniversary mods live too). From most to least certain:

1. What you confirmed (remembered by the plugin's content, so it follows the mod to other projects).
2. The download: what the Mod Manager Download button brought knows its mod and version.
3. LOOT's list, checked with the current name and the original names the app recorded.
4. A merge shows the mods inside it.

The tag appears in Mods, on benches, in Add mods and in the Catalog. The **?** next to it opens the mod's card: other possible pages, **It's this one**, **Search on Nexus**, or paste the link by hand.

**Versions for Switch** looks inside each file of the mod on Nexus. A version with SKSE plugins (`.dll`) doesn't work on Switch; one that names SKSE, Address Library, PapyrusUtil or SPID is marked **Check**. It shows yours, the latest and the best one for Switch. **I have this one** tells it which you have.

| Feature | Needs |
| --- | --- |
| Recognising by LOOT | LOOT's list (**Download LOOT's list to recognise more**). |
| Names, versions, updates, Versions for Switch | Your personal Nexus API key in Settings. It stays only on this PC. |
| Mod Manager Download button | Turned on in Settings (works with a free account). |
| Suggest order | LOOT's list; it downloads itself the first time. |

## Tools and Settings {#tools}

**Settings** has: language, **When the app opens, go back to the pack that was open** (on by default; it also works after installing a new version; closing the pack with Open another starts the next time on the welcome page), tools folder, console inis for new projects, game BSAs folder, USSEP folder, Library folder, **Link files with their origin** (off by default), your Nexus API key, the Mod Manager Download button, external tools, **See all your gear** and credits.

External tools (SSEEdit, zEdit, NifSkope, BAE, Cathedral Assets Optimizer) are found in `C:\SkyNX\Tools` or chosen by hand. The app opens them on the project or on a copy, as each page explains. See [Your setup](#h-setup) for what each one turns on.

## AE and SE {#ae-se}

A mod made for one edition almost always works on the other; the app makes the change on the way in (Add mods, Convert, batch, From a modpack and the Catalog), and leaves a note on the mod's card.

| Case | AE project | SE project |
| --- | --- | --- |
| SE mod | Goes in as it is. | Goes in as it is. |
| `.esp` with the ESL flag (most NX mods for AE) | As it is. | The flag is cleared; SE would ignore it. |
| HEDR 1.71 header | As it is. | Lowered to 1.70 when no record of its own uses low form IDs. If it does, it stays and the Doctor explains. |
| A real `.esl` | As it is. | Not directly: put it through Convert mods, or use the Doctor fix **Turn it into .esp for SE**. |
| Needs Creation Club content | Goes in and is activated. | Stays in Data but off the list: SE has no CC. |
| `_AE` and `_SE` folders in one mod | Uses the AE one. | Uses the SE one; with only an AE one, uses the one not marked AE. |

On SE the load list is the `Plugins` file and has no `.ccc` byte limit.

## Switch limits {#limits}

| Limit | Value | Where you see it |
| --- | --- | --- |
| Load list `Skyrim_aoc.ccc` (AE) | 4096 bytes; the game stops reading past that | Bottom bar, Mods, Convert, Catalog |
| Ini archive lists (`sResourceArchiveList`, `sResourceArchiveList2`) | 1024 characters each; the language ini (`Skyrim_en.ini`) wins over `Skyrim.ini`. Near the limit the Doctor offers to shorten the names of the mod BSAs the ini loads (they load in the same place, only the name changes) | Bottom bar, Doctor |
| BSA | 1.9 GB per file; joining BSAs splits into several | Join BSAs |
| BSA order | It depends on the kind of file. **Scripts:** a BSA in the ini wins over one loaded by its plugin's name, the other way round from PC. Seen on the console: KokaNX's `USSEP.bsa` (in the ini) took Growl's and Sacrosanct's scripts, and the game's `Skyrim - Misc.bsa` took Quick Start's; with their BSAs in the ini, after the others, they worked. **Textures and meshes:** as on PC; Noble Skyrim's textures, loaded by its plugin, show over the game's | Doctor (mods losing scripts), Check file conflicts |
| Record IDs below 0x800 (extended ESL range, Skyrim PC 1.6.1130, Dec 2023) | The Switch build is from 2022 and probably can't load them; HEDR 1.71 without those IDs does load | Add mods, Doctor |
| SKSE plugins (`.dll`) | Don't work on Switch | Convert (left out), Versions for Switch |
| Textures | Switch NVN format, or PC DDS forced to DXT5; limited memory | Textures & audio, Diet |
| Animations, behaviors, skeletons (`.hkx`) | Switch uses its own Havok layout. Animations convert with a byte change; behaviors, skeletons and Oldrim files need HavokBehaviorPostProcess (and hkxc for 64-bit ones) | Convert |
| Names with apostrophes or symbols | Google Drive turns them into `_` and the plugin stops loading | Doctor (safe name) |

## Folders on disk {#folders}

Everything lives in `C:\SkyNX`. The app doesn't write outside these folders.

| Folder | What it holds |
| --- | --- |
| `C:\SkyNX\SwitchNX Studio.exe` | The app. Rebuilt with `construir.bat` from `SkyNX Studio`. |
| `C:\SkyNX\SkyNX Studio` | Source code, `README.md`, `LEEME.md` and `construir.bat`. |
| `C:\SkyNX\Tools` | texconv, ffmpeg, VGAudioCli, NvnTexpkg and its DLLs; SSEEdit, zEdit, NifSkope, BAE and CAO in subfolders. |
| `C:\SkyNX\Vanilla\INIs` | The console's clean inis for new projects. |
| `C:\SkyNX\Vanilla\BSAs` | The game's files from `romfs\Data`: its BSAs (`Skyrim - *.bsa`, `cc*.bsa`) and its plugins (`.esm`, `.esl`). Once the game list is built the BSAs can be deleted except `Skyrim - Interface.bsa`, which holds the game's texts; the plugins stay for xEdit. |
| `C:\SkyNX\Base Mods\USSEP` | KokaNX's USSEP (All_CC, No_CC, SurvivalMode). |
| `C:\SkyNX\Library\Projects` | Your projects, one folder each. |
| `C:\SkyNX\Library\Mods` | Loose mods as they arrived. |
| `C:\SkyNX\Library\Converted` | Every mod the app converts or saves from a bench. |
| `C:\SkyNX\Library\Workshop` | Workshop benches. |
| `C:\SkyNX\Library\Downloads` | What Nexus' Mod Manager Download button brings. |
| `C:\SkyNX\Library\.trash` | Deleted projects, until you empty it by hand. |
| `C:\SkyNX\Library\Packs`, `Drafts` | Modpacks from before projects, until you delete them. |
| `%APPDATA%\SwitchNX Studio` | Settings, LOOT's masterlist and caches. |

## Common problems {#problems}

| What you see | Why | What to do |
| --- | --- | --- |
| "It has several versions; I used the one for this edition" | The mod ships `_AE` and `_SE` folders with the same plugin | Nothing. If you wanted the other, extract the archive and add that folder. |
| "… is still compressed" (Serious) | The project has mods as `.7z` inside Data | Doctor » **Extract … into Data**. |
| "I can't open .rar files" | No 7-Zip, and Windows' `tar.exe` couldn't | Install 7-Zip, or extract it and drop the folder. |
| "… has no SEQ file" | The plugin has start-up quests and no `.seq` | Doctor » create the SEQ. |
| "The .ccc would reach … bytes" | What you're adding doesn't fit in 4096 bytes | Shorten names (**Rename**, **Short**) or untick a mod. Nothing is written until it fits. |
| "… has characters Google Drive changes" | Apostrophes or symbols in the name | Doctor » rename to the safe version. |
| A plugin like `Ryn_s` doesn't load | Drive already damaged the name | Doctor » rename it back and move the leftover copy to the trash. |
| Textures in PC format | A Switch mod with some unconverted texture | If they look purple or black, convert it or use the Diet. |
| "I didn't find the atmosphere folder" | In Copy to SD the path isn't the SD root | Type the drive (`E:\`) or its `atmosphere\contents` folder. |
| "The ini asks for X.bsa and it doesn't exist" | A converter joined BSAs and left the old name, or the BSA is really missing | With the game BSAs set up, the Doctor checks the files. If nothing is missing, removing it from the ini is safe. |
| An `.esl` in an SE project (Serious) | SE can't load `.esl` | Doctor » **Turn it into .esp for SE**. |
| "… is a modpack" when importing to the Library | Modpacks aren't kept in the Library | Start a project with it, or bring its mods into the open project. |
| A file I deleted in `Mods\` came back | `Mods\` shows the project as it is | Untick the mod or remove it on the Mods page. |
| "Changes made in the project folder" in the History | You edited files in `Mods\` or `Base\` | Nothing: they're in the project. Undo it there if it wasn't on purpose. |

If a change didn't turn out as you wanted: **History » Undo**.
