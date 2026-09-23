"""The one .txt file next to the .exe (R8, R13).

Format is `key = value`, one per line. `#` starts a comment. Missing, empty or
malformed files never crash the app: every key falls back to a default and the
admin window refuses to open when credentials are absent (R8 edge cases).
"""
import os

from . import paths

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
