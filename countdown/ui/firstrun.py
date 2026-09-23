"""First run window (R2).

Three fields. Department is a closed list. Background operation does not start
until all three are supplied: closing the window without filling it exits the
app, and the window returns at the next Windows startup.
"""
import logging
import tkinter as tk

from .. import identity
from . import design as d

log = logging.getLogger(__name__)

WIDTH = 420


class FirstRunWindow:
    def __init__(self, root, departments):
        self.completed = False
        self.result = None
        self.departments = list(departments)

        self.window = tk.Toplevel(root)
        self.window.title("Countdown")
        self.window.resizable(False, False)
        d.dress(self.window)

        outer = tk.Frame(self.window, bg=d.C["bg"])
        outer.pack(fill="both", expand=True, padx=26, pady=26)

        tk.Label(outer, text="Countdown", font=d.DISPLAY(), fg=d.C["text"],
                 bg=d.C["bg"], anchor="w").pack(fill="x")
        tk.Label(outer,
                 text="Watches the RO dates for your department\nand tells you before one comes due.",
                 font=d.BODY(), fg=d.C["text_2"], bg=d.C["bg"],
                 anchor="w", justify="left").pack(fill="x", pady=(4, 20))

        card = d.Surface(outer, radius=16, padding=(20, 18), bg=d.C["bg"])
        card.pack(fill="x")

        self.name_var = tk.StringVar()
        self.number_var = tk.StringVar(value=identity.personal_number_from_logon() or "")
        self.department_var = tk.StringVar()

        body = card.body
        self._label(body, "Name").pack(fill="x")
        self.name_field = d.Field(body, self.name_var, bg=d.C["surface"])
        self.name_field.pack(fill="x", pady=(6, 14))

        self._label(body, "Personal number").pack(fill="x")
        self.number_field = d.Field(body, self.number_var, bg=d.C["surface"])
        self.number_field.pack(fill="x", pady=(6, 14))

        self._label(body, "Department").pack(fill="x")
        self.department_select = d.Select(body, self.departments, self.department_var,
                                          placeholder="Choose your department",
                                          bg=d.C["surface"])
        self.department_select.pack(fill="x", pady=(6, 0))
        card.fit()

        self.error = tk.Label(outer, text="", font=d.CAPTION(), fg=d.C["danger"],
                              bg=d.C["bg"], anchor="w", justify="left",
                              wraplength=WIDTH - 52)
        self.error.pack(fill="x", pady=(12, 0))

        d.Button(outer, "Start", kind="filled", stretch=True,
                 command=self._submit, bg=d.C["bg"]).pack(fill="x", pady=(8, 8))
        d.Button(outer, "Not now", kind="plain", stretch=True,
                 command=self._cancel, bg=d.C["bg"]).pack(fill="x")

        for var in (self.name_var, self.number_var, self.department_var):
            var.trace_add("write", lambda *_: self.error.configure(text=""))

        self.window.protocol("WM_DELETE_WINDOW", self._cancel)
        self.window.bind("<Return>", lambda _event: self._submit())
        d.present(self.window, root, width=WIDTH + 52)
        self.window.focus_force()
        self.name_field.entry.focus_set()

    def _label(self, parent, text):
        return tk.Label(parent, text=text, font=d.SUB(), fg=d.C["text_2"],
                        bg=d.C["surface"], anchor="w")

    def _submit(self):
        name = self.name_var.get().strip()
        number = self.number_var.get().strip()
        department = self.department_var.get().strip()
        if not name:
            return self._fail("Enter your name.")
        if not number:
            return self._fail("Enter your personal number.")
        if not number.isdigit():
            return self._fail("The personal number should be digits only.")
        if not department:
            return self._fail("Choose your department.")
        self.result = (name, number, department)
        self.completed = True
        self.window.destroy()

    def _fail(self, message):
        self.error.configure(text=message)

    def _cancel(self):
        # R2 open question, decided: nothing is saved and the app does not start
        # background operation. The window returns at the next startup.
        self.completed = False
        self.window.destroy()


def ask(root, departments):
    window = FirstRunWindow(root, departments)
    root.wait_window(window.window)
    return window.result if window.completed else None
