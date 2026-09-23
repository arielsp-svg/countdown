"""The look of the app.

Everything is drawn on a canvas rather than themed with ttk, for three reasons:
ttk cannot round a corner, its widgets look different on every platform, and
R13 rules out a widget toolkit as a dependency. What is here is a small set of
pieces - surfaces, buttons, fields, a select - built only on tkinter.

The vocabulary is Apple's: a lot of quiet space, one accent colour used
sparingly, type that carries the hierarchy instead of borders and boxes.
"""
import sys
import tkinter as tk
from tkinter import font as tkfont

# --- colour ---------------------------------------------------------------

LIGHT = {
    "bg": "#F5F5F7",          # the window itself
    "surface": "#FFFFFF",     # cards sitting on it
    "surface_sunken": "#F0F0F3",
    "text": "#1D1D1F",
    "text_2": "#6E6E73",
    "text_3": "#9A9AA0",
    "hairline": "#E0E0E5",
    "field": "#FFFFFF",
    "field_line": "#D8D8DE",
    "accent": "#0071E3",
    "accent_hover": "#0A84FF",
    "accent_press": "#0059B3",
    "accent_wash": "#EAF3FD",
    "on_accent": "#FFFFFF",
    "danger": "#E5342A",
    "warn": "#C77700",
    "warn_wash": "#FFF4E0",
    "ok": "#1D9E4B",
    "overlay": "#00000022",
}

DARK = {
    "bg": "#1C1C1E",
    "surface": "#2C2C2E",
    "surface_sunken": "#242426",
    "text": "#F5F5F7",
    "text_2": "#A1A1A6",
    "text_3": "#7C7C81",
    "hairline": "#3A3A3C",
    "field": "#1C1C1E",
    "field_line": "#48484A",
    "accent": "#0A84FF",
    "accent_hover": "#3D9BFF",
    "accent_press": "#0060CC",
    "accent_wash": "#16324F",
    "on_accent": "#FFFFFF",
    "danger": "#FF6961",
    "warn": "#FFB340",
    "warn_wash": "#3A2C12",
    "ok": "#30D158",
    "overlay": "#00000055",
}

C = dict(LIGHT)


def use_theme(name: str) -> None:
    C.clear()
    C.update(DARK if name == "dark" else LIGHT)


def windows_prefers_dark() -> bool:
    """Follow the Windows light/dark setting, the way a native app would."""
    if not sys.platform.startswith("win"):
        return False
    try:
        import winreg
        key = r"Software\Microsoft\Windows\CurrentVersion\Themes\Personalize"
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, key) as handle:
            return not winreg.QueryValueEx(handle, "AppsUseLightTheme")[0]
    except (ImportError, OSError):
        return False


def adopt_system_theme() -> None:
    use_theme("dark" if windows_prefers_dark() else "light")


# --- type -----------------------------------------------------------------

FAMILY_PREFERENCE = [
    "Segoe UI Variable Display", "Segoe UI",     # Windows
    "SF Pro Display", "SF Pro Text", "Helvetica Neue",  # macOS
    "Inter", "DejaVu Sans",                       # Linux
]

_family = None


def family() -> str:
    """The best available face, so the app looks native wherever it runs."""
    global _family
    if _family is None:
        try:
            available = set(tkfont.families())
        except tk.TclError:
            available = set()
        _family = next((f for f in FAMILY_PREFERENCE if f in available), "TkDefaultFont")
    return _family


def font(size=13, weight="normal"):
    return (family(), size, weight) if weight != "normal" else (family(), size)


DISPLAY = lambda: font(26, "bold")
TITLE = lambda: font(19, "bold")
HEADLINE = lambda: font(14, "bold")
BODY = lambda: font(13)
SUB = lambda: font(12)
CAPTION = lambda: font(11)


# --- geometry -------------------------------------------------------------

def rounded(canvas, x1, y1, x2, y2, radius, **kwargs):
    """A rounded rectangle with corners that stay crisp at any size."""
    radius = max(0, min(radius, (x2 - x1) / 2, (y2 - y1) / 2))
    steps = 6
    points = []
    corners = [
        (x2 - radius, y1 + radius, -90, 0),
        (x2 - radius, y2 - radius, 0, 90),
        (x1 + radius, y2 - radius, 90, 180),
        (x1 + radius, y1 + radius, 180, 270),
    ]
    import math
    for cx, cy, start, end in corners:
        for i in range(steps + 1):
            angle = math.radians(start + (end - start) * i / steps)
            points.extend([cx + radius * math.cos(angle), cy + radius * math.sin(angle)])
    return canvas.create_polygon(points, smooth=False, **kwargs)


