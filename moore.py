"""Moore Machine Simulator - CustomTkinter GUI.
Install once:  pip install customtkinter
Run:           python moore.py        Self-check:  python moore.py --test
"""
import json
import math
import sys
import time
import tkinter as tk
from tkinter import filedialog, messagebox, ttk
from tkinter import font as tkfont

from PIL import Image, ImageColor, ImageDraw, ImageGrab

try:
    import customtkinter as ctk
except ImportError:
    sys.exit("This program needs CustomTkinter. Install it with:  pip install customtkinter")

ctk.set_appearance_mode("light")  # the diagram canvas and tables are light, so keep the whole window light
ctk.set_default_color_theme("blue")

# font hierarchy - every label picks from these five, so headings and captions stay consistent
F_H1 = ("Arial", 17, "bold")   # dialog titles
F_H2 = ("Arial", 15, "bold")   # panel / section titles
F_H3 = ("Arial", 12, "bold")   # field labels, buttons, emphasised values
F_BODY = ("Arial", 12)         # running text
F_CAP = ("Arial", 11)          # captions, hints, column headers

FONT_B = ("Arial", 12, "bold")
DASH = "—"
STYLES = {  # button colours: (normal, hover)
    "go": ("#2e7d32", "#1b5e20"), "warn": ("#ef6c00", "#e65100"),
    "danger": ("#c62828", "#8e0000"), "plain": ("#607d8b", "#455a64"),
}
HELP_WHAT = ("WHAT IS A MOORE MACHINE?\n"
             "A small machine that sits in one state at a time. Whatever state it is sitting in is\n"
             "what it prints. The input NEVER picks the output - the input only decides which state\n"
             "you move to next.\n"
             "\n"
             "        [ state: prints 0 ] --(input 1)--> [ state: prints 1 ]\n"
             "\n"
             "Like a lift: where you are decides what you see, the button only moves you.\n"
             "\n")

HELP_STEPS = ("HOW TO USE IT - 7 steps\n"
              "Create -> Connect -> Visualize -> Enter Input -> Step/Run -> Understand Output\n"
              "\n"
              "1. CREATE STATES. Type a name (q0) and an output (0 or 1), then press Add State.\n"
              "2. EVERY STATE NEEDS AN OUTPUT. In a Moore machine the output belongs to the state itself.\n"
              "3. SET THE INITIAL STATE. Click a state in the list, then press Set as Initial State (green arrow).\n"
              "4. CONNECT THEM. Pick From, type ONE input symbol, pick To, then press Add Transition.\n"
              "5. ENTER AN INPUT STRING such as 10110 in the Input string box.\n"
              "6. PRESS STEP for exactly one symbol, or RUN to play the whole string (PAUSE stops, RESET "
              "restarts only the simulation). The machine starts in the start state and shows its output "
              "before reading anything.\n"
              "7. WATCH THE OUTPUT. Follow the highlighted state in the diagram, the Simulation Results, and the "
              "table, which fills in by itself.\n"
              "\n"
              "THE MOORE RULE: read a symbol -> follow the arrow -> land in a new state -> show THAT state's output. "
              "The output always comes from the state you arrive in, never from the input.\n"
              "\n"
              "CHECK YOUR WORK. Type what you expect into 'Expected output' and run the machine - the line under it "
              "says whether it matches, and if not, where the first difference is.\n"
              "\n"
              "TIPS\n"
              "- Press Enter in the Name, Output or Input string box to act quickly.\n"
              "- Click any row in a list to load it into the boxes for editing.\n"
              "- Drag a state in the diagram to move it. Use Zoom In / Zoom Out / Fit Diagram to resize.\n"
              "- Auto Build (top of the Machine Editor) works out the states, their outputs and every\n"
              "  transition from an input string and the output it should print. Press Build, then\n"
              "  rename the states if you like.\n"
              "- Reset Simulation keeps your machine. Clear Machine deletes it (and always asks first).")

# ---------- core logic (pure functions, no GUI) ----------
def validate(states, initial, trans, need_start=True):
    """states: {name: output}; trans: {(src, symbol): dst}. Returns a list of student-friendly errors.
    need_start=False skips the checks that only matter before simulating (initial set, no gaps).
    Every message says WHAT went wrong and HOW to fix it."""
    errs = []
    if need_start and not states:
        errs.append("⚠️ No states yet\nA Moore machine needs at least one state.\n"
                    "Fix: under 'States' type a name (e.g. q0) and an output (e.g. 0), then press Add State.")
    for n, o in states.items():
        if not n.strip():
            errs.append("⚠️ Empty state name\nA state has an empty name.\n"
                        "Fix: give every state a short unique name such as q0 or A.")
        if not o.strip():
            errs.append(f"⚠️ Missing state output\nState '{n}' has no output. Every Moore state needs exactly one output.\n"
                        f"Fix: click '{n}' in the list, type an output (e.g. 0) in the Output box, then press Edit State.")
    for (s, a), d in trans.items():
        if not a:
            errs.append(f"⚠️ Empty input symbol\nTransition {s} --?--> {d} has an empty input symbol.\n"
                        f"Fix: click that transition in the list, type one character (0 or 1), then press Edit Transition.")
        for x in (s, d):
            if x not in states:
                errs.append(f"⚠️ Invalid state reference\nTransition {s} --{a}--> {d} refers to missing state '{x}'.\n"
                            f"Fix: add a state named '{x}' under 'States', or delete this transition.")
    if initial is not None and initial not in states:
        errs.append(f"⚠️ No initial state\nThe initial state '{initial}' does not exist.\n"
                    "Fix: click a state in 'States', then press Set as Initial State.")
    if need_start:
        if initial is None:
            errs.append("⚠️ No initial state\nNo initial state selected. Pick a state in the list and press 'Set as Initial State'.\n"
                        "Fix: click a state in 'States' (it turns blue in the diagram), then press Set as Initial State.")
        alphabet = {a for _, a in trans}
        for s in states:
            for a in sorted(alphabet):
                if (s, a) not in trans:
                    errs.append(f"⚠️ Missing transition\nState '{s}' has no transition for input '{a}'.\n"
                                f"Fix: under 'Transitions' set From = {s}, Input = {a}, choose a To state, "
                                f"then press Add Transition.")
    return errs


