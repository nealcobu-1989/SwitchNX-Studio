<p align="center"><img src="app/web/img/emblem.png" width="120" alt=""></p>

# SwitchNX Studio

Arma, revisa, arregla y convierte **modpacks de Skyrim para Nintendo Switch 1**, y los copia a la SD.
Una app para Windows en inglés y español, más un homebrew para encender y apagar mods en la consola.

*Read in English: [README.md](README.md)*

> Proyecto de fans, no oficial. Necesitas tu propia copia del juego y una Switch con firmware
> personalizado (Atmosphère, con LayeredFS). Aquí no hay ni habrá archivos del juego, herramientas
> del SDK de Nintendo ni mods de otras personas.

## Qué hay aquí

| Parte | Qué es | Carpeta |
| --- | --- | --- |
| **SwitchNX Studio** | La app de Windows: proyectos, conversión de mods, el Doctor, orden de carga, copia a la SD | `app/`, `skynx/` |
| **SkyNX Mods** | Homebrew (`.nro`) para encender y apagar mods en la Switch, ver cuánto pesa cada uno y leer los reportes de crash de Skyrim | `extras/nxmods/` |
| **SkyNX Test Tools** | Un mod pequeño: un poder menor con menús para teletransportarse, hacer aparecer enemigos, cambiar la hora y curarse, para probar packs | `extras/nxtest/` |
| **Modo SkyNX del overlay** | Un modo de una línea para Status Monitor Deux: RAM del juego, pico, CPU, GPU, FPS, lectura de la SD | `extras/status-monitor/` |
| **Carpetas base** | Las carpetas de `C:\SkyNX` que espera la app, cada una con una nota de qué va adentro | `extras/skeleton/` |
| **Skill para Claude** | Una guía para que Claude acompañe a alguien con la app | `extras/skill/` |

## Descargas

Los archivos están en **[Releases](../../releases)**:

