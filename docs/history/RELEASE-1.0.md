# SwitchNX Studio 1.0

Changes since 0.9.24. / Cambios desde la 0.9.24.

## English

Safer renames
- Renaming a plugin now also renames the **script properties** that hold its file name (the
  plugin's own and every other plugin's in the pack). Mods that check for another mod through a
  property keep working after the rename. The Doctor's preview lists each plugin it will touch.
- When a mod is converted with renamed plugins, the app looks for places that **still name the old plugin** inside a longer text
  (a script string, a script property, a text config) and warns about each one. Those are left as
  they are on purpose: changing part of a text could break it.

Doctor
- New: **scripts that name a plugin that isn't there any more** (deep check). It compares every
  script and script property with the plugins this project renamed (in the Doctor or when converting) or merged. In a real pack it
  found follower scripts looking for a magic mod that had been merged into a suite: the follower
  works, and that extra stays off.
- New, information: **meshes from the 2011 game (LE)** in a BSA (deep check). Most of them work on
  Switch; the list is there for when a model shows up invisible or stretched. The fix is to resave
  them with Cathedral Assets Optimizer on "Full optimization".
- **Junk files in BSAs** now also catches `.DS_Store`, `Thumbs.db`, `desktop.ini` and stray `.png`
  images outside `interface`.

App
- Texts and labels with neutral names: the "Classic rules" texture preset, "USSEP for Switch",
  and checks described as tested on the console.
- New document: **how it works**, each feature step by step (`docs/how-it-works.en.md`).
- The README explains what is original in this project and what was learned from others.

## Español

Renombres más seguros
- Al renombrar un plugin ahora también se renombran las **propiedades de script** que tienen su
  nombre de archivo (las del propio plugin y las de todos los demás del pack). Los mods que revisan
  si otro mod está instalado por medio de una propiedad siguen funcionando después del renombre. La
  vista previa del Doctor dice qué plugins va a tocar.
- Al convertir un mod con plugins renombrados, la app busca los lugares que **todavía nombran el plugin viejo** dentro
  de un texto más largo (un texto de script, una propiedad, un archivo de configuración) y avisa
  cada uno. Esos se dejan como están a propósito: cambiar una parte de un texto lo puede dañar.

Doctor
- Nuevo: **scripts que nombran un plugin que ya no está** (revisión a fondo). Compara cada script
  y cada propiedad de script con los plugins que este proyecto renombró (en el Doctor o al convertir) o fusionó. En un pack real
  encontró scripts de seguidores que buscan un mod de magia que se había fusionado en una suite: el
  seguidor funciona, y ese extra queda apagado.
- Nuevo, informativo: **mallas del juego de 2011 (LE)** en un BSA (revisión a fondo). Casi todas
  funcionan en Switch; la lista sirve para cuando un modelo sale invisible o estirado. Se arreglan
  guardándolas otra vez con Cathedral Assets Optimizer en "Full optimization".
- **Archivos basura en BSA** ahora también encuentra `.DS_Store`, `Thumbs.db`, `desktop.ini` e
  imágenes `.png` sueltas fuera de `interface`.

App
- Textos y etiquetas con nombres neutros: el preset de texturas "Reglas clásicas", "USSEP para
  Switch" y revisiones descritas como probadas en la consola.
- Documento nuevo: **cómo funciona**, cada función paso a paso (`docs/how-it-works.es.md`).
- El README explica qué es original en este proyecto y qué se aprendió de otros.
