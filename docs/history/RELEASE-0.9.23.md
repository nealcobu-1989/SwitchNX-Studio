# SwitchNX Studio 0.9.23

Changes since 0.9.20. / Cambios desde la 0.9.20.

## English

**The big finding: mod files open from the SD.** Atmosphère serves every mod plugin and mod
BSA from the SD card, and the game keeps them open. With too many, files the game opens later
fail: message boxes come out empty, NPCs stand there without talking, race descriptions go
missing, and a sound that failed to open can crash the game when it's closed (opening the map).
Creation Club and the game's own files don't count. In one long test on a Switch 1: 255 failed
at once, about 160 failed in busy scenes, 117 still left one message box empty, 104 to 108 worked.

Doctor
- New: **mod files open from the SD**, counted on every check (info up to 112, warning above,
  serious above 150).
- New: plugins whose texts read `<Error: No strings file for lstring ID ...>` (a patch saved in
  an editor without the game's texts). **Use the game's texts** puts the real ones back.
- New, serious: **the behaviors call files that don't load** (everyone in T-pose after switching
  off an animation mod the behaviors were generated with).
- BSAs that SkyNX Mods leaves out (every plugin of the mod off) no longer count as loaded.
- A behavior file that only restores the game's own copy is no longer a conflict.
- Mods marked **Doesn't go** are no longer reported as "not active" or "BSA that doesn't load".

Mods page and project
- **Doesn't go** keeps an archive that other mods still going share (a joined suite), so taking
  one mod out never takes the others' files with it.
- Syncing the project folder no longer sets aside files whose date changed but whose content didn't.
- Short BSA names never take the name of a plugin in the load order.

Behaviors (Nemesis)
- The game's own behavior files are seeded from Nemesis' cache (fixes ERROR 1210 on `0_master.hkx`).
- A mod switched off with `#` no longer feeds the generation.
- In SkyNX Mods, the generated behaviors switch off with the mods they were made from.

Packing
- The LOOT reminder before packing ignores plugins LOOT doesn't know (your own merges, mods from a pack).

Guide skill (`switchnx-studio-guide`)
- The SD open-files limit, how to make room (join BSAs, merge patches, Doesn't go), and new
  common situations (empty message boxes, crash in `LibAudioUpdate`, `<Error: No strings file>`,
  T-pose after switching an animation mod off, Nemesis ERROR 1210 `jumpbehavior.hkx`).

## Español

**El gran hallazgo: archivos de mods abiertos desde la SD.** Atmosphère sirve cada plugin y cada
BSA de mods desde la tarjeta, y el juego los mantiene abiertos. Con demasiados, fallan los
archivos que el juego abre después: letreros vacíos, NPCs que se quedan quietos sin hablar,
descripciones de razas que no salen, y un sonido que no se pudo abrir puede cerrar el juego al
cerrarlo (al abrir el mapa). Los del Creation Club y los del juego no cuentan. En una prueba
larga en Switch 1: con 255 falló de una, con unos 160 fallaba en escenas pesadas, con 117 todavía
salió un letrero vacío, y con 104 a 108 funcionó.

Doctor
- Nuevo: **archivos de mods abiertos desde la SD**, contados en cada revisión (información hasta
  112, aviso por encima, grave por encima de 150).
- Nuevo: plugins cuyos textos dicen `<Error: No strings file for lstring ID ...>` (un parche
  guardado en un editor sin los textos del juego). **Usar los textos del juego** devuelve los reales.
- Nuevo, grave: **los comportamientos llaman archivos que no cargan** (todos en T-pose después de
  apagar un mod de animaciones con el que se generaron).
- Los BSAs que SkyNX Mods deja fuera (todos los plugins del mod apagados) ya no cuentan como cargados.
- Un archivo de comportamiento que solo repone la copia del juego ya no es un conflicto.
- Los mods marcados **No va** ya no salen como "no activo" ni como "BSA que no carga".

Página de Mods y proyecto
- **No va** deja en su sitio un archivo que comparten otros mods que sí van (una suite juntada),
  así que sacar un mod nunca se lleva los archivos de los demás.
- Al sincronizar la carpeta del proyecto ya no se apartan archivos a los que solo les cambió la fecha.
- Los nombres cortos de BSA nunca toman el nombre de un plugin de la lista de carga.

Comportamientos (Nemesis)
- Los archivos de comportamiento del juego se siembran desde la caché de Nemesis (arregla el ERROR
  1210 de `0_master.hkx`).
- Un mod apagado con `#` ya no entra en la generación.
- En SkyNX Mods, los comportamientos generados se apagan con los mods con los que se hicieron.

Empaquetar
- El aviso de LOOT antes de empaquetar ignora los plugins que LOOT no conoce (tus merges, mods de un pack).

Skill de guía (`switchnx-studio-guide`)
- El límite de archivos abiertos desde la SD, cómo hacer espacio (juntar BSAs, unir parches, No va)
  y situaciones nuevas (letreros vacíos, cierre en `LibAudioUpdate`, `<Error: No strings file>`,
  T-pose después de apagar un mod de animaciones, ERROR 1210 de Nemesis con `jumpbehavior.hkx`).
