"""What each Creation Club plugin is, for the load list, the Mods page and SkyNX Mods.

Titles and what each one adds follow the Anniversary Edition listing (Push
Square, "Skyrim Anniversary Edition: All Creation Club DLC Listed"); the
plugin each one lives in was checked against the console's own plugins
(their quests, cells and locations). The Switch's load list also names six
plugins the game doesn't have (`NOT_ON_SWITCH`), none of them in the
Anniversary listing. Arcane Archer Pack's BSA is in the game; its plugin
wasn't in the console dump this was checked against.
"""
from __future__ import annotations

# plugin (lowercase) -> (title, kind en, kind es, what it adds en, what it adds es)
CC: dict[str, tuple[str, str, str, str, str]] = {}


def _add(plugin: str, title: str, kind: tuple[str, str], en: str, es: str) -> None:
    CC[plugin.lower()] = (title, kind[0], kind[1], en, es)


ARMOR = ("Armor", "Armadura")
WEAPON = ("Weapon", "Arma")
HOME = ("Player home", "Casa")
QUEST = ("Quest", "Misión")
PET = ("Pet", "Mascota")
GAMEPLAY = ("Gameplay", "Jugabilidad")
ITEMS = ("Items", "Objetos")
MOUNT = ("Mount", "Montura")

_add("ccBGSSSE001-Fish.esm", "Fishing", GAMEPLAY,
     "Fishing spots across Skyrim, rods and a fishing questline.",
     "Puntos de pesca por todo Skyrim, cañas y una cadena de misiones de pesca.")
_add("ccQDRSSE001-SurvivalMode.esl", "Survival Mode", GAMEPLAY,
     "Hunger, thirst, sleep and cold; switched on or off in the options.",
     "Hambre, sed, sueño y frío; se activa o desactiva en las opciones.")
_add("ccBGSSSE037-Curios.esl", "Rare Curios", ITEMS,
     "New ingredients and potions, sold by merchants and found in containers.",
     "Ingredientes y pociones nuevos, en tiendas y en cofres.")
_add("ccBGSSSE025-AdvDSGS.esm", "Saints & Seducers", QUEST,
     "Quest 'Balance of Power' with Golden Saints and Dark Seducers; weapons and armor.",
     "Misión 'Balance of Power' con Santos Dorados y Seductores Oscuros; armas y armaduras.")
_add("ccAFDSSE001-DweSanctuary.esm", "Nchuanthumz: Dwarven Home", HOME,
     "A large Dwemer player home near Winterhold, through a quest.",
     "Una casa enana grande cerca de Winterhold, con misión.")
_add("ccMDRSSE001-DweSanctuary.esm", "Dwarven Sanctuary (Switch)", HOME,
     "A small home setup (Klogirc) shipped with the Switch's copy; not in the PC listing.",
     "Una casa pequeña (Klogirc) que viene en la copia de Switch; no está en la lista de PC.")
_add("ccBGSSSE016-Umbra.esm", "Umbra", WEAPON,
     "The soul-stealing sword Umbra, through the quest 'Vile Whispers' north of Riften.",
     "La espada Umbra, que roba almas, con la misión 'Vile Whispers' al norte de Riften.")
_add("ccASVSSE001-ALMSIVI.esm", "Ghosts of the Tribunal", QUEST,
     "A quest in Raven Rock (Dragonborn) with unique weapons and armor.",
     "Una misión en Raven Rock (Dragonborn) con armas y armaduras únicas.")
_add("ccBGSSSE067-DaedInv.esm", "The Cause", QUEST,
     "High-level quest (level 46+) against a Daedric invasion; weapons and a mount.",
     "Misión de nivel alto (46+) contra una invasión daédrica; armas y una montura.")
_add("ccEEJSSE001-Hstead.esm", "Tundra Homestead", HOME,
     "A small home near Whiterun, bought from Proventus.",
     "Una casa pequeña cerca de Whiterun; se le compra a Proventus.")
_add("ccTWBSSE001-PuzzleDungeon.esm", "Forgotten Seasons", QUEST,
     "A Dwemer puzzle dungeon near Markarth; helmets, a mount and new powers.",
     "Una mazmorra enana de acertijos cerca de Markarth; yelmos, montura y poderes.")
_add("ccBGSSSE002-ExoticArrows.esl", "Arcane Archer Pack", WEAPON,
     "Magic arrows sold by merchants and found in chests.",
     "Flechas mágicas en tiendas y cofres.")
_add("ccBGSSSE003-Zombies.esl", "Plague of the Dead", GAMEPLAY,
     "Zombies roam at night after the quest 'The Rising Dead'.",
     "Zombis de noche después de la misión 'The Rising Dead'.")
