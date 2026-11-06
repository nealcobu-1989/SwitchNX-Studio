"""SkyNX Test Tools: the plugin and the pack's quest list in it."""
import struct

from skynx import nxtest as NX
from skynx.records import iter_records

TPL = {
    "MGEF": [("EDID", b"x\0"), ("VMAD", b""), ("FULL", b"x\0"), ("DNAM", b"\0")],
    "SPEL": [("EDID", b"x\0"), ("FULL", b"x\0"), ("DESC", b"x\0"), ("EFID", b"\0" * 4), ("EFIT", b"\0" * 12)],
}


def _table(n=3, stages=(0, 10, 20, 200)):
    quests = [[i % 2, 0x800 + i, f"Quest {i}", list(stages)] for i in range(n)]
    return {"files": ["Skyrim.esm", "Mod.esp"], "quests": quests, "version": 0x1234ABCD, "left_out": 0}


def _vmad_props(data: bytes) -> dict:
    """{name: (type, raw value)} of a single-script VMAD."""
    o = 6
    n = struct.unpack_from("<H", data, o)[0]; o += 2 + n + 1
    count = struct.unpack_from("<H", data, o)[0]; o += 2
    out = {}
    for _ in range(count):
        n = struct.unpack_from("<H", data, o)[0]; name = data[o + 2:o + 2 + n].decode(); o += 2 + n
        typ = data[o]; o += 2
        if typ == 1:
            val = data[o:o + 8]; o += 8
        elif typ == 3:
            val = struct.unpack_from("<i", data, o)[0]; o += 4
        elif typ == 11:
            c = struct.unpack_from("<I", data, o)[0]; val = [struct.unpack_from("<HhI", data, o + 4 + 8 * k)[2]
                                                              for k in range(c)]; o += 4 + 8 * c
        elif typ == 12:
            c = struct.unpack_from("<I", data, o)[0]; o += 4; val = []
            for _k in range(c):
                n = struct.unpack_from("<H", data, o)[0]; val.append(data[o + 2:o + 2 + n].decode()); o += 2 + n
        elif typ == 13:
            c = struct.unpack_from("<I", data, o)[0]; val = list(struct.unpack_from(f"<{c}i", data, o + 4))
            o += 4 + 4 * c
        else:
            raise AssertionError(typ)
        out[name] = (typ, val)
    return out


def _quest_props(esp: bytes) -> dict:
    q = next(r for r in iter_records(esp, types=["QUST"]))
    return _vmad_props(dict(q.subrecords())["VMAD"])


def test_plugin_has_one_message_per_quest_and_the_version():
    esp = NX.build_esp(TPL, _table(5))
    msgs = [r for r in iter_records(esp, types=["MESG"])]
    assert len(msgs) == 10 + 5                   # 10 menus (Mod creatures since build 3) + one per quest
    names = [dict(r.subrecords())["DESC"] for r in msgs if r.formid >= NX.MSG_QUEST0]
    assert names[0].startswith(b"Quest 0\n(Skyrim.esm)")
    p = _quest_props(esp)
    assert p["QuestCount"][1] == 5 and p["DataVersion"][1] == 0x1234ABCD
    assert p["Files"][1] == ["Skyrim.esm", "Mod.esp"]
    assert p["M0"][1] == [NX.MSG_QUEST0 + i for i in range(5)]


def test_stored_version_reads_back(tmp_path):
    f = tmp_path / "NXTest.esp"
    f.write_bytes(NX.build_esp(TPL, _table()))
    assert NX.stored_version(f) == 0x1234ABCD


def test_without_quests_the_plugin_still_builds():
    esp = NX.build_esp(TPL)
    p = _quest_props(esp)
    assert p["QuestCount"][1] == 0 and "QA0" not in p


