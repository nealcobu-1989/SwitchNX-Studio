"""The bridge between the window (HTML/JS) and the engine.

Every public method returns JSON-serialisable data. Long jobs run in a
thread; the page polls `progress()`. Attributes start with "_" so pywebview
doesn't try to expose them to the page.
"""
from __future__ import annotations

import re
import json
import os
import shutil
import sys
import threading
import time
import traceback
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from skynx import __version__, knowledge as K  # noqa: E402
from skynx import i18n as I18N  # noqa: E402
from skynx.audit import run_audit  # noqa: E402
from skynx.builder import add_mod, create_project, mods_view, remove_mod  # noqa: E402
from skynx.ccc import parse_ccc, reorder  # noqa: E402
from skynx.deploy import deploy, import_from_sd  # noqa: E402
from skynx.errors import SkynxError  # noqa: E402
from skynx.fixes import FixError, apply, preview  # noqa: E402
from skynx.history import Transaction, list_history, recover_interrupted, undo  # noqa: E402
from skynx.pack import Pack  # noqa: E402
from skynx import converter as CV  # noqa: E402
from skynx.tools import locate  # noqa: E402

APP_NAME = "SwitchNX Studio"


def _vanilla_status(folder) -> str:
    try:
        from skynx.vanilla import status
        return status(Path(folder) if folder else None, settings_path().parent / "cache")
    except Exception:  # noqa: BLE001
        return "unset"


def _vanilla_summary(folder) -> dict:
    try:
        from skynx.vanilla import summary
        return summary(Path(folder) if folder else None, settings_path().parent / "cache")
    except Exception:  # noqa: BLE001
        return {}


def C_entries(raw: bytes) -> list:
    from skynx.ccc import parse_ccc
    return parse_ccc(raw).entries if raw else []


class _Busy(Exception):
    """A background job holds the slot."""


# Default folders under C:\SkyNX, newest names first (older names still work).
DEFAULT_FOLDERS = {
    "ussep_dir": [r"C:\SkyNX\Base Mods\USSEP", r"C:\SkyNX\USSEP"],
    "vanilla_dir": [r"C:\SkyNX\Vanilla\BSAs", r"C:\SkyNX\Vanilla"],
    "inis_dir": [r"C:\SkyNX\Vanilla\INIs", r"C:\SkyNX\original inis"],
}


def settings_path() -> Path:
    base = os.environ.get("APPDATA") or str(Path.home() / ".config")
    p = Path(base) / APP_NAME
    p.mkdir(parents=True, exist_ok=True)
    return p / "settings.json"


def _sweep_temp(max_age_h: float = 6.0) -> None:
    """Remove staging folders left behind by a run that was closed mid-job."""
    import shutil
    import tempfile
    import time
    base = Path(tempfile.gettempdir())
    now = time.time()
    try:
        for d in base.iterdir():
            if d.is_dir() and d.name.startswith(("skynx-conv-", "skynx-mod-")):
                try:
                    if now - d.stat().st_mtime > max_age_h * 3600:
                        shutil.rmtree(d, ignore_errors=True)
                except OSError:
                    pass
    except OSError:
        pass


