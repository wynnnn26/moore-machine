"""_e2e.py - external end-to-end test driver for moore.py.

Read-only with respect to the application: it never edits moore.py, it only drives it.
Run:  python -u _e2e.py
"""
import json
import os
import random
import sys
import tempfile
import time

sys.stdout.reconfigure(encoding="utf-8", errors="backslashreplace")
sys.stderr.reconfigure(encoding="utf-8", errors="backslashreplace")

import customtkinter as ctk
from tkinter import filedialog, messagebox, TclError
from PIL import Image

import moore
from moore import (check_input, ex_pair_check, from_dict, no_dups, out_string,
                   simulate, synthesize, to_dict, validate)

DASH = moore.DASH
TMP = tempfile.mkdtemp(prefix="moore_e2e_")

# ---------------------------------------------------------------- result bookkeeping
RESULTS = []          # (section, id, name, status, detail)


def check(sec, cid, name, cond, detail=""):
    st = "PASS" if cond else "FAIL"
    RESULTS.append((sec, cid, name, st, "" if cond else str(detail)))
    print("  [%s] %-5s %s%s" % (st, cid, name, ("" if cond else "  -- " + str(detail))), flush=True)
    return bool(cond)


def skip(sec, cid, name, why):
    RESULTS.append((sec, cid, name, "SKIP", why))
    print("  [SKIP] %-5s %s  -- %s" % (cid, name, why), flush=True)


# ---------------------------------------------------------------- harness
root = ctk.CTk()
ASKED = []                       # every confirmation the app raises
ANSWER = [True]                  # what askyesno returns


def _ask(*a, **k):
    ASKED.append((a[0] if a else "", a[1] if len(a) > 1 else ""))
    return ANSWER[0]


messagebox.askyesno = _ask
messagebox.showerror = messagebox.showwarning = messagebox.showinfo = lambda *a, **k: None
filedialog.asksaveasfilename = lambda **k: ""
filedialog.askopenfilename = lambda **k: ""

app = moore.App(root)
root.update()
app.delay = 10                    # Run animation: 10 ms/symbol so tests do not wait 700 ms


def pump(ms=200):
    end = time.time() + ms / 1000.0
    while time.time() < end:
        root.update()
        time.sleep(0.004)


def sel(tree, iid):
    tree.selection_set(iid)
    root.update()


def last_notice():
    return app.notices[-1] if app.notices else ""


def tree_bar(t):                  # the CTkScrollbar packed in a table's slot
    def find(w):
        for c in w.winfo_children():
            if c.__class__.__name__ == "CTkScrollbar":
                return c
            r = find(c)
            if r is not None:
                return r
    return find(t.master)


class Ev:
    def __init__(self, widget, x=0, y=0):
        self.widget, self.x, self.y = widget, x, y


def machine():
    return dict(app.states), app.initial, dict(app.trans)


def say(msg, title="T"):
    app.err(msg, title)


# ================================================================ 1. startup / structure
S = "1 startup"
print("\n== %s ==" % S, flush=True)
check(S, "1.1", "main window is mapped", bool(root.winfo_ismapped()))
check(S, "1.2", "the three tables exist", all(hasattr(app, k) for k in ("st", "tt", "table")))
for k in ("start",):
    check(S, "1.3", "Start button is gone from the dashboard", k not in (app.cbtn or {}),
          "cbtn keys=%s" % list((app.cbtn or {})))
check(S, "1.4", "Step / Run / Pause present",
      all(k in app.cbtn for k in ("step", "run", "pause")))
titles = []
stack = [root]
while stack:
    w = stack.pop()
    try:
        t = w.cget("text")
    except Exception:
        t = ""
    if isinstance(t, str) and t:
        titles.append(t)
    stack.extend(w.winfo_children())
check(S, "1.5", "no 'Step 1 / Step 2 / Step 3' labels anywhere",
      not [t for t in titles if t.startswith(("Step 1", "Step 2", "Step 3"))],
      [t for t in titles if t.startswith("Step ")][:4])
check(S, "1.6", "panels are unnumbered (States / Transitions / Simulation)",
      not [t for t in titles if t[:2] in ("1.", "2.", "3.")],
      [t for t in titles if t[:2] in ("1.", "2.", "3.")])

# ================================================================ 2. states CRUD
S = "2 states"
print("\n== %s ==" % S, flush=True)
app.clear()
pump(50)
check(S, "2.1", "clear starts empty", not app.states and app.initial is None and not app.trans)
before = machine()

app.name.set(""), app.out.set("0")
app.add_state()
check(S, "2.2", "empty name refused", "Empty state name" in last_notice(), last_notice()[:60])
check(S, "2.3", "refusal leaves machine unchanged", machine() == before)

app.name.set("q0"), app.out.set("")
app.add_state()
check(S, "2.4", "missing output refused", "Missing state output" in last_notice(), last_notice()[:60])
check(S, "2.5", "still unchanged after that refusal", not app.states)

app.name.set("q0"), app.out.set("0")
app.add_state()
check(S, "2.6", "first state added", app.states == {"q0": "0"})
check(S, "2.7", "first state becomes the initial state", app.initial == "q0")

app.name.set("q0"), app.out.set("1")
app.add_state()
check(S, "2.8", "duplicate name refused", "Duplicate state name" in last_notice(), last_notice()[:60])
check(S, "2.9", "no duplicate created", app.states == {"q0": "0"}, app.states)

app.name.set("q1"), app.out.set("1")
app.add_state()
check(S, "2.10", "second state added", app.states == {"q0": "0", "q1": "1"})
check(S, "2.11", "States table has both rows", list(app.st.get_children()) == ["q0", "q1"])

# transitions that must follow a rename
app.src.set("q0"), app.sym.set("1"), app.dst.set("q1"), app.add_trans()
app.src.set("q1"), app.sym.set("0"), app.dst.set("q0"), app.add_trans()
check(S, "2.12", "transitions added", len(app.trans) == 2, app.trans)

sel(app.st, "q0")
app.name.set("A"), app.out.set("1")
app.edit_state()
check(S, "2.13", "rename follows into the States table", "A" in app.states)
check(S, "2.14", "rename follows into transitions",
      ("A", "1") in app.trans and all(s != "q0" for (s, _ ) in app.trans), app.trans)
check(S, "2.15", "rename follows into the initial state", app.initial == "A", app.initial)
check(S, "2.16", "old name is gone", "q0" not in app.states)

sel(app.st, "A")
app.name.set("q1"), app.out.set("1")
app.edit_state()
check(S, "2.17", "rename onto an existing name refused", "Duplicate state name" in last_notice())
check(S, "2.18", "machine unchanged by refused rename",
      machine() == ({"A": "1", "q1": "1"}, "A", {("A", "1"): "q1", ("q1", "0"): "A"}), machine())

