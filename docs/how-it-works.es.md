# Cómo funciona SwitchNX Studio

Qué le hace la app a tus archivos, función por función: qué entra, los pasos (con el módulo de `skynx/` que los ejecuta), la herramienta externa que usa, si usa alguna, y qué sale. La interfaz en `app/web` solo llama a estos módulos.

Dos reglas valen para todo. **Los archivos de origen nunca se modifican:** un mod se extrae o se copia primero a una carpeta temporal de trabajo, y los BSA que arregla el Doctor se reconstruyen como archivos nuevos que luego toman el lugar del original. **Cada cambio en un pack queda registrado** y se puede deshacer (sección 11).

## Herramientas externas

La app busca una sola carpeta de herramientas: `tools` junto al programa o `C:\SkyNX\Tools` (`skynx/tools.py`). No descarga nada. Las herramientas corren sin ventana de consola, y si una falla, su mensaje de error queda en el informe.

- **texconv:** formato, tamaño y mipmaps de las texturas de PC.
- **ffmpeg** y **VGAudioCli** (con VGAudio.dll): audio. Hacen falta las dos; sin alguna, los sonidos quedan como venían.
- **NvnTexpkg** (con sus cuatro DLL): texturas nativas de Switch. Es parte del SDK de Nintendo; la pones tú y la app nunca la incluye. Sin ella, las texturas convertidas quedan como DDS de PC.
- **HavokBehaviorPostProcess.exe** (Creation Kit de Bethesda) y **hkxc.exe** (serde-hkx): archivos de Havok que un parche de bytes no alcanza a convertir.
- **Nemesis:** generación de comportamientos para mods de FNIS y Nemesis.

## 1. Convertir un mod

**Entra:** un mod de PC para Skyrim SE o AE (`.zip`, `.7z` o carpeta). **Sale:** sus plugins y sus BSA de Switch dentro del pack abierto, como un solo paso que se puede deshacer. Módulo: `skynx/converter.py`, en dos llamadas.

**Analizar** no escribe nada en el pack:

1. El mod se extrae en una carpeta temporal (`skynx-conv-…`) y se rechazan las rutas que intenten salirse de ella. Si trae instalador FOMOD, la app muestra sus pasos e instala ahí lo que elijas (`skynx/fomod.py`). Si la descarga trae versiones AE y SE lado a lado, se usa la que corresponde a la edición del pack (`skynx/variants.py`).
2. La raíz del mod (la carpeta menos profunda que tenga un plugin, un BSA o una carpeta del juego) se copia a una carpeta `data` de trabajo. Se conservan los plugins, los BSA y las carpetas del juego (`meshes`, `textures`, `sound`, `music`, `scripts`, `interface`, `seq`, `strings`…). Quedan por fuera carpetas como `fomod`, `skse`, `source`, `docs` y `optional`, archivos como `.psc`, `.bak`, `.psd`, `.dll` y `.exe`, la basura de Mac y los `.ini` de la raíz; los plugins de SKSE y los inis del mod generan un aviso, porque Switch no corre ninguno de los dos. Los BSA propios del mod se desempacan en la carpeta de trabajo, y un archivo suelto con la misma ruta gana, igual que en PC.
3. Se borran los restos de voces que el juego nunca carga: la carpeta `processing` del Creation Kit, tomas viejas, archivos de voz vacíos y carpetas de voz de nombres anteriores del plugin.
4. Se leen los encabezados de las texturas, se clasifican los archivos de Havok y se agrupan los sonidos. Un nombre de archivo por fuera de Windows-1252 detiene la conversión, porque un BSA no lo puede guardar. Las copias de los masters del propio juego se descartan.
5. Se leen los encabezados de los plugins. Los masters que faltan se reportan, y un master que este pack conoce con otro nombre se apunta a ese nombre (sección 6). Un HEDR menor que 1.0 (el juego de 2011) genera un aviso. La app sugiere un nombre seguro y uno corto; si las carpetas de voces o FaceGen usan otro nombre de plugin, sugiere ese.

**Convertir:**

