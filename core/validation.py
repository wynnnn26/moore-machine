"""Machine validation: every rule that decides whether a machine can be built or run.

No GUI imports anywhere - the rules are testable without opening a window (see tests/)."""


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
