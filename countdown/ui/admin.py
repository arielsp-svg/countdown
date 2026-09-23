"""Maintenance window (R7, R8).

Credentials are checked against the .txt next to the .exe before anything is
shown. Threshold and frequency changes are written to state and picked up by the
next daily run.
"""
import logging
import tkinter as tk

from .. import config as config_module
from .. import paths, state as state_module, users as users_module
from ..state import MAX_SNOOZE_DAYS, MAX_SNOOZES_PER_SYSTEM
from . import design as d

log = logging.getLogger(__name__)


class CredentialPrompt:
    WIDTH = 360

    def __init__(self, root, cfg):
        self.cfg = cfg
        self.ok = False
        self.window = tk.Toplevel(root)
        self.window.title("Countdown")
        self.window.resizable(False, False)
        d.dress(self.window)

        outer = tk.Frame(self.window, bg=d.C["bg"])
        outer.pack(fill="both", expand=True, padx=26, pady=26)
        tk.Label(outer, text="Maintenance", font=d.TITLE(), fg=d.C["text"],
                 bg=d.C["bg"], anchor="w").pack(fill="x")

        if not cfg.has_admin_credentials:
            # R8 edge case: the file is missing, empty or malformed.
            tk.Label(outer,
                     text="No administrator credentials are set. Add "
                          "admin_username and admin_password to countdown.txt.",
                     font=d.BODY(), fg=d.C["text_2"], bg=d.C["bg"], anchor="w",
                     justify="left", wraplength=self.WIDTH).pack(fill="x", pady=(8, 6))
            tk.Label(outer, text=paths.config_path(), font=d.CAPTION(),
                     fg=d.C["text_3"], bg=d.C["bg"], anchor="w", justify="left",
                     wraplength=self.WIDTH).pack(fill="x", pady=(0, 16))
            d.Button(outer, "Close", kind="filled", stretch=True,
                     command=self.window.destroy, bg=d.C["bg"]).pack(fill="x")
            self._present(root)
            return

        tk.Label(outer, text="Sign in to change the alert settings.",
                 font=d.BODY(), fg=d.C["text_2"], bg=d.C["bg"], anchor="w").pack(
            fill="x", pady=(4, 18))

        self.user_var = tk.StringVar()
        self.password_var = tk.StringVar()
        card = d.Surface(outer, radius=16, padding=(20, 18), bg=d.C["bg"])
        card.pack(fill="x")
        tk.Label(card.body, text="Username", font=d.SUB(), fg=d.C["text_2"],
                 bg=d.C["surface"], anchor="w").pack(fill="x")
        self.user_field = d.Field(card.body, self.user_var, bg=d.C["surface"])
        self.user_field.pack(fill="x", pady=(6, 14))
        tk.Label(card.body, text="Password", font=d.SUB(), fg=d.C["text_2"],
                 bg=d.C["surface"], anchor="w").pack(fill="x")
        d.Field(card.body, self.password_var, show="•", bg=d.C["surface"]).pack(
            fill="x", pady=(6, 0))
        card.fit()

        self.error = tk.Label(outer, text="", font=d.CAPTION(), fg=d.C["danger"],
                              bg=d.C["bg"], anchor="w")
        self.error.pack(fill="x", pady=(12, 0))
        d.Button(outer, "Open", kind="filled", stretch=True, command=self._check,
                 bg=d.C["bg"]).pack(fill="x", pady=(8, 8))
        d.Button(outer, "Cancel", kind="plain", stretch=True,
                 command=self.window.destroy, bg=d.C["bg"]).pack(fill="x")
        self.window.bind("<Return>", lambda _e: self._check())
        self._present(root)
        self.user_field.entry.focus_set()

    def _present(self, root):
        d.present(self.window, root, width=self.WIDTH + 52)
        self.window.focus_force()

    def _check(self):
        if (self.user_var.get().strip() == self.cfg.admin_username
                and self.password_var.get() == self.cfg.admin_password):
            self.ok = True
            self.window.destroy()
        else:
            self.error.configure(text="Those credentials do not match.")


TABS = [
    ("tiers", "Alert tiers"),
    ("users", "Users"),
    ("snoozed", "Snoozed"),
    ("skipped", "Skipped rows"),
    ("status", "Status"),
]


