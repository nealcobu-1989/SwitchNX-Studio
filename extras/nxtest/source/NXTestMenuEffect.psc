Scriptname NXTestMenuEffect extends ActiveMagicEffect
{SkyNX test tools: the power's menus. Switch has no console and no MCM, so
everything goes through message boxes, like the game's own settings menus.}

NXTestQuestScript Property Tools Auto
Message Property MainMenu Auto
Message Property PlaceMenu Auto
Message Property SpawnMenu Auto
Message Property CountMenu Auto
Message Property TimeMenu Auto
ObjectReference[] Property Places Auto
Form[] Property Spawns Auto
GlobalVariable Property GameHour Auto

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
			Actor p = Game.GetPlayer()
			p.RestoreActorValue("Health", 100000.0)
			p.RestoreActorValue("Magicka", 100000.0)
			p.RestoreActorValue("Stamina", 100000.0)
			Debug.Notification("Healed")
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
