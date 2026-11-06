# NXTest: test tools for Switch packs

A lesser power, **SkyNX Test Tools**, that opens message-box menus (Switch has no
console and no MCM):

- **Teleport** to the big cities.
- **Spawn one or many** enemies from the game's leveled lists (so the pack's mods
  decide what appears), and **remove** everything it spawned.
- **Mod creatures** (1.3): Harkon in his combat form (Dawnguard), Karstaag and a
  werebear (Dragonborn), or a mix of 14 different MihailMods creatures at once, to test
  memory with many new meshes and textures in view. Each one is looked up with
  `Game.GetFormFromFile` (plugin name and form id), so a plugin that isn't in the pack is
  just skipped. **Remove spawned** takes them away too.
- **Time of day**.
- **Quests** (1.2): goes through the quests marked as active in the Journal. For each
  one: **Next stage** (what `setstage` did on PC: the first later stage not done yet),
  **Restart quest** (what `resetquest` did: stop, reset, start, after a confirmation)
  or the next tracked quest. Skipping stages can leave things undone: save first.
- **Player** (1.2): +1 perk point, +1000 gold, god mode on and off, and **No collision**
  to walk out of a spot where you got stuck (use it again to switch it back). **Heal** moved
  here in 1.3.
- **Weather** (1.2): clear, cloudy, rain, snow or fog until **Normal weather**.

The quest menu needs the pack's quests: plugin, form id, stages and name (a script
can't read a quest's name without SKSE, so each quest gets a message with its name
written in). SkyNX Studio writes them into `NXTest.esp` every time the project is
packed and the list changed (`skynx/nxtest.py`, `refresh`). Quests are found with
`Game.GetFormFromFile`, so `Skyrim.esm` stays the only master and a plugin that is
switched off on the console is just skipped. Up to 1024 quests and 12288 stages.

- `source/*.psc`: the two scripts. `NXTestQuestScript.psc` is written by
  `tools/gen_quest_script.py` (the data comes in arrays of 128, the most a Papyrus
  array is sure to hold, so its getters are generated).
- `build.py`: writes `NXTest.esp` (without quests) and `NXTest.bsa` (scripts and SEQ)
  from the compiled scripts and the game's `Skyrim.esm`, which it copies two records'
  layout from. The records themselves are in `skynx/nxtest.py`.

Compile the scripts with any Papyrus compiler, with the game's script sources as
headers (they come with the Creation Kit and aren't part of this repository), e.g.
[papyrus-compiler](https://github.com/russo-2025/papyrus-compiler):

    python tools/gen_quest_script.py
    papyrus-compiler compile -h <Data\Source\Scripts> -i source -o pex
    python build.py <Skyrim.esm> pex out
