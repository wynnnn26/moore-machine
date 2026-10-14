"""Popups: beginner help, the simple add-state dialog, and Auto Build."""

import tkinter as tk
from tkinter import messagebox

import customtkinter as ctk

from core.simulation import out_string, simulate
from core.synthesis import ex_pair_check, synthesize
from ui.theme import F_BODY, F_CAP, F_H1, F_H3, HELP_STEPS, HELP_WHAT, STYLES


class DialogMixin:
    """Every floating window the app can open."""

    def set_speed(self, v):
        self.delay = int(1500 - 1300 * float(v))  # 0 -> 1500 ms, 1 -> 200 ms
        self.speed_lbl.configure(text=f"{self.delay} ms / symbol")

    # ----- popups: beginner help + simple add dialog -----
    def popup(self, w):  # remember it so a second popup replaces the first
        for d in self.dialogs:
            if d.winfo_exists():
                d.destroy()
        self.dialogs.append(w)
        w.transient(self.root)
        w.attributes("-topmost", True)
        w.after(400, lambda: w.attributes("-topmost", False))
        # Windows cascades new toplevels itself, which can push them past the edge
        def center(*_a):
            if not w.winfo_exists():
                return
            # Clamp to the main window's own box: winfo_screen*() comes back in logical pixels
            # while widget geometry is physical, so mixing them would push a dialog that is
            # perfectly visible off to nowhere. The root's box is always in the same units.
            rx, ry = self.root.winfo_rootx(), self.root.winfo_rooty()
            rw, rh = self.root.winfo_width(), self.root.winfo_height()
            # CustomTkinter settles a new Toplevel onto its real height over a few frames, so a
            # window measured too early is smaller than it will end up; clamp against the larger
            # of the two or the bottom row of buttons lands outside once the content arrives.
            dw = max(w.winfo_width(), w.winfo_reqwidth())
            dh = max(w.winfo_height(), w.winfo_reqheight())
            # target in screen coordinates ...
            tx = max(rx, min(rx + (rw - dw) // 2, rx + rw - dw))
            ty = max(ry, min(ry + (rh - dh) // 2, ry + rh - dh))
            # ... but this window's own winfo_x/y and its geometry string are measured from its
            # parent (the main window), so compare and set in that frame or nothing ever moves.
            if (tx, ty) != (w.winfo_rootx(), w.winfo_rooty()):   # idempotent: cannot loop
                w.geometry("+%d+%d" % (tx - rx, ty - ry))
        w.after(60, center)
        w.after(400, center)   # again once the content has settled on its real height
        # ...and whenever the window is still growing, but only for the first moment: after
        # that the dialog belongs to the user and must not be yanked back while they drag it.
        settling = [True]
        grown = []

        def settle(_e):
            # Only chase a window that has actually grown. Re-centering on EVERY configure -
            # including the ones our own move causes - never drains: each event spawns another
            # and the event loop blocks for the whole 1500 ms settling window (1.5 s of lag the
            # moment a dialog opens). A move changes nothing but the position, so ignore it.
            if not settling[0]:
                return
            size = (w.winfo_width(), w.winfo_height())
            if grown and grown[0] == size:
                return
            grown[:] = [size]
            center()

        w.after(1500, lambda: settling.__setitem__(0, False))
        w.bind("<Configure>", settle, add=True)
        w.bind("<Escape>", lambda *_a: w.destroy())  # *_a: Tk may deliver no event while tearing down
        return w

    def formal_def(self):
        """(Q, Σ, Γ, δ, λ, q0) written out - the tuple an exam or homework asks for."""
        st, tr = self.states, self.trans
        if not st:
            return "  There is no machine yet - add a state, or press Auto Build to make one from an\n" \
                   "  input string and the output it should print."
        sigma = ", ".join(sorted({a for _, a in tr})) or "(no inputs yet)"
        delta = ", ".join(f"δ({s},{a})={d}" for (s, a), d in sorted(tr)) or "(no transitions yet)"
        lam = ", ".join(f"λ({s})={o}" for s, o in sorted(st.items()))
        return "\n".join([
            f"    Q   (states)         = {{{', '.join(st)}}}",
            f"    Σ   (input symbols)   = {{{sigma}}}",
            f"    Γ   (output symbols)  = {{{', '.join(sorted(set(st.values())))}}}",
            f"    δ   (next state)      = {delta}",
            f"    λ   (output)          = {lam}",
            f"    start state           = {self.initial or '(not set)'}",
        ])

    def machine_explain(self):
        """Plain-English walk of the loaded machine, then its formal definition."""
        head = "WHAT THE MACHINE ON SCREEN DOES\n\n"
        st, tr = self.states, self.trans
        if not st:
            return head + ("  There is no machine yet. Add a state on the left, or press Auto Build to\n"
                           "  have one built from an input string and its output.\n\n"
                           "FORMAL DEFINITION (the tuple an exam asks for)\n\n" + self.formal_def())
        lines = []
        if self.initial in st:
            lines.append(f"  It starts in {self.initial}, which prints {st[self.initial]}.")
        else:
            lines.append("  It has no start state yet - click a state and press Set as Initial State.")
        for s in st:
            outs = [(a, d) for (x, a), d in sorted(tr.items()) if x == s]
            if not outs:
                lines.append(f"  {s} (prints {st[s]}) has no way out - connect it with a transition.")
                continue
            bits = ", ".join(f"input {a} {'keeps it in' if d == s else 'sends it to'} {d}" for a, d in outs)
            lines.append(f"  {s} (prints {st[s]}): {bits}.")
        lines.append("")
        lines.append(f"  Try it: press Run with {self.inp.get().strip() or '(an input string)'} and watch.")
        return head + "\n".join(lines) + "\n\nFORMAL DEFINITION (the tuple an exam asks for)\n\n" + self.formal_def()

    def show_help(self, *_):
        w = self.popup(ctk.CTkToplevel(self.root, fg_color=("white", "#242424")))
        w.title("How to Use")
        w.geometry("640x600")
        w.minsize(460, 400)
        tb = ctk.CTkTextbox(w, font=F_BODY, wrap="word", corner_radius=8)
        tb.pack(fill="both", expand=True, padx=12, pady=(12, 6))
        tb.insert("1.0", HELP_WHAT + self.machine_explain() + "\n\n" + HELP_STEPS)
        tb.configure(state="disabled")
        row = ctk.CTkFrame(w, fg_color="transparent")
        row.pack(fill="x", padx=12, pady=(6, 12))
        ctk.CTkButton(row, text="Got it", command=w.destroy, width=120, height=34).pack(side="right")
        w.focus_force()

    def add_state_dialog(self, *_):
        if self.name.get().strip() in self.states or not self.name.get().strip():
            self.fresh_fields()  # always offer a free name, never a duplicate
        w = self.popup(ctk.CTkToplevel(self.root, fg_color=("white", "#242424")))
        w.title("Add State")
        w.geometry("370x270")
        w.resizable(False, False)
        ctk.CTkLabel(w, text="Add a state", font=F_H1, anchor="w").pack(
            fill="x", padx=18, pady=(16, 2))
        ctk.CTkLabel(w, text="A Moore state has a name and exactly one output,\nfor example q0 with output 0.",
                     font=F_BODY, text_color=("gray40", "#9aa7b3"),
                     justify="left", anchor="w").pack(fill="x", padx=18, pady=(0, 8))
        form = ctk.CTkFrame(w, fg_color="transparent")
        form.pack(fill="x", padx=18)
        ctk.CTkLabel(form, text="State Name", anchor="w", font=F_CAP,
                     text_color=("gray35", "#9aa7b3")).pack(fill="x")
        ne = ctk.CTkEntry(form, textvariable=self.name, height=34)
        ne.pack(fill="x", pady=(2, 8))
        ctk.CTkLabel(form, text="Output", anchor="w", font=F_CAP,
                     text_color=("gray35", "#9aa7b3")).pack(fill="x")
        oe = ctk.CTkEntry(form, textvariable=self.out, height=34)
        oe.pack(fill="x", pady=(2, 0))
        for x in (ne, oe):
            x.bind("<Return>", lambda e: self.state_ok(w))
        row = ctk.CTkFrame(w, fg_color="transparent")
        row.pack(fill="x", padx=18, pady=14)
        ctk.CTkButton(row, text="Cancel", command=w.destroy, width=100, height=34,
                      fg_color=STYLES["plain"][0], hover_color=STYLES["plain"][1]).pack(side="right", padx=(8, 0))
        ctk.CTkButton(row, text="Add State", command=lambda: self.state_ok(w), width=140, height=34,
                      fg_color=STYLES["go"][0], hover_color=STYLES["go"][1]).pack(side="right")
        ne.focus_force()
        ne.select_range(0, "end")

    def state_ok(self, w):  # validate first: a bad value keeps the dialog open with the error shown
        if not self.read_state():
            return
        w.destroy()
        self.add_state()
        self.name_entry.focus()

    # ----- auto build: one input and its output -> machine -----
    def ex_len_refresh(self, *_):
        """Say what the Expected Output box needs, next to the box, on every keystroke.
        A Moore machine prints one symbol per state including the start state, so an output is
        always one character longer than its input - the one rule that gets examples rejected.
        Typing anything also clears the error from the last attempt: the user is on it."""
        if getattr(self, "ex_err", None) and self.ex_err.get():
            self.ex_err.set("")
        i, o = self.ex_in.get().strip(), self.ex_out.get().strip()
        if not o:
            self.ex_len_hint.set(
                "Expected Output is required - one character longer than the input "
                "(that first character is printed by the start state).")
            self.ex_len_lab.configure(text_color=("gray40", "#9aa7b3"))
            return
        need = len(i) + 1
        self.ex_len_hint.set(
            f"Output for input '{i}' must be exactly {need} characters "
            f"- you have typed {len(o)}.")
        self.ex_len_lab.configure(text_color=("#2e7d32", "#66bb6a") if len(o) == need
                                  else ("#c62828", "#ef5350"))

    def auto_build_dialog(self, *_):
        """Two boxes, two buttons. Type what goes in and what should come out, press Build -
        the states, their outputs, the start state and every transition are worked out."""
        w = self.popup(ctk.CTkToplevel(self.root, fg_color=("white", "#242424")))
        w.title("Auto Build")
        # Sized in unscaled units: CustomTkinter multiplies by the display scale, and Tk reports
        # winfo_screenheight() in *logical* pixels while widget geometry is physical - so the main
        # window's own height is the one figure in the same units as everything else on screen.
        sc = ctk.ScalingTracker.get_window_scaling(w) or 1
        room = self.root.winfo_height() - 48
        self.ex_base_h = max(230, min(250, int(room / sc)))
        self.ex_sc = sc
        w.geometry("660x%d" % self.ex_base_h)
        w.minsize(560, 230)
        ctk.CTkLabel(w, text="Auto Build", font=F_H1, anchor="w").pack(
            fill="x", padx=18, pady=(14, 2))
        self.wrapped(w, text=(
            "Type the symbols the machine should read and what should come out - then press "
            "Build."),
            font=F_BODY, text_color=("gray35", "#9aa7b3")).pack(fill="x", padx=18, pady=(0, 8))

        self.ex_in, self.ex_out = (tk.StringVar(value=self.ex_last[0]),
                                   tk.StringVar(value=self.ex_last[1]))  # hand the last attempt back
        ef = ctk.CTkFrame(w, fg_color="transparent")
        ef.pack(fill="x", padx=18, pady=(4, 0))
        ie = ctk.CTkEntry(ef, textvariable=self.ex_in, height=32, placeholder_text="e.g. 10110")
        oe = ctk.CTkEntry(ef, textvariable=self.ex_out, height=32,
                          placeholder_text="required - one longer than the input")
        self.field(ef, "Input String", ie, 0)
        self.field(ef, "Expected Output", oe, 1)
        for e in (ie, oe):  # every keystroke re-answers "what am I about to get?"
            e.bind("<KeyRelease>", self.ex_len_refresh)
            e.bind("<Return>", lambda _e: self.auto_build_go(w))
        for c in (1, 3):
            ef.columnconfigure(c, weight=1)  # the boxes take the slack
        # Wrong output length is what gets almost every hand-typed example rejected, and telling
        # the user only AFTER Build is too late - answer the rule here while they type.
        self.ex_len_hint = tk.StringVar()
        self.ex_len_lab = ctk.CTkLabel(w, textvariable=self.ex_len_hint, font=F_CAP, anchor="w",
                                       text_color=("gray40", "#9aa7b3"))
        self.ex_len_lab.pack(fill="x", padx=18, pady=(4, 0))
        # Anything wrong with what is typed is written HERE, under the boxes - the answer is about
        # these two boxes, so bouncing the user back to the dashboard to read it loses the one
        # thing they were about to fix. The window grows to fit it and closes only on success.
        # A fixed wraplength, NOT wrapped(): that helper re-wraps on every <Configure> of the
        # window, and a second one on the same window oscillates against the first - 500 configure
        # events and a second of lag on open. The dialog is 660 wide whatever the user does.
        self.ex_err = tk.StringVar()
        self.ex_err_lab = ctk.CTkLabel(w, textvariable=self.ex_err, font=F_CAP, anchor="w",
                                       justify="left", wraplength=624,
                                       text_color=("#c62828", "#ef5350"))
        self.ex_err_lab.pack(fill="x", padx=18, pady=(6, 0))

        # The committing buttons are pinned underneath so they can never scroll off-screen.
        row = ctk.CTkFrame(w, fg_color="transparent")
        row.pack(fill="x", side="bottom", padx=18, pady=(12, 14))
        ctk.CTkButton(row, text="Cancel", command=w.destroy, width=130, height=36, font=F_H3,
                      fg_color=STYLES["plain"][0], hover_color=STYLES["plain"][1]).pack(
            side="right", padx=(8, 0))
        ctk.CTkButton(row, text="Build", command=lambda: self.auto_build_go(w),
                      width=210, height=36, font=F_H3,
                      fg_color=STYLES["go"][0], hover_color=STYLES["go"][1]).pack(side="right")
        self.ex_len_refresh()
        ie.focus_force()

    def show_ex_err(self, w, text):
        """Write a '⚠️ Title / detail / Fix:' block under the boxes and grow the window to hold it.
        The dialog stays open because the thing to fix is the two boxes still on screen."""
        lines = text.splitlines()
        title = lines[0].replace("⚠️", "").strip() or "Auto Build"
        self.ex_err.set(f"{title}\n" + "\n".join(lines[1:]).strip())
        w.update_idletasks()
        # The measured height, never less than a small floor: a stale measurement would clip the
        # last line, and a clipped "Fix:" is worse than a little empty space.
        extra = max(60, int((self.ex_err_lab.winfo_reqheight() + 8) / self.ex_sc))
        w.geometry("660x%d" % (self.ex_base_h + extra))
        w.lift()
        return ""

    def auto_build_go(self, w):
        """Build from the two boxes: the input string and the output it has to print.
        Anything wrong is written under the boxes and the dialog stays open, so it is fixed where
        it was typed; only a pair that builds closes the window and goes on to ask about replacing
        the current machine."""
        inp, out = self.ex_in.get().strip(), self.ex_out.get().strip()
        self.ex_last = (inp, out)
        bad, made = ex_pair_check(inp, out), None
        if not bad:
            try:
                # Fit a machine, then PROVE it replays the example: a fitter that quietly produced
                # a machine missing it would be installed without a word, and this is the last gate
                # before the user's own machine is thrown away.
                states, initial, trans, defaulted = synthesize([(inp, out)])
                got = out_string(simulate(states, initial, trans, inp))
                if got != out:
                    raise ValueError(
                        "These examples cannot all be true at once.\n"
                        f"The machine prints '{got}' for input '{inp}', but the example says '{out}'.\n"
                        "Fix: check that example for a typo.")
                made = (states, initial, trans, defaulted)
            except ValueError as e:  # synthesize explains itself: wrong length, or a clash
                bad = str(e)
        if bad:
            return self.show_ex_err(w, bad)
        w.destroy()
        if self.states and not messagebox.askyesno(
                "Replace the current machine?",
                f"Auto Build worked out a {len(made[0])}-state machine that reads '{inp}'.\n\n"
                f"This replaces your current {len(self.states)}-state machine.\n"
                "You can still edit every state and transition afterwards.",
                parent=self.root):
            return  # keep my machine: nothing has been touched
        self.ex_install(made[0], made[1], made[2], inp, out, made[3])

    def ex_install(self, states, initial, trans, inp, out, defaulted):
        """Put the worked-out machine on the dashboard: both tables, the diagram, and a run of it.
        Filling it is the point of the build, so run the simulation here rather than sending the
        user off to press Run. Stepped by hand rather than through run()'s animation so the
        finished trace is on screen the moment the dialog closes."""
        self.states, self.initial, self.trans = states, initial, trans
        self.off = {}  # layout deltas belong to the machine they were dragged on
        self.inp.set(inp)
        self.exp.set(out)  # the output the build promised, so the verdict can be checked
        for v in (self.src, self.sym, self.dst):
            v.set("")
        self.changed()  # refills the States and Transitions tables and clears stale field text
        self.fresh_fields()
        self.start()
        while self.rows and self.shown < len(self.rows):
            self.advance()
        head = f"Every output of '{inp}' now prints exactly '{out}'.\n"
        note = ""
        if defaulted:
            note = f" {defaulted} transition{'s' if defaulted != 1 else ''} no symbol of your " \
                   f"input mentioned hold their state (a self-loop)."
        n_s, n_t = len(states), len(trans)
        self.ok(f"{n_s} state{'s' if n_s != 1 else ''}, {n_t} transition{'s' if n_t != 1 else ''}."
                f"{note}\n{head}"
                f"States, Transitions, the diagram and the results table all show it.",
                "Built and applied")
        self.fit_diagram()