# delete: decline then accept
sel(app.st, "A")
ANSWER[0] = False
ASKED.clear()
app.del_state()
check(S, "2.19", "deleting a state asks first", bool(ASKED), ASKED[:1])
check(S, "2.20", "declining changes nothing", machine()[0] == {"A": "1", "q1": "1"}, machine())
ANSWER[0] = True
ASKED.clear()
app.del_state()
check(S, "2.21", "accepting deletes the state and its transitions",
      app.states == {"q1": "1"} and app.trans == {}, machine())
check(S, "2.22", "deleting the initial state clears it", app.initial is None, app.initial)
check(S, "2.23", "and warns the user", last_notice().startswith("WARNING"), last_notice()[:70])
check(S, "2.24", "validate() now reports no initial state",
      any("No initial state" in e for e in validate(app.states, app.initial, app.trans)),
      validate(app.states, app.initial, app.trans))

# ================================================================ 3. transitions CRUD
S = "3 transitions"
print("\n== %s ==" % S, flush=True)
app.clear()
pump(50)
app.name.set("q0"), app.out.set("0"), app.add_state()
app.name.set("q1"), app.out.set("1"), app.add_state()
before = machine()

app.src.set(""), app.sym.set("0"), app.dst.set("q1")
app.add_trans()
check(S, "3.1", "unknown From state refused", "Invalid state reference" in last_notice())
app.src.set("q0"), app.dst.set("nope")
app.add_trans()
check(S, "3.2", "unknown To state refused", "Invalid state reference" in last_notice())
app.src.set("q0"), app.dst.set("q1"), app.sym.set("")
app.add_trans()
check(S, "3.3", "empty symbol refused", "Empty input symbol" in last_notice())
app.sym.set("01")
app.add_trans()
check(S, "3.4", "two-character symbol refused", "Invalid input symbol" in last_notice())
check(S, "3.5", "all four refusals left the machine alone", machine() == before, machine())

app.sym.set("0")
app.add_trans()
check(S, "3.6", "valid transition added", app.trans == {("q0", "0"): "q1"}, app.trans)
n = len(app.trans)
app.sym.set("0")                    # add_trans clears the symbol box for the next one
app.add_trans()
check(S, "3.7", "duplicate transition refused", "Duplicate transition" in last_notice(),
      last_notice()[:70])
check(S, "3.8", "no duplicate row created", len(app.trans) == n, app.trans)

# edit: change destination
sel(app.tt, str(app.tkeys.index(("q0", "0"))))
app.dst.set("q0")
app.edit_trans()
check(S, "3.9", "edit changes the destination", app.trans[("q0", "0")] == "q0", app.trans)

# self-loop + transition back to the initial state
app.src.set("q1"), app.sym.set("1"), app.dst.set("q1"), app.add_trans()
app.src.set("q1"), app.sym.set("0"), app.dst.set("q0"), app.add_trans()
check(S, "3.10", "self-loop stored", app.trans[("q1", "1")] == "q1")
check(S, "3.11", "transition back to the initial state stored", app.trans[("q1", "0")] == "q0")
check(S, "3.12", "Transitions table lists all three", len(app.tt.get_children()) == 3)

# delete: decline then accept
sel(app.tt, str(app.tkeys.index(("q0", "0"))))
ANSWER[0] = False
ASKED.clear()
app.del_trans()
check(S, "3.13", "deleting a transition asks first", bool(ASKED), ASKED[:1])
check(S, "3.14", "declining changes nothing", len(app.trans) == 3, app.trans)
ANSWER[0] = True
ASKED.clear()
app.del_trans()
check(S, "3.15", "accepting deletes it", len(app.trans) == 2, app.trans)

# delete with nothing selected
app.tt.selection_remove(app.tt.get_children())
app.notices.clear()
app.del_trans()
check(S, "3.16", "delete with no selection is refused", "Nothing selected" in last_notice())

# ================================================================ 4. initial state
S = "4 initial state"
print("\n== %s ==" % S, flush=True)
app.clear()
pump(50)
app.name.set("q0"), app.out.set("0"), app.add_state()
app.name.set("q1"), app.out.set("1"), app.add_state()
sel(app.st, "q1")
app.set_initial()
check(S, "4.1", "Set as Initial changes the start state", app.initial == "q1", app.initial)
app.st.selection_remove(app.st.get_children())
app.notices.clear()
app.set_initial()
check(S, "4.2", "Set as Initial with nothing selected is refused",
      "No initial state" in last_notice())
check(S, "4.3", "refusal kept the old start state", app.initial == "q1", app.initial)
check(S, "4.4", "validate() is happy with this machine",
      validate(app.states, app.initial, app.trans) == [],
      validate(app.states, app.initial, app.trans))

# ================================================================ 5. validate() rules
S = "5 validate"
print("\n== %s ==" % S, flush=True)
check(S, "5.1", "empty machine is reported", any("No states yet" in e for e in validate({}, None, {})))
check(S, "5.2", "no initial state is reported",
      any("No initial state" in e for e in validate({"q0": "0"}, None, {})))
check(S, "5.3", "missing transition is reported",
      any("Missing transition" in e for e in
          validate({"q0": "0", "q1": "1"}, "q0", {("q0", "0"): "q0"})),
      validate({"q0": "0", "q1": "1"}, "q0", {("q0", "0"): "q0"}))
check(S, "5.4", "empty state name is reported",
      any("Empty state name" in e for e in validate({"  ": "0"}, None, {})))
check(S, "5.5", "missing state output is reported",
      any("Missing state output" in e for e in validate({"q0": " "}, "q0", {})))
check(S, "5.6", "empty input symbol is reported",
      any("Empty input symbol" in e for e in validate({"q0": "0"}, "q0", {("q0", ""): "q0"})))
check(S, "5.7", "dangling state reference is reported",
      any("Invalid state reference" in e for e in validate({"q0": "0"}, "q0", {("q0", "0"): "ghost"})))
check(S, "5.8", "initial state that no longer exists is reported",
      any("No initial state" in e for e in validate({"q0": "0"}, "ghost", {})))
check(S, "5.9", "a complete machine reports nothing", validate({"q0": "0"}, "q0", {("q0", "0"): "q0"}) == [])
check(S, "5.10", "need_start=False skips only the run-time rules",
      validate({"q0": "0"}, None, {}, need_start=False) == [],
      validate({"q0": "0"}, None, {}, need_start=False))

