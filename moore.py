"""Backwards-compatible entry point for the Moore Machine Simulator.

The simulator was split into a modular layout; this file keeps the old commands working:

    main.py     the entry point            core/   machine logic (validation, simulation,
    moore.py    this file - forwards          synthesis, serialization)
                                                 ui/   the interface (pages, widgets,
    python main.py            run the app          dialogs, diagram, theme, icons)
    python moore.py --test    run the tests        tests/  the test suite

It has no code of its own - only the re-exports the test driver reads by the old name.
"""
from main import main

from core import (DASH, check_input, ex_pair_check, from_dict, no_dups, out_string, simulate,
                  synthesize, to_dict, validate)
from ui.app import App

__all__ = ["App", "DASH", "check_input", "ex_pair_check", "from_dict", "main", "no_dups",
           "out_string", "simulate", "synthesize", "to_dict", "validate"]

if __name__ == "__main__":
    raise SystemExit(main())
