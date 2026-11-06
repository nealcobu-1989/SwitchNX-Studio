"""Writes source/NXTestQuestScript.psc. The quest data comes in chunks of 128
(the most a Papyrus array is sure to hold), so the getters are generated."""
from pathlib import Path

QCH, SCH = 8, 48            # 1024 quests, 48*128 ints = 12288 stages (two per int)


def chain(fn, ret, prefix, n, body):
    out = [f"{ret} Function {fn}(Int i)", "\tInt c = i / 128", "\tInt k = i - c * 128"]
    for c in range(n):
        out.append(f"\t{'If' if c == 0 else 'ElseIf'} c == {c}")
        out.append(f"\t\t{body.format(p=f'{prefix}{c}')}")
    out += ["\tEndIf", "\tReturn " + ("None" if ret not in ("Int",) else "0"), "EndFunction", ""]
    return out


def setter(prefix, n):
    out = ["Function SetC(Int i, Quest q)", "\tInt c = i / 128", "\tInt k = i - c * 128"]
    for c in range(n):
        out.append(f"\t{'If' if c == 0 else 'ElseIf'} c == {c}")
        out.append(f"\t\t{prefix}{c}[k] = q")
    out += ["\tEndIf", "EndFunction", ""]
    return out


HEAD = '''Scriptname NXTestQuestScript extends Quest
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
{qa}
{qb}
{s}
{m}

Quest[] {c}
Int CachedVersion = -1
'''

BODY = r'''
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
	{newcache}
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
'''


def main():
    qa = "\n".join(f"Int[] Property QA{c} Auto" for c in range(QCH))
    qb = "\n".join(f"Int[] Property QB{c} Auto" for c in range(QCH))
    s = "\n".join(f"Int[] Property S{c} Auto" for c in range(SCH))
    m = "\n".join(f"Message[] Property M{c} Auto" for c in range(QCH))
    c = ", ".join(f"C{c}" for c in range(QCH))
    head = HEAD.replace("{qa}", qa).replace("{qb}", qb).replace("{s}", s).replace("{m}", m)
    head = head.replace("Quest[] {c}", "\n".join(f"Quest[] C{c}" for c in range(QCH)))
    body = BODY.replace("{newcache}", "\n\t".join(f"C{c} = new Quest[128]" for c in range(QCH)))
    lines = [head, body]
    lines += chain("QA", "Int", "QA", QCH, "If {p}\n\t\t\tReturn {p}[k]\n\t\tEndIf")
    lines += chain("QB", "Int", "QB", QCH, "If {p}\n\t\t\tReturn {p}[k]\n\t\tEndIf")
    lines += chain("S", "Int", "S", SCH, "If {p}\n\t\t\tReturn {p}[k]\n\t\tEndIf")
    lines += chain("GetM", "Message", "M", QCH, "If {p}\n\t\t\tReturn {p}[k]\n\t\tEndIf")
    lines += chain("GetC", "Quest", "C", QCH, "Return {p}[k]")
    lines += setter("C", QCH)
    Path(__file__).resolve().parents[1].joinpath("source", "NXTestQuestScript.psc").write_text(
        "\n".join(x if isinstance(x, str) else "" for x in lines).replace("\r", ""))


if __name__ == "__main__":
    main()