def check_input(trans, text):
    """Returns an error string, or None if the input string is usable."""
    if not text:
        return ("⚠️ Invalid input\nThe input string is empty.\n"
                "Fix: type the symbols to feed the machine, such as 10110, then press Step or Run.")
    alphabet = {a for _, a in trans}
    bad = sorted({c for c in text if c not in alphabet})
    if bad:
        # repr() so a stray space or tab is visible instead of vanishing into the sentence
        shown = ", ".join(repr(c) for c in bad)
        return (f"⚠️ Invalid input\nThe input string contains symbol(s) with no transition: {shown}.\n"
                f"Symbols this machine understands: {', '.join(sorted(alphabet)) or '(none yet - add transitions first)'}.\n"
                f"Fix: delete those symbols from the input, or add transitions for them under 'Transitions'.")


def simulate(states, initial, trans, text):
    """Rows of (step, input, previous state, current state, output).
    Moore rule: input -> transition -> new state -> the NEW STATE's output."""
    cur = initial
    rows = [(0, DASH, DASH, cur, states[cur])]
    for i, a in enumerate(text, 1):
        if (cur, a) not in trans:
            raise ValueError(f"Missing transition at step {i}: state '{cur}' has no transition for input '{a}'.")
        prev, cur = cur, trans[(cur, a)]
        rows.append((i, a, prev, cur, states[cur]))
    return rows


def out_string(rows):
    outs = [r[4] for r in rows]
    return ("" if all(len(o) == 1 for o in outs) else " ").join(outs)


def to_dict(states, initial, trans):
    return {"states": dict(states), "initial": initial,
            "transitions": [{"from": s, "input": a, "to": d} for (s, a), d in sorted(trans.items())]}


def no_dups(pairs):  # json object_pairs_hook: json would silently keep only the last duplicate
    keys = [k for k, _ in pairs]
    if len(keys) != len(set(keys)):
        raise ValueError("The file lists the same name twice (duplicate state names).")
    return dict(pairs)


def from_dict(d):
    """Inverse of to_dict. Raises ValueError with a readable message on bad data."""
    try:
        states = {}
        for k, v in d["states"].items():
            if v is None or isinstance(v, (dict, list)):  # str() would turn null into the output "None"
                raise ValueError(f"State '{k}' has no usable output (found {v!r}).\n"
                                "Fix: give it a plain output such as 0 or 1.")
            states[str(k)] = str(v)
        trans = {}
        for t in d["transitions"]:
            key = (str(t["from"]), str(t["input"]))
            if key in trans:
                raise ValueError(f"Duplicate transition: state '{key[0]}' already has a transition on input '{key[1]}'.")
            trans[key] = str(t["to"])
        initial = d.get("initial")
    except (KeyError, TypeError, AttributeError):
        raise ValueError("This is not a Moore machine file. Expected: states, initial, transitions.")
    errs = validate(states, initial, trans, need_start=False)
    if errs:
        raise ValueError("\n".join(errs))
    return states, initial, trans


def ex_pair_check(inp, out):
    """The two Auto Build boxes, checked. Returns an error string, or None when they are usable.
    Both boxes are required: a Moore machine is defined by what it prints, so without an output
    there is nothing to aim at and every state could print the same symbol."""
    for label, text in (("Input String", inp), ("Expected Output", out)):
        gaps = [i for i, c in enumerate(text) if c.isspace()]
        if gaps:
            return (f"⚠️ {label} contains a space\n"
                    f"{label} has {len(gaps)} space(s); symbols go straight after each other with "
                    f"no gaps between them (the first is at position {gaps[0] + 1}).\n"
                    f"Fix: delete the spaces, so the box reads '{text.replace(' ', '')}'.")
    if not inp:
        return ("⚠️ Input String is empty\n"
                "There is nothing for the machine to read, so there is nothing to build.\n"
                "Fix: type the symbols to feed the machine, such as 10110.")
    if not out:
        return ("⚠️ Expected Output is empty\n"
                "A Moore machine is defined by what it prints, so an output is what makes the "
                "machine mean anything at all.\n"
                f"Fix: type what should come out for input '{inp}' - exactly {len(inp) + 1} "
                f"characters, such as {'0' * (len(inp) + 1)}.")
    if len(out) != len(inp) + 1:
        return (f"⚠️ Wrong output length\n"
                f"Input '{inp}' has {len(inp)} symbol(s), so its output must have {len(inp) + 1} - "
                f"you typed {len(out)}.\n"
                "Fix: the first output belongs to the start state and is printed before any input is read.")
    return None


