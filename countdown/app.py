"""Countdown - RO date reminders.

Reads the department RO table from SharePoint once a day and pops an alert when
a system in the user's department is approaching its RO date.

Who the user is comes from the user list, a second workbook linked from
countdown.txt: the personal number is taken from the Windows logon name (R3) and
looked up there. Nobody is ever asked to fill anything in.

Nothing is visible unless an alert is due or the maintenance window is opened
(R12). Launching the .exe a second time while it is running opens the
maintenance window instead of starting a second copy.
"""
import logging
import logging.handlers
import sys
import threading
import tkinter as tk
from datetime import date, datetime, timedelta
from tkinter import messagebox

from . import (config as config_module, engine, identity, paths, single_instance,
               startup, state as state_module, table, users as users_module)
from .ui import admin as admin_ui, alert as alert_ui
from .ui import design

log = logging.getLogger("countdown")

READ_INTERVAL = timedelta(hours=24)   # R4
TICK_MS = 15 * 60 * 1000              # how often the clock is consulted
RETRY_AFTER = timedelta(hours=2)      # after an unreachable link


def should_read(last_read, now, scanned_this_launch, not_before=None) -> bool:
    """Whether to go and read the table now.

    R4 asks for a read every 24 hours. On top of that, every launch reads once
    before anything else: the app starts with Windows, so a machine that was off
    for a week would otherwise wait out the rest of the interval on the stale
    timestamp it saved before shutting down.

    A launch read ignores the retry backoff as well. The backoff exists for a
    link that was unreachable, and a fresh launch is the most likely moment for
    the network to have come back.

    Reading is not alerting: R6, R10 and R11 still decide whether anything is
    shown, so opening the app repeatedly refreshes the data without nagging.
    """
    if not scanned_this_launch:
        return True
    if not_before and now < not_before:
        return False
    return last_read is None or (now - last_read) >= READ_INTERVAL


def setup_logging() -> None:
    handler = logging.handlers.RotatingFileHandler(
        paths.log_path(), maxBytes=512_000, backupCount=2, encoding="utf-8")
    handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)-7s %(name)s: %(message)s"))
    root = logging.getLogger()
    root.setLevel(logging.INFO)
    root.addHandler(handler)


