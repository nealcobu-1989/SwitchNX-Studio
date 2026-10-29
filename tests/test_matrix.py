"""Cross-check: many mod shapes, into an AE pack and an SE pack, through every
way in (add as it is, convert one, convert several), with the same rules
checked after each step, and every change undone at the end.

Shapes: plain, ESL, ESL-flagged .esp, HEDR 1.71, a Creation Club master, a
master + a plugin that needs it, AE/SE version folders, Mac junk, BSA only,
apostrophe in the name, an optional sub-mod folder, a FOMOD.
"""
import hashlib
import shutil
import struct
import sys
import time
import zipfile
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tests"))
pytest.importorskip("etcpak")
pytestmark = pytest.mark.skipif(not shutil.which("ffmpeg"), reason="needs ffmpeg")

from skynx import knowledge as K  # noqa: E402
from skynx.audit import run_audit  # noqa: E402
from skynx.bsa import read_bsa, write_bsa  # noqa: E402
from skynx.ccc import parse_ccc  # noqa: E402
from skynx.history import list_history, undo  # noqa: E402
from skynx.ini import parse_ini  # noqa: E402
from skynx.pack import Pack  # noqa: E402
from skynx.plugin import FLAG_LIGHT, read_header  # noqa: E402
from test_convert import BASE_INIS, FAKE, dds, make_fomod_zip, plugin_bytes  # noqa: E402
from test_requirements import nif  # noqa: E402

FACEGEOM = "meshes\\actors\\character\\facegendata\\facegeom\\"


def bsa(dest: Path, files: dict[str, bytes]) -> Path:
    tmp = dest.parent / (".src-" + dest.name)
    pairs = []
    for i, (p, data) in enumerate(files.items()):
        f = tmp / str(i)
        f.parent.mkdir(parents=True, exist_ok=True)
        f.write_bytes(data)
        pairs.append((p, f))
    dest.parent.mkdir(parents=True, exist_ok=True)
    write_bsa(pairs, dest)
    shutil.rmtree(tmp)
    return dest


def shapes(src: Path) -> dict[str, Path]:
    """name -> folder or archive of a Switch-ready mod (textures inside BSAs)."""
    out = {}

    def folder(name, files):
        d = src / name
        d.mkdir(parents=True)
        for rel, data in files.items():
            p = d / rel
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_bytes(data)
        out[name] = d
        return d
    tex = {"textures\\m\\a.dds": dds(64, 64)}
    d = folder("Plain", {"Plain.esp": plugin_bytes(["Skyrim.esm"])})
    bsa(d / "Plain.bsa", tex)
    d = folder("Lighty", {"Lighty.esl": plugin_bytes(["Skyrim.esm"], flags=FLAG_LIGHT)})
    bsa(d / "Lighty.bsa", {**tex, FACEGEOM + "lighty.esl\\00000801.nif": nif([])})
    folder("Flagged", {"Flagged.esp": plugin_bytes(["Skyrim.esm"], flags=FLAG_LIGHT)})
    folder("Fishy", {"Fishy.esp": plugin_bytes(["Skyrim.esm", "ccBGSSSE001-Fish.esm"])})
    folder("Needs Lighty", {"Needs Lighty.esp": plugin_bytes(["Skyrim.esm", "Lighty.esl"])})
    d = folder("Only BSA", {})
    bsa(d / "OnlyBsa.bsa", {"meshes\\ob\\x.nif": nif([])})
    folder("Ryns", {"Ryn's Thing.esp": plugin_bytes(["Skyrim.esm"])})
    d = folder("Auri", {"Auri.esp": plugin_bytes(["Skyrim.esm"]),
                        "Auri Optional/AuriExtra.esp": plugin_bytes(["Skyrim.esm"])})
    d = folder("Heart", {"Heart.esp": plugin_bytes(["Skyrim.esm"]),
                         "Body Option/Heart Body.esp": plugin_bytes(["Skyrim.esm", "Heart.esp"])})
    bsa(d / "Heart - Textures.bsa", tex)
    bsa(d / "Body Option" / "Heart - Textures.bsa", {"textures\\m\\b.dds": dds(64, 64)})
    z = src / "Versions.zip"
    with zipfile.ZipFile(z, "w") as zf:
        zf.writestr("Versions_AE/Versions.esp", plugin_bytes(["Skyrim.esm"], flags=FLAG_LIGHT))
        zf.writestr("Versions_SE/Versions.esp", plugin_bytes(["Skyrim.esm"]))
        zf.writestr("__MACOSX/Versions_AE/._Versions.esp", b"\0\5junk")
        zf.writestr("Versions_SE/._Versions.esp", b"junk")
    out["Versions"] = z
    out["Fomod"] = make_fomod_zip(src)
    return out


