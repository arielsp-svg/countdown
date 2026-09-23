"""Persisted state: identity, admin tiers, per system alert history.

Lives in %APPDATA%\\Countdown\\state.json (see paths.py for why).
"""
import json
import os
import tempfile
import threading
from datetime import date, datetime

from . import paths

# R7 defaults: 12 months / monthly, 6 months / weekly.
DEFAULT_TIERS = [
    {"name": "wide", "months": 12, "every_days": 30},
    {"name": "tight", "months": 6, "every_days": 7},
]

# Snooze ceiling. The spec leaves this open; without a ceiling a user can push a
# system past its RO date one snooze at a time with nobody aware.
MAX_SNOOZE_DAYS = 90
MAX_SNOOZES_PER_SYSTEM = 3

_lock = threading.Lock()

_DEFAULT = {
    "version": 1,
    "first_run_complete": False,
    "name": "",
    "personal_number": "",
    "personal_number_typed": "",
    "department": "",
    "tiers": DEFAULT_TIERS,
    "last_read": None,        # ISO timestamp of the last successful table read
    "systems": {},            # key -> {last_alert, snooze_until, snooze_count, ...}
    "departments_seen": [],   # department values observed in the table
    "skipped_rows": [],       # rows whose RO date cell was not a date
}


def _default():
    return json.loads(json.dumps(_DEFAULT))


class State:
    def __init__(self, data=None):
        self.data = data if data is not None else _default()

    # --- identity (R2, R3) -------------------------------------------------
    @property
    def first_run_complete(self) -> bool:
        return bool(self.data.get("first_run_complete"))

    @property
    def department(self) -> str:
        return self.data.get("department", "")

    @property
    def personal_number(self) -> str:
        return self.data.get("personal_number", "")

    def set_identity(self, name, personal_number, department):
        self.data["name"] = name
        self.data["personal_number"] = personal_number
        self.data["personal_number_typed"] = personal_number
        self.data["department"] = department
        self.data["first_run_complete"] = True

    # --- admin tiers (R7) --------------------------------------------------
    @property
    def tiers(self) -> list:
        tiers = self.data.get("tiers") or DEFAULT_TIERS
        # Tightest threshold last, so evaluation can let the tighter tier win.
        return sorted(tiers, key=lambda t: -int(t["months"]))

    def set_tiers(self, tiers):
        self.data["tiers"] = tiers

    # --- table read cadence (R4) -------------------------------------------
    @property
    def last_read(self):
        raw = self.data.get("last_read")
        if not raw:
            return None
        try:
            return datetime.fromisoformat(raw)
        except ValueError:
            return None

    def mark_read(self, when=None):
        self.data["last_read"] = (when or datetime.now()).isoformat(timespec="seconds")

    # --- per system record -------------------------------------------------
    def system(self, key) -> dict:
        return self.data.setdefault("systems", {}).setdefault(
            key, {"last_alert": None, "snooze_until": None, "snooze_count": 0}
        )

    def last_alert(self, key):
        raw = self.system(key).get("last_alert")
        if not raw:
            return None
        try:
            return date.fromisoformat(raw)
        except ValueError:
            return None

    def mark_alerted(self, key, when=None):
        self.system(key)["last_alert"] = (when or date.today()).isoformat()

    def snooze_until(self, key):
        raw = self.system(key).get("snooze_until")
        if not raw:
            return None
        try:
            return date.fromisoformat(raw)
        except ValueError:
            return None

    def snooze_count(self, key) -> int:
        try:
            return int(self.system(key).get("snooze_count") or 0)
        except (TypeError, ValueError):
            return 0

    def set_snooze(self, key, until):
        rec = self.system(key)
        rec["snooze_until"] = until.isoformat()
        rec["snooze_count"] = self.snooze_count(key) + 1
        # A snooze also counts as "seen today", so the cadence resumes from here.
        rec["last_alert"] = date.today().isoformat()

    def snoozed_systems(self) -> list:
        """For admin visibility (spec Risks: snoozing with nobody aware)."""
        today = date.today()
        out = []
        for key, rec in self.data.get("systems", {}).items():
            raw = rec.get("snooze_until")
            if not raw:
                continue
            try:
                until = date.fromisoformat(raw)
            except ValueError:
                continue
            if until >= today:
                out.append((key, until, int(rec.get("snooze_count") or 0)))
        return sorted(out, key=lambda item: item[1])


def load() -> State:
    try:
        with open(paths.state_path(), "r", encoding="utf-8") as fh:
            data = json.load(fh)
    except (OSError, ValueError):
        return State()
    if not isinstance(data, dict):
        return State()
    merged = _default()
    merged.update(data)
    return State(merged)


def save(state: State) -> None:
    """Atomic write: a half written state file would lose every snooze."""
    target = paths.state_path()
    with _lock:
        fd, tmp = tempfile.mkstemp(dir=os.path.dirname(target), suffix=".tmp")
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as fh:
                json.dump(state.data, fh, indent=2)
            os.replace(tmp, target)
        except OSError:
            try:
                os.unlink(tmp)
            except OSError:
                pass