# ================================================================ 6. input validation
S = "6 input"
print("\n== %s ==" % S, flush=True)
T = {("q0", "0"): "q0", ("q0", "1"): "q1", ("q1", "0"): "q0", ("q1", "1"): "q1"}
check(S, "6.1", "empty input is rejected", "empty" in (check_input(T, "") or "x"))
check(S, "6.2", "unknown symbol is rejected",
      check_input({("q0", "0"): "q0"}, "01") is not None and "2" not in check_input({("q0", "0"): "q0"}, "01"))
check(S, "6.3", "the unknown symbol is named in the message", "'1'" in check_input({("q0", "0"): "q0"}, "01"),
      check_input({("q0", "0"): "q0"}, "01"))
check(S, "6.4", "a stray space is named visibly", "' '" in check_input(T, "1 0"), check_input(T, "1 0"))
check(S, "6.5", "a legal input passes", check_input(T, "10110") is None)
check(S, "6.6", "input over an empty transition set is rejected", check_input({}, "0") is not None)

# ================================================================ 7. Moore rules (pure)
S = "7 moore rules"
print("\n== %s ==" % S, flush=True)
S2 = {"q0": "0", "q1": "1"}
T2 = {("q0", "0"): "q0", ("q0", "1"): "q1", ("q1", "0"): "q0", ("q1", "1"): "q1"}
rows = simulate(S2, "q0", T2, "10110")
check(S, "7.1", "step 0 prints the INITIAL state's output before any input",
      rows[0] == (0, DASH, DASH, "q0", "0"), rows[0])
check(S, "7.2", "output is one symbol longer than the input", len(rows) == len("10110") + 1)
check(S, "7.3", "output string is 010110", out_string(rows) == "010110", out_string(rows))
check(S, "7.4", "self-loop holds the state and its output",
      simulate(S2, "q0", T2, "00")[2][3] == "q0" and out_string(simulate(S2, "q0", T2, "00")) == "000",
      out_string(simulate(S2, "q0", T2, "00")))
back = simulate(S2, "q0", T2, "10")
check(S, "7.5", "transition back to the initial state lands on q0", back[-1][3] == "q0", back)
check(S, "7.6", "the Moore rule: output comes from the state you ARRIVE in",
      all(r[4] == S2[r[3]] for r in rows), rows)
try:
    simulate(S2, "q0", {("q0", "0"): "q0"}, "01")
    check(S, "7.7", "a missing transition raises instead of inventing one", False, "no exception")
except ValueError as e:
    check(S, "7.7", "a missing transition raises instead of inventing one", "Missing transition" in str(e), e)
check(S, "7.8", "multi-symbol outputs are joined with a space",
      out_string([(0, DASH, DASH, "a", "00"), (1, "0", "a", "b", "11")]) == "00 11",
      out_string([(0, DASH, DASH, "a", "00"), (1, "0", "a", "b", "11")]))

# ================================================================ 8. simulation controls
S = "8 simulation"
print("\n== %s ==" % S, flush=True)
app.clear()
pump(50)
app.inp.set("10110")
app.notices.clear()
ok_start = app.start()
check(S, "8.1", "start on an empty machine is refused", not ok_start, ok_start)
check(S, "8.2", "and explained", "No states yet" in last_notice(), last_notice()[:60])

app.load_example(ask=False)
pump(50)
app.inp.set("")
app.notices.clear()
check(S, "8.3", "empty input refuses to start", not app.start(), "start returned truthy")
check(S, "8.4", "empty input is explained", "input string is empty" in last_notice(), last_notice()[:60])
check(S, "8.5", "the machine itself is untouched", app.states == {"q0": "0", "q1": "1"}, app.states)

app.inp.set("10112")
app.notices.clear()
check(S, "8.6", "input with an unknown symbol refuses to start", not app.start())
check(S, "8.7", "unknown symbol is named", "'2'" in last_notice(), last_notice()[:80])
check(S, "8.8", "machine untouched by a bad input", app.states == {"q0": "0", "q1": "1"})

# a machine with a gap: validate must stop it before simulate does
app.states = {"q0": "0", "q1": "1"}
app.initial = "q0"
app.trans = {("q0", "0"): "q0"}
app.changed()
pump(50)
app.inp.set("00")
app.notices.clear()
check(S, "8.9", "a gap in the transitions refuses to start", not app.start())
check(S, "8.10", "the gap is reported as a missing transition", "Missing transition" in last_notice(),
      last_notice()[:120])
check(S, "8.11", "nothing was invented for the gap", app.trans == {("q0", "0"): "q0"}, app.trans)

# step-by-step run matches the pure simulation
app.load_example(ask=False)
pump(50)
app.inp.set("10110"), app.exp.set("010110")
check(S, "8.12", "start succeeds on a good machine", bool(app.start()))
check(S, "8.13", "step 0 shows the initial output", app.outseq.get() == "0", app.outseq.get())
check(S, "8.14", "status is Paused at step 0", app.sim_status.get() in ("Paused", "Finished"),
      app.sim_status.get())
for _ in range(5):
    app.step()
pump(50)
check(S, "8.15", "stepping produces exactly the pure result",
      app.outseq.get() == out_string(simulate(app.states, app.initial, app.trans, "10110")),
      app.outseq.get())
check(S, "8.16", "results table has one row per step", len(app.table.get_children()) == 6,
      len(app.table.get_children()))
check(S, "8.17", "status is Finished", app.sim_status.get() == "Finished", app.sim_status.get())
check(S, "8.18", "verdict matches the expected output", app.verdict.get().startswith("✓"),
      app.verdict.get())

# Run animates to the end
app.reset()
pump(50)
check(S, "8.19", "reset clears the run", app.outseq.get() == DASH and not app.table.get_children())
check(S, "8.20", "reset keeps the machine", app.states == {"q0": "0", "q1": "1"}, app.states)
check(S, "8.21", "status is Not Started after reset", app.sim_status.get() == "Not Started",
      app.sim_status.get())
app.run()
pump(1200)
check(S, "8.22", "Run animates to the end", app.shown == len(app.rows), (app.shown, len(app.rows)))
check(S, "8.23", "Run produces the full output", app.outseq.get() == "010110", app.outseq.get())

# pause mid-run
app.reset()
pump(30)
app.delay = 300
app.run()
pump(120)
running = app.job is not None
app.pause(True)
check(S, "8.24", "Pause stops an in-flight Run", running and app.job is None, (running, app.job))
check(S, "8.25", "Pause reports the stopped run", app.msg.get().startswith("Paused"), app.msg.get()[:40])
check(S, "8.26", "status is Paused", app.sim_status.get() == "Paused", app.sim_status.get())
app.pause(True)
check(S, "8.27", "Pause with nothing running says so", "Nothing is running" in app.msg.get(),
      app.msg.get()[:60])
