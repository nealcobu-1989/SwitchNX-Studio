# SwitchNX Studio 0.9.24

Changes since 0.9.23. / Cambios desde la 0.9.23.

Video tour of the app / Recorrido en video por la app: https://youtu.be/cHxcAihTc3M

## English

Doctor
- New: **how many quests start with a new game** (from 300). Every mod's start-up quests start
  at once and the Switch is slow with them: mod followers may not talk for the first minutes.
- New: **SEQ files that are only loose** in `Data\seq` (not confirmed on Switch; keep them in a BSA).
- **BSA that loses scripts to the ini** no longer counts the PC script extender's copies of the
  game's scripts: promoting such a BSA would have made them win (Auri's BSA brought 39).
- **Merges of your own** (zMerge merges brought into the project) no longer count among "plugins
  LOOT doesn't know": they get their own note, saying LOOT can't place them and their place in
  the load order is your call.
- New, serious: **blank files in a BSA** (deep check). Files with the right size and every byte
  zero: 21 Apothecary meshes (the Potion of Poison Resistance showed a red "!") and 7 College of
  Winterhold meshes came out like this in a joined archive. The fix is the mod's original file,
  put in the mod's folder under `Mods`.

Mods page and project
- **Remove** on a mod inside a joined suite no longer takes the suite with it: the archive and its
  ini line stay while other mods still use it (before, removing Cloaks&Capes would have sent
  SuiteXM and SuiteXT, shared by 22 mods, to the trash).
- Rewriting a BSA (Doctor fixes, Join mods) keeps meshes compressed when the archive stores them
  compressed file by file with its default flag off, as the console's suites do. Before, a rewrite of
  SuiteXM stored them all uncompressed (286 MB became 407 MB).

Behaviors (Nemesis)
- Nemesis' template for `attackbehavior.hkx` is left out unless a mod brings that file (fixes
  ERROR 1210 on `jumpbehavior.hkx` with FNIS animations plus XPMSE).

Workshop (Join plugins)
- zMerge's `map.json` is read when the merge is brought: **Join mods** then renames voices and
  FaceGen of renumbered records, points FaceGen meshes at their renamed tints, and fixes scripts
  that look a merged plugin up by name (`Game.GetFormFromFile`: the plugin name and the ids).

Guide skill (`switchnx-studio-guide`)
- What a merge changes besides the plugin, joining BSAs from both ini lists, start-up quests in
  a new game, loose SEQ files, script weight, frame pacing, followers, faces without FaceGen,
  scripts that look for a plugin by its PC name, Nemesis ERROR 6006 and the new fix for 1210.
- Stuck quests with Test Tools, and Survival Mode's level up after sleeping.
- One mod's message box empty while the others work (NX Quick Save), blank files in a BSA, and the rule
  for hand fixes in a project: edit the file in `Mods`, never in `Switch` (Copy to SD builds it again).
- Mod files open from the SD: 108 starts fine but leaves texts empty once playing (hunger, low
  magicka, the standing stones). Aim for 104 or fewer.
- **zMerge and the first plugin**: with Clean it can't drop the first plugin as a master; Clobber
  builds without a warning but leaves broken references (84 in a merge of 33 patches). The fix
  is a decoy plugin first, then checking every reference. Plugins with navmeshes of their own
  stay out of merges, and `merges.json` is only edited with zEdit closed.
- How to patch a big creature mod against the rest of a pack (load it early, carry over new
  scripts, skeletons and merchant chests inside a merged patch).

