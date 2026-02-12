"""
Status bar setup for PyXSchem.

Displays:
- Current file
- Editor mode and active tool
- Grid and snap state
- Simulation state
- Current layer, coordinates, and zoom
"""

from typing import TYPE_CHECKING, Optional
from PySide6.QtWidgets import QStatusBar, QLabel

if TYPE_CHECKING:
    from pyxschem.ui.main_window import MainWindow


class StatusBarSetup:
    """
    Sets up the status bar for the main window.

    Manages permanent widgets showing editor and simulation state,
    plus coordinate/zoom information.
    """

    def __init__(self, main_window: "MainWindow"):
        self._window = main_window
        self._statusbar: Optional[QStatusBar] = None

        # Permanent widgets
        self._file_label: Optional[QLabel] = None
        self._mode_label: Optional[QLabel] = None
        self._tool_label: Optional[QLabel] = None
        self._grid_label: Optional[QLabel] = None
        self._snap_label: Optional[QLabel] = None
        self._sim_label: Optional[QLabel] = None
        self._layer_label: Optional[QLabel] = None
        self._coord_label: Optional[QLabel] = None
        self._zoom_label: Optional[QLabel] = None

    @property
    def statusbar(self) -> Optional[QStatusBar]:
        """Get the status bar."""
        return self._statusbar

    def setup_status_bar(self) -> None:
        """Create and configure the status bar."""
        self._statusbar = QStatusBar()
        self._statusbar.setSizeGripEnabled(False)
        self._window.setStatusBar(self._statusbar)

        # File info (stretches to fill space)
        self._file_label = QLabel("untitled")
        self._file_label.setObjectName("status_item_weak")
        self._statusbar.addWidget(self._file_label, 1)

        self._mode_label = QLabel("Mode: SPICE")
        self._mode_label.setObjectName("status_item")
        self._statusbar.addPermanentWidget(self._mode_label)

        self._tool_label = QLabel("Tool: Select")
        self._tool_label.setObjectName("status_item")
        self._statusbar.addPermanentWidget(self._tool_label)

        self._grid_label = QLabel("Grid: On")
        self._grid_label.setObjectName("status_item")
        self._statusbar.addPermanentWidget(self._grid_label)

        self._snap_label = QLabel("Snap: On")
        self._snap_label.setObjectName("status_item")
        self._statusbar.addPermanentWidget(self._snap_label)

        self._sim_label = QLabel("Sim: Idle")
        self._sim_label.setObjectName("status_item_ok")
        self._statusbar.addPermanentWidget(self._sim_label)

        self._layer_label = QLabel("Layer: 4")
        self._layer_label.setObjectName("status_item")
        self._statusbar.addPermanentWidget(self._layer_label)

        self._coord_label = QLabel("X: 0.0, Y: 0.0")
        self._coord_label.setObjectName("status_item")
        self._coord_label.setMinimumWidth(160)
        self._statusbar.addPermanentWidget(self._coord_label)

        self._zoom_label = QLabel("Zoom: 100%")
        self._zoom_label.setObjectName("status_item")
        self._zoom_label.setMinimumWidth(90)
        self._statusbar.addPermanentWidget(self._zoom_label)

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
            text = filename or "untitled"
            if modified:
                text += " *"
            self._file_label.setText(text)

    def update_mode(self, mode: str) -> None:
        """Update the mode display."""
        if self._mode_label:
            self._mode_label.setText(f"Mode: {mode}")

    def update_tool(self, tool_name: str) -> None:
        """Update the active tool display."""
        if self._tool_label:
            self._tool_label.setText(f"Tool: {tool_name}")

    def update_grid(self, enabled: bool) -> None:
        """Update grid status display."""
        if self._grid_label:
            self._grid_label.setText(f"Grid: {'On' if enabled else 'Off'}")

    def update_snap(self, enabled: bool) -> None:
        """Update snap status display."""
        if self._snap_label:
            self._snap_label.setText(f"Snap: {'On' if enabled else 'Off'}")

    def update_simulation(self, state: str) -> None:
        """Update simulation status display."""
        if self._sim_label:
            self._sim_label.setText(f"Sim: {state}")

    def show_message(self, message: str, timeout: int = 0) -> None:
        """Show a temporary message."""
        if self._statusbar:
            self._statusbar.showMessage(message, timeout)

    def clear_message(self) -> None:
        """Clear the temporary message."""
        if self._statusbar:
            self._statusbar.clearMessage()
