"""Every user-facing string of the engine, in English and Spanish.

The engine stores message keys and parameters; the window renders them in the
language the user picked. English is the default.
"""
from __future__ import annotations

LANGS = ("en", "es")

CATEGORIES = {
    "layout": {"en": "Structure", "es": "Estructura"},
    "files": {"en": "Files", "es": "Archivos"},
    "list": {"en": "Load list", "es": "Lista de carga"},
    "plugins": {"en": "Plugins", "es": "Plugins"},
    "masters": {"en": "Masters", "es": "Masters"},
    "inis": {"en": "Inis", "es": "Inis"},
    "bsa": {"en": "BSA", "es": "BSA"},
    "textures": {"en": "Textures", "es": "Texturas"},
    "audio": {"en": "Audio", "es": "Audio"},
    "requirements": {"en": "Requirements", "es": "Requisitos"},
    "duplicates": {"en": "Duplicates", "es": "Duplicados"},
}

# key: {lang: (title, detail)}
MSG = {
    "loot-note": {
        "en": ("{plugin}: LOOT says", "{text_en}"),
        "es": ("{plugin}: LOOT dice", "{text_es}")},
    "loot-unknown": {
        "en": ("{n} plugins LOOT doesn't know", "LOOT's masterlist has no rules for them, so it can't say where they go or what they need. In Load order, Suggest order (LOOT) lets you pick a category for each one; your choice is remembered for every pack."),
        "es": ("{n} plugins que LOOT no conoce", "La masterlist de LOOT no tiene reglas para ellos, así que no sabe dónde van ni qué necesitan. En Orden de carga, Sugerir orden (LOOT) te deja escoger una categoría para cada uno; tu elección queda guardada para todos los packs.")},
    "loot-merge": {
        "en": ("{plugin} is a merge of {n} mods", "It was built with a merge tool and contains: {list}. LOOT's rules for those mods apply to it.{dummies_en}"),
        "es": ("{plugin} es un merge de {n} mods", "Se armó con una herramienta de merge y contiene: {list}. Las reglas de LOOT para esos mods se le aplican a él.{dummies_es}")},
    "layout-base": {
        "en": ("Game folder not found", "I looked for {tid}\\romfs inside the chosen folder and it isn't there."),
        "es": ("No encontré la carpeta del juego", "Busqué {tid}\\romfs dentro de la carpeta elegida y no está.")},
    "layout-list": {
        "en": ("No load list", "There's no {aoc}\\romfs\\Skyrim_aoc.ccc (AE) and no romfs\\Plugins (SE)."),
        "es": ("No hay lista de carga", "No encontré {aoc}\\romfs\\Skyrim_aoc.ccc (AE) ni romfs\\Plugins (SE).")},
    "layout-both": {
        "en": ("Both an AE and an SE list exist", "There's a Skyrim_aoc.ccc and also an SE Plugins file. With AE installed, the .ccc is the one that counts."),
        "es": ("Hay lista AE y lista SE a la vez", "Existe Skyrim_aoc.ccc y también el archivo Plugins de SE. Con la AE instalada, la lista que manda es el .ccc.")},
    "data-archive": {
        "en": ("{name} is still compressed", "There's an archive inside Data. The game can't open it; its .esp and .bsa files need to be extracted into Data."),
        "es": ("{name} sigue comprimido", "Hay un archivo comprimido dentro de Data. El juego no lo abre; hay que extraer su .esp y sus .bsa en Data.")},
    "data-loose": {
        "en": ("Loose folder in Data: {name}", "The packs we checked put everything in BSAs. Loose files might work, but that isn't confirmed on Switch."),
        "es": ("Carpeta suelta en Data: {name}", "Los packs que revisamos empacan todo en BSA. Los archivos sueltos podrían funcionar, pero no está confirmado en Switch.")},
    "ini-alt": {
        "en": ("The game doesn't read {name}", "Only Skyrim.ini and Skyrim_<language>.ini are read. This looks like a variant (30 or 60 FPS, for example) meant to be renamed by hand."),
        "es": ("{name} no lo lee el juego", "Solo se leen Skyrim.ini y Skyrim_<idioma>.ini. Este parece una variante (por ejemplo 30 o 60 FPS) para renombrar a mano.")},
    "list-bom": {
        "en": ("{list} starts with a BOM", "It has an invisible mark at the start that can break the first plugin's name."),
        "es": ("{list} empieza con BOM", "Tiene una marca invisible al inicio que puede romper el nombre del primer plugin.")},
    "list-ws": {
        "en": ("Extra spaces around names", "Some lines have spaces at the start or the end."),
        "es": ("Espacios sobrantes en nombres", "Algunas líneas tienen espacios al inicio o al final.")},
    "list-nl": {
        "en": ("Mixed line endings", "It mixes CRLF and LF. It works in the packs we checked, but it's better to make them all the same."),
        "es": ("Saltos de línea mezclados", "Mezcla CRLF y LF. Funciona en los packs revisados, pero conviene unificar.")},
    "list-se-nl": {
        "en": ("Plugins should use LF line endings", "The NX Toolkit guide asks for the Plugins file to be saved with Unix (LF) line endings."),
        "es": ("Plugins debería usar saltos LF", "La guía del NX Toolkit pide guardar Plugins con fin de línea Unix (LF).")},
    "list-dup": {
        "en": ("Listed twice: {name}", "It appears more than once; only one counts and the other wastes bytes."),
        "es": ("Repetido: {name}", "Aparece más de una vez; solo cuenta una y la otra gasta bytes.")},
    "bsa-needs-rename": {
        "en": ("{name} doesn't load", "'{twin}' needs '{want}' and only this copy with a different name exists."),
        "es": ("{name} no carga", "'{twin}' necesita '{want}' y solo existe esta copia con otro nombre.")},
    "leftover": {
        "en": ("Leftover copy: {name}", "It's a copy of '{twin}', which is the one that loads. It takes {size} on the SD."),
        "es": ("Copia sobrante: {name}", "Es una copia de '{twin}', que es el que sí carga. Ocupa {size} en la SD.")},
    "leftover-bsa": {
        "en": ("Leftover copy: {name}", "'{twin}' already exists and is the one that loads."),
        "es": ("Copia sobrante: {name}", "Ya existe '{twin}', que es el que carga.")},
    "list-case": {
        "en": ("Different capitals: {name}", "The list says '{name}' but the file is '{file}'. The rentry guide says names are case sensitive."),
        "es": ("Mayúsculas distintas: {name}", "La lista dice '{name}' pero el archivo se llama '{file}'. La guía de rentry indica que los nombres distinguen mayúsculas.")},
    "list-disabled": {
        "en": ("Switched off: {name}", "It starts with '#', so the game can't find it and skips it. Some authors use this to turn a mod off."),
        "es": ("Desactivado: {name}", "Empieza con '#', así que el juego no lo encuentra y lo salta. Es la forma que usan algunos autores para apagar un mod.")},
    "list-near-faces": {
        "en": ("Doesn't load: {name}", "The list asks for '{name}' and the file is '{file}'. Its BSA keeps faces or voices under '{name}', so the file should get that name back.{guess}"),
        "es": ("No carga: {name}", "La lista pide '{name}' y el archivo se llama '{file}'. Su BSA guarda caras o voces bajo el nombre '{name}', así que conviene devolverle ese nombre al archivo.{guess}")},
    "list-near": {
        "en": ("Doesn't load: {name}", "The list asks for '{name}' and the file is '{file}'. Nothing in the mod depends on its name, so fixing the list is enough.{guess}"),
        "es": ("No carga: {name}", "La lista pide '{name}' y el archivo se llama '{file}'. Nada del mod depende del nombre, así que basta corregir la lista.{guess}")},
    "guess": {
        "en": ("", " The match is approximate: make sure it's the same mod."),
        "es": ("", " El parecido es aproximado: confirma que sea el mismo mod.")},
    "covered-yes": {
        "en": ("", " Nothing the plugins ask for is missing (scripts, meshes and the textures those meshes use): its files are surely inside another BSA, so taking it out of the ini is safe. Voices and sounds aren't checked."),
        "es": ("", " No falta nada de lo que piden los plugins (scripts, mallas y las texturas de esas mallas): sus archivos seguramente quedaron dentro de otro BSA, así que quitarlo del ini es seguro. Las voces y sonidos no se revisan.")},
    "covered-gaps": {
        "en": ("", " Files the plugins ask for are also missing (see Requirements); they may have been in this BSA."),
        "es": ("", " Además faltan archivos que piden los plugins (mira Requisitos); puede que estuvieran en este BSA.")},
    "covered-unknown": {
        "en": ("", " To know whether its files are inside another BSA, set the base game folder in Settings."),
        "es": ("", " Para saber si sus archivos quedaron dentro de otro BSA, configura la carpeta del juego base en Ajustes.")},
    "archives-note": {
        "en": ("", " Careful: there are unextracted mods in Data; it may be inside one of them."),
        "es": ("", " Ojo: hay mods sin extraer en Data; puede que esté dentro de uno.")},
    "list-missing": {
        "en": ("Not found: {name}", "It's in the list but there's no file. The game skips it; if another plugin uses it as a master, that one will fail.{note}"),
        "es": ("No existe: {name}", "Está en la lista pero no hay archivo. El juego la salta; si otro plugin lo usa como master, ese otro fallará.{note}")},
    "plugin-unlisted": {
        "en": ("Not active: {name}", "The file is in Data but not in {list} or sTestFile. It takes {size} on the SD without loading. It may be on purpose."),
        "es": ("No está activado: {name}", "El archivo está en Data pero no en {list} ni en sTestFile. Ocupa {size} en la SD sin cargarse. Puede ser a propósito.")},
    "stest-missing": {
        "en": ("sTestFile points to a missing plugin: {name}", "An sTestFile line in the ini asks for a plugin that isn't in Data."),
        "es": ("sTestFile apunta a algo que no existe: {name}", "Un sTestFile del ini pide un plugin que no está en Data.")},
    "stest-extra": {
        "en": ("Loaded from the ini: {name}", "This plugin comes in through sTestFile, outside the list. It saves .ccc bytes, but it loads before everything in the list."),
        "es": ("Carga desde el ini: {name}", "Este plugin entra por sTestFile, fuera de la lista. Ahorra bytes del .ccc, pero carga antes que todo lo de la lista.")},
    "plugin-bad": {
        "en": ("Damaged plugin: {name}", "{error}"),
        "es": ("Plugin dañado: {name}", "{error}")},
    "plugin-oldrim": {
        "en": ("Original Skyrim (LE) plugin: {name}", "Header version {ver} (Skyrim LE). It may work if it only changes settings, but the safe route is to re-save it in the SE Creation Kit."),
        "es": ("Plugin de Skyrim original: {name}", "Versión de encabezado {ver} (Skyrim LE). Puede funcionar si solo cambia ajustes, pero lo seguro es guardarlo de nuevo con el Creation Kit de SE.")},
    "plugin-form43": {
        "en": ("Old header format: {name}", "Form version {ver} in the header. It usually works; if it causes trouble, re-save it in SE."),
        "es": ("Encabezado con formato viejo: {name}", "Formato {ver} en el encabezado. Suele funcionar; si da problemas, conviene guardarlo de nuevo en SE.")},
    "plugin-esl-se": {
        "en": ("ESL in SE mode: {name}", "According to the NX Toolkit wiki, the SE version on Switch can't read ESL. Rename it to .esp and clear the ESL flag."),
        "es": ("ESL en modo SE: {name}", "Según la wiki del NX Toolkit, la versión SE de Switch no lee ESL. Hay que renombrarlo a .esp y quitarle la marca ESL.")},
    "plugin-dummy": {
        "en": ("Empty plugin: {name}", "It has no records; it only exists to load its BSA. It uses {bytes} bytes of the .ccc that can be freed by moving the BSA to the ini. None of its files would change who wins them."),
        "es": ("Plugin vacío: {name}", "No tiene registros; solo sirve para cargar su BSA. Ocupa {bytes} bytes del .ccc que se pueden liberar pasando el BSA al ini. Ninguno de sus archivos cambiaría de ganador.")},
    "off-without-file": {
        "en": ("{n} lines switched off for plugins that are gone: {names}", "These plugins were removed from the project, but their switched-off lines stayed in the load list. The game skips them; taking them out tidies the load order and SkyNX Mods' list."),
        "es": ("{n} líneas apagadas de plugins que ya no están: {names}", "Esos plugins se quitaron del proyecto, pero sus líneas apagadas quedaron en la lista de carga. El juego las salta; sacarlas limpia el orden de carga y la lista de SkyNX Mods.")},
    "cc-not-in-game": {
        "en": ("{n} Creation Club lines the game doesn't have: {bytes} bytes of the .ccc for nothing", "The console's own list names them, but the game has neither their plugin nor their BSA, so nothing loads from them. Taking them out frees {bytes} bytes and changes nothing in the game."),
        "es": ("{n} líneas del Creation Club que el juego no tiene: {bytes} bytes del .ccc para nada", "La lista de la propia consola las nombra, pero el juego no tiene ni su plugin ni su BSA, así que no cargan nada. Quitarlas libera {bytes} bytes y no cambia nada en el juego.")},
    "ccc-shorten": {
        "en": ("{n} plugins with long names: {saved} bytes of the .ccc to gain", "Each plugin costs its name in the .ccc, and the list is close to its limit: every mod you add needs room. Short names in the style of the BSAs (first word and initials) free {saved} bytes; everything that uses each name follows it (other plugins' masters, BSAs, voices, faces, SEQ, scripts). Saves remember plugin names: do it before the real playthrough, not in the middle of it."),
        "es": ("{n} plugins con nombre largo: {saved} bytes del .ccc por ganar", "Cada plugin ocupa su nombre en el .ccc, y la lista está cerca de su límite: cada mod que agregues necesita espacio. Nombres cortos al estilo de los BSA (primera palabra e iniciales) liberan {saved} bytes; todo lo que usa cada nombre lo sigue (masters de otros plugins, BSA, voces, caras, SEQ, scripts). Las partidas guardadas recuerdan el nombre de los plugins: hazlo antes de la partida de verdad, no en medio.")},
    "names-foreign": {
        "en": ("{name}: {n} names in another language", "Like \"{example}\": the mod comes from a translated upload, and changing a record copied its name too, so the game shows it that way. For {fixable} of them the game's own name can be put back; only the names change. Its own new records have no game name to go back to."),
        "es": ("{name}: {n} nombres en otro idioma", "Como \"{example}\": el mod viene de una versión traducida y, al cambiar un registro, copió también su nombre, así que el juego lo muestra así. A {fixable} de ellos se les puede devolver el nombre del juego; solo cambian los nombres. Sus registros nuevos no tienen un nombre del juego al cual volver.")},
    "plugin-dummy-keep": {
        "en": ("Empty plugin: {name} (leave it as it is)", "It has no records and only loads its BSA. Moving the BSA to the ini would free {bytes} bytes of the .ccc, but {n} of its files would change who wins them: the ini loads first, so mods loading before {name} would cover them (and its scripts would start winning). Below, each file and who would win it."),
        "es": ("Plugin vacío: {name} (déjalo así)", "No tiene registros y solo carga su BSA. Pasar el BSA al ini liberaría {bytes} bytes del .ccc, pero {n} de sus archivos cambiarían de ganador: lo del ini carga antes, así que los mods que cargan antes de {name} los taparían (y sus scripts empezarían a ganar). Abajo, cada archivo y quién lo ganaría.")},
    "master-cc": {
        "en": ("{name} needs {n} Creation Club plugins that aren't in the list", "It uses them as masters: {list}. Without them it doesn't load. Adding them takes .ccc space ({now} → {after} of {limit} bytes). If you don't use that content, take {name} out of the list instead."),
        "es": ("{name} necesita {n} plugins del Creation Club que no están en la lista", "Los usa como masters: {list}. Sin ellos no carga. Agregarlos ocupa espacio del .ccc ({now} → {after} de {limit} bytes). Si no usas ese contenido, mejor saca {name} de la lista.")},
    "master-missing": {
        "en": ("{name} needs {master}", "A master is missing. Without it, the plugin won't load or the game will close."),
        "es": ("{name} necesita {master}", "Le falta un master. Sin él, el plugin no carga o el juego se cierra.")},
    "master-order-ini": {
        "en": ("{name} (from the ini) uses {master}", "This plugin comes in through sTestFile and its master is in the list. The order the game uses for them isn't confirmed; if it works, leave it."),
        "es": ("{name} (desde el ini) usa {master}", "Este plugin entra por sTestFile y su master está en la lista. No está confirmado en qué orden los carga el juego; si funciona, déjalo así.")},
    "master-order": {
        "en": ("{master} loads after {name}", "A master has to load before the plugins that depend on it."),
        "es": ("{master} carga después de {name}", "Un master tiene que cargar antes de los plugins que dependen de él.")},
    "ccc-bytes": {
        "en": ("The .ccc uses {used} of {limit} bytes", "The exact limit isn't confirmed, but the largest packs stay close to 4000 bytes. Each plugin costs its name plus 2 bytes."),
        "es": ("El .ccc usa {used} de {limit} bytes", "El límite exacto no está confirmado, pero los packs más grandes se quedan cerca de 4000 bytes. Cada plugin gasta su nombre más 2 bytes.")},
    "ini-dup": {
        "en": ("{ini}: repeated key {key}", "It appears on lines {lines}; the last one wins."),
        "es": ("{ini}: clave repetida {key}", "Aparece en las líneas {lines}; vale la última.")},
    "ini-long": {
        "en": ("{key} is over 1024 characters", "{ini}: {n} characters. According to Koka, the game cuts anything past 1024."),
        "es": ("{key} pasa de 1024 caracteres", "{ini}: {n} caracteres. Según Koka, el juego corta lo que pasa de 1024.")},
    "ini-nearly": {
        "en": ("{key} is almost full", "{ini}: {n} of 1024 characters."),
        "es": ("{key} casi llena", "{ini}: {n} de 1024 caracteres.")},
    "ini-comma": {
        "en": ("{key} ends with a comma", "{ini}: the Toolkit guide asks for no comma after the last BSA."),
        "es": ("{key} termina en coma", "{ini}: la guía del Toolkit pide que el último BSA no lleve coma.")},
    "ini-bsa-missing": {
        "en": ("The ini asks for {name}, which doesn't exist", "{key} lists a BSA that isn't in Data.{note}{covered}"),
        "es": ("El ini pide {name} y no existe", "{key} lista un BSA que no está en Data.{note}{covered}")},
    "bsa-loses-to-ini": {
        "en": ("{n} mods lose scripts to BSAs loaded from the ini: {list}", "On Switch a BSA in the ini wins over the BSA a plugin loads by its name (on PC it's the other way round, which is how these mods were made). Their scripts are replaced by those of an ini BSA such as USSEP's, or by the game's own (Skyrim - Misc.bsa, which also loads from the ini), so parts of the mod don't work: Growl and Sacrosanct say it with an 'integrity issue' message, Quick Start doesn't offer to skip the intro. Seen on the console. The fix puts these BSAs in the ini after the others, in load order."),
        "es": ("{n} mods pierden scripts frente a BSA del ini: {list}", "En Switch un BSA del ini le gana al BSA que un plugin carga por su nombre (en PC es al revés, y así se hicieron estos mods). Sus scripts los reemplazan los de un BSA del ini, como el de USSEP, o los del propio juego (Skyrim - Misc.bsa, que también carga desde el ini), así que partes del mod no funcionan: Growl y Sacrosanct lo avisan con un mensaje de 'integrity issue' y Quick Start no ofrece saltar la introducción. Comprobado en la consola. El arreglo pone estos BSA en el ini después de los demás, en el orden de carga.")},
    "ini-bsa-double": {
        "en": ("{name} loads twice", "It already loads because its plugin is active, and it's also in the ini. It does no harm, but it uses ini characters."),
        "es": ("{name} carga dos veces", "Carga solo porque su plugin está activo y además está en el ini. No hace daño, pero gasta caracteres del ini.")},
    "lang-ini-hides": {
        "en": ("{ini} hides {n} BSAs of {key}", "On Switch the language ini loads after Skyrim.ini and replaces this list, so these BSAs from Skyrim.ini don't load in that language: {items}."),
        "es": ("{ini} tapa {n} BSA de {key}", "En Switch el ini de idioma carga después de Skyrim.ini y reemplaza esta lista, así que estos BSA de Skyrim.ini no cargan en ese idioma: {items}.")},
    "lang-ini-differ": {
        "en": ("The language inis don't list the same BSAs", "{key} differs between language inis; whoever plays in another language won't get: {items}."),
        "es": ("Los inis de idioma no listan los mismos BSA", "{key} cambia entre inis de idioma; quien juegue en otro idioma no tendrá: {items}.")},
    "lang-ini-missing": {
        "en": ("No language ini in the pack", "Skyrim.ini lists mod BSAs in {key}, but the console's own Skyrim_<language>.ini replaces that list. Add the language ini from the clean dump (DBI) so these load: {items}."),
        "es": ("El pack no tiene ini de idioma", "Skyrim.ini lista BSA de mods en {key}, pero el Skyrim_<idioma>.ini de la consola reemplaza esa lista. Agrega el ini de idioma desde los inis limpios (DBI) para que carguen: {items}.")},
    "tex-diet": {
        "en": ("{name} can save texture memory", "About {before} of textures could go down to about {after}: uncompressed textures (like FaceGen tints) become BC, and oversized ones shrink to Koka's sizes. It needs texconv (and NvnTexpkg for best results)."),
        "es": ("{name} puede ahorrar memoria de texturas", "Cerca de {before} de texturas podrían bajar a unos {after}: las texturas sin comprimir (como los tintes faciales) pasan a BC y las muy grandes bajan a los tamaños de Koka. Necesita texconv (y NvnTexpkg para el mejor resultado).")},
    "tint-broken": {
        "en": ("{name}: {n} faces point to a missing tint", "Their FaceGen mesh asks for a tint under '{old}', which no archive in the pack has. The face can look dark or wrong. If the tint exists under the mesh's own plugin folder, the fix points it there."),
        "es": ("{name}: {n} caras apuntan a un tinte que no existe", "Su malla FaceGen pide un tinte en '{old}', que ningún archivo del pack tiene. La cara puede verse oscura o rara. Si el tinte existe en la carpeta del propio plugin, el arreglo la apunta ahí.")},
    "name-unsafe": {
        "en": ("{name} has characters Google Drive changes", "Drive turns apostrophes and some symbols into '_' when the pack is shared, and then the plugin stops loading. A full rename to '{to}' (plugin, BSAs, voice and FaceGen folders, tint paths, scripts, masters, load list) avoids it. Saves that already use it won't find it under the new name."),
        "es": ("{name} tiene caracteres que Google Drive cambia", "Drive convierte apóstrofos y algunos símbolos en '_' al compartir el pack y el plugin deja de cargar. Renombrarlo completo a '{to}' (plugin, BSA, carpetas de voces y FaceGen, rutas de tinte, scripts, masters, lista de carga) lo evita. Las partidas que ya lo usan no lo van a encontrar con el nombre nuevo.")},
    "bsa-disabled": {
        "en": ("{name} is switched off", "Its plugin is switched off with '#' in the list."),
        "es": ("{name} está apagado", "Su plugin está desactivado con '#' en la lista.")},
    "bsa-unloaded-near": {
        "en": ("{name} doesn't load", "It looks like '{near}', which is active; the names must match exactly."),
        "es": ("{name} no carga", "Se parece a '{near}', que sí está activo; el nombre debe coincidir exacto.")},
    "bsa-unloaded": {
        "en": ("{name} doesn't load", "No active plugin has its name and it isn't in the ini. It takes {size} on the SD."),
        "es": ("{name} no carga", "Ningún plugin activo tiene su nombre y no está en el ini. Ocupa {size} en la SD.")},
    "bsa-bad": {
        "en": ("Couldn't read {name}", "{error}"),
        "es": ("No pude leer {name}", "{error}")},
    "bsa-big": {
        "en": ("{name} is over 2 GB", "BSAs can't be larger than 2 GB."),
        "es": ("{name} pasa de 2 GB", "Los BSA no pueden pasar de 2 GB.")},
    "bsa-owner": {
        "en": ("Orphaned voices or faces in {name}", "The plugin is called '{plugin}', but {n} voice or FaceGen files are under '{old}'. That's how voices get lost (the Auri case). The safest fix is to give the plugin back its original name; it costs {cost} more bytes in the list.{faces}"),
        "es": ("Voces o caras huérfanas en {name}", "El plugin se llama '{plugin}', pero {n} archivos de voz o FaceGen están bajo '{old}'. Así se pierden las voces (el caso Auri). Lo más seguro es devolverle al plugin su nombre original; cuesta {cost} bytes más en la lista.{faces}")},
    "faces-note": {
        "en": ("", " Moving the folders won't work here: the face models carry the old path inside."),
        "es": ("", " Mover las carpetas no sirve aquí: los modelos de cara llevan la ruta vieja por dentro.")},
    "bsa-dead": {
        "en": ("Files with no owner in {name}", "There are voices or faces for plugins that aren't active. They do no harm."),
        "es": ("Archivos sin dueño en {name}", "Hay voces o caras para plugins que no están activos. No estorban.")},
    "bsa-junk": {
        "en": ("{name}: {n} files the game doesn't use", "{name} includes script source code, backups or work images."),
        "es": ("{name}: {n} archivos que el juego no usa", "{name} trae código fuente de scripts, respaldos o imágenes de trabajo.")},
    "tex-pc": {
        "en": ("{name}: {n} textures in PC format", "They aren't in Switch's own format (DFvN). The Toolkit without the SDK leaves them like this and forces DXT5; if they show up purple or black, this is the suspect."),
        "es": ("{name}: {n} texturas en formato PC", "No están en el formato propio de Switch (DFvN). El Toolkit sin SDK las deja así y las fuerza a DXT5; si se ven moradas o negras, este es el sospechoso.")},
    "audio-broken": {
        "en": ("{name}: {n} sounds are damaged", "These files were read in full and don't hold together: cut short, a size that doesn't match, or a header the game doesn't know. The game can crash when it plays or closes one (Skyrim's crash report then points to the audio thread). Usually the download or the copy was cut; download the mod again and convert it."),
        "es": ("{name}: {n} sonidos están dañados", "Leí estos archivos completos y no cuadran: están cortados, tienen un tamaño que no coincide o una cabecera que el juego no conoce. El juego se puede cerrar al reproducir o cerrar uno (el reporte de crash de Skyrim apunta entonces al hilo de audio). Casi siempre se cortó la descarga o la copia; vuelve a bajar el mod y conviértelo.")},
    "audio-pc": {
        "en": ("{name}: {n} PC audio files", "They're PC XWMA or WAV. The converted mods we checked use Nintendo Opus or MCADPCM; they should be converted."),
        "es": ("{name}: {n} audios de PC", "Son XWMA o WAV de PC. Los mods convertidos que revisamos usan Opus o MCADPCM de Nintendo; conviene convertirlos.")},
    "tex-facetint": {
        "en": ("{size} in uncompressed face tints", "Face tints are RGBA at 4 bytes per pixel. They only weigh while that NPC is loaded; compressing them would save a lot, but it needs testing on the console."),
        "es": ("{size} en tintes faciales sin comprimir", "Los tintes de cara están en RGBA de 4 bytes por pixel. Solo pesan cuando ese NPC está cargado; comprimirlos ahorraría mucho, pero hay que probarlo en la consola.")},
    "orphan-files": {
        "en": ("{owner}: {n} files", ""),
        "es": ("{owner}: {n} archivos", "")},
    # ---- requirements
    "req-vanilla-unset": {
        "en": ("Vanilla files folder not set", "Set the folder with the console's vanilla BSAs in Settings to check missing textures, meshes and scripts."),
        "es": ("Falta la carpeta de archivos originales", "Elige en Ajustes la carpeta con los BSA originales de la consola para revisar texturas, mallas y scripts que falten.")},
    "req-vanilla-missing": {
        "en": ("The vanilla files folder doesn't exist", "{path} isn't there anymore. Choose it again in Settings to check missing textures, meshes and scripts."),
        "es": ("La carpeta de archivos originales no existe", "{path} ya no está. Vuelve a elegirla en Ajustes para revisar texturas, mallas y scripts que falten.")},
    "req-vanilla-empty": {
        "en": ("No vanilla BSAs in the chosen folder", "{path} has no readable BSA. Put the console's 'Skyrim - *.bsa' files there (from romfs\\Data) to check missing textures, meshes and scripts."),
        "es": ("La carpeta elegida no tiene BSA originales", "{path} no tiene ningún BSA que se pueda leer. Pon ahí los 'Skyrim - *.bsa' de la consola (de romfs\\Data) para revisar texturas, mallas y scripts que falten.")},
    "req-vanilla-partial": {
        "en": ("The game list is missing {n} of the game's BSAs", "It was never built with {names}. Files from them look missing, so some findings below may be false. Copy them from romfs\\Data to the game files folder once; the app keeps the list afterwards."),
        "es": ("A la lista del juego le faltan {n} BSA del juego", "Nunca se armó con {names}. Sus archivos parecen faltar, así que algunos avisos de abajo pueden ser falsos. Cópialos una vez desde romfs\\Data a la carpeta de archivos del juego; después la app conserva la lista.")},
    "req-script-fragment": {
        "en": ("{name}: {n} script fragments the author didn't include", "Fragments are the small scripts of a quest stage, a perk, a scene or a line of dialogue (QF_, PRKF_, SF_, TIF_...). These aren't in the mod's own files, so they're missing on PC too and there's nothing to add. If its other scripts are missing as well, its scripts BSA isn't loading."),
        "es": ("{name}: {n} fragmentos de script que el autor no incluyó", "Los fragmentos son los scripts pequeños de una etapa de misión, un perk, una escena o una línea de diálogo (QF_, PRKF_, SF_, TIF_...). No vienen en los archivos del mod, así que también faltan en PC y no hay nada que agregar. Si además faltan sus otros scripts, su BSA de scripts no está cargando.")},
    "req-tex-minor": {
        "en": ("{n} detail maps aren't there", "Relief (_p), shine (_m, _em, _s), glow (_g) or skin (_sk) maps that no BSA has. Without them those surfaces look flat or dull, never purple. Often it's the same on PC: the author's meshes ask for maps they didn't ship."),
        "es": ("No están {n} mapas de detalle", "Mapas de relieve (_p), brillo (_m, _em, _s), resplandor (_g) o piel (_sk) que ningún BSA tiene. Sin ellos esas superficies se ven planas u opacas, nunca moradas. Muchas veces pasa igual en PC: las mallas del autor piden mapas que no incluyó.")},
    "req-path-broken": {
        "en": ("{n} paths are typed wrong by the mod's author", "A space before the extension or next to a folder name, no extension, or a texture in a model field. No mod or game can have such a file, so it's the same on PC and there's nothing to add or fix here."),
        "es": ("{n} rutas que el autor del mod escribió mal", "Un espacio antes de la extensión o junto al nombre de una carpeta, sin extensión, o una textura donde va un modelo. Ningún mod ni el juego pueden tener ese archivo, así que pasa igual en PC y aquí no hay nada que agregar ni arreglar.")},
    "req-records-unreadable": {
        "en": ("{name}: some records couldn't be read", "{n} records couldn't be read, so their scripts and models weren't checked. {error}"),
        "es": ("{name}: no pude leer algunos registros", "No pude leer {n} registros, así que no revisé sus scripts ni sus modelos. {error}")},
    "req-script-missing": {
        "en": ("{name}: {n} scripts are missing", "Its records use scripts that aren't in any BSA that loads, in Data\\scripts or in the game. Those objects won't run their script: quests may not start and effects may do nothing. Usually the mod needs another mod that isn't in the pack."),
        "es": ("{name}: faltan {n} scripts", "Sus registros usan scripts que no están en ningún BSA que cargue, ni en Data\\scripts, ni en el juego. Esos objetos no van a ejecutar su script: puede que una misión no arranque o que un efecto no haga nada. Casi siempre el mod necesita otro mod que no está en el pack.")},
    "req-script-pconly": {
        "en": ("{name}: {n} PC menu scripts aren't there (expected)", "They belong to SkyUI's mod menu (MCM) or to SKSE, which only exist on PC. On Switch the mod works without its settings menu; nothing else is missing."),
        "es": ("{name}: no están {n} scripts del menú de PC (es normal)", "Son del menú de mods de SkyUI (MCM) o de SKSE, que solo existen en PC. En Switch el mod funciona sin su menú de ajustes; no falta nada más.")},
    "req-script-parent": {
        "en": ("{name}: {n} scripts are built on a missing script", "They extend {parents}, which isn't in the pack or in the game, so they won't run. It's usually SkyUI's menu (SKI_ConfigBase) or an SKSE library, and Switch has neither."),
        "es": ("{name}: {n} scripts dependen de un script que no está", "Extienden {parents}, que no está en el pack ni en el juego, así que no van a funcionar. Suele ser el menú de SkyUI (SKI_ConfigBase) o una librería de SKSE, y Switch no tiene ninguno de los dos.")},
    "script-skse-base": {
        "en": ("{name} brings SKSE's base scripts from PC ({n})", "It carries the PC copy of the scripts every other script is built on (Quest, Actor, ObjectReference, Game, Form...), as SKSE installs them. They aren't the mod's own: they slipped in when it was packed. On Switch they take the place of the game's own, which have functions the PC ones lack, and SKSE's additions don't exist without SKSE. Quests can stall and scripts fail anywhere in the game. Taking them out of the BSA leaves the rest of the mod as it is."),
        "es": ("{name} trae los scripts base de SKSE de PC ({n})", "Trae la copia de PC de los scripts sobre los que se construyen todos los demás (Quest, Actor, ObjectReference, Game, Form...), tal como los instala SKSE. No son del mod: se colaron al empacarlo. En Switch reemplazan a los del juego, que tienen funciones que los de PC no tienen, y lo que agrega SKSE no existe sin SKSE. Las misiones se pueden atascar y los scripts fallar en cualquier parte del juego. Sacarlos del BSA deja el resto del mod como está.")},
    "script-replaces-ussep": {
        "en": ("{n} scripts fixed by USSEP are replaced by other mods: {mods}", "These mods bring their own copy of scripts that USSEP fixes, and theirs is the one that runs. That's fine when the mod was built on top of USSEP; when it wasn't (or its copy is older), USSEP's fixes for those scripts are lost and the quest or object they belong to can get stuck. On Switch a BSA in the ini wins over the game's and over the BSAs plugins load, whatever the load list says. If a quest of the base game stalls, look here first."),
        "es": ("{n} scripts que USSEP corrige quedan reemplazados por otros mods: {mods}", "Estos mods traen su propia copia de scripts que USSEP corrige, y la que corre es la suya. Está bien si el mod se hizo sobre USSEP; si no (o si su copia es más vieja), se pierden los arreglos de USSEP para esos scripts y la misión u objeto al que pertenecen se puede quedar atascado. En Switch un BSA del ini gana sobre el juego y sobre los BSA que cargan los plugins, diga lo que diga la lista de carga. Si una misión del juego base se queda quieta, mira aquí primero.")},
    "script-replaces-game": {
        "en": ("{n} game scripts are replaced by {mods} mods", "Each line is a mod and the game's scripts it brings its own copy of (its copy is the one that runs). It's how many mods work, so it isn't a problem by itself. If a quest or object of the base game misbehaves, these are the mods to suspect first."),
        "es": ("{mods} mods reemplazan {n} scripts del juego", "Cada línea es un mod y los scripts del juego de los que trae su propia copia (la suya es la que corre). Así funcionan muchos mods, así que no es un problema por sí solo. Si una misión u objeto del juego base se porta raro, estos son los primeros sospechosos.")},
    "script-plugin-off": {
        "en": ("Scripts ask for {n} plugins that aren't loaded: {list}", "These scripts look for a plugin by its name. [off] means it's in the pack but switched off; [gone] means it isn't in the pack. Most of the time it's an optional check (\"if this mod is installed, also do this\") and nothing happens. It matters after removing a mod: a script left behind that was built around it can stop halfway."),
        "es": ("Hay scripts que buscan {n} plugins que no cargan: {list}", "Estos scripts buscan un plugin por su nombre. [off] quiere decir que está en el pack pero apagado; [gone], que no está en el pack. Casi siempre es una revisión opcional (\"si este mod está, haz esto también\") y no pasa nada. Importa después de quitar un mod: un script que quedó y estaba hecho para ese mod se puede quedar a mitad de camino.")},
    "script-load": {
        "en": ("Mods that keep scripts running on their own: {top} first", "For each mod: how many of its scripts run, how many repeat on a timer, how many wait for a single timer, and how many react to frequent events (hits, equipping, items, changing places). A guide, not a measurement: it counts what the scripts can do, not how often they run in your game. The Switch has little CPU for scripts; when quests stall or scripts lag, the mods at the top cost the most."),
        "es": ("Mods que mantienen scripts corriendo solos: primero {top}", "Para cada mod: cuántos de sus scripts corren, cuántos se repiten con un temporizador, cuántos esperan un temporizador de una vez, y cuántos reaccionan a eventos frecuentes (golpes, equipar, objetos, cambiar de lugar). Es una guía, no una medida: cuenta lo que los scripts pueden hacer, no cuántas veces corren en tu partida. La Switch tiene poca CPU para scripts; cuando las misiones se atascan o los scripts van tarde, los de arriba son los que más cuestan.")},
    "req-mesh-missing": {
        "en": ("{name}: {n} models are missing", "Its records point to meshes that aren't in any BSA that loads, in Data or in the game. In game they show up invisible or as a red exclamation mark, and some can crash it. Usually the mod needs another mod, or its BSA isn't loading."),
        "es": ("{name}: faltan {n} modelos", "Sus registros apuntan a mallas que no están en ningún BSA que cargue, ni en Data, ni en el juego. En el juego se ven invisibles o como un signo de exclamación rojo, y algunas pueden cerrarlo. Casi siempre el mod necesita otro mod, o su BSA no está cargando.")},
    "req-tex-missing": {
        "en": ("{name}: {n} textures are missing", "Meshes in this BSA use textures that aren't in any BSA that loads, in Data or in the game. Those surfaces will look purple or blank."),
        "es": ("{name}: faltan {n} texturas", "Las mallas de este BSA usan texturas que no están en ningún BSA que cargue, ni en Data, ni en el juego. Esas superficies se van a ver moradas o en blanco.")},
    "req-anim-framework": {
        "en": ("{name} has animations for {kinds}", "{n} files are for animation frameworks that need SKSE ({kinds}). Switch has no SKSE, so those animations won't play; they only take space."),
        "es": ("{name} trae animaciones para {kinds}", "{n} archivos son para sistemas de animación que necesitan SKSE ({kinds}). Switch no tiene SKSE, así que esas animaciones no se van a ver; solo ocupan espacio.")},
    "req-behavior-conflict": {
        "en": ("{name} replaces {n} behavior files", "These behavior files also come in {others} with different content. Only the last one loaded counts, the one in {name}. On PC FNIS or Nemesis would combine them; on Switch they can't be merged, so animations from the other mods may not play."),
        "es": ("{name} reemplaza {n} archivos de comportamiento", "Estos archivos de comportamiento también vienen en {others} con otro contenido. Solo cuenta el último que carga, el de {name}. En PC FNIS o Nemesis los combinan; en Switch no se pueden unir, así que las animaciones de los otros mods pueden no verse.")},
    # ---- duplicates
    "dup-plugin-same": {
        "en": ("The same plugin loads twice: {name}", "{other} has exactly the same content and also loads. Its new items, spells and quests exist twice and its scripts may run twice. Keep only one."),
        "es": ("El mismo plugin carga dos veces: {name}", "{other} tiene exactamente el mismo contenido y también carga. Sus objetos, hechizos y misiones nuevos quedan repetidos y sus scripts pueden correr dos veces. Deja solo uno.")},
    "dup-plugin-name": {
        "en": ("The same plugin loads twice: {name}", "{other} has the same name except for Google Drive's damage (apostrophes turned into '_'), and both are in the load list. Its records load twice. Keep only the one whose name matches the original."),
        "es": ("El mismo plugin carga dos veces: {name}", "{other} tiene el mismo nombre salvo por el daño de Google Drive (apóstrofos convertidos en '_'), y los dos están en la lista de carga. Sus registros cargan dos veces. Deja solo el que tenga el nombre original.")},
    "dup-plugin-copy": {
        "en": ("{name} is a copy of {other}", "It has exactly the same content as {other}, which is the one that loads. It takes {size} on the SD."),
        "es": ("{name} es una copia de {other}", "Tiene exactamente el mismo contenido que {other}, que es el que carga. Ocupa {size} en la SD.")},
    "dup-bsa": {
        "en": ("{name} and {other} are the same", "Both BSAs have the same {files} files with the same sizes, and both load. It's the same mod twice: the earlier copy does nothing and only takes space."),
        "es": ("{name} y {other} son iguales", "Los dos BSA tienen los mismos {files} archivos con los mismos tamaños y los dos cargan. Es el mismo mod dos veces: la copia que carga primero no sirve de nada y solo ocupa espacio.")},
    "dup-merged": {
        "en": ("{name} is also inside {merged}", "{merged} is a merged plugin that already contains {name}, and {name} also loads as a full plugin ({records} records). Its records load twice (the later one wins), new items and quests exist twice and scripts may run twice. Take it out of the load list; if another plugin uses it as a master, replace it with an empty placeholder."),
        "es": ("{name} también está dentro de {merged}", "{merged} es un plugin fusionado que ya contiene {name}, y {name} además carga completo ({records} registros). Sus registros cargan dos veces (gana el último), los objetos y misiones nuevos quedan repetidos y los scripts pueden correr dos veces. Sácalo de la lista de carga; si otro plugin lo usa como master, cámbialo por un plugin vacío.")},
    "draft-parked": {
        "en": ("{n} mods marked as not going", "They stay in Data while you decide, out of the load list and the inis. The Doctor leaves them alone, and Create modpack doesn't copy them: {names}."),
        "es": ("{n} mods marcados para no ir", "Siguen en Data mientras decides, fuera de la lista de carga y de las inis. El Doctor no los toca y Crear modpack no los copia: {names}.")},
    "dup-ignored": {
        "en": ("{n} duplicates you chose to keep", "The Doctor doesn't warn about them anymore. If you change your mind, show them again."),
        "es": ("{n} duplicados que decidiste dejar", "El Doctor ya no avisa de ellos. Si cambias de idea, vuelve a mostrarlos.")},
    "dup-merged-copy": {
        "en": ("{name} is already inside {merged}", "It isn't in the load list, and that's right: the merged plugin {merged} already contains it. It takes {size} on the SD."),
        "es": ("{name} ya está dentro de {merged}", "No está en la lista de carga, y está bien así: el plugin fusionado {merged} ya lo contiene. Ocupa {size} en la SD.")},
    "mod-unconverted": {
        "en": ("{name} looks like a PC mod", "{detail}"),
        "es": ("{name} parece un mod de PC", "{detail}")},
    # KokaNX (Oct 2026)
    "ini-memory-mods": {
        "en": ("{n} mod BSAs are kept in memory", "sArchiveToLoadInMemoryList in {inis} holds {items}{size_en}. KokaNX tested in October 2026 that animation BSAs only need sResourceArchiveList: the in-memory list just keeps them in RAM for the whole game. The game's own entries stay as they are. If T-poses or animation stutters show up after taking them out, put them back in that list."),
        "es": ("{n} BSA de mods se quedan en memoria", "sArchiveToLoadInMemoryList en {inis} tiene {items}{size_es}. KokaNX probó en octubre de 2026 que los BSA de animaciones solo necesitan sResourceArchiveList: la lista en memoria solo los deja en la RAM durante toda la partida. Las entradas del juego quedan como están. Si después de sacarlos aparecen T-poses o tirones en las animaciones, vuelve a ponerlos en esa lista.")},
    "font-in-bsa": {
        "en": ("A font's FontConfig.txt is inside {bsa}", "Font mods only take effect with Interface\\FontConfig.txt loose in Data (the Switch port of Sovngarde says so in its readme). Inside a BSA the game keeps its own font."),
        "es": ("El FontConfig.txt de una fuente está dentro de {bsa}", "Las fuentes solo se aplican con Interface\\FontConfig.txt suelto en Data (el port de Switch de Sovngarde lo dice en su readme). Dentro de un BSA el juego sigue con su fuente.")},
    "font-missing-lib": {
        "en": ("FontConfig.txt names {n} font file(s) that aren't in the pack", "It asks for {items}. A font library that doesn't exist leaves the text that uses it blank. Add the font mod's BSA, or take FontConfig.txt out of Data\\Interface."),
        "es": ("FontConfig.txt pide {n} archivo(s) de fuente que no están en el pack", "Pide {items}. Si una librería de fuente no existe, el texto que la usa queda en blanco. Agrega el BSA del mod de fuente o saca FontConfig.txt de Data\\Interface.")},
    "plugin-lowid-nx": {
        "en": ("{name} uses record IDs the Switch may not understand", "{n} of its records use IDs below 0x800, the extended ESL range Skyrim PC added in version 1.6.1130 (December 2023). The Switch version came out in 2022, so it probably can't load them: things from this mod may be missing or the game may crash. Test it on the console; if it fails, use a version of the mod from before December 2023."),
        "es": ("{name} usa IDs de registro que la Switch quizá no entiende", "{n} de sus registros usan IDs por debajo de 0x800, el rango ESL extendido que Skyrim PC agregó en la versión 1.6.1130 (diciembre de 2023). La versión de Switch salió en 2022, así que probablemente no los carga: pueden faltar cosas del mod o cerrarse el juego. Pruébalo en la consola; si falla, usa una versión del mod anterior a diciembre de 2023.")},
    "plugin-hedr171-se": {
        "en": ("{name} has header version 1.71", "It was saved with a newer Creation Kit (1.6.1130 or later), and the SE version can ignore plugins with version 1.71. KokaNX's fix is to set it to 1.70 in SSEEdit; this does the same and changes only the 4 bytes of that number.{low_en}"),
        "es": ("{name} tiene encabezado versión 1.71", "Se guardó con un Creation Kit más nuevo (1.6.1130 o posterior), y la versión SE puede ignorar plugins con versión 1.71. El arreglo de KokaNX es ponerle 1.70 en SSEEdit; esto hace lo mismo y solo cambia los 4 bytes de ese número.{low_es}")},
    "hedr-low": {
        "en": ("", " Careful: {k} of its own records use FormIDs below 0x800, which only version 1.71 allows. With 1.70 those records may not work; renumber them in SSEEdit (Compact FormIDs for ESL) before saving it as 1.70."),
        "es": ("", " Ojo: {k} de sus propios registros usan FormID por debajo de 0x800, que solo permite la versión 1.71. Con 1.70 esos registros pueden fallar; conviene renumerarlos en SSEEdit (Compact FormIDs for ESL) antes de dejarlo en 1.70.")},
    "seq-missing": {
        "en": ("{name} has no SEQ file", "It has {n} Start Game Enabled quests, and the game needs seq\\{seq} (inside its BSA or loose in Data) to start them. Without it, NPC dialogue and those quests may not start. The file is what xEdit's Create SEQ File writes: the FormIDs of those quests, 4 bytes each."),
        "es": ("{name} no tiene archivo SEQ", "Tiene {n} misiones con Start Game Enabled y el juego necesita seq\\{seq} (dentro de su BSA o suelto en Data) para arrancarlas. Sin él, los diálogos de los NPC y esas misiones pueden no arrancar. El archivo es el que genera Create SEQ File en xEdit: los FormID de esas misiones, 4 bytes cada uno.")},
    "seq-differ": {
        "en": ("{name}'s SEQ doesn't match its quests", "seq\\{seq} in {where} lists {have} quests, and the plugin has {want} Start Game Enabled quests. Missing: {missing}. Extra: {extra}. A quest missing from the SEQ may not start."),
        "es": ("El SEQ de {name} no coincide con sus misiones", "seq\\{seq} en {where} trae {have} misiones, y el plugin tiene {want} con Start Game Enabled. Faltan: {missing}. Sobran: {extra}. Una misión que falte en el SEQ puede no arrancar.")},
    "ussep-bsa-order": {
        "en": ("USSEP's BSAs aren't right after the game's", "KokaNX's advice: USSEP's BSAs go right after the game's own BSAs in each list (Skyrim.ini sResourceArchiveList for scripts, meshes and animations; Skyrim_en.ini sResourceArchiveList2 for textures and voices), so every other mod can override its files. Out of place in: {where}."),
        "es": ("Los BSA de USSEP no van justo después de los del juego", "Consejo de KokaNX: los BSA de USSEP van justo después de los BSA del juego en cada lista (sResourceArchiveList de Skyrim.ini para scripts, mallas y animaciones; sResourceArchiveList2 de Skyrim_en.ini para texturas y voces), así cualquier otro mod puede reemplazar sus archivos. Fuera de lugar en: {where}.")},
    "ussep-first": {
        "en": ("USSEP isn't the first mod in {list}", "KokaNX's advice: {name} goes first in the load list, right after the Creation Club entries (AE) or at the top of Plugins (SE), so every other mod and patch loads after it. Now {n} mods load before it, starting with {before}."),
        "es": ("USSEP no es el primer mod de {list}", "Consejo de KokaNX: {name} va primero en la lista de carga, justo después de las entradas del Creation Club (AE) o arriba del todo en Plugins (SE), así todos los demás mods y parches cargan después. Ahora cargan {n} mods antes, empezando por {before}.")},
}

