"""
Main window for PyXSchem.

The MainWindow is the central application window containing:
- Menu bar with File, Edit, View, Options, Properties, etc.
- Toolbar with common operations
- Status bar showing coordinates and zoom
- Schematic canvas (central widget)
- Dockable panels (future: hierarchy browser, property panel)
"""

from pathlib import Path
from typing import Optional, List
import os

from PySide6.QtCore import Qt, Signal, Slot, QSettings
from PySide6.QtWidgets import (
    QMainWindow,
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QFileDialog,
    QMessageBox,
    QDockWidget,
    QTabWidget,
    QApplication,
)
from PySide6.QtGui import QKeySequence, QCloseEvent, QAction

from pyxschem.core.context import SchematicContext, UIState, NetlistType
from pyxschem.graphics import SchematicCanvas, SchematicRenderer, LayerManager
from pyxschem.io import read_schematic, write_schematic
from pyxschem.ui.menubar import MenuBarSetup
from pyxschem.ui.toolbar import ToolBarSetup
from pyxschem.ui.statusbar import StatusBarSetup


class MainWindow(QMainWindow):
    """
    Main application window for PyXSchem.

    Provides the complete schematic editor interface including:
    - Menu bar with all xschem-compatible menus
    - Toolbar with quick access to common operations
    - Status bar with coordinate and zoom display
    - Central schematic canvas
    - Tabbed interface for multiple schematics

    Signals:
        schematic_changed: Emitted when the current schematic changes
        selection_changed: Emitted when selection changes
    """

    schematic_changed = Signal(object)  # SchematicContext
    selection_changed = Signal(list)  # List of selected items

    # Recent files list
    MAX_RECENT_FILES = 10

    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)

        self.setWindowTitle("PyXSchem")
        self.setMinimumSize(1024, 768)

        # Application state
        self._context: Optional[SchematicContext] = None
        self._recent_files: List[str] = []
        self._settings = QSettings("PyXSchem", "PyXSchem")

        # UI mode flags
        self._dark_scheme = True
        self._show_grid = True
        self._snap_to_grid = True
        self._netlist_type = NetlistType.SPICE

        # Initialize components
        self._setup_layer_manager()
        self._setup_central_widget()
        self._setup_menu_bar()
        self._setup_toolbar()
        self._setup_status_bar()
        self._setup_dock_widgets()

        # Load settings
        self._load_settings()

        # Connect signals
        self._connect_signals()

        # Create new empty schematic
        self.new_schematic()

    def _setup_layer_manager(self) -> None:
        """Initialize the layer manager."""
        self._layer_manager = LayerManager(dark_scheme=self._dark_scheme)

    def _setup_central_widget(self) -> None:
        """Set up the central widget with tabbed schematic views."""
        # Tab widget for multiple schematics
        self._tab_widget = QTabWidget()
        self._tab_widget.setTabsClosable(True)
        self._tab_widget.setMovable(True)
        self._tab_widget.setDocumentMode(True)
        self._tab_widget.tabCloseRequested.connect(self._on_tab_close_requested)
        self._tab_widget.currentChanged.connect(self._on_tab_changed)

        self.setCentralWidget(self._tab_widget)

    def _setup_menu_bar(self) -> None:
        """Set up the menu bar."""
        self._menu_setup = MenuBarSetup(self)
        self._menu_setup.setup_menus()

    def _setup_toolbar(self) -> None:
        """Set up the toolbar."""
        self._toolbar_setup = ToolBarSetup(self)
        self._toolbar_setup.setup_toolbar()

    def _setup_status_bar(self) -> None:
        """Set up the status bar."""
        self._status_setup = StatusBarSetup(self)
        self._status_setup.setup_status_bar()

    def _setup_dock_widgets(self) -> None:
        """Set up dock widgets for panels."""
        # Placeholder for future dock widgets:
        # - Hierarchy browser
        # - Property panel
        # - Library browser
        pass

    def _connect_signals(self) -> None:
        """Connect internal signals."""
        pass

    def _load_settings(self) -> None:
        """Load application settings."""
        # Window geometry
        geometry = self._settings.value("geometry")
        if geometry:
            self.restoreGeometry(geometry)

        state = self._settings.value("windowState")
        if state:
            self.restoreState(state)

        # Recent files
        self._recent_files = self._settings.value("recentFiles", []) or []
        if isinstance(self._recent_files, str):
            self._recent_files = [self._recent_files] if self._recent_files else []

        # Color scheme
        self._dark_scheme = self._settings.value("darkScheme", True, type=bool)
        self._layer_manager.dark_scheme = self._dark_scheme

        # Grid settings
        self._show_grid = self._settings.value("showGrid", True, type=bool)
        self._snap_to_grid = self._settings.value("snapToGrid", True, type=bool)

    def _save_settings(self) -> None:
        """Save application settings."""
        self._settings.setValue("geometry", self.saveGeometry())
        self._settings.setValue("windowState", self.saveState())
        self._settings.setValue("recentFiles", self._recent_files[:self.MAX_RECENT_FILES])
        self._settings.setValue("darkScheme", self._dark_scheme)
        self._settings.setValue("showGrid", self._show_grid)
        self._settings.setValue("snapToGrid", self._snap_to_grid)

    # -------------------------------------------------------------------------
    # Properties
    # -------------------------------------------------------------------------

    @property
    def context(self) -> Optional[SchematicContext]:
        """Get the current schematic context."""
        return self._context

    @property
    def canvas(self) -> Optional[SchematicCanvas]:
        """Get the current canvas."""
        widget = self._tab_widget.currentWidget()
        if isinstance(widget, SchematicCanvas):
            return widget
        return None

    @property
    def renderer(self) -> Optional[SchematicRenderer]:
        """Get the current renderer."""
        canvas = self.canvas
        if canvas and hasattr(canvas, '_renderer'):
            return canvas._renderer
        return None

    @property
    def layer_manager(self) -> LayerManager:
        """Get the layer manager."""
        return self._layer_manager

    # -------------------------------------------------------------------------
    # File Operations
    # -------------------------------------------------------------------------

    @Slot()
    def new_schematic(self) -> None:
        """Create a new empty schematic."""
        context = SchematicContext()
        self._add_schematic_tab(context, "Untitled")

    @Slot()
    def new_symbol(self) -> None:
        """Create a new empty symbol."""
        context = SchematicContext()
        context.current_name = "untitled.sym"
        self._add_schematic_tab(context, "Untitled.sym")

    def _add_schematic_tab(self, context: SchematicContext, title: str) -> int:
        """Add a new tab with a schematic canvas."""
        canvas = SchematicCanvas(layer_manager=self._layer_manager)
        canvas.show_grid = self._show_grid
        canvas.snap_to_grid = self._snap_to_grid

        renderer = SchematicRenderer(canvas)
        renderer.context = context
        canvas._renderer = renderer  # Store reference

        # Connect canvas signals
        canvas.zoom_changed.connect(self._on_zoom_changed)
        canvas.cursor_moved.connect(self._on_cursor_moved)
        canvas.selection_changed.connect(self._on_selection_changed)

        idx = self._tab_widget.addTab(canvas, title)
        self._tab_widget.setCurrentIndex(idx)

        self._context = context
        self.schematic_changed.emit(context)
        self._update_window_title()

        return idx

    @Slot()
    def open_file(self, file_path: Optional[Path] = None) -> bool:
        """
        Open a schematic or symbol file.

        Args:
            file_path: Path to file, or None to show dialog

        Returns:
            True if file was opened successfully
        """
        if file_path is None:
            file_path, _ = QFileDialog.getOpenFileName(
                self,
                "Open Schematic",
                "",
                "Schematic Files (*.sch *.sym);;All Files (*)"
            )
            if not file_path:
                return False
            file_path = Path(file_path)

        if not file_path.exists():
            QMessageBox.warning(
                self,
                "File Not Found",
                f"The file '{file_path}' does not exist."
            )
            return False

        try:
            context = read_schematic(str(file_path))
            self._add_schematic_tab(context, file_path.name)
            self._add_recent_file(str(file_path))
            return True
        except Exception as e:
            QMessageBox.critical(
                self,
                "Error Opening File",
                f"Failed to open '{file_path}':\n{e}"
            )
            return False

    @Slot()
    def open_file_new_window(self) -> None:
        """Open a file in a new window."""
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "Open Schematic in New Window",
            "",
            "Schematic Files (*.sch *.sym);;All Files (*)"
        )
        if file_path:
            # Create new window
            new_window = MainWindow()
            new_window.open_file(Path(file_path))
            new_window.show()

    @Slot()
    def save_file(self) -> bool:
        """Save the current schematic."""
        if not self._context:
            return False

        if not self._context.current_name or self._context.current_name.startswith("untitled"):
            return self.save_file_as()

        return self._save_to_file(self._context.current_name)

    @Slot()
    def save_file_as(self) -> bool:
        """Save the current schematic with a new name."""
        if not self._context:
            return False

        suffix = ".sym" if self._context.is_symbol else ".sch"
        file_filter = "Symbol Files (*.sym)" if self._context.is_symbol else "Schematic Files (*.sch)"

        file_path, _ = QFileDialog.getSaveFileName(
            self,
            "Save Schematic As",
            "",
            f"{file_filter};;All Files (*)"
        )

        if not file_path:
            return False

        # Ensure correct extension
        if not file_path.endswith(suffix):
            file_path += suffix

        return self._save_to_file(file_path)

    def _save_to_file(self, file_path: str) -> bool:
        """Save schematic to a specific file."""
        if not self._context:
            return False

        try:
            self._context.current_name = file_path
            write_schematic(self._context, file_path)
            self._context.modified = False
            self._update_tab_title()
            self._update_window_title()
            self._add_recent_file(file_path)
            return True
        except Exception as e:
            QMessageBox.critical(
                self,
                "Error Saving File",
                f"Failed to save '{file_path}':\n{e}"
            )
            return False

    @Slot()
    def reload_file(self) -> None:
        """Reload the current file from disk."""
        if not self._context or not self._context.current_name:
            return

        if self._context.modified:
            result = QMessageBox.question(
                self,
                "Reload File",
                "The schematic has unsaved changes. Are you sure you want to reload?",
                QMessageBox.Yes | QMessageBox.No
            )
            if result != QMessageBox.Yes:
                return

        try:
            file_path = self._context.current_name
            new_context = read_schematic(file_path)

            # Update the current tab
            canvas = self.canvas
            if canvas and canvas._renderer:
                canvas._renderer.context = new_context
                canvas._renderer.fit_view()

            self._context = new_context
            self.schematic_changed.emit(new_context)
            self._update_window_title()
        except Exception as e:
            QMessageBox.critical(
                self,
                "Error Reloading File",
                f"Failed to reload file:\n{e}"
            )

    def _add_recent_file(self, file_path: str) -> None:
        """Add a file to the recent files list."""
        if file_path in self._recent_files:
            self._recent_files.remove(file_path)
        self._recent_files.insert(0, file_path)
        self._recent_files = self._recent_files[:self.MAX_RECENT_FILES]
        self._menu_setup.update_recent_files_menu()

    def open_recent_file(self, file_path: str) -> None:
        """Open a file from the recent files list."""
        self.open_file(Path(file_path))

    # -------------------------------------------------------------------------
    # View Operations
    # -------------------------------------------------------------------------

    @Slot()
    def zoom_in(self) -> None:
        """Zoom in."""
        if self.canvas:
            self.canvas.zoom_in()

    @Slot()
    def zoom_out(self) -> None:
        """Zoom out."""
        if self.canvas:
            self.canvas.zoom_out()

    @Slot()
    def zoom_fit(self) -> None:
        """Fit all content in view."""
        if self.renderer:
            self.renderer.fit_view()

    @Slot()
    def zoom_box(self) -> None:
        """Start zoom box selection mode."""
        if self._context:
            self._context.ui_state = UIState.STARTZOOM

    @Slot()
    def toggle_grid(self) -> None:
        """Toggle grid visibility."""
        self._show_grid = not self._show_grid
        if self.canvas:
            self.canvas.show_grid = self._show_grid

    @Slot()
    def toggle_color_scheme(self) -> None:
        """Toggle between dark and light color schemes."""
        self._dark_scheme = not self._dark_scheme
        self._layer_manager.dark_scheme = self._dark_scheme

        # Update all canvases
        for i in range(self._tab_widget.count()):
            canvas = self._tab_widget.widget(i)
            if isinstance(canvas, SchematicCanvas):
                canvas.set_dark_scheme(self._dark_scheme)
                if hasattr(canvas, '_renderer'):
                    canvas._renderer.render()

    @Slot()
    def redraw(self) -> None:
        """Force a redraw of the current schematic."""
        if self.renderer:
            self.renderer.render()

    # -------------------------------------------------------------------------
    # Edit Operations
    # -------------------------------------------------------------------------

    @Slot()
    def undo(self) -> None:
        """Undo the last operation."""
        # TODO: Implement undo stack
        self.statusBar().showMessage("Undo not yet implemented", 2000)

    @Slot()
    def redo(self) -> None:
        """Redo the last undone operation."""
        # TODO: Implement redo
        self.statusBar().showMessage("Redo not yet implemented", 2000)

    @Slot()
    def cut(self) -> None:
        """Cut selected objects to clipboard."""
        self.copy()
        self.delete_selected()

    @Slot()
    def copy(self) -> None:
        """Copy selected objects to clipboard."""
        # TODO: Implement clipboard
        self.statusBar().showMessage("Copy not yet implemented", 2000)

    @Slot()
    def paste(self) -> None:
        """Paste objects from clipboard."""
        # TODO: Implement paste
        self.statusBar().showMessage("Paste not yet implemented", 2000)

    @Slot()
    def delete_selected(self) -> None:
        """Delete selected objects."""
        # TODO: Implement delete
        self.statusBar().showMessage("Delete not yet implemented", 2000)

    @Slot()
    def select_all(self) -> None:
        """Select all objects."""
        # TODO: Implement select all
        self.statusBar().showMessage("Select all not yet implemented", 2000)

    @Slot()
    def deselect_all(self) -> None:
        """Deselect all objects."""
        if self.canvas:
            self.canvas.get_scene().clearSelection()

    @Slot()
    def duplicate(self) -> None:
        """Duplicate selected objects."""
        if self._context:
            self._context.ui_state = UIState.STARTCOPY

    @Slot()
    def move_selected(self) -> None:
        """Start moving selected objects."""
        if self._context:
            self._context.ui_state = UIState.STARTMOVE

    @Slot()
    def rotate_selected(self) -> None:
        """Rotate selected objects 90 degrees."""
        # TODO: Implement rotation
        self.statusBar().showMessage("Rotate not yet implemented", 2000)

    @Slot()
    def flip_horizontal(self) -> None:
        """Flip selected objects horizontally."""
        # TODO: Implement flip
        self.statusBar().showMessage("Flip horizontal not yet implemented", 2000)

    @Slot()
    def flip_vertical(self) -> None:
        """Flip selected objects vertically."""
        # TODO: Implement flip
        self.statusBar().showMessage("Flip vertical not yet implemented", 2000)

    # -------------------------------------------------------------------------
    # Drawing Operations
    # -------------------------------------------------------------------------

    @Slot()
    def start_wire(self) -> None:
        """Start drawing a wire."""
        if self._context:
            self._context.ui_state = UIState.STARTWIRE
            self.statusBar().showMessage("Click to start wire, click to add points, double-click to finish")

    @Slot()
    def start_line(self) -> None:
        """Start drawing a line."""
        if self._context:
            self._context.ui_state = UIState.STARTLINE
            self.statusBar().showMessage("Click to start line, click to end")

    @Slot()
    def start_rect(self) -> None:
        """Start drawing a rectangle."""
        if self._context:
            self._context.ui_state = UIState.STARTRECT
            self.statusBar().showMessage("Click to start rectangle, click to set opposite corner")

    @Slot()
    def start_arc(self) -> None:
        """Start drawing an arc."""
        if self._context:
            self._context.ui_state = UIState.STARTARC
            self.statusBar().showMessage("Click to set center, drag to set radius")

    @Slot()
    def start_polygon(self) -> None:
        """Start drawing a polygon."""
        if self._context:
            self._context.ui_state = UIState.STARTPOLYGON
            self.statusBar().showMessage("Click to add points, double-click to finish")

    @Slot()
    def start_text(self) -> None:
        """Start placing text."""
        if self._context:
            self._context.ui_state = UIState.PLACE_TEXT
            self.statusBar().showMessage("Click to place text")

    @Slot()
    def place_symbol(self) -> None:
        """Open symbol chooser to place a component."""
        from pyxschem.ui.dialogs import SymbolChooserDialog

        dialog = SymbolChooserDialog(self)
        if dialog.exec():
            symbol_path = dialog.selected_symbol
            if symbol_path:
                self._context.ui_state = UIState.PLACE_SYMBOL
                # TODO: Load symbol and start placement
                self.statusBar().showMessage(f"Click to place {symbol_path}")

    # -------------------------------------------------------------------------
    # Properties
    # -------------------------------------------------------------------------

    @Slot()
    def edit_properties(self) -> None:
        """Edit properties of selected object."""
        from pyxschem.ui.dialogs import PropertyEditorDialog

        # TODO: Get selected object properties
        dialog = PropertyEditorDialog(self)
        if dialog.exec():
            # TODO: Apply changes
            pass

    @Slot()
    def edit_schematic_properties(self) -> None:
        """Edit schematic-level properties."""
        from pyxschem.ui.dialogs import PropertyEditorDialog

        if not self._context:
            return

        dialog = PropertyEditorDialog(self, self._context.schprop or "")
        if dialog.exec():
            self._context.schprop = dialog.text
            self._context.modified = True
            self._update_tab_title()

    # -------------------------------------------------------------------------
    # Hierarchy Navigation
    # -------------------------------------------------------------------------

    @Slot()
    def descend_schematic(self) -> None:
        """Descend into selected instance's schematic."""
        # TODO: Implement hierarchy navigation
        self.statusBar().showMessage("Descend not yet implemented", 2000)

    @Slot()
    def descend_symbol(self) -> None:
        """Descend into selected instance's symbol."""
        # TODO: Implement hierarchy navigation
        self.statusBar().showMessage("Descend symbol not yet implemented", 2000)

    @Slot()
    def go_back(self) -> None:
        """Go back up one level in hierarchy."""
        if self._context and self._context.pop_hierarchy():
            # TODO: Reload parent schematic
            self._update_window_title()
        else:
            self.statusBar().showMessage("Already at top level", 2000)

    # -------------------------------------------------------------------------
    # Netlisting
    # -------------------------------------------------------------------------

    @Slot()
    def generate_netlist(self) -> None:
        """Generate netlist for current schematic."""
        # TODO: Implement netlisting
        self.statusBar().showMessage("Netlist generation not yet implemented", 2000)

    @Slot()
    def set_netlist_type_spice(self) -> None:
        """Set netlist type to SPICE."""
        self._netlist_type = NetlistType.SPICE
        self.statusBar().showMessage("Netlist type: SPICE", 2000)

    @Slot()
    def set_netlist_type_verilog(self) -> None:
        """Set netlist type to Verilog."""
        self._netlist_type = NetlistType.VERILOG
        self.statusBar().showMessage("Netlist type: Verilog", 2000)

    @Slot()
    def set_netlist_type_vhdl(self) -> None:
        """Set netlist type to VHDL."""
        self._netlist_type = NetlistType.VHDL
        self.statusBar().showMessage("Netlist type: VHDL", 2000)

    # -------------------------------------------------------------------------
    # Tab Management
    # -------------------------------------------------------------------------

    def _on_tab_close_requested(self, index: int) -> None:
        """Handle tab close request."""
        canvas = self._tab_widget.widget(index)
        if isinstance(canvas, SchematicCanvas) and hasattr(canvas, '_renderer'):
            context = canvas._renderer.context
            if context and context.modified:
                result = QMessageBox.question(
                    self,
                    "Close Tab",
                    f"The schematic '{context.filename}' has unsaved changes.\n"
                    "Do you want to save before closing?",
                    QMessageBox.Save | QMessageBox.Discard | QMessageBox.Cancel
                )
                if result == QMessageBox.Save:
                    self._save_to_file(context.current_name)
                elif result == QMessageBox.Cancel:
                    return

        self._tab_widget.removeTab(index)

        # Create new tab if all tabs closed
        if self._tab_widget.count() == 0:
            self.new_schematic()

    def _on_tab_changed(self, index: int) -> None:
        """Handle tab change."""
        if index < 0:
            return

        canvas = self._tab_widget.widget(index)
        if isinstance(canvas, SchematicCanvas) and hasattr(canvas, '_renderer'):
            self._context = canvas._renderer.context
            self.schematic_changed.emit(self._context)
            self._update_window_title()

    def _update_tab_title(self) -> None:
        """Update the current tab's title."""
        if not self._context:
            return

        idx = self._tab_widget.currentIndex()
        title = self._context.filename
        if self._context.modified:
            title += " *"
        self._tab_widget.setTabText(idx, title)

    def _update_window_title(self) -> None:
        """Update the window title."""
        if self._context and self._context.current_name:
            title = f"PyXSchem - {self._context.current_name}"
            if self._context.modified:
                title += " *"
        else:
            title = "PyXSchem"
        self.setWindowTitle(title)

    # -------------------------------------------------------------------------
    # Canvas Signal Handlers
    # -------------------------------------------------------------------------

    def _on_zoom_changed(self, zoom: float) -> None:
        """Handle zoom change from canvas."""
        self._status_setup.update_zoom(zoom)

    def _on_cursor_moved(self, x: float, y: float) -> None:
        """Handle cursor movement from canvas."""
        self._status_setup.update_coordinates(x, y)

    def _on_selection_changed(self) -> None:
        """Handle selection change from canvas."""
        # TODO: Update property panel
        self.selection_changed.emit([])

    # -------------------------------------------------------------------------
    # Event Handlers
    # -------------------------------------------------------------------------

    def closeEvent(self, event: QCloseEvent) -> None:
        """Handle window close event."""
        # Check for unsaved changes in all tabs
        for i in range(self._tab_widget.count()):
            canvas = self._tab_widget.widget(i)
            if isinstance(canvas, SchematicCanvas) and hasattr(canvas, '_renderer'):
                context = canvas._renderer.context
                if context and context.modified:
                    result = QMessageBox.question(
                        self,
                        "Quit",
                        f"The schematic '{context.filename}' has unsaved changes.\n"
                        "Do you want to save before closing?",
                        QMessageBox.Save | QMessageBox.Discard | QMessageBox.Cancel
                    )
                    if result == QMessageBox.Save:
                        self._tab_widget.setCurrentIndex(i)
                        if not self.save_file():
                            event.ignore()
                            return
                    elif result == QMessageBox.Cancel:
                        event.ignore()
                        return

        self._save_settings()
        event.accept()

    def keyPressEvent(self, event) -> None:
        """Handle key press events."""
        key = event.key()
        modifiers = event.modifiers()

        # Escape key cancels current operation
        if key == Qt.Key_Escape:
            if self._context:
                self._context.ui_state = UIState.NONE
            self.deselect_all()
            self.statusBar().clearMessage()
            event.accept()
            return

        super().keyPressEvent(event)