class Countdown:
    def __init__(self):
        self.config = config_module.load()
        self.state = state_module.load()
        self.root = tk.Tk()
        self.root.withdraw()          # R12: no window when nothing is due
        self.root.title("Countdown")
        design.adopt_system_theme()
        self._busy = False
        self._scanned_this_launch = False
        self._resolved = False
        self._next_read_not_before = None

    # --- who is signed in --------------------------------------------------
    def resolve_user(self):
        """Look the signed in person up in the user list.

        Returns True when a department is known and alerts can be evaluated.
        Everything about the attempt is recorded, so the maintenance window can
        explain a machine that never alerts.
        """
        try:
            users, skipped = users_module.load(self.config.users_url)
        except users_module.UsersError as exc:
            log.warning("could not read the user list: %s", exc)
            self.state.set_directory_status(str(exc))
            return False
        except Exception as exc:
            # Anything else - a locked workbook, a corrupt file - must not take
            # the scheduler down with it. The app stays quiet and says why.
            log.exception("unexpected failure reading the user list")
            self.state.set_directory_status(f"the user list could not be read: {exc}")
            return False

        self.state.data["users_skipped"] = skipped
        user, reason = identity.resolve(users)
        if user is None:
            log.warning("no department for this machine: %s", reason)
            self.state.set_directory_status(reason)
            return False

        if (user.department != self.state.department
                or user.personal_number != self.state.personal_number):
            log.info("resolved %s (%s) in %s", user.name, user.personal_number,
                     user.department)
        self.state.set_identity(user.name, user.personal_number, user.department)
        self.state.set_directory_status("")
        return True

    # --- daily cycle (R4 to R11) ------------------------------------------
    def due_for_read(self) -> bool:
        return should_read(self.state.last_read, datetime.now(),
                           self._scanned_this_launch, self._next_read_not_before)

    def tick(self):
        if not self._busy and self.due_for_read():
            self.start_cycle()
        self.root.after(TICK_MS, self.tick)

    def start_cycle(self):
        self._busy = True
        self._scanned_this_launch = True
        # Pick up anything the maintenance window changed since the last run:
        # the tiers of R7, and the user list. Both live outside this process.
        self.state = state_module.load()
        self.config = config_module.load()

        # The table is read whether or not the person is known. Reading it is
        # what R4 asks for; knowing who is signed in only decides whether any
        # of its rows are alerted on. Keeping the two apart means the last read
        # timestamp, the departments and the skipped rows are all available to
        # the maintenance window even on a machine nobody is matched to.
        self._resolved = self.resolve_user()
        url = self.config.sharepoint_url
        thread = threading.Thread(target=self._download, args=(url,), daemon=True)
        thread.start()

    def _download(self, url):
        try:
            rows, skipped = table.fetch(url)
            self.root.after(0, lambda: self._cycle_finished(rows, skipped, None))
        except table.TableError as exc:
            self.root.after(0, lambda: self._cycle_finished(None, None, exc))
        except Exception as exc:  # never let a background thread kill the app
            log.exception("unexpected failure while reading the table")
            self.root.after(0, lambda: self._cycle_finished(None, None, exc))

    def _cycle_finished(self, rows, skipped, error):
        try:
            if error is not None:
                # R4 edge case, decided: retry quietly, and record it for the
                # admin window. The user is not interrupted for a link problem.
                log.warning("table read failed: %s", error)
                self._next_read_not_before = datetime.now() + RETRY_AFTER
                return

            self.state.mark_read()
            self.state.data["skipped_rows"] = skipped
            found = sorted({r.department for r in rows if r.department})
            if found:
                self.state.data["departments_seen"] = found
            if self.state.department and self.state.department not in found:
                # R5 edge case: the department no longer appears in the table.
                log.warning("department %r is not present in the table", self.state.department)
            for item in skipped:
                log.info("row %s skipped, RO date cell reads %r", item["row"], item["value"])
            state_module.save(self.state)

            if not self._resolved:
                log.info("read %d rows, but nobody here is matched to a "
                         "department, so nothing is evaluated", len(rows))
                return

            due = engine.due_systems(rows, self.state)
            overdue = engine.overdue_systems(rows, self.state)
            log.info("read %d rows, %d due, %d already past their RO date",
                     len(rows), len(due), len(overdue))
            self._show_alerts(due)
        finally:
            self._busy = False

    def _show_alerts(self, due):
        """One popup per system, one after another (R9 edge case)."""
        today = date.today()
        for row, tier in due:
            key = row.key
            outcome, chosen = alert_ui.show(
                self.root, row, snooze_count=self.state.snooze_count(key), today=today)
            if outcome == "acknowledge":
                # R10: quiet until the next interval of its tier.
                self.state.mark_alerted(key, today)
            elif outcome == "snooze" and chosen:
                # R11: quiet until the chosen date, then the cadence resumes.
                self.state.set_snooze(key, chosen, label=row.label)
                log.info("%s snoozed until %s", row.label, chosen)
            else:
                log.info("%s dismissed with the X; it will be offered again", row.label)
            state_module.save(self.state)

    # --- entry point -------------------------------------------------------
    def run(self):
        self.root.after(1500, self.tick)
        self.root.mainloop()
        return 0


def open_maintenance_only() -> int:
    root = tk.Tk()
    root.withdraw()
    design.adopt_system_theme()
    admin_ui.open_maintenance(root, config_module.load(), state_module.load())
    root.destroy()
    return 0


def main(argv=None) -> int:
    argv = list(argv if argv is not None else sys.argv[1:])
    setup_logging()
    config_module.ensure_exists()

    # R1: rewritten on every launch, so a moved folder repairs itself.
    startup.register(paths.exe_path())

    first_copy = single_instance.acquire()
    if "--admin" in argv or not first_copy:
        # Already running, or asked for explicitly: show the maintenance window.
        return open_maintenance_only()

    if not paths.writable():
        # Everything the app saves lives beside the .exe. A folder it cannot
        # write to means no first run details, no snoozes and no alert history,
        # so say so rather than run and quietly forget everything.
        root = tk.Tk()
        root.withdraw()
        messagebox.showerror(
            "Countdown",
            "Countdown keeps its settings in the folder it runs from, and that "
            "folder is read only:\n\n"
            f"{paths.app_dir()}\n\n"
            "Copy Countdown.exe and countdown.txt somewhere you can write to, "
            "such as a folder under your user profile, and run it again.",
        )
        root.destroy()
        log.error("the app folder is not writable: %s", paths.app_dir())
        return 1

    log.info("starting, exe at %s, logon %s", paths.exe_path(), identity.logon_name())
    try:
        return Countdown().run()
    except Exception:
        log.exception("Countdown stopped unexpectedly")
        return 1