# Fix labels and preview lines
LABEL = {
    "fix-bom": {"en": "Remove the mark", "es": "Quitar la marca"},
    "fix-ws": {"en": "Trim spaces", "es": "Limpiar espacios"},
    "fix-nl": {"en": "Use CRLF everywhere", "es": "Unificar a CRLF"},
    "fix-lf": {"en": "Convert to LF", "es": "Convertir a LF"},
    "fix-dedupe": {"en": "Keep only the first", "es": "Dejar solo la primera"},
    "fix-rename-to": {"en": "Rename to '{to}'", "es": "Renombrar a '{to}'"},
    "fix-rename-files": {"en": "Rename files to '{to}'", "es": "Renombrar archivos a '{to}'"},
    "fix-trash": {"en": "Move to the project trash", "es": "Mover a la papelera del proyecto"},
    "fix-write": {"en": "Write '{to}'", "es": "Escribir '{to}'"},
    "fix-write-list": {"en": "Write '{to}' in the list", "es": "Escribir '{to}' en la lista"},
    "fix-remove": {"en": "Remove from the list", "es": "Quitar de la lista"},
    "fix-activate": {"en": "Activate in the list", "es": "Activarlo en la lista"},
    "fix-dummy": {"en": "Move its BSA to the ini", "es": "Pasar su BSA al ini"},
    "fix-master-retarget": {"en": "Point it at {to}", "es": "Apuntarlo a {to}"},
    "fix-list-shorten": {"en": "Shorten the {n} names (frees {saved} bytes)", "es": "Acortar los {n} nombres (libera {saved} bytes)"},
    "fix-cc-not-in-game": {"en": "Take out the {n} lines", "es": "Quitar las {n} líneas"},
    "fix-drop-skse": {"en": "Take out the {n} SKSE scripts", "es": "Sacar los {n} scripts de SKSE"},
    "fix-off-without-file": {"en": "Take out the {n} lines", "es": "Quitar las {n} líneas"},
    "fix-names": {"en": "Use the game's names ({n})", "es": "Usar los nombres del juego ({n})"},
    "fix-add-cc": {"en": "Add {to}", "es": "Agregar {to}"},
    "fix-add-cc-n": {"en": "Add the {n} to the list", "es": "Agregar los {n} a la lista"},
    "fix-take-out": {"en": "Take {name} out of the list", "es": "Sacar {name} de la lista"},
    "fix-move-after": {"en": "Move {name} after {to}", "es": "Mover {name} después de {to}"},
    "fix-ini-remove": {"en": "Remove it from the ini", "es": "Quitarlo del ini"},
    "fix-ini-add-after": {"en": "Put the {n} BSAs in the ini", "es": "Poner los {n} BSA en el ini"},
    "fix-ini-shorten": {"en": "Shorten {n} BSA names (frees {saved} characters)", "es": "Acortar {n} nombres de BSA (libera {saved} caracteres)"},
    "fix-drop-junk": {"en": "Remove the {n} unused files", "es": "Quitar los {n} archivos que no se usan"},
    "fix-tints": {"en": "Point {n} faces to their tint", "es": "Apuntar {n} caras a su tinte"},
    "fix-diet": {"en": "Shrink textures (about {after})", "es": "Reducir texturas (a unos {after})"},
    "fix-diet-rule": {"en": "Shrink textures ({rule})", "es": "Reducir texturas ({rule})"},
    "fix-safe-name": {"en": "Rename everything to '{to}'", "es": "Renombrar todo a '{to}'"},
    "fix-dup-keep-only": {"en": "Keep only {name}", "es": "Dejar solo {name}"},
    "fix-dup-keep-both": {"en": "Keep both", "es": "Dejar los dos"},
    "fix-dup-keep-all": {"en": "Keep them all", "es": "Dejarlos todos"},
    "fix-dup-delete-copy": {"en": "Delete the copy", "es": "Borrar la copia"},
    "fix-dup-remove-loose": {"en": "Take out the loose {name}", "es": "Quitar el {name} suelto"},
    "fix-dup-empty-loose": {"en": "Empty the loose {name}", "es": "Vaciar el {name} suelto"},
    "fix-dup-unignore": {"en": "Show them again", "es": "Volver a mostrarlos"},
    "fix-lang-copy": {"en": "Add them to {ini}", "es": "Agregarlos a {ini}"},
    "fix-restore-name": {"en": "Give it back the name '{to}'", "es": "Devolverle el nombre '{to}'"},
    "fix-move-voices": {"en": "Move the voices to '{to}'", "es": "Mover las voces a '{to}'"},
    "fix-memory-out": {"en": "Take them out of the in-memory list", "es": "Sacarlos de la lista en memoria"},
    "fix-font-loose": {"en": "Put it loose in Data\\Interface", "es": "Dejarlo suelto en Data\\Interface"},
    "fix-hedr-170": {"en": "Set the version to 1.70", "es": "Ponerle versión 1.70"},
    "fix-seq-add": {"en": "Create the SEQ in {bsa}", "es": "Crear el SEQ en {bsa}"},
    "fix-esl-esp": {"en": "Turn it into {to} for SE", "es": "Pasarlo a {to} para SE"},
    "fix-archive-extract": {"en": "Extract {name} into Data", "es": "Extraer {name} en Data"},
    "fix-seq-rewrite": {"en": "Rewrite the SEQ", "es": "Reescribir el SEQ"},
    "fix-ussep-bsas": {"en": "Move them right after the game's BSAs", "es": "Moverlos justo después de los BSA del juego"},
    "fix-move-first": {"en": "Move {name} to the top", "es": "Mover {name} al principio"},
}

