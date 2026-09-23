"""The alert popup (R9, R10, R11).

One popup per system, shown one after another when several fall due on the same
day. Closing with the X acknowledges nothing: the system is offered again at the
next daily run.
"""
import logging
import tkinter as tk
from datetime import date, timedelta

from .. import calendar_file
from ..state import MAX_SNOOZE_DAYS, MAX_SNOOZES_PER_SYSTEM
from . import design as d
from .calendar_view import CalendarView

log = logging.getLogger(__name__)

ACK_TEXT = "I read, understood, close window"
SNOOZE_TEXT = "Remind me later"

FIELDS = [
    ("Type of system", "type_of_system"),
    ("Nav system", "nav_system"),
    ("Receiver model", "receiver_model"),
    ("Using TOD", "using_tod"),
]

WIDTH = 460


class AlertWindow:
    def __init__(self, root, row, snooze_count=0, today=None):
        self.row = row
        self.today = today or date.today()
        self.outcome = "dismiss"
        self.snooze_date = None
        self._picker = None

        self.window = tk.Toplevel(root)
        self.window.title("Countdown")
        self.window.resizable(False, False)
        d.dress(self.window)

        outer = tk.Frame(self.window, bg=d.C["bg"])
        outer.pack(fill="both", expand=True, padx=20, pady=20)

        self._header(outer)
        self.card = d.Surface(outer, radius=16, padding=(22, 20), bg=d.C["bg"])
        self.card.pack(fill="x", pady=(16, 0))
        self._card_body(self.card.body)
        self.card.fit()

        self.snooze_holder = tk.Frame(outer, bg=d.C["bg"])
        self.snooze_holder.pack(fill="x")

        self.note = tk.Label(outer, text="", font=d.CAPTION(), fg=d.C["text_2"],
                             bg=d.C["bg"], wraplength=WIDTH - 40, justify="left", anchor="w")
        self.note.pack(fill="x", pady=(14, 0))

        self._actions(outer)
        self._limits(snooze_count)

        self.window.protocol("WM_DELETE_WINDOW", self._close_without_answer)
        self.window.bind("<Escape>", lambda _e: self._close_without_answer())
        d.present(self.window, root, width=WIDTH + 40)
        self.window.attributes("-topmost", True)
        self.window.focus_force()
        self.window.bell()

    # --- layout ------------------------------------------------------------
    def _header(self, parent):
        days_left = (self.row.ro_date - self.today).days
        head = tk.Frame(parent, bg=d.C["bg"])
        head.pack(fill="x")

        urgent = days_left <= 185
        chip_ink = d.C["danger"] if urgent else d.C["warn"]
        chip_bg = d.C["warn_wash"]
        from tkinter import font as tkfont
        chip_text = f"{days_left} days left"
        chip_face = d.font(11, "bold")
        chip_w = tkfont.Font(font=chip_face).measure(chip_text) + 24
        chip = tk.Canvas(head, height=24, width=chip_w, highlightthickness=0, bd=0,
                         bg=d.C["bg"])
        chip.pack(anchor="w")
        d.rounded(chip, 0, 0, chip_w, 24, 12, fill=chip_bg, outline=chip_bg)
        chip.create_text(chip_w / 2, 13, text=chip_text,
                         fill=chip_ink, font=chip_face)

        tk.Label(head, text=self.row.platform or self.row.label,
                 font=d.DISPLAY(), fg=d.C["text"], bg=d.C["bg"],
                 anchor="w", justify="left", wraplength=WIDTH).pack(
            fill="x", pady=(12, 2))
        tk.Label(head, text="is approaching its RO date",
                 font=d.BODY(), fg=d.C["text_2"], bg=d.C["bg"], anchor="w").pack(fill="x")

    def _card_body(self, body):
        top = tk.Frame(body, bg=d.C["surface"])
        top.pack(fill="x")
        tk.Label(top, text="RO DATE", font=d.font(10, "bold"), fg=d.C["text_3"],
                 bg=d.C["surface"], anchor="w").pack(fill="x")
        tk.Label(top, text=self.row.ro_date.strftime("%d %B %Y"),
                 font=d.TITLE(), fg=d.C["text"], bg=d.C["surface"], anchor="w").pack(
            fill="x", pady=(2, 0))

        rows = [(lbl, str(getattr(self.row, f, "") or "").strip())
                for lbl, f in FIELDS]
        rows = [(lbl, val) for lbl, val in rows if val]
        if rows:
            tk.Frame(body, height=1, bg=d.C["hairline"]).pack(fill="x", pady=14)
            grid = tk.Frame(body, bg=d.C["surface"])
            grid.pack(fill="x")
            grid.columnconfigure(1, weight=1)
            for index, (lbl, value) in enumerate(rows):
                tk.Label(grid, text=lbl, font=d.SUB(), fg=d.C["text_2"],
                         bg=d.C["surface"], anchor="w").grid(
                    row=index, column=0, sticky="w", pady=3, padx=(0, 18))
                tk.Label(grid, text=value, font=d.SUB(), fg=d.C["text"],
                         bg=d.C["surface"], anchor="e").grid(
                    row=index, column=1, sticky="e", pady=3)

        comments = str(self.row.comments or "").strip()
        if comments:
            tk.Frame(body, height=1, bg=d.C["hairline"]).pack(fill="x", pady=14)
            tk.Label(body, text=comments, font=d.SUB(), fg=d.C["text_2"],
                     bg=d.C["surface"], anchor="w", justify="left",
                     wraplength=WIDTH - 84).pack(fill="x")

    def _actions(self, parent):
        self.calendar_button = d.Button(
            parent, "Add to calendar", kind="tinted", command=self._add_to_calendar,
            bg=d.C["bg"])
        self.calendar_button.pack(anchor="w", pady=(16, 0))

        self.ack_button = d.Button(parent, ACK_TEXT, kind="filled", stretch=True,
                                   command=self._acknowledge, bg=d.C["bg"])
        self.ack_button.pack(fill="x", pady=(18, 8))
        self.snooze_button = d.Button(parent, SNOOZE_TEXT, kind="plain", stretch=True,
                                      command=self._open_picker, bg=d.C["bg"])
        self.snooze_button.pack(fill="x")

    def _limits(self, snooze_count):
        self.snooze_earliest = self.today + timedelta(days=1)
        self.snooze_latest = min(self.row.ro_date - timedelta(days=1),
                                 self.today + timedelta(days=MAX_SNOOZE_DAYS))
        if snooze_count >= MAX_SNOOZES_PER_SYSTEM:
            self.snooze_button.set_enabled(False)
            self._note(f"This system has already been put off {snooze_count} times, "
                       "so it can no longer be postponed.")
        elif self.snooze_latest < self.snooze_earliest:
            self.snooze_button.set_enabled(False)
            self._note("The RO date is too close to put this off any further.")

    # --- behaviour ---------------------------------------------------------
    def _note(self, text):
        self.note.configure(text=text)

    def _add_to_calendar(self):
        if calendar_file.open_in_calendar(self.row):
            self.calendar_button.set_text("Added to calendar")
            self._note("The date was handed to your calendar.")
        else:
            self._note("The calendar file could not be opened on this machine.")

    def _open_picker(self):
        if self._picker is not None:
            return
        panel = d.Surface(self.snooze_holder, radius=16, padding=(16, 14), bg=d.C["bg"])
        panel.pack(fill="x", pady=(16, 0))
        tk.Label(panel.body, text="Remind me again on", font=d.HEADLINE(),
                 fg=d.C["text"], bg=d.C["surface"], anchor="w").pack(fill="x")
        tk.Label(panel.body,
                 text=f"Before the RO date, and at most {MAX_SNOOZE_DAYS} days out.",
                 font=d.CAPTION(), fg=d.C["text_2"], bg=d.C["surface"], anchor="w").pack(
            fill="x", pady=(2, 10))
        self._picker = CalendarView(
            panel.body, minimum=self.snooze_earliest, maximum=self.snooze_latest,
            initial=min(self.today + timedelta(days=7), self.snooze_latest),
            bg=d.C["surface"],
        )
        self._picker.pack(fill="x")
        d.Button(panel.body, "Set reminder", kind="filled", bg=d.C["surface"],
                 command=self._confirm_snooze).pack(anchor="w", pady=(12, 0))
        panel.fit()
        self.snooze_button.set_enabled(False)
        d.present(self.window, width=WIDTH + 40)

    def _confirm_snooze(self):
        chosen = self._picker.selected
        # The calendar is already bounded; this refuses anything that slips past.
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