| Archivo | Qué hacer con él |
| --- | --- |
| `SwitchNX-Studio-<versión>-windows.zip` | La app. Pon `SwitchNX Studio.exe` en `C:\SkyNX`. |
| `SkyNX-folders.zip` | Descomprímelo en `C:\` para tener `C:\SkyNX\Tools`, `Vanilla`, `Library`... |
| `SkyNX-tools-MIT.zip` | texconv y el VGAudio del Skyrim NX Toolkit: descomprímelo en `C:\SkyNX`. |
| `SkyNXMods-<versión>.zip` | Copia `switch/SkyNXMods.nro` a la carpeta `switch` de la SD. |
| `SkyNX-TestTools-1.1.zip` | Agrega la carpeta `SkyNX Test Tools` a un proyecto (Agregar mods » Agregar tal cual). |
| `StatusMonitor-SkyNX-mode.zip` | Copia su carpeta `config` a la raíz de la SD (necesita Status Monitor Deux). |
| `switchnx-studio-guide-skill.zip` | Súbelo como skill en Claude para tener una guía que conoce la app. |

## Para empezar

Necesitas Windows 10 u 11 (con Microsoft Edge WebView2, que Windows ya trae), una Switch 1 con
Atmosphère y Skyrim Anniversary Edition o Special Edition.

1. **Carpetas.** Descomprime `SkyNX-folders.zip` en `C:\` y pon la app en `C:\SkyNX`.
2. **Herramientas.** Descomprime `SkyNX-tools-MIT.zip` en `C:\SkyNX`. Para mods de PC con sonidos
   consigue también `ffmpeg.exe`. `C:\SkyNX\Tools\LEEME-tools.txt` dice para qué sirve cada
   herramienta opcional y de dónde sale.
3. **Los archivos de tu consola.** De tu propia copia del juego (por ejemplo con DBI), pon las
   inis (`Skyrim.ini`, `Skyrim_en.ini`, `Skyrim_aoc.ccc`) en `C:\SkyNX\Vanilla\INIs`, y los BSA
   y plugins de `romfs\Data` en `C:\SkyNX\Vanilla\BSAs`. Con ellos la app empieza proyectos desde
   cero y distingue un archivo que de verdad falta de uno que ya trae el juego. Abrir y revisar
   un modpack compartido funciona sin ellos.
4. **Abre la app.** La primera pantalla, **Tu equipo**, muestra qué encontró y para qué sirve cada herramienta.
5. **Empieza un proyecto** desde cero, desde un modpack que alguien compartió o desde tu SD.
6. **Agrega mods** soltando los archivos en la ventana. Cada tarjeta dice qué es: los mods de
   Switch se agregan tal cual; los de PC y los instaladores FOMOD pasan por **Convertir**.
7. **Doctor » Revisar de nuevo.** Arregla primero lo *Grave*. Cada arreglo muestra qué va a
   cambiar, y todo se puede deshacer desde el Historial.
8. **Orden de carga » Sugerir orden (LOOT) » Usar este orden » Guardar orden.**
9. **Empacar**, luego **Copiar a la SD** (la SD necesita una letra de unidad: un lector de
   tarjetas, o hekate » Tools » USB Tools » SD Card). **Ver los cambios** muestra el plan antes de
   escribir nada.
10. Abre el juego. El primer arranque después de copiar es más lento mientras Atmosphère rearma
    su caché de archivos.

El botón **Ayuda** abre el manual completo en la página donde estás (`docs/manual.es.md`).

## Qué hace la app

- **Proyectos**: cada modpack en su propia carpeta, con sus mods, su historial y lo que va a la
  Switch. Se empieza desde cero, desde un modpack (carpeta, zip, 7z, rar) o desde la SD.
- **Convertir mods de PC**: texturas (con "dietas" de tamaño para la memoria de la Switch), voces y
  sonidos a los formatos de Switch, behaviors y animaciones de 64 bits, instaladores FOMOD paso a
  paso, renombres seguros de plugins que siguen todo lo que usa el nombre (BSA, voces, FaceGen,
  scripts, masters).
- **El Doctor**: revisa la lista de carga (y su límite de 4096 bytes), masters, BSA, inis,
  texturas, audio, scripts y mallas que faltan, scripts que reemplazan a los del juego o del USSEP,
  archivos de SKSE que no funcionan en Switch, y más. Cada hallazgo explica qué pasa en el juego y
  cómo arreglarlo.
- **Orden de carga** con la masterlist de LOOT, **conflictos de archivos**, **peso de texturas y
  audio** por mod.
- **Copiar a la SD** copia solo lo que cambió y respalda todo lo que reemplaza.
- **SkyNX Mods** en la consola lee lo que la app escribe en la SD: qué es cada mod, cuánto pesa,
  quién lo necesita. Lo que cambies en la consola se puede traer de vuelta al proyecto.

## Límites que conviene saber

| Límite | Valor |
| --- | --- |
| Lista de carga `Skyrim_aoc.ccc` (AE) | 4096 bytes; el juego deja de leer después de eso |
| Listas de archivos de las inis | 1024 caracteres cada una; `Skyrim_en.ini` gana sobre `Skyrim.ini` |
| Scripts dentro de BSA | Un BSA del ini le gana a uno que carga su plugin (al revés que en PC) |
| Memoria del juego ("Application" en Status Monitor) | Unos 3285 MB en total; hubo crashes desde unos 2,8 GB |
| SKSE, sus plugins `.dll` y los menús MCM | No existen en Switch |

## Compilar desde el código

**La app** (Windows, Python 3.12 de python.org marcando "Add python.exe to PATH"):

    construir.bat          arma dist\SwitchNX Studio.exe (la primera vez tarda unos minutos)
    abrir-sin-exe.bat      abre la app desde el código, sin armar el .exe

**SkyNX Mods** (devkitPro con "Switch Development" en `C:\devkitPro`):

    extras\nxmods\construir_nro.bat          arma extras\nxmods\SkyNXMods.nro

En Linux, `make -f Makefile.linux` dentro de `extras/nxmods` arma una versión de escritorio (SDL2)
para probar, y `make -f Makefile.linux test_modlist && ./test_modlist` corre sus pruebas.

**SkyNX Test Tools**: `python extras/nxtest/build.py <tu Skyrim.esm> extras/nxtest/pex out`.

**Un release**: después de las dos compilaciones de arriba,
`preparar_release.bat "C:\SkyNX\Vanilla\BSAs\Skyrim.esm" "C:\SkyNX\Tools"` deja todos los zip
de la tabla de descargas en `release\`.

**Pruebas**: `python -m pytest -q`. Algunas necesitan archivos que no se pueden compartir y se
saltan solas; ver `tests/README.md`.

## Cómo está organizado

    app/                  la ventana (pywebview) y la interfaz (app/web)
    skynx/                el motor: BSA, plugins, Doctor, conversor, LOOT, copia a la SD...
    docs/                 el manual de la app (EN y ES) y notas de versiones anteriores
    extras/nxmods/        SkyNX Mods, el homebrew de Switch (C++, SDL2)
    extras/nxtest/        SkyNX Test Tools (fuentes Papyrus, scripts compilados, armador)
    extras/status-monitor/  el modo del overlay
    extras/skeleton/      las carpetas base de C:\SkyNX
    extras/skill/         la skill para Claude
    extras/release/       el script de releases y las licencias de las herramientas que incluye
    tests/                pruebas (pytest) y herramientas falsas pequeñas

## Contribuir

Los issues y pull requests son bienvenidos. Cuando algo falla en un pack, lo más útil es adjuntar
el reporte del Doctor (**Copiar informe**), el orden de carga (**Copiar orden**) y, si hubo crash,
el reporte de `atmosphere/crash_reports` (SkyNX Mods los muestra en la consola).

Nunca adjuntes ni subas archivos del juego, del SDK de Nintendo ni mods de otras personas. Para
compartir un pack entero usa **Receta del pack**: lista los mods con sus enlaces de Nexus.

## Créditos

Hecho por **nealcobu**, con mucha ayuda de Claude (Anthropic).

Un agradecimiento gigante a **KokaNX**, cuyo trabajo con Skyrim en Switch (los límites de memoria
y del `.ccc`, cómo cargan los BSA, los behaviors, el USSEP para Switch) está detrás de muchas
reglas de la app. Gracias también a Antony Marshall y Zappastuff (Skyrim NX Toolkit), ElminsterAU
y el equipo de xEdit, Mator (zEdit), el equipo de LOOT, Arthmoor y el equipo del USSEP, masagrator
(Status Monitor Deux), Microsoft (texconv), Alex Barney (VGAudio), el proyecto FFmpeg, y todos los
que convierten, prueban y comparten modpacks.

## Licencia

MIT para el código y el arte de este repositorio (`LICENSE`). Las partes de terceros conservan
sus licencias: ver `THIRD-PARTY-NOTICES.md`.

The Elder Scrolls y Skyrim son de Bethesda Softworks / ZeniMax Media, y la Nintendo Switch es de
Nintendo. Este proyecto no está hecho ni respaldado por ninguno de los dos.