1. Se revisan los nombres finales (extensión, caracteres seguros, máximo 60 caracteres, que no estén ocupados, que no choquen con los archivos del juego). En un pack AE, la conversión se detiene antes de trabajar si `Skyrim_aoc.ccc` pasaría de 4096 bytes, salvo que lo autorices.
2. Se aplican los renombres en la carpeta de trabajo (sección 6).
3. En un pack SE, `skynx/edition.py` quita la marca ESL (un `.esl` ya recibió nombre `.esp`) y deja en 1.70 un HEDR 1.71 cuando el plugin no tiene registros propios por debajo del ID 0x800; si los tiene, la versión se queda y el Doctor explica cómo renumerarlos. Un plugin que necesita masters del Creation Club recibe un aviso y queda en `Data`, desactivado.
4. Se convierten texturas, archivos de Havok y sonidos (secciones 2, 3 y 4).
5. Los archivos se empacan en BSA (sección 7).
6. `builder.add_mod` copia plugins y BSA a `Data`, agrega los plugins al final de la lista de carga, suma a las listas de los inis los BSA que cargan por ahí y guarda la configuración y el origen en `.skynx/mods.json`, todo en una sola entrada del historial. Por defecto también deja una copia en `Biblioteca\Converted` para otros packs.

## 2. Texturas

`skynx/texplan.py` planea cada archivo, `skynx/converter.py` ejecuta el plan, `skynx/diet.py` se encarga de las texturas que ya son de Switch y `skynx/nvn.py` lee y escribe el formato nativo `DFvN`.

