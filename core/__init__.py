"""Core machine logic - no GUI imports anywhere in this package.

Everything here is a plain function of its arguments: the Moore rules, what counts as a valid
machine, and working one out from examples. Keeping these independent of the interface is what
makes them testable without opening a window (see tests/test_core.py).

    validate / check_input   validation.py      can this machine be built / run?
    simulate / out_string    simulation.py      read an input, collect the output
    to_dict / from_dict      serialization.py   save and load JSON
    synthesize / ex_pair_check  synthesis.py    Auto Build
"""
from core.constants import DASH
from core.serialization import from_dict, no_dups, to_dict
from core.simulation import out_string, simulate
from core.synthesis import ex_pair_check, synthesize
from core.validation import check_input, validate

__all__ = ["DASH", "check_input", "ex_pair_check", "from_dict", "no_dups", "out_string",
           "simulate", "synthesize", "to_dict", "validate"]