def snapshot(root: Path) -> dict[str, str]:
    out = {}
    for p in sorted(root.rglob("*")):
        rel = p.relative_to(root).as_posix()
        if p.is_file() and not rel.startswith(".skynx/"):
            out[rel] = hashlib.sha1(p.read_bytes()).hexdigest()
    return out


def check(pack: Pack, allowed_crit: set[str] = frozenset()) -> list[str]:
    """The rules every pack must keep. Returns what broke."""
    pack = Pack.open(pack.root)
    bad = []
    data = pack.data_dir
    names = {p.name.lower(): p for p in data.iterdir() if p.is_file()}
    if [n for n in names if n.startswith("._")]:
        bad.append("mac junk in Data")
    game = {m.lower() for m in K.VANILLA_MASTERS + K.SWITCH_MASTERS + K.AE_CC_PLUGINS}
    for e in pack.list_entries:
        low = e.lower()
        if low.startswith("#") or low in game:
            continue
        if low not in names:
            bad.append(f"listed but not in Data: {e}")
        if low.startswith("._"):
            bad.append(f"junk in the list: {e}")
    if pack.mode == "AE" and len(pack.list_path.read_bytes()) > K.CCC_BYTE_LIMIT:
        bad.append(".ccc over 4096")
    for ini in pack.ini_paths:
        p = parse_ini(ini.read_bytes())
        for key in ("sResourceArchiveList", "sResourceArchiveList2"):
            if len(", ".join(p.archive_list(key) or [])) > K.INI_ARCHIVE_LIMIT:
                bad.append(f"{ini.name} {key} over 1024")
    plugins = {n: p for n, p in names.items() if n.endswith((".esp", ".esm", ".esl"))}
    if pack.mode == "SE":
        for n, p in plugins.items():
            h = read_header(p)
            if n.endswith(".esl") or h.is_light_flag:
                bad.append(f"ESL in SE: {p.name}")
            if round(h.hedr_version, 2) >= 1.71:
                bad.append(f"HEDR 1.71 in SE: {p.name}")
    # voices / FaceGen folders inside the BSAs belong to a plugin that's there
    for n, p in names.items():
        if not n.endswith(".bsa"):
            continue
        for e in read_bsa(p).entries:
            path = e.path.lower()
            if path.startswith(FACEGEOM):
                owner = path[len(FACEGEOM):].split("\\", 1)[0]
                if owner.endswith(".esl") and owner not in plugins and owner[:-4] + ".esp" in plugins:
                    bad.append(f"{p.name}: FaceGen still under {owner}")
    crit = {f.code for f in run_audit(pack, deep=True).findings if f.severity == "critico"}
    extra = crit - set(allowed_crit)
    if extra:
        bad.append(f"Doctor critical: {sorted(extra)}")
    return sorted(set(bad))


def make_api(tmp_path, monkeypatch, edition):
    import importlib
    monkeypatch.setenv("APPDATA", str(tmp_path / "appdata"))
    monkeypatch.setenv("SKYNX_LIBRARY", str(tmp_path / "lib"))
    sys.path.insert(0, str(ROOT / "app"))
    import api as A
    importlib.reload(A)
    from skynx.builder import create_project
    api = A.Api()
    api._settings["tools_dir"] = str(FAKE)
    root = create_project(tmp_path / f"pack-{edition}", edition, BASE_INIS, "ussep" if edition == "AE" else "none")
    api.open_pack(str(root))
    wait(api)
    return api, root


