"""The one .txt file next to the .exe (R8, R13).

Format is `key = value`, one per line. `#` starts a comment. Missing, empty or
malformed files never crash the app: every key falls back to a default and the
admin window refuses to open when credentials are absent (R8 edge cases).
"""
import logging
import os
import tempfile

from . import paths

log = logging.getLogger(__name__)

DEFAULTS = {
    "admin_username": "",
    "admin_password": "",
    "sharepoint_url": "",
    "departments": "",
}

TEMPLATE = """\
# Countdown configuration. Keep this file next to Countdown.exe.
# Anyone who can read this folder can read these credentials (see spec Risks).

admin_username = admin
admin_password = change-me

# Anonymous SharePoint direct link to the RO table (.xlsx or .csv).
sharepoint_url =

# Closed list offered on the first run window (R2). Comma separated.
# Leave blank to take the list from the table's department column instead.
departments =
"""


class Config(dict):
    @property
    def admin_username(self) -> str:
        return self.get("admin_username", "").strip()

    @property
    def admin_password(self) -> str:
        return self.get("admin_password", "")

    @property
    def sharepoint_url(self) -> str:
        return self.get("sharepoint_url", "").strip()

    @property
    def departments(self) -> list:
        raw = self.get("departments", "")
        return [p.strip() for p in raw.split(",") if p.strip()]

    @property
    def has_admin_credentials(self) -> bool:
        return bool(self.admin_username and self.admin_password)


def load() -> Config:
    cfg = Config(DEFAULTS)
    path = paths.config_path()
    try:
        with open(path, "r", encoding="utf-8-sig", errors="replace") as fh:
            text = fh.read()
    except OSError:
        return cfg
    for line in text.splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        key = key.strip().lower().replace(" ", "_")
        if key in DEFAULTS:
            cfg[key] = value.strip()
    return cfg


def save_value(key: str, value: str) -> bool:
    """Write one key back to countdown.txt, leaving the rest of the file alone.

    The file is the admin's, with their comments and their ordering, and it also
    holds the credentials. Only the one line is rewritten; an absent key is
    appended at the end.
    """
    key = key.strip().lower()
    if key not in DEFAULTS:
        return False
    ensure_exists()
    path = paths.config_path()
    try:
        with open(path, "r", encoding="utf-8-sig", errors="replace") as fh:
            lines = fh.read().splitlines()
    except OSError:
        lines = []

    replaced = False
    for index, line in enumerate(lines):
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or "=" not in stripped:
            continue
        name = stripped.partition("=")[0].strip().lower().replace(" ", "_")
        if name == key:
            lines[index] = f"{key} = {value}"
            replaced = True
            break
    if not replaced:
        lines.append(f"{key} = {value}")

    target = path
    fd, tmp = tempfile.mkstemp(dir=os.path.dirname(target) or ".", suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            fh.write("\n".join(lines) + "\n")
        os.replace(tmp, target)
        return True
    except OSError as exc:
        log.warning("could not write %s: %s", target, exc)
        try:
            os.unlink(tmp)
        except OSError:
            pass
        return False


def ensure_exists() -> None:
    """Write the template on first run if the file is not there at all."""
    path = paths.config_path()
    if os.path.exists(path):
        return
    try:
        with open(path, "w", encoding="utf-8") as fh:
            fh.write(TEMPLATE)
    except OSError:
        pass
