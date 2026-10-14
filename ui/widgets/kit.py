"""WidgetKit - the reusable controls every page is built from."""

import customtkinter as ctk
from tkinter import ttk

from ui.icons import draw_icon
from ui.theme import F_CAP, F_H2, F_H3, STYLES
from ui.widgets.helpers import Tip


class WidgetKit:
    """wrapped / card / tree / btn / icon / buttons / field / empty_note."""

    # ----- layout helpers -----
    def wrapped(self, parent, **kw):  # label whose text re-wraps to the width of its parent
        lb = ctk.CTkLabel(parent, anchor="w", justify="left", **kw)
        scale = ctk.ScalingTracker.get_window_scaling(parent)
        # CTkLabel wants wraplength in unscaled units while <Configure> reports pixels.
        # Re-setting the same wraplength still relayouts the label, which can resize its parent,
        # which fires <Configure> again: an oscillation that burned 500+ events and over a second
        # of lag every time a dialog opened. Only act when the width actually changed.
        last = []

        def rewrap(*_e):
            want = max(60, (parent.winfo_width() - 40) / scale)
            if last and last[0] == want:
                return
            last[:] = [want]
            lb.configure(wraplength=want)

        parent.bind("<Configure>", rewrap, add=True)
        return lb

    def card(self, parent, title, sub=""):  # rounded panel with a heading
        f = ctk.CTkFrame(parent, fg_color=("white", "#242424"), corner_radius=10)
        ctk.CTkLabel(f, text=title, font=F_H2, anchor="w").pack(fill="x", padx=12, pady=(8, 0))
        if sub:
            self.wrapped(f, text=sub, text_color=("gray40", "#9aa7b3"), font=F_CAP).pack(fill="x", padx=12)
        return f

    def tree(self, parent, cols, heads, widths, height, grow=False):
        f = ctk.CTkFrame(parent, fg_color="transparent")
        f.pack(fill="both", expand=grow, padx=10, pady=4)
        t = ttk.Treeview(f, columns=cols, show="headings", height=height, selectmode="browse")
        # The bar is always there, never shown and hidden again. Hiding it let the tree stretch
        # into the room it left behind, ttk then reported that stretched width as the tree's
        # requested size, and once "winfo reqwidth" caught up the bar was asking for space that
        # no longer existed - Tk gave a zero-width window no room and left it unmapped, so it
        # could never come back. A reserved gutter costs 24px and never lies about the content.
        sb = ctk.CTkScrollbar(f, command=t.yview, height=10)  # default min height is 200px
        t.configure(yscrollcommand=sb.set)

        def wheel(e):
            """The wheel scrolls the table it is over - otherwise the only way down a long
            results table is to drag a thin bar. 'break' stops it reaching anything above,
            so a wheel over a table can never zoom the diagram."""
            d = e.delta
            # Windows reports +-120 a notch; other platforms report +-1 or +-3. Count notches.
            notches = -round(d / 120) if abs(d) > 3 else -d
            if notches:
                t.yview_scroll(int(notches), "units")
            return "break"

        for w in (t, sb):
            w.bind("<MouseWheel>", wheel, add=True)
        for c, h, w in zip(cols, heads, widths):
            t.heading(c, text=h)
            t.column(c, width=w, anchor="center")
        sb.pack(side="right", fill="y")
        t.pack(side="left", fill="both", expand=True)
        return t

    def btn(self, parent, text, cmd, tip, style=None, height=32, width=0):
        kw = dict(zip(("fg_color", "hover_color"), STYLES[style])) if style else {}
        b = ctk.CTkButton(parent, text=text, command=cmd, height=height, width=width or 110,
                          font=F_H3, **kw)
        Tip(b, tip)
        return b

    def icon(self, name, px=18):
        """A drawn icon in both themes - CustomTkinter picks the right one when the mode flips,
        so the toolbar never needs rebuilding on a theme change."""
        if not hasattr(self, "_icons"):
            self._icons = {}
        if name not in self._icons:
            self._icons[name] = ctk.CTkImage(
                light_image=draw_icon(name, "#37474f", px),   # dark ink on a light toolbar
                dark_image=draw_icon(name, "#cfd8dc", px),    # light ink on a dark toolbar
                size=(px, px))
        return self._icons[name]

    def theme_icon(self):
        """Sun while light (you are looking at daylight), moon while dark - swapped by CTk itself."""
        if not hasattr(self, "_icons"):
            self._icons = {}
        if "theme" not in self._icons:
            self._icons["theme"] = ctk.CTkImage(
                light_image=draw_icon("sun", "#37474f", 18),
                dark_image=draw_icon("moon", "#cfd8dc", 18),
                size=(18, 18))
        return self._icons["theme"]

    def icon_btn(self, parent, image, cmd, tip, size=32):
        """Square toolbar button carrying a drawn icon and a tooltip that names it.
        Only for actions whose picture is unambiguous: anything a beginner has to read
        (Step, Add State, ...) stays a labelled button."""
        b = ctk.CTkButton(parent, text="", image=image, command=cmd, width=size, height=size,
                          corner_radius=8, fg_color=("white", "#242424"),
                          hover_color=("#e3f2fd", "#37474f"), border_width=1,
                          border_color=("#d5dbe1", "#3a3a3a"))
        Tip(b, tip)
        return b

    def buttons(self, parent, specs, cols):  # specs: (text, command, tooltip[, style])
        f = ctk.CTkFrame(parent, fg_color="transparent")
        f.pack(fill="x", padx=8, pady=(2, 8))
        made = []
        for i, spec in enumerate(specs):
            b = self.btn(f, *spec)
            b.grid(row=i // cols, column=i % cols, sticky="ew", padx=3, pady=3)
            f.columnconfigure(i % cols, weight=1)
            made.append(b)
        return made  # callers keep the ones they need to grey out

    def field(self, parent, label, widget, col):
        ctk.CTkLabel(parent, text=label).grid(row=0, column=col * 2, padx=(4, 2))
        widget.grid(row=0, column=col * 2 + 1, padx=(0, 6))

    def empty_note(self, parent, text):  # what to do next, shown only while a list is empty
        return self.wrapped(parent, text=text, font=F_CAP, text_color=("gray45", "#8b97a3"))
