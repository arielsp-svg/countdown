"""Maintenance window (R7, R8).

Credentials are checked against the .txt next to the .exe before anything is
shown. Threshold and frequency changes are written to state and picked up by the
next daily run.
"""
import logging
import tkinter as tk
from tkinter import ttk

from .. import config as config_module
from .. import paths, state as state_module
from ..state import MAX_SNOOZE_DAYS, MAX_SNOOZES_PER_SYSTEM
from .widgets import apply_style, centre

log = logging.getLogger(__name__)


class CredentialPrompt:
    def __init__(self, root, cfg):
        self.cfg = cfg
        self.ok = False
        self.window = tk.Toplevel(root)
        self.window.title("Countdown - maintenance")
        self.window.configure(bg="#f4f5f7")
        self.window.resizable(False, False)
        apply_style(self.window)

        frame = ttk.Frame(self.window, padding=(22, 18))
        frame.pack(fill="both", expand=True)
        ttk.Label(frame, text="Maintenance", style="Title.TLabel").pack(anchor="w")

        if not cfg.has_admin_credentials:
            # R8 edge case: the file is missing, empty or malformed.
            ttk.Label(
                frame,
                text=f"No administrator credentials are set.\nAdd admin_username and "
                     f"admin_password to:\n{paths.config_path()}",
                style="Muted.TLabel", justify="left",
            ).pack(anchor="w", pady=(10, 14))
            ttk.Button(frame, text="Close", command=self.window.destroy).pack(anchor="e")
            self._finish()
            return

        self.user_var = tk.StringVar()
        self.password_var = tk.StringVar()
        ttk.Label(frame, text="Username").pack(anchor="w", pady=(12, 2))
        entry = ttk.Entry(frame, textvariable=self.user_var, width=30)
        entry.pack(anchor="w")
        ttk.Label(frame, text="Password").pack(anchor="w", pady=(10, 2))
        ttk.Entry(frame, textvariable=self.password_var, show="•", width=30).pack(anchor="w")

        self.error = ttk.Label(frame, text="", foreground="#b3261e", style="Muted.TLabel")
        self.error.pack(anchor="w", pady=(10, 0))

        buttons = ttk.Frame(frame)
        buttons.pack(fill="x", pady=(14, 0))
        ttk.Button(buttons, text="Cancel", command=self.window.destroy).pack(side="right")
        ttk.Button(buttons, text="Open", style="Accent.TButton",
                   command=self._check).pack(side="right", padx=(0, 8))
        self.window.bind("<Return>", lambda _e: self._check())
        entry.focus_set()
        self._finish()

    def _finish(self):
        centre(self.window)
        self.window.grab_set()
        self.window.focus_force()

    def _check(self):
        if (self.user_var.get().strip() == self.cfg.admin_username
                and self.password_var.get() == self.cfg.admin_password):
            self.ok = True
            self.window.destroy()
        else:
            self.error.configure(text="Those credentials do not match.")


