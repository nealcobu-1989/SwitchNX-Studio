"""What we know about Skyrim on Nintendo Switch, with the source of each fact.

Everything here was either read from real files (the five community packs in
C:\\SkyNX) or from a public guide. Facts that are still unverified are marked.
"""

TITLE_BASE = "01000A10041EA000"     # base game + update (inis, Data)
TITLE_AOC = "01000A10041EB009"      # Anniversary Edition DLC (Skyrim_aoc.ccc)

VANILLA_MASTERS = ["Skyrim.esm", "Update.esm", "Dawnguard.esm", "HearthFires.esm",
                   "Dragonborn.esm"]
SWITCH_MASTERS = ["Hyrule.esm"]

# Creation Club plugins as listed, in this order, by two independent packs
# (Simonrim, Flowergirls). 80 entries, 2197 bytes with CRLF.
AE_CC_PLUGINS = [
    "ccBGSSSE001-Fish.esm", "ccQDRSSE001-SurvivalMode.esl", "ccBGSSSE037-Curios.esl",
    "ccBGSSSE026-GoldenSaint.esl", "ccAFDSSE001-DweSanctuary.esm",
    "ccMDRSSE001-DweSanctuary.esm", "ccBGSSSE016-Umbra.esm", "ccASVSSE001-ALMSIVI.esm",
    "ccBGSSSE025-AdvDSGS.esm", "ccBGSSSE067-DaedInv.esm", "ccEEJSSE001-Hstead.esm",
    "ccTWBSSE001-PuzzleDungeon.esm", "ccBGSSSE002-ExoticArrows.esl",
    "ccBGSSSE003-Zombies.esl", "ccBGSSSE004-RuinsEdge.esl", "ccBGSSSE005-Goldbrand.esl",
    "ccBGSSSE006-StendarsHammer.esl", "ccBGSSSE007-Chrysamere.esl",
    "ccBGSSSE008-Wraithguard.esl", "ccBGSSSE010-PetDwarvenArmoredMudcrab.esl",
    "ccBGSSSE011-HrsArmrElvn.esl", "ccBGSSSE012-HrsArmrStl.esl",
    "ccBGSSSE013-Dawnfang.esl", "ccBGSSSE014-SpellPack01.esl",
    "ccBGSSSE017-SwordofJyggalag.esl", "ccBGSSSE018-Shadowrend.esl",
    "ccBGSSSE019-StaffofSheogorath.esl", "ccBGSSSE020-GrayCowl.esl",
    "ccBGSSSE021-LordsMail.esl", "ccBGSSSE029-Nerveshatter.esl",
    "ccBGSSSE031-AdvCyrus.esm", "ccBGSSSE032-MntDaed.esl", "ccBGSSSE034-MntUni.esl",
    "ccBGSSSE035-PetNHound.esl", "ccBGSSSE036-PetBWolf.esl",
    "ccBGSSSE038-BowofShadows.esl", "ccBGSSSE040-AdvObGobs.esl",
    "ccBGSSSE041-NetchLeather.esl", "ccBGSSSE043-CrossElv.esl",
    "ccBGSSSE045-Hasedoki.esl", "ccBGSSSE050-BA_Daedric.esl",
    "ccBGSSSE051-BA_DaedricMail.esl", "ccBGSSSE052-BA_Iron.esl",
    "ccBGSSSE053-BA_Leather.esl", "ccBGSSSE054-BA_Orcish.esl",
    "ccBGSSSE055-BA_OrcishScaled.esl", "ccBGSSSE056-BA_Silver.esl",
    "ccBGSSSE057-BA_Stalhrim.esl", "ccBGSSSE058-BA_Steel.esl",
    "ccBGSSSE059-BA_Dragonplate.esl", "ccBGSSSE060-BA_Dragonscale.esl",
    "ccBGSSSE061-BA_Dwarven.esl", "ccBGSSSE062-BA_DwarvenMail.esl",
    "ccBGSSSE063-BA_Ebony.esl", "ccBGSSSE064-BA_Elven.esl",
    "ccBGSSSE065-LightAxeHammer.esl", "ccBGSSSE066-Staves.esl",
    "ccBGSSSE068-Bloodfall.esl", "ccBGSSSE069-Contest.esl", "ccCBHSSE001-Gaunt.esl",
    "ccEDHSSE001-NorJewel.esl", "ccEDHSSE002-SplKntSet.esl", "ccEDHSSE003-Redguard.esl",
    "ccEEJSSE002-Tower.esl", "ccEEJSSE003-Hollow.esl", "ccEEJSSE004-Hall.esl",
    "ccEEJSSE005-Cave.esm", "ccFFBSSE001-ImperialDragon.esl",
    "ccFFBSSE002-CrossbowPack.esl", "ccFSVSSE001-Backpacks.esl", "ccKRTSSE001_Altar.esl",
    "ccMTYSSE001-KnightsOfTheNine.esl", "ccMTYSSE002-VE.esl",
    "ccPEWSSE002-ArmsOfChaos.esl", "ccQDRSSE002-Firewood.esl",
    "ccRMSSSE001-NecroHouse.esl", "ccVSVSSE001-Winter.esl", "ccVSVSSE003-NecroArts.esl",
    "ccVSVSSE002-Pets.esl", "ccVSVSSE004-BeAFarmer.esl",
]
# Masters that USSEP (AE build) requires, read from its TES4 header.
USSEP_CC_MASTERS = ["ccBGSSSE001-Fish.esm", "ccQDRSSE001-SurvivalMode.esl",
                    "ccBGSSSE037-Curios.esl", "ccBGSSSE025-AdvDSGS.esm"]

