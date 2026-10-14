"""Saving and loading machines as JSON.

from_dict() finishes by running validate(), so a rejected file can never half-load."""

from core.validation import validate


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
