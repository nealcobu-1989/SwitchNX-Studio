"""Registers SwitchNX Studio as the Windows handler for nxm:// links (current user only).

Everything lives under ``HKEY_CURRENT_USER\\Software\\Classes\\nxm``::

    nxm                     (default) = "URL:NXM Protocol", "URL Protocol" = ""
                            "SwitchNXPrevious" = command of the handler we replaced
                            "SwitchNXCommand"  = the command we wrote
    nxm\\shell\\open\\command (default) = '"...\\SwitchNX Studio.exe" "%1"'

Vortex and Mod Organizer 2 usually own nxm. Before overwriting, the previous
command is kept in ``SwitchNXPrevious`` so ``unregister`` can put it back; if
there was none, ``unregister`` removes the key (Windows then falls back to a
machine-wide handler in HKLM, if any). Nothing outside HKCU is written.

``winreg`` can be injected so this is testable off Windows.
"""
from __future__ import annotations

import os
import re

ROOT_PATH = r"Software\Classes\nxm"
CMD_PATH = ROOT_PATH + r"\shell\open\command"
PREV_VALUE = "SwitchNXPrevious"
OURS_VALUE = "SwitchNXCommand"
EXE_NAMES = ("switchnx studio.exe", "switchnx-studio.exe", "switchnxstudio.exe")


def _wr(winreg):
    if winreg is not None:
        return winreg
    import winreg as real  # type: ignore  # Windows only
    return real


def _read(wr, root, path: str, name: str = ""):
    try:
        k = wr.OpenKey(root, path, 0, wr.KEY_READ)
    except OSError:
        return None
    try:
        return wr.QueryValueEx(k, name)[0]
    except OSError:
        return None
    finally:
        wr.CloseKey(k)


def _write(wr, path: str, name: str, value: str):
    k = wr.CreateKeyEx(wr.HKEY_CURRENT_USER, path, 0, wr.KEY_ALL_ACCESS)
    try:
        wr.SetValueEx(k, name, 0, wr.REG_SZ, value)
    finally:
        wr.CloseKey(k)


def _delete_value(wr, path: str, name: str):
    try:
        k = wr.OpenKey(wr.HKEY_CURRENT_USER, path, 0, wr.KEY_ALL_ACCESS)
    except OSError:
        return
    try:
        wr.DeleteValue(k, name)
    except OSError:
        pass
    finally:
        wr.CloseKey(k)


def _delete_tree(wr, path: str):
    try:
        k = wr.OpenKey(wr.HKEY_CURRENT_USER, path, 0, wr.KEY_ALL_ACCESS)
    except OSError:
        return
    try:
        subs = []
        i = 0
        while True:
            try:
                subs.append(wr.EnumKey(k, i))
            except OSError:
                break
            i += 1
    finally:
        wr.CloseKey(k)
    for s in subs:
        _delete_tree(wr, path + "\\" + s)
    try:
        wr.DeleteKey(wr.HKEY_CURRENT_USER, path)
    except OSError:
        pass


def _split_command(cmd: str) -> list[str]:
    """Windows-style split: quoted chunks or runs without spaces."""
    return [a or b for a, b in re.findall(r'"([^"]*)"|(\S+)', cmd or "")]


def is_ours(command_or_exe: str | None) -> bool:
    """True when a command line (or an exe path) launches SwitchNX Studio."""
    if not command_or_exe:
        return False
    parts = _split_command(command_or_exe) or [command_or_exe]
    exe = os.path.basename(parts[0].replace("\\", "/")).lower()
    if exe in EXE_NAMES:
        return True
    for a in parts[1:3]:
        norm = a.replace("\\", "/").lower()
        if norm.endswith("/app/main.py") or norm == "app/main.py":
            return True
    return False