def wait(api, j=None):
    while (api.progress(j) if j else api.progress())["busy"]:
        time.sleep(0.05)
    return api.progress(j) if j else api.progress()


def job(api, method, *args):
    r = getattr(api, method)(*args)
    if isinstance(r, dict) and "job" in r and r.get("ok") is not False:
        p = wait(api, r["job"])
        return p.get("result"), p.get("error")
    return r, (r.get("error") if isinstance(r, dict) and r.get("ok") is False else None)


@pytest.mark.parametrize("edition", ["AE", "SE"])
def test_every_shape_every_way_in(tmp_path, monkeypatch, edition):
    api, root = make_api(tmp_path, monkeypatch, edition)
    before = snapshot(root)
    src = shapes(tmp_path / "src")
    allowed = {"master-missing", "master-cc"} if edition == "SE" else set()   # Fishy needs CC on SE

    # 1. as they are (Switch-ready): what goes in, what is refused
    added, refused = [], {}
    for name in ["Plain", "Flagged", "Only BSA", "Versions", "Ryns", "Heart"]:
        r, err = job(api, "add_mod", str(src[name]))
        (refused.__setitem__(name, err) if err else added.append(name))
        assert not check(Pack.open(root), allowed), (name, check(Pack.open(root), allowed))
    assert not refused, refused        # on SE a flagged .esp loses the flag on the way in
    pack = Pack.open(root)
    if edition == "SE":
        assert round(read_header(pack.data_dir / "Plain.esp").hedr_version, 2) == 1.70   # 1.71 brought down
        assert not read_header(pack.data_dir / "Flagged.esp").is_light_flag
    assert not (pack.data_dir / "Heart Body.esp").exists()        # the option that replaces files stays out

    # 2. several at once, everything that's left (masters first, ESL -> ESP on SE)
    rest = [str(src[n]) for n in ["Lighty", "Needs Lighty", "Fishy", "Auri", "Fomod"] + list(refused)]
    v, err = job(api, "batch_add", rest)
    assert not err, err
    for it in v["items"]:
        if it["kind"] == "fomod":
            job(api, "batch_fomod_start", it["id"])
            job(api, "batch_fomod_finish", it["id"], {})
    v, _ = job(api, "batch_view")
    plan = [{"id": it["id"], "options": {"sdk": False}} for it in v["items"] if it["kind"] == "ready"]
    assert len(plan) == len(rest), v["items"]
    res, err = job(api, "batch_run", plan)
    assert not err, err
    failed = [(x["name"], x.get("error")) for x in res["results"] if not x["ok"]]
    assert not failed, failed
    problems = check(Pack.open(root), allowed)
    assert not problems, problems
    pack = Pack.open(root)
    if edition == "SE":
        assert (pack.data_dir / "Lighty.esp").exists() and not (pack.data_dir / "Lighty.esl").exists()
        assert read_header(pack.data_dir / "Needs Lighty.esp").masters[-1] == "Lighty.esp"
        notes = " ".join(n for x in res["results"] for n in x.get("notes", []))
        assert "Creation Club" in notes
    else:
        assert (pack.data_dir / "Lighty.esl").exists()

    # 3. every change undone, newest first: back to the empty pack, byte for byte
    for e in list_history(root):
        if not e.get("undone") and not e.get("is_undo"):
            undo(root, e["id"])
    assert snapshot(root) == before