class AdminWindow:
    def __init__(self, root, state):
        self.state = state
        self.window = tk.Toplevel(root)
        self.window.title("Countdown - maintenance")
        self.window.configure(bg="#f4f5f7")
        apply_style(self.window)

        notebook = ttk.Notebook(self.window)
        notebook.pack(fill="both", expand=True, padx=12, pady=12)
        notebook.add(self._tiers_tab(notebook), text="Alert tiers")
        notebook.add(self._snoozed_tab(notebook), text="Snoozed systems")
        notebook.add(self._skipped_tab(notebook), text="Skipped rows")
        notebook.add(self._status_tab(notebook), text="Status")

        centre(self.window, 640, 540)
        self.window.grab_set()
        self.window.focus_force()

    # --- R7 ----------------------------------------------------------------
    def _tiers_tab(self, parent):
        frame = ttk.Frame(parent, padding=(16, 14))
        ttk.Label(frame, text="Alert tiers", style="Title.TLabel").pack(anchor="w")
        ttk.Label(
            frame,
            text="A system alerts on the tightest tier its RO date falls inside.\n"
                 "Changes take effect at the next daily run.",
            style="Muted.TLabel", justify="left",
        ).pack(anchor="w", pady=(2, 12))

        self.tier_vars = []
        grid = ttk.Frame(frame)
        grid.pack(anchor="w")
        ttk.Label(grid, text="Tier", style="Muted.TLabel").grid(row=0, column=0, sticky="w")
        ttk.Label(grid, text="Alert when the RO date is within (months)",
                  style="Muted.TLabel").grid(row=0, column=1, sticky="w", padx=10)
        ttk.Label(grid, text="Alert every (days)", style="Muted.TLabel").grid(
            row=0, column=2, sticky="w", padx=10)

        for index, tier in enumerate(self.state.tiers, start=1):
            ttk.Label(grid, text=f"{index}").grid(row=index, column=0, sticky="w", pady=4)
            months = tk.StringVar(value=str(tier.get("months", "")))
            days = tk.StringVar(value=str(tier.get("every_days", "")))
            ttk.Entry(grid, textvariable=months, width=10).grid(row=index, column=1, padx=10)
            ttk.Entry(grid, textvariable=days, width=10).grid(row=index, column=2, padx=10)
            self.tier_vars.append((tier.get("name", f"tier{index}"), months, days))

        self.tier_message = ttk.Label(frame, text="", style="Muted.TLabel", wraplength=520,
                                      justify="left")
        self.tier_message.pack(anchor="w", pady=(12, 0))

        buttons = ttk.Frame(frame)
        buttons.pack(anchor="w", pady=(12, 0))
        ttk.Button(buttons, text="Save", style="Accent.TButton",
                   command=self._save_tiers).pack(side="left")
        ttk.Button(buttons, text="Restore defaults",
                   command=self._restore_defaults).pack(side="left", padx=8)
        return frame

    def _save_tiers(self):
        tiers, errors = [], []
        for name, months_var, days_var in self.tier_vars:
            try:
                months = int(months_var.get().strip())
            except ValueError:
                errors.append("Thresholds must be whole numbers of months.")
                continue
            raw_days = days_var.get().strip()
            try:
                days = int(raw_days) if raw_days else 0
            except ValueError:
                days = 0
            if months <= 0:
                errors.append("A threshold must be greater than zero.")
                continue
            if days <= 0:
                # R7 edge case: blank or zero would mean alerting every day.
                days = 30
                errors.append("A blank or zero frequency was replaced with 30 days.")
            tiers.append({"name": name, "months": months, "every_days": days})

        if len([t for t in tiers]) != len(self.tier_vars):
            self.tier_message.configure(text=" ".join(errors) or "Nothing was saved.")
            return

        ordered = sorted(tiers, key=lambda t: -t["months"])
        if len({t["months"] for t in ordered}) != len(ordered):
            # R7 edge case: a tighter threshold set at or above the wider one.
            self.tier_message.configure(text="The two thresholds must differ. Nothing was saved.")
            return

        self.state.set_tiers(ordered)
        state_module.save(self.state)
        summary = ", ".join(f"{t['months']}m every {t['every_days']}d" for t in ordered)
        self.tier_message.configure(
            text=(" ".join(errors) + " " if errors else "") + f"Saved: {summary}.")

    def _restore_defaults(self):
        self.state.set_tiers(state_module.DEFAULT_TIERS)
        state_module.save(self.state)
        self.tier_message.configure(
            text="Restored 12 months / monthly and 6 months / weekly. Reopen this window to see them.")

    # --- snooze visibility -------------------------------------------------
    def _snoozed_tab(self, parent):
        frame = ttk.Frame(parent, padding=(16, 14))
        ttk.Label(frame, text="Snoozed systems", style="Title.TLabel").pack(anchor="w")
        ttk.Label(
            frame,
            text=f"A system may be put off at most {MAX_SNOOZES_PER_SYSTEM} times and at most "
                 f"{MAX_SNOOZE_DAYS} days at a time.",
            style="Muted.TLabel",
        ).pack(anchor="w", pady=(2, 10))

        tree = ttk.Treeview(frame, columns=("until", "count"), show="tree headings", height=12)
        tree.heading("#0", text="System")
        tree.heading("until", text="Quiet until")
        tree.heading("count", text="Times put off")
        tree.column("#0", width=320)
        tree.column("until", width=110, anchor="center")
        tree.column("count", width=110, anchor="center")
        tree.pack(fill="both", expand=True)

        rows = self.state.snoozed_systems()
        for key, until, count in rows:
            label = " / ".join(part for part in key.split("|") if part) or key
            tree.insert("", "end", text=label,
                        values=(until.strftime("%d/%m/%Y"), count))
        if not rows:
            ttk.Label(frame, text="Nothing is snoozed.", style="Muted.TLabel").pack(
                anchor="w", pady=(8, 0))
        return frame

    # --- R4 skipped rows ---------------------------------------------------
    def _skipped_tab(self, parent):
        frame = ttk.Frame(parent, padding=(16, 14))
        ttk.Label(frame, text="Rows skipped at the last read", style="Title.TLabel").pack(anchor="w")
        ttk.Label(
            frame,
            text="These rows hold no readable RO date, so they raise no alert.\n"
                 "The table owner should correct the cell.",
            style="Muted.TLabel", justify="left",
        ).pack(anchor="w", pady=(2, 10))

        tree = ttk.Treeview(frame, columns=("dept", "platform", "value"),
                            show="headings", height=12)
        for column, title, width in [("dept", "Department", 150),
                                     ("platform", "Platform", 170),
                                     ("value", "RO date cell", 200)]:
            tree.heading(column, text=title)
            tree.column(column, width=width)
        tree.pack(fill="both", expand=True)
        skipped = self.state.data.get("skipped_rows") or []
        for item in skipped:
            tree.insert("", "end", values=(item.get("department", ""),
                                           item.get("platform", ""),
                                           item.get("value", "") or "(empty)"))
        if not skipped:
            ttk.Label(frame, text="No rows were skipped.", style="Muted.TLabel").pack(
                anchor="w", pady=(8, 0))
        return frame

    # --- status ------------------------------------------------------------
    def _status_tab(self, parent):
        frame = ttk.Frame(parent, padding=(16, 14))
        ttk.Label(frame, text="Status", style="Title.TLabel").pack(anchor="w")
        cfg = config_module.load()
        last_read = self.state.last_read
        typed = self.state.data.get("personal_number_typed", "")
        resolved = self.state.personal_number
        lines = [
            ("User", self.state.data.get("name", "")),
            ("Personal number", resolved + (f"  (typed at first run: {typed})"
                                            if typed and typed != resolved else "")),
            ("Department", self.state.department),
            ("Last table read", last_read.strftime("%d/%m/%Y %H:%M") if last_read else "never"),
            ("SharePoint link", cfg.sharepoint_url or "(not set)"),
            ("Configuration file", paths.config_path()),
            ("State file", paths.state_path()),
            ("Log file", paths.log_path()),
        ]
        grid = ttk.Frame(frame)
        grid.pack(anchor="w", fill="x", pady=(10, 0))
        for index, (label, value) in enumerate(lines):
            ttk.Label(grid, text=label, style="Muted.TLabel").grid(
                row=index, column=0, sticky="nw", padx=(0, 14), pady=3)
            ttk.Label(grid, text=value or "-", wraplength=380, justify="left").grid(
                row=index, column=1, sticky="w", pady=3)
        return frame


def open_maintenance(root, cfg, state):
    prompt = CredentialPrompt(root, cfg)
    root.wait_window(prompt.window)
    if not prompt.ok:
        return False
    window = AdminWindow(root, state)
    root.wait_window(window.window)
    return True
