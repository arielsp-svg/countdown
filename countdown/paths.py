"""Where the app's files live.

Everything the app writes sits in the folder the .exe is in. Nothing is written
anywhere else: no %APPDATA%, no registry beyond the single startup value of R1,
no temporary folder. Copy the folder and the whole thing moves with it.

R13 asks for one .exe plus one .txt. The spec's own Open Questions note that
this leaves persisted state homeless, so the folder also comes to hold a state
file and a log.

The state and the log are named per Windows user. R3 calls out a second user
signing in on the same machine, and a single shared state file would hand him
the first user's name, personal number, department, snoozes and alert history.
Per user files keep the whole lot in the one folder without mixing people up.

Setting COUNTDOWN_HOME points all of this somewhere else, which is how the app
is run and reset during testing. Nothing on a delivered machine sets it.
"""
import os
import re
import sys

FALLBACK_USER = "user"


def home_override():
    """COUNTDOWN_HOME, when set, stands in for the .exe's folder."""
    home = os.environ.get("COUNTDOWN_HOME")
    if not home:
        return None
    home = os.path.abspath(os.path.expanduser(home))
    os.makedirs(home, exist_ok=True)
    return home


def app_dir() -> str:
    """Folder the .exe sits in (or the source root when run from Python)."""
    override = home_override()
    if override:
        return override
    if getattr(sys, "frozen", False):
        return os.path.dirname(os.path.abspath(sys.executable))
    return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def exe_path() -> str:
    if getattr(sys, "frozen", False):
        return os.path.abspath(sys.executable)
    return os.path.abspath(sys.argv[0])


def user_slug() -> str:
    """A filename safe form of the logon name, for naming this user's files.

    `iaf\\8123456` becomes `8123456`, which is the personal number R3 works in.
    """
    raw = os.environ.get("USERNAME") or os.environ.get("USER") or ""
    slug = re.sub(r"[^A-Za-z0-9._-]", "_", raw.strip())
    return slug[:40] or FALLBACK_USER


def config_path() -> str:
    return os.path.join(app_dir(), "countdown.txt")


def state_dir() -> str:
    return app_dir()


def state_path() -> str:
    return os.path.join(state_dir(), f"countdown-state-{user_slug()}.json")


def log_path() -> str:
    return os.path.join(state_dir(), f"countdown-{user_slug()}.log")


def lock_path() -> str:
    return os.path.join(state_dir(), f"countdown-{user_slug()}.lock")


def writable() -> bool:
    """Whether the folder the .exe is in can actually be written to.

    A folder under Program Files, or a read only share, cannot hold the state.
    The caller says so plainly rather than failing silently later.
    """
    probe = os.path.join(app_dir(), f".countdown-write-test-{os.getpid()}")
    try:
        with open(probe, "w", encoding="utf-8") as fh:
            fh.write("")
        os.unlink(probe)
        return True
    except OSError:
        return False