def test_se_pack_fixes_an_esl_already_inside(tmp_path):
    """An ESL that got into an SE pack by hand: the Doctor turns it into an .esp,
    with its FaceGen folder, the list and the plugins that use it."""
    from skynx.builder import create_project
    from skynx.fixes import apply
    root = create_project(tmp_path / "se", "SE", BASE_INIS, "none")
    pack = Pack.open(root)
    d = pack.data_dir
    (d / "Lighty.esl").write_bytes(plugin_bytes(["Skyrim.esm"], flags=FLAG_LIGHT))
    (d / "User.esp").write_bytes(plugin_bytes(["Skyrim.esm", "Lighty.esl"]))
    bsa(d / "Lighty.bsa", {FACEGEOM + "lighty.esl\\00000801.nif": nif([])})
    lst = pack.list_path
    lst.write_bytes(lst.read_bytes() + b"Lighty.esl\nUser.esp\n")
    pack = Pack.open(root)
    f = next(x for x in run_audit(pack).findings if x.code == "plugin-esl-se")
    assert f.fix["kind"] == "esl_to_esp" and f.fix["to"] == "Lighty.esp"
    apply(pack, f.fix)
    pack = Pack.open(root)
    assert "Lighty.esp" in pack.list_entries and "Lighty.esl" not in pack.list_entries
    assert not read_header(d / "Lighty.esp").is_light_flag
    assert read_header(d / "User.esp").masters == ["Skyrim.esm", "Lighty.esp"]
    assert any(e.path.lower().startswith(FACEGEOM + "lighty.esp\\") for e in read_bsa(d / "Lighty.bsa").entries)
    assert not [x for x in run_audit(pack).findings if x.code == "plugin-esl-se"]


# ------------------------------------------------------------------ found by the independent review
def test_versions_in_tricky_layouts():
    from skynx import variants as VA

    def kept(files, ed):
        r = VA.choose(files, ed)
        return [f for f in files if not VA.skipped(f, r["skip"])]
    shared_parent = ["Bandolier SE/AE/Bandolier.esp", "Bandolier SE/SE/Bandolier.esp"]
    assert kept(shared_parent, "AE") == ["Bandolier SE/AE/Bandolier.esp"]
    assert kept(shared_parent, "SE") == ["Bandolier SE/SE/Bandolier.esp"]
    top_and_se = ["Mod.esl", "Mod.bsa", "SE Version/Mod.esl", "SE Version/Mod.bsa"]
    assert kept(top_and_se, "AE") == ["Mod.esl", "Mod.bsa"]
    assert kept(top_and_se, "SE") == ["SE Version/Mod.esl", "SE Version/Mod.bsa"]
    assert kept(["AE/Mod.esl", "SE/Mod.esp"], "SE") == ["SE/Mod.esp"]            # same mod, other extension
    option = ["H/Astrid.esp", "H/Heart - Textures.bsa", "H/Body/Body.esp", "H/Body/Heart - Textures.bsa"]
    assert kept(option, "AE") == ["H/Astrid.esp", "H/Heart - Textures.bsa"]


def test_transfer_takes_the_destination_build_and_says_what_it_changed(tmp_path):
    from skynx.builder import create_project
    from skynx.transfer import apply_transfer, list_pack_mods, plan_transfer
    ae = Pack.open(create_project(tmp_path / "ae", "AE", BASE_INIS, "none"))
    se = create_project(tmp_path / "se", "SE", BASE_INIS, "none")
    with zipfile.ZipFile(ae.data_dir / "Vers.zip", "w") as z:
        z.writestr("Vers_AE/Vers.esp", plugin_bytes(["Skyrim.esm"], flags=FLAG_LIGHT))
        z.writestr("Vers_SE/Vers.esp", plugin_bytes(["Skyrim.esm"]) + b"SEVERSION")
    (ae.data_dir / "Flag.esp").write_bytes(plugin_bytes(["Skyrim.esm"], flags=FLAG_LIGHT))
    (ae.data_dir / "Fishy.esp").write_bytes(plugin_bytes(["Skyrim.esm", "ccBGSSSE001-Fish.esm"]))
    ae.list_path.write_bytes(ae.list_path.read_bytes() + b"\r\nFlag.esp\r\nFishy.esp\r\n")
    ae = Pack.open(ae.root)
    units = list_pack_mods(ae)
    tp = plan_transfer(ae, Pack.open(se), [u.id for u in units], units=units)
    assert any("Fishy" in r["name"] for r in tp.refused)                      # needs CC: never on SE
    notes = " ".join(n[0] for n in tp.notes)
    assert "Flag.esp loses its ESL flag" in notes and "HEDR 1.71 to 1.70" in notes
    apply_transfer(tp)
    ps = Pack.open(se)
    assert (ps.data_dir / "Vers.esp").read_bytes().endswith(b"SEVERSION")
    assert not read_header(ps.data_dir / "Flag.esp").is_light_flag
    assert not (ps.data_dir / "Fishy.esp").exists()
    assert not check(ps)