def present(window, master=None, width=None, height=None) -> None:
    """Size a window to its content and place it in the upper third.

    `transient` is only set when the master is actually on screen: pointing a
    transient window at the hidden root leaves it unmapped on macOS, which shows
    as a window with nothing in it.
    """
    window.update_idletasks()
    width = width or window.winfo_reqwidth()
    height = height or window.winfo_reqheight()
    x = (window.winfo_screenwidth() - width) // 2
    y = max((window.winfo_screenheight() - height) // 3, 20)
    window.geometry(f"{width}x{height}+{max(x, 0)}+{y}")
    if master is not None and master.winfo_viewable():
        window.transient(master)


def dress(window) -> None:
    """Common setup for every window the app shows."""
    window.configure(bg=C["bg"])
    try:
        window.tk.call("tk", "scaling", window.tk.call("tk", "scaling"))
    except tk.TclError:
        pass


# --- pieces ---------------------------------------------------------------

class Surface(tk.Canvas):
    """A rounded card. Put content into `.body`."""

    def __init__(self, master, radius=14, fill=None, padding=(20, 18), outline=None, **kw):
        super().__init__(master, highlightthickness=0, bd=0,
                         bg=kw.pop("bg", C["bg"]), **kw)
        self._radius = radius
        self._fill = fill or C["surface"]
        self._outline = outline
        self._shape = None
        self.body = tk.Frame(self, bg=self._fill)
        self._window = self.create_window(0, 0, window=self.body, anchor="nw")
        self._padding = padding
        self.bind("<Configure>", self._redraw)

    def _redraw(self, event=None):
        width, height = self.winfo_width(), self.winfo_height()
        if self._shape:
            self.delete(self._shape)
        self._shape = rounded(self, 0, 0, width, height, self._radius,
                              fill=self._fill,
                              outline=self._outline or self._fill,
                              width=1)
        self.tag_lower(self._shape)
        px, py = self._padding
        self.coords(self._window, px, py)
        self.itemconfigure(self._window, width=max(width - px * 2, 1),
                           height=max(height - py * 2, 1))

    def fit(self):
        """Grow the canvas to whatever the body needs."""
        self.body.update_idletasks()
        px, py = self._padding
        self.configure(width=self.body.winfo_reqwidth() + px * 2,
                       height=self.body.winfo_reqheight() + py * 2)


class Button(tk.Canvas):
    """A pill button. `kind` is filled, tinted or plain."""

    HEIGHT = 38

    def __init__(self, master, text, command=None, kind="filled", width=None,
                 bg=None, danger=False, stretch=False):
        self.kind = kind
        self._stretch = stretch
        self.danger = danger
        self._bg = bg or C["bg"]
        self._text = text
        self._command = command
        self._enabled = True
        self._state = "idle"

        face = font(13, "bold" if kind == "filled" else "normal")
        probe = tkfont.Font(font=face)
        self._width = width or probe.measure(text) + (44 if kind != "plain" else 20)
        super().__init__(master, width=self._width, height=self.HEIGHT,
                         highlightthickness=0, bd=0, bg=self._bg)
        self._face = face
        self._shape = None
        self._label = None
        self._draw()
        if stretch:
            self.bind("<Configure>", self._restretch)
        self.bind("<Enter>", lambda _e: self._set("hover"))
        self.bind("<Leave>", lambda _e: self._set("idle"))
        self.bind("<ButtonPress-1>", lambda _e: self._set("press"))
        self.bind("<ButtonRelease-1>", self._release)

    def _colours(self):
        accent = C["danger"] if self.danger else C["accent"]
        if not self._enabled:
            # A plain button has no pill to grey out; it just goes quiet.
            if self.kind == "plain":
                return self._bg, C["text_3"]
            return C["surface_sunken"], C["text_3"]
        if self.kind == "filled":
            fill = {"idle": accent,
                    "hover": C["accent_hover"] if not self.danger else accent,
                    "press": C["accent_press"] if not self.danger else accent}[self._state]
            return fill, C["on_accent"]
        if self.kind == "tinted":
            fill = C["accent_wash"] if self._state != "press" else C["field_line"]
            return fill, accent
        return (self._bg if self._state == "idle" else C["accent_wash"]), accent

    def _draw(self):
        fill, ink = self._colours()
        if self._shape:
            self.delete(self._shape)
        if self._label:
            self.delete(self._label)
        self._shape = rounded(self, 1, 1, self._width - 1, self.HEIGHT - 1,
                              self.HEIGHT / 2, fill=fill, outline=fill)
        self._label = self.create_text(self._width / 2, self.HEIGHT / 2 + 1,
                                       text=self._text, fill=ink, font=self._face)
        self.configure(cursor="hand2" if self._enabled else "arrow")

    def _restretch(self, event):
        if event.width > 1 and event.width != self._width:
            self._width = event.width
            self._draw()

    def _set(self, state):
        if not self._enabled:
            return
        self._state = state
        self._draw()

    def _release(self, _event):
        if not self._enabled:
            return
        self._set("hover")
        if self._command:
            self._command()

    def set_enabled(self, enabled: bool):
        self._enabled = enabled
        self._state = "idle"
        self._draw()

    def set_text(self, text: str):
        self._text = text
        self._draw()


class Field(tk.Frame):
    """A rounded text field with a focus ring."""

    HEIGHT = 42

    def __init__(self, master, textvariable, show=None, bg=None, width=300):
        self._bg = bg or C["bg"]
        super().__init__(master, bg=self._bg, height=self.HEIGHT, width=width)
        self.pack_propagate(False)
        self.canvas = tk.Canvas(self, height=self.HEIGHT, width=width,
                                highlightthickness=0, bd=0, bg=self._bg)
        self.canvas.pack(fill="both", expand=True)
        self._shape = None
        self._focused = False
        self.entry = tk.Entry(
            self.canvas, textvariable=textvariable, show=show,
            bd=0, relief="flat", bg=C["field"], fg=C["text"],
            insertbackground=C["accent"], font=BODY(),
            highlightthickness=0, justify="left",
        )
        self._embedded = self.canvas.create_window(14, self.HEIGHT / 2,
                                                   window=self.entry, anchor="w")
        self.canvas.bind("<Configure>", self._redraw)
        self.entry.bind("<FocusIn>", lambda _e: self._focus(True))
        self.entry.bind("<FocusOut>", lambda _e: self._focus(False))
        self.canvas.bind("<Button-1>", lambda _e: self.entry.focus_set())

    def _focus(self, focused):
        self._focused = focused
        self._redraw()

    def _redraw(self, _event=None):
        width = self.canvas.winfo_width() or self.canvas["width"]
        if self._shape:
            self.canvas.delete(self._shape)
        self._shape = rounded(self.canvas, 1, 1, width - 1, self.HEIGHT - 1, 10,
                              fill=C["field"],
                              outline=C["accent"] if self._focused else C["field_line"],
                              width=2 if self._focused else 1)
        self.canvas.tag_lower(self._shape)
        self.canvas.itemconfigure(self._embedded, width=max(width - 28, 10))


class Select(tk.Canvas):
    """A closed list. Opens a floating panel of choices."""

    HEIGHT = 42

    def __init__(self, master, values, variable, placeholder="Choose", bg=None, width=300):
        self._bg = bg or C["bg"]
        super().__init__(master, height=self.HEIGHT, width=width,
                         highlightthickness=0, bd=0, bg=self._bg, cursor="hand2")
        self.values = list(values)
        self.variable = variable
        self.placeholder = placeholder
        self._open = False
        self._popup = None
        self._items = []
        self.bind("<Configure>", self._redraw)
        self.bind("<Button-1>", lambda _e: self.toggle())
        variable.trace_add("write", lambda *_: self._redraw())

    def _redraw(self, _event=None):
        self.delete("all")
        width = self.winfo_width() or int(self["width"])
        rounded(self, 1, 1, width - 1, self.HEIGHT - 1, 10,
                fill=C["field"],
                outline=C["accent"] if self._open else C["field_line"],
                width=2 if self._open else 1)
        chosen = self.variable.get()
        self.create_text(14, self.HEIGHT / 2, anchor="w",
                         text=chosen or self.placeholder,
                         fill=C["text"] if chosen else C["text_3"], font=BODY())
        cx, cy = width - 20, self.HEIGHT / 2
        self.create_line(cx - 5, cy - 2, cx, cy + 3, fill=C["text_2"], width=2,
                         capstyle="round")
        self.create_line(cx, cy + 3, cx + 5, cy - 2, fill=C["text_2"], width=2,
                         capstyle="round")

    def toggle(self):
        self.close() if self._open else self.open()

    def open(self):
        if self._open or not self.values:
            return
        self._open = True
        self._redraw()
        width = self.winfo_width()
        row = 36
        height = min(len(self.values), 7) * row + 12
        self._popup = tk.Toplevel(self)
        self._popup.overrideredirect(True)
        self._popup.configure(bg=C["hairline"])
        x = self.winfo_rootx()
        y = self.winfo_rooty() + self.HEIGHT + 6
        self._popup.geometry(f"{width}x{height}+{x}+{y}")
        canvas = tk.Canvas(self._popup, bg=C["surface"], highlightthickness=0, bd=0)
        canvas.pack(fill="both", expand=True, padx=1, pady=1)

        for index, value in enumerate(self.values):
            top = 6 + index * row
            tag = f"row{index}"
            canvas.create_rectangle(4, top, width - 4, top + row, fill=C["surface"],
                                    outline=C["surface"], tags=tag)
            canvas.create_text(16, top + row / 2, anchor="w", text=value,
                               fill=C["text"], font=BODY(), tags=tag)
            if value == self.variable.get():
                canvas.create_text(width - 20, top + row / 2, anchor="e", text="✓",
                                   fill=C["accent"], font=font(13, "bold"), tags=tag)
            canvas.tag_bind(tag, "<Button-1>", lambda _e, v=value: self._choose(v))

        # A transparent rectangle on top of each row carries the hover and the
        # click, so the highlight can sit behind the text without hiding it.
        for index in range(len(self.values)):
            top = 6 + index * row
            rect = canvas.create_rectangle(4, top, width - 4, top + row,
                                           fill="", outline="", tags=f"hit{index}")
            canvas.tag_bind(f"hit{index}", "<Enter>",
                            lambda _e, i=index, c=canvas, w=width, r=row: self._hover(c, i, w, r, True))
            canvas.tag_bind(f"hit{index}", "<Leave>",
                            lambda _e, i=index, c=canvas, w=width, r=row: self._hover(c, i, w, r, False))
            canvas.tag_bind(f"hit{index}", "<Button-1>",
                            lambda _e, v=self.values[index]: self._choose(v))
            canvas.tag_raise(rect)
        self._canvas = canvas
        self._popup.bind("<FocusOut>", lambda _e: self.close())
        self._popup.focus_set()

    def _hover(self, canvas, index, width, row, on):
        top = 6 + index * row
        canvas.delete(f"hl{index}")
        if on:
            item = rounded(canvas, 6, top + 1, width - 6, top + row - 1, 8,
                           fill=C["accent_wash"], outline=C["accent_wash"],
                           tags=f"hl{index}")
            canvas.tag_lower(item)

    def _choose(self, value):
        self.variable.set(value)
        self.close()

    def close(self):
        self._open = False
        if self._popup is not None:
            self._popup.destroy()
            self._popup = None
        self._redraw()


class ScrollArea(tk.Frame):
    """A vertically scrolling region. Put content into `.body`.

    The scrollbar only appears when the content is actually taller than the
    window, so a short tab looks exactly as it did before.
    """

    def __init__(self, master, bg=None, **kw):
        self._bg = bg or C["bg"]
        super().__init__(master, bg=self._bg, **kw)
        self.canvas = tk.Canvas(self, bg=self._bg, highlightthickness=0, bd=0)
        self.canvas.pack(side="left", fill="both", expand=True)

        self.bar = tk.Scrollbar(self, orient="vertical", command=self.canvas.yview,
                                width=12, troughcolor=self._bg, bd=0,
                                highlightthickness=0, relief="flat")
        self.canvas.configure(yscrollcommand=self._on_scroll)

        self.body = tk.Frame(self.canvas, bg=self._bg)
        self._window = self.canvas.create_window(0, 0, window=self.body, anchor="nw")
        self.body.bind("<Configure>", self._body_resized)
        self.canvas.bind("<Configure>", self._canvas_resized)
        for widget in (self, self.canvas, self.body):
            widget.bind("<Enter>", self._grab_wheel)
            widget.bind("<Leave>", self._release_wheel)

    def _on_scroll(self, first, last):
        # Show the bar only when there is something to scroll to.
        if float(first) <= 0.0 and float(last) >= 1.0:
            self.bar.pack_forget()
        else:
            self.bar.pack(side="right", fill="y")
        self.bar.set(first, last)

    def _body_resized(self, _event=None):
        self.canvas.configure(scrollregion=self.canvas.bbox("all"))

    def _canvas_resized(self, event):
        self.canvas.itemconfigure(self._window, width=event.width)

    # Wheel events go to whatever the pointer is over, so they are bound while
    # the pointer is inside and released when it leaves.
    def _grab_wheel(self, _event=None):
        self.canvas.bind_all("<MouseWheel>", self._wheel)       # Windows, macOS
        self.canvas.bind_all("<Button-4>", self._wheel)         # X11
        self.canvas.bind_all("<Button-5>", self._wheel)

    def _release_wheel(self, _event=None):
        for sequence in ("<MouseWheel>", "<Button-4>", "<Button-5>"):
            self.canvas.unbind_all(sequence)

    def _wheel(self, event):
        first, last = self.canvas.yview()
        if first <= 0.0 and last >= 1.0:
            return
        if getattr(event, "num", None) == 4:
            step = -1
        elif getattr(event, "num", None) == 5:
            step = 1
        else:
            step = -1 if event.delta > 0 else 1
        self.canvas.yview_scroll(step, "units")


def label(master, text, style=None, fg=None, bg=None, **kw):
    return tk.Label(master, text=text, font=style or BODY(),
                    fg=fg or C["text"], bg=bg or C["surface"],
                    anchor="w", justify="left", **kw)


def hairline(master, bg=None):
    return tk.Frame(master, height=1, bg=C["hairline"])
