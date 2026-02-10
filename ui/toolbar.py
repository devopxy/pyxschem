"""
Toolbar setup for PyXSchem.

Provides quick access to common operations:
- File operations (New, Open, Save)
- Edit operations (Undo, Redo, Copy, Paste, Delete)
- Drawing tools (Wire, Line, Rectangle, Arc, Polygon, Text)
- View operations (Zoom, Fit, Grid)
- Navigation (Descend, Go back)
"""

from typing import TYPE_CHECKING, Optional
from PySide6.QtCore import Qt
from PySide6.QtGui import QAction, QIcon
from PySide6.QtWidgets import QToolBar, QToolButton, QWidget, QSizePolicy

if TYPE_CHECKING:
    from pyxschem.ui.main_window import MainWindow


class ToolBarSetup:
    """
    Sets up the toolbar for the main window.

    Creates toolbar with common operations grouped by category.
    """

    def __init__(self, main_window: "MainWindow"):
        self._window = main_window
        self._toolbar: Optional[QToolBar] = None

    @property
    def toolbar(self) -> Optional[QToolBar]:
        """Get the toolbar."""
        return self._toolbar

    def setup_toolbar(self) -> None:
        """Create the main toolbar."""
        self._toolbar = QToolBar("Main Toolbar")
        self._toolbar.setMovable(True)
        self._toolbar.setFloatable(True)
        self._window.addToolBar(Qt.TopToolBarArea, self._toolbar)

        self._add_file_actions()
        self._toolbar.addSeparator()
        self._add_edit_actions()
        self._toolbar.addSeparator()
        self._add_view_actions()
        self._toolbar.addSeparator()
        self._add_drawing_actions()
        self._toolbar.addSeparator()
        self._add_navigation_actions()

    def _add_file_actions(self) -> None:
        """Add file operation actions."""
        action = QAction("New", self._window)
        action.setToolTip("New schematic (Ctrl+N)")
        action.triggered.connect(self._window.new_schematic)
        self._toolbar.addAction(action)

        action = QAction("Open", self._window)
        action.setToolTip("Open file (Ctrl+O)")
        action.triggered.connect(self._window.open_file)
        self._toolbar.addAction(action)

        action = QAction("Save", self._window)
        action.setToolTip("Save file (Ctrl+S)")
        action.triggered.connect(self._window.save_file)
        self._toolbar.addAction(action)

    def _add_edit_actions(self) -> None:
        """Add edit operation actions."""
        action = QAction("Undo", self._window)
        action.setToolTip("Undo (U)")
        action.triggered.connect(self._window.undo)
        self._toolbar.addAction(action)

        action = QAction("Redo", self._window)
        action.setToolTip("Redo (Shift+U)")
        action.triggered.connect(self._window.redo)
        self._toolbar.addAction(action)

        self._toolbar.addSeparator()

        action = QAction("Copy", self._window)
        action.setToolTip("Copy (C)")
        action.triggered.connect(self._window.duplicate)
        self._toolbar.addAction(action)

        action = QAction("Move", self._window)
        action.setToolTip("Move (M)")
        action.triggered.connect(self._window.move_selected)
        self._toolbar.addAction(action)

        action = QAction("Delete", self._window)
        action.setToolTip("Delete (Del)")
        action.triggered.connect(self._window.delete_selected)
        self._toolbar.addAction(action)

        self._toolbar.addSeparator()

        action = QAction("Rotate", self._window)
        action.setToolTip("Rotate 90° (Shift+R)")
        action.triggered.connect(self._window.rotate_selected)
        self._toolbar.addAction(action)

        action = QAction("Flip H", self._window)
        action.setToolTip("Flip Horizontal (Shift+F)")
        action.triggered.connect(self._window.flip_horizontal)
        self._toolbar.addAction(action)

        action = QAction("Flip V", self._window)
        action.setToolTip("Flip Vertical (Shift+V)")
        action.triggered.connect(self._window.flip_vertical)
        self._toolbar.addAction(action)

    def _add_view_actions(self) -> None:
        """Add view operation actions."""
        action = QAction("Fit", self._window)
        action.setToolTip("Fit all in view (F)")
        action.triggered.connect(self._window.zoom_fit)
        self._toolbar.addAction(action)

        action = QAction("Zoom+", self._window)
        action.setToolTip("Zoom in (Shift+Z)")
        action.triggered.connect(self._window.zoom_in)
        self._toolbar.addAction(action)

        action = QAction("Zoom-", self._window)
        action.setToolTip("Zoom out (Ctrl+Z)")
        action.triggered.connect(self._window.zoom_out)
        self._toolbar.addAction(action)

        action = QAction("ZoomBox", self._window)
        action.setToolTip("Zoom to box (Z)")
        action.triggered.connect(self._window.zoom_box)
        self._toolbar.addAction(action)

        self._toolbar.addSeparator()

        self._grid_action = QAction("Grid", self._window)
        self._grid_action.setToolTip("Toggle grid (%)")
        self._grid_action.setCheckable(True)
        self._grid_action.setChecked(True)
        self._grid_action.triggered.connect(self._window.toggle_grid)
        self._toolbar.addAction(self._grid_action)

    def _add_drawing_actions(self) -> None:
        """Add drawing tool actions."""
        action = QAction("Wire", self._window)
        action.setToolTip("Draw wire (W)")
        action.triggered.connect(self._window.start_wire)
        self._toolbar.addAction(action)

        action = QAction("Line", self._window)
        action.setToolTip("Draw line (L)")
        action.triggered.connect(self._window.start_line)
        self._toolbar.addAction(action)

        action = QAction("Rect", self._window)
        action.setToolTip("Draw rectangle (R)")
        action.triggered.connect(self._window.start_rect)
        self._toolbar.addAction(action)

        action = QAction("Arc", self._window)
        action.setToolTip("Draw arc")
        action.triggered.connect(self._window.start_arc)
        self._toolbar.addAction(action)

        action = QAction("Poly", self._window)
        action.setToolTip("Draw polygon")
        action.triggered.connect(self._window.start_polygon)
        self._toolbar.addAction(action)

        action = QAction("Text", self._window)
        action.setToolTip("Place text (T)")
        action.triggered.connect(self._window.start_text)
        self._toolbar.addAction(action)

        self._toolbar.addSeparator()

        action = QAction("Symbol", self._window)
        action.setToolTip("Insert symbol (Ins, Ctrl+I)")
        action.triggered.connect(self._window.place_symbol)
        self._toolbar.addAction(action)

    def _add_navigation_actions(self) -> None:
        """Add hierarchy navigation actions."""
        action = QAction("Descend", self._window)
        action.setToolTip("Push into schematic (E)")
        action.triggered.connect(self._window.descend_schematic)
        self._toolbar.addAction(action)

        action = QAction("Back", self._window)
        action.setToolTip("Pop up (Ctrl+E)")
        action.triggered.connect(self._window.go_back)
        self._toolbar.addAction(action)

    def update_grid_button(self, checked: bool) -> None:
        """Update the grid button state."""
        if hasattr(self, '_grid_action'):
            self._grid_action.setChecked(checked)