_add("ccBGSSSE004-RuinsEdge.esl", "Ruin's Edge", WEAPON,
     "An enchanted bow dropped in Stony Creek Cave.",
     "Un arco encantado que suelta un enemigo en Stony Creek Cave.")
_add("ccBGSSSE005-Goldbrand.esl", "Goldbrand", WEAPON,
     "The sword Goldbrand, through a quest at the Sacellum of Boethiah.",
     "La espada Goldbrand, con una misión en el santuario de Boethiah.")
_add("ccBGSSSE006-StendarsHammer.esl", "Stendarr's Hammer", WEAPON,
     "An enchanted warhammer in the Dwemer Museum of Markarth.",
     "Un martillo encantado en el Museo Dwemer de Markarth.")
_add("ccBGSSSE007-Chrysamere.esl", "Chrysamere", WEAPON,
     "The greatsword Chrysamere, dropped at Forelhost.",
     "El mandoble Chrysamere, en Forelhost.")
_add("ccBGSSSE008-Wraithguard.esl", "Sunder & Wraithguard", WEAPON,
     "Gauntlets and a hammer through the quest 'Legends Lost'.",
     "Guanteletes y un martillo con la misión 'Legends Lost'.")
_add("ccBGSSSE010-PetDwarvenArmoredMudcrab.esl", "Dwarven Armored Mudcrab", PET,
     "A Dwemer mudcrab pet sold by Calcelmo in Markarth.",
     "Un cangrejo enano de mascota; lo vende Calcelmo en Markarth.")
_add("ccBGSSSE011-HrsArmrElvn.esl", "Horse Armor - Elven", ARMOR,
     "Elven armor for your horse, from stables.", "Armadura élfica para el caballo, en los establos.")
_add("ccBGSSSE012-HrsArmrStl.esl", "Horse Armor - Steel", ARMOR,
     "Steel armor for your horse, from stables.", "Armadura de acero para el caballo, en los establos.")
_add("ccBGSSSE013-Dawnfang.esl", "Dawnfang & Duskfang", WEAPON,
     "A sword that changes by day and night, from the Ratway.",
     "Una espada que cambia de día y de noche, en el Ratway.")
_add("ccBGSSSE014-SpellPack01.esl", "Arcane Accessories", ITEMS,
     "Enchanted robes and spell books in chests and shops.",
     "Túnicas encantadas y libros de hechizos en cofres y tiendas.")
_add("ccBGSSSE018-Shadowrend.esl", "Shadowrend", WEAPON,
     "A greatsword and a battleaxe through 'Through a Glass, Darkly'.",
     "Un mandoble y un hacha con la misión 'Through a Glass, Darkly'.")
_add("ccBGSSSE019-StaffofSheogorath.esl", "Staff of Sheogorath", WEAPON,
     "Sheogorath's staff through a quest in Raven Rock.",
     "El bastón de Sheogorath con una misión en Raven Rock.")
_add("ccBGSSSE020-GrayCowl.esl", "The Grey Cowl Returns!", ARMOR,
     "The Grey Cowl of Nocturnal through a quest in Riften.",
     "La capucha gris de Nocturnal con una misión en Riften.")
_add("ccBGSSSE021-LordsMail.esl", "Lord's Mail", ARMOR,
     "An enchanted cuirass through 'Gift of Kynareth' in Solitude.",
     "Una coraza encantada con la misión 'Gift of Kynareth' en Solitude.")
_add("ccBGSSSE031-AdvCyrus.esm", "Dead Man's Dread", QUEST,
     "A ghost pirate ship quest from Solitude; a sword, clothes and a ship home.",
     "Una misión con un barco pirata fantasma desde Solitude; espada, ropa y un barco de casa.")
_add("ccBGSSSE034-MntUni.esl", "Wild Horses", MOUNT,
     "Wild horses to tame across Skyrim, with saddles at stables.",
     "Caballos salvajes para domar por Skyrim, con sillas en los establos.")
_add("ccBGSSSE035-PetNHound.esl", "Nix-Hound", PET,
     "A Nix-Hound pet sold in Raven Rock.", "Un nix-hound de mascota; lo venden en Raven Rock.")
_add("ccBGSSSE036-PetBWolf.esl", "Bone Wolf", PET,
     "A skeletal wolf pet after 'The Wolf Queen Awakened'.",
     "Un lobo esqueleto de mascota, después de 'The Wolf Queen Awakened'.")
_add("ccBGSSSE038-BowofShadows.esl", "Bow of Shadows", WEAPON,
     "An enchanted bow through a quest from Proventus in Dragonsreach.",
     "Un arco encantado con una misión de Proventus en Dragonsreach.")
