"""Entry point for the frozen .exe.

PyInstaller runs its entry script as a top level module with no package
context, so the import here is absolute. `python -m countdown` still works
through countdown/__main__.py.
"""
import sys

from countdown.app import main

if __name__ == "__main__":
    sys.exit(main())