Convert (found 2026-11-04 with Realistic Water Two 5.7.3)
- **Water textures keep 4 mips.** `textures\water\` (the water normals, RWTCalmWater, the per-cell
  flow maps) converted with the full mip chain drew bright cyan rectangles on the sea and rings
  around water wheels on the Switch. The community port of the same files has 4 mips at 1024
  and at 64 and renders right; the game's own NX water textures stop at 10 for 1024 and the
  flow maps have 1. Convert and the Diet now cap water textures at 4 mips (`texplan.target_mips`).
- **Remove** on a mod whose plugin was merged into another (the record lists no plugin, only the
  suites it shares) no longer takes those suites: MILK listed SuiteQM/SuiteQT, shared with the
  quest expansions, and Remove would have sent them to the trash.

Lessons kept in the guide skill
- **Beyond Skyrim: Bruma doesn't fit a full Switch 1 pack.** With 79 plugins and 23 BSAs the
  game sat at 2.57 GB right after loading and 2.77 GB at the Pale Pass gate; crossing the border
  (a whole second worldspace while Skyrim stays in memory) crashed three times in the loader
  thread `BSTaskManager`, in `memcpy` with a null destination: an allocation that failed. No file
  was missing or damaged. The pack went back to Midwood Isle and Wyrmstooth.
- **Reading an Atmosphère crash report**: thread `BSTaskManager` + `__memcpy_device` with
  `X[00] = 0` is out of memory while loading; `LibAudioUpdate` at `CloseFile` is a sound that
  failed to open (too many files open); the "0% CPU, nothing moves" freeze before a crash is the
  allocator hunting for a free block.
- A whole worldspace load needs 300 to 400 MB free on top of what the pack holds in the field.

Convert
- **BC1 in the "For all" bar.** Converting several mods at once can turn BC1 on for all of them,
  like a single mod (BC1 for opaque textures halves their memory; it needs the native format).

SkyNX Test Tools 1.3 (`extras/nxtest`)
- New **Mod creatures** menu: Harkon in his combat form, Karstaag, a werebear, or a mix of 14
  different MihailMods creatures at once (a memory test). Each one is found with
  `Game.GetFormFromFile`, so a plugin that isn't in the pack is skipped.
- **Heal** moved into the **Player** menu. The plugin's layout changed (build 3): Pack writes
  `NXTest.esp` again for every project with Test Tools, and the scripts are new (replace them
  in the BSA that holds them).

## Español

Doctor
- Nuevo: **cuántas misiones arrancan con una partida nueva** (desde 300). Las misiones de inicio de
  todos los mods arrancan a la vez y la Switch va lenta con ellas: los seguidores de mods pueden
  no hablar en los primeros minutos.
- Nuevo: **archivos SEQ que solo están sueltos** en `Data\seq` (no confirmado en Switch; mejor dentro de un BSA).
- **BSA que pierde scripts frente al ini** ya no cuenta las copias de los scripts del juego que trae
  el script extender de PC: subir ese BSA las habría hecho ganar (el BSA de Auri traía 39).
- **Merges propios** (merges de zMerge traídos al proyecto) ya no cuentan entre los "plugins que LOOT
  no conoce": tienen su propia nota, que dice que LOOT no sabe dónde van y que su lugar en el orden
  de carga lo decides tú.
- Nuevo, grave: **archivos en blanco dentro de un BSA** (revisión a fondo). Archivos con el tamaño
  correcto y todos sus bytes en cero: 21 mallas de Apothecary (la Potion of Poison Resistance salía
  con un "!" rojo) y 7 del College of Winterhold salieron así en un archivo juntado. El arreglo es
  el archivo original del mod, puesto en la carpeta del mod dentro de `Mods`.

Página de Mods y proyecto
- **Quitar** un mod que está dentro de una suite juntada ya no se lleva la suite: el archivo y su línea
  del ini se quedan mientras otros mods lo usen (antes, quitar Cloaks&Capes habría mandado a la
  papelera SuiteXM y SuiteXT, que comparten 22 mods).
- Reescribir un BSA (arreglos del Doctor, Juntar mods) mantiene las mallas comprimidas cuando el archivo
  las guarda comprimidas una por una con la marca por defecto apagada, como las suites de la consola.
  Antes, reescribir SuiteXM las guardaba todas sin comprimir (286 MB pasaban a 407 MB).

Comportamientos (Nemesis)
- La plantilla de Nemesis para `attackbehavior.hkx` queda fuera salvo que un mod traiga ese archivo
  (arregla el ERROR 1210 con `jumpbehavior.hkx` cuando se juntan animaciones FNIS y XPMSE).

Taller (Juntar plugins)
- Al traer el merge se lee el `map.json` de zMerge: **Juntar mods** renombra entonces las voces y el
  FaceGen de los registros renumerados, apunta las mallas de FaceGen a sus tintes renombrados y
  arregla los scripts que buscan un plugin fusionado por nombre (`Game.GetFormFromFile`: el
  nombre del plugin y los ids).

Skill de guía (`switchnx-studio-guide`)
- Lo que cambia un merge además del plugin, juntar BSAs de las dos listas del ini, las misiones de
  inicio en una partida nueva, los SEQ sueltos, el peso de los scripts, el frame pacing, los
  seguidores, las caras sin FaceGen, los scripts que buscan un plugin por su nombre de PC, el
  ERROR 6006 de Nemesis y el arreglo nuevo del 1210.
- Misiones trabadas con Test Tools, y la subida de nivel de Survival al dormir.
- El letrero vacío de un solo mod mientras los demás funcionan (NX Quick Save), los archivos en blanco dentro de un BSA,
  y la regla para arreglos a mano en un proyecto: se edita el archivo en `Mods`, nunca en `Switch`
  (Copiar a la SD lo vuelve a armar).
- Archivos de mods abiertos desde la SD: con 108 el juego arranca bien, pero ya jugando deja
  textos vacíos (hambre, magicka baja, las piedras guardianas). Lo seguro es 104 o menos.
- **zMerge y el primer plugin**: con Clean no logra quitar el primer plugin como master; Clobber
  construye sin avisar pero deja referencias rotas (84 en un merge de 33 parches). El arreglo es un
  plugin señuelo de primero y revisar cada referencia. Los plugins con navmesh propio se quedan
  fuera de los merges, y `merges.json` solo se edita con zEdit cerrado.
- Cómo parchar un mod grande de criaturas contra el resto de un pack (cargarlo temprano, llevar los
  scripts nuevos, los esqueletos y los cofres de mercaderes dentro de un parche fusionado).

Convertir (hallado el 2026-11-04 con Realistic Water Two 5.7.3)
- **Las texturas de agua se quedan con 4 mips.** `textures\water\` (las normales del agua,
  RWTCalmWater, los flow maps por celda) convertidas con la cadena de mips completa pintaban
  rectángulos cian brillantes en el mar y anillos alrededor de las ruedas de los molinos en la
  Switch. El port comunitario de los mismos archivos tiene 4 mips a 1024 y a 64 y se ve bien; las
  texturas de agua NX del propio juego paran en 10 para 1024 y los flow maps tienen 1. Convertir y
  la Dieta ahora limitan las texturas de agua a 4 mips (`texplan.target_mips`).
- **Quitar** un mod cuyo plugin se fusionó en otro (la ficha no lista plugin, solo las suites que
  comparte) ya no se lleva esas suites: MILK listaba SuiteQM/SuiteQT, compartidas con las
  expansiones de misiones, y Quitar las habría mandado a la papelera.

Lecciones que quedan en el skill de guía
- **Beyond Skyrim: Bruma no cabe en un pack completo de Switch 1.** Con 79 plugins y 23 BSA el juego
  estaba en 2,57 GB recién cargado y en 2,77 GB en la puerta de Pale Pass; cruzar la frontera (un
  segundo worldspace entero mientras Skyrim sigue en memoria) se cerró tres veces en el hilo
  cargador `BSTaskManager`, en `memcpy` con destino nulo: una reserva de memoria que falló. No
  faltaba ni estaba dañado ningún archivo. El pack volvió a Midwood Isle y Wyrmstooth.
- **Leer un reporte de cierre de Atmosphère**: hilo `BSTaskManager` + `__memcpy_device` con
  `X[00] = 0` es memoria agotada mientras carga; `LibAudioUpdate` en `CloseFile` es un sonido que
  no pudo abrirse (demasiados archivos abiertos); el congelamiento con "0 % de CPU y nada se
  mueve" antes del cierre es el asignador buscando un bloque libre.
- Cargar un worldspace entero necesita 300 a 400 MB libres además de lo que el pack ya tiene en el campo.

Convertir
- **BC1 en la barra "Para todos".** Al convertir varios mods a la vez se puede encender BC1 para
  todos, como en uno solo (BC1 para texturas opacas usa la mitad de memoria; necesita el formato nativo).

SkyNX Test Tools 1.3 (`extras/nxtest`)
- Nuevo menú **Mod creatures**: Harkon en su forma de combate, Karstaag, un hombre oso, o una mezcla
  de 14 criaturas distintas de MihailMods a la vez (prueba de memoria). Cada una se busca con
  `Game.GetFormFromFile`, así que un plugin que no está en el pack se salta.
- **Heal** pasa al menú **Player**. Cambió la estructura del plugin (build 3): Empaquetar vuelve a
  escribir `NXTest.esp` en cada proyecto con Test Tools, y los scripts son nuevos (se reemplazan
  en el BSA que los tiene).
