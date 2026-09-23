"""Shared look, and the date picker the snooze popup needs (R11).

tkinter ships no calendar widget, so there is a small one here rather than a
third party dependency, which R13 rules out.
"""
import calendar
import tkinter as tk
from datetime import date, timedelta
from tkinter import ttk

BG = "#f4f5f7"
ACCENT = "#1f3a5f"
MUTED = "#5b6673"


def apply_style(root) -> None:
    style = ttk.Style(root)
    try:
        style.theme_use("vista")
    except tk.TclError:
        try:
            style.theme_use("clam")
        except tk.TclError:
            pass
    style.configure("TFrame", background=BG)
    style.configure("TLabel", background=BG, font=("Segoe UI", 10))
    style.configure("Title.TLabel", font=("Segoe UI Semibold", 14), foreground=ACCENT)
    style.configure("Muted.TLabel", foreground=MUTED, font=("Segoe UI", 9))
    style.configure("Big.TLabel", font=("Segoe UI Semibold", 12))
    style.configure("TButton", font=("Segoe UI", 10), padding=(10, 6))
    style.configure("Accent.TButton", font=("Segoe UI Semibold", 10), padding=(10, 6))


def centre(window, width=None, height=None) -> None:
    """Size the window to its content unless told otherwise, and centre it."""
    window.update_idletasks()
    width = width or window.winfo_reqwidth()
    height = height or window.winfo_reqheight()
    x = (window.winfo_screenwidth() - width) // 2
    y = (window.winfo_screenheight() - height) // 3
    window.geometry(f"{width}x{height}+{max(x, 0)}+{max(y, 0)}")


class DatePicker(ttk.Frame):
    """A month grid bounded by `minimum` and `maximum`, both inclusive."""

    def __init__(self, master, minimum: date, maximum: date, initial: date = None, on_change=None):
        super().__init__(master, padding=(4, 4))
        self.minimum = minimum
        self.maximum = max(maximum, minimum)
        self.on_change = on_change
        self.selected = min(max(initial or minimum, self.minimum), self.maximum)
        self.shown = self.selected.replace(day=1)

        header = ttk.Frame(self)
        header.pack(fill="x")
        self._prev = ttk.Button(header, text="‹", width=3, command=self._back)
        self._prev.pack(side="left")
        self._title = ttk.Label(header, anchor="center", style="Big.TLabel")
        self._title.pack(side="left", expand=True, fill="x")
        self._next = ttk.Button(header, text="›", width=3, command=self._forward)
        self._next.pack(side="right")

        self._grid = ttk.Frame(self)
        self._grid.pack(fill="both", expand=True, pady=(6, 0))
        self._buttons = []
        self._draw()

    def _shift(self, months):
        index = self.shown.month - 1 + months
        year = self.shown.year + index // 12
        self.shown = date(year, index % 12 + 1, 1)
        self._draw()

    def _back(self):
        self._shift(-1)

    def _forward(self):
        self._shift(1)

    def _choose(self, day):
        self.selected = day
        if self.on_change:
            self.on_change(day)
        self._draw()

    def _draw(self):
        for widget in self._grid.winfo_children():
            widget.destroy()
        self._title.configure(text=self.shown.strftime("%B %Y"))
        for column, name in enumerate(["Mo", "Tu", "We", "Th", "Fr", "Sa", "Su"]):
            ttk.Label(self._grid, text=name, style="Muted.TLabel", anchor="center").grid(
                row=0, column=column, sticky="nsew", padx=1, pady=1)
        for column in range(7):
            self._grid.columnconfigure(column, weight=1, minsize=34)

        for week_index, week in enumerate(calendar.Calendar().monthdatescalendar(
                self.shown.year, self.shown.month), start=1):
            for column, day in enumerate(week):
                if day.month != self.shown.month:
                    ttk.Label(self._grid, text="").grid(row=week_index, column=column)
                    continue
                enabled = self.minimum <= day <= self.maximum
                button = tk.Button(
                    self._grid, text=str(day.day), relief="flat", bd=0,
                    font=("Segoe UI", 9, "bold" if day == self.selected else "normal"),
                    bg=ACCENT if day == self.selected else "#ffffff",
                    fg="#ffffff" if day == self.selected else ("#222222" if enabled else "#bbbbbb"),
                    activebackground="#dce6f2", cursor="hand2" if enabled else "arrow",
                    state="normal" if enabled else "disabled",
                    command=(lambda d=day: self._choose(d)),
                )
                button.grid(row=week_index, column=column, sticky="nsew", padx=1, pady=1)

        first_of_month = self.shown
        self._prev.state(["!disabled"] if first_of_month > self.minimum.replace(day=1) else ["disabled"])
        last = (first_of_month.replace(day=28) + timedelta(days=4)).replace(day=1)
        self._next.state(["!disabled"] if last <= self.maximum else ["disabled"])
