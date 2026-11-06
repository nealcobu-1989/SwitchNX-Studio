Scriptname NXTestQuestScript extends Quest
{SkyNX test tools: gives the player the power, keeps track of what it spawned,
and helps with the tracked quests. Switch has no console: "next stage" and
"restart" do what setstage and resetquest did on PC.

The pack's quests come from the app when it packs (plugin, form id, stages
and a message with the quest's name). Game.GetFormFromFile finds each one, so a
plugin that is off is simply skipped.}

Spell Property NXTestPower Auto

ObjectReference[] Spawned
Int SpawnedCount = 0

; ---- the pack's quests (filled by SkyNX Studio when it packs)
String[] Property Files Auto
Int Property QuestCount Auto
Int Property DataVersion Auto
Message Property RestartConfirm Auto
Message Property NoQuestMsg Auto
Int[] Property QA0 Auto
Int[] Property QA1 Auto
Int[] Property QA2 Auto
Int[] Property QA3 Auto
Int[] Property QA4 Auto
Int[] Property QA5 Auto
Int[] Property QA6 Auto
Int[] Property QA7 Auto
Int[] Property QB0 Auto
Int[] Property QB1 Auto
Int[] Property QB2 Auto
Int[] Property QB3 Auto
Int[] Property QB4 Auto
Int[] Property QB5 Auto
Int[] Property QB6 Auto
Int[] Property QB7 Auto
Int[] Property S0 Auto
Int[] Property S1 Auto
Int[] Property S2 Auto
Int[] Property S3 Auto
Int[] Property S4 Auto
Int[] Property S5 Auto
Int[] Property S6 Auto
Int[] Property S7 Auto
Int[] Property S8 Auto
Int[] Property S9 Auto
Int[] Property S10 Auto
Int[] Property S11 Auto
Int[] Property S12 Auto
Int[] Property S13 Auto
Int[] Property S14 Auto
Int[] Property S15 Auto
Int[] Property S16 Auto
Int[] Property S17 Auto
Int[] Property S18 Auto
Int[] Property S19 Auto
Int[] Property S20 Auto
Int[] Property S21 Auto
Int[] Property S22 Auto
Int[] Property S23 Auto
Int[] Property S24 Auto
Int[] Property S25 Auto
Int[] Property S26 Auto
Int[] Property S27 Auto
Int[] Property S28 Auto
Int[] Property S29 Auto
Int[] Property S30 Auto
Int[] Property S31 Auto
Int[] Property S32 Auto
Int[] Property S33 Auto
Int[] Property S34 Auto
Int[] Property S35 Auto
Int[] Property S36 Auto
Int[] Property S37 Auto
Int[] Property S38 Auto
Int[] Property S39 Auto
Int[] Property S40 Auto
Int[] Property S41 Auto
Int[] Property S42 Auto
Int[] Property S43 Auto
Int[] Property S44 Auto
Int[] Property S45 Auto
Int[] Property S46 Auto
Int[] Property S47 Auto
Message[] Property M0 Auto
Message[] Property M1 Auto
Message[] Property M2 Auto
Message[] Property M3 Auto
Message[] Property M4 Auto
Message[] Property M5 Auto
Message[] Property M6 Auto
Message[] Property M7 Auto

Quest[] C0
Quest[] C1
Quest[] C2
Quest[] C3
Quest[] C4
Quest[] C5
Quest[] C6
Quest[] C7
Int CachedVersion = -1


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

; ------------------------------------------------------------------ quests

; Finds every quest of the list once per data version (the list changes when
; the pack is packed again with other mods).
Function EnsureCache()
	If CachedVersion == DataVersion && C0
		Return
	EndIf
	Debug.Notification("Test tools: reading the pack's quests...")
	C0 = new Quest[128]
	C1 = new Quest[128]
	C2 = new Quest[128]
	C3 = new Quest[128]
	C4 = new Quest[128]
	C5 = new Quest[128]
	C6 = new Quest[128]
	C7 = new Quest[128]
	Int i = 0
	While i < QuestCount
		Int id = QA(i)
		Int f = id / 16777216
		Quest q = None
		If Files && f < Files.Length
			q = Game.GetFormFromFile(id - f * 16777216, Files[f]) as Quest
		EndIf
		SetC(i, q)
		i += 1
	EndWhile
	CachedVersion = DataVersion
EndFunction

Int Function StageAt(Int n)
	Int v = S(n / 2)
	Int hi = v / 65536
	If n % 2 == 1
		Return hi
	EndIf
	Return v - hi * 65536
EndFunction

