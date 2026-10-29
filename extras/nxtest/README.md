# NXTest: test tools for Switch packs

A lesser power, **SkyNX Test Tools**, that opens message-box menus (Switch has no
console and no MCM): teleport to the big cities, spawn one or many enemies from the
game's leveled lists (so the pack's mods decide what appears), remove everything it
spawned, set the time of day, heal.

- `source/*.psc`: the two scripts.
- `pex/*.pex`: the same scripts, compiled, so the mod can be built without a Papyrus compiler.
- `build.py`: writes `NXTest.esp` and `NXTest.bsa` (scripts and SEQ) from the compiled
  scripts and the game's `Skyrim.esm`, which it copies two records' layout from.

To build it with the compiled scripts that come here:

    python build.py <Skyrim.esm> pex out

Then add `out` to a project in SwitchNX Studio (Add mods » Add as it is; in Spanish, Agregar mods » Agregar tal cual). The teleport menu has
nine places and Back: a message box takes ten buttons at most.

To change the scripts, compile them with any Papyrus compiler, with the game's script sources as
headers (they come with the Creation Kit and aren't part of this repository), e.g.
[papyrus-compiler](https://github.com/russo-2025/papyrus-compiler):

    papyrus-compiler compile -h <Data\Source\Scripts> -i source -o pex
