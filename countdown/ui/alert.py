"""The alert popup (R9, R10, R11).

One popup per system, shown one after another when several fall due on the same
day. Closing with the X acknowledges nothing: the system is offered again at the
next daily run.
"""
import logging
import tkinter as tk
from datetime import date, timedelta
from tkinter import ttk

from .. import calendar_file
from ..state import MAX_SNOOZE_DAYS, MAX_SNOOZES_PER_SYSTEM
from .widgets import apply_style, centre, DatePicker

log = logging.getLogger(__name__)

ACK_TEXT = "I read, understood, close window"
SNOOZE_TEXT = "Remind me later"

FIELDS = [
    ("Type of system", "type_of_system"),
    ("Nav system", "nav_system"),
    ("Receiver model", "receiver_model"),
    ("Using TOD", "using_tod"),
    ("Comments", "comments"),
]


class AlertWindow:
    def __init__(self, root, row, snooze_count=0, today=None):
        self.row = row
        self.today = today or date.today()
        self.outcome = "dismiss"
        self.snooze_date = None
        self._picker = None

        self.window = tk.Toplevel(root)
        self.window.title("Countdown - RO date")
        self.window.configure(bg="#f4f5f7")
        self.window.resizable(False, False)
        apply_style(self.window)

        frame = ttk.Frame(self.window, padding=(22, 18))
        frame.pack(fill="both", expand=True)

        days_left = (row.ro_date - self.today).days
        ttk.Label(frame, text="RO date approaching", style="Title.TLabel").pack(anchor="w")

        ttk.Label(frame, text=row.platform or row.label, style="Big.TLabel").pack(
            anchor="w", pady=(12, 2))
        ttk.Label(
            frame,
            text=f"RO date {row.ro_date.strftime('%d/%m/%Y')}  -  {days_left} days away",
            style="Muted.TLabel",
        ).pack(anchor="w")

        details = ttk.Frame(frame)
        details.pack(anchor="w", fill="x", pady=(12, 0))
        shown = 0
        for label, field in FIELDS:
            value = str(getattr(row, field, "") or "").strip()
            if not value:
                continue
            ttk.Label(details, text=label, style="Muted.TLabel").grid(
                row=shown, column=0, sticky="w", padx=(0, 12), pady=1)
            ttk.Label(details, text=value, wraplength=280, justify="left").grid(
                row=shown, column=1, sticky="w", pady=1)
            shown += 1

        ttk.Separator(frame).pack(fill="x", pady=(14, 12))

        self.calendar_button = ttk.Button(
            frame, text="Add this date to my calendar", command=self._add_to_calendar)
        self.calendar_button.pack(anchor="w")

        self.snooze_holder = ttk.Frame(frame)
        self.snooze_holder.pack(fill="x")

        buttons = ttk.Frame(frame)
        buttons.pack(fill="x", pady=(16, 0))

        self.snooze_earliest = self.today + timedelta(days=1)
        self.snooze_latest = min(
            row.ro_date - timedelta(days=1),
            self.today + timedelta(days=MAX_SNOOZE_DAYS),
        )
        self.snooze_button = ttk.Button(buttons, text=SNOOZE_TEXT, command=self._open_picker)
        self.snooze_button.pack(side="left")
        ttk.Button(buttons, text=ACK_TEXT, style="Accent.TButton",
                   command=self._acknowledge).pack(side="right")

        self.note = ttk.Label(frame, text="", style="Muted.TLabel", wraplength=380,
                              justify="left")
        self.note.pack(anchor="w", pady=(8, 0))

        if snooze_count >= MAX_SNOOZES_PER_SYSTEM:
            self.snooze_button.state(["disabled"])
            self._note(f"This system has already been put off {snooze_count} times. "
                       "Snooze is no longer offered for it.")
        elif self.snooze_latest < self.snooze_earliest:
            self.snooze_button.state(["disabled"])
            self._note("The RO date is too close to put this off any further.")

        self.window.protocol("WM_DELETE_WINDOW", self._close_without_answer)
        centre(self.window)
        self.window.attributes("-topmost", True)
        self.window.transient(root)
        self.window.grab_set()
        self.window.focus_force()
        self.window.bell()

    def _note(self, text):
        self.note.configure(text=text)

    def _add_to_calendar(self):
        if calendar_file.open_in_calendar(self.row):
            self._note("The date was handed to your calendar.")
        else:
            self._note("The calendar file could not be opened on this machine.")

    def _open_picker(self):
        if self._picker is not None:
            return
        ttk.Label(self.snooze_holder, text="Remind me again on", style="Muted.TLabel").pack(
            anchor="w", pady=(12, 2))
        self._picker = DatePicker(
            self.snooze_holder,
            minimum=self.snooze_earliest,
            maximum=self.snooze_latest,
            initial=min(self.today + timedelta(days=7), self.snooze_latest),
        )
        self._picker.pack(anchor="w", fill="x")
        confirm = ttk.Button(self.snooze_holder, text="Set reminder", command=self._confirm_snooze)
        confirm.pack(anchor="w", pady=(8, 0))
        self.snooze_button.state(["disabled"])
        self._note(
            "The date must fall before the RO date and no more than "
            f"{MAX_SNOOZE_DAYS} days out. The normal reminders resume on that date."
        )
        self.window.geometry("")
        centre(self.window)

    def _confirm_snooze(self):
        chosen = self._picker.selected
        # The picker is already bounded; this refuses anything that slips past.
        if chosen <= self.today or chosen >= self.row.ro_date or chosen > self.snooze_latest:
            self._note("Choose a date after today and before the RO date.")
            return
        self.snooze_date = chosen
        self.outcome = "snooze"
        self.window.destroy()

    def _acknowledge(self):
        self.outcome = "acknowledge"
        self.window.destroy()

    def _close_without_answer(self):
        # R9 edge case: the X is not an acknowledgement. Nothing is recorded, so
        # the system is offered again at the next daily run.
        self.outcome = "dismiss"
        self.window.destroy()


def show(root, row, snooze_count=0, today=None):
    """Return ("acknowledge"|"snooze"|"dismiss", chosen date or None)."""
    window = AlertWindow(root, row, snooze_count=snooze_count, today=today)
    root.wait_window(window.window)
    return window.outcome, window.snooze_date
