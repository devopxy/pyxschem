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
import logging
from PySide6.QtCore import Qt
from PySide6.QtGui import QAction, QKeySequence, QActionGroup
from PySide6.QtWidgets import QMenu, QMenuBar, QStyle
try:
    from shiboken6 import isValid as _qt_is_valid
except Exception:  # pragma: no cover - shiboken6 ships with PySide6 at runtime
    _qt_is_valid = None

if TYPE_CHECKING:
    from pyxschem.ui.main_window import MainWindow


logger = logging.getLogger(__name__)


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
        self._dynamic_menus: list[QMenu] = []
        self._grid_action: Optional[QAction] = None
        self._snap_action: Optional[QAction] = None
        self._simulate_action: Optional[QAction] = None
        self._probe_action: Optional[QAction] = None
        self._waves_action: Optional[QAction] = None
        self._stop_action: Optional[QAction] = None
        self._theme_dark_action: Optional[QAction] = None
        self._theme_light_action: Optional[QAction] = None

        menu_cfg = self._window.config_manager.section("menus")
        shortcuts = menu_cfg.get("shortcuts", {})
        self._menu_shortcuts = shortcuts if isinstance(shortcuts, dict) else {}
        reserved = menu_cfg.get("reserved_shortcuts", ["Esc", "Escape"])
        self._reserved_shortcuts = {
            str(item).strip().lower()
            for item in reserved
            if isinstance(item, str) and item.strip()
        }
        # Esc must stay reserved for global command cancellation.
        self._reserved_shortcuts.update({"esc", "escape"})

    def _add_action(
        self,
        menu: QMenu,
        text: str,
        callback: Callable,
        shortcut: str | QKeySequence | None = None,
        action_id: str | None = None,
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

        self._set_action_shortcut(action, action_id, shortcut)
        if checkable:
            action.setCheckable(True)
            action.setChecked(checked)
        action.triggered.connect(callback)
        return action

    def _set_action_shortcut(
        self,
        action: QAction,
        action_id: str | None,
        default_shortcut: str | QKeySequence | None = None,
    ) -> None:
        """Apply a shortcut from JSON override (or default) to an action."""
        shortcut = self._resolve_shortcut(action_id, default_shortcut)
        if shortcut is not None:
            action.setShortcut(shortcut)

    def _resolve_shortcut(
        self,
        action_id: str | None,
        default_shortcut: str | QKeySequence | None = None,
    ) -> str | QKeySequence | None:
        """Resolve shortcut with JSON overrides and reserved-key filtering."""
        candidate = default_shortcut
        if action_id and action_id in self._menu_shortcuts:
            candidate = self._menu_shortcuts[action_id]

        if candidate is None:
            return None
        if isinstance(candidate, str):
            candidate = candidate.strip()
            if not candidate:
                return None

        if self._is_reserved_shortcut(candidate):
            logger.warning(
                "Skipping reserved shortcut '%s' for menu action '%s'",
                candidate,
                action_id or "(unnamed)",
            )
            return None
        return candidate

    def _is_reserved_shortcut(self, shortcut: str | QKeySequence) -> bool:
        """Return True if shortcut is reserved for core command routing."""
        if isinstance(shortcut, QKeySequence):
            text = shortcut.toString(QKeySequence.PortableText)
        else:
            text = str(shortcut)

        normalized = text.strip().lower()
        if not normalized:
            return False
        if normalized in self._reserved_shortcuts:
            return True

        portable = QKeySequence(text).toString(QKeySequence.PortableText).strip().lower()
        return bool(portable and portable in self._reserved_shortcuts)

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
        self._create_vscode_menus()
        self._create_help_menu()
        self._sanitize_reserved_shortcuts()

    def _create_file_menu(self) -> None:
        """Create the File menu."""
        menu = self._menubar.addMenu("&File")

        # New (shortcut Ctrl+N is on toolbar)
        self._add_action(
            menu,
            "Clear &Schematic",
            self._window.new_schematic,
            action_id="file.clear_schematic",
            icon=QStyle.SP_FileIcon,
        )
        self._add_action(
            menu,
            "Clear S&ymbol",
            self._window.new_symbol,
            "Ctrl+Shift+N",
            "file.clear_symbol",
            QStyle.SP_FileDialogDetailedView,
        )

        menu.addSeparator()

        # Component browser (shortcut Ctrl+I is on toolbar)
        self._add_action(
            menu,
            "Component &browser",
            self._window.place_symbol,
            action_id="file.component_browser",
            icon=QStyle.SP_FileDialogContentsView,
        )

        menu.addSeparator()

        # Open (shortcut Ctrl+O is on toolbar)
        self._add_action(
            menu,
            "&Open...",
            self._window.open_file,
            action_id="file.open",
            icon=QStyle.SP_DialogOpenButton,
        )
        self._add_action(
            menu,
            "Open in &new window...",
            self._window.open_file_new_window,
            "Alt+O",
            "file.open_new_window",
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
            "file.new_tab",
            QStyle.SP_FileDialogNewFolder,
        )

        menu.addSeparator()

        # Save (shortcut Ctrl+S is on toolbar)
        self._add_action(
            menu,
            "&Save",
            self._window.save_file,
            action_id="file.save",
            icon=QStyle.SP_DialogSaveButton,
        )
        self._add_action(
            menu,
            "Save &as...",
            self._window.save_file_as,
            "Ctrl+Shift+S",
            "file.save_as",
            QStyle.SP_DriveHDIcon,
        )
        self._add_action(
            menu,
            "&Reload",
            self._window.reload_file,
            "Alt+S",
            "file.reload",
            QStyle.SP_BrowserReload,
        )

        menu.addSeparator()

        # Export submenu
        export_menu = menu.addMenu("&Image export")

        action = export_menu.addAction("PDF/PS Export")
        self._set_action_shortcut(action, "file.export_pdf_ps", "*")
        # action.triggered.connect(...)

        action = export_menu.addAction("PNG Export")
        self._set_action_shortcut(action, "file.export_png", "Ctrl+*")
        # action.triggered.connect(...)

        action = export_menu.addAction("SVG Export")
        self._set_action_shortcut(action, "file.export_svg", "Alt+*")
        # action.triggered.connect(...)

        menu.addSeparator()

        # Close/Quit
        self._add_action(
            menu,
            "&Close schematic",
            lambda: self._window._on_tab_close_requested(self._window._tab_widget.currentIndex()),
            "Ctrl+W",
            "file.close_schematic",
            QStyle.SP_DialogCloseButton,
        )
        self._add_action(
            menu,
            "&Quit",
            self._window.close,
            QKeySequence.Quit,
            "file.quit",
            QStyle.SP_TitleBarCloseButton,
        )

    def _create_edit_menu(self) -> None:
        """Create the Edit menu."""
        menu = self._menubar.addMenu("&Edit")

        action = menu.addAction("&Undo")
        self._set_action_shortcut(action, "edit.undo", "U")
        action.triggered.connect(self._window.undo)

        action = menu.addAction("&Redo")
        self._set_action_shortcut(action, "edit.redo", "Shift+U")
        action.triggered.connect(self._window.redo)

        menu.addSeparator()

        action = menu.addAction("&Copy")
        self._set_action_shortcut(action, "edit.copy")
        # Shortcut Ctrl+C is on toolbar
        action.triggered.connect(self._window.copy)

        action = menu.addAction("Cu&t")
        self._set_action_shortcut(action, "edit.cut")
        # Shortcut Ctrl+X is on toolbar
        action.triggered.connect(self._window.cut)

        action = menu.addAction("&Paste")
        self._set_action_shortcut(action, "edit.paste")
        # Shortcut Ctrl+V is on toolbar
        action.triggered.connect(self._window.paste)

        action = menu.addAction("&Delete")
        self._set_action_shortcut(action, "edit.delete")
        # Shortcut Delete is on toolbar
        action.triggered.connect(self._window.delete_selected)

        menu.addSeparator()

        action = menu.addAction("Select &all")
        self._set_action_shortcut(action, "edit.select_all", QKeySequence.SelectAll)
        action.triggered.connect(self._window.select_all)

        action = menu.addAction("D&eselect all")
        self._set_action_shortcut(action, "edit.deselect_all")
        # Escape is handled by canvas/MainWindow keyPressEvent (cancel drawing + deselect)
        action.triggered.connect(self._window.deselect_all)

        menu.addSeparator()

        action = menu.addAction("D&uplicate objects")
        self._set_action_shortcut(action, "edit.duplicate", "C")
        action.triggered.connect(self._window.duplicate)

        action = menu.addAction("&Move objects")
        self._set_action_shortcut(action, "edit.move")
        # Shortcut M is on toolbar
        action.triggered.connect(self._window.move_selected)

        menu.addSeparator()

        action = menu.addAction("&Rotate selected")
        self._set_action_shortcut(action, "edit.rotate")
        # Shortcut Shift+R is on toolbar
        action.triggered.connect(self._window.rotate_selected)

        action = menu.addAction("&Horizontal flip")
        self._set_action_shortcut(action, "edit.horizontal_flip", "Shift+F")
        action.triggered.connect(self._window.flip_horizontal)

        action = menu.addAction("&Vertical flip")
        self._set_action_shortcut(action, "edit.vertical_flip", "Shift+V")
        action.triggered.connect(self._window.flip_vertical)

        menu.addSeparator()

        action = menu.addAction("Push &schematic")
        self._set_action_shortcut(action, "edit.push_schematic", "E")
        action.triggered.connect(self._window.descend_schematic)

        action = menu.addAction("Push s&ymbol")
        self._set_action_shortcut(action, "edit.push_symbol", "I")
        action.triggered.connect(self._window.descend_symbol)

        action = menu.addAction("P&op")
        self._set_action_shortcut(action, "edit.pop", "Ctrl+E")
        action.triggered.connect(self._window.go_back)

    def _create_view_menu(self) -> None:
        """Create the View menu."""
        menu = self._menubar.addMenu("&View")

        action = menu.addAction("&Redraw")
        self._set_action_shortcut(action, "view.redraw")
        # Escape is handled by canvas/MainWindow keyPressEvent (cancel drawing + deselect + redraw)
        action.triggered.connect(self._window.redraw)

        menu.addSeparator()

        action = menu.addAction("Zoom &Full")
        self._set_action_shortcut(action, "view.zoom_full")
        # Shortcut F is on toolbar
        action.triggered.connect(self._window.zoom_fit)

        action = menu.addAction("Zoom &In")
        self._set_action_shortcut(action, "view.zoom_in", "Shift+Z")
        action.triggered.connect(self._window.zoom_in)

        action = menu.addAction("Zoom &Out")
        self._set_action_shortcut(action, "view.zoom_out")
        # Was Ctrl+Z which conflicts with Undo (toolbar). Use canvas +/- instead.
        action.triggered.connect(self._window.zoom_out)

        action = menu.addAction("Zoom &box")
        self._set_action_shortcut(action, "view.zoom_box", "Z")
        action.triggered.connect(self._window.zoom_box)

        menu.addSeparator()

        theme_menu = menu.addMenu("&Theme")
        theme_group = QActionGroup(self._window)
        theme_group.setExclusive(True)

        self._theme_dark_action = theme_menu.addAction("&Dark")
        self._theme_dark_action.setCheckable(True)
        self._theme_dark_action.setChecked(self._window.ui_theme == "dark")
        self._set_action_shortcut(self._theme_dark_action, "view.theme_dark")
        self._theme_dark_action.triggered.connect(self._window.set_theme_dark)
        theme_group.addAction(self._theme_dark_action)

        self._theme_light_action = theme_menu.addAction("&Light")
        self._theme_light_action.setCheckable(True)
        self._theme_light_action.setChecked(self._window.ui_theme == "light")
        self._set_action_shortcut(self._theme_light_action, "view.theme_light")
        self._theme_light_action.triggered.connect(self._window.set_theme_light)
        theme_group.addAction(self._theme_light_action)

        menu.addSeparator()

        # Show/Hide submenu
        show_menu = menu.addMenu("Show / &Hide")

        self._grid_action = self._add_action(
            show_menu,
            "Draw &grid",
            self._window.toggle_grid,
            # Shortcut % is on toolbar
            action_id="view.draw_grid",
            icon=QStyle.SP_DialogResetButton,
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

        if self._window.terminal_console_dock is not None:
            terminal_action = self._window.terminal_console_dock.toggleViewAction()
            terminal_action.setText("Terminal / Debug Panel")
            terminal_action.setIcon(self._style.standardIcon(QStyle.SP_ComputerIcon))
            panels_menu.addAction(terminal_action)

        panels_menu.addSeparator()
        self._add_action(
            panels_menu,
            "Show All Panels",
            self._show_all_panels,
            action_id="view.show_all_panels",
            icon=QStyle.SP_DialogYesButton,
        )
        self._add_action(
            panels_menu,
            "Hide All Panels",
            self._hide_all_panels,
            action_id="view.hide_all_panels",
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
            action_id="view.reset_toolbar_defaults",
            icon=QStyle.SP_DialogResetButton,
        )

    def _create_options_menu(self) -> None:
        """Create the Options menu."""
        menu = self._menubar.addMenu("&Options")

        # Snap settings
        self._snap_action = menu.addAction("Enable &snap to grid")
        self._snap_action.setCheckable(True)
        self._snap_action.setChecked(self._window.snap_to_grid_enabled)
        self._set_action_shortcut(self._snap_action, "options.snap_to_grid")
        # Shortcut Y is on toolbar
        self._snap_action.triggered.connect(self._window.toggle_snap_to_grid)

        action = menu.addAction("Half Snap Threshold")
        self._set_action_shortcut(action, "options.half_snap_threshold")
        # G conflicts with toolbar ground placement

        action = menu.addAction("Double Snap Threshold")
        self._set_action_shortcut(action, "options.double_snap_threshold", "Shift+G")

        menu.addSeparator()

        # Netlist format submenu
        netlist_menu = menu.addMenu("&Netlist format")

        group = QActionGroup(self._window)

        action = netlist_menu.addAction("&SPICE netlist")
        action.setCheckable(True)
        action.setChecked(True)
        self._set_action_shortcut(action, "options.netlist_spice")
        action.triggered.connect(self._window.set_netlist_type_spice)
        group.addAction(action)

        action = netlist_menu.addAction("&Verilog netlist")
        action.setCheckable(True)
        self._set_action_shortcut(action, "options.netlist_verilog")
        action.triggered.connect(self._window.set_netlist_type_verilog)
        group.addAction(action)

        action = netlist_menu.addAction("V&HDL netlist")
        action.setCheckable(True)
        self._set_action_shortcut(action, "options.netlist_vhdl")
        action.triggered.connect(self._window.set_netlist_type_vhdl)
        group.addAction(action)

    def _create_properties_menu(self) -> None:
        """Create the Properties menu."""
        menu = self._menubar.addMenu("&Properties")

        action = menu.addAction("&Edit")
        self._set_action_shortcut(action, "properties.edit", "Q")
        action.triggered.connect(self._window.edit_properties)

        action = menu.addAction("Edit &Header/License")
        self._set_action_shortcut(action, "properties.edit_header", "Shift+B")
        action.triggered.connect(self._window.edit_schematic_properties)

    def _create_layers_menu(self) -> None:
        """Create the Layers menu."""
        menu = self._menubar.addMenu("&Layers")

        # Add layer selection items
        from pyxschem.graphics.layers import CADLAYERS

        for i in range(min(CADLAYERS, 22)):  # First 22 layers
            action = menu.addAction(f"Layer {i}")
            action.setData(i)
            self._set_action_shortcut(action, f"layers.layer_{i}", str(i) if i < 10 else None)
            action.triggered.connect(lambda checked, layer=i: self._set_layer(layer))

    def _create_tools_menu(self) -> None:
        """Create the Tools menu."""
        menu = self._menubar.addMenu("&Tools")

        action = menu.addAction("&Search")
        self._set_action_shortcut(action, "tools.search", "Ctrl+F")
        action.triggered.connect(self._window.show_search_dialog)

        action = menu.addAction("&Align")
        self._set_action_shortcut(action, "tools.align")
        # action.triggered.connect(...)

        action = menu.addAction("&Measure distance")
        self._set_action_shortcut(action, "tools.measure_distance")
        # action.triggered.connect(...)

    def _create_symbol_menu(self) -> None:
        """Create the Symbol menu."""
        menu = self._menubar.addMenu("&Symbol")

        action = menu.addAction("Make symbol from &schematic")
        self._set_action_shortcut(action, "symbol.make_from_schematic")
        # A conflicts with toolbar net_label placement
        # action.triggered.connect(...)

        action = menu.addAction("&Attach labels to component")
        self._set_action_shortcut(action, "symbol.attach_labels", "Shift+H")
        # action.triggered.connect(...)

    def _create_highlight_menu(self) -> None:
        """Create the Highlight menu."""
        menu = self._menubar.addMenu("&Highlight")

        action = menu.addAction("&Highlight selected nets")
        self._set_action_shortcut(action, "highlight.highlight_selected", "K")
        action.triggered.connect(self._window.highlight_selected_nets)

        action = menu.addAction("&Un-highlight all")
        self._set_action_shortcut(action, "highlight.unhighlight_all", "Shift+K")
        action.triggered.connect(self._window.unhighlight_all)

    def _create_simulation_menu(self) -> None:
        """Create the Simulation menu."""
        menu = self._menubar.addMenu("S&imulation")

        action = menu.addAction("&Set netlist dir")
        self._set_action_shortcut(action, "simulation.set_netlist_dir")
        # action.triggered.connect(...)

        self._add_action(
            menu,
            "&Netlist",
            self._window.generate_netlist,
            action_id="simulation.netlist",
            # Shortcut N is on toolbar
            icon=QStyle.SP_ArrowRight,
        )

        self._simulate_action = self._add_action(
            menu,
            "&Run",
            self._window.run_simulation,
            action_id="simulation.run",
            icon=QStyle.SP_MediaPlay,
        )

        self._stop_action = self._add_action(
            menu,
            "S&top",
            self._window.stop_simulation,
            action_id="simulation.stop",
            icon=QStyle.SP_MediaStop,
        )

        self._probe_action = self._add_action(
            menu,
            "&Probe",
            self._window.start_probe_mode,
            action_id="simulation.probe",
            icon=QStyle.SP_DialogHelpButton,
        )

        self._waves_action = self._add_action(
            menu,
            "&Waves",
            self._window.open_waves,
            action_id="simulation.waves",
            icon=QStyle.SP_MediaPlay,
        )

    def _create_vscode_menus(self) -> None:
        """Create JSON-driven VS Code-like additional menus."""
        config = self._window.config_manager.section("menus")
        if not config.get("enable_vscode_menus", True):
            return

        menu_defs = config.get("vscode_like_menus", [])
        if not isinstance(menu_defs, list):
            return

        for menu_def in menu_defs:
            if not isinstance(menu_def, dict):
                continue
            title = menu_def.get("title")
            items = menu_def.get("items")
            if not isinstance(title, str) or not title.strip() or not isinstance(items, list):
                continue

            menu = self._menubar.addMenu(title)
            self._dynamic_menus.append(menu)

            for item in items:
                if not isinstance(item, dict):
                    continue
                if item.get("separator"):
                    menu.addSeparator()
                    continue

                label = item.get("label")
                callback_name = item.get("callback")
                if not isinstance(label, str) or not label.strip():
                    continue

                action = menu.addAction(label)
                action_id = item.get("id") if isinstance(item.get("id"), str) else None
                shortcut = item.get("shortcut")
                resolved = self._resolve_shortcut(action_id, shortcut)
                if resolved is not None:
                    action.setShortcut(resolved)

                callback = self._resolve_window_callback(callback_name)
                if callback is None:
                    action.setEnabled(False)
                    continue
                action.triggered.connect(callback)

    def _sanitize_reserved_shortcuts(self) -> None:
        """Remove reserved shortcuts from all menu actions as a final safety pass."""
        for top_action in self._menubar.actions():
            menu = top_action.menu()
            if menu is None:
                continue
            for action in self._iter_menu_actions(menu):
                if not self._is_action_valid(action):
                    continue
                shortcut = action.shortcut()
                if shortcut.isEmpty():
                    continue
                if self._is_reserved_shortcut(shortcut):
                    logger.warning(
                        "Clearing reserved shortcut '%s' on menu action '%s'",
                        shortcut.toString(QKeySequence.PortableText),
                        action.text(),
                    )
                    action.setShortcut(QKeySequence())

    def _iter_menu_actions(self, menu: QMenu):
        """Yield all actions under a menu recursively."""
        for action in menu.actions():
            if not self._is_action_valid(action):
                continue
            yield action
            try:
                child = action.menu()
            except RuntimeError:
                continue
            if child is not None:
                yield from self._iter_menu_actions(child)

    @staticmethod
    def _is_action_valid(action: Optional[QAction]) -> bool:
        """Return True when a QAction wrapper still points to a live C++ object."""
        if action is None:
            return False
        try:
            if _qt_is_valid is not None and not _qt_is_valid(action):
                return False
            # Touch a cheap property to surface invalid wrapped C++ instances.
            action.isEnabled()
            return True
        except RuntimeError:
            return False

    def _resolve_window_callback(self, callback_name) -> Optional[Callable]:
        """Resolve callback name from MainWindow; return None if unavailable."""
        if not isinstance(callback_name, str) or not callback_name:
            return None
        callback = getattr(self._window, callback_name, None)
        if callable(callback):
            return callback
        return None

    def _create_help_menu(self) -> None:
        """Create the Help menu."""
        menu = self._menubar.addMenu("&Help")

        action = menu.addAction("&Help")
        self._set_action_shortcut(action, "help.help", "?")
        action.triggered.connect(self._show_help)

        action = menu.addAction("Show &Keybindings")
        self._set_action_shortcut(action, "help.show_keybindings")
        action.triggered.connect(self._show_keybindings)

        menu.addSeparator()

        action = menu.addAction("&About PyXSchem")
        self._set_action_shortcut(action, "help.about")
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
        if self._window.terminal_console_dock is not None:
            self._window.terminal_console_dock.show()

    def _hide_all_panels(self) -> None:
        """Hide all configurable toolbars and side workflow panel."""
        self._window._toolbar_setup.set_visibility(False, False, False)
        if self._window.workflow_dock is not None:
            self._window.workflow_dock.hide()
        if self._window.terminal_console_dock is not None:
            self._window.terminal_console_dock.hide()

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
        if not self._is_action_valid(self._grid_action):
            self._grid_action = None
            return
        self._grid_action.setChecked(checked)

    def update_snap_action(self, checked: bool) -> None:
        """Keep the Options menu snap check state synced to application state."""
        if not self._is_action_valid(self._snap_action):
            self._snap_action = None
            return
        self._snap_action.setChecked(checked)

    def update_theme_actions(self, theme_name: str) -> None:
        """Keep the View->Theme menu check state synced to current theme."""
        if self._is_action_valid(self._theme_dark_action):
            self._theme_dark_action.setChecked(theme_name == "dark")
        else:
            self._theme_dark_action = None
        if self._is_action_valid(self._theme_light_action):
            self._theme_light_action.setChecked(theme_name == "light")
        else:
            self._theme_light_action = None

    def set_simulation_actions_state(
        self,
        *,
        run_enabled: bool,
        probe_enabled: bool,
        stop_enabled: bool,
    ) -> None:
        """Enable or disable simulation actions based on app context."""
        if self._is_action_valid(self._simulate_action):
            self._simulate_action.setEnabled(run_enabled)
        else:
            self._simulate_action = None
        if self._is_action_valid(self._probe_action):
            self._probe_action.setEnabled(probe_enabled)
        else:
            self._probe_action = None
        if self._is_action_valid(self._stop_action):
            self._stop_action.setEnabled(stop_enabled)
        else:
            self._stop_action = None
        if self._is_action_valid(self._waves_action):
            self._waves_action.setEnabled(probe_enabled)
        else:
            self._waves_action = None

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