; The first stage after the current one that isn't done yet (-1: none left)
Int Function NextStage(Int i, Quest q)
	Int cur = q.GetStage()
	Int b = QB(i)
	Int first = b / 256
	Int count = b - first * 256
	Int n = 0
	While n < count
		Int st = StageAt(first + n)
		If st > cur && !q.IsStageDone(st)
			Return st
		EndIf
		n += 1
	EndWhile
	Return -1
EndFunction

Function Restart(Quest q)
	q.Stop()
	Int n = 0
	While !q.IsStopped() && n < 50
		Utility.Wait(0.1)
		n += 1
	EndWhile
	q.Reset()
	If q.Start()
		q.SetActive(True)
		Debug.Notification("Quest restarted")
	Else
		Debug.Notification("The quest could not start again")
	EndIf
EndFunction

; Shows the tracked quests one after another.
Function QuestMenu()
	EnsureCache()
	Int i = 0
	Int shown = 0
	Bool closed = False
	While i < QuestCount && !closed
		Quest q = GetC(i)
		If q && q.IsActive() && q.IsRunning() && !q.IsCompleted()
			shown += 1
			closed = QuestActions(i, q)
		EndIf
		i += 1
	EndWhile
	If shown == 0
		NoQuestMsg.Show()
	ElseIf !closed
		Debug.Notification("No more tracked quests")
	EndIf
EndFunction

; One quest's menu. Returns True when the person closed the menus.
Bool Function QuestActions(Int i, Quest q)
	Message m = GetM(i)
	While True
		Int nxt = NextStage(i, q)
		Int b = m.Show(q.GetStage(), nxt)
		If b == 0
			If nxt < 0
				Debug.Notification("No later stage")
			ElseIf q.SetStage(nxt)
				Debug.Notification("Stage " + nxt + " set")
			Else
				Debug.Notification("Stage " + nxt + " could not be set")
			EndIf
		ElseIf b == 1
			If RestartConfirm.Show() == 0
				Restart(q)
				Return True
			EndIf
		ElseIf b == 2
			Return False
		Else
			Return True
		EndIf
	EndWhile
	Return True
EndFunction

Int Function QA(Int i)
	Int c = i / 128
	Int k = i - c * 128
	If c == 0
		If QA0
			Return QA0[k]
		EndIf
	ElseIf c == 1
		If QA1
			Return QA1[k]
		EndIf
	ElseIf c == 2
		If QA2
			Return QA2[k]
		EndIf
	ElseIf c == 3
		If QA3
			Return QA3[k]
		EndIf
	ElseIf c == 4
		If QA4
			Return QA4[k]
		EndIf
	ElseIf c == 5
		If QA5
			Return QA5[k]
		EndIf
	ElseIf c == 6
		If QA6
			Return QA6[k]
		EndIf
	ElseIf c == 7
		If QA7
			Return QA7[k]
		EndIf
	EndIf
	Return 0
EndFunction

Int Function QB(Int i)
	Int c = i / 128
	Int k = i - c * 128
	If c == 0
		If QB0
			Return QB0[k]
		EndIf
	ElseIf c == 1
		If QB1
			Return QB1[k]
		EndIf
	ElseIf c == 2
		If QB2
			Return QB2[k]
		EndIf
	ElseIf c == 3
		If QB3
			Return QB3[k]
		EndIf
	ElseIf c == 4
		If QB4
			Return QB4[k]
		EndIf
	ElseIf c == 5
		If QB5
			Return QB5[k]
		EndIf
	ElseIf c == 6
		If QB6
			Return QB6[k]
		EndIf
	ElseIf c == 7
		If QB7
			Return QB7[k]
		EndIf
	EndIf
	Return 0
EndFunction

