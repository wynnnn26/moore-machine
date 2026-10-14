"""UI pages: the window is assembled here, one builder per panel.

build() owns the window itself - title, size, ttk table style, grid weights - and then
hands each panel to its own method. The pages only share local variables they pass
explicitly: the root window in, and (sm, rowf) from Simulation to Simulation Output.
"""

import customtkinter as ctk
import tkinter as tk
from tkinter import ttk

from ui.theme import FONT_B, F_BODY, F_CAP, F_H2, F_H3
from ui.widgets.helpers import Tip, auto_hide_bar


class PagesMixin:
    """Builds the window and swaps panels in and out."""

    def build(self):
        r = self.root
        r.title("Moore Machine Simulator")
        r.geometry("1240x680+20+4")  # explicit position: otherwise Windows cascades it off-screen
        r.minsize(1180, 620)
        def zoom():  # start maximized so every panel (editor, diagram, table) is visible; the
            # window manager only honours this once the window is mapped, and the PyInstaller
            # windowed build gets mapped later than plain python does - so ask again shortly
            # after start-up instead of trusting the first attempt.
            try:
                r.state("zoomed")
            except tk.TclError:
                pass  # platform without window zooming keeps the sized window above
        zoom()
        r.after(400, zoom)
        sty = ttk.Style()  # the tables are ttk Treeviews: style them to match
        sty.theme_use("clam")
        sty.configure("Treeview", rowheight=26, font=F_CAP, background="white", fieldbackground="white", borderwidth=0)
        sty.configure("Treeview.Heading", font=("Arial", 11, "bold"), background="#e8eef4", relief="flat")
        sty.map("Treeview", background=[("selected", "#1f6aa5")], foreground=[("selected", "white")])
        r.columnconfigure(1, weight=1)
        r.rowconfigure(1, weight=1)   # the diagram is the primary view: it absorbs every spare pixel.
        # row 2 is left at weight 0 so the simulation panel takes exactly what it needs and never
        # squeezes the results table; any spare height goes to the picture instead.

        self.build_topbar(r)
        self.build_editor(r)
        self.build_diagram(r)
        sm, rowf = self.build_simulation(r)
        self.build_output(sm, rowf)


    def build_topbar(self, r):
        # ---------- top bar: what to do next + grouped file / view / destructive buttons.
        # Grouped and separated so the eye can find a category; icons carry the actions whose
        # picture is universal, while anything that changes data stays as a word.
        bar = ctk.CTkFrame(r, fg_color=("#e3f2fd", "#0d1b2a"), corner_radius=10)
        bar.grid(row=0, column=0, columnspan=2, sticky="ew", padx=8, pady=(8, 2))
        self.hint = tk.StringVar()
        hf = ctk.CTkFrame(bar, fg_color="transparent")
        hf.pack(side="left", fill="x", expand=True, padx=8, pady=6)
        self.wrapped(hf, textvariable=self.hint, text_color=("#0d47a1", "#90caf9"), font=("Arial", 13, "bold")).pack(fill="x")

        grp = ctk.CTkFrame(bar, fg_color="transparent")
        grp.pack(side="right", padx=(8, 10), pady=6)

        def sep():  # thin rule between categories.
            # height is NOT optional here: an empty CTkFrame asks for 200pt (300px at 150%),
            # so without it each rule forces the whole bar to 330px and starves the diagram row.
            ctk.CTkFrame(grp, fg_color=("#c9d4de", "#39414a"), width=1, height=16).pack(
                side="right", fill="y", padx=10, pady=4)

        # packed right-to-left, so this order reads left-to-right on screen
        self.btn(grp, "Clear Machine", self.clear,
                 "Delete EVERY state and transition (always asks first). "
                 "To restart only the simulation, press Reset Simulation.", "danger",
                 width=130).pack(side="right")
        sep()
        self.btn(grp, "Load Example", self.load_example,
                 "Two-state example: q0/0 and q1/1, input 10110. "
                 "Loads instantly so you can press Run.", "go", width=126).pack(side="right")
        self.icon_btn(grp, self.theme_icon(), self.toggle_theme,
                      "Light / dark mode - switch the whole app between light and dark.",
                      size=32).pack(side="right", padx=(0, 6))
        self.icon_btn(grp, self.icon("help"), self.show_help,
                      "Help - the short 8-step beginner guide.", size=32).pack(side="right", padx=3)
        sep()
        self.icon_btn(grp, self.icon("image"), self.export_png,
                      "Export PNG - save the machine diagram as a picture file.",
                      size=32).pack(side="right", padx=3)
        self.icon_btn(grp, self.icon("open"), self.load,
                      "Load JSON - open a machine saved by this program.",
                      size=32).pack(side="right", padx=3)
        self.icon_btn(grp, self.icon("save"), self.save,
                      "Save JSON - save states, outputs, transitions and the start state to a file.",
                      size=32).pack(side="right", padx=3)


    def build_editor(self, r):
        # ---------- 1. Build sidebar (left column).
        # The column is a plain frame with the scrollable stack inside it, so the notification
        # overlay has a surface of its own to sit on and never lands on the diagram.
        left = ctk.CTkFrame(r, fg_color="transparent")
        left.grid(row=1, column=0, rowspan=2, sticky="ns", padx=(8, 0), pady=4)
        self.notice_host = left
        # a click anywhere outside the notification overlay closes it (never the other way round)
        r.bind("<Button-1>", self._notice_hit, add=True)
        ed = ctk.CTkScrollableFrame(left, fg_color="transparent", width=320)
        ed.pack(fill="both", expand=True)
        auto_hide_bar(ed)   # a bar that is always drawn is the "unnecessary nested scrollbar"
        mh = ctk.CTkFrame(ed, fg_color="transparent")
        mh.pack(fill="x", padx=12, pady=(2, 4))
        ctk.CTkLabel(mh, text="Machine Editor", font=F_H2, anchor="w").pack(side="left")

        # group 0 - build the whole machine at once
        c0 = self.card(ed, "Machine", "Make the whole machine from an input string and its output.")
        c0.pack(fill="x", pady=(0, 6))
        self.btn(c0, "Auto Build...", self.auto_build_dialog,
                 "Type the symbols the machine should read and what should come out - the program "
                 "works out the states and transitions for you. The only thing left to edit is "
                 "each state's name.", "go"
                 ).pack(fill="x", padx=8, pady=(6, 8))

        # group 1 - states
        c1 = self.card(ed, "States", "Every state has exactly one output. Click a row to load it for editing.")
        c1.pack(fill="x", pady=(0, 6))
        self.st = self.tree(c1, ("n", "o", "i"), ("State", "Output", "Initial"), (100, 70, 70), 3)
        self.st.bind("<<TreeviewSelect>>", self.pick_state)
        # names the row you are editing - the blue highlight on its own is easy to miss
        self.st_sel = tk.StringVar(value="")
        self.st_sel_lbl = self.wrapped(c1, textvariable=self.st_sel, font=F_CAP,
                                       text_color=("gray45", "#8b97a3"))
        self.st_sel_lbl.pack(fill="x", padx=12, pady=(0, 2))
        self.st_empty = self.empty_note(
            c1, "No states yet. Type a name and an output below and press Add State, "
                "or press Auto Build to make a machine from an input string and its output.")
        self.name, self.out = tk.StringVar(), tk.StringVar()
        f = ctk.CTkFrame(c1, fg_color="transparent")
        f.pack(fill="x", padx=6, pady=2)
        self.name_entry = ctk.CTkEntry(f, textvariable=self.name, width=90, height=30, placeholder_text="q0")
        oe = ctk.CTkEntry(f, textvariable=self.out, width=70, height=30, placeholder_text="0")
        self.field(f, "Name", self.name_entry, 0)
        self.field(f, "Output", oe, 1)
        for w in (self.name_entry, oe):
            w.bind("<Return>", lambda e: self.add_state())
        self.btn_state = dict(zip(("add", "edit", "delete", "initial"), self.buttons(c1, [
            ("Add State", self.add_state_dialog, "Open a simple dialog: State Name + Output. "
                                                 "(Or type in the two boxes above and press Enter.)"),
            ("Edit State", self.edit_state, "Select a state in the list, change the boxes, then click this. "
                                            "Renaming updates its transitions too.", "plain"),
            ("Delete State", self.del_state, "Removes the selected state AND every transition touching it (asks first).", "danger"),
            ("Set as Initial State", self.set_initial, "Make the selected state the start state - it gets the "
                                                  "big green arrow and the ring in the diagram.", "go"),
        ], 2)))

        c2 = self.card(ed, "Transitions",
                       "From  --input symbol-->  To, one symbol per transition. "
                       "Click a row to load it for editing.")
        c2.pack(fill="x")
        self.tt = self.tree(c2, ("s", "a", "d"), ("From", "Input", "To"), (80, 60, 80), 2)
        self.tt.bind("<<TreeviewSelect>>", self.pick_trans)
        # same idea here: spells out which transition Edit / Delete will act on
        self.tt_sel = tk.StringVar(value="")
        self.tt_sel_lbl = self.wrapped(c2, textvariable=self.tt_sel, font=F_CAP,
                                       text_color=("gray45", "#8b97a3"))
        self.tt_sel_lbl.pack(fill="x", padx=12, pady=(0, 2))
        self.tt_empty = self.empty_note(
            c2, "No transitions yet. Pick From, type ONE input symbol, pick To, then press Add Transition.")
        self.src, self.sym, self.dst = tk.StringVar(), tk.StringVar(), tk.StringVar()
        form = ctk.CTkFrame(c2, fg_color="transparent")
        form.pack(fill="x", padx=10, pady=(4, 2))
        cs = ctk.CTkComboBox(form, variable=self.src, values=[], state="readonly", height=30)
        cd = ctk.CTkComboBox(form, variable=self.dst, values=[], state="readonly", height=30)
        se = ctk.CTkEntry(form, textvariable=self.sym, height=30, font=("Consolas", 13),
                          placeholder_text="e.g. 0")
        se.bind("<Return>", lambda e: self.add_trans())
        self.combos = (cs, cd)
        for i, (lab, wid) in enumerate((("From State", cs), ("Input", se), ("To State", cd))):
            ctk.CTkLabel(form, text=lab, anchor="w", font=F_CAP,
                         text_color=("gray35", "#9aa7b3")).grid(row=i, column=0, sticky="w", padx=(2, 8))
            wid.grid(row=i, column=1, sticky="ew", pady=(0, 4))
        form.columnconfigure(1, weight=1)
        self.btn_tr = dict(zip(("add", "edit", "delete"), self.buttons(c2, [
            ("Add Transition", self.add_trans, "Pick From, type ONE input symbol, pick To. "
                                               "Each state allows only one transition per symbol (or press Enter)."),
            ("Edit Transition", self.edit_trans, "Select a transition in the list, change the boxes, then click this.", "plain"),
            ("Delete Transition", self.del_trans, "Removes the selected transition.", "danger"),
        ], 2)))


    def build_diagram(self, r):
        # ---------- 2. Machine Diagram (top right, scrollable + zoomable + draggable)
        dg = ctk.CTkFrame(r, fg_color=("white", "#242424"), corner_radius=10)
        dg.grid(row=1, column=1, sticky="nsew", padx=8, pady=4)
        hdr = ctk.CTkFrame(dg, fg_color="transparent")
        hdr.pack(fill="x", padx=12, pady=(6, 0))
        ctk.CTkLabel(hdr, text="Machine Diagram", font=F_H2, anchor="w").pack(side="left")
        Tip(hdr, "Circle = one state: its name on top, its own output below in blue. "
                 "Pale blue = the state you just left. Drag a state to move it.")
        # the colour key lives on the header row, so the canvas keeps the whole row below it
        lg = ctk.CTkFrame(hdr, fg_color="transparent")
        lg.pack(side="left", padx=(18, 0))
        for dot, label, col in (
                ("●", "state", ("#111827", "#d0d0d0")),
                ("→", "start state", ("#2e7d32", "#66bb6a")),
                ("●", "current state", ("#e65100", "#ffd54f")),
                ("→", "arrow just taken", ("#bf360c", "#ff8a65"))):
            item = ctk.CTkFrame(lg, fg_color="transparent")
            item.pack(side="left", padx=(0, 10))
            ctk.CTkLabel(item, text=dot, text_color=col, font=("Arial", 14, "bold")).pack(side="left")
            ctk.CTkLabel(item, text=label, font=F_CAP, text_color=("gray35", "#9aa7b3")).pack(
                side="left", padx=(4, 0))
        zb = ctk.CTkFrame(hdr, fg_color="transparent")
        zb.pack(side="right")
        # Panel size: collapse the diagram to its header, or give it the whole column. These
        # change the panel, not the window, and never touch the machine or the run in progress.
        self.min_btn = self.icon_btn(
            zb, self.icon("panel_min"), lambda: self.set_panel("min"),
            "Minimize diagram - collapse the picture to just this header and let the Simulation "
            "panel grow into the space. Click again to restore it.")
        self.max_btn = self.icon_btn(
            zb, self.icon("panel_max"), lambda: self.set_panel("max"),
            "Maximize diagram - collapse the Simulation panel so the picture gets the whole "
            "column. Click again to bring the Simulation panel back.")
        self.min_btn.pack(side="left", padx=(0, 3))
        self.max_btn.pack(side="left", padx=3)
        ctk.CTkFrame(zb, fg_color=("#c9d4de", "#39414a"), width=1, height=20).pack(
            side="left", fill="y", padx=6, pady=3)
        for image, cmd, tip in (
                (self.icon("zoom_out"), self.zoom_out, "Zoom out - make the diagram smaller."),
                (self.icon("zoom_in"), self.zoom_in, "Zoom in - make the diagram bigger."),
                (self.icon("fit"), self.fit_diagram,
                 "Fit diagram - resize it so the whole machine fits the window.")):
            self.icon_btn(zb, image, cmd, tip, size=30).pack(side="left", padx=3)
        self.zoomlbl = ctk.CTkLabel(zb, text="100%", font=F_BODY, width=48,
                                    text_color=("gray40", "#9aa7b3"))
        self.zoomlbl.pack(side="left", padx=(6, 0))

        body = ctk.CTkFrame(dg, fg_color="transparent")
        body.pack(fill="both", expand=True, padx=8, pady=(4, 6))
        self.cv = tk.Canvas(body, bg="white", highlightthickness=1, highlightbackground="#cfd8dc")
        sy = ctk.CTkScrollbar(body, orientation="vertical", command=self.cv.yview, height=10)
        sx = ctk.CTkScrollbar(body, orientation="horizontal", command=self.cv.xview, height=10)
        self.cv.configure(xscrollcommand=sx.set, yscrollcommand=sy.set)
        self.cv.grid(row=0, column=0, sticky="nsew")
        sy.grid(row=0, column=1, sticky="ns")
        sx.grid(row=1, column=0, sticky="ew")
        body.rowconfigure(0, weight=1)
        body.columnconfigure(0, weight=1)
        self.cv.bind("<ButtonPress-1>", self.drag_start)
        self.cv.bind("<B1-Motion>", self.drag_move)
        self.cv.bind("<ButtonRelease-1>", self.drag_end)
        self.cv.bind("<Configure>", lambda _: self.draw())
        # The wheel is bound on the canvas alone, so scrolling a table or the sidebar never
        # zooms the picture. Plain wheel pans, Ctrl+wheel zooms in at the pointer.
        self.cv.bind("<MouseWheel>", self.on_wheel, add=True)
        for bar in (sx, sy):
            bar.bind("<MouseWheel>", self.on_wheel, add=True)   # wheel over the bar pans too
        self._dg_body, self._dg_card = body, dg


    def build_simulation(self, r):
        # ---------- Simulation (bottom right)
        sm = self.card(r, "Simulation")
        sm.grid(row=2, column=1, sticky="nsew", padx=8, pady=(4, 8))
        rowf = ctk.CTkFrame(sm, fg_color="transparent")
        rowf.pack(fill="both", padx=8, pady=6)

        info = ctk.CTkFrame(rowf, fg_color=("#f1f5f9", "#16222e"), corner_radius=8)
        info.pack(side="right", fill="y", padx=(10, 0))
        ctk.CTkLabel(info, text="Machine Information", font=FONT_B).pack(fill="x", padx=10, pady=(6, 2))
        self.info = {}
        # Machine facts here; the four LIVE values (current state, its output, symbol just read,
        # symbols processed) are rendered by the Simulation Output panel below, where the spec
        # wants them. Showing them twice made this panel - not the controls - the tallest thing
        # in the row, and that is what pushed the diagram out of the window.
        for key, label in (("States", "States"), ("Transitions", "Transitions"),
                           ("Initial state", "Initial State"), ("Input string", "Input String")):
            fr = ctk.CTkFrame(info, fg_color="transparent")
            fr.pack(fill="x", padx=8)
            # Column widths match the widest string actually drawn here ("Input String:" is 77px,
            # the widest value 73px). The old 96/112 columns wasted 160px of width, and that is
            # exactly what squeezed the controls row until "Reset Simulation" lost a character.
            ctk.CTkLabel(fr, text=label + ":", font=F_CAP, height=18,
                         text_color=("gray35", "#9aa7b3"), width=64, anchor="w").pack(side="left")
            self.info[key] = tk.StringVar()
            ctk.CTkLabel(fr, textvariable=self.info[key], font=F_H3, height=18,
                         width=96, anchor="w").pack(side="left")
        for key in ("Current state", "Current output", "Input symbol", "Position"):
            self.info[key] = tk.StringVar()  # kept for callers/tests; drawn by the output panel

        lf = ctk.CTkFrame(rowf, fg_color="transparent")
        lf.pack(side="left", fill="both", expand=True)
        top = ctk.CTkFrame(lf, fg_color="transparent")
        top.pack(fill="x", pady=(0, 4))
        ctk.CTkLabel(top, text="Input string:", font=F_H3).pack(side="left")
        self.inp = tk.StringVar()
        e = ctk.CTkEntry(top, textvariable=self.inp, width=220, height=32, font=("Consolas", 14))
        e.pack(side="left", padx=6)
        e.bind("<Return>", lambda ev: self.start())
        Tip(e, "Type the symbols to feed the machine, e.g. 10110. Each character is one input symbol. Press Enter to start.")
        sp = ctk.CTkFrame(top, fg_color="transparent")
        sp.pack(side="right")
        Tip(sp, "How long Run waits between two input symbols. Slide left for a slow walk-through, "
                "right to get to the end quickly. Step is always instant.")
        self.speed_lbl = ctk.CTkLabel(sp, text="Run speed", font=F_CAP,
                                      text_color=("gray30", "#9aa7b3"), width=104, anchor="e")
        self.speed_lbl.pack(side="left")
        sl = ctk.CTkSlider(sp, from_=0, to=1, width=110, command=self.set_speed)
        sl.set(.6)
        sl.pack(side="left", padx=4)
        self.set_speed(.6)

        # "did I get it right?" - the answer appears below the box, and updates as you type
        top2 = ctk.CTkFrame(lf, fg_color="transparent")
        top2.pack(fill="x", pady=(0, 4))
        ctk.CTkLabel(top2, text="Expected output (optional):", font=F_H3).pack(side="left")
        self.exp, self.verdict = tk.StringVar(), tk.StringVar()
        e2 = ctk.CTkEntry(top2, textvariable=self.exp, width=220, height=32, font=("Consolas", 14))
        e2.pack(side="left", padx=6)
        e2.bind("<Return>", lambda ev: self.start())
        Tip(e2, "Type what you expect the machine to print for this input, e.g. 010110. "
                "Leave it empty to skip the check - the verdict shows up next to this box once the run finishes.")
        # the verdict sits on the same row as the box it judges, so the diagram gets the row back
        self.verdict_lbl = ctk.CTkLabel(top2, textvariable=self.verdict, font=F_H3,
                                        text_color=("gray50", "#9aa7b3"), anchor="w")
        self.verdict_lbl.pack(side="left", padx=(8, 0))

        cf = ctk.CTkFrame(lf, fg_color="transparent")
        cf.pack(fill="x", padx=8, pady=(2, 8))
        self.cbtn = {}  # remembered so the buttons can grey themselves out while a Run is animating
        # No Start button: Step and Run both check the machine and start it, so a separate button
        # that does the same thing one symbol earlier was a third thing to explain.
        for i, (key, text, cmd, tip, style) in enumerate((
                ("step", "Step", self.step, "Process exactly ONE input symbol.", None),
                ("run", "Run", self.run, "Animate: process the remaining symbols one at a time.", None),
                ("pause", "Pause", lambda: self.pause(True),
                 "Stop the animation. Nothing is reset; press Run or Step to continue.", "warn"),
                ("reset", "Reset Simulation", self.reset,
                 "Restart the simulation only. Your machine (states and transitions) is kept. "
                 "To delete the machine, use Clear Machine.", "plain"))):
            b = self.btn(cf, text, cmd, tip, style)
            b.grid(row=0, column=i, sticky="ew", padx=3, pady=3)
            cf.columnconfigure(i, weight=1)
            self.cbtn[key] = b

        self.msg, self.outseq, self.prog = tk.StringVar(), tk.StringVar(), tk.StringVar()
        mrow = ctk.CTkFrame(lf, fg_color="transparent")
        mrow.pack(fill="x")
        self.wrapped(mrow, textvariable=self.msg).pack(side="left", fill="x", expand=True)

        return sm, rowf


    def build_output(self, sm, rowf):
        # ---------- 3b. Simulation Output: every answer in ONE place ----------
        # The status, the sequence and the numbers used to live on three different rows. They are
        # gathered here because this block is what the student is actually being marked on.
        # It shares a full-width row with the trace table below: stacked, the two made the
        # simulation card taller than the window and grid starved the diagram down to nothing.
        lower = ctk.CTkFrame(sm, fg_color="transparent")
        # remembered with their pack options so the maximize toggle can hide and restore them
        self._sim_parts = ((rowf, dict(fill="both", padx=8, pady=6)),
                           (lower, dict(fill="both", expand=True, padx=8, pady=(0, 8))))
        lower.pack(fill="both", expand=True, padx=8, pady=(0, 8))
        res = ctk.CTkFrame(lower, fg_color=("#eaf7ec", "#10281a"), corner_radius=10,
                           border_width=1, border_color=("#c3e6cb", "#1d3a2a"))
        res.pack(side="left", fill="both", expand=True, padx=(4, 6), pady=2)
        rr = ctk.CTkFrame(res, fg_color="transparent")
        rr.pack(fill="x", padx=12, pady=(8, 0))
        ctk.CTkLabel(rr, text="SIMULATION OUTPUT", font=F_H3).pack(side="left")
        self.sim_status = tk.StringVar(value="Not Started")
        self.status_lbl = ctk.CTkLabel(rr, textvariable=self.sim_status, font=F_H3,
                                       width=104, anchor="e", text_color=("gray45", "#8b97a3"))
        self.status_lbl.pack(side="right")
        self.btn(rr, "Copy Output", self.copy_out,
                 "Copy the whole output sequence to the clipboard.", "plain",
                 height=26, width=118).pack(side="right", padx=(0, 10))
        # Input / Output on one line on a white card: this is the answer, read left to right.
        big = ctk.CTkFrame(res, fg_color=("white", "#0d1b12"), corner_radius=8)
        big.pack(fill="x", padx=12, pady=(6, 6))
        self.run_in = tk.StringVar()
        brow = ctk.CTkFrame(big, fg_color="transparent")
        brow.pack(fill="x", padx=14, pady=7)
        for label, var, font, colour in (
                ("Input", self.run_in, ("Consolas", 15), ("gray25", "#cfd8dc")),
                ("Output", self.outseq, ("Consolas", 19, "bold"), ("#1b5e20", "#81c784"))):
            ctk.CTkLabel(brow, text=label + ":", font=F_H3, width=66, anchor="e",
                         text_color=("gray35", "#9aa7b3")).pack(side="left")
            ctk.CTkLabel(brow, textvariable=var, font=font, anchor="w",
                         text_color=colour).pack(side="left", padx=(14, 28))
        # Label and value on ONE line each: stacked, these four cells alone were 84px tall.
        meta = ctk.CTkFrame(res, fg_color="transparent")
        meta.pack(fill="x", padx=12, pady=(0, 8))
        for label, var in (("State", self.info["Current state"]),
                           ("State's output", self.info["Current output"]),
                           ("Symbol", self.info["Input symbol"]),
                           ("Processed", self.prog)):
            cell = ctk.CTkFrame(meta, fg_color="transparent")
            cell.pack(side="left", padx=(0, 14))
            ctk.CTkLabel(cell, text=label + ":", font=F_CAP,
                         text_color=("gray35", "#9aa7b3")).pack(side="left")
            ctk.CTkLabel(cell, textvariable=var, font=F_H3).pack(side="left", padx=(5, 0))
        self.refresh_status()

        tcol = ctk.CTkFrame(lower, fg_color="transparent")
        tcol.pack(side="right", fill="y", padx=(0, 4), pady=2)
        self.table = self.tree(tcol, ("k", "i", "p", "s", "o"),
                               ("Step", "Input", "Previous State", "Current State", "Output"),
                               (60, 70, 110, 110, 70), 5, grow=True)
        self.table.tag_configure("latest", background="#ffe082")
        self.inp.trace_add("write", lambda *_: self.update_info())
        self.exp.trace_add("write", lambda *_: self.update_info())


    def set_panel(self, mode):
        """Resize the Machine Diagram panel: "normal", "min" (picture collapsed to its header,
        the Simulation panel grows into the space) or "max" (Simulation panel collapsed, so the
        picture gets the whole column). Pressing the active button again restores normal.
        Panels only - the machine, the drag offsets and any run in progress are untouched."""
        mode = "normal" if mode == self.panel else mode
        self.panel = mode
        if mode == "min":
            self._dg_body.pack_forget()
        else:
            self._dg_body.pack(fill="both", expand=True, padx=8, pady=(4, 6))
        for part, kw in self._sim_parts:
            if mode == "max":
                part.pack_forget()
            else:
                part.pack(**kw)
        self.root.rowconfigure(1, weight=0 if mode == "min" else 1)
        self.root.rowconfigure(2, weight=1 if mode == "min" else 0)
        self.root.update_idletasks()
        # while the canvas is unmapped it has no size; <Configure> repaints it when it returns
        if self._dg_body.winfo_ismapped():
            self.draw()

