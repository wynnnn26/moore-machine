"""Moore Machine Simulator - entry point.

Run:        python main.py
Self-check: python main.py --test        (or:  python -m tests)

The application itself lives in ui/ (interface) and core/ (machine logic); this file only
decides which of the two things to do.
"""
import sys


def main(argv=None):
    argv = sys.argv[1:] if argv is None else list(argv)

    if "--test" in argv:
        from tests import run_all
        return run_all()

    from ui import ctk        # ui checks CustomTkinter is installed before anything else runs
    from ui.app import App

    root = ctk.CTk()
    App(root)
    root.mainloop()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
