# SwitchNX Studio 0.8

Herramienta para revisar, arreglar y llevar a la SD modpacks de Skyrim para Nintendo Switch.
Funciona con Anniversary Edition (Skyrim_aoc.ccc) y con Special Edition (archivo Plugins).

## Novedades 0.8

- **Proyectos.** Cada modpack que armas o mantienes es un proyecto en su propia carpeta
  (`Library\Projects\<nombre>`): `Mods\` con los archivos de cada mod y un `mod.json` (versión, origen,
  conversión, si va), `Base\` con las inis y la lista de carga, y `Switch\`, que hace **Empacar**, con las dos
  carpetas para la consola. Un proyecto empieza desde cero, desde un modpack (carpeta, zip/7z/rar, otro proyecto) o
  desde la SD; la fuente se copia y nunca se escribe. Lo que cambies o agregues a mano en `Mods\` o `Base\` entra al
  proyecto como un cambio que se puede deshacer. Llevar a la SD siempre empaca antes y manda exactamente lo que hay en
  `Switch\`.
- **Los modpacks ya no se guardan en la Biblioteca.** Un modpack se vuelve proyecto, o una fuente de la que traes mods
  (Mods » Desde un modpack…, directo desde su zip). Los packs y packs en creación de antes salen en el Inicio con
  **Convertir en proyecto**; los originales se quedan hasta que los borres.
- **Inicio en tres partes:** Proyectos, el Taller (trabajos rápidos sobre mods sueltos, igual que antes) y la
  Biblioteca de mods (mods y el Catálogo, que ahora lee tus proyectos).
- **Revisión de seguridad** del código nuevo: los proyectos copian su fuente por defecto (enlazar es un ajuste,
  apagado), `Switch\` son copias reales que se arman por partes, lo que la app no hizo se mueve a la papelera en vez de
  borrarse, dos archivos a mano para el mismo lugar se guardan ambos aparte, y Mods/Base no se tocan si falta la
  copia de trabajo.

## Novedades 0.7

- **Inicio en cuatro caminos**: Trabajar un mod, Trabajar varios mods, Crear tu modpack, Usar un modpack ya hecho.
  Debajo, tareas sueltas (revisar y arreglar, reducir texturas, aligerar un pack, juntar BSA, conflictos de archivos,
  orden de carga, renombrar, versiones para Switch, llevar a la SD, deshacer); sin pack abierto, la app pregunta cuál.
- **Ayuda**: el manual dentro de la app (barra de arriba » Ayuda), en inglés y español, con índice y búsqueda. Se abre
  en la parte de la página donde estás. Fuentes: `docs/manual.en.md` y `docs/manual.es.md`; después de editarlas,
  correr `python docs/build_manual.py`.
- **Primera vez**: créditos y qué hace la app, luego Tu equipo: cada herramienta y carpeta, si la encontró y qué queda
  apagado sin ella. El inicio deja una lista corta de lo que falta.
- **Catálogo** (Biblioteca > Catálogo): todos los packs y mods de tu Biblioteca quedan en un solo estante. Filtras por
  pack o categoría, marcas los que quieres (30 de un pack, 10 de otro) y el panel lateral planea el pack nuevo:
  edición, CC, USSEP, inis base, presupuesto del .ccc y del ini, masters que faltan. "Crear pack" lo arma y lo abre,
  listo para agregarle extras.
- **Comparar con el original**: un mod convertido en Agregar mods se compara con su versión de PC (registros, archivos,
  texturas, pesos) para ver qué cambió la conversión de otra persona.
- **Revisiones de KokaNX en el Doctor**: animaciones fuera de la lista en memoria, HEDR 1.71 en SE, `.seq` que faltan o
  están viejos para quests que arrancan solas, BSA de USSEP justo después de los vanilla y USSEP primero después del CC.
- **Opciones del conversor**: tamaño máximo de textura con estimado, empaquetado (un BSA por plugin, un solo BSA o
  cargado por ini) y compresión de BSA.
- **Herramientas externas**: SSEEdit abre sobre el pack (lo que guardes entra solo al pack al cerrarlo, con deshacer)
  o sobre una copia (al cerrarlo eliges: traer los cambios, guardar la copia para después o borrarla). El orden de carga tiene casilla de activo y muestra los masters de cada plugin. Los mods se pueden extraer de su BSA.
- **Tres espacios**: la pantalla de inicio abre Modpacks (roble oscuro y latón), el Taller de mods (cerezo y cobre) y la
  Biblioteca (nogal y verdín); el marco, el menú y los botones cambian de madera para que siempre sepas dónde estás.
  Packs, mesas, mods y la Biblioteca tienen enlaces "Abrir carpeta" al explorador.
- **Taller de mods**: una mesa es un espacio de trabajo privado para mods, sin pack. Convierte un mod de PC, edita un mod
  (renombrar con todo lo que lo sigue, extraer, SSEEdit), junta varios mods en una suite (sus BSA quedan en uno, en el
  orden de carga del juego, gana el archivo que carga después) o fusiona plugins con zMerge paso a paso (la app prepara
  la carpeta para zEdit, trae el merge, saca los plugins fusionados y junta sus BSA bajo el merge). Guardar deja el
  resultado en Library\\Converted.
- **Cuál mod es (Nexus)**: cada mod de la página Mods y de la mesa muestra su página de Nexus cuando la app la sabe: lo
  que confirmaste (se recuerda por archivo de plugin, así que lo sigue a otros packs), una descarga de Nexus o la
  masterlist de LOOT, consultada con el nombre del pack y con los nombres originales que la app registró (renombres, el
  '_' de Drive). Los merges muestran los mods que tienen dentro. Para el resto: buscar en Nexus con las palabras del
  plugin o pegar el enlace. Con la API key trae nombres y versiones. Los enlaces van a las páginas de Skyrim Special
  Edition, donde viven los mods de Anniversary.
  La misma etiqueta sale en las tarjetas de Agregar mods y en las filas del Catálogo, y la receta exportada lleva esos
  enlaces (dice si los reconoció LOOT o si los confirmaste a mano).
- **Probado con descargas y packs reales**: la basura de Mac en los zip (`__MACOSX`, `._Mod.esp`) ya no llega a Data
  ni a la lista; si un mod trae carpetas `_AE` y `_SE` se usa la de la edición del pack; las carpetas opcionales con su
  propio plugin entran como parte del mod; un mod de solo BSA conserva el nombre de su BSA; el Doctor ofrece extraer en
  Data los mods que un pack trae comprimidos (la lista de Ashiro); los `.rar` se abren con 7-Zip o con el `tar.exe` de
  Windows; ningún arreglo, mod agregado ni "va" deja el .ccc por encima de 4096 bytes; el Historial sale en español.
- **Mods de AE y de SE en cualquier pack**: un mod de SE entra a un pack de AE tal cual. En un pack de SE, un mod
  hecho para AE se adapta al entrar (Agregar mods, Convertir, lote, Traer de otro pack, Catálogo): su `.esp` pierde la
  marca ESL (SE la ignoraría) y el HEDR 1.71 baja a 1.70 cuando ningún registro propio usa los form IDs bajos que solo
  permite 1.71 (si los usa, se queda y el Doctor lo explica). Un `.esl` de verdad pasa por Convertir o por el arreglo
  del Doctor "Pasarlo a .esp para SE". Los plugins que necesitan contenido del Creation Club quedan en Data pero fuera de la
  lista, porque SE no tiene CC. Cada caso deja una nota en la tarjeta.
- **Convertir varios a la vez**: en Convertir mods, pestaña "Varios a la vez" (o "Convertir varios mods" en el menú
  principal, o "Convertir todos los de PC" en Agregar mods). Cada mod sale en una tarjeta angosta con su dieta, tamaño
  máximo, empacado, formato nativo y los nombres de sus plugins; "Para todos" aplica lo mismo a todas. Los FOMOD se
  eligen dentro del lote, y sus parches para otros mods del lote quedan disponibles. Arriba se ve el .ccc y las texturas
  con todos sumados. Antes de empezar revisa que ningún nombre se repita y que el .ccc alcance; después convierte
  primero los que otros necesitan y les apunta el nombre final. Si uno falla, los demás siguen y el que falló queda para
  leerlo de nuevo. Cada mod se guarda también en Library\Converted (si la casilla está marcada).
- **Versiones para Switch**: "Versiones para Switch" (barra de Nexus en Mods, o "Buscar actualizaciones en Nexus", o la
  ficha de un mod) mira por dentro los archivos de cada mod en Nexus (la lista de contenido que publica Nexus) y su
  descripción y changelog. Una versión que trae plugins de SKSE (.dll) no sirve en Switch; si nombra SKSE, Address
  Library, PapyrusUtil, SPID y similares, queda para revisar. Muestra la que tienes, la última y la mejor para Switch
  (la más nueva que sirve), con enlace a su archivo. Si la app no sabe qué versión tienes, "Tengo esta" la recuerda.
  Necesita la API key.
- **El pack en creación**: empieza como copia exacta de otro pack (Biblioteca > "Armar un pack desde este": mismos
  archivos, mismos bytes del .ccc, mismas inis) o desde el Catálogo. En su página de Mods cada mod tiene una casilla: si la
  desmarcas sale de la lista de carga y de las inis (los números del .ccc y de las inis se actualizan); si la marcas,
  vuelve a donde estaba. Cualquier plugin se puede renombrar viendo antes todo lo que sigue al nombre y los bytes del
  .ccc. "Traer del Catálogo" le agrega mods de otros packs. "Crear modpack" deja una copia limpia (solo lo que va, sin
  historial) en la carpeta que nombres y luego ofrece copiarla a la SD. En el mismo disco ambos usan enlaces (no ocupan
  espacio extra); la app nunca escribe dentro de un archivo, así que el pack de origen no cambia (en Ajustes se apagan).
- **Biblioteca\\Converted**: cada mod que conviertes deja también una copia ahí (plugins, BSA y cómo se convirtió).
  Aparece en la Biblioteca y en el Catálogo, para meterlo en otros packs sin volver a convertirlo.
- **Un pack que se movió**: si lo abres desde los recientes, lo busca por nombre en la Biblioteca.
- **Créditos y Tu equipo**: pantalla de inicio con los créditos (con "no volver a mostrar") y una página con lo que
  la app puede usar en este PC, lo que ya está y lo que falta.
- **Aire de taberna**: pared de madera, páginas de pergamino, botones de roble y latón, y el ícono de la app.
- **Duplicados que tú decides**: cada duplicado del Doctor ofrece dejarlos o dejar solo una copia. Al dejar una, queda
  donde estaba la primera copia, los parches pasan a usarla y se conservan (o se renombran) los BSA que necesita. Un mod
  que también está dentro de un merge se vacía (sus registros salen, sus BSA siguen cargando). "Dejar los dos" oculta el
  aviso hasta que lo vuelvas a mostrar. Todo se puede deshacer.
- **Nexus**: pega tu API key personal en Ajustes. El botón Mod Manager Download del sitio puede mandar los archivos aquí
  (se descargan en la Biblioteca y aparecen en Agregar mods; sirve con cuenta gratis; Vortex o Mod Organizer pueden
  recuperar el botón). Los archivos descargados recuerdan su mod y versión de Nexus; los demás se pueden buscar en Nexus
  por MD5. "Buscar actualizaciones en Nexus", en la página Mods, compara tus versiones solo cuando lo oprimes.
- **Receta del pack**: cada mod que agregues desde ahora registra de dónde vino (Nexus, comprimido, carpeta, otro pack,
  USSEP), sus opciones de FOMOD y la configuración de conversión. La página Mods muestra la receta, qué cambió desde que
  se guardó, y exporta un .md para compartir con links de Nexus y sin rutas de tu PC.

## Novedades 0.6

- **LOOT y plugins fusionados**: un merge (Merge Plugins / zMerge, como el EnaiRim_NR.esp de Avner) se lee desde
  su propio encabezado y se trata como los mods que contiene: toma el grupo de LOOT más tardío de ellos y hereda sus
  reglas, requisitos y avisos de parches. Reconoce los plugins vacíos que se dejan para los parches y avisa si un
  mod está dentro del merge y además suelto.
- **Plugins que LOOT no conoce**: cada uno recibe una categoría sugerida según lo que trae (tierras y objetos
  nuevos, parches, razas, perks...), con la razón. Tú confirmas o escoges otra; queda guardado para todos los packs.
- **Requisitos en el Doctor**: requisitos, incompatibilidades y avisos de parches de LOOT (sin los de herramientas
  solo de PC como plugins de SKSE), animaciones que necesitan DAR, OAR, Nemesis o FNIS, y archivos de behavior que
  se pisan. Con los BSA vanilla de la consola configurados en Ajustes también encuentra scripts, meshes y texturas
  que faltan.
- **Duplicados en el Doctor**: el mismo plugin con dos nombres, el mismo BSA cargado dos veces, un mod dentro de un
  merge y además suelto.
- **Traer mods de otro pack** les pone de una vez un nombre que Google Drive no daña.

## Novedades 0.5

- **Agregar mods**: suelta zips, 7z, carpetas o un .esp/.bsa suelto en la ventana (o escógelos). Cada uno se
  identifica: los modpacks van a la Biblioteca, los mods ya convertidos para Switch pasan una revisión rápida y
  entran directo, los de PC y los instaladores FOMOD se abren en Convertir.
- **Revisión antes de agregar** (mods de Switch del Discord, por ejemplo): voces o caras guardadas con otro
  nombre de plugin, archivos de PC que quedaron adentro, nombres inseguros, masters que faltan, ESL en SE, uso
  de SKSE y cuánto ahorraría la dieta de texturas. Recomienda agregarlo tal cual o pasarlo por Convertir.
- **Biblioteca** (`C:\SkyNX\Library`, con `Packs` y `Mods`; se cambia en Ajustes): importa zips de modpacks
  (también los zips partidos de Drive), guarda mods y muestra la salud de cada pack de un vistazo.
- **Traer mods de otro pack**: escoges mods de cualquier pack de la Biblioteca; vienen con sus masters, se deja lo
  que el pack ya tiene, y el plan muestra el presupuesto del .ccc y de texturas antes de copiar nada.
- **USSEP en packs nuevos**: escoges la versión KokaNX (All_CC, SurvivalMode, No_CC o ninguna). Los masters de
  Creation Club que falten se agregan a la lista.
- **Primeros pasos** en la bienvenida: herramientas, inis de la consola, USSEP y Biblioteca, con qué hacer en cada uno.
- **Orden de LOOT**: sugiere un orden con la masterlist oficial de LOOT (se descarga y se guarda), con la razón
  de cada movimiento, y respeta tu orden donde nada dice lo contrario.
- **Conflictos de archivos**: qué BSA reemplaza archivos de otros y cuáles quedan reemplazados por completo.
- **Llevar a la SD**: copia solo lo que cambió, muestra el plan antes y respalda en .zip todo lo que se reemplaza o quita.
- **Doctor**: tints de FaceGen que apuntan al plugin equivocado (Cheat Room), nombres que Drive daña con
  renombrado seguro completo (Ryn's Standing Stones), dieta para texturas de Switch ya convertidas (tints de
  USSEP), basura dentro de BSA (fuentes .psc) y avisos de SKSE / MCM.

## Cómo construir el .exe

1. Instala Python 3.12 desde python.org (marca "Add python.exe to PATH").
2. Doble clic en `construir.bat`. Tarda unos minutos la primera vez.
3. El programa queda en `dist\SwitchNX Studio.exe`. Ese archivo funciona solo; puedes moverlo a donde quieras.

Para probar cambios del código sin reconstruir: `abrir-sin-exe.bat`.
Si la ventana propia no abre (falta WebView2), el programa abre la misma interfaz en el navegador.

## Herramientas externas

Todas van juntas en `C:\SkyNX\tools` (o en una carpeta `tools` junto al .exe). Ver `LEEME-tools.txt` en esa carpeta.

| Archivo | Para qué | ¿Obligatorio? |
|---|---|---|
| texconv.exe | Formato, tamaño y mipmaps de las texturas | Para convertir texturas |
| ffmpeg.exe | Leer audio de PC (.xwm, .wav) | Para convertir sonidos |
| VGAudioCli.exe + VGAudio.dll | Escribir Opus de Switch y .mcadpcm (versión del Skyrim NX Toolkit) | Para convertir sonidos |
| NvnTexpkg.exe + NvnTexpkg.dll, NvnImage.dll, DdsLoader.dll, TgaLoader.dll | Texturas en formato nativo de Switch (DFvN) | Opcional |

## Qué hace hoy

- **Empezar desde cero**: crea las carpetas, los inis y la lista de carga. Los inis base salen de tu consola (con DBI) o de un modpack de confianza; conservo sus ajustes y le quito sus mods.
- **Convertir mods de PC**: lee el mod, muestra el presupuesto (bytes del .ccc y memoria de texturas antes y después) y lo convierte:
  - Texturas con las reglas de Koka, o con las dietas "Switch 1" y "Extrema". Con NvnTexpkg quedan en formato nativo y las opacas pueden bajar a BC1 (la mitad de memoria). Sin NvnTexpkg quedan en DDS DXT5, como hace Koka. La interfaz nunca se reduce y nada se agranda.
  - Voces a Opus de Switch dentro de FUZE (con su lip), música y efectos a .mcadpcm. El formato se comprobó byte a byte contra 995 voces reales.
  - Animaciones de 64 bits de SE con el método del Skyrim NX Toolkit.
  - Renombre seguro de plugins (apóstrofos, ESL en SE, nombres cortos para ahorrar bytes del .ccc): actualiza el plugin, sus BSA, voces, FaceGen, rutas de tinte dentro de los meshes, SEQ, strings, scripts .pex, configs json/ini y los masters de quien lo usa. Si un mod posterior usa el nombre original como master, lo apunta al nombre nuevo solo.
  - Empaca `Nombre.bsa` y `Nombre - Textures.bsa`, que cargan solos con el plugin, y lo agrega al pack en un solo paso del historial.
- **Asistente FOMOD**: si el mod trae instalador, lo muestra paso a paso con imágenes y descripciones, siguiendo las reglas del esquema oficial (orden, pasos que aparecen según lo elegido, prioridades de archivos, instalaciones condicionales). Los parches de mods que no están activos en tu pack salen como "no disponible"; si el converter renombró un plugin, el asistente lo reconoce por su nombre original. Lo elegido queda guardado en el registro del mod.
- **Inglés**: el pack se arma en inglés. "Empezar desde cero" copia Skyrim.ini y Skyrim_en.ini (si falta, escribe el original de la consola). En Switch Skyrim_en.ini reemplaza la lista de texturas de Skyrim.ini, así que los BSA que van por ini se escriben en los dos, y el Doctor avisa si alguno queda tapado.
- **Mods**: agrega mods ya convertidos desde una carpeta, .7z o .zip. Los plugins van a la lista después de sus masters; los BSA sin plugin van al ini según lo que contienen. Se quitan con un clic.
- **Idioma**: inglés o español, con el botón EN/ES arriba.
- **Abre cualquier modpack**: la raíz de la SD, `atmosphere`, `contents` o una carpeta con `01000A10041EA000` y `01000A10041EB009`.
- **Doctor**: revisa lista de carga, masters, BSA, inis, texturas y audio. Cada hallazgo explica qué pasa y, cuando hay arreglo, muestra antes exactamente qué va a cambiar.
- **Arreglos con historial**: antes de tocar un archivo guarda una copia en `.skynx\history` del modpack. Todo se puede deshacer. Lo que se elimina va a `.skynx\papelera`. Si el programa se cierra a mitad de un cambio, la próxima vez que abras el modpack lo revierte.
- **Orden de carga**: arrastrar y soltar, con aviso en vivo de masters faltantes o fuera de orden.
- **Texturas y audio**: lee los encabezados dentro de cada BSA (DDS de PC y DFvN de Switch) y estima cuánto pesa cada mod.
- **Llevar a la SD**: respalda en el PC lo que haya en la SD y luego copia el modpack. También importa un modpack desde la SD.

## Qué revisa el Doctor

| Revisión | Ejemplo real que encontró |
|---|---|
| Nombres de la lista que no coinciden con el archivo (apóstrofos de Google Drive, puntos dobles, letras de más o de menos) | `Ryn's Standing Stones.esp` contra `Ryn_s Standing Stones.esp` |
| Mayúsculas distintas | `Sexlab.esm` contra `SexLab.esm` |
| Masters faltantes o que cargan después | Staves antes de MysticismMagic |
| Voces y caras guardadas bajo otro nombre de plugin (el caso Auri) | Arreglo reconstruyendo el BSA sin recomprimir |
| BSA que nunca cargan, copias sobrantes, plugins sin activar | Wintersun en Data pero fuera del .ccc |
| Bytes del .ccc y caracteres de las listas del ini | 4016 de 4096 bytes |
| Mods todavía comprimidos dentro de Data | Los .7z del pack de Ashiro |
| Plugins de Skyrim original, ESL en modo SE, plugins vacíos | Proper Aiming.esp |
| Texturas en formato PC, audio XWMA de PC, tintes faciales sin comprimir, archivos basura en BSA | 97 MB de tintes en el USSEP de Koka |