PREVIEW = {
    "pv-replace": {"en": "{file}: '{old}' → '{new}'", "es": "{file}: '{old}' → '{new}'"},
    "pv-remove": {"en": "{file}: remove the line '{name}'", "es": "{file}: quitar la línea '{name}'"},
    "pv-dedupe": {"en": "{file}: keep '{name}' only once", "es": "{file}: dejar una sola vez '{name}'"},
    "pv-add": {"en": "{file}: add '{name}' after its last master", "es": "{file}: agregar '{name}' después de su último master"},
    "pv-insert": {"en": "{file}: add '{name}' before '{before}'", "es": "{file}: agregar '{name}' antes de '{before}'"},
    "pv-move": {"en": "{file}: move '{name}' right after '{after}'", "es": "{file}: mover '{name}' justo después de '{after}'"},
    "pv-rewrite": {"en": "{file}: rewrite cleanly (same names, same order)", "es": "{file}: reescribir con formato limpio (mismos nombres, mismo orden)"},
    "pv-ini-short": {"en": "ini: the list gets {n} characters shorter; the BSAs load in the same place, only their names change", "es": "ini: la lista queda {n} caracteres más corta; los BSA cargan en el mismo lugar, solo cambia su nombre"},
    "pv-rename": {"en": "Data: '{old}' → '{new}'", "es": "Data: '{old}' → '{new}'"},
    "pv-master": {"en": "{file}: update its master to '{new}'", "es": "{file}: actualizar su master a '{new}'"},
    "pv-voices": {"en": "{file}: voices from '…\\{old}\\' → '…\\{new}\\'", "es": "{file}: voces de '…\\{old}\\' → '…\\{new}\\'"},
    "pv-rebuild": {"en": "The BSA is rebuilt copying the same data; the original stays in the history.", "es": "Se reconstruye el BSA copiando los mismos datos; el original queda en el historial."},
    "pv-trash": {"en": "Data: move '{name}' to .skynx\\trash (can be undone)", "es": "Data: mover '{name}' a .skynx\\trash (se puede deshacer)"},
    "pv-ini-remove": {"en": "ini, {key}: remove '{name}'", "es": "ini, {key}: quitar '{name}'"},
    "pv-ini-add": {"en": "ini, {key}: add '{name}'", "es": "ini, {key}: agregar '{name}'"},
    "pv-drop-skse": {"en": "{file}: remove the {n} SKSE base scripts (and their sources)", "es": "{file}: quitar los {n} scripts base de SKSE (y sus fuentes)"},
    "pv-drop-junk": {"en": "{file}: remove {n} files the game doesn't use (.psc sources, backups...)", "es": "{file}: quitar {n} archivos que el juego no usa (fuentes .psc, respaldos...)"},
    "pv-tint": {"en": "{file}: {nif} → tint from '{old}' to '{new}'", "es": "{file}: {nif} → tinte de '{old}' a '{new}'"},
    "pv-diet": {"en": "{file}: textures shrunk with the '{preset}' sizes", "es": "{file}: texturas reducidas con los tamaños '{preset}'"},
    "pv-diet-how": {"en": "Uncompressed textures become BC (BC1 if opaque); oversized ones lose their largest mips or get resized. The original stays in the history.", "es": "Las texturas sin comprimir pasan a BC (BC1 si son opacas); las muy grandes pierden sus mips más grandes o se redimensionan. El original queda en el historial."},
    "pv-inside": {"en": "{file}: folders, tint paths and scripts that say '{old}' → '{new}'", "es": "{file}: carpetas, rutas de tinte y scripts que dicen '{old}' → '{new}'"},
    "pv-saves": {"en": "Saves that already use this plugin won't find it under the new name.", "es": "Las partidas que ya usan este plugin no lo van a encontrar con el nombre nuevo."},
    "pv-ini-remove-any": {"en": "inis: take '{name}' out of the archive lists", "es": "inis: sacar '{name}' de las listas de archivos"},
    "pv-dup-keep": {"en": "Doctor: stop warning about this duplicate; nothing in the pack changes", "es": "Doctor: no volver a avisar de este duplicado; no cambia nada del pack"},
    "pv-dup-unkeep": {"en": "Doctor: warn again about {n} duplicates", "es": "Doctor: volver a avisar de {n} duplicados"},
    "pv-dup-placeholder": {"en": "Data: '{name}' becomes an empty plugin (only its header and masters). Its records stop loading twice, its BSAs keep loading for the merge{deps}", "es": "Data: '{name}' queda como plugin vacío (solo encabezado y masters). Sus registros dejan de cargar dos veces y sus BSA siguen cargando para el merge{deps}"},
    "pv-ini-add-in": {"en": "{ini}, {key}: add '{name}'", "es": "{ini}, {key}: agregar '{name}'"},
    "pv-ini-remove-in": {"en": "{ini}, {key}: remove '{name}'", "es": "{ini}, {key}: quitar '{name}'"},
    "pv-memory-back": {"en": "If T-poses or animation stutters show up, put them back in sArchiveToLoadInMemoryList (or undo this from the history).", "es": "Si aparecen T-poses o tirones en las animaciones, vuelve a ponerlos en sArchiveToLoadInMemoryList (o deshaz este cambio desde el historial)."},
    "pv-font-loose": {"en": "Copy Interface\\FontConfig.txt out of {bsa}, loose to Data\\Interface", "es": "Copiar Interface\\FontConfig.txt de {bsa}, suelto a Data\\Interface"},
    "pv-list-shorten": {"en": "Each one also updates the plugins that use it as a master, its BSAs, voices, faces, SEQ and scripts, and the load list.", "es": "Cada uno actualiza además los plugins que lo usan como master, sus BSA, voces, caras, SEQ y scripts, y la lista de carga."},
    "pv-names": {"en": "{file}: {n} names go back to the game's (only the names change):", "es": "{file}: {n} nombres vuelven a los del juego (solo cambian los nombres):"},
    "pv-master-retarget": {"en": "{file}: master {old} → {new} (renamed in this pack; only the name in its header changes)", "es": "{file}: master {old} → {new} (renombrado en este pack; solo cambia el nombre en su encabezado)"},
    "pv-hedr": {"en": "{file}: header version {old} → {new} (only those 4 bytes change)", "es": "{file}: versión del encabezado {old} → {new} (solo cambian esos 4 bytes)"},
    "pv-esl-flag": {"en": "{name}: clear the ESL flag (and HEDR 1.71 to 1.70)", "es": "{name}: quitar la marca ESL (y HEDR 1.71 a 1.70)"},
    "pv-extract": {"en": "Data: take {files} out of {name}", "es": "Data: sacar {files} de {name}"},
    "pv-extract-list": {"en": "{file}: activate {names}", "es": "{file}: activar {names}"},
    "pv-extract-loose": {"en": "{n} loose files stay out (they'd need packing into a BSA)", "es": "{n} archivos sueltos quedan por fuera (habría que empacarlos en un BSA)"},
    "pv-extract-trash": {"en": "{name} goes to the project's trash", "es": "{name} pasa a la papelera del proyecto"},
    "pv-seq-add": {"en": "{file}: add seq\\{seq} with {n} quests", "es": "{file}: agregar seq\\{seq} con {n} misiones"},
    "pv-seq-replace": {"en": "{file}: replace seq\\{seq} with one that lists {n} quests", "es": "{file}: reemplazar seq\\{seq} por uno con {n} misiones"},
    "pv-seq-new": {"en": "Data: create '{file}' with seq\\{seq} ({n} quests); it loads with {plugin}", "es": "Data: crear '{file}' con seq\\{seq} ({n} misiones); carga junto con {plugin}"},
    "pv-seq-loose": {"en": "Data\\seq: write '{seq}' with {n} quests", "es": "Data\\seq: escribir '{seq}' con {n} misiones"},
    "pv-ini-order": {"en": "{ini}, {key}: {items} right after the game's BSAs", "es": "{ini}, {key}: {items} justo después de los BSA del juego"},
    "pv-move-first": {"en": "{file}: move '{name}' to the first line", "es": "{file}: mover '{name}' a la primera línea"},
    "pv-ini-keep": {"en": "{ini}, {key}: add '{name}' so it keeps loading", "es": "{ini}, {key}: agregar '{name}' para que siga cargando"},
}


