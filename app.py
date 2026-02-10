"""
PyXSchem Application setup and main window initialization.
"""

import sys
from typing import List

from PySide6.QtWidgets import QApplication


def run_app(args: List[str]) -> int:
    """Initialize and run the PyXSchem application."""
    app = QApplication(sys.argv)
    app.setApplicationName("PyXSchem")
    app.setApplicationVersion("0.1.0")
    app.setOrganizationName("PyXSchem")

    # Import here to avoid circular imports
    from pyxschem.ui.main_window import MainWindow

    window = MainWindow()

    # Open file if provided
    if args:
        from pathlib import Path
        file_path = Path(args[0])
        if file_path.exists():
            window.open_file(file_path)

    window.show()
    return app.exec()
