"""Countdown - RO date reminders.

Reads the department RO table from SharePoint once a day and pops an alert when
a system in the user's department is approaching its RO date.

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
               startup, state as state_module, table)
from .ui import admin as admin_ui, alert as alert_ui, firstrun as firstrun_ui
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
        self._next_read_not_before = None

    # --- first run (R2) ----------------------------------------------------
    def department_choices(self):
        """Closed list for the first run window.

        The list from countdown.txt wins, which is what the maintenance window
        edits. With none set, the list is taken from the table's own department
        column, which keeps the two in step.
        """
        if self.config.departments:
            return self.config.departments
        seen = self.state.data.get("departments_seen") or []
        if seen:
            return seen
        try:
            rows, _ = table.fetch(self.config.sharepoint_url)
        except table.TableError as exc:
            log.warning("could not derive the department list: %s", exc)
            return []
        found = sorted({r.department for r in rows if r.department})
        self.state.data["departments_seen"] = found
        state_module.save(self.state)
        return found

    def run_first_run(self) -> bool:
        departments = self.department_choices()
        if not departments:
            messagebox.showerror(
                "Countdown",
                "The list of departments is not available.\n\n"
                "Set `departments` or a reachable `sharepoint_url` in:\n"
                f"{paths.config_path()}\n\nThe app will start once one of them is set.",
            )
            return False
        result = firstrun_ui.ask(self.root, departments)
        if not result:
            log.info("first run window closed without details; not starting")
            return False
        name, number, department = result
        self.state.set_identity(name, number, department)
        self.state.data["personal_number"] = identity.resolve(self.state) or number
        state_module.save(self.state)
        log.info("first run complete for %s, department %s", name, department)
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
        # Pick up anything the maintenance window changed since the last run
        # (R7, and the department list). Both live outside this process.
        self.state = state_module.load()
        self.config = config_module.load()
        self.state.data["personal_number"] = identity.resolve(self.state) or self.state.personal_number
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
        if not self.state.first_run_complete:
            if not self.run_first_run():
                return 1
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

    log.info("starting, exe at %s, logon %s", paths.exe_path(), identity.logon_name())
    try:
        return Countdown().run()
    except Exception:
        log.exception("Countdown stopped unexpectedly")
        return 1