**Los perfiles de tamaño** funcionan por área: la textura se reduce a la mitad hasta que ancho × alto quepa en lado × lado. Nada se agranda, y las texturas de `interface\` y `menus\` nunca cambian de tamaño.

- **Dieta Switch 1** (por defecto): 1024; los mapas que no son de color (`_n`, `_msn`, `_s`, `_m`, `_g`, `_e` y parecidos) y el clutter, los efectos, las plantas y el pasto quedan en 512.
- **Reglas clásicas:** 1024; `actors\` en 2048.
- **Extrema:** 512; mapas en 256; `actors\character` en 1024.
- **Tamaño original:** sin regla de tamaño.

Encima del perfil, un tamaño máximo opcional (256, 512, 1024, 2048 o 4096) sigue reduciendo a la mitad hasta que el lado más largo quepa.

**Formatos.** Sin NvnTexpkg, el resultado sigue siendo DDS de PC en BC3 (DXT5), y los mapas normales BC5 se quedan en BC5. Con NvnTexpkg, BC1 y R8 quedan en BC1, BC4 y RG8 en BC5, BC2 y BC5 se mantienen y el resto queda en BC3. La opción **BC1 en texturas opacas** (solo con NvnTexpkg) guarda como BC1, con la mitad de memoria, una textura en la que todos los píxeles son opacos.

**Mipmaps.** Se regenera la cadena completa, salvo en las texturas de agua (`textures\water\`), que se quedan en 4 niveles porque con la cadena completa el agua de Switch muestra artefactos. Las de interfaz conservan los suyos.

**Por cada textura de PC:** texconv corre solo si cambian el formato, el tamaño o los mips (`-dx9 -sepalpha -f <formato>`, más `-w`, `-h`, `-m`), y lo que entrega tiene que ser un DDS del tamaño planeado. Con el SDK sigue `NvnTexpkg -i <dds> -o <xtx>`, cuyo resultado tiene que empezar por `DFvN`; si falla, la textura queda como DDS de PC en BC3 y se reporta. Ante cualquier otra falla, el archivo vuelve a quedar exactamente como venía.

**Texturas que ya son nativas** (al convertir y en la Dieta): las que no tienen compresión (RGBA8, R8, RG8; los tintes de FaceGen son el caso típico) pasan a BC3, BC4 o BC5 (BC1 si son opacas y la opción está activa) con el tamaño del perfil. A las comprimidas que superan el perfil se les quitan los mips más grandes cuando los tienen, lo cual es exacto; si no, texconv las reduce. El archivo nativo nuevo lo escribe NvnTexpkg cuando está, y si no, el escritor propio de la app.

**Dieta sobre un BSA existente** (`bsafix.diet`): se planea cada textura, se escribe un BSA nuevo al lado del original y se pone en su lugar a través del historial. Una textura que falla queda idéntica byte a byte. El Doctor la sugiere cuando la Dieta Switch 1 con BC1 ahorra 8 MB o más.

## 3. Audio

Módulos: `converter._convert_sound`, `skynx/nxaudio.py`, `skynx/audio.py`. Los archivos de `sound\` y `music\` se agrupan por nombre base; un grupo se convierte si tiene un `.xwm` o un `.wav`, o un `.fuz` con audio de PC. Los `.fuz` de Switch y los `.mcadpcm` no se tocan.

- **Voces** (`sound\voice\`): un `.fuz` de PC se separa en datos de lip-sync y audio. ffmpeg lo decodifica a PCM mono de 48 kHz y 16 bits, VGAudioCli lo codifica en Opus de Nintendo, y `nxaudio.build_fuz` arma el archivo `FUZE` de Switch con el lip-sync, el encabezado Opus de Skyrim y el audio.
- **Música y efectos:** ffmpeg decodifica a PCM de 44,1 kHz (máximo estéreo) y VGAudioCli escribe un `.mcadpcm`, con un flujo DSP-ADPCM por canal.

Los archivos de PC de cada grupo convertido se eliminan de la carpeta de trabajo; un sonido que falla queda como venía y se reporta. La revisión a fondo del Doctor marca el audio de PC dentro de los BSA y lee completas las voces y la música de Switch para encontrar archivos cortados (`audio-broken`).

## 4. Animaciones y comportamientos

**Archivos de Havok** (`skynx/hkx.py`, `skynx/havok.py`): el byte 16 del encabezado dice el tamaño de puntero (4 en el juego de 2011, 8 en 64 bits) y el byte 18, la plataforma.

- Las animaciones de PC de 64 bits se convierten en el sitio sin herramientas: se marca el byte de plataforma y se mueven cuatro bytes del encabezado.
- Los grafos de comportamiento, los esqueletos y los archivos de 32 bits o XML los reescribe HavokBehaviorPostProcess con `--platformps4`; los de 64 bits pasan antes por `hkxc convert -v xml`. El resultado tiene que usar las reglas de Switch (8-1-1-1).
- Sin esas herramientas, estos archivos quedan como venían y el informe los cuenta.

**Generar comportamientos** (`skynx/behaviors.py`): al convertir, se guardan los originales de PC que la generación necesita (listas de FNIS con sus animaciones, el parche de Nemesis) en `.skynx/behavior-sources/`. **Generar comportamientos** (página Mods) arma una carpeta de trabajo con una copia de Nemesis, un `SkyrimSE.exe` vacío para que la trate como Special Edition, los comportamientos del juego y las fuentes de cada mod. Tú oprimes Update Engine y Launch en Nemesis. Cuando su registro dice "Behavior generation complete", se recogen los archivos que cambiaron, cada `.hkx` se pasa al formato nativo de Switch y todo va a `SkyNXBehaviors.bsa`, que entra como el mod "SkyNX - Generated behaviors". Una nueva generación reemplaza la anterior.

## 5. Tintes de cara (FaceGen)

Cada malla de cara (`…\facegendata\facegeom\<plugin>\`) nombra su textura de tinte (`…\facegendata\facetint\<plugin>\`) dentro de un bloque `BSShaderTextureSet`.

- **Renombres:** las dos carpetas siguen el nombre nuevo, y `nif.replace_texture_folders` reescribe las rutas de tinte, cambiando solo los segmentos de ruta iguales al nombre viejo. `skynx/nif.py` rechaza una malla cuyos tamaños de bloque no sumen exacto; al convertir, una malla de FaceGen ilegible hace que el plugin conserve su nombre.
- **Memoria:** los tintes sin compresión son el blanco principal de la dieta; el Doctor agrega un hallazgo de Ahorro cuando pasan de 20 MB.
- **Rutas rotas** (revisión a fondo, `bsafix.scan_tints`): un tinte que no está en ningún BSA del pack se reporta (`tint-broken`). Si existe en la carpeta del plugin dueño de la malla, un arreglo seguro (`bsafix.fix_tints`) reconstruye el BSA con las mallas apuntando ahí.

## 6. Renombrar plugins

El nombre de archivo de un plugin aparece en muchos lugares, y un renombre los actualiza todos juntos. `rename.safe_name` quita apóstrofos, comillas, tildes y símbolos, que Google Drive daña.

**Al convertir** (`rename.apply`, sobre la carpeta de trabajo): los archivos del plugin; los masters de cada plugin; las propiedades de script (`VMAD`) cuyo valor completo es un nombre viejo (`records.rename_in_vmad`); las carpetas de voces, `facegeom` y `facetint`; `seq\<plugin>.seq` y `strings\<plugin>_<idioma>.*strings`; las rutas de tinte de FaceGen; las entradas de la tabla de textos de Papyrus iguales al nombre viejo, como el archivo que recibe `GetFormFromFile` (`pex.rename_plugins`); y los archivos de configuración de texto (`.json`, `.ini`, `.txt`, `.xml`…), solo donde el nombre aparece como valor completo. Las cadenas de renombres y los cambios solo de mayúsculas funcionan porque los archivos se mueven en dos fases.

**En un pack existente** (`bsafix.rename_plan`, `bsafix.safe_rename`) una vista previa muestra lo que va a cambiar; luego, en una sola entrada del historial, la app reconstruye los BSA cuyas rutas o scripts nombran el plugin, renombra el plugin y los BSA que cargan con él, actualiza masters y propiedades de script en todos los plugins, la línea de la lista de carga (también si está apagada con `#`), las entradas `sTestFile` y las listas de BSA de los inis, y `.skynx/mods.json`. Además escribe el registro de renombres `.skynx/renames.json`, que apunta al nombre nuevo los mods que lleguen después usando el original como master, responde las condiciones de los FOMOD y alimenta `script-gone-name`. El Doctor ofrece este renombre para los nombres que Google Drive dañaría.

