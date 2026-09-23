"""Where the app's files live.

R13 says one .exe plus one .txt in the same folder. The spec's own Open
Questions note that this leaves persisted state homeless, so state goes to
%APPDATA%\\Countdown\\state.json and the delivered folder stays as specified.
"""
import os
import sys


def app_dir() -> str:
    """Folder the .exe sits in (or the source root when run from Python)."""
    if getattr(sys, "frozen", False):
        return os.path.dirname(os.path.abspath(sys.executable))
    return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def exe_path() -> str:
    if getattr(sys, "frozen", False):
        return os.path.abspath(sys.executable)
    return os.path.abspath(sys.argv[0])


def config_path() -> str:
    return os.path.join(app_dir(), "countdown.txt")


def state_dir() -> str:
    base = os.environ.get("APPDATA") or os.path.expanduser("~")
    d = os.path.join(base, "Countdown")
    os.makedirs(d, exist_ok=True)
    return d


def state_path() -> str:
    return os.path.join(state_dir(), "state.json")


def log_path() -> str:
    return os.path.join(state_dir(), "countdown.log")


def lock_path() -> str:
    return os.path.join(state_dir(), "countdown.lock")
