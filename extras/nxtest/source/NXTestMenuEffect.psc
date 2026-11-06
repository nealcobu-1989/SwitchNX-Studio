Scriptname NXTestMenuEffect extends ActiveMagicEffect
{SkyNX test tools: the power's menus. Switch has no console and no MCM, so
everything goes through message boxes, like the game's own settings menus.}

NXTestQuestScript Property Tools Auto
Message Property MainMenu Auto
Message Property PlaceMenu Auto
Message Property SpawnMenu Auto
Message Property CountMenu Auto
Message Property TimeMenu Auto
Message Property PlayerMenu Auto
Message Property WeatherMenu Auto
Message Property ModSpawnMenu Auto
ObjectReference[] Property Places Auto
Form[] Property Spawns Auto
Weather[] Property Weathers Auto
GlobalVariable Property GameHour Auto
MiscObject Property Gold Auto

Event OnEffectStart(Actor akTarget, Actor akCaster)
	MainLoop()
EndEvent

Function MainLoop()
	Bool done = False
	While !done
		Int b = MainMenu.Show(Tools.CountSpawned())
		If b == 0
			done = Teleport()
		ElseIf b == 1
			Int kind = SpawnMenu.Show()
			If kind >= 0 && kind < Spawns.Length
				Spawn(Spawns[kind], 1)
				done = True
			EndIf
		ElseIf b == 2
			Int kind = SpawnMenu.Show()
			If kind >= 0 && kind < Spawns.Length
				Int c = CountMenu.Show()
				Int n = 0
				If c == 0
					n = 5
				ElseIf c == 1
					n = 10
				ElseIf c == 2
					n = 20
				ElseIf c == 3
					n = 40
				EndIf
				If n > 0
					Spawn(Spawns[kind], n)
					done = True
				EndIf
			EndIf
		ElseIf b == 3
			Int removed = Tools.RemoveSpawned()
			Debug.Notification("Removed " + removed)
		ElseIf b == 4
			Int t = TimeMenu.Show()
			If t == 0
				SetHour(6.0)
			ElseIf t == 1
				SetHour(12.0)
			ElseIf t == 2
				SetHour(18.0)
			ElseIf t == 3
				SetHour(0.0)
			EndIf
		ElseIf b == 5
			done = ModSpawn()
		ElseIf b == 6
			; runs on the quest: this effect is short and may end meanwhile
			Tools.QuestMenu()
			done = True
		ElseIf b == 7
			done = PlayerTools()
		ElseIf b == 8
			WeatherTools()
		Else
			done = True
		EndIf
	EndWhile
EndFunction

Bool Function Teleport()
	Int i = PlaceMenu.Show()
	If i >= 0 && i < Places.Length && Places[i]
		Game.GetPlayer().MoveTo(Places[i])
		Return True
	EndIf
	Return False
EndFunction

Function SetHour(Float h)
	GameHour.SetValue(h)
	Debug.Notification("Time set")
EndFunction

Function Spawn(Form what, Int count)
	Tools.SpawnMany(what, count)
EndFunction

; Returns True when the menus should close
Bool Function PlayerTools()
	Int b = PlayerMenu.Show()
	Actor p = Game.GetPlayer()
	If b == 0
		Game.AddPerkPoints(1)
		Debug.Notification("+1 perk point")
	ElseIf b == 1
		p.AddItem(Gold, 1000)
	ElseIf b == 2
		Debug.SetGodMode(True)
		Debug.Notification("God mode on")
	ElseIf b == 3
		Debug.SetGodMode(False)
		Debug.Notification("God mode off")
	ElseIf b == 4
		; walk through walls to get out of a stuck spot; press it again after
		Debug.ToggleCollisions()
		Debug.Notification("Collision switched (press again to switch back)")
		Return True
	ElseIf b == 5
		p.RestoreActorValue("Health", 100000.0)
		p.RestoreActorValue("Magicka", 100000.0)
		p.RestoreActorValue("Stamina", 100000.0)
		Debug.Notification("Healed")
	EndIf
	Return False
EndFunction

; Creatures from mods, looked up by plugin and form id (a plugin that isn't
; in the pack is skipped). Returns True when the menus should close.
Bool Function ModSpawn()
	Int b = ModSpawnMenu.Show()
	If b == 0
		Return SpawnFrom("Dawnguard.esm", 0x01A93D, 1)          ; DLC1HarkonCombat
	ElseIf b == 1
		Return SpawnFrom("Dragonborn.esm", 0x019665, 1)         ; DLC2dunKarstaag
	ElseIf b == 2
		Return SpawnFrom("Dragonborn.esm", 0x0322B1, 1)         ; DLC2EncWerebear
	ElseIf b == 3
		Int n = 0
		Mixed = 0
		n += SpawnCount("MihailNX.esp", 0x000E15)               ; dwarven defender
		n += SpawnCount("MihailNX.esp", 0x001057)               ; draugr cavalry
		n += SpawnCount("MihailNX.esp", 0x000B71)               ; cthulhoid
		n += SpawnCount("MihailNX.esp", 0x000803)               ; crystal golem
		n += SpawnCount("MihailNX.esp", 0x000FDE)               ; wendigo
		n += SpawnCount("MihailNX.esp", 0x000F95)               ; iron atronach
		n += SpawnCount("MihailNX.esp", 0x000D92)               ; storm golem
		n += SpawnCount("MihailNX.esp", 0x000C09)               ; ancient skeleton
		n += SpawnCount("mihaildeadrapack.esp", 0x00084B)       ; fiendroth
		n += SpawnCount("mihailhighfantasypack.esp", 0x000CAC)  ; mounted falmer
		n += SpawnCount("mihailhighfantasypack.esp", 0x000D59)  ; ogre
		n += SpawnCount("mihailhighfantasypack.esp", 0x00087D)  ; goblin
		n += SpawnCount("mihailnecropriestsandbonetyrants.esp", 0x014C2C)  ; lon skeleton
		n += SpawnCount("mihailwraithsandspectres.esp", 0x000809)          ; wraith
		Debug.Notification("Mihail mix: " + n + " kinds")
		Return n > 0
	EndIf
	Return False
EndFunction

Bool Function SpawnFrom(String file, Int id, Int count)
	Form f = Game.GetFormFromFile(id, file)
	If !f
		Debug.Notification("Not in this pack: " + file)
		Return False
	EndIf
	Tools.SpawnMany(f, count)
	Return True
EndFunction

Int Mixed = 0

; One of each, in a fan in front of the player (rows of 5, like SpawnMany)
Int Function SpawnCount(String file, Int id)
	Form f = Game.GetFormFromFile(id, file)
	If !f
		Return 0
	EndIf
	Actor p = Game.GetPlayer()
	Float a = p.GetAngleZ()
	Float spread = (Mixed % 5) * 18.0 - 36.0
	Float dist = 400.0 + (Mixed / 5) * 200.0
	ObjectReference ref = p.PlaceAtMe(f, 1)
	If !ref
		Return 0
	EndIf
	ref.MoveTo(p, dist * Math.Sin(a + spread), dist * Math.Cos(a + spread), 0.0)
	Mixed += 1
	If !Tools.Track(ref)
		ref.Disable()
		ref.Delete()
		Return 0
	EndIf
	Return 1
EndFunction

Function WeatherTools()
	Int w = WeatherMenu.Show()
	If w >= 0 && w < Weathers.Length && Weathers[w]
		Weathers[w].ForceActive(True)
		Debug.Notification("Weather set (Normal weather undoes it)")
	ElseIf w == Weathers.Length
		Weather.ReleaseOverride()
		Debug.Notification("Normal weather")
	EndIf
EndFunction