def synthesize(examples):
    """Fit the fewest Moore states to (input, output) examples.
    Returns (states, initial, trans, defaulted): what to_dict() takes, plus how many transitions no
    example mentioned (each filled with a self-loop, so an input you never typed holds the state).
    Moore rule: the output is one symbol longer than the input - output[0] belongs to the start
    state and is printed before any input is read. Raises ValueError when nothing can fit."""
    seen = {}  # input prefix -> (the output printed there, an example it came from)
    for inp, out in examples:
        if len(out) != len(inp) + 1:
            raise ValueError(
                f"⚠️ Wrong output length\n"
                f"Input '{inp}' has {len(inp)} symbol(s), so its output must have {len(inp) + 1}.\n"
                "Fix: the first output belongs to the start state and is printed before any input is read.")
        for k in range(len(inp) + 1):
            p, want = inp[:k], out[k]
            if p in seen and seen[p][0] != want:
                raise ValueError(
                    f"⚠️ Conflicting examples\n"
                    f"After reading '{p}' one example needs output '{seen[p][0]}' but another needs '{want}'.\n"
                    f"(The examples '{seen[p][1]}' and '{inp}' disagree.)\n"
                    "Fix: no machine can satisfy both - correct or delete one of them.")
            seen[p] = (want, inp)
    if not seen:
        raise ValueError("⚠️ No examples yet\nThere is nothing to build a machine from.\n"
                         "Fix: type at least one line such as  10110 010110")

    alphabet = sorted({a for inp, _ in examples for a in inp})
    edges = {}  # only the transitions your examples actually justify
    for inp, _ in examples:
        for k, a in enumerate(inp):
            edges[(inp[:k], a)] = inp[:k + 1]

    def fit(order):
        """Fold states together in this order: two become one when they agree on every input they
        BOTH mention. An input neither one mentions is still free, so it never blocks a merge."""
        alive, tr, par = set(order), dict(edges), {s: s for s in order}
        while True:
            before = len(alive)
            for u in order:
                if u not in alive:
                    continue
                for v in order:
                    if v == u or v not in alive or seen[u][0] != seen[v][0]:
                        continue
                    if any((u, a) in tr and (v, a) in tr and tr[(u, a)] != tr[(v, a)] for a in alphabet):
                        continue
                    for a in alphabet:  # u keeps its own edges and borrows the ones only v had
                        if (u, a) not in tr and (v, a) in tr:
                            tr[(u, a)] = tr[(v, a)]
                        tr.pop((v, a), None)
                    for k in list(tr):  # everything that pointed at v now points at u
                        if tr[k] == v:
                            tr[k] = u
                    par[v] = u
                    alive.discard(v)
            if len(alive) == before:
                root = ""
                while par[root] != root:  # "" may have been folded away: follow it to what it became
                    root = par[root]
                return alive, tr, root

    # two scan orders: folding leaves first finds the small machine more often than roots first.
    # ponytail: greedy fold - near-minimal, not provably minimal (fewest states is NP-hard, and
    # scan order, refinement, and post-minimizing were all measured worse). Upgrade path: branch
    # and bound over output-homogeneous partitions when there are few prefixes, greedy above that.
    deep = sorted(seen, key=lambda s: (-len(s), s))
    shallow = sorted(seen, key=lambda s: (len(s), s))
    alive, tr, root = min((fit(deep), fit(shallow)), key=lambda r: len(r[0]))

    defaulted = 0
    for s in sorted(alive):  # an input your examples never mentioned holds the state
        for a in alphabet:
            if (s, a) not in tr:
                tr[(s, a)] = s
                defaulted += 1

    order, walked = [root], {root}
    i = 0
    while i < len(order):  # q0 is the start state; the rest are numbered in the shape of your examples
        s = order[i]
        i += 1
        for a in alphabet:
            t = tr[(s, a)]
            if t not in walked:
                walked.add(t)
                order.append(t)
    for s in sorted(alive):  # unreachable states cannot happen - but never silently drop one either
        if s not in walked:
            order.append(s)
    names = {s: f"q{i}" for i, s in enumerate(order)}
    states = {names[s]: seen[s][0] for s in order}
    trans = {(names[s], a): names[tr[(s, a)]] for s in order for a in alphabet}
    return states, names[root], trans, defaulted