app.delay = 10
app.reset()

# buttons are enabled/disabled around a run
app.delay = 400
app.run()
pump(80)
disabled = [k for k in ("step", "run") if str(app.cbtn[k].cget("state")) == "disabled"]
pause_on = str(app.cbtn["pause"].cget("state")) != "disabled"
app.pause()
check(S, "8.28", "Step/Run are disabled while animating", len(disabled) == 2, disabled)
check(S, "8.29", "Pause is enabled only while animating", pause_on)
app.delay = 10
app.reset()

# ================================================================ 9. expected output
S = "9 expected output"
print("\n== %s ==" % S, flush=True)
app.load_example(ask=False)
app.inp.set("10110")
app.exp.set("010110")
check(S, "9.1", "before running: told to run", app.verdict_text() in ("Press Run to check.",), app.verdict_text())
app.exp.set("01011")
check(S, "9.2", "wrong length is caught before running",
      app.verdict_text().startswith("⚠️"), app.verdict_text())
app.exp.set("")
check(S, "9.3", "no expected output means no verdict is claimed", app.verdict_text() == "",
      repr(app.verdict_text()))
app.exp.set("010110")
app.start()
for _ in range(5):
    app.step()
pump(50)
check(S, "9.4", "match is reported", app.verdict_text().startswith("✓"), app.verdict_text())
app.exp.set("010111")
check(S, "9.5", "mismatch names the first difference",
      "first difference at position 6" in app.verdict_text(), app.verdict_text())
app.exp.set("111111")
check(S, "9.6", "mismatch at position 1 is reported",
      "first difference at position 1" in app.verdict_text(), app.verdict_text())
app.exp.set("01")
check(S, "9.7", "length mismatch after a run is reported",
      app.verdict_text().startswith("✗ Expected 2 symbol"), app.verdict_text())
app.exp.set("010110")
app.reset()
app.start()
pump(30)
check(S, "9.8", "half-run says keep running", app.verdict_text() == "Keep running to check.",
      app.verdict_text())
app.copy_out()
pump(30)
try:
    clip = root.clipboard_get()
except TclError:
    clip = ""
check(S, "9.9", "Copy Output puts the sequence on the clipboard", clip == "0", clip)
for _ in range(5):
    app.step()
app.copy_out()
pump(30)
try:
    clip = root.clipboard_get()
except TclError:
    clip = ""
check(S, "9.10", "Copy Output after a full run", clip == "010110", clip)

# ================================================================ 10. Auto Build
S = "10 auto build"
print("\n== %s ==" % S, flush=True)
app.load_example(ask=False)
pump(40)


def build(inp, out):
    """Open the dialog, type, press Build. Returns (dialog_open, notice_or_none)."""
    app.auto_build_dialog()
    w = app.dialogs[-1]
    pump(60)
    app.ex_in.set(inp), app.ex_out.set(out)
    app.notices.clear()
    ASKED.clear()
    app.auto_build_go(w)
    pump(120)
    return w, (app.ex_err.get() if w.winfo_exists() else ""), list(ASKED)


before = machine()
w, msg, asked = build("10110", "010110")
check(S, "10.1", "valid build closes the dialog", not w.winfo_exists())
check(S, "10.2", "replacing an existing machine asks first", len(asked) == 1, asked)
check(S, "10.3", "generated machine validates", validate(app.states, app.initial, app.trans) == [],
      validate(app.states, app.initial, app.trans))
check(S, "10.4", "generated machine reproduces the example",
      out_string(simulate(app.states, app.initial, app.trans, "10110")) == "010110",
      out_string(simulate(app.states, app.initial, app.trans, "10110")))
check(S, "10.5", "input and expected output are filled in",
      app.inp.get() == "10110" and app.exp.get() == "010110", (app.inp.get(), app.exp.get()))
check(S, "10.6", "the results table was filled", len(app.table.get_children()) == 6,
      len(app.table.get_children()))
check(S, "10.7", "verdict is a match", app.verdict.get().startswith("✓"), app.verdict.get())
check(S, "10.8", "a success overlay is shown", bool(app.notices) and "Built" in last_notice(),
      last_notice()[:60])
app.dismiss_notice()

# --- refusals must not touch the machine
base = machine()
cases = [("", "", "Input String is empty"),
         ("10110", "", "Expected Output is empty"),
         ("101 10", "", "contains a space"),
         ("10110", "0101 1", "contains a space"),
         ("10110", "10110", "Wrong output length"),
         ("10110", "01011", "Wrong output length")]
for i, (inp, out, want) in enumerate(cases, 1):
    w, msg, asked = build(inp, out)
    ok = want in msg and w.winfo_exists() and machine() == base and not asked
    check(S, "10.%d" % (8 + i), "refusal %d (%r/%r) shown inside the dialog, machine intact"
          % (i, inp, out), ok, "msg=%r open=%s same=%s asked=%s" % (msg[:40], w.winfo_exists(),
                                                                    machine() == base, asked))
    w.destroy()
    pump(40)

# --- the dialog recovers for a retry
w, msg, asked = build("10110", "")
check(S, "10.15", "boxes keep what was typed for the retry",
      app.ex_in.get() == "10110" and app.ex_out.get() == "", (app.ex_in.get(), app.ex_out.get()))
app.ex_len_refresh()
check(S, "10.16", "the hint says the output is required",
      "Expected Output is required" in app.ex_len_hint.get(), app.ex_len_hint.get())
w.destroy()
pump(40)

# --- optional expected output (the brief asks for it; the app requires it)
w, msg, asked = build("101", "")
optional_ok = not w.winfo_exists()
check(S, "10.17", "Auto Build with BLANK expected output produces a machine", optional_ok,
      "dialog stayed open, message=%r" % msg[:70])
if not optional_ok:
    skip(S, "10.18", "optional-output machine validates", "no machine was built")
    skip(S, "10.19", "optional-output machine runs the input", "no machine was built")
    w.destroy()
    pump(40)
else:
    check(S, "10.18", "optional-output machine validates",
          validate(app.states, app.initial, app.trans) == [])

# --- synthesize: correctness, conflicts, impossible requirements
S = "10b synthesize"
print("\n== %s ==" % S, flush=True)
pairs = [("0", "00"), ("1", "11"), ("10110", "010110"), ("000", "1111"),
         ("1111", "01001"), ("10", "010"), ("0101", "10101")]
allok = True
why = ""
for inp, out in pairs:
    st, ini, tr, _d = synthesize([(inp, out)])
    got = out_string(simulate(st, ini, tr, inp))
    if got != out or validate(st, ini, tr) != []:
        allok, why = False, "%r -> %r != %r  errs=%s" % (inp, got, out, validate(st, ini, tr))
