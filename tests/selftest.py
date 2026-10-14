"""The end-to-end self-check: pure logic, editing, dialogs, diagram."""

import json
import math
import time
import tkinter as tk
from tkinter import filedialog, messagebox

from PIL import Image

import customtkinter as ctk

from core.constants import DASH
from core.serialization import from_dict, no_dups, to_dict
from core.simulation import out_string, simulate
from core.synthesis import ex_pair_check, synthesize
from core.validation import check_input, validate
from ui.app import App
from ui.theme import HELP_STEPS, HELP_WHAT


def selftest():
    def raises(f, *a):
        """The message when f() refuses - truthy either way, so 'assert raises(...)' still holds."""
        try:
            f(*a)
        except ValueError as e:
            return str(e)
        return False

    # ---- pure logic
    S = {"q0": "0", "q1": "1"}
    T = {("q0", "0"): "q0", ("q0", "1"): "q1", ("q1", "0"): "q0", ("q1", "1"): "q1"}
    rows = simulate(S, "q0", T, "10110")
    assert rows[0] == (0, DASH, DASH, "q0", "0") and rows[1] == (1, "1", "q0", "q1", "1")
    assert [r[3] for r in rows] == ["q0", "q1", "q0", "q1", "q1", "q0"]
    assert out_string(rows) == "010110"  # output = output of the state reached
    assert validate(S, "q0", T) == []
    assert any("initial" in e for e in validate(S, None, T))
    T2 = {k: v for k, v in T.items() if k != ("q1", "1")}
    assert any("has no transition for input '1'" in e for e in validate(S, "q0", T2))
    assert raises(simulate, S, "q0", T2, "11")
    assert any("missing state" in e for e in validate(S, "q0", {**T, ("q0", "0"): "zz"}))
    assert any("no output" in e for e in validate({"a": " "}, "a", {}))
    assert check_input(T, "") and check_input(T, "12") and not check_input(T, "10110")
    m = to_dict(S, "q0", T)
    assert from_dict(json.loads(json.dumps(m))) == (S, "q0", T)
    assert raises(from_dict, {}) and raises(from_dict, [])
    assert raises(from_dict, {**m, "transitions": m["transitions"] * 2})  # duplicate transitions
    assert raises(from_dict, {**m, "initial": "nope"})
    assert raises(from_dict, {**m, "states": {"q0": None, "q1": "1"}})  # null output must not import as "None"
    assert raises(lambda: json.loads('{"states": {"a": "0", "a": "1"}}', object_pairs_hook=no_dups))

    # ---- auto-build: fit a machine to input/output examples
    ex = [("10110", "010110"), ("0", "00"), ("11", "011")]
    S3, I3, T3, gap = synthesize(ex)
    assert len(S3) == 2 and I3 == "q0" and len(T3) == 4 and gap == 0, (S3, I3, T3, gap)
    assert validate(S3, I3, T3) == []  # a generated machine is a valid machine
    for i, o in ex:  # every example replays exactly
        assert out_string(simulate(S3, I3, T3, i)) == o, i
    assert len(synthesize([("", "0"), ("0", "00")])[0]) == 1  # fewest states, not one per example
    # output 1 only after two 1s in a row: genuinely needs three states, so it catches a
    # fold that inflates. 3 is optimal; <=4 keeps a later improvement from breaking this line.
    d = [("0", "00"), ("1", "00"), ("00", "000"), ("01", "000"), ("10", "000"), ("11", "001"),
         ("111", "0011"), ("110", "0010"), ("011", "0001"), ("101", "0000")]
    S4, I4, T4, _ = synthesize(d)
    assert len(S4) <= 4 and validate(S4, I4, T4) == [], (S4, T4)
    for i, o in d:
        assert out_string(simulate(S4, I4, T4, i)) == o, i
    assert "output must have" in raises(synthesize, [("10", "01")])
    assert "Conflicting" in raises(synthesize, [("1", "01"), ("1", "00")])
    assert "No examples" in raises(synthesize, [])
    # the Auto Build boxes, checked before anything is fitted: both boxes are required
    assert ex_pair_check("10110", "010110") is None
    assert "Input String is empty" in ex_pair_check("", "")
    assert "Expected Output is empty" in ex_pair_check("10110", "")
    assert "Wrong output length" in ex_pair_check("10110", "1011")
    assert "contains a space" in ex_pair_check("101 10", "")     # pasted with gaps in it
    assert "contains a space" in ex_pair_check("10110", "01 110")
    assert "contains a space" in ex_pair_check("10\t1", "")

    # ---- GUI (skipped when there is no display)
    import os
    import shutil
    import tempfile
    import time
    try:
        root = ctk.CTk()
    except tk.TclError:
        print("logic ok; no display, GUI checks skipped")
        return
    # Validation messages are in-app overlays now, so the tests read the app's own notification
    # history instead of patching a popup. Same messages, same assertions, different transport.
    messagebox.askyesno = lambda *a, **k: True   # confirmations for destructive acts stay as-is
    app = App(root)
    root.update()
    app.set_speed(1)
    assert app.delay == 200
    app.delay = 100

    def pump(ms):
        end = time.time() + ms / 1000
        while time.time() < end:
            root.update()
            time.sleep(0.005)

    def sel(tree, iid):
        tree.selection_set(iid)
        root.update()

    def state(n, o):
        app.name.set(n), app.out.set(o)
        app.add_state()

    def trans(s, a, d):
        app.src.set(s), app.sym.set(a), app.dst.set(d)
        app.add_trans()

    def pick(s, a):
        sel(app.tt, str(app.tkeys.index((s, a))))

    def last():
        return app.notices[-1] if app.notices else ""

    def table():
        return [[str(v) for v in app.table.item(i, "values")] for i in app.table.get_children()]

    def printable(s):
        # safe for an assert message: this box's piped console is cp1252 and chokes on ✓ / δ / Σ
        return s.encode("ascii", "backslashreplace").decode()

    app.clear()
    assert not app.states and app.info["States"].get() == "0" and app.info["Current state"].get() == DASH
    assert "first state" in app.hint.get() and app.name.get() == "q0"  # friendly guidance + suggested name
    # 1. create states (+ empty / duplicate / no-output validation)
    state("A", "0"), state("B", "1")
    assert app.states == {"A": "0", "B": "1"} and app.initial == "A"  # first state becomes the start state
    assert app.name.get() == "q0" and app.out.get() == ""  # boxes are ready for the next state
    state("A", "1")
    assert "already exists" in last()
    state("", "1")
    assert "empty" in last()
    state("C", "")
    assert "output" in last()
    # 4. initial state (simulation must refuse without one)
    app.initial = None
    app.changed()
    app.inp.set("10")
    assert "start state" in app.hint.get()
    assert not app.start() and "No initial state" in last()
    sel(app.st, "B")
    app.set_initial()
    assert app.initial == "B"
    sel(app.st, "A")
    app.set_initial()
    assert app.initial == "A"
    # 5. transitions, 12. missing transition
    trans("A", "0", "A"), trans("A", "1", "B"), trans("B", "0", "A")
    assert len(app.trans) == 3
    assert not app.start() and "has no transition for input '1'" in last() and "'B'" in last()
    trans("B", "1", "B")
    # 8. duplicates / bad transitions
    trans("A", "1", "A")
    assert "already has a transition" in last() and app.trans[("A", "1")] == "B"
    trans("A", "", "A")
    assert "cannot be empty" in last()
    trans("A", "0", "Q")
    assert "must already exist" in last()
    # 6. edit transition, 7. delete transition
    pick("B", "1")
    app.dst.set("A")
    app.edit_trans()
    assert app.trans[("B", "1")] == "A"
    pick("B", "1")
    app.dst.set("B")
    app.edit_trans()
    assert app.trans[("B", "1")] == "B"
    pick("B", "1")
    app.del_trans()
    assert ("B", "1") not in app.trans
    trans("B", "1", "B")
    # 2. edit state: rename + output, transitions follow; rename to an existing name is refused
    sel(app.st, "B")
    app.name.set("Bee"), app.out.set("5")
    app.edit_state()
    assert app.states == {"A": "0", "Bee": "5"}
    assert app.trans[("A", "1")] == "Bee" and app.trans[("Bee", "0")] == "A" and app.trans[("Bee", "1")] == "Bee"
    sel(app.st, "Bee")
    app.name.set("A")
    app.edit_state()
    assert "already exists" in last() and "Bee" in app.states
    # 3. delete state (its transitions go too)
    state("Z", "0"), trans("Z", "0", "A")
    sel(app.st, "Z")
    app.del_state()
    assert "Z" not in app.states and all("Z" not in (k[0], v) for k, v in app.trans.items())

    # 9. example machine, 16. input 10110
    app.load_example(ask=False)
    assert app.states == S and app.initial == "q0" and app.trans == T and app.inp.get() == "10110"
    assert app.cur == "q0" and app.info["Current output"].get() == "0"  # initial output before any input
    assert "Step" in app.hint.get() and app.name.get() == "q2"
    # 10. step by step
    assert app.start() and table() == [["0", DASH, DASH, "q0", "0"]]
    app.step()
    assert table()[-1] == ["1", "1", "q0", "q1", "1"] and app.active == ("q0", "1", "q1")
    assert "→" in app.msg.get() and app.info["Position"].get().startswith("1 of 5")
    for _ in range(4):
        app.step()
    t = table()
    assert len(t) == 6 and "".join(r[4] for r in t) == "010110" and "010110" in app.outseq.get()
    assert app.active == ("q1", "0", "q0") and app.info["Position"].get().endswith("(finished)")
    assert "Finished" in app.hint.get()
    kids = app.table.get_children()
    assert "latest" in app.table.item(kids[-1], "tags") and "latest" not in app.table.item(kids[-2], "tags")
    items = app.cv.find_all()
    assert any(app.cv.itemcget(i, "fill") == "#ffd54f" for i in items)  # current state highlighted
    assert any(app.cv.itemcget(i, "fill") == "#e65100" for i in items)  # transition just taken
    app.step()
    assert len(table()) == 6
    # 10b. "did I get it right?" - the expected-output check
    app.exp.set("010110")  # the run above is finished, so it can compare right now
    assert app.verdict.get().startswith("✓") and "010110" in app.verdict.get(), printable(app.verdict.get())
    app.exp.set("010111")  # same length: names the first differing position
    assert app.verdict.get().startswith("✗") and "position 6" in app.verdict.get(), printable(app.verdict.get())
    app.exp.set("01011")  # wrong length: says so instead of guessing a position
    assert "5 symbol" in app.verdict.get(), printable(app.verdict.get())
    app.exp.set("")  # empty = the check is switched off
    assert app.verdict.get() == "", printable(app.verdict.get())
    app.reset()
    app.exp.set("01011")  # before any run, the length rule is answered only when it is provable
    assert "needs 6 symbol" in app.verdict.get(), printable(app.verdict.get())
    app.exp.set("010110")
    assert "Press Run to check" in app.verdict.get(), printable(app.verdict.get())
    app.start()
    assert "Keep running" in app.verdict.get(), printable(app.verdict.get())  # started, not finished
    for _ in range(5):
        app.step()
    assert app.verdict.get().startswith("✓"), printable(app.verdict.get())
    app.exp.set("")
    # the pinned coaching strings must be untouched by all of the above
    assert "Finished" in app.hint.get() and "→" in app.msg.get()
    # 11. run / pause / reset
    app.reset()
    assert table() == [] and app.cur == "q0" and app.shown == 0
    app.run()
    pump(250)
    app.pause()
    k = len(table())
    assert 1 < k < 6
    pump(250)
    assert len(table()) == k  # pause holds, nothing reset
    app.run()
    pump(400)
    assert len(table()) == 6
    app.reset()
    assert table() == [] and app.cur == "q0"
    # 13. save JSON, 14. load JSON
    d = tempfile.mkdtemp()
    p = os.path.join(d, "m.json")
    filedialog.asksaveasfilename = lambda **k: p
    filedialog.askopenfilename = lambda **k: p
    app.save()
    with open(p) as f:
        data = json.load(f)
    assert {"states", "initial", "transitions"} <= set(data) and data["initial"] == "q0" and len(data["transitions"]) == 4
    app.clear()
    app.load()
    assert app.states == S and app.initial == "q0" and app.trans == T
    # dragged positions survive a save / load round-trip
    app.off["q0"] = (37, -12)
    app.save()
    app.clear()
    app.load()
    assert app.off.get("q0") == (37.0, -12.0)
    app.off = {}
    app.inp.set("10110")
    assert app.start()
    for _ in range(5):
        app.step()
    assert "".join(r[4] for r in table()) == "010110"
    app.copy_out()
    assert app.root.clipboard_get() == "010110"  # copy the output sequence
    with open(p, "w") as f:
        f.write("{not json")
    app.load()
    assert "Could not load" in last()
    # export the diagram as a PNG
    app.load_example(ask=False)
    png = os.path.join(d, "diagram.png")
    filedialog.asksaveasfilename = lambda **k: png
    z = app.zoom
    app.export_png()
    assert app.zoom == z, (z, app.zoom)  # the fit used for the capture is put back
    with Image.open(png) as im:
        im.load()
        assert im.format == "PNG" and im.size[0] > 100 and im.size[1] > 100, (im.format, im.size)
        cols = im.convert("RGB").getcolors(maxcolors=1 << 22)
        assert cols is None or len(cols) > 8, "the exported diagram looks blank"
    # an empty diagram explains itself instead of writing a file
    app.clear()
    app.notices.clear()
    app.export_png()
    assert app.notices and "Nothing to export" in app.notices[-1]
    app.load_example(ask=False)  # the checks below need q0 back
    shutil.rmtree(d)
    # auto-build through the real dialog: two boxes, Build - the machine is worked out
    asked = []  # replacing a machine is destructive, so it has to ask
    messagebox.askyesno = lambda *a, **k: (asked.append(a), True)[1]
    app.auto_build_dialog()
    # the length rule answers beside the boxes while typing, not in a popup
    app.ex_in.set("10110"), app.ex_out.set("10110")
    app.ex_len_refresh()
    hint = app.ex_len_hint.get()
    assert "exactly 6 character" in hint and "typed 5" in hint, printable(hint)
    app.ex_out.set("010110")
    app.ex_len_refresh()
    assert "typed 6" in app.ex_len_hint.get(), "a right-length output turns the hint green"
    app.ex_out.set("")
    app.ex_len_refresh()
    assert "Expected Output is required" in app.ex_len_hint.get(), "the hint says it is required"
    # every refusal is written under the boxes with the dialog still open, and changes nothing
    def refused(inp, out, want):
        app.auto_build_dialog()          # replaces the previous attempt's dialog
        w = app.dialogs[-1]
        app.ex_in.set(inp), app.ex_out.set(out)
        app.auto_build_go(w)
        assert want in app.ex_err.get(), printable(app.ex_err.get())
        assert w.winfo_exists(), "the dialog stays open, so the fix is typed right where it was made"
        assert app.states == {"q0": "0", "q1": "1"} and not asked, "a refused build changes nothing"

    refused("", "", "Input String is empty")
    refused("10110", "", "Expected Output is empty")     # an input with no output to aim at
    refused("101 10", "", "contains a space")            # pasted with gaps between the symbols
    refused("10110", "10110", "Wrong output length")     # one short, the classic hand-typed slip
    # with an output pinned down, the machine has to print exactly it
    app.auto_build_dialog()
    app.ex_in.set("11"), app.ex_out.set("011")
    app.auto_build_go(app.dialogs[-1])
    assert len(asked) == 1, asked          # replacing a machine asks first
    assert app.states == {"q0": "0", "q1": "1"} and app.initial == "q0" and len(app.trans) == 2
    assert list(app.st.get_children()) == ["q0", "q1"]  # the tables and diagram refreshed too
    assert check_input(app.trans, "11") is None         # and the machine accepts the input
    assert app.exp.get() == "011" and app.outseq.get() == "011", (app.exp.get(), app.outseq.get())
    assert app.verdict.get().startswith("✓"), app.verdict.get()
    app.dismiss_notice()
    app.load_example(ask=False)  # the checks below need the example machine
    # deleting the initial state forces choosing another one
    sel(app.st, "q0")
    app.del_state()
    assert app.initial is None and last().startswith("WARNING") and "q0" not in app.states
    app.inp.set("1")
    assert not app.start() and "No initial state" in last()
    # 15. Clear All (with a simulation in progress)
    app.load_example(ask=False)
    app.start(), app.step()
    app.clear()
    assert not app.states and not app.trans and app.initial is None and app.inp.get() == ""
    assert table() == [] and app.cur is None and app.info["States"].get() == "0" and app.info["Initial state"].get() == "(not set)"
    assert all(app.cv.type(i) != "oval" for i in app.cv.find_all())
    # 16. view controls, theme and the beginner dialogs
    app.load_example(ask=False)
    app.inp.set("10110")
    assert app.start() and app.info["Input symbol"].get() == DASH  # nothing read yet
    app.step()
    assert app.info["Input symbol"].get() == "1"
    z0 = app.zoom
    app.zoom_in()
    assert app.zoom > z0 and app.zoomlbl.cget("text").endswith("%")
    app.zoom_out(), app.zoom_out()
    assert app.zoom < z0
    app.fit_diagram()
    assert 0.35 <= app.zoom <= 3.0
    # 16a. a state dragged far sideways must stay INSIDE the scroll region, or the scrollbars
    # cannot reach it and Fit Diagram cannot get it back (regression: state lost off-canvas).
    for off_x, off_y in ((4000, 0), (-4000, 0), (0, 4000)):
        app.off["q1"] = (off_x, off_y)
        app.draw()
        W, H = app._diag
        sr = app.cv.cget("scrollregion")
        sx0, sy0, sx1, sy1 = [float(v) for v in (sr.split() if isinstance(sr, str) else sr)]
        assert (sx1, sy1) == (W, H), (sr, app._diag)  # fit_diagram reads _diag, so they must agree
        for s in app.states:
            x, y = app.layout[s][0] + app.off.get(s, (0, 0))[0], app.layout[s][1] + app.off.get(s, (0, 0))[1]
            r = app.radius(s) * app.zoom
            assert x - r >= sx0 and y - r >= sy0 and x + r <= sx1 and y + r <= sy1, \
                (s, off_x, off_y, x, y, r, (sx1, sy1))
    app.off.clear()
    app.draw()
    was = app.dark()
    app.toggle_theme()
    assert app.dark() != was and app.cv.cget("bg") in ("#141414", "white")
    app.toggle_theme()
    assert app.dark() == was
    app.pause(True)
    assert "Nothing is running" in app.msg.get()  # Pause must never look like a dead button
    # 16b. the Help text teaches the concept first, then describes this exact machine
    assert "WHAT IS A MOORE MACHINE?" in HELP_WHAT and "HOW TO USE IT" in HELP_STEPS
    ex = app.machine_explain()
    assert "WHAT THE MACHINE ON SCREEN DOES" in ex, printable(ex)
    assert "It starts in q0, which prints 0." in ex, printable(ex)
    assert "q0 (prints 0): input 0 keeps it in q0, input 1 sends it to q1." in ex, printable(ex)
    fd = app.formal_def()
    assert "Q   (states)" in fd and "next state" in fd and "start state" in fd, printable(fd)
    assert "λ(q0)=0" in fd, printable(fd)
    app.clear()  # Help with no machine loaded still explains itself instead of crashing
    assert "no machine yet" in app.machine_explain() and "no machine yet" in app.formal_def()
    app.load_example(ask=False)
    app.show_help()
    boxes = [c for c in app.dialogs[-1].winfo_children() if isinstance(c, ctk.CTkTextbox)]
    ht = boxes[0].get("1.0", "end") if boxes else ""
    assert "WHAT IS A MOORE MACHINE?" in ht and "WHAT THE MACHINE ON SCREEN DOES" in ht, printable(ht)
    assert ht.index("WHAT IS A MOORE MACHINE?") < ht.index("WHAT THE MACHINE ON SCREEN DOES") \
        < ht.index("HOW TO USE IT"), printable(ht)  # concept -> this machine -> the procedure
    assert "λ(q0)=0" in ht, printable(ht)
    app.add_state_dialog()
    pump(200)
    dlg = app.dialogs[-1]
    assert dlg.winfo_exists()
    dlg.focus_force()  # Tk only delivers key events to the focused window
    dlg.event_generate("<Escape>")  # no update in between: nothing else may run first
    pump(50)
    assert not dlg.winfo_exists()  # Escape closes popups
    # 17. the symbols the interface rework added: output panel, selection rails, drawn icons
    app.load_example(ask=False)
    app.inp.set("10110")
    app.reset()
    assert app.sim_status.get() == "Not Started"
    # the badge really is bound to that variable: read it back through the label it is drawn in
    inner = [c for c in app.status_lbl.winfo_children() if isinstance(c, tk.Label)][0]
    assert root.getvar(str(inner.cget("textvariable"))) == app.sim_status.get()
    assert app.run_in.get() == "10110" and app.outseq.get() == DASH and app.prog.get() == "0 / 5"
    assert app.start() and app.sim_status.get() == "Paused" and app.outseq.get() == "0"
    while app.shown < len(app.rows):
        app.step()
    assert app.outseq.get() == "010110" and app.prog.get() == "5 / 5"  # Moore: initial output first
    assert app.sim_status.get() == "Finished"
    app.reset()
    assert app.sim_status.get() == "Not Started"
    assert app.outseq.get() == DASH and app.prog.get() == "0 / 5"  # Reset clears output AND progress
    # selection rail: nothing picked -> Edit / Delete / Set-as-Initial are dead, Add never is
    app.st.selection_remove(app.st.get_children())
    app.tt.selection_remove(app.tt.get_children())
    app.refresh_sel()
    assert "No state selected" in app.st_sel.get() and "No transition selected" in app.tt_sel.get()
    assert app.btn_state["edit"].cget("state") == "disabled"
    assert app.btn_state["initial"].cget("state") == "disabled"
    assert app.btn_state["add"].cget("state") == "normal"
    assert app.btn_tr["edit"].cget("state") == "disabled"
    assert app.btn_tr["add"].cget("state") == "normal"
    sel(app.st, "q0")
    app.refresh_sel()
    assert app.st_sel.get().startswith("Editing") and "q0" in app.st_sel.get()
    assert app.btn_state["edit"].cget("state") == "normal"
    sel(app.tt, str(app.tkeys.index(("q0", "1"))))
    app.refresh_sel()
    assert "--1-->" in app.tt_sel.get() and app.btn_tr["edit"].cget("state") == "normal"
    # every icon is drawn in one size for both themes, and every icon button explains itself in words
    for n in ("zoom_in", "zoom_out", "fit", "save", "open", "image", "help"):
        img = app.icon(n)
        assert img._light_image.size == img._dark_image.size == (18, 18), n
    assert app.theme_icon()._light_image.size == (18, 18)
    icons = []
    stack = [app.root]
    while stack:  # icon buttons are the empty-text buttons carrying a drawn image
        w = stack.pop()
        if isinstance(w, ctk.CTkButton) and w.cget("text") == "" and w.cget("image"):
            icons.append(w)
        stack.extend(w.winfo_children())
    assert len(icons) >= 7, len(icons)  # save / open / image / help / theme + 3 zoom
    for b in icons:
        tip = getattr(b, "_tip", None)
        assert tip is not None and len(str(tip.text).split()) >= 4, getattr(tip, "text", None)
        assert str(tip.text).strip()[0].isupper(), tip.text
    # 18. the popup-free UI rework: notification overlays, table scrollbars, Auto Build
    #     layout, the start arrow, the diagram panel modes, the wheel and panning
    def pump(ms):
        end = time.time() + ms / 1000.0
        while time.time() < end:
            root.update()
            time.sleep(0.005)

    def bbox(w):
        return (w.winfo_rootx(), w.winfo_rooty(),
                w.winfo_rootx() + w.winfo_width(), w.winfo_rooty() + w.winfo_height())

    def inside(b, o, pad=0):
        return (b[0] >= o[0] - pad and b[1] >= o[1] - pad
                and b[2] <= o[2] + pad and b[3] <= o[3] + pad)

    def overlaps(b, o):
        return not (b[2] <= o[0] or o[2] <= b[0] or b[3] <= o[1] or o[3] <= b[1])

    def tree_bar(t):  # the CTkScrollbar packed in a table's slot
        def find(w):
            for c in w.winfo_children():
                if c.__class__.__name__ == "CTkScrollbar":
                    return c
                r = find(c)
                if r is not None:
                    return r
        return find(t.master)

    def over_overlay():  # the overlay button that closes it
        return [c for c in app._notice.winfo_children()[0].winfo_children()
                if isinstance(c, ctk.CTkButton)][0]

    class Click:  # what _notice_hit reads off the event
        def __init__(self, widget):
            self.widget = widget

    # validation reports through an overlay, never through a modal window
    def no_popup(title, message, *a, **k):
        raise AssertionError("modal popup %r: %r" % (title, message))

    messagebox.showerror = messagebox.showwarning = no_popup
    app.dismiss_notice()
    app.notices.clear()
    app.name.set("")
    app.out.set("")
    app.add_state()
    root.update()                                # let the overlay actually get mapped
    assert app._notice is not None and app._notice.winfo_ismapped()   # the refusal is visible
    assert app.notices and not app.notices[-1].startswith("WARNING")  # errors are not warnings
    assert "empty" in app.notices[-1]
    assert inside(bbox(app._notice), bbox(app.notice_host), 4)   # it lives on the Build sidebar
    assert not overlaps(bbox(app._notice), bbox(app.cv))         # ...so never on the diagram
    assert not overlaps(bbox(app._notice), bbox(app._sim_parts[0][0]))  # ...nor the sim controls
    assert not root.grab_current(), "an overlay must not grab the pointer"
    # it is dismissed by its own button, and by clicking outside - never by a timer
    pump(400)
    assert app._notice is not None, "an overlay must not time itself away while being read"
    over_overlay()._command()
    assert app._notice is None
    app.err("click outside", "T")
    assert app._notice is not None
    app._notice_hit(Click(app.st))
    assert app._notice is None, "clicking outside the overlay dismisses it"
    app.err("click inside", "T")
    app._notice_hit(Click(app._notice.winfo_children()[0]))
    assert app._notice is not None, "clicking inside it leaves it up"
    app.dismiss_notice()
    assert app._notice is None
    # nothing is blocked while it is on screen, and the other two kinds are styled apart
    app.err("blocks nothing", "T")
    app.name.set("zz"), app.out.set("1")
    app.add_state()
    assert "zz" in app.states, "the app stays usable while an overlay is showing"
    messagebox.askyesno = lambda *a, **k: (asked.append(a), True)[1]   # destructive still asks
    asked.clear()
    sel(app.st, "zz")
    app.del_state()
    assert asked, "deleting a state still asks for confirmation first"
    app.load_example(ask=False)
    pick("q0", "1")                              # every destructive action asks, not just states
    asked.clear()
    app.del_trans()
    assert asked, "deleting a transition asks for confirmation first"
    asked.clear()
    app.clear()
    assert asked, "clearing the machine asks for confirmation first"
    app.load_example(ask=False)
    app.warn("just so you know", "Heads up")
    assert app.notices[-1].startswith("WARNING"), "warnings are tagged for the tests"
    app.ok("saved it", "Done")
    assert not app.notices[-1].startswith("WARNING"), "success is an ordinary notification"
    # a long message wraps inside the overlay, and the × must never be squeezed off the end
    app.ok("a long message that has to wrap " * 10, "Short title")
    root.update()
    assert app._notice.winfo_width() <= app.notice_host.winfo_width() + 1, "the overlay fits"
    head_btns = [c for c in app._notice.winfo_children()[0].winfo_children()
                 if c.__class__.__name__ == "CTkButton"]
    assert head_btns and head_btns[0].winfo_width() >= 20, "the × stays clickable"
    assert inside(bbox(app._notice), bbox(app.notice_host), 4)
    app.dismiss_notice()
    app.load_example(ask=False)

    # every table keeps its scrollbar, before the rows overflow and after they fit again
    for t in (app.st, app.tt, app.table):
        pump(40)
        assert tree_bar(t).winfo_ismapped(), "the bar must be there while the rows overflow"
    app.st.selection_remove(app.st.get_children())
    for k in app.st.get_children()[2:]:       # shrink until every row is on screen
        app.st.delete(k)
    pump(60)
    assert app.st.yview()[1] >= 0.999, app.st.yview()
    assert tree_bar(app.st).winfo_ismapped(), "the rows fit, and the bar is still there"
    for i in range(40):                       # ...and it still scrolls once they stop fitting
        app.name.set("t%d" % i)
        app.out.set("0")
        app.add_state()
    pump(60)
    assert app.st.yview()[1] < 0.999 and tree_bar(app.st).winfo_ismapped(), \
        (len(app.st.get_children()), app.st.yview())
    app.load_example(ask=False)
    pump(60)

    # Auto Build: every button stays inside the dialog and on screen
    sc = ctk.ScalingTracker.get_window_scaling(app.root) or 1
    screen = (0, 0, int(app.root.winfo_screenwidth() * sc),
              int(app.root.winfo_screenheight() * sc))
    app.auto_build_dialog()
    w = app.dialogs[-1]
    pump(700)                                # let the Toplevel settle onto its real size

    def dialog_buttons(win):
        found, stack = {}, [win]
        while stack:
            x = stack.pop()
            try:
                label = x.cget("text")
            except (tk.TclError, ValueError):
                label = ""
            if label in ("Build", "Cancel"):
                found[label] = x
            stack.extend(x.winfo_children())
        return found

    btns = dialog_buttons(w)
    assert set(btns) == {"Build", "Cancel"}, \
        "two inputs and two buttons - nothing for the user to configure at all"
    box = bbox(w)
    for name, b in btns.items():
        assert inside(bbox(b), box), (name, bbox(b), box)          # nothing overlaps
        assert inside(bbox(b), screen), (name, bbox(b), screen)    # nothing off-screen
    assert w.winfo_height() <= app.root.winfo_height(), "the dialog never outgrows the window"
    w.destroy()
    root.update()
    app.load_example(ask=False)

    # Auto Build installs the machine it worked out, and fills the dashboard with it
    app.auto_build_dialog()
    w = app.dialogs[-1]
    pump(600)
    app.ex_in.set("10110"), app.ex_out.set("010110")
    asked.clear()
    app.auto_build_go(w)
    pump(200)
    assert not w.winfo_exists(), "the dialog closes"
    assert len(asked) == 1, asked
    assert validate(app.states, app.initial, app.trans) == [], app.states  # a valid machine
    assert app.notices and app.notices[-1].startswith("Built and applied"), printable(app.notices[-1])
    assert app.inp.get() == "10110", app.inp.get()     # an input the new machine was built for
    assert app.exp.get() == "010110", app.exp.get()    # and the output it must print
    assert app.outseq.get() == "010110", app.outseq.get()
    assert app.verdict.get().startswith("✓"), app.verdict.get()
    assert list(app.st.get_children()) == list(app.states), "the States table is refilled"
    assert len(app.tt.get_children()) == len(app.trans), "and so is the Transitions table"
    assert len(app.table.get_children()) == len(app.rows) > 1, \
        "Build fills the whole results table - no button press needed"
    assert app.shown == len(app.rows), "and it is finished, not left mid-run"
    assert app.start(), "the simulation runs the new machine"
    app.reset()
    app.dismiss_notice()
    app.load_example(ask=False)
    pump(300)

    # the start arrow always sits on its state: tip on the circle, shaft outside it, in view
    app.st.selection_set("q0")
    app.set_initial()
    for z in (0.35, 1.0, 3.0):
        app.set_zoom(z)
        root.update()
        for s in ("q0", "q1"):
            app.st.selection_set(s)
            app.set_initial()
            root.update()
            x, y = app.layout[s]
            x += app.off.get(s, (0, 0))[0]
            y += app.off.get(s, (0, 0))[1]
            r = app.radius(s) * z
            lines = [i for i in app.cv.find_all() if app.cv.type(i) == "line"
                     and str(app.cv.itemcget(i, "fill")) in ("#2e7d32", "#66bb6a")
                     and len(app.cv.coords(i)) == 4]
            assert lines, "the start arrow is drawn"
            i = lines[0]
            x1, y1, x2, y2 = [float(v) for v in app.cv.coords(i)]
            tip = (x2, y2) if app.cv.itemcget(i, "arrow") == "last" else (x1, y1)
            tail = (x1, y1) if app.cv.itemcget(i, "arrow") == "last" else (x2, y2)
            assert abs(math.hypot(tip[0] - x, tip[1] - y) - r) < 2, (s, z)   # ends on the rim
            assert math.hypot(tail[0] - x, tail[1] - y) > r + 5, (s, z)      # starts clear of it
            assert y1 == y2, (s, z)      # straight in from the left, never at an angle
            assert x1 < x2, (s, z)       # ...so it reads as an arrival, not a departure
            assert tip[1] == y, (s, z)   # and meets the circle dead-on its middle
            assert not any(math.hypot(x1 + (x2 - x1) * k / 20 - x,
                                      y1 + (y2 - y1) * k / 20 - y) < r - .5
                           for k in range(21)), (s, z)                       # never crosses it
            sr = [float(v) for v in app.cv.cget("scrollregion").split()]
            assert min(x1, x2) >= sr[0] and max(x1, x2) <= sr[2] \
                and min(y1, y2) >= sr[1] and max(y1, y2) <= sr[3], (s, z)    # never clipped
    app.off.clear()
    app.set_zoom(1.0)
    app.fit_diagram()
    root.update()

    # Stepping re-colours the picture in place instead of repainting it. draw() deletes every
    # canvas item and rebuilds it, which cost about 150 ms on a 100-state machine - enough to
    # stop a Run animation from keeping up. A repaint also hands out brand new item ids.
    app.load_example(ask=False)
    root.update()
    app.inp.set("10110")
    assert app.start(), "the example machine runs"
    ids = tuple(app.cv.find_all())
    for _ in range(5):
        app.advance()
        assert tuple(app.cv.find_all()) == ids, "a step re-colours what is there, never repaints"

    def painted():
        """Type, geometry and colour of every item - independent of the ids a repaint reissues."""
        out = []
        for i in app.cv.find_all():
            row = [app.cv.type(i), tuple(app.cv.coords(i))]
            for opt in ("fill", "outline", "width"):  # no item type has all three
                try:
                    row.append(app.cv.itemcget(i, opt))
                except Exception:
                    row.append(None)
            out.append(tuple(row))
        return sorted(out)

    stepped = painted()
    app.draw()
    assert painted() == stepped, "highlight() paints exactly the picture draw() would have"
    assert app.cur in app.states, "the current state is still highlighted after the repaint"
    assert len(app._meas) > 1, "state text is measured once and remembered, not on every repaint"

    # the diagram panel minimizes to its header, maximizes over the simulation, and restores
    app.set_panel("min")
    pump(40)
    assert app.panel == "min" and not app._dg_body.winfo_ismapped()
    assert all(p.winfo_ismapped() for p, _ in app._sim_parts), "the simulation stays reachable"
    app.set_panel("min")
    pump(40)
    assert app.panel == "normal" and app._dg_body.winfo_ismapped(), "minimize toggles back"
    app.set_panel("max")
    pump(40)
    assert app.panel == "max" and not any(p.winfo_ismapped() for p, _ in app._sim_parts)
    app.set_panel("max")
    pump(40)
    assert app.panel == "normal" and all(p.winfo_ismapped() for p, _ in app._sim_parts)
    assert app.states and app.initial, "layout changes never touch the machine"

    # the wheel: plain scrolls, Ctrl zooms at the pointer, over a table it scrolls the table
    app.set_zoom(1.0)
    app.fit_diagram()
    root.update()
    z0 = app.zoom
    app.cv.yview_moveto(0)
    v0 = app.cv.yview()
    app.cv.event_generate("<MouseWheel>", delta=-120, x=30, y=30, state=0)
    pump(60)
    assert app.zoom == z0 and app.cv.yview() != v0, "plain wheel over the diagram only pans"
    sx = 200
    wx = app.cv.canvasx(sx)
    z1 = app.zoom
    app.cv.event_generate("<MouseWheel>", delta=120, x=sx, y=40, state=0x0004)
    pump(80)
    assert app.zoom > z1, "Ctrl+wheel zooms in"
    moved = abs(wx - app.cv.xview()[0] * app._diag[0] - sx)
    assert moved < 45, moved                       # the point under the cursor stays put
    app.zoom_out()
    app.fit_diagram()
    root.update()
    assert 0.35 <= app.zoom <= 3.0, app.zoom       # Zoom Out and Fit still work
    z2 = app.zoom
    app.st.yview_moveto(0)
    tv = app.st.yview()
    app.st.event_generate("<MouseWheel>", delta=-120, x=5, y=5, state=0)
    pump(60)
    assert app.zoom == z2, "a wheel over a table must never zoom the diagram"
    assert app.st.yview() == tv, "with every row visible there is nothing to scroll"
    # ...but over a table longer than its box the wheel scrolls it. Dragging the thin bar was
    # the only way down before, which is not a way most people look for.
    for i in range(60):
        app.table.insert("", "end", values=(i, "1", "q0", "q1", "1"))
    root.update()
    app.table.yview_moveto(0)
    rv = app.table.yview()
    app.table.event_generate("<MouseWheel>", delta=-120, x=5, y=5, state=0)
    pump(60)
    assert app.table.yview() != rv, (app.table.yview(), rv)
    assert app.table.yview()[0] > 0, "one notch moves it a row's worth, not off the end"
    assert app.zoom == z2, "and the wheel still never zooms the diagram"
    app.table.yview_moveto(0)
    rv = app.table.yview()
    app.table.event_generate("<MouseWheel>", delta=120, x=5, y=5, state=0)
    pump(60)
    assert app.table.yview() == rv, "a wheel the other way scrolls back up"
    app.reset()  # those rows existed only to make the table longer than its box

    # dragging empty space pans the view; dragging a state still moves the state
    app.set_zoom(3.0)
    root.update()
    app.cv.xview_moveto(0.5)
    app.cv.yview_moveto(0.5)
    v0 = (app.cv.xview(), app.cv.yview())
    e = Click(None)
    e.x, e.y = 30, 30
    app.drag_start(e)
    assert app._pan is not None and app.dragging is None, "empty space starts a pan"
    e.x, e.y = 80, 60
    app.drag_move(e)
    app.drag_end(e)
    assert (app.cv.xview(), app.cv.yview()) != v0, "panning moves the view"
    assert app._pan is None, "the pan ends on release"
    app.set_zoom(1.0)
    app.fit_diagram()
    root.update()
    item = next(i for i in app.cv.find_withtag("s:q0"))
    app.cv.dtag("all", "current")                 # a synthetic event sets no "current" tag
    app.cv.addtag_withtag("current", item)
    e.x, e.y = app.cv.winfo_width() // 2, app.cv.winfo_height() // 2
    app.drag_start(e)
    assert app.dragging == "q0" and app._pan is None, "dragging a state still drags the state"
    app.drag_end(e)
    app.load_example(ask=False)
    for d in app.dialogs:
        if d.winfo_exists():
            d.destroy()
    root.destroy()
    print("self-check ok")
