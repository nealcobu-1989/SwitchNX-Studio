Scriptname NXTestQuestScript extends Quest
{SkyNX test tools: gives the player the power and keeps track of what it spawned.}

Spell Property NXTestPower Auto

ObjectReference[] Spawned
Int SpawnedCount = 0

Event OnInit()
	Spawned = new ObjectReference[128]
	Actor player = Game.GetPlayer()
	If !player.HasSpell(NXTestPower)
		player.AddSpell(NXTestPower, False)
	EndIf
EndEvent

; Re-gives the power if the player lost it (called from the menu too)
Function EnsurePower()
	Actor player = Game.GetPlayer()
	If !player.HasSpell(NXTestPower)
		player.AddSpell(NXTestPower, False)
	EndIf
EndFunction

Bool Function Track(ObjectReference ref)
	If Spawned == None
		Spawned = new ObjectReference[128]
	EndIf
	If SpawnedCount >= 128
		Return False
	EndIf
	Spawned[SpawnedCount] = ref
	SpawnedCount += 1
	Return True
EndFunction

Int Function CountSpawned()
	Return SpawnedCount
EndFunction

Int Function RemoveSpawned()
	Int i = 0
	Int removed = 0
	While i < SpawnedCount
		ObjectReference ref = Spawned[i]
		If ref
			ref.Disable()
			ref.Delete()
			removed += 1
		EndIf
		Spawned[i] = None
		i += 1
	EndWhile
	SpawnedCount = 0
	Return removed
EndFunction

; Spawns in front of the player, in a fan so they don't stack. Runs here, on
; the quest, so it keeps going after the power's short effect ends.
Int Function SpawnMany(Form what, Int count)
	Actor p = Game.GetPlayer()
	Float a = p.GetAngleZ()
	Int i = 0
	Int placed = 0
	While i < count
		Float spread = (i % 5) * 18.0 - 36.0
		Float dist = 350.0 + (i / 5) * 150.0
		ObjectReference ref = p.PlaceAtMe(what, 1)
		If ref
			ref.MoveTo(p, dist * Math.Sin(a + spread), dist * Math.Cos(a + spread), 0.0)
			If Track(ref)
				placed += 1
			Else
				ref.Disable()
				ref.Delete()
				Debug.Notification("128 spawned already: remove them first")
				i = count
			EndIf
		EndIf
		i += 1
	EndWhile
	Debug.Notification("Spawned " + placed + " (" + SpawnedCount + " in total)")
	Return placed
EndFunction
