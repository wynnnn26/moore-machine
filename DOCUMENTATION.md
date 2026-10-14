# Documentation — how the simulator is built

This is a guided tour of the source. It assumes no prior knowledge of the project: what the
program is made of, what each part does, and why it is built that way.

The application used to be a single module, `moore.py`. It is now a small package — `core/` for
the machine logic, `ui/` for the interface, `tests/` for the tests — with a thin `moore.py`
forwarder left behind so the old commands still work. The split moved code; it did not change
what any of it does. The whole point of the layout is stated in
[Design decisions](#14-design-decisions): `core` cannot import `ui`, so the machine rules are
testable without a window.

> Original single-file line numbers still appear in places as landmarks — they refer to the
> pre-split `moore.py`, which is preserved in git history.

---

## Contents

1. [The big picture](#1-the-big-picture)
2. [The data model](#2-the-data-model)
3. [core/ — pure machine logic](#3-core--pure-machine-logic)
4. [ui/icons.py — icons](#4-uiiconspy--icons)
5. [ui/widgets/ — the GUI toolkit](#5-uiwidgets--the-gui-toolkit)
6. [ui/pages.py — `App` and the window layout](#6-uipagespy--app-and-the-window-layout)
7. [ui/dialogs.py — dialogs and Auto Build](#7-uidialogspy--dialogs-and-auto-build)
8. [ui/theme.py and the view — appearance and diagram control](#8-uithemepy-and-the-view--appearance-and-diagram-control)
9. [Notifications](#9-notifications)
10. [ui/app.py — editing the machine](#10-uiapppy--editing-the-machine)
11. [Simulation](#11-simulation)
12. [ui/diagram.py — drawing the diagram](#12-uidiagrampy--drawing-the-diagram)
13. [tests/ — the test suites](#13-tests--the-test-suites)
14. [Design decisions](#14-design-decisions)
15. [Glossary](#15-glossary)

---

## 1. The big picture

```
        main.py ──────── entry point: open the window, or run the tests with --test
        moore.py ─────── forwarder: re-exports the old names, calls main()
   │
   ├── core/                    machine logic — imports no GUI, ever
   │     constants.py           DASH, the placeholder shown at step 0
   │     validation.py          validate · check_input
   │     simulation.py          simulate · out_string
   │     serialization.py       to_dict · from_dict · no_dups
   │     synthesis.py           ex_pair_check · synthesize
   │
   ├── ui/                      the interface
   │     theme.py               fonts, STYLES, help text, light/dark   (ThemeMixin)
   │     icons.py               draw_icon
   │     widgets/helpers.py     winfo_exists · auto_hide_bar · Tip
   │     widgets/kit.py         WidgetKit: card · tree · btn · field … (WidgetKit)
   │     pages.py               build() and one builder per panel      (PagesMixin)
   │     dialogs.py             popup · help · add state · Auto Build  (DialogMixin)
   │     diagram.py             zoom · pan · drag · export · draw …    (DiagramMixin)
   │     app.py                 class App — state, editing, simulation
   │
   └── tests/                   test_core.py (logic only) · selftest.py (drives the window)
```

`App` is assembled from mixins — `class App(ThemeMixin, DialogMixin, DiagramMixin, PagesMixin,
WidgetKit)` — and none of those mixins imports `App`. That is what keeps the cycle out: the
dependency always points from `app.py` towards the others, never back.

Two rules run through the whole project:

1. **The machine logic never touches the GUI.** Everything in `core/` is a plain function of its
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

A tuple key for transitions is the single most useful decision in the project. Looking up
`trans[(cur, a)]` is one dictionary hit — no searching a list, no possibility of accidentally
adding the same transition twice.

`App.__init__` (in `ui/app.py`) holds these, plus the simulation state:

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

## 3. core/ — pure machine logic

No GUI imports are used here at all — `tests/test_core.py` asserts that by importing `core/` in a
fresh interpreter and checking the GUI modules are still absent.

### `validate(states, initial, trans, need_start=True)` — `core/validation.py`

Returns a **list** of human-readable problems, not a boolean. Showing the user every problem at
once is much kinder than making them fix them one at a time.

It checks, in order: there is at least one state; no state has an empty name or a missing
output; every transition's symbols and endpoints are real; the initial state exists. With
`need_start=True` it additionally requires an initial state and **no gaps** — a gap being a
state that is missing a transition for a symbol the alphabet uses.

`need_start=False` is for loading a file: a machine may legitimately be incomplete on disk and
completed later in the editor, but it cannot be *run* until it is total.

### `check_input(trans, text)` — `core/validation.py`

Checks the input string against the alphabet that `trans` actually uses. Note the character
handling: a stray space is reported as `' '` — a *visible* space — because an invisible
character in the error message is worse than useless.

### `simulate(states, initial, trans, text)` — `core/simulation.py`

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

### `out_string(rows)` — `core/simulation.py`

Joins the outputs. Single-character outputs concatenate directly (`010110`); longer ones are
joined with a space so a multi-symbol output stays readable.

### `to_dict` / `from_dict` / `no_dups` — `core/serialization.py`

The JSON boundary. Two details are worth knowing:

- `no_dups` is passed to `json.load(..., object_pairs_hook=no_dups)`. Plain `dict(pairs)` would
  silently keep the **last** of two identical keys, so a file with `"q0"` twice would quietly
  lose a state. Raising instead means the user is told.
- `from_dict` raises `ValueError` with a readable message for every failure mode, and finishes
  by running `validate()`. A rejected file can never half-load.

### `ex_pair_check(inp, out)` — `core/synthesis.py`

The Auto Build gate, checked in the most useful order: reject a space first (the most common
slip), then an empty input, then an empty output (the message names a concrete example of a
correct answer), then the wrong length.

### `synthesize(examples)` — `core/synthesis.py`

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

## 4. ui/icons.py — icons

`draw_icon(name, fg, px)` renders an icon into a `PIL.Image` and converts it to a Tk photo. It
is a small drawing DSL: each icon is a list of primitives (`line`, `arc`, `ring`, `dot`) that a
few helpers turn into pixel coordinates. Keeping icons as data means the whole set stays in one
place and scales cleanly with the requested size.

This is also where PNG export comes from — the same machinery renders a diagram at a chosen
size.

---

## 5. ui/widgets/ — the GUI toolkit

Small pieces that the rest of the GUI leans on, split across two modules.

`helpers.py`:

- **`winfo_exists(w)`** — a widget that has been destroyed raises `TclError` when you
  ask it anything. Wrapping the check keeps call sites readable.
- **`auto_hide_bar(sf)`** — a scrollbar that reports a *reserved gutter* rather than
  appearing and disappearing. The comment above it explains a genuinely subtle bug: hiding the
  bar let the tree stretch into the space, ttk then reported the stretched width as its
  requested size, Tk gave the bar a zero-width window, and it could never come back. Reserving
  the gutter costs 24 px and never lies about the content.
- **`Tip`** — hover tooltips, bound on `<Enter>`/`<Leave>` and shown on demand. There
  is no timer hiding them, so a slow reader never loses one mid-sentence.

`kit.py` — **`WidgetKit`** (`wrapped`, `card`, `tree`, `btn`, `icon_btn`, `field`, `empty_note`)
— one place that knows how this app draws a panel, a table or a button, so every screen looks
the same and a style change is one edit.

`tree()` deserves a note: it binds the mouse wheel **to the table**, so scrolling a long results
table works without hunting for a thin scrollbar — and the diagram's own wheel binding is on the
canvas alone, so scrolling a table never zooms the picture.

---

## 6. ui/pages.py — `App` and the window layout

`ui/app.py` defines `class App`, whose `__init__` sets up state and calls `build()`.

`build()` (in `ui/pages.py`) constructs the window top to bottom. It owns the window itself —
title, size, maximising, the ttk table style, grid weights — and then hands each panel to its
own method:

| Region | Builder | Contents |
|---|---|---|
| Top bar | `build_topbar(r)` | the "what to do next" hint, plus file / view / destructive buttons grouped by colour |
| Machine Editor (left) | `build_editor(r)` | Auto Build, then the **States** and **Transitions** cards |
| Machine Diagram (top right) | `build_diagram(r)` | a scrollable, zoomable, draggable Tk canvas |
| Simulation (bottom right) | `build_simulation(r)` | input, expected output, controls, live status |
| Simulation Output | `build_output(sm, rowf)` | the results table and the output sequence in one place |

The pages share no local variables at all, except the two that are passed explicitly: the root
window goes in, and `build_simulation` returns `(sm, rowf)` because the Simulation Output panel
is a child of the Simulation card. Everything a later action needs is stored on `self`.

Two conventions are worth knowing when reading it:

- **Colour is meaning.** Blue means "go" (Step, Run, Add), grey means "neutral" (Edit, Reset),
  red means "destroys something" (Delete, Clear), green means "safe or constructive" (Load
  Example, Auto Build, Set as Initial), orange means "stop" (Pause). The palette lives in one
  `STYLES` dict in `ui/theme.py`.
- **Panels are cards.** `card()` gives every section the same rounded container and heading, so
  the layout reads as a set of groups rather than a wall of widgets.

`set_panel(mode)` also lives here: it shrinks the diagram to its header, or the simulation to its
header, to give the other one the whole column. Pressing the active button restores normal.
It only changes packing, so the machine and any run in progress are untouched.

---

## 7. ui/dialogs.py — dialogs and Auto Build

`popup()` is the single way any dialog opens: it centres the window over its
parent, keeps it on top, and makes it dismissible with the **×** or a click outside — never by
a timer.

`settle()` inside it contains one of the most important comments in the project. It used to
re-centre on every `<Configure>` event, including the ones its own re-centring caused, so the
event queue never drained and opening a dialog cost over a second. It now only re-centres when
the window actually **grew**. That single guard took Auto Build's open time from 1.46 s to 0.11 s.

Auto Build itself is three methods:

- `auto_build_dialog()` — the two inputs and a live hint saying how long the output
  must be.
- `auto_build_go(w)` — validate, synthesize, and on failure **leave the dialog
  open** with the problem shown inside it. The window grows to fit the message; typing clears
  it; only a successful build closes the dialog and asks before replacing the machine.
- `ex_install(...)` — puts the result on screen: states, transitions, input and
  expected output, then runs it so the answer appears immediately.

Note the ordering in `auto_build_go`: the dialog is destroyed **before** the confirmation box is
shown. A dialog holding a `grab` would otherwise hide a message box parented to the main window.

---

## 8. ui/theme.py and the view — appearance and diagram control

`ui/theme.py` holds the constants — fonts, `STYLES`, the help text — and `ThemeMixin`:

- `toggle_theme()` — flips light/dark and repaints.

`ui/diagram.py` holds the view around the picture:

- `zoom_at(factor, e)` — zooms around a point, keeping the thing under the pointer
  under the pointer.
- `on_wheel` — plain wheel pans, Ctrl+wheel zooms. Bound on the canvas only.
- `drag_start` / `drag_move` / `drag_end` — pressing a state moves that state;
  pressing empty canvas pans the view instead, so a machine bigger than the window is still
  reachable. The grab offset is remembered so the circle does not jump to the cursor.
- `export_png()` — captures the canvas to a file.

---

## 9. Notifications

`notify(kind, title, message)` (in `ui/app.py`) puts a box over the Machine Editor sidebar.

The constraints it is built to: **one at a time** (a run of errors cannot bury the interface),
**no timer** (nothing is taken away while it is being read), **no grab** (every other control
stays usable), and dismissed by the **×** or by clicking anywhere outside it. It never covers
the diagram or the simulation controls.

`err()`, `warn()` and `ok()` are the three colours of it, and they also
record into `self.notices` — a bounded history the tests read.

Destructive confirmations deliberately use a normal modal `messagebox.askyesno` instead: those
*should* stop you.

---

## 10. ui/app.py — editing the machine

### States

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

### Transitions

`read_state`'s twin, `read_trans()`, checks both endpoints exist and that the symbol is exactly
one character. `add_trans()` also refuses a duplicate `(from, symbol)` pair, because a function
that takes two values cannot have two.

### Whole-machine actions

`load_example`, `clear`, `save`, `load`.

`changed()` is the one entry point every mutation funnels through:

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

## 11. Simulation

```
start()  →  validate → check_input → simulate → rows  → advance()   (step 0)
step()   →  start() if needed → advance()
run()    →  tick() now, then tick() again after delay, until the rows run out
advance()→  reveal rows[shown], then highlight() + refresh the panels
reset()  →  rows=[], shown=0, highlight back to the start state
```

**`start()`** begins by calling `reset()`. That is not tidiness — a *refused* start
must not leave the previous run's output on screen, because then the panel would be showing
results for something that never ran.

**`advance()`** is one step. It reveals a row, updates the status line, and calls
`highlight()` — see the next section, because that call is load-bearing for performance.

**`tick()`** is the animation loop: advance, and if there is more, schedule itself
again with `self.root.after(self.delay, self.tick)`. `job` holds the id so `pause()` can cancel
it. Speed is a plain multiplier: the slider maps 0→1500 ms and 1→200 ms per symbol.

**`verdict_text()`** decides what the Expected output box should say, and returns
`""` when nobody asked to be checked — it never claims a verdict the user did not request.

All of this is in `ui/app.py`; the picture it drives is `ui/diagram.py`.

---

## 12. ui/diagram.py — drawing the diagram

This is the part with a performance story, so it is worth reading carefully.

### `measure(text)` and `radius(s)`

A state's circle has to be big enough for its name and its output. Working that out means
asking Tk how wide a piece of text is — and asking Tk is a **round-trip**.

`radius()` used to call `font.measure()` twice per state on **every repaint**. On a 100-state
machine that was 200 round-trips per frame, and profiling showed it was **half the cost of
drawing the entire diagram**. Since the answer cannot change unless the font does, `measure()`
now caches it by string. The cache is bounded — a machine only ever has a handful of distinct
names, and if it somehow grew past 400 it just clears and starts again.

### `draw()`

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

### `highlight(prev_cur, prev_act)`

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

## 13. tests/ — the test suites

```bash
python main.py --test      # everything
python -m tests            # the same, from the tests package
python -m tests.test_core  # just the machine logic; needs no GUI at all
```

**`tests/test_core.py`** exercises `core/` directly with no window at all, and includes one
structural check that a running application cannot make: importing `core/` in a fresh
interpreter must not bring `tkinter`, `customtkinter` or `PIL` in with it.

**`tests/selftest.py`** builds a real `App`, drives it the way a user would, and asserts on what
comes out. It covers the pure logic, the editing rules, every refusal, the simulation, the Auto
Build dialog's geometry, scrollbars, the wheel, and the layout invariants.

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

A second, larger end-to-end driver exists alongside the project (243 UI-level cases across 19
areas). It drives the application from outside and never modifies it. It is a development tool
and is deliberately not published in this repository.

---

## 14. Design decisions

**A package, split along one line.** `core/` and `ui/` are the only two top-level halves, and the
dependency between them is one-way: `ui` may import `core`, never the reverse. Everything else
was split where the seams already were — one module per panel builder, per dialog family, per
drawing concern — rather than by guessing at a future structure. The mixin shape
(`class App(ThemeMixin, ...)`) exists so the pieces could be separated without any of them
having to know what `App` is, which is what keeps the cycle out.

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

**Repaint only when something moved.** See [drawing the diagram](#12-uidiagrampy--drawing-the-diagram).

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
