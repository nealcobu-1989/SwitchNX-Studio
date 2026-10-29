"""Entry point. Opens the app in its own window (Edge WebView2 on Windows).

If the window can't be created (WebView2 missing), it falls back to the
local server and opens the default browser. `--server` forces that mode.
"""
from __future__ import annotations

import sys
from pathlib import Path

HERE = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parent))
if not (HERE / "web").exists():
    HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
sys.path.insert(0, str(HERE))

from api import Api  # noqa: E402

TITLE = "SwitchNX Studio"


def run_server(api: Api, open_browser: bool = True, port: int = 8765):
    from server import serve
    serve(api, HERE / "web", port=port, open_browser=open_browser)


def single_instance(api: Api, holder: dict):
    """Only one copy runs. A second launch (for example Windows opening an
    nxm:// link from Nexus' Mod Manager Download button) hands its link to the
    running copy and exits. Returns False when this process should exit."""
    url = next((a for a in sys.argv[1:] if a.lower().startswith("nxm://")), None)
    try:
        from api import settings_path
        from ipc import claim

        def on_message(msg):
            import threading
            threading.Thread(target=deliver, args=(msg,), daemon=True).start()

        def deliver(msg):
            # off the IPC thread, so the second launch gets its answer at once
            if msg.get("nxm"):
                api.nexus_receive(msg["nxm"])
            win = holder.get("win")
            if win is not None:
                for fn in ("restore", "show"):
                    try:
                        getattr(win, fn)()
                    except Exception:  # noqa: BLE001
                        pass
        server = claim(settings_path().parent / "ipc.token", on_message, url)
    except Exception as e:  # noqa: BLE001
        print(f"Single-instance check skipped: {e}")
        server = True
    if server is None:
        return False
    if url:
        api._pending_nxm = [url]
    return True


def main():
    api = Api()
    holder: dict = {}
    if "--no-single" not in sys.argv and not single_instance(api, holder):
        return
    if "--server" in sys.argv:
        run_server(api, open_browser="--no-browser" not in sys.argv)
        return
    try:
        import webview  # type: ignore
        win = webview.create_window(TITLE, str(HERE / "web" / "index.html"), js_api=api,
                                    width=1320, height=860, min_size=(1100, 700),
                                    background_color="#efe4cc")
        api._window = win
        holder["win"] = win

        def on_closing():
            # A job half-way (adding a mod, copying to the SD) is rolled back the
            # next time the pack is opened, but it's better not to cut it.
            if not api.busy:
                return True
            msg = ("A task is still running. If you close now it will be cut short and rolled "
                   "back the next time you open the modpack. Close anyway?"
                   if api._lang == "en" else
                   "Hay una tarea en curso. Si cierras ahora se corta y se revierte la próxima vez "
                   "que abras el modpack. ¿Cerrar igual?")
            try:
                return bool(win.create_confirmation_dialog(TITLE, msg))
            except Exception:  # noqa: BLE001
                return False
        try:
            win.events.closing += on_closing
        except Exception:  # noqa: BLE001
            pass

        def wire_drop():
            # Files dropped on the window arrive here with their full paths
            # (pywebview 5 DOM events); the page gets them through onDroppedPaths.
            import json
            try:
                from webview.dom import DOMEventHandler  # type: ignore

                def on_drop(e):
                    box = e.get("dataTransfer") or e.get("domTransfer") or {}
                    paths = []
                    for f in box.get("files", []) or []:
                        p = f.get("pywebviewFullPath") if isinstance(f, dict) else f
                        if p:
                            paths.append(p)
                    if paths:
                        win.evaluate_js(f"window.onDroppedPaths && window.onDroppedPaths({json.dumps(paths)})")
                doc = win.dom.document
                doc.events.dragover += DOMEventHandler(lambda e: None, True, True)
                doc.events.drop += DOMEventHandler(on_drop, True, True)
            except Exception as e:  # noqa: BLE001
                print(f"Drag and drop not available: {e}")
        win.events.loaded += wire_drop
        webview.start(http_server=True)
    except Exception as e:  # noqa: BLE001
        print(f"Could not open the app window ({e}); opening the browser instead.")
        run_server(api)


if __name__ == "__main__":
    main()