class Api:
    def __init__(self):
        self._run_lock = threading.Lock()
        self._window = None
        self._pack: Pack | None = None
        self._result = None
        self._progress = {"busy": False, "label": "", "i": 0, "n": 0, "error": None}
        self._settings = self._load_settings()
        self._analysis = None
        self._fomod = None
        self._batch: dict = {}
        _sweep_temp()
        import atexit
        atexit.register(self._drop_analysis)
        atexit.register(self._clear_import_cache)
        try:        # archives extracted to bring mods from, left by a run that didn't close
            ic = self._library_root() / ".import-cache"
            for d in (ic.iterdir() if ic.is_dir() else []):
                if time.time() - d.stat().st_mtime > 6 * 3600:
                    shutil.rmtree(d, ignore_errors=True)
        except OSError:
            pass

    @property
    def busy(self) -> bool:
        return bool(self._progress.get("busy"))

    # ------------------------------------------------------------ helpers
    @property
    def _lang(self) -> str:
        return self._settings.get("lang", "en")

    def _err(self, e: Exception) -> str:
        return e.text(self._lang) if isinstance(e, SkynxError) else str(e)

    def _load_settings(self) -> dict:
        try:
            return json.loads(settings_path().read_text(encoding="utf-8"))
        except Exception:  # noqa: BLE001
            return {"recent": [], "tools_dir": r"C:\SkyNX\tools", "lang": "en"}

    def _save_settings(self):
        settings_path().write_text(json.dumps(self._settings, indent=1, ensure_ascii=False),
                                   encoding="utf-8")

    def _audit_out(self) -> dict:
        return {"pack": self._pack_summary(), "audit": self._result.to_dict(self._lang),
                "sync": getattr(self, "_sync_report", None)}

    def _pack_summary(self) -> dict:
        p = self._pack
        from skynx import draft as DR
        d = DR.load(p.root)
        from skynx import workshop as WS
        b = WS.load(p.root)
        proj = None
        if p.project:
            from skynx import project as PJ
            i = PJ.read_info(p.root)
            proj = {"name": i.get("name") or p.root.name, "last_build": i.get("last_build"),
                    "last_sd": i.get("last_sd"), "origin": i.get("origin") or {}}
        return {"root": str(p.root), "name": proj["name"] if proj else p.root.name, "mode": p.mode,
                "project": proj,
                "list": p.list_path.name if p.list_path else None,
                "inis": [x.name for x in p.ini_paths],
                "draft": {"name": d.get("name"), "excluded": len(d["excluded"])} if d else None,
                "bench": {"name": b.get("name"), "kind": b.get("kind"), "edit_of": b.get("edit_of")} if b else None}

    def _remember(self, path: str, replaces: str | None = None):
        rec = [r for r in self._settings.get("recent", []) if r not in (path, replaces)]
        self._settings["recent"] = [path] + rec[:7]
        self._settings["last_open"] = path
        self._save_settings()

    def _forget_recent(self, path: str):
        rec = self._settings.get("recent", [])
        if path in rec:
            self._settings["recent"] = [r for r in rec if r != path]
            self._save_settings()
        if self._settings.get("last_open") == path:
            self._settings.pop("last_open", None)
            self._save_settings()

    def _relocate(self, path: Path) -> Path | None:
        """A pack folder that is no longer where it was: look for a folder with
        the same name among the Library's packs (where it usually went)."""
        name = path.name.lower()
        if not name:
            return None
        try:
            from skynx import library as L
            for row in L.list_library(self._library_root(), health=False):
                p = Path(row["path"])
                if row["kind"] == "pack" and p.name.lower() == name and p.is_dir():
                    pk = Pack.open(p)
                    if pk.base_dir is not None:
                        return p
        except Exception:  # noqa: BLE001
            return None
        return None

    # ------------------------------------------------------------ settings
    def _tools(self):
        return locate(self._settings.get("tools_dir") or None)

    def state(self) -> dict:
        ts = self._tools()
        return {"version": __version__, "app": APP_NAME, "lang": self._lang,
                "recent": self._settings.get("recent", []),
                "tools_dir": str(ts.folder or self._settings.get("tools_dir") or ""),
                "tools": ts.status(), "ram_cap": self._settings.get("ram_cap"),
                "library_dir": str(self._library_root()),
                "nexus_key": bool(self._settings.get("nexus_key")),
                "nexus_user": self._settings.get("nexus_user"),
                "vanilla_dir": self._folder("vanilla_dir"),
                "vanilla_status": _vanilla_status(self._folder("vanilla_dir")),
                "vanilla_list": _vanilla_summary(self._folder("vanilla_dir")),
                "inis_dir": self._folder("inis_dir"),
                "ussep_dir": self._folder("ussep_dir"),
                "pack": self._pack_summary() if self._pack else None}

    def set_ram_cap(self, mb) -> dict:
        try:
            v = int(float(mb))
        except (TypeError, ValueError):
            v = 0
        self._settings["ram_cap"] = v if v > 0 else None
        self._save_settings()
        return self.state()

    def set_tools_dir(self, path: str) -> dict:
        self._settings["tools_dir"] = path
        self._save_settings()
        return self.state()

    def set_lang(self, lang: str) -> dict:
        self._settings["lang"] = "es" if lang == "es" else "en"
        self._save_settings()
        return self.state()

    # ------------------------------------------------------------ dialogs
    def pick_folder(self) -> str | None:
        if not self._window:
            return None
        import webview  # type: ignore
        kind = getattr(getattr(webview, "FileDialog", None), "FOLDER", None) or webview.FOLDER_DIALOG
        res = self._window.create_file_dialog(kind)
        return res[0] if res else None

    def pick_files(self) -> list:
        """Several archives (or plugins/BSAs) at once."""
        if not self._window:
            return []
        import webview  # type: ignore
        kind = getattr(getattr(webview, "FileDialog", None), "OPEN", None) or webview.OPEN_DIALOG
        res = self._window.create_file_dialog(kind, allow_multiple=True, file_types=(
            "Mods and modpacks (*.7z;*.zip;*.rar;*.esp;*.esm;*.esl;*.bsa)", "All files (*.*)"))
        return list(res or [])

    def pick_archive(self) -> str | None:
        if not self._window:
            return None
        import webview  # type: ignore
        kind = getattr(getattr(webview, "FileDialog", None), "OPEN", None) or webview.OPEN_DIALOG
        res = self._window.create_file_dialog(kind, file_types=("Mods (*.7z;*.zip;*.rar)", "All files (*.*)"))
        return res[0] if res else None

    # ------------------------------------------------------------ progress
    def progress(self, job_id=None) -> dict:
        """The running job, or a finished one by id (its result is kept even
        if another job has started since)."""
        if job_id is not None:
            done = getattr(self, "_done", {}).get(job_id)
            if done is not None:
                return dict(done)
            cur = dict(self._progress)
            if cur.get("job") == job_id:
                return cur
            return {"busy": False, "job": job_id, "error": "Lost", "result": None}
        return dict(self._progress)

    def _run(self, label, fn, *args):
        with self._run_lock:
            if self._progress.get("busy"):
                return {"ok": False, "busy": True,
                        "error": "Busy" if self._lang == "en" else "Hay otra tarea en curso"}
            self._job_seq = getattr(self, "_job_seq", 0) + 1
            jid = self._job_seq
            prog = {"busy": True, "label": label, "i": 0, "n": 0, "error": None,
                    "result": None, "job": jid}
            self._progress = prog

        def tick(text, i=0, n=0):
            prog.update(label=I18N.progress_label(text, self._lang), i=i, n=n)

        def job():
            try:
                prog["result"] = fn(tick, *args)
            except Exception as e:  # noqa: BLE001
                prog["error"] = self._err(e)
                prog["trace"] = traceback.format_exc()
            finally:
                done = getattr(self, "_done", {})
                done[jid] = {k: v for k, v in prog.items() if k != "trace"} | {"busy": False}
                for old in sorted(done)[:-20]:
                    done.pop(old, None)
                self._done = done
                prog["busy"] = False

        threading.Thread(target=job, daemon=True).start()
        return {"ok": True, "job": jid}

    # ------------------------------------------------------------ pack
    def open_pack(self, path: str) -> dict:
        def work(tick, path):
            if Path(path).is_file():
                raise CV.ConvertError("That's a file. Import it to the Library first, then open the folder.",
                                      "Eso es un archivo. Impórtalo a la Biblioteca primero y luego abre la carpeta.")
            moved = None
            if not Path(path).exists():
                anchor = Path(path).anchor
                if anchor and not Path(anchor).exists():
                    raise CV.ConvertError(f"The drive of {path} isn't connected. Plug it in and try again.",
                                          f"La unidad de {path} no está conectada. Conéctala e inténtalo de nuevo.")
                found = self._relocate(Path(path))
                if found is None:
                    self._forget_recent(path)
                    raise CV.ConvertError(
                        f"That folder doesn't exist anymore: {path}. If you moved it, open it from where it is now "
                        "(or from the Library).",
                        f"Esa carpeta ya no existe: {path}. Si la moviste, ábrela desde donde quedó "
                        "(o desde la Biblioteca).")
                moved = {"from": path, "to": str(found)}
                path = str(found)
            self._drop_analysis()
            self._pack = Pack.open(Path(path))
            recovered = recover_interrupted(self._pack.root)
            if recovered:
                self._pack.reload()
            self._remember(path, replaces=moved["from"] if moved else None)
            if self._pack.project:
                from skynx import project as PJ
                PJ.write_info(self._pack.root, opened=time.strftime("%Y-%m-%d %H:%M:%S"))
            self._result = self._audit(True, tick)
            return {**self._audit_out(), "recovered": recovered, "moved": moved}
        return self._run("…", work, path)

    def reaudit(self, deep: bool = True) -> dict:
        def work(tick):
            self._pack.reload()
            self._result = self._audit(deep, tick)
            return self._audit_out()
        return self._run("…", work)

    def doctor_report(self) -> dict:
        """The last Doctor run as Markdown, with every detail."""
        from skynx.audit import report_markdown
        if not self._pack or not self._result:
            return {"ok": False}
        st = self._result.stats or {}
        es = self._lang == "es"
        lines = [f"{'Versión de la app' if es else 'App version'}: {__version__}",
                 f"{'Modo' if es else 'Mode'}: {self._pack.mode}"]
        if self._pack.mode == "AE" and self._pack.ccc:
            lines.append(f".ccc: {self._pack.list_bytes} / 4096 bytes")
        v = st.get("vanilla") or {}
        if v.get("state"):
            lines.append(f"{'Lista del juego' if es else 'Game list'}: {v['state']}")
        name = (self._pack_summary() or {}).get("name") or self._pack.root.name
        md = report_markdown(self._result, self._lang, name, lines)
        return {"ok": True, "md": md, "name": f"{name} - Doctor.md"}

    def save_text(self, name: str, text: str) -> dict:
        """Save text through a Save dialog (the Doctor report)."""
        if not self._window:
            return {"ok": False}
        import webview  # type: ignore
        kind = getattr(getattr(webview, "FileDialog", None), "SAVE", None) or webview.SAVE_DIALOG
        res = self._window.create_file_dialog(kind, save_filename=name,
                                              file_types=("Markdown (*.md)", "All files (*.*)"))
        path = res[0] if isinstance(res, (list, tuple)) and res else res
        if not path:
            return {"ok": False, "cancelled": True}
        Path(path).write_text(text, encoding="utf-8")
        return {"ok": True, "path": str(path)}

    def close_pack(self) -> dict:
        """Back to the start: nothing is open (a page reload doesn't reopen it)."""
        with self._run_lock:
            if self._progress.get("busy"):
                return {"ok": False, "busy": True}
            self._drop_analysis()
            self._clear_import_cache()
            self._pack = None
            self._result = None
        if self._settings.pop("last_open", None):     # closed on purpose: start on the welcome page
            self._save_settings()
        return {"ok": True}

    def current(self) -> dict | None:
        if not self._result:
            return None
        return self._audit_out()

    def _fix(self, fid: str) -> dict:
        """fid is a finding id, optionally followed by '#altN' for an alternative fix."""
        base, _, alt = fid.partition("#alt")
        for f in self._result.findings:
            if f.id == base:
                fx = f.alt[int(alt)] if alt else f.fix
                if fx:
                    return fx
        raise FixError("That finding no longer exists; check again",
                       "Ese hallazgo ya no existe; vuelve a revisar")

    def preview_fix(self, fid: str) -> dict:
        try:
            return {"ok": True, **preview(self._pack, self._fix(fid), self._lang)}
        except Exception as e:  # noqa: BLE001
            return {"ok": False, "error": self._err(e)}

    def apply_fix(self, fid: str) -> dict:
        """Runs as a job: some fixes rebuild big archives."""
        def work(tick, fid):
            fix = dict(self._fix(fid))
            fix["tools_dir"] = str(self._tools().folder or "")
            out = apply(self._pack, fix, progress=tick)   # title in English, shown translated (_hist_title)
            self._result = self._audit(True, tick)
            return {"ok": True, **out, **self._audit_out()}
        return self._run("…", work, fid)

    def _diet_args(self, bsa: str, preset: str, max_size):
        from skynx.texplan import NO_PRESET, PRESETS, check_max_size, with_cap
        if not self._pack or not bsa or str(bsa).lower() not in self._pack.bsas:
            raise FixError("That BSA isn't in the pack", "Ese BSA no está en el pack")
        if preset not in PRESETS and preset != NO_PRESET:
            raise FixError(f"Unknown size rule '{preset}'", f"Regla de tamaño desconocida '{preset}'")
        return self._pack.bsas[str(bsa).lower()], with_cap(preset, check_max_size(max_size))

    def diet_estimate(self, bsa: str, preset: str, max_size=None, bc1: bool = True) -> dict:
        """Texture memory of one BSA now and with these sizes (no tools needed)."""
        try:
            from skynx.diet import estimate_bsa
            path, full = self._diet_args(bsa, preset, max_size)
            return {"ok": True, **estimate_bsa(path, full, bool(bc1))}
        except Exception as e:  # noqa: BLE001
            return {"ok": False, "error": self._err(e)}

    def diet_bsa(self, bsa: str, preset: str, max_size=None, bc1: bool = True) -> dict:
        """Shrink one BSA's textures with the chosen sizes (undoable)."""
        def work(tick, bsa, preset, max_size, bc1):
            from skynx.audit import F
            path, full = self._diet_args(bsa, preset, max_size)
            rule = full.replace(":", " · ") + (" px" if ":" in full else "")
            fix = F("diet_bsa", "fix-diet-rule", "revisar", {"rule": rule}, bsa=path.name, preset=full,
                    bc1=bool(bc1), tools_dir=str(self._tools().folder or ""))
            out = apply(self._pack, fix, progress=tick)
            self._result = self._audit(True, tick)
            return {"ok": True, **out, **self._audit_out()}
        return self._run("…", work, bsa, preset, max_size, bc1)

    def apply_safe(self) -> dict:
        """Apply every fix marked safe, one at a time, re-checking in between.

        Some findings only come from the deep check (FaceGen tints, junk inside
        BSAs): those are taken from the list on screen and applied after the
        quick ones, each once."""
        def work(tick):
            done, skipped = [], []
            shown = self._result.sorted() if self._result else []
            deep_todo = [f for f in shown if f.fix and f.fix.get("risk") == "seguro"]
            tried: set[str] = set()

            def run_one(f, i, n):
                tick(f.text(self._lang)[0], i, n)
                tried.add(f.id)
                try:
                    out = apply(self._pack, {**f.fix, "tools_dir": str(self._tools().folder or "")},
                                progress=tick)
                    if out.get("changed"):
                        done.append(f.text(self._lang)[0])
                    else:
                        skipped.append(f.id)
                except Exception:  # noqa: BLE001
                    traceback.print_exc()
                    skipped.append(f.id)

            for _ in range(300):
                res = self._audit(False)
                todo = [f for f in res.sorted() if f.fix and f.fix.get("risk") == "seguro"
                        and f.id not in tried]
                if not todo:
                    break
                run_one(todo[0], len(done), len(done) + len(todo))
            # deep-only ones (still pending after the quick ones)
            quick_ids = {f.id for f in self._audit(False).findings}
            rest = [f for f in deep_todo if f.id not in tried and f.id not in quick_ids]
            for i, f in enumerate(rest):
                run_one(f, len(done), len(done) + len(rest) - i)
            self._result = self._audit(True, tick)
            return {"done": done, "skipped": skipped, **self._audit_out()}
        return self._run("…", work)

    # ------------------------------------------------------------ build
    def new_project(self, path: str, edition: str, base: str, preset: str, ussep: str = "") -> dict:
        def work(tick, path, edition, base, preset, ussep):
            self._drop_analysis()
            create_project(Path(path), edition, Path(base), preset, ussep=ussep or None,
                           ussep_dir=Path(self._folder("ussep_dir")))
            self._pack = Pack.open(Path(path))
            self._remember(path)
            self._result = self._audit(True, tick)
            return self._audit_out()
        return self._run("…", work, path, edition, base, preset, ussep)

    def mods(self) -> list[dict]:
        if not self._pack:
            return []
        from skynx.console import clean_mod_name, load_descriptions
        desc = load_descriptions(self._pack)
        return [{**r, "title": clean_mod_name(r["name"]), "desc": desc.get(r["id"], "")}
                for r in mods_view(self._pack)]

    def mod_describe(self, row_id: str, text: str) -> dict:
        """The person's own description of a mod (shown here and on the console)."""
        from skynx.console import set_description
        try:
            with Transaction(self._pack.root, f"Describe {row_id}") as tx:
                set_description(self._pack, row_id, text, tx)
            return {"ok": True}
        except Exception as e:  # noqa: BLE001
            return {"ok": False, "error": self._err(e)}

    def _console_extra(self) -> dict:
        """Row id -> {title, desc} from what is known on Nexus (names and summaries
        fetched before; nothing is fetched here)."""
        out = {}
        try:
            r = self.identify_mods()
            for x in r.get("rows", []) if r.get("ok") else []:
                det = (x.get("ident") or {}).get("details") or {}
                if det.get("name") or det.get("summary"):
                    out[x["id"]] = {"title": det.get("name"), "desc": det.get("summary")}
        except Exception:  # noqa: BLE001
            pass
        return out

    def _loose(self, source: Path):
        """A plugin/BSA picked on its own goes in through a temporary folder
        holding it and its companion files. Returns (folder, temp or None)."""
        from skynx.intake import bundle_to_folder, loose_bundle
        if not loose_bundle(source):
            return source, None
        import tempfile
        tmp = Path(tempfile.mkdtemp(prefix="skynx-loose-"))
        return bundle_to_folder(source, tmp / source.stem), tmp

    def add_mod(self, source: str) -> dict:
        def work(tick, source):
            tick(Path(source).name)
            src, tmp = self._loose(Path(source))
            try:
                rep = add_mod(self._pack, src, nexus=self._nexus_for(source))
            finally:
                if tmp:
                    shutil.rmtree(tmp, ignore_errors=True)
            self._result = self._audit(False)
            return {"report": rep.to_dict(self._lang), **self._audit_out()}
        return self._run("…", work, source)

    def remove_mod(self, mod_id: str, with_users: bool = False) -> dict:
        """Remove a mod. When other plugins use it as a master, the answer has
        `users` ([{plugin, mod, whole}]) so the page can offer to remove them
        too (with_users=True)."""
        try:
            remove_mod(self._pack, mod_id, with_users=bool(with_users))
            self._result = self._audit(False)
            return {"ok": True, **self._audit_out()}
        except Exception as e:  # noqa: BLE001
            out = {"ok": False, "error": self._err(e)}
            if getattr(e, "users", None):
                out["users"] = e.users
            return out

    # ------------------------------------------------------------ convert
    def _drop_batch(self):
        for it in list(getattr(self, "_batch", {}).values()):
            for k in ("an", "fomod"):
                if it.get(k):
                    it[k].cleanup()
        self._batch = {}

    def _drop_analysis(self, batch: bool = True):
        if batch:
            self._drop_batch()
        if self._analysis:
            self._analysis.cleanup()
            self._analysis = None
        if getattr(self, "_fomod", None):
            self._fomod.cleanup()
            self._fomod = None
        # plans made for the previous pack must never be applied to another one
        if getattr(self, "_transfer", None):
            self._transfer.cleanup()
            self._transfer = None
        self._loot = None

    def convert_analyze(self, source: str) -> dict:
        def work(tick, source):
            self._drop_analysis(batch=False)
            res = CV.start(self._pack, Path(source), progress=tick)
            if isinstance(res, CV.FomodSession):
                self._fomod = res
                return {"fomod": self._fomod_view({}, 0)}
            self._analysis = res
            return CV.analysis_view(self._pack, self._analysis, self._tools(), self._lang)
        return self._run("…", work, source)

    def _fomod_view(self, choices: dict, step: int, sess=None) -> dict:
        from skynx import fomod as FM
        s = sess or self._fomod
        ev = FM.evaluate(s.fm, s.ctx, choices or {})
        return {"name": ev["name"], "source": s.source, "steps": ev["steps"],
                "module_ok": ev["module_ok"], "unknown": ev["unknown"],
                "image": FM._image(s.fm, s.fm.image), "images": FM.step_images(s.fm, step),
                "step": step}

    def fomod_eval(self, choices: dict, step: int = 0, item=None) -> dict:
        sess = (self._batch.get(str(item)) or {}).get("fomod") if item is not None else self._fomod
        if not sess:
            return {"ok": False, "error": "Read the mod again" if self._lang == "en" else "Vuelve a leer el mod"}
        try:
            return {"ok": True, **self._fomod_view(choices, int(step), sess)}
        except Exception as e:  # noqa: BLE001
            return {"ok": False, "error": self._err(e)}

    def fomod_finish(self, choices: dict) -> dict:
        def work(tick, choices):
            if not self._fomod:
                raise CV.ConvertError("Read the mod again", "Vuelve a leer el mod")
            sess = self._fomod
            try:
                self._analysis = CV.fomod_finish(self._pack, sess, choices or {}, progress=tick)
            finally:
                self._fomod = None   # the work folder now belongs to the analysis (or is gone)
            if not self._analysis.work.exists():
                self._analysis = None
            return CV.analysis_view(self._pack, self._analysis, self._tools(), self._lang)
        return self._run("…", work, choices)

    # ------------------------------------------------------------ convert several
    def _batch_item_view(self, it: dict) -> dict:
        from skynx import batch as B
        out = {"id": it["id"], "source": it["source"], "name": B.source_name(it["source"]),
               "error": it.get("error"), "kind": "error" if it.get("error") else "fomod" if it.get("fomod") else "ready"}
        if it.get("fomod"):
            out["fomod"] = {"name": getattr(it["fomod"].fm, "name", None) or out["name"],
                            "steps": sum(1 for _ in getattr(it["fomod"].fm, "steps", []) or [])}
        if it.get("an"):
            if "view" not in it:
                v = CV.analysis_view(self._pack, it["an"], self._tools(), self._lang)
                v.pop("budget", None)
                v.pop("tools", None)
                it["view"] = v
            out["view"] = it["view"]
        return out

    def batch_view(self) -> dict:
        if not self._pack:
            return {"items": []}
        b = None
        try:
            lst = self._pack.ccc if self._pack.mode == "AE" else self._pack.plugin_list
            nl = 1 if (lst and lst.newline == "LF") or self._pack.mode == "SE" else 2
            from skynx import knowledge as K
            b = {"ccc_now": self._pack.list_bytes, "nl": nl,
                 "ccc_limit": K.CCC_BYTE_LIMIT if self._pack.mode == "AE" else None,
                 "ccc_warn": K.CCC_BYTE_WARN if self._pack.mode == "AE" else None,
                 "tex_pack": CV.pack_texture_bytes(self._pack)}
        except Exception:  # noqa: BLE001
            traceback.print_exc()
        return {"items": [self._batch_item_view(it) for it in self._batch.values()], "budget": b,
                "tools": self._tools().status()}

    def batch_add(self, sources: list) -> dict:
        """Read several mods (archives or folders); each keeps its own options."""
        def work(tick, sources):
            have = {it["source"].lower() for it in self._batch.values()}
            todo = [str(s) for s in sources or [] if str(s).strip() and str(s).lower() not in have]
            for i, src in enumerate(todo):
                tick(Path(src).name, i, len(todo))
                self._batch_seq = getattr(self, "_batch_seq", 0) + 1
                it = {"id": str(self._batch_seq), "source": src}
                try:
                    res = CV.start(self._pack, Path(src))
                    it["fomod" if isinstance(res, CV.FomodSession) else "an"] = res
                except Exception as e:  # noqa: BLE001
                    it["error"] = self._err(e)
                self._batch[it["id"]] = it
            return self.batch_view()
        if not self._pack:
            return {"ok": False, "error": "?"}
        return self._run("…", work, sources)

    def batch_remove(self, item) -> dict:
        it = self._batch.pop(str(item), None)
        for k in ("an", "fomod"):
            if it and it.get(k):
                it[k].cleanup()
        return {"ok": True}

    def batch_clear(self) -> dict:
        self._drop_batch()
        return {"ok": True}

    def batch_fomod_start(self, item) -> dict:
        it = self._batch.get(str(item))
        if not it or not it.get("fomod"):
            return {"ok": False, "error": "?"}
        try:
            # the other mods of the batch count as installed (their patches become usable)
            ctx = it["fomod"].ctx
            for other in self._batch.values():
                if other is not it and other.get("an"):
                    names = {pl["name"].lower() for pl in other["an"].plugins}
                    ctx.active |= names
                    ctx.present |= names
            return {"ok": True, **self._fomod_view({}, 0, it["fomod"])}
        except Exception as e:  # noqa: BLE001
            return {"ok": False, "error": self._err(e)}

    def batch_fomod_finish(self, item, choices: dict) -> dict:
        def work(tick, item, choices):
            it = self._batch.get(str(item))
            if not it or not it.get("fomod"):
                raise CV.ConvertError("Read the mod again", "Vuelve a leer el mod")
            sess = it["fomod"]
            an = CV.fomod_finish(self._pack, sess, choices or {}, progress=tick)
            it.pop("fomod", None)
            it.pop("view", None)
            it["an"] = an
            return self._batch_item_view(it)
        return self._run("…", work, item, choices)

    def batch_estimate(self, item, preset: str, sdk: bool, max_size) -> dict:
        it = self._batch.get(str(item))
        if not it or not it.get("an"):
            return {"ok": False}
        try:
            from skynx.texplan import check_max_size
            return {"ok": True, **it["an"].estimate(preset if preset in (*CV.PRESETS, CV.NO_PRESET) else CV.DEFAULT_PRESET, bool(sdk),
                                                    check_max_size(max_size))}
        except Exception as e:  # noqa: BLE001
            return {"ok": False, "error": self._err(e)}

    def batch_run(self, plan: list) -> dict:
        """plan: [{id, options}] for the mods to convert now (with their options)."""
        from skynx import batch as B
        from skynx import workshop as WS
        rows = []
        for p in plan or []:
            it = self._batch.get(str(p.get("id")))
            if it and it.get("an"):
                rows.append((it["id"], it["an"], dict(p.get("options") or {})))
        if not rows:
            return {"ok": False, "error": "Nothing ready to convert." if self._lang == "en" else "No hay nada listo para convertir."}
        problems = B.check(self._pack, rows)
        if problems:
            return {"ok": False, "problems": [{"id": x["id"], "text": x.get(self._lang) or x["en"]} for x in problems],
                    "error": (problems[0].get(self._lang) or problems[0]["en"])}

        def work(tick, rows):
            opts_of = {iid: o for iid, _a, o in rows}
            an_of = {iid: a for iid, a, _o in rows}
            on_bench = WS.is_bench(self._pack.root)
            produced: dict[str, str] = {}
            failed_names: dict[str, str] = {}        # plugin (lower) of a mod that failed -> that mod
            results = []
            ids = B.order([(iid, a) for iid, a, _o in rows])
            for n, iid in enumerate(ids):
                an, opts = an_of[iid], dict(opts_of[iid])
                name = B.source_name(an.source)

                def sub(text, i=0, k=0, n=n, name=name):
                    tick(f"{n + 1}/{len(ids)} · {name} · {text}" if text and text != "…" else f"{n + 1}/{len(ids)} · {name}",
                         n, len(ids))
                sub("")
                try:
                    lost = sorted({failed_names[m.lower()] for pl in an.plugins for m in pl.get("missing") or []
                                   if m.lower() in failed_names})
                    if lost:
                        raise CV.ConvertError(
                            f"It needs {', '.join(lost)}, which couldn't be converted. Fix that one first.",
                            f"Necesita {', '.join(lost)}, que no se pudo convertir. Arregla ese primero.")
                    pointed = B.point_masters(an, produced)
                    # on a bench too: each mod of the batch goes to the Library on its own
                    if (on_bench or self._settings.get("keep_converted", True)) and opts.get("keep", True):
                        opts["keep_to"] = str(self._library_root() / "Converted")
                    res = CV.convert(self._pack, an, opts, self._tools(), progress=sub,
                                     nexus=self._nexus_for(getattr(an, "source", None)))
                    for pl, final in zip(an.plugins, res["plugins"]):
                        produced[pl["name"].lower()] = final
                    lang = self._lang
                    rep = res["report"].to_dict(lang)
                    results.append({"id": iid, "name": name, "ok": True, "stats": res["stats"], "bsas": res["bsas"],
                                    "plugins": res["plugins"], "renamed": res["renamed"], "kept": res["kept"],
                                    "pointed": pointed,
                                    "notes": [x.get(lang, x["en"]) for x in res["notes"]] + list(rep.get("notes") or [])})
                    it = self._batch.pop(iid, None)
                    if it and it.get("an"):
                        it["an"].cleanup()
                except Exception as e:  # noqa: BLE001
                    traceback.print_exc()
                    results.append({"id": iid, "name": name, "ok": False, "error": self._err(e)})
                    for pl in an.plugins:
                        failed_names[pl["name"].lower()] = name
                    # its work folder may be half renamed: it has to be read again
                    it = self._batch.get(iid)
                    if it is not None:
                        if it.get("an"):
                            it["an"].cleanup()
                        self._batch[iid] = {"id": iid, "source": it["source"], "error": self._err(e)}
            self._result = self._audit(False)
            return {"results": results, **self._audit_out()}
        return self._run("…", work, rows)

    def convert_view(self) -> dict | None:
        if not self._analysis:
            return None
        return CV.analysis_view(self._pack, self._analysis, self._tools(), self._lang)

    def convert_cancel(self) -> dict:
        self._drop_analysis(batch=False)
        return {"ok": True}

    def convert_run(self, options: dict) -> dict:
        def work(tick, options):
            if not self._analysis:
                raise CV.ConvertError("Analyze the mod again", "Vuelve a analizar el mod")
            an = self._analysis
            try:
                opts = dict(options or {})
                from skynx import workshop as WS
                on_bench = WS.is_bench(self._pack.root)
                if self._settings.get("keep_converted", True) and opts.get("keep", True) and not on_bench:
                    opts["keep_to"] = str(self._library_root() / "Converted")
                res = CV.convert(self._pack, an, opts, self._tools(), progress=tick,
                                 nexus=self._nexus_for(getattr(an, "source", None)))
            finally:
                self._drop_analysis(batch=False)
            lang = self._lang
            res["notes"] = [n.get(lang, n["en"]) for n in res["notes"]]
            res["report"] = res["report"].to_dict(lang)
            self._result = self._audit(False)
            return {"result": res, **self._audit_out()}
        return self._run("…", work, options)

    # ------------------------------------------------------------ Nexus
    def _nexus_client(self):
        from skynx import nexus as NX
        key = self._settings.get("nexus_key") or ""
        if not key:
            raise NX.NexusError("Paste your Nexus API key in Settings first.",
                                "Pega primero tu API key de Nexus en Ajustes.", kind="no_key")
        from skynx import __version__
        return NX.Client(key, app_version=__version__)

    @staticmethod
    def _sidecar(path) -> Path:
        p = Path(path)
        return p.with_name(p.name + ".nexus.json")

    def _nexus_for(self, path) -> dict | None:
        """What we know from Nexus about a downloaded or identified file
        (kept next to it as <file>.nexus.json)."""
        if not path:
            return None
        f = self._sidecar(path)
        try:
            return json.loads(f.read_text(encoding="utf-8")) if f.exists() else None
        except (OSError, ValueError):
            return None

    def _write_sidecar(self, path, info: dict) -> None:
        try:
            self._sidecar(path).write_text(json.dumps(info, indent=1, ensure_ascii=False), encoding="utf-8")
        except OSError:
            pass

    def nexus_status(self) -> dict:
        from skynx import nxm
        out = {"has_key": bool(self._settings.get("nexus_key")), "user": self._settings.get("nexus_user"),
               "handler": None, "ours": False, "previous": None, "windows": sys.platform == "win32"}
        if sys.platform == "win32":
            try:
                out.update({k: v for k, v in nxm.status(self._nxm_command()).items()
                            if k in ("handler", "ours", "previous")})
            except Exception:  # noqa: BLE001
                traceback.print_exc()
        return out

    def nexus_set_key(self, key: str) -> dict:
        def work(tick, key):
            from skynx import nexus as NX
            key = (key or "").strip()
            if not key:
                self._settings.pop("nexus_key", None)
                self._settings.pop("nexus_user", None)
                self._save_settings()
                return self.nexus_status()
            from skynx import __version__
            user = NX.Client(key, app_version=__version__).validate()
            self._settings["nexus_key"] = key
            self._settings["nexus_user"] = {"name": user.get("name"), "premium": bool(user.get("is_premium"))}
            self._save_settings()
            return self.nexus_status()
        return self._run("…", work, key)

    def _nxm_command(self) -> str:
        from skynx import nxm
        frozen = bool(getattr(sys, "frozen", False))
        return nxm.default_command(frozen, sys.executable, str(Path(__file__).resolve().parent / "main.py"))

    def nexus_handler(self, on: bool) -> dict:
        from skynx import nxm
        try:
            if on:
                nxm.register(self._nxm_command())
            else:
                nxm.unregister()
            return {"ok": True, **self.nexus_status()}
        except Exception as e:  # noqa: BLE001
            return {"ok": False, "error": self._err(e)}

    def nexus_download(self, url: str) -> dict:
        """An nxm:// link (the site's Mod Manager Download button): ask Nexus
        for the file, download it into the Library's Downloads folder and keep
        what Nexus says about it next to the file."""
        def work(tick, url):
            from skynx import nexus as NX
            link = NX.parse_nxm(url)
            cl = self._nexus_client()
            tick("Nexus")
            mod = cl.mod(link.mod_id)
            info = cl.file(link.mod_id, link.file_id)
            links = cl.download_links(link)
            if not links:
                raise NX.NexusError("Nexus gave no download link.", "Nexus no dio enlace de descarga.")
            dest = self._library_root() / "Downloads"
            path = NX.download(links[0]["url"], dest, progress=tick, filename=info.get("file_name"),
                               expected_md5=info.get("md5") or None, label=info.get("name") or mod.get("name"),
                               identity=f"{link.mod_id}:{link.file_id}")
            try:
                (dest / (path.name + ".part.id")).unlink(missing_ok=True)
            except OSError:
                pass
            meta = {"mod_id": link.mod_id, "file_id": link.file_id, "game": link.game,
                    "name": mod.get("name"), "file_name": info.get("file_name") or path.name,
                    "version": info.get("version") or info.get("mod_version") or mod.get("version"),
                    "category": info.get("category_name"), "md5": NX.file_md5(path),
                    "page": NX.mod_page(link.mod_id)}
            self._write_sidecar(path, meta)
            return {"path": str(path), "nexus": meta}
        return self._run("…", work, url)

    def nexus_identify(self, path: str) -> dict:
        """Find a downloaded archive on Nexus by its MD5."""
        def work(tick, path):
            from skynx import nexus as NX
            p = Path(path)
            if not p.is_file():
                raise NX.NexusError("Only downloaded files (.zip, .7z) can be identified.",
                                    "Solo se pueden identificar archivos descargados (.zip, .7z).")
            tick(p.name)
            md5 = NX.file_md5(p)
            matches = self._nexus_client().md5_search(md5)
            sky = [m for m in matches if (m.get("game") or "skyrimspecialedition") == "skyrimspecialedition"]
            if len(sky) == 1:
                m = sky[0]
                meta = {"mod_id": m["mod_id"], "file_id": m["file_id"], "game": "skyrimspecialedition",
                        "name": m.get("mod_name"), "file_name": m.get("file_name"),
                        "version": m.get("version") or m.get("mod_version"), "category": m.get("category"),
                        "md5": md5, "page": NX.mod_page(m["mod_id"])}
                self._write_sidecar(p, meta)
                return {"found": True, "nexus": meta, "matches": sky}
            return {"found": False, "matches": sky}
        return self._run("…", work, path)

    def nexus_updates(self) -> dict:
        """Mods of the current pack that came from Nexus: is there a newer file?"""
        def work(tick):
            from skynx import nexus as NX
            from skynx import recipe as RC
            mods, seen = [], set()
            for rid, rec in CV.load_mods(self._pack).items():
                if not isinstance(rec, dict):
                    continue
                nx = RC.nexus_of(RC.source_of(rec))
                if nx and nx.get("mod_id") and (nx["mod_id"], nx.get("file_id")) not in seen:
                    seen.add((nx["mod_id"], nx.get("file_id")))
                    mods.append({"mod_id": int(nx["mod_id"]), "file_id": nx.get("file_id"),
                                 "version": nx.get("version"), "name": nx.get("name") or rid})
            if not mods:
                return {"rows": [], "none": True}
            rows = NX.check_updates(self._nexus_client(), mods)
            for r in rows:
                r["page"] = NX.mod_page(r["mod_id"])
                if r.get("error"):
                    r["error"] = r["error"].get(self._lang) or r["error"].get("en")
            return {"rows": rows, "none": False}
        return self._run("…", work)

    def nexus_receive(self, url: str) -> None:
        """Called by the single-instance server when another launch hands over
        an nxm link; the page starts the download (or picks it up when it's
        ready)."""
        from skynx import nexus as NX
        try:
            NX.parse_nxm(url)
        except Exception:  # noqa: BLE001
            return
        if self._window and getattr(self, "_page_ready", False):
            try:
                self._window.evaluate_js(f"window.onNxm && window.onNxm({json.dumps(url)})")
                return
            except Exception:  # noqa: BLE001
                pass
        self._pending_nxm = getattr(self, "_pending_nxm", []) + [url]

    def pending_nxm(self) -> list:
        """The page asks for links that arrived before it was ready."""
        self._page_ready = True
        out = getattr(self, "_pending_nxm", [])
        self._pending_nxm = []
        return out

    def open_url(self, url: str) -> dict:
        import webbrowser
        if str(url).startswith("https://www.nexusmods.com/"):
            webbrowser.open(url)
            return {"ok": True}
        return {"ok": False}

    # ------------------------------------------------------------ recipe
    def _userlist_path(self) -> Path:
        return self._loot_paths()[2]

    def recipe_view(self) -> dict:
        def work(tick):
            from skynx import recipe as RC
            new = RC.build(self._pack, userlist_path=self._userlist_path())
            old = RC.current(self._pack)
            d = RC.diff(old, new) if old else None
            return {"counts": new["counts"], "saved": bool(old),
                    "saved_at": old.get("created") if old else None,
                    "diff": RC.diff_text(d, self._lang) if d else [],
                    "history": RC.history(self._pack)[:10],
                    "verify": [{"kind": v["kind"], "file": v.get("file"), "text": v.get(self._lang) or v.get("en")}
                               for v in (RC.verify(self._pack, old) if old else [])][:200],
                    "nexus": sum(1 for m in new["mods"] if RC.nexus_of(m.get("source") or {}))}
        return self._run("…", work)

    def recipe_save(self) -> dict:
        def work(tick):
            from skynx import recipe as RC
            r = RC.build(self._pack, userlist_path=self._userlist_path())
            path = RC.save(self._pack, r)
            return {"path": str(path), "counts": r["counts"]}
        return self._run("…", work)

    def recipe_export(self) -> dict:
        """The shareable recipe (.md, no local paths) next to the pack folder."""
        def work(tick):
            from skynx import recipe as RC
            r = RC.build(self._pack, userlist_path=self._userlist_path())
            RC.save(self._pack, r)
            links = {}
            try:                                    # what recognising the mods found (LOOT, confirmed by you)
                from skynx import identify as ID
                got = self.identify_mods()
                rows = {x["id"]: x for x in self._ident_rows()}
                for x in got.get("rows") or []:
                    if x["ident"].get("url"):
                        b = ID.brief(x["ident"])
                        links[x["id"]] = b
                        for p in (rows.get(x["id"]) or {}).get("plugins") or []:
                            links.setdefault(p.lower(), b)
            except Exception:  # noqa: BLE001
                traceback.print_exc()
            md = RC.export_markdown(r, lang=self._lang, links=links)
            name = ("Recipe - " if self._lang == "en" else "Receta - ") + self._pack.root.name + ".md"
            out = self._pack.root / name
            out.write_text(md, encoding="utf-8")
            return {"path": str(out)}
        return self._run("…", work)

    def _folder(self, which: str) -> str:
        """A folder setting, or the first default that exists."""
        v = self._settings.get(which)
        if v:
            return v
        cands = DEFAULT_FOLDERS.get(which, [])
        return next((c for c in cands if Path(c).is_dir()), cands[0] if cands else "")

    # ------------------------------------------------------------ convert: size cap estimate
    def convert_estimate(self, preset: str, sdk: bool, max_size) -> dict:
        if not self._analysis:
            return {"ok": False}
        try:
            ms = int(max_size) if max_size else None
            return {"ok": True, **self._analysis.estimate(preset, bool(sdk), ms)}
        except Exception as e:  # noqa: BLE001
            return {"ok": False, "error": self._err(e)}

    # ------------------------------------------------------------ compare with the original
    def pick_file(self) -> str | None:
        r = self.pick_files()
        return r[0] if r else None

    def compare_mods(self, converted: str, original: str) -> dict:
        def work(tick, converted, original):
            from skynx.compare import compare
            r = compare(Path(converted), Path(original), progress=tick)
            pick = (lambda d: d.get(self._lang) or d.get("en")) if True else None
            r["verdict_text"] = pick(r["verdict"])
            r["notes"] = [{"level": n.get("level"), "text": pick(n)} for n in r.get("notes", [])]
            return r
        return self._run("…", work, converted, original)

    # ------------------------------------------------------------ catalog (build a pack from the Library)
    def catalog_build(self, refresh: bool = False) -> dict:
        def work(tick, refresh):
            from skynx import catalog as CT
            ml = None
            _c, ml_path, _u = self._loot_paths()
            if ml_path.exists():
                try:
                    from skynx import loot
                    ml = loot.load_masterlist(ml_path)
                except Exception:  # noqa: BLE001
                    ml = None
            if refresh:
                import shutil as _sh
                _sh.rmtree(self._library_root() / ".catalog", ignore_errors=True)
            self._catalog = CT.build_catalog(self._library_root(), progress=tick, masterlist=ml)
            return self._catalog
        return self._run("…", work, refresh)

    def _base_for(self, base: dict) -> dict:
        b = dict(base or {})
        if b.get("into") == "open":
            if not self._pack:
                raise CV.ConvertError("Open the pack first.", "Abre primero el pack.")
            b["into"] = str(self._pack.root)
            st = getattr(self._result, "stats", None) or {}
            b["tex_bytes"] = st.get("tex_bytes") or 0
        b.setdefault("inis_dir", self._folder("inis_dir"))
        b.setdefault("ussep_dir", self._folder("ussep_dir"))
        b.setdefault("lang", "en")
        return b

    def catalog_plan(self, picks: list, base: dict) -> dict:
        from skynx import catalog as CT
        if not getattr(self, "_catalog", None):
            return {"ok": False, "error": "Read the catalog first" if self._lang == "en" else "Lee primero el catálogo"}
        try:
            return {"ok": True, "plan": CT.plan_build(self._catalog, list(picks or []), self._base_for(base))}
        except Exception as e:  # noqa: BLE001
            traceback.print_exc()
            return {"ok": False, "error": self._err(e)}

    def catalog_execute(self, picks: list, base: dict, dest: str, force: bool = False) -> dict:
        def work(tick, picks, base, dest, force):
            from skynx import catalog as CT
            self._drop_analysis()
            from skynx import draft as DR
            b = self._base_for(base)
            if not b.get("into") and not dest:
                raise CV.ConvertError("Give the new pack a name.", "Ponle nombre al pack nuevo.")
            if b.get("into"):
                out = CT.execute_build(self._catalog, list(picks or []), b, None, progress=tick, force=bool(force))
                dest = out["dest"]
                self._pack = Pack.open(self._pack.root if self._pack and self._pack.project else Path(dest))
            elif os.path.isabs(dest):          # a folder of its own (kept for scripts and tests)
                out = CT.execute_build(self._catalog, list(picks or []), b, Path(dest), progress=tick,
                                       force=bool(force))
                dest = out["dest"]
                if not DR.is_draft(Path(dest)):
                    DR.mark(Path(dest), Path(dest).name, {"kind": "catalog", "picks": len(picks or [])})
                self._pack = Pack.open(Path(dest))
            else:                              # a name: a new project
                from skynx import project as PJ
                root = PJ._new_root(self._library_root(), dest)
                work_dir = PJ.work_root(root)
                try:
                    out = CT.execute_build(self._catalog, list(picks or []), b, work_dir, progress=tick,
                                           force=bool(force))
                    PJ._lift_records(work_dir / ".skynx", root / ".skynx")
                    shutil.rmtree(work_dir / ".skynx", ignore_errors=True)
                    self._pack = PJ._finish(root, PJ.clean_name(dest),
                                            {"kind": "catalog", "picks": len(picks or [])}, register=True)
                except BaseException:
                    shutil.rmtree(root, ignore_errors=True)
                    raise
                dest = str(root)
                out["dest"] = dest
            self._remember(str(self._pack.root))
            self._result = self._audit(True, tick)
            return {"build": out, **self._audit_out()}
        return self._run("…", work, picks, base, dest, force)

    # ------------------------------------------------------------ projects
    def projects(self) -> dict:
        """The projects in the Library, and modpacks from before projects that
        can become one."""
        from skynx import project as PJ
        lib = self._library_root()
        try:
            legacy = PJ.legacy(lib)
        except Exception:  # noqa: BLE001
            legacy = []
        return {"projects": PJ.list_projects(lib), "legacy": legacy,
                "root": str(PJ.projects_root(lib))}

    def project_new(self, kind: str, name: str, opts: dict | None = None) -> dict:
        """kind: "empty" (edition, base, preset, ussep), "pack" (src: a folder,
        a zip/7z/rar or another project) or "sd" (sd: the SD drive)."""
        def work(tick, kind, name, opts):
            from skynx import project as PJ
            o = dict(opts or {})
            lib = self._library_root()
            self._drop_analysis()
            link = self._settings.get("project_links") is True
            prog = lambda f, i=0, n=0: tick(f, i, n)  # noqa: E731
            if kind == "empty":
                pk = PJ.new_empty(lib, name, o.get("edition") or "AE",
                                  Path(o.get("base") or self._folder("inis_dir")), o.get("preset") or "ussep",
                                  ussep=o.get("ussep") or None, ussep_dir=Path(self._folder("ussep_dir")))
            elif kind == "pack":
                if not o.get("src"):
                    raise CV.ConvertError("Pick the modpack.", "Escoge el modpack.")
                pk = PJ.from_pack(lib, name, Path(o["src"]), progress=prog, link=link)
            elif kind == "sd":
                if not o.get("sd"):
                    raise CV.ConvertError("Type the SD drive.", "Escribe la unidad de la SD.")
                pk = PJ.from_sd(lib, name, Path(o["sd"]), progress=prog)
            else:
                raise CV.ConvertError(f"Unknown kind {kind}", f"Tipo desconocido {kind}")
            self._pack = pk
            self._remember(str(pk.root))
            PJ.write_info(pk.root, opened=time.strftime("%Y-%m-%d %H:%M:%S"))
            self._result = self._audit(True, tick)
            return self._audit_out()
        return self._run("…", work, kind, name, opts)

    # findings the usual routine fixes before packing (they all have a button)
    ROUTINE = ("bsa-loses-to-ini", "seq-missing", "ini-long", "lang-ini-hides", "plugin-dummy")

    def pack_reminders(self) -> dict:
        """What the usual routine hasn't done yet, to show before packing: the
        LOOT order (plugins it would still move), serious Doctor problems,
        routine fixes left, behaviors to generate. Reading only."""
        def work(tick):
            out = []
            from skynx import loot
            _c, ml_path, ul_path = self._loot_paths()
            if not ml_path.exists():
                out.append({"kind": "loot_never"})
            else:
                tick("LOOT")
                try:
                    ml = loot.load_masterlist(ml_path)
                    sg = loot.suggest(self._pack, ml, aliases=self._aliases(),
                                      userlist=loot.load_userlist(ul_path))
                    if sg.moves:
                        out.append({"kind": "loot", "n": len(sg.moves),
                                    "names": [m.name for m in sg.moves[:6]]})
                except Exception:  # noqa: BLE001
                    out.append({"kind": "loot_never"})
            tick("Doctor")
            res = self._audit(False)
            self._result = res
            crit = [f for f in res.findings if f.severity == "critico"]
            if crit:
                out.append({"kind": "critico", "n": len(crit)})
            routine = [f for f in res.findings if f.code in self.ROUTINE and f.fix
                       and f.severity in ("critico", "aviso")]
            if routine:
                out.append({"kind": "routine", "n": len(routine),
                            "names": [f.to_dict(self._lang)["title"] for f in routine[:6]]})
            try:
                from skynx import behaviors as BH
                if BH.status(self._pack, self._tools())["state"] in ("never", "stale"):
                    out.append({"kind": "behaviors"})
            except Exception:  # noqa: BLE001
                pass
            return {"items": out, **self._audit_out()}
        return self._run("…", work)

    def project_build(self) -> dict:
        """Pack: the two folders for the console in the project's Switch folder."""
        def work(tick):
            from skynx import project as PJ
            if not (self._pack and self._pack.project):
                raise CV.ConvertError("Open a project first.", "Abre primero un proyecto.")
            out = PJ.build(self._pack, progress=lambda f, i=0, n=0: tick(f, i, n))
            from skynx import behaviors as BH
            try:
                beh = BH.status(self._pack, self._tools())["state"]
            except Exception:  # noqa: BLE001
                beh = None
            return {"build": out, "pack": self._pack_summary(), "behaviors": beh}
        return self._run("…", work)

    # ------------------------------------------------------------ behaviors (FNIS / Nemesis)
    def behaviors_status(self) -> dict:
        from skynx import behaviors as BH
        if not self._pack:
            return {"ok": False}
        try:
            st = BH.status(self._pack, self._tools())
            proc = getattr(self, "_nemesis_proc", None)
            st["running"] = bool(proc and proc.poll() is None)
            st["log"] = BH.nemesis_log(self._pack) if BH.work_dir(self._pack).is_dir() else None
            return {"ok": True, **st}
        except Exception as e:  # noqa: BLE001
            return {"ok": False, "error": self._err(e)}

    def behaviors_start(self) -> dict:
        """Make the work folder and open Nemesis on it."""
        def work(tick):
            from skynx import behaviors as BH
            if not self._pack:
                raise CV.ConvertError("Open a project first.", "Abre primero un proyecto.")
            tick("Nemesis")
            info = BH.prepare(self._pack, self._tools())
            self._nemesis_proc = BH.launch(self._pack)
            return info
        return self._run("…", work)

    def behaviors_finish(self) -> dict:
        """After Nemesis: Switch files, into the pack as one mod."""
        def work(tick):
            from skynx import behaviors as BH
            if not self._pack:
                raise CV.ConvertError("Open a project first.", "Abre primero un proyecto.")
            proc = getattr(self, "_nemesis_proc", None)
            if proc and proc.poll() is None:
                raise BH.BehaviorError("Nemesis is still open. Close it when it says it finished, then try again.",
                                       "Nemesis sigue abierto. Ciérralo cuando diga que terminó y vuelve a intentar.")
            out = BH.collect(self._pack, self._tools(), progress=lambda f, i=0, n=0: tick(f, i, n))
            self._pack = Pack.open(self._pack.root)
            self._result = self._audit(True, tick)
            return {"ok": True, **out, **self._audit_out(), "pack": self._pack_summary()}
        return self._run("…", work)

    def project_delete(self, path: str) -> dict:
        from skynx import project as PJ
        try:
            with self._exclusive("…"):
                if self._pack and Path(self._pack.root).resolve() == Path(path).resolve():
                    self._drop_analysis()
                    self._pack, self._result = None, None
                dest = PJ.delete(self._library_root(), Path(path))
                self._forget_recent(path)
                return {"ok": True, "trash": str(dest)}
        except _Busy:
            return self._busy_out()
        except Exception as e:  # noqa: BLE001
            return {"ok": False, "error": self._err(e)}

    def _pack_source(self, src: str, tick=None) -> Path:
        """A modpack to bring mods from: a folder or project as it is, an
        archive extracted once into the Library's import cache (left there
        while the app is open, so choosing mods again doesn't extract again)."""
        if not str(src or "").strip():
            raise CV.ConvertError("Pick the modpack.", "Escoge el modpack.")
        p = Path(src)
        if not p.is_file():
            return p
        import hashlib
        from skynx import project as PJ
        st = p.stat()
        key = hashlib.sha1(f"{p.resolve()}|{st.st_size}|{st.st_mtime_ns}".encode()).hexdigest()[:16]
        cache = self._library_root() / ".import-cache" / key
        if (cache / "done").is_file():
            return cache / "pack"
        shutil.rmtree(cache, ignore_errors=True)
        cache.mkdir(parents=True)
        PJ._extract_pack(p, cache, cache / "pack", tick)
        (cache / "done").write_text(str(p), encoding="utf-8")
        self._import_cache = getattr(self, "_import_cache", set()) | {str(cache)}
        return cache / "pack"

    def _clear_import_cache(self) -> None:
        for c in getattr(self, "_import_cache", set()):
            shutil.rmtree(c, ignore_errors=True)
        self._import_cache = set()

    # ------------------------------------------------------------ the pack being created
    def draft_start(self, src: str, name: str) -> dict:
        """A new pack in creation that starts as an exact copy of another pack."""
        def work(tick, src, name):
            from skynx import draft as DR
            nm = (name or "").strip() or Path(src).name
            if any(c in nm for c in '<>:"/\\|?*'):
                raise CV.ConvertError("The name can't have < > : \" / \\ | ? *",
                                      "El nombre no puede tener < > : \" / \\ | ? *")
            dest = self._library_root() / "Drafts" / nm
            tick(nm)
            self._drop_analysis()
            self._pack = DR.start_from_pack(Pack.open(Path(src)), dest, nm,
                                            progress=lambda f, i=0, n=0: tick(f, i, n),
                                            link=self._settings.get("draft_links", True) is not False)
            self._remember(str(dest))
            self._result = self._audit(True, tick)
            return self._audit_out()
        return self._run("…", work, src, name)

    def draft_view(self) -> dict:
        from skynx import draft as DR
        if not self._pack or not DR.is_draft(self._pack.root):
            return {"ok": True, "draft": None}
        v = DR.view(self._pack, mods_view(self._pack))
        if self._pack.project:
            from skynx import project as PJ
            fo = PJ.folders_for(self._pack)
            mods_dir = Path(self._pack.root) / PJ.MODS
            for r in v["rows"]:
                if r["id"] in fo:
                    r["folder"] = str(mods_dir / fo[r["id"]])
            v["project"] = {"mods": str(mods_dir), "root": str(self._pack.root)}
        return {"ok": True, "draft": v}

    def draft_toggle(self, row_id: str, goes: bool, force: bool = False) -> dict:
        from skynx import draft as DR
        try:
            with self._exclusive("…"):
                if goes:
                    with Transaction(self._pack.root, f"Goes: {row_id}") as tx:
                        r = DR.include(self._pack, row_id, tx, force=bool(force))
                    if r.get("refused"):
                        return {"ok": False, "needs": r["needs"], "parked": r["parked"]}
                else:
                    row = next((x for x in mods_view(self._pack) if x["id"] == row_id), None)
                    if row is None:
                        return {"ok": False, "error": f"{row_id}?"}
                    with Transaction(self._pack.root, f"Doesn't go: {row_id}") as tx:
                        r = DR.exclude(self._pack, row, tx, force=bool(force))
                    if r.get("refused"):
                        return {"ok": False, "users": r["users"]}
                self._pack.reload()
                self._result = self._audit(False)
                return {"ok": True, "missing": r.get("missing", []),
                        "draft": DR.view(self._pack, mods_view(self._pack)), **self._audit_out()}
        except _Busy:
            return self._busy_out()
        except Exception as e:  # noqa: BLE001
            return {"ok": False, "error": self._err(e)}

    def draft_create(self, name: str, dest: str = "") -> dict:
        """Create the modpack: a clean copy of the draft without the mods that don't go."""
        def work(tick, name, dest):
            from skynx import draft as DR
            nm = (name or "").strip()
            if not nm or any(c in nm for c in '<>:"/\\|?*'):
                raise CV.ConvertError("Give the modpack a name without < > : \" / \\ | ? *",
                                      "Ponle al modpack un nombre sin < > : \" / \\ | ? *")
            target = Path(dest) if dest else self._library_root() / "Packs" / nm
            out = DR.create_modpack(self._pack, target, progress=lambda f, i=0, n=0: tick(f, i, n),
                                    link=self._settings.get("draft_links", True) is not False)
            return {"created": out}
        return self._run("…", work, name, dest)

    def rename_preview(self, name: str, new: str) -> dict:
        from skynx.bsafix import rename_plan
        from skynx.rename import safe_name
        from skynx import knowledge as KN
        new = (new or "").strip()
        if not new:
            return {"ok": False, "error": "?"}
        ext = Path(name).suffix
        if Path(new).suffix.lower() != ext.lower():
            new += ext
        problems = []
        if any(c in new for c in '<>:"/\\|?*'):
            problems.append(["Windows doesn't allow < > : \" / \\ | ? * in names.",
                             "Windows no permite < > : \" / \\ | ? * en los nombres."])
        if safe_name(new) != new:
            problems.append([f"Google Drive and some copies damage this name; {safe_name(new)} travels safely.",
                             f"Google Drive y algunas copias dañan este nombre; {safe_name(new)} viaja seguro."])
        if new.lower() != name.lower() and (self._pack.data_dir / new).exists():
            problems.append([f"{new} already exists.", f"{new} ya existe."])
        plan = rename_plan(self._pack, name, new)
        raw = self._pack.list_path.read_bytes() if self._pack.list_path else b""
        on_list = any(e.lstrip("#").strip().lower() == name.lower() for e in C_entries(raw))
        from skynx.ccc import ENC, ERR
        delta = (len(new.encode(ENC, ERR)) - len(name.encode(ENC, ERR))) if on_list else 0
        return {"ok": True, "new": new, "safe": safe_name(new), "problems": problems,
                "plan": {"bsas": [list(x) for x in plan["bsas_rename"]], "patch": plan["bsas_patch"],
                         "dependents": plan["dependents"], "list": plan["list"],
                         "inis": [getattr(x, "name", str(x)) for x in plan["inis"]]},
                "ccc_delta": delta, "ccc_bytes": self._pack.list_bytes + delta,
                "ccc_limit": KN.CCC_BYTE_LIMIT if self._pack.mode == "AE" else None}

    def rename_plugin(self, name: str, new: str) -> dict:
        from skynx.bsafix import safe_rename
        pv = self.rename_preview(name, new)
        if not pv.get("ok"):
            return pv
        hard = [p for p in pv["problems"] if p[0].startswith(("Windows", f"{pv['new']} already"))]
        if hard:
            return {"ok": False, "error": hard[0][1 if self._lang == "es" else 0]}
        try:
            with self._exclusive("…"):
                with Transaction(self._pack.root, f"Rename {name} -> {pv['new']}") as tx:
                    safe_rename(self._pack, name, pv["new"], tx)
                self._pack.reload()
                self._result = self._audit(False)
                return {"ok": True, "new": pv["new"], **self._audit_out()}
        except _Busy:
            return self._busy_out()
        except Exception as e:  # noqa: BLE001
            return {"ok": False, "error": self._err(e)}

    # ------------------------------------------------------------ the mod workshop
    def _bench(self):
        from skynx import workshop as WS
        if not self._pack or not WS.is_bench(self._pack.root):
            raise CV.ConvertError("Open a workshop bench first.", "Abre primero una mesa del taller.")
        return self._pack

    def workshop_list(self) -> dict:
        from skynx import workshop as WS
        root = self._library_root() / "Workshop"
        out = []
        if root.is_dir():
            for d in sorted(root.iterdir(), key=lambda x: -x.stat().st_mtime):
                b = WS.load(d) if d.is_dir() else None
                if not b:
                    continue
                data = d / "01000A10041EA000" / "romfs" / "Data"
                n = len([f for f in data.iterdir() if f.suffix.lower() in (".esp", ".esm", ".esl", ".bsa")]) if data.is_dir() else 0
                out.append({"path": str(d), "name": b.get("name") or d.name, "kind": b.get("kind"),
                            "files": n, "edit_of": b.get("edit_of"),
                            "when": time.strftime("%Y-%m-%d %H:%M", time.localtime(d.stat().st_mtime))})
        return {"ok": True, "root": str(root), "benches": out}

    def workshop_new(self, kind: str, name: str, edition: str = "AE", sources: list | None = None) -> dict:
        def work(tick, kind, name, edition, sources):
            from skynx import workshop as WS
            nm = (name or "").strip() or {"convert": "Convert", "edit": "Edit", "suite": "Suite",
                                          "merge": "Merge"}.get(kind, "Bench")
            if any(c in nm for c in '<>:"/\\|?*'):
                raise CV.ConvertError("The name can't have < > : \" / \\ | ? *",
                                      "El nombre no puede tener < > : \" / \\ | ? *")
            dest = WS.free_name(self._library_root() / "Workshop", nm)
            self._drop_analysis()
            bench = WS.new_bench(dest, nm, kind, edition, Path(self._folder("inis_dir")))
            reports = []
            if sources:
                reports = WS.bring(bench, list(sources), progress=tick)
            if kind == "edit" and sources and len(sources) == 1:
                b = WS.load(dest) or {}
                b["edit_of"] = str(sources[0])
                WS._write_info(dest, b)
            self._pack = Pack.open(dest)
            self._result = self._audit(False, tick)
            return {"reports": reports, **self._audit_out()}
        return self._run("…", work, kind, name, edition, sources or [])

    def workshop_open(self, path: str) -> dict:
        def work(tick, path):
            from skynx import workshop as WS
            if not WS.is_bench(Path(path)):
                raise CV.ConvertError("That isn't a workshop bench.", "Eso no es una mesa del taller.")
            self._drop_analysis()
            self._pack = Pack.open(Path(path))
            recover_interrupted(self._pack.root)
            self._pack.reload()
            self._result = self._audit(False, tick)
            return self._audit_out()
        return self._run("…", work, path)

    def workshop_bring(self, sources: list) -> dict:
        def work(tick, sources):
            from skynx import workshop as WS
            reports = WS.bring(self._bench(), list(sources), progress=tick)
            self._pack.reload()
            self._result = self._audit(False, tick)
            return {"reports": reports, **self._audit_out()}
        return self._run("…", work, sources)

    def workshop_view(self) -> dict:
        from skynx import workshop as WS
        try:
            bench = self._bench()
        except Exception as e:  # noqa: BLE001
            return {"ok": False, "error": self._err(e)}
        info = WS.load(bench.root) or {}
        rows = mods_view(bench)
        order = [e for e, _ in bench.load_order() if not e.startswith("#") and e.lower() in bench.plugins]
        out = {"ok": True, "info": info, "rows": rows, "plugins": order,
               "bsas": sorted(p.name for p in bench.bsas.values()), "loose": list(bench.loose_dirs),
               "size": bench.data_size(), "path": str(bench.root), "data": str(bench.data_dir)}
        if len(out["bsas"]) >= 2 or info.get("merged"):
            try:
                ren = self._retarget(info)
                plan = WS.merge_plan(bench, None, ren)
                out["join"] = {k: plan[k] for k in ("anchor", "files", "size", "textures", "result", "ini_loaded")}
                out["join"]["overlaps"] = plan["overlaps"][:50]
                out["join"]["n_overlaps"] = len(plan["overlaps"])
                out["join"]["order"] = plan["order"]
            except Exception as e:  # noqa: BLE001
                out["join_error"] = self._err(e)
        return out

    @staticmethod
    def _retarget(info: dict) -> dict:
        m = info.get("merged") or {}
        return {c.lower(): m["plugin"] for c in m.get("components", [])} if m.get("plugin") else {}

    def workshop_join_plan(self, anchor: str | None = None) -> dict:
        from skynx import workshop as WS
        try:
            bench = self._bench()
            plan = WS.merge_plan(bench, anchor, self._retarget(WS.load(bench.root) or {}))
            plan["n_overlaps"] = len(plan["overlaps"])
            plan["overlaps"] = plan["overlaps"][:50]
            return {"ok": True, "plan": plan}
        except Exception as e:  # noqa: BLE001
            return {"ok": False, "error": self._err(e)}

    def workshop_join(self, anchor: str | None = None, name: str = "") -> dict:
        def work(tick, anchor, name):
            from skynx import workshop as WS
            bench = self._bench()
            ren = self._retarget(WS.load(bench.root) or {})
            with Transaction(bench.root, "Join BSAs") as tx:
                r = WS.merge_bsas(bench, tx, anchor, name or None, ren or None, progress=tick)
            self._pack.reload()
            self._result = self._audit(False, tick)
            return {"join": r, **self._audit_out()}
        return self._run("…", work, anchor, name)

    def workshop_bring_merge(self, folder: str) -> dict:
        from skynx import workshop as WS
        try:
            with self._exclusive("…"):
                bench = self._bench()
                with Transaction(bench.root, "Bring the merged plugin") as tx:
                    r = WS.bring_merge(bench, Path(folder), tx)
                self._pack.reload()
                self._result = self._audit(False)
                return {"ok": True, "merge": r, **self._audit_out()}
        except _Busy:
            return self._busy_out()
        except Exception as e:  # noqa: BLE001
            return {"ok": False, "error": self._err(e)}

    def workshop_zedit(self) -> dict:
        """A folder zEdit accepts as a Skyrim SE game, with the bench's plugins,
        for building a merge with zMerge; zEdit opens if it is set up."""
        def work(tick):
            from skynx import xtools as X
            bench = self._bench()
            dest = self._workspace_root() / (bench.root.name + " (zEdit)")
            # never force: a merge zMerge left in that folder (not brought yet) must not be wiped
            ws = X.make_xedit_workspace(bench, Path(self._folder("vanilla_dir")), dest, zedit_stub=True)
            exe = next((t["path"] for t in self.tools_list()["tools"] if t["id"] == "zedit" and t["path"]), None)
            started = False
            if exe:
                X.launch(X.zedit_command(Path(exe)), cwd=str(Path(exe).parent))
                started = True
            return {"workspace": ws["root"], "data": ws["data"], "zedit": exe, "started": started,
                    "missing": ws["missing"], "merges": str(Path(exe).parent / "merges") if exe else None}
        return self._run("…", work)

    def workshop_save(self, name: str, replace: bool = False) -> dict:
        def work(tick, name, replace):
            from skynx import workshop as WS
            bench = self._bench()
            info = WS.load(bench.root) or {}
            conv = self._library_root() / "Converted"
            target = None
            if replace and info.get("edit_of"):
                eo = Path(info["edit_of"])
                if eo.is_dir() and eo.parent.resolve() == conv.resolve():
                    target = eo
                else:
                    raise CV.ConvertError("Only mods in Library\\Converted can be replaced; save it as a new mod.",
                                          "Solo se reemplazan mods de Library\\Converted; guárdalo como mod nuevo.")
            out = WS.save_mod(bench, conv, name, replace=target, trash_root=self._library_root() / ".trash")
            return {"saved": out}
        return self._run("…", work, name, replace)

    def workshop_discard(self) -> dict:
        from skynx import workshop as WS
        try:
            with self._exclusive("…"):
                bench = self._bench()
                root = bench.root
                if not WS.is_bench(root) or root.parent.resolve() != (self._library_root() / "Workshop").resolve():
                    return {"ok": False, "error": "?"}
                self._pack = None
                self._result = None
                shutil.rmtree(root, ignore_errors=True)
                return {"ok": True}
        except _Busy:
            return self._busy_out()
        except Exception as e:  # noqa: BLE001
            return {"ok": False, "error": self._err(e)}

    # ------------------------------------------------------------ which mod is it (Nexus)
    def _ident_rows(self) -> list:
        from skynx import draft as DR
        rows = mods_view(self._pack)
        if DR.is_draft(self._pack.root):
            rows = DR.view(self._pack, rows)["rows"]
        return rows

    def identify_mods(self) -> dict:
        """Every mod of the open pack (or bench), with what is known of its Nexus page."""
        from skynx import identify as ID
        from skynx import loot
        if not self._pack:
            return {"ok": False, "error": "?"}
        try:
            _d, ml_path, _u = self._loot_paths()
            ml = loot.load_masterlist(ml_path) if ml_path.exists() else None
            store = ID.load_store(self._library_root())
            records = CV.load_mods(self._pack)
            aliases = self._aliases()
            paths = {k: h.path for k, h in self._pack.plugins.items()}
            out = []
            for r in self._ident_rows():
                if not r.get("plugins"):
                    q = ID.query_for((r.get("bsas") or [r["name"]])[0])
                    out.append({"id": r["id"], "ident": {"status": "unknown", "mod_id": None, "query": q,
                                                         "search": ID.search_url(q), "candidates": [], "hints": {},
                                                         "originals": []}})
                    continue
                ident = ID.identify(r["plugins"], self._pack.plugins, record=records.get(r["id"]), aliases=aliases,
                                    masterlist=ml, store=store, paths=paths)
                out.append({"id": r["id"], "ident": ident})
            return {"ok": True, "rows": out, "masterlist": ml is not None,
                    "nexus_key": bool(self._settings.get("nexus_key"))}
        except Exception as e:  # noqa: BLE001
            traceback.print_exc()
            return {"ok": False, "error": self._err(e)}

    def identify_lookup(self, items: list) -> dict:
        """Mods outside the open pack (the Add mods queue, the Catalog):
        [{key, plugins, hashes?}] -> {key: chip}. Uses what you confirmed
        (by plugin SHA-1) and LOOT's list; no Nexus calls."""
        from skynx import identify as ID
        from skynx import loot
        try:
            _d, ml_path, _u = self._loot_paths()
            ml = loot.load_masterlist(ml_path) if ml_path.exists() else None
            store = ID.load_store(self._library_root())
            out = {}
            for it in items or []:
                plugins = [p for p in (it.get("plugins") or []) if p]
                if not plugins:
                    continue
                shas = {}
                for p, h in zip(plugins, it.get("hashes") or []):
                    if h:
                        shas[p.lower()] = h
                for extra in it.get("more_hashes") or []:          # other versions of the same mod
                    for p, h in zip(plugins, extra or []):
                        if h and ID._store_hit(store, h, p):
                            shas[p.lower()] = h
                out[str(it.get("key"))] = ID.brief(ID.identify(plugins, {}, masterlist=ml, store=store, shas=shas))
            return {"ok": True, "rows": out, "masterlist": ml is not None}
        except Exception as e:  # noqa: BLE001
            traceback.print_exc()
            return {"ok": False, "error": self._err(e)}

    def identify_set(self, plugin: str, text: str) -> dict:
        """The person says which Nexus mod a plugin is (a link or the number);
        empty text forgets it."""
        from skynx import identify as ID
        h = self._pack.plugins.get(str(plugin).lower()) if self._pack else None
        if h is None:
            return {"ok": False, "error": f"{plugin}?"}
        mod_id = None
        if str(text or "").strip():
            mod_id = ID.parse_input(text)
            if mod_id is None:
                return {"ok": False, "error": "Paste a Skyrim Special Edition Nexus link (…/skyrimspecialedition/mods/123) or the number."
                        if self._lang == "en" else
                        "Pega un enlace de Nexus de Skyrim Special Edition (…/skyrimspecialedition/mods/123) o el número."}
        ID.remember(self._library_root(), h.path, mod_id, h.name)
        return {"ok": True, "mod_id": mod_id}

    def identify_details(self, mod_ids: list) -> dict:
        """Name, version and author from Nexus for these mods (needs the API key)."""
        def work(tick, mod_ids):
            from skynx import identify as ID
            client = self._nexus_client()
            got, errors = {}, []
            ids = sorted({int(x) for x in mod_ids if str(x).isdigit() or isinstance(x, int)})
            for i, mid in enumerate(ids):
                tick(f"Nexus {mid}", i, len(ids))
                try:
                    info = client.mod(mid)
                    ID.remember_details(self._library_root(), mid, info)
                    got[str(mid)] = {k: info.get(k) for k in ("name", "version", "author")}
                except Exception as e:  # noqa: BLE001
                    errors.append(f"{mid}: {self._err(e)}")
                    if "rate" in str(e).lower():
                        break
            return {"details": got, "errors": errors}
        return self._run("…", work, mod_ids)

    def nexus_compat(self, row_ids: list | None = None) -> dict:
        """For the identified mods of the open pack: which Nexus version you
        have, the latest, and the newest one that works on Switch (no SKSE)."""
        idents = self.identify_mods()
        if not idents.get("ok"):
            return idents
        names = {r["id"]: r["name"] for r in self._ident_rows()}
        plugins = {r["id"]: (r.get("plugins") or [None])[0] for r in self._ident_rows()}
        want = {str(x) for x in (row_ids or [])}
        todo = [r for r in idents["rows"] if r["ident"].get("mod_id") and (not want or str(r["id"]) in want)]

        def work(tick, todo):
            from skynx import compat as CP
            if not todo:
                return {"mods": [], "errors": [], "skipped": len(idents["rows"])}
            client = self._nexus_client()
            out, errors, done = [], [], {}
            for i, r in enumerate(todo):
                ident = r["ident"]
                mid = int(ident["mod_id"])
                tick(f"Nexus {mid}", i, len(todo))
                inst = ident.get("installed")
                key = (mid, json.dumps(inst, sort_keys=True))
                try:
                    if key not in done:
                        done[key] = CP.check(client, mid, inst)
                    res = done[key]
                except Exception as e:  # noqa: BLE001
                    errors.append(f"{names.get(r['id'], mid)}: {self._err(e)}")
                    if "rate" in str(e).lower():
                        break
                    continue
                es = self._lang == "es"

                def tr(row):
                    return None if row is None else dict(row, reasons=[x[1] if es else x[0] for x in row["reasons"]])
                out.append({"id": r["id"], "name": names.get(r["id"], r["id"]), "plugin": plugins.get(r["id"]),
                            "mod_id": mid, "url": ident.get("url"),
                            "title": (ident.get("details") or {}).get("name") or ident.get("title"),
                            "installed": inst, "status": res["status"],
                            **{k: tr(res[k]) for k in ("have", "latest", "best")},
                            "rows": [tr(x) for x in res["rows"][:12]]})
            return {"mods": out, "errors": errors, "skipped": len(idents["rows"]) - len(todo)}
        return self._run("…", work, todo)

    def identify_installed(self, plugin: str, mod_id: int, file_id=None, version=None) -> dict:
        """"I have this one": which file of the Nexus mod the plugin is."""
        from skynx import identify as ID
        h = self._pack.plugins.get(str(plugin).lower()) if self._pack else None
        if h is None:
            return {"ok": False, "error": f"{plugin}?"}
        try:
            ID.remember_installed(self._library_root(), h.path, int(mod_id), file_id=file_id, version=version, name=h.name)
            return {"ok": True}
        except Exception as e:  # noqa: BLE001
            return {"ok": False, "error": self._err(e)}

    def loot_download(self) -> dict:
        def work(tick):
            from skynx import loot
            cache, _ml, _u = self._loot_paths()
            tick("masterlist")
            loot.fetch_masterlist(cache)
            return {"ok": True}
        return self._run("…", work)

    def open_folder(self, path: str) -> dict:
        p = Path(path)
        if not p.is_dir():
            return {"ok": False}
        try:
            if os.name == "nt":
                os.startfile(str(p))  # type: ignore[attr-defined]
            return {"ok": True}
        except OSError as e:
            return {"ok": False, "error": str(e)}

    # ------------------------------------------------------------ external tools, plugin manager, BSA extract
    def tools_list(self) -> dict:
        from skynx import xtools as X
        paths = self._settings.get("ext_tools") or {}
        dirs = [Path(self._settings.get("tools_dir") or r"C:\SkyNX\Tools")]
        out = []
        for t in X.known_tools():
            p = paths.get(t["id"]) or (str(X.find_tool(t["id"], dirs) or "") if t["id"] != "other" else "")
            out.append({"id": t["id"], "name": t["name"], "kind": t["kind"], "path": p,
                        "how": t["how"].get(self._lang) or t["how"]["en"]})
        return {"tools": out}

    def set_tool_path(self, tool_id: str, path: str) -> dict:
        tools = dict(self._settings.get("ext_tools") or {})
        if path:
            tools[tool_id] = path.strip()
        else:
            tools.pop(tool_id, None)
        self._settings["ext_tools"] = tools
        self._save_settings()
        return self.tools_list()

    def _workspace_root(self) -> Path:
        v = self._settings.get("workspace_dir")
        if v:
            return Path(v)
        sk = Path(r"C:\SkyNX")
        return (sk / "Workspace") if sk.is_dir() else settings_path().parent / "workspace"

    def xedit_open(self, tool_id: str = "sseedit", mode: str = "copy", existing: str = "") -> dict:
        """mode "direct": when xEdit closes, its changes go into the pack by
        themselves (one history entry, undoable) and the working folder is
        removed. mode "copy": when xEdit closes, the person decides whether to
        bring the changes, keep the copy for later or delete it.
        existing: "reuse" opens a kept copy as it is; "rebuild" starts over and
        drops its edits; "" refuses to touch a copy with edits not brought back."""
        mode = "direct" if mode == "direct" else "copy"

        def work(tick, tool_id):
            from skynx import xtools as X
            sess = getattr(self, "_xe_session", None)
            if sess and sess.get("running"):
                raise CV.ConvertError("SSEEdit is already open with a working copy. Close it first.",
                                      "SSEEdit ya está abierto con una copia de trabajo. Ciérralo primero.")
            exe = (self.tools_list()["tools"])
            exe = next((t["path"] for t in exe if t["id"] == tool_id and t["path"]), None)
            if not exe:
                raise CV.ConvertError("Set where SSEEdit is in Settings, External tools.",
                                      "Indica dónde está SSEEdit en Ajustes, Herramientas externas.")
            dest = self._workspace_root() / self._pack.root.name
            tick("workspace")
            if (dest / X.MANIFEST).is_file() and existing != "rebuild":
                X.relink_workspace(dest, self._pack)        # the pack moved since: follow it
            if existing == "reuse" and (dest / X.MANIFEST).is_file():
                ws = X.open_existing_workspace(dest)
            else:
                ws = X.make_xedit_workspace(self._pack, Path(self._folder("vanilla_dir")), dest,
                                            force=(existing == "rebuild"))
            self._xedit_ws = ws
            sess = {"mode": mode, "pack": str(self._pack.root), "workspace": ws["root"],
                    "running": True, "code": None}

            def closed(code, sess=sess):
                sess["running"] = False
                sess["code"] = code
            X.launch(X.xedit_command(Path(exe), ws), cwd=str(Path(exe).parent), on_exit=closed)
            self._xe_session = sess          # only once it really started
            return {"workspace": ws["root"], "mode": mode, "missing": ws["missing"],
                    "notes": [n.get(self._lang) or n.get("en") for n in ws["notes"]]}
        return self._run("…", work, tool_id)

    def _exclusive(self, label: str):
        """Hold the job slot for a short synchronous change, so it never runs
        at the same time as a background job on the same pack."""
        api = self

        class Slot:
            def __enter__(self_):
                with api._run_lock:
                    if api._progress.get("busy"):
                        raise _Busy()
                    self_.prog = {"busy": True, "label": label, "i": 0, "n": 0, "error": None,
                                  "result": None, "job": None}
                    api._progress = self_.prog
                return self_

            def __exit__(self_, *exc):
                self_.prog["busy"] = False
                return False
        return Slot()

    def _busy_out(self) -> dict:
        return {"ok": False, "busy": True,
                "error": "Another task is running; try again when it ends." if self._lang == "en"
                else "Hay otra tarea en curso; inténtalo cuando termine."}

    def _session_pack(self, sess):
        if self._pack and os.path.normcase(str(self._pack.root)) == os.path.normcase(sess["pack"]):
            return self._pack, True
        return Pack.open(Path(sess["pack"])), False

    def xedit_session(self) -> dict:
        """State of the last xEdit launch, for the page to poll."""
        from skynx import xtools as X
        sess = getattr(self, "_xe_session", None)
        if not sess:
            return {"ok": True, "session": None}
        out = dict(sess)
        out["pack_name"] = Path(sess["pack"]).name
        if not sess["running"]:
            try:
                pack, _ = self._session_pack(sess)
                st = X.sync_status(pack, sess["workspace"])
                out.update({k: st.get(k, []) for k in ("changed", "new", "conflicts", "pending_saves",
                                                        "gone", "vanilla_changed")})
            except Exception as e:  # noqa: BLE001
                out["error"] = self._err(e)
        return {"ok": True, "session": out}

    def xedit_finish(self, action: str) -> dict:
        """After xEdit closed: "bring" puts its changes into the pack (conflicts
        included: the person saw them listed) and deletes the working copy when
        nothing is left in it; "keep" leaves the copy for later; "discard"
        deletes the copy unchanged."""
        from skynx import xtools as X
        sess = getattr(self, "_xe_session", None)
        if not sess:
            return {"ok": True, "files": []}
        if sess.get("running"):
            return {"ok": False, "error": "SSEEdit is still open." if self._lang == "en" else "SSEEdit sigue abierto."}
        try:
            with self._exclusive("SSEEdit"):
                files: list = []
                left: list = []
                pack, current = self._session_pack(sess)
                if action == "bring":
                    st = X.sync_status(pack, sess["workspace"])
                    if st.get("pending_saves"):
                        return {"ok": False, "error": ("SSEEdit didn't finish saving: " if self._lang == "en"
                                                       else "SSEEdit no terminó de guardar: ") + ", ".join(st["pending_saves"])}
                    if st["changed"] or st["new"] or st["conflicts"]:
                        with Transaction(pack.root, "Changes from SSEEdit") as tx:
                            files = X.sync_back(pack, sess["workspace"], tx, force=True)
                    left = X.pending_edits(X.sync_status(pack, sess["workspace"]))
                    if not left:
                        X.discard_workspace(sess["workspace"])
                elif action == "discard":
                    X.discard_workspace(sess["workspace"])
                self._xe_session = None
                if action == "discard" or (action == "bring" and not left):
                    self._xedit_ws = None
                out = {"ok": True, "files": files, "left": left}
                if current and files:
                    self._pack.reload()
                    self._result = self._audit(False)
                    out.update(self._audit_out())
                return out
        except _Busy:
            return self._busy_out()
        except Exception as e:  # noqa: BLE001
            return {"ok": False, "error": self._err(e)}

    def _xedit_workspace(self):
        from skynx import xtools as X
        dest = self._workspace_root() / self._pack.root.name
        ws = getattr(self, "_xedit_ws", None)
        if ws and Path(ws["root"]) == dest and (dest / X.MANIFEST).is_file():
            return ws
        return str(dest) if (dest / X.MANIFEST).is_file() else None

    def xedit_status(self) -> dict:
        from skynx import xtools as X
        ws = self._xedit_workspace()
        if not ws:
            return {"ok": True, "workspace": None}
        root = ws["root"] if isinstance(ws, dict) else ws
        try:
            X.relink_workspace(root, self._pack)
            return {"ok": True, "workspace": root, **X.sync_status(self._pack, ws)}
        except Exception as e:  # noqa: BLE001
            return {"ok": False, "workspace": root, "foreign": True, "error": self._err(e)}

    def xedit_sync(self, force: bool = False) -> dict:
        from skynx import xtools as X
        ws = self._xedit_workspace()
        if not ws:
            return {"ok": False, "error": "Open the pack in SSEEdit first" if self._lang == "en"
                    else "Abre primero el pack en SSEEdit"}
        try:
            with self._exclusive("SSEEdit"):
                X.relink_workspace(ws["root"] if isinstance(ws, dict) else ws, self._pack)
                with Transaction(self._pack.root, "Changes from SSEEdit") as tx:
                    files = X.sync_back(self._pack, ws, tx, force=bool(force))
                self._pack.reload()
                self._result = self._audit(False)
                return {"ok": True, "files": files, **self._audit_out()}
        except _Busy:
            return self._busy_out()
        except Exception as e:  # noqa: BLE001
            return {"ok": False, "error": self._err(e)}

    def masters_view(self) -> list:
        from skynx import xtools as X
        return X.masters_view(self._pack) if self._pack else []

    def plugin_active(self, name: str, active: bool, force: bool = False) -> dict:
        from skynx import xtools as X
        try:
            with self._exclusive("…"):
                with Transaction(self._pack.root, f"{'Enable' if active else 'Disable'} {name}") as tx:
                    r = X.set_plugin_active(self._pack, name, bool(active), tx, force=bool(force))
                if r.get("refused"):
                    return {"ok": False, "users": r.get("users", []),
                            "error": (f"{', '.join(r.get('users', []))} use it as a master." if self._lang == "en"
                                      else f"{', '.join(r.get('users', []))} lo usan como master.")}
                self._pack.reload()
                self._result = self._audit(False)
                return {"ok": True, **self._audit_out()}
        except _Busy:
            return self._busy_out()
        except Exception as e:  # noqa: BLE001
            return {"ok": False, "error": self._err(e)}

    def cc_off_unneeded(self, the_patch: bool = False) -> dict:
        from skynx import xtools as X
        try:
            with self._exclusive("…"):
                with Transaction(self._pack.root, "Creation Club: switch off what nothing needs"
                                 + (" (with its unofficial patch)" if the_patch else "")) as tx:
                    off = X.cc_off_unneeded(self._pack, tx, bool(the_patch))
                self._pack.reload()
                self._result = self._audit(False)
                return {"ok": True, "off": off, **self._audit_out()}
        except _Busy:
            return self._busy_out()
        except Exception as e:  # noqa: BLE001
            return {"ok": False, "error": self._err(e)}

    def bsa_extract(self, names: list, dest: str) -> dict:
        def work(tick, names, dest):
            from skynx import xtools as X
            return X.extract_pack_bsas(self._pack, list(names), Path(dest), progress=tick)
        return self._run("…", work, names, dest)

    # ------------------------------------------------------------ audit with the app's settings
    def _cache_dir(self) -> Path:
        d = settings_path().parent / "cache"
        d.mkdir(parents=True, exist_ok=True)
        return d

    def _loot_paths(self):
        d = settings_path().parent / "loot"
        return d, d / "masterlist.yaml", d / "userlist.json"

    def _aliases(self) -> dict:
        from skynx.bsafix import load_renames
        aliases = {}
        for rec in CV.load_mods(self._pack).values():
            aliases.update(rec.get("renamed") or {})
        aliases.update(load_renames(self._pack))
        return aliases

    def _audit(self, deep: bool, progress=None):
        """The Doctor with the app's settings: vanilla folder, caches, and the
        LOOT masterlist when it's already downloaded (never fetched here)."""
        self._sync_project(progress)
        R = run_audit(self._pack, deep=deep, progress=progress,
                      vanilla_dir=self._folder("vanilla_dir") or None, cache_dir=self._cache_dir())
        _d, ml_path, ul_path = self._loot_paths()
        if ml_path.exists() and self._pack.list_path:
            try:
                from skynx import loot
                from skynx.audit import add_loot_findings
                add_loot_findings(R, self._pack, loot.load_masterlist(ml_path), aliases=self._aliases(),
                                  userlist=loot.load_userlist(ul_path))
            except Exception:  # noqa: BLE001
                traceback.print_exc()
        self._draft_filter(R)
        self._project_health(R)
        return R

    def _sync_project(self, progress=None) -> None:
        """A project: Mods/ and Base/ follow the working pack, and what was
        changed by hand there comes in (as one undoable change)."""
        self._sync_report = None
        if not (self._pack and self._pack.project):
            return
        from skynx import project as PJ
        try:
            rep = PJ.sync(self._pack)
            if rep.get("pulled"):
                self._pack.reload()
            self._sync_report = rep
        except Exception:  # noqa: BLE001
            traceback.print_exc()

    def _project_health(self, R) -> None:
        if not (self._pack and self._pack.project):
            return
        try:
            c = {s: sum(1 for f in R.findings if f.severity == s) for s in ("critico", "aviso", "ahorro", "info")}
            (Path(self._pack.root) / ".skynx" / "summary.json").write_text(json.dumps(
                {**c, "plugins": len(self._pack.plugins), "mode": self._pack.mode,
                 "when": time.strftime("%Y-%m-%d %H:%M:%S")}), encoding="utf-8")
        except OSError:
            pass

    def _draft_filter(self, R) -> None:
        """In a pack being created, the mods marked "doesn't go" are parked on
        purpose: the Doctor must neither report nor fix anything about them."""
        from skynx import draft as DR
        from skynx.audit import Finding
        d = DR.load(self._pack.root)
        if not d or not d["excluded"]:
            return
        skip = DR.excluded_files(self._pack.root)

        def touches(f) -> bool:
            # only findings ABOUT a parked file; a plugin that goes and misses a parked master still shows
            return bool(f.subject) and f.subject.lower().split(" (")[0].strip() in skip
        R.findings = [f for f in R.findings if not touches(f)]
        names = ", ".join(r.get("name") or k for k, r in d["excluded"].items())
        R.findings.append(Finding("draft-parked", "info", "list", "draft-parked", "",
                                  {"n": len(d["excluded"]), "names": names}))

    # ------------------------------------------------------------ settings: folders
    def _library_root(self) -> Path:
        from skynx.library import default_root
        return Path(self._settings.get("library_dir") or default_root())

    def set_folder(self, which: str, path: str) -> dict:
        if which in ("library_dir", "ussep_dir", "tools_dir", "vanilla_dir", "inis_dir"):
            self._settings[which] = path.strip()
            self._save_settings()
        return self.state()

    def vanilla_build(self):
        """Build (or bring up to date) the game list now, as a job."""
        def work(tick):
            from skynx.vanilla import load
            vd = self._folder("vanilla_dir")
            if _vanilla_status(vd) != "ok":
                return {"ok": False, "list": {}}
            load(Path(vd), self._cache_dir(), progress=tick)
            return {"ok": True, "list": _vanilla_summary(vd)}
        return self._run("…", work)

    def vanilla_forget(self) -> dict:
        """Drop the BSAs and plugins that are no longer in the game files folder."""
        from skynx.vanilla import forget_kept
        vd = self._folder("vanilla_dir")
        n = forget_kept(Path(vd), self._cache_dir()) if vd else 0
        return {"n": n, "state": self.state()}

    def ussep_scan(self) -> dict:
        from skynx.ussep import scan
        return scan(self._folder("ussep_dir"))

    # ------------------------------------------------------------ splash and setup
    UI_PREFS = ("splash_hide", "keep_converted", "draft_links", "intro_seen", "project_links", "reopen_last")

    def set_ui_pref(self, key: str, value) -> dict:
        if key in self.UI_PREFS:
            self._settings[key] = bool(value)
            self._save_settings()
        return {"ok": True, "prefs": {k: self._settings.get(k) for k in self.UI_PREFS}}

    def ui_prefs(self) -> dict:
        return {"splash_hide": bool(self._settings.get("splash_hide")),
                "draft_links": self._settings.get("draft_links", True) is not False,
                "keep_converted": self._settings.get("keep_converted", True) is not False,
                "intro_seen": bool(self._settings.get("intro_seen")),
                "project_links": self._settings.get("project_links") is True,
                "reopen_last": self._settings.get("reopen_last", True) is not False,
                "reopen": self._reopen_path(),
                "version": __version__}

    def _reopen_path(self) -> str | None:
        """The pack that was open when the app last closed (a new version of the
        app starts where the old one was), unless it was closed on purpose."""
        if self._settings.get("reopen_last", True) is False:
            return None
        last = self._settings.get("last_open")
        return last if last and Path(last).is_dir() else None

    def setup_status(self) -> dict:
        """Everything the app can use on this PC: what it is for, whether it is
        needed, and whether it was found (and where)."""
        from skynx.ussep import scan
        ts = self._tools()
        st = ts.status()
        folder = st.get("folder") or self._settings.get("tools_dir") or r"C:\SkyNX\Tools"

        def it(id_, group, need, ok, path, en, es, fix=None, warn=None):
            return {"id": id_, "group": group, "need": need, "ok": bool(ok), "path": str(path or ""),
                    "what": [en, es], "fix": fix, "warn": warn}
        items = [
            it("texconv", "tools", "convert", st["texconv"], ts.texconv or folder,
               "Converts PC textures (DirectXTex texconv.exe).", "Convierte texturas de PC (texconv.exe de DirectXTex).",
               {"kind": "folder", "which": "tools_dir"}),
            it("ffmpeg", "tools", "convert", st["ffmpeg"], ts.ffmpeg or folder,
               "Reads PC sounds (ffmpeg.exe).", "Lee los sonidos de PC (ffmpeg.exe).",
               {"kind": "folder", "which": "tools_dir"}),
            it("vgaudio", "tools", "convert", st["vgaudio"] and st["vgaudio_toolkit"], ts.vgaudio or folder,
               "Writes Switch sounds (VGAudioCli.exe + VGAudio.dll, Skyrim NX Toolkit build).",
               "Escribe sonidos de Switch (VGAudioCli.exe + VGAudio.dll, versión del Skyrim NX Toolkit).",
               {"kind": "folder", "which": "tools_dir"},
               (["This VGAudio isn't the Toolkit build; Switch sounds need that one.",
                 "Este VGAudio no es la versión del Toolkit; los sonidos de Switch necesitan esa."]
                if st["vgaudio"] and not st["vgaudio_toolkit"] else None)),
            it("nvntexpkg", "tools", "optional", st["sdk"], ts.nvntexpkg or folder,
               "Native Switch textures (NvnTexpkg.exe and its DLLs). Without it, textures stay DDS.",
               "Texturas nativas de Switch (NvnTexpkg.exe y sus DLL). Sin él, las texturas quedan en DDS.",
               {"kind": "folder", "which": "tools_dir"},
               (["Missing DLLs: " + ", ".join(st["nvn_missing"]), "Faltan DLL: " + ", ".join(st["nvn_missing"])]
                if st.get("nvn_missing") else None)),
            it("hbpp", "tools", "optional", st.get("hbpp"), ts.hbpp or folder,
               "Writes behaviors, skeletons and Oldrim animations for Switch (HavokBehaviorPostProcess.exe, "
               "from Bethesda's Creation Kit on Steam).",
               "Escribe comportamientos, esqueletos y animaciones de Oldrim para Switch (HavokBehaviorPostProcess.exe, "
               "del Creation Kit de Bethesda en Steam).",
               {"kind": "folder", "which": "tools_dir"}),
            it("hkxc", "tools", "optional", st.get("hkxc"), ts.hkxc or folder,
               "Reads 64-bit PC behaviors and skeletons (hkxc.exe from serde-hkx, Nexus SE mod 126214). "
               "Works together with HavokBehaviorPostProcess.",
               "Lee comportamientos y esqueletos de PC de 64 bits (hkxc.exe de serde-hkx, mod 126214 de Nexus SE). "
               "Trabaja junto con HavokBehaviorPostProcess.",
               {"kind": "folder", "which": "tools_dir"},
               (["Without HavokBehaviorPostProcess.exe it isn't used.",
                 "Sin HavokBehaviorPostProcess.exe no se usa."] if st.get("hkxc") and not st.get("hbpp") else None)),
            it("nemesis", "tools", "optional", st.get("nemesis"), ts.nemesis or folder,
               "Nemesis Behavior Engine (Nexus SE mod 60033), unpacked in Tools\\Nemesis. Generates the behaviors "
               "for mods with new animations (FNIS lists, Nemesis patches) on a copy of the project.",
               "Nemesis Behavior Engine (mod 60033 de Nexus SE), descomprimido en Tools\\Nemesis. Genera los "
               "comportamientos de los mods con animaciones nuevas (listas FNIS, parches de Nemesis) sobre una copia "
               "del proyecto.",
               {"kind": "folder", "which": "tools_dir"},
               (["Its results are made Switch files with HavokBehaviorPostProcess and hkxc: add those too.",
                 "Sus resultados se pasan a Switch con HavokBehaviorPostProcess y hkxc: agrégalos también."]
                if st.get("nemesis") and not st.get("havok") else None)),
        ]
        inis_dir = Path(self._folder("inis_dir"))
        names = {p.name.lower() for p in inis_dir.iterdir()} if inis_dir.is_dir() else set()
        miss = [n for n in ("Skyrim.ini", "Skyrim_en.ini", "Skyrim_aoc.ccc") if n.lower() not in names]
        items.append(it("inis", "game", "new", "skyrim.ini" in names, inis_dir,
                        "The console's clean inis, for new packs (Skyrim.ini, Skyrim_en.ini, Skyrim_aoc.ccc).",
                        "Las inis limpias de la consola, para packs nuevos (Skyrim.ini, Skyrim_en.ini, Skyrim_aoc.ccc).",
                        {"kind": "folder", "which": "inis_dir"},
                        (["Missing: " + ", ".join(miss), "Faltan: " + ", ".join(miss)] if miss and names else None)))
        vd = self._folder("vanilla_dir")
        items.append(it("vanilla", "game", "optional", _vanilla_status(vd) == "ok", vd,
                        "The game's own BSAs and .esm, so the Doctor can check missing scripts, meshes and textures.",
                        "Los BSA y .esm del juego, para que el Doctor revise scripts, meshes y texturas que faltan.",
                        {"kind": "folder", "which": "vanilla_dir"}))
        us = scan(self._folder("ussep_dir"))
        items.append(it("ussep", "game", "optional", bool(us["variants"]), us["folder"],
                        "KokaNX's USSEP for Switch, to start new packs with it.",
                        "El USSEP de KokaNX para Switch, para empezar packs nuevos con él.",
                        {"kind": "folder", "which": "ussep_dir"}))
        items.append(it("library", "game", "always", True, self._library_root(),
                        "The Library: your packs, mods and converted mods.",
                        "La Biblioteca: tus packs, mods y mods convertidos.",
                        {"kind": "folder", "which": "library_dir"}))
        what = {"sseedit": ("look into and edit plugins; opens on the pack or on a copy.",
                            "revisar y editar plugins; abre sobre el pack o sobre una copia."),
                "zedit": ("edit and merge plugins (opens with its own profile).",
                          "editar y fusionar plugins (abre con su propio perfil)."),
                "nifskope": ("look at meshes (.nif).", "ver meshes (.nif)."),
                "bae": ("open BSAs by hand.", "abrir BSA a mano."),
                "cao": ("optimize textures and meshes on PC.", "optimizar texturas y meshes en el PC.")}
        for t in self.tools_list()["tools"]:
            if t["id"] == "other":
                continue
            en, es = what.get(t["id"], ("external tool.", "herramienta externa."))
            items.append(it(t["id"], "extra", "optional", bool(t["path"]) and Path(t["path"]).is_file(), t["path"],
                            f"{t['name']}: {en}", f"{t['name']}: {es}", {"kind": "tool", "id": t["id"]}))
        _, ml, _ = self._loot_paths()
        items.append(it("loot", "extra", "optional", ml.exists(), ml,
                        "LOOT masterlist, to suggest load order (downloaded from the Load order page).",
                        "Masterlist de LOOT, para sugerir el orden (se descarga desde Orden de carga).",
                        {"kind": "page", "page": "orden"}))
        items.append(it("nexus", "extra", "optional", bool(self._settings.get("nexus_key")), "",
                        "Nexus Mods API key, to download with the site's button and check updates.",
                        "API key de Nexus Mods, para descargar con el botón del sitio y buscar actualizaciones.",
                        {"kind": "page", "page": "ajustes"}))
        from skynx.intake import rar_tool
        rt = rar_tool()
        is7 = bool(rt) and Path(rt[0]).name.lower().startswith("7z")
        items.insert(4, it("rar", "tools", "optional", is7, rt[0] if rt else r"C:\Program Files\7-Zip",
                           "7-Zip, to open .rar downloads.", "7-Zip, para abrir descargas .rar.",
                           None,
                           (["Without 7-Zip, Windows' tar.exe tries to open .rar files; some don't open that way.",
                             "Sin 7-Zip, el tar.exe de Windows intenta abrir los .rar; algunos no abren así."]
                            if rt and not is7 else None)))
        for i in items:
            i["lose"] = list(self.SETUP_LOSE.get(i["id"], ("", "")))
        return {"items": items}

    # what stops working while an item of the setup is missing (en, es)
    SETUP_LOSE = {
        "texconv": ("PC mods with textures can't be converted (one mod, many mods, Join mods), and the texture diet "
                    "can't run on a pack.",
                    "Los mods de PC con texturas no se pueden convertir (un mod, varios mods, Juntar mods), y la dieta "
                    "de texturas no corre sobre un pack."),
        "ffmpeg": ("PC mods with sounds or voices can't be converted.",
                   "Los mods de PC con sonidos o voces no se pueden convertir."),
        "vgaudio": ("PC mods with sounds or voices can't be converted: the Switch sounds can't be written.",
                    "Los mods de PC con sonidos o voces no se pueden convertir: no se pueden escribir los sonidos de Switch."),
        "nvntexpkg": ("Converted textures stay DDS, the PC format the Switch also reads, instead of its native format.",
                      "Las texturas convertidas quedan en DDS, el formato de PC que la Switch también lee, en vez de su "
                      "formato nativo."),
        "hbpp": ("Behavior files, skeletons and Oldrim (32-bit) animations from PC mods are packed as they are, "
                 "and may not work on Switch.",
                 "Los archivos de comportamiento, los esqueletos y las animaciones de Oldrim (32 bits) de mods de PC "
                 "se empacan tal cual, y puede que no funcionen en Switch."),
        "hkxc": ("64-bit PC behavior files and skeletons are packed as they are, and may not work on Switch.",
                 "Los comportamientos y esqueletos de PC de 64 bits se empacan tal cual, y puede que no funcionen "
                 "en Switch."),
        "nemesis": ("Mods with new animations (FNIS or Nemesis) get no generated behaviors: those animations "
                    "don't play in game.",
                    "Los mods con animaciones nuevas (FNIS o Nemesis) quedan sin comportamientos generados: esas "
                    "animaciones no se ven en el juego."),
        "rar": (".rar downloads only open if Windows' tar.exe can read them; otherwise extract them by hand.",
                "Las descargas .rar solo abren si el tar.exe de Windows puede leerlas; si no, hay que extraerlas a mano."),
        "inis": ("You can't start a modpack from scratch. Opening packs and building from another pack still work.",
                 "No puedes empezar un modpack desde cero. Abrir packs y armar desde otro pack siguen funcionando."),
        "vanilla": ("The Doctor can't tell whether the scripts, meshes and textures a plugin needs are there, and "
                    "SSEEdit can't open a pack.",
                    "El Doctor no puede saber si están los scripts, meshes y texturas que pide un plugin, y SSEEdit no "
                    "puede abrir un pack."),
        "ussep": ("New packs start without USSEP.", "Los packs nuevos empiezan sin USSEP."),
        "library": ("", ""),
        "sseedit": ("The \"Open in SSEEdit\" buttons stay off.", "Los botones «Abrir en SSEEdit» quedan apagados."),
        "zedit": ("\"Join plugins\" (a merge) can't run.", "«Juntar plugins» (un merge) no se puede hacer."),
        "nifskope": ("Meshes can't be opened from the app.", "Las meshes no se abren desde la app."),
        "bae": ("BSAs can't be opened by hand from the app (extracting still works).",
                "Los BSA no se abren a mano desde la app (extraerlos sí funciona)."),
        "cao": ("Its button stays off.", "Su botón queda apagado."),
        "loot": ("No \"Suggest order\", and fewer mods get their Nexus page. It downloads itself the first time.",
                 "Sin «Sugerir orden», y menos mods reconocen su página de Nexus. Se descarga sola la primera vez."),
        "nexus": ("No names, versions or update checks from Nexus, and no Mod Manager Download button.",
                  "Sin nombres, versiones ni actualizaciones de Nexus, y sin el botón Mod Manager Download."),
    }

    def first_steps(self) -> dict:
        """Checklist for the welcome page."""
        from skynx.ussep import scan
        ts = self._tools()
        base = Path(self._folder("inis_dir"))
        inis = base.is_dir() and any(p.name.lower() == "skyrim.ini" for p in base.iterdir())
        us = scan(self._folder("ussep_dir"))
        return {"tools": ts.status(), "inis": inis, "inis_dir": str(base),
                "ussep": bool(us["variants"]), "ussep_dir": us["folder"],
                "library": str(self._library_root()), "recent": bool(self._settings.get("recent")),
                "vanilla": _vanilla_status(self._folder("vanilla_dir")) == "ok",
                "vanilla_dir": self._folder("vanilla_dir")}

    # ------------------------------------------------------------ add (intake)
    def intake_detect(self, paths: list) -> dict:
        """What each dropped item is. Loose plugins and their BSAs (picked
        together or not) become one entry per mod."""
        KIND_RANK = ["fomod", "pc-mod", "mixed", "switch-mod", "modpack", "unknown"]

        def one(p, tick):
            from skynx.intake import detect
            try:
                return detect(Path(p), progress=tick).to_dict(self._lang)
            except Exception as e:  # noqa: BLE001
                return {"path": p, "kind": "unknown", "action": None, "supported": False,
                        "summary": self._err(e), "notes": [], "evidence": {}}

        def work(tick, paths):
            from skynx.intake import group_loose
            out = []
            groups = group_loose(paths)
            for i, (main, files) in enumerate(groups):
                tick(Path(main).name, i, len(groups))
                if len(files) <= 1:
                    d = one(main, tick)
                    d["bundle"] = [Path(f).name for f in files] if files and files[0] != main else []
                    out.append(d)
                    continue
                parts = [one(f, tick) for f in files]
                kinds = [x["kind"] for x in parts if x["kind"] in KIND_RANK]
                best = min(kinds, key=KIND_RANK.index) if kinds else "unknown"
                lead = next((x for x in parts if x["kind"] == best and x is not parts[0]), parts[0])
                ev = {"plugins": [], "bsas": [], "bytes": 0}
                for x in parts:
                    e = x.get("evidence") or {}
                    ev["plugins"] += e.get("plugins") or []
                    ev["bsas"] += e.get("bsas") or []
                    ev["bytes"] += e.get("bytes") or 0
                notes = []
                for x in parts:
                    for n in x.get("notes") or []:
                        if n not in notes:
                            notes.append(n)
                out.append({**lead, "path": main, "kind": best,
                            "action": next((x["action"] for x in parts if x["kind"] == best), lead.get("action")),
                            "summary": lead.get("summary"), "notes": notes, "evidence": ev,
                            "bundle": [Path(f).name for f in files]})
            return out
        return self._run("…", work, list(paths or []))

    def precheck(self, path: str) -> dict:
        def work(tick, path):
            from skynx.precheck import precheck
            src, tmp = self._loose(Path(path))
            vanilla = None
            vdir = self._folder("vanilla_dir")
            if vdir and _vanilla_status(vdir) == "ok":
                from skynx.vanilla import game_refs, index
                tick("Vanilla")
                # what the game's own records ask for counts as there: some of it
                # doesn't exist in the game either (vanilla races' .egt)
                vanilla = index(Path(vdir), self._cache_dir()) | game_refs(Path(vdir), self._cache_dir())
            try:
                r = precheck(self._pack, src, progress=tick, vanilla=vanilla, origin=Path(path),
                             cache_dir=self._cache_dir())
            finally:
                if tmp:
                    shutil.rmtree(tmp, ignore_errors=True)
            r["notes"] = [{"level": n["level"], "text": n.get(self._lang, n["en"])} for n in r["notes"]]
            return r
        return self._run("…", work, path)

    # ------------------------------------------------------------ library
    def library_mods(self) -> dict:
        """The Library's mods (Converted first), quickly, for pickers."""
        from skynx.library import list_library
        rows = [r for r in list_library(self._library_root(), health=False)
                if r["kind"] == "mod" and not r.get("missing")]
        rows.sort(key=lambda r: (not r.get("converted"), r["name"].lower()))
        return {"root": str(self._library_root()), "rows": rows}

    def library_list(self) -> dict:
        def work(tick):
            from skynx.library import list_library
            from skynx import project as PJ
            leg = [x for x in PJ.legacy(self._library_root()) if not x.get("done")]
            return {"root": str(self._library_root()), "legacy": len(leg),
                    "rows": list_library(self._library_root(), progress=tick, kinds=("mod",))}
        return self._run("…", work)

    def library_import(self, path: str, kind: str = "") -> dict:
        def work(tick, path, kind):
            from skynx.library import add_external, import_mod, import_pack
            src = Path(path)
            explicit = bool(kind)
            if not kind:
                from skynx.intake import detect
                kind = detect(src, progress=tick, deep=False).kind
            if kind == "modpack":
                if not explicit:
                    raise CV.ConvertError(
                        f"{src.name} is a modpack. Modpacks aren't kept in the Library: start a project with it "
                        "(Home » New project), or bring its mods into the open project.",
                        f"{src.name} es un modpack. Los modpacks no se guardan en la Biblioteca: empieza un proyecto "
                        "con él (Inicio » Nuevo proyecto) o trae sus mods al proyecto abierto.")
                return import_pack(src, self._library_root(), progress=tick)
            if src.is_dir():
                return add_external(self._library_root(), src)
            return import_mod(src, self._library_root(), progress=tick)
        return self._run("…", work, path, kind)

    def library_forget(self, path: str) -> dict:
        """Out of the Library list; copies the Library made are deleted."""
        from skynx.library import remove
        try:
            return remove(self._library_root(), Path(path))
        except Exception as e:  # noqa: BLE001
            return {"ok": False, "error": self._err(e)}

    # ------------------------------------------------------------ bring mods from another pack
    def transfer_list(self, src: str) -> dict:
        def work(tick, src):
            from skynx.transfer import list_pack_mods, units_view
            sp = Pack.open(self._pack_source(src, tick))
            if not sp.data_dir:
                raise CV.ConvertError("That folder isn't a modpack.", "Esa carpeta no es un modpack.")
            return {"src": str(src), "name": Path(src).name, "mode": sp.mode,
                    "units": units_view(list_pack_mods(sp, textures=True, progress=tick), self._lang)}
        return self._run("…", work, src)

    def transfer_plan(self, src: str, ids: list) -> dict:
        def work(tick, src, ids):
            from skynx.transfer import plan_transfer
            if getattr(self, "_transfer", None):
                self._transfer.cleanup()
            self._transfer = plan_transfer(Pack.open(self._pack_source(src, tick)), self._pack, list(ids),
                                           progress=tick)
            return self._transfer.to_dict(self._lang)
        return self._run("…", work, src, ids)

    def transfer_apply(self) -> dict:
        def work(tick):
            from skynx.transfer import apply_transfer
            plan = getattr(self, "_transfer", None)
            if plan and Path(plan.dst.root).resolve() != Path(self._pack.root).resolve():
                plan.cleanup()
                self._transfer = None
                plan = None
            if not plan:
                raise CV.ConvertError("Plan the transfer again.", "Vuelve a preparar la copia.")
            try:
                out = apply_transfer(plan, progress=tick)
            finally:
                plan.cleanup()
                self._transfer = None
            self._pack.reload()
            out["safe_renamed"] = self._safe_names(out.get("list_added") or [], tick)
            self._result = self._audit(False)
            out["notes"] = [n[1] if (isinstance(n, (list, tuple)) and self._lang == "es") else
                            (n[0] if isinstance(n, (list, tuple)) else n) for n in out.get("notes", [])]
            return {"result": out, **self._audit_out()}
        return self._run("…", work)

    def _safe_names(self, names: list, tick) -> list:
        """Give plugins just brought from another pack a name Google Drive
        won't damage (full rename, one undoable step each)."""
        from skynx.bsafix import safe_rename
        from skynx.rename import safe_name
        done = []
        for name in names:
            name = name.lstrip("#")
            new = safe_name(name)
            if new == name or self._pack.plugins.get(name.lower()) is None:
                continue
            if (self._pack.data_dir / new).exists():
                continue
            tick(name)
            try:
                with Transaction(self._pack.root, f"Safe name: {name} -> {new}") as tx:
                    safe_rename(self._pack, name, new, tx)
                done.append([name, new])
            except Exception:  # noqa: BLE001
                traceback.print_exc()
            self._pack.reload()
        return done

    # ------------------------------------------------------------ LOOT
    def _loot_view(self, tick, fetch: bool = True) -> dict:
        from skynx import loot
        cache, ml_path, ul_path = self._loot_paths()
        tick("masterlist")
        ml = loot.load_masterlist(loot.fetch_masterlist(cache) if fetch else ml_path)
        userlist = loot.load_userlist(ul_path)
        sg = loot.suggest(self._pack, ml, aliases=self._aliases(), userlist=userlist)
        self._loot_base = (str(self._pack.root), list(self._pack.list_entries))
        es = self._lang == "es"
        pick = (lambda t: t[1] if es else t[0])
        self._loot = sg
        chosen = {v.get("name") or k: {"group": v.get("group") or "", "after": v.get("after") or []}
                  for k, v in (userlist.get("plugins") or {}).items()}
        in_pack = {n.lower() for n in self._pack.list_entries}
        return {"changed": sg.changed, "order": sg.order,
                "moves": [{"name": m.name, "from": m.old_index, "to": m.new_index,
                           "why": pick(loot.describe(m))} for m in sg.moves],
                "warnings": [pick(w) for w in sg.warnings],
                "notes": {k: [{"level": n.level, "text": (n.es or n.en) if es else n.en}
                              for n in v] for k, v in sg.notes.items()},
                "groups": sg.groups,
                "merges": sg.merges, "dummies": sg.dummies,
                "duplicates": [list(d) for d in sg.duplicates],
                "unknown": [{"name": u["name"], "guess": u["guess"], "why": pick(u["why"]),
                             "masters": u["masters"]} for u in sg.unknown],
                "chosen": {k: v for k, v in chosen.items() if k.lower() in in_pack},
                "friendly": [{"group": g["group"], "label": g["es" if es else "en"],
                              "help": g["es_help" if es else "en_help"]} for g in loot.FRIENDLY_GROUPS],
                "all_groups": loot.all_groups(ml),
                "age_days": round(loot.masterlist_age_days(ml_path), 1) if ml_path.exists() else None}

    def loot_suggest(self) -> dict:
        return self._run("…", lambda tick: self._loot_view(tick, fetch=True))

    def loot_classify(self, choices: dict) -> dict:
        """choices: {plugin name: {"group": g, "after": [names]}}; an empty
        group clears that plugin's choice. Saved for every pack."""
        def work(tick, choices):
            from skynx import loot
            _c, _m, ul_path = self._loot_paths()
            data = loot.load_userlist(ul_path)
            for name, ch in (choices or {}).items():
                data = loot.userlist_set(data, name, group=(ch or {}).get("group") or "",
                                         after=(ch or {}).get("after"))
            loot.save_userlist(ul_path, data)
            view = self._loot_view(tick, fetch=False)
            self._result = self._audit(False)
            view.update(self._audit_out())
            return view
        return self._run("…", work, choices)

    def loot_apply(self) -> dict:
        sg = getattr(self, "_loot", None)
        if not sg:
            return {"ok": False, "error": "Ask for the suggestion again" if self._lang == "en"
                    else "Vuelve a pedir la sugerencia"}
        self._loot = None
        base = getattr(self, "_loot_base", None)
        if not base or base != (str(self._pack.root), list(self._pack.list_entries)):
            return {"ok": False, "error": "The load list changed since the suggestion. Ask for it again."
                    if self._lang == "en" else "La lista de carga cambió desde la sugerencia. Vuelve a pedirla."}
        return self.save_load_order(sg.order)

    # ------------------------------------------------------------ conflicts
    def conflicts(self) -> dict:
        def work(tick):
            from skynx.conflicts import find_conflicts
            return find_conflicts(self._pack, progress=tick, lang="en").to_dict()
        return self._run("…", work)

    # ------------------------------------------------------------ load order
    def load_order(self) -> dict:
        p = self._pack
        order = p.load_order()
        pos = {n.lower(): i for i, (n, _) in enumerate(order)}
        es = self._lang == "es"
        rows = []
        for i, (name, src) in enumerate(order):
            h = p.plugins.get(name.lower())
            row = {"name": name, "source": src, "exists": bool(h) or src == "juego"
                   or (p.mode == "AE" and p.is_cc(name)),
                   "cc": p.mode == "AE" and p.is_cc(name), "masters": [], "problems": [],
                   "records": None, "bsas": []}
            if row["cc"]:
                from skynx.ccinfo import info as cc_info
                ci = cc_info(name.lstrip("#"))
                if ci:
                    row["title"] = ci["title"]
                    row["desc"] = ci["desc"][1 if es else 0]
            if h:
                row["masters"] = h.masters
                row["records"] = h.num_records
                row["light"] = h.is_light_flag or h.extension == ".esl"
                row["bsas"] = [b.name for b in p.bsas_for_plugin(name)]
                for m in h.masters:
                    if m.lower() not in pos:
                        row["problems"].append(f"Falta el master {m}" if es else f"Missing master {m}")
                    elif pos[m.lower()] > i:
                        row["problems"].append(f"{m} debe ir antes" if es else f"{m} must come first")
            rows.append(row)
        return {"rows": rows, "limit": K.CCC_BYTE_LIMIT if p.mode == "AE" else None,
                "bytes": p.list_bytes,
                "list": p.list_path.name if p.list_path else None}

    def save_load_order(self, names: list[str]) -> dict:
        p = self._pack
        path = p.list_path
        raw = path.read_bytes()
        cur = parse_ccc(raw).entries
        if sorted(x.lower() for x in names) != sorted(x.lower() for x in cur):
            return {"ok": False, "error": "The new list doesn't have the same plugins"
                    if self._lang == "en" else "La lista nueva no tiene los mismos plugins"}
        with Transaction(p.root, "Reorder load list") as tx:
            tx.write_bytes(path, reorder(raw, names))
        p.reload()
        self._result = self._audit(False)
        return {"ok": True, **self._audit_out()}

    # ------------------------------------------------------------ history
    _HIST_ES = [("Undo: ", "Deshacer: "), ("Add mod: ", "Agregar mod: "), ("Remove mod: ", "Quitar mod: "),
                ("Goes: ", "Va: "), ("Doesn't go: ", "No va: "), ("Safe name: ", "Nombre seguro: "),
                ("Rename ", "Renombrar "), ("Join BSAs", "Juntar BSA"), ("Bring the merged plugin", "Traer el plugin fusionado"),
                ("Changes from SSEEdit", "Cambios desde SSEEdit"), ("Enable ", "Activar "), ("Disable ", "Desactivar "),
                ("Reorder load list", "Reordenar la lista de carga"),
                ("Add Creation Club masters for USSEP", "Agregar masters del Creation Club para USSEP"),
                ("Changes made in the project folder", "Cambios hechos en la carpeta del proyecto")]

    def _hist_title(self, title: str, detail: str = "") -> str:
        """History titles are stored in English; show them in the app's language."""
        import ast
        from skynx import i18n
        if detail.startswith("{") and "label_key" in detail:
            try:
                fx = ast.literal_eval(detail)
                return i18n.label(fx["label_key"], self._lang, **(fx.get("label_args") or {}))
            except Exception:  # noqa: BLE001
                pass
        if self._lang != "es":
            return title
        if title.startswith("Undo: "):
            return "Deshacer: " + self._hist_title(title[6:])
        m = re.match(r"Extract (.+) into Data$", title)
        if m:
            return f"Extraer {m.group(1)} en Data"
        m = re.match(r"Bring (\d+) mods? from (.+)$", title)
        if m:
            return f"Traer {m.group(1)} mod{'s' if m.group(1) != '1' else ''} de {m.group(2)}"
        for en, es in self._HIST_ES:
            if title.startswith(en):
                return es + title[len(en):]
        return title

    def history(self) -> list[dict]:
        if not self._pack:
            return []
        out = list_history(self._pack.root)        # newest first
        raws = [e.get("title") or "" for e in out]
        shown = [self._hist_title(r, e.get("detail") or "") for r, e in zip(raws, out)]
        for i, e in enumerate(out):
            r = raws[i]
            if r.startswith("Undo: "):
                # the entry it undid: the closest older one with that title
                j = next((k for k in range(i + 1, len(out)) if raws[k] == r[6:]), None)
                if j is not None:
                    e["title"] = ("Deshacer: " if self._lang == "es" else "Undo: ") + shown[j]
                    continue
            e["title"] = shown[i]
        return out

    def undo(self, entry_id: str) -> dict:
        try:
            files = undo(self._pack.root, entry_id)
            self._pack.reload()
            self._result = self._audit(False)
            return {"ok": True, "files": files, **self._audit_out()}
        except Exception as e:  # noqa: BLE001
            return {"ok": False, "error": self._err(e)}

    # ------------------------------------------------------------ SD
    def _build_for_sd(self, tick) -> dict | None:
        if not (self._pack and self._pack.project):
            return None
        from skynx import project as PJ
        return PJ.build(self._pack, progress=lambda f, i=0, n=0: tick(f, i, n))

    def sd_plan(self, sd_root: str) -> dict:
        def work(tick, sd):
            from skynx.deploy import plan_sync
            built = self._build_for_sd(tick)
            out = plan_sync(self._pack.root, Path(sd), progress=tick).to_dict()
            if built:
                out["built"] = built
            if self._pack.project:
                from skynx.console import console_changes
                try:
                    out["console"] = console_changes(self._pack, Path(sd))
                except Exception:  # noqa: BLE001   only a notice
                    out["console"] = None
            return out
        return self._run("…", work, sd_root)

    def sd_use_console(self, sd_root: str) -> dict:
        """Bring the on/off choices made on the console with SkyNX Mods into the project."""
        def work(tick, sd):
            from skynx.console import use_console
            with Transaction(self._pack.root, "Use the console's choices") as tx:
                ch = use_console(self._pack, Path(sd), tx)
            self._pack.reload()
            self._result = self._audit(False)
            return {"changes": ch, **self._audit_out()}
        return self._run("…", work, sd_root)

    def deploy(self, sd_root: str, mode: str = "sync") -> dict:
        def work(tick, sd, mode):
            self._build_for_sd(tick)
            out = deploy(self._pack.root, Path(sd), tick, mode=mode)
            from skynx.console import write_sd_files
            try:
                vd = self._folder("vanilla_dir")
                out["console_files"] = write_sd_files(self._pack, Path(sd), self._console_extra(), tick,
                                                      vd if vd and Path(vd).is_dir() else None)
            except OSError as e:
                out["console_error"] = str(e)
            if self._pack.project:
                from skynx import project as PJ
                PJ.write_info(self._pack.root, last_sd=time.strftime("%Y-%m-%d %H:%M:%S"), last_sd_path=str(sd))
            return out
        return self._run("…", work, sd_root, mode)

    def import_sd(self, sd_root: str, dest: str) -> dict:
        def work(tick, sd, dest):
            self._drop_analysis()
            out = import_from_sd(Path(sd), Path(dest), tick)
            self._pack = Pack.open(Path(dest))
            self._remember(dest)
            self._result = self._audit(True, tick)
            return {**out, **self._audit_out()}
        return self._run("…", work, sd_root, dest)