check(S, "10b.1", "every single example is reproduced exactly", allok, why)
# explicit total (no gap) check
tot = True
totwhy = ""
for inp, out in pairs:
    st, ini, tr, _ = synthesize([(inp, out)])
    alpha = {x for _, x in tr}
    missing = [s for s in st for a in alpha if (s, a) not in tr]
    if missing:
        tot, totwhy = False, "%r missing %s" % (inp, missing)
check(S, "10b.2", "generated machines have every transition", tot, totwhy)

# real checks
try:
    synthesize([("10", "1")])
    check(S, "10b.4", "impossible: output shorter than input+1 raises", False, "no exception")
except ValueError as e:
    check(S, "10b.4", "impossible: output shorter than input+1 raises",
          "Wrong output length" in str(e), e)
try:
    synthesize([("00", "111"), ("0", "01")])
    check(S, "10b.5", "conflicting examples are detected", False, "no exception")
except ValueError as e:
    check(S, "10b.5", "conflicting examples are detected", "Conflicting examples" in str(e), e)
try:
    synthesize([("0", "11"), ("0", "22")])
    check(S, "10b.6", "same input, two different outputs, is a conflict", False, "no exception")
except ValueError as e:
    check(S, "10b.6", "same input, two different outputs, is a conflict",
          "Conflicting examples" in str(e), e)
try:
    synthesize([])
    check(S, "10b.7", "no examples raises", False, "no exception")
except ValueError as e:
    check(S, "10b.7", "no examples raises", "No examples" in str(e), e)

# a single correct-length example is ALWAYS realisable - report what actually happens
try:
    st, ini, tr, _ = synthesize([("01", "101")])
    check(S, "10b.8", "single well-formed example always fits",
          out_string(simulate(st, ini, tr, "01")) == "101", out_string(simulate(st, ini, tr, "01")))
except ValueError as e:
    check(S, "10b.8", "single well-formed example always fits", False, e)

# ex_pair_check
check(S, "10b.9", "ex_pair_check accepts a well-formed pair", ex_pair_check("10110", "010110") is None)
check(S, "10b.10", "ex_pair_check rejects empty input", "Input String is empty" in ex_pair_check("", ""))
check(S, "10b.11", "ex_pair_check rejects blank output",
      "Expected Output is empty" in ex_pair_check("10110", ""))
check(S, "10b.12", "ex_pair_check rejects wrong length",
      "Wrong output length" in ex_pair_check("10110", "1011"))
check(S, "10b.13", "ex_pair_check rejects a space in the input",
      "contains a space" in ex_pair_check("10 1", "01010"))
check(S, "10b.14", "ex_pair_check rejects a space in the output",
      "contains a space" in ex_pair_check("101", "01 10"))

# randomised property test
random.seed(20261014)
bad = []
for _ in range(60):
    n = random.randint(0, 8)
    inp = "".join(random.choice("01") for _ in range(n))
    out = "".join(random.choice("01") for _ in range(n + 1))
    try:
        st, ini, tr, _ = synthesize([(inp, out)])
        if out_string(simulate(st, ini, tr, inp)) != out or validate(st, ini, tr) != []:
            bad.append((inp, out))
    except ValueError as e:
        bad.append((inp, out, str(e)))
check(S, "10b.15", "60 random (input, output) pairs all round-trip", not bad, bad[:3])

# ================================================================ 11. overlays
S = "11 overlays"
print("\n== %s ==" % S, flush=True)
app.load_example(ask=False)
pump(30)
app.dismiss_notice()
app.err("body text here", "Title")
check(S, "11.1", "an error overlay appears", app._notice is not None)
check(S, "11.2", "it is recorded in history", "Title" in last_notice() and "body text here" in last_notice(),
      last_notice()[:60])
inside_widget = app._notice
app._notice_hit(Ev(inside_widget))
check(S, "11.3", "clicking INSIDE it leaves it alone", app._notice is not None)
app._notice_hit(Ev(app.root))
check(S, "11.4", "clicking OUTSIDE dismisses it", app._notice is None, app._notice)
app.warn("just so you know", "Heads up")
check(S, "11.5", "warnings are tagged in history", last_notice().startswith("WARNING"), last_notice()[:40])
app.dismiss_notice()
check(S, "11.6", "the close button dismisses", app._notice is None)
app.ok("all good", "Done")
check(S, "11.7", "success overlay shows", app._notice is not None)
app.err("second one", "Second")
check(S, "11.8", "one at a time - the newest replaces the old", app._notice is not None)
check(S, "11.9", "the app stays usable while an overlay is showing",
      (app.name.set("zz"), app.out.set("1"), app.add_state(), "zz" in app.states)[-1])
app.dismiss_notice()
del app.states["zz"]
app.changed()
pump(30)

# ================================================================ 12. scrollbars
S = "12 scrollbars"
print("\n== %s ==" % S, flush=True)
app.load_example(ask=False)
pump(60)
for i in range(40):
    app.name.set("s%d" % i)
    app.out.set("0")
    app.add_state()
pump(120)
check(S, "12.1", "States bar visible while rows overflow", tree_bar(app.st) is not None
      and tree_bar(app.st).winfo_ismapped(), tree_bar(app.st))
z0 = app.zoom
before = app.st.yview()
app.st.event_generate("<MouseWheel>", delta=-120, x=5, y=5, state=0)
pump(60)
after = app.st.yview()
check(S, "12.2", "wheel scrolls the States table", abs(after[0] - before[0]) > 1e-9, (before, after))
check(S, "12.3", "scrolling a table does NOT zoom the diagram", app.zoom == z0, (z0, app.zoom))
app.st.event_generate("<MouseWheel>", delta=120, x=5, y=5, state=0)
pump(60)
back = app.st.yview()
check(S, "12.4", "wheel scrolls back the other way", abs(back[0] - before[0]) < 1e-6, (before, back))
# shrink until everything fits - the bar must still be there
for iid in list(app.st.get_children())[2:]:
    app.st.delete(iid)
pump(120)
check(S, "12.5", "bar stays visible when the rows fit", tree_bar(app.st).winfo_ismapped())
app.load_example(ask=False)
pump(60)
app.inp.set("10110")
app.start()
for _ in range(5):
    app.step()
