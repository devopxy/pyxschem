"""
PyXSchem entry point.

Usage:
    python -m pyxschem [schematic.sch]
"""

import sys
from pathlib import Path


def main() -> int:
    """Main entry point for PyXSchem."""
    from pyxschem.app import run_app
    return run_app(sys.argv[1:])


if __name__ == "__main__":
    sys.exit(main())
