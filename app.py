"""
PyXSchem Application setup and main window initialization.
"""

import sys
from typing import List
import logging

from PySide6.QtWidgets import QApplication

from pyxschem.config import JsonConfigManager
from pyxschem.logging_config import setup_logging


logger = logging.getLogger(__name__)


def run_app(args: List[str]) -> int:
    """Initialize and run the PyXSchem application."""
    log_path = setup_logging()
    config_manager = JsonConfigManager()
    logger.info("Starting PyXSchem (args=%s, log_file=%s)", args, log_path)
    logger.info("Configuration directory: %s", config_manager.config_dir)

    app = QApplication(sys.argv)
    app.setApplicationName("PyXSchem")
    app.setApplicationVersion("0.1.0")
    app.setOrganizationName("PyXSchem")

    # Import here to avoid circular imports
    from pyxschem.ui.main_window import MainWindow

    window = MainWindow(config_manager=config_manager)

    # Open file if provided
    if args:
        from pathlib import Path
        file_path = Path(args[0])
        if file_path.exists():
            logger.info("Opening startup file: %s", file_path)
            window.open_file(file_path)
        else:
            logger.warning("Startup file not found: %s", file_path)

    window.show()
    rc = app.exec()
    logger.info("Application exited with code %d", rc)
    return rc