pump(60)
tb = tree_bar(app.table)
z1 = app.zoom
app.table.event_generate("<MouseWheel>", delta=-120, x=5, y=5, state=0)
pump(60)
check(S, "12.6", "results table wheel scrolls", tb is not None, tb)
check(S, "12.7", "results table wheel never zooms", app.zoom == z1, (z1, app.zoom))
app.tt.event_generate("<MouseWheel>", delta=-120, x=5, y=5, state=0)
pump(60)
check(S, "12.8", "transitions table wheel never zooms", app.zoom == z1, (z1, app.zoom))
sb = tree_bar(app.st)
check(S, "12.9", "scrollbar widget is reachable", sb is not None and sb.winfo_ismapped(), sb)
# sidebar notice area
check(S, "12.10", "sidebar content host exists", hasattr(app, "notice_host") and app.notice_host is not None)

# ================================================================ 13. diagram & view
S = "13 diagram"
print("\n== %s ==" % S, flush=True)
app.load_example(ask=False)
pump(80)
check(S, "13.1", "the diagram draws something", len(app.cv.find_all()) > 0, len(app.cv.find_all()))
ovals = [i for i in app.cv.find_all() if app.cv.type(i) == "oval"]
check(S, "13.2", "one oval per state, plus the extra ring on the initial state",
      len(ovals) == len(app.states) + 1, (len(ovals), len(app.states)))
z0 = app.zoom
app.zoom_in()
check(S, "13.3", "Zoom In increases the zoom", app.zoom > z0, (z0, app.zoom))
z1 = app.zoom
app.zoom_out()
check(S, "13.4", "Zoom Out decreases the zoom", app.zoom < z1, (z1, app.zoom))
app.fit_diagram()
check(S, "13.5", "Fit Diagram lands inside the allowed range", 0.35 <= app.zoom <= 3.0, app.zoom)
check(S, "13.6", "zoom label shows a percentage", str(app.zoomlbl.cget("text")).endswith("%"),
      app.zoomlbl.cget("text"))
# drag: Tk's "current" tag is what the OS sets when the pointer hovers a canvas item.
# A synthetic <Motion> does not set it here, so the test sets it the same way a hover would
# and then runs the real drag_start / drag_move / drag_end handlers with real event objects.
app.load_example(ask=False)
pump(80)
ovals = [i for i in app.cv.find_all() if app.cv.type(i) == "oval"]
x0 = dict(app.off)
item = ovals[0]
cx = int(sum(app.cv.coords(item)[0:2]) / 2)
cy = int(sum(app.cv.coords(item)[1:3]) / 2)
app.cv.addtag("current", "withtag", item)
pump(10)
app.drag_start(Ev(app.cv, cx, cy))
pump(20)
dragged = app.dragging
if dragged:
    app.drag_move(Ev(app.cv, cx + 150, cy + 90))
    app.drag_end(Ev(app.cv, cx, cy))
    pump(80)
moved = bool(dragged) and app.off.get(dragged) != x0.get(dragged)
check(S, "13.7", "pressing a state starts dragging it", bool(dragged),
      "dragging=%r" % (dragged,))
check(S, "13.8", "dragging moves the state", moved, (dragged, x0, app.off))
check(S, "13.9", "the diagram redraws after the drag",
      len([i for i in app.cv.find_all() if app.cv.type(i) == "oval"]) == len(app.states) + 1,
      len([i for i in app.cv.find_all() if app.cv.type(i) == "oval"]))
# panning: press empty canvas, drag
app.cv.event_generate("<Motion>", x=5, y=5)
pump(10)
app.cv.event_generate("<Button-1>", x=5, y=5)
pump(10)
app.cv.event_generate("<B1-Motion>", x=60, y=40)
pump(20)
app.cv.event_generate("<ButtonRelease-1>", x=60, y=40)
pump(60)
check(S, "13.10", "pressing empty canvas starts a pan, not a state drag", app.dragging is None,
      app.dragging)
app.load_example(ask=False)
pump(60)

# ================================================================ 14. save / load
S = "14 save load"
print("\n== %s ==" % S, flush=True)
app.load_example(ask=False)
pump(40)
path = os.path.join(TMP, "m.json")
filedialog.asksaveasfilename = lambda **k: path
app.save()
pump(60)
check(S, "14.1", "save writes a file", os.path.exists(path))
raw = json.load(open(path, encoding="utf-8"))
check(S, "14.2", "the file has states, initial and transitions",
      set(raw) >= {"states", "initial", "transitions"}, sorted(raw))
m = from_dict(raw)
check(S, "14.3", "the file round-trips to the same machine",
      m == ({"q0": "0", "q1": "1"}, "q0",
            {("q0", "0"): "q0", ("q0", "1"): "q1", ("q1", "0"): "q0", ("q1", "1"): "q1"}), m)
check(S, "14.4", "to_dict/from_dict are inverses", from_dict(to_dict(*m)) == m)

# load it back over the machine
filedialog.askopenfilename = lambda **k: path
app.clear()
pump(40)
app.load()
pump(80)
check(S, "14.5", "load restores the machine", app.states == {"q0": "0", "q1": "1"}, app.states)
check(S, "14.6", "load restores the start state", app.initial == "q0", app.initial)
check(S, "14.7", "load restores all four transitions", len(app.trans) == 4, app.trans)

before = machine()
bad = os.path.join(TMP, "bad.json")
open(bad, "w").write("{not json")
filedialog.askopenfilename = lambda **k: bad
app.notices.clear()
app.load()
pump(60)
check(S, "14.8", "corrupt file is refused", "Could not load" in last_notice(), last_notice()[:60])
check(S, "14.9", "corrupt load leaves the machine alone", machine() == before, machine())

bad2 = os.path.join(TMP, "dup.json")
open(bad2, "w").write('{"states": {"q0": "0", "q0": "1"}, "initial": "q0", "transitions": []}')
filedialog.askopenfilename = lambda **k: bad2
app.notices.clear()
app.load()
pump(60)
check(S, "14.10", "duplicate state names in a file are refused",
      "Could not load" in last_notice() and "twice" in last_notice(), last_notice()[:90])
check(S, "14.11", "machine still intact", machine() == before, machine())

bad3 = os.path.join(TMP, "dup2.json")
open(bad3, "w").write(json.dumps(
    {"states": {"q0": "0", "q1": "1"}, "initial": "q0",
     "transitions": [{"from": "q0", "input": "0", "to": "q0"},
                     {"from": "q0", "input": "0", "to": "q1"}]}))
filedialog.askopenfilename = lambda **k: bad3
app.notices.clear()
app.load()
pump(60)
check(S, "14.12", "duplicate transitions in a file are refused",
      "Duplicate transition" in last_notice(), last_notice()[:90])
check(S, "14.13", "machine still intact", machine() == before, machine())