# ---------- icons ----------
# Drawn here with PIL (already imported for PNG export), so there is no icon library to install
# and no font to ship: one function, one 18x18 design grid, one line weight for every glyph.
def draw_icon(name, fg, px=18):
    """Monochrome icon `name` on a transparent `px` square."""
    S = 4  # supersample: keeps curves readable on a 150% DPI screen
    g = 18 * S
    im = Image.new("RGBA", (g, g), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    ink = tuple(ImageColor.getrgb(fg)[:3])
    w = max(2, int(round(1.7 * S)))

    def line(x0, y0, x1, y1, width=w):
        d.line([x0 * S, y0 * S, x1 * S, y1 * S], fill=ink + (255,), width=width)

    def ring(x, y, r, width=w):
        d.ellipse([(x - r) * S, (y - r) * S, (x + r) * S, (y + r) * S], outline=ink + (255,), width=width)

    def dot(x, y, r):
        d.ellipse([(x - r) * S, (y - r) * S, (x + r) * S, (y + r) * S], fill=ink + (255,))

    if name in ("zoom_in", "zoom_out"):        # magnifying glass + handle
        ring(7.4, 7.4, 5.2, width=int(w * 0.72))
        line(11.6, 11.6, 15.2, 15.2, int(w * 1.15))
        # The sign is the ONLY thing that tells these two apart, so both arms run the full width
        # of the lens: a short plus would clear the horizontal bar by a couple of pixels only.
        gx = int(w * 1.45)
        d.line([3.1 * S, 7.4 * S, 11.7 * S, 7.4 * S], fill=ink + (255,), width=gx)
        if name == "zoom_in":
            d.line([7.4 * S, 3.1 * S, 7.4 * S, 11.7 * S], fill=ink + (255,), width=gx)
    elif name == "fit":                        # four corner brackets = fit to screen
        for cx, cy, sx, sy in ((3.0, 3.0, 1, 1), (15.0, 3.0, -1, 1),
                               (3.0, 15.0, 1, -1), (15.0, 15.0, -1, -1)):
            line(cx, cy, cx + 5.0 * sx, cy)
            line(cx, cy, cx, cy + 5.0 * sy)
    elif name == "sun":                        # disc + 8 rays
        dot(9, 9, 3.3)
        for k in range(8):
            a = k * math.pi / 4
            line(9 + 5.0 * math.cos(a), 9 + 5.0 * math.sin(a),
                 9 + 7.4 * math.cos(a), 9 + 7.4 * math.sin(a))
    elif name == "moon":                       # crescent = disc with a bite punched out
        mask = Image.new("L", (g, g), 0)       # L-mode fill=0 genuinely erases (RGBA may blend)
        md = ImageDraw.Draw(mask)
        md.ellipse([2.8 * S, 2.8 * S, 15.2 * S, 15.2 * S], fill=255)
        md.ellipse([7.8 * S, 1.0 * S, 17.4 * S, 10.6 * S], fill=0)
        im.paste(ink + (255,), (0, 0), mask)
    elif name == "save":                       # floppy disk
        d.rectangle([3.0 * S, 3.0 * S, 15.0 * S, 15.0 * S], outline=ink + (255,), width=w)
        d.rectangle([5.8 * S, 3.0 * S, 12.2 * S, 7.6 * S], fill=ink + (255,))
        d.rectangle([10.0 * S, 10.2 * S, 13.4 * S, 14.0 * S], fill=ink + (255,))
    elif name == "open":                       # folder with a tab
        d.polygon([(3.0 * S, 4.8 * S), (6.9 * S, 4.8 * S), (8.4 * S, 6.9 * S),
                   (15.0 * S, 6.9 * S), (15.0 * S, 14.4 * S), (3.0 * S, 14.4 * S)],
                  outline=ink + (255,), width=w)
    elif name == "image":                      # picture frame with a mountain and a sun
        d.rounded_rectangle([3.0 * S, 3.8 * S, 15.0 * S, 14.2 * S], radius=int(1.5 * S),
                            outline=ink + (255,), width=w)
        dot(6.4, 7.0, 1.3)
        d.line([(4.2 * S, 12.6 * S), (7.6 * S, 9.6 * S), (10.0 * S, 11.7 * S),
                (13.8 * S, 8.7 * S)], fill=ink + (255,), width=int(w * 0.8), joint="curve")
    elif name == "help":                       # a bold question mark - no badge ring to crowd it
        d.arc([(9 - 4.6) * S, (7.5 - 4.6) * S, (9 + 4.6) * S, (7.5 + 4.6) * S],
              start=150, end=30, fill=ink + (255,), width=w)
        line(12.9, 9.9, 9.8, 12.8, int(w * 1.1))
        dot(9.4, 15.3, 1.2)
    elif name == "panel_min":                  # a box with a heavy floor - collapse to a strip
        d.rectangle([3.6 * S, 3.6 * S, 14.4 * S, 14.4 * S], outline=ink + (255,), width=w)
        line(3.2, 12.2, 14.8, 12.2, int(w * 1.3))
    elif name == "panel_max":                  # four corner brackets - take the whole area
        for x0, y0, dx, dy in ((3.6, 3.6, 1, 1), (14.4, 3.6, -1, 1),
                               (3.6, 14.4, 1, -1), (14.4, 14.4, -1, -1)):
            line(x0, y0, x0 + 4.2 * dx, y0, int(w * 1.3))
            line(x0, y0, x0, y0 + 4.2 * dy, int(w * 1.3))
    elif name == "error":                      # circled cross - the "this did not work" badge
        ring(9, 9, 6.4)
        line(6.4, 6.4, 11.6, 11.6, int(w * 1.2))
        line(11.6, 6.4, 6.4, 11.6, int(w * 1.2))
    elif name == "warn":                       # triangle with a bar and a dot
        d.polygon([(9 * S, 2.6 * S), (16.4 * S, 15.2 * S), (1.6 * S, 15.2 * S)],
                  outline=ink + (255,), width=w)
        line(9, 7.6, 9, 11.2, int(w * 1.2))
        dot(9, 13.6, 1.0)
    elif name == "ok":                         # circled tick
        ring(9, 9, 6.4)
        line(5.9, 9.3, 8.3, 11.8, int(w * 1.2))
        line(8.3, 11.8, 12.4, 6.7, int(w * 1.2))
    else:
        raise ValueError("no icon named %r" % name)
    return im.resize((px, px), Image.BILINEAR)  # bilinear: Lanczos rings onto the transparent edge


# ---------- GUI ----------
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


class App:
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

    # ----- light / dark -----
    def dark(self):
        return ctk.get_appearance_mode() == "Dark"

    def toggle_theme(self, *_):
        ctk.set_appearance_mode("light" if self.dark() else "dark")
        self.apply_theme()

    def apply_theme(self):
        dk = self.dark()
        self.cv.configure(highlightbackground="#3a3a3a" if dk else "#cfd8dc")
        sty = ttk.Style()
        sty.configure("Treeview", background="#2b2b2b" if dk else "white",
                      fieldbackground="#2b2b2b" if dk else "white",
                      foreground="#e0e0e0" if dk else "black")
        sty.configure("Treeview.Heading", background="#3a3a3a" if dk else "#e8eef4",
                      foreground="#e0e0e0" if dk else "black")
        sty.map("Treeview", background=[("selected", "#1f6aa5")], foreground=[("selected", "white")])
        self.table.tag_configure("latest", background="#6d4c00" if dk else "#ffe082")
        self.draw()

    # ----- diagram view: zoom + drag -----
    def zfont(self):
        """Bold font scaled to the current zoom, cached per size."""
        size = max(8, int(round(12 * self.zoom)))
        if size not in self._fonts:
            self._fonts[size] = tkfont.Font(size=size, weight="bold")
        return self._fonts[size]

    def set_zoom(self, z, follow=True):
        self.zoom = max(0.35, min(3.0, round(z, 3)))
        self.zoomlbl.configure(text=f"{int(round(self.zoom * 100))}%")
        # a wheel zoom must not also re-centre on the current state - that is the jump the
        # spec asks to avoid. follow=False leaves the view exactly where the caller put it.
        self._no_follow = not follow
        try:
            self.draw()
        finally:
            self._no_follow = False

    def zoom_in(self, *_):
        self.set_zoom(self.zoom * 1.25)

    def zoom_out(self, *_):
        self.set_zoom(self.zoom / 1.25)

    def zoom_at(self, factor, e=None):
        """Zoom by `factor`, keeping whatever is under the pointer in the same screen spot.
        The picture is laid out about the centre of the scroll region, so the anchor moves
        with that centre and scales with the zoom - close enough that the diagram does not
        slide out from under the cursor."""
        try:
            ax, ay = self.cv.canvasx(e.x), self.cv.canvasy(e.y)
        except (AttributeError, tk.TclError):
            return self.set_zoom(self.zoom * factor)
        z0, (W0, H0) = self.zoom, self._diag
        self.set_zoom(self.zoom * factor, follow=False)
        if self.zoom == z0 or not W0 or not H0:
            return
        W, H = self._diag
        k = self.zoom / z0   # how far the content moved away from the centre
        self._moveto((W / 2 + (ax - W0 / 2) * k - e.x) / max(W, 1),
                     (H / 2 + (ay - H0 / 2) * k - e.y) / max(H, 1))

    def _moveto(self, fx, fy):
        """Scroll so the world point fx*W lands at the left edge, clamped to the region."""
        self.cv.xview_moveto(max(0.0, min(1.0, fx)))
        self.cv.yview_moveto(max(0.0, min(1.0, fy)))

    def on_wheel(self, e):
        """Ctrl + wheel zooms at the pointer, Shift + wheel pans sideways, plain wheel pans up
        and down. Bound on the diagram canvas only, so a wheel over a table or the sidebar
        scrolls that widget and never zooms the picture."""
        step = -3 if (getattr(e, "delta", 0) or 0) > 0 else 3
        if e.state & 0x0004:                       # Control -> zoom in towards the cursor
            self.zoom_at(1.2 if step < 0 else 1 / 1.2, e)
        elif e.state & 0x0001:                     # Shift -> sideways
            self.cv.xview_scroll(step, "units")
        else:
            self.cv.yview_scroll(step, "units")
        return "break"

    def fit_diagram(self, *_):
        w, h = self.cv.winfo_width(), self.cv.winfo_height()
        W, H = self._diag
        if w > 50 and h > 50 and W and H:
            self.set_zoom(min(1.0, self.zoom * min(w / W, h / H)))  # fit: never zoom past 100%

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

    def export_png(self, *_):
        if not self.states:
            return self.err("⚠️ Nothing to export\nThe diagram is empty - it has no states to draw.\n"
                            "Fix: add a state first, or press 'Load Example' to load a working machine.",
                            "Could not export")
        path = filedialog.asksaveasfilename(defaultextension=".png", initialfile="moore-machine.png",
                                            filetypes=[("PNG image", "*.png")])
        if not path:
            return
        keep = self.zoom  # fit so the whole machine lands in frame, then put the zoom back
        try:
            self.fit_diagram()
            # ponytail: grab() copies whatever is on screen, so lift first - but this still loses
            # to another window covering us; capture the canvas offscreen (Win32 PrintWindow) if it bites
            self.root.lift()
            self.root.focus_force()
            self.root.update()
            time.sleep(0.1)
            x, y = self.cv.winfo_rootx(), self.cv.winfo_rooty()
            ImageGrab.grab(bbox=(x, y, x + self.cv.winfo_width(), y + self.cv.winfo_height())).save(path)
        except (OSError, ValueError) as e:
            self.set_zoom(keep)
            self.msg.set("")  # do not leave the last "Saved the diagram to ..." banner standing
            return self.err(f"⚠️ Could not export\n{e}\n"
                            "Fix: choose a folder you can write to, such as Documents or Downloads.",
                            "Could not export")
        self.set_zoom(keep)
        self.msg.set(f"Saved the diagram to {path}")

    def drag_start(self, e):
        self.dragging, self._pan = None, None
        for item in self.cv.find_withtag("current"):  # topmost state circle / label under the cursor
            for t in self.cv.gettags(item):
                if t.startswith("s:"):
                    self.dragging = t[2:]
                    # remember where the grab happened so the circle does not jump to the cursor
                    self._press = (self.cv.canvasx(e.x), self.cv.canvasy(e.y))
                    self._base = self.off.get(self.dragging, (0, 0))
                    self.cv.configure(cursor="fleur")
                    return
        # no state under the pointer: drag the view instead, so a big machine can be panned
        self._pan = (e.x, e.y, self.cv.xview()[0], self.cv.yview()[0])
        self.cv.configure(cursor="fleur")

    def drag_move(self, e):
        if self.dragging:
            px, py = self._press
            bx, by = self._base
            self.off[self.dragging] = (bx + self.cv.canvasx(e.x) - px, by + self.cv.canvasy(e.y) - py)
            self.draw()
        elif self._pan:
            x0, y0, fx, fy = self._pan
            W, H = self._diag
            self._moveto(fx - (e.x - x0) / max(W, 1), fy - (e.y - y0) / max(H, 1))

    def drag_end(self, _):
        if self.dragging or self._pan:
            self.dragging, self._pan = None, None
            self.cv.configure(cursor="")

    # ----- state editing -----
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

    # ----- diagram -----
    def measure(self, text):
        """Pixel width of `text` in the state font.

        Asking Tk is a round-trip, and draw() asks for every state on every repaint - on a big
        machine that was most of what a repaint cost. The answers cannot change unless the font
        does, so they are remembered by string."""
        got = self._meas.get(text)
        if got is None:
            if len(self._meas) > 400:  # bounded: a machine only ever has a handful of names
                self._meas.clear()
            got = self._meas[text] = self.font.measure(text)
        return got

    def radius(self, s):
        """Circle radius that fits the state's name and output."""
        w = max(self.measure(s), self.measure(self.states[s]))
        return max(28, math.hypot(w / 2, 19) + 5)

    def draw(self):
        c = self.cv
        c.delete("all")
        w, h = c.winfo_width(), c.winfo_height()
        z, fz, dk = self.zoom, self.zfont(), self.dark()
        ink = "#d0d0d0" if dk else "black"  # outlines and ordinary arrows
        paper = "#141414" if dk else "white"  # canvas colour: label boxes blend into it
        green = "#66bb6a" if dk else "#2e7d32"
        c.configure(bg=paper)
        if not self.states:
            c.configure(scrollregion=(0, 0, w, h))
            self._diag = (max(w, 1), max(h, 1))
            c.create_text(w / 2, h / 2, font=fz, fill="#9aa7b3" if dk else "gray",
                          text="No states yet - Load the example, or add your first state.")
            return
        n = len(self.states)
        rs = {s: self.radius(s) * z for s in self.states}  # circles scale with the zoom
        rm = max(rs.values())

        def reach(s):
            """How far outside its centre this state's own drawing can stick out.

            A self-loop and the label beside it reach about 2.75r; the start state's arrow
            reaches r + 70z with a "start" box about 28px wide past it. Everything has to land
            inside the scroll region - outside it the scrollbars cannot reach it, the canvas
            clips it, and the arrow reads as detached from the state it points at."""
            r = rs[s]
            far = max(3 * r + 30 * z, 2.75 * r + 28)
            return max(far, r + 70 * z + 28) if s == self.initial else far

        margin = max(3 * rm + 30 * z,          # self-loop plus its label
                     reach(self.initial) if self.initial in rs else 0)   # ...and the start arrow
        need = (2 * rm + 90 * z) / (2 * math.sin(math.pi / n)) if n > 1 else 0  # keeps neighbours apart
        # compact when the machine is small, filling the canvas when it is big (never below `need`)
        rx = max(need, min(w / 2 - margin, need * 1.6)) if n > 1 else 0
        ry = max(need, min(h / 2 - margin, need * 1.6)) if n > 1 else 0
        W, H = max(w, 2 * (rx + margin)), max(h, 2 * (ry + margin))
        # A state dragged sideways has to stay INSIDE the scroll region: outside it the scrollbars
        # cannot reach the circle and Fit Diagram cannot get it back. pos = centre + rx*cos(a) + drag,
        # so the worst case on each axis is |rx*cos(a) + drag| plus that state's own reach.
        if self.off:
            ang = [math.pi + 2 * math.pi * i / n for i in range(n)]
            W = max(W, 2 * max(abs(rx * math.cos(a) + self.off.get(s, (0, 0))[0]) + reach(s)
                               for a, s in zip(ang, self.states)))
            H = max(H, 2 * max(abs(ry * math.sin(a) + self.off.get(s, (0, 0))[1]) + reach(s)
                               for a, s in zip(ang, self.states)))
        cx, cy = W / 2, H / 2
        c.configure(scrollregion=(0, 0, W, H))  # bigger than the window -> scrollbars work
        self._diag = (W, H)  # remembered so Fit Diagram knows the natural size
        self.layout = {s: (cx + rx * math.cos(math.pi + 2 * math.pi * i / n),
                           cy + ry * math.sin(math.pi + 2 * math.pi * i / n)) for i, s in enumerate(self.states)}
        pos = {}  # layout position + wherever the user has dragged the state
        for s, (lx, ly) in self.layout.items():
            dx, dy = self.off.get(s, (0, 0))
            pos[s] = (lx + dx, ly + dy)

        def outward(x, y):  # unit vector pointing away from the diagram centre
            L = math.hypot(x - cx, y - cy)
            return ((x - cx) / L, (y - cy) / L) if L > 1 else (0, -1)

        def toward(p, q, dist):  # point `dist` px from p in the direction of q
            L = math.hypot(q[0] - p[0], q[1] - p[1]) or 1
            return p[0] + dist * (q[0] - p[0]) / L, p[1] + dist * (q[1] - p[1]) / L

        def tag(x, y, text, bg, fg, extra=""):  # label on a small box so it stays readable over lines
            kw = {"tags": (extra,)} if extra else {}
            t = c.create_text(x, y, text=text, font=fz, fill=fg, **kw)
            b = c.bbox(t)
            c.create_rectangle(b[0] - 2, b[1], b[2] + 2, b[3], fill=bg, outline="", **kw)
            c.tag_raise(t)

        ARROW = (max(6, 13 * z), max(7, 15 * z), max(2, 5 * z))
        act = self.active
        edges = {}  # parallel edges share one arrow and one label: q0 -"0, 1"-> q1
        for (s, a), d in self.trans.items():
            edges.setdefault((s, d), []).append(a)
        self._edge_tag = {}  # so highlight() can find one arrow again without redrawing them all
        for i, ((s, d), syms) in enumerate(edges.items()):
            etag = "e%d" % i
            self._edge_tag[(s, d)] = etag
            on = bool(act) and (s, d) == (act[0], act[2])  # the transition being processed
            col, bg = ("#e65100", "#ffe0b2") if on else (ink, paper)
            wd = max(1, (4 if on else 2) * z)
            lab = "#e65100" if on else ("#ef5350" if dk else "#c62828")
            label = ", ".join(sorted(syms))
            (x1, y1), (x2, y2) = pos[s], pos[d]
            if s == d:  # self-loop, drawn outside the circle
                r = rs[s]
                ux, uy = outward(x1, y1)
                if s == self.initial and ux < 0:
                    # The start arrow always comes straight in from the left, so a loop on that
                    # side would draw through it. Turn the loop a quarter away, staying on the
                    # vertical side the state was already leaning towards.
                    ux, uy = 0.0, -1.0 if uy <= 0 else 1.0
                pts = []
                for k, t in ((-.75, 1), (-.5, 2.3), (.5, 2.3), (.75, 1)):
                    vx, vy = ux * math.cos(k) - uy * math.sin(k), ux * math.sin(k) + uy * math.cos(k)
                    pts += [x1 + vx * r * t, y1 + vy * r * t]
                c.create_line(*pts, smooth=True, arrow="last", arrowshape=ARROW, width=wd,
                              fill=col, tags=(etag,))
                tag(x1 + ux * r * 2.75, y1 + uy * r * 2.75, label, bg, lab, etag)
            else:
                L = math.hypot(x2 - x1, y2 - y1) or 1
                nx, ny = -(y2 - y1) / L, (x2 - x1) / L
                bend = max(70 * z, .3 * L) if (d, s) in edges else 0  # arrows in both directions curve apart
                q = ((x1 + x2) / 2 + nx * bend, (y1 + y2) / 2 + ny * bend)
                # ponytail: straight arrows may cross a third state in dense layouts; route around it if that bites
                a0, a1 = toward((x1, y1), q, rs[s]), toward((x2, y2), q, rs[d])
                c.create_line(*a0, *q, *a1, smooth=True, arrow="last", arrowshape=ARROW, width=wd,
                              fill=col, tags=(etag,))
                mx, my = .25 * a0[0] + .5 * q[0] + .25 * a1[0], .25 * a0[1] + .5 * q[1] + .25 * a1[1]
                tag(mx + nx * 14 * z, my + ny * 14 * z, label, bg, lab, etag)

        prev = act[0] if act else None
        for s, (x, y) in pos.items():
            r, now = rs[s], s == self.cur
            st = ("s:" + s,)  # tag so the whole state can be dragged
            if s == self.initial:  # prominent start ring, outside the circle
                c.create_oval(x - r - 7 * z, y - r - 7 * z, x + r + 7 * z, y + r + 7 * z,
                              outline=green, width=max(2, 3 * z), dash=(6, 4), tags=st + ("ring",))
            # "circ" separates the circle itself from the ring and the text, so highlight()
            # can re-colour it in place instead of repainting the whole picture.
            c.create_oval(x - r, y - r, x + r, y + r,
                          fill="#ffd54f" if now else "#e3f2fd" if s == prev else "white",
                          outline="#e65100" if now else ink, width=4 if now else 2,
                          tags=st + ("circ",))
            c.create_line(x - r + 6 * z, y, x + r - 6 * z, y, fill="gray", tags=st)
            c.create_text(x, y - 9 * z, text=s, font=fz, tags=st)
            c.create_text(x, y + 10 * z, text=self.states[s], font=fz, fill="#1565c0", tags=st)
        # The start arrow is drawn LAST: it is the one thing a beginner looks for, and drawing
        # it inside the state loop let a state added later bury the arrow and its "start" label.
        if self.initial in pos:
            x, y = pos[self.initial]
            r = rs[self.initial]
            # Always the same arrow in the same place: straight in from the left, tip on the rim,
            # label at the tail. It used to be aimed along the state's bearing around the diagram
            # centre, so dragging a state swung it round to another side of the circle and it
            # stopped reading as "this is where it starts".
            c.create_line(x - r - 55 * z, y, x - r, y,
                          arrow="last", arrowshape=(max(8, 15 * z), max(9, 17 * z), max(3, 6 * z)),
                          width=max(2, 3 * z), fill=green)
            tag(x - r - 70 * z, y, "start", paper, green)
        if self.cur in pos and self.rows and self.dragging is None and not self._no_follow:
            # follow the current state when the diagram scrolls (not while the user is dragging)
            c.xview_moveto(max(0, pos[self.cur][0] - w / 2) / W)
            c.yview_moveto(max(0, pos[self.cur][1] - h / 2) / H)

    def highlight(self, prev_cur=None, prev_act=None):
        """Re-colour the three things a step or a reset actually changes - the current state,
        the state the active arrow came from, and that arrow - and leave the rest alone.

        draw() repaints every circle and label on the canvas. That is right when the machine
        itself has changed, but far too expensive to pay once per animation frame: a repaint of
        a 100-state machine cost about 150 ms, so a Run could not keep up with itself."""
        c, dk, z = self.cv, self.dark(), self.zoom
        ink = "#d0d0d0" if dk else "black"
        paper = "#141414" if dk else "white"
        orange, back = "#e65100", "#e3f2fd"

        def circle(s, fill, width=2, outline=None):
            if s is None or s not in self.states:
                return
            for i in c.find_withtag("s:" + s):
                if "circ" in c.gettags(i):  # the circle itself, never the start ring
                    c.itemconfig(i, fill=fill, width=width,
                                 outline=ink if outline is None else outline)

        def edge(e, on):
            t = self._edge_tag.get(e)
            if not t:
                return
            lab = orange if on else ("#ef5350" if dk else "#c62828")
            for i in c.find_withtag(t):
                kind = c.type(i)
                if kind == "line":
                    c.itemconfig(i, fill=orange if on else ink, width=max(1, (4 if on else 2) * z))
                elif kind == "text":
                    c.itemconfig(i, fill=lab)
                elif kind == "rectangle":
                    c.itemconfig(i, fill="#ffe0b2" if on else paper)

        def as_edge(a):  # an active tuple (from, symbol, to) as the edge that was drawn for it
            return (a[0], a[2]) if a else None

        circle(prev_cur, "white")  # take the previous step off the picture...
        if prev_act:
            circle(prev_act[0], "white")
            edge(as_edge(prev_act), False)
        # ...then put this one on. Being the arrow's source never outranks being current, which
        # is the same order draw() uses when it picks a fill.
        cur = self.cur
        circle(cur, "#ffd54f", 4, orange)
        if self.active:
            src = self.active[0]
            circle(src, "#ffd54f" if src == cur else back, 4 if src == cur else 2,
                   orange if src == cur else None)
            edge(as_edge(self.active), True)
        # keep following the current state while a run plays, exactly as draw() does
        if cur in self.layout and self.rows and self.dragging is None and not self._no_follow:
            x, y = self.layout[cur]
            dx, dy = self.off.get(cur, (0, 0))
            W, H = self._diag
            c.xview_moveto(max(0, x + dx - c.winfo_width() / 2) / max(W, 1))
            c.yview_moveto(max(0, y + dy - c.winfo_height() / 2) / max(H, 1))


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


if __name__ == "__main__":
    if "--test" in sys.argv:
        selftest()
    else:
        root = ctk.CTk()
        App(root)
        root.mainloop()