class AdminWindow:
    WIDTH, HEIGHT = 860, 650
    SIDEBAR = 180

    def __init__(self, root, state):
        self.state = state
        self.window = tk.Toplevel(root)
        self.window.title("Countdown")
        self.window.minsize(self.WIDTH, self.HEIGHT)
        d.dress(self.window)

        shell = tk.Frame(self.window, bg=d.C["bg"])
        shell.pack(fill="both", expand=True)

        self.sidebar = tk.Frame(shell, bg=d.C["surface_sunken"], width=self.SIDEBAR)
        self.sidebar.pack(side="left", fill="y")
        self.sidebar.pack_propagate(False)
        tk.Label(self.sidebar, text="Maintenance", font=d.HEADLINE(), fg=d.C["text"],
                 bg=d.C["surface_sunken"], anchor="w").pack(
            fill="x", padx=18, pady=(22, 14))

        self.tab_buttons = {}
        for key, title in TABS:
            button = tk.Label(self.sidebar, text=title, font=d.BODY(),
                              fg=d.C["text_2"], bg=d.C["surface_sunken"],
                              anchor="w", padx=14, pady=9, cursor="hand2")
            button.pack(fill="x", padx=8, pady=1)
            button.bind("<Button-1>", lambda _e, k=key: self.show(k))
            self.tab_buttons[key] = button

        self.content = tk.Frame(shell, bg=d.C["bg"])
        self.content.pack(side="left", fill="both", expand=True)

        d.present(self.window, root, width=self.WIDTH, height=self.HEIGHT)
        self.window.focus_force()
        self.show("tiers")

    # --- navigation --------------------------------------------------------
    def show(self, key):
        for name, button in self.tab_buttons.items():
            selected = name == key
            button.configure(fg=d.C["accent"] if selected else d.C["text_2"],
                             bg=d.C["accent_wash"] if selected else d.C["surface_sunken"],
                             font=d.font(13, "bold") if selected else d.BODY())
        for child in self.content.winfo_children():
            child.destroy()
        # Every tab scrolls: the user list and the tiers both outgrow the window.
        area = d.ScrollArea(self.content, bg=d.C["bg"])
        area.pack(fill="both", expand=True)
        frame = tk.Frame(area.body, bg=d.C["bg"])
        frame.pack(fill="both", expand=True, padx=28, pady=26)
        {"tiers": self._tiers, "users": self._users,
         "snoozed": self._snoozed, "skipped": self._skipped,
         "status": self._status}[key](frame)

    def _heading(self, parent, title, subtitle):
        tk.Label(parent, text=title, font=d.TITLE(), fg=d.C["text"], bg=d.C["bg"],
                 anchor="w").pack(fill="x")
        tk.Label(parent, text=subtitle, font=d.SUB(), fg=d.C["text_2"], bg=d.C["bg"],
                 anchor="w", justify="left", wraplength=560).pack(fill="x", pady=(3, 18))

    # --- R7 ----------------------------------------------------------------
    def _tiers(self, parent):
        self._heading(parent, "Alert tiers",
                      "A system alerts on the tightest tier its RO date falls inside. "
                      "Changes take effect at the next daily run.")
        self.tier_vars = []
        for index, tier in enumerate(self.state.tiers):
            card = d.Surface(parent, radius=14, padding=(18, 14), bg=d.C["bg"])
            card.pack(fill="x", pady=(0, 10))
            body = card.body
            name = "Wider tier" if index == 0 else "Tighter tier"
            tk.Label(body, text=name, font=d.HEADLINE(), fg=d.C["text"],
                     bg=d.C["surface"], anchor="w").pack(fill="x")

            grid = tk.Frame(body, bg=d.C["surface"])
            grid.pack(fill="x", pady=(10, 0))
            months = tk.StringVar(value=str(tier.get("months", "")))
            days = tk.StringVar(value=str(tier.get("every_days", "")))
            for column, (caption, var) in enumerate(
                    [("Within (months)", months), ("Alert every (days)", days)]):
                cell = tk.Frame(grid, bg=d.C["surface"])
                cell.grid(row=0, column=column, sticky="w", padx=(0, 22))
                tk.Label(cell, text=caption, font=d.CAPTION(), fg=d.C["text_2"],
                         bg=d.C["surface"], anchor="w").pack(fill="x")
                d.Field(cell, var, bg=d.C["surface"], width=120).pack(pady=(4, 0))
            self.tier_vars.append((tier.get("name", f"tier{index}"), months, days))
            card.fit()

        self.tier_message = tk.Label(parent, text="", font=d.CAPTION(),
                                     fg=d.C["text_2"], bg=d.C["bg"], anchor="w",
                                     justify="left", wraplength=440)
        self.tier_message.pack(fill="x", pady=(6, 12))
        buttons = tk.Frame(parent, bg=d.C["bg"])
        buttons.pack(fill="x")
        d.Button(buttons, "Save", kind="filled", command=self._save_tiers,
                 bg=d.C["bg"]).pack(side="left")
        d.Button(buttons, "Restore defaults", kind="plain",
                 command=self._restore_defaults, bg=d.C["bg"]).pack(side="left", padx=6)

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

        if len(tiers) != len(self.tier_vars):
            self.tier_message.configure(text=" ".join(errors) or "Nothing was saved.")
            return
        ordered = sorted(tiers, key=lambda t: -t["months"])
        if len({t["months"] for t in ordered}) != len(ordered):
            # R7 edge case: a tighter threshold set at or above the wider one.
            self.tier_message.configure(
                text="The two thresholds must differ. Nothing was saved.")
            return
        self.state.set_tiers(ordered)
        state_module.save(self.state)
        summary = ", ".join(f"{t['months']} months every {t['every_days']} days"
                            for t in ordered)
        self.tier_message.configure(
            text=(" ".join(errors) + " " if errors else "") + f"Saved: {summary}.")

    def _restore_defaults(self):
        self.state.set_tiers(state_module.DEFAULT_TIERS)
        state_module.save(self.state)
        self.show("tiers")
        self.tier_message.configure(
            text="Restored 12 months monthly, and 6 months weekly.")

    # --- the user list ------------------------------------------------------
    def _users(self, parent):
        cfg = config_module.load()
        source = cfg.users_url
        self._heading(parent, "Users",
                      "Name, personal number and department, one row per person. "
                      "The app matches the Windows logon name against the personal "
                      "number, so nobody is ever asked to fill anything in.")

        report = users_module.describe(source)
        self._source_card(parent, report)

        if report["error"] or not source:
            return

        users, skipped = users_module.load(source)

        self._users_cache = users
        editable = users_module.writable_path(source) is not None

        card = d.Surface(parent, radius=14, padding=(18, 12), bg=d.C["bg"])
        card.pack(fill="x")
        body = card.body
        if not users:
            tk.Label(body, text="The list is empty.", font=d.BODY(),
                     fg=d.C["text_3"], bg=d.C["surface"], anchor="w").pack(
                fill="x", pady=6)
        for index, user in enumerate(users[:9]):
            if index:
                tk.Frame(body, height=1, bg=d.C["hairline"]).pack(fill="x")
            line = tk.Frame(body, bg=d.C["surface"])
            line.pack(fill="x", pady=2)
            if editable:
                d.Button(line, "Remove", kind="plain", bg=d.C["surface"],
                         command=lambda u=user: self._remove_user(u)).pack(side="right")
            tk.Label(line, text=user.name or "(no name)", font=d.BODY(),
                     fg=d.C["text"], bg=d.C["surface"], anchor="w", width=18).pack(
                side="left", pady=5)
            tk.Label(line, text=user.personal_number, font=d.SUB(),
                     fg=d.C["text_2"], bg=d.C["surface"], anchor="w", width=11).pack(
                side="left")
            tk.Label(line, text=user.department, font=d.SUB(), fg=d.C["text_2"],
                     bg=d.C["surface"], anchor="w").pack(side="left", fill="x",
                                                         expand=True)
        card.fit()

        if len(users) > 9:
            tk.Label(parent, text=f"and {len(users) - 9} more in the workbook",
                     font=d.CAPTION(), fg=d.C["text_3"], bg=d.C["bg"], anchor="w").pack(
                fill="x", pady=(6, 0))

        self.user_message = tk.Label(parent, text="", font=d.CAPTION(),
                                     fg=d.C["text_2"], bg=d.C["bg"], anchor="w",
                                     justify="left", wraplength=440)

        if not editable:
            # An anonymous link can be downloaded through and nothing more.
            self.user_message.pack(fill="x", pady=(14, 0))
            self.user_message.configure(
                text="This list is a link, so it can only be read. Point users_url "
                     "at a file path - a share, a mapped drive, or a name next to "
                     "the .exe - to add and remove people here.")
            return

        self._add_user_form(parent, users)
        self.user_message.pack(fill="x", pady=(12, 0))
        if skipped:
            self.user_message.configure(
                text=f"{len(skipped)} row(s) in the workbook have no personal number "
                     "or no department, and are ignored.")

    def _add_user_form(self, parent, users):
        self.new_name = tk.StringVar()
        self.new_number = tk.StringVar()
        self.new_department = tk.StringVar()

        form = d.Surface(parent, radius=14, padding=(18, 14), bg=d.C["bg"])
        form.pack(fill="x", pady=(14, 0))
        tk.Label(form.body, text="Add someone", font=d.HEADLINE(), fg=d.C["text"],
                 bg=d.C["surface"], anchor="w").pack(fill="x", pady=(0, 10))

        grid = tk.Frame(form.body, bg=d.C["surface"])
        grid.pack(fill="x")
        for column, (caption, var, width) in enumerate([
                ("Name", self.new_name, 170),
                ("Personal number", self.new_number, 130)]):
            cell = tk.Frame(grid, bg=d.C["surface"])
            cell.grid(row=0, column=column, sticky="w", padx=(0, 14))
            tk.Label(cell, text=caption, font=d.CAPTION(), fg=d.C["text_2"],
                     bg=d.C["surface"], anchor="w").pack(fill="x")
            d.Field(cell, var, bg=d.C["surface"], width=width).pack(pady=(4, 0))

        known = sorted({u.department for u in users if u.department}
                       | set(self.state.data.get("departments_seen") or []))
        cell = tk.Frame(grid, bg=d.C["surface"])
        cell.grid(row=0, column=2, sticky="w")
        tk.Label(cell, text="Department", font=d.CAPTION(), fg=d.C["text_2"],
                 bg=d.C["surface"], anchor="w").pack(fill="x")
        if known:
            d.Select(cell, known, self.new_department, placeholder="Choose",
                     bg=d.C["surface"], width=150).pack(pady=(4, 0))
        else:
            d.Field(cell, self.new_department, bg=d.C["surface"], width=150).pack(
                pady=(4, 0))

        d.Button(form.body, "Add to the list", kind="filled", bg=d.C["surface"],
                 command=self._add_user).pack(anchor="w", pady=(12, 0))
        form.fit()

    def _source_card(self, parent, report):
        """Say plainly what the user list did, so a silent failure is readable."""
        good = not report["error"]
        card = d.Surface(parent, radius=14, padding=(18, 14), bg=d.C["bg"])
        card.pack(fill="x", pady=(0, 14))
        body = card.body

        headline = (f"Read {report['count']} people" if good
                    else "The user list could not be read")
        tk.Label(body, text=headline, font=d.HEADLINE(),
                 fg=d.C["text"] if good else d.C["danger"],
                 bg=d.C["surface"], anchor="w").pack(fill="x")

        lines = [("users_url", report["source"])]
        if report["resolved"] and report["resolved"] != report["source"]:
            lines.append(("Resolves to", report["resolved"]))
        if report["exists"] is not None:
            lines.append(("File found", "yes" if report["exists"] else "no"))
        if good:
            lines.append(("Editable here", "yes" if report["editable"]
                          else "no, it is a link"))
            if report["skipped"]:
                lines.append(("Rows ignored",
                              f"{report['skipped']} with no personal number or department"))
        else:
            lines.append(("Error", report["error"]))

        for caption, value in lines:
            line = tk.Frame(body, bg=d.C["surface"])
            line.pack(fill="x", pady=(6, 0))
            tk.Label(line, text=caption, font=d.CAPTION(), fg=d.C["text_2"],
                     bg=d.C["surface"], anchor="w", width=14).pack(side="left")
            tk.Label(line, text=value, font=d.SUB(), fg=d.C["text"],
                     bg=d.C["surface"], anchor="w", justify="left",
                     wraplength=430).pack(side="left", fill="x", expand=True)
        card.fit()

    def _empty_card(self, parent, message):
        card = d.Surface(parent, radius=14, padding=(18, 20), bg=d.C["bg"])
        card.pack(fill="x")
        tk.Label(card.body, text=message, font=d.BODY(), fg=d.C["text_3"],
                 bg=d.C["surface"], anchor="w", justify="left",
                 wraplength=420).pack(fill="x")
        card.fit()

    def _write_users(self, users, message):
        try:
            users_module.save(config_module.load().users_url, users)
        except users_module.UsersError as exc:
            self.user_message.configure(text=str(exc))
            return
        except Exception as exc:  # a locked workbook, a vanished share
            log.exception("could not write the user list")
            self.user_message.configure(
                text=f"The user list could not be saved: {exc}")
            return
        self.show("users")
        self.user_message.configure(text=message)

    def _add_user(self):
        try:
            updated = users_module.add(self._users_cache, self.new_name.get(),
                                       self.new_number.get(), self.new_department.get())
        except users_module.UsersError as exc:
            self.user_message.configure(text=str(exc))
            return
        self._write_users(updated, f"Added {self.new_name.get().strip()}.")

    def _remove_user(self, user):
        note = f"Removed {user.name or user.personal_number}."
        if user.personal_number == self.state.personal_number:
            note += (" That is the person signed in here, so this machine will "
                     "stop alerting at the next run.")
        self._write_users(users_module.remove(self._users_cache, user.personal_number),
                          note)

    # --- lists -------------------------------------------------------------
    def _rows(self, parent, columns, records, empty):
        """One grid for the header and every row, so the columns line up."""
        card = d.Surface(parent, radius=14, padding=(18, 14), bg=d.C["bg"])
        card.pack(fill="x")
        table = card.body
        if not records:
            tk.Label(table, text=empty, font=d.BODY(), fg=d.C["text_3"],
                     bg=d.C["surface"], anchor="w").pack(fill="x", pady=6)
            card.fit()
            return

        grid = tk.Frame(table, bg=d.C["surface"])
        grid.pack(fill="x")
        for index, (title, weight) in enumerate(columns):
            grid.columnconfigure(index, weight=weight)
            tk.Label(grid, text=title.upper(), font=d.font(10, "bold"),
                     fg=d.C["text_3"], bg=d.C["surface"], anchor="w").grid(
                row=0, column=index, sticky="w", pady=(0, 8), padx=(0, 14))

        line = 1
        for record in records:
            tk.Frame(grid, height=1, bg=d.C["hairline"]).grid(
                row=line, column=0, columnspan=len(columns), sticky="ew")
            line += 1
            for index, value in enumerate(record):
                tk.Label(grid, text=value, font=d.SUB(), fg=d.C["text"],
                         bg=d.C["surface"], anchor="w").grid(
                    row=line, column=index, sticky="w", pady=9, padx=(0, 14))
            line += 1
        card.fit()

    def _snoozed(self, parent):
        self._heading(parent, "Snoozed systems",
                      f"A system may be put off at most {MAX_SNOOZES_PER_SYSTEM} times, "
                      f"and at most {MAX_SNOOZE_DAYS} days at a time.")
        records = [(label, until.strftime("%d/%m/%Y"), str(count))
                   for label, until, count in self.state.snoozed_systems()]
        self._rows(parent, [("System", 3), ("Quiet until", 1), ("Times put off", 1)],
                   records, "Nothing is snoozed.")

    def _skipped(self, parent):
        self._heading(parent, "Skipped rows",
                      "These rows hold no readable RO date, so they raise no alert. "
                      "The table owner should correct the cell.")
        records = [(item.get("department", ""), item.get("platform", ""),
                    item.get("value", "") or "(empty)")
                   for item in (self.state.data.get("skipped_rows") or [])]
        self._rows(parent, [("Department", 1), ("Platform", 1), ("RO date cell", 2)],
                   records, "No rows were skipped at the last read.")

    @staticmethod
    def _shorten(text, limit=34):
        """Tk wraps on whitespace only, so a long path has to be cut by hand."""
        text = str(text)
        if len(text) <= limit:
            return text
        head = limit // 2 - 2
        return text[:head] + " … " + text[-(limit - head - 3):]

    def _status(self, parent):
        self._heading(parent, "Status", "What the app knows right now.")
        cfg = config_module.load()
        last_read = self.state.last_read
        lines = [
            ("User", self.state.data.get("name", "") or "not resolved"),
            ("Personal number", self.state.personal_number or "-"),
            ("Department", self.state.department or "-"),
            ("Directory", self.state.directory_status or "matched in the user list"),
            ("User list", self._shorten(cfg.users_url or "(not set)")),
            ("Last table read",
             last_read.strftime("%d/%m/%Y at %H:%M") if last_read else "never"),
            ("Table source", self._shorten(cfg.sharepoint_url or "(not set)")),
            ("Configuration", self._shorten(paths.config_path())),
            ("State", self._shorten(paths.state_path())),
            ("Log", self._shorten(paths.log_path())),
        ]
        card = d.Surface(parent, radius=14, padding=(20, 16), bg=d.C["bg"])
        card.pack(fill="x")
        body = card.body
        for index, (label, value) in enumerate(lines):
            if index:
                tk.Frame(body, height=1, bg=d.C["hairline"]).pack(fill="x", pady=8)
            line = tk.Frame(body, bg=d.C["surface"])
            line.pack(fill="x")
            tk.Label(line, text=label, font=d.SUB(), fg=d.C["text_2"],
                     bg=d.C["surface"], anchor="w", width=15).pack(side="left")
            tk.Label(line, text=value or "-", font=d.SUB(), fg=d.C["text"],
                     bg=d.C["surface"], anchor="w", justify="left",
                     wraplength=340).pack(side="left", fill="x", expand=True)
        card.fit()


def open_maintenance(root, cfg, state):
    prompt = CredentialPrompt(root, cfg)
    root.wait_window(prompt.window)
    if not prompt.ok:
        return False
    window = AdminWindow(root, state)
    root.wait_window(window.window)
    return True
