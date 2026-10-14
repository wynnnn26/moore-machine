"""The interface: CustomTkinter pages, widgets, dialogs and the diagram.

Importing this package checks for CustomTkinter first, so a missing dependency produces the
same friendly message the single-file version did instead of a traceback. Every module in
here goes through its package, so the check always runs before any widget code does.

Layout:
    theme.py      fonts, button colours, help text, light / dark
    icons.py      icons drawn with PIL
    widgets/      reusable controls (WidgetKit) and small helpers
    pages.py      the window, one builder per panel
    dialogs.py    popups: help, add state, Auto Build
    diagram.py    the picture: draw, highlight, zoom, pan, drag, export
    app.py        App - machine state, notifications, editing, simulation
"""
import sys

try:
    import customtkinter as ctk  # noqa: F401  (re-exported: `from ui import ctk`)
except ImportError:
    sys.exit("This program needs CustomTkinter. Install it with:  pip install customtkinter")
