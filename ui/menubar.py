"""
Menu bar setup for PyXSchem.

Provides all xschem-compatible menus:
- File: New, Open, Save, Export, Recent files, Quit
- Edit: Undo, Redo, Cut, Copy, Paste, Delete, Select, Move, Rotate
- View: Zoom, Grid, Colors, Layers
- Options: Snap, Netlist format, Drawing options
- Properties: Edit properties, Schematic properties
- Layers: Layer visibility and selection
- Tools: Search, Align, Measurement
- Symbol: Symbol-specific operations
- Highlight: Net highlighting operations
- Simulation: Netlist, Simulate, Waves
- Help: Documentation, About
"""

from typing import TYPE_CHECKING, List, Optional
from PySide6.QtGui import QAction, QKeySequence, QActionGroup
from PySide6.QtWidgets import QMenu, QMenuBar

if TYPE_CHECKING:
    from pyxschem.ui.main_window import MainWindow


class MenuBarSetup:
    """
    Sets up the menu bar for the main window.

    Creates all menus with their actions and keyboard shortcuts,
    matching the xschem menu structure.
    """

    def __init__(self, main_window: "MainWindow"):
        self._window = main_window
        self._menubar = main_window.menuBar()
        self._recent_files_menu: Optional[QMenu] = None

    def setup_menus(self) -> None:
        """Create all menus."""
        self._create_file_menu()
        self._create_edit_menu()
        self._create_view_menu()
        self._create_options_menu()
        self._create_properties_menu()
        self._create_layers_menu()
        self._create_tools_menu()
        self._create_symbol_menu()
        self._create_highlight_menu()
        self._create_simulation_menu()
        self._create_help_menu()

    def _create_file_menu(self) -> None:
        """Create the File menu."""
        menu = self._menubar.addMenu("&File")

        # New
        action = menu.addAction("Clear &Schematic")
        action.setShortcut(QKeySequence.New)
        action.triggered.connect(self._window.new_schematic)

        action = menu.addAction("Clear S&ymbol")
        action.setShortcut("Ctrl+Shift+N")
        action.triggered.connect(self._window.new_symbol)

        menu.addSeparator()

        # Component browser
        action = menu.addAction("Component &browser")
        action.setShortcut("Ctrl+I")
        action.triggered.connect(self._window.place_symbol)

        menu.addSeparator()

        # Open
        action = menu.addAction("&Open...")
        action.setShortcut(QKeySequence.Open)
        action.triggered.connect(self._window.open_file)

        action = menu.addAction("Open in &new window...")
        action.setShortcut("Alt+O")
        action.triggered.connect(self._window.open_file_new_window)

        # Recent files submenu
        self._recent_files_menu = menu.addMenu("Open &recent")
        self.update_recent_files_menu()

        menu.addSeparator()

        # New tab
        action = menu.addAction("Create new &tab")
        action.setShortcut("Ctrl+T")
        action.triggered.connect(self._window.new_schematic)

        menu.addSeparator()

        # Save
        action = menu.addAction("&Save")
        action.setShortcut(QKeySequence.Save)
        action.triggered.connect(self._window.save_file)

        action = menu.addAction("Save &as...")
        action.setShortcut("Ctrl+Shift+S")
        action.triggered.connect(self._window.save_file_as)

        action = menu.addAction("&Reload")
        action.setShortcut("Alt+S")
        action.triggered.connect(self._window.reload_file)

        menu.addSeparator()

        # Export submenu
        export_menu = menu.addMenu("&Image export")

        action = export_menu.addAction("PDF/PS Export")
        action.setShortcut("*")
        # action.triggered.connect(...)

        action = export_menu.addAction("PNG Export")
        action.setShortcut("Ctrl+*")
        # action.triggered.connect(...)

        action = export_menu.addAction("SVG Export")
        action.setShortcut("Alt+*")
        # action.triggered.connect(...)

        menu.addSeparator()

        # Close/Quit
        action = menu.addAction("&Close schematic")
        action.setShortcut("Ctrl+W")
        action.triggered.connect(lambda: self._window._on_tab_close_requested(
            self._window._tab_widget.currentIndex()))

        action = menu.addAction("&Quit")
        action.setShortcut(QKeySequence.Quit)
        action.triggered.connect(self._window.close)

    def _create_edit_menu(self) -> None:
        """Create the Edit menu."""
        menu = self._menubar.addMenu("&Edit")

        action = menu.addAction("&Undo")
        action.setShortcut("U")
        action.triggered.connect(self._window.undo)

        action = menu.addAction("&Redo")
        action.setShortcut("Shift+U")
        action.triggered.connect(self._window.redo)

        menu.addSeparator()

        action = menu.addAction("&Copy")
        action.setShortcut(QKeySequence.Copy)
        action.triggered.connect(self._window.copy)

        action = menu.addAction("Cu&t")
        action.setShortcut(QKeySequence.Cut)
        action.triggered.connect(self._window.cut)

        action = menu.addAction("&Paste")
        action.setShortcut(QKeySequence.Paste)
        action.triggered.connect(self._window.paste)

        action = menu.addAction("&Delete")
        action.setShortcut(QKeySequence.Delete)
        action.triggered.connect(self._window.delete_selected)

        menu.addSeparator()

        action = menu.addAction("Select &all")
        action.setShortcut(QKeySequence.SelectAll)
        action.triggered.connect(self._window.select_all)

        action = menu.addAction("D&eselect all")
        action.setShortcut("Escape")
        action.triggered.connect(self._window.deselect_all)

        menu.addSeparator()

        action = menu.addAction("D&uplicate objects")
        action.setShortcut("C")
        action.triggered.connect(self._window.duplicate)

        action = menu.addAction("&Move objects")
        action.setShortcut("M")
        action.triggered.connect(self._window.move_selected)

        menu.addSeparator()

        action = menu.addAction("&Rotate selected")
        action.setShortcut("Shift+R")
        action.triggered.connect(self._window.rotate_selected)

        action = menu.addAction("&Horizontal flip")
        action.setShortcut("Shift+F")
        action.triggered.connect(self._window.flip_horizontal)

        action = menu.addAction("&Vertical flip")
        action.setShortcut("Shift+V")
        action.triggered.connect(self._window.flip_vertical)

        menu.addSeparator()

        action = menu.addAction("Push &schematic")
        action.setShortcut("E")
        action.triggered.connect(self._window.descend_schematic)

        action = menu.addAction("Push s&ymbol")
        action.setShortcut("I")
        action.triggered.connect(self._window.descend_symbol)

        action = menu.addAction("P&op")
        action.setShortcut("Ctrl+E")
        action.triggered.connect(self._window.go_back)

    def _create_view_menu(self) -> None:
        """Create the View menu."""
        menu = self._menubar.addMenu("&View")

        action = menu.addAction("&Redraw")
        action.setShortcut("Escape")
        action.triggered.connect(self._window.redraw)

        menu.addSeparator()

        action = menu.addAction("Zoom &Full")
        action.setShortcut("F")
        action.triggered.connect(self._window.zoom_fit)

        action = menu.addAction("Zoom &In")
        action.setShortcut("Shift+Z")
        action.triggered.connect(self._window.zoom_in)

        action = menu.addAction("Zoom &Out")
        action.setShortcut("Ctrl+Z")
        action.triggered.connect(self._window.zoom_out)

        action = menu.addAction("Zoom &box")
        action.setShortcut("Z")
        action.triggered.connect(self._window.zoom_box)

        menu.addSeparator()

        action = menu.addAction("Toggle &colorscheme")
        action.setShortcut("Shift+O")
        action.triggered.connect(self._window.toggle_color_scheme)

        menu.addSeparator()

        # Show/Hide submenu
        show_menu = menu.addMenu("Show / &Hide")

        self._grid_action = show_menu.addAction("Draw &grid")
        self._grid_action.setCheckable(True)
        self._grid_action.setChecked(True)
        self._grid_action.setShortcut("%")
        self._grid_action.triggered.connect(self._window.toggle_grid)

        self._toolbar_action = show_menu.addAction("Show &Toolbar")
        self._toolbar_action.setCheckable(True)
        self._toolbar_action.setChecked(True)
        self._toolbar_action.triggered.connect(self._toggle_toolbar)

    def _create_options_menu(self) -> None:
        """Create the Options menu."""
        menu = self._menubar.addMenu("&Options")

        # Snap settings
        self._snap_action = menu.addAction("Enable &stretch")
        self._snap_action.setCheckable(True)
        self._snap_action.setShortcut("Y")

        action = menu.addAction("Half Snap Threshold")
        action.setShortcut("G")

        action = menu.addAction("Double Snap Threshold")
        action.setShortcut("Shift+G")

        menu.addSeparator()

        # Netlist format submenu
        netlist_menu = menu.addMenu("&Netlist format")

        group = QActionGroup(self._window)

        action = netlist_menu.addAction("&SPICE netlist")
        action.setCheckable(True)
        action.setChecked(True)
        action.triggered.connect(self._window.set_netlist_type_spice)
        group.addAction(action)

        action = netlist_menu.addAction("&Verilog netlist")
        action.setCheckable(True)
        action.triggered.connect(self._window.set_netlist_type_verilog)
        group.addAction(action)

        action = netlist_menu.addAction("V&HDL netlist")
        action.setCheckable(True)
        action.triggered.connect(self._window.set_netlist_type_vhdl)
        group.addAction(action)

    def _create_properties_menu(self) -> None:
        """Create the Properties menu."""
        menu = self._menubar.addMenu("&Properties")

        action = menu.addAction("&Edit")
        action.setShortcut("Q")
        action.triggered.connect(self._window.edit_properties)

        action = menu.addAction("Edit &Header/License")
        action.setShortcut("Shift+B")
        action.triggered.connect(self._window.edit_schematic_properties)

    def _create_layers_menu(self) -> None:
        """Create the Layers menu."""
        menu = self._menubar.addMenu("&Layers")

        # Add layer selection items
        from pyxschem.graphics.layers import CADLAYERS

        for i in range(min(CADLAYERS, 22)):  # First 22 layers
            action = menu.addAction(f"Layer {i}")
            action.setData(i)
            if i < 10:
                action.setShortcut(str(i))
            action.triggered.connect(lambda checked, layer=i: self._set_layer(layer))

    def _create_tools_menu(self) -> None:
        """Create the Tools menu."""
        menu = self._menubar.addMenu("&Tools")

        action = menu.addAction("&Search")
        action.setShortcut("Ctrl+F")
        # action.triggered.connect(...)

        action = menu.addAction("&Align")
        # action.triggered.connect(...)

        action = menu.addAction("&Measure distance")
        # action.triggered.connect(...)

    def _create_symbol_menu(self) -> None:
        """Create the Symbol menu."""
        menu = self._menubar.addMenu("&Symbol")

        action = menu.addAction("Make symbol from &schematic")
        action.setShortcut("A")
        # action.triggered.connect(...)

        action = menu.addAction("&Attach labels to component")
        action.setShortcut("Shift+H")
        # action.triggered.connect(...)

    def _create_highlight_menu(self) -> None:
        """Create the Highlight menu."""
        menu = self._menubar.addMenu("&Highlight")

        action = menu.addAction("&Highlight selected nets")
        action.setShortcut("K")
        # action.triggered.connect(...)

        action = menu.addAction("&Un-highlight all")
        action.setShortcut("Shift+K")
        # action.triggered.connect(...)

    def _create_simulation_menu(self) -> None:
        """Create the Simulation menu."""
        menu = self._menubar.addMenu("S&imulation")

        action = menu.addAction("&Set netlist dir")
        # action.triggered.connect(...)

        action = menu.addAction("&Netlist")
        action.setShortcut("N")
        action.triggered.connect(self._window.generate_netlist)

        action = menu.addAction("&Simulate")
        # action.triggered.connect(...)

        action = menu.addAction("&Waves")
        # action.triggered.connect(...)

    def _create_help_menu(self) -> None:
        """Create the Help menu."""
        menu = self._menubar.addMenu("&Help")

        action = menu.addAction("&Help")
        action.setShortcut("?")
        action.triggered.connect(self._show_help)

        action = menu.addAction("Show &Keybindings")
        action.triggered.connect(self._show_keybindings)

        menu.addSeparator()

        action = menu.addAction("&About PyXSchem")
        action.triggered.connect(self._show_about)

    # -------------------------------------------------------------------------
    # Helper methods
    # -------------------------------------------------------------------------

    def update_recent_files_menu(self) -> None:
        """Update the recent files menu."""
        if not self._recent_files_menu:
            return

        self._recent_files_menu.clear()

        for file_path in self._window._recent_files:
            action = self._recent_files_menu.addAction(file_path)
            action.triggered.connect(
                lambda checked, path=file_path: self._window.open_recent_file(path)
            )

        if not self._window._recent_files:
            action = self._recent_files_menu.addAction("(No recent files)")
            action.setEnabled(False)

    def _toggle_toolbar(self) -> None:
        """Toggle toolbar visibility."""
        toolbar = self._window._toolbar_setup.toolbar
        if toolbar:
            toolbar.setVisible(not toolbar.isVisible())
            self._toolbar_action.setChecked(toolbar.isVisible())

    def _set_layer(self, layer: int) -> None:
        """Set the current drawing layer."""
        if self._window._context:
            self._window._context.rectcolor = layer
            self._window.statusBar().showMessage(f"Layer: {layer}", 2000)

    def _show_help(self) -> None:
        """Show help dialog."""
        from PySide6.QtWidgets import QMessageBox
        QMessageBox.information(
            self._window,
            "PyXSchem Help",
            "PyXSchem is a Python/PySide6 port of xschem.\n\n"
            "For more information, visit the documentation."
        )

    def _show_keybindings(self) -> None:
        """Show keybindings dialog."""
        from PySide6.QtWidgets import QMessageBox
        keybindings = """
Common Keybindings:

File:
  Ctrl+N      Clear schematic
  Ctrl+O      Open file
  Ctrl+S      Save
  Ctrl+W      Close tab
  Ctrl+Q      Quit

Edit:
  U           Undo
  Shift+U     Redo
  C           Copy/Duplicate
  M           Move
  Del         Delete
  Shift+R     Rotate
  Shift+F     Flip horizontal

View:
  F           Fit all
  Z           Zoom box
  Shift+Z     Zoom in
  Ctrl+Z      Zoom out
  %           Toggle grid

Drawing:
  W           Wire
  L           Line
  R           Rectangle
  T           Text
  Q           Edit properties

Navigation:
  E           Descend into schematic
  I           Descend into symbol
  Ctrl+E      Go back/up

Layers:
  0-9         Select layer 0-9
"""
        QMessageBox.information(
            self._window,
            "PyXSchem Keybindings",
            keybindings
        )

    def _show_about(self) -> None:
        """Show about dialog."""
        from PySide6.QtWidgets import QMessageBox
        QMessageBox.about(
            self._window,
            "About PyXSchem",
            "<h3>PyXSchem</h3>"
            "<p>Version 0.1.0</p>"
            "<p>A Python/PySide6 port of xschem schematic capture tool.</p>"
            "<p>Based on xschem by Stefan Frederik Schippers.</p>"
            "<p>Copyright 2024</p>"
        )
