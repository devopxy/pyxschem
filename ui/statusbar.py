"""
Status bar setup for PyXSchem.

Displays:
- Current coordinates (X, Y)
- Zoom level
- Current layer
- File name and modification status
- Operation hints and messages
"""

from typing import TYPE_CHECKING, Optional
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QStatusBar, QLabel, QFrame

if TYPE_CHECKING:
    from pyxschem.ui.main_window import MainWindow


class StatusBarSetup:
    """
    Sets up the status bar for the main window.

    Manages permanent widgets showing coordinates, zoom, and layer info,
    plus a message area for operation hints.
    """

    def __init__(self, main_window: "MainWindow"):
        self._window = main_window
        self._statusbar: Optional[QStatusBar] = None

        # Permanent widgets
        self._file_label: Optional[QLabel] = None
        self._coord_label: Optional[QLabel] = None
        self._zoom_label: Optional[QLabel] = None
        self._layer_label: Optional[QLabel] = None
        self._mode_label: Optional[QLabel] = None

    @property
    def statusbar(self) -> Optional[QStatusBar]:
        """Get the status bar."""
        return self._statusbar

    def setup_status_bar(self) -> None:
        """Create and configure the status bar."""
        self._statusbar = QStatusBar()
        self._window.setStatusBar(self._statusbar)

        # File info (stretches to fill space)
        self._file_label = QLabel("No file")
        self._statusbar.addWidget(self._file_label, 1)

        # Add separator
        self._add_separator()

        # Mode indicator
        self._mode_label = QLabel("Ready")
        self._mode_label.setMinimumWidth(100)
        self._statusbar.addPermanentWidget(self._mode_label)

        self._add_separator()

        # Layer indicator
        self._layer_label = QLabel("Layer: 4")
        self._layer_label.setMinimumWidth(70)
        self._statusbar.addPermanentWidget(self._layer_label)

        self._add_separator()

        # Coordinates
        self._coord_label = QLabel("X: 0.0, Y: 0.0")
        self._coord_label.setMinimumWidth(150)
        self._statusbar.addPermanentWidget(self._coord_label)

        self._add_separator()

        # Zoom level
        self._zoom_label = QLabel("Zoom: 100%")
        self._zoom_label.setMinimumWidth(80)
        self._statusbar.addPermanentWidget(self._zoom_label)

    def _add_separator(self) -> None:
        """Add a vertical separator line."""
        separator = QFrame()
        separator.setFrameShape(QFrame.VLine)
        separator.setFrameShadow(QFrame.Sunken)
        self._statusbar.addPermanentWidget(separator)

    def update_coordinates(self, x: float, y: float) -> None:
        """Update the coordinate display."""
        if self._coord_label:
            self._coord_label.setText(f"X: {x:.1f}, Y: {y:.1f}")

    def update_zoom(self, zoom: float) -> None:
        """Update the zoom display."""
        if self._zoom_label:
            percent = zoom * 100
            self._zoom_label.setText(f"Zoom: {percent:.0f}%")

    def update_layer(self, layer: int) -> None:
        """Update the layer display."""
        if self._layer_label:
            self._layer_label.setText(f"Layer: {layer}")

    def update_file(self, filename: str, modified: bool = False) -> None:
        """Update the file display."""
        if self._file_label:
            text = filename
            if modified:
                text += " *"
            self._file_label.setText(text)

    def update_mode(self, mode: str) -> None:
        """Update the mode display."""
        if self._mode_label:
            self._mode_label.setText(mode)

    def show_message(self, message: str, timeout: int = 0) -> None:
        """Show a temporary message."""
        if self._statusbar:
            self._statusbar.showMessage(message, timeout)

    def clear_message(self) -> None:
        """Clear the temporary message."""
        if self._statusbar:
            self._statusbar.clearMessage()