Los arreglos marcados como "seguros" cambian solo lo que dicen. Los marcados para "revisar" cambian cómo carga el pack (por ejemplo, activar un plugin o pasar un BSA al ini).

## Lo que está verificado y lo que no

Verificado con los cinco packs de `C:\SkyNX\Other modpacks`:
- El hash de nombres de BSA coincide en 9815 de 9815 archivos reales.
- Reconstruir un BSA sin cambios produce un archivo idéntico byte a byte al original.
- El arreglo de Auri mueve las carpetas de voces y caras y conserva el contenido exacto de los 1206 archivos.

Verificado contra archivos reales de Switch:
- El contenedor FUZE de voces se reconstruye idéntico en las 995 voces de los packs.
- Los 146 meshes de los packs se leen completos; cambiar la ruta del tinte facial y volverla atrás deja el archivo idéntico.
- Los 786 scripts .pex se leen completos.

Sin confirmar todavía (el programa lo dice donde aplica):
- Que las voces y la música convertidas suenen en consola (el formato coincide, falta oírlo).
- La conversión de animaciones de 64 bits (método del Toolkit, sin archivos de PC para probar aquí).
- El límite exacto del .ccc (4096 bytes es lo que cuadra con la evidencia).
- En qué orden carga el juego los plugins que entran por `sTestFile`.
- Si los archivos sueltos en Data funcionan en Switch.

## Próximas fases

1. **Dieta para mods ya convertidos** (DDS y DFvN).
2. **Orden sugerido** con el masterlist de LOOT.

## Estructura

```
skynx/        motor (sin interfaz): plugin, ccc, ini, bsa, textures, audio, pack, audit, fixes, history,
              deploy, knowledge, builder, converter, texplan, rename, nif, pex, hkx, nxaudio, tools, fomod
app/          ventana: main.py, api.py, server.py y web/ (HTML, CSS, JS, fuentes)
tests/        pruebas con copias de los packs reales
```

Créditos: formatos de sonido y método de animaciones del Skyrim NX Toolkit (Antony Marshall y Zappastuff, licencia MIT); reglas de texturas de Koka.
Fuentes: Barlow Condensed y Cinzel, licencia SIL Open Font License (ver `app/web/fonts`).