def msg(_key: str, _lang: str, **kw) -> tuple[str, str]:
    lang = _lang if _lang in LANGS else "en"
    title, detail = MSG[_key][lang]
    return title.format(**kw), detail.format(**kw)


def label(_key: str, _lang: str, **kw) -> str:
    lang = _lang if _lang in LANGS else "en"
    return LABEL[_key][lang].format(**kw)


def pv(_key: str, _lang: str, **kw) -> str:
    lang = _lang if _lang in LANGS else "en"
    return PREVIEW[_key][lang].format(**kw)


SEVERITIES = {"critico": {"en": "Serious", "es": "Grave"}, "aviso": {"en": "Check", "es": "Revisar"},
              "ahorro": {"en": "Savings", "es": "Ahorro"}, "info": {"en": "Info", "es": "Dato"}}


def severity(key: str, lang: str) -> str:
    return SEVERITIES.get(key, {}).get(lang if lang in LANGS else "en", key)


def cat(key: str, lang: str) -> str:
    lang = lang if lang in LANGS else "en"
    return CATEGORIES[key][lang]


def note(key: str, lang: str, on: bool) -> str:
    """Optional sentence appended to a detail (stored as the second slot)."""
    return MSG[key][lang if lang in LANGS else "en"][1] if on else ""


# Progress labels. Library code reports progress in English (a fixed word like
# "textures", or a verb and a file name like "Copying Mod.bsa"); the app turns
# them into the interface language here, in one place.
PROGRESS_WORDS = {"textures": "texturas", "sounds": "sonidos", "assets": "archivos",
                  "workspace": "mesa de trabajo", "plan": "plan", "masterlist": "masterlist"}
PROGRESS_VERBS = {"Backing up ": "Respaldando ", "Comparing ": "Comparando ", "Copying ": "Copiando ",
                  "Removing ": "Quitando ", "Renaming ": "Renombrando ", "Updating ": "Actualizando ",
                  "Checking the pack again": "Revisando el pack otra vez"}


def progress_label(text: str, lang: str) -> str:
    """The progress text in the interface language (unknown text unchanged)."""
    if lang != "es" or not isinstance(text, str):
        return text
    if text in PROGRESS_WORDS:
        return PROGRESS_WORDS[text]
    for en, es in PROGRESS_VERBS.items():
        if text.startswith(en):
            return es + text[len(en):]
    return text