_add("ccBGSSSE040-AdvObGobs.esl", "Goblins", QUEST,
     "Goblins in the wilds and a goblin follower through 'Blue in the Face'.",
     "Goblins en el mundo y un seguidor goblin con la misión 'Blue in the Face'.")
_add("ccBGSSSE041-NetchLeather.esl", "Netch Leather Armor", ARMOR,
     "A light armor set through a quest on Solstheim.",
     "Un juego de armadura ligera con una misión en Solstheim.")
_add("ccBGSSSE043-CrossElv.esl", "Elite Crossbows", WEAPON,
     "Two unique crossbows through 'Night Hunter'.", "Dos ballestas únicas con la misión 'Night Hunter'.")
_add("ccBGSSSE045-Hasedoki.esl", "Staff of Hasedoki", WEAPON,
     "A staff through a quest at a bandit camp west of Whiterun.",
     "Un bastón con una misión en un campamento al oeste de Whiterun.")
for _p, _t, _q in [("050-BA_Daedric", "Daedric Plate", "Beyond the Grave"),
                   ("051-BA_DaedricMail", "Daedric Mail", "Missing Merchant"),
                   ("052-BA_Iron", "Iron", "Brothers in Irons"),
                   ("053-BA_Leather", "Leather", "Double-Edged"),
                   ("054-BA_Orcish", "Orcish Plate", "Smith 'N Slash"),
                   ("055-BA_OrcishScaled", "Orcish Scaled", "Gambler's Edge"),
                   ("056-BA_Silver", "Silver", "When the Cat's Away"),
                   ("057-BA_Stalhrim", "Stalhrim Fur", "Ancient Ice"),
                   ("058-BA_Steel", "Steel Soldier", "Over the Edge"),
                   ("059-BA_Dragonplate", "Dragon Plate", "Bounty for Crowstooth"),
                   ("060-BA_Dragonscale", "Dragonscale", "Tilted Scales"),
                   ("061-BA_Dwarven", "Dwarven Plate", "Mightier than the Sword"),
                   ("062-BA_DwarvenMail", "Dwarven Mail", "Fan Favorite"),
                   ("063-BA_Ebony", "Ebony Plate", "Heart of Crimson"),
                   ("064-BA_Elven", "Elven Hunter", "Once a Hunter")]:
    _add(f"ccBGSSSE{_p}.esl", f"Alternative Armors - {_t}", ARMOR,
         f"A redesigned {_t.lower()} set, through the quest '{_q}' and in chests.",
         f"Una versión rediseñada de la armadura ({_t}), con la misión '{_q}' y en cofres.")
_add("ccBGSSSE066-Staves.esl", "Staves", WEAPON,
     "Many new staves, from Neloth or a staff-making table.",
     "Muchos bastones nuevos, de Neloth o de una mesa para fabricarlos.")
_add("ccBGSSSE068-Bloodfall.esl", "Headman's Cleaver", WEAPON,
     "A two-handed axe through 'Blood in the Water', from innkeeper rumors.",
     "Un hacha a dos manos con la misión 'Blood in the Water', por rumores de posadero.")
_add("ccBGSSSE069-Contest.esl", "The Contest", WEAPON,
     "A sword and gauntlets through 'Caught in a Web' in Windhelm.",
     "Una espada y guanteletes con la misión 'Caught in a Web' en Windhelm.")
_add("ccCBHSSE001-Gaunt.esl", "Fearsome Fists", ARMOR,
     "Gauntlets that raise unarmed damage.", "Guanteletes que suben el daño sin armas.")
_add("ccEDHSSE001-NorJewel.esl", "Nordic Jewelry", ITEMS,
     "New craftable jewelry styles.", "Estilos nuevos de joyas para fabricar.")
_add("ccEDHSSE002-SplKntSet.esl", "Spell Knight Armor", ARMOR,
     "Armor sets through 'Crypt of the Heart' in Markarth.",
     "Juegos de armadura con la misión 'Crypt of the Heart' en Markarth.")
_add("ccEDHSSE003-Redguard.esl", "Redguard Elite Armaments", ARMOR,
     "Weapons and armor through 'Interception' at Shor's Stone.",
     "Armas y armaduras con la misión 'Interception' en Shor's Stone.")
_add("ccEEJSSE002-Tower.esl", "Myrwatch", HOME,
     "A large mage tower home east of Morthal.", "Una torre de mago grande de casa, al este de Morthal.")
_add("ccEEJSSE003-Hollow.esl", "Shadowfoot Sanctum", HOME,
     "A small thieves' home in the Ratway, sold by Vekel.",
     "Una casa pequeña de ladrones en el Ratway; la vende Vekel.")
_add("ccEEJSSE004-Hall.esl", "Hendraheim", HOME,
     "A large Nordic hall home through 'Warrior's Challenge'.",
     "Un salón nórdico grande de casa, con la misión 'Warrior's Challenge'.")