def test_extract_from_data_follows_the_add_rules_on_se(tmp_path):
    from skynx.builder import create_project
    from skynx.fixes import FixError, apply  # noqa: F401
    pack = Pack.open(create_project(tmp_path / "se", "SE", BASE_INIS, "none"))
    with zipfile.ZipFile(pack.data_dir / "Flaggy.zip", "w") as z:
        z.writestr("Flag.esp", plugin_bytes(["Skyrim.esm"], flags=FLAG_LIGHT))
        z.writestr("Fishy.esp", plugin_bytes(["Skyrim.esm", "ccBGSSSE001-Fish.esm"]))
    tmp = tmp_path / "ob"
    bsa(tmp / "OnlyBsa.bsa", {"meshes\\ob\\x.nif": nif([])})
    with zipfile.ZipFile(pack.data_dir / "OnlyBsa.zip", "w") as z:
        z.write(tmp / "OnlyBsa.bsa", "OnlyBsa.bsa")
    with zipfile.ZipFile(pack.data_dir / "Lighty.zip", "w") as z:
        z.writestr("Lighty.esl", plugin_bytes(["Skyrim.esm"], flags=FLAG_LIGHT))
    pack = Pack.open(pack.root)
    fixes = {f.subject: f.fix for f in run_audit(pack).findings if f.code == "data-archive"}
    apply(pack, fixes["Flaggy.zip"])
    apply(pack, fixes["OnlyBsa.zip"])
    with pytest.raises(Exception, match="Convert"):
        apply(pack, fixes["Lighty.zip"])                       # an .esl goes through Convert
    pack = Pack.open(pack.root)
    assert "Flag.esp" in pack.list_entries and not read_header(pack.data_dir / "Flag.esp").is_light_flag
    assert "Fishy.esp" not in pack.list_entries                      # in Data, not switched on
    assert any("OnlyBsa.bsa" in (parse_ini(i.read_bytes()).archive_list("sResourceArchiveList") or [])
               for i in pack.ini_paths)
    assert not (pack.data_dir / "Flaggy.zip").exists() and (pack.data_dir / "Lighty.zip").exists()
    titles = [e["title"] for e in list_history(pack.root)]
    assert titles[0] == "Extract OnlyBsa.zip into Data"


def test_a_failed_master_stops_its_dependents(tmp_path, monkeypatch):
    from skynx import converter as CV
    api, root = make_api(tmp_path, monkeypatch, "AE")
    src = tmp_path / "src"
    for name, plugs in [("Base", {"Base.esp": ["Skyrim.esm"]}), ("Dep", {"Dep.esp": ["Skyrim.esm", "Base.esp"]})]:
        d = src / name
        d.mkdir(parents=True)
        for p, ms in plugs.items():
            (d / p).write_bytes(plugin_bytes(ms))
        bsa(d / f"{name}.bsa", {"textures\\x\\a.dds": dds(64, 64)})
    v, _ = job(api, "batch_add", [str(src / "Dep"), str(src / "Base")])
    real = CV.convert

    def fake(pack, an, *a, **kw):
        if an.plugins and an.plugins[0]["name"] == "Base.esp":
            raise CV.ConvertError("broken", "roto")
        return real(pack, an, *a, **kw)
    monkeypatch.setattr(CV, "convert", fake)
    res, err = job(api, "batch_run", [{"id": i["id"], "options": {"sdk": False}} for i in v["items"]])
    by = {x["name"]: x for x in res["results"]}
    assert not by["Base"]["ok"] and not by["Dep"]["ok"] and "Base" in by["Dep"]["error"]
    assert "Dep.esp" not in Pack.open(root).list_entries
    for i in api.batch_view()["items"]:
        api.batch_remove(i["id"])                       # failed ones must be read again
    job(api, "batch_add", [str(src / "Dep")])
    # a name the game uses is refused before anything runs
    it = next(i for i in api.batch_view()["items"] if i["kind"] == "ready")
    r = api.batch_run([{"id": it["id"], "options": {"names": {"Dep.esp": "Skyrim - Textures0.esp"}}}])
    assert not r["ok"] and r["problems"]
