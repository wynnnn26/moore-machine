# Documentation — how `moore.py` works

This is a guided tour of the source. It assumes no prior knowledge of the project: what the
program is made of, what each part does, and why it is built that way.

The whole application is **one module**, `moore.py`. That is deliberate — see
[Design decisions](#design-decisions) at the end.

> Line numbers below match the current file. They drift as the code changes, so treat them as
> rough landmarks rather than something to rely on.

---

## Contents

1. [The big picture](#1-the-big-picture)
2. [The data model](#2-the-data-model)
3. [Part 1 — pure machine logic (lines 76–307)](#3-part-1--pure-machine-logic-lines-76307)
4. [Part 2 — icons (lines 309–399)](#4-part-2--icons-lines-309399)
5. [Part 3 — GUI toolkit (lines 401–472)](#5-part-3--gui-toolkit-lines-401472)
6. [Part 4 — `App` and the window layout (lines 474–1145)](#6-part-4--app-and-the-window-layout-lines-4741145)
7. [Part 5 — dialogs and Auto Build (lines 1147–1309)](#7-part-5--dialogs-and-auto-build-lines-11471309)
8. [Part 6 — appearance and the diagram view (lines 1311–1480)](#8-part-6--appearance-and-the-diagram-view-lines-13111480)
9. [Part 7 — notifications (lines 1482–1550)](#9-part-7--notifications-lines-14821550)
10. [Part 8 — editing the machine (lines 1552–1807)](#10-part-8--editing-the-machine-lines-15521807)
11. [Part 9 — simulation (lines 1832–2044)](#11-part-9--simulation-lines-18322044)
12. [Part 10 — drawing the diagram (lines 2045–2270)](#12-part-10--drawing-the-diagram-lines-20452270)
13. [Part 11 — the self-test (line 2273 on)](#13-part-11--the-self-test-line-2273-on)
14. [Design decisions](#14-design-decisions)
15. [Glossary](#15-glossary)

---

## 1. The big picture

```
        ┌──────────────────────────── module level ────────────────────────────┐
        │  constants, fonts, help text                                        │
        │  pure logic   validate · check_input · synthesize · simulate …      │
        │  drawing      draw_icon                                             │
        │  GUI helpers  winfo_exists · auto_hide_bar · Tip                    │
        │  class App    everything the window knows and does                  │
        │  selftest()   the built-in test suite (python moore.py --test)      │
        └──────────────────────────────────────────────────────────────────────┘
```

Two rules run through the whole file:

1. **The machine logic never touches the GUI.** Everything in Part 1 is a plain function of its
   arguments. That is what makes it testable without opening a window, and what lets Auto Build
   reuse `validate()` and `simulate()` unchanged.
2. **Every refusal explains itself.** Error messages are not "invalid input" — they say what is
   wrong, why it matters, and what to do instead. Each one ends with a `Fix:` line.

---

## 2. The data model

Three values describe a machine everywhere in the code:

| Name | Type | Meaning |
|---|---|---|
| `states` | `dict[str, str]` | `{state name: output}` |
| `initial` | `str \| None` | the start state's name |
| `trans` | `dict[tuple[str, str], str]` | `{(from state, input symbol): to state}` |

A tuple key for transitions is the single most useful decision in the file. Looking up
`trans[(cur, a)]` is one dictionary hit — no searching a list, no possibility of accidentally
adding the same transition twice.

`App.__init__` (line 476) holds these, plus the simulation state:

```python
self.states, self.initial, self.trans = {}, None, {}   # the machine
self.rows, self.shown, self.cur, self.active, self.job, self.text = [], 0, None, None, None, ""
```

- `rows` — the whole simulation, precomputed: a list of `(step, input symbol, previous state,
  current state, output)` tuples. Computing it all up front is what makes **Step**, **Run** and
  **Pause** trivial: stepping just reveals one more row.
- `shown` — how many of those rows the user can currently see.
- `active` — the transition being processed, `(from, symbol, to)`, or `None` at step 0. The
  diagram uses it to light up the arrow just taken.
- `job` — the Tk `after()` id of a running animation, or `None` when nothing is playing.

---

## 3. Part 1 — pure machine logic (lines 76–307)

No GUI imports are used here at all.

### `validate(states, initial, trans, need_start=True)` — line 76

Returns a **list** of human-readable problems, not a boolean. Showing the user every problem at
once is much kinder than making them fix them one at a time.

It checks, in order: there is at least one state; no state has an empty name or a missing
output; every transition's symbols and endpoints are real; the initial state exists. With
`need_start=True` it additionally requires an initial state and **no gaps** — a gap being a
state that is missing a transition for a symbol the alphabet uses.

`need_start=False` is for loading a file: a machine may legitimately be incomplete on disk and
completed later in the editor, but it cannot be *run* until it is total.

### `check_input(trans, text)` — line 116

Checks the input string against the alphabet that `trans` actually uses. Note the character
handling: a stray space is reported as `' '` — a *visible* space — because an invisible
character in the error message is worse than useless.

### `simulate(states, initial, trans, text)` — line 131

The Moore rule, in four lines:

```python
cur = initial
rows = [(0, DASH, DASH, cur, states[cur])]      # step 0: the START STATE's output
for i, a in enumerate(text, 1):
    prev, cur = cur, trans[(cur, a)]            # read a symbol -> move
    rows.append((i, a, prev, cur, states[cur])) # ...and print the state you LANDED in
```

The first row is the reason the output is always one symbol longer than the input: the machine
prints something before it has read anything. A missing transition raises `ValueError` rather
than inventing one.

### `out_string(rows)` — line 144

Joins the outputs. Single-character outputs concatenate directly (`010110`); longer ones are
joined with a space so a multi-symbol output stays readable.

### `to_dict` / `from_dict` / `no_dups` — lines 149, 154, 161

The JSON boundary. Two details are worth knowing:

- `no_dups` is passed to `json.load(..., object_pairs_hook=no_dups)`. Plain `dict(pairs)` would
  silently keep the **last** of two identical keys, so a file with `"q0"` twice would quietly
  lose a state. Raising instead means the user is told.
- `from_dict` raises `ValueError` with a readable message for every failure mode, and finishes
  by running `validate()`. A rejected file can never half-load.

### `ex_pair_check(inp, out)` — line 185

The Auto Build gate, checked in the most useful order: reject a space first (the most common
slip), then an empty input, then an empty output (the message names a concrete example of a
correct answer), then the wrong length.

### `synthesize(examples)` — line 214

Turns `(input, output)` examples into the fewest states that fit. Three stages:

1. **Check the examples against each other.** Every input prefix maps to exactly one required
   output. If two examples demand different outputs after the same prefix, no machine can
   satisfy both, and that is reported as *"Conflicting examples"* naming both inputs.
2. **Build the states.** `fit(order)` starts with one state per input prefix and repeatedly
   merges any two that agree on every input they **both** mention. An input neither one
   mentions is still free, so it never blocks a merge. This is the same idea as the standard
   Myhill–Nerode construction, but arrived at by merging rather than by building the quotient.
3. **Fill the gaps.** Transitions no example mentioned become self-loops, and their count is
   returned as `defaulted` so the UI can say *"1 transition filled with a self-loop"* instead
   of quietly doing something the user did not ask for.

Returns `(states, initial, trans, defaulted)` — exactly what `to_dict()` wants.

---

## 4. Part 2 — icons (lines 309–399)

`draw_icon(name, fg, px)` renders an icon into a `PIL.Image` and converts it to a Tk photo. It
is a small drawing DSL: each icon is a list of primitives (`line`, `arc`, `ring`, `dot`) that a
few helpers turn into pixel coordinates. Keeping icons as data means the whole set stays in one
place and scales cleanly with the requested size.

This is also where PNG export comes from — the same machinery renders a diagram at a chosen
size.

---

## 5. Part 3 — GUI toolkit (lines 401–472)

Small pieces that the rest of the GUI leans on.

- **`winfo_exists(w)`** (line 402) — a widget that has been destroyed raises `TclError` when you
  ask it anything. Wrapping the check keeps call sites readable.
- **`auto_hide_bar(sf)`** (line 410) — a scrollbar that reports a *reserved gutter* rather than
  appearing and disappearing. The comment above it explains a genuinely subtle bug: hiding the
  bar let the tree stretch into the space, ttk then reported the stretched width as its
  requested size, Tk gave the bar a zero-width window, and it could never come back. Reserving
  the gutter costs 24 px and never lies about the content.
- **`Tip`** (line 446) — hover tooltips, bound on `<Enter>`/`<Leave>` and shown on demand. There
  is no timer hiding them, so a slow reader never loses one mid-sentence.
- **The widget mixin** (`wrapped`, `card`, `tree`, `btn`, `icon_btn`, `field`, `empty_note`) —
  one place that knows how this app draws a panel, a table or a button, so every screen looks
  the same and a style change is one edit.

`tree()` deserves a note: it binds the mouse wheel **to the table**, so scrolling a long results
table works without hunting for a thin scrollbar — and the diagram's own wheel binding is on the
canvas alone, so scrolling a table never zooms the picture.

---

## 6. Part 4 — `App` and the window layout (lines 474–1145)

`class App` is the whole application. `__init__` (line 476) sets up state and calls `build()`.

`build()` (line 616) constructs the window top to bottom, and its comments are the map:

| Region | Rough lines | Contents |
|---|---|---|
| Top bar | 641+ | the "what to do next" hint, plus file / view / destructive buttons grouped by colour |
| Machine Editor (left) | 685+ | Auto Build, then the **States** and **Transitions** cards |
| Machine Diagram (top right) | 775+ | a scrollable, zoomable, draggable Tk canvas |
| Simulation (bottom right) | 844+ | input, expected output, controls, live status |
| Simulation Output | 933+ | the results table and the output sequence in one place |

Two conventions are worth knowing when reading it:

- **Colour is meaning.** Blue means "go" (Step, Run, Add), grey means "neutral" (Edit, Reset),
  red means "destroys something" (Delete, Clear), green means "safe or constructive" (Load
  Example, Auto Build, Set as Initial), orange means "stop" (Pause). The palette lives in one
  `STYLES` dict.
- **Panels are cards.** `card()` gives every section the same rounded container and heading, so
  the layout reads as a set of groups rather than a wall of widgets.

---

## 7. Part 5 — dialogs and Auto Build (lines 1147–1309)

`popup()` (near line 1000) is the single way any dialog opens: it centres the window over its
parent, keeps it on top, and makes it dismissible with the **×** or a click outside — never by
a timer.

`settle()` inside it contains one of the most important comments in the file. It used to
re-centre on every `<Configure>` event, including the ones its own re-centring caused, so the
event queue never drained and opening a dialog cost over a second. It now only re-centres when
the window actually **grew**. That single guard took Auto Build's open time from 1.46 s to 0.11 s.

Auto Build itself is three methods:

- `auto_build_dialog()` (line 1169) — the two inputs and a live hint saying how long the output
  must be.
- `auto_build_go(w)` (line 1248) — validate, synthesize, and on failure **leave the dialog
  open** with the problem shown inside it. The window grows to fit the message; typing clears
  it; only a successful build closes the dialog and asks before replacing the machine.
- `ex_install(...)` (line 1283) — puts the result on screen: states, transitions, input and
  expected output, then runs it so the answer appears immediately.

Note the ordering in `auto_build_go`: the dialog is destroyed **before** the confirmation box is
shown. A dialog holding a `grab` would otherwise hide a message box parented to the main window.

---

## 8. Part 6 — appearance and the diagram view (lines 1311–1480)

- `toggle_theme()` (line 1315) — flips light/dark and repaints.
- `zoom_at(factor, e)` (line 1357) — zooms around a point, keeping the thing under the pointer
  under the pointer.
- `on_wheel` (line 1380) — plain wheel pans, Ctrl+wheel zooms. Bound on the canvas only.
- `set_panel(mode)` (line 1399) — shrinks the diagram to its header, or the simulation to its
  header, to give the other one the whole column. Pressing the active button restores normal.
  It only changes packing, so the machine and any run in progress are untouched.
- `drag_start` / `drag_move` / `drag_end` (line 1451+) — pressing a state moves that state;
  pressing empty canvas pans the view instead, so a machine bigger than the window is still
  reachable. The grab offset is remembered so the circle does not jump to the cursor.

---

## 9. Part 7 — notifications (lines 1482–1550)

`notify(kind, title, message)` (line 1491) puts a box over the Machine Editor sidebar.

The constraints it is built to: **one at a time** (a run of errors cannot bury the interface),
**no timer** (nothing is taken away while it is being read), **no grab** (every other control
stays usable), and dismissed by the **×** or by clicking anywhere outside it. It never covers
the diagram or the simulation controls.

`err()`, `warn()` and `ok()` (lines 1537–1545) are the three colours of it, and they also
record into `self.notices` — a bounded history the tests read.

Destructive confirmations deliberately use a normal modal `messagebox.askyesno` instead: those
*should* stop you.

---

## 10. Part 8 — editing the machine (lines 1552–1807)

### States (1552–1668)

`read_state()` validates the two boxes and returns `(name, output)` or `None`. `add_state()`,
`edit_state()` and `del_state()` all start there, so the same three rules — non-empty, unique,
has an output — apply everywhere.

Two behaviours are easy to miss and worth knowing:

- **The first state becomes the initial state.** Otherwise a new machine would be unrunnable
  until the user discovered Set as Initial.
- **Renaming follows the name everywhere.** `edit_state()` rewrites the key in `states`, the key
  in every transition that mentions it, and `initial` if it was that state. Rename nothing and
  the machine silently tears itself apart.
- **Deleting the initial state clears it** and warns, rather than leaving a dangling reference.

### Transitions (1670–1740)

`read_state`'s twin, `read_trans()`, checks both endpoints exist and that the symbol is exactly
one character. `add_trans()` also refuses a duplicate `(from, symbol)` pair, because a function
that takes two values cannot have two.

### Whole-machine actions (1741–1807)

`load_example`, `clear`, `save`, `load`.

`changed()` (line 1809) is the one entry point every mutation funnels through:

```python
def changed(self):
    """Any edit: refresh the lists, repaint the diagram, then reset the simulation."""
    ... rebuild both tables ...
    self.refresh_sel()
    self.draw()   # the machine itself changed, so the whole picture has to be rebuilt...
    self.reset()  # ...and reset() then only re-marks the start state, which is cheap
```

Eleven call sites route through it — add, edit and delete for states and transitions, set
initial, clear, load example, load file, and Auto Build's install. Because there is exactly one
path, there is exactly one thing to keep correct.

---

## 11. Part 9 — simulation (lines 1832–2044)

```
start()  →  validate → check_input → simulate → rows  → advance()   (step 0)
step()   →  start() if needed → advance()
run()    →  tick() now, then tick() again after delay, until the rows run out
advance()→  reveal rows[shown], then highlight() + refresh the panels
reset()  →  rows=[], shown=0, highlight back to the start state
```

**`start()`** (line 1845) begins by calling `reset()`. That is not tidiness — a *refused* start
must not leave the previous run's output on screen, because then the panel would be showing
results for something that never ran.

**`advance()`** (line 1862) is one step. It reveals a row, updates the status line, and calls
`highlight()` — see the next section, because that call is load-bearing for performance.

**`tick()`** (line 1900) is the animation loop: advance, and if there is more, schedule itself
again with `self.root.after(self.delay, self.tick)`. `job` holds the id so `pause()` can cancel
it. Speed is a plain multiplier: the slider maps 0→1500 ms and 1→200 ms per symbol.

**`verdict_text()`** (line 1977) decides what the Expected output box should say, and returns
`""` when nobody asked to be checked — it never claims a verdict the user did not request.

---

## 12. Part 10 — drawing the diagram (lines 2045–2270)

This is the part with a performance story, so it is worth reading carefully.

### `measure(text)` and `radius(s)` — lines 2049, 2062

A state's circle has to be big enough for its name and its output. Working that out means
asking Tk how wide a piece of text is — and asking Tk is a **round-trip**.

`radius()` used to call `font.measure()` twice per state on **every repaint**. On a 100-state
machine that was 200 round-trips per frame, and profiling showed it was **half the cost of
drawing the entire diagram**. Since the answer cannot change unless the font does, `measure()`
now caches it by string. The cache is bounded — a machine only ever has a handful of distinct
names, and if it somehow grew past 400 it just clears and starts again.

### `draw()` — line 2067

Rebuilds the whole picture from scratch: `delete("all")`, recompute the circular layout, then
create every edge, every circle, every label.

Worth knowing while reading it:

- **Parallel edges are merged.** `q0 -"0"→ q1` and `q0 -"1"→ q1` become one arrow labelled
  `0, 1`, because two overlapping arrows are unreadable.
- **Self-loops are placed outwards**, away from the diagram centre, and turned a quarter away
  from the start arrow when they are on the initial state — otherwise the loop draws straight
  through the arrow that is meant to read as "this is where it starts".
- **The start arrow is drawn last**, so a state added later cannot bury it.
- **Layout and drag offsets are separate.** `layout` is the circle position; `off` is however
  far the user has dragged that state. Keeping them apart means a drag survives any redraw, and
  the scroll region can be grown to keep every dragged state reachable.
- Items are **tagged** so they can be found again: `s:<name>` for everything belonging to one
  state, plus `circ` and `ring` to tell the circle from the start ring, and `e<n>` for each edge.

### `highlight(prev_cur, prev_act)` — line 2214

A step changes exactly three things on the picture: the current state, the state the arrow came
from, and the arrow itself. `highlight()` re-colours those in place with `itemconfig` and
touches nothing else.

It exists because `draw()` was being called **once per animation frame**. Profiling a 100-state
machine:

| Operation | Before | After |
|---|---|---|
| `draw()` — one full repaint | 154.5 ms | 45.8 ms (the `measure()` cache) |
| `changed()` — one edit | 178.7 ms | 73.0 ms |
| `advance()` — one Step / one Run frame | 154.5 ms | **2.4 ms** |
| `reset()` — one Reset press | 154.5 ms | 2.2 ms |

Step time is now flat at about 2 ms whether the machine has 2 states or 100.

The two methods must agree, and they do: after a full run, the canvas produced by stepping is
**item-for-item identical** to the one a full `draw()` produces — 0 of 1004 items differ. The
self-test asserts exactly that (see below), so the shortcut can never quietly drift out of step
with the repaint.

`changed()` keeps calling `draw()` — the machine genuinely changed, so the picture genuinely has
to be rebuilt. Only the paths where *nothing but the highlight moved* take the cheap route.

---

## 13. Part 11 — the self-test (line 2273 on)

```bash
python moore.py --test
```

`selftest()` builds a real `App`, drives it the way a user would, and asserts on what comes
out. It covers the pure logic, the editing rules, every refusal, the simulation, the Auto Build
dialog's geometry, scrollbars, the wheel, and the layout invariants.

The invariant added with the performance work:

```python
ids = tuple(app.cv.find_all())
for _ in range(5):
    app.advance()
    assert tuple(app.cv.find_all()) == ids, "a step re-colours what is there, never repaints"
...
stepped = painted()
app.draw()
assert painted() == stepped, "highlight() paints exactly the picture draw() would have"
```

The first assertion is the sharp one: `draw()` calls `delete("all")` and hands out brand new
item ids, so **any** revert to repainting on a step changes the id list immediately. The second
proves the two paths produce the same picture.

A second, larger suite lives in `_e2e.py` (243 UI-level cases across 19 areas). It drives the
application from outside and never modifies it.

---

## 14. Design decisions

**One file.** The whole program is ~3,000 lines in `moore.py`. For a single-purpose desktop
tool this beats a package: no import cycles, no "which module owns this?", and the file reads
top to bottom in the order things were built. The cost is real — the file is long — and it is
the right trade only while the program stays this size.

**The machine is three plain values.** Not a class. `states`, `initial`, `trans` are data, so
every function that touches them is testable without a window, and there is no way for an
object to get into a state its own invariants forbid.

**Compute the whole run up front.** `simulate()` produces every row immediately, so Step, Run,
Pause and Reset are all just bookkeeping over a list. The trade is memory: a very long input
string holds a row per symbol. In practice that is nothing.

**Validate twice, at two different depths.** `validate(need_start=False)` on load accepts an
incomplete machine; `validate()` before a run requires a total one. A file you are still
building should load; a machine you are about to run must be complete.

**Errors are strings, not exceptions.** `check_input` and `ex_pair_check` return a message or
`None`. The rare case — a genuinely impossible machine, or a gap found mid-simulation — raises,
and the caller turns it into the same kind of message.

**One `changed()`.** Every mutation goes through one method. Eleven call sites, one thing to
keep correct.

**Repaint only when something moved.** See [Part 10](#12-part-10--drawing-the-diagram-lines-20452270).

**`ponytail:` comments.** Where a shortcut was taken deliberately and has a known ceiling, the
code says so and names the upgrade path — for example the saved `positions` being drag *deltas*
rather than absolute coordinates, with a note about when that would start to bite.

---

## 15. Glossary

| Term | Meaning here |
|---|---|
| **Moore machine** | A finite-state machine whose output comes from the current state, not the input. Contrast a Mealy machine, where the output comes from the transition. |
| **Alphabet** | The set of input symbols the machine understands, inferred from the transitions. |
| **Total** | Every state has a transition for every symbol in the alphabet — no gaps. Required before a run, not before saving. |
| **Initial state** | Where the machine starts, and the state whose output is printed before any input is read. |
| **Self-loop** | A transition from a state back to itself. |
| **Defaulted** | A transition no example asked for, filled with a self-loop by Auto Build and reported to the user. |
| **Myhill–Nerode** | The classical construction `synthesize()` implements by merging: two prefixes are the same state exactly when no input can tell them apart. |