**Lo que no puede cambiar.** Solo se reemplazan valores completos. Un nombre dentro de un texto más largo (un mensaje, una propiedad con varios valores) se deja como está, porque cambiar una parte de un texto lo puede dañar. Después de un renombre al convertir, `rename.leftovers` busca el nombre viejo como palabra suelta en los textos de scripts, las propiedades de script y las líneas de configuración, y el resultado avisa con la cantidad, hasta cinco ejemplos "archivo: texto" y la recomendación de probarlo en el juego. En un pack existente, la revisión a fondo los lista.

## 7. Empacado en BSA y compresión

El convertidor escribe BSA versión 105 con `bsa.write_bsa`, en uno de cuatro modos:

- **Un BSA en los inis (versión Switch, por defecto):** un `<nombre>.bsa` en la lista de BSA del ini que quede más corta. El nombre es el del plugin, compactado a 12 caracteres y nunca igual al de un plugin (cargaría dos veces). Si ninguna lista tiene espacio, se usa el modo siguiente.
- **Un solo BSA con el nombre del plugin (sin ini):** `<plugin>.bsa`.
- **BSA con el nombre del plugin (sin ini):** `<plugin>.bsa` y `<plugin> - Textures.bsa`.
- **BSA en los inis (la forma estable):** `<nombre>M.bsa` (mallas, scripts, animaciones) en `sResourceArchiveList` y `<nombre>T.bsa` (texturas, voces) en `sResourceArchiveList2`.

Un BSA que pase de 1,9 GB se parte. **La compresión** (activa por defecto) se aplica solo a `.nif`, `.hkx`, `.tri`, `.btr` y `.bto`, con LZ4 archivo por archivo; texturas y sonidos se guardan sin comprimir, como en los packs de Switch revisados. Al terminar, el BSA se vuelve a leer y cada archivo se compara con su fuente antes de reemplazar el destino. Cuando el Doctor solo mueve o renombra archivos, `bsa.rebuild_bsa` reutiliza los datos guardados sin volver a comprimir.

## 8. El Doctor

`skynx/audit.py` y `skynx/scriptcheck.py` solo leen. Cada hallazgo tiene una gravedad (Grave, Revisar, Ahorro, Dato) y puede traer un arreglo, marcado como seguro o como "revisa antes de aplicar".

- **Revisión rápida:** estructura del pack, formato de la lista de carga, encabezados de plugins, masters y su orden, tamaño del `.ccc`, duplicados y largo de las listas de los inis, BSA cuyas carpetas de voces o FaceGen nombran otro plugin, basura dentro de los BSA.
- **Revisión a fondo:** suma el contenido de los BSA (formatos de textura, texturas y audio de PC, archivos llenos de ceros, mallas de 2011), los tintes de FaceGen, los archivos SEQ, los requisitos contra los BSA de la consola cuando esa carpeta está configurada y las revisiones de scripts (plugins que se piden por nombre y no están cargados, scripts que reemplazan los del juego, `script-gone-name`). Corre al abrir un pack, con **Volver a revisar** y después de cada arreglo; deshacer y renombrar corren la rápida.

**Arreglos** (`skynx/fixes.py`): `preview` lista cada cambio sin tocar nada. `apply` ejecuta el arreglo completo en una sola Transaction del historial (cambios en la lista, renombres, cambios en inis, BSA reconstruidos como `.skynx-new` y puestos en su lugar), así que se deshace en un paso, y si falla a mitad de camino se revierte de inmediato. **Arreglar lo seguro** aplica los arreglos seguros uno por uno, revisando otra vez entre cada uno.

