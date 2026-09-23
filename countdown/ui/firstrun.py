"""First run window (R2).

Three fields. Department is a closed list. Background operation does not start
until all three are supplied: closing the window without filling it exits the
app, and the window returns at the next Windows startup.
"""
import logging
import tkinter as tk
from tkinter import ttk

from .. import identity
from .widgets import apply_style, centre

log = logging.getLogger(__name__)


class FirstRunWindow:
    def __init__(self, root, departments):
        self.completed = False
        self.result = None
        self.departments = list(departments)

        self.window = tk.Toplevel(root)
        self.window.title("Countdown - first run")
        self.window.configure(bg="#f4f5f7")
        self.window.resizable(False, False)
        apply_style(self.window)

        frame = ttk.Frame(self.window, padding=(22, 18))
        frame.pack(fill="both", expand=True)

        ttk.Label(frame, text="Countdown", style="Title.TLabel").pack(anchor="w")
        ttk.Label(
            frame,
            text="Countdown watches the RO dates of your department and tells you\n"
                 "before one comes due. Fill these in once.",
            style="Muted.TLabel", justify="left",
        ).pack(anchor="w", pady=(2, 14))

        self.name_var = tk.StringVar()
        self.number_var = tk.StringVar(value=identity.personal_number_from_logon() or "")
        self.department_var = tk.StringVar()

        self._field(frame, "Name", self.name_var)
        self._field(frame, "Personal number", self.number_var)

        ttk.Label(frame, text="Department").pack(anchor="w", pady=(10, 2))
        self.department_box = ttk.Combobox(
            frame, textvariable=self.department_var, values=self.departments,
            state="readonly", width=38,
        )
        self.department_box.pack(anchor="w")

        self.error = ttk.Label(frame, text="", foreground="#b3261e", style="Muted.TLabel")
        self.error.pack(anchor="w", pady=(10, 0))

        buttons = ttk.Frame(frame)
        buttons.pack(fill="x", pady=(16, 0))
        ttk.Button(buttons, text="Cancel", command=self._cancel).pack(side="right")
        ttk.Button(buttons, text="Start", style="Accent.TButton",
                   command=self._submit).pack(side="right", padx=(0, 8))

        for var in (self.name_var, self.number_var, self.department_var):
            var.trace_add("write", lambda *_: self.error.configure(text=""))

        self.window.protocol("WM_DELETE_WINDOW", self._cancel)
        self.window.bind("<Return>", lambda _event: self._submit())
        centre(self.window)
        self.window.transient(root)
        self.window.grab_set()
        self.window.focus_force()

    def _field(self, parent, label, variable):
        ttk.Label(parent, text=label).pack(anchor="w", pady=(10, 2))
        ttk.Entry(parent, textvariable=variable, width=40).pack(anchor="w")

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
