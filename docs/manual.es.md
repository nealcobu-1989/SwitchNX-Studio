## Para empezar {#start}

SwitchNX Studio arma, revisa, arregla y convierte modpacks de Skyrim para Nintendo Switch, tanto Anniversary Edition (AE) como Special Edition (SE). Nada de lo que hace es definitivo: cada cambio queda en el Historial y se puede deshacer.

El inicio tiene tres partes:

| Parte | Para qué sirve |
| --- | --- |
| **Proyectos** | Cada modpack que armas o mantienes, en su propia carpeta: sus mods, su historial y lo que va a la Switch. Empieza uno desde cero, desde un modpack que alguien compartió o desde tu SD. |
| **Taller** | Trabajos rápidos sobre mods sueltos, sin proyecto: convertir un mod de PC, convertir varios, editar un mod de Switch, juntar mods en un BSA, juntar plugins. El resultado va a la Biblioteca de mods. |
| **Biblioteca de mods** | Los mods que tienes a mano (convertidos, descargados o agregados) y el Catálogo, con todos los mods de todos tus proyectos. |

**Siempre a mano.** La barra de arriba tiene **Biblioteca**, **Ayuda** (este manual; se abre en la parte de la página donde estás) y **EN / ES** para el idioma. Dentro de un proyecto también tiene **Empacar** y **Proyectos** (volver a la lista). Puedes soltar mods o modpacks sobre la ventana en cualquier momento: van a [Agregar mods](#h-add).

**Dónde estás.** Tres maderas distinguen los espacios: roble para los proyectos, cerezo y cobre para el taller, nogal para la Biblioteca de mods.

> ¿Primera vez? Mira [Tu equipo](#h-setup): dice qué falta en este PC y qué queda apagado sin eso.

## Tu equipo {#setup}

La primera vez que abre, la app muestra los créditos, qué hace y luego **Tu equipo**: cada herramienta y carpeta que puede usar, si la encontró y qué no puedes hacer sin ella. Cada línea tiene un botón para elegir su carpeta o su .exe. Puedes volver cuando quieras desde **Ajustes » Ver todo tu equipo**, y el inicio muestra una versión corta al final.

Abrir, revisar y arreglar proyectos funciona sin nada instalado. Lo demás depende de esto:

| Qué | Para qué | Sin esto |
| --- | --- | --- |
| texconv | Convierte texturas de PC | Los mods de PC con texturas no se pueden convertir, y la dieta de texturas no corre sobre un proyecto. |
| ffmpeg | Lee los sonidos de PC | Los mods de PC con sonidos o voces no se pueden convertir. |
| VGAudioCli + VGAudio.dll (versión del Skyrim NX Toolkit) | Escribe los sonidos de Switch | Igual que ffmpeg: los sonidos no se convierten. Otra versión de VGAudio no sirve. |
| NvnTexpkg y sus DLL | El formato nativo de texturas de Switch | Las texturas convertidas quedan en DDS (el formato de PC que la Switch también lee). |
| HavokBehaviorPostProcess.exe (Creation Kit, Steam) | Escribe comportamientos, esqueletos y animaciones de Oldrim (32 bits) en el formato de Switch | Esos archivos de mods de PC se empacan tal cual y puede que no funcionen en Switch. |
| hkxc.exe (serde-hkx, mod 126214 de Nexus SE) | Lee comportamientos y esqueletos de PC de 64 bits para que HavokBehaviorPostProcess los convierta | Los comportamientos y esqueletos de PC de 64 bits quedan tal cual. Puede ir en su propia subcarpeta (`Tools\serde-hkx`). |
| Nemesis (mod 60033 de Nexus SE), descomprimido en `Tools\Nemesis` | Genera los comportamientos de los mods con animaciones nuevas (listas FNIS, parches de Nemesis) | Esas animaciones no se ven en el juego. Necesita también HavokBehaviorPostProcess y hkxc. |
| 7-Zip | Abre descargas `.rar` | Solo abren los rar que el `tar.exe` de Windows puede leer; los demás se extraen a mano. |
| Inis de la consola | `Skyrim.ini`, `Skyrim_en.ini` y `Skyrim_aoc.ccc` limpios | No puedes empezar un proyecto desde cero (desde un modpack o desde la SD sí). |
| BSA y .esm del juego | Los archivos del juego base | El Doctor no puede saber si faltan scripts, meshes y texturas, y SSEEdit no puede abrir un proyecto. |
| USSEP (KokaNX) | El parche no oficial para proyectos nuevos | Los proyectos nuevos empiezan sin él. |
| SSEEdit, zEdit, NifSkope, BAE, Cathedral Assets Optimizer | Herramientas externas que la app abre por ti | Sus botones quedan apagados. zEdit hace falta para **Juntar plugins**. |
| Masterlist de LOOT | Reglas de orden y nombres de mods | Sin **Sugerir orden (LOOT)**; menos mods reconocen su página de Nexus. Se descarga sola la primera vez. |
| API key de Nexus | Nombres, versiones y actualizaciones de Nexus | Sin nombres ni actualizaciones de Nexus, y sin el botón Mod Manager Download. |

El lugar habitual de las herramientas es `C:\SkyNX\Tools`; el resto está en [Carpetas en disco](#h-folders).

## Proyectos {#projects}

Un proyecto es un modpack que armas o mantienes, guardado en una carpeta propia dentro de la Biblioteca (`Library\Projects\<nombre>`). Los modpacks ya no se guardan en la Biblioteca: un modpack que alguien comparte se vuelve un proyecto, o una fuente de la que traes mods.

| En la carpeta del proyecto | Qué guarda |
| --- | --- |
| `Mods\<mod>\` | Los archivos de cada mod, como van dentro de Data, y un `mod.json` con su nombre, versión, de dónde vino, cómo se convirtió y si va. |
| `Base\` | Las inis, la lista de carga (`Skyrim_aoc.ccc` o `Plugins`) y los archivos de Data que no son de ningún mod. |
| `Switch\` | Lo hace **Empacar**: las dos carpetas que van a la consola (`01000A10041EA000` y `01000A10041EB009`). |
| `skynx-project.json` | Qué es el proyecto: nombre, de dónde salió, último empaque, última copia a la SD. |
| `.skynx\` | Historial, papelera y registros, y la copia de trabajo que usan las herramientas. |

**Empezar uno.** Inicio » **Nuevo proyecto**, ponle un nombre y elige desde dónde empieza:

- **Cero**: las inis limpias de la consola, la edición, el Creation Club y USSEP. Tú agregas los mods.
- **Un modpack**: una carpeta, un `.zip`/`.7z`/`.rar` que alguien compartió (las descargas partidas de Google Drive se unen) u otro proyecto. Se copia al proyecto; el original no se toca.
- **La SD**: lo que tienes ahora en tu SD. La SD solo se lee.

Al soltar un modpack sobre la ventana también aparece **Nuevo proyecto con él**.

**Abrir uno.** Haz clic en su tarjeta en el inicio. Cada tarjeta muestra la edición, cuántos mods tiene y cuántos no van, lo que encontró el Doctor y cuándo se empacó y se copió a la SD por última vez. **Borrar** mueve el proyecto a la papelera de la Biblioteca (`.trash\Projects`), de donde lo puedes recuperar.

**Modpacks de antes.** Los packs y packs en creación que estaban en la Biblioteca antes de los proyectos salen en el inicio con **Convertir en proyecto**. El proyecto empieza como copia exacta (un pack en creación conserva qué mods no van). Los originales quedan donde están: bórralos tú cuando ya no los necesites.

> Nunca se escribe nada fuera del proyecto: un proyecto copia su fuente, así que nada de lo que hagas en él puede llegar al original. Para ahorrar espacio puedes encender **Enlazar archivos con su origen** en Ajustes: en el mismo disco el proyecto comparte entonces los archivos con el original. La app nunca escribe dentro de un archivo compartido, pero otro programa que guarde un archivo en su lugar cambiaría también el original.

## Trabajar en un proyecto {#pack}

Con un proyecto abierto, el menú de la izquierda tiene:

| Página | Para qué sirve |
| --- | --- |
| Resumen | Edición, plugins activos, peso de Data, texturas que más pesan y cuántos problemas hay de cada tipo. |
| Doctor | Todos los problemas encontrados, con su explicación y su arreglo. |
| Agregar mods | La cola: sueltas zips, 7z, rar o carpetas y la app dice qué es cada uno. |
| Mods | Los mods del proyecto: qué va, la carpeta de cada mod, página de Nexus, renombrar, extraer, quitar, receta, versiones para Switch y conflictos de archivos. |
| Orden de carga | La lista con flechas, LOOT y SSEEdit. |
| Texturas y audio | Peso de texturas por BSA, formatos y la Dieta. |
| Historial | Cada cambio, con **Deshacer**. |
| Llevar a la SD | Empaca el proyecto y copia a la SD solo lo que cambió. |
| Convertir mods | Un mod de PC o varios a la vez a este proyecto. |
| Biblioteca | La Biblioteca de mods y el Catálogo. |
| Ajustes | Idioma, carpetas, Nexus, herramientas externas y créditos. |

**La barra de abajo** está siempre a la vista: a la izquierda los bytes de la lista de carga `.ccc` (máximo 4096), en el centro los problemas graves, a la derecha la lista de archivos más larga del ini (máximo 1024 caracteres).

**Historial y deshacer.** Cada cambio guarda una copia de lo que había antes en la carpeta `.skynx` del proyecto. **Deshacer** devuelve esos archivos. Si algo sale mal a mitad de un cambio, el proyecto vuelve a como estaba.

**Editar a mano.** `Mods\` y `Base\` muestran siempre el proyecto como está. Si cambias o agregas un archivo ahí con otro programa (una ini, una textura, un plugin dentro de la carpeta de un mod), entra al proyecto la próxima vez que la app lo revisa, como un cambio en el Historial («Cambios hechos en la carpeta del proyecto»). Un archivo que borras ahí a mano vuelve a aparecer: para sacar un mod, desmárcalo o quítalo en Mods. Si el mismo archivo cambió a mano y en la app, o dos archivos que agregaste caerían en el mismo lugar, queda la versión de la app y los tuyos se guardan en `.skynx\mirror-conflicts`. Los léeme e imágenes que dejes junto a un mod se quedan ahí y no van al juego.

Los archivos de `Mods\` son los del proyecto (enlazados, no copiados, para ahorrar espacio). Un programa que guarde un archivo en su lugar ahí cambia el proyecto directamente: la app lo nota y te avisa, pero ese cambio no se puede deshacer desde el Historial. Las inis y la lista de carga de `Base\` son copias reales, así que editarlas siempre se puede deshacer.

## Mods en un proyecto {#mods}

Cada mod del proyecto tiene una fila y una carpeta en `Mods\`. En cada fila:

- La casilla: al desmarcarla, el mod **no va**. Sus plugins salen de la lista de carga y sus BSA de las inis (los números de arriba se actualizan), pero sus archivos se quedan en el proyecto, y al volver a marcarla regresa a su lugar. Si otro mod lo usa como master, la app ofrece sacarlos juntos.
- **Carpeta** abre la carpeta del mod en `Mods\`.
- **Renombrar** muestra cuántos bytes del `.ccc` ganas o pierdes y cambia plugin, BSA, voces, FaceGen, masters y lista de una vez. El mod conserva su carpeta.
- **Extraer** copia los archivos de sus BSA a la carpeta que elijas.
- **Quitar** lo saca de la lista y de las inis y mueve sus archivos a la papelera del proyecto (se puede deshacer). Si otros plugins lo usan como master, los nombra y ofrece quitarlos en el mismo paso; un plugin que comparte su mod con otros (parches de un mismo FOMOD) sale solo y el resto de ese mod se queda.
- La etiqueta de Nexus, cuando reconoce el mod (ver [Nexus y LOOT](#h-nexus)).

Arriba: **Empacar**, la **Carpeta Mods** y las formas de agregar:

- **Agregar mods**: la cola, para descargas y mods de Switch ([Agregar mods](#h-add)).
- **Desde un modpack…**: escoge la carpeta de un modpack, su `.zip`/`.7z`/`.rar` u otro de tus proyectos; marca los mods que quieres y la app los trae con los masters que necesitan, y deja por fuera lo que el proyecto ya tiene. Un comprimido se extrae una vez mientras el proyecto está abierto; la fuente solo se lee. La lista se ordena por nombre, como en el pack o por tamaño.
- **Traer del Catálogo**: mods de cualquier proyecto o de la Biblioteca de mods ([Biblioteca de mods y Catálogo](#h-library)).

También arriba: **Revisar conflictos de archivos** (cada archivo que trae más de un BSA, y cuál gana según el orden de carga), **Receta del pack** (de dónde salió cada mod, sus opciones de FOMOD y de conversión, y qué cambió; **Exportar para compartir (.md)** la escribe con los enlaces de Nexus y sin rutas de tu PC) y la barra de Nexus.

### Comportamientos (FNIS / Nemesis)

Los mods con animaciones nuevas (Flower Girls, mods de poses, de combate) no traen los archivos de comportamiento del juego: traen una lista (`FNIS_<mod>_List.txt`) o un parche de Nemesis, y un generador escribe `0_master.hkx`, `defaultmale.hkx` y los demás para todo el pack. Sin ese paso esas animaciones no se ven.

Al convertir un mod de PC, la app guarda lo que hace falta para generarlos (listas, animaciones, parche de Nemesis, como originales de PC). Cuando el proyecto tiene mods así, la página Mods muestra el recuadro **Comportamientos** con su estado: sin generar, desactualizados (cambiaron esos mods) o al día.

**Generar comportamientos**:

1. La app arma una carpeta de trabajo con una copia de Nemesis y de esos archivos (tu Skyrim no se toca) y abre Nemesis.
2. En Nemesis: **Update Engine**, marca los parches que la app te nombra, **Launch Nemesis Behavior Engine**, y ciérralo cuando diga *Behavior generation complete*.
3. En la app: **Listo**. Los archivos que Nemesis escribió se pasan a Switch y entran al proyecto como un mod más, «SkyNX - Generated behaviors», en un BSA de la lista del ini con más espacio. Volver a generar reemplaza ese mod.

Necesita Nemesis, HavokBehaviorPostProcess y hkxc en la carpeta de herramientas ([Tu equipo](#h-setup)). Al empacar, la app avisa si quedaron sin generar o desactualizados. Los mods que piden SKSE (SexLab, por ejemplo) no funcionan en Switch aunque sus comportamientos se generen.

## Agregar mods {#add}

Suelta archivos o carpetas sobre la ventana, o usa **Agregar a la lista**. Cada uno sale en una tarjeta que dice qué es y qué hacer:

| La app dice | Qué hacer |
| --- | --- |
| Mod de Switch | **Revisarlo** y **Agregar tal cual**. Va directo al proyecto. |
| Mod de PC | **Convertir**: pasa a Convertir mods. |
| Mixto | Tiene partes de Switch y de PC: conviértelo. |
| FOMOD | Tiene instalador: Convertir mods abre el asistente. |
| Modpack | **Nuevo proyecto con él**, o **Traer mods de ahí** al proyecto abierto. |

Cada tarjeta muestra también la etiqueta de Nexus cuando reconoce el mod. Con dos o más mods de PC en la cola aparece **Convertir todos los de PC**, que los manda juntos a Convertir varios mods. La tarjeta de un mod de Switch tiene **Comparar con el original**: le indicas la versión de PC y la app compara registros y archivos.

Al leer un comprimido la app deja por fuera la basura de Mac (`__MACOSX`, `._Mod.esp`). Si el mod trae versiones lado a lado (por ejemplo `Mod_AE` y `Mod_SE`), usa la de la edición del proyecto y lo dice en una nota. Los `.rar` abren con 7-Zip o con el `tar.exe` de Windows; si ninguno puede, la tarjeta lo dice y basta con extraerlo y soltar la carpeta.

**Fuentes** (Sovngarde y similares): el `Interface\FontConfig.txt` de un mod de fuente queda suelto en `Data\Interface`, porque las fuentes solo cargan así; sus librerías (`fonts_*.swf`) van en el BSA como siempre. Solo puede haber una fuente activa: la última que agregas reemplaza a la anterior, y deshacer ese paso la devuelve. El Doctor avisa si un `FontConfig.txt` quedó dentro de un BSA (y lo saca suelto) o si pide una librería que no está en el pack.

**Masters renombrados.** Si un mod usa como master un plugin que en este proyecto tiene otro nombre (porque lo acortaste al convertir o con Renombrar), al agregarlo la app lo apunta al nombre nuevo, igual que al convertir. Si uno ya entró apuntando al nombre viejo, el Doctor lo marca como master faltante y ofrece **Apuntarlo a …**, que es seguro.

**Nombres de plugin.** En Convertir mods el nombre se escribe sin la extensión, como en Renombrar: la extensión aparece al lado y se conserva sola.

## El Doctor {#doctor}

Cada problema tiene una gravedad: **Grave** (algo no va a cargar o el juego se puede cerrar), **Revisar** (probablemente falla o se ve mal), **Ahorro** (se puede ganar memoria) y **Dato**. Los filtros de arriba muestran un tipo a la vez.

Cada botón de arreglo muestra antes exactamente qué va a cambiar. **Arreglar lo seguro** aplica de una los arreglos marcados como seguros; el resto va uno por uno después de su vista previa. **Volver a revisar** lee el proyecto de nuevo. Los mods que no van quedan por fuera del Doctor a propósito.

Arreglos frecuentes: renombrar archivos que Google Drive dañó (`Ryn_s` a `Ryn's`), activar plugins que están en Data pero no en la lista, quitar del ini BSA que no existen, crear el archivo SEQ de un plugin con misiones de inicio, extraer mods que quedaron comprimidos dentro de Data, pasar un `.esl` a `.esp` en SE y mover a la papelera copias sobrantes. Ningún arreglo deja el `.ccc` por encima de 4096 bytes: si no cabe, la app avisa y no cambia nada.

Con los BSA del juego configurados, el Doctor también revisa si de verdad están los scripts, meshes y texturas que pide cada plugin. Un BSA que el ini nombra pero no existe se juzga por sus archivos: si no falta nada (un convertidor juntó varios BSA en uno), baja a Dato y quitarlo del ini es seguro.

**La lista del juego.** Para eso la app arma una lista de todo lo que trae el juego: cada archivo dentro de sus BSA, más lo que piden los propios plugins del juego (`Skyrim.esm`, los DLC y el Creation Club) y las texturas que nombran sus mallas. Se arma una sola vez desde la carpeta de archivos del juego y queda guardada: después puedes borrar los BSA de esa carpeta y la lista sigue igual. Si vuelves a copiar un BSA (por una actualización del juego), lo lee de nuevo. Los `.esm` y `.esl` sí deben quedarse, porque xEdit los necesita. En Ajustes ves cuántos archivos tiene, si le falta algún BSA básico del juego y cuáles ya no están en la carpeta.

**Lo que no es un faltante.** Hay cosas que el Doctor ya no marca como faltantes, o que pasa a Dato:
- **Lo que el juego mismo pide.** Los registros de raza del juego nombran `upperbodyhumanmale.egt`, que no existe en ningún BSA; un mod que copia esa raza (Mortal Enemies, el USSEP) no tiene ningún problema.
- **Fragmentos de script** (`QF_`, `PRKF_`, `SF_`, `TIF_`…): son los scripts pequeños de una etapa de misión, un perk, una escena o un diálogo. Si faltan, es porque el autor no los incluyó, y pasa igual en PC.
- **Mapas de detalle** (`_p` relieve, `_m`/`_em`/`_s` brillo, `_g` resplandor, `_sk` piel): sin ellos la superficie se ve plana u opaca, nunca morada.
- **Rutas mal escritas por el autor**: un espacio antes de la extensión o junto a una carpeta, sin extensión, o una textura donde va un modelo. Ningún mod puede traer ese archivo.

**Scripts y sonidos que corren en la consola.** En la revisión completa, el Doctor también mira lo que de verdad corre (de cada script, la copia que gana en la Switch):
- **Scripts base de SKSE dentro de un mod** (Grave): la copia de PC de `Quest`, `Actor`, `Game` y los demás scripts base, colada al empacar un mod. En Switch reemplaza a la del juego. El arreglo los saca del BSA y deja el resto del mod.
- **Scripts que USSEP corrige y otro mod reemplaza** (Revisar): la copia del otro mod es la que corre, y si no se hizo sobre USSEP se pierden sus arreglos. Si una misión del juego base se queda quieta, mira aquí primero.
- **Scripts del juego que reemplazan los mods** (Dato): así funcionan muchos mods; la lista dice cuáles, para tener sospechosos.
- **Scripts que buscan plugins que no cargan** (Dato): `[off]` está en el pack pero apagado, `[gone]` no está. Casi siempre es una revisión opcional; importa después de quitar un mod.
- **Mods que mantienen scripts corriendo solos** (Dato): cuántos scripts corren, cuántos se repiten con temporizador y cuántos reaccionan a eventos frecuentes. Es una guía para listas con muchos scripts.
- **Sonidos dañados** (Revisar): lee completas las voces y la música y avisa las que están cortadas o no cuadran. Lo leído se guarda por BSA, así que la siguiente revisión solo lee lo que cambió.

**Plugin vacío con su BSA.** Pasar el BSA al ini libera bytes del `.ccc`, pero lo del ini carga antes. Antes de ofrecerlo, el Doctor revisa archivo por archivo quién ganaría después. Si alguno cambia de ganador (las texturas de Noble Skyrim le ganan a los mods que cargan antes que su plugin; en el ini perderían), dice que lo dejes así, muestra cada archivo y no ofrece el arreglo. Si nada cambia, el arreglo es seguro.

**Nombres largos de plugins.** Cuando el `.ccc` pasa de unos 3.500 bytes, el Doctor ofrece **Acortar los nombres** de los plugins activos con nombre largo, todos en un solo paso que se puede deshacer: el nombre antes del guion al estilo Enai (`Wintersun - Faiths of Skyrim.esp` → `Wintersun.esp`) o la primera palabra con iniciales (`AmazingFollowerTweaks.esp` → `AmazingFT.esp`). Nunca un nombre que ya tenga un plugin o un BSA, ni los del USSEP y el USCCCP. Todo lo que usa cada nombre lo sigue. Las partidas guardadas recuerdan los nombres: hazlo antes de la partida de verdad.

**Nombres en otro idioma.** Algunos ports vienen de una versión traducida: en The Ordinary Women, 61 mujeres tenían el nombre en ruso (Gerdur salía como «Гердур»). Si el juego está en un idioma con alfabeto latino, el Doctor avisa los nombres en otro alfabeto y ofrece **Usar los nombres del juego**, que pone el nombre original (lo lee del `.esm` y de los textos del juego en `Skyrim - Interface.bsa`; por eso conviene dejar ese BSA en la carpeta). Solo cambian los nombres. Los registros nuevos del mod no tienen un nombre del juego al cual volver; esos solo se muestran.

**Copiar informe** y **Guardar como .md** sacan todos los hallazgos con todos sus detalles (sin el «+N») en Markdown, para pegarlos en un chat o guardarlos.

## Orden de carga {#order}

La lista de plugins con flechas (o arrastrándolos). Los masters deben quedar arriba de quien los usa; las filas en rojo dicen qué falla. **Guardar orden** la escribe (se puede deshacer).

- **Sugerir orden (LOOT)** ordena por masters, reglas y grupos de LOOT, y respeta tu orden donde nada dice otra cosa. El Creation Club y los archivos del juego no se mueven. A los plugins que LOOT no conoce les puedes dar una categoría; tu elección se recuerda para todos los proyectos.
- **Abrir en SSEEdit** pregunta si trabajar sobre el proyecto o sobre una copia. Con copia, al cerrar SSEEdit la app pregunta qué hacer: traer los cambios (quedan en el Historial), guardar la copia para después o borrarla. **Traer cambios de SSEEdit** lo hace a mano.
- **Mostrar el Creation Club** muestra las entradas de CC de la lista.

**Copiar orden** copia la lista como está en pantalla (con los cambios sin guardar y los masters de cada plugin), para pegarla en un chat o una nota.

Las entradas del Creation Club muestran su nombre (Fishing, Survival Mode…) al lado del archivo. Si la lista del juego tiene el Creation Club, el Doctor avisa de las líneas del CC que el juego no tiene (ni plugin ni BSA; la lista de la Switch trae cinco así) y ofrece quitarlas: liberan bytes del `.ccc` sin cambiar nada en el juego.

La casilla de cada plugin lo **activa o apaga** sin sacarlo del proyecto (queda con `#` en la lista). Empacar deja por fuera las líneas apagadas, y también los BSA de ese mod que estén en los inis (`sResourceArchiveList`...), porque esos cargan aunque el plugin no esté: un BSA sale del ini cuando todos los plugins de su mod están apagados.

## Texturas y audio {#textures}

El peso de las texturas activas por BSA, los formatos en uso (NVN es el propio de Switch; DDS es de PC) y cuántos mods tienen todavía texturas o sonidos de PC. La columna **Con dieta** muestra cuánto ocuparía cada BSA con la Dieta Switch 1. **Dieta** (en cada BSA con texturas) pregunta la regla de tamaño y el tamaño máximo, muestra el cálculo y lo aplica (se puede deshacer). El total suma todas las texturas; el juego solo carga lo que está cerca, así que úsalo para comparar mods y proyectos.

Si las texturas no se han leído todavía, **Volver a revisar** las lee.

## Empacar y llevar a la SD {#sd}

**Empacar** (el botón dorado de arriba, en Resumen o en la página Mods). Antes, la app avisa si falta algo de la rutina: plugins que LOOT todavía movería, problemas graves del Doctor o arreglos de rutina pendientes (SEQ, BSA que pierden scripts, lista del ini llena). Puedes ir a resolverlo o empacar de todas formas. Empacar arma la carpeta `Switch\` del proyecto: las dos carpetas para la consola, con cada mod que va y sin los que no van, sin el historial ni los registros de la app. Antes revisa que cada plugin que va tenga sus masters. `Switch\` tiene copias reales, y cada Empacar copia solo lo que cambió desde el anterior. Lo que haya en `Switch\` que no puso la app, o que se cambió a mano, se mueve a la papelera del proyecto (`.skynx\trash`), nunca se borra. Después de empacar puedes llevarlo a la SD, abrir la carpeta o cerrar.

**Llevar a la SD.** Escribe la unidad de la SD (por ejemplo `E:\`) o su carpeta `atmosphere\contents` y oprime **Ver los cambios**. Un proyecto siempre se empaca antes, así que lo que va a la SD es exactamente lo que hay en `Switch\`. La app solo toca `01000A10041EA000` y `01000A10041EB009`: copia lo nuevo o cambiado, borra lo que el proyecto ya no tiene y antes guarda un respaldo de lo que reemplaza en `.skynx\sd-backups`. Revisa el espacio libre antes de copiar. **Mejor copia completa** copia todo de nuevo, para SD editadas a mano. Si la SD todavía no tiene las carpetas de Skyrim (una SD nueva, o sin `atmosphere\contents` aún), es una **primera copia**: todo entra nuevo, no hay nada que respaldar y la app crea las carpetas. Para no equivocarse de unidad, solo lo hace si la carpeta parece la raíz de una SD de Switch (tiene `Nintendo`, `switch`, `bootloader` o `atmosphere`). Cada archivo se escribe con otro nombre, se fuerza a la tarjeta y solo entonces toma su nombre real; si la copia falla a mitad, la SD vuelve a como estaba. Saca la SD con **Expulsar** de Windows. La SD tiene que tener letra de unidad: métela en el lector del PC o usa hekate, Tools, USB Tools, SD Card; MTP (DBI) no da letra de unidad. Un archivo que solo cambió de nombre en el pack (por ejemplo, al acortar nombres de BSA) se renombra en la SD en vez de copiarse otra vez.

**SkyNX Mods en la consola.** SkyNX Mods es el homebrew de este proyecto para activar y apagar mods desde la Switch (está en `extras\nxmods`; se compila con `construir_nro.bat` y el `SkyNXMods.nro` va a la carpeta `switch` de la SD). Cada vez que la app copia a la SD, deja en `switch\SkyNXMods` la lista completa del proyecto (con los apagados) y qué BSA de los inis son de qué plugin, así SkyNX Mods también saca y devuelve esos BSA. Si apagaste o activaste algo en la consola, **Ver los cambios** lo muestra arriba y ofrece **Usar lo de la consola**, que lo pasa al proyecto (queda en el Historial). Si copias sin eso, la consola vuelve a la lista del proyecto.

Además deja `skyrim-info.txt`: qué es cada plugin (nombre, descripción y sus BSA), para que SkyNX Mods lo muestre con su tamaño en la SD. La descripción sale de lo que escribas en la página Mods (**Describirlo**), del resumen de Nexus si ya lo trajiste, o del propio plugin; las del Creation Club ya vienen en la app.

También mide cuánto pesa cada mod: los registros del plugin (que quedan en memoria todo el tiempo que esté activo) y, dentro de sus BSA, cuánto es de texturas, mallas y audio. SkyNX Mods 1.3 lo muestra como carga ligera, media o pesada, con el total de registros de lo activo arriba. Es una estimación: las texturas y mallas solo ocupan memoria mientras lo suyo está en pantalla, y el audio se lee de la SD al sonar. La primera copia después de agregar mods tarda un poco más mientras mide los BSA nuevos; luego queda guardado en el proyecto.

SkyNX Mods 1.3 también lee los informes de crash que Atmosphère deja en `atmosphere\crash_reports` (un informe y una captura de cada vez que el juego se cierra por error): **− Más**, **Crashes de Skyrim**.

## El taller {#workshop}

El taller es para mods sueltos, sin proyecto: para cuando solo quieres convertir un mod y listo. Cada trabajo es una **mesa**: un espacio privado en `Library\Workshop\<nombre>` que nunca va a la SD. Al terminar, **Guardar** deja el resultado en `Library\Converted`, listo para cualquier proyecto y para el Catálogo.

| Inicio » Taller | Qué hace |
| --- | --- |
| Convertir un mod de PC | Pregunta la edición y abre Convertir mods sobre una mesa vacía ([un mod](#h-one-mod)). |
| Convertir varios mods | Lo mismo, varios a la vez, cada uno guardado por separado ([varios mods](#h-many-mods)). |
| Editar un mod de Switch | Trae un mod a la mesa para renombrar, extraer BSA, abrir en SSEEdit y guardar. |
| Juntar mods en un BSA | Varios mods bajo un plugin, con sus BSA juntos. |
| Juntar plugins (merge) | Un merge con zMerge de zEdit, guiado. |

En una mesa el menú cambia a: Mesa, Convertir mods, Juntar BSA, Juntar plugins, Historial y Todas las mesas. **Mesas guardadas** en el inicio las vuelve a abrir. **Descartar esta mesa** la borra; lo que ya guardaste en la Biblioteca se queda.

## Convertir o editar un mod {#one-mod}

Convertir mods » **Un mod** (desde el taller, o dentro de un proyecto, donde el mod entra directo).

1. Elige la carpeta o el comprimido del mod (`.zip`, `.7z`, `.rar`) y oprime **Leer el mod**. Todavía no se escribe nada.
2. Elige la **Dieta de texturas**: **Dieta Switch 1** (la que viene por defecto: 1K, mapas y objetos menores a 512), **Reglas de Koka** (1K en general, 2K para personajes), **Extrema** (512, para packs con muchos mods) o **Tamaño original** (sin regla de tamaño). Encima de cualquiera, **Tamaño máximo** limita el lado más grande a 256, 512, 1K, 2K o 4K. Para texturas a 2K en todo, elige Tamaño original y 2K. Las texturas nunca se agrandan.
3. Elige el formato: **Formato nativo de Switch (NvnTexpkg)**, y **BC1** en texturas opacas (la mitad de memoria). Sin NvnTexpkg las texturas quedan en DDS forzado a DXT5, como hace Koka.
4. Elige el **Empacado**. El que viene por defecto, **Un BSA en los inis**, pone todo en un BSA de nombre corto y lo anota en la lista del ini que tenga más espacio: la forma estable de cargar de Koka, con un nombre por mod en vez de dos, así caben más mods en el ini. Si ninguna lista tiene espacio, el mod queda en un BSA con el nombre del plugin y la app te avisa. Las otras opciones: BSA con el nombre del plugin, un solo BSA con el nombre del plugin, o dos BSA en los inis (meshes y texturas aparte, como hace Koka).
5. Revisa los nombres de los plugins. La app propone nombres que Google Drive no daña, y **Corto** ahorra bytes del `.ccc`.
6. Oprime **Convertir y agregar al pack**. Arriba se ven el `.ccc` y la memoria de texturas con el mod incluido.

El resultado queda en el proyecto (o en la mesa) y una copia en `Library\Converted`. Lo que un mod de Switch no puede usar (léeme, fuentes, plugins `.dll` de SKSE) queda por fuera y se lista.

**Voces a medio portar.** Algunos ports traen restos que el juego nunca lee: voces guardadas con nombres anteriores del plugin, tomas viejas (`-old1`), la carpeta de lip-sync del Creation Kit y copias `.temp.wav`. Se quedan por fuera y se listan. Si una línea quedó como `.fuz` vacío con su `.temp.wav` al lado (pasa en The Tempest Isle NX), la app la convierte a partir de ese `.wav`.

**Instaladores FOMOD.** Un mod con instalador abre primero el asistente FOMOD: sus pasos, opciones, imágenes y descripciones, como en un gestor de mods. Los parches de mods que no están en tu proyecto se esconden. **Instalar estas opciones y seguir** pasa a las opciones de conversión.

**Editar un mod de Switch.** Taller » **Editar un mod de Switch**. En la mesa puedes renombrar sus plugins (voces, FaceGen, BSA y masters siguen el nombre), extraer sus BSA, abrirlo en SSEEdit y **Guardar** en `Library\Converted`.

## Varios mods a la vez {#many-mods}

**Convertir varios mods**: Taller » Convertir varios mods, la pestaña **Varios a la vez** de Convertir mods, o **Convertir todos los de PC** en Agregar mods. Cada mod sale en una tarjeta angosta con su dieta, tamaño máximo, empacado, formato nativo y nombres de plugins; **Más opciones** muestra el resto. **Para todos** aplica lo mismo a todas las tarjetas. Los FOMOD se eligen dentro del lote con **Elegir opciones**. Arriba se ven el `.ccc` y la memoria de texturas con todo sumado. Antes de empezar, la app revisa que ningún nombre se repita y que el `.ccc` alcance; convierte primero los mods que otros necesitan y les apunta los nombres finales. Si uno falla, los demás siguen, los que lo necesitaban se detienen con la razón, y el que falló queda con **Leerlo de nuevo**.

**Juntar mods en un BSA.** Escoge los mods en el orden en que deben cargar. Sus BSA se vuelven uno, o unos pocos cuando pasan de 1,9 GB, con el nombre de un plugin para que carguen con él. Los plugins siguen separados, así que el `.ccc` no cambia, pero bajan las listas del ini y la cantidad de archivos.

**Juntar plugins (merge).** El merge lo hace zMerge (dentro de zEdit); la app prepara y ordena:

1. Agrega a la mesa los plugins que vas a juntar.
2. **Preparar y abrir zEdit**. La primera vez, crea en zEdit un perfil de Skyrim SE con la carpeta que muestra la app como ruta del juego.
3. En zMerge, crea un merge con los plugins de la mesa y constrúyelo.
4. **Traer** la carpeta que hizo zMerge. Los plugins fusionados salen de la mesa.
5. Junta los BSA bajo el merge y guarda la suite en la Biblioteca.

## Biblioteca de mods y Catálogo {#library}

La Biblioteca de mods (barra de arriba » **Biblioteca**) tiene dos pestañas.

**Mods.** Los mods que tienes a mano: convertidos aquí (`Library\Converted`), descargados con el botón de Nexus o importados desde un zip o una carpeta. Cada uno con la opinión rápida del Doctor y sus botones: **Agregar al proyecto actual**, **Editar en el taller**, abrir carpeta y Borrar. Los modpacks no se guardan aquí: un modpack se vuelve proyecto (si importas uno aquí, la app lo dice).

**Catálogo.** Todos los mods de todos los proyectos y de la Biblioteca de mods, una vez cada uno, con su categoría y su etiqueta de Nexus. Si un mod está en varios proyectos, eliges la versión. Marca mods y elige: un **Proyecto nuevo**, o **Agregar a** el proyecto abierto (los que ya tiene se saltan y se listan con la razón). Antes de crear, el panel muestra el `.ccc`, el ini y las texturas.

## Nexus y LOOT {#nexus}

La app reconoce los mods aunque tengan el nombre cambiado y enlaza su página en Nexus (Skyrim Special Edition, donde viven también los de Anniversary). De más a menos seguro:

1. Lo que tú confirmaste (se recuerda por el contenido del plugin, así que lo sigue a otros proyectos).
2. La descarga: lo que bajó el botón Mod Manager Download sabe su mod y su versión.
3. La lista de LOOT, consultada con el nombre actual y con los nombres originales que la app registró.
4. Un merge muestra los mods que tiene adentro.

La etiqueta aparece en Mods, en las mesas, en Agregar mods y en el Catálogo. El **?** al lado abre la ficha del mod: otras páginas posibles, **Es este**, **Buscar en Nexus**, o pegar el enlace a mano.

**Versiones para Switch** mira por dentro cada archivo del mod en Nexus. Una versión con plugins de SKSE (`.dll`) no sirve en Switch; una que nombra SKSE, Address Library, PapyrusUtil o SPID queda en **Revisar**. Muestra la tuya, la última y la mejor para Switch. **Tengo esta** le dice cuál tienes.

| Función | Necesita |
| --- | --- |
| Reconocer por LOOT | La lista de LOOT (**Descargar la lista de LOOT para reconocer más**). |
| Nombres, versiones, actualizaciones, Versiones para Switch | Tu API key personal de Nexus en Ajustes. Se queda solo en este PC. |
| Botón Mod Manager Download | Activarlo en Ajustes (sirve con cuenta gratis). |
| Sugerir orden | La lista de LOOT; la primera vez se descarga sola. |

## Herramientas y Ajustes {#tools}

**Ajustes** tiene: idioma, **Al abrir la app, volver al pack que estaba abierto** (encendido por defecto: también sirve al instalar una versión nueva; si cierras el pack con Abrir otro, la próxima vez empieza en la bienvenida), carpeta de herramientas, inis de la consola para proyectos nuevos, carpeta de BSA del juego, carpeta de USSEP, carpeta de la Biblioteca, **Enlazar archivos con su origen** (apagado por defecto), tu API key de Nexus, el botón Mod Manager Download, las herramientas externas, **Ver todo tu equipo** y los créditos.

Las herramientas externas (SSEEdit, zEdit, NifSkope, BAE, Cathedral Assets Optimizer) se buscan en `C:\SkyNX\Tools` o se eligen a mano. La app las abre sobre el proyecto o sobre una copia, como explica cada página. En [Tu equipo](#h-setup) está qué activa cada una.

## AE y SE {#ae-se}

Un mod hecho para una edición casi siempre sirve en la otra; la app hace el ajuste al entrar (Agregar mods, Convertir, el lote, Desde un modpack y el Catálogo) y deja una nota en la tarjeta del mod.

| Caso | Proyecto AE | Proyecto SE |
| --- | --- | --- |
| Mod de SE | Entra tal cual. | Entra tal cual. |
| `.esp` con marca ESL (la mayoría de mods NX para AE) | Tal cual. | Se le quita la marca; SE la ignoraría. |
| Encabezado HEDR 1.71 | Tal cual. | Baja a 1.70 si ningún registro propio usa form IDs bajos. Si los usa, se queda y el Doctor lo explica. |
| Un `.esl` de verdad | Tal cual. | No entra directo: pásalo por Convertir mods o usa el arreglo del Doctor **Pasarlo a .esp para SE**. |
| Necesita contenido del Creation Club | Entra y se activa. | Queda en Data pero fuera de la lista: SE no tiene CC. |
| Carpetas `_AE` y `_SE` en un mismo mod | Usa la de AE. | Usa la de SE; si solo hay de AE, usa la que no dice AE. |

En SE la lista de carga es el archivo `Plugins` y no tiene el límite de bytes del `.ccc`.

## Límites de Switch {#limits}

| Límite | Valor | Dónde se ve |
| --- | --- | --- |
| Lista de carga `Skyrim_aoc.ccc` (AE) | 4096 bytes; el juego deja de leer lo que pase de ahí | Barra de abajo, Mods, Convertir, Catálogo |
| Listas de archivos del ini (`sResourceArchiveList`, `sResourceArchiveList2`) | 1024 caracteres cada una; el ini del idioma (`Skyrim_en.ini`) manda sobre `Skyrim.ini`. Cerca del límite, el Doctor ofrece acortar los nombres de los BSA de mods que carga el ini (cargan en el mismo lugar, solo cambia el nombre) | Barra de abajo, Doctor |
| BSA | 1,9 GB por archivo; al juntar BSA la app parte en varios | Juntar BSA |
| Orden de los BSA | Depende del tipo de archivo. **Scripts:** un BSA del ini le gana a uno que carga por el nombre de su plugin, al revés que en PC. Visto en la consola: el `USSEP.bsa` de Koka (en el ini) le quitó sus scripts a Growl y a Sacrosanct, y el `Skyrim - Misc.bsa` del juego le quitó a Quick Start el suyo; con sus BSA en el ini, después de los otros, funcionaron. **Texturas y modelos:** como en PC; las texturas de Noble Skyrim, que carga por su plugin, se ven sobre las del juego | Doctor (mods que pierden scripts), Revisar conflictos de archivos |
| IDs de registro por debajo de 0x800 (rango ESL extendido, Skyrim PC 1.6.1130, dic. 2023) | La versión de Switch es de 2022 y probablemente no los carga; HEDR 1.71 sin esos IDs sí carga | Agregar mods, Doctor |
| Plugins de SKSE (`.dll`) | No funcionan en Switch | Convertir (quedan por fuera), Versiones para Switch |
| Texturas | Formato NVN de Switch, o DDS de PC forzado a DXT5; memoria limitada | Texturas y audio, Dieta |
| Animaciones, comportamientos, esqueletos (`.hkx`) | La Switch usa su propio formato de Havok. Las animaciones se convierten cambiando unos bytes; los comportamientos, esqueletos y archivos de Oldrim necesitan HavokBehaviorPostProcess (y hkxc para los de 64 bits) | Convertir |
| Nombres con apóstrofo o símbolos | Google Drive los cambia por `_` y el plugin deja de cargar | Doctor (nombre seguro) |

## Carpetas en disco {#folders}

Todo vive en `C:\SkyNX`. La app no escribe fuera de estas carpetas.

| Carpeta | Qué guarda |
| --- | --- |
| `C:\SkyNX\SwitchNX Studio.exe` | La app. Se reconstruye con `construir.bat` desde `SkyNX Studio`. |
| `C:\SkyNX\SkyNX Studio` | El código fuente, `README.md`, `LEEME.md` y `construir.bat`. |
| `C:\SkyNX\Tools` | texconv, ffmpeg, VGAudioCli, NvnTexpkg y sus DLL; SSEEdit, zEdit, NifSkope, BAE y CAO en subcarpetas. |
| `C:\SkyNX\Vanilla\INIs` | Las inis limpias de la consola para proyectos nuevos. |
| `C:\SkyNX\Vanilla\BSAs` | Los archivos del juego de `romfs\Data`: sus BSA (`Skyrim - *.bsa`, `cc*.bsa`) y sus plugins (`.esm`, `.esl`). Con la lista del juego ya armada, los BSA se pueden borrar menos `Skyrim - Interface.bsa`, que trae los textos del juego; los plugins se quedan para xEdit. |
| `C:\SkyNX\Base Mods\USSEP` | El USSEP de KokaNX (All_CC, No_CC, SurvivalMode). |
| `C:\SkyNX\Library\Projects` | Tus proyectos, una carpeta cada uno. |
| `C:\SkyNX\Library\Mods` | Mods sueltos tal como llegaron. |
| `C:\SkyNX\Library\Converted` | Cada mod que la app convierte o guarda desde una mesa. |
| `C:\SkyNX\Library\Workshop` | Las mesas del taller. |
| `C:\SkyNX\Library\Downloads` | Lo que baja el botón Mod Manager Download de Nexus. |
| `C:\SkyNX\Library\.trash` | Proyectos borrados, hasta que la vacíes a mano. |
| `C:\SkyNX\Library\Packs`, `Drafts` | Modpacks de antes de los proyectos, hasta que los borres. |
| `%APPDATA%\SwitchNX Studio` | Ajustes, la masterlist de LOOT y cachés. |

## Problemas comunes {#problems}

| Lo que ves | Por qué pasa | Qué hacer |
| --- | --- | --- |
| «Trae varias versiones; usé la de esta edición» | El mod trae carpetas `_AE` y `_SE` con el mismo plugin | Nada. Si querías la otra, extrae el comprimido y agrega esa carpeta. |
| «… sigue comprimido» (Grave) | El proyecto trae mods en `.7z` dentro de Data | Doctor » **Extraer … en Data**. |
| «No puedo abrir archivos .rar» | No hay 7-Zip y el `tar.exe` de Windows no pudo | Instala 7-Zip, o extráelo y suelta la carpeta. |
| «… no tiene archivo SEQ» | El plugin tiene misiones de inicio y no trae su `.seq` | Doctor » crear el SEQ. |
| «El .ccc llegaría a … bytes» | Lo que agregas no cabe en los 4096 bytes | Acorta nombres (**Renombrar**, **Corto**) o desmarca un mod. No se escribe nada hasta que quepa. |
| «… tiene caracteres que Google Drive cambia» | Apóstrofos o símbolos en el nombre | Doctor » renombrar a la versión segura. |
| Un plugin como `Ryn_s` no carga | Drive ya dañó el nombre | Doctor » renombrarlo y mover la copia sobrante a la papelera. |
| Texturas en formato de PC | Un mod de Switch con alguna textura sin convertir | Si se ven moradas o negras, conviértelo o usa la Dieta. |
| «No encontré la carpeta atmosphere» | En Llevar a la SD la ruta no es la raíz de la SD | Escribe la unidad (`E:\`) o su carpeta `atmosphere\contents`. |
| «El ini pide X.bsa y no existe» | Un convertidor juntó BSA y dejó el nombre viejo, o el BSA de verdad falta | Con los BSA del juego configurados, el Doctor revisa los archivos. Si no falta nada, quitarlo del ini es seguro. |
| Un `.esl` en un proyecto SE (Grave) | SE no puede cargar `.esl` | Doctor » **Pasarlo a .esp para SE**. |
| «… es un modpack» al importar a la Biblioteca | Los modpacks no se guardan en la Biblioteca | Empieza un proyecto con él, o trae sus mods al proyecto abierto. |
| Un archivo que borré en `Mods\` volvió | `Mods\` muestra el proyecto como está | Desmarca el mod o quítalo en la página Mods. |
| «Cambios hechos en la carpeta del proyecto» en el Historial | Editaste archivos en `Mods\` o `Base\` | Nada: ya están en el proyecto. Deshazlo ahí si no fue a propósito. |

Si un cambio no quedó como querías: **Historial » Deshacer**.
