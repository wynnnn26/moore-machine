"""Unit tests for core/ - deliberately GUI-free, so they prove the machine logic on its own.

Run:  python -m tests.test_core        (no CustomTkinter required)

tests/selftest.py covers the same rules from the outside, driving the real window. These
cover them from the inside and add one structural check that cannot be made from a running
application: that importing core/ never pulls the interface in with it.
"""
import json
import os
import subprocess
import sys

from core import (DASH, check_input, ex_pair_check, from_dict, no_dups, out_string, simulate,
                  synthesize, to_dict, validate)

# the example machine the whole project is written around
S = {"q0": "0", "q1": "1"}
T = {("q0", "0"): "q0", ("q0", "1"): "q1", ("q1", "0"): "q0", ("q1", "1"): "q1"}


def raises(f, *a):
    """The message f() refused with - truthy either way, so `assert raises(...)` still holds."""
    try:
        f(*a)
    except ValueError as e:
        return str(e)
    return False


def test_core_does_not_import_the_gui():
    """core/ must import in a bare interpreter: no tkinter, no CustomTkinter, no PIL."""
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    probe = ("import sys, core; "
             "print(','.join(m for m in ('tkinter', 'customtkinter', 'PIL') if m in sys.modules))")
    out = subprocess.run([sys.executable, "-c", probe], cwd=root, capture_output=True, text=True)
    assert out.returncode == 0, out.stderr
    assert out.stdout.strip() == "", "core/ pulled in the GUI: %s" % out.stdout.strip()


def test_validation():
    assert validate(S, "q0", T) == []                      # a complete machine has no complaints
    assert any("initial" in e for e in validate(S, None, T))
    gaps = {k: v for k, v in T.items() if k != ("q1", "1")}
    assert any("has no transition for input '1'" in e for e in validate(S, "q0", gaps))
    assert any("missing state" in e for e in validate(S, "q0", {**T, ("q0", "0"): "zz"}))
    assert any("no output" in e for e in validate({"a": " "}, "a", {}))
    # every message tells the reader what to do about it
    for e in validate(S, None, T):
        assert "Fix:" in e, e


def test_simulation_follows_the_moore_rule():
    rows = simulate(S, "q0", T, "10110")
    assert rows[0] == (0, DASH, DASH, "q0", "0")           # step 0 prints the START state
    assert rows[1] == (1, "1", "q0", "q1", "1")            # then: move, then print where you landed
    assert len(rows) == len("10110") + 1                   # output is one symbol longer than input
    assert out_string(rows) == "010110"
    assert raises(simulate, S, "q0", {k: v for k, v in T.items() if k != ("q1", "1")}, "11")


def test_input_checking():
    assert check_input(T, "")                              # empty is refused
    assert check_input(T, "12")                            # symbol outside the alphabet
    assert not check_input(T, "10110")                     # valid passes


def test_serialization_round_trip():
    blob = json.loads(json.dumps(to_dict(S, "q0", T)))
    assert from_dict(blob) == (S, "q0", T)
    assert raises(from_dict, {}) and raises(from_dict, [])
    assert raises(from_dict, {**blob, "initial": "nope"})
    assert raises(from_dict, {**blob, "states": {"q0": None, "q1": "1"}})  # null must not become "None"
    assert raises(from_dict, {**blob, "transitions": blob["transitions"] * 2})
    assert raises(lambda: json.loads('{"states": {"a": "0", "a": "1"}}',
                                     object_pairs_hook=no_dups))


def test_synthesis_replays_every_example():
    examples = [("10110", "010110"), ("0", "00"), ("11", "011")]
    states, initial, trans, defaulted = synthesize(examples)
    assert validate(states, initial, trans) == []          # what it builds is a real machine
    for i, o in examples:
        assert out_string(simulate(states, initial, trans, i)) == o, i
    assert raises(synthesize, [("10", "01")])              # output too short for its input
    assert raises(synthesize, [("1", "01"), ("1", "00")])  # two examples that contradict


def test_auto_build_input_gate():
    assert not ex_pair_check("10110", "010110")            # a good pair passes
    assert ex_pair_check("10110", "")                      # output is required
    assert ex_pair_check("", "010110")                     # so is input
    assert "length" in (ex_pair_check("10110", "01011") or "")  # and they must line up


def run_core_tests():
    for name, fn in sorted(globals().items()):
        if name.startswith("test_") and callable(fn):
            fn()
    print("core tests ok (%d)" % len([n for n in globals() if n.startswith("test_")]))


if __name__ == "__main__":
    run_core_tests()
