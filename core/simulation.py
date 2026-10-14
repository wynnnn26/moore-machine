"""Simulating a machine: read the input, follow the transitions,
collect the output. The Moore rule lives here."""

from core.constants import DASH


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