def default_command(frozen: bool, exe: str, script: str) -> str:
    """Command for the registry. Frozen: ``"exe" "%1"``; from source: ``"python" "main.py" "%1"``
    (pythonw.exe is preferred when it sits next to python.exe, so no console flashes)."""
    if frozen:
        return f'"{exe}" "%1"'
    py = exe
    base = os.path.basename(exe.replace("\\", "/")).lower()
    if base == "python.exe":
        cand = exe[: len(exe) - len("python.exe")] + "pythonw.exe"
        if os.path.exists(cand):
            py = cand
    return f'"{py}" "{script}" "%1"'


def current_handler(winreg=None) -> str | None:
    """The command Windows will run for nxm:// (HKCU first, then the merged HKCR view)."""
    wr = _wr(winreg)
    cmd = _read(wr, wr.HKEY_CURRENT_USER, CMD_PATH)
    if cmd:
        return cmd
    hkcr = getattr(wr, "HKEY_CLASSES_ROOT", None)
    if hkcr is not None:
        return _read(wr, hkcr, r"nxm\shell\open\command") or None
    return None


def register(command: str, winreg=None) -> dict:
    """Makes ``command`` the nxm:// handler. Returns ``{command, previous, changed}``
    where ``previous`` is the handler that will come back on ``unregister``."""
    if not command or "%1" not in command:
        raise ValueError("the command must contain \"%1\"")
    wr = _wr(winreg)
    hkcu = wr.HKEY_CURRENT_USER
    existing = _read(wr, hkcu, CMD_PATH)
    saved = _read(wr, hkcu, ROOT_PATH, PREV_VALUE)
    ours_before = _read(wr, hkcu, ROOT_PATH, OURS_VALUE)
    someone_else = bool(existing) and existing != ours_before and not is_ours(existing)
    if someone_else:
        _write(wr, ROOT_PATH, PREV_VALUE, existing)
        saved = existing
    changed = existing != command
    _write(wr, ROOT_PATH, "", "URL:NXM Protocol")
    _write(wr, ROOT_PATH, "URL Protocol", "")
    _write(wr, ROOT_PATH, OURS_VALUE, command)
    _write(wr, CMD_PATH, "", command)
    return {"command": command, "previous": saved or None, "changed": changed}


def unregister(winreg=None) -> dict:
    """Gives nxm:// back. Returns ``{restored, removed}``: ``restored`` is the command
    put back (or None), ``removed`` is True when our key was deleted."""
    wr = _wr(winreg)
    hkcu = wr.HKEY_CURRENT_USER
    existing = _read(wr, hkcu, CMD_PATH)
    ours = _read(wr, hkcu, ROOT_PATH, OURS_VALUE)
    prev = _read(wr, hkcu, ROOT_PATH, PREV_VALUE)
    if existing and existing != ours and not is_ours(existing):
        # someone else took nxm after us: leave theirs, just drop our notes
        _delete_value(wr, ROOT_PATH, OURS_VALUE)
        _delete_value(wr, ROOT_PATH, PREV_VALUE)
        return {"restored": None, "removed": False}
    if prev:
        _write(wr, CMD_PATH, "", prev)
        _delete_value(wr, ROOT_PATH, OURS_VALUE)
        _delete_value(wr, ROOT_PATH, PREV_VALUE)
        return {"restored": prev, "removed": False}
    if existing or ours:
        _delete_tree(wr, ROOT_PATH)
        return {"restored": None, "removed": True}
    return {"restored": None, "removed": False}


def status(command: str | None = None, winreg=None) -> dict:
    """For the Settings screen: ``{handler, ours, previous}``."""
    wr = _wr(winreg)
    h = current_handler(wr)
    ours = bool(h) and (h == command or is_ours(h) or
                        h == _read(wr, wr.HKEY_CURRENT_USER, ROOT_PATH, OURS_VALUE))
    return {"handler": h, "ours": ours,
            "previous": _read(wr, wr.HKEY_CURRENT_USER, ROOT_PATH, PREV_VALUE)}