bad4 = os.path.join(TMP, "ghost.json")
open(bad4, "w").write(json.dumps(
    {"states": {"q0": "0"}, "initial": "q0",
     "transitions": [{"from": "q0", "input": "0", "to": "ghost"}]}))
filedialog.askopenfilename = lambda **k: bad4
app.notices.clear()
app.load()
pump(60)
check(S, "14.14", "a transition to a missing state is refused",
      "Invalid state reference" in last_notice(), last_notice()[:90])
check(S, "14.15", "machine still intact", machine() == before, machine())

# PNG export
png = os.path.join(TMP, "d.png")
filedialog.asksaveasfilename = lambda **k: png
z = app.zoom
app.export_png()
pump(300)
check(S, "14.16", "export writes a PNG", os.path.exists(png))
if os.path.exists(png):
    with Image.open(png) as im:
        im.load()
        check(S, "14.17", "it is a real PNG of a sensible size",
              im.format == "PNG" and im.size[0] > 100 and im.size[1] > 100, (im.format, im.size))
        cols = im.convert("RGB").getcolors(maxcolors=1 << 22)
        check(S, "14.18", "it is not blank", cols is None or len(cols) > 8, cols and len(cols))
check(S, "14.19", "the zoom used for the capture is restored", app.zoom == z, (z, app.zoom))
app.clear()
pump(60)
app.notices.clear()
app.export_png()
pump(100)
check(S, "14.20", "exporting an empty diagram explains itself instead",
      "Nothing to export" in last_notice(), last_notice()[:60])

# ================================================================ 15. large machine / rapid
S = "15 large"
print("\n== %s ==" % S, flush=True)
app.clear()
pump(60)
t0 = time.perf_counter()
for i in range(100):
    app.name.set("q%d" % i)
    app.out.set(str(i % 2))
    app.add_state()
t_add = time.perf_counter() - t0
check(S, "15.1", "100 states added", len(app.states) == 100, len(app.states))
check(S, "15.2", "adding 100 states stays responsive", t_add < 10, "%.2fs" % t_add)
t0 = time.perf_counter()
per_add = []
for i in range(100):
    for a in "01":
        app.src.set("q%d" % i)
        app.sym.set(a)
        app.dst.set("q%d" % ((i + int(a)) % 100))
        ta = time.perf_counter()
        app.add_trans()
        per_add.append(time.perf_counter() - ta)
t_tr = time.perf_counter() - t0
check(S, "15.3", "200 transitions added", len(app.trans) == 200, len(app.trans))
check(S, "15.4", "adding them stays responsive", t_tr < 20, "%.2fs total, %.0f ms/add" % (t_tr, 1000 * t_tr / 200))
first10 = sum(per_add[:10]) / 10
last10 = sum(per_add[-10:]) / 10
print("      timing: first 10 adds %.1f ms each, last 10 adds %.1f ms each, total %.1fs"
      % (1000 * first10, 1000 * last10, t_tr), flush=True)
check(S, "15.5", "a complete 100-state machine validates",
      validate(app.states, app.initial, app.trans) == [],
      validate(app.states, app.initial, app.trans)[:2])
t0 = time.perf_counter()
errs = validate(app.states, app.initial, app.trans)
t_val = time.perf_counter() - t0
check(S, "15.6", "validate() is fast on 200 transitions", t_val < 1, "%.3fs" % t_val)
long_input = "01" * 150
app.inp.set(long_input)
t0 = time.perf_counter()
app.notices.clear()
started = app.start()
t_start = time.perf_counter() - t0
check(S, "15.7", "a 300-symbol input starts", bool(started), last_notice()[:60])
check(S, "15.8", "start on a long input is responsive", t_start < 3, "%.2fs" % t_start)
full = out_string(simulate(app.states, app.initial, app.trans, long_input))
check(S, "15.9", "output is one symbol longer than the input",
      len(full) == len(long_input) + 1 and app.outseq.get() == full[:1],
      (len(full), app.outseq.get()))
t0 = time.perf_counter()
while app.shown < len(app.rows):
    app.advance()
t_run = time.perf_counter() - t0
check(S, "15.10", "stepping 301 times is responsive", t_run < 15,
      "%.2fs total, %.0f ms/step" % (t_run, 1000 * t_run / max(1, len(app.rows))))
check(S, "15.11", "all 301 rows are shown", app.shown == len(app.rows) == 301,
      (app.shown, len(app.rows)))
t0 = time.perf_counter()
app.draw()
t_draw = time.perf_counter() - t0
check(S, "15.12", "redrawing 100 states is responsive", t_draw < 3, "%.2fs" % t_draw)
check(S, "15.13", "the diagram still draws 100 states (+ the initial-state ring)",
      len([i for i in app.cv.find_all() if app.cv.type(i) == "oval"]) == len(app.states) + 1,
      len([i for i in app.cv.find_all() if app.cv.type(i) == "oval"]))
pump(200)
check(S, "15.14", "the States table is scrollable with 100 rows",
      app.st.yview()[1] < 0.999, app.st.yview())
check(S, "15.15", "its bar is visible", tree_bar(app.st).winfo_ismapped())

# rapid actions
t0 = time.perf_counter()
for _ in range(60):
    app.step()
    app.reset()
    app.start()
t_rapid = time.perf_counter() - t0
check(S, "15.16", "180 rapid start/step/reset cycles stay responsive", t_rapid < 20, "%.2fs" % t_rapid)
check(S, "15.17", "the machine is still intact after the storm",
      len(app.states) == 100 and len(app.trans) == 200, (len(app.states), len(app.trans)))
# rapid refusals
app.notices.clear()
for _ in range(30):
    app.name.set("")
    app.out.set("")
    app.add_state()
check(S, "15.18", "30 rapid bad adds leave the machine alone", len(app.states) == 100, len(app.states))
n0 = len(app.notices)
check(S, "15.19", "the notice history is bounded", n0 <= 50, n0)

# ================================================================ 16. clear / example
S = "16 whole machine"
print("\n== %s ==" % S, flush=True)
app.load_example(ask=False)
pump(40)
before = machine()
ANSWER[0] = False
ASKED.clear()
app.clear()
check(S, "16.1", "Clear Machine asks first", bool(ASKED), ASKED[:1])
check(S, "16.2", "declining leaves everything", machine() == before, machine())
ANSWER[0] = True
ASKED.clear()
app.clear()
pump(60)
check(S, "16.3", "accepting clears states, initial and transitions",
      not app.states and app.initial is None and not app.trans, machine())
check(S, "16.4", "tables are emptied",
      not app.st.get_children() and not app.tt.get_children())
