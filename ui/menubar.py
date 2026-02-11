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

from typing import TYPE_CHECKING, List, Optional, Callable
from PySide6.QtCore import Qt
from PySide6.QtGui import QAction, QKeySequence, QActionGroup
from PySide6.QtWidgets import QMenu, QMenuBar, QStyle

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
        self._style = main_window.style()
        self._grid_action: Optional[QAction] = None
        self._snap_action: Optional[QAction] = None
        self._simulate_action: Optional[QAction] = None
        self._probe_action: Optional[QAction] = None
        self._waves_action: Optional[QAction] = None
        self._stop_action: Optional[QAction] = None
        self._theme_dark_action: Optional[QAction] = None
        self._theme_light_action: Optional[QAction] = None

    def _add_action(
        self,
        menu: QMenu,
        text: str,
        callback: Callable,
        shortcut: str | QKeySequence | None = None,
        icon: Optional[QStyle.StandardPixmap] = None,
        checkable: bool = False,
        checked: bool = False,
    ) -> QAction:
        """Create an action with optional icon/shortcut and connect callback."""
        if icon is None:
            action = menu.addAction(text)
        else:
            action = QAction(self._style.standardIcon(icon), text, self._window)
            menu.addAction(action)

        if shortcut is not None:
            action.setShortcut(shortcut)
        if checkable:
            action.setCheckable(True)
            action.setChecked(checked)
        action.triggered.connect(callback)
        return action

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
        self._add_action(
            menu,
            "Clear &Schematic",
            self._window.new_schematic,
            QKeySequence.New,
            QStyle.SP_FileIcon,
        )
        self._add_action(
            menu,
            "Clear S&ymbol",
            self._window.new_symbol,
            "Ctrl+Shift+N",
            QStyle.SP_FileDialogDetailedView,
        )

        menu.addSeparator()

        # Component browser
        self._add_action(
            menu,
            "Component &browser",
            self._window.place_symbol,
            "Ctrl+I",
            QStyle.SP_FileDialogContentsView,
        )

        menu.addSeparator()

        # Open
        self._add_action(
            menu,
            "&Open...",
            self._window.open_file,
            QKeySequence.Open,
            QStyle.SP_DialogOpenButton,
        )
        self._add_action(
            menu,
            "Open in &new window...",
            self._window.open_file_new_window,
            "Alt+O",
            QStyle.SP_TitleBarNormalButton,
        )

        # Recent files submenu
        self._recent_files_menu = menu.addMenu("Open &recent")
        self.update_recent_files_menu()

        menu.addSeparator()

        # New tab
        self._add_action(
            menu,
            "Create new &tab",
            self._window.new_schematic,
            "Ctrl+T",
            QStyle.SP_FileDialogNewFolder,
        )

        menu.addSeparator()

        # Save
        self._add_action(
            menu,
            "&Save",
            self._window.save_file,
            QKeySequence.Save,
            QStyle.SP_DialogSaveButton,
        )
        self._add_action(
            menu,
            "Save &as...",
            self._window.save_file_as,
            "Ctrl+Shift+S",
            QStyle.SP_DriveHDIcon,
        )
        self._add_action(
            menu,
            "&Reload",
            self._window.reload_file,
            "Alt+S",
            QStyle.SP_BrowserReload,
        )

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
        self._add_action(
            menu,
            "&Close schematic",
            lambda: self._window._on_tab_close_requested(self._window._tab_widget.currentIndex()),
            "Ctrl+W",
            QStyle.SP_DialogCloseButton,
        )
        self._add_action(
            menu,
            "&Quit",
            self._window.close,
            QKeySequence.Quit,
            QStyle.SP_TitleBarCloseButton,
        )

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

        theme_menu = menu.addMenu("&Theme")
        theme_group = QActionGroup(self._window)
        theme_group.setExclusive(True)

        self._theme_dark_action = theme_menu.addAction("&Dark")
        self._theme_dark_action.setCheckable(True)
        self._theme_dark_action.setChecked(self._window.ui_theme == "dark")
        self._theme_dark_action.triggered.connect(self._window.set_theme_dark)
        theme_group.addAction(self._theme_dark_action)

        self._theme_light_action = theme_menu.addAction("&Light")
        self._theme_light_action.setCheckable(True)
        self._theme_light_action.setChecked(self._window.ui_theme == "light")
        self._theme_light_action.triggered.connect(self._window.set_theme_light)
        theme_group.addAction(self._theme_light_action)

        menu.addSeparator()

        # Show/Hide submenu
        show_menu = menu.addMenu("Show / &Hide")

        self._grid_action = self._add_action(
            show_menu,
            "Draw &grid",
            self._window.toggle_grid,
            "%",
            QStyle.SP_DialogResetButton,
            checkable=True,
            checked=True,
        )

        panels_menu = show_menu.addMenu("&Panels")

        # Individual toolbar and sidebar visibility actions.
        quick_action = self._window._toolbar_setup.toolbar.toggleViewAction()
        quick_action.setText("Core Toolbar")
        quick_action.setIcon(self._style.standardIcon(QStyle.SP_ToolBarHorizontalExtensionButton))
        panels_menu.addAction(quick_action)

        draw_action = self._window._toolbar_setup.draw_toolbar.toggleViewAction()
        draw_action.setText("Placement Toolbar")
        draw_action.setIcon(self._style.standardIcon(QStyle.SP_FileDialogListView))
        panels_menu.addAction(draw_action)

        sim_action = self._window._toolbar_setup.sim_toolbar.toggleViewAction()
        sim_action.setText("Analysis Toolbar")
        sim_action.setIcon(self._style.standardIcon(QStyle.SP_MediaPlay))
        panels_menu.addAction(sim_action)

        if self._window.workflow_dock is not None:
            workflow_action = self._window.workflow_dock.toggleViewAction()
            workflow_action.setText("Workflow Sidebar")
            workflow_action.setIcon(self._style.standardIcon(QStyle.SP_FileDialogDetailedView))
            panels_menu.addAction(workflow_action)

        panels_menu.addSeparator()
        self._add_action(
            panels_menu,
            "Show All Panels",
            self._show_all_panels,
            icon=QStyle.SP_DialogYesButton,
        )
        self._add_action(
            panels_menu,
            "Hide All Panels",
            self._hide_all_panels,
            icon=QStyle.SP_DialogNoButton,
        )

        # Toolbar configuration menu.
        toolbar_config_menu = menu.addMenu("Toolbar &Config")

        style_menu = toolbar_config_menu.addMenu("Button &Style")
        style_group = QActionGroup(self._window)
        style_group.setExclusive(True)

        current_style = self._window._toolbar_setup.current_tool_button_style()
        style_options = [
            ("Text Under Icons", Qt.ToolButtonTextUnderIcon),
            ("Text Beside Icons", Qt.ToolButtonTextBesideIcon),
            ("Icons Only", Qt.ToolButtonIconOnly),
            ("Text Only", Qt.ToolButtonTextOnly),
        ]
        for label, style in style_options:
            action = style_menu.addAction(label)
            action.setCheckable(True)
            action.setChecked(current_style == style)
            action.triggered.connect(lambda checked, s=style: self._apply_toolbar_style(s))
            style_group.addAction(action)

        icon_menu = toolbar_config_menu.addMenu("&Icon Size")
        icon_group = QActionGroup(self._window)
        icon_group.setExclusive(True)

        current_icon_size = self._window._toolbar_setup.current_icon_size()
        for size in (16, 20, 24, 28, 32):
            action = icon_menu.addAction(f"{size}px")
            action.setCheckable(True)
            action.setChecked(current_icon_size == size)
            action.triggered.connect(lambda checked, px=size: self._apply_toolbar_icon_size(px))
            icon_group.addAction(action)

        self._add_action(
            toolbar_config_menu,
            "Reset Toolbar Defaults",
            self._reset_toolbar_config,
            icon=QStyle.SP_DialogResetButton,
        )

    def _create_options_menu(self) -> None:
        """Create the Options menu."""
        menu = self._menubar.addMenu("&Options")

        # Snap settings
        self._snap_action = menu.addAction("Enable &snap to grid")
        self._snap_action.setCheckable(True)
        self._snap_action.setChecked(self._window.snap_to_grid_enabled)
        self._snap_action.setShortcut("Y")
        self._snap_action.triggered.connect(self._window.toggle_snap_to_grid)

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

        self._add_action(
            menu,
            "&Netlist",
            self._window.generate_netlist,
            "N",
            QStyle.SP_ArrowRight,
        )

        self._simulate_action = self._add_action(
            menu,
            "&Run",
            self._window.run_simulation,
            icon=QStyle.SP_MediaPlay,
        )

        self._stop_action = self._add_action(
            menu,
            "S&top",
            self._window.stop_simulation,
            icon=QStyle.SP_MediaStop,
        )

        self._probe_action = self._add_action(
            menu,
            "&Probe",
            self._window.start_probe_mode,
            icon=QStyle.SP_DialogHelpButton,
        )

        self._waves_action = self._add_action(
            menu,
            "&Waves",
            self._window.open_waves,
            icon=QStyle.SP_MediaPlay,
        )

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

    def _show_all_panels(self) -> None:
        """Show all configurable toolbars and side workflow panel."""
        self._window._toolbar_setup.set_visibility(True, True, True)
        if self._window.workflow_dock is not None:
            self._window.workflow_dock.show()

    def _hide_all_panels(self) -> None:
        """Hide all configurable toolbars and side workflow panel."""
        self._window._toolbar_setup.set_visibility(False, False, False)
        if self._window.workflow_dock is not None:
            self._window.workflow_dock.hide()

    def _apply_toolbar_style(self, style: Qt.ToolButtonStyle) -> None:
        """Apply selected toolbar button style."""
        self._window._toolbar_setup.set_tool_button_style(style)

    def _apply_toolbar_icon_size(self, size: int) -> None:
        """Apply selected toolbar icon size."""
        self._window._toolbar_setup.set_icon_size(size)

    def _reset_toolbar_config(self) -> None:
        """Reset toolbar configuration to default style and visibility."""
        self._window._toolbar_setup.set_tool_button_style(Qt.ToolButtonTextUnderIcon)
        self._window._toolbar_setup.set_icon_size(20)
        self._show_all_panels()

    def update_grid_action(self, checked: bool) -> None:
        """Keep the View menu grid check state synced to application state."""
        if self._grid_action is not None:
            self._grid_action.setChecked(checked)

    def update_snap_action(self, checked: bool) -> None:
        """Keep the Options menu snap check state synced to application state."""
        if self._snap_action is not None:
            self._snap_action.setChecked(checked)

    def update_theme_actions(self, theme_name: str) -> None:
        """Keep the View->Theme menu check state synced to current theme."""
        if self._theme_dark_action is not None:
            self._theme_dark_action.setChecked(theme_name == "dark")
        if self._theme_light_action is not None:
            self._theme_light_action.setChecked(theme_name == "light")

    def set_simulation_actions_state(
        self,
        *,
        run_enabled: bool,
        probe_enabled: bool,
        stop_enabled: bool,
    ) -> None:
        """Enable or disable simulation actions based on app context."""
        if self._simulate_action is not None:
            self._simulate_action.setEnabled(run_enabled)
        if self._probe_action is not None:
            self._probe_action.setEnabled(probe_enabled)
        if self._stop_action is not None:
            self._stop_action.setEnabled(stop_enabled)
        if self._waves_action is not None:
            self._waves_action.setEnabled(probe_enabled)

    def _set_layer(self, layer: int) -> None:
        """Set the current drawing layer."""
        if self._window._context:
            self._window._context.rectcolor = layer
            self._window._status_setup.update_layer(layer)
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