_add("ccEEJSSE005-Cave.esm", "Bloodchill Manor", HOME,
     "A large manor in an ice cave, through 'Guests for Dinner' (level 12+).",
     "Una mansión grande en una cueva de hielo, con 'Guests for Dinner' (nivel 12+).")
_add("ccFFBSSE001-ImperialDragon.esl", "Civil War Champions", QUEST,
     "Quest 'Battle of Champions'; two heavy armor sets and weapons.",
     "Misión 'Battle of Champions'; dos armaduras pesadas y armas.")
_add("ccFFBSSE002-CrossbowPack.esl", "Expanded Crossbow Pack", WEAPON,
     "Many new crossbows, sold, found and craftable.",
     "Muchas ballestas nuevas, en tiendas, cofres y forja.")
_add("ccFSVSSE001-Backpacks.esl", "Adventurer's Backpack", ITEMS,
     "Craftable backpacks that raise carry weight.", "Mochilas para fabricar que suben el peso que cargas.")
_add("ccKRTSSE001_Altar.esl", "Bittercup", QUEST,
     "A quest-driven item whose effect depends on how you finish 'A Dying Wish'.",
     "Un objeto cuyo efecto depende de cómo terminas la misión 'A Dying Wish'.")
_add("ccMTYSSE001-KnightsOfTheNine.esl", "Divine Crusader", ARMOR,
     "Knight of the Nine weapons and armor at Four Skull Lookout.",
     "Armas y armaduras de caballero de los Nueve en Four Skull Lookout.")
_add("ccMTYSSE002-VE.esl", "Vigil Enforcer Armor Set", ARMOR,
     "Vigilant armor sets through 'Unholy Vigil'.", "Armaduras de los Vigilantes con la misión 'Unholy Vigil'.")
_add("ccPEWSSE002-ArmsOfChaos.esl", "Arms of Chaos", WEAPON,
     "Two staves and accessories through a quest north of the College.",
     "Dos bastones y accesorios con una misión al norte del Colegio.")
_add("ccQDRSSE002-Firewood.esl", "Camping", GAMEPLAY,
     "Craftable camping gear to sleep, cook and fast travel to your camp.",
     "Equipo de campamento para dormir, cocinar y viajar rápido al campamento.")
_add("ccRMSSSE001-NecroHouse.esl", "Gallows Hall", HOME,
     "A necromancer's home near Mara's Eye Pond, through 'Dreams of the Dead'.",
     "Una casa de nigromante cerca de Mara's Eye Pond, con 'Dreams of the Dead'.")
_add("ccVSVSSE001-Winter.esl", "Saturalia Holiday Pack", ITEMS,
     "A merchant near Dawnstar with holiday clothes and a mount.",
     "Un vendedor cerca de Dawnstar con ropa de fiesta y una montura.")
_add("ccVSVSSE002-Pets.esl", "Pets of Skyrim", PET,
     "Several pets through 'Pets of Skyrim' at the Bannered Mare.",
     "Varias mascotas con la misión 'Pets of Skyrim' en el Bannered Mare.")
_add("ccVSVSSE003-NecroArts.esl", "Necromancer Grimoire", ITEMS,
     "Necromancer robes and Conjuration spell books.", "Túnicas de nigromante y libros de Conjuración.")
_add("ccVSVSSE004-BeAFarmer.esl", "Farming", HOME,
     "A farm to own and run, through 'The Unquiet Dead' east of Rorikstead.",
     "Una granja propia, con la misión 'The Unquiet Dead' al este de Rorikstead.")

# In the Switch's load list, but the game has neither the plugin nor its BSA
# (none of them is in the Anniversary listing). Their lines only cost bytes.
NOT_ON_SWITCH = {"ccbgssse026-goldensaint.esl", "ccbgssse017-swordofjyggalag.esl",
                 "ccbgssse029-nerveshatter.esl", "ccbgssse032-mntdaed.esl",
                 "ccbgssse065-lightaxehammer.esl"}


def info(plugin: str) -> dict | None:
    """{"title", "kind": (en, es), "desc": (en, es)} or None."""
    low = plugin.lower()
    e = CC.get(low)
    if e:
        return {"title": e[0], "kind": (e[1], e[2]), "desc": (e[3], e[4])}
    if low in NOT_ON_SWITCH:
        stem = plugin.rsplit(".", 1)[0].split("-", 1)[-1]
        return {"title": stem, "kind": ("Not on Switch", "No está en Switch"),
                "desc": ("Named in the console's load list, but the game has neither its plugin nor its BSA.",
                         "La lista de carga de la consola lo nombra, pero el juego no tiene ni su plugin ni su BSA.")}
    return None
