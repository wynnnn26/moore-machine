"""The application: state, notifications, editing and simulation."""

import json
from tkinter import font as tkfont
from tkinter import filedialog, messagebox

import customtkinter as ctk

from core.constants import DASH
from core.serialization import from_dict, no_dups, to_dict
from core.simulation import out_string, simulate
from core.validation import check_input, validate
from ui.diagram import DiagramMixin
from ui.dialogs import DialogMixin
from ui.pages import PagesMixin
from ui.theme import FONT_B, F_BODY, F_H3, ThemeMixin
from ui.widgets.helpers import winfo_exists
from ui.widgets.kit import WidgetKit


class App(ThemeMixin, DialogMixin, DiagramMixin, PagesMixin, WidgetKit):
    """Everything the machine and the simulation do. The pages and drawing it uses are mixed in."""

    def __init__(self, root):
        self.root = root
        self.font = tkfont.Font(font=FONT_B)  # for measuring text -> circle size
        self._meas = {}     # cached text widths - see measure()
        self._edge_tag = {} # edge -> canvas tag, so a step can re-colour one arrow - see highlight()
        self.delay = 700  # ms between Run steps (the speed slider changes it)
        self.states, self.initial, self.trans = {}, None, {}   # the machine
        self.rows, self.shown, self.cur, self.active, self.job, self.text = [], 0, None, None, None, ""  # simulation
        self._latest = None  # the one table row currently highlighted as "just happened"
        self._err = False    # the last attempt to start was refused -> status reads "Error"
        self.tkeys = []
        # in-app notifications: history for the tests, plus the one overlay currently on screen
        self.notices, self._notice = [], None
        # diagram view: zoom + per-state drag offsets (kept when you edit, cleared with the machine)
        self.zoom, self.off, self.layout = 1.0, {}, {}
        self.dragging, self._fonts, self._diag, self.dialogs = None, {}, (0, 0), []
        self.ex_last = ("", "")  # the last Auto Build attempt, handed back when the dialog reopens
        self.panel = "normal"   # diagram panel: normal | min (body hidden) | max (sim hidden)
        self._pan = None        # click-and-drag on empty canvas -> move the view
        self._no_follow = False # a zoom is in flight: do not scroll back to the current state
        self.build()
        self.load_example(ask=False)

    # Validation and other informational messages are shown as an overlay on the Build sidebar,
    # never as a modal window: the user keeps the app, keeps reading, and dismisses it themselves.
    NOTICE = {  # kind -> (ink, background, border, icon glyph)
        "error":   ("#b71c1c", "#fdecea", "#f2b8b5", "error"),
        "warning": ("#e65100", "#fff3e0", "#ffcc80", "warn"),
        "success": ("#1b5e20", "#e8f5e9", "#a5d6a7", "ok"),
    }

    def notify(self, kind, title, message):
        """Put `message` over the Build sidebar.

        Dismissed by the × or by clicking anywhere outside it - there is no timer, so it is
        never taken away while it is being read, and nothing is grabbed, so every other control
        stays usable. One at a time, so a run of errors cannot bury the interface, and it never
        covers the diagram or the simulation controls. Confirmation dialogs for destructive
        actions are deliberately left as they are."""
        ink, bg, bd, glyph = self.NOTICE.get(kind, self.NOTICE["error"])
        self.notices.append(("WARNING " if kind == "warning" else "") + "%s\n%s" % (title, message))
        del self.notices[:-50]   # history for the tests, bounded so it cannot grow forever
        self.dismiss_notice()
        host = getattr(self, "notice_host", None)
        if host is None or not winfo_exists(host):
            return None
        box = ctk.CTkFrame(host, fg_color=bg, corner_radius=10, border_width=2, border_color=bd)
        self._notice = box
        head = ctk.CTkFrame(box, fg_color="transparent")
        head.pack(fill="x", padx=(10, 6), pady=(8, 0))
        ctk.CTkLabel(head, image=self.icon(glyph), text="").pack(side="left")
        ctk.CTkLabel(head, text=title, font=F_H3, text_color=ink, anchor="w").pack(
            side="left", padx=(6, 0))
        ctk.CTkButton(head, text="×", width=26, height=26, corner_radius=13,
                      font=("Arial", 15, "bold"), fg_color="transparent", hover_color=bd,
                      text_color=ink, command=self.dismiss_notice).pack(side="right")
        self.wrapped(box, text=message, font=F_BODY, text_color=ink).pack(
            fill="x", padx=12, pady=(4, 10))
        box.place(relx=0.5, rely=0.0, anchor="n", relwidth=1)   # top of the sidebar, auto height
        box.lift()
        return box

    def dismiss_notice(self, *_):
        box, self._notice = getattr(self, "_notice", None), None
        if box is not None and winfo_exists(box):
            box.place_forget()
            box.destroy()

    def _notice_hit(self, e):
        """Clicking outside the overlay closes it; clicking inside it leaves it alone."""
        w = e.widget
        while w is not None:
            if w is self._notice:
                return
            w = getattr(w, "master", None)
        self.dismiss_notice()

    def err(self, m, title="Please fix this"):
        self.notify("error", title, m)
        return ""   # falsy, exactly like the popup it replaced: `return self.err(...)` stays a no-op

    def warn(self, m, title="Heads up"):
        self.notify("warning", title, m)
        return ""

    def ok(self, m, title="Done"):
        self.notify("success", title, m)
        return ""

    def sel_state(self):
        s = self.st.selection()
        return s[0] if s else None

    def pick_state(self, _):
        s = self.sel_state()
        if s:
            self.name.set(s)
            self.out.set(self.states[s])
        self.refresh_sel()

    def refresh_sel(self):
        """Name the row Edit / Delete will act on, and grey out the ones that cannot work yet.
        Add vs Edit is otherwise a guess: both read the same three boxes."""
        if not getattr(self, "st_sel", None):
            return  # called before build() finished
        s = self.sel_state()
        if s and s in self.states:
            self.st_sel.set(f"Editing  {s}   ·   output {self.states[s]}")
            self.st_sel_lbl.configure(text_color=("#1565c0", "#64b5f6"))
            state_btn = "normal"
        else:
            self.st_sel.set("No state selected - click a row to edit it.")
            self.st_sel_lbl.configure(text_color=("gray45", "#8b97a3"))
            state_btn = "disabled"
        sel_t = self.tt.selection()
        k = self.tkeys[int(sel_t[0])] if sel_t and int(sel_t[0]) < len(self.tkeys) else None
        if k:
            self.tt_sel.set(f"Editing  {k[0]}  --{k[1]}-->  {self.trans[k]}")
            self.tt_sel_lbl.configure(text_color=("#1565c0", "#64b5f6"))
            tr_btn = "normal"
        else:
            self.tt_sel.set("No transition selected - click a row to edit it.")
            self.tt_sel_lbl.configure(text_color=("gray45", "#8b97a3"))
            tr_btn = "disabled"
        for key in ("edit", "delete", "initial"):   # Add never needs a selection, so it stays live
            self.btn_state[key].configure(state=state_btn)
        for key in ("edit", "delete"):
            self.btn_tr[key].configure(state=tr_btn)

    def next_name(self):
        i = 0
        while f"q{i}" in self.states:
            i += 1
        return f"q{i}"

    def fresh_fields(self):  # ready-to-type boxes: suggested name, empty output
        self.name.set(self.next_name())
        self.out.set("")

    def read_state(self, old=None):
        n, o = self.name.get().strip(), self.out.get().strip()
        if not n:
            return self.err("⚠️ Empty state name\nA state name cannot be empty.\n"
                            "Fix: type a short unique name such as q0 or A.")
        if n != old and n in self.states:
            return self.err(f"⚠️ Duplicate state name\nA state named '{n}' already exists. State names must be unique.\n"
                            f"Fix: choose a different name, or click '{n}' in the list and use Edit State.")
        if not o:
            return self.err(f"⚠️ Missing state output\nState '{n}' has no output. Every Moore state needs exactly one output.\n"
                            "Fix: type an output value (e.g. 0 or 1) in the Output box.")
        return n, o

    def add_state(self):
        v = self.read_state()
        if v:
            if not self.states:
                self.initial = v[0]  # the first state is the start state until the user picks another
            self.states[v[0]] = v[1]
            self.changed()
            self.fresh_fields()
            self.name_entry.focus()

    def edit_state(self):
        old = self.sel_state()
        if not old:
            return self.err("⚠️ Nothing selected\nSelect a state in the States list first.\n"
                            "Fix: click a row in 'States'.")
        v = self.read_state(old)
        if v:
            n, o = v
            self.states = {(n if k == old else k): (o if k == old else x) for k, x in self.states.items()}
            self.trans = {(n if s == old else s, a): (n if d == old else d) for (s, a), d in self.trans.items()}
            if self.initial == old:
                self.initial = n
            if old in self.off:  # keep where the user dragged it
                self.off[n] = self.off.pop(old)
            self.changed()
            self.st.selection_set(n)
            self.refresh_sel()  # the select event is async: name the row right away

    def del_state(self):
        old = self.sel_state()
        if not old:
            return self.err("⚠️ Nothing selected\nSelect a state in the States list first.\n"
                            "Fix: click a row in 'States'.")
        k = sum(1 for (s, _), d in self.trans.items() if old in (s, d))
        if not messagebox.askyesno("Delete state",
                                   f"Delete state '{old}' and the {k} transition(s) that use it?\n\n"
                                   "This cannot be undone. (To restart only the simulation, use Reset Simulation.)"):
            return
        del self.states[old]
        self.trans = {key: d for key, d in self.trans.items() if old not in (key[0], d)}
        was_initial = self.initial == old
        if was_initial:
            self.initial = None
        self.changed()
        if was_initial:
            self.warn(f"'{old}' was the initial state. Click another state and press "
                      f"'Set as Initial State' before simulating.", "Initial state deleted")

    def set_initial(self):
        s = self.sel_state()
        if not s:
            return self.err("⚠️ No initial state\nSelect a state in the States list first.\n"
                            "Fix: click a row in 'States', then press Set as Initial State.")
        self.initial = s
        self.changed()
        self.st.selection_set(s)
        self.refresh_sel()

    # ----- transition editing -----
    def pick_trans(self, _):
        s = self.tt.selection()
        if s:
            k = self.tkeys[int(s[0])]
            self.src.set(k[0])
            self.sym.set(k[1])
            self.dst.set(self.trans[k])
        self.refresh_sel()

    def read_trans(self):
        s, a, d = self.src.get(), self.sym.get().strip(), self.dst.get()
        if s not in self.states:
            return self.err("⚠️ Invalid state reference\nChoose the From state from the drop-down list (it must already exist).\n"
                            "Fix: press Add State first to create that state.")
        if d not in self.states:
            return self.err("⚠️ Invalid state reference\nChoose the To state from the drop-down list (it must already exist).\n"
                            "Fix: press Add State first to create that state.")
        if not a:
            return self.err("⚠️ Empty input symbol\nThe input symbol cannot be empty.\n"
                            "Fix: type one character such as 0 or 1.")
        if len(a) != 1:
            return self.err("⚠️ Invalid input symbol\nThe input symbol must be exactly one character, e.g. 0 or 1.\n"
                            "Fix: type a single character and press Add Transition again.")
        return s, a, d

    def add_trans(self):
        t = self.read_trans()
        if not t:
            return
        if t[:2] in self.trans:
            return self.err(f"⚠️ Duplicate transition\n'{t[0]}' already has a transition on '{t[1]}'. "
                            f"A machine can only have one transition per symbol.\n"
                            f"Fix: click that transition in the list and press Edit Transition, or use a different input symbol.",
                            "Duplicate transition")
        self.trans[t[:2]] = t[2]
        self.changed()
        self.sym.set("")  # keep From/To, ready for the next symbol

    def edit_trans(self):
        sel = self.tt.selection()
        if not sel:
            return self.err("⚠️ Nothing selected\nSelect a transition in the Transitions list first.\n"
                            "Fix: click a row in 'Transitions'.")
        old = self.tkeys[int(sel[0])]
        t = self.read_trans()
        if not t:
            return
        if t[:2] != old and t[:2] in self.trans:
            return self.err(f"⚠️ Duplicate transition\n'{t[0]}' already has a transition on '{t[1]}'.\n"
                            "Fix: pick a different input symbol or state.", "Duplicate transition")
        del self.trans[old]
        self.trans[t[:2]] = t[2]
        self.changed()
        self.tt.selection_set(str(self.tkeys.index(t[:2])))
        self.refresh_sel()

    def del_trans(self):
        sel = self.tt.selection()
        if not sel:
            return self.err("⚠️ Nothing selected\nSelect a transition in the Transitions list first.\n"
                            "Fix: click a row in 'Transitions'.")
        i = int(sel[0])
        f, a = self.tkeys[i]
        if not messagebox.askyesno("Delete transition",
                                   f"Delete the transition {f} --{a}--> {self.trans[(f, a)]}?\n\n"
                                   "This cannot be undone."):
            return
        del self.trans[self.tkeys[i]]
        self.changed()

    # ----- whole-machine actions -----
    def load_example(self, ask=True):
        if ask and self.states and not messagebox.askyesno("Load Example", "Replace the current machine with the example?"):
            return
        self.states = {"q0": "0", "q1": "1"}
        self.initial = "q0"
        self.trans = {("q0", "0"): "q0", ("q0", "1"): "q1", ("q1", "0"): "q0", ("q1", "1"): "q1"}
        self.inp.set("10110")
        self.off = {}  # a brand new machine starts from the standard layout
        self.changed()
        self.fresh_fields()

    def clear(self):
        if self.states and not messagebox.askyesno("Clear Machine",
                                                   "Delete the whole machine?\n\n"
                                                   "Every state and transition will be removed.\n"
                                                   "(To restart only the simulation, press Reset Simulation instead.)"):
            return
        self.states, self.initial, self.trans = {}, None, {}
        self.off = {}
        for v in (self.inp, self.src, self.sym, self.dst):
            v.set("")
        self.changed()
        self.fresh_fields()

    def save(self):
        path = filedialog.asksaveasfilename(defaultextension=".json", initialfile="moore-machine.json",
                                            filetypes=[("Moore machine", "*.json")])
        if path:
            data = to_dict(self.states, self.initial, self.trans)
            # ponytail: stored as layout *deltas* - exact for a round-trip of this machine, but
            # hand-editing the file to add states shifts them; save absolute coords and re-derive
            # after draw() computes the layout if that ever bites
            data["positions"] = {s: list(self.off[s]) for s in self.states if s in self.off}
            try:
                with open(path, "w", encoding="utf-8") as f:
                    json.dump(data, f, indent=2)
            except OSError as e:
                self.err(f"Could not save the file:\n{e}\n\nFix: choose a folder you can write to, "
                         "such as Documents or Downloads.", "Could not save")
            else:
                self.ok(f"Wrote {len(self.states)} states and {len(self.trans)} transitions to\n{path}",
                        "Machine saved")

    def load(self):
        path = filedialog.askopenfilename(filetypes=[("Moore machine", "*.json")])
        if not path:
            return
        try:
            with open(path, encoding="utf-8") as f:
                raw = json.load(f, object_pairs_hook=no_dups)
            m = from_dict(raw)
            pos = raw.get("positions")
            # float() raises on garbage while still inside here -> reported like any other bad file
            off = {k: (float(v[0]), float(v[1])) for k, v in pos.items()} if isinstance(pos, dict) else {}
        except (OSError, ValueError, TypeError, KeyError) as e:  # json errors are ValueErrors too
            return self.err(f"Could not load '{path}':\n{e}\n\n"
                            "Fix: pick a .json file saved by this program, or press "
                            "'Load Example' to see a working machine.", "Could not load")
        if self.states and not messagebox.askyesno("Load Machine", "Replace the current machine with this file?"):
            return
        self.states, self.initial, self.trans = m
        self.off = {k: p for k, p in off.items() if k in self.states}
        self.changed()
        self.fresh_fields()
        self.ok(f"Read {len(self.states)} states and {len(self.trans)} transitions from\n{path}",
                "Machine loaded")

    def changed(self):
        """Any edit: refresh the lists, repaint the diagram, then reset the simulation.

        The repaint lives here rather than in reset() because a reset on its own - a Reset
        press, or the start of a new run - changes only the highlight, which is cheap."""
        self.st.delete(*self.st.get_children())
        for n, o in self.states.items():
            self.st.insert("", "end", iid=n, values=(n, o, "start" if n == self.initial else ""))
        self.tt.delete(*self.tt.get_children())
        self.tkeys = sorted(self.trans)
        for i, k in enumerate(self.tkeys):
            self.tt.insert("", "end", iid=str(i), values=(k[0], k[1], self.trans[k]))
        first = next(iter(self.states), "")
        for cb, v in zip(self.combos, (self.src, self.dst)):
            cb.configure(values=list(self.states))
            if v.get() not in self.states:
                v.set(first)  # drop-downs always start on a real state
        for tree, note in ((self.st, self.st_empty), (self.tt, self.tt_empty)):
            if tree.get_children():
                note.pack_forget()
            else:
                note.pack(fill="x", padx=12, pady=(0, 4))
        self.refresh_sel()  # rebuilding the lists clears the selection: say so rather than lie
        self.draw()   # the machine itself changed, so the whole picture has to be rebuilt...
        self.reset()  # ...and reset() then only re-marks the start state, which is cheap

    # ----- simulation -----
    def refuse(self, m, title):
        """A refused start: show the error and put the panel into Error, then stop.
        The machine is untouched and no new run starts. start() has already cleared the previous
        trace - it belongs to the old input, so leaving it up while the new one is refused would
        be showing results for something that never ran."""
        self._err = True
        self.refresh_status()
        return self.err(m, title)

    def start(self):
        self.reset()  # clears the previous run - so a refusal below never leaves stale output
        errs = validate(self.states, self.initial, self.trans)
        if errs:
            return self.refuse("\n\n".join(errs), "Machine needs a quick fix")
        text = self.inp.get().strip()
        e = check_input(self.trans, text)
        if e:
            return self.refuse(e, "Invalid input")
        try:
            self.rows = simulate(self.states, self.initial, self.trans, text)
        except ValueError as e:
            return self.refuse(str(e), "Missing transition")
        self.text = text
        self.advance()  # step 0
        return True

    def advance(self):
        row = self.rows[self.shown]
        k, a, prev, cur, out = row
        self.shown += 1
        if self._latest is not None:  # unhighlight last step only, not every row on every step
            self.table.item(self._latest, tags=())
        self._latest = self.table.insert("", "end", values=row, tags=("latest",))
        self.table.yview_moveto(1)
        prev_cur, prev_act = self.cur, self.active  # what highlight() must take back off
        self.cur, self.active = cur, ((prev, a, cur) if k else None)
        done = self.shown == len(self.rows)
        if k:
            self.msg.set(f"Step {k}: read '{a}'  →  transition {prev} --{a}--> {cur}  →  new state {cur}  →  its output is {out}.")
        else:
            self.msg.set(f"Step 0: start in initial state {cur}. Its output ({out}) is shown before any input is read.")
        if done:  # say so plainly instead of leaving the last step message hanging
            self.msg.set(self.msg.get() + f"   (finished - all {len(self.text)} input symbols processed)")
        # raw sequence only: the status headline says Finished, so appending it here would
        # risk showing a PARTIAL sequence with a finished marker on it.
        self.outseq.set(out_string(self.rows[:self.shown]))
        self.update_info()
        self.highlight(prev_cur, prev_act)
        self.refresh_controls()
        self.refresh_status()

    def step(self):
        self.pause()
        if not self.rows and not self.start():
            return
        if self.shown < len(self.rows):
            self.advance()

    def run(self):
        self.pause()
        if (not self.rows or self.shown >= len(self.rows)) and not self.start():
            return
        self.tick()

    def tick(self):
        self.job = None
        if self.shown < len(self.rows):
            self.advance()
            if self.shown < len(self.rows):
                self.job = self.root.after(self.delay, self.tick)
        self.refresh_controls()

    def pause(self, say=False):
        if self.job:
            self.root.after_cancel(self.job)
            self.job = None
            if say:
                self.msg.set("Paused. " + self.msg.get())
        elif say:
            self.msg.set("Nothing is running. Press Run or Step to continue.")
        self.refresh_controls()
        self.refresh_status()

    def refresh_status(self):
        """One word for what the simulation is doing, shown as the panel headline.
        Not Started -> Running -> Paused -> Finished, with Error whenever the last attempt to
        start was refused. Running means the Run animation is actually ticking; any other point
        inside a run is Paused, because nothing is moving and Step/Run is what resumes it."""
        if not getattr(self, "status_lbl", None):
            return  # called before build() finished
        if getattr(self, "_err", False):
            word, colour = "Error", ("#c62828", "#ef5350")
        elif not self.rows:
            word, colour = "Not Started", ("gray45", "#8b97a3")
        elif self.shown >= len(self.rows):
            word, colour = "Finished", ("#2e7d32", "#66bb6a")
        elif self.job is not None:
            word, colour = "Running", ("#ef6c00", "#ffb74d")
        else:
            word, colour = "Paused", ("#1565c0", "#64b5f6")
        if self.sim_status.get() != word:
            self.sim_status.set(word)
        self.status_lbl.configure(text_color=colour)

    def refresh_controls(self):
        """The buttons show what is possible right now: Pause only while animating, the rest only when idle.
        A CTk button redraws itself on every configure, so this returns early unless the answer changed -
        calling it on all four buttons per step would cost more than the whole step."""
        if not getattr(self, "cbtn", None):
            return  # called before build() finished
        running = self.job is not None
        if getattr(self, "_running", None) == running:
            return
        self._running = running
        for key in ("step", "run"):
            self.cbtn[key].configure(state="disabled" if running else "normal")
        self.cbtn["pause"].configure(state="normal" if running else "disabled")

    def reset(self):
        self.pause()
        prev_cur, prev_act = self.cur, self.active  # what highlight() must take back off
        self.rows, self.shown, self.active = [], 0, None
        self.cur = self.initial if self.initial in self.states else None
        self.table.delete(*self.table.get_children())
        self._latest = None
        self.outseq.set(DASH)
        self.msg.set(f"Ready. The machine is in initial state {self.cur}; its output is {self.states[self.cur]}. "
                     "Press Step or Run." if self.cur else "")
        self._err = False
        self.update_info()
        self.highlight(prev_cur, prev_act)
        self.refresh_status()

    def copy_out(self, *_):
        seq = out_string(self.rows[:self.shown])
        if not seq:
            return self.msg.set("Nothing to copy yet - press Step or Run first.")
        self.root.clipboard_clear()
        self.root.clipboard_append(seq)
        self.msg.set(f"Copied the output sequence to the clipboard: {seq}")

    def verdict_text(self):
        """What the 'Expected output' box should say right now, or "" when nobody asked to be checked."""
        want = self.exp.get().strip()
        if not want:
            return ""
        if self.rows and self.inp.get().strip() == self.text:  # this run matches the box above it
            if self.shown == len(self.rows):  # finished: actually compare
                got = out_string(self.rows)
                if want == got:
                    return f"✓ Matches: {got}"
                if len(want) != len(got):
                    return f"✗ Expected {len(want)} symbol(s), the machine printed {len(got)}."
                k = next(i for i in range(len(want)) if want[i] != got[i])
                return f"✗ Expected {want}, the machine printed {got} - first difference at position {k + 1}."
            return "Keep running to check."
        # Nothing to compare against yet. Answer the length rule now, but only when it is provable -
        # it holds exactly when every state prints a single symbol.
        n = len(self.inp.get().strip()) + 1
        if self.states and all(len(o) == 1 for o in self.states.values()) and len(want) != n:
            return f"⚠️ Expected output needs {n} symbol(s) for that input."
        return "Press Run to check."

    def next_hint(self):
        if not self.states:
            return "Add your first state: type a name and an output on the left, then click Add State."
        if self.initial is None:
            return "Pick the start state: click a state in the list, then click Set as Initial State."
        if not self.trans:
            return "Add transitions: choose From, type one input symbol, choose To, then click Add Transition."
        errs = validate(self.states, self.initial, self.trans)
        if errs:
            detail = errs[0].splitlines()  # errors are multi-line now: headline / detail / fix
            return "Almost there - " + (detail[1] if len(detail) > 1 else detail[0])
        if not self.rows:
            return "Type an input string (like 10110) and press Step or Run."
        if self.shown >= len(self.rows):
            return f"Finished! Output sequence: {out_string(self.rows)}.  Press Reset Simulation to try again."
        return "Press Step to read one symbol, Run to animate, or Pause to stop."

    def update_info(self):
        i, s = self.info, self.states
        text = self.text if self.rows else self.inp.get().strip()
        if getattr(self, "run_in", None):
            self.run_in.set(text or DASH)   # the Input line of the output panel
        i["States"].set(len(s))
        i["Transitions"].set(len(self.trans))
        i["Initial state"].set(self.initial or "(not set)")
        i["Current state"].set(self.cur or DASH)
        i["Current output"].set(s[self.cur] if self.cur in s else DASH)
        i["Input string"].set(text or "(empty)")
        if self.rows:
            done = self.shown - 1
            i["Input symbol"].set(text[done - 1] if done >= 1 else DASH)  # symbol just read (nothing at step 0)
            i["Position"].set(f"{done} of {len(text)} read" + (f" (next: {text[done]})" if done < len(text) else " (finished)"))
        else:
            i["Input symbol"].set(DASH)
            i["Position"].set("not started")
        v = self.verdict_text()
        self.verdict.set(v)
        self.verdict_lbl.configure(
            text_color=("#c62828", "#ef5350") if v[:1] in ("✗", "⚠") else
            ("#2e7d32", "#66bb6a") if v[:1] == "✓" else ("gray50", "#9aa7b3"))
        self.update_progress()
        self.hint.set(self.next_hint())

    def update_progress(self):
        """How far the run has got, as a bare count - the panel's label supplies the words."""
        total = (len(self.rows) - 1) if self.rows else len(self.inp.get().strip())
        done = min(max(0, self.shown - 1), total)
        self.prog.set(f"{done} / {total}")