app.load_example(ask=False)
pump(60)
ASKED.clear()
app.load_example(ask=True)
check(S, "16.5", "Load Example over a machine asks first", bool(ASKED), ASKED[:1])
check(S, "16.6", "example is loaded", app.states == {"q0": "0", "q1": "1"} and app.inp.get() == "10110")

# ================================================================ 17. performance scaling
S = "17 performance"
print("\n== %s ==" % S, flush=True)
profile = []
step_ms = []
for n in (2, 20, 100):
    app.clear()
    pump(40)
    for i in range(n):
        app.name.set("q%d" % i)
        app.out.set("0")
        app.add_state()
    for i in range(n):                      # a complete machine: every state loops on 'a'
        app.src.set("q%d" % i)
        app.sym.set("a")
        app.dst.set("q%d" % i)
        app.add_trans()
    # --- cost of ONE step on a machine this size (advance() redraws everything)
    app.inp.set("a" * 20)
    if app.start():
        ts = []
        for _ in range(5):
            ta = time.perf_counter()
            app.advance()
            ts.append(time.perf_counter() - ta)
        step_ms.append((n, 1000 * sum(ts) / len(ts)))
    # --- cost of ONE more edit on a machine this size
    t = []
    for i in range(10):
        app.src.set("q0")
        app.sym.set(str(i))                 # 0..9, none of which is 'a'
        app.dst.set("q0")
        ta = time.perf_counter()
        app.add_trans()
        t.append(time.perf_counter() - ta)
    avg_ms = 1000 * sum(t) / len(t)
    profile.append((n, avg_ms))
    check(S, "17.%d" % len(profile),
          "one edit at %d states stays under 400 ms" % n, avg_ms < 400,
          "%.1f ms/edit" % avg_ms)
print("      edit scaling : " + "   ".join("%d states = %.1f ms" % p for p in profile), flush=True)
print("      step scaling : " + "   ".join("%d states = %.1f ms" % p for p in step_ms), flush=True)
check(S, "17.4", "one step at 100 states stays under 400 ms",
      step_ms and step_ms[-1][1] < 400, "%.1f ms/step" % (step_ms[-1][1] if step_ms else -1))
app.clear()
pump(40)

# ================================================================ 18. UI chrome
S = "18 ui chrome"
print("\n== %s ==" % S, flush=True)
app.load_example(ask=False)
pump(60)
m0 = ctk.get_appearance_mode()
app.toggle_theme()
pump(100)
check(S, "18.1", "theme toggle flips the appearance mode", ctk.get_appearance_mode() != m0,
      (m0, ctk.get_appearance_mode()))
app.toggle_theme()
pump(100)
check(S, "18.2", "theme toggle flips back", ctk.get_appearance_mode() == m0,
      (m0, ctk.get_appearance_mode()))
app.show_help()
pump(400)
w = app.dialogs[-1]
check(S, "18.3", "the Help window opens", w.winfo_exists())
stack, texts = [w], []
while stack:
    x = stack.pop()
    try:
        texts.append(str(x.cget("text")))
    except Exception:
        pass
    if x.__class__.__name__ == "CTkTextbox":      # the help body lives here, not in "text"
        try:
            texts.append(x.get("1.0", "end"))
        except Exception:
            pass
    stack.extend(x.winfo_children())
help_text = " ".join(texts)
check(S, "18.4", "it explains the Moore rule", "output belongs to the state" in help_text,
      help_text[:80])
check(S, "18.5", "it has no Copy Definition button",
      not [t for t in texts if "Copy Definition" in t], [t for t in texts if "Copy" in t])
w.destroy()
pump(60)
app.set_panel("min")
pump(80)
check(S, "18.6", "min collapses the diagram body", not app._dg_body.winfo_ismapped())
check(S, "18.7", "panel change leaves the machine alone", app.states == {"q0": "0", "q1": "1"},
      app.states)
app.set_panel("normal")
pump(80)
check(S, "18.8", "normal brings the diagram back", app._dg_body.winfo_ismapped())
app.set_panel("max")
pump(80)
check(S, "18.9", "max collapses the simulation panel",
      not any(p.winfo_ismapped() for p, _ in app._sim_parts))
app.set_panel("normal")
pump(80)
app.set_speed(1.0)
check(S, "18.10", "speed slider sets the fastest step", app.delay == 200, app.delay)
app.set_speed(0.0)
check(S, "18.11", "speed slider sets the slowest step", app.delay == 1500, app.delay)
app.set_speed(0.5)
check(S, "18.12", "speed slider sets a middle step", app.delay == 850, app.delay)
app.delay = 10

# Add State dialog
before = len(app.states)
app.add_state_dialog()
w = app.dialogs[-1]
pump(200)
check(S, "18.13", "the Add State dialog opens", w.winfo_exists())
app.name.set("")
app.out.set("")
app.notices.clear()
app.state_ok(w)
pump(80)
check(S, "18.14", "a bad value keeps the dialog open", w.winfo_exists())
check(S, "18.15", "and shows the reason", "Empty state name" in last_notice(), last_notice()[:60])
check(S, "18.16", "and adds nothing", len(app.states) == before, len(app.states))
app.name.set("qX"), app.out.set("1")
app.state_ok(w)
pump(80)
check(S, "18.17", "a good value closes it and adds the state",
      not w.winfo_exists() and "qX" in app.states, sorted(app.states))
app.notices.clear()
app.add_state_dialog()
w = app.dialogs[-1]
pump(150)
w.destroy()
pump(60)
check(S, "18.18", "Cancel closes it without adding", "qY" not in app.states, sorted(app.states))
del app.states["qX"]
app.changed()
pump(60)
check(S, "18.19", "every chrome action left the machine valid",
      validate(app.states, app.initial, app.trans) == [],
      validate(app.states, app.initial, app.trans))

# ================================================================ report
print("\n" + "=" * 72, flush=True)
from collections import Counter
c = Counter(r[3] for r in RESULTS)
print("TOTAL %d   PASS %d   FAIL %d   SKIP %d" % (len(RESULTS), c["PASS"], c["FAIL"], c["SKIP"]),
      flush=True)
fails = [r for r in RESULTS if r[3] == "FAIL"]
skips = [r for r in RESULTS if r[3] == "SKIP"]
if fails:
    print("\nFAILURES:", flush=True)
    for sec, cid, name, st, det in fails:
        print("  %-5s %-14s %s\n         actual: %s" % (cid, sec, name, det), flush=True)
if skips:
    print("\nSKIPPED (blocked by another result):", flush=True)
    for sec, cid, name, st, det in skips:
        print("  %-5s %-14s %s  (%s)" % (cid, sec, name, det), flush=True)
print("=" * 72, flush=True)

for d in app.dialogs:
    if d.winfo_exists():
        d.destroy()
root.destroy()
