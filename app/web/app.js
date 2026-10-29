"use strict";
// SwitchNX Studio front end. Talks to Python through pywebview (window app)
// or through POST /api/<method> (browser fallback / development).

const $ = (s, el = document) => el.querySelector(s);
const $$ = (s, el = document) => [...el.querySelectorAll(s)];
const esc = (s) => String(s ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
const SEV_ORDER = ["critico", "aviso", "ahorro", "info"];

// ------------------------------------------------------------------ strings
const STR = {
  en: {
    openOther: "Open another", "nav.summary": "Summary", "nav.doctor": "Doctor", "nav.mods": "Mods",
    "nav.order": "Load order", "nav.textures": "Textures & audio", "nav.history": "History",
    "nav.sd": "Copy to SD", "nav.convert": "Convert mods", "nav.settings": "Settings",
    sev: { critico: "Serious", aviso: "Check", ahorro: "Savings", info: "Info" },
    lede: "Build, check, fix and convert Skyrim modpacks for Nintendo Switch (AE and SE), then copy them to the SD with a backup.",
    pathOpen: "Open a modpack", pathOpenP: "One you already have, on the PC or from Discord.",
    pathNew: "Start from scratch", pathNewP: "An empty modpack; you add mods one by one.",
    pathSd: "Bring it from the SD", pathSdP: "Copy what's on the SD to the PC first.",
    folderLabel: "Modpack folder", folderPh: "C:\\SkyNX\\My modpack (the folder holding 01000A10041EA000)",
    folderHint: "The SD root, the atmosphere folder, contents, or any folder with the Skyrim folders inside works.",
    browse: "Browse", open: "Open", recent: "Opened recently", cancel: "Cancel", apply: "Apply",
    needFolder: "Type or pick the modpack folder", working: "Working", reading: "Reading the modpack",
    newTitle: "New modpack", newSub: "Creates the folders, the inis and the load list. Then you add mods from the Mods page.",
    newFolder: "Folder for the new modpack (empty or new)", edition: "Game edition",
    aeLabel: "Anniversary (Skyrim_aoc.ccc)", seLabel: "Special (Plugins file)",
    baseLabel: "Where to take the base inis from",
    baseHint: "Best: the clean ones from your console. The pack is built in English: I copy Skyrim.ini and Skyrim_en.ini (if it's missing I write the vanilla one), because on Switch Skyrim_en.ini replaces Skyrim.ini's texture list. You can also point to a modpack you trust: I keep its tweaks and remove its mods.",
    ccLabel: "Creation Club in the list", ccAll: "All 80", ccUssep: "Only the 4 USSEP needs", ccNone: "None", ccBase: "As in the base folder",
    create: "Create modpack", creating: "Creating",
    verdictCrit: (n) => `${n} ${n === 1 ? "thing keeps" : "things keep"} something from loading right. The Doctor has the details and a fix for most.`,
    verdictWarn: (n) => `Nothing serious. ${n} ${n === 1 ? "point" : "points"} to check.`,
    verdictOk: "Everything looks right from what I can check on the PC.",
    openDoctor: "Open the Doctor", gameVer: "Game edition", entriesIn: (l) => `Entries in ${l}`,
    ofCC: (n) => `(${n} Creation Club)`, active: "Active plugins", ofData: (a, b) => `${a} of ${b} in Data`,
    bsaData: "BSAs in Data", dataSize: "Size of Data", texActive: "Active textures (estimate)", texFormats: "Texture formats",
    audio: "Audio", noData: "no data", heaviest: "Heaviest textures", noTex: "No textures in the active BSAs.", tex: "Textures",
    doctorSub: "Each fix shows exactly what will change first, and goes to the history so you can undo it.",
    fixSafe: (n) => `Fix the safe ones (${n}, all categories)`, recheck: "Check again", all: "All", nothingHere: "Nothing in this category.",
    cases: (n, t) => `${n} like this one: ${t}`, seeAll: (n) => `See all ${n}`, details: (n) => `Details (${n})`,
    riskSafe: "Safe fix. It can be undone from the history.", riskReview: "Check before applying: it changes how the pack loads. It can be undone from the history.",
    done: "Done. It's in the history.", fixSafeTitle: "Fix the safe ones",
    fixSafeBody: (n) => `I'll apply ${n} fixes marked as safe, one by one, checking the pack between each. Every change goes to the history.`,
    fixWord: "Fix", fixedN: (a, b) => `${a} fixes applied${b ? `, ${b} couldn't be applied` : ""}.`,
    modsSub: "Add mods already converted for Switch: a folder or a .7z/.zip with their .esp and .bsa. I put the plugins in the load list and the loose BSAs in the ini. For PC mods, use Convert mods.",
    addMod: "Add mod", addFolder: "Folder", addArchive: ".7z or .zip", modPh: "Path to the mod folder or archive",
    remove: "Remove", removeTitle: "Remove mod", removeBody: (n) => `I'll take <b>${esc(n)}</b> out of the list and the ini, and move its files to the project trash. It can be undone.`,
    rmUsersTitle: "Others use it as a master",
    rmUsersBody: (n) => `These plugins use <b>${esc(n)}</b> as a master. Left alone they would close the game, so they can go with it, in the same step (undoable):`,
    rmUsersWhole: (m) => `the whole mod ${esc(m)} goes with it`,
    rmUsersPart: (m) => `only this plugin leaves ${esc(m)}; the rest of that mod stays`,
    rmUsersGo: (k) => `Remove all ${k}`,
    noMods: "No mods yet. Add the first one above.", addedTitle: "Mod added",
    addedFiles: "Copied to Data", addedList: "Added to the load list", addedIni: "Added to the ini", notes: "Notes",
    fromIni: "from the ini", recorded: "added here",
    orderSub: "Drag plugins or use the arrows. Masters must sit above whoever uses them; red rows tell you what's wrong.",
    ccOff: "Creation Club not in use: off", ccOffHint: "Switches off the Creation Club entries no plugin that's on uses as a master. Each one is a BSA the game keeps open.",
    ccOffTitle: "Switch off the Creation Club nothing uses?", ccOffBody: "Each Creation Club entry is a BSA the game keeps open all the time. These go off with a # in the list (undo it from the History). The unofficial Creation Club patch uses most of them as masters: with it on, those stay.",
    ccOffFree: "Only what nothing uses", ccOffPatch: "Also the unofficial patch", ccOffPatchHint: "It goes off first, then everything only it used. What USSEP or other mods need stays.",
    ccOffDone: (n) => `${n} switched off. It's in the history.`,
    saveOrder: "Save order", showCC: "Show the Creation Club", orderCopy: "Copy order", orderCopyHint: "Copies the list as it is on screen, with each plugin's masters, to paste in a chat or a note.", orderCopyTitle: (n) => `Load order: ${n}`, orderCopied: "Order copied.", up: "Up", down: "Down", orderSaved: "Order saved. It's in the history.",
    srcGame: "game", srcIni: "ini", empty: "empty",
    texSub: "I only read the headers inside each active BSA. The total is what all textures would take at once; the game only loads what's near you, so use it to compare mods.",
    pcTex: "BSAs with PC textures", pcAudio: "BSAs with PC audio",
    texNote: "DFvN is Switch's own format (shown as NVN). Making it needs NvnTexpkg.exe; without it, textures stay as PC DDS.",
    byBsa: "By BSA", plugin: "Plugin", files: "Files", sdSize: "Size on SD",
    histSub: "Every change keeps a copy of what was there before in the modpack's .skynx folder. Undo puts those files back.",
    undo: "Undo", undoBody: "I'll put the files back the way they were before this change.", undone: "Undone.", noHist: "No changes yet.",
    file1: "file", fileN: "files", undoneAt: "undone",
    sdSub: "First I save a .zip on the PC with whatever Skyrim files are on the SD. Then I replace those two folders with the modpack's.",
    sdCrit: (n) => `There are still ${n} serious problems. You can copy anyway, but it's better to fix them first.`,
    sdDrive: "SD drive", sdGo: "Back up and copy", sdHint: "I only copy 01000A10041EA000 and 01000A10041EB009 inside atmosphere\\contents. The backup goes to .skynx\\sd-backups.",
    sdNeed: "Type the SD drive", sdConfirm: (d) => `I'll back up and then replace the Skyrim folders on <b>${esc(d)}</b>.`, copy: "Copy",
    sdDone: (n, s, b) => `Copied ${n} files (${s}).${b ? " Backup saved." : ""}`, importTitle: "Bring a modpack from the SD",
    importSd: "SD drive, e.g. E:\\", importDest: "New folder on the PC", import: "Import", importNeed: "The SD or the destination folder is missing",
    convSub: "Turn a PC mod (Skyrim SE/AE) into a Switch mod and add it to this pack. First I read it and show you what it will cost; nothing is written until you press Convert.",
    convPick: "Folder or .7z/.zip of the PC mod (FOMOD installers open in the assistant)", analyze: "Read the mod", analyzing: "Reading the mod", converting: "Converting",
    toolsTitle: "Tools", toolTexconv: "texconv (textures)", toolFfmpeg: "ffmpeg (PC audio)", toolVga: "VGAudioCli (Switch audio)", toolNvn: "NvnTexpkg (native Switch textures)", toolHavok: "Behaviors and skeletons (Havok)", havokPart: "32-bit only; hkxc.exe missing",
    bhTitle: "Behaviors (FNIS / Nemesis)", bhGo: "Generate behaviors", bhPreparing: "Preparing Nemesis…", bhCollecting: "Making the behaviors Switch files…",
    bhNever: (n) => `${n} mod(s) bring new animations. Their behaviors haven't been generated yet; without them those animations don't play.`,
    bhStale: "The mods with new animations changed since the behaviors were generated. Generate them again.",
    bhOk: (d, n) => `Up to date (generated ${d}, ${n} files).`,
    bhNoNemesis: "Nemesis isn't in the tools folder: unpack its download into Tools\\Nemesis (Nexus SE mod 60033).",
    bhNoHavok: "HavokBehaviorPostProcess.exe and hkxc.exe (serde-hkx) are needed to make the result Switch files.",
    bhOpened: "Nemesis opened in its own window, working on a copy of this project's animations (your Skyrim isn't touched).",
    bhStep1: "Press <b>Update Engine</b> and wait.", bhStep2: "Press <b>Launch Nemesis Behavior Engine</b>.",
    bhStep3: "When it says <b>Behavior generation complete</b>, close Nemesis.", bhStep4: "Come back and press <b>Done</b>.",
    bhPatches: (p) => `Nemesis patches in the list to tick before Launch: ${p}.`, bhWhere: (w) => `Work folder: ${w}`,
    bhDone: "Done", bhLater: "Later", bhFinish: "Nemesis finished: make them Switch files", bhAdded: (n, h) => `Behaviors added to the project: ${n} files (${h} Havok files made for Switch).`,
    bhAtPack: "This project has mods with new animations whose behaviors aren't generated (or are out of date): Mods » Generate behaviors.",
    toolsWhere: (d) => d ? `Folder: ${d}` : "I didn't find the tools folder. Put them in C:\\SkyNX\\Tools or set the folder in Settings.",
    nvnMissing: (l) => `missing ${l}`, vgaOfficial: "official build: use the Skyrim NX Toolkit one",
    budgetTitle: "Budget", cccLine: (a, b, l) => `${a} + ${b} bytes${l ? ` of ${l}` : ""}`, cccLbl: "Load list (.ccc)", seList: "Plugins file",
    texPackLbl: "Textures in the pack (estimate)", texCap: "Reference cap (MB)", texCapHint: "Optional. A number you trust, for example what a pack that runs well for you weighs. The estimate adds up every texture; the game only loads what's near you.",
    overCap: "goes over your cap", overCcc: "goes over the .ccc limit", nearCcc: "close to the .ccc limit",
    dietTitle: "Texture diet", modTex: (a, b) => `This mod: ${a} → ${b}`,
    presetKoka: "Koka's rules", presetKokaP: "1K in general, 2K for actors. Mipmaps rebuilt.",
    presetDiet: "Switch 1 diet (default)", presetDietP: "1K in general; normal, specular and other maps at 512; clutter and effects at 512.",
    presetExtreme: "Extreme", presetExtremeP: "512 in general, maps at 256, characters at 1K. For packs with many mods.",
    presetNone: "Original size", presetNoneP: "No size rule: textures keep their size, up to the maximum size you pick (2K, 4K…). Formats still change for Switch.",
    optNative: "Native Switch format (NvnTexpkg)", optNativeOff: "Without NvnTexpkg textures stay PC DDS forced to DXT5, as Koka does.",
    optBc1: "BC1 for opaque textures (half the memory; only with the native format)",
    uiNote: "The interface is never resized and nothing is ever enlarged.",
    pluginsTitle: "Plugins and names", nameCol: "Name in the pack", shorten: "Short", reasonChars: "apostrophe or symbols", reasonEsl: "ESL → ESP (SE)", reasonBlocked: "keeps its name",
    renameNote: "When a name changes I update the plugin, its BSAs, voice and FaceGen folders, tint paths inside the meshes, SEQ, strings, the scripts that mention it and the masters of the plugins that use it. Saves that already use the mod won't find it under the new name.",
    needs: (l) => `needs ${l}`,
    contentTitle: "What's inside", cTex: "Textures", cTexP: (a, b) => `${a} to convert, ${b} already Switch`, cSnd: "Sounds", cSndP: (a) => `${a} from PC`, cAnim: "Animations", cMesh: "Meshes", cScripts: "Scripts", cDropped: "Left out (readmes, sources, SKSE...)",
    convertGo: "Convert and add to the pack", convertCancel: "Discard",
    convDone: "Mod converted", convStats: (s) => `Textures: ${s.tex_ok} converted (${s.tex_nvn} native, ${s.tex_bc1} to BC1), ${s.tex_fail} with problems. Sounds: ${s.snd_ok} converted, ${s.snd_fail} failed. Animations: ${s.hkx_ok} converted${s.hkx_havok ? `; behaviors, skeletons and Oldrim files: ${s.hkx_havok}` : ""}.`,
    convMem: (a, b) => `Texture memory: ${a} → ${b}`, convBsas: "BSAs created", convRenamed: "Renamed",
    fmTitle: "Installer options", fmSub: "This mod comes with a FOMOD installer. Choose like in a mod manager; I hide patches for mods you don't have in the pack.",
    fmStepOf: (a, b) => `Step ${a} of ${b}`, fmBack: "Back", fmNext: "Next", fmFinish: "Install these options and continue",
    fmPick: { SelectExactlyOne: "Pick one", SelectAtMostOne: "Pick one or none", SelectAtLeastOne: "Pick at least one", SelectAll: "All are installed", SelectAny: "Pick any" },
    fmType: { Required: "required", Recommended: "recommended", Optional: "", CouldBeUsable: "may not work", NotUsable: "not available" },
    fmNone: "None", fmModuleWarn: "The installer says this mod needs mods that aren't active in your pack.",
    fmUnknown: (l) => `Conditions I can't check here (treated as not met): ${l}`, fmNoDesc: "No description.", fmInstalling: "Installing options",
    needPack: "Open or create a modpack first.", bc1More: "(less with BC1)",
    recovered: (l) => `A change was cut short last time and I rolled it back: ${l}`,
    toolsIn: (d) => `Tools in ${d}`, found: "found", missing: "missing",
    toolsLabel: "Tools folder (texconv, ffmpeg, VGAudioCli, NvnTexpkg and its DLLs)", save: "Save", saved: "Saved.",
    version: (v) => `Version ${v}. Changes to each modpack are kept in its .skynx folder.`,
    hudCrit: (n) => (n ? `${n} serious ${n === 1 ? "problem" : "problems"}` : "No serious problems"),
    hudCcc: (a, b) => `.ccc: ${a} of ${b} bytes`, hudPlugins: (n) => `Plugins: ${n} entries`, hudIni: (n) => `Longest ini list: ${n} of 1024`,
    aeName: "Anniversary (Skyrim_aoc.ccc)", seName: "Special (Plugins)", none: "Not detected",
  },
  es: {
    openOther: "Abrir otro", "nav.summary": "Resumen", "nav.doctor": "Doctor", "nav.mods": "Mods",
    "nav.order": "Orden de carga", "nav.textures": "Texturas y audio", "nav.history": "Historial",
    "nav.sd": "Llevar a la SD", "nav.convert": "Convertir mods", "nav.settings": "Ajustes",
    sev: { critico: "Grave", aviso: "Revisar", ahorro: "Ahorro", info: "Dato" },
    lede: "Arma, revisa, arregla y convierte modpacks de Skyrim para Switch (AE y SE), y cópialos a la SD con respaldo.",
    pathOpen: "Abrir un modpack", pathOpenP: "Uno que ya tengas, en el PC o bajado del Discord.",
    pathNew: "Empezar desde cero", pathNewP: "Un modpack vacío al que le vas agregando mods.",
    pathSd: "Traerlo de la SD", pathSdP: "Primero copia al PC lo que hay en la SD.",
    folderLabel: "Carpeta del modpack", folderPh: "C:\\SkyNX\\Mi modpack (la carpeta que tiene 01000A10041EA000)",
    folderHint: "Sirve la raíz de la SD, la carpeta atmosphere, contents o cualquier carpeta que tenga dentro las de Skyrim.",
    browse: "Examinar", open: "Abrir", recent: "Abiertos hace poco", cancel: "Cancelar", apply: "Aplicar",
    needFolder: "Escribe o elige la carpeta del modpack", working: "Trabajando", reading: "Leyendo el modpack",
    newTitle: "Modpack nuevo", newSub: "Crea las carpetas, los inis y la lista de carga. Después agregas mods desde la página Mods.",
    newFolder: "Carpeta del modpack nuevo (vacía o nueva)", edition: "Edición del juego",
    aeLabel: "Anniversary (Skyrim_aoc.ccc)", seLabel: "Special (archivo Plugins)",
    baseLabel: "De dónde saco los inis base",
    baseHint: "Lo ideal: los limpios de tu consola. El pack se arma en inglés: copio Skyrim.ini y Skyrim_en.ini (si falta, escribo el original), porque en Switch Skyrim_en.ini reemplaza la lista de texturas de Skyrim.ini. También puedes elegir un modpack de confianza: conservo sus ajustes y le quito sus mods.",
    ccLabel: "Creation Club en la lista", ccAll: "Los 80", ccUssep: "Solo los 4 que pide USSEP", ccNone: "Ninguno", ccBase: "Como en la carpeta base",
    create: "Crear modpack", creating: "Creando",
    verdictCrit: (n) => `Encontré ${n} ${n === 1 ? "cosa que impide" : "cosas que impiden"} que algo cargue bien. El Doctor tiene el detalle y el arreglo de casi todas.`,
    verdictWarn: (n) => `Nada grave. Hay ${n} ${n === 1 ? "punto" : "puntos"} para revisar.`,
    verdictOk: "Todo en orden según lo que puedo revisar desde el PC.",
    openDoctor: "Abrir el Doctor", gameVer: "Edición del juego", entriesIn: (l) => `Entradas en ${l}`,
    ofCC: (n) => `(${n} del Creation Club)`, active: "Plugins activos", ofData: (a, b) => `${a} de ${b} en Data`,
    bsaData: "BSA en Data", dataSize: "Peso de Data", texActive: "Texturas activas (estimado)", texFormats: "Formatos de textura",
    audio: "Audio", noData: "sin datos", heaviest: "Lo que más pesa en texturas", noTex: "Sin texturas en los BSA activos.", tex: "Texturas",
    doctorSub: "Cada arreglo muestra antes qué va a cambiar y queda en el historial para deshacerlo.",
    fixSafe: (n) => `Arreglar lo seguro (${n}, todas las categorías)`, recheck: "Volver a revisar", all: "Todo", nothingHere: "Nada en esta categoría.",
    cases: (n, t) => `${n} como este: ${t}`, seeAll: (n) => `Ver los ${n}`, details: (n) => `Detalle (${n})`,
    riskSafe: "Arreglo seguro. Se puede deshacer desde el historial.", riskReview: "Revisa antes de aplicar: cambia cómo carga el pack. Se puede deshacer desde el historial.",
    done: "Listo. Quedó en el historial.", fixSafeTitle: "Arreglar lo seguro",
    fixSafeBody: (n) => `Voy a aplicar ${n} arreglos marcados como seguros, uno por uno, revisando el pack entre cada uno. Cada cambio queda en el historial.`,
    fixWord: "Arreglar", fixedN: (a, b) => `${a} arreglos aplicados${b ? `, ${b} no se pudieron` : ""}.`,
    modsSub: "Agrega mods ya convertidos para Switch: una carpeta o un .7z/.zip con sus .esp y .bsa. Pongo los plugins en la lista de carga y los BSA sueltos en el ini. Para mods de PC, usa Convertir mods.",
    addMod: "Agregar mod", addFolder: "Carpeta", addArchive: ".7z o .zip", modPh: "Ruta de la carpeta o del comprimido del mod",
    remove: "Quitar", removeTitle: "Quitar mod", removeBody: (n) => `Saco <b>${esc(n)}</b> de la lista y del ini, y muevo sus archivos a la papelera del proyecto. Se puede deshacer.`,
    rmUsersTitle: "Otros lo usan como master",
    rmUsersBody: (n) => `Estos plugins usan <b>${esc(n)}</b> como master. Si se quedan, cerrarían el juego, así que pueden salir con él, en el mismo paso (se puede deshacer):`,
    rmUsersWhole: (m) => `sale todo el mod ${esc(m)}`,
    rmUsersPart: (m) => `solo este plugin sale de ${esc(m)}; el resto de ese mod se queda`,
    rmUsersGo: (k) => `Quitar los ${k}`,
    noMods: "Todavía no hay mods. Agrega el primero arriba.", addedTitle: "Mod agregado",
    addedFiles: "Copiados a Data", addedList: "Agregados a la lista de carga", addedIni: "Agregados al ini", notes: "Notas",
    fromIni: "desde el ini", recorded: "agregado aquí",
    orderSub: "Arrastra los plugins o usa las flechas. Los masters deben quedar arriba de quien los usa; las filas en rojo te dicen qué falla.",
    ccOff: "Creation Club sin uso: apagar", ccOffHint: "Apaga los contenidos del Creation Club que ningún plugin encendido usa como master. Cada uno es un BSA que el juego mantiene abierto.",
    ccOffTitle: "¿Apagar el Creation Club que nada usa?", ccOffBody: "Cada contenido del Creation Club es un BSA que el juego mantiene abierto todo el tiempo. Se apagan con un # en la lista (se deshace desde el Historial). El parche no oficial del Creation Club usa la mayoría como masters: si está encendido, esos se quedan.",
    ccOffFree: "Solo lo que nada usa", ccOffPatch: "También el parche no oficial", ccOffPatchHint: "Se apaga primero el parche y luego todo lo que solo él usaba. Lo que el USSEP u otros mods necesitan se queda.",
    ccOffDone: (n) => `${n} apagados. Quedó en el historial.`,
    saveOrder: "Guardar orden", showCC: "Mostrar el Creation Club", orderCopy: "Copiar orden", orderCopyHint: "Copia la lista como está en pantalla, con los masters de cada plugin, para pegarla en un chat o una nota.", orderCopyTitle: (n) => `Orden de carga: ${n}`, orderCopied: "Orden copiado.", up: "Subir", down: "Bajar", orderSaved: "Orden guardado. Quedó en el historial.",
    srcGame: "juego", srcIni: "ini", empty: "vacío",
    texSub: "Leo solo los encabezados dentro de cada BSA activo. El total es lo que ocuparían todas las texturas a la vez; el juego carga solo las de lo que tienes cerca, así que sirve para comparar mods.",
    pcTex: "BSA con texturas de PC", pcAudio: "BSA con audio de PC",
    texNote: "DFvN es el formato propio de Switch (aparece como NVN). Para producirlo hace falta NvnTexpkg.exe; sin él, las texturas quedan como DDS de PC.",
    byBsa: "Por BSA", plugin: "Plugin", files: "Archivos", sdSize: "Peso en SD",
    histSub: "Cada cambio guarda una copia de lo que había antes en la carpeta .skynx del modpack. Deshacer devuelve esos archivos.",
    undo: "Deshacer", undoBody: "Devuelvo los archivos a como estaban antes de este cambio.", undone: "Deshecho.", noHist: "Todavía no hay cambios.",
    file1: "archivo", fileN: "archivos", undoneAt: "deshecho",
    sdSub: "Primero guardo en el PC un .zip con lo que ya hay de Skyrim en la SD. Después reemplazo esas dos carpetas por las del modpack.",
    sdCrit: (n) => `Quedan ${n} problemas graves. Puedes copiar igual, pero lo ideal es arreglarlos antes.`,
    sdDrive: "Unidad de la SD", sdGo: "Respaldar y copiar", sdHint: "Copio solo 01000A10041EA000 y 01000A10041EB009 dentro de atmosphere\\contents. El respaldo queda en .skynx\\sd-backups.",
    sdNeed: "Escribe la unidad de la SD", sdConfirm: (d) => `Voy a respaldar y luego reemplazar las carpetas de Skyrim en <b>${esc(d)}</b>.`, copy: "Copiar",
    sdDone: (n, s, b) => `Copiados ${n} archivos (${s}).${b ? " Respaldo guardado." : ""}`, importTitle: "Traer un modpack desde la SD",
    importSd: "Unidad de la SD, por ejemplo E:\\", importDest: "Carpeta nueva en el PC", import: "Importar", importNeed: "Faltan la SD o la carpeta de destino",
    convSub: "Convierte un mod de PC (Skyrim SE/AE) para Switch y agrégalo a este pack. Primero lo leo y te muestro cuánto va a costar; no se escribe nada hasta que le des a Convertir.",
    convPick: "Carpeta o .7z/.zip del mod de PC (los instaladores FOMOD se abren en el asistente)", analyze: "Leer el mod", analyzing: "Leyendo el mod", converting: "Convirtiendo",
    toolsTitle: "Herramientas", toolTexconv: "texconv (texturas)", toolFfmpeg: "ffmpeg (audio de PC)", toolVga: "VGAudioCli (audio de Switch)", toolNvn: "NvnTexpkg (texturas nativas de Switch)", toolHavok: "Comportamientos y esqueletos (Havok)", havokPart: "solo 32 bits; falta hkxc.exe",
    bhTitle: "Comportamientos (FNIS / Nemesis)", bhGo: "Generar comportamientos", bhPreparing: "Preparando Nemesis…", bhCollecting: "Pasando los comportamientos a Switch…",
    bhNever: (n) => `${n} mod(s) traen animaciones nuevas. Sus comportamientos todavía no se generan; sin ellos esas animaciones no se ven.`,
    bhStale: "Cambiaron los mods con animaciones nuevas desde la última vez. Genera otra vez los comportamientos.",
    bhOk: (d, n) => `Al día (generados el ${d}, ${n} archivos).`,
    bhNoNemesis: "Nemesis no está en la carpeta de herramientas: descomprime su descarga en Tools\\Nemesis (mod 60033 de Nexus SE).",
    bhNoHavok: "Hacen falta HavokBehaviorPostProcess.exe y hkxc.exe (serde-hkx) para pasar el resultado a Switch.",
    bhOpened: "Nemesis se abrió en su propia ventana, sobre una copia de las animaciones de este proyecto (tu Skyrim no se toca).",
    bhStep1: "Oprime <b>Update Engine</b> y espera.", bhStep2: "Oprime <b>Launch Nemesis Behavior Engine</b>.",
    bhStep3: "Cuando diga <b>Behavior generation complete</b>, cierra Nemesis.", bhStep4: "Vuelve aquí y oprime <b>Listo</b>.",
    bhPatches: (p) => `Parches de Nemesis que hay que marcar en la lista antes de Launch: ${p}.`, bhWhere: (w) => `Carpeta de trabajo: ${w}`,
    bhDone: "Listo", bhLater: "Más tarde", bhFinish: "Nemesis terminó: pasarlos a Switch", bhAdded: (n, h) => `Comportamientos agregados al proyecto: ${n} archivos (${h} archivos de Havok pasados a Switch).`,
    bhAtPack: "Este proyecto tiene mods con animaciones nuevas cuyos comportamientos no se han generado (o están desactualizados): Mods » Generar comportamientos.",
    toolsWhere: (d) => d ? `Carpeta: ${d}` : "No encontré la carpeta de herramientas. Ponlas en C:\\SkyNX\\Tools o indica la carpeta en Ajustes.",
    nvnMissing: (l) => `falta ${l}`, vgaOfficial: "versión oficial: usa la del Skyrim NX Toolkit",
    budgetTitle: "Presupuesto", cccLine: (a, b, l) => `${a} + ${b} bytes${l ? ` de ${l}` : ""}`, cccLbl: "Lista de carga (.ccc)", seList: "Archivo Plugins",
    texPackLbl: "Texturas del pack (estimado)", texCap: "Tope de referencia (MB)", texCapHint: "Opcional. Un número en el que confíes, por ejemplo lo que pesa un pack que te corre bien. El estimado suma todas las texturas; el juego solo carga las de lo que tienes cerca.",
    overCap: "se pasa de tu tope", overCcc: "se pasa del límite del .ccc", nearCcc: "cerca del límite del .ccc",
    dietTitle: "Dieta de texturas", modTex: (a, b) => `Este mod: ${a} → ${b}`,
    presetKoka: "Reglas de Koka", presetKokaP: "1K en general, 2K para actores. Mipmaps regenerados.",
    presetDiet: "Dieta Switch 1 (por defecto)", presetDietP: "1K en general; mapas normales, especulares y demás a 512; clutter y efectos a 512.",
    presetExtreme: "Extrema", presetExtremeP: "512 en general, mapas a 256, personajes a 1K. Para packs con muchos mods.",
    presetNone: "Tamaño original", presetNoneP: "Sin regla de tamaño: las texturas quedan como vienen, hasta el tamaño máximo que elijas (2K, 4K…). Los formatos igual se ajustan a Switch.",
    optNative: "Formato nativo de Switch (NvnTexpkg)", optNativeOff: "Sin NvnTexpkg las texturas quedan como DDS de PC forzadas a DXT5, como hace Koka.",
    optBc1: "BC1 en texturas opacas (la mitad de memoria; solo con formato nativo)",
    uiNote: "La interfaz nunca se reduce y nada se agranda.",
    pluginsTitle: "Plugins y nombres", nameCol: "Nombre en el pack", shorten: "Corto", reasonChars: "apóstrofo o símbolos", reasonEsl: "ESL → ESP (SE)", reasonBlocked: "conserva su nombre",
    renameNote: "Si cambia un nombre, actualizo el plugin, sus BSA, las carpetas de voces y FaceGen, las rutas de tinte dentro de los meshes, SEQ, strings, los scripts que lo mencionan y los masters de los plugins que lo usan. Las partidas que ya usan el mod no lo van a encontrar con el nombre nuevo.",
    needs: (l) => `necesita ${l}`,
    contentTitle: "Qué trae", cTex: "Texturas", cTexP: (a, b) => `${a} por convertir, ${b} ya de Switch`, cSnd: "Sonidos", cSndP: (a) => `${a} de PC`, cAnim: "Animaciones", cMesh: "Meshes", cScripts: "Scripts", cDropped: "Quedan por fuera (léeme, fuentes, SKSE...)",
    convertGo: "Convertir y agregar al pack", convertCancel: "Descartar",
    convDone: "Mod convertido", convStats: (s) => `Texturas: ${s.tex_ok} convertidas (${s.tex_nvn} nativas, ${s.tex_bc1} a BC1), ${s.tex_fail} con problemas. Sonidos: ${s.snd_ok} convertidos, ${s.snd_fail} fallaron. Animaciones: ${s.hkx_ok} convertidas${s.hkx_havok ? `; comportamientos, esqueletos y archivos de Oldrim: ${s.hkx_havok}` : ""}.`,
    convMem: (a, b) => `Memoria de texturas: ${a} → ${b}`, convBsas: "BSA creados", convRenamed: "Renombrados",
    fmTitle: "Opciones del instalador", fmSub: "Este mod trae instalador FOMOD. Elige como en un gestor de mods; escondo los parches de mods que no tienes en el pack.",
    fmStepOf: (a, b) => `Paso ${a} de ${b}`, fmBack: "Atrás", fmNext: "Siguiente", fmFinish: "Instalar estas opciones y seguir",
    fmPick: { SelectExactlyOne: "Elige una", SelectAtMostOne: "Elige una o ninguna", SelectAtLeastOne: "Elige al menos una", SelectAll: "Se instalan todas", SelectAny: "Elige las que quieras" },
    fmType: { Required: "obligatoria", Recommended: "recomendada", Optional: "", CouldBeUsable: "puede no funcionar", NotUsable: "no disponible" },
    fmNone: "Ninguna", fmModuleWarn: "El instalador dice que este mod necesita mods que no están activos en tu pack.",
    fmUnknown: (l) => `Condiciones que no puedo revisar aquí (las tomo como no cumplidas): ${l}`, fmNoDesc: "Sin descripción.", fmInstalling: "Instalando opciones",
    needPack: "Abre o crea un modpack primero.", bc1More: "(menos con BC1)",
    recovered: (l) => `Un cambio quedó a medias la vez pasada y lo revertí: ${l}`,
    toolsIn: (d) => `Herramientas en ${d}`, found: "encontrado", missing: "falta",
    toolsLabel: "Carpeta de herramientas (texconv, ffmpeg, VGAudioCli, NvnTexpkg y sus DLL)", save: "Guardar", saved: "Guardado.",
    version: (v) => `Versión ${v}. Los cambios a cada modpack se guardan en su carpeta .skynx.`,
    hudCrit: (n) => (n ? `${n} ${n === 1 ? "problema grave" : "problemas graves"}` : "Sin problemas graves"),
    hudCcc: (a, b) => `.ccc: ${a} de ${b} bytes`, hudPlugins: (n) => `Plugins: ${n} entradas`, hudIni: (n) => `Lista más larga del ini: ${n} de 1024`,
    aeName: "Anniversary (Skyrim_aoc.ccc)", seName: "Special (Plugins)", none: "No detectada",
  },
};
// strings for v0.5 (Add, Library, transfer, LOOT, SD sync, conflicts, USSEP)
Object.assign(STR.en, {
  "nav.add": "Add mods", "nav.library": "Library", home: "Home",
  dropHere: "Drop mods or modpacks here",
  dropBrowser: "Drag and drop works in the app window. Here, use the buttons.",
  // first steps
  spBy: "Made by", spThanksTitle: "A huge thank you to KokaNX",
  spThanks: "For all the development and for exploring what Skyrim can do on Switch: the RAM and .ccc limits, how BSAs should load, the behaviors, USSEP for Switch, and countless tests that are now rules in this app.",
  spAlso: "Also thanks to", spToolkit: "Antony Marshall and Zappastuff (MIT licence): Switch sound formats and the animation conversion method.",
  spXedit: "ElminsterAU and the xEdit team.", spZedit: "Mator.", spLoot: "The LOOT team: the masterlist and load order rules.",
  spUssep: "Arthmoor and team, for USSEP.", spTexconv: "Microsoft, for texconv.", spVgaudio: "Alex Barney; the Switch build comes from the Skyrim NX Toolkit.",
  spFfmpeg: "The FFmpeg project.", spNexus: "For the API behind downloads and update checks.",
  spCommunity: "The Switch modding community", spCommunityP: "Everyone who converts, tests and shares modpacks.",
  spBethesda: "Skyrim belongs to Bethesda Softworks and the Nintendo Switch to Nintendo. This is an unofficial fan tool, not made or endorsed by either.",
  spHide: "Don't show this again", spEnter: "Enter", spShow: "Credits",
  suTitle: "Your gear", suSub: "What SwitchNX Studio can use on this PC, what's already here and what's missing. Nothing here is required to open and fix a pack.",
  suGTools: "To convert PC mods", suGGame: "Game files and folders", suGExtra: "Extras",
  suNeedConvert: "to convert", suNeedNew: "for new packs", suOptional: "optional", suAlways: "always",
  suInis: "Console inis", suVanilla: "Base game (BSAs)", suUssep: "KokaNX's USSEP",
  suFound: "Found in", suLooked: "I looked in", suPickFolder: "Choose folder", suPickExe: "Choose .exe", suChange: "Change", suGo: "Go",
  suAskFolder: "Folder path", suAskExe: "Path to the .exe", suContinue: "Continue", suBack: "Back to the pack", suLink: "See all your gear",
  drBadge: "Being created", drBadgeTip: "A pack in creation: mark what goes, rename, add, and when it's ready, Create modpack.",
  drTitle: (n) => `Pack being created: ${n}`, drFrom: (n) => `· started from ${n}`, drCreate: "Create modpack",
  drGoes: "Mods that go", drIniTop: "Longest ini list", drPlugins: "Plugins",
  drHint: "Untick a mod and it leaves the load list and the inis (the numbers above update); its files stay until you create the modpack. Tick it again and it goes back where it was.",
  drFromCatalog: "Bring from the Catalog", drGoesTip: "Goes in the modpack", drOut: "doesn't go",
  drOutTitle: "It's a master", drUsers: (n, u) => `${n} is a master of ${u}. For it not to go, those can't go either.`, drOutToo: "Leave them out too",
  drCant: "I couldn't change it.", drMissing: (l) => `Some of its files are no longer in Data: ${l}`,
  rnGo: "Rename", rnTitle: "Rename", rnWhich: "Which plugin?", rnBody: (n) => `New name for ${n}. Everything that uses the name follows it, in one step you can undo.`,
  rnPatch: (l) => `Inside the BSAs (FaceGen, voices, scripts…): ${l}`, rnDeps: (l) => `Plugins that use it as a master: ${l}`,
  rnList: (d, t) => `Load list: ${d} bytes (${t})`, rnInis: (l) => `Inis: ${l}`, rnUseSafe: (n) => `Use ${n}`, rnDone: (n) => `Renamed to ${n}.`,
  drCreateBody: (g, t) => `A clean copy with the ${g} mods that go (of ${t}), without history or the files of the mods that don't. The pack being created stays as it is, for the next version.`,
  drName: "Name", drWhere: "Folder (optional)", drWherePh: "Empty: Library\\Packs\\<name>",
  drOverCcc: (b, l) => `The load list is ${b} bytes; the limit is about ${l}. It may not boot.`, drOverIni: (c, l) => `An ini list is ${c} characters; the limit is ${l}.`,
  drCreating: "Creating the modpack", drDone: "Modpack created", drDoneBody: (d) => `It's in ${d}.`, drLeftOut: (n) => `Left out (mods that don't go): ${n} files`,
  drSdAsk: "Copy it to the SD now?", drToSd: "Copy to the SD", drManual: "I'll copy it myself", drManualHint: "Opens the folder.", drLater: "Later",
  drStart: "Start a pack from this one", drStartTip: "A pack being created that begins as an exact copy of this one; the original isn't touched.",
  drStartBody: (n) => `A copy of ${n}, identical file for file (same .ccc and inis), in Library\\Drafts. On the same drive the files are linked, so it takes almost no space. Then you mark what goes, rename, add from other packs, and create the modpack. ${n} isn't touched.`,
  drMine: "mine", drCopying: "Copying the pack",
  catIntoNew: "New pack", catIntoOpen: (n) => `Add to ${n}`, catIntoTitle: "Add to the open pack", catIntoHint: (n) => `The ticked mods go into ${n}, with the masters they need. Mods it already has are skipped.`, catIntoGo: "Add to the pack",
  catNewName: "Name of the new pack", catNewNamePh: "My pack", catNewNameHint: "It's created in Library\\Drafts as a pack being created (a full path also works).", catNeedName: "Give the new pack a name.",
  "ws.bench": "Bench", "ws.join": "Join BSAs", "ws.merge": "Join plugins", "ws.home": "All benches", "ws.leave": "Leave the workshop", "ws.tag": "Workshop",
  filter: "Filter", ok: "OK", libEditWs: "Edit in the workshop", setLinks: "Link files in packs being created and created modpacks (they don't take the space twice)",
  setLinksHint: "On the same drive, a copy shares the files with the pack it came from. The app never writes into a file in place (it writes a new one and swaps it), so the original doesn't change. If you edit files of those folders with other programs (CAO, NifSkope), do it on a separate copy.",
  drLinked: (n) => `${n} files linked to the pack being created (no extra space)`, drInTitle: "It needs its masters", drNeeds: (n, m) => `${n} needs ${m}, which you marked as not going.`, drInToo: "Bring them back too", libBringBench: "Bring mods to the bench", openFolder: "Open folder", openLibFolder: "Open the Library folder", folderCopied: (p) => `Folder path copied: ${p}`,
  spcPacks: "Modpacks", spcPacksP: "Open, build and fix whole packs for the Switch.", spcFrom: "Build from another pack", spcFromP: "An exact copy you then trim, rename and extend.",
  spcFromToast: "Pick a pack and press \"Start a pack from this one\".",
  spcWs: "Mod workshop", spcWsP: "Single mods and suites, without a pack.", spcLibP: "Everything you've collected: packs, mods, converted mods.",
  spcLibOpen: "Open the Library", spcLibOpenP: "Packs and mods, with their health.", spcCat: "Catalog", spcCatP: "Every mod of every pack, to pick from.",
  wsConvert: "Convert a mod", wsConvertP: "A PC mod into a Switch mod for the Library.", wsBatch: "Convert several mods", wsBatchP: "Each with its own options, all in one go, into the Library.", wsBatchName: "Batch", wsEdit: "Edit a mod", wsEditP: "Rename, extract, SSEEdit, save.",
  wsSuite: "Join mods", wsSuiteP: "Several mods in one suite: their BSAs joined.", wsMerge: "Join plugins", wsMergeP: "A merge with zEdit's zMerge, guided.",
  wsBenches: "Saved benches", wsBenchesTitle: "Benches", wsNoBenches: "No benches yet. Start with one of the buttons above.",
  wsSub: "A bench is a small private workspace for mods. Nothing here touches your packs; the result goes to Library\\Converted when you save it.",
  wsFiles: "files", wsEditOf: (n) => `editing ${n}`, wsKind_convert: "convert", wsKind_edit: "edit", wsKind_suite: "suite", wsKind_merge: "merge",
  wsKindP_convert: "Convert a PC mod here, check it, rename it if needed and save it to the Library.",
  wsKindP_edit: "The mod is on the bench: rename plugins (everything that uses the name follows), extract BSAs, open it in SSEEdit. Then save it.",
  wsKindP_suite: "Several mods on one bench. Join their BSAs so they load as one suite, then save it.",
  wsKindP_merge: "Several plugins to merge into one with zMerge, step by step.",
  wsPickOne: "Pick the mod.", wsPickMany: "Pick the mods (in the order they should load).", wsNoLibMods: "The Library has no loose mods yet.",
  wsOther: "Another folder or .zip/.7z…", wsOtherAsk: "Path of the mod folder or archive", wsGo: "Continue", wsNeedTwo: "Pick at least two mods.",
  wsEdAsk: "For which edition of the game?", wsConvertName: "Convert", wsSuiteName: "Name of the suite", wsPreparing: "Preparing the bench",
  wsSomeOut: "Some didn't come in", wsPcHint: "PC mods go through Convert a mod first; a mod with a FOMOD installer too.",
  wsBring: "Add mods to the bench", wsConvertHere: "Convert a PC mod here", wsEmpty: "The bench is empty.",
  wsLoose: (l) => `Loose folders (${l}) aren't saved with the mod; pack them into a BSA by converting.`,
  wsSaveTitle: "Save to the Library", wsSaveP: "Plugins and BSAs go to Library\\Converted\\&lt;name&gt;, ready for any pack and for the Catalog. The bench stays until you discard it.",
  wsSave: "Save", wsReplace: (n) => `Replace ${n} (the old one goes to Library\\.trash)`, wsSaving: "Saving",
  wsSaved: "Saved", wsSavedP: (d) => `It's in ${d}.`, wsLooseLeft: (l) => `Not saved (loose folders): ${l}`, wsKeepBench: "Keep working", wsDoneBench: "Done: discard the bench",
  wsDiscard: "Discard this bench", wsDiscardP: "The bench folder is deleted. What you saved to the Library stays.",
  wsJoinSub: "The BSAs of every mod on the bench become one (or a few when they're big), named after a plugin so they load with it. Fewer archives and shorter ini lists.",
  wsJoinNeed: "There must be at least two BSAs on the bench.", wsJoinOrder: "Order", wsJoinOrderP: "As the game reads them: when two have the same file, the later one wins.",
  wsJoinAnchor: "Name", wsJoinAnchorP: "The plugin they load with. Without one, they're listed in the ini.", wsJoinIni: "None: load from the ini",
  wsJoinResult: "Result", wsJoinOverlaps: (n) => `Files in more than one BSA: ${n}`, wsWins: (b) => `the one in ${b} stays`, wsNoOverlaps: "None.",
  wsJoinRetarget: (p) => `Voice and FaceGen folders of the merged plugins move to ${p}.`,
  wsJoinNote: "The plugins stay separate (the .ccc doesn't change). If later you take one of them out of a pack, its files stay inside the joined BSA.",
  wsBack: "Back to the bench", wsJoining: "Joining BSAs", wsJoined: (n, l) => `${n} BSAs joined into ${l}.`, wsUndoHint: "It's in the bench's history; it can be undone.",
  wsMergeSub: "Merging plugins frees load-list lines and bytes. The merge itself is done by zMerge (inside zEdit), the proven tool for it; the app prepares, brings and tidies.",
  wsM1: "Plugins on the bench", wsM1p: (n) => `${n} plugins now. Add the ones to merge.`, wsM1done: (p) => `Merged into ${p}.`,
  wsM2: "Merge them in zEdit", wsM2p: "I make a folder zEdit accepts as Skyrim SE with these plugins and the game's files, and open zEdit.", wsM2go: "Prepare and open zEdit",
  wsM2folder: "Game folder for zEdit:",
  wsZ1: "In zEdit, create a profile for Skyrim SE with that folder as the game path (the first time only).",
  wsZ2: "Open the profile, go to zMerge and make a new merge with the plugins of the bench.",
  wsZ3: "In the merge's Data tab, Copy General Assets can stay off: the BSAs are joined here afterwards.",
  wsZ4: "Build the merge. zMerge leaves it in its output folder (you see it in zEdit's settings).",
  wsNoZedit: "I didn't find zEdit. Put it in C:\\SkyNX\\Tools\\zEdit or set it in Your gear.",
  wsM3: "Bring the merge", wsM3p: "Pick the folder zMerge made for this merge. The merged plugins leave the bench; their BSAs stay to be joined.",
  wsM3ph: "Folder of the merge zMerge built", wsM3go: "Bring", wsM3in: (l) => `Inside the merge: ${l}`, wsM3extra: (l) => `Also brought: ${l}`,
  wsM3missing: (l) => `The merge lists plugins that weren't on the bench: ${l}`,
  wsM4: "Join the BSAs under the merge", wsM4p: "So they load with the merged plugin; voice and FaceGen folders follow its name.",
  wsM5: "Save the suite", wsM5p: "To Library\\Converted, ready for packs.",
  nxConfirmed: "You confirmed it", nxKnown: "Downloaded from Nexus with the app", nxLikely: "Found by name in LOOT's list (likely)", nxMerge: "A merge",
  nxWhich: "Which mod?", nxMergeChip: "Merge: see inside", nxWhoTip: "How it was recognised, other options, or change it",
  nxUnknown: "Not recognised yet", nxIsMerge: "It's a merge of several mods", nxVia: (n) => `matched as ${n}`,
  nxOriginal: (n) => `Original name: ${n}`, nxOthers: "Other pages LOOT links", nxThisOne: "It's this one", nxInside: "Mods inside the merge",
  nxAuthor: "Author in the plugin", nxSearchLabel: "Search on Nexus", nxSearch: "Search on Nexus",
  nxPasteLink: "Nexus link or number", nxPasteHint: "Open the mod's page on Nexus, copy the address and paste it here. It's remembered for this plugin in every pack.",
  nxForgetMine: "Forget what I said", nxDetails: "Get name and version from Nexus", nxFetching: "Asking Nexus",
  nxSaved: (n) => `Saved: Nexus #${n}`, nxForgot: "Forgotten.", nxSummary: (k, n) => `Nexus: ${k} of ${n} mods recognised.`,
  nxGetMl: "Download LOOT's list to recognise more", nxGetNames: (n) => `Get names from Nexus (${n})`,
  bModeOne: "One mod", bModeMany: "Several at once",
  bSub: "Add several mods and decide, card by card, how each one is converted: diet, size, packing and plugin names. Then everything is converted in one go. Mods that others need go first.",
  bAddFiles: "Archives…", bAddFolder: "Folder…", bAdd: "Add", bPathPh: "Path to a zip, 7z or mod folder",
  bAll: "For all", bApply: "Apply to all", bEmpty: "No mods yet. Add archives or folders.",
  bRun: (n) => `Convert ${n} mod${n === 1 ? "" : "s"}`, bClear: "Empty the list", bReading: "Reading mods",
  bInclude: "Convert it", bMore: "More options", bWarn: (n) => `Notes (${n})`, bFomod: "Has an installer (FOMOD): choose its options first.",
  bFomodGo: "Choose options", bFromBatch: (n) => `comes with ${n}`, bEst: (a, b) => `Textures ${a} → ${b}`,
  bCccAll: (n) => `.ccc +${n} bytes`, bRunning: "Converting", bDoneTitle: "Converted",
  bDoneSum: (ok, n) => `${ok} of ${n} converted.`, bFailed: "Not converted", bPointed: (l) => `Points to the new name of: ${l}`,
  bLeft: "The ones that weren't converted stay on the list.", bQueueGo: (n) => `Convert all PC mods (${n})`,
  bPlugins: (n) => `${n} plugin${n === 1 ? "" : "s"}`, bNoPlugins: "No plugins (textures, meshes, sounds)", bReread: "Read it again",
  cpBtn: "Versions for Switch", cpOne: "Which version works on Switch", cpTitle: "Versions that work on Switch",
  cpIntro: "Newer versions sometimes start needing SKSE (.dll plugins, Address Library…), which doesn't exist on Switch. I look inside each file on Nexus and suggest the newest one that still works.",
  cpYou: "You have", cpLatest: "Latest", cpBest: "Best for Switch", cpUnverified: "not checked: Nexus shows no file list",
  cpAll: "All main files", cpHave: "I have this one", cpHaveSaved: "Saved which version you have.", cpOpenFile: "Files on Nexus",
  cpNone: "No identified mods. Recognise them first (chip next to each mod).", cpSkipped: (n) => `${n} mods not recognised yet were left out.`,
  cpV: { ok: "Works on Switch", warn: "Check", no: "Needs SKSE", unknown: "Not checked" },
  cpS: { best: "You have the latest and it works on Switch.", kept: "You have the best one for Switch: the newer ones need SKSE or need checking.",
    update: "There's a newer version that works on Switch.", have_skse: "Your version ships SKSE plugins. Use the one suggested.",
    all_skse: "Every main file ships SKSE plugins: none works as is on Switch.", unknown_have: "I don't know which version you have. Mark yours with \"I have this one\".",
    none: "Nexus shows no main files for this mod." },
  fsTitle: "Before you start", fsDone: "All set.",
  fsTools: "Tools folder", fsToolsOk: (d) => `texconv, ffmpeg and VGAudio found in ${d}.`,
  fsToolsNo: (d) => `Put texconv, ffmpeg and the Toolkit's VGAudioCli in ${d} (Settings changes the folder). Only needed to convert PC mods.`,
  fsSdk: "NvnTexpkg (Switch native textures)", fsSdkOk: "Found.", fsSdkNo: "Optional. Without it, converted textures stay as DDS (they work, a bit heavier).",
  fsInis: "Clean console inis", fsInisOk: (d) => `Skyrim.ini found in ${d}.`, fsInisNo: (d) => `Copy Skyrim.ini and Skyrim_en.ini from your console to ${d}. New packs start from them.`,
  fsUssep: "USSEP (KokaNX)", fsUssepOk: (d) => `Found in ${d}. New packs can include it.`, fsUssepNo: (d) => `Optional. Put the KokaNX folders (All_CC, SurvivalMode, No_CC and the BSAs) in ${d}.`,
  fsLib: "Library", fsLibP: (d) => `Imported modpacks and mods are kept in ${d}.`,
  // new pack: USSEP
  usTitle: "Unofficial patch (USSEP, KokaNX build)", usNone: "Don't include it",
  usNeeds: (l) => `Needs ${l}; I add them to the list if they're missing.`, usBase: "Only the base game.",
  usMissing: (d) => `No USSEP found in ${d}. You can set the folder in Settings, or add it later as a mod.`,
  usSe: "Special Edition has no Creation Club: only No_CC works.",
  usHint: "Pick the one that matches what you'll use. All_CC is the full one for Anniversary.",
  // add page
  addTitle: "Add mods", addSub: "Drop zips, 7z or folders, or pick them. I look at each one and tell you what it is and what to do with it: modpacks go to the Library, Switch mods go straight in, PC mods go through Convert.",
  pickFiles: "Pick files", pickFolder: "Pick a folder", queueAdd: "Add to the list", pathsPh: "Path to a zip, 7z or folder",
  queueEmpty: "Nothing here yet.", detecting: "Looking at the files", clearDone: "Clear finished",
  kind: { modpack: "Modpack", fomod: "FOMOD installer", "switch-mod": "Switch mod", "pc-mod": "PC mod", mixed: "PC + Switch", unknown: "Not recognized" },
  qImport: "Import to the Library", qOpen: "Open it", qBring: "Bring mods from it", qCheck: "Check it", qAddAsIs: "Add as it is",
  qConvert: "Convert", qKeep: "Keep a copy in the Library", qRemove: "Remove from the list",
  qNeedPack: "Open or create a modpack first to add mods to it.",
  qRecAdd: "Ready to go in as it is.", qRecConvert: "Better through Convert: it fixes what's listed above.",
  qDone: "Done", qImported: (p) => `In the Library: ${p}`,
  // library
  libTitle: "Library", libSub: (d) => `Modpacks and mods you keep at hand, in ${d}. Each pack shows what the Doctor thinks of it (quick check).`,
  libImport: "Import zip or folder", libRefresh: "Check again", libPacks: "Modpacks", libMods: "Mods", libEmpty: "The Library is empty. Import a modpack zip or drop it on the window.",
  libOpen: "Open", libBring: "Bring mods to the current pack", libAddPack: "Add to the current pack", libForget: "Forget",
  libForgetBody: (n) => `I'll take <b>${esc(n)}</b> off the Library list. Nothing is deleted from the disk.`,
  libDelete: "Delete", libDeleteBody: (n) => `I'll delete the Library's copy of <b>${esc(n)}</b> from the disk. The zip you imported it from isn't touched.`,
  busyNow: "Wait for the current task to finish.",
  libMissing: "The folder isn't there anymore.", libExternal: "kept where it is", libReading: "Reading the Library",
  health: { ok: "Looks right", warn: "To check", broken: "Problems", error: "Can't read" },
  // transfer
  xTitle: (s, d) => `Bring mods from ${s} to ${d}`, xSub: "Pick what you want. I bring along the masters they need and leave behind what the pack already has.",
  xSort: "Sort", xSorts: { name: "By name", order: "As in the pack", size: "By size" },
  xFilter: "Filter", xPlan: "Prepare", xBack: "Back", xSelected: (n) => `${n} selected`,
  xKinds: { plugin: "plugin", bsa: "BSA only", archive: "packed" },
  xPlanTitle: "What will happen", xUnits: "Will be brought", xWhy: { selected: "picked", picked: "picked", master: "needed as master" },
  xNeededBy: (l) => `needed by ${l}`, xSkipped: "Left out", xRefused: "Can't be brought", xMissing: "Missing masters",
  xBudget: "Budget", xCcc: (a, b, l) => `Load list: ${a} → ${b}${l ? ` of ${l}` : ""} bytes`,
  xTex: (a, b) => `Textures: ${a} in the pack + ${b}`, xBytes: (a) => `Copying ${a}`,
  xGo: "Bring them", xDoneTitle: "Mods brought", xNothing: "Nothing to bring with this selection.", xErrors: "Problems",
  // load order: LOOT
  lootGo: "Suggest order (LOOT)", lootTitle: "LOOT suggestion", lootSame: "The current order already follows the LOOT masterlist.",
  lootMoves: (n) => `${n} ${n === 1 ? "plugin moves" : "plugins move"}`, lootUse: "Use this order",
  lootAge: (d) => `Masterlist from ${d} days ago.`, lootNotes: "Masterlist notes", lootWarn: "Warnings",
  lootHint: "It sorts by masters, LOOT rules and groups, keeping your order where nothing says otherwise. Creation Club and game files don't move.",
  // mods: conflicts
  cfGo: "Check file conflicts", cfTitle: "File conflicts", cfNone: "No two archives carry the same file.",
  cfStats: (s) => `${s.bsas} archives, ${s.conflicting_paths} files in more than one. The one loaded later wins: for textures and meshes the ini's BSAs load first, as on PC; for scripts the ini's win.`,
  cfDead: "Archives fully replaced by others", cfDeadP: (b, w) => `${esc(b)}: all its files are replaced by ${esc(w)}.`,
  cfPairs: "Who wins", cfPair: (w, l, n) => `${esc(w)} replaces ${n} of ${esc(l)}`, cfUnloaded: "Archives nothing loads",
  cfIdentical: (n) => `${n} are identical copies (harmless, just space).`,
  // SD
  sdPlan: "Preview changes", sdPlanTitle: "What changes on the SD", sdSync: "Copy the changes", sdFull: "Full copy instead",
  sdFullP: "Copies everything again (slower). Use it if the SD was edited by hand or another tool.",
  sdRows: { copy: "To copy", new: "New", replace: "Replace", delete: "Remove", move: "Renamed (not copied again)", rename: "Name case", unchanged: "Unchanged", backup: "Backup first" },
  sdFits: (f) => `Free on the SD: ${f}.`, sdNoFit: "Not enough free space on the SD.",
  sdAssume: "Unchanged means same size and date as on the PC. Only the two Skyrim folders are touched; what the pack no longer has is removed. Everything replaced or removed goes into a backup zip first.",
  sdFirst: "First copy: this SD doesn't have Skyrim's folders yet, so everything goes in new and there's nothing to back up.",
  sdHow: "Connect the SD so Windows gives it a drive letter: put it in the PC's card reader, or on the Switch open hekate, Tools, USB Tools, SD Card. MTP (DBI) gives no drive letter and is unreliable for big copies.",
  sdMoveNote: (n) => `${n} files only changed name in the pack (short BSA names, for example): I rename them on the SD instead of copying them again.`,
  sdBackupNote: "The backup holds every SD file that gets replaced or removed, so you can always go back.",
  sdMetaItem: "Atmosphère's cache, rebuilt when the game starts",
  descAdd: "Describe it", descEdit: "Edit", descTitle: (n) => `What is ${n}?`,
  descAsk: "A line about what this mod does. It shows here and in SkyNX Mods on the console. Empty to remove it.",
  sdConTitle: "Changed on the console",
  sdCon: (off, on) => `SkyNX Mods (the homebrew) has ${[off.length ? `turned off ${off.map(esc).join(", ")}` : "", on.length ? `turned on ${on.map(esc).join(", ")}` : ""].filter(Boolean).join(" and ")}, the other way from the project.`,
  sdConUse: "Use the console's choices", sdConHint: "Copying without this puts the project's list back on the console.",
  sdConDone: "The project now has the console's choices.",
  sdMetaNote: "romfs_metadata.bin is the list of mod files Atmosphère keeps to start the game faster. It's removed with the old files and Atmosphère makes it again the next time the game starts.",
  prTitle: "Before packing", prAnyway: "Pack anyway", prGoLoot: "Sort with LOOT", prGoDoctor: "Go to the Doctor",
  prLoot: (n, l) => `LOOT would still move ${n} plugins (${l}). The order decides which mod wins when two change the same thing.`,
  prLootNever: "The load order hasn't been checked with LOOT yet.",
  prCrit: (n) => `The Doctor has ${n} serious problems.`,
  prRoutine: (n, l) => `${n} routine fixes are left in the Doctor: ${l}.`,
  sdNothing: "The SD already has this pack exactly.", sdDone2: (r) => `Copied ${r.copied}, removed ${r.deleted}${r.moved ? `, renamed ${r.moved}` : ""}, unchanged ${r.unchanged}.`,
  // settings
  libDirLabel: "Library folder", ussepDirLabel: "USSEP (KokaNX) folder",
  reasonOrphan: "voices/faces under another name",
  lootGuessMark: "(suggested)", lootNoChoice: "Leave to LOOT (General)", lootCommon: "Common", lootAllGroups: "All LOOT groups",
  lootDupTitle: "The same mod twice", lootDup: (a, m) => `${a} is in the pack on its own and also inside ${m}. Its records load twice; keep one of them.`,
  lootMergeTitle: "Merged plugins", lootMerge: (m, n) => `${m} holds ${n} mods; LOOT's rules for them apply to it.`,
  lootDummies: (l) => `Empty placeholders kept so patches find their masters: ${l}.`,
  lootUnknownTitle: (n) => `Plugins LOOT doesn't know (${n})`,
  lootPickBtn: "Choose what kind of mod each one is",
  lootUnknownP: "Pick the category that fits each one best. I suggest one from what the plugin contains. Your choice is saved for every pack and LOOT uses it from now on.",
  lootWhatGroups: "What each category means", lootCategory: "Category", lootSave: "Save and sort again", lootSaved: "Saved. LOOT will remember it.",
  lootChosen: (n) => `Your saved choices in this pack (${n})`,
  vanillaDirLabel: "Vanilla game files (the console's Skyrim - *.bsa)",
  vanillaHint: "Put the game's own files from the console's romfs\\Data (its BSAs and its .esm and .esl plugins) in a folder and point here. From them the app builds the game list the Doctor checks missing scripts, meshes and textures against.",
  vanillaState: { unset: "Not set.", missing: "That folder doesn't exist.", empty: "No BSA in that folder.", ok: "Ready." },
  drCopy: "Copy report", drCopyHint: "Copies every finding with all its details as Markdown, to paste in a chat or a note.", drSave: "Save as .md",
  drCopied: "Report copied.", drSaved: (p) => `Saved in ${p}`,
  vlNone: "The game list isn't built yet; the Doctor builds it the first time it checks requirements.", vlBuild: "Build it now", vlBuilding: "Reading the game's files",
  vlSummary: (n, b, p, d) => `Game list: ${n} files from ${b} BSAs, plus what ${p} game plugins ask for${d ? ` (updated ${d})` : ""}. Once it's built you can delete the BSAs from the folder (the list stays), except Skyrim - Interface.bsa, which holds the game's texts. Keep the .esm and .esl files, xEdit needs them.`,
  vlMissing: (names) => `It was never built with ${names}; the Doctor may report their files as missing.`,
  vlKept: (n) => `${n} of the game's files are no longer in the folder; the list keeps what they had (normal after deleting the BSAs).`, vlForget: "Forget them (only if they're no longer part of the game)",
  vlForgot: (n) => `Forgot ${n} files.`, vlForgetWarn: "The list will drop everything those files had. If you deleted the BSAs on purpose, the Doctor would then report their files as missing again. Only do this if they're no longer part of the game.", vlRebuild: "Bring the list up to date",
  libLegend: "Delete removes a copy the Library made (the zip you imported from stays). Forget only takes a folder you registered off the list; nothing is deleted.",
  libDeleteTip: "Deletes the Library's copy from the disk. The original zip isn't touched.",
  libForgetTip: "Only takes it off the list. The folder stays where it is.",
  xSafeNames: "Given a name Drive won't damage",
  libTabList: "Packs and mods", libTabCatalog: "Catalog", catReading: "Reading the catalog",
  catSub: (p, n) => `${n} mods from ${p} packs in the Library, each listed once. Pick what you want from any pack; masters come along on their own.`,
  catMulti: "Only in several packs", catOnlyPicked: "Only picked", catInPacks: (n) => `in ${n} packs`, catIdentical: "identical",
  catInMerge: (m) => `also inside ${m}`, catVersion: "Version", catMore: (n) => `${n} more: narrow the filter.`,
  catNewPack: "New pack", catPickSome: "Pick mods on the left to see the budget.", catCreate: "Create the pack", catClear: "Clear picks",
  catSize: "Size", catInisHint: "Your console's clean inis, or a pack you trust: its ini tweaks are kept and its mods removed.", catAutoMasters: (n) => `${n} masters come along`, catSkipped: (n) => `Left out (${n})`,
  catBlocked: "There are problems that keep the pack from loading well:", catCreateAnyway: "Create it anyway",
  catDone: "Pack created", catDoneP: (n) => `${n} mods brought. The Doctor already checked it; add the extras from Add mods.`,
  cmpGo: "Compare with the original", cmpAsk: "Path to the original mod (zip, 7z or folder)", cmpWorking: "Comparing",
  cmpTitle: "Compared with the original", cmpRecs: (a, r, c, s) => `records: ${a} added, ${r} removed, ${c} changed, ${s} the same`,
  cmpAssets: "Files", cmpConv: (t, d, a, h) => `Format conversion: ${t} textures (${d} also smaller), ${a} sounds, ${h} animations.`,
  cmpMeshes: "Meshes changed", cmpScripts: "Scripts changed", cmpScriptsGone: "Scripts removed", cmpOnlyOrig: "Only in the original", cmpOnlyConv: "Only in the converted one",
  xtTitle: "External tools", xtSub: "Programs the app can open for you. SSEEdit opens the current pack with the console's .esm files from the Vanilla folder.",
  xeOpen: "Open in SSEEdit", xeSync: "Bring SSEEdit changes", xeOpening: "Preparing SSEEdit", xeTitle: "SSEEdit",
  xeOpened: "SSEEdit is opening with a working copy of this pack. Edit and save there, close it, then press Bring SSEEdit changes.",
  xeModeTitle: "How do you want to work?", xeModeBody: "SSEEdit needs the game's base files next to the plugins, so it always opens a working folder built from this pack.",
  xeDirect: "Work on the pack", xeDirectHint: "When you close SSEEdit, what you saved goes into the pack by itself (undoable in the history).",
  xeCopy: "Work on a copy", xeCopyHint: "When you close SSEEdit, I ask what to do: bring the changes, keep the copy for later, or delete it.",
  xeOpenedDirect: "SSEEdit is opening. Edit and save there; when you close it, the changes go into the pack and the history.",
  xeOpenedCopy: "SSEEdit is opening with a copy of this pack. Edit and save there; when you close it, I'll ask what to do with the copy.",
  xeKeptTitle: "There's a kept SSEEdit copy", xeKeptBody: "An earlier copy of this pack has edits that are not in the pack yet:",
  xeKeptReuse: "Keep working on that copy", xeKeptBring: "Bring those changes first", xeKeptDrop: "Start over (those edits are lost)",
  xeClosedTitle: "SSEEdit closed", xeClosedChanges: (p) => `SSEEdit changed these files of the copy of ${p}:`, xeClosedNone: "SSEEdit closed without changing anything.",
  xeDoBring: "Bring the changes and delete the copy", xeDoKeep: "Keep the copy for later", xeDoDiscard: "Delete the copy",
  xeForeignDrop: "Start over with this pack (that copy is deleted)",
  xeStuck: (l) => `These were edited in the copy but can't go into the pack (game files, or files no longer in the pack): ${l}. The copy stays so they aren't lost.`,
  xeLeft: (l) => `I kept the copy: these couldn't go into the pack: ${l}.`,
  xeDiscarded: "Copy deleted. The pack didn't change.", xeKeptToast: "The copy stays; Bring SSEEdit changes or Open in SSEEdit pick it up later.",
  xeUnfinished: "SSEEdit closed without finishing these saves, so I didn't touch the pack. The copy stays; open it again and save:",
  xeMissing: "Not in the working copy", xeAfter: "Nothing in the pack changes until you bring the changes; that step goes to the history.",
  xeNone: "Open the pack in SSEEdit first.", xeStillOpen: "SSEEdit is still open (or didn't finish saving). Close it first.",
  xeNoChanges: "SSEEdit didn't change anything.", xeConflicts: (l) => `These also changed in the pack meanwhile; SSEEdit's version will win: ${l}`,
  xeSynced: (n) => `${n} files brought from SSEEdit. They're in the history.`,
  pmActive: "Active (unchecked: off with #)", pmMasters: "Masters", pmDisable: "Turn off the plugin",
  pmUsers: (n, u) => `${n} is a master of ${u}. If you turn it off they won't load either.`, pmDisableAnyway: "Turn it off anyway",
  cvMaxSize: "Largest texture size", cvMaxNone: "As the diet says", cvMaxHint: "Caps every texture's largest side (never enlarges; interface textures are left alone).",
  cvPacking: "Packing", cvPack_ini1: "One BSA in the inis (Switch version, default)", cvPack_plugin: "BSAs named after the plugin (no ini)", cvPack_single: "One BSA named after the plugin (no ini)", cvPack_ini: "BSAs listed in the inis (Koka's stable way)",
  cvPackHint_ini1: "Everything in one short-named BSA, listed in the ini list with more room. Koka's stable way, with one name per mod instead of two.", cvPackHint_plugin: "Name.bsa and Name - Textures.bsa load with the plugin.", cvPackHint_single: "Everything in Name.bsa; it loads with the plugin.",
  cvPackHint_ini: "Two BSAs in the inis (meshes and scripts in Skyrim.ini, textures and voices in Skyrim_en.ini). Koka found it the most stable; it uses ini characters.",
  cvCompress: "Compress the BSAs", cvKeep: "Also keep a copy in Library\\Converted (to reuse it in other packs)",
  libConverted: "Converted here", cvKept: (p) => `A copy stays in ${p}; it shows up in the Library and the Catalog.`,
  packMoved: (p) => `The folder had moved; I opened it from ${p} and updated the recent list.`, extract: "Extract", extractWhere: "Folder to extract to", extractDone: (n, d) => `${n} files extracted to ${d}`,
  fsVanilla: "Vanilla game files (console BSAs and .esm)", fsVanillaOk: (d) => `Found in ${d}. The Doctor can check missing scripts, meshes and textures.`,
  fsVanillaNo: (d) => `Optional. Extract the Skyrim - *.bsa and .esm files from the console's romfs\\Data into ${d}.`,
  inisDirLabel: "Console inis for new packs (Skyrim.ini, Skyrim_en.ini, Skyrim_aoc.ccc)",
  qBundle: "Goes in together", qFromPack: "Bring it from its pack",
  qFromPackHint: (p) => `It's inside the modpack ${p}. Bringing it from there also brings the masters it needs and its ini entries.`,
  texNotScanned: "The textures haven't been read yet (only the deep check reads them).", texWithDiet: "With diet",
  dietDlgIntro: (b) => `Shrink the textures inside <b>${b}</b>. Pick the size rule and, if you want, a maximum size.`, dietDlgEst: (a, b, n) => `Texture memory: ${a} now, about ${b} after (${n} textures change).`, dietDlgUndo: "The original BSA stays in the history; you can undo it.",
  texDietGo: "Diet", texDietHint: "With diet: what the textures would take with the Switch 1 diet (1K; maps, clutter and effects at 512; mips rebuilt) and BC1 where there's no transparency. Every BSA with textures has a Diet button, where you pick the size rule (Switch 1 diet, Koka's, Extreme or the original size) and a maximum size; it's highlighted when the Switch 1 diet saves 8 MB or more. It needs texconv, and NvnTexpkg for Switch textures. Interface textures are never shrunk.",
  safeAll: (b) => `Safe fixes in every category: ${b}`,
  nxKey: "Your personal API key", nxKeyHint: "On nexusmods.com, open your account settings and look for API Keys; copy your Personal API Key. It stays only on this PC, in the app's settings. Nexus allows personal keys for personal tools.",
  nxCheckSave: "Check and save", nxForget: "Forget it", nxPaste: "Paste the key first.",
  nxConnected: (n, p) => `Connected as ${n} (${p ? "Premium" : "free account"}).`, nxNoKey: "Not connected.",
  nxHandler: "Nexus' Mod Manager Download button", nxHandlerOurs: "SwitchNX Studio handles it.",
  nxHandlerOther: (h) => `Another program handles it now: ${h}`, nxHandlerNone: "No program handles it.",
  nxTakeOver: "Use SwitchNX Studio for it", nxGiveBack: "Give it back to the previous program", nxStopHandling: "Stop handling it",
  nxHandlerHint: "With this on, the Mod Manager Download button on a Nexus file page sends the file here: it downloads into the Library and appears in Add mods. It works with a free account. Vortex or Mod Organizer can take it back any time, and the button above gives it back.",
  nxDownloading: "Downloading from Nexus", nxDownloaded: (n) => `Downloaded: ${n}. It's in Add mods.`,
  nxIdentify: "Find it on Nexus", nxFound: (n) => `Found on Nexus: ${n}`, nxNotFound: "Nexus doesn't know this file (it may be a Discord conversion or a repack).",
  nxMany: (n) => `${n} possible matches on Nexus; I can't pick one for sure.`,
  nxUpdates: "Check Nexus for updates", nxNoNexusMods: "No mod of this pack came from Nexus yet (download with the Mod Manager button or use Find it on Nexus).",
  nxYours: "Yours", nxLatest: "Latest", nxStUpdate: "Update", nxStOk: "Up to date", nxStRemoved: "Removed from Nexus", nxStError: "Error",
  nxUpdatesHint: "Only checked when you press the button (Nexus' rules). An update comes as a PC file: it goes through Convert again.",
  rcGo: "Pack recipe", rcTitle: "Pack recipe", rcSub: "How this pack was built: every mod with where it came from (Nexus, Discord, another pack), its FOMOD options, conversion settings and renames, plus the load order and inis. It lets you see what changed and share the pack without passing anyone's files.",
  rcMods: "Mods", rcNexus: "From Nexus", rcUnknown: "Files with no known origin", rcSaved: "Last saved", rcNever: "never",
  rcChanges: "Changes since the saved recipe", rcNoChanges: "Nothing changed.", rcVerify: (n) => `${n} files differ from the saved recipe`,
  rcSave: "Save the recipe", rcExport: "Export to share (.md)", rcSavedOk: "Recipe saved.",
  rcExported: "Saved in the pack folder (it doesn't go to the SD). It has no paths from your PC, and Nexus links for mods that came from there.",
  rcExportHint: "Packs built before this version show their files with no known origin; from now on every mod you add is recorded.",
  lootNothingPicked: "Change a category first, or use the suggested ones.", lootGone: "(not in the masterlist anymore)",
  lootSaveAll: "Use all the suggested categories", lootSaveAllTip: "Saves every suggestion shown, for every pack. You can change them later here.",
  sdSub: "I compare the pack with the SD and copy only what changed. Anything replaced or removed is saved first in a .zip on the PC.",
  sdHint: "The SD root or its atmosphere\\contents folder. I only touch 01000A10041EA000 and 01000A10041EB009. The backup goes to the pack's .skynx\\sd-backups.",
});
Object.assign(STR.es, {
  "nav.add": "Agregar mods", "nav.library": "Biblioteca", home: "Inicio",
  dropHere: "Suelta aquí mods o modpacks",
  dropBrowser: "Arrastrar y soltar funciona en la ventana de la app. Aquí usa los botones.",
  spBy: "Hecho por", spThanksTitle: "Un agradecimiento gigante a KokaNX",
  spThanks: "Por todo su desarrollo y por explorar lo que Skyrim puede hacer en Switch: los límites de RAM y del .ccc, cómo deben cargar los BSA, los behaviors, el USSEP para Switch y muchísimas pruebas que hoy son reglas de esta app.",
  spAlso: "Gracias también a", spToolkit: "Antony Marshall y Zappastuff (licencia MIT): formatos de sonido de Switch y el método para convertir animaciones.",
  spXedit: "ElminsterAU y el equipo de xEdit.", spZedit: "Mator.", spLoot: "El equipo de LOOT: la masterlist y las reglas de orden de carga.",
  spUssep: "Arthmoor y su equipo, por el USSEP.", spTexconv: "Microsoft, por texconv.", spVgaudio: "Alex Barney; la versión para Switch viene del Skyrim NX Toolkit.",
  spFfmpeg: "El proyecto FFmpeg.", spNexus: "Por la API detrás de las descargas y las actualizaciones.",
  spCommunity: "La comunidad de mods de Switch", spCommunityP: "Todos los que convierten, prueban y comparten modpacks.",
  spBethesda: "Skyrim es de Bethesda Softworks y la Nintendo Switch es de Nintendo. Esta es una herramienta de fans, no oficial, sin relación con ninguno de los dos.",
  spHide: "No volver a mostrar", spEnter: "Entrar", spShow: "Créditos",
  suTitle: "Tu equipo", suSub: "Lo que SwitchNX Studio puede usar en este PC, lo que ya está y lo que falta. Nada de esto hace falta para abrir y arreglar un pack.",
  suGTools: "Para convertir mods de PC", suGGame: "Archivos y carpetas del juego", suGExtra: "Extras",
  suNeedConvert: "para convertir", suNeedNew: "para packs nuevos", suOptional: "opcional", suAlways: "siempre",
  suInis: "Inis de la consola", suVanilla: "Juego base (BSA)", suUssep: "USSEP de KokaNX",
  suFound: "Encontrado en", suLooked: "Busqué en", suPickFolder: "Elegir carpeta", suPickExe: "Elegir .exe", suChange: "Cambiar", suGo: "Ir",
  suAskFolder: "Ruta de la carpeta", suAskExe: "Ruta del .exe", suContinue: "Continuar", suBack: "Volver al pack", suLink: "Ver todo tu equipo",
  drBadge: "En creación", drBadgeTip: "Pack en creación: marca lo que va, renombra, agrega y, cuando esté listo, Crear modpack.",
  drTitle: (n) => `Pack en creación: ${n}`, drFrom: (n) => `· empezó desde ${n}`, drCreate: "Crear modpack",
  drGoes: "Mods que van", drIniTop: "Lista de ini más larga", drPlugins: "Plugins",
  drHint: "Si desmarcas un mod, sale de la lista de carga y de las inis (los números de arriba se actualizan); sus archivos se quedan hasta que crees el modpack. Si lo vuelves a marcar, regresa a donde estaba.",
  drFromCatalog: "Traer del Catálogo", drGoesTip: "Va en el modpack", drOut: "no va",
  drOutTitle: "Es un master", drUsers: (n, u) => `${n} es master de ${u}. Para que no vaya, esos tampoco pueden ir.`, drOutToo: "Sacarlos también",
  drCant: "No pude cambiarlo.", drMissing: (l) => `Algunos de sus archivos ya no están en Data: ${l}`,
  rnGo: "Renombrar", rnTitle: "Renombrar", rnWhich: "¿Cuál plugin?", rnBody: (n) => `Nombre nuevo para ${n}. Todo lo que usa ese nombre lo sigue, en un solo paso que se puede deshacer.`,
  rnPatch: (l) => `Dentro de los BSA (FaceGen, voces, scripts…): ${l}`, rnDeps: (l) => `Plugins que lo usan como master: ${l}`,
  rnList: (d, t) => `Lista de carga: ${d} bytes (${t})`, rnInis: (l) => `Inis: ${l}`, rnUseSafe: (n) => `Usar ${n}`, rnDone: (n) => `Renombrado a ${n}.`,
  drCreateBody: (g, t) => `Una copia limpia con los ${g} mods que van (de ${t}), sin historial ni los archivos de los que no van. El pack en creación queda como está, para la siguiente versión.`,
  drName: "Nombre", drWhere: "Carpeta (opcional)", drWherePh: "Vacío: Library\\Packs\\<nombre>",
  drOverCcc: (b, l) => `La lista de carga tiene ${b} bytes; el límite es de unos ${l}. Puede no arrancar.`, drOverIni: (c, l) => `Una lista de ini tiene ${c} caracteres; el límite es ${l}.`,
  drCreating: "Creando el modpack", drDone: "Modpack creado", drDoneBody: (d) => `Quedó en ${d}.`, drLeftOut: (n) => `Quedaron fuera (mods que no van): ${n} archivos`,
  drSdAsk: "¿Lo copio a la SD ahora?", drToSd: "Copiar a la SD", drManual: "Lo copio yo", drManualHint: "Abre la carpeta.", drLater: "Después",
  drStart: "Armar un pack desde este", drStartTip: "Un pack en creación que empieza como copia exacta de este; el original no se toca.",
  drStartBody: (n) => `Una copia de ${n}, idéntica archivo por archivo (mismo .ccc y mismas inis), en Library\\Drafts. En el mismo disco los archivos se enlazan, así que casi no ocupa espacio. Después marcas lo que va, renombras, agregas de otros packs y creas el modpack. ${n} no se toca.`,
  drMine: "mío", drCopying: "Copiando el pack",
  catIntoNew: "Pack nuevo", catIntoOpen: (n) => `Agregar a ${n}`, catIntoTitle: "Agregar al pack abierto", catIntoHint: (n) => `Los mods marcados entran a ${n}, con los masters que necesiten. Los que ya tiene se saltan.`, catIntoGo: "Agregar al pack",
  catNewName: "Nombre del pack nuevo", catNewNamePh: "Mi pack", catNewNameHint: "Se crea en Library\\Drafts como pack en creación (también sirve una ruta completa).", catNeedName: "Ponle nombre al pack nuevo.",
  "ws.bench": "Mesa", "ws.join": "Juntar BSA", "ws.merge": "Juntar plugins", "ws.home": "Todas las mesas", "ws.leave": "Salir del taller", "ws.tag": "Taller",
  filter: "Filtrar", ok: "Aceptar", libEditWs: "Editar en el taller", setLinks: "Enlazar archivos en packs en creación y modpacks creados (no ocupan el doble)",
  setLinksHint: "En el mismo disco, la copia comparte los archivos con el pack del que salió. La app nunca escribe dentro de un archivo (escribe uno nuevo y lo cambia), así que el original no cambia. Si editas archivos de esas carpetas con otros programas (CAO, NifSkope), hazlo sobre una copia aparte.",
  drLinked: (n) => `${n} archivos enlazados con el pack en creación (sin espacio extra)`, drInTitle: "Necesita sus masters", drNeeds: (n, m) => `${n} necesita ${m}, que marcaste para no ir.`, drInToo: "Marcarlos también", libBringBench: "Traer mods a la mesa", openFolder: "Abrir carpeta", openLibFolder: "Abrir la carpeta de la Biblioteca", folderCopied: (p) => `Ruta copiada: ${p}`,
  spcPacks: "Modpacks", spcPacksP: "Abrir, armar y arreglar packs completos para la Switch.", spcFrom: "Armar desde otro pack", spcFromP: "Una copia exacta que luego recortas, renombras y amplías.",
  spcFromToast: "Elige un pack y oprime \"Armar un pack desde este\".",
  spcWs: "Taller de mods", spcWsP: "Mods sueltos y suites, sin pack.", spcLibP: "Todo lo que has juntado: packs, mods, mods convertidos.",
  spcLibOpen: "Abrir la Biblioteca", spcLibOpenP: "Packs y mods, con su estado.", spcCat: "Catálogo", spcCatP: "Todos los mods de todos los packs, para escoger.",
  wsConvert: "Convertir un mod", wsConvertP: "Un mod de PC a mod de Switch para la Biblioteca.", wsBatch: "Convertir varios mods", wsBatchP: "Cada uno con sus opciones, todos de una, a la Biblioteca.", wsBatchName: "Lote", wsEdit: "Editar un mod", wsEditP: "Renombrar, extraer, SSEEdit, guardar.",
  wsSuite: "Juntar mods", wsSuiteP: "Varios mods en una suite: sus BSA juntos.", wsMerge: "Juntar plugins", wsMergeP: "Un merge con zMerge de zEdit, guiado.",
  wsBenches: "Mesas guardadas", wsBenchesTitle: "Mesas", wsNoBenches: "Todavía no hay mesas. Empieza con uno de los botones de arriba.",
  wsSub: "Una mesa es un espacio de trabajo privado para mods. Nada de aquí toca tus packs; el resultado va a Library\\Converted cuando lo guardas.",
  wsFiles: "archivos", wsEditOf: (n) => `editando ${n}`, wsKind_convert: "convertir", wsKind_edit: "editar", wsKind_suite: "suite", wsKind_merge: "merge",
  wsKindP_convert: "Convierte aquí un mod de PC, revísalo, renómbralo si hace falta y guárdalo en la Biblioteca.",
  wsKindP_edit: "El mod está en la mesa: renombra plugins (todo lo que usa el nombre lo sigue), extrae BSA, ábrelo en SSEEdit. Luego guárdalo.",
  wsKindP_suite: "Varios mods en una mesa. Junta sus BSA para que carguen como una suite y guárdala.",
  wsKindP_merge: "Varios plugins para fusionar en uno con zMerge, paso a paso.",
  wsPickOne: "Elige el mod.", wsPickMany: "Elige los mods (en el orden en que deben cargar).", wsNoLibMods: "La Biblioteca todavía no tiene mods sueltos.",
  wsOther: "Otra carpeta o .zip/.7z…", wsOtherAsk: "Ruta de la carpeta o del comprimido del mod", wsGo: "Continuar", wsNeedTwo: "Elige al menos dos mods.",
  wsEdAsk: "¿Para qué edición del juego?", wsConvertName: "Convertir", wsSuiteName: "Nombre de la suite", wsPreparing: "Preparando la mesa",
  wsSomeOut: "Algunos no entraron", wsPcHint: "Los mods de PC pasan primero por Convertir un mod; los que traen instalador FOMOD también.",
  wsBring: "Agregar mods a la mesa", wsConvertHere: "Convertir aquí un mod de PC", wsEmpty: "La mesa está vacía.",
  wsLoose: (l) => `Las carpetas sueltas (${l}) no se guardan con el mod; empácalas en un BSA convirtiéndolo.`,
  wsSaveTitle: "Guardar en la Biblioteca", wsSaveP: "Plugins y BSA van a Library\\Converted\\&lt;nombre&gt;, listos para cualquier pack y para el Catálogo. La mesa se queda hasta que la descartes.",
  wsSave: "Guardar", wsReplace: (n) => `Reemplazar ${n} (el anterior va a Library\\.trash)`, wsSaving: "Guardando",
  wsSaved: "Guardado", wsSavedP: (d) => `Quedó en ${d}.`, wsLooseLeft: (l) => `No se guardaron (carpetas sueltas): ${l}`, wsKeepBench: "Seguir trabajando", wsDoneBench: "Listo: descartar la mesa",
  wsDiscard: "Descartar esta mesa", wsDiscardP: "Se borra la carpeta de la mesa. Lo que guardaste en la Biblioteca se queda.",
  wsJoinSub: "Los BSA de todos los mods de la mesa quedan en uno (o en pocos si pesan mucho), con el nombre de un plugin para que carguen con él. Menos archivos y listas de ini más cortas.",
  wsJoinNeed: "Tiene que haber al menos dos BSA en la mesa.", wsJoinOrder: "Orden", wsJoinOrderP: "Como los lee el juego: si dos traen el mismo archivo, gana el que carga después.",
  wsJoinAnchor: "Nombre", wsJoinAnchorP: "El plugin con el que cargan. Sin plugin, van en la lista del ini.", wsJoinIni: "Ninguno: cargar desde el ini",
  wsJoinResult: "Resultado", wsJoinOverlaps: (n) => `Archivos que están en más de un BSA: ${n}`, wsWins: (b) => `queda el de ${b}`, wsNoOverlaps: "Ninguno.",
  wsJoinRetarget: (p) => `Las carpetas de voces y FaceGen de los plugins fusionados pasan a ${p}.`,
  wsJoinNote: "Los plugins siguen separados (el .ccc no cambia). Si después sacas uno de ellos de un pack, sus archivos siguen dentro del BSA juntado.",
  wsBack: "Volver a la mesa", wsJoining: "Juntando BSA", wsJoined: (n, l) => `${n} BSA juntados en ${l}.`, wsUndoHint: "Quedó en el historial de la mesa; se puede deshacer.",
  wsMergeSub: "Fusionar plugins libera líneas y bytes de la lista de carga. La fusión la hace zMerge (dentro de zEdit), la herramienta probada para eso; la app prepara, trae y ordena.",
  wsM1: "Plugins en la mesa", wsM1p: (n) => `${n} plugins por ahora. Agrega los que quieres fusionar.`, wsM1done: (p) => `Fusionados en ${p}.`,
  wsM2: "Fusionarlos en zEdit", wsM2p: "Armo una carpeta que zEdit acepta como Skyrim SE, con estos plugins y los archivos del juego, y abro zEdit.", wsM2go: "Preparar y abrir zEdit",
  wsM2folder: "Carpeta del juego para zEdit:",
  wsZ1: "En zEdit, crea un perfil de Skyrim SE con esa carpeta como ruta del juego (solo la primera vez).",
  wsZ2: "Abre el perfil, entra a zMerge y crea un merge nuevo con los plugins de la mesa.",
  wsZ3: "En la pestaña Data del merge, Copy General Assets puede quedar apagado: los BSA se juntan aquí después.",
  wsZ4: "Construye el merge. zMerge lo deja en su carpeta de salida (la ves en la configuración de zEdit).",
  wsNoZedit: "No encontré zEdit. Ponlo en C:\\SkyNX\\Tools\\zEdit o indícalo en Tu equipo.",
  wsM3: "Traer el merge", wsM3p: "Elige la carpeta que zMerge creó para este merge. Los plugins fusionados salen de la mesa; sus BSA se quedan para juntarlos.",
  wsM3ph: "Carpeta del merge que hizo zMerge", wsM3go: "Traer", wsM3in: (l) => `Dentro del merge: ${l}`, wsM3extra: (l) => `También se trajo: ${l}`,
  wsM3missing: (l) => `El merge nombra plugins que no estaban en la mesa: ${l}`,
  wsM4: "Juntar los BSA bajo el merge", wsM4p: "Para que carguen con el plugin fusionado; las carpetas de voces y FaceGen siguen su nombre.",
  wsM5: "Guardar la suite", wsM5p: "En Library\\Converted, lista para los packs.",
  nxConfirmed: "Lo confirmaste tú", nxKnown: "Descargado de Nexus con la app", nxLikely: "Encontrado por nombre en la lista de LOOT (probable)", nxMerge: "Un merge",
  nxWhich: "¿Cuál es?", nxMergeChip: "Merge: ver qué tiene", nxWhoTip: "Cómo se reconoció, otras opciones o cambiarlo",
  nxUnknown: "Todavía no se reconoce", nxIsMerge: "Es un merge de varios mods", nxVia: (n) => `encontrado como ${n}`,
  nxOriginal: (n) => `Nombre original: ${n}`, nxOthers: "Otras páginas que enlaza LOOT", nxThisOne: "Es este", nxInside: "Mods dentro del merge",
  nxAuthor: "Autor en el plugin", nxSearchLabel: "Buscar en Nexus", nxSearch: "Buscar en Nexus",
  nxPasteLink: "Enlace o número de Nexus", nxPasteHint: "Abre la página del mod en Nexus, copia la dirección y pégala aquí. Se recuerda para este plugin en todos los packs.",
  nxForgetMine: "Olvidar lo que dije", nxDetails: "Traer nombre y versión de Nexus", nxFetching: "Preguntando a Nexus",
  nxSaved: (n) => `Guardado: Nexus #${n}`, nxForgot: "Olvidado.", nxSummary: (k, n) => `Nexus: ${k} de ${n} mods reconocidos.`,
  nxGetMl: "Descargar la lista de LOOT para reconocer más", nxGetNames: (n) => `Traer nombres de Nexus (${n})`,
  bModeOne: "Un mod", bModeMany: "Varios a la vez",
  bSub: "Agrega varios mods y decide, tarjeta por tarjeta, cómo se convierte cada uno: dieta, tamaño, empacado y nombres de los plugins. Luego se convierten todos de una. Los que otros necesitan van primero.",
  bAddFiles: "Comprimidos…", bAddFolder: "Carpeta…", bAdd: "Agregar", bPathPh: "Ruta a un zip, 7z o carpeta de mod",
  bAll: "Para todos", bApply: "Aplicar a todos", bEmpty: "Todavía no hay mods. Agrega comprimidos o carpetas.",
  bRun: (n) => `Convertir ${n} mod${n === 1 ? "" : "s"}`, bClear: "Vaciar la lista", bReading: "Leyendo los mods",
  bInclude: "Convertirlo", bMore: "Más opciones", bWarn: (n) => `Avisos (${n})`, bFomod: "Tiene instalador (FOMOD): elige primero sus opciones.",
  bFomodGo: "Elegir opciones", bFromBatch: (n) => `lo trae ${n}`, bEst: (a, b) => `Texturas ${a} → ${b}`,
  bCccAll: (n) => `.ccc +${n} bytes`, bRunning: "Convirtiendo", bDoneTitle: "Convertidos",
  bDoneSum: (ok, n) => `${ok} de ${n} convertidos.`, bFailed: "Sin convertir", bPointed: (l) => `Apunta al nombre nuevo de: ${l}`,
  bLeft: "Los que no se convirtieron siguen en la lista.", bQueueGo: (n) => `Convertir todos los de PC (${n})`,
  bPlugins: (n) => `${n} plugin${n === 1 ? "" : "s"}`, bNoPlugins: "Sin plugins (texturas, mallas, sonidos)", bReread: "Leerlo de nuevo",
  cpBtn: "Versiones para Switch", cpOne: "Qué versión funciona en Switch", cpTitle: "Versiones que funcionan en Switch",
  cpIntro: "A veces las versiones nuevas empiezan a necesitar SKSE (plugins .dll, Address Library…), que no existe en Switch. Miro por dentro cada archivo en Nexus y sugiero la más nueva que todavía funciona.",
  cpYou: "Tienes", cpLatest: "Última", cpBest: "Mejor para Switch", cpUnverified: "sin verificar: Nexus no muestra la lista de archivos",
  cpAll: "Todos los archivos principales", cpHave: "Tengo esta", cpHaveSaved: "Guardé qué versión tienes.", cpOpenFile: "Archivos en Nexus",
  cpNone: "No hay mods identificados. Reconócelos primero (la etiqueta junto a cada mod).", cpSkipped: (n) => `Quedaron por fuera ${n} mods que aún no se reconocen.`,
  cpV: { ok: "Sirve en Switch", warn: "Revisar", no: "Necesita SKSE", unknown: "Sin revisar" },
  cpS: { best: "Tienes la última y funciona en Switch.", kept: "Tienes la mejor para Switch: las más nuevas necesitan SKSE o hay que revisarlas.",
    update: "Hay una versión más nueva que funciona en Switch.", have_skse: "Tu versión trae plugins de SKSE. Usa la que se sugiere.",
    all_skse: "Todos los archivos principales traen plugins de SKSE: ninguno funciona tal cual en Switch.", unknown_have: "No sé qué versión tienes. Marca la tuya con «Tengo esta».",
    none: "Nexus no muestra archivos principales de este mod." },
  fsTitle: "Antes de empezar", fsDone: "Todo listo.",
  fsTools: "Carpeta de herramientas", fsToolsOk: (d) => `texconv, ffmpeg y VGAudio están en ${d}.`,
  fsToolsNo: (d) => `Pon texconv, ffmpeg y el VGAudioCli del Toolkit en ${d} (en Ajustes cambias la carpeta). Solo hace falta para convertir mods de PC.`,
  fsSdk: "NvnTexpkg (texturas nativas de Switch)", fsSdkOk: "Encontrado.", fsSdkNo: "Opcional. Sin él, las texturas convertidas quedan en DDS (funcionan, pesan un poco más).",
  fsInis: "Inis limpios de la consola", fsInisOk: (d) => `Skyrim.ini está en ${d}.`, fsInisNo: (d) => `Copia Skyrim.ini y Skyrim_en.ini de tu consola a ${d}. Los packs nuevos parten de ahí.`,
  fsUssep: "USSEP (KokaNX)", fsUssepOk: (d) => `Está en ${d}. Los packs nuevos lo pueden incluir.`, fsUssepNo: (d) => `Opcional. Pon las carpetas de KokaNX (All_CC, SurvivalMode, No_CC y los BSA) en ${d}.`,
  fsLib: "Biblioteca", fsLibP: (d) => `Los modpacks y mods importados se guardan en ${d}.`,
  usTitle: "Parche no oficial (USSEP, versión KokaNX)", usNone: "No incluirlo",
  usNeeds: (l) => `Necesita ${l}; los agrego a la lista si faltan.`, usBase: "Solo el juego base.",
  usMissing: (d) => `No encontré USSEP en ${d}. Puedes cambiar la carpeta en Ajustes o agregarlo después como mod.`,
  usSe: "Special Edition no tiene Creation Club: solo sirve No_CC.",
  usHint: "Escoge el que corresponda a lo que vas a usar. All_CC es el completo para Anniversary.",
  addTitle: "Agregar mods", addSub: "Suelta zips, 7z o carpetas, o escógelos. Reviso cada uno y te digo qué es y qué hacer: los modpacks van a la Biblioteca, los mods de Switch entran directo, los de PC pasan por Convertir.",
  pickFiles: "Escoger archivos", pickFolder: "Escoger carpeta", queueAdd: "Agregar a la lista", pathsPh: "Ruta a un zip, 7z o carpeta",
  queueEmpty: "Todavía no hay nada.", detecting: "Revisando los archivos", clearDone: "Quitar los terminados",
  kind: { modpack: "Modpack", fomod: "Instalador FOMOD", "switch-mod": "Mod de Switch", "pc-mod": "Mod de PC", mixed: "PC + Switch", unknown: "No reconocido" },
  qImport: "Importar a la Biblioteca", qOpen: "Abrirlo", qBring: "Traer mods de ahí", qCheck: "Revisarlo", qAddAsIs: "Agregar tal cual",
  qConvert: "Convertir", qKeep: "Guardar copia en la Biblioteca", qRemove: "Quitar de la lista",
  qNeedPack: "Abre o crea un modpack primero para agregarle mods.",
  qRecAdd: "Listo para entrar tal cual.", qRecConvert: "Mejor por Convertir: arregla lo que ves arriba.",
  qDone: "Hecho", qImported: (p) => `En la Biblioteca: ${p}`,
  libTitle: "Biblioteca", libSub: (d) => `Modpacks y mods que tienes a mano, en ${d}. Cada pack muestra lo que opina el Doctor (revisión rápida).`,
  libImport: "Importar zip o carpeta", libRefresh: "Revisar de nuevo", libPacks: "Modpacks", libMods: "Mods", libEmpty: "La Biblioteca está vacía. Importa el zip de un modpack o suéltalo en la ventana.",
  libOpen: "Abrir", libBring: "Traer mods al pack actual", libAddPack: "Agregar al pack actual", libForget: "Olvidar",
  libForgetBody: (n) => `Saco <b>${esc(n)}</b> de la lista de la Biblioteca. No se borra nada del disco.`,
  libDelete: "Borrar", libDeleteBody: (n) => `Borro del disco la copia de <b>${esc(n)}</b> que tiene la Biblioteca. El zip del que la importaste no se toca.`,
  busyNow: "Espera a que termine la tarea actual.",
  libMissing: "La carpeta ya no está.", libExternal: "se queda donde está", libReading: "Leyendo la Biblioteca",
  health: { ok: "Se ve bien", warn: "Por revisar", broken: "Con problemas", error: "No se puede leer" },
  xTitle: (s, d) => `Traer mods de ${s} a ${d}`, xSub: "Escoge lo que quieras. Traigo también los masters que necesitan y dejo lo que el pack ya tiene.",
  xSort: "Ordenar", xSorts: { name: "Por nombre", order: "Como en el pack", size: "Por tamaño" },
  xFilter: "Filtrar", xPlan: "Preparar", xBack: "Volver", xSelected: (n) => `${n} escogidos`,
  xKinds: { plugin: "plugin", bsa: "solo BSA", archive: "empacado" },
  xPlanTitle: "Lo que va a pasar", xUnits: "Se traen", xWhy: { selected: "escogido", picked: "escogido", master: "lo necesitan como master" },
  xNeededBy: (l) => `lo necesita ${l}`, xSkipped: "Se quedan", xRefused: "No se pueden traer", xMissing: "Masters que faltan",
  xBudget: "Presupuesto", xCcc: (a, b, l) => `Lista de carga: ${a} → ${b}${l ? ` de ${l}` : ""} bytes`,
  xTex: (a, b) => `Texturas: ${a} en el pack + ${b}`, xBytes: (a) => `Se copian ${a}`,
  xGo: "Traerlos", xDoneTitle: "Mods traídos", xNothing: "Con esta selección no hay nada que traer.", xErrors: "Problemas",
  lootGo: "Sugerir orden (LOOT)", lootTitle: "Sugerencia de LOOT", lootSame: "El orden actual ya sigue la masterlist de LOOT.",
  lootMoves: (n) => `${n} ${n === 1 ? "plugin se mueve" : "plugins se mueven"}`, lootUse: "Usar este orden",
  lootAge: (d) => `Masterlist de hace ${d} días.`, lootNotes: "Notas de la masterlist", lootWarn: "Avisos",
  lootHint: "Ordena por masters, reglas y grupos de LOOT, y respeta tu orden donde nada dice lo contrario. El Creation Club y los archivos del juego no se mueven.",
  cfGo: "Revisar conflictos de archivos", cfTitle: "Conflictos de archivos", cfNone: "Ningún par de archivos BSA trae el mismo archivo.",
  cfStats: (s) => `${s.bsas} BSA, ${s.conflicting_paths} archivos en más de uno. Gana el que carga después: para texturas y modelos los BSA del ini cargan primero, como en PC; para scripts ganan los del ini.`,
  cfDead: "BSA reemplazados por completo", cfDeadP: (b, w) => `${esc(b)}: todos sus archivos los reemplaza ${esc(w)}.`,
  cfPairs: "Quién gana", cfPair: (w, l, n) => `${esc(w)} reemplaza ${n} de ${esc(l)}`, cfUnloaded: "BSA que nada carga",
  cfIdentical: (n) => `${n} son copias idénticas (inofensivas, solo ocupan espacio).`,
  sdPlan: "Ver los cambios", sdPlanTitle: "Lo que cambia en la SD", sdSync: "Copiar los cambios", sdFull: "Mejor copia completa",
  sdFullP: "Copia todo otra vez (más lento). Úsala si la SD se editó a mano o con otra herramienta.",
  sdRows: { copy: "Por copiar", new: "Nuevos", replace: "Reemplazar", delete: "Quitar", move: "Renombrados (sin copiar de nuevo)", rename: "Mayúsculas en el nombre", unchanged: "Sin cambios", backup: "Respaldo antes" },
  sdFits: (f) => `Libre en la SD: ${f}.`, sdNoFit: "No hay espacio suficiente en la SD.",
  sdAssume: "Sin cambios quiere decir mismo tamaño y fecha que en el PC. Solo toco las dos carpetas de Skyrim; lo que el pack ya no tiene se quita. Todo lo que se reemplaza o se quita va antes a un zip de respaldo.",
  sdFirst: "Primera copia: esta SD todavía no tiene las carpetas de Skyrim, así que todo entra nuevo y no hay nada que respaldar.",
  sdHow: "Conecta la SD de forma que Windows le dé una letra de unidad: métela en el lector de tarjetas del PC, o en la Switch abre hekate, Tools, USB Tools, SD Card. MTP (DBI) no da letra de unidad y falla con copias grandes.",
  sdMoveNote: (n) => `${n} archivos solo cambiaron de nombre en el pack (por ejemplo, nombres cortos de BSA): los renombro en la SD en vez de copiarlos otra vez.`,
  sdBackupNote: "El respaldo guarda cada archivo de la SD que se reemplaza o se quita, para que siempre puedas volver atrás.",
  sdMetaItem: "caché de Atmosphère, la rehace al abrir el juego",
  descAdd: "Describirlo", descEdit: "Editar", descTitle: (n) => `¿Qué es ${n}?`,
  descAsk: "Una línea sobre lo que hace este mod. Sale aquí y en SkyNX Mods en la consola. Vacío para quitarla.",
  sdConTitle: "Cambios hechos en la consola",
  sdCon: (off, on) => `SkyNX Mods (el homebrew) ${[off.length ? `apagó ${off.map(esc).join(", ")}` : "", on.length ? `activó ${on.map(esc).join(", ")}` : ""].filter(Boolean).join(" y ")}, al revés de como está en el proyecto.`,
  sdConUse: "Usar lo de la consola", sdConHint: "Si copias sin esto, la consola vuelve a la lista del proyecto.",
  sdConDone: "El proyecto ya tiene lo que elegiste en la consola.",
  sdMetaNote: "romfs_metadata.bin es la lista de archivos de mods que Atmosphère guarda para arrancar el juego más rápido. Se quita con los archivos viejos y Atmosphère la vuelve a crear la próxima vez que abres el juego.",
  prTitle: "Antes de empacar", prAnyway: "Empacar de todas formas", prGoLoot: "Ordenar con LOOT", prGoDoctor: "Ir al Doctor",
  prLoot: (n, l) => `LOOT todavía movería ${n} plugins (${l}). El orden decide qué mod gana cuando dos cambian lo mismo.`,
  prLootNever: "El orden de carga todavía no se ha revisado con LOOT.",
  prCrit: (n) => `El Doctor tiene ${n} problemas graves.`,
  prRoutine: (n, l) => `Quedan ${n} arreglos de rutina en el Doctor: ${l}.`,
  sdNothing: "La SD ya tiene este pack tal cual.", sdDone2: (r) => `Copiados ${r.copied}, quitados ${r.deleted}${r.moved ? `, renombrados ${r.moved}` : ""}, sin cambios ${r.unchanged}.`,
  libDirLabel: "Carpeta de la Biblioteca", ussepDirLabel: "Carpeta de USSEP (KokaNX)",
  reasonOrphan: "voces/caras con otro nombre",
  lootGuessMark: "(sugerido)", lootNoChoice: "Dejarlo a LOOT (General)", lootCommon: "Comunes", lootAllGroups: "Todos los grupos de LOOT",
  lootDupTitle: "El mismo mod dos veces", lootDup: (a, m) => `${a} está suelto en el pack y también dentro de ${m}. Sus registros cargan dos veces; deja uno de los dos.`,
  lootMergeTitle: "Plugins fusionados (merge)", lootMerge: (m, n) => `${m} contiene ${n} mods; las reglas de LOOT para ellos se le aplican a él.`,
  lootDummies: (l) => `Plugins vacíos que se dejan para que los parches encuentren sus masters: ${l}.`,
  lootUnknownTitle: (n) => `Plugins que LOOT no conoce (${n})`,
  lootPickBtn: "Escoger qué tipo de mod es cada uno",
  lootUnknownP: "Escoge la categoría que más se parezca a cada uno. Te sugiero una según lo que trae el plugin. Tu elección queda guardada para todos los packs y LOOT la usa desde ahora.",
  lootWhatGroups: "Qué significa cada categoría", lootCategory: "Categoría", lootSave: "Guardar y ordenar de nuevo", lootSaved: "Guardado. LOOT lo va a recordar.",
  lootChosen: (n) => `Tus elecciones guardadas en este pack (${n})`,
  vanillaDirLabel: "Archivos del juego base (los Skyrim - *.bsa de la consola)",
  vanillaHint: "Pon en una carpeta los archivos del juego que saques de romfs\\Data de la consola (sus BSA y sus plugins .esm y .esl) y apunta aquí. Con ellos la app arma la lista del juego contra la que el Doctor revisa scripts, meshes y texturas que faltan.",
  vanillaState: { unset: "Sin configurar.", missing: "Esa carpeta no existe.", empty: "No hay BSA en esa carpeta.", ok: "Listo." },
  drCopy: "Copiar informe", drCopyHint: "Copia todos los hallazgos con todos sus detalles en Markdown, para pegarlos en un chat o una nota.", drSave: "Guardar como .md",
  drCopied: "Informe copiado.", drSaved: (p) => `Guardado en ${p}`,
  vlNone: "La lista del juego todavía no está armada; el Doctor la arma la primera vez que revisa requisitos.", vlBuild: "Armarla ahora", vlBuilding: "Leyendo los archivos del juego",
  vlSummary: (n, b, p, d) => `Lista del juego: ${n} archivos de ${b} BSA, más lo que piden ${p} plugins del juego${d ? ` (actualizada el ${d})` : ""}. Ya armada, puedes borrar los BSA de la carpeta (la lista se queda), menos Skyrim - Interface.bsa, que trae los textos del juego. Conserva los .esm y .esl, que xEdit los necesita.`,
  vlMissing: (names) => `Nunca se armó con ${names}; el Doctor puede reportar sus archivos como faltantes.`,
  vlKept: (n) => `${n} archivos del juego ya no están en la carpeta; la lista conserva lo que tenían (es normal después de borrar los BSA).`, vlForget: "Olvidarlos (solo si ya no son parte del juego)",
  vlForgot: (n) => `Olvidé ${n} archivos.`, vlForgetWarn: "La lista va a quitar todo lo que tenían esos archivos. Si borraste los BSA a propósito, el Doctor volvería a marcar sus archivos como faltantes. Hazlo solo si ya no son parte del juego.", vlRebuild: "Poner la lista al día",
  libLegend: "Borrar elimina una copia que hizo la Biblioteca (el zip del que importaste se queda). Olvidar solo saca de la lista una carpeta que registraste; no se borra nada.",
  libDeleteTip: "Borra del disco la copia de la Biblioteca. El zip original no se toca.",
  libForgetTip: "Solo la saca de la lista. La carpeta se queda donde está.",
  xSafeNames: "Con nombre que Drive no daña",
  libTabList: "Packs y mods", libTabCatalog: "Catálogo", catReading: "Leyendo el catálogo",
  catSub: (p, n) => `${n} mods de ${p} packs de la Biblioteca, cada uno una sola vez. Escoge lo que quieras de cualquier pack; los masters vienen solos.`,
  catMulti: "Solo los que están en varios packs", catOnlyPicked: "Solo los escogidos", catInPacks: (n) => `en ${n} packs`, catIdentical: "idénticos",
  catInMerge: (m) => `también dentro de ${m}`, catVersion: "Versión", catMore: (n) => `${n} más: afina el filtro.`,
  catNewPack: "Pack nuevo", catPickSome: "Escoge mods a la izquierda para ver el presupuesto.", catCreate: "Crear el pack", catClear: "Quitar la selección",
  catSize: "Tamaño", catInisHint: "Los inis limpios de tu consola, o un pack de confianza: se conservan sus ajustes del ini y se le quitan los mods.", catAutoMasters: (n) => `${n} masters vienen solos`, catSkipped: (n) => `Se quedan (${n})`,
  catBlocked: "Hay problemas que impiden que el pack cargue bien:", catCreateAnyway: "Crearlo igual",
  catDone: "Pack creado", catDoneP: (n) => `${n} mods traídos. El Doctor ya lo revisó; agrega lo extra desde Agregar mods.`,
  cmpGo: "Comparar con el original", cmpAsk: "Ruta del mod original (zip, 7z o carpeta)", cmpWorking: "Comparando",
  cmpTitle: "Comparado con el original", cmpRecs: (a, r, c, s) => `registros: ${a} agregados, ${r} quitados, ${c} cambiados, ${s} iguales`,
  cmpAssets: "Archivos", cmpConv: (t, d, a, h) => `Conversión de formato: ${t} texturas (${d} además más pequeñas), ${a} sonidos, ${h} animaciones.`,
  cmpMeshes: "Meshes cambiados", cmpScripts: "Scripts cambiados", cmpScriptsGone: "Scripts quitados", cmpOnlyOrig: "Solo en el original", cmpOnlyConv: "Solo en el convertido",
  xtTitle: "Herramientas externas", xtSub: "Programas que la app te puede abrir. SSEEdit abre el pack actual con los .esm de la consola de la carpeta Vanilla.",
  xeOpen: "Abrir en SSEEdit", xeSync: "Traer cambios de SSEEdit", xeOpening: "Preparando SSEEdit", xeTitle: "SSEEdit",
  xeOpened: "SSEEdit se está abriendo con una copia de trabajo de este pack. Edita y guarda allá, ciérralo, y luego oprime Traer cambios de SSEEdit.",
  xeModeTitle: "¿Cómo quieres trabajar?", xeModeBody: "SSEEdit necesita los archivos base del juego junto a los plugins, así que siempre abre una carpeta de trabajo armada a partir de este pack.",
  xeDirect: "Trabajar sobre el pack", xeDirectHint: "Al cerrar SSEEdit, lo que guardaste entra solo al pack (queda en el historial para deshacer).",
  xeCopy: "Trabajar en una copia", xeCopyHint: "Al cerrar SSEEdit te pregunto qué hacer: traer los cambios, guardar la copia para después o borrarla.",
  xeOpenedDirect: "SSEEdit se está abriendo. Edita y guarda allá; al cerrarlo, los cambios entran al pack y al historial.",
  xeOpenedCopy: "SSEEdit se está abriendo con una copia de este pack. Edita y guarda allá; al cerrarlo te pregunto qué hacer con la copia.",
  xeKeptTitle: "Hay una copia de SSEEdit guardada", xeKeptBody: "Una copia anterior de este pack tiene cambios que todavía no están en el pack:",
  xeKeptReuse: "Seguir con esa copia", xeKeptBring: "Traer esos cambios primero", xeKeptDrop: "Empezar de cero (esos cambios se pierden)",
  xeClosedTitle: "SSEEdit se cerró", xeClosedChanges: (p) => `SSEEdit cambió estos archivos de la copia de ${p}:`, xeClosedNone: "SSEEdit se cerró sin cambiar nada.",
  xeDoBring: "Traer los cambios y borrar la copia", xeDoKeep: "Guardar la copia para después", xeDoDiscard: "Borrar la copia",
  xeForeignDrop: "Empezar de cero con este pack (esa copia se borra)",
  xeStuck: (l) => `Estos se editaron en la copia pero no pueden entrar al pack (archivos del juego, o que ya no están en el pack): ${l}. La copia se guarda para que no se pierdan.`,
  xeLeft: (l) => `Guardé la copia: estos no pudieron entrar al pack: ${l}.`,
  xeDiscarded: "Copia borrada. El pack no cambió.", xeKeptToast: "La copia queda guardada; Traer cambios de SSEEdit o Abrir en SSEEdit la retoman después.",
  xeUnfinished: "SSEEdit se cerró sin terminar de guardar estos archivos, así que no toqué el pack. La copia queda; ábrela de nuevo y guarda:",
  xeMissing: "No está en la copia de trabajo", xeAfter: "El pack no cambia hasta que traigas los cambios; ese paso queda en el historial.",
  xeNone: "Abre primero el pack en SSEEdit.", xeStillOpen: "SSEEdit sigue abierto (o no terminó de guardar). Ciérralo primero.",
  xeNoChanges: "SSEEdit no cambió nada.", xeConflicts: (l) => `Estos también cambiaron en el pack mientras tanto; gana la versión de SSEEdit: ${l}`,
  xeSynced: (n) => `${n} archivos traídos de SSEEdit. Quedaron en el historial.`,
  pmActive: "Activo (sin marcar: apagado con #)", pmMasters: "Masters", pmDisable: "Apagar el plugin",
  pmUsers: (n, u) => `${n} es master de ${u}. Si lo apagas, esos tampoco cargan.`, pmDisableAnyway: "Apagarlo igual",
  cvMaxSize: "Tamaño máximo de texturas", cvMaxNone: "El que diga la dieta", cvMaxHint: "Limita el lado más grande de cada textura (nunca agranda; las de interfaz no se tocan).",
  cvPacking: "Empacado", cvPack_ini1: "Un BSA en los inis (versión Switch, por defecto)", cvPack_plugin: "BSA con el nombre del plugin (sin ini)", cvPack_single: "Un solo BSA con el nombre del plugin (sin ini)", cvPack_ini: "BSA en los inis (la forma estable de Koka)",
  cvPackHint_ini1: "Todo en un BSA de nombre corto, en la lista del ini que tenga más espacio. La forma estable de Koka, con un nombre por mod en vez de dos.", cvPackHint_plugin: "Nombre.bsa y Nombre - Textures.bsa cargan con el plugin.", cvPackHint_single: "Todo en Nombre.bsa; carga con el plugin.",
  cvPackHint_ini: "Dos BSA en los inis (meshes y scripts en Skyrim.ini, texturas y voces en Skyrim_en.ini). Koka lo encontró lo más estable; gasta caracteres del ini.",
  cvCompress: "Comprimir los BSA", cvKeep: "Guardar también una copia en Biblioteca\\Converted (para usarlo en otros packs)",
  libConverted: "Convertido aquí", cvKept: (p) => `Quedó una copia en ${p}; aparece en la Biblioteca y en el Catálogo.`,
  packMoved: (p) => `La carpeta se había movido; la abrí desde ${p} y actualicé los recientes.`, extract: "Extraer", extractWhere: "Carpeta donde extraer", extractDone: (n, d) => `${n} archivos extraídos en ${d}`,
  fsVanilla: "Archivos del juego base (BSA y .esm de la consola)", fsVanillaOk: (d) => `Están en ${d}. El Doctor puede revisar scripts, meshes y texturas que faltan.`,
  fsVanillaNo: (d) => `Opcional. Extrae los Skyrim - *.bsa y los .esm de romfs\\Data de la consola en ${d}.`,
  inisDirLabel: "Inis de la consola para packs nuevos (Skyrim.ini, Skyrim_en.ini, Skyrim_aoc.ccc)",
  qBundle: "Entran juntos", qFromPack: "Traerlo desde su pack",
  qFromPackHint: (p) => `Está dentro del modpack ${p}. Si lo traes desde ahí, vienen también los masters que necesita y sus entradas del ini.`,
  texNotScanned: "Las texturas todavía no se han leído (solo la revisión profunda las lee).", texWithDiet: "Con dieta",
  dietDlgIntro: (b) => `Reducir las texturas dentro de <b>${b}</b>. Elige la regla de tamaño y, si quieres, un tamaño máximo.`, dietDlgEst: (a, b, n) => `Memoria de texturas: ${a} ahora, unos ${b} después (cambian ${n} texturas).`, dietDlgUndo: "El BSA original queda en el historial; se puede deshacer.",
  texDietGo: "Dieta", texDietHint: "Con dieta: lo que pesarían las texturas con la Dieta Switch 1 (1K; mapas, clutter y efectos a 512; mips reconstruidos) y BC1 donde no hay transparencia. Cada BSA con texturas tiene un botón Dieta, donde eliges la regla de tamaño (Dieta Switch 1, la de Koka, Extrema o el tamaño original) y un tamaño máximo; se resalta cuando la Dieta Switch 1 ahorra 8 MB o más. Necesita texconv, y NvnTexpkg para texturas de Switch. Las texturas de interfaz nunca se reducen.",
  safeAll: (b) => `Arreglos seguros en todas las categorías: ${b}`,
  nxKey: "Tu API key personal", nxKeyHint: "En nexusmods.com entra a la configuración de tu cuenta y busca API Keys; copia tu Personal API Key. Queda solo en este PC, en los ajustes de la app. Nexus permite keys personales para herramientas personales.",
  nxCheckSave: "Revisar y guardar", nxForget: "Olvidarla", nxPaste: "Pega primero la key.",
  nxConnected: (n, p) => `Conectado como ${n} (${p ? "Premium" : "cuenta gratis"}).`, nxNoKey: "Sin conectar.",
  nxHandler: "Botón Mod Manager Download de Nexus", nxHandlerOurs: "Lo maneja SwitchNX Studio.",
  nxHandlerOther: (h) => `Ahora lo maneja otro programa: ${h}`, nxHandlerNone: "Ningún programa lo maneja.",
  nxTakeOver: "Usar SwitchNX Studio para eso", nxGiveBack: "Devolvérselo al programa anterior", nxStopHandling: "Dejar de manejarlo",
  nxHandlerHint: "Con esto activo, el botón Mod Manager Download de la página de un archivo en Nexus lo manda aquí: se descarga en la Biblioteca y aparece en Agregar mods. Sirve con cuenta gratis. Vortex o Mod Organizer lo pueden recuperar cuando quieran, y el botón de arriba se lo devuelve.",
  nxDownloading: "Descargando de Nexus", nxDownloaded: (n) => `Descargado: ${n}. Está en Agregar mods.`,
  nxIdentify: "Buscarlo en Nexus", nxFound: (n) => `Encontrado en Nexus: ${n}`, nxNotFound: "Nexus no conoce este archivo (puede ser una conversión de Discord o un reempaque).",
  nxMany: (n) => `${n} posibles coincidencias en Nexus; no puedo escoger una con seguridad.`,
  nxUpdates: "Buscar actualizaciones en Nexus", nxNoNexusMods: "Ningún mod de este pack vino de Nexus todavía (descarga con el botón Mod Manager o usa Buscarlo en Nexus).",
  nxYours: "El tuyo", nxLatest: "El último", nxStUpdate: "Hay versión nueva", nxStOk: "Al día", nxStRemoved: "Retirado de Nexus", nxStError: "Error",
  nxUpdatesHint: "Solo se revisa cuando oprimes el botón (reglas de Nexus). Una actualización llega como archivo de PC: vuelve a pasar por Convertir.",
  rcGo: "Receta del pack", rcTitle: "Receta del pack", rcSub: "Cómo se armó este pack: cada mod con su origen (Nexus, Discord, otro pack), sus opciones de FOMOD, la configuración de conversión y los renombres, más el orden de carga y los inis. Sirve para ver qué cambió y para compartir el pack sin pasar archivos de nadie.",
  rcMods: "Mods", rcNexus: "De Nexus", rcUnknown: "Archivos sin origen conocido", rcSaved: "Guardada por última vez", rcNever: "nunca",
  rcChanges: "Cambios desde la receta guardada", rcNoChanges: "No cambió nada.", rcVerify: (n) => `${n} archivos difieren de la receta guardada`,
  rcSave: "Guardar la receta", rcExport: "Exportar para compartir (.md)", rcSavedOk: "Receta guardada.",
  rcExported: "Quedó en la carpeta del pack (no se copia a la SD). No tiene rutas de tu PC, y trae los links de Nexus de los mods que vinieron de allá.",
  rcExportHint: "Los packs armados antes de esta versión muestran sus archivos sin origen conocido; desde ahora queda registrado cada mod que agregues.",
  lootNothingPicked: "Cambia primero alguna categoría, o usa las sugeridas.", lootGone: "(ya no está en la masterlist)",
  lootSaveAll: "Usar todas las categorías sugeridas", lootSaveAllTip: "Guarda todas las sugerencias que ves, para todos los packs. Las puedes cambiar después aquí.",
  sdSub: "Comparo el pack con la SD y copio solo lo que cambió. Lo que se reemplaza o se quita queda antes en un .zip en el PC.",
  sdHint: "La raíz de la SD o su carpeta atmosphere\\contents. Solo toco 01000A10041EA000 y 01000A10041EB009. El respaldo queda en .skynx\\sd-backups del pack.",
});

// strings for the home paths, single tasks, first run and Help
Object.assign(STR.en, {
  p1T: "Work on one mod", p1P: "Turn a PC mod into a Switch mod, or open a Switch mod to rename, extract or edit it.",
  p1Convert: "Convert a PC mod", p1ConvertP: "Textures, sounds and plugin names, made ready for the Switch.",
  p1Edit: "Edit a Switch mod", p1EditP: "Rename it, extract its BSA, open it in SSEEdit.",
  p2T: "Work on many mods", p2P: "Several mods at once, each with its own options, or joined into one.",
  p2Batch: "Convert several mods", p2BatchP: "One narrow card per mod, all converted in one go.",
  p2Suite: "Join mods into one BSA", p2SuiteP: "Several mods under one plugin; frees load-list and ini space.",
  p2Merge: "Join plugins (merge)", p2MergeP: "A merge with zEdit's zMerge, guided step by step.",
  p3T: "Create your modpack", p3P: "A new pack for the Switch, from nothing or from what you've collected.",
  p3New: "Start from scratch", p3NewP: "An empty pack with the console's inis; add mods one by one.",
  p3Cat: "Pick mods from the Catalog", p3CatP: "Every mod of every pack in your Library, to choose from.",
  p3From: "Build from another pack", p3FromP: "An exact copy you then trim, rename and extend.",
  p4T: "Use a pre-made modpack", p4P: "A pack someone shared on Discord, a zip, or the one on your SD.",
  p4Open: "Open a modpack", p4OpenP: "A folder on the PC: check it, fix it, add to it.",
  p4Sd: "Bring it from the SD", p4SdP: "Copy what's on the SD to the PC first.",
  p4Import: "Keep it in the Library", p4ImportP: "Copy a pack folder or zip into your Library.",
  p4ImportAsk: "Path of the pack folder or zip",
  tasksTitle: "Single tasks", tasksP: "One job on a pack. If no pack is open, the app asks which one.",
  tkDoctor: "Check and fix a pack", tkDoctorP: "The Doctor lists the problems and shows each fix before applying it.",
  tkTex: "Resize textures", tkTexP: "Texture diet per BSA, with the memory it saves.",
  tkShrink: "Shrink a pack", tkShrinkP: "Texture diet, junk inside BSAs and other savings, in one list.",
  tkJoinBsa: "Join BSAs into one file", tkJoinBsaP: "Several mods' BSAs under one plugin. No pack needed.",
  tkConflicts: "Check file conflicts", tkConflictsP: "Which BSAs carry the same file, and which one wins.",
  tkOrder: "Sort the load order", tkOrderP: "LOOT's suggestion, arrows, and SSEEdit.",
  tkRename: "Rename a plugin safely", tkRenameP: "Plugin, BSA, voices, FaceGen and masters, all at once.",
  tkNexus: "Find Switch versions on Nexus", tkNexusP: "The best or latest version that works without SKSE.",
  tkSd: "Copy a pack to the SD", tkSdP: "Only what changed, with a backup of what it replaces.",
  tkUndo: "Undo a change", tkUndoP: "Every change the app made to a pack, ready to undo.",
  tkPickPack: "Which pack?", tkPickPackP: "This task works on a modpack. Pick a recent one, look for its folder, or choose it in the Library.",
  tkBrowse: "Look for its folder…", tkFromLib: "Choose it in the Library", tkLibToast: "Open a pack from the list; the task opens right after.",
  help: "Help", helpSub: "The manual: where everything is and what you can do there.", helpSearch: "Search the manual",
  helpNone: "Nothing in the manual matches that.", helpBack: "Back", helpToc: "Contents",
  inWhat: "SwitchNX Studio builds, checks, fixes and converts Skyrim modpacks for the Nintendo Switch (Anniversary and Special Edition). From the home screen you can:",
  inNext: "Next: your setup", inBack: "Back", inStart: "Start", inHelp: "Open the Help",
  inSetupT: "Your setup", inSetupAll: "Everything was found. Every part of the app works.",
  inSetupSome: (n) => `Opening, checking and fixing packs already works. ${n === 1 ? "One thing is" : n + " things are"} missing; each line says what it turns off until you add it.`,
  inLose: "Without it:", inLater: "You can come back to this any time: Settings » See all your gear.",
  homeSetup: "Your setup", homeSetupOk: "all set", homeSetupMiss: (n) => `${n} missing`,
});
Object.assign(STR.es, {
  p1T: "Trabajar un mod", p1P: "Pasar un mod de PC a mod de Switch, o abrir un mod de Switch para renombrarlo, extraerlo o editarlo.",
  p1Convert: "Convertir un mod de PC", p1ConvertP: "Texturas, sonidos y nombres de plugin, listos para la Switch.",
  p1Edit: "Editar un mod de Switch", p1EditP: "Renombrarlo, extraer su BSA, abrirlo en SSEEdit.",
  p2T: "Trabajar varios mods", p2P: "Varios mods a la vez, cada uno con sus opciones, o juntos en uno.",
  p2Batch: "Convertir varios mods", p2BatchP: "Una tarjeta angosta por mod, todos convertidos de una.",
  p2Suite: "Juntar mods en un BSA", p2SuiteP: "Varios mods bajo un plugin; libera espacio de la lista y del ini.",
  p2Merge: "Juntar plugins (merge)", p2MergeP: "Un merge con zMerge de zEdit, guiado paso a paso.",
  p3T: "Crear tu modpack", p3P: "Un pack nuevo para la Switch, desde cero o con lo que has juntado.",
  p3New: "Empezar desde cero", p3NewP: "Un pack vacío con las inis de la consola; le agregas mods uno a uno.",
  p3Cat: "Escoger mods del Catálogo", p3CatP: "Todos los mods de todos los packs de tu Biblioteca, para escoger.",
  p3From: "Armar desde otro pack", p3FromP: "Una copia exacta que luego recortas, renombras y amplías.",
  p4T: "Usar un modpack ya hecho", p4P: "Un pack que alguien compartió en Discord, un zip, o el que tienes en la SD.",
  p4Open: "Abrir un modpack", p4OpenP: "Una carpeta en el PC: revisarla, arreglarla, agregarle mods.",
  p4Sd: "Traerlo de la SD", p4SdP: "Primero copia al PC lo que hay en la SD.",
  p4Import: "Guardarlo en la Biblioteca", p4ImportP: "Copia a tu Biblioteca la carpeta o el zip de un pack.",
  p4ImportAsk: "Ruta de la carpeta o del zip del pack",
  tasksTitle: "Tareas sueltas", tasksP: "Un trabajo sobre un pack. Si no hay uno abierto, la app pregunta cuál.",
  tkDoctor: "Revisar y arreglar un pack", tkDoctorP: "El Doctor lista los problemas y muestra cada arreglo antes de aplicarlo.",
  tkTex: "Reducir texturas", tkTexP: "Dieta de texturas por BSA, con la memoria que ahorra.",
  tkShrink: "Aligerar un pack", tkShrinkP: "Dieta de texturas, basura dentro de los BSA y otros ahorros, en una lista.",
  tkJoinBsa: "Juntar BSA en un archivo", tkJoinBsaP: "Los BSA de varios mods bajo un plugin. No hace falta pack.",
  tkConflicts: "Revisar conflictos de archivos", tkConflictsP: "Qué BSA traen el mismo archivo y cuál gana.",
  tkOrder: "Ordenar la lista de carga", tkOrderP: "La sugerencia de LOOT, flechas y SSEEdit.",
  tkRename: "Renombrar un plugin sin romper nada", tkRenameP: "Plugin, BSA, voces, FaceGen y masters, todo de una.",
  tkNexus: "Buscar versiones para Switch en Nexus", tkNexusP: "La mejor o la última versión que funciona sin SKSE.",
  tkSd: "Llevar un pack a la SD", tkSdP: "Solo lo que cambió, con respaldo de lo que reemplaza.",
  tkUndo: "Deshacer un cambio", tkUndoP: "Cada cambio que la app hizo a un pack, listo para deshacer.",
  tkPickPack: "¿Qué pack?", tkPickPackP: "Esta tarea trabaja sobre un modpack. Escoge uno reciente, busca su carpeta o elígelo en la Biblioteca.",
  tkBrowse: "Buscar su carpeta…", tkFromLib: "Elegirlo en la Biblioteca", tkLibToast: "Abre un pack de la lista; la tarea se abre enseguida.",
  help: "Ayuda", helpSub: "El manual: dónde está cada cosa y qué se puede hacer ahí.", helpSearch: "Buscar en el manual",
  helpNone: "Nada en el manual coincide con eso.", helpBack: "Volver", helpToc: "Contenido",
  inWhat: "SwitchNX Studio arma, revisa, arregla y convierte modpacks de Skyrim para Nintendo Switch (Anniversary y Special Edition). Desde el inicio puedes:",
  inNext: "Siguiente: tu equipo", inBack: "Atrás", inStart: "Empezar", inHelp: "Abrir la Ayuda",
  inSetupT: "Tu equipo", inSetupAll: "Encontré todo. Toda la app funciona.",
  inSetupSome: (n) => `Abrir, revisar y arreglar packs ya funciona. ${n === 1 ? "Falta una cosa" : "Faltan " + n + " cosas"}; cada línea dice qué queda apagado hasta que la agregues.`,
  inLose: "Sin esto:", inLater: "Puedes volver aquí cuando quieras: Ajustes » Ver todo tu equipo.",
  homeSetup: "Tu equipo", homeSetupOk: "todo listo", homeSetupMiss: (n) => `${n === 1 ? "falta 1" : "faltan " + n}`,
});

// strings for projects (each modpack in its own folder), the workshop and the Mod Library
Object.assign(STR.en, {
  lede: "Build, check, fix and convert Skyrim modpacks for Nintendo Switch (AE and SE), then copy them to the SD with a backup.",
  pjTitle: "Projects", pjSub: "Each project is a modpack in its own folder: its mods, its history, and what goes to the Switch.",
  pjNew: "New project", pjEmpty: "No projects yet. Start one from scratch, from a modpack someone shared, or from your SD.",
  pjMods: (n, off) => `${n} mods${off ? ` · ${off} don't go` : ""}`, pjBuilt: (d) => `Packed ${d}`, pjSd: (d) => `SD ${d}`,
  pjNever: "Not packed yet", pjNoSerious: "nothing serious", pjDelete: "Delete",
  pjDeleteBody: (n) => `I'll move <b>${n}</b> to the Library's trash (.trash\\Projects). Nothing outside the project is touched, and you can bring it back from there.`,
  pjLegacyT: "Modpacks from before projects",
  pjLegacyP: "These are still in the Library from before. Turn each one into a project: it starts as an exact copy (linked on the same drive, so almost no extra space) and the original stays where it is. Delete the originals yourself when you no longer need them.",
  pjConvert: "Turn into a project", pjTag: "Project", pjLeave: "Projects",
  pjPack: "Pack", pjPackTip: "Makes the project's Switch folder: the two folders for the console, without the mods that don't go.",
  pjPacking: "Packing", pjPacked: "Packed", pjPackedBody: (d) => `The two folders for the Switch are in ${d}.`,
  pjToSd: "Copy to the SD", pjSetAside: (n, d) => `${n} ${n === 1 ? "file" : "files"} in Switch weren't made by the app or were changed by hand; I moved them to ${d}.`, pjOpenOut: "Open the folder", pjClose: "Close",
  pjModsTitle: (n) => `Project: ${n}`, pjModsFolder: "Mods folder", pjModFolder: "Folder",
  pjHint: "Untick a mod and it doesn't go to the Switch when you pack (the numbers above update); its files stay in the project. Each mod's files are in its own folder inside Mods; what you change there by hand comes into the project, with history.",
  pjFromPack: "From a modpack…", pjFromPackP: "Pick the modpack to bring mods from: its folder, its .zip/.7z/.rar, or another of your projects. It's only read.",
  pjAnother: "Another project", pjNoOthers: "There's no other project yet.",
  pjPulled: (n) => `${n} ${n === 1 ? "change" : "changes"} made by hand in the project folder came in (they're in the History).`,
  pjConflict: (n) => `${n} ${n === 1 ? "file was" : "files were"} changed both by hand and by the app: the app's version stays, yours is kept in .skynx\\mirror-conflicts.`,
  pjInplace: (n) => `${n} ${n === 1 ? "file" : "files"} in Mods ${n === 1 ? "was" : "were"} edited in place by another program: the change is in the project, but it can't be undone from the History.`,
  pjHeld: "Most of the project's working files are missing, so I didn't touch the Mods and Base folders. Reopen the project; if it persists, restore it from the History or the trash.",
  wsT: "Workshop", wsP: "Quick jobs on single mods, without a project. The result goes to the Mod Library.",
  libT: "Mod Library", libP: "Your converted and downloaded mods, and the Catalog with every mod of your projects.",
  libOpenMods: "Open the Mod Library", libOpenModsP: "Mods converted here, downloaded or added.",
  catOpen: "Catalog", catOpenP: "Every mod of every project, to bring into another.",
  npSub: "A project is a folder of its own in the Library: Mods (each mod in its folder), Base (the inis and the load list) and, when you pack, Switch (what goes to the console).",
  npName: "Project name", npNamePh: "My modpack", npWhere: (d) => `It goes in ${d}.`, npFrom: "Start from",
  np_empty: "Scratch", np_emptyP: "The console's clean inis; you add the mods.",
  np_pack: "A modpack", np_packP: "A folder, a .zip/.7z/.rar someone shared, or a pack from before.",
  np_sd: "The SD", np_sdP: "What's on your SD now.",
  npSrc: "Folder or archive of the modpack", npSrcPh: "C:\\Downloads\\Some modpack.zip", npFolder: "Folder…", npArchive: "Archive…",
  npSrcHint: "It's copied into the project (linked when it's on the same drive). The original isn't touched.",
  npSdHint: "The SD root or its atmosphere\\contents folder. The SD is only read.",
  npCreate: "Create project", npCreating: "Creating the project", npNeedName: "Give the project a name.", npNeedSrc: "Pick the modpack.",
  qNewProject: "New project with it",
  sdProject: "A project goes to the SD from its Switch folder: I pack it first, every time.",
  libTitle: "Mod Library", libTabList: "Mods",
  libSub: (d) => `Mods you keep at hand, in ${d}: converted here, downloaded or added. Modpacks aren't kept here: they're projects.`,
  libEmpty: "No mods yet. Convert one in the workshop, or import a mod's zip or folder.",
  libLegacyHint: (n) => `${n} modpacks from before are on Home, ready to become projects.`,
  catIntoNew: "New project", catNewPack: "New project", catNewName: "Name of the new project", catCreate: "Create the project",
  catNewNameHint: "It's created as a new project in the Library.", catDone: "Project created",
  libAddPack: "Add to the current project",
  catSub: (p, n) => `${n} mods from ${p} projects and the Library, each listed once. Pick what you want from any of them; masters come along on their own.`,
  setReopen: "When the app opens, go back to the pack that was open",
  setReopenHint: "Also after installing a new version. Closing the pack (Open another) starts the next time on the welcome page.",
  setLinks: "Link files with their origin when a project starts from another pack (they don't take the space twice)",
  setLinksHint: "Off (recommended): a new project copies the pack's files, so nothing you do in the project can touch the original. On: on the same drive the project shares the files with the original and takes almost no space; the app never writes into a shared file, but another program that saves a file in place (some editors, NifSkope) would change the original too.",
});
Object.assign(STR.es, {
  lede: "Arma, revisa, arregla y convierte modpacks de Skyrim para Switch (AE y SE), y cópialos a la SD con respaldo.",
  pjTitle: "Proyectos", pjSub: "Cada proyecto es un modpack en su propia carpeta: sus mods, su historial y lo que va a la Switch.",
  pjNew: "Nuevo proyecto", pjEmpty: "Todavía no hay proyectos. Empieza uno desde cero, desde un modpack que alguien compartió o desde tu SD.",
  pjMods: (n, off) => `${n} mods${off ? ` · ${off} no van` : ""}`, pjBuilt: (d) => `Empacado ${d}`, pjSd: (d) => `SD ${d}`,
  pjNever: "Sin empacar todavía", pjNoSerious: "nada grave", pjDelete: "Borrar",
  pjDeleteBody: (n) => `Muevo <b>${n}</b> a la papelera de la Biblioteca (.trash\\Projects). No se toca nada fuera del proyecto y lo puedes recuperar de ahí.`,
  pjLegacyT: "Modpacks de antes de los proyectos",
  pjLegacyP: "Siguen en la Biblioteca desde antes. Convierte cada uno en proyecto: empieza como copia exacta (enlazada en el mismo disco, así que casi no ocupa espacio) y el original queda donde está. Borra los originales tú mismo cuando ya no los necesites.",
  pjConvert: "Convertir en proyecto", pjTag: "Proyecto", pjLeave: "Proyectos",
  pjPack: "Empacar", pjPackTip: "Arma la carpeta Switch del proyecto: las dos carpetas para la consola, sin los mods que no van.",
  pjPacking: "Empacando", pjPacked: "Empacado", pjPackedBody: (d) => `Las dos carpetas para la Switch están en ${d}.`,
  pjToSd: "Llevar a la SD", pjSetAside: (n, d) => `${n === 1 ? "Un archivo" : n + " archivos"} de Switch no los hizo la app o se cambiaron a mano; los moví a ${d}.`, pjOpenOut: "Abrir la carpeta", pjClose: "Cerrar",
  pjModsTitle: (n) => `Proyecto: ${n}`, pjModsFolder: "Carpeta Mods", pjModFolder: "Carpeta",
  pjHint: "Si desmarcas un mod, no va a la Switch cuando empacas (los números de arriba se actualizan); sus archivos se quedan en el proyecto. Los archivos de cada mod están en su carpeta dentro de Mods; lo que cambies ahí a mano entra al proyecto, con historial.",
  pjFromPack: "Desde un modpack…", pjFromPackP: "Escoge el modpack del que traes mods: su carpeta, su .zip/.7z/.rar u otro de tus proyectos. Solo se lee.",
  pjAnother: "Otro proyecto", pjNoOthers: "Todavía no hay otro proyecto.",
  pjPulled: (n) => `Entraron ${n} ${n === 1 ? "cambio hecho" : "cambios hechos"} a mano en la carpeta del proyecto (quedan en el Historial).`,
  pjConflict: (n) => `${n === 1 ? "Un archivo cambió" : n + " archivos cambiaron"} a mano y en la app a la vez: queda la versión de la app y la tuya se guarda en .skynx\\mirror-conflicts.`,
  pjInplace: (n) => `${n === 1 ? "Un archivo de Mods fue editado" : n + " archivos de Mods fueron editados"} en su lugar por otro programa: el cambio está en el proyecto, pero no se puede deshacer desde el Historial.`,
  pjHeld: "Faltan la mayoría de los archivos de trabajo del proyecto, así que no toqué las carpetas Mods y Base. Vuelve a abrir el proyecto; si sigue, recupéralo desde el Historial o la papelera.",
  wsT: "Taller", wsP: "Trabajos rápidos sobre mods sueltos, sin proyecto. El resultado va a la Biblioteca de mods.",
  libT: "Biblioteca de mods", libP: "Tus mods convertidos y descargados, y el Catálogo con todos los mods de tus proyectos.",
  libOpenMods: "Abrir la Biblioteca de mods", libOpenModsP: "Mods convertidos aquí, descargados o agregados.",
  catOpen: "Catálogo", catOpenP: "Todos los mods de todos tus proyectos, para llevarlos a otro.",
  npSub: "Un proyecto es una carpeta propia en la Biblioteca: Mods (cada mod en su carpeta), Base (las inis y la lista de carga) y, al empacar, Switch (lo que va a la consola).",
  npName: "Nombre del proyecto", npNamePh: "Mi modpack", npWhere: (d) => `Queda en ${d}.`, npFrom: "Empezar desde",
  np_empty: "Cero", np_emptyP: "Las inis limpias de la consola; tú agregas los mods.",
  np_pack: "Un modpack", np_packP: "Una carpeta, un .zip/.7z/.rar que alguien compartió, o un pack de antes.",
  np_sd: "La SD", np_sdP: "Lo que tienes ahora en tu SD.",
  npSrc: "Carpeta o comprimido del modpack", npSrcPh: "C:\\Descargas\\Algún modpack.zip", npFolder: "Carpeta…", npArchive: "Comprimido…",
  npSrcHint: "Se copia al proyecto (enlazado si está en el mismo disco). El original no se toca.",
  npSdHint: "La raíz de la SD o su carpeta atmosphere\\contents. La SD solo se lee.",
  npCreate: "Crear proyecto", npCreating: "Creando el proyecto", npNeedName: "Ponle un nombre al proyecto.", npNeedSrc: "Escoge el modpack.",
  qNewProject: "Nuevo proyecto con él",
  sdProject: "Un proyecto va a la SD desde su carpeta Switch: lo empaco antes, siempre.",
  libTitle: "Biblioteca de mods", libTabList: "Mods",
  libSub: (d) => `Mods que tienes a mano, en ${d}: convertidos aquí, descargados o agregados. Los modpacks no se guardan aquí: son proyectos.`,
  libEmpty: "Todavía no hay mods. Convierte uno en el taller, o importa el zip o la carpeta de un mod.",
  libLegacyHint: (n) => `${n} modpacks de antes están en el Inicio, listos para volverse proyectos.`,
  catIntoNew: "Proyecto nuevo", catNewPack: "Proyecto nuevo", catNewName: "Nombre del proyecto nuevo", catCreate: "Crear el proyecto",
  catNewNameHint: "Se crea como proyecto nuevo en la Biblioteca.", catDone: "Proyecto creado",
  libAddPack: "Agregar al proyecto actual",
  catSub: (p, n) => `${n} mods de ${p} proyectos y de la Biblioteca, cada uno una sola vez. Escoge lo que quieras de cualquiera; los masters vienen solos.`,
  setReopen: "Al abrir la app, volver al pack que estaba abierto",
  setReopenHint: "También después de instalar una versión nueva. Si cierras el pack (Abrir otro), la próxima vez empieza en la bienvenida.",
  setLinks: "Enlazar archivos con su origen cuando un proyecto empieza desde otro pack (no ocupan el doble)",
  setLinksHint: "Apagado (recomendado): un proyecto nuevo copia los archivos del pack, así que nada de lo que hagas en el proyecto puede tocar el original. Encendido: en el mismo disco el proyecto comparte los archivos con el original y casi no ocupa espacio; la app nunca escribe dentro de un archivo compartido, pero otro programa que guarde un archivo en su lugar (algunos editores, NifSkope) cambiaría también el original.",
});

let LANG = "en";
const T = (k, ...a) => { const v = (STR[LANG] || STR.en)[k] ?? STR.en[k] ?? k; return typeof v === "function" ? v(...a) : v; };
const mb = (n) => (n / 1048576).toLocaleString(LANG === "es" ? "es-CO" : "en-US", { maximumFractionDigits: 1 }) + " MB";

let S = { state: null, pack: null, audit: null, filter: "todo", showCC: false, firstCrit: null, page: "welcome", conv: null, fomod: null };

// ------------------------------------------------------------------ bridge
function hasWebview() { return window.pywebview && window.pywebview.api; }
async function call(method, ...args) {
  if (hasWebview()) return await window.pywebview.api[method](...args);
  const r = await fetch("/api/" + method, { method: "POST", headers: { "X-SkyNX": "1" }, body: JSON.stringify(args) });
  return await r.json();
}
async function job(title, method, ...args) {
  const start = await call(method, ...args);
  if (!start || start.ok === false) { toast(start?.error || "Error", true); return null; }
  $("#veil").hidden = false; $("#veil-title").textContent = title;
  while (true) {
    await new Promise((r) => setTimeout(r, 250));
    const p = await call("progress", start.job ?? null);
    $("#veil-label").textContent = p.label && p.label !== "…" ? p.label : "";
    $("#veil-fill").style.width = p.n ? Math.round((100 * p.i) / p.n) + "%" : "15%";
    if (!p.busy) {
      $("#veil").hidden = true;
      if (p.error) { toast(p.error, true); return null; }
      return p.result;
    }
  }
}
async function followJob(title, jid) {
  $("#veil").hidden = false; $("#veil-title").textContent = title;
  while (true) {
    await new Promise((r) => setTimeout(r, 250));
    const p = await call("progress", jid);
    $("#veil-label").textContent = p.label && p.label !== "…" ? p.label : "";
    $("#veil-fill").style.width = p.n ? Math.round((100 * p.i) / p.n) + "%" : "15%";
    if (!p.busy) {
      $("#veil").hidden = true;
      if (p.error) { toast(p.error, true); return null; }
      return p.result;
    }
  }
}
function toast(msg, err = false) {
  const t = $("#toast"); t.textContent = msg; t.classList.toggle("err", err); t.hidden = false;
  clearTimeout(toast._t); toast._t = setTimeout(() => (t.hidden = true), err ? 8000 : 3500);
}
// Remove a mod; when other plugins use it as a master, offer to take them too.
async function removeWithUsers(id) {
  let r = await call("remove_mod", id);
  if (!r.ok && r.users && r.users.length) {
    const items = r.users.map((u) => `<li><b>${esc(u.plugin)}</b>${u.mod ? ` <small class="hint">(${u.whole ? T("rmUsersWhole", u.mod) : T("rmUsersPart", u.mod)})</small>` : ""}</li>`).join("");
    if (!(await confirmDlg(T("rmUsersTitle"), `<p>${T("rmUsersBody", id)}</p><ul class="report">${items}</ul>`, T("rmUsersGo", r.users.length + 1)))) return null;
    r = await call("remove_mod", id, true);
  }
  if (!r.ok) { toast(r.error, true); return null; }
  return r;
}

function confirmDlg(title, html, okLabel) {
  return new Promise((res) => {
    const d = $("#dlg"); $("#dlg-title").textContent = title; $("#dlg-body").innerHTML = html;
    $("#dlg-ok").textContent = okLabel || T("apply"); $("#dlg-cancel").textContent = T("cancel");
    $("#dlg-ok").hidden = false;
    // a stale close event from the previous dialog arrives while this one is open: ignore it
    d.onclose = () => { if (d.open) return; res(d.returnValue === "ok"); }; d.returnValue = ""; d.showModal();
  });
}
function choiceDlg(title, html, choices) {
  // choices: [{id, label, primary?, hint?}]; resolves with the chosen id, or "" if closed
  return new Promise((res) => {
    const d = $("#dlg"); $("#dlg-title").textContent = title;
    $("#dlg-body").innerHTML = html + `<div class="choices">${choices.map((c) => `<button type="button" class="${c.primary ? "primary" : "ghost"}" data-choice="${esc(c.id)}">${esc(c.label)}${c.hint ? `<small>${esc(c.hint)}</small>` : ""}</button>`).join("")}</div>`;
    $("#dlg-ok").hidden = true; $("#dlg-cancel").textContent = T("cancel");
    let picked = "";
    $$("#dlg-body [data-choice]").forEach((b) => b.addEventListener("click", () => { picked = b.dataset.choice; d.close(); }));
    d.onclose = () => { if (d.open) return; $("#dlg-ok").hidden = false; res(picked); }; d.returnValue = ""; d.showModal();
  });
}
function infoDlg(title, html) {
  return new Promise((res) => {
    const d = $("#dlg"); $("#dlg-title").textContent = title; $("#dlg-body").innerHTML = html;
    $("#dlg-ok").hidden = true; $("#dlg-cancel").textContent = "OK";
    d.onclose = () => { if (d.open) return; $("#dlg-ok").hidden = false; res(); }; d.showModal();
  });
}

// ------------------------------------------------------------------ language
function applyLang() {
  document.documentElement.lang = LANG;
  $$("[data-t]").forEach((el) => (el.textContent = T(el.dataset.t)));
  $$(".lang button").forEach((b) => b.classList.toggle("on", b.dataset.lang === LANG));
}
$$(".lang button").forEach((b) => b.addEventListener("click", async () => {
  LANG = b.dataset.lang; S.state = await call("set_lang", LANG); applyLang();
  if (S.pack) { const cur = await call("current"); if (cur) setAudit(cur); show(S.page); }
  else show(S.page);
}));

// ------------------------------------------------------------------ navigation
const WS_PAGES = new Set(["taller", "mesa", "juntar", "fusionar"]);
function spaceOf(page) {
  if (page === "help") return S.helpFrom && S.helpFrom !== "help" ? spaceOf(S.helpFrom) : "home";
  if (page === "library") return "library";
  if (WS_PAGES.has(page) || (S.pack?.bench && ["convertir", "historial"].includes(page))) return "workshop";
  if (["welcome", "setup", "new"].includes(page)) return "home";
  return "pack";
}
function syncChrome(page) {
  const bench = !!S.pack?.bench, has = !!S.pack;
  const inPack = has && !["welcome", "setup", "new", "taller"].includes(page);
  document.body.dataset.space = spaceOf(page);
  document.body.classList.toggle("no-pack", !inPack);
  document.body.classList.toggle("no-hud", bench);
  $("#menu").hidden = !inPack || bench;
  $("#menu-ws").hidden = !inPack || !bench;
  $("#hud").hidden = !inPack || bench;
  const proj = !!S.pack?.project;
  $("#btn-open-top").hidden = !has;
  $("#btn-open-top").textContent = bench ? T("ws.leave") : proj ? T("pjLeave") : T("openOther");
  $("#btn-create-pack").hidden = !(has && (proj || S.pack.draft));
  $("#btn-create-pack").textContent = proj ? T("pjPack") : T("drCreate");
  $("#btn-create-pack").title = proj ? T("pjPackTip") : T("drBadgeTip");
}
function show(page) {
  if (page !== "library") S.afterOpen = null;
  S.page = page;
  syncChrome(page);
  $$(".page").forEach((p) => p.classList.remove("on"));
  $("#p-" + page).classList.add("on");
  $$(".menu button").forEach((b) => b.classList.toggle("on", b.dataset.page === page));
  $("#btn-help").classList.toggle("on", page === "help");
  ({ taller: renderTallerHome, mesa: renderMesa, juntar: renderJuntar, fusionar: renderFusionar,
     resumen: renderSummary, doctor: renderDoctor, mods: renderMods, orden: renderOrder, texturas: renderTextures,
     historial: renderHistory, sd: renderSD, convertir: renderConvert, ajustes: renderSettings,
     welcome: renderWelcome, new: renderNew, add: renderAdd, library: () => renderLibrary(), setup: renderSetup, help: renderHelp }[page] || (() => {}))();
  $("#main").scrollTop = 0;
}
$$(".menu button").forEach((b) => b.addEventListener("click", () => show(b.dataset.page)));

// ------------------------------------------------------------------ help (the manual, from manual.js)
const HELP_FOR = { welcome: "start", setup: "setup", new: "projects", resumen: "pack", doctor: "doctor", add: "add",
  mods: "mods", orden: "order", texturas: "textures", historial: "pack", sd: "sd", convertir: "one-mod",
  library: "library", ajustes: "tools", taller: "workshop", mesa: "workshop", juntar: "many-mods", fusionar: "many-mods" };
const fold = (x) => String(x || "").normalize("NFD").replace(/[̀-ͯ]/g, "").toLowerCase();
function openHelp(section) {
  if (S.page !== "help") S.helpFrom = S.page;
  S.helpSec = section || HELP_FOR[S.helpFrom] || null;
  S.helpQ = "";
  show("help");
}
$("#btn-help").addEventListener("click", () => (S.page === "help" ? show(S.helpFrom || "welcome") : openHelp()));
function helpSections() {
  const M = window.MANUAL || {};
  return M[LANG] && M[LANG].length ? M[LANG] : M.en || [];
}
function renderHelp() {
  const el = $("#p-help"), secs = helpSections();
  el.innerHTML = `<div class="help">
      <nav class="help-toc" aria-label="${esc(T("helpToc"))}">
        <button class="link back-home" id="hp-back">${T("helpBack")}</button>
        <input id="hp-q" type="search" spellcheck="false" placeholder="${esc(T("helpSearch"))}" aria-label="${esc(T("helpSearch"))}" value="${esc(S.helpQ || "")}">
        <h4>${T("helpToc")}</h4>${secs.map((x) => `<a href="#h-${x.id}" data-sec="${x.id}">${esc(x.title)}</a>`).join("")}</nav>
      <div class="help-body">${secs.map((x) => `<section class="help-sec" id="h-${x.id}" data-sec="${x.id}"><h2>${esc(x.title)}</h2>${x.html}</section>`).join("")}
        <p class="empty" id="hp-none" hidden>${T("helpNone")}</p></div>
    </div>`;
  const text = Object.fromEntries(secs.map((x) => [x.id, fold(x.title + " " + x.html.replace(/<[^>]+>/g, " "))]));
  const filter = () => {
    const q = fold($("#hp-q").value.trim()); S.helpQ = $("#hp-q").value;
    // words that start with what you typed ("rar" finds .rar, not Library)
    const re = q ? new RegExp("(^|[^a-z0-9])" + q.replace(/[.*+?^${}()|[\]\\]/g, "\\$&")) : null;
    const hit = (id) => !re || re.test(text[id]);
    let n = 0;
    $$(".help-sec", el).forEach((sec) => { const on = hit(sec.dataset.sec); sec.hidden = !on; if (on) n++; });
    $$(".help-toc a", el).forEach((a) => (a.hidden = !hit(a.dataset.sec)));
    $("#hp-none").hidden = n > 0;
    $("#main").scrollTop = 0; mark();
  };
  $("#hp-q").addEventListener("input", filter);
  $("#hp-back").addEventListener("click", () => show(S.helpFrom && S.helpFrom !== "help" ? S.helpFrom : "welcome"));
  const jump = (id) => { const t = $("#h-" + CSS.escape(id), el); if (t) { t.hidden = false; t.scrollIntoView({ block: "start" }); } };
  el.onclick = (e) => {
    const a = e.target.closest("a[href^='#']"); if (!a) return;
    e.preventDefault();
    const h = a.getAttribute("href");
    if (h.startsWith("#h-")) { if ($("#hp-q").value) { $("#hp-q").value = ""; filter(); } jump(h.slice(3)); }
    else if (h.startsWith("#page-")) { const pg = h.slice(6); if (pg === "welcome" || pg === "setup" || pg === "library" || S.pack) show(pg); }
  };
  const toc = $$(".help-toc a", el);
  const mark = () => {
    const top = $("#main").getBoundingClientRect().top + 90;
    let cur = null;
    $$(".help-sec", el).forEach((sec) => { if (!sec.hidden && sec.getBoundingClientRect().top <= top) cur = sec.dataset.sec; });
    toc.forEach((a) => a.classList.toggle("on", a.dataset.sec === cur));
  };
  $("#main").onscroll = () => { if (S.page === "help") mark(); };
  if (S.helpQ) filter();
  if (S.helpSec && S.helpSec !== secs[0]?.id) requestAnimationFrame(() => { jump(S.helpSec); S.helpSec = null; mark(); });
  else { S.helpSec = null; mark(); }
}

// ------------------------------------------------------------------ welcome
// Projects (each modpack in its own folder), the workshop for quick jobs on
// single mods, and the Mod Library.
function renderWelcome() {
  S.afterOpen = null;
  const el = $("#p-welcome");
  const btn = (id, key, primary, attrs = "") => `<button class="${primary ? "primary" : "ghost"}" id="${id}" ${attrs}>${T(key)}<small>${T(key + "P")}</small></button>`;
  el.innerHTML = `
    <img src="img/emblem.png" alt="" class="crest">
    <h1 class="title">SwitchNX Studio</h1>
    <p class="lede">${T("lede")}</p>
    <div class="ornament" aria-hidden="true"></div>
    <section class="projects">
      <header><div><h3>${T("pjTitle")}</h3><p class="hint">${T("pjSub")}</p></div>
        <button class="primary" id="pj-new">${T("pjNew")}</button></header>
      <div id="pj-list" class="pj-grid"><p class="hint">…</p></div>
      <div id="pj-legacy"></div>
    </section>
    <div class="spaces two">
      <section class="space sp-ws"><header><h4>${T("wsT")}</h4><p>${T("wsP")}</p></header>
        <div class="acts">${btn("h-conv", "p1Convert", true, 'data-ws="convert"')}${btn("h-batch", "p2Batch", false, 'data-ws="batch"')}${btn("h-edit", "p1Edit", false, 'data-ws="edit"')}${btn("h-suite", "p2Suite", false, 'data-ws="suite"')}${btn("h-merge", "p2Merge", false, 'data-ws="merge"')}</div>
        <div class="foot"><button class="link" id="go-taller">${T("wsBenches")}</button></div></section>
      <section class="space sp-lib"><header><h4>${T("libT")}</h4><p>${T("libP")}</p></header>
        <div class="acts">${btn("go-lib2", "libOpenMods", true)}${btn("go-cat", "catOpen", false)}</div>
        <div class="foot"><button class="folder-link" id="go-libdir">${T("openLibFolder")}</button></div></section>
    </div>
    <p class="hint drop-hint">${T("dropHere")} · <button class="link" id="go-help">${T("help")}</button></p>
    <div id="first-steps"></div>`;
  $("#pj-new").addEventListener("click", () => { S.newProj = null; show("new"); });
  $("#go-lib2").addEventListener("click", () => { S.libTab = "list"; show("library"); });
  $("#go-cat").addEventListener("click", () => { S.libTab = "catalog"; show("library"); });
  $("#go-libdir").addEventListener("click", async () => openFolder((await call("state")).library_dir));
  $("#go-taller").addEventListener("click", () => show("taller"));
  $("#go-help").addEventListener("click", () => openHelp());
  $$("[data-ws]", el).forEach((b) => b.addEventListener("click", () => startWorkshop(b.dataset.ws)));
  renderProjects();
  renderFirstSteps();
}
const shortDate = (d) => (d ? String(d).slice(0, 16) : "");
async function renderProjects() {
  const box = $("#pj-list"); if (!box) return;
  let r; try { r = await call("projects"); } catch (e) { return; }
  if (!box.isConnected) return;
  const ps = r.projects || [];
  const card = (p) => {
    const h = p.health || {};
    const dots = h.when ? `<span class="pj-health">${h.critico ? `<i class="crit">${h.critico} ${esc(T("sev").critico)}</i>` : `<i class="ok">${esc(T("pjNoSerious"))}</i>`}${h.aviso ? `<i class="warn">${h.aviso} ${esc(T("sev").aviso)}</i>` : ""}</span>` : "";
    return `<div class="pj-card" data-pj="${esc(p.path)}" tabindex="0" role="button">
      <div class="pj-top"><b>${esc(p.name)}</b> <span class="mode">${esc(p.edition || "?")}</span></div>
      <div class="pj-facts">${esc(T("pjMods", p.mods || 0, p.off || 0))}${dots}</div>
      <div class="hint">${p.last_build ? esc(T("pjBuilt", shortDate(p.last_build))) : esc(T("pjNever"))}${p.last_sd ? ` · ${esc(T("pjSd", shortDate(p.last_sd)))}` : ""}</div>
      ${p.error ? `<p class="note warn">${esc(p.error)}</p>` : ""}
      <div class="pj-acts"><button class="folder-link" data-pjdir="${esc(p.path)}">${T("openFolder")}</button>
        <button class="link danger" data-pjdel="${esc(p.path)}" data-n="${esc(p.name)}">${T("pjDelete")}</button></div></div>`;
  };
  box.innerHTML = ps.length ? ps.map(card).join("") : `<div class="pj-empty"><p>${T("pjEmpty")}</p></div>`;
  $$("[data-pj]", box).forEach((c) => {
    const go = (e) => { if (e.target.closest("button")) return; openPack(c.dataset.pj); };
    c.addEventListener("click", go);
    c.addEventListener("keydown", (e) => { if (e.key === "Enter") go(e); });
  });
  $$("[data-pjdir]", box).forEach((b) => b.addEventListener("click", () => openFolder(b.dataset.pjdir)));
  $$("[data-pjdel]", box).forEach((b) => b.addEventListener("click", async () => {
    if (!(await confirmDlg(T("pjDelete"), `<p>${T("pjDeleteBody", esc(b.dataset.n))}</p>`, T("pjDelete")))) return;
    const x = await call("project_delete", b.dataset.pjdel);
    if (!x.ok) return toast(x.error, true);
    toast(T("done")); renderProjects();
  }));
  const leg = (r.legacy || []).filter((x) => !x.done);
  const lb = $("#pj-legacy");
  if (!lb) return;
  lb.innerHTML = leg.length ? `<details class="steps legacy" open><summary>${T("pjLegacyT")} · ${leg.length}</summary>
    <p class="hint">${T("pjLegacyP")}</p>
    <ul class="checklist">${leg.map((x) => `<li class="todo"><span class="mark">○</span><div><b>${esc(x.name)}</b> ${x.kind === "draft" ? `<span class="pill p-draft">${T("drBadge")}</span>` : ""}<p class="hint">${esc(x.path)}</p></div>
      <div class="act"><button class="ghost sm" data-legacy="${esc(x.path)}" data-n="${esc(x.name)}">${T("pjConvert")}</button></div></li>`).join("")}</ul></details>` : "";
  $$("[data-legacy]", lb).forEach((b) => b.addEventListener("click", () => newProjectFrom(b.dataset.legacy, b.dataset.n)));
}
// a new project that starts as a copy of a modpack (folder, archive or old pack)
async function newProjectFrom(src, name) {
  const nm = await askText(T("pjNew"), T("npName"), String(name || baseName(src)).replace(/\.(zip|7z|rar|001)$/i, ""));
  if (nm === null || !nm) return;
  const r = await job(T("npCreating"), "project_new", "pack", nm, { src });
  if (!r) return;
  S.firstCrit = null; packChanged(); setAudit(r); enterPack();
}
async function boot(resume = true) {
  S.state = await call("state");
  setTimeout(async () => { try { (await call("pending_nxm")).forEach((u) => window.onNxm(u)); } catch (e) { /* */ } }, 800);
  setTimeout(async () => { try { if ((await call("xedit_session")).session) watchXedit(); } catch (e) { /* */ } }, 1200);
  if (!hasWebview()) setInterval(async () => { try { (await call("pending_nxm")).forEach((u) => window.onNxm(u)); } catch (e) { /* */ } }, 4000);
  LANG = S.state.lang || "en"; applyLang();
  renderWelcome();
  let prefs = {}; try { prefs = await call("ui_prefs"); } catch (e) { /* */ }
  const cur = resume ? await call("current") : null;
  if (cur) { setAudit(cur); enterPack(); }
  else if (resume && prefs.intro_seen && prefs.reopen) {
    // a new version of the app (or a restart) goes back to the pack that was open
    if (!(await openPack(prefs.reopen))) renderWelcome();
  }
  if (resume && !prefs.intro_seen) showIntro(prefs);
  else if (resume && !prefs.splash_hide) showSplash(prefs);
}

// ------------------------------------------------------------------ splash (credits), first run and setup
function creditsHtml(prefs = {}) {
  const credit = (who, what) => `<li><b>${who}</b> <span>${what}</span></li>`;
  return `<img src="img/emblem.png" alt="" class="crest">
    <h1 id="splash-title">SwitchNX Studio</h1>
    <p class="by">${T("spBy")} <b>nealcobu</b> · v${esc(prefs.version || S.state?.version || "")}</p>
    <div class="ornament"></div>
    <div class="thanks"><h2>${T("spThanksTitle")}</h2><p>${T("spThanks")}</p></div>
    <h3>${T("spAlso")}</h3>
    <ul class="credits">
      ${credit("Skyrim NX Toolkit", T("spToolkit"))}
      ${credit("xEdit / SSEEdit", T("spXedit"))}
      ${credit("zEdit", T("spZedit"))}
      ${credit("LOOT", T("spLoot"))}
      ${credit("Unofficial Patch Project", T("spUssep"))}
      ${credit("DirectXTex (texconv)", T("spTexconv"))}
      ${credit("VGAudio", T("spVgaudio"))}
      ${credit("FFmpeg", T("spFfmpeg"))}
      ${credit("Nexus Mods", T("spNexus"))}
      ${credit(T("spCommunity"), T("spCommunityP"))}
    </ul>
    <p class="hint">${T("spBethesda")}</p>`;
}
function splashOpen(html, onEsc) {
  const el = $("#splash");
  el.innerHTML = `<div class="splash-card" role="dialog" aria-modal="true" aria-labelledby="splash-title">${html}</div>`;
  el.hidden = false; el.scrollTop = 0;
  if (splashOpen._esc) document.removeEventListener("keydown", splashOpen._esc);
  splashOpen._esc = (e) => { if (e.key === "Escape") onEsc(); };
  document.addEventListener("keydown", splashOpen._esc);
  return el;
}
function splashClose() {
  const el = $("#splash"); el.hidden = true; el.innerHTML = "";
  if (splashOpen._esc) document.removeEventListener("keydown", splashOpen._esc);
  splashOpen._esc = null;
}
function showSplash(prefs = {}) {
  const go = async () => {
    try { await call("set_ui_pref", "splash_hide", $("#sp-hide").checked); } catch (e) { /* */ }
    splashClose();
  };
  splashOpen(`${creditsHtml(prefs)}
    <div class="splash-foot">
      <label><input type="checkbox" id="sp-hide" ${prefs.splash_hide ? "checked" : ""}> ${T("spHide")}</label>
      <button class="primary" id="sp-go">${T("spEnter")}</button>
    </div>`, go);
  $("#sp-go").addEventListener("click", go);
  $("#sp-go").focus({ preventScroll: true });
}
// first run: who made it and what it does, then what's on this PC and what is off without the rest
async function showIntro(prefs = {}, step = 1) {
  const finish = async (then) => {
    try { await call("set_ui_pref", "intro_seen", true); } catch (e) { /* */ }
    splashClose(); if (then) then();
  };
  if (step === 1) {
    const paths = ["p1", "p2", "p3", "p4"].map((k) => `<li><b>${T(k + "T")}.</b> ${T(k + "P")}</li>`).join("");
    splashOpen(`${creditsHtml(prefs).replace('<div class="ornament"></div>', `<div class="ornament"></div>
      <div class="intro-what"><p>${T("inWhat")}</p><ul>${paths}</ul><p>${T("tasksP")}</p></div>`)}
      <div class="splash-foot"><button class="link" id="in-help">${T("inHelp")}</button>
        <button class="primary" id="in-next">${T("inNext")}</button></div>`, () => finish());
    $("#in-next").addEventListener("click", () => showIntro(prefs, 2));
    $("#in-help").addEventListener("click", () => finish(() => openHelp("start")));
    $("#in-next").focus({ preventScroll: true });
    return;
  }
  let items = [];
  try { items = (await call("setup_status")).items || []; } catch (e) { /* */ }
  const missing = items.filter((i) => !i.ok);
  const el = splashOpen(`<h1 id="splash-title" class="intro-h">${T("inSetupT")}</h1>
    <p class="intro-sum">${missing.length ? T("inSetupSome", missing.length) : T("inSetupAll")}</p>
    <div class="intro-setup">${setupGroupsHtml(items, { inSplash: true })}</div>
    <p class="hint">${T("inLater")}</p>
    <div class="splash-foot"><button class="ghost" id="in-back">${T("inBack")}</button>
      <span><button class="link" id="in-help">${T("inHelp")}</button> <button class="primary" id="in-start">${T("inStart")}</button></span></div>`, () => finish());
  wireSetup(el, () => showIntro(prefs, 2), { inSplash: true });
  $("#in-back").addEventListener("click", () => showIntro(prefs, 1));
  $("#in-help").addEventListener("click", () => finish(() => openHelp("setup")));
  $("#in-start").addEventListener("click", () => finish(() => show(S.pack ? S.page : "welcome")));
  $("#in-start").focus({ preventScroll: true });
}

const SETUP_NAMES = { texconv: "texconv", ffmpeg: "ffmpeg", vgaudio: "VGAudio", nvntexpkg: "NvnTexpkg", hbpp: "HavokBehaviorPostProcess", hkxc: "serde-hkx (hkxc)", nemesis: "Nemesis", rar: "7-Zip", inis: () => T("suInis"),
  vanilla: () => T("suVanilla"), ussep: () => T("suUssep"), library: () => T("nav.library"), sseedit: "SSEEdit", zedit: "zEdit",
  nifskope: "NifSkope", bae: "Bethesda Archive Extractor", cao: "Cathedral Assets Optimizer", loot: "LOOT", nexus: "Nexus Mods" };
const setupName = (i) => { const n = SETUP_NAMES[i.id]; return typeof n === "function" ? n() : n || i.id; };
function setupRowHtml(i, opts = {}) {
  const need = { convert: T("suNeedConvert"), new: T("suNeedNew"), optional: T("suOptional"), always: T("suAlways") };
  const fix = i.fix || {};
  const btn = fix.kind === "folder" ? `<button class="ghost sm" data-su-folder="${esc(fix.which)}">${T("suPickFolder")}</button>`
    : fix.kind === "tool" ? `<button class="ghost sm" data-su-tool="${esc(fix.id)}">${i.ok ? T("suChange") : T("suPickExe")}</button>`
    : fix.kind === "page" && !opts.inSplash && (S.pack || fix.page === "ajustes") ? `<button class="ghost sm" data-su-page="${esc(fix.page)}">${T("suGo")}</button>` : "";
  const lose = !i.ok && i.lose && pick2(i.lose) ? `<p class="lose"><b>${T("inLose")}</b> ${esc(pick2(i.lose))}</p>` : "";
  return `<li class="${i.ok ? "ok" : i.need === "optional" ? "opt" : "todo"}"><span class="mark">${i.ok ? "✓" : "○"}</span>
    <div><b>${esc(setupName(i))}</b> <span class="pill">${need[i.need] || ""}</span>
      <p>${esc(pick2(i.what))}</p>${lose}
      ${i.warn ? `<p class="note warn">${esc(pick2(i.warn))}</p>` : ""}
      ${i.path ? `<p class="hint">${i.ok ? T("suFound") : T("suLooked")} ${esc(i.path)}</p>` : ""}</div>
    <div class="act">${btn}</div></li>`;
}
function setupGroupsHtml(items, opts = {}) {
  const group = (g, title) => {
    const xs = items.filter((i) => i.group === g);
    return xs.length ? `<h3>${title} <small>${xs.filter((i) => i.ok).length}/${xs.length}</small></h3><ul class="checklist setup">${xs.map((i) => setupRowHtml(i, opts)).join("")}</ul>` : "";
  };
  return group("tools", T("suGTools")) + group("game", T("suGGame")) + group("extra", T("suGExtra"));
}
function wireSetup(root, rerender, opts = {}) {
  $$("[data-su-folder]", root).forEach((b) => b.addEventListener("click", async () => {
    const p = hasWebview() ? await call("pick_folder") : await askText(T("suPickFolder"), T("suAskFolder"), "");
    if (!p) return;
    S.state = b.dataset.suFolder === "tools_dir" ? await call("set_tools_dir", p) : await call("set_folder", b.dataset.suFolder, p);
    rerender();
  }));
  $$("[data-su-tool]", root).forEach((b) => b.addEventListener("click", async () => {
    const p = hasWebview() ? await call("pick_file") : await askText(T("suPickExe"), T("suAskExe"), "");
    if (!p) return;
    await call("set_tool_path", b.dataset.suTool, p); rerender();
  }));
  if (!opts.inSplash) $$("[data-su-page]", root).forEach((b) => b.addEventListener("click", () => show(b.dataset.suPage)));
}
async function renderSetup() {
  const el = $("#p-setup");
  el.innerHTML = `<h2>${T("suTitle")}</h2><p class="sub">${T("suSub")}</p><p class="hint">…</p>`;
  let r; try { r = await call("setup_status"); } catch (e) { return; }
  const items = r.items || [];
  el.innerHTML = `${S.pack ? "" : homeBtn()}<h2>${T("suTitle")}</h2><p class="sub">${T("suSub")}</p>
    ${setupGroupsHtml(items)}
    <div class="ornament"></div>
    <p><button class="primary" id="su-done">${S.pack ? T("suBack") : T("suContinue")}</button> <button class="link" id="su-credits">${T("spShow")}</button></p>`;
  wireHome(el);
  wireSetup(el, renderSetup);
  $("#su-done").addEventListener("click", () => show(S.pack ? "resumen" : "welcome"));
  $("#su-credits").addEventListener("click", async () => showSplash(await call("ui_prefs")));
}
async function leavePack() {
  const wasBench = !!S.pack?.bench;
  $("#packname").innerHTML = ""; S.pack = null; S.audit = null; packChanged();
  try { await call("close_pack"); S.state = await call("state"); } catch (e) { /* */ }
  show(wasBench ? "taller" : "welcome");
}
$("#btn-open-top").addEventListener("click", leavePack);
$("#btn-create-pack").addEventListener("click", () => (S.pack?.project ? projectBuild() : createModpack()));
document.addEventListener("change", async (e) => {
  if (e.target.id === "set-links") await call("set_ui_pref", "project_links", e.target.checked);
  if (e.target.id === "set-reopen") await call("set_ui_pref", "reopen_last", e.target.checked);
});
document.addEventListener("click", async (e) => {
  const t = e.target.closest && e.target.closest("#set-setup, #set-credits");
  if (!t) return;
  if (t.id === "set-setup") show("setup"); else showSplash(await call("ui_prefs"));
});
$("#btn-library-top").addEventListener("click", () => { S.xfer = null; show("library"); });
function syncToast(rep) {
  if (!rep) return;
  if (rep.held) toast(T("pjHeld"), true);
  else if (rep.conflicts?.length) toast(T("pjConflict", rep.conflicts.length), true);
  else if (rep.inplace?.length) toast(T("pjInplace", rep.inplace.length), true);
  else if (rep.pulled?.length) toast(T("pjPulled", rep.pulled.length));
}
// Pack: the project's Switch folder, then the SD if you want
// the usual routine before packing (LOOT order, Doctor's routine fixes): say
// what's left and let him go do it; true = go on
async function routineOk() {
  // the usual routine before packing: say what's left, and let him go do it.
  // "Pack anyway" also covers the copy to the SD that usually follows.
  if (S.routineAck) { S.routineAck = false; return true; }
  const pre = await job(T("working"), "pack_reminders");
  if (!pre) return false;
  setAudit(pre);
  if (pre.items.length) {
    const line = (it) => it.kind === "loot" ? T("prLoot", it.n, esc(it.names.join(", ")))
      : it.kind === "loot_never" ? T("prLootNever") : it.kind === "critico" ? T("prCrit", it.n)
      : it.kind === "routine" ? T("prRoutine", it.n, esc(it.names.join(" · "))) : T("bhAtPack");
    const loot = pre.items.some((i) => i.kind.startsWith("loot"));
    const doc = pre.items.some((i) => i.kind === "critico" || i.kind === "routine");
    const c = await choiceDlg(T("prTitle"), `<ul class="report">${pre.items.map((i) => `<li>${line(i)}</li>`).join("")}</ul>`, [
      ...(loot ? [{ id: "loot", label: T("prGoLoot"), primary: true }] : []),
      ...(doc ? [{ id: "doc", label: T("prGoDoctor"), primary: !loot }] : []),
      { id: "pack", label: T("prAnyway") }]);
    if (c === "loot") { show("orden"); lootSuggest(); return false; }
    if (c === "doc") { show("doctor"); return false; }
    if (c !== "pack") return false;
    S.routineAck = true;
  }
  return true;
}
async function projectBuild(force = false) {
  if (!force && !(await routineOk())) return;
  S.routineAck = true;   // the SD step right after doesn't ask again
  const r = await job(T("pjPacking"), "project_build");
  if (!r) return;
  if (r.pack) S.pack = r.pack;
  const b = r.build;
  const pick = await choiceDlg(T("pjPacked"), `<p>${T("pjPackedBody", esc(b.dest))}</p>
    <ul class="report"><li>${T("drPlugins")}: ${b.plugins}</li><li>BSA: ${b.bsas}</li>${b.ccc_bytes ? `<li>.ccc: ${b.ccc_bytes} bytes</li>` : ""}<li>Data: ${mb(b.size)}</li>
    ${b.left_out.length ? `<li>${T("drLeftOut", b.left_out.length)}</li>` : ""}</ul>
    ${b.set_aside?.length ? `<p class="note warn">${T("pjSetAside", b.set_aside.length, esc(b.trash))}</p>` : ""}
    ${r.behaviors === "never" || r.behaviors === "stale" ? `<p class="note warn">${T("bhAtPack")}</p>` : ""}`, [
    { id: "sd", label: T("pjToSd"), primary: true },
    { id: "dir", label: T("pjOpenOut") },
    { id: "close", label: T("pjClose") }]);
  if (pick === "sd") show("sd");
  else if (pick === "dir") openFolder(b.dest);
}

// ------------------------------------------------------------------ behaviors (FNIS / Nemesis)
async function renderBehaviors() {
  const box = $("#m-beh"); if (!box) return;
  const st = await call("behaviors_status");
  if (!box.isConnected || !st?.ok || !st.needed) { box.innerHTML = ""; return; }
  const mods = st.mods || [];
  const line = st.state === "ok" ? T("bhOk", esc(st.generated || ""), st.files || 0)
    : st.state === "stale" ? T("bhStale") : T("bhNever", mods.length);
  const miss = [!st.nemesis ? T("bhNoNemesis") : "", !st.havok ? T("bhNoHavok") : ""].filter(Boolean);
  box.innerHTML = `<div class="behaviors ${st.state === "ok" ? "ok" : "todo"}">
    <div class="db-head"><b>${T("bhTitle")}</b><span class="hint">${esc(mods.map((m) => m.id).join(", "))}</span>
      ${st.log?.done ? `<button class="primary" id="bh-finish">${T("bhFinish")}</button>` : ""}
      <button class="${st.state === "ok" || st.log?.done ? "ghost" : "primary"}" id="bh-go" ${miss.length || !mods.length ? "disabled" : ""}>${T("bhGo")}</button></div>
    <p>${line}</p>${miss.map((m) => `<p class="note warn">${m}</p>`).join("")}</div>`;
  $("#bh-go")?.addEventListener("click", bhGenerate);
  $("#bh-finish")?.addEventListener("click", bhFinish);
}
async function bhGenerate() {
  const info = await job(T("bhPreparing"), "behaviors_start");
  if (!info) return;
  const patches = info.patches?.length ? `<p>${T("bhPatches", esc(info.patches.join(", ")))}</p>` : "";
  const pick = await choiceDlg(T("bhTitle"), `<p>${T("bhOpened")}</p>
    <ol class="steps"><li>${T("bhStep1")}</li><li>${T("bhStep2")}</li><li>${T("bhStep3")}</li><li>${T("bhStep4")}</li></ol>${patches}
    <p class="hint">${T("bhWhere", esc(info.work))}</p>`,
    [{ id: "done", label: T("bhDone"), primary: true }, { id: "later", label: T("bhLater") }]);
  if (pick !== "done") { renderBehaviors(); return; }
  await bhFinish();
}
async function bhFinish() {
  const r = await job(T("bhCollecting"), "behaviors_finish");
  if (!r) { renderBehaviors(); return; }
  if (r.pack) S.pack = r.pack;
  setAudit(r);
  toast(T("bhAdded", r.files, r.hkx));
  renderMods();
}

async function openPack(path) {
  if (!path) { toast(T("needFolder"), true); return false; }
  const res = await job(T("reading"), "open_pack", path);
  if (!res) return false;
  const after = S.afterOpen; S.afterOpen = null;
  S.firstCrit = null; packChanged(); setAudit(res); enterPack();
  if (res.recovered && res.recovered.length) toast(T("recovered", res.recovered.join(", ")));
  if (res.moved) toast(T("packMoved", res.moved.to));
  if (after && !S.pack?.bench) after();
  return true;
}
async function importSd(sd, dest) {
  if (!sd || !dest) return toast(T("importNeed"), true);
  const r = await job(T("working"), "import_sd", sd, dest);
  if (r) { S.firstCrit = null; packChanged(); setAudit(r); enterPack(); }
}
function enterPack(page = "resumen") {
  show(S.pack?.bench && page === "resumen" ? "mesa" : page);
}
async function openFolder(path) {
  if (!path) return;
  const r = await call("open_folder", path);
  if (!r?.ok) { try { await navigator.clipboard.writeText(path); } catch (e) { /* */ } toast(T("folderCopied", path)); }
}
function setAudit(res) {
  if (res.pack) S.pack = res.pack;
  syncToast(res.sync);
  S.audit = res.audit;
  const crit = S.audit.findings.filter((f) => f.severity === "critico").length;
  if (S.firstCrit === null) S.firstCrit = crit;
  $("#packname").innerHTML = `<b>${esc(S.pack.bench ? S.pack.bench.name : S.pack.name)}</b><span class="mode">${esc(S.pack.mode)}</span>${S.pack.project ? `<span class="space-tag">${T("pjTag")}</span>` : S.pack.draft ? `<span class="mode draft" title="${esc(T("drBadgeTip"))}">${T("drBadge")}</span>` : ""}${S.pack.bench ? `<span class="space-tag">${T("ws.tag")}</span>` : ""}
    <button class="folder-link" id="pack-folder" title="${esc(S.pack.root)}">${T("openFolder")}</button>`;
  $("#pack-folder").addEventListener("click", () => openFolder(S.pack.root));
  syncChrome(S.page);
  $("#nav-crit").textContent = crit ? crit : "";
  renderHud();
}

// ------------------------------------------------------------------ new modpack
function renderNew() {
  const from = S.newProj || "empty";
  const tab = (id) => `<button class="np-tab ${from === id ? "on" : ""}" data-np="${id}"><b>${T("np_" + id)}</b><small>${T("np_" + id + "P")}</small></button>`;
  const body = {
    empty: `<div class="open-row"><label>${T("edition")}</label>
        <div class="radio-row"><label><input type="radio" name="ed" value="AE" checked> ${T("aeLabel")}</label><label><input type="radio" name="ed" value="SE"> ${T("seLabel")}</label></div></div>
      <div class="open-row"><label>${T("baseLabel")}</label>
        <div class="field"><input id="n-base" value="${esc(S.state?.inis_dir || "C:\\SkyNX\\Vanilla\\INIs")}">${hasWebview() ? `<button class="ghost" id="n-base-browse">${T("browse")}</button>` : ""}</div>
        <p class="hint">${T("baseHint")}</p></div>
      <div class="open-row" id="n-cc-row"><label>${T("ccLabel")}</label>
        <div class="radio-row">
          <label><input type="radio" name="cc" value="ussep" checked> ${T("ccUssep")}</label>
          <label><input type="radio" name="cc" value="all"> ${T("ccAll")}</label>
          <label><input type="radio" name="cc" value="none"> ${T("ccNone")}</label>
          <label><input type="radio" name="cc" value="base"> ${T("ccBase")}</label></div></div>
      <div class="open-row"><label>${T("usTitle")}</label><div id="n-ussep"></div></div>`,
    pack: `<div class="open-row"><label for="n-src">${T("npSrc")}</label>
        <div class="field"><input id="n-src" spellcheck="false" placeholder="${esc(T("npSrcPh"))}">${hasWebview() ? `<button class="ghost" id="n-src-dir">${T("npFolder")}</button><button class="ghost" id="n-src-arc">${T("npArchive")}</button>` : ""}</div>
        <p class="hint">${T("npSrcHint")}</p></div>`,
    sd: `<div class="open-row"><label for="n-sd">${T("sdDrive")}</label>
        <div class="field"><input id="n-sd" spellcheck="false" placeholder="${esc(T("importSd"))}"></div>
        <p class="hint">${T("npSdHint")}</p></div>`,
  }[from];
  $("#p-new").innerHTML = `${homeBtn()}
    <h2>${T("pjNew")}</h2>
    <p class="sub">${T("npSub")}</p>
    <div class="form">
      <div class="open-row"><label for="n-name">${T("npName")}</label>
        <div class="field"><input id="n-name" spellcheck="false" value="${esc(S.newProjName || "")}" placeholder="${esc(T("npNamePh"))}"></div>
        <p class="hint" id="n-where"></p></div>
      <div class="open-row"><label>${T("npFrom")}</label><div class="np-tabs">${tab("empty")}${tab("pack")}${tab("sd")}</div></div>
      ${body}
      <div><button class="primary" id="n-go">${T("npCreate")}</button> <button class="link" id="n-back" style="color:var(--ink-dim)">${T("cancel")}</button></div>
    </div>`;
  wireHome($("#p-new"));
  call("projects").then((r) => { const w = $("#n-where"); if (w) w.textContent = T("npWhere", r.root || ""); }).catch(() => {});
  $("#n-name").addEventListener("input", (e) => (S.newProjName = e.target.value));
  $$("[data-np]").forEach((b) => b.addEventListener("click", () => { S.newProj = b.dataset.np; renderNew(); }));
  if (from === "empty") {
    $$('input[name="ed"]').forEach((r) => r.addEventListener("change", () => { $("#n-cc-row").hidden = r.value === "SE" && r.checked; renderUssepPick(); }));
    renderUssepPick();
    $("#n-base-browse")?.addEventListener("click", async () => { const p = await call("pick_folder"); if (p) $("#n-base").value = p; });
  }
  const setSrc = (p) => {
    if (!p) return;
    $("#n-src").value = p;
    if (!$("#n-name").value.trim()) { $("#n-name").value = baseName(p).replace(/\.(zip|7z|rar|001)$/i, ""); S.newProjName = $("#n-name").value; }
  };
  $("#n-src-dir")?.addEventListener("click", async () => setSrc(await call("pick_folder")));
  $("#n-src-arc")?.addEventListener("click", async () => setSrc(await call("pick_archive")));
  if (S.newProjSrc && $("#n-src")) { setSrc(S.newProjSrc); S.newProjSrc = null; }
  $("#n-back").addEventListener("click", () => show("welcome"));
  $("#n-go").addEventListener("click", async () => {
    const name = $("#n-name").value.trim();
    if (!name) { $("#n-name").focus(); return toast(T("npNeedName"), true); }
    let opts = {};
    if (from === "empty") {
      const base = $("#n-base").value.trim();
      if (!base) return toast(T("needFolder"), true);
      opts = { edition: $('input[name="ed"]:checked').value, base, preset: $('input[name="cc"]:checked').value,
               ussep: $('input[name="us"]:checked')?.value || "" };
    } else if (from === "pack") {
      const src = $("#n-src").value.trim();
      if (!src) { $("#n-src").focus(); return toast(T("npNeedSrc"), true); }
      opts = { src };
    } else {
      const sd = $("#n-sd").value.trim();
      if (!sd) { $("#n-sd").focus(); return toast(T("importNeed"), true); }
      opts = { sd };
    }
    const r = await job(T("npCreating"), "project_new", from, name, opts);
    if (r) { S.newProjName = ""; S.firstCrit = null; packChanged(); setAudit(r); enterPack(from === "empty" ? "mods" : "resumen"); }
  });
}

// ------------------------------------------------------------------ HUD
function renderHud() {
  const st = S.audit.stats, f = S.audit.findings;
  const crit = f.filter((x) => x.severity === "critico").length;
  const health = crit === 0 ? 100 : Math.max(6, 100 - crit * (90 / Math.max(S.firstCrit || crit, 1)));
  const hb = $("#bar-health");
  hb.querySelector(".fill").style.width = `calc(${health}% - 4px)`;
  hb.querySelector(".lbl").textContent = T("hudCrit", crit);
  const cb = $("#bar-ccc");
  if (st.list_limit) {
    cb.querySelector(".fill").style.width = `calc(${Math.min(100, (100 * st.list_bytes) / st.list_limit)}% - 4px)`;
    cb.querySelector(".lbl").textContent = T("hudCcc", st.list_bytes, st.list_limit);
    cb.classList.toggle("warn", st.list_bytes > 3900);
  } else {
    cb.querySelector(".fill").style.width = "0";
    cb.querySelector(".lbl").textContent = T("hudPlugins", st.list_entries || 0);
  }
  const maxc = Object.values(st.ini_lists || {}).reduce((m, x) => Math.max(m, x.chars), 0);
  const ib = $("#bar-ini");
  ib.querySelector(".fill").style.width = `calc(${Math.min(100, (100 * maxc) / 1024)}% - 4px)`;
  ib.querySelector(".lbl").textContent = T("hudIni", maxc);
  ib.classList.toggle("warn", maxc > 900);
}

// ------------------------------------------------------------------ summary
function counts() {
  const c = { critico: 0, aviso: 0, ahorro: 0, info: 0 };
  S.audit.findings.forEach((f) => c[f.severity]++);
  return c;
}
function renderSummary() {
  const st = S.audit.stats, c = counts();
  const verdict = c.critico ? T("verdictCrit", c.critico) : c.aviso ? T("verdictWarn", c.aviso) : T("verdictOk");
  const fmts = Object.entries(st.tex_formats || {}).slice(0, 6).map(([k, v]) => `${esc(k)}: ${v}`).join(", ") || T("noData");
  $("#p-resumen").innerHTML = `
    <h2>${T("nav.summary")}</h2>
    <p class="sub">${esc(st.root)}</p>
    <p class="verdict">${verdict}</p>
    <div class="sevline">${SEV_ORDER.map((s) => `<span class="sev-n s-${s}"><span class="tick"></span><b>${c[s]}</b> ${T("sev")[s].toLowerCase()}</span>`).join("")}</div>
    <div class="cv-actions"><button class="primary" id="go-doctor">${T("openDoctor")}</button>
      ${S.pack.project ? `<button class="primary" id="sum-pack">${T("pjPack")}</button><button class="ghost" id="sum-sd">${T("nav.sd")}</button>` : ""}</div>
    <div class="ornament"></div>
    <dl class="ledger">
      <div><dt>${T("gameVer")}</dt><dd>${st.mode === "AE" ? T("aeName") : st.mode === "SE" ? T("seName") : T("none")}</dd></div>
      <div><dt>${T("entriesIn", esc(st.list_name || ""))}</dt><dd>${st.list_entries ?? 0} ${st.cc_entries ? T("ofCC", st.cc_entries) : ""}</dd></div>
      <div><dt>${T("active")}</dt><dd>${T("ofData", st.plugins_active ?? 0, st.plugins_total ?? 0)}</dd></div>
      <div><dt>${T("bsaData")}</dt><dd>${st.bsas_total ?? 0}</dd></div>
      <div><dt>${T("dataSize")}</dt><dd>${mb(st.data_bytes || 0)}</dd></div>
      <div><dt>${T("texActive")}</dt><dd>${mb(st.tex_bytes || 0)}</dd></div>
      <div><dt>${T("texFormats")}</dt><dd>${fmts}</dd></div>
      <div><dt>${T("audio")}</dt><dd>${Object.entries(st.audio || {}).map(([k, v]) => `${k}: ${v}`).join(", ") || T("noData")}</dd></div>
    </dl>
    <h3>${T("heaviest")}</h3>
    ${texTable(st.tex_top || [], 8)}`;
  $("#go-doctor").addEventListener("click", () => show("doctor"));
  $("#sum-pack")?.addEventListener("click", () => projectBuild());
  $("#sum-sd")?.addEventListener("click", () => show("sd"));
}
function texTable(rows, n) {
  rows = rows.filter((r) => (r.bytes ?? r.tex) > 0);
  if (!rows.length) return `<p class="empty">${T("noTex")}</p>`;
  const max = Math.max(...rows.map((r) => r.bytes ?? r.tex), 1);
  return `<table><tr><th>BSA</th><th class="r">${T("tex")}</th><th></th></tr>${rows.slice(0, n).map((r) => {
    const b = r.bytes ?? r.tex;
    return `<tr><td>${esc(r.bsa)}</td><td class="r">${mb(b)}</td><td><div class="meter"><i style="width:${(100 * b) / max}%"></i></div></td></tr>`; }).join("")}</table>`;
}

// ------------------------------------------------------------------ doctor
function renderDoctor() {
  const all = S.audit.findings;
  const list = S.filter === "todo" ? all : all.filter((f) => f.severity === S.filter);
  const safe = all.filter((f) => f.fix && f.fix.risk === "seguro").length;
  const c = counts();
  const groups = {};
  list.forEach((f) => (groups[f.category] = groups[f.category] || []).push(f));
  const order = Object.keys(groups).sort((a, b) => Math.min(...groups[a].map((f) => SEV_ORDER.indexOf(f.severity))) - Math.min(...groups[b].map((f) => SEV_ORDER.indexOf(f.severity))));
  $("#p-doctor").innerHTML = `
    <h2>${T("nav.doctor")}</h2>
    <p class="sub">${T("doctorSub")}</p>
    <div class="doctor-head">
      <button class="primary" id="fix-safe" ${safe ? "" : "disabled"} title="${esc(T("safeAll", SEV_ORDER.map((v) => [v, all.filter((f) => f.fix && f.fix.risk === "seguro" && f.severity === v).length]).filter(([, n]) => n).map(([v, n]) => `${n} ${T("sev")[v].toLowerCase()}`).join(" · ")))}">${T("fixSafe", safe)}</button>
      <button class="ghost" id="reaudit">${T("recheck")}</button>
      <button class="ghost" id="dr-copy" title="${esc(T("drCopyHint"))}">${T("drCopy")}</button>
      <button class="ghost" id="dr-save">${T("drSave")}</button>
      <div class="filters">${["todo", ...SEV_ORDER].map((s) => `<button data-f="${s}" class="${S.filter === s ? "on" : ""}">${s === "todo" ? T("all") : T("sev")[s]} ${s === "todo" ? all.length : c[s]}</button>`).join("")}</div>
    </div>
    ${order.length ? order.map((cat) => groupHtml(cat, groups[cat])).join("") : `<p class="empty">${T("nothingHere")}</p>`}`;
  $$("#p-doctor .filters button").forEach((b) => b.addEventListener("click", () => { S.filter = b.dataset.f; renderDoctor(); }));
  $("#reaudit").addEventListener("click", async () => { const r = await job(T("working"), "reaudit", true); if (r) { setAudit(r); renderDoctor(); } });
  $("#fix-safe").addEventListener("click", fixSafe);
  $("#dr-copy").addEventListener("click", async () => {
    const r = await call("doctor_report"); if (!r.ok) return;
    try { await navigator.clipboard.writeText(r.md); toast(T("drCopied")); }
    catch (e) { const s2 = await call("save_text", r.name, r.md); if (s2.ok) toast(T("drSaved", s2.path)); }
  });
  $("#dr-save").addEventListener("click", async () => {
    const r = await call("doctor_report"); if (!r.ok) return;
    const s2 = await call("save_text", r.name, r.md); if (s2.ok) toast(T("drSaved", s2.path));
  });
  $$("#p-doctor [data-fix]").forEach((b) => b.addEventListener("click", () => fixOne(b.dataset.fix)));
  $$("#p-doctor [data-goloot]").forEach((b) => b.addEventListener("click", async () => { show("orden"); await lootSuggest(); }));
}
function groupHtml(cat, fs) {
  fs.sort((a, b) => SEV_ORDER.indexOf(a.severity) - SEV_ORDER.indexOf(b.severity));
  const byCode = {};
  fs.forEach((f) => (byCode[f.code] = byCode[f.code] || []).push(f));
  let html = "";
  for (const code of Object.keys(byCode)) {
    const arr = byCode[code];
    if (arr.length > 6 && !arr.some((f) => f.fix)) {
      const f = arr[0];
      html += `<div class="finding s-${f.severity}"><span class="tick"></span><div><div class="t">${T("cases", arr.length, esc(f.title))}</div><div class="d">${esc(f.detail)}</div>
        <details class="more"><summary>${T("seeAll", arr.length)}</summary><div class="sub-findings">${arr.map(findingHtml).join("")}</div></details></div><div></div></div>`;
    } else html += arr.map(findingHtml).join("");
  }
  return `<div class="group"><h3>${esc(cat)} <small>${fs.length}</small></h3>${html}</div>`;
}
function findingHtml(f) {
  const items = f.items && f.items.length ? `<details class="more"><summary>${T("details", f.items.length)}</summary><ul class="items">${f.items.map((i) => `<li>${esc(i)}</li>`).join("")}</ul></details>` : "";
  const btn = (f.fix ? `<button class="fix ${f.fix.risk === "seguro" ? "safe" : ""}" data-fix="${esc(f.id)}">${esc(f.fix.label)}</button>` : "")
    + (f.alt || []).map((a, i) => `<button class="fix" data-fix="${esc(f.id)}#alt${i}">${esc(a.label)}</button>`).join("")
    + (f.code === "loot-unknown" ? `<button class="fix" data-goloot="1">${T("lootPickBtn")}</button>` : "");
  return `<div class="finding s-${f.severity}"><span class="tick" title="${T("sev")[f.severity]}"></span>
    <div><div class="t">${esc(f.title)}</div><div class="d">${esc(f.detail)}</div>${items}</div><div class="act">${btn}</div></div>`;
}
async function fixOne(id) {
  const pv = await call("preview_fix", id);
  if (!pv.ok) { toast(pv.error, true); return; }
  const ok = await confirmDlg(pv.label, `<ul>${pv.changes.map((c) => `<li>${esc(c)}</li>`).join("")}</ul>
    <p class="risk">${pv.risk === "seguro" ? T("riskSafe") : T("riskReview")}</p>`);
  if (!ok) return;
  const r = await job(T("working"), "apply_fix", id);
  if (!r) return;
  setAudit(r); renderDoctor(); toast(T("done"));
}
async function fixSafe() {
  const n = S.audit.findings.filter((f) => f.fix && f.fix.risk === "seguro").length;
  if (!(await confirmDlg(T("fixSafeTitle"), `<p>${T("fixSafeBody", n)}</p>`, T("fixWord")))) return;
  const r = await job(T("working"), "apply_safe");
  if (!r) return;
  setAudit(r); renderDoctor(); toast(T("fixedN", r.done.length, r.skipped.length));
}

// ------------------------------------------------------------------ mods
async function renderMods() {
  const mods = await call("mods");
  const dv = S.pack?.draft ? (await call("draft_view")).draft : null;
  const rows = dv ? dv.rows : mods.map((m) => ({ ...m, goes: true }));
  const pct = (a, b) => (b ? Math.min(100, Math.round((a / b) * 100)) : 0);
  const draftBar = dv ? `<div class="draftbar">
      <div class="db-head"><b>${dv.project ? T("pjModsTitle", esc(S.pack.name)) : T("drTitle", esc(dv.name || S.pack.name))}</b>${dv.origin?.name ? ` <span class="hint">${T("drFrom", esc(dv.origin.name))}</span>` : ""}
        ${dv.project ? `<button class="folder-link" id="m-modsdir">${T("pjModsFolder")}</button>` : ""}
        <button class="primary" id="m-create">${dv.project ? T("pjPack") : T("drCreate")}</button></div>
      <div class="db-stats">
        <div><span>${T("drGoes")}</span><b>${dv.goes} / ${dv.total}</b></div>
        <div class="${dv.ccc_limit && dv.ccc_bytes > dv.ccc_limit ? "bad" : ""}"><span>.ccc</span><b>${dv.ccc_bytes}${dv.ccc_limit ? ` / ${dv.ccc_limit}` : ""}</b>${dv.ccc_limit ? `<i style="width:${pct(dv.ccc_bytes, dv.ccc_limit)}%"></i>` : ""}</div>
        ${dv.ini_top ? `<div class="${dv.ini_top.chars > dv.ini_limit ? "bad" : ""}"><span>${T("drIniTop")}</span><b>${dv.ini_top.chars} / ${dv.ini_limit}</b><i style="width:${pct(dv.ini_top.chars, dv.ini_limit)}%"></i></div>` : ""}
        <div><span>${T("drPlugins")}</span><b>${dv.plugins}</b></div>
        <div><span>Data</span><b>${mb(dv.data_size)}</b></div>
      </div>
      <p class="hint">${dv.project ? T("pjHint") : T("drHint")}</p></div>` : "";
  $("#p-mods").innerHTML = `
    <h2>${T("nav.mods")}</h2>
    ${draftBar}
    <div id="m-beh"></div>
    <p class="sub">${T("modsSub")}</p>
    <div class="field">
      <input id="m-path" placeholder="${esc(T("modPh"))}" spellcheck="false">
      ${hasWebview() ? `<button class="ghost" id="m-folder">${T("addFolder")}</button><button class="ghost" id="m-archive">${T("addArchive")}</button>` : ""}
      <button class="primary" id="m-add">${T("addMod")}</button>
    </div>
    <div class="doctor-head"><button class="ghost" id="m-intake">${T("nav.add")}</button>${S.pack.bench ? "" : `<button class="ghost" id="m-frompack">${T("pjFromPack")}</button>`}<button class="ghost" id="m-catalog">${T("drFromCatalog")}</button><button class="ghost" id="m-conf">${T("cfGo")}</button>
      <button class="ghost" id="m-recipe">${T("rcGo")}</button>${S.state?.nexus_key ? `<button class="ghost" id="m-updates">${T("nxUpdates")}</button>` : ""}</div>
    <div id="m-extra"></div>
    <div id="m-nexus" class="hint"></div>
    <div class="ornament"></div>
    ${rows.length ? rows.map((m) => `<div class="modrow ${dv ? "with-goes" : ""} ${m.goes ? "" : "off"}">
        ${dv ? `<label class="goes" title="${esc(T("drGoesTip"))}"><input type="checkbox" data-goes="${esc(m.id)}" ${m.goes ? "checked" : ""}></label>` : ""}
        <div><div class="t"><b>${esc(m.name)}</b>${m.goes ? "" : ` <span class="pill">${T("drOut")}</span>`} <span class="nx-slot" data-slot="${esc(m.id)}"></span></div>
        <div class="files">${esc([...m.plugins, ...m.bsas].join(" · "))}${m.kind === "bsa" ? ` · ${T("fromIni")}` : ""}</div>
        <div class="mdesc">${m.desc ? esc(m.desc) : ""}<button class="link" data-desc="${esc(m.id)}">${m.desc ? T("descEdit") : T("descAdd")}</button></div></div>
        <div class="risk">${mb(m.size)}</div>
        <div class="act">${m.folder ? `<button class="folder-link" data-modfolder="${esc(m.folder)}" title="${esc(m.folder)}">${T("pjModFolder")}</button>` : ""}${m.goes && m.plugins.length ? `<button class="ghost sm" data-rename="${esc(m.plugins.join("|"))}">${T("rnGo")}</button>` : ""}${m.goes && m.bsas.length ? `<button class="ghost sm" data-extract="${esc(m.bsas.join("|"))}">${T("extract")}</button>` : ""}${m.goes ? `<button class="ghost danger" data-rm="${esc(m.id)}">${T("remove")}</button>` : ""}</div></div>`).join("") : `<p class="empty">${T("noMods")}</p>`}`;
  $("#m-folder")?.addEventListener("click", async () => { const p = await call("pick_folder"); if (p) $("#m-path").value = p; });
  $("#m-archive")?.addEventListener("click", async () => { const p = await call("pick_archive"); if (p) $("#m-path").value = p; });
  $("#m-add").addEventListener("click", async () => {
    const p = $("#m-path").value.trim(); if (!p) return toast(T("needFolder"), true);
    const r = await job(T("working"), "add_mod", p);
    if (!r) return;
    setAudit(r);
    await infoDlg(T("addedTitle"), reportHtml(r.report));
    renderMods();
  });
  $("#m-create")?.addEventListener("click", () => (dv?.project ? projectBuild() : createModpack()));
  $("#m-modsdir")?.addEventListener("click", () => openFolder(dv.project.mods));
  $$("[data-modfolder]").forEach((b) => b.addEventListener("click", () => openFolder(b.dataset.modfolder)));
  $("#m-frompack")?.addEventListener("click", pickPackSource);
  $("#m-catalog").addEventListener("click", () => { S.libTab = "catalog"; S.catBase = { edition: "AE", cc_preset: "ussep", ussep: "", ...(S.catBase || {}), into: true }; show("library"); });
  $("#m-conf").addEventListener("click", showConflicts);
  $("#m-recipe").addEventListener("click", showRecipe);
  $("#m-updates")?.addEventListener("click", showUpdates);
  $("#m-intake").addEventListener("click", () => show("add"));
  $$("[data-goes]").forEach((c) => c.addEventListener("change", () => toggleGoes(c.dataset.goes, c.checked)));
  S.modRows = Object.fromEntries(rows.map((m) => [m.id, m]));
  fillNexus($("#p-mods"), $("#m-nexus"));
  if (!S.pack.bench) renderBehaviors();
  $$("[data-rename]").forEach((b) => b.addEventListener("click", () => renameFlow(b.dataset.rename.split("|"))));
  $$("[data-desc]").forEach((b) => b.addEventListener("click", async () => {
    const id = b.dataset.desc, m = S.modRows[id];
    const nx = S.ident?.[id]?.details?.summary || "";
    const t = await askText(T("descTitle", m.title || m.name), T("descAsk"), m.desc || nx);
    if (t === null) return;
    const r = await call("mod_describe", id, t);
    if (!r.ok) return toast(r.error, true);
    renderMods();
  }));
  $$("[data-extract]").forEach((b) => b.addEventListener("click", async () => {
    const dest = hasWebview() ? await call("pick_folder") : prompt(T("extractWhere"));
    if (!dest) return;
    const r = await job(T("working"), "bsa_extract", b.dataset.extract.split("|"), dest);
    if (r) toast(T("extractDone", r.files ?? r.total ?? 0, dest));
  }));
  $$("[data-rm]").forEach((b) => b.addEventListener("click", async () => {
    if (!(await confirmDlg(T("removeTitle"), `<p>${T("removeBody", b.dataset.rm)}</p>`, T("remove")))) return;
    const r = await removeWithUsers(b.dataset.rm);
    if (!r) return;
    setAudit(r); toast(T("done")); renderMods();
  }));
}


// ------------------------------------------------------------------ the mod workshop
async function pickMods(title, multi) {
  // Library mods (converted first) plus "another folder or archive"; resolves with paths or null
  const L = await call("library_mods");
  const rows = L.rows || [];
  const html = `<p>${multi ? T("wsPickMany") : T("wsPickOne")}</p>
    <div class="field"><input id="pm-q" placeholder="${esc(T("filter"))}" spellcheck="false"></div>
    <div class="pm-list" style="max-height:340px;overflow:auto;margin-top:8px">${rows.length ? rows.map((r, i) => `<label class="pm-row" data-name="${esc(r.name.toLowerCase())}" style="display:flex;gap:8px;padding:4px 0;border-top:1px solid var(--rule)">
      <input type="${multi ? "checkbox" : "radio"}" name="pm" value="${i}"> <span><b>${esc(r.name)}</b> ${r.converted ? `<span class="pill p-conv">${T("libConverted")}</span>` : ""}<br><small class="hint">${esc(r.path)}</small></span></label>`).join("") : `<p class="hint">${T("wsNoLibMods")}</p>`}</div>
    <p style="margin-top:10px"><button class="ghost sm" id="pm-other">${T("wsOther")}</button> <span class="hint" id="pm-extra"></span></p>`;
  const extra = [];
  const pending = confirmDlg(title, html, T("wsGo"));
  $("#pm-q").addEventListener("input", (e) => { const q = e.target.value.toLowerCase(); $$(".pm-row").forEach((r) => (r.hidden = q && !r.dataset.name.includes(q))); });
  $("#pm-other").addEventListener("click", async () => {
    let p = null;
    if (hasWebview()) { p = await call("pick_folder"); if (!p) p = await call("pick_archive"); } else p = prompt(T("wsOtherAsk"));
    if (p) { extra.push(p); $("#pm-extra").textContent = extra.map(baseName).join(" · "); }
  });
  if (!(await pending)) return null;
  const picked = $$('#dlg-body input[name="pm"]:checked').map((c) => rows[+c.value].path);
  const out = [...picked, ...extra];
  return out.length ? out : null;
}
async function startWorkshop(kind) {
  let sources = [], name = "", edition = "AE";
  const batch = kind === "batch";
  if (batch) kind = "convert";
  if (kind === "convert") {
    const ed = await choiceDlg(T(batch ? "wsBatch" : "wsConvert"), `<p>${T("wsEdAsk")}</p>`, [{ id: "AE", label: "AE (Anniversary)", primary: true }, { id: "SE", label: "SE" }]);
    if (!ed) return;
    edition = ed; name = T(batch ? "wsBatchName" : "wsConvertName");
  } else {
    const multi = kind !== "edit";
    const got = await pickMods(T(kind === "edit" ? "wsEdit" : kind === "suite" ? "wsSuite" : "wsMerge"), multi);
    if (!got) return;
    if (multi && got.length < 2) return toast(T("wsNeedTwo"), true);
    sources = got;
    name = kind === "edit" ? baseName(got[0]).replace(/\.(zip|7z)$/i, "") : "";
    if (multi) {
      const nm = await askText(T(kind === "suite" ? "wsSuite" : "wsMerge"), T("wsSuiteName"), kind === "suite" ? "Suite" : "Merge");
      if (nm === null) return;
      name = nm || (kind === "suite" ? "Suite" : "Merge");
    }
  }
  const r = await job(T("wsPreparing"), "workshop_new", kind, name, edition, sources);
  if (!r) return;
  S.firstCrit = null; packChanged(); setAudit(r);
  const bad = (r.reports || []).filter((x) => !x.ok);
  if (bad.length) await infoDlg(T("wsSomeOut"), `<ul class="report">${bad.map((x) => `<li><b>${esc(baseName(x.source))}</b>: ${esc(pick2(x.text))}</li>`).join("")}</ul><p class="hint">${T("wsPcHint")}</p>`);
  S.convMode = batch ? "batch" : "one";
  show(kind === "convert" ? "convertir" : kind === "suite" ? "juntar" : kind === "merge" ? "fusionar" : "mesa");
}
function askText(title, label, value) {
  const pending = confirmDlg(title, `<div class="open-row"><label for="ask-in">${label}</label><div class="field"><input id="ask-in" value="${esc(value || "")}" spellcheck="false"></div></div>`, T("ok"));
  const i = $("#ask-in"); i.focus(); i.select();
  return pending.then((ok) => (ok ? $("#ask-in").value.trim() : null));
}
async function renderTallerHome() {
  const el = $("#p-taller");
  const L = await call("workshop_list");
  el.innerHTML = `${homeBtn()}<h2>${T("spcWs")}</h2><p class="sub">${T("wsSub")}</p>
    <div class="doctor-head">
      <button class="primary" data-ws="convert">${T("wsConvert")}</button><button class="ghost" data-ws="edit">${T("wsEdit")}</button>
      <button class="ghost" data-ws="suite">${T("wsSuite")}</button><button class="ghost" data-ws="merge">${T("wsMerge")}</button>
      <button class="folder-link" id="tw-dir">${T("openFolder")}</button></div>
    <h3>${T("wsBenchesTitle")} <small>${L.benches.length}</small></h3>
    <div class="bench-list">${L.benches.length ? L.benches.map((b) => `<div class="row"><div><b>${esc(b.name)}</b> <span class="pill">${esc(T("wsKind_" + b.kind))}</span>
        <div class="hint">${b.files} ${T("wsFiles")} · ${esc(b.when)}${b.edit_of ? ` · ${T("wsEditOf", esc(baseName(b.edit_of)))}` : ""}</div></div>
        <div class="act"><button class="primary sm" data-bench="${esc(b.path)}">${T("libOpen")}</button><button class="folder-link" data-dir="${esc(b.path)}">${T("openFolder")}</button></div></div>`).join("")
      : `<p class="empty">${T("wsNoBenches")}</p>`}</div>`;
  wireHome(el);
  $$("[data-ws]", el).forEach((b) => b.addEventListener("click", () => startWorkshop(b.dataset.ws)));
  $("#tw-dir").addEventListener("click", () => openFolder(L.root));
  $$("[data-dir]", el).forEach((b) => b.addEventListener("click", () => openFolder(b.dataset.dir)));
  $$("[data-bench]", el).forEach((b) => b.addEventListener("click", async () => {
    const r = await job(T("reading"), "workshop_open", b.dataset.bench);
    if (!r) return;
    S.firstCrit = null; packChanged(); setAudit(r); show("mesa");
  }));
}
async function renderMesa() {
  const el = $("#p-mesa");
  const v = await call("workshop_view");
  if (!v.ok) { el.innerHTML = `<h2>${T("ws.bench")}</h2><p class="empty">${esc(v.error)}</p>`; return; }
  const I = v.info || {};
  el.innerHTML = `<h2>${esc(I.name || "")}</h2>
    <p class="sub">${T("wsKindP_" + (I.kind || "edit"))}</p>
    <div class="doctor-head">
      <button class="ghost" id="ms-bring">${T("wsBring")}</button>
      <button class="ghost" id="ms-convert">${T("wsConvertHere")}</button>
      <button class="ghost" id="ms-xedit">${T("xeOpen")}</button>
      <button class="folder-link" id="ms-dir">${T("openFolder")}</button></div>
    <div class="ornament"></div>
    <div id="ms-nexus" class="hint"></div>
    ${v.rows.length ? v.rows.map((m) => `<div class="modrow"><div><div class="t"><b>${esc(m.name)}</b> <span class="nx-slot" data-slot="${esc(m.id)}"></span></div>
        <div class="files">${esc([...m.plugins, ...m.bsas].join(" · "))}${m.kind === "bsa" ? ` · ${T("fromIni")}` : ""}</div></div>
        <div class="risk">${mb(m.size)}</div>
        <div class="act">${m.plugins.length ? `<button class="ghost sm" data-rename="${esc(m.plugins.join("|"))}">${T("rnGo")}</button>` : ""}${m.bsas.length ? `<button class="ghost sm" data-extract="${esc(m.bsas.join("|"))}">${T("extract")}</button>` : ""}<button class="ghost danger" data-rm="${esc(m.id)}">${T("remove")}</button></div></div>`).join("")
      : `<p class="empty">${T("wsEmpty")}</p>`}
    ${v.loose.length ? `<p class="note warn">${T("wsLoose", esc(v.loose.join(", ")))}</p>` : ""}
    <div class="ornament"></div>
    <div class="doctor-head">
      ${v.bsas.length >= 2 && !(I.joined && v.bsas.every((b) => I.joined.into.includes(b))) ? `<button class="ghost" id="ms-join">${T("ws.join")} (${v.bsas.length} BSA)</button>` : ""}
      ${v.plugins.length >= 2 ? `<button class="ghost" id="ms-merge">${T("ws.merge")} (${v.plugins.length})</button>` : ""}
    </div>
    <h3>${T("wsSaveTitle")}</h3>
    <p class="hint">${T("wsSaveP")}</p>
    <div class="field"><input id="ms-name" value="${esc(I.name || "")}" spellcheck="false">
      <button class="primary" id="ms-save" ${v.rows.length ? "" : "disabled"}>${T("wsSave")}</button></div>
    ${I.edit_of ? `<p><label><input type="checkbox" id="ms-replace"> ${T("wsReplace", esc(baseName(I.edit_of)))}</label></p>` : ""}
    <p style="margin-top:24px"><button class="link danger" id="ms-discard">${T("wsDiscard")}</button></p>`;
  $("#ms-dir").addEventListener("click", () => openFolder(v.data));
  S.modRows = Object.fromEntries(v.rows.map((m) => [m.id, m]));
  fillNexus(el, $("#ms-nexus"));
  $("#ms-convert").addEventListener("click", () => show("convertir"));
  $("#ms-xedit").addEventListener("click", openInXedit);
  $("#ms-join")?.addEventListener("click", () => show("juntar"));
  $("#ms-merge")?.addEventListener("click", () => show("fusionar"));
  $("#ms-bring").addEventListener("click", async () => {
    const got = await pickMods(T("wsBring"), true);
    if (!got) return;
    const r = await job(T("working"), "workshop_bring", got);
    if (!r) return;
    setAudit(r);
    const bad = (r.reports || []).filter((x) => !x.ok);
    if (bad.length) await infoDlg(T("wsSomeOut"), `<ul class="report">${bad.map((x) => `<li><b>${esc(baseName(x.source))}</b>: ${esc(pick2(x.text))}</li>`).join("")}</ul><p class="hint">${T("wsPcHint")}</p>`);
    renderMesa();
  });
  $$("[data-rename]", el).forEach((b) => b.addEventListener("click", async () => { await renameFlow(b.dataset.rename.split("|")); renderMesa(); }));
  $$("[data-extract]", el).forEach((b) => b.addEventListener("click", async () => {
    const dest = hasWebview() ? await call("pick_folder") : prompt(T("extractWhere"));
    if (!dest) return;
    const r = await job(T("working"), "bsa_extract", b.dataset.extract.split("|"), dest);
    if (r) toast(T("extractDone", r.files ?? r.total ?? 0, dest));
  }));
  $$("[data-rm]", el).forEach((b) => b.addEventListener("click", async () => {
    if (!(await confirmDlg(T("removeTitle"), `<p>${T("removeBody", b.dataset.rm)}</p>`, T("remove")))) return;
    const r = await removeWithUsers(b.dataset.rm);
    if (!r) return;
    setAudit(r); renderMesa();
  }));
  $("#ms-save").addEventListener("click", async () => {
    const name = $("#ms-name").value.trim();
    const r = await job(T("wsSaving"), "workshop_save", name, !!$("#ms-replace")?.checked);
    if (!r) return;
    const o = r.saved;
    const c = await choiceDlg(T("wsSaved"), `<p>${T("wsSavedP", esc(o.dest))}</p><ul class="report"><li>${esc([...o.plugins, ...o.bsas].join(" · "))}</li><li>${mb(o.size)}</li></ul>
      ${o.loose_left.length ? `<p class="note warn">${T("wsLooseLeft", esc(o.loose_left.join(", ")))}</p>` : ""}`, [
      { id: "folder", label: T("openFolder") }, { id: "keep", label: T("wsKeepBench"), primary: true }, { id: "done", label: T("wsDoneBench") }]);
    if (c === "folder") openFolder(o.dest);
    if (c === "done") { const d = await call("workshop_discard"); if (d.ok) { S.pack = null; S.audit = null; show("taller"); } }
  });
  $("#ms-discard").addEventListener("click", async () => {
    if (!(await confirmDlg(T("wsDiscard"), `<p>${T("wsDiscardP")}</p>`, T("wsDiscard")))) return;
    const d = await call("workshop_discard");
    if (!d.ok) return toast(d.error, true);
    S.pack = null; S.audit = null; show("taller");
  });
}
async function renderJuntar() {
  const el = $("#p-juntar");
  const v = await call("workshop_view");
  if (!v.ok) { el.innerHTML = `<h2>${T("ws.join")}</h2><p class="empty">${esc(v.error)}</p>`; return; }
  const J = v.join;
  const anchor = S.joinAnchor ?? (J ? J.anchor : null);
  let plan = J;
  if (J && anchor !== J.anchor) { const r = await call("workshop_join_plan", anchor || ""); if (r.ok) plan = r.plan; }
  const res = plan ? (plan.anchor ? plan.result : [(v.info.name || "Suite") + "M.bsa", (v.info.name || "Suite") + "T.bsa"]) : [];
  el.innerHTML = `<h2>${T("ws.join")}</h2><p class="sub">${T("wsJoinSub")}</p>
    ${!plan ? `<p class="empty">${T("wsJoinNeed")}</p>${v.join_error ? `<p class="note warn">${esc(v.join_error)}</p>` : ""}` : `
    <ol class="steps-ws">
      <li><b>${T("wsJoinOrder")}</b><p class="hint">${T("wsJoinOrderP")}</p><ul class="report">${plan.order.map((b) => `<li>${esc(b)}</li>`).join("")}</ul></li>
      <li><b>${T("wsJoinAnchor")}</b><p class="hint">${T("wsJoinAnchorP")}</p>
        <select id="jn-anchor">${v.plugins.map((p) => `<option value="${esc(p)}" ${p === plan.anchor ? "selected" : ""}>${esc(p)}</option>`).join("")}<option value="" ${plan.anchor ? "" : "selected"}>${T("wsJoinIni")}</option></select>
        <p>${T("wsJoinResult")}: <b>${esc(res.join(", "))}</b> · ${plan.files} ${T("wsFiles")} · ${mb(plan.size)}</p></li>
      <li><b>${T("wsJoinOverlaps", plan.n_overlaps ?? plan.overlaps.length)}</b>
        ${plan.overlaps.length ? `<div class="overlaps"><ul class="report">${plan.overlaps.map((o) => `<li>${esc(o.path)}: ${T("wsWins", esc(o.wins))}</li>`).join("")}</ul></div>` : `<p class="hint">${T("wsNoOverlaps")}</p>`}</li>
    </ol>
    ${v.info.merged ? `<p class="hint">${T("wsJoinRetarget", esc(v.info.merged.plugin))}</p>` : ""}
    <p class="hint">${T("wsJoinNote")}</p>
    <div class="cv-actions"><button class="primary" id="jn-go">${T("ws.join")}</button> <button class="link" id="jn-back">${T("wsBack")}</button></div>`}`;
  $("#jn-anchor")?.addEventListener("change", (e) => { S.joinAnchor = e.target.value; renderJuntar(); });
  $("#jn-back")?.addEventListener("click", () => show("mesa"));
  $("#jn-go")?.addEventListener("click", async () => {
    const r = await job(T("wsJoining"), "workshop_join", anchor || "", v.info.name || "");
    if (!r) return;
    setAudit(r); S.joinAnchor = undefined;
    await infoDlg(T("ws.join"), `<p>${T("wsJoined", r.join.from.length, esc(r.join.into.join(", ")))}</p><p class="hint">${T("wsUndoHint")}</p>`);
    show("mesa");
  });
}
async function renderFusionar() {
  const el = $("#p-fusionar");
  const v = await call("workshop_view");
  if (!v.ok) { el.innerHTML = `<h2>${T("ws.merge")}</h2><p class="empty">${esc(v.error)}</p>`; return; }
  const M = v.info.merged;
  const zed = S.zedit;
  el.innerHTML = `<h2>${T("ws.merge")}</h2><p class="sub">${T("wsMergeSub")}</p>
    <ol class="steps-ws">
      <li class="${v.plugins.length >= 2 || M ? "done" : ""}"><b>${T("wsM1")}</b><p class="hint">${M ? T("wsM1done", esc(M.plugin)) : T("wsM1p", v.plugins.length)}</p>
        ${!M ? `<button class="ghost sm" id="mg-bring">${T("wsBring")}</button>` : ""}</li>
      <li class="${zed || M ? "done" : ""}"><b>${T("wsM2")}</b><p class="hint">${T("wsM2p")}</p>
        ${!M ? `<button class="primary sm" id="mg-zedit" ${v.plugins.length >= 2 ? "" : "disabled"}>${T("wsM2go")}</button>` : ""}
        ${zed ? `<div class="note"><p>${T("wsM2folder")} <b>${esc(zed.workspace)}</b> <button class="folder-link" data-dir="${esc(zed.workspace)}">${T("openFolder")}</button></p>
          <ol class="report"><li>${T("wsZ1")}</li><li>${T("wsZ2")}</li><li>${T("wsZ3")}</li><li>${T("wsZ4")}</li></ol>
          ${zed.zedit ? "" : `<p class="note warn">${T("wsNoZedit")}</p>`}</div>` : ""}</li>
      <li class="${M ? "done" : ""}"><b>${T("wsM3")}</b><p class="hint">${T("wsM3p")}</p>
        ${M ? `<ul class="report"><li>${T("wsM3in", esc(M.inside.join(", ")))}</li>${M.extras.length ? `<li>${T("wsM3extra", esc(M.extras.join(", ")))}</li>` : ""}${(M.components || []).filter((c) => !M.inside.map((x) => x.toLowerCase()).includes(c.toLowerCase())).length ? `<li class="warn">${T("wsM3missing", esc(M.components.filter((c) => !M.inside.map((x) => x.toLowerCase()).includes(c.toLowerCase())).join(", ")))}</li>` : ""}</ul>`
          : `<div class="field"><input id="mg-folder" placeholder="${esc(T("wsM3ph"))}" spellcheck="false">${hasWebview() ? `<button class="ghost sm" id="mg-browse">${T("browse")}</button>` : ""}<button class="primary sm" id="mg-take">${T("wsM3go")}</button></div>`}</li>
      <li class="${M && v.bsas.length <= 2 ? "done" : ""}"><b>${T("wsM4")}</b><p class="hint">${T("wsM4p")}</p>
        ${M ? `<button class="ghost sm" id="mg-join">${T("ws.join")}</button>` : ""}</li>
      <li><b>${T("wsM5")}</b><p class="hint">${T("wsM5p")}</p>${M ? `<button class="ghost sm" id="mg-save">${T("wsSaveTitle")}</button>` : ""}</li>
    </ol>`;
  $$("[data-dir]", el).forEach((b) => b.addEventListener("click", () => openFolder(b.dataset.dir)));
  $("#mg-bring")?.addEventListener("click", () => show("mesa"));
  $("#mg-join")?.addEventListener("click", () => show("juntar"));
  $("#mg-save")?.addEventListener("click", () => show("mesa"));
  $("#mg-zedit")?.addEventListener("click", async () => {
    const r = await job(T("wsPreparing"), "workshop_zedit");
    if (!r) return;
    S.zedit = r; renderFusionar();
  });
  $("#mg-browse")?.addEventListener("click", async () => { const p = await call("pick_folder"); if (p) $("#mg-folder").value = p; });
  $("#mg-take")?.addEventListener("click", async () => {
    const f = $("#mg-folder").value.trim(); if (!f) return toast(T("needFolder"), true);
    const r = await call("workshop_bring_merge", f);
    if (!r.ok) return toast(r.error, true);
    setAudit(r); S.zedit = null; renderFusionar();
  });
}


// ------------------------------------------------------------------ which mod is it (Nexus)
const NX_LABEL = { confirmed: "nxConfirmed", known: "nxKnown", likely: "nxLikely", merge: "nxMerge" };
async function fillNexus(root, bar) {
  const r = await call("identify_mods");
  if (!r.ok) return;
  S.ident = Object.fromEntries(r.rows.map((x) => [x.id, x.ident]));
  S.identMeta = r;
  $$(".nx-slot", root).forEach((slot) => {
    const id = slot.dataset.slot, d = S.ident[id];
    if (!d) return;
    const label = d.details?.name ? esc(d.details.name) : d.title ? esc(d.title) : d.mod_id ? `Nexus #${d.mod_id}` : "";
    slot.innerHTML = d.url
      ? `<button class="nx-chip s-${d.status}" data-nx-open="${esc(d.url)}" title="${esc(T(NX_LABEL[d.status] || "nxLikely"))}">${label} ↗</button><button class="nx-who" data-nx-who="${esc(id)}" title="${esc(T("nxWhoTip"))}">?</button>`
      : `<button class="nx-chip s-unknown" data-nx-who="${esc(id)}">${d.status === "merge" ? T("nxMergeChip") : T("nxWhich")}</button>`;
  });
  $$("[data-nx-open]", root).forEach((b) => b.addEventListener("click", () => call("open_url", b.dataset.nxOpen)));
  $$("[data-nx-who]", root).forEach((b) => b.addEventListener("click", () => identWho(b.dataset.nxWho, root, bar)));
  const ids = r.rows.map((x) => x.ident).filter((d) => d.mod_id && !d.details).map((d) => d.mod_id);
  const known = r.rows.filter((x) => x.ident.mod_id).length;
  if (bar) bar.innerHTML = `${T("nxSummary", known, r.rows.length)}
    ${!r.masterlist ? ` · <button class="link" id="nx-ml">${T("nxGetMl")}</button>` : ""}
    ${r.nexus_key && ids.length ? ` · <button class="link" id="nx-names">${T("nxGetNames", ids.length)}</button>` : ""}
    ${r.nexus_key && known ? ` · <button class="link" id="nx-compat">${T("cpBtn")}</button>` : ""}`;
  $("#nx-compat")?.addEventListener("click", () => compatFlow(null, root, bar));
  $("#nx-ml")?.addEventListener("click", async () => { if (await job(T("working"), "loot_download")) fillNexus(root, bar); });
  $("#nx-names")?.addEventListener("click", async () => {
    const x = await job(T("nxFetching"), "identify_details", [...new Set(ids)]);
    if (x?.errors?.length) toast(x.errors[0], true);
    fillNexus(root, bar);
  });
}
async function identWho(id, root, bar) {
  const d = S.ident?.[id], m = S.modRows?.[id];
  if (!d || !m) return;
  const plugin = m.plugins?.[0];
  const st = d.mod_id ? T(NX_LABEL[d.status] || "nxLikely") : d.status === "merge" ? T("nxIsMerge") : T("nxUnknown");
  const html = `<p><b>${st}</b>${d.matched && d.how === "loot" && d.matched.toLowerCase() !== String(plugin || "").toLowerCase() ? ` · ${T("nxVia", esc(d.matched))}` : ""}</p>
    ${d.url ? `<p><button class="primary sm" data-open="${esc(d.url)}">${d.details?.name ? esc(d.details.name) : d.title ? esc(d.title) : "Nexus #" + d.mod_id} ↗</button>${d.details?.version ? ` <span class="hint">v${esc(d.details.version)}${d.details.author ? " · " + esc(d.details.author) : ""}</span>` : ""}</p>` : ""}
    ${d.originals?.length ? `<p class="hint">${T("nxOriginal", esc(d.originals.join(", ")))}</p>` : ""}
    ${d.candidates?.length ? `<h4>${T("nxOthers")}</h4><ul class="report">${d.candidates.map((c) => `<li><button class="link" data-open="${esc(c.url)}">${c.title ? esc(c.title) : "Nexus #" + c.mod_id} ↗</button> <span class="hint">(${esc(c.via)})</span> ${plugin ? `<button class="ghost sm" data-pick="${c.mod_id}">${T("nxThisOne")}</button>` : ""}</li>`).join("")}</ul>` : ""}
    ${d.merge?.length ? `<h4>${T("nxInside")}</h4><ul class="report">${d.merge.map((c) => `<li>${esc(c.plugin)} ${c.url ? `<button class="link" data-open="${esc(c.url)}">Nexus #${c.mod_id} ↗</button>` : `<button class="link" data-open="${esc(c.search)}">${T("nxSearch")} ↗</button>`}</li>`).join("")}</ul>` : ""}
    ${d.hints?.author || d.hints?.description ? `<p class="hint">${d.hints.author ? `${T("nxAuthor")}: ${esc(d.hints.author)}` : ""}${d.hints.description ? `<br>${esc(d.hints.description)}` : ""}</p>` : ""}
    <div class="open-row"><label>${T("nxSearchLabel")}</label><div class="field"><input id="nx-q" value="${esc(d.query || "")}" spellcheck="false"><button class="ghost" id="nx-go">${T("nxSearch")} ↗</button></div></div>
    ${plugin ? `<div class="open-row"><label>${T("nxPasteLink")}</label><div class="field"><input id="nx-in" placeholder="https://www.nexusmods.com/skyrimspecialedition/mods/…" spellcheck="false"><button class="primary" id="nx-save">${T("save")}</button></div>
      <p class="hint">${T("nxPasteHint")}</p></div>` : ""}
    ${d.status === "confirmed" ? `<p><button class="link danger" id="nx-forget">${T("nxForgetMine")}</button></p>` : ""}
    ${d.mod_id && !d.details && S.identMeta?.nexus_key ? `<p><button class="link" id="nx-det">${T("nxDetails")}</button></p>` : ""}
    ${d.mod_id && S.identMeta?.nexus_key ? `<p><button class="link" id="nx-cp">${T("cpOne")}</button></p>` : ""}`;
  const pending = infoDlg(m.name, html);
  const body = $("#dlg-body");
  $$("[data-open]", body).forEach((b) => b.addEventListener("click", () => call("open_url", b.dataset.open)));
  $("#nx-go").addEventListener("click", () => call("open_url", "https://www.nexusmods.com/games/skyrimspecialedition/search?keyword=" + encodeURIComponent($("#nx-q").value.trim())));
  const save = async (text) => {
    const r = await call("identify_set", plugin, text);
    if (!r.ok) return toast(r.error, true);
    $("#dlg").close();
    if (r.mod_id && S.identMeta?.nexus_key) await job(T("nxFetching"), "identify_details", [r.mod_id]);
    toast(r.mod_id ? T("nxSaved", r.mod_id) : T("nxForgot"));
    fillNexus(root, bar);
  };
  $("#nx-save")?.addEventListener("click", () => save($("#nx-in").value));
  $$("[data-pick]", body).forEach((b) => b.addEventListener("click", () => save(b.dataset.pick)));
  $("#nx-forget")?.addEventListener("click", () => save(""));
  $("#nx-det")?.addEventListener("click", async () => { $("#dlg").close(); await job(T("nxFetching"), "identify_details", [d.mod_id]); fillNexus(root, bar); });
  $("#nx-cp")?.addEventListener("click", async () => { $("#dlg").close(); await pending; compatFlow([id], root, bar); });
  await pending;
}
// a small chip for mods outside the open pack (queue, catalog)
function nxChipLite(d) {
  if (!d) return "";
  if (d.url) return `<button class="nx-chip s-${esc(d.status)}" data-nx-open="${esc(d.url)}" title="${esc(T(NX_LABEL[d.status] || "nxLikely"))}">${d.title ? esc(d.title) : "Nexus #" + d.mod_id} ↗</button>`;
  return d.search ? `<button class="nx-chip s-unknown" data-nx-open="${esc(d.search)}" title="${esc(T("nxSearch"))}">${d.merge ? T("nxMergeChip") : T("nxSearch")} ↗</button>` : "";
}
function wireNxOpen(root) { $$("[data-nx-open]", root).forEach((b) => { if (b._nx) return; b._nx = 1; b.addEventListener("click", (e) => { e.stopPropagation(); e.preventDefault(); call("open_url", b.dataset.nxOpen); }); }); }
async function fillQueueNexus(el) {
  const items = S.queue.map((q, i) => ({ key: String(i), plugins: (q.det?.evidence?.plugins || []).slice(0, 6), q }))
    .filter((x) => !x.q.nexus && x.plugins.length && x.q.det?.kind !== "modpack");
  if (!items.length) return;
  const r = await call("identify_lookup", items.map(({ key, plugins }) => ({ key, plugins })));
  if (!r?.ok) return;
  items.forEach((x) => { const slot = $(`.nx-slot[data-q-slot="${x.key}"]`, el); if (slot) slot.innerHTML = nxChipLite(r.rows[x.key]); });
  wireNxOpen(el);
}
async function catalogIdent() {
  if (S.catIdent || !S.cat) return;
  const items = S.cat.entries.map((e) => ({ key: e.key, plugins: e.versions[0].plugins, hashes: e.versions[0].hashes,
    more_hashes: e.versions.slice(1).map((v) => v.hashes) })).filter((x) => x.plugins?.length);
  const r = await call("identify_lookup", items);
  S.catIdent = r?.ok ? r.rows : {};
}

// which Nexus version works on Switch
function cpPill(v) { return `<span class="cp-v v-${esc(v)}">${esc(T("cpV")[v] || v)}</span>`; }
function cpLine(label, row, extra = "") {
  if (!row) return "";
  return `<div class="cp-line"><span class="cp-k">${label}</span> <b>${esc(row.version ? "v" + row.version : row.name || "#" + row.file_id)}</b>
    <span class="hint">${esc(row.uploaded ? String(row.uploaded).slice(0, 10) : "")}</span> ${cpPill(row.verdict)} ${extra}
    ${row.reasons?.length ? `<div class="hint cp-why">${row.reasons.map(esc).join("<br>")}</div>` : ""}</div>`;
}
async function compatFlow(ids, root, bar) {
  const r = await job(T("nxFetching"), "nexus_compat", ids);
  if (!r) return;
  if (!r.mods.length) { await infoDlg(T("cpTitle"), `<p>${T("cpNone")}</p>${r.errors.length ? `<p class="hint">${r.errors.map(esc).join("<br>")}</p>` : ""}`); return; }
  const html = `<p class="hint">${T("cpIntro")}</p>
    ${r.skipped && !ids ? `<p class="hint">${T("cpSkipped", r.skipped)}</p>` : ""}
    ${r.errors.length ? `<p class="bad">${r.errors.map(esc).join("<br>")}</p>` : ""}
    ${r.mods.map((m, i) => `<section class="cp-mod s-${esc(m.status)}">
      <h4>${esc(m.title || m.name)} <button class="nx-chip s-known" data-open="${esc(m.url)}">Nexus #${m.mod_id} ↗</button></h4>
      <p class="cp-status">${esc(T("cpS")[m.status] || m.status)}</p>
      ${cpLine(T("cpYou"), m.have)}
      ${(() => { const same = (a, b) => a && b && a.file_id === b.file_id;
        return (m.latest && !same(m.latest, m.have) && !same(m.latest, m.best) ? cpLine(T("cpLatest"), m.latest) : "")
          + (m.best && !same(m.best, m.have) ? cpLine(T("cpBest"), m.best, `<button class="primary sm" data-open="${esc(m.best.page)}">${T("cpOpenFile")} ↗</button>${m.best.verdict === "unknown" ? ` <span class="hint">(${T("cpUnverified")})</span>` : ""}`) : ""); })()}
      <details><summary>${T("cpAll")} (${m.rows.length})</summary><ul class="report cp-rows">${m.rows.map((x) => `<li>
        <b>${esc(x.version ? "v" + x.version : x.name)}</b> <span class="hint">${esc(x.category)} · ${esc(String(x.uploaded || "").slice(0, 10))}</span> ${cpPill(x.verdict)}
        <button class="link" data-open="${esc(x.page)}">↗</button>
        ${m.plugin && (!m.have || m.have.file_id !== x.file_id) ? `<button class="ghost sm" data-have="${i}|${x.file_id}|${esc(x.version || "")}">${T("cpHave")}</button>` : ""}
        ${x.reasons?.length ? `<div class="hint cp-why">${x.reasons.map(esc).join("<br>")}</div>` : ""}</li>`).join("")}</ul></details>
    </section>`).join("")}`;
  const pending = infoDlg(T("cpTitle"), html);
  const body = $("#dlg-body");
  $$("[data-open]", body).forEach((b) => b.addEventListener("click", () => call("open_url", b.dataset.open)));
  $$("[data-have]", body).forEach((b) => b.addEventListener("click", async () => {
    const [i, fid, ver] = b.dataset.have.split("|"), m = r.mods[+i];
    const x = await call("identify_installed", m.plugin, m.mod_id, +fid, ver || null);
    if (!x.ok) return toast(x.error, true);
    toast(T("cpHaveSaved"));
    $("#dlg").close(); await pending;
    if (root) fillNexus(root, bar);
    compatFlow(ids || [m.id], root, bar);
  }));
  await pending;
}

// ------------------------------------------------------------------ the pack being created
async function toggleGoes(id, goes) {
  let r = await call("draft_toggle", id, goes, false);
  if (goes && !r.ok && r.parked?.length) {
    // its masters are marked as not going: offer to bring them back too
    if (!(await confirmDlg(T("drInTitle"), `<p>${T("drNeeds", esc(id), esc(r.needs.join(", ")))}</p>`, T("drInToo")))) return renderMods();
    const done = new Set();
    const back = async (rid) => {
      if (done.has(rid)) return true;
      done.add(rid);
      const q = await call("draft_toggle", rid, true, false);
      if (q.ok) return true;
      if (q.parked?.length) { for (const x of q.parked) if (!(await back(x))) return false; return (await call("draft_toggle", rid, true, false)).ok; }
      toast(q.error || rid, true); return false;
    };
    for (const x of r.parked) await back(x);
    r = await call("draft_toggle", id, goes, false);
  }
  if (!r.ok && r.users?.length) {
    // its plugins are masters of others that still go: offer to take those out too
    if (!(await confirmDlg(T("drOutTitle"), `<p>${T("drUsers", esc(id), esc(r.users.join(", ")))}</p>`, T("drOutToo")))) return renderMods();
    const done = new Set();
    const out = async (name) => {
      if (done.has(name)) return true;
      done.add(name);
      const q = await call("draft_toggle", name, false, false);
      if (q.ok) return true;
      if (q.users?.length) { for (const u of q.users) if (!(await out(u))) return false; return (await call("draft_toggle", name, false, false)).ok; }
      toast(q.error || name, true); return false;
    };
    for (const u of r.users) await out(u);
    r = await call("draft_toggle", id, goes, false);
  }
  if (!r.ok) { toast(r.error || T("drCant"), true); return renderMods(); }
  setAudit(r);
  if (r.missing?.length) toast(T("drMissing", r.missing.join(", ")), true);
  renderMods();
}
async function renameFlow(plugins) {
  let name = plugins[0];
  if (plugins.length > 1) {
    name = await choiceDlg(T("rnTitle"), `<p>${T("rnWhich")}</p>`, plugins.map((p) => ({ id: p, label: p })));
    if (!name) return;
  }
  const stem = name.replace(/\.(esp|esm|esl)$/i, "");
  const html = `<p>${T("rnBody", esc(name))}</p>
    <div class="field"><input id="rn-new" value="${esc(stem)}" spellcheck="false"><span class="hint" style="align-self:center">${esc(name.slice(stem.length))}</span></div>
    <div id="rn-pv" class="hint"></div>`;
  const pending = confirmDlg(T("rnTitle"), html, T("rnGo"));
  const inp = $("#rn-new"); inp.focus(); inp.select();
  let seq = 0;
  const preview = async () => {
    const my = ++seq;
    const v = inp.value.trim();
    if (!v || v === stem) { $("#rn-pv").innerHTML = ""; return; }
    const pv = await call("rename_preview", name, v);
    if (my !== seq || !pv.ok) return;
    const P = pv.plan;
    const li = [
      `${esc(name)} → <b>${esc(pv.new)}</b>`,
      ...P.bsas.map(([a, b]) => `${esc(a)} → ${esc(b)}`),
      P.patch.length ? T("rnPatch", esc(P.patch.join(", "))) : "",
      P.dependents.length ? T("rnDeps", esc(P.dependents.join(", "))) : "",
      P.list ? T("rnList", (pv.ccc_delta > 0 ? "+" : "") + pv.ccc_delta, pv.ccc_bytes + (pv.ccc_limit ? " / " + pv.ccc_limit : "")) : "",
      P.inis.length ? T("rnInis", esc(P.inis.join(", "))) : "",
    ].filter(Boolean);
    $("#rn-pv").innerHTML = `<ul class="report">${li.map((x) => `<li>${x}</li>`).join("")}</ul>
      ${pv.problems.map((p) => `<p class="note warn">${esc(pick2(p))}</p>`).join("")}
      ${pv.safe !== pv.new ? `<p><button class="link" id="rn-safe">${T("rnUseSafe", esc(pv.safe))}</button></p>` : ""}`;
    $("#rn-safe")?.addEventListener("click", () => { inp.value = pv.safe.replace(/\.(esp|esm|esl)$/i, ""); preview(); });
  };
  let t = null;
  inp.addEventListener("input", () => { clearTimeout(t); t = setTimeout(preview, 250); });
  if (!(await pending)) return;
  const v = inp.value.trim();
  if (!v || v === stem) return;
  const r = await call("rename_plugin", name, v);
  if (!r.ok) return toast(r.error, true);
  setAudit(r); toast(T("rnDone", r.new)); renderMods();
}
async function createModpack() {
  const dv = (await call("draft_view")).draft;
  if (!dv) return;
  const html = `<p>${T("drCreateBody", dv.goes, dv.total)}</p>
    <div class="open-row"><label for="cm-name">${T("drName")}</label><div class="field"><input id="cm-name" value="${esc(dv.name || "")}" spellcheck="false"></div></div>
    <div class="open-row"><label for="cm-dest">${T("drWhere")}</label><div class="field"><input id="cm-dest" placeholder="${esc(T("drWherePh"))}" spellcheck="false">${hasWebview() ? `<button class="ghost" id="cm-browse">${T("browse")}</button>` : ""}</div></div>
    ${dv.ccc_limit && dv.ccc_bytes > dv.ccc_limit ? `<p class="note warn">${T("drOverCcc", dv.ccc_bytes, dv.ccc_limit)}</p>` : ""}
    ${dv.ini_top && dv.ini_top.chars > dv.ini_limit ? `<p class="note warn">${T("drOverIni", dv.ini_top.chars, dv.ini_limit)}</p>` : ""}`;
  const pending = confirmDlg(T("drCreate"), html, T("drCreate"));
  $("#cm-browse")?.addEventListener("click", async () => { const p = await call("pick_folder"); if (p) $("#cm-dest").value = p + "\\" + ($("#cm-name").value.trim() || "Modpack"); });
  if (!(await pending)) return;
  const name = $("#cm-name").value.trim(), dest = $("#cm-dest").value.trim();
  const r = await job(T("drCreating"), "draft_create", name, dest);
  if (!r) return;
  const c = r.created;
  const pick = await choiceDlg(T("drDone"), `<p>${T("drDoneBody", esc(c.dest))}</p>
    <ul class="report"><li>${T("drPlugins")}: ${c.plugins}</li><li>BSA: ${c.bsas}</li><li>.ccc: ${c.ccc_bytes} bytes</li><li>Data: ${mb(c.size)}</li>
    ${c.left_out.length ? `<li>${T("drLeftOut", c.left_out.length)}</li>` : ""}${c.linked ? `<li>${T("drLinked", c.linked)}</li>` : ""}</ul><p>${T("drSdAsk")}</p>`, [
    { id: "sd", label: T("drToSd"), primary: true },
    { id: "manual", label: T("drManual"), hint: T("drManualHint") },
    { id: "later", label: T("drLater") }]);
  if (pick === "sd") { await openPack(c.dest); show("sd"); }
  else if (pick === "manual") { const o = await call("open_folder", c.dest); if (!o.ok) await infoDlg(T("drDone"), `<p class="hint">${esc(c.dest)}</p>`); }
}
async function startDraftFrom(path, name) {
  const html = `<p>${T("drStartBody", esc(name))}</p>
    <div class="open-row"><label for="ds-name">${T("drName")}</label><div class="field"><input id="ds-name" value="${esc(name)} (${esc(T("drMine"))})" spellcheck="false"></div></div>`;
  const pending = confirmDlg(T("drStart"), html, T("drStart"));
  if (!(await pending)) return;
  const nm = $("#ds-name").value.trim();
  const r = await job(T("drCopying"), "draft_start", path, nm);
  if (!r) return;
  S.firstCrit = null; packChanged(); setAudit(r); enterPack("mods");
}

// ------------------------------------------------------------------ load order
async function renderOrder() {
  const o = await call("load_order");
  $("#p-orden").innerHTML = `
    <h2>${T("nav.order")}</h2>
    <p class="sub">${T("orderSub")}</p>
    <div class="order-head">
      <button class="primary" id="save-order" disabled>${T("saveOrder")}</button>
      <button class="ghost" id="loot-go">${T("lootGo")}</button>
      <button class="ghost" id="xe-open">${T("xeOpen")}</button>
      <button class="ghost" id="xe-sync">${T("xeSync")}</button>
      <button class="ghost" id="order-copy" title="${esc(T("orderCopyHint"))}">${T("orderCopy")}</button>
      <label><input type="checkbox" id="show-cc" ${S.showCC ? "checked" : ""}> ${T("showCC")}</label>
      <button class="ghost" id="cc-off" title="${esc(T("ccOffHint"))}">${T("ccOff")}</button>
      <span class="risk">${esc(o.list || "")} · ${o.bytes}${o.limit ? ` / ${o.limit}` : ""} bytes</span>
    </div>
    <div id="loot-panel"></div>
    <ol class="order" id="order">${o.rows.map(rowHtml).join("")}</ol>`;
  $("#show-cc").addEventListener("change", (e) => { S.showCC = e.target.checked; $$("#order li.cc").forEach((li) => li.classList.toggle("hide", !S.showCC)); });
  $("#cc-off").addEventListener("click", async () => {
    const pick = await choiceDlg(T("ccOffTitle"), `<p>${T("ccOffBody")}</p>`,
      [{ id: "free", label: T("ccOffFree"), primary: true }, { id: "patch", label: T("ccOffPatch"), hint: T("ccOffPatchHint") }]);
    if (!pick) return;
    const r = await call("cc_off_unneeded", pick === "patch");
    if (!r.ok) return toast(r.error, true);
    setAudit(r); S.showCC = true; renderOrder(); toast(T("ccOffDone", r.off.length));
  });
  wireOrder();
  $("#save-order").addEventListener("click", saveOrder);
  $("#loot-go").addEventListener("click", lootSuggest);
  $("#xe-open").addEventListener("click", openInXedit);
  $("#xe-sync").addEventListener("click", syncFromXedit);
  $("#order-copy").addEventListener("click", async () => {
    // what the page shows now, unsaved moves included; the Creation Club only when shown
    const lines = $$("#order li").filter((li) => !li.classList.contains("hide")).map((li) => {
      const n = li.querySelector(".n")?.textContent || "", nm = li.dataset.name || "";
      const tag = li.querySelector(".src")?.textContent || "";
      const mst = li.querySelector(".mst")?.textContent || "";
      return `${n.padStart(3)}  ${nm.startsWith("#") ? "[off] " + nm.slice(1) : nm}${tag ? `  (${tag})` : ""}${mst ? `  ← ${mst}` : ""}`;
    });
    const text = `${T("orderCopyTitle", S.pack?.name || "")}\n\n${lines.join("\n")}\n`;
    try { await navigator.clipboard.writeText(text); toast(T("orderCopied")); }
    catch (e) { const r = await call("save_text", `${S.pack?.name || "pack"} - load order.txt`, text); if (r.ok) toast(T("drSaved", r.path)); }
  });
  $$("#order [data-act]").forEach((c) => c.addEventListener("change", () => togglePlugin(c.dataset.act, c.checked)));
  renderLootPanel();
}
function rowHtml(r, i) {
  const cls = [r.source !== "lista" ? "fixed" : "", r.cc ? "cc" : "", r.cc && !S.showCC ? "hide" : "", r.problems.length ? "bad" : "", !r.exists ? "missing" : ""].join(" ");
  const meta = r.source === "juego" ? T("srcGame") : r.source === "ini" ? T("srcIni") : r.cc ? "CC" : r.records === 0 ? T("empty") : r.light ? "ESL" : "";
  return `<li class="${cls}" data-name="${esc(r.name)}" ${r.source === "lista" ? 'draggable="true"' : ""}>
    <span class="n">${i}</span>
    <span>${r.source === "lista" ? `<input type="checkbox" class="act" title="${esc(T("pmActive"))}" data-act="${esc(r.name.replace(/^#/, ""))}" ${r.name.startsWith("#") ? "" : "checked"}> ` : ""}<span class="nm ${r.name.startsWith("#") ? "off" : ""}" title="${esc(r.masters?.length ? T("pmMasters") + ": " + r.masters.join(", ") : r.desc || "")}">${esc(r.name.replace(/^#/, ""))}</span>${r.title ? ` <span class="hint" title="${esc(r.desc || "")}">${esc(r.title)}</span>` : ""}${r.masters?.length && !r.cc ? `<div class="mst">${esc(r.masters.filter((m) => !/^(skyrim|update|dawnguard|hearthfires|dragonborn)\.esm$/i.test(m)).join(" · "))}</div>` : ""}${r.problems.length ? `<div class="prob">${r.problems.map(esc).join(" · ")}</div>` : ""}</span>
    <span>${meta ? `<span class="src">${meta}</span>` : ""}</span>
    <span class="mv">${r.source === "lista" ? `<button data-up title="${T("up")}">▲</button><button data-down title="${T("down")}">▼</button>` : ""}</span></li>`;
}
function wireOrder() {
  const ol = $("#order");
  const dirty = () => ($("#save-order").disabled = false);
  const sib = (el, dir) => { let x = el[dir]; while (x && x.classList.contains("hide")) x = x[dir]; return x; };
  // Dragging with pointer events, not the browser's drag and drop: inside the app
  // window that one competes with the file drop that Python handles and could
  // leave the page stuck mid-drag (seen moving Bandit War). Esc cancels.
  let drag = null;
  const clear = () => { $$(".over, .over-after", ol).forEach((x) => x.classList.remove("over", "over-after")); };
  const end = (commit) => {
    if (!drag) return;
    const { li, target, after, started } = drag;
    li.classList.remove("drag"); clear(); document.body.classList.remove("dragging");
    if (commit && started && target && target !== li) {
      ol.insertBefore(li, after ? target.nextSibling : target); renumber(); dirty();
    }
    drag = null;
  };
  $$("li[draggable]", ol).forEach((li) => {
    li.removeAttribute("draggable"); li.classList.add("movable");
    li.addEventListener("pointerdown", (e) => {
      if (e.button !== 0 || e.target.closest("button, input, a")) return;
      drag = { li, x: e.clientX, y: e.clientY, started: false, target: null, after: false };
      li.setPointerCapture(e.pointerId);
    });
    li.addEventListener("pointermove", (e) => {
      if (!drag || drag.li !== li) return;
      if (!drag.started) {
        if (Math.abs(e.clientY - drag.y) < 6) return;
        drag.started = true; li.classList.add("drag"); document.body.classList.add("dragging");
      }
      const under = document.elementFromPoint(e.clientX, e.clientY)?.closest("#order li.movable");
      clear();
      if (under && under !== li) {
        const r = under.getBoundingClientRect();
        drag.target = under; drag.after = e.clientY > r.top + r.height / 2;
        under.classList.add(drag.after ? "over-after" : "over");
      } else drag.target = null;
      // keep the list scrolling near the window's edges
      if (e.clientY < 60) window.scrollBy(0, -12); else if (e.clientY > innerHeight - 60) window.scrollBy(0, 12);
    });
    li.addEventListener("pointerup", () => end(true));
    li.addEventListener("pointercancel", () => end(false));
    li.addEventListener("lostpointercapture", () => end(false));
    $("[data-up]", li).addEventListener("click", () => { const p = sib(li, "previousElementSibling"); if (p && p.classList.contains("movable")) { ol.insertBefore(li, p); renumber(); dirty(); } });
    $("[data-down]", li).addEventListener("click", () => { const n = sib(li, "nextElementSibling"); if (n) { ol.insertBefore(n, li); renumber(); dirty(); } });
  });
  document.addEventListener("keydown", (e) => { if (e.key === "Escape") end(false); });
}
function renumber() { $$("#order li").forEach((li, i) => ($(".n", li).textContent = i)); }
async function saveOrder() {
  const names = $$("#order li.movable").map((li) => li.dataset.name);
  const r = await call("save_load_order", names);
  if (!r.ok) { toast(r.error, true); return; }
  setAudit(r); toast(T("orderSaved")); renderOrder();
}

// ------------------------------------------------------------------ textures
function renderTextures() {
  const st = S.audit.stats, mods = S.audit.mods || [];
  const diets = Object.fromEntries(S.audit.findings.filter((f) => f.code === "tex-diet").map((f) => [f.subject, f]));
  const scanned = mods.some((m) => m.scanned);
  $("#p-texturas").innerHTML = `
    <h2>${T("nav.textures")}</h2>
    <p class="sub">${T("texSub")}</p>
    ${scanned ? "" : `<p class="note">${T("texNotScanned")} <button class="ghost sm" id="tex-scan">${T("recheck")}</button></p>`}
    <dl class="ledger">
      <div><dt>${T("texActive")}</dt><dd>${mb(st.tex_bytes || 0)}</dd></div>
      <div><dt>${T("pcTex")}</dt><dd>${mods.filter((m) => m.pc_dds).length}</dd></div>
      <div><dt>${T("pcAudio")}</dt><dd>${mods.filter((m) => m.audio_pc).length}</dd></div>
      <div><dt>${T("texFormats")}</dt><dd>${Object.entries(st.tex_formats || {}).map(([k, v]) => `${esc(k)}: ${v}`).join(", ") || T("noData")}</dd></div>
    </dl>
    <p class="note">${T("texNote")}</p>
    <p class="hint">${T("texDietHint")}</p>
    <h3>${T("byBsa")}</h3>
    <table><tr><th>BSA</th><th>${T("plugin")}</th><th class="r">${T("files")}</th><th class="r">${T("tex")}</th><th class="r">${T("texWithDiet")}</th><th class="r">${T("sdSize")}</th><th></th></tr>
    ${mods.map((m) => { const d = diets[m.bsa]; return `<tr><td>${esc(m.bsa)}</td><td>${esc(m.plugin)}</td><td class="r">${m.files}</td>
      <td class="r">${m.tex_count ? mb(m.tex) : "–"}</td><td class="r">${m.tex_count && m.diet_after != null && m.diet_after < m.tex ? mb(m.diet_after) : "–"}</td>
      <td class="r">${mb(m.size)}</td><td>${m.tex_count ? `<button class="${d && d.fix ? "" : "ghost "}sm" data-diet="${esc(m.bsa)}">${T("texDietGo")}</button>` : ""}</td></tr>`; }).join("")}</table>`;
  $("#tex-scan")?.addEventListener("click", async () => { const r = await job(T("working"), "reaudit", true); if (r) { setAudit(r); renderTextures(); } });
  $$("#p-texturas [data-diet]").forEach((b) => b.addEventListener("click", () => dietDialog(b.dataset.diet)));
}
async function dietDialog(bsa) {
  const html = `<p>${T("dietDlgIntro", esc(bsa))}</p>
    <div class="opts">
      <label>${T("dietTitle")} <select id="dd-preset">${PRESETS.map((p) => `<option value="${p}">${T("preset" + p[0].toUpperCase() + p.slice(1))}</option>`).join("")}</select></label>
      <p class="hint" id="dd-hint"></p>
      <label>${T("cvMaxSize")} <select id="dd-max"><option value="">${T("cvMaxNone")}</option>${MAX_SIZES.map((m) => `<option value="${m}">${sizeLabel(m)}</option>`).join("")}</select></label>
      <label><input type="checkbox" id="dd-bc1" checked> ${T("optBc1")}</label>
      <p class="note" id="dd-est">…</p>
    </div>
    <p class="hint">${T("dietDlgUndo")}</p>`;
  const args = () => [bsa, $("#dd-preset").value, $("#dd-max").value ? +$("#dd-max").value : null, $("#dd-bc1").checked];
  const refresh = async () => {
    const p = $("#dd-preset")?.value; if (!p) return;
    $("#dd-hint").textContent = T("preset" + p[0].toUpperCase() + p.slice(1) + "P");
    const r = await call("diet_estimate", ...args());
    if ($("#dd-est")) $("#dd-est").textContent = r?.ok ? T("dietDlgEst", mb(r.before), mb(r.after), r.count) : (r?.error || "");
  };
  const wait = confirmDlg(T("texDietGo") + ": " + bsa, html, T("texDietGo"));
  ["#dd-preset", "#dd-max", "#dd-bc1"].forEach((sel) => $(sel).addEventListener("change", refresh));
  refresh();
  if (!(await wait)) return;
  const r = await job(T("working"), "diet_bsa", ...args());
  if (!r) return;
  setAudit(r); renderTextures(); toast(T("done"));
}

// ------------------------------------------------------------------ history
async function renderHistory() {
  const h = await call("history");
  $("#p-historial").innerHTML = `
    <h2>${T("nav.history")}</h2>
    <p class="sub">${T("histSub")}</p>
    ${h.length ? h.map((e) => `<div class="hist ${e.undone ? "undone" : ""}"><div><div class="t">${esc(e.title)}</div>
      <div class="when">${esc(e.time)} · ${e.files.length} ${e.files.length === 1 ? T("file1") : T("fileN")}${e.undone ? ` · ${T("undoneAt")} ${esc(e.undone)}` : ""}</div></div>
      <div>${e.undone || e.is_undo ? "" : `<button class="ghost" data-undo="${esc(e.id)}">${T("undo")}</button>`}</div></div>`).join("") : `<p class="empty">${T("noHist")}</p>`}`;
  $$("[data-undo]").forEach((b) => b.addEventListener("click", async () => {
    if (!(await confirmDlg(T("undo"), `<p>${T("undoBody")}</p>`, T("undo")))) return;
    const r = await call("undo", b.dataset.undo);
    if (!r.ok) { toast(r.error, true); return; }
    setAudit(r); toast(T("undone")); renderHistory();
  }));
}

// ------------------------------------------------------------------ convert
const PRESETS = ["diet", "koka", "extreme", "none"];
const MAX_SIZES = [256, 512, 1024, 2048, 4096];
const sizeLabel = (m) => (m >= 1024 ? m / 1024 + "K" : String(m));
const PACKINGS = ["ini1", "plugin", "single", "ini"];
function toolChips(t) {
  const chip = (ok, label, extra = "") => `<span class="chip ${ok ? "ok" : "no"}">${esc(label)}${extra ? ` <small>${esc(extra)}</small>` : ""}</span>`;
  return `<div class="chips">
    ${chip(t.texconv, T("toolTexconv"))}${chip(t.ffmpeg, T("toolFfmpeg"))}
    ${chip(t.vgaudio && t.vgaudio_toolkit, T("toolVga"), t.vgaudio && !t.vgaudio_toolkit ? T("vgaOfficial") : "")}
    ${chip(t.sdk, T("toolNvn"), t.nvntexpkg && t.nvn_missing.length ? T("nvnMissing", t.nvn_missing.join(", ")) : "")}
    ${chip(t.havok, T("toolHavok"), t.hbpp && !t.hkxc ? T("havokPart") : "")}
  </div><p class="hint">${T("toolsWhere", esc(t.folder || ""))}</p>`;
}
function convModes() {
  return `<div class="tabs cv-modes"><button data-cvmode="one" class="${S.convMode === "batch" ? "" : "on"}">${T("bModeOne")}</button><button data-cvmode="batch" class="${S.convMode === "batch" ? "on" : ""}">${T("bModeMany")}</button></div>`;
}
function wireConvModes(el) {
  $$("[data-cvmode]", el).forEach((b) => b.addEventListener("click", () => { S.convMode = b.dataset.cvmode; renderConvert(); }));
}
async function renderConvert() {
  if (!S.pack) { $("#p-convertir").innerHTML = `<h2>${T("nav.convert")}</h2><p class="empty">${T("needPack")}</p>`; return; }
  if (S.convMode === "batch") return renderBatch();
  S.state = await call("state");
  const view = await call("convert_view");
  S.conv = view ? { view, preset: S.conv?.preset || "diet", native: S.conv?.native ?? true, bc1: S.conv?.bc1 ?? false,
                    names: S.conv?.view?.id === view.id ? S.conv.names : {} } : null;
  $("#p-convertir").innerHTML = `
    <h2>${T("nav.convert")}</h2>
    ${convModes()}
    <p class="sub">${T("convSub")}</p>
    <h3 class="sm">${T("toolsTitle")}</h3>
    ${toolChips(S.state.tools)}
    <div class="open-row"><label for="cv-path">${T("convPick")}</label>
      <div class="field"><input id="cv-path" spellcheck="false" value="${esc(view?.source || "")}">
        ${hasWebview() ? `<button class="ghost" id="cv-folder">${T("addFolder")}</button><button class="ghost" id="cv-archive">${T("addArchive")}</button>` : ""}
        <button class="primary" id="cv-read">${T("analyze")}</button></div></div>
    <div id="cv-body"></div>`;
  wireConvModes($("#p-convertir"));
  $("#cv-folder")?.addEventListener("click", async () => { const p = await call("pick_folder"); if (p) $("#cv-path").value = p; });
  $("#cv-archive")?.addEventListener("click", async () => { const p = await call("pick_archive"); if (p) $("#cv-path").value = p; });
  $("#cv-read").addEventListener("click", async () => {
    const p = $("#cv-path").value.trim(); if (!p) return toast(T("needFolder"), true);
    const v = await job(T("analyzing"), "convert_analyze", p);
    if (!v) return;
    if (v.fomod) { S.conv = null; S.fomod = { view: v.fomod, choices: {}, step: firstVisible(v.fomod, -1), images: {}, focus: null }; return renderFomod(); }
    S.conv = { view: v, preset: "diet", native: v.tools.sdk, bc1: false, names: {} };
    renderConvBody();
  });
  if (S.convPrefill) {
    $("#cv-path").value = S.convPrefill; S.convPrefill = null;
    S.fomod = null; S.conv = null; $("#cv-read").click(); return;
  }
  if (S.fomod) renderFomod(); else if (S.conv) renderConvBody();
}
// ---------------------------------------------------------------- FOMOD assistant
function firstVisible(view, after) { const s = view.steps.find((x) => x.index > after && x.visible); return s ? s.index : -1; }
function prevVisible(view, before) { const s = [...view.steps].reverse().find((x) => x.index < before && x.visible); return s ? s.index : -1; }
async function fomodRefresh() {
  const f = S.fomod;
  const r = await call("fomod_eval", f.choices, f.step, f.item ?? null);
  if (!r.ok) return toast(r.error, true);
  f.view = r; Object.assign(f.images, Object.fromEntries(Object.entries(r.images || {}).map(([k, v]) => [f.step + ":" + k, v])));
  renderFomod();
}
function renderFomod() {
  const f = S.fomod, v = f.view;
  if (f.step < 0) f.step = firstVisible(v, -1);
  const vis = v.steps.filter((x) => x.visible);
  const st = v.steps.find((x) => x.index === f.step);
  if (st && !Object.keys(f.images).some((k) => k.startsWith(f.step + ":")) && v.step !== f.step) { fomodRefresh(); return; }
  if (st && v.step === f.step) Object.assign(f.images, Object.fromEntries(Object.entries(v.images || {}).map(([k, x]) => [f.step + ":" + k, x])));
  const pos = vis.findIndex((x) => x.index === f.step) + 1;
  const last = firstVisible(v, f.step) < 0;
  const focus = f.focus && st ? st.groups[f.focus[0]]?.options[f.focus[1]] : null;
  const img = focus ? f.images[`${f.step}:${f.focus[0]}:${f.focus[1]}`] : (v.image || null);
  $("#cv-body").innerHTML = `
    <div class="ornament"></div>
    <h3>${T("fmTitle")}: ${esc(v.name)}</h3>
    <p class="hint">${T("fmSub")}</p>
    ${v.module_ok ? "" : `<p class="note warn">${T("fmModuleWarn")}</p>`}
    ${v.unknown.length ? `<p class="note">${T("fmUnknown", esc(v.unknown.join(", ")))}</p>` : ""}
    <div class="fm-steps">${vis.map((x, i) => `<span class="${x.index === f.step ? "on" : ""}">${i + 1}. ${esc(x.name)}</span>`).join("")}</div>
    ${st ? `<div class="fm">
      <div class="fm-groups">${st.groups.map((g) => {
        const single = g.type === "SelectExactlyOne" || g.type === "SelectAtMostOne";
        const opts = g.options.map((o) => {
          const dis = o.type === "NotUsable" || o.type === "Required" || g.type === "SelectAll";
          const on = g.selected.includes(o.index);
          const badge = T("fmType")[o.type] || "";
          return `<label class="fm-opt ${o.type === "NotUsable" ? "off" : ""} ${on ? "on" : ""}" data-g="${g.index}" data-o="${o.index}">
            <input type="${single ? "radio" : "checkbox"}" name="g${g.index}" ${on ? "checked" : ""} ${dis ? "disabled" : ""}>
            <span>${esc(o.name)}</span>${badge ? `<em class="t-${o.type}">${badge}</em>` : ""}</label>`; }).join("");
        const none = g.type === "SelectAtMostOne" ? `<label class="fm-opt ${g.selected.length ? "" : "on"}" data-g="${g.index}" data-o="-1"><input type="radio" name="g${g.index}" ${g.selected.length ? "" : "checked"}><span>${T("fmNone")}</span></label>` : "";
        return `<div class="fm-group"><h4>${esc(g.name)} <small>${T("fmPick")[g.type] || ""}</small></h4>${opts}${none}</div>`; }).join("")}</div>
      <aside class="fm-preview">${img ? `<img src="${img}" alt="">` : ""}
        <div class="fm-desc">${focus ? `<b>${esc(focus.name)}</b><p>${esc(focus.description || T("fmNoDesc"))}</p>` : ""}</div></aside>
    </div>` : ""}
    <div class="cv-actions">
      <button class="ghost" id="fm-back" ${prevVisible(v, f.step) < 0 ? "disabled" : ""}>${T("fmBack")}</button>
      <span class="hint">${T("fmStepOf", pos, vis.length)}</span>
      ${last ? `<button class="primary" id="fm-finish">${T("fmFinish")}</button>` : `<button class="primary" id="fm-next">${T("fmNext")}</button>`}
      <button class="ghost" id="fm-cancel">${f.item ? T("xBack") : T("convertCancel")}</button></div>`;
  $$(".fm-opt").forEach((l) => {
    const gi = +l.dataset.g, oi = +l.dataset.o;
    l.addEventListener("mouseenter", () => { if (oi >= 0 && (!f.focus || f.focus[0] !== gi || f.focus[1] !== oi)) { f.focus = [gi, oi]; renderFomodPreview(); } });
    $("input", l).addEventListener("change", (e) => {
      const g = st.groups[gi];
      const single = g.type === "SelectExactlyOne" || g.type === "SelectAtMostOne";
      let sel = single ? (oi < 0 ? [] : [oi]) : (e.target.checked ? [...new Set([...g.selected, oi])] : g.selected.filter((x) => x !== oi));
      f.choices[f.step] = f.choices[f.step] || {}; f.choices[f.step][gi] = sel; f.focus = oi >= 0 ? [gi, oi] : f.focus;
      fomodRefresh();
    });
  });
  $("#fm-back").addEventListener("click", () => { f.step = prevVisible(v, f.step); f.focus = null; renderFomod(); });
  $("#fm-next")?.addEventListener("click", () => { f.step = firstVisible(v, f.step); f.focus = null; renderFomod(); });
  $("#fm-cancel").addEventListener("click", async () => {
    if (f.item) { S.fomod = null; return renderBatch(); }
    await call("convert_cancel"); S.fomod = null; renderConvert(); });
  $("#fm-finish")?.addEventListener("click", async () => {
    if (f.item) {
      const it = await job(T("fmInstalling"), "batch_fomod_finish", f.item, f.choices);
      if (!it) return;
      S.fomod = null;
      const i = S.batch.items.findIndex((x) => x.id === it.id);
      if (i >= 0) S.batch.items[i] = it;
      return renderBatch();
    }
    const r = await job(T("fmInstalling"), "fomod_finish", f.choices);
    if (!r) return;
    S.fomod = null;
    S.conv = { view: r, preset: "diet", native: r.tools.sdk, bc1: false, names: {} };
    renderConvBody();
  });
}
function renderFomodPreview() {
  const f = S.fomod, st = f.view.steps.find((x) => x.index === f.step);
  const o = st.groups[f.focus[0]].options[f.focus[1]];
  const img = f.images[`${f.step}:${f.focus[0]}:${f.focus[1]}`];
  $(".fm-preview").innerHTML = `${img ? `<img src="${img}" alt="">` : ""}<div class="fm-desc"><b>${esc(o.name)}</b><p>${esc(o.description || T("fmNoDesc"))}</p></div>`;
}

// ---------------------------------------------------------------- convert several at once
const B_KEYS = ["preset", "max_size", "packing", "native", "bc1", "compress", "keep"];
function bDefaults() { return { preset: "diet", max_size: null, packing: "ini1", native: true, bc1: false, compress: true, keep: true }; }
function bOpts(id) {
  const B = S.batch;
  if (!B.opts[id]) B.opts[id] = { ...(B.all || bDefaults()), names: {}, on: true };
  return B.opts[id];
}
function bName(it, pl) { return bOpts(it.id).names[pl.name] || pl.suggested; }
function bEstimate(it) {
  const o = bOpts(it.id), sdk = o.native && S.batch.tools?.sdk;
  const key = `${o.preset}|${sdk ? 1 : 0}|${o.max_size || ""}`;
  if (!o.max_size) return it.view.estimates[o.preset][sdk ? "sdk" : "pc"];
  const c = (S.batch.est[it.id] = S.batch.est[it.id] || {});
  if (c[key]) return c[key];
  if (!c["_" + key]) {
    c["_" + key] = 1;
    call("batch_estimate", it.id, o.preset, sdk, o.max_size).then((r) => { if (r?.ok) { c[key] = r; bRefreshNumbers(); } });
  }
  return it.view.estimates[o.preset][sdk ? "sdk" : "pc"];
}
async function renderBatch() {
  const el = $("#p-convertir");
  S.state = S.state || (await call("state"));
  if (!S.batch) S.batch = { items: [], opts: {}, est: {}, problems: {} };
  if (S.batchPrefill) {
    const paths = S.batchPrefill; S.batchPrefill = null;
    const v = await job(T("bReading"), "batch_add", paths);
    if (v) Object.assign(S.batch, { items: v.items, budget: v.budget, tools: v.tools });
  } else if (!S.batch.loaded) {
    const v = await call("batch_view");
    Object.assign(S.batch, { items: v.items, budget: v.budget, tools: v.tools });
  }
  S.batch.loaded = true;
  if (S.fomod?.item) {
    el.innerHTML = `<h2>${T("nav.convert")}</h2>${convModes()}<div id="cv-body"></div>`;
    wireConvModes(el);
    return renderFomod();
  }
  const B = S.batch, A = B.all || bDefaults(), tools = B.tools || {};
  const ready = B.items.filter((it) => it.kind === "ready");
  const sizes = [256, 512, 1024, 2048, 4096];
  const sizeOpts = (cur) => `<option value="">${T("cvMaxNone")}</option>${sizes.map((m) => `<option value="${m}" ${String(cur || "") === String(m) ? "selected" : ""}>${m >= 1024 ? m / 1024 + "K" : m}</option>`).join("")}`;
  const presetOpts = (cur) => PRESETS.map((p) => `<option value="${p}" ${cur === p ? "selected" : ""}>${T("preset" + p[0].toUpperCase() + p.slice(1))}</option>`).join("");
  const packOpts = (cur) => PACKINGS.map((k) => `<option value="${k}" ${(cur || "ini1") === k ? "selected" : ""}>${T("cvPack_" + k)}</option>`).join("");
  // which batch mod brings each plugin (to explain "missing" masters)
  const owner = {};
  ready.forEach((it) => it.view.plugins.forEach((pl) => (owner[pl.name.toLowerCase()] = it.name)));
  const card = (it) => {
    const head = `<div class="bc-head"><b title="${esc(it.source)}">${esc(it.name)}</b><button class="link rm" data-brm="${esc(it.id)}" title="${T("qRemove")}">✕</button></div>`;
    if (it.kind === "error") return `<div class="bcard err">${head}<p class="note warn">${esc(it.error)}</p><button class="ghost sm" data-breread="${esc(it.id)}">${T("bReread")}</button></div>`;
    if (it.kind === "fomod") return `<div class="bcard fomod">${head}<p>${T("bFomod")}</p><button class="primary sm" data-bfomod="${esc(it.id)}">${T("bFomodGo")}</button></div>`;
    const o = bOpts(it.id), v = it.view, warns = v.notes.filter((n) => n.level === "warn").length;
    const prob = (B.problems[it.id] || []).map((t) => `<p class="note warn">${esc(t)}</p>`).join("");
    return `<div class="bcard ${o.on ? "" : "off"} ${prob ? "bad" : ""}" data-bcard="${esc(it.id)}">${head}
      <label class="bc-on"><input type="checkbox" data-bon="${esc(it.id)}" ${o.on ? "checked" : ""}> ${T("bInclude")}</label>
      <div class="bc-grid">
        <label>${T("dietTitle")}<select data-bset="preset" data-id="${esc(it.id)}">${presetOpts(o.preset)}</select></label>
        <label>${T("cvMaxSize")}<select data-bset="max_size" data-id="${esc(it.id)}">${sizeOpts(o.max_size)}</select></label>
      </div>
      <div class="bc-num" data-bnum="${esc(it.id)}"></div>
      ${v.plugins.length ? `<div class="bc-names">${v.plugins.map((pl, i) => {
        const miss = pl.missing.map((m) => owner[m.toLowerCase()] ? `<span class="tag">${esc(m)}: ${esc(T("bFromBatch", owner[m.toLowerCase()]))}</span>` : `<span class="tag bad">${esc(T("needs", m))}</span>`).join("");
        return `<div class="bc-pl"><div class="hint">${esc(pl.name)}</div>
          <div class="field"><input class="bnm" data-id="${esc(it.id)}" data-i="${i}" value="${esc(plStem(bName(it, pl)))}" ${pl.locked ? "disabled" : ""} spellcheck="false"><span class="hint" style="align-self:center">${esc(plExt(bName(it, pl)))}</span>${pl.locked ? "" : `<button class="ghost sm" data-bshort="${esc(it.id)}|${i}">${T("shorten")}</button>`}</div>
          ${pl.reasons.length || miss ? `<div class="tags">${pl.reasons.map((r) => `<span class="tag">${T({ chars: "reasonChars", esl: "reasonEsl", blocked: "reasonBlocked", orphan: "reasonOrphan" }[r] || r)}</span>`).join("")}${miss}</div>` : ""}</div>`; }).join("")}</div>`
        : `<p class="hint">${T("bNoPlugins")}</p>`}
      <details class="bc-more"><summary>${T("bMore")}</summary>
        <label>${T("cvPacking")}<select data-bset="packing" data-id="${esc(it.id)}">${packOpts(o.packing)}</select></label>
        <label class="ck"><input type="checkbox" data-bset="native" data-id="${esc(it.id)}" ${o.native && tools.sdk ? "checked" : ""} ${tools.sdk ? "" : "disabled"}> ${T("optNative")}</label>
        <label class="ck"><input type="checkbox" data-bset="bc1" data-id="${esc(it.id)}" ${o.bc1 && o.native && tools.sdk ? "checked" : ""} ${o.native && tools.sdk ? "" : "disabled"}> ${T("optBc1")}</label>
        <label class="ck"><input type="checkbox" data-bset="compress" data-id="${esc(it.id)}" ${o.compress ? "checked" : ""}> ${T("cvCompress")}</label>
        <label class="ck"><input type="checkbox" data-bset="keep" data-id="${esc(it.id)}" ${o.keep ? "checked" : ""}> ${T("cvKeep")}</label>
      </details>
      ${v.notes.length ? `<details class="bc-notes ${warns ? "warn" : ""}"><summary>${T("bWarn", v.notes.length)}</summary>${v.notes.map((n) => `<p class="note ${n.level === "warn" ? "warn" : ""}">${esc(n.text)}</p>`).join("")}</details>` : ""}
      ${prob}</div>`;
  };
  const nOn = ready.filter((it) => bOpts(it.id).on).length;
  el.innerHTML = `
    <h2>${T("nav.convert")}</h2>
    ${convModes()}
    <p class="sub">${T("bSub")}</p>
    ${toolChips(S.state.tools)}
    <div class="open-row"><div class="field"><input id="b-path" spellcheck="false" placeholder="${esc(T("bPathPh"))}">
      ${hasWebview() ? `<button class="ghost" id="b-files">${T("bAddFiles")}</button><button class="ghost" id="b-folder">${T("bAddFolder")}</button>` : ""}
      <button class="primary" id="b-add">${T("bAdd")}</button></div></div>
    <div class="budget" id="b-budget"></div>
    ${ready.length > 1 ? `<div class="b-all"><b>${T("bAll")}</b>
      <label>${T("dietTitle")} <select id="ba-preset">${presetOpts(A.preset)}</select></label>
      <label>${T("cvMaxSize")} <select id="ba-max">${sizeOpts(A.max_size)}</select></label>
      <label>${T("cvPacking")} <select id="ba-pack">${packOpts(A.packing)}</select></label>
      <label class="ck"><input type="checkbox" id="ba-native" ${A.native && tools.sdk ? "checked" : ""} ${tools.sdk ? "" : "disabled"}> NvnTexpkg</label>
      <button class="ghost sm" id="ba-apply">${T("bApply")}</button></div>` : ""}
    ${B.problems._ ? `<p class="note warn">${esc(B.problems._)}</p>` : ""}
    <div class="bgrid">${B.items.length ? B.items.map(card).join("") : `<p class="empty">${T("bEmpty")}</p>`}</div>
    <div class="cv-actions"><button class="primary" id="b-run" ${nOn ? "" : "disabled"}>${T("bRun", nOn)}</button>
      ${B.items.length ? `<button class="ghost" id="b-clear">${T("bClear")}</button>` : ""}</div>`;
  wireConvModes(el);
  const addPaths = async (paths) => {
    paths = (paths || []).filter(Boolean); if (!paths.length) return;
    const v = await job(T("bReading"), "batch_add", paths);
    if (v) { Object.assign(S.batch, { items: v.items, budget: v.budget, tools: v.tools }); renderBatch(); }
  };
  $("#b-files")?.addEventListener("click", async () => addPaths(await call("pick_files")));
  $("#b-folder")?.addEventListener("click", async () => addPaths([await call("pick_folder")]));
  $("#b-add").addEventListener("click", () => addPaths([$("#b-path").value.trim()]));
  $("#b-path").addEventListener("keydown", (e) => { if (e.key === "Enter") addPaths([e.target.value.trim()]); });
  $$("[data-brm]", el).forEach((b) => b.addEventListener("click", async () => {
    await call("batch_remove", b.dataset.brm);
    B.items = B.items.filter((x) => x.id !== b.dataset.brm); delete B.opts[b.dataset.brm]; renderBatch(); }));
  $$("[data-breread]", el).forEach((b) => b.addEventListener("click", async () => {
    const it = B.items.find((x) => x.id === b.dataset.breread); if (!it) return;
    await call("batch_remove", it.id); delete B.opts[it.id];
    B.items = B.items.filter((x) => x.id !== it.id); addPaths([it.source]);
  }));
  $$("[data-bfomod]", el).forEach((b) => b.addEventListener("click", async () => {
    const r = await call("batch_fomod_start", b.dataset.bfomod);
    if (!r.ok) return toast(r.error, true);
    S.fomod = { view: r, choices: {}, step: firstVisible(r, -1), images: {}, focus: null, item: b.dataset.bfomod };
    renderBatch();
  }));
  $$("[data-bon]", el).forEach((c) => c.addEventListener("change", () => { bOpts(c.dataset.bon).on = c.checked; renderBatch(); }));
  $$("[data-bset]", el).forEach((c) => c.addEventListener("change", () => {
    const o = bOpts(c.dataset.id), k = c.dataset.bset;
    o[k] = c.type === "checkbox" ? c.checked : k === "max_size" ? (c.value ? +c.value : null) : c.value;
    const open = $(`[data-bcard="${CSS.escape(c.dataset.id)}"] details.bc-more`)?.open;
    renderBatch().then(() => { if (open) { const d = $(`[data-bcard="${CSS.escape(c.dataset.id)}"] details.bc-more`); if (d) d.open = true; } });
  }));
  $$(".bnm", el).forEach((inp) => inp.addEventListener("input", () => {
    const it = B.items.find((x) => x.id === inp.dataset.id);
    const pl = it.view.plugins[+inp.dataset.i];
    bOpts(it.id).names[pl.name] = plJoin(inp.value, bName(it, pl)); bRefreshNumbers();
  }));
  $$("[data-bshort]", el).forEach((b) => b.addEventListener("click", () => {
    const [id, i] = b.dataset.bshort.split("|"), it = B.items.find((x) => x.id === id), pl = it.view.plugins[+i];
    bOpts(id).names[pl.name] = pl.compact; $(`.bnm[data-id="${CSS.escape(id)}"][data-i="${i}"]`).value = plStem(pl.compact); bRefreshNumbers();
  }));
  $("#ba-apply")?.addEventListener("click", () => {
    B.all = { ...A, preset: $("#ba-preset").value, max_size: $("#ba-max").value ? +$("#ba-max").value : null,
              packing: $("#ba-pack").value, native: !!$("#ba-native")?.checked };
    ready.forEach((it) => { const o = bOpts(it.id); ["preset", "max_size", "packing", "native"].forEach((k) => (o[k] = B.all[k])); });
    renderBatch();
  });
  $("#b-clear")?.addEventListener("click", async () => { await call("batch_clear"); S.batch = null; renderBatch(); });
  $("#b-run").addEventListener("click", runBatch);
  bRefreshNumbers();
}
function bRefreshNumbers() {
  const B = S.batch, b = B.budget; if (!b) return;
  const utf8 = (s) => new TextEncoder().encode(s).length;
  let add = 0, before = 0, after = 0;
  B.items.filter((it) => it.kind === "ready").forEach((it) => {
    const o = bOpts(it.id), e = bEstimate(it);
    const bytes = it.view.plugins.reduce((n, pl) => n + utf8(bName(it, pl)) + b.nl, 0);
    const box = $(`[data-bnum="${CSS.escape(it.id)}"]`);
    if (box) box.innerHTML = `${T("bEst", mb(e.before), mb(e.after))} · ${it.view.plugins.length ? T("bCccAll", bytes) : T("bPlugins", 0)}`;
    if (!o.on) return;
    add += bytes; before += e.before; after += e.after;
  });
  const cap = (S.state?.ram_cap || 0) * 1048576, lim = b.ccc_limit, cccTotal = b.ccc_now + add;
  const cccWarn = lim && cccTotal > lim ? T("overCcc") : (b.ccc_warn && cccTotal > b.ccc_warn ? T("nearCcc") : "");
  const scaleC = lim || Math.max(cccTotal, 1), texTotal = b.tex_pack + after, scaleT = Math.max(cap, texTotal, 1);
  const run = $("#b-run"); if (run && lim && cccTotal > lim) run.disabled = true;
  const box = $("#b-budget"); if (!box) return;
  box.innerHTML = `
    <div class="brow"><div class="blbl">${lim ? T("cccLbl") : T("seList")}</div>
      <div class="bmeter magicka"><i style="width:${(100 * b.ccc_now) / scaleC}%"></i><i class="new" style="left:${(100 * b.ccc_now) / scaleC}%;width:${(100 * add) / scaleC}%"></i></div>
      <div class="bval ${cccWarn ? "bad" : ""}">${T("cccLine", b.ccc_now, add, lim)}${cccWarn ? ` · ${cccWarn}` : ""}</div></div>
    <div class="brow"><div class="blbl">${T("texPackLbl")}</div>
      <div class="bmeter stamina"><i style="width:${(100 * b.tex_pack) / scaleT}%"></i><i class="new" style="left:${(100 * b.tex_pack) / scaleT}%;width:${(100 * after) / scaleT}%"></i>${cap ? `<b class="cap" style="left:${(100 * cap) / scaleT}%"></b>` : ""}</div>
      <div class="bval ${cap && texTotal > cap ? "bad" : ""}">${mb(b.tex_pack)} + ${mb(after)}${cap && texTotal > cap ? ` · ${T("overCap")}` : ""}</div></div>`;
}
async function runBatch() {
  const B = S.batch;
  const plan = B.items.filter((it) => it.kind === "ready" && bOpts(it.id).on).map((it) => {
    const o = bOpts(it.id), sdk = o.native && !!B.tools?.sdk;
    const names = {}; it.view.plugins.forEach((pl) => (names[pl.name] = bName(it, pl)));
    return { id: it.id, options: { preset: o.preset, sdk, bc1: o.bc1 && sdk, names, packing: o.packing || "ini1",
                                   compress: o.compress !== false, max_size: o.max_size || null, keep: o.keep !== false } };
  });
  B.problems = {};
  const start = await call("batch_run", plan);
  if (!start.ok) {
    (start.problems || []).forEach((p) => { if (p.id) (B.problems[p.id] = B.problems[p.id] || []).push(p.text); else B.problems._ = p.text; });
    toast(start.error || "Error", true);
    return renderBatch();
  }
  const r = await followJob(T("bRunning"), start.job);
  S.batch.loaded = false;
  if (!r) return renderBatch();
  setAudit(r);
  const res = r.results, ok = res.filter((x) => x.ok);
  res.filter((x) => x.ok).forEach((x) => delete B.opts[x.id]);
  await infoDlg(T("bDoneTitle"), `<p><b>${T("bDoneSum", ok.length, res.length)}</b></p>
    ${res.map((x) => x.ok ? `<section class="b-res"><h4>✓ ${esc(x.name)}</h4>
        <p class="hint">${T("convStats", x.stats)}</p><p class="hint">${T("convMem", mb(x.stats.before), mb(x.stats.after))} · ${esc(x.bsas.join(", "))}</p>
        ${Object.keys(x.renamed || {}).length ? `<p class="hint">${T("convRenamed")}: ${Object.entries(x.renamed).map(([n, o]) => `${esc(o)} → ${esc(n)}`).join(", ")}</p>` : ""}
        ${x.pointed?.length ? `<p class="hint">${T("bPointed", esc(x.pointed.join(", ")))}</p>` : ""}
        ${x.notes?.length ? `<details><summary>${T("bWarn", x.notes.length)}</summary><ul class="report">${x.notes.map((n) => `<li>${esc(n)}</li>`).join("")}</ul></details>` : ""}</section>`
      : `<section class="b-res bad"><h4>✗ ${esc(x.name)}</h4><p class="note warn">${esc(x.error)}</p></section>`).join("")}
    ${ok.length < res.length ? `<p class="hint">${T("bLeft")}</p>` : ""}`);
  renderBatch();
}

function convName(pl) { return S.conv.names[pl.name] || pl.suggested; }
// Plugin names are edited without their extension (like Rename in Mods): the
// box holds the stem, the extension sits next to it, and typing one anyway is fine.
const plExt = (n) => (/\.(esp|esm|esl)$/i.exec(n) || [""])[0];
const plStem = (n) => n.slice(0, n.length - plExt(n).length);
const plJoin = (typed, like) => { const t = typed.trim(); return !t || plExt(t) ? t : t + plExt(like); };
async function updateMaxEstimate() {
  const c = S.conv; if (!c) return;
  if (!c.max_size) { c.maxEst = null; return renderBudget(); }
  const r = await call("convert_estimate", c.preset, c.native && c.view.tools.sdk, c.max_size);
  if (r.ok) { c.maxEst = r; renderBudget(); }
}
function renderConvBody() {
  const c = S.conv, v = c.view, t = v.tools, cnt = v.counts;
  const native = c.native && t.sdk;
  const est = (p) => v.estimates[p][native ? "sdk" : "pc"];
  const toConvert = est(c.preset).convert, already = est(c.preset).switch;
  $("#cv-body").innerHTML = `
    <div class="ornament"></div>
    <h3>${T("budgetTitle")}</h3>
    <div class="budget" id="cv-budget"></div>
    <h3>${T("dietTitle")}</h3>
    <div class="presets">${PRESETS.map((p) => `
      <label class="preset ${c.preset === p ? "on" : ""}"><input type="radio" name="cv-preset" value="${p}" ${c.preset === p ? "checked" : ""}>
        <b>${T("preset" + p[0].toUpperCase() + p.slice(1))}</b><span>${T("preset" + p[0].toUpperCase() + p.slice(1) + "P")}</span>
        <em>${mb(est(p).before)} → ${mb(est(p).after)}</em></label>`).join("")}</div>
    <div class="opts">
      <label><input type="checkbox" id="cv-native" ${native ? "checked" : ""} ${t.sdk ? "" : "disabled"}> ${T("optNative")}</label>
      ${t.sdk ? "" : `<p class="hint">${T("optNativeOff")}</p>`}
      <label><input type="checkbox" id="cv-bc1" ${c.bc1 && native ? "checked" : ""} ${native ? "" : "disabled"}> ${T("optBc1")}</label>
      <p class="hint">${T("uiNote")}</p>
      <label>${T("cvMaxSize")} <select id="cv-max"><option value="">${T("cvMaxNone")}</option>${(v.options?.max_sizes || [256, 512, 1024, 2048, 4096]).map((m) => `<option value="${m}" ${String(c.max_size || "") === String(m) ? "selected" : ""}>${m >= 1024 ? m / 1024 + "K" : m}</option>`).join("")}</select></label>
      <p class="hint">${T("cvMaxHint")}</p>
      <label>${T("cvPacking")} <select id="cv-pack">${PACKINGS.map((k) => `<option value="${k}" ${(c.packing || "ini1") === k ? "selected" : ""}>${T("cvPack_" + k)}</option>`).join("")}</select></label>
      <p class="hint">${T("cvPackHint_" + (c.packing || "ini1"))}</p>
      <label><input type="checkbox" id="cv-compress" ${c.compress === false ? "" : "checked"}> ${T("cvCompress")}</label>
      <label><input type="checkbox" id="cv-keep" ${c.keep === false ? "" : "checked"}> ${T("cvKeep")}</label>
    </div>
    ${v.plugins.length ? `<h3>${T("pluginsTitle")}</h3>
    <table class="names"><tr><th>Plugin</th><th>${T("nameCol")}</th><th></th></tr>
      ${v.plugins.map((pl, i) => `<tr><td><div>${esc(pl.name)}</div>
          <div class="tags">${pl.reasons.map((r) => `<span class="tag">${T({ chars: "reasonChars", esl: "reasonEsl", blocked: "reasonBlocked", orphan: "reasonOrphan" }[r] || r)}</span>`).join("")}
          ${pl.missing.length ? `<span class="tag bad">${esc(T("needs", pl.missing.join(", ")))}</span>` : ""}</div></td>
        <td><div class="field"><input class="nm-in" data-i="${i}" value="${esc(plStem(convName(pl)))}" ${pl.locked ? "disabled" : ""} spellcheck="false"><span class="hint" style="align-self:center">${esc(plExt(convName(pl)))}</span></div></td>
        <td>${pl.locked ? "" : `<button class="ghost sm" data-short="${i}">${T("shorten")}</button>`}</td></tr>`).join("")}</table>
    <p class="hint">${T("renameNote")}</p>` : ""}
    <h3>${T("contentTitle")}</h3>
    <dl class="ledger">
      <div><dt>${T("cTex")}</dt><dd>${cnt.dds} <small>${T("cTexP", toConvert, already)}</small></dd></div>
      <div><dt>${T("cSnd")}</dt><dd>${v.sounds} <small>${T("cSndP", v.sounds_pc)}</small></dd></div>
      <div><dt>${T("cAnim")}</dt><dd>${cnt.hkx}</dd></div>
      <div><dt>${T("cMesh")}</dt><dd>${cnt.nif}</dd></div>
      <div><dt>${T("cScripts")}</dt><dd>${cnt.pex}</dd></div>
      <div><dt>${T("cDropped")}</dt><dd>${v.dropped}</dd></div>
    </dl>
    ${v.notes.length ? `<h3>${T("notes")}</h3>${v.notes.map((n) => `<p class="note ${n.level === "warn" ? "warn" : ""}">${esc(n.text)}</p>`).join("")}` : ""}
    <div class="cv-actions"><button class="primary" id="cv-go">${T("convertGo")}</button> <button class="ghost" id="cv-cancel">${T("convertCancel")}</button></div>`;
  $$('input[name="cv-preset"]').forEach((r) => r.addEventListener("change", () => { c.preset = r.value; renderConvBody(); }));
  $("#cv-native").addEventListener("change", (e) => { c.native = e.target.checked; renderConvBody(); });
  $("#cv-bc1").addEventListener("change", (e) => { c.bc1 = e.target.checked; renderBudget(); });
  $("#cv-pack").addEventListener("change", (e) => { c.packing = e.target.value; renderConvBody(); });
  $("#cv-compress").addEventListener("change", (e) => { c.compress = e.target.checked; });
  $("#cv-keep").addEventListener("change", (e) => { c.keep = e.target.checked; });
  $("#cv-max").addEventListener("change", (e) => { c.max_size = e.target.value ? +e.target.value : null; updateMaxEstimate(); });
  updateMaxEstimate();
  $$(".nm-in").forEach((inp) => inp.addEventListener("input", () => { const pl = v.plugins[+inp.dataset.i]; c.names[pl.name] = plJoin(inp.value, convName(pl)); renderBudget(); }));
  $$("[data-short]").forEach((b) => b.addEventListener("click", () => {
    const pl = v.plugins[+b.dataset.short]; c.names[pl.name] = pl.compact; $(`.nm-in[data-i="${b.dataset.short}"]`).value = plStem(pl.compact); renderBudget(); }));
  $("#cv-cancel").addEventListener("click", async () => { await call("convert_cancel"); S.conv = null; renderConvert(); });
  $("#cv-go").addEventListener("click", runConvert);
  renderBudget();
}
function renderBudget() {
  const c = S.conv, v = c.view, b = v.budget, native = c.native && v.tools.sdk;
  const utf8 = (s) => new TextEncoder().encode(s).length;
  const add = v.plugins.reduce((n, pl) => n + utf8(convName(pl)) + b.nl, 0);
  const e = (c.max_size && c.maxEst) || v.estimates[c.preset][native ? "sdk" : "pc"];
  const cap = (S.state.ram_cap || 0) * 1048576;
  const lim = b.ccc_limit;
  const cccTotal = b.ccc_now + add;
  const cccWarn = lim && cccTotal > lim ? T("overCcc") : (b.ccc_warn && cccTotal > b.ccc_warn ? T("nearCcc") : "");
  const go = $("#cv-go"); if (go) go.disabled = !!(lim && cccTotal > lim);
  const scaleC = lim || Math.max(cccTotal, 1);
  const texTotal = b.tex_pack + e.after, scaleT = Math.max(cap, texTotal, 1);
  $("#cv-budget").innerHTML = `
    <div class="brow"><div class="blbl">${lim ? T("cccLbl") : T("seList")}</div>
      <div class="bmeter magicka"><i style="width:${(100 * b.ccc_now) / scaleC}%"></i><i class="new" style="left:${(100 * b.ccc_now) / scaleC}%;width:${(100 * add) / scaleC}%"></i></div>
      <div class="bval ${cccWarn ? "bad" : ""}">${T("cccLine", b.ccc_now, add, lim)}${cccWarn ? ` · ${cccWarn}` : ""}</div></div>
    <div class="brow"><div class="blbl">${T("texPackLbl")}</div>
      <div class="bmeter stamina"><i style="width:${(100 * b.tex_pack) / scaleT}%"></i><i class="new" style="left:${(100 * b.tex_pack) / scaleT}%;width:${(100 * e.after) / scaleT}%"></i>${cap ? `<b class="cap" style="left:${(100 * cap) / scaleT}%"></b>` : ""}</div>
      <div class="bval ${cap && texTotal > cap ? "bad" : ""}">${mb(b.tex_pack)} + ${mb(e.after)}${cap && texTotal > cap ? ` · ${T("overCap")}` : ""}</div></div>
    <div class="brow"><div class="blbl">${T("texCap")}</div>
      <div class="field cap-field"><input id="cv-cap" type="number" min="0" step="50" value="${S.state.ram_cap || ""}" placeholder="—"></div>
      <div class="bval hint">${T("modTex", mb(e.before), mb(e.after))}${native && c.bc1 ? ` ${T("bc1More")}` : ""}</div></div>
    <p class="hint">${T("texCapHint")}</p>`;
  $("#cv-cap").addEventListener("change", async (ev) => { S.state = await call("set_ram_cap", ev.target.value); renderBudget(); });
}
async function runConvert() {
  const c = S.conv;
  const opts = { preset: c.preset, sdk: c.native && c.view.tools.sdk, bc1: c.bc1 && c.native, names: {},
                 packing: c.packing || "ini1", compress: c.compress !== false, max_size: c.max_size || null, keep: c.keep !== false };
  c.view.plugins.forEach((pl) => (opts.names[pl.name] = convName(pl)));
  const r = await job(T("converting"), "convert_run", opts);
  if (!r) return;
  S.conv = null;
  setAudit(r);
  const res = r.result, rep = res.report;
  const ren = Object.entries(res.renamed || {});
  await infoDlg(T("convDone"), `
    <p>${T("convStats", res.stats)}</p>
    <p>${T("convMem", mb(res.stats.before), mb(res.stats.after))}</p>
    <h4>${T("convBsas")}</h4><ul class="report">${res.bsas.map((x) => `<li>${esc(x)}</li>`).join("")}</ul>
    ${res.kept ? `<p class="hint">${T("cvKept", esc(res.kept))}</p>` : ""}
    ${ren.length ? `<h4>${T("convRenamed")}</h4><ul class="report">${ren.map(([n, o]) => `<li>${esc(o)} → ${esc(n)}</li>`).join("")}</ul>` : ""}
    ${rep.list_added.length ? `<h4>${T("addedList")}</h4><ul class="report">${rep.list_added.map((x) => `<li>${esc(x)}</li>`).join("")}</ul>` : ""}
    ${rep.ini_added.length ? `<h4>${T("addedIni")}</h4><ul class="report">${rep.ini_added.map((x) => `<li>${esc(x.key)}: ${esc(x.bsa)}</li>`).join("")}</ul>` : ""}
    ${[...res.notes, ...rep.notes].length ? `<h4>${T("notes")}</h4><ul class="report">${[...res.notes, ...rep.notes].map((x) => `<li>${esc(x)}</li>`).join("")}</ul>` : ""}`);
  show(S.pack?.bench ? "mesa" : "mods");
}

// ------------------------------------------------------------------ helpers (v0.5)
function packChanged() { S.xfer = null; S.lib = null; S.lootView = null; S.batch = null; if (S.fomod?.item) S.fomod = null; (S.queue || []).forEach((q) => (q.pre = null)); }
const isArchive = (p) => /\.(zip|7z|rar|001)$/i.test(String(p || ""));
const homeBtn = () => (S.pack ? "" : `<button class="link back-home" data-home>${T("home")}</button>`);
function wireHome(root) { $$("[data-home]", root).forEach((b) => b.addEventListener("click", () => show("welcome"))); }
const baseName = (p) => String(p || "").replace(/[\\/]+$/, "").split(/[\\/]/).pop();
const pick2 = (pair) => (Array.isArray(pair) ? (LANG === "es" ? pair[1] ?? pair[0] : pair[0]) : pair);
function notesHtml(notes) {
  return (notes || []).map((n) => {
    const lvl = typeof n === "string" ? "info" : n.level;
    const txt = typeof n === "string" ? n : n.text ?? pick2([n.en, n.es]);
    return `<p class="note ${lvl === "warn" || lvl === "crit" ? "warn" : ""}">${esc(txt)}</p>`;
  }).join("");
}

// ------------------------------------------------------------------ welcome: first steps
async function renderFirstSteps() {
  const box = $("#first-steps"); if (!box) return;
  let items; try { items = (await call("setup_status")).items || []; } catch (e) { return; }
  // what's missing and what it turns off; the optional extras only count when they matter day to day
  const shown = items.filter((i) => !i.ok && (i.need !== "optional" || ["nvntexpkg", "vanilla", "rar"].includes(i.id)));
  const needed = shown.filter((i) => i.need !== "optional");
  box.innerHTML = `<details class="steps" ${needed.length ? "open" : ""}><summary>${T("homeSetup")} · ${shown.length ? T("homeSetupMiss", shown.length) : T("homeSetupOk")}</summary>
    ${shown.length ? `<ul class="checklist">${shown.map((i) => `<li class="todo"><span class="mark">○</span><div><b>${esc(setupName(i))}</b>
      <p>${esc(pick2(i.what))}</p><p class="lose"><b>${T("inLose")}</b> ${esc(pick2(i.lose))}</p></div></li>`).join("")}</ul>` : ""}
    <p><button class="link" id="fs-setup">${T("suLink")}</button> · <button class="link" id="fs-credits">${T("spShow")}</button></p></details>`;
  if (!box.isConnected) return;
  $("#fs-setup", box).addEventListener("click", () => show("setup"));
  $("#fs-credits", box).addEventListener("click", async () => showSplash(await call("ui_prefs")));
}

// ------------------------------------------------------------------ new pack: USSEP selector
async function renderUssepPick() {
  const box = $("#n-ussep"); if (!box) return;
  const info = await call("ussep_scan");
  const se = $('input[name="ed"]:checked')?.value === "SE";
  if (!info.variants || !info.variants.length) {
    box.innerHTML = `<p class="hint">${T("usMissing", esc(info.folder))}</p><input type="hidden" name="us" value="">`;
    return;
  }
  const cur = S.ussepPick ?? "";
  box.innerHTML = `<div class="radio-col">
      <label><input type="radio" name="us" value="" ${cur === "" ? "checked" : ""}> ${T("usNone")}</label>
      ${info.variants.map((v) => {
        const off = se && v.cc.length;
        return `<label class="${off ? "off" : ""}"><input type="radio" name="us" value="${esc(v.id)}" ${cur === v.id && !off ? "checked" : ""} ${off ? "disabled" : ""}>
          <b>${esc(v.id)}</b> <small>${v.cc.length ? esc(T("usNeeds", v.cc.join(", "))) : T("usBase")}</small></label>`; }).join("")}
    </div><p class="hint">${se ? T("usSe") : T("usHint")} · ${esc(info.folder)}</p>`;
  $$('input[name="us"]', box).forEach((r) => r.addEventListener("change", () => (S.ussepPick = r.value)));
}

// ------------------------------------------------------------------ add (intake queue)
S.queue = [];
async function addToQueue(paths) {
  paths = (paths || []).filter((p) => p && !S.queue.some((q) => q.path === p));
  if (!paths.length) return;
  const pr = await call("progress");
  if (pr && pr.busy) return toast(T("busyNow"), true);
  if (S.page !== "add") show("add");
  const res = await job(T("detecting"), "intake_detect", paths);
  if (!res) return;
  res.forEach((d) => S.queue.push({ path: d.path, det: d, pre: null, done: null }));
  renderAdd();
}
window.onDroppedPaths = (paths) => { $("#dropveil").hidden = true; addToQueue(paths); };

function renderAdd() {
  const el = $("#p-add");
  el.innerHTML = `${homeBtn()}
    <h2>${T("addTitle")}</h2>
    <p class="sub">${T("addSub")}</p>
    <div class="dropzone" id="dz"><div>${T("dropHere")}</div>
      <div class="field">
        ${hasWebview() ? `<button class="ghost" id="a-files">${T("pickFiles")}</button><button class="ghost" id="a-folder">${T("pickFolder")}</button>` : ""}
        <input id="a-path" placeholder="${esc(T("pathsPh"))}" spellcheck="false"><button class="primary" id="a-add">${T("queueAdd")}</button>
      </div></div>
    ${S.queue.some((q) => q.done) ? `<button class="link" id="a-clear">${T("clearDone")}</button>` : ""}
    ${S.pack && convertible().length > 1 ? `<button class="primary sm" id="a-batch">${T("bQueueGo", convertible().length)}</button>` : ""}
    <div class="queue">${S.queue.length ? S.queue.map(queueCard).join("") : `<p class="empty">${T("queueEmpty")}</p>`}</div>`;
  wireHome(el);
  $("#a-files")?.addEventListener("click", async () => addToQueue(await call("pick_files")));
  $("#a-folder")?.addEventListener("click", async () => { const p = await call("pick_folder"); if (p) addToQueue([p]); });
  $("#a-add").addEventListener("click", () => { const p = $("#a-path").value.trim(); if (p) addToQueue([p]); });
  $("#a-path").addEventListener("keydown", (e) => { if (e.key === "Enter" && e.target.value.trim()) addToQueue([e.target.value.trim()]); });
  $("#a-clear")?.addEventListener("click", () => { S.queue = S.queue.filter((q) => !q.done); renderAdd(); });
  $("#a-batch")?.addEventListener("click", () => {
    const qs = convertible();
    S.batchPrefill = qs.map((q) => q.path); S.queue = S.queue.filter((q) => !qs.includes(q));
    S.convMode = "batch"; show("convertir");
  });
  $$("[data-q]", el).forEach((b) => b.addEventListener("click", () => queueAction(+b.dataset.i, b.dataset.q)));
  $$("[data-nxpage]", el).forEach((b) => b.addEventListener("click", () => call("open_url", b.dataset.nxpage)));
  fillQueueNexus(el);
}
function convertible() { return (S.queue || []).filter((q) => !q.done && ["pc-mod", "fomod", "mixed"].includes(q.det?.kind)); }
function queueCard(q, i) {
  const d = q.det, k = d.kind, need = !S.pack;
  const btn = (act, label, primary = false, dis = false) => `<button class="${primary ? "primary" : "ghost"} sm" data-q="${act}" data-i="${i}" ${dis ? "disabled" : ""}>${label}</button>`;
  let acts = "";
  if (q.done) acts = `<span class="done-tag">${esc(q.done)}</span>` + (k === "modpack" && q.libPath
    ? btn("open", T("qOpen")) + (S.pack ? btn("bring", T("qBring")) : "") : "");
  else if (k === "modpack") acts = btn("newproject", T("qNewProject"), true) + (S.pack && !S.pack.bench ? btn("bring", T("qBring")) : "");
  else if (k === "switch-mod") {
    acts = q.pre ? (q.pre.recommend === "add" ? btn("add", T("qAddAsIs"), true, need) + btn("convert", T("qConvert"), false, need)
                                              : btn("convert", T("qConvert"), true, need) + btn("add", T("qAddAsIs"), false, need))
                 : btn("check", T("qCheck"), true, need) + btn("add", T("qAddAsIs"), false, need);
    acts += btn("keep", T("qKeep"));
  } else if (k === "pc-mod" || k === "fomod" || k === "mixed") acts = btn("convert", T("qConvert"), true, need) + btn("keep", T("qKeep"));
  if (!q.done && !q.nexus && S.state?.nexus_key && isArchive(q.path) && k !== "modpack") acts += btn("identify", T("nxIdentify"));
  if (!q.done && (k === "switch-mod" || k === "mixed")) acts += btn("compare", T("cmpGo"));
  const ev = d.evidence || {};
  const fromPack = packOf(q.path);
  if (fromPack && !q.done && S.pack && fromPack.toLowerCase() !== (S.pack.root || "").toLowerCase()) acts = btn("frompack", T("qFromPack"), true) + acts;
  const facts = [(ev.plugins || []).length ? (ev.plugins || []).slice(0, 4).join(", ") + ((ev.plugins || []).length > 4 ? "…" : "") : "",
                 (ev.bsas || []).length ? `${ev.bsas.length} BSA` : "", ev.bytes ? mb(ev.bytes) : ""].filter(Boolean).join(" · ");
  const pre = q.pre ? `${notesHtml(q.pre.notes)}<p class="hint"><b>${q.pre.recommend === "add" ? T("qRecAdd") : T("qRecConvert")}</b></p>` : "";
  return `<div class="qcard k-${esc(k)} ${q.done ? "done" : ""}">
    <div class="qhead"><span class="kind">${T("kind")[k] || esc(k)}</span><b>${esc(baseName(q.path))}</b><span class="nx-slot" data-q-slot="${i}"></span>
      <button class="link rm" data-q="remove" data-i="${i}" title="${T("qRemove")}">✕</button></div>
    <div class="hint">${esc(q.path)}</div>
    ${q.nexus ? `<div class="nx-tag">Nexus: <button class="link" data-nxpage="${esc(q.nexus.page)}">${esc(q.nexus.name || "")}</button>${q.nexus.version ? ` · v${esc(q.nexus.version)}` : ""}${q.nexus.file_name ? ` · ${esc(q.nexus.file_name)}` : ""}</div>` : ""}
    <p>${esc(d.summary || "")}</p>${facts ? `<div class="files">${esc(facts)}</div>` : ""}
    ${(d.bundle || []).length > 1 ? `<div class="files">${T("qBundle")}: ${esc(d.bundle.join(" + "))}</div>` : ""}
    ${fromPack && !q.done ? `<p class="hint">${T("qFromPackHint", esc(fromPack.split(/[\\/]/).pop()))}</p>` : ""}
    ${notesHtml(d.notes)}${pre}
    ${need && k !== "modpack" && k !== "unknown" && !q.done ? `<p class="hint">${T("qNeedPack")}</p>` : ""}
    <div class="qacts">${acts}</div></div>`;
}
async function queueAction(i, act) {
  const q = S.queue[i]; if (!q) return;
  if (act === "remove") { S.queue.splice(i, 1); return renderAdd(); }
  if (act === "open") return openPack(q.libPath || q.path);
  if (act === "convert") { S.convPrefill = q.path; S.queue.splice(i, 1); return show("convertir"); }
  if (act === "bring") return startTransfer(q.libPath || q.path);
  if (act === "newproject") { S.newProj = "pack"; S.newProjSrc = q.path; S.newProjName = ""; return show("new"); }
  if (act === "frompack") return startTransfer(packOf(q.path), [...(q.det.bundle || []), baseName(q.path)]);
  if (act === "import" || act === "keep") {
    const r = await job(T("working"), "library_import", q.path, act === "import" ? "modpack" : "mod");
    if (!r) return;
    q.done = T("qImported", r.path || r.name || ""); q.libPath = r.path;
    if (act === "import" && r.notes && r.notes.length) toast(r.notes.map(pick2).join(" "));
    return renderAdd();
  }
  if (act === "compare") return compareWithOriginal(q.path);
  if (act === "identify") {
    const r = await job(T("working"), "nexus_identify", q.path);
    if (!r) return;
    if (r.found) { q.nexus = r.nexus; toast(T("nxFound", r.nexus.name)); } else toast(r.matches.length ? T("nxMany", r.matches.length) : T("nxNotFound"), !r.matches.length);
    return renderAdd();
  }
  if (act === "check") {
    const r = await job(T("working"), "precheck", q.path);
    if (r) { q.pre = r; renderAdd(); }
    return;
  }
  if (act === "add") {
    const r = await job(T("working"), "add_mod", q.path);
    if (!r) return;
    setAudit(r); q.done = T("qDone");
    const rep = r.report;
    await infoDlg(T("addedTitle"), reportHtml(rep));
    renderAdd();
  }
}
function reportHtml(rep) {
  return `${rep.added.length ? `<h4>${T("addedFiles")}</h4><ul class="report">${rep.added.map((x) => `<li>${esc(x)}</li>`).join("")}</ul>` : ""}
    ${rep.list_added.length ? `<h4>${T("addedList")}</h4><ul class="report">${rep.list_added.map((x) => `<li>${esc(x)}</li>`).join("")}</ul>` : ""}
    ${rep.ini_added.length ? `<h4>${T("addedIni")}</h4><ul class="report">${rep.ini_added.map((x) => `<li>${esc(x.key)}: ${esc(x.bsa)}</li>`).join("")}</ul>` : ""}
    ${rep.notes.length ? `<h4>${T("notes")}</h4><ul class="report">${rep.notes.map((x) => `<li>${esc(x)}</li>`).join("")}</ul>` : ""}`;
}

// window-level drag feedback (the drop itself is handled by Python, which knows the full paths)
let dragDepth = 0;
const hasFiles = (e) => [...(e.dataTransfer?.types || [])].includes("Files");
document.addEventListener("dragenter", (e) => { if (!hasFiles(e)) return; dragDepth++; $("#dropveil").hidden = false; });
document.addEventListener("dragleave", (e) => { if (!hasFiles(e)) return; if (--dragDepth <= 0) { dragDepth = 0; $("#dropveil").hidden = true; } });
document.addEventListener("dragover", (e) => { if (hasFiles(e)) e.preventDefault(); });
document.addEventListener("drop", (e) => {
  if (!hasFiles(e)) return;
  e.preventDefault(); dragDepth = 0; $("#dropveil").hidden = true;
  if (!hasWebview()) toast(T("dropBrowser"));
});

// ------------------------------------------------------------------ library
async function renderLibrary(refresh = true) {
  const el = $("#p-library");
  if (S.xfer && S.xfer.pack !== S.pack?.root) S.xfer = null;
  if (S.xfer) return renderTransfer();
  if (S.libTab === "catalog") return renderCatalog(false);
  if (refresh || !S.lib) { const r = await job(T("libReading"), "library_list"); if (!r) return; S.lib = r; }
  const L = S.lib, packs = L.rows.filter((r) => r.kind === "pack"), mods = L.rows.filter((r) => r.kind !== "pack");
  const cur = S.pack?.root || "";
  const row = (r) => {
    const h = r.health || {}, st = r.missing ? "error" : h.status || "warn";
    const isCur = cur && r.path.toLowerCase() === cur.toLowerCase();
    const facts = r.kind === "pack" && h.mode ? [h.mode, `${h.plugins} plugins`, `${h.bsas} BSA`, h.ccc_bytes ? `.ccc ${h.ccc_bytes} B` : ""].filter(Boolean).join(" · ")
                : h.kind ? T("kind")[h.kind] || h.kind : "";
    let acts = "";
    if (!r.missing) {
      if (r.kind === "pack") acts = (isCur ? "" : `<button class="ghost sm" data-lib="open" data-p="${esc(r.path)}">${T("libOpen")}</button>`)
        + (r.draft ? "" : `<button class="ghost sm" data-lib="draft" data-p="${esc(r.path)}" data-n="${esc(r.name)}" title="${esc(T("drStartTip"))}">${T("drStart")}</button>`)
        + (S.pack && !isCur ? `<button class="primary sm" data-lib="bring" data-p="${esc(r.path)}">${S.pack.bench ? T("libBringBench") : T("libBring")}</button>` : "");
      else if (S.pack && !S.pack.bench) acts = `<button class="primary sm" data-lib="add" data-p="${esc(r.path)}">${T("libAddPack")}</button>`;
      if (r.kind === "mod") acts += `<button class="ghost sm" data-lib="edit" data-p="${esc(r.path)}" data-n="${esc(r.name)}">${T("libEditWs")}</button>`;
      acts += `<button class="folder-link" data-lib="dir" data-p="${esc(r.path)}">${T("openFolder")}</button>`;
    }
    acts += `<button class="ghost sm danger" title="${esc(r.owned ? T("libDeleteTip") : T("libForgetTip"))}" data-lib="forget" data-own="${r.owned ? 1 : 0}" data-p="${esc(r.path)}" data-n="${esc(r.name)}">${r.owned ? T("libDelete") : T("libForget")}</button>`;
    return `<div class="librow h-${st}"><span class="tick"></span>
      <div><div class="t"><b>${esc(r.name)}</b> <span class="pill p-${st}">${r.missing ? T("libMissing") : T("health")[st] || st}</span>${r.converted ? ` <span class="pill p-conv">${T("libConverted")}</span>` : ""}${r.draft ? ` <span class="pill p-draft">${T("drBadge")}</span>` : ""}</div>
        <div class="files">${esc(facts)}${r.size ? ` · ${mb(r.size)}` : ""}${r.external ? ` · ${T("libExternal")}` : ""}</div>
        ${h.summary ? `<div class="hint">${esc(pick2(h.summary))}</div>` : ""}<div class="hint">${esc(r.path)}</div></div>
      <div class="act">${acts}</div></div>`;
  };
  el.innerHTML = `${homeBtn()}
    <h2>${T("libTitle")}</h2>
    ${tabsHtml("list")}
    <p class="sub">${T("libSub", esc(L.root))} <button class="folder-link" id="lib-dir">${T("openFolder")}</button></p>
    ${L.legacy ? `<p class="note">${T("libLegacyHint", L.legacy)} <button class="link" data-home>${T("home")}</button></p>` : ""}
    <p class="hint">${T("libLegend")}</p>
    <div class="doctor-head">${hasWebview() ? `<button class="primary" id="l-import">${T("libImport")}</button>` : ""}
      <div class="field grow"><input id="l-path" placeholder="${esc(T("pathsPh"))}" spellcheck="false"><button class="ghost" id="l-add">${T("import")}</button></div>
      <button class="ghost" id="l-refresh">${T("libRefresh")}</button></div>
    ${L.rows.length ? `${packs.length ? `<h3>${T("libPacks")} <small>${packs.length}</small></h3>${packs.map(row).join("")}` : ""}
      ${mods.length ? `<h3>${T("libMods")} <small>${mods.length}</small></h3>${mods.map(row).join("")}` : ""}` : `<p class="empty">${T("libEmpty")}</p>`}`;
  wireHome(el); wireTabs(el);
  $("#lib-dir")?.addEventListener("click", () => openFolder(L.root));
  const imp = async (paths) => {
    for (const p of paths || []) { const r = await job(T("working"), "library_import", p, ""); if (!r) break; }
    renderLibrary();
  };
  $("#l-import")?.addEventListener("click", async () => imp(await call("pick_files")));
  $("#l-add").addEventListener("click", () => { const p = $("#l-path").value.trim(); if (p) imp([p]); });
  $("#l-refresh").addEventListener("click", () => renderLibrary());
  $$("[data-lib]", el).forEach((b) => b.addEventListener("click", async () => {
    const p = b.dataset.p, a = b.dataset.lib;
    if (a === "open") return openPack(p);
    if (a === "draft") return startDraftFrom(p, b.dataset.n);
    if (a === "dir") return openFolder(/\.(zip|7z|rar)$/i.test(p) ? p.replace(/[\\/][^\\/]+$/, "") : p);
    if (a === "edit") {
      const r = await job(T("wsPreparing"), "workshop_new", "edit", String(b.dataset.n).replace(/\.(zip|7z)$/i, ""), "AE", [p]);
      if (!r) return;
      S.firstCrit = null; packChanged(); setAudit(r);
      const bad = (r.reports || []).filter((x) => !x.ok);
      if (bad.length) await infoDlg(T("wsSomeOut"), `<ul class="report">${bad.map((x) => `<li>${esc(pick2(x.text))}</li>`).join("")}</ul><p class="hint">${T("wsPcHint")}</p>`);
      return show("mesa");
    }
    if (a === "bring") return startTransfer(p);
    if (a === "add") return addToQueue([p]);
    if (a === "forget") {
      const own = b.dataset.own === "1";
      if (!(await confirmDlg(own ? T("libDelete") : T("libForget"), `<p>${own ? T("libDeleteBody", b.dataset.n) : T("libForgetBody", b.dataset.n)}</p>`, own ? T("libDelete") : T("libForget")))) return;
      const r = await call("library_forget", p);
      if (r && r.ok === false) toast(r.error, true);
      renderLibrary();
    }
  }));
}

// ------------------------------------------------------------------ bring mods from another pack
function packOf(p) {
  // a file picked from inside another modpack's Data folder
  const m = String(p || "").match(/^(.*?)[\\/](?:contents[\\/])?01000A10041EA000[\\/]romfs[\\/]Data[\\/]/i);
  return m ? m[1] : null;
}
// bring mods from a modpack: a folder, an archive or another project
async function pickPackSource() {
  let p = null;
  if (hasWebview()) {
    const c = await choiceDlg(T("pjFromPack"), `<p>${T("pjFromPackP")}</p>`, [
      { id: "dir", label: T("npFolder"), primary: true }, { id: "arc", label: T("npArchive") }, { id: "pj", label: T("pjAnother") }]);
    if (!c) return;
    if (c === "pj") {
      const r = await call("projects");
      const others = (r.projects || []).filter((x) => x.path !== S.pack?.root);
      if (!others.length) return toast(T("pjNoOthers"), true);
      const pick = await choiceDlg(T("pjAnother"), "", others.map((x, i) => ({ id: String(i), label: x.name, hint: `${x.edition} · ${T("pjMods", x.mods, x.off)}` })));
      if (pick === "") return;
      p = others[+pick].path;
    } else p = await call(c === "dir" ? "pick_folder" : "pick_archive");
  } else p = await askText(T("pjFromPack"), T("npSrc"), "");
  if (p) startTransfer(p);
}
async function startTransfer(src, preselect = []) {
  if (!S.pack) return toast(T("needPack"), true);
  const r = await job(T("reading"), "transfer_list", src);
  if (!r) return;
  const want = new Set(preselect.map((x) => String(x).toLowerCase()));
  const sel = new Set(r.units.filter((u) => [...u.plugins, ...u.bsas].some((f) => want.has(f.toLowerCase()))).map((u) => u.id));
  const units = [...r.units.filter((u) => sel.has(u.id)), ...r.units.filter((u) => !sel.has(u.id))];
  S.xfer = { src, pack: S.pack.root, name: r.name, mode: r.mode, units, sel, filter: "", plan: null };
  show("library");
}
function renderTransfer() {
  if (!S.pack) { S.xfer = null; return renderLibrary(false); }
  const x = S.xfer, el = $("#p-library");
  if (x.plan) return renderTransferPlan();
  const f = x.filter.toLowerCase();
  const sort = S.xferSort || "name";
  const vis = x.units.filter((u) => !f || u.name.toLowerCase().includes(f) || u.plugins.some((p) => p.toLowerCase().includes(f)) || u.bsas.some((b) => b.toLowerCase().includes(f)));
  if (sort === "name") vis.sort((a, b) => a.name.localeCompare(b.name, undefined, { sensitivity: "base", numeric: true }));
  else if (sort === "size") vis.sort((a, b) => (b.size || 0) - (a.size || 0));
  el.innerHTML = `
    <button class="link back-home" id="x-back">${T("xBack")}</button>
    <h2>${esc(T("xTitle", x.name, S.pack.name))}</h2>
    <p class="sub">${T("xSub")}</p>
    <div class="doctor-head"><div class="field grow"><input id="x-filter" placeholder="${esc(T("xFilter"))}" value="${esc(x.filter)}" spellcheck="false"></div>
      <select id="x-sort" title="${esc(T("xSort"))}">${["name", "order", "size"].map((k) => `<option value="${k}" ${sort === k ? "selected" : ""}>${T("xSorts")[k]}</option>`).join("")}</select>
      <span class="hint" id="x-count">${T("xSelected", x.sel.size)}</span>
      <button class="primary" id="x-plan" ${x.sel.size ? "" : "disabled"}>${T("xPlan")}</button></div>
    <div class="units">${vis.map((u) => `<label class="unit ${x.sel.has(u.id) ? "on" : ""}">
        <input type="checkbox" data-u="${esc(u.id)}" ${x.sel.has(u.id) ? "checked" : ""}>
        <div><div class="t"><b>${esc(u.name)}</b> <span class="src">${T("xKinds")[u.kind] || esc(u.kind)}</span>${u.light ? ` <span class="src">ESL</span>` : ""}</div>
          <div class="files">${esc([...u.plugins, ...u.bsas].join(" · "))}</div>
          ${u.masters.length ? `<div class="hint">Masters: ${esc(u.masters.join(", "))}</div>` : ""}
          ${u.flags.map((fl) => `<div class="hint flag">${esc(fl.text)}</div>`).join("")}</div>
        <div class="risk">${mb(u.size || 0)}${u.tex_bytes ? `<br><small>${T("tex")} ${mb(u.tex_bytes)}</small>` : ""}</div></label>`).join("")}</div>`;
  $("#x-back").addEventListener("click", () => { S.xfer = null; renderLibrary(false); });
  $("#x-sort").addEventListener("change", (e) => { S.xferSort = e.target.value; renderTransfer(); });
  $("#x-filter").addEventListener("input", (e) => { x.filter = e.target.value; const pos = e.target.selectionStart; renderTransfer(); const i = $("#x-filter"); i.focus(); i.setSelectionRange(pos, pos); });
  $$("[data-u]", el).forEach((c) => c.addEventListener("change", () => {
    c.checked ? x.sel.add(c.dataset.u) : x.sel.delete(c.dataset.u);
    c.closest(".unit").classList.toggle("on", c.checked);
    $("#x-count").textContent = T("xSelected", x.sel.size); $("#x-plan").disabled = !x.sel.size;
  }));
  $("#x-plan").addEventListener("click", async () => {
    const p = await job(T("working"), "transfer_plan", x.src, [...x.sel]);
    if (p) { x.plan = p; renderTransfer(); }
  });
}
function renderTransferPlan() {
  const x = S.xfer, p = x.plan, b = p.budget || {}, el = $("#p-library");
  const li = (arr, fn) => arr.length ? `<ul class="report">${arr.map(fn).join("")}</ul>` : "";
  el.innerHTML = `
    <button class="link back-home" id="x-back">${T("xBack")}</button>
    <h2>${T("xPlanTitle")}</h2>
    <p class="sub">${esc(T("xTitle", p.src, p.dst))}</p>
    <h3>${T("xUnits")} <small>${p.units.length}</small></h3>
    ${p.units.length ? li(p.units, (u) => `<li><b>${esc(u.name)}</b> <span class="src">${T("xWhy")[u.reason] || esc(u.reason)}</span>
        ${u.needed_by.length ? ` <small>${esc(T("xNeededBy", u.needed_by.join(", ")))}</small>` : ""}
        ${u.reason_text ? `<br><small>${esc(u.reason_text)}</small>` : ""}
        <br><small>${esc([...u.plugins.map((n) => u.target[n] && u.target[n] !== n ? `${n} → ${u.target[n]}` : n), ...u.bsas].join(" · "))}</small></li>`) : `<p class="empty">${T("xNothing")}</p>`}
    ${p.skipped.length ? `<h3>${T("xSkipped")}</h3>${li(p.skipped, (s) => `<li><b>${esc(s.name)}</b>: ${esc(s.reason)}</li>`)}` : ""}
    ${p.refused.length ? `<h3>${T("xRefused")}</h3>${li(p.refused, (s) => `<li><b>${esc(s.name)}</b>: ${esc(s.reason)}</li>`)}` : ""}
    ${p.missing_masters.length ? `<h3>${T("xMissing")}</h3>${li(p.missing_masters, (m) => `<li>${esc(m.plugin)} → ${esc(m.master)}</li>`)}` : ""}
    <h3>${T("xBudget")}</h3>
    <dl class="ledger">
      <div><dt>.ccc</dt><dd class="${b.ccc_over ? "bad" : ""}">${T("xCcc", b.ccc_before ?? 0, b.ccc_after ?? 0, b.ccc_limit)}</dd></div>
      <div><dt>${T("tex")}</dt><dd>${T("xTex", mb(b.tex_dst || 0), mb(b.tex_added || 0))}</dd></div>
      <div><dt>${T("files")}</dt><dd>${T("xBytes", mb(b.bytes_added || 0))}</dd></div>
    </dl>
    ${p.notes.length ? `<h3>${T("notes")}</h3>${p.notes.map((n) => `<p class="note">${esc(n)}</p>`).join("")}` : ""}
    ${p.errors.length ? `<h3>${T("xErrors")}</h3>${p.errors.map((n) => `<p class="note warn">${esc(n)}</p>`).join("")}` : ""}
    <div class="cv-actions"><button class="primary" id="x-go" ${p.ok && !b.ccc_over ? "" : "disabled"}>${T("xGo")}</button>
      <button class="ghost" id="x-back2">${T("xBack")}</button></div>`;
  const back = () => { x.plan = null; renderTransfer(); };
  $("#x-back").addEventListener("click", back); $("#x-back2").addEventListener("click", back);
  $("#x-go").addEventListener("click", async () => {
    const r = await job(T("working"), "transfer_apply");
    if (!r) return;
    setAudit(r); S.xfer = null;
    const o = r.result;
    await infoDlg(T("xDoneTitle"), `
      ${o.added?.length ? `<h4>${T("addedFiles")}</h4><ul class="report">${o.added.map((x2) => `<li>${esc(x2)}</li>`).join("")}</ul>` : ""}
      ${o.safe_renamed?.length ? `<h4>${T("xSafeNames")}</h4><ul class="report">${o.safe_renamed.map(([a, b]) => `<li>${esc(a)} → ${esc(b)}</li>`).join("")}</ul>` : ""}
      ${o.list_added?.length ? `<h4>${T("addedList")}</h4><ul class="report">${o.list_added.map((x2) => `<li>${esc(x2)}</li>`).join("")}</ul>` : ""}
      ${o.notes?.length ? `<h4>${T("notes")}</h4><ul class="report">${o.notes.map((x2) => `<li>${esc(x2)}</li>`).join("")}</ul>` : ""}`);
    enterPack("mods");
  });
}

// ------------------------------------------------------------------ load order: LOOT
async function lootSuggest() {
  const r = await job(T("working"), "loot_suggest");
  if (!r) return;
  r._pack = S.pack?.root; S.lootView = r; S.lootPick = {};
  renderLootPanel();
}
function groupSelect(name, cur, guess, r) {
  const fr = r.friendly.map((g) => g.group);
  const opt = (g, label) => `<option value="${esc(g)}" ${g === cur ? "selected" : ""}>${esc(label)}${g === guess ? ` ${T("lootGuessMark")}` : ""}</option>`;
  const known = cur && (fr.includes(cur) || r.all_groups.includes(cur));
  return `<select data-cls="${esc(name)}">
    <option value="" ${cur ? "" : "selected"}>${T("lootNoChoice")}</option>
    ${cur && !known ? `<option value="${esc(cur)}" selected>${esc(cur)} ${T("lootGone")}</option>` : ""}
    <optgroup label="${esc(T("lootCommon"))}">${r.friendly.map((g) => opt(g.group, g.label)).join("")}</optgroup>
    <optgroup label="${esc(T("lootAllGroups"))}">${r.all_groups.filter((g) => !fr.includes(g)).map((g) => opt(g, g)).join("")}</optgroup></select>`;
}
function renderLootPanel() {
  const r = S.lootView, box = $("#loot-panel");
  if (!r || !box) return;
  if (r._pack !== S.pack?.root) { S.lootView = null; box.innerHTML = ""; return; }
  const notes = Object.entries(r.notes || {}).flatMap(([pl, ns]) => ns.map((n) => `<li><b>${esc(pl)}</b>: ${esc(n.text)}</li>`));
  const merges = Object.entries(r.merges || {});
  const chosen = Object.entries(r.chosen || {});
  const help = r.friendly.map((g) => `<li><b>${esc(g.label)}</b>: ${esc(g.help)}</li>`).join("");
  box.innerHTML = `<div class="loot">
    <div class="loot-head"><h3>${T("lootTitle")}</h3><button class="link" id="loot-close">✕</button></div>
    <p class="hint">${T("lootHint")}${r.age_days != null ? ` ${T("lootAge", r.age_days)}` : ""}</p>
    ${r.changed ? `<p><b>${T("lootMoves", r.moves.length)}</b></p><ul class="report">${r.moves.map((m) => `<li><b>${esc(m.name)}</b> ${m.from} → ${m.to}<br><small>${esc(m.why)}</small></li>`).join("")}</ul>` : `<p>${T("lootSame")}</p>`}
    <div class="cv-actions">${r.changed ? `<button class="primary" id="loot-use">${T("lootUse")}</button>` : ""}</div>
    ${r.duplicates.length ? `<h4>${T("lootDupTitle")}</h4>${r.duplicates.map(([a, m]) => `<p class="note warn">${T("lootDup", esc(a), esc(m))}</p>`).join("")}` : ""}
    ${merges.length ? `<h4>${T("lootMergeTitle")}</h4>${merges.map(([m, comps]) => `<p class="note">${T("lootMerge", esc(m), comps.length)}<br><small>${esc(comps.join(", "))}</small>
        ${Object.entries(r.dummies).filter(([, v]) => v === m).length ? `<br><small>${T("lootDummies", esc(Object.entries(r.dummies).filter(([, v]) => v === m).map(([k]) => k).join(", ")))}</small>` : ""}</p>`).join("")}` : ""}
    ${r.unknown.length ? `<h4>${T("lootUnknownTitle", r.unknown.length)}</h4>
      <p class="hint">${T("lootUnknownP")}</p>
      <details class="more"><summary>${T("lootWhatGroups")}</summary><ul class="report">${help}</ul></details>
      <table class="cls"><tr><th>Plugin</th><th>${T("lootCategory")}</th></tr>
      ${r.unknown.map((u) => `<tr><td><b>${esc(u.name)}</b><br><small>${esc(u.why)}</small></td>
        <td>${groupSelect(u.name, S.lootPick[u.name] ?? u.guess, u.guess, r)}</td></tr>`).join("")}</table>
      <div class="cv-actions"><button class="primary" id="loot-save">${T("lootSave")}</button>
        <button class="ghost" id="loot-save-all" title="${esc(T("lootSaveAllTip"))}">${T("lootSaveAll")}</button></div>` : ""}
    ${chosen.length ? `<details class="more"><summary>${T("lootChosen", chosen.length)}</summary>
      <table class="cls">${chosen.map(([n, c]) => `<tr><td>${esc(n)}</td><td>${groupSelect(n, c.group, "", r)}</td></tr>`).join("")}</table>
      <div class="cv-actions"><button class="ghost" id="loot-save2">${T("lootSave")}</button></div></details>` : ""}
    ${r.warnings.length ? `<h4>${T("lootWarn")}</h4><ul class="report">${r.warnings.map((w) => `<li>${esc(w)}</li>`).join("")}</ul>` : ""}
    ${notes.length ? `<details class="more"><summary>${T("lootNotes")} (${notes.length})</summary><ul class="report">${notes.join("")}</ul></details>` : ""}
  </div>`;
  $("#loot-close").addEventListener("click", () => { S.lootView = null; box.innerHTML = ""; });
  $$("select[data-cls]", box).forEach((sel) => sel.addEventListener("change", () => (S.lootPick[sel.dataset.cls] = sel.value)));
  const save = async (all = false) => {
    const choices = {};
    $$("select[data-cls]", box).forEach((sel) => {
      const n = sel.dataset.cls, prev = (r.chosen || {})[n];
      const touched = n in S.lootPick || all;
      if (touched && (sel.value || prev) && sel.value !== (prev ? prev.group : "")) choices[n] = { group: sel.value };
    });
    if (!Object.keys(choices).length) return toast(T("lootNothingPicked"));
    const v = await job(T("working"), "loot_classify", choices);
    if (!v) return;
    setAudit(v); v._pack = S.pack?.root; S.lootView = v; S.lootPick = {}; toast(T("lootSaved")); renderLootPanel();
  };
  $("#loot-save")?.addEventListener("click", () => save(false));
  $("#loot-save-all")?.addEventListener("click", () => save(true));
  $("#loot-save2")?.addEventListener("click", () => save(false));
  $("#loot-use")?.addEventListener("click", async () => {
    const a = await call("loot_apply");
    if (!a.ok) return toast(a.error, true);
    S.lootView = null; setAudit(a); toast(T("orderSaved")); renderOrder();
  });
}

// ------------------------------------------------------------------ mods: conflicts
async function showConflicts() {
  const r = await job(T("working"), "conflicts");
  if (!r) return;
  const s = r.stats || {};
  const body = !r.pairs.length ? `<p>${T("cfNone")}</p>` : `
    <p>${T("cfStats", s)}${s.identical ? ` ${T("cfIdentical", s.identical)}` : ""}</p>
    ${r.dead.length ? `<h4>${T("cfDead")}</h4><ul class="report">${r.dead.map((d) => `<li>${T("cfDeadP", d.bsa, d.winners.join(", "))} <small>${d.files} · ${mb(d.bytes)}</small></li>`).join("")}</ul>` : ""}
    <h4>${T("cfPairs")}</h4><ul class="report">${r.pairs.slice(0, 40).map((p) => `<li>${T("cfPair", p.winner, p.loser, p.count)} <small>${mb(p.bytes)}</small>
      ${p.examples.length ? `<br><small>${esc(p.examples.join(", "))}</small>` : ""}</li>`).join("")}</ul>
    ${r.unloaded.length ? `<h4>${T("cfUnloaded")}</h4><ul class="report">${r.unloaded.map((u) => `<li>${esc(u)}</li>`).join("")}</ul>` : ""}`;
  infoDlg(T("cfTitle"), body);
}

// ------------------------------------------------------------------ SD (sync)
function renderSD() {
  const crit = S.audit.findings.filter((f) => f.severity === "critico").length;
  $("#p-sd").innerHTML = `
    <h2>${T("nav.sd")}</h2>
    <p class="sub">${T("sdSub")}</p>
    ${S.pack.project ? `<p class="note">${T("sdProject")}</p>` : ""}
    ${crit ? `<p class="note">${T("sdCrit", crit)}</p>` : ""}
    <div class="open-row"><label for="sd-in">${T("sdDrive")}</label>
      <div class="field"><input id="sd-in" placeholder="E:\\" spellcheck="false" value="${esc(S.sdLast || S.pack.project?.last_sd_path || "")}">${hasWebview() ? `<button class="ghost" id="sd-browse">${T("browse")}</button>` : ""}<button class="primary" id="sd-plan">${T("sdPlan")}</button></div>
      <p class="hint">${T("sdHint")}</p>
      <p class="note">${T("sdHow")}</p></div>
    <div id="sd-body"></div>
    ${S.pack.project ? "" : `<h3>${T("importTitle")}</h3>
    <div class="open-row"><div class="field"><input id="imp-sd" placeholder="${esc(T("importSd"))}"><input id="imp-dest" placeholder="${esc(T("importDest"))}"><button class="ghost" id="imp-go">${T("import")}</button></div></div>`}`;
  $("#sd-browse")?.addEventListener("click", async () => { const p = await call("pick_folder"); if (p) $("#sd-in").value = p; });
  $("#sd-plan").addEventListener("click", async () => {
    const sd = $("#sd-in").value.trim(); if (!sd) return toast(T("sdNeed"), true);
    S.sdLast = sd;
    if (S.pack.project && !(await routineOk())) return;
    const p = await job(T("working"), "sd_plan", sd);
    if (p) renderSdPlan(sd, p);
  });
  $("#imp-go")?.addEventListener("click", () => importSd($("#imp-sd").value.trim(), $("#imp-dest").value.trim()));
}
function renderSdPlan(sd, p) {
  const R = T("sdRows");
  const nothing = !p.copy && !p.delete && !p.rename && !p.move;
  const rows = [[R.copy, `${p.copy} · ${mb(p.copy_bytes)}`], [R.new, p.new], [R.replace, p.replace], [R.delete, `${p.delete} · ${mb(p.delete_bytes)}`],
                [R.move, p.move || 0], [R.rename, p.rename], [R.unchanged, `${p.unchanged} · ${mb(p.unchanged_bytes)}`], [R.backup, `${p.backup_files} · ${mb(p.backup_bytes)}`]];
  const note = (x) => /romfs_metadata\.bin$/i.test(x) ? ` <span class="hint">(${esc(T("sdMetaItem"))})</span>` : "";
  const more = (label, list, total) => list && list.length ? `<details class="more"><summary>${label} (${total ?? list.length})</summary><ul class="items">${list.map((x) => `<li>${esc(x)}${note(x)}</li>`).join("")}${(total ?? 0) > list.length ? `<li>(+${total - list.length})</li>` : ""}</ul></details>` : "";
  $("#sd-body").innerHTML = `
    ${p.console ? `<div class="note"><b>${T("sdConTitle")}</b><p>${T("sdCon", p.console.off, p.console.on)}</p>
      <p><button class="primary" id="sd-con">${T("sdConUse")}</button></p><p class="hint">${T("sdConHint")}</p></div>` : ""}
    <h3>${T("sdPlanTitle")}</h3>
    <p class="hint">${esc(p.target)}</p>
    ${p.first ? `<p class="verdict">${T("sdFirst")}</p>` : ""}
    <dl class="ledger">${(p.first ? rows.filter(([k]) => k === R.copy) : rows).map(([k, v]) => `<div><dt>${k}</dt><dd>${v}</dd></div>`).join("")}</dl>
    ${more(R.new, p.examples.copy, p.new)}
    ${more(R.replace, p.examples.replace, p.replace)}
    ${more(R.delete, p.examples.delete, p.delete)}
    ${more(R.move, p.examples.move, p.move)}
    ${more(R.rename, p.examples.rename, p.rename)}
    ${more(R.backup, p.examples.backup, p.backup_files)}
    ${p.metadata ? `<p class="hint">${T("sdMetaNote")}</p>` : ""}
    ${p.move ? `<p class="hint">${T("sdMoveNote", p.move)}</p>` : ""}
    ${p.backup_files ? `<p class="hint">${T("sdBackupNote")}</p>` : ""}
    ${p.free != null ? `<p class="${p.fits ? "hint" : "note warn"}">${p.fits ? T("sdFits", mb(p.free)) : T("sdNoFit")}</p>` : ""}
    ${p.first ? "" : `<p class="hint">${T("sdAssume")}</p>`}
    ${nothing ? `<p class="verdict">${T("sdNothing")}</p>` : ""}
    <div class="cv-actions"><button class="primary" id="sd-sync" ${nothing || p.fits === false ? "disabled" : ""}>${T("sdSync")}</button>
      ${p.first ? "" : `<button class="ghost" id="sd-full">${T("sdFull")}</button>`}</div>
    ${p.first ? "" : `<p class="hint">${T("sdFullP")}</p>`}`;
  const run = async (mode) => {
    if (!(await confirmDlg(T("nav.sd"), `<p>${T("sdConfirm", sd)}</p>`, T("copy")))) return;
    const r = await job(T("working"), "deploy", sd, mode);
    if (r) { toast(T("sdDone2", r)); $("#sd-body").innerHTML = `<p class="verdict">${T("sdDone2", r)}</p>${r.backup ? `<p class="hint">${esc(r.backup)}</p>` : ""}`; }
  };
  $("#sd-con")?.addEventListener("click", async () => {
    const r = await job(T("working"), "sd_use_console", sd);
    if (!r) return;
    setAudit(r); toast(T("sdConDone"));
    const q = await job(T("working"), "sd_plan", sd);
    if (q) renderSdPlan(sd, q);
  });
  $("#sd-sync").addEventListener("click", () => run("sync"));
  $("#sd-full")?.addEventListener("click", () => run("full"));
}

// ------------------------------------------------------------------ settings
function renderSettings() {
  const st = S.state || {};
  call("ui_prefs").then((p) => { const c = $("#set-links"); if (c) c.checked = p.project_links === true; const r = $("#set-reopen"); if (r) r.checked = p.reopen_last !== false; }).catch(() => {});
  const row = (id, label, val) => `<div class="open-row"><label for="${id}">${label}</label>
    <div class="field"><input id="${id}" value="${esc(val || "")}" spellcheck="false">${hasWebview() ? `<button class="ghost" data-browse="${id}">${T("browse")}</button>` : ""}<button class="primary" data-save="${id}">${T("save")}</button></div></div>`;
  $("#p-ajustes").innerHTML = `${homeBtn()}
    <h2>${T("nav.settings")}</h2>
    <p><button class="link" id="set-setup">${T("suLink")}</button> · <button class="link" id="set-credits">${T("spShow")}</button></p>
    <div class="open-row"><label><input type="checkbox" id="set-links"> ${T("setLinks")}</label><p class="hint">${T("setLinksHint")}</p></div>
    <div class="open-row"><label><input type="checkbox" id="set-reopen"> ${T("setReopen")}</label><p class="hint">${T("setReopenHint")}</p></div>
    ${row("tools_dir", T("toolsLabel"), st.tools_dir)}
    ${row("library_dir", T("libDirLabel"), st.library_dir)}
    ${row("ussep_dir", T("ussepDirLabel"), st.ussep_dir)}
    ${row("inis_dir", T("inisDirLabel"), st.inis_dir)}
    ${row("vanilla_dir", T("vanillaDirLabel"), st.vanilla_dir)}
    <p class="hint">${T("vanillaHint")} <b>${T("vanillaState")[st.vanilla_status || "unset"]}</b></p>
    ${vanillaListHtml(st)}
    <h3>Nexus Mods</h3><div id="nx-settings"></div>
    <h3>${T("xtTitle")}</h3><p class="hint">${T("xtSub")}</p><div id="xt-settings"></div>
    <p class="hint">${T("version", esc(st.version || ""))}</p>`;
  wireHome($("#p-ajustes"));
  renderNexusSettings();
  renderToolSettings();
  $("#vl-build")?.addEventListener("click", async () => { const r = await job(T("vlBuilding"), "vanilla_build"); if (r) { S.state = await call("state"); renderSettings(); } });
  $("#vl-forget")?.addEventListener("click", async () => { if (!(await confirmDlg(T("vlForget"), `<p>${T("vlForgetWarn")}</p>`))) return; const r = await call("vanilla_forget"); S.state = r.state; toast(T("vlForgot", r.n)); renderSettings(); });
  $$("#p-ajustes [data-browse]").forEach((b) => b.addEventListener("click", async () => { const p = await call("pick_folder"); if (p) $("#" + b.dataset.browse).value = p; }));
  $$("#p-ajustes [data-save]").forEach((b) => b.addEventListener("click", async () => {
    S.state = await call("set_folder", b.dataset.save, $("#" + b.dataset.save).value.trim()); S.lib = null; toast(T("saved")); renderSettings();
  }));
}

function vanillaListHtml(st) {
  if (st.vanilla_status !== "ok") return "";
  const v = st.vanilla_list || {};
  if (!v.files) return `<p class="hint">${T("vlNone")} <button class="ghost sm" id="vl-build">${T("vlBuild")}</button></p>`;
  const when = v.built ? new Date(v.built * 1000).toLocaleDateString(S.lang === "es" ? "es-CO" : "en-US") : "";
  return `<p class="hint">${T("vlSummary", v.files.toLocaleString(), v.bsas, v.plugins, when)}
      ${v.missing_core && v.missing_core.length ? `<br>${T("vlMissing", esc(v.missing_core.join(", ")))}` : ""}
      ${v.kept && v.kept.length ? `<br>${T("vlKept", v.kept.length)} <button class="ghost sm" id="vl-forget">${T("vlForget")}</button>` : ""}
      <br><button class="ghost sm" id="vl-build">${T("vlRebuild")}</button></p>`;
}

// ------------------------------------------------------------------ Nexus
async function renderNexusSettings() {
  const box = $("#nx-settings"); if (!box) return;
  const n = await call("nexus_status");
  const u = n.user;
  const handler = n.ours ? T("nxHandlerOurs") : n.handler ? T("nxHandlerOther", n.handler) : T("nxHandlerNone");
  box.innerHTML = `
    <p class="hint">${T("nxKeyHint")}</p>
    <div class="open-row"><label for="nx-key">${T("nxKey")}</label>
      <div class="field"><input id="nx-key" type="password" autocomplete="off" spellcheck="false" placeholder="${n.has_key ? "••••••••" : ""}">
        <button class="primary" id="nx-save">${T("nxCheckSave")}</button>${n.has_key ? `<button class="ghost danger" id="nx-clear">${T("nxForget")}</button>` : ""}</div>
      <p class="hint">${n.has_key && u ? T("nxConnected", esc(u.name || ""), u.premium) : T("nxNoKey")}</p></div>
    ${n.windows ? `<div class="open-row"><label>${T("nxHandler")}</label>
      <p class="hint">${esc(handler)}</p>
      <div>${n.ours ? `<button class="ghost" id="nx-unreg">${n.previous ? T("nxGiveBack") : T("nxStopHandling")}</button>` : `<button class="primary" id="nx-reg">${T("nxTakeOver")}</button>`}</div>
      <p class="hint">${T("nxHandlerHint")}</p></div>` : ""}`;
  $("#nx-save").addEventListener("click", async () => {
    const k = $("#nx-key").value.trim(); if (!k) return toast(T("nxPaste"), true);
    const r = await job(T("working"), "nexus_set_key", k);
    if (r) { S.state = await call("state"); toast(T("saved")); renderNexusSettings(); }
  });
  $("#nx-clear")?.addEventListener("click", async () => { const r = await job(T("working"), "nexus_set_key", ""); if (r) { S.state = await call("state"); renderNexusSettings(); } });
  $("#nx-reg")?.addEventListener("click", async () => { const r = await call("nexus_handler", true); if (!r.ok) toast(r.error, true); renderNexusSettings(); });
  $("#nx-unreg")?.addEventListener("click", async () => { const r = await call("nexus_handler", false); if (!r.ok) toast(r.error, true); renderNexusSettings(); });
}

S.nxm = []; S.nxmRunning = false;
window.onNxm = (url) => { S.nxm.push(url); processNxm(); };
async function processNxm() {
  if (S.nxmRunning) return;
  S.nxmRunning = true;
  try {
    while (S.nxm.length) {
      const pr = await call("progress");
      if (pr && pr.busy) { await new Promise((r) => setTimeout(r, 1000)); continue; }
      const url = S.nxm.shift();
      const st = await call("nexus_download", url);
      if (st && st.busy) { S.nxm.unshift(url); await new Promise((r) => setTimeout(r, 1000)); continue; }
      if (!st || st.ok === false) { toast(st?.error || "Error", true); continue; }
      const r = await followJob(T("nxDownloading"), st.job);
      if (!r) continue;
      await addToQueue([r.path]);
      const q = S.queue.find((x) => x.path === r.path);
      if (q) { q.nexus = r.nexus; renderAdd(); }
      toast(T("nxDownloaded", r.nexus.name || r.path));
    }
  } finally { S.nxmRunning = false; }
}

async function showUpdates() {
  // updates that keep the pack working on Switch (newer files may need SKSE)
  return compatFlow(null, S.pack ? $("#p-mods") : null, S.pack ? $("#m-nexus") : null);
}

// ------------------------------------------------------------------ recipe
async function showRecipe() {
  const r = await job(T("working"), "recipe_view");
  if (!r) return;
  const c = r.counts;
  $("#m-extra").innerHTML = `<div class="loot">
    <div class="loot-head"><h3>${T("rcTitle")}</h3><button class="link" id="rc-close">✕</button></div>
    <p class="hint">${T("rcSub")}</p>
    <dl class="ledger">
      <div><dt>${T("rcMods")}</dt><dd>${c.mods}</dd></div>
      <div><dt>Plugins / BSA</dt><dd>${c.plugins} / ${c.bsas}</dd></div>
      <div><dt>${T("rcNexus")}</dt><dd>${r.nexus}</dd></div>
      <div><dt>${T("rcUnknown")}</dt><dd>${c.unowned}</dd></div>
      <div><dt>${T("rcSaved")}</dt><dd>${r.saved ? esc(r.saved_at || "") : T("rcNever")}</dd></div>
    </dl>
    ${r.saved ? `<h4>${T("rcChanges")}</h4>${r.diff.length ? `<ul class="report">${r.diff.map((x) => `<li>${esc(x)}</li>`).join("")}</ul>` : `<p class="hint">${T("rcNoChanges")}</p>`}
      ${r.verify.length ? `<details class="more"><summary>${T("rcVerify", r.verify.length)}</summary><ul class="report">${r.verify.map((v) => `<li>${esc(v.text)}</li>`).join("")}</ul></details>` : ""}` : ""}
    <div class="cv-actions"><button class="primary" id="rc-save">${T("rcSave")}</button><button class="ghost" id="rc-export">${T("rcExport")}</button></div>
    <p class="hint">${T("rcExportHint")}</p></div>`;
  $("#rc-close").addEventListener("click", () => ($("#m-extra").innerHTML = ""));
  $("#rc-save").addEventListener("click", async () => { const x = await job(T("working"), "recipe_save"); if (x) { toast(T("rcSavedOk")); showRecipe(); } });
  $("#rc-export").addEventListener("click", async () => { const x = await job(T("working"), "recipe_export"); if (x) infoDlg(T("rcExport"), `<p>${T("rcExported")}</p><p class="hint">${esc(x.path)}</p>`); });
}

// ------------------------------------------------------------------ catalog: build a pack from the Library
const tabsHtml = (on) => `<div class="tabs"><button data-libtab="list" class="${on === "list" ? "on" : ""}">${T("libTabList")}</button><button data-libtab="catalog" class="${on === "catalog" ? "on" : ""}">${T("libTabCatalog")}</button></div>`;
function wireTabs(el) {
  $$("[data-libtab]", el).forEach((b) => b.addEventListener("click", () => { S.libTab = b.dataset.libtab; renderLibrary(false); }));
}
const pick2t = (t) => (Array.isArray(t) ? pick2(t) : t || "");

async function renderCatalog(refresh = false) {
  const el = $("#p-library");
  if (refresh || !S.cat) {
    const r = await job(T("catReading"), "catalog_build", refresh);
    if (!r) return;
    const keep = S.cat ? catalogPicks() : [];
    S.cat = r; S.catPicks = {}; S.catPlan = null; S.catIdent = null;
    keep.forEach((p) => {        // re-find each pick by pack and unit: indexes shift when packs come and go
      const e = r.entries.find((x) => x.key === p.key);
      const vi = e ? e.versions.findIndex((v) => v.pack_path === p.pack_path && v.unit_id === p.unit_id) : -1;
      if (vi >= 0) S.catPicks[p.key] = vi;
    });
  }
  await catalogIdent();
  S.catBase = S.catBase || { edition: "AE", cc_preset: "ussep", ussep: "" };
  S.catFilter = S.catFilter || { q: "", cat: "", multi: false, picked: false };
  if (!S.catUssep) { try { S.catUssep = await call("ussep_scan"); } catch (e) { S.catUssep = { variants: [] }; } }
  const C = S.cat, F = S.catFilter, B = S.catBase;
  const into = !!(B.into && S.pack);
  const cats = C.categories || [];
  const catName = (id) => { const c = cats.find((x) => x.id === id); return c ? (LANG === "es" ? c.es : c.en) : id; };
  const q = F.q.toLowerCase();
  const vis = C.entries.filter((e) => (!F.cat || e.category === F.cat) && (!F.multi || e.versions.length > 1)
    && (!F.picked || S.catPicks[e.key] !== undefined)
    && (!q || e.name.toLowerCase().includes(q) || e.versions.some((v) => [...v.plugins, ...v.bsas].some((f) => f.toLowerCase().includes(q)))));
  const counts = {}; C.entries.forEach((e) => (counts[e.category] = (counts[e.category] || 0) + 1));
  const nPicked = Object.keys(S.catPicks).length;
  el.innerHTML = `${homeBtn()}
    <h2>${T("libTitle")}</h2>
    ${tabsHtml("catalog")}
    <p class="sub">${T("catSub", C.packs.filter((p) => p.kind === "pack").length, C.entries.length)}</p>
    <div class="cat-wrap">
      <div class="cat-list">
        <div class="doctor-head"><div class="field grow"><input id="cat-q" placeholder="${esc(T("xFilter"))}" value="${esc(F.q)}" spellcheck="false"></div>
          <label class="hint"><input type="checkbox" id="cat-multi" ${F.multi ? "checked" : ""}> ${T("catMulti")}</label>
          <label class="hint"><input type="checkbox" id="cat-picked" ${F.picked ? "checked" : ""}> ${T("catOnlyPicked")}</label>
          <button class="ghost sm" id="cat-refresh">${T("libRefresh")}</button></div>
        <div class="filters cat-chips"><button data-cat="" class="${F.cat ? "" : "on"}">${T("all")} ${C.entries.length}</button>${cats.filter((c) => counts[c.id]).map((c) => `<button data-cat="${esc(c.id)}" class="${F.cat === c.id ? "on" : ""}">${esc(LANG === "es" ? c.es : c.en)} ${counts[c.id]}</button>`).join("")}</div>
        <div class="units">${vis.slice(0, 400).map((e) => {
          const vi = S.catPicks[e.key];
          const on = vi !== undefined;
          const v = e.versions[on ? vi : 0];
          const many = e.versions.length > 1;
          return `<div class="unit cat-entry ${on ? "on" : ""}">
            <input type="checkbox" data-pick="${esc(e.key)}" ${on ? "checked" : ""}>
            <div><div class="t"><b>${esc(e.name)}</b>${nxChipLite(S.catIdent?.[e.key])} <span class="src">${esc(catName(e.category))}</span>
                ${many ? `<span class="src">${T("catInPacks", e.versions.length)}${e.identical ? ` · ${T("catIdentical")}` : ""}</span>` : ""}
                ${e.inside_merges?.length ? `<span class="src warnc">${T("catInMerge", esc(e.inside_merges[0].merge))}</span>` : ""}</div>
              <div class="files">${esc([...v.plugins, ...v.bsas].join(" · "))}</div>
              ${many ? `<div class="hint">${T("catVersion")}: <select data-ver="${esc(e.key)}">${e.versions.map((x, i) => `<option value="${i}" ${(on ? vi : 0) === i ? "selected" : ""}>${esc(x.pack)} · ${mb(x.size || 0)}</option>`).join("")}</select></div>`
                    : `<div class="hint">${esc(v.pack)}</div>`}
              <div class="hint">${esc(pick2t(e.category_why))}</div>
              ${(v.flags || []).slice(0, 2).map((f) => `<div class="hint flag">${esc(pick2([f.en, f.es]))}</div>`).join("")}</div>
            <div class="risk">${mb(v.size || 0)}${v.tex_bytes ? `<br><small>${T("tex")} ${mb(v.tex_bytes)}</small>` : ""}</div></div>`; }).join("")}
          ${vis.length > 400 ? `<p class="hint">${T("catMore", vis.length - 400)}</p>` : ""}</div>
      </div>
      <aside class="cat-side">
        ${S.pack ? `<div class="radio-row cat-into"><label><input type="radio" name="cb-into" value="new" ${B.into ? "" : "checked"}> ${T("catIntoNew")}</label>
          <label><input type="radio" name="cb-into" value="open" ${B.into ? "checked" : ""}> ${T("catIntoOpen", esc(S.pack.name))}</label></div>` : ""}
        <h3>${into ? T("catIntoTitle") : T("catNewPack")} <small>${nPicked}</small></h3>
        ${into ? `<p class="hint">${T("catIntoHint", esc(S.pack.name))}</p>` : `<div class="open-row"><label>${T("edition")}</label>
          <div class="radio-row"><label><input type="radio" name="cb-ed" value="AE" ${B.edition === "AE" ? "checked" : ""}> AE</label><label><input type="radio" name="cb-ed" value="SE" ${B.edition === "SE" ? "checked" : ""}> SE</label></div></div>
        ${B.edition === "AE" ? `<div class="open-row"><label>${T("ccLabel")}</label>
          <select id="cb-cc"><option value="ussep" ${B.cc_preset === "ussep" ? "selected" : ""}>${T("ccUssep")}</option><option value="all" ${B.cc_preset === "all" ? "selected" : ""}>${T("ccAll")}</option><option value="none" ${B.cc_preset === "none" ? "selected" : ""}>${T("ccNone")}</option></select></div>` : ""}
        <div class="open-row"><label>USSEP</label>
          <select id="cb-us"><option value="">${T("usNone")}</option>${(S.catUssep.variants || []).map((v) => `<option value="${esc(v.id)}" ${B.ussep === v.id ? "selected" : ""} ${B.edition === "SE" && v.cc.length ? "disabled" : ""}>${esc(v.id)}</option>`).join("")}</select></div>
        <div class="open-row"><label>${T("baseLabel")}</label>
          <div class="field"><input id="cb-inis" value="${esc(B.inis_dir || S.state?.inis_dir || "")}" spellcheck="false">${hasWebview() ? `<button class="ghost sm" id="cb-inis-browse">${T("browse")}</button>` : ""}</div>
          <p class="hint">${T("catInisHint")}</p></div>
        <div class="open-row"><label>${T("catNewName")}</label>
          <div class="field"><input id="cb-dest" value="${esc(B.dest || "")}" placeholder="${esc(T("catNewNamePh"))}">${hasWebview() ? `<button class="ghost sm" id="cb-browse">${T("browse")}</button>` : ""}</div>
          <p class="hint">${T("catNewNameHint")}</p></div>`}
        <div id="cat-plan">${nPicked ? `<p class="hint">${T("working")}…</p>` : `<p class="hint">${T("catPickSome")}</p>`}</div>
        <div class="cv-actions"><button class="primary" id="cb-go" ${nPicked ? "" : "disabled"}>${into ? T("catIntoGo") : T("catCreate")}</button>
          ${nPicked ? `<button class="link" id="cb-clear">${T("catClear")}</button>` : ""}</div>
      </aside>
    </div>`;
  wireHome(el); wireTabs(el); wireNxOpen(el);
  const rerender = () => { const pos = $("#cat-q").selectionStart; renderCatalog(false).then(() => { const i = $("#cat-q"); if (i && document.activeElement !== i && S._catTyping) { i.focus(); i.setSelectionRange(pos, pos); } }); };
  $("#cat-q").addEventListener("input", (e) => { F.q = e.target.value; S._catTyping = true; clearTimeout(S._catQ); S._catQ = setTimeout(rerender, 250); });
  $("#cat-multi").addEventListener("change", (e) => { F.multi = e.target.checked; S._catTyping = false; rerender(); });
  $("#cat-picked").addEventListener("change", (e) => { F.picked = e.target.checked; S._catTyping = false; rerender(); });
  $("#cat-refresh").addEventListener("click", () => renderCatalog(true));
  $$("[data-cat]", el).forEach((b) => b.addEventListener("click", () => { F.cat = b.dataset.cat; S._catTyping = false; rerender(); }));
  $$("[data-pick]", el).forEach((c) => c.addEventListener("change", () => {
    const k = c.dataset.pick;
    if (c.checked) { const sel = $(`select[data-ver="${CSS.escape(k)}"]`, el); S.catPicks[k] = sel ? +sel.value : 0; } else delete S.catPicks[k];
    S._catTyping = false; rerender();
  }));
  $$("[data-ver]", el).forEach((s) => s.addEventListener("change", () => { const k = s.dataset.ver; S.catPicks[k] = +s.value; S._catTyping = false; rerender(); }));
  $$('input[name="cb-ed"]').forEach((r) => r.addEventListener("change", () => { B.edition = r.value; if (r.value === "SE") B.ussep = ""; S._catTyping = false; rerender(); }));
  $("#cb-cc")?.addEventListener("change", (e) => { B.cc_preset = e.target.value; refreshCatalogPlan(); });
  $("#cb-us")?.addEventListener("change", (e) => { B.ussep = e.target.value; refreshCatalogPlan(); });
  $$('input[name="cb-into"]', el).forEach((r) => r.addEventListener("change", () => { B.into = r.value === "open"; S._catTyping = false; renderCatalog(false); }));
  $("#cb-dest")?.addEventListener("change", (e) => (B.dest = e.target.value.trim()));
  $("#cb-inis")?.addEventListener("change", (e) => { B.inis_dir = e.target.value.trim(); refreshCatalogPlan(); });
  $("#cb-inis-browse")?.addEventListener("click", async () => { const p = await call("pick_folder"); if (p) { B.inis_dir = p; $("#cb-inis").value = p; refreshCatalogPlan(); } });
  $("#cb-browse")?.addEventListener("click", async () => { const p = await call("pick_folder"); if (p) { B.dest = p; $("#cb-dest").value = p; } });
  $("#cb-clear")?.addEventListener("click", () => { S.catPicks = {}; S._catTyping = false; rerender(); });
  $("#cb-go").addEventListener("click", () => createFromCatalog(false));
  if (nPicked) refreshCatalogPlan();
}
function catalogPicks() {
  return Object.entries(S.catPicks).map(([key, vi]) => {
    const e = S.cat.entries.find((x) => x.key === key); if (!e) return null;
    const v = e.versions[vi] || e.versions[0];
    return { key, pack_path: v.pack_path, unit_id: v.unit_id };
  }).filter(Boolean);
}
function catBase() {
  const B = S.catBase;
  if (B.into && S.pack) return { into: "open" };
  const out = { edition: B.edition, cc_preset: B.edition === "AE" ? B.cc_preset : "none", ussep: B.ussep || null };
  if (B.inis_dir) out.inis_dir = B.inis_dir;
  return out;
}
async function refreshCatalogPlan() {
  const box = $("#cat-plan"); if (!box) return;
  const seq = (S._planSeq = (S._planSeq || 0) + 1);
  const r = await call("catalog_plan", catalogPicks(), catBase());
  if (seq !== S._planSeq || !$("#cat-plan")) return;
  if (!r.ok) { box.innerHTML = `<p class="note warn">${esc(r.error)}</p>`; return; }
  const p = S.catPlan = r.plan, b = p.budget;
  const stat = (s) => (s === "over" ? "bad" : s === "tight" || s === "warn" ? "warnc" : "");
  const bring = p.items.filter((i) => i.status === "bring");
  const autos = bring.filter((i) => i.reason === "master");
  box.innerHTML = `
    <dl class="ledger mini">
      <div><dt>.ccc</dt><dd class="${stat(b.ccc.status)}">${b.ccc.bytes} / ${b.ccc.limit}</dd></div>
      ${b.inis.filter((i) => i.key !== "sArchiveToLoadInMemoryList").map((i) => `<div><dt>${esc(i.ini)} · ${esc(i.key.replace("sResourceArchive", ""))}</dt><dd class="${stat(i.status)}">${i.chars} / ${i.limit}</dd></div>`).join("")}
      <div><dt>Plugins / BSA</dt><dd>${b.plugins} / ${b.bsas}</dd></div>
      <div><dt>${T("tex")}</dt><dd class="${stat(b.ram.status)}">${mb(b.tex_bytes || 0)}</dd></div>
      <div><dt>${T("catSize")}</dt><dd>${mb(b.size || 0)}</dd></div>
    </dl>
    ${b.ram.text ? `<p class="hint">${esc(pick2t(b.ram.text))}</p>` : ""}
    ${autos.length ? `<p class="hint">${T("catAutoMasters", autos.length)}: ${esc(autos.map((a) => a.name).join(", "))}</p>` : ""}
    ${p.problems.length ? p.problems.map((x) => `<p class="note ${x.severity === "block" ? "warn" : ""}">${esc(pick2t(x.text))}${x.fix ? `<br><small>${esc(pick2t(x.fix))}</small>` : ""}</p>`).join("") : ""}
    ${p.suggestions.length ? `<div>${p.suggestions.map((sg, i) => `<button class="ghost sm sugg" data-sugg="${i}">${esc(pick2t(sg.text))}</button>`).join("")}</div>` : ""}
    ${p.skipped.length ? `<details class="more"><summary>${T("catSkipped", p.skipped.length)}</summary><ul class="report">${p.skipped.map((s) => `<li><b>${esc(s.name)}</b>: ${esc(pick2t(s.reason))}</li>`).join("")}</ul></details>` : ""}`;
  $$("[data-sugg]", box).forEach((btn) => btn.addEventListener("click", () => {
    const sg = p.suggestions[+btn.dataset.sugg];
    (sg.add || []).forEach((a) => { const e = S.cat.entries.find((x) => x.key === a.key); if (e) S.catPicks[a.key] = Math.max(0, e.versions.findIndex((v) => v.unit_id === a.unit_id && v.pack_path === a.pack_path)); });
    (sg.remove || []).forEach((a) => delete S.catPicks[a.key]);
    if (sg.cc_preset) S.catBase.cc_preset = sg.cc_preset;
    S._catTyping = false; renderCatalog(false);
  }));
}
async function createFromCatalog(force) {
  const into = !!(S.catBase.into && S.pack);
  const dest = into ? "" : ($("#cb-dest")?.value || "").trim();
  if (!into && !dest) return toast(T("catNeedName"), true);
  if (!into) S.catBase.dest = dest;
  const blocking = (S.catPlan?.problems || []).filter((x) => x.severity === "block");
  if (blocking.length && !force) {
    if (!(await confirmDlg(T("catCreate"), `<p>${T("catBlocked")}</p><ul class="report">${blocking.map((x) => `<li>${esc(pick2t(x.text))}</li>`).join("")}</ul>`, T("catCreateAnyway")))) return;
    force = true;
  }
  const r = await job(T("creating"), "catalog_execute", catalogPicks(), catBase(), dest, force);
  if (!r) return;
  const o = r.build;
  packChanged(); S.firstCrit = null; setAudit(r); S.catPicks = {}; S.catPlan = null;
  await infoDlg(T("catDone"), `
    <p>${T("catDoneP", o.brought.length)}</p>
    ${o.skipped.length ? `<h4>${T("catSkipped", o.skipped.length)}</h4><ul class="report">${o.skipped.map((s) => `<li><b>${esc(s.name)}</b>: ${esc(pick2t(s.reason))}</li>`).join("")}</ul>` : ""}
    ${o.errors.length ? `<h4>${T("xErrors")}</h4><ul class="report">${o.errors.map((s) => `<li>${esc(pick2t(s.text || s))}</li>`).join("")}</ul>` : ""}
    ${o.notes.length ? `<h4>${T("notes")}</h4><ul class="report">${o.notes.map((s) => `<li>${esc(pick2t(s.text || s))}</li>`).join("")}</ul>` : ""}`);
  enterPack("mods");
}

// ------------------------------------------------------------------ compare with the original
async function compareWithOriginal(path) {
  let orig = hasWebview() ? await call("pick_file") : prompt(T("cmpAsk"));
  if (!orig) return;
  const r = await job(T("cmpWorking"), "compare_mods", path, orig);
  if (!r) return;
  const a = r.assets || {}, c = a.counts || {};
  const recs = (r.plugins || []).filter((p) => p.records).map((p) => {
    const x = p.records;
    const types = Object.entries(x.by_type || {}).slice(0, 6).map(([t, n]) => `${t} ${typeof n === "object" ? (n.changed || 0) + (n.added || 0) + (n.removed || 0) : n}`).join(", ");
    return `<li><b>${esc(p.converted || "–")}</b> ↔ ${esc(p.original || "–")} <small>(${esc(p.match || "")})</small><br>
      <small>${T("cmpRecs", x.added || 0, x.removed || 0, x.changed || 0, x.same || 0)}${types ? ` · ${esc(types)}` : ""}</small>
      ${(x.examples || []).slice(0, 6).map((e) => `<br><small>· ${esc(e.type)} ${esc(e.edid || e.formid)}: ${esc(e.what || "")}${e.subs?.length ? ` (${esc(e.subs.join(", "))})` : ""}</small>`).join("")}</li>`;
  }).join("");
  const list = (k, label) => (a[k] && a[k].length ? `<details class="more"><summary>${label} (${c[k] ?? a[k].length})</summary><ul class="items">${a[k].slice(0, 50).map((x) => `<li>${esc(typeof x === "string" ? x : x.path || JSON.stringify(x))}</li>`).join("")}</ul></details>` : "");
  infoDlg(T("cmpTitle"), `
    <p class="verdict">${esc(r.verdict_text || "")}</p>
    ${recs ? `<h4>Plugins</h4><ul class="report">${recs}</ul>` : ""}
    <h4>${T("cmpAssets")}</h4>
    <p class="hint">${T("cmpConv", a.converted_textures || 0, a.downscaled || 0, a.converted_audio || 0, a.converted_anims || 0)}</p>
    ${list("meshes_changed", T("cmpMeshes"))}${list("scripts_changed", T("cmpScripts"))}${list("scripts_removed", T("cmpScriptsGone"))}
    ${list("only_original", T("cmpOnlyOrig"))}${list("only_converted", T("cmpOnlyConv"))}
    ${(r.notes || []).map((n) => `<p class="note ${n.level === "warn" ? "warn" : ""}">${esc(n.text)}</p>`).join("")}`);
}

// ------------------------------------------------------------------ external tools (settings)
async function renderToolSettings() {
  const box = $("#xt-settings"); if (!box) return;
  const r = await call("tools_list");
  box.innerHTML = r.tools.filter((t) => t.id !== "other").map((t) => `<div class="open-row"><label>${esc(t.name)}</label>
    <div class="field"><input data-tool="${esc(t.id)}" value="${esc(t.path || "")}" placeholder="…\\${esc(t.name)}.exe" spellcheck="false">${hasWebview() ? `<button class="ghost sm" data-toolpick="${esc(t.id)}">${T("browse")}</button>` : ""}<button class="primary sm" data-toolsave="${esc(t.id)}">${T("save")}</button></div>
    <p class="hint">${esc(t.how || "")}</p></div>`).join("");
  $$("[data-toolpick]", box).forEach((b) => b.addEventListener("click", async () => { const p = await call("pick_file"); if (p) $(`input[data-tool="${b.dataset.toolpick}"]`, box).value = p; }));
  $$("[data-toolsave]", box).forEach((b) => b.addEventListener("click", async () => { await call("set_tool_path", b.dataset.toolsave, $(`input[data-tool="${b.dataset.toolsave}"]`, box).value.trim()); toast(T("saved")); renderToolSettings(); }));
}

// ------------------------------------------------------------------ load order: xEdit and plugin manager
async function openInXedit() {
  // a copy kept from an earlier session that still has edits?
  let existing = "";
  const st = await call("xedit_status");
  if (!st.ok && st.foreign) {
    const c = await choiceDlg(T("xeTitle"), `<p>${esc(st.error)}</p><p class="hint">${esc(st.workspace)}</p>`, [
      { id: "rebuild", label: T("xeForeignDrop") }]);
    if (c !== "rebuild") return;
    existing = "rebuild";
  }
  const pend = st.ok && st.workspace ? [...(st.changed || []), ...(st.conflicts || []), ...(st.new || []), ...(st.pending_saves || []), ...(st.gone || []), ...(st.vanilla_changed || [])] : [];
  if (pend.length) {
    const c = await choiceDlg(T("xeKeptTitle"), `<p>${T("xeKeptBody")}</p><ul class="report">${pend.map((x) => `<li>${esc(x)}</li>`).join("")}</ul>`, [
      { id: "reuse", label: T("xeKeptReuse"), primary: true },
      { id: "bring", label: T("xeKeptBring") },
      { id: "rebuild", label: T("xeKeptDrop") }]);
    if (!c) return;
    if (c === "bring") {
      const r = await call("xedit_sync", true);
      if (!r.ok) return toast(r.error, true);
      setAudit(r); toast(T("xeSynced", r.files.length));
      existing = "rebuild";
    } else existing = c;
  }
  let last = "copy"; try { last = localStorage.getItem("xeMode") || "copy"; } catch (e) { /* */ }
  const mode = await choiceDlg(T("xeModeTitle"), `<p>${T("xeModeBody")}</p>`, [
    { id: "direct", label: T("xeDirect"), hint: T("xeDirectHint"), primary: last === "direct" },
    { id: "copy", label: T("xeCopy"), hint: T("xeCopyHint"), primary: last !== "direct" }]);
  if (!mode) return;
  try { localStorage.setItem("xeMode", mode); } catch (e) { /* */ }
  const r = await job(T("xeOpening"), "xedit_open", "sseedit", mode, existing);
  if (!r) return;
  watchXedit();
  infoDlg(T("xeTitle"), `<p>${mode === "direct" ? T("xeOpenedDirect") : T("xeOpenedCopy")}</p><p class="hint">${esc(r.workspace)}</p>
    ${r.missing?.length ? `<h4>${T("xeMissing")}</h4><ul class="report">${r.missing.slice(0, 30).map((m) => `<li>${esc(m.name)} <small>(${esc(m.kind)})</small></li>`).join("")}</ul>` : ""}
    ${r.notes?.length ? `<ul class="report">${r.notes.map((n) => `<li>${esc(n)}</li>`).join("")}</ul>` : ""}`);
}
let xeTimer = null;
function watchXedit() {
  if (xeTimer) return;
  xeTimer = setInterval(async () => {
    let r; try { r = await call("xedit_session"); } catch (e) { return; }
    const sess = r && r.session;
    if (!sess) { clearInterval(xeTimer); xeTimer = null; return; }
    if (sess.running) return;
    clearInterval(xeTimer); xeTimer = null;
    await xeditClosed(sess);
  }, 3000);
}
async function xeditClosed(sess) {
  const d = $("#dlg");
  if (d.open) { d.close(); await new Promise((r) => setTimeout(r, 80)); }   // let its close event fire first
  const changes = [...(sess.changed || []), ...(sess.new || []), ...(sess.conflicts || [])];
  const stuck = [...(sess.gone || []), ...(sess.vanilla_changed || [])];
  const finish = async (action) => {
    let r;
    for (let i = 0; i < 200; i++) {           // another task running: wait for it, don't step on it
      r = await call("xedit_finish", action);
      if (!r.busy) break;
      await new Promise((ok) => setTimeout(ok, 2000));
    }
    if (!r.ok) { toast(r.error, true); return; }
    if (r.audit) setAudit(r);
    if (r.left?.length) toast(T("xeLeft", r.left.join(", ")), true);
    else if (action === "bring") toast(r.files.length ? T("xeSynced", r.files.length) : T("xeNoChanges"));
    else if (action === "discard") toast(T("xeDiscarded"));
    else toast(T("xeKeptToast"));
    if (S.page === "orden") renderOrder();
  };
  if (sess.error) { toast(sess.error, true); return finish("keep"); }
  if (sess.pending_saves?.length) {
    await infoDlg(T("xeTitle"), `<p>${T("xeUnfinished")}</p><ul class="report">${sess.pending_saves.map((x) => `<li>${esc(x)}</li>`).join("")}</ul>`);
    return finish("keep");
  }
  if (sess.mode === "direct" && !sess.conflicts?.length && !stuck.length) return finish("bring");
  const body = (changes.length
    ? `<p>${T("xeClosedChanges", esc(sess.pack_name))}</p><ul class="report">${changes.map((c) => `<li>${esc(c)}</li>`).join("")}</ul>${sess.conflicts?.length ? `<p class="note warn">${T("xeConflicts", esc(sess.conflicts.join(", ")))}</p>` : ""}`
    : stuck.length ? "" : `<p>${T("xeClosedNone")}</p>`)
    + (stuck.length ? `<p class="note warn">${T("xeStuck", esc(stuck.join(", ")))}</p>` : "");
  const opts = changes.length
    ? [{ id: "bring", label: T("xeDoBring"), primary: true }, { id: "keep", label: T("xeDoKeep") }, { id: "discard", label: T("xeDoDiscard") }]
    : stuck.length ? [{ id: "keep", label: T("xeDoKeep"), primary: true }, { id: "discard", label: T("xeDoDiscard") }]
    : [{ id: "discard", label: T("xeDoDiscard"), primary: true }, { id: "keep", label: T("xeDoKeep") }];
  const c = await choiceDlg(T("xeClosedTitle"), body, opts);
  return finish(c || "keep");
}
async function syncFromXedit() {
  const st = await call("xedit_status");
  if (!st.ok) return toast(st.error, true);
  if (!st.workspace) return toast(T("xeNone"), true);
  if (st.pending_saves?.length) return toast(T("xeStillOpen"), true);
  const ch = [...(st.changed || []), ...(st.new || []), ...(st.conflicts || [])];
  if (!ch.length) return toast(T("xeNoChanges"));
  const force = (st.conflicts || []).length > 0;
  if (!(await confirmDlg(T("xeSync"), `<ul class="report">${ch.map((c) => `<li>${esc(c)}</li>`).join("")}</ul>${force ? `<p class="note warn">${T("xeConflicts", esc(st.conflicts.join(", ")))}</p>` : ""}`, T("xeSync")))) return;
  const r = await call("xedit_sync", force);
  if (!r.ok) return toast(r.error, true);
  setAudit(r); toast(T("xeSynced", r.files.length)); renderOrder();
}
async function togglePlugin(name, active) {
  let r = await call("plugin_active", name, active, false);
  if (!r.ok && r.users?.length) {
    if (!(await confirmDlg(T("pmDisable"), `<p>${T("pmUsers", esc(name), esc(r.users.join(", ")))}</p>`, T("pmDisableAnyway")))) return renderOrder();
    r = await call("plugin_active", name, active, true);
  }
  if (!r.ok) { toast(r.error, true); return renderOrder(); }
  setAudit(r); renderOrder();
}

// ------------------------------------------------------------------ start
document.body.classList.add("no-pack");
let booted = false;
function start() { if (booted) return; booted = true; boot(); }
if (hasWebview() || new URLSearchParams(location.search).get("mode") === "server") start();
window.addEventListener("pywebviewready", start);
