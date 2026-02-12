"""
User Interface package for PyXSchem.

This package provides the Qt/PySide6-based user interface:
- MainWindow: Main application window with menus, toolbar, status bar
- Property editor dialog
- Symbol chooser with library browser
- Drawing and edit operations
"""

from pyxschem.ui.main_window import MainWindow
from pyxschem.ui.menubar import MenuBarSetup
from pyxschem.ui.toolbar import ToolBarSetup
from pyxschem.ui.statusbar import StatusBarSetup
from pyxschem.ui.drawing_controller import DrawingController, DrawingMode
from pyxschem.ui.edit_controller import EditController
from pyxschem.ui.command_manager import CommandManager, CommandState
from pyxschem.ui.widgets import TerminalConsoleDock

__all__ = [
    "MainWindow",
    "MenuBarSetup",
    "ToolBarSetup",
    "StatusBarSetup",
    "DrawingController",
    "DrawingMode",
    "EditController",
    "CommandManager",
    "CommandState",
    "TerminalConsoleDock",
]
