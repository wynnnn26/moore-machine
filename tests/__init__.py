"""Automated tests for the simulator.

    python main.py --test     whole suite - pure logic, then the GUI end-to-end check
    python -m tests           the same thing
    python -m tests.test_core just the machine logic; needs no GUI at all

Imports are done inside run_all() so that importing the tests package never drags in
CustomTkinter - which is exactly what tests/test_core.py asserts.
"""


def run_all():
    """Run every suite in order and return 0 only if all of them pass."""
    from tests.test_core import run_core_tests

    run_core_tests()      # pure logic first, while the GUI has not been imported yet
    from tests.selftest import selftest

    selftest()            # prints "self-check ok"
    return 0
