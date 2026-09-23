"""Register the app to run at every Windows startup (R1).

HKCU is used rather than HKLM: it needs no elevation, and the app is per user
by design. The value is rewritten on every launch, so moving the folder or
copying the .exe to a second machine repairs the registration by itself.
"""
import logging
import sys

log = logging.getLogger(__name__)

RUN_KEY = r"Software\Microsoft\Windows\CurrentVersion\Run"
VALUE_NAME = "Countdown"


def is_windows() -> bool:
    return sys.platform.startswith("win")


def register(exe_path: str) -> bool:
    """True when the Run value now points at this .exe."""
    if not is_windows():
        log.info("startup registration skipped: not Windows")
        return False
    try:
        import winreg
    except ImportError:
        return False
    command = f'"{exe_path}"'
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, RUN_KEY, 0,
                            winreg.KEY_READ | winreg.KEY_WRITE) as key:
            try:
                current, _ = winreg.QueryValueEx(key, VALUE_NAME)
                if current == command:
                    return True
            except FileNotFoundError:
                pass
            winreg.SetValueEx(key, VALUE_NAME, 0, winreg.REG_SZ, command)
        log.info("registered for startup: %s", command)
        return True
    except OSError as exc:
        # Policy or antivirus can deny this key (R1 edge case). The app still
        # runs for this session; it simply will not come back after a reboot.
        log.warning("could not register for startup: %s", exc)
        return False


def is_registered(exe_path: str) -> bool:
    if not is_windows():
        return False
    try:
        import winreg
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, RUN_KEY) as key:
            current, _ = winreg.QueryValueEx(key, VALUE_NAME)
        return current.strip('"') == exe_path
    except (ImportError, OSError):
        return False