def _decode(p, i):
    """What the script does (NXTestQuestScript: QA, QB, StageAt)."""
    def get(prefix, k):
        c, j = k // 128, k % 128
        return p[f"{prefix}{c}"][1][j]
    qa = get("QA", i)
    f = qa // 16777216
    b = get("QB", i)
    first, count = b // 256, b % 256
    stages = []
    for n in range(first, first + count):
        v = get("S", n // 2)
        hi = v // 65536
        stages.append(hi if n % 2 else v - hi * 65536)
    return f, qa - f * 16777216, stages


def test_chunks_and_packing_decode_like_the_script():
    quests = [[i % 3, 0xFFF000 + i, f"Q{i}", [0, 5 + i % 7, 100, 9999][: 1 + i % 4]] for i in range(300)]
    table = {"files": ["A.esm", "B.esp", "C.esl"], "quests": quests, "version": 1, "left_out": 0}
    p = _quest_props(NX.build_esp(TPL, table))
    assert "QA2" in p and "QA3" not in p
    for i in (0, 1, 127, 128, 129, 299):
        f, local, stages = _decode(p, i)
        assert (f, local, stages) == (quests[i][0], quests[i][1], quests[i][3])


def _qust(fid, full=b"Name\0", stages=(0, 10), objs=1):
    subs = b"FULL" + struct.pack("<H", len(full)) + full
    for s in stages:
        subs += b"INDX" + struct.pack("<H", 4) + struct.pack("<hBB", s, 0, 0)
    for k in range(objs):
        subs += b"QOBJ" + struct.pack("<H", 2) + struct.pack("<h", k * 10)
    return b"QUST" + struct.pack("<IIIHHHH", len(subs), 0, fid, 0, 0, 44, 0) + subs


def _esp(path, masters, records):
    hedr = b"HEDR" + struct.pack("<H", 12) + struct.pack("<fiI", 1.7, len(records), 0x800)
    mast = b"".join(b"MAST" + struct.pack("<H", len(m) + 1) + m.encode() + b"\0"
                    + b"DATA" + struct.pack("<H", 8) + bytes(8) for m in masters)
    tes4 = b"TES4" + struct.pack("<IIIHHHH", len(hedr) + len(mast), 0, 0, 0, 0, 44, 0) + hedr + mast
    body = b"".join(records)
    grup = b"GRUP" + struct.pack("<I", 24 + len(body)) + b"QUST" + bytes(12) + body
    path.write_bytes(tes4 + grup)


def test_plugin_quests_reads_names_stages_and_owner(tmp_path):
    f = tmp_path / "Mod.esp"
    _esp(f, ["Skyrim.esm"], [_qust(0x00012345, stages=(20, 0, 10)), _qust(0x01000801, b"Mine\0", objs=0)])
    localized, qs = NX._plugin_quests(f, "Mod.esp")
    assert not localized
    assert qs[0]["owner"] == "Skyrim.esm" and qs[0]["local"] == 0x12345 and qs[0]["stages"] == [0, 10, 20]
    assert qs[1]["owner"] == "Mod.esp" and qs[1]["local"] == 0x801 and qs[1]["objs"] == 0


class _H:
    def __init__(self, path):
        self.path, self.error, self.name = path, None, path.name


class _Pack:
    def __init__(self, tmp_path, listed):
        self.data_dir = tmp_path
        self.lang_inis = []
        self.list_entries = listed
        self.plugins = {}
        for n in ("Mod.esp", "NXTest.esp"):
            if (tmp_path / n).exists():
                self.plugins[n.lower()] = _H(tmp_path / n)

    def load_order(self):
        return [(e, "lista") for e in self.list_entries]


def test_quest_table_keeps_trackable_quests_and_the_last_edit_wins(tmp_path):
    _esp(tmp_path / "Mod.esp", ["Skyrim.esm"], [_qust(0x00012345, b"Base\0"), _qust(0x01000801, b"Mine\0"),
                                                 _qust(0x01000802, b"NoObj\0", objs=0)])
    t = NX.quest_table(_Pack(tmp_path, ["Mod.esp"]), None)
    assert t["files"] == ["Skyrim.esm", "Mod.esp"]
    assert [q[2] for q in t["quests"]] == ["Base", "Mine"]


def test_pending_only_when_on_and_changed(tmp_path):
    _esp(tmp_path / "Mod.esp", ["Skyrim.esm"], [_qust(0x01000801, b"Mine\0")])
    (tmp_path / "NXTest.esp").write_bytes(NX.build_esp(TPL))
    assert NX.pending(_Pack(tmp_path, ["Mod.esp", "#NXTest.esp"]), None) is None
    job = NX.pending(_Pack(tmp_path, ["Mod.esp", "NXTest.esp"]), None)
    assert job and job["quests"] == 1
    (tmp_path / "NXTest.esp").write_bytes(job["data"])
    assert NX.pending(_Pack(tmp_path, ["Mod.esp", "NXTest.esp"]), None) is None


def test_mod_creatures_menu_and_heal_in_player():
    data = NX.build_esp({"MGEF": [("EDID", b"x\0"), ("VMAD", b""), ("FULL", b""), ("DNAM", b"")],
                         "SPEL": [("EDID", b"x\0")]})
    msgs = {r.formid: r for r in iter_records(data) if r.type == "MESG"}
    buttons = lambda fid: [d.rstrip(b"\0").decode() for s, d in msgs[fid].subrecords() if s == "ITXT"]
    assert "Mod creatures" in buttons(NX.MSG_MAIN) and "Heal" not in buttons(NX.MSG_MAIN)
    assert "Heal" in buttons(NX.MSG_PLAYER)
    assert buttons(NX.MSG_MODSPAWN) == ["Harkon (combat form)", "Karstaag", "Werebear", "Mihail mix", "Back"]
    mgef = next(r for r in iter_records(data) if r.type == "MGEF")
    assert b"ModSpawnMenu" in dict(mgef.subrecords())["VMAD"]
