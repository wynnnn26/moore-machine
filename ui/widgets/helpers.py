"""Small pieces the interface leans on: safe widget checks, a scrollbar that reports its own
gutter, and hover tips."""

import tkinter as tk

import customtkinter as ctk


def winfo_exists(w):
    """True while a widget still exists - scroll callbacks outlive their widget on teardown."""
    try:
        return bool(w.winfo_exists())
    except tk.TclError:
        return False


def auto_hide_bar(sf):
    """Draw a CTkScrollableFrame's bar only while its content is taller than the view.

    CustomTkinter always grids the bar, so with a short list the user gets a strip that does
    nothing. The check runs on both the content frame and the viewport, so it re-evaluates when
    rows are added or removed and when the window is resized."""
    try:
        pf, cv = sf._parent_frame, sf._parent_canvas
        bar = next(c for c in pf.winfo_children() if c.__class__.__name__ == "CTkScrollbar")
        info = bar.grid_info()
    except (AttributeError, StopIteration, tk.TclError):
        return None  # CustomTkinter changed shape - leave its built-in behaviour alone

    def sync(*_):
        if not winfo_exists(bar) or not winfo_exists(cv):
            return
        need = sf.winfo_reqheight() > cv.winfo_height() + 1
        # "packed" rather than "mapped": at the first <Map> the children are not mapped yet,
        # so the mapped answer arrives a beat too early and the bar would stand there forever.
        if need != (bar.winfo_manager() == "grid"):
            if need:
                bar.grid(**info)
            else:
                bar.grid_forget()

    cv.bind("<Configure>", sync, add=True)
    sf.bind("<Configure>", sync, add=True)
    # The content maps a beat after the frame does, so a bar decided at <Map> time can be a
    # decision about a half-laid-out panel. Re-check once Tk has finished and on every remap -
    # a bar wrongly left hidden is content the user cannot reach at all.
    sf.bind("<Map>", lambda _e: sf.after_idle(sync), add=True)
    sf.after_idle(sync)
    sync()
    return bar


class Tip:
    """Tiny hover tooltip (CustomTkinter, so it matches the rest of the UI)."""
    def __init__(self, widget, text):
        self.w, self.text, self.tw = widget, text, None
        widget._tip = self  # keeps the explanation reachable for anything that needs to read it
        widget.bind("<Enter>", self.show)
        widget.bind("<Leave>", self.hide)

    def show(self, e):
        self.hide(None)  # Enter can fire twice without a Leave: never stack two tooltips
        self.tw = tk.Toplevel(self.w)
        self.tw.wm_overrideredirect(True)
        self.tw.attributes("-topmost", True)
        self.tw.geometry(f"+{e.x_root + 12}+{e.y_root + 14}")
        ctk.CTkLabel(self.tw, text=self.text, fg_color=("#fffbe6", "#3a3720"),
                     text_color=("black", "white"), corner_radius=6, border_width=1,
                     border_color=("#e0d8a8", "#6b6540"), justify="left", wraplength=280,
                     padx=10, pady=6).pack()

    def hide(self, _):
        if self.tw:
            try:
                self.tw.destroy()
            except tk.TclError:
                pass
            self.tw = None