Int Function S(Int i)
	Int c = i / 128
	Int k = i - c * 128
	If c == 0
		If S0
			Return S0[k]
		EndIf
	ElseIf c == 1
		If S1
			Return S1[k]
		EndIf
	ElseIf c == 2
		If S2
			Return S2[k]
		EndIf
	ElseIf c == 3
		If S3
			Return S3[k]
		EndIf
	ElseIf c == 4
		If S4
			Return S4[k]
		EndIf
	ElseIf c == 5
		If S5
			Return S5[k]
		EndIf
	ElseIf c == 6
		If S6
			Return S6[k]
		EndIf
	ElseIf c == 7
		If S7
			Return S7[k]
		EndIf
	ElseIf c == 8
		If S8
			Return S8[k]
		EndIf
	ElseIf c == 9
		If S9
			Return S9[k]
		EndIf
	ElseIf c == 10
		If S10
			Return S10[k]
		EndIf
	ElseIf c == 11
		If S11
			Return S11[k]
		EndIf
	ElseIf c == 12
		If S12
			Return S12[k]
		EndIf
	ElseIf c == 13
		If S13
			Return S13[k]
		EndIf
	ElseIf c == 14
		If S14
			Return S14[k]
		EndIf
	ElseIf c == 15
		If S15
			Return S15[k]
		EndIf
	ElseIf c == 16
		If S16
			Return S16[k]
		EndIf
	ElseIf c == 17
		If S17
			Return S17[k]
		EndIf
	ElseIf c == 18
		If S18
			Return S18[k]
		EndIf
	ElseIf c == 19
		If S19
			Return S19[k]
		EndIf
	ElseIf c == 20
		If S20
			Return S20[k]
		EndIf
	ElseIf c == 21
		If S21
			Return S21[k]
		EndIf
	ElseIf c == 22
		If S22
			Return S22[k]
		EndIf
	ElseIf c == 23
		If S23
			Return S23[k]
		EndIf
	ElseIf c == 24
		If S24
			Return S24[k]
		EndIf
	ElseIf c == 25
		If S25
			Return S25[k]
		EndIf
	ElseIf c == 26
		If S26
			Return S26[k]
		EndIf
	ElseIf c == 27
		If S27
			Return S27[k]
		EndIf
	ElseIf c == 28
		If S28
			Return S28[k]
		EndIf
	ElseIf c == 29
		If S29
			Return S29[k]
		EndIf
	ElseIf c == 30
		If S30
			Return S30[k]
		EndIf
	ElseIf c == 31
		If S31
			Return S31[k]
		EndIf
	ElseIf c == 32
		If S32
			Return S32[k]
		EndIf
	ElseIf c == 33
		If S33
			Return S33[k]
		EndIf
	ElseIf c == 34
		If S34
			Return S34[k]
		EndIf
	ElseIf c == 35
		If S35
			Return S35[k]
		EndIf
	ElseIf c == 36
		If S36
			Return S36[k]
		EndIf
	ElseIf c == 37
		If S37
			Return S37[k]
		EndIf
	ElseIf c == 38
		If S38
			Return S38[k]
		EndIf
	ElseIf c == 39
		If S39
			Return S39[k]
		EndIf
	ElseIf c == 40
		If S40
			Return S40[k]
		EndIf
	ElseIf c == 41
		If S41
			Return S41[k]
		EndIf
	ElseIf c == 42
		If S42
			Return S42[k]
		EndIf
	ElseIf c == 43
		If S43
			Return S43[k]
		EndIf
	ElseIf c == 44
		If S44
			Return S44[k]
		EndIf
	ElseIf c == 45
		If S45
			Return S45[k]
		EndIf
	ElseIf c == 46
		If S46
			Return S46[k]
		EndIf
	ElseIf c == 47
		If S47
			Return S47[k]
		EndIf
	EndIf
	Return 0
EndFunction

Message Function GetM(Int i)
	Int c = i / 128
	Int k = i - c * 128
	If c == 0
		If M0
			Return M0[k]
		EndIf
	ElseIf c == 1
		If M1
			Return M1[k]
		EndIf
	ElseIf c == 2
		If M2
			Return M2[k]
		EndIf
	ElseIf c == 3
		If M3
			Return M3[k]
		EndIf
	ElseIf c == 4
		If M4
			Return M4[k]
		EndIf
	ElseIf c == 5
		If M5
			Return M5[k]
		EndIf
	ElseIf c == 6
		If M6
			Return M6[k]
		EndIf
	ElseIf c == 7
		If M7
			Return M7[k]
		EndIf
	EndIf
	Return None
EndFunction

Quest Function GetC(Int i)
	Int c = i / 128
	Int k = i - c * 128
	If c == 0
		Return C0[k]
	ElseIf c == 1
		Return C1[k]
	ElseIf c == 2
		Return C2[k]
	ElseIf c == 3
		Return C3[k]
	ElseIf c == 4
		Return C4[k]
	ElseIf c == 5
		Return C5[k]
	ElseIf c == 6
		Return C6[k]
	ElseIf c == 7
		Return C7[k]
	EndIf
	Return None
EndFunction

Function SetC(Int i, Quest q)
	Int c = i / 128
	Int k = i - c * 128
	If c == 0
		C0[k] = q
	ElseIf c == 1
		C1[k] = q
	ElseIf c == 2
		C2[k] = q
	ElseIf c == 3
		C3[k] = q
	ElseIf c == 4
		C4[k] = q
	ElseIf c == 5
		C5[k] = q
	ElseIf c == 6
		C6[k] = q
	ElseIf c == 7
		C7[k] = q
	EndIf
EndFunction
