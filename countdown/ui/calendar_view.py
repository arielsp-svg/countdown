"""The month view the snooze panel uses (R11).

tkinter ships no calendar, and R13 rules out pulling one in, so it is drawn
here: a plain month grid, days outside the allowed range greyed rather than
hidden, and the chosen day marked with a filled circle.
"""
import calendar
import tkinter as tk
from datetime import date, timedelta

from . import design as d

CELL = 38
ROW = 34
HEADER = 58


class CalendarView(tk.Canvas):
    def __init__(self, master, minimum: date, maximum: date, initial=None,
                 on_change=None, bg=None):
        self.minimum = minimum
        self.maximum = max(maximum, minimum)
        self.on_change = on_change
        self.selected = min(max(initial or minimum, self.minimum), self.maximum)
        self.shown = self.selected.replace(day=1)
        self._bg = bg or d.C["surface"]
        width = CELL * 7
        super().__init__(master, width=width, height=HEADER + ROW * 7,
                         highlightthickness=0, bd=0, bg=self._bg)
        self._width = width
        self.bind("<Button-1>", self._click)
        self._hot = None
        self.bind("<Motion>", self._motion)
        self.bind("<Leave>", lambda _e: self._hover(None))
        self.draw()

    # --- navigation --------------------------------------------------------
    def _can_go(self, months):
        index = self.shown.month - 1 + months
        target = date(self.shown.year + index // 12, index % 12 + 1, 1)
        if months < 0:
            return target >= self.minimum.replace(day=1)
        return target <= self.maximum

    def _shift(self, months):
        if not self._can_go(months):
            return
        index = self.shown.month - 1 + months
        self.shown = date(self.shown.year + index // 12, index % 12 + 1, 1)
        self.draw()

    # --- drawing -----------------------------------------------------------
    def draw(self):
        self.delete("all")
        self._cells = []

        self.create_text(self._width / 2, 16, text=self.shown.strftime("%B %Y"),
                         fill=d.C["text"], font=d.HEADLINE())
        for label, dx, months in (("‹", 14, -1), ("›", self._width - 14, 1)):
            enabled = self._can_go(months)
            self.create_text(dx, 16, text=label,
                             fill=d.C["accent"] if enabled else d.C["text_3"],
                             font=d.font(18), tags=f"nav{months}")
            if enabled:
                self.tag_bind(f"nav{months}", "<Button-1>",
                              lambda _e, m=months: self._shift(m))

        for column, name in enumerate(["M", "T", "W", "T", "F", "S", "S"]):
            self.create_text(column * CELL + CELL / 2, 44, text=name,
                             fill=d.C["text_3"], font=d.font(10, "bold"))

        weeks = calendar.Calendar().monthdatescalendar(self.shown.year, self.shown.month)
        for week_index, week in enumerate(weeks):
            for column, day in enumerate(week):
                if day.month != self.shown.month:
                    continue
                cx = column * CELL + CELL / 2
                cy = HEADER + week_index * ROW + ROW / 2
                allowed = self.minimum <= day <= self.maximum
                self._cells.append((cx, cy, day, allowed))

                if day == self.selected:
                    self.create_oval(cx - 16, cy - 16, cx + 16, cy + 16,
                                     fill=d.C["accent"], outline=d.C["accent"])
                    ink = d.C["on_accent"]
                elif not allowed:
                    ink = d.C["text_3"]
                else:
                    ink = d.C["text"]
                if day == date.today() and day != self.selected:
                    self.create_oval(cx - 16, cy - 16, cx + 16, cy + 16,
                                     outline=d.C["field_line"])
                self.create_text(cx, cy, text=str(day.day), fill=ink,
                                 font=d.font(12, "bold" if day == self.selected else "normal"))
        self.configure(height=HEADER + len(weeks) * ROW + 6)

    # --- interaction -------------------------------------------------------
    def _at(self, x, y):
        for cx, cy, day, allowed in getattr(self, "_cells", []):
            if abs(x - cx) <= CELL / 2 and abs(y - cy) <= ROW / 2 and allowed:
                return day
        return None

    def _motion(self, event):
        self._hover(self._at(event.x, event.y))

    def _hover(self, day):
        if day == self._hot:
            return
        self._hot = day
        self.configure(cursor="hand2" if day else "arrow")

    def _click(self, event):
        day = self._at(event.x, event.y)
        if day is None:
            return
        self.selected = day
        if self.on_change:
            self.on_change(day)
        self.draw()