## 9. Lista de carga e inis

Un pack tiene `01000A10041EA000\romfs` (`Data`, los inis y, en SE, la lista `Plugins`) y, en AE, `01000A10041EB009\romfs\Skyrim_aoc.ccc`.

**Lista de carga** (`skynx/ccc.py`): un plugin por línea; las ediciones dejan idénticas byte a byte las líneas que no tocan, con su BOM y sus saltos de línea. Una línea que empieza por `#` está apagada y Empacar la deja por fuera. Los plugins nuevos van al final, después de sus masters. `knowledge.py` fija el techo del `.ccc` de AE en 4096 bytes, con aviso por encima de 3900, y se rechaza cualquier escritura que lo haga crecer más allá.

**Inis** (`skynx/ini.py`): un lector tolerante (claves duplicadas, comentarios con `#` y `;`, claves con espacios) cuyas ediciones tocan una sola línea. El ini de idioma (`Skyrim_es.ini`…) reemplaza el `sResourceArchiveList2` de `Skyrim.ini`, así que cada entrada va en todos los inis que tengan esa clave. Un BSA sin plugin va a `sResourceArchiveList2` si trae texturas o voces, y a `sResourceArchiveList` en los demás casos. Cada lista admite máximo 1024 caracteres, con aviso por encima de 900.

## 10. Empacar y copiar a la SD

**Empacar** (`project.build`) escribe la carpeta `Switch\` de un proyecto: copias reales de las dos carpetas de título, sin los mods que dejaste por fuera, sin las líneas con `#` y sin las entradas de ini de BSA cuyos plugins están todos apagados. Se niega si un plugin que va necesita un master que no va, copia solo lo que cambió y manda a la papelera del proyecto lo que se haya editado a mano.

**Copiar a la SD** (`skynx/deploy.py`) solo toca las dos carpetas de Skyrim dentro de `atmosphere\contents`, revisa que la unidad parezca una SD de Switch y deja 200 MB libres. **Copiar los cambios** (por defecto) compara rutas sin distinguir mayúsculas; mismo tamaño y una hora con menos de 2 segundos de diferencia significa sin cambios, y mismo tamaño con otra fecha significa comparar el contenido en archivos de menos de 8 MB. Antes de tocar la SD, cada archivo que se va a sobrescribir o borrar se guarda en un zip en `.skynx\sd-backups`, que se verifica; si algo falla, la SD vuelve a quedar como estaba. **Mejor copia completa** reemplaza las dos carpetas enteras, con la misma protección. **Pasar mods entre packs** (`skynx/transfer.py`) planea sin escribir y luego copia archivos, líneas de la lista y entradas de ini en una sola entrada del historial.

## 11. Deshacer e historial

`skynx/history.py` envuelve cada cambio en una Transaction. Antes de cambiar, crear, renombrar o borrar un archivo, su estado anterior se copia en `.skynx\history\<entrada>\` y se verifica con SHA-1; `manifest.json` guarda el hash de cada archivo antes y después. Los archivos borrados van a `.skynx\trash`. Un registro escrito antes de cada cambio le permite a la app revertir una entrada interrumpida la próxima vez que se abre el pack, y un cambio que falla se restaura de inmediato. **Deshacer** se niega si un archivo cambió otra vez después (el mensaje dice cuáles), queda registrado también y no se puede deshacer a su vez: en ese caso, vuelve a aplicar el arreglo.

## Novedades de la 1.0

- **Las propiedades de script siguen al renombre:** las propiedades `VMAD` de texto que guardan el nombre del plugin se renombran en todos los plugins del mod que se convierte, y en todos los plugins del pack cuando renombras dentro de un pack existente.
- **Aviso de restos:** después de un renombre al convertir, la app lista los lugares que todavía nombran el plugin viejo dentro de un texto más largo y los deja como están.
- **Doctor, `script-gone-name`** (revisión a fondo): scripts y propiedades de script que todavía nombran un plugin que este proyecto renombró o fusionó.
- **Doctor, `mesh-le`** (revisión a fondo, Dato): mallas del juego de 2011 (NIF stream 83). Casi todas funcionan; si un modelo sale invisible o estirado, vuelve a guardarlas con Cathedral Assets Optimizer en "Full optimization".
- **Basura en los BSA** ahora también encuentra `.DS_Store`, `Thumbs.db`, `desktop.ini` e imágenes `.png` sueltas fuera de `interface`.