# Limits ---------------------------------------------------------------------
# Unverified hard number, but consistent with the evidence: Flowergirls' author
# hit "the limit" at 147 entries / 4015 bytes while Avner Revised loads 152
# entries in 3850 bytes, so the limit is in bytes, not entries.
CCC_BYTE_LIMIT = 4096
CCC_BYTE_WARN = 3900
# Koka's guide: archive list strings are capped at 1024 characters.
INI_ARCHIVE_LIMIT = 1024

# Behaviour learned from the packs -------------------------------------------
# * Missing .ccc entries are skipped silently (Avner disables mods with '#').
# * sTestFile1..10 in [General] load plugins outside the .ccc (Flowergirls).
# * Mod.bsa and "Mod - Textures.bsa" auto-load with Mod.esp (rentry guide,
#   Simonrim's DeadlySpellImpacts). BSA names are case sensitive (rentry).
# * Voices / FaceGen / SEQ live under folders named after the owning plugin.
# * Switch-converted textures are NVN "DFvN" containers with a .dds extension.
#   Creating them needs NvnTexpkg.exe (Nintendo SDK). Without it, Koka's rules
#   keep PC DDS and force DXT5.
# * Voices in converted mods are Nintendo Opus (48 kHz mono) inside FUZE;
#   music and some effects are .mcadpcm.
# * SE (old method, NX Toolkit wiki): plugin list in romfs/Plugins (no
#   extension, LF, case sensitive), no ESL support, BSAs listed in the inis.
# * Clean console dump (DBI, Oct 2026, AE): Skyrim.ini lists Skyrim - Hyrule.bsa
#   in sResourceArchiveList and Textures0-8 in sResourceArchiveList2;
#   Skyrim_es.ini sets its own sResourceArchiveList2 (Voices_es0-1, Textures0-5).
#   The language ini loads after Skyrim.ini and replaces that list, so mod BSAs
#   in list 2 must go in the language ini (Ashiro's pack does this in
#   Skyrim_en.ini). Skyrim_aoc.ccc: the same 80 CC plugins, alphabetical, CRLF,
#   no newline after the last one (2195 bytes).
STEST_KEYS = [f"sTestFile{i}" for i in range(1, 11)]
PLUGIN_FOLDER_ROOTS = (
    "sound\\voice\\",
    "meshes\\actors\\character\\facegendata\\facegeom\\",
    "textures\\actors\\character\\facegendata\\facetint\\",
)
JUNK_IN_BSA = (".psc", ".bak", ".tga", ".txt.bak", ".log", ".xcf", ".psd")

# KokaNX's tests and advice (Oct 2026) ------------------------------------------
# * Animation BSAs only need sResourceArchiveList. sArchiveToLoadInMemoryList
#   just keeps them in RAM; it's only worth it if T-poses or animation stutters
#   show up. The game's own entries there are left alone.
# * The SE version can ignore a plugin whose HEDR version is 1.71 (saved with
#   CK 1.6.1130+); Koka sets it to 1.70 in SSEEdit.
# * USSEP goes first: its BSAs right after the game's own BSAs in every ini list
#   (Skyrim.ini sResourceArchiveList: scripts/meshes/animations; Skyrim_en.ini
#   sResourceArchiveList2: textures/voices), and its plugin first in the load
#   list, right after the Creation Club entries (AE) or first in Plugins (SE).
# * seq\<plugin>.seq: flat array of little-endian uint32 FormIDs (as stored in
#   the plugin) of its Start Game Enabled quests (QUST DNAM flags bit 0x0001).
#   xEdit's "Create SEQ File" (xeMainForm.pas, GenerateSEQFileForFile) writes
#   new SGE quests and overrides that turn SGE on for a master quest.
HEDR_SE = 1.70
USSEP_PLUGIN = "Unofficial Skyrim Special Edition Patch.esp"
USSEP_KOKA_BSAS = ["USSEP.bsa", "USSEPA.bsa", "USSEPT.bsa", "USSEPV.bsa"]
QUST_START_GAME_ENABLED = 0x0001


def is_vanilla_bsa(name: str) -> bool:
    """The game's own archives (the console has them; packs only list them)."""
    low = name.lower().strip()
    return low.startswith("skyrim - ") or "relicsofhyrule" in low


def after_vanilla(items: list[str], first: list[str]) -> list[str]:
    """`items` with the names in `first` (kept in their current order) moved
    right after the last vanilla entry, or to the front if there is none."""
    low = {f.lower() for f in first}
    moved = [i for i in items if i.lower() in low]
    rest = [i for i in items if i.lower() not in low]
    at = max([n + 1 for n, i in enumerate(rest) if is_vanilla_bsa(i)], default=0)
    return rest[:at] + moved + rest[at:]
