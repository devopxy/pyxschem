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
import logging

from PySide6.QtCore import Qt, Signal, Slot, QByteArray
from PySide6.QtWidgets import (
    QMainWindow,
    QWidget,
    QVBoxLayout,
    QFileDialog,
    QMessageBox,
    QDockWidget,
    QTabWidget,
    QPushButton,
    QStyle,
    QMenu,
)
from PySide6.QtGui import QCloseEvent, QAction

from pyxschem.automation import ScriptAutomationRunner
from pyxschem.config import JsonConfigManager
from pyxschem.core.context import SchematicContext, UIState, NetlistType
from pyxschem.graphics import SchematicCanvas, SchematicRenderer, LayerManager
from pyxschem.io import read_schematic, write_schematic
from pyxschem.plugins import PluginManager
from pyxschem.ui.menubar import MenuBarSetup
from pyxschem.ui.toolbar import ToolBarSetup
from pyxschem.ui.statusbar import StatusBarSetup
from pyxschem.ui.theme import apply_editor_theme, is_dark_theme
from pyxschem.ui.widgets import TerminalConsoleDock
from pyxschem.ui.edit_controller import EditController
from pyxschem.ui.drawing_controller import DrawingController


logger = logging.getLogger(__name__)


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

    def __init__(
        self,
        parent: Optional[QWidget] = None,
        config_manager: Optional[JsonConfigManager] = None,
    ):
        super().__init__(parent)

        self.setWindowTitle("PyXSchem")
        self.setMinimumSize(1024, 768)

        # Application state
        self._context: Optional[SchematicContext] = None
        self._recent_files: List[str] = []
        self._config_manager = config_manager or JsonConfigManager()

        # Plugin/UI extension state
        self._plugin_menus: dict[str, QMenu] = {}
        self._plugin_menu_actions: list[QAction] = []

        # UI mode flags
        self._ui_theme = "dark"
        self._dark_scheme = True
        self._show_grid = True
        self._snap_to_grid = True
        self._netlist_type = NetlistType.SPICE
        self._current_tool_name = "Select"
        self._simulation_running = False
        self._has_wave_results = False
        self._sim_profile_exists = False

        # Service subsystems
        self._plugin_manager = PluginManager(self, self._config_manager)
        self._automation_runner = ScriptAutomationRunner(self)

        # Initialize components
        self._setup_layer_manager()
        self._setup_central_widget()
        self._setup_toolbar()
        self._setup_dock_widgets()
        self._setup_menu_bar()
        self._setup_status_bar()

        # Load settings
        self._load_settings()

        # Connect signals
        self._connect_signals()

        # Apply UI styling after widgets are created.
        self._apply_modern_theme()

        # Load extension plugins after the full UI surface is available.
        self._plugin_manager.load_plugins()

        # Create new empty schematic
        self.new_schematic()
        self._sync_status_indicators()
        self._refresh_simulation_action_states()
        logger.info(
            "MainWindow initialized (theme=%s, dark_scheme=%s, show_grid=%s, snap_to_grid=%s)",
            self._ui_theme,
            self._dark_scheme,
            self._show_grid,
            self._snap_to_grid,
        )

    def _setup_layer_manager(self) -> None:
        """Initialize the layer manager."""
        self._layer_manager = LayerManager(dark_scheme=self._dark_scheme)

    def _setup_central_widget(self) -> None:
        """Set up the central widget with tabbed schematic views."""
        self._central_container = QWidget()
        central_layout = QVBoxLayout(self._central_container)
        central_layout.setContentsMargins(8, 6, 8, 8)
        central_layout.setSpacing(6)

        # Tab widget for multiple schematics
        self._tab_widget = QTabWidget()
        self._tab_widget.setTabsClosable(True)
        self._tab_widget.setMovable(True)
        self._tab_widget.setDocumentMode(True)
        self._tab_widget.tabCloseRequested.connect(self._on_tab_close_requested)
        self._tab_widget.currentChanged.connect(self._on_tab_changed)
        central_layout.addWidget(self._tab_widget, 1)

        self.setCentralWidget(self._central_container)

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
        self._create_workflow_dock()
        self._create_terminal_console_dock()

    def _create_workflow_dock(self) -> None:
        """Create a compact IC workflow palette."""
        dock = QDockWidget("Workflow", self)
        dock.setObjectName("workflow_dock")
        dock.setAllowedAreas(Qt.LeftDockWidgetArea | Qt.RightDockWidgetArea)
        dock.setFeatures(
            QDockWidget.DockWidgetMovable
            | QDockWidget.DockWidgetFloatable
            | QDockWidget.DockWidgetClosable
        )
        dock.setMinimumWidth(184)

        panel = QWidget()
        panel.setObjectName("workflow_panel")
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(8)

        self._add_workflow_button(
            layout,
            "Place Symbol",
            self.place_symbol,
            QStyle.SP_FileDialogDetailedView,
        )
        self._add_workflow_button(
            layout,
            "Wire Route",
            self.start_wire,
            QStyle.SP_ArrowRight,
        )
        self._add_workflow_button(
            layout,
            "Line / Annotation",
            self.start_line,
            QStyle.SP_FileDialogListView,
        )
        self._add_workflow_button(
            layout,
            "Text Label",
            self.start_text,
            QStyle.SP_FileDialogContentsView,
        )
        self._add_workflow_button(
            layout,
            "Edit Properties",
            self.edit_properties,
            QStyle.SP_FileDialogInfoView,
        )
        self._add_workflow_button(
            layout,
            "Generate Netlist",
            self.generate_netlist,
            QStyle.SP_ArrowRight,
        )
        self._add_workflow_button(
            layout,
            "Run Simulation",
            self.run_simulation,
            QStyle.SP_MediaPlay,
        )
        self._add_workflow_button(
            layout,
            "Open Waves",
            self.open_waves,
            QStyle.SP_MediaPlay,
        )
        layout.addStretch(1)

        dock.setWidget(panel)
        self.addDockWidget(Qt.LeftDockWidgetArea, dock)
        self._workflow_dock = dock
        logger.debug("Workflow dock initialized")

    def _create_terminal_console_dock(self) -> None:
        """Create integrated terminal and debug console dock."""
        dock = TerminalConsoleDock(self)
        dock.attach_log_handler()
        self.addDockWidget(Qt.BottomDockWidgetArea, dock)
        self._terminal_console_dock = dock
        logger.debug("Terminal/debug dock initialized")

    def _add_workflow_button(
        self,
        layout: QVBoxLayout,
        text: str,
        slot,
        standard_icon: QStyle.StandardPixmap,
    ) -> None:
        """Add a styled workflow button to the side panel."""
        button = QPushButton(text)
        button.setObjectName("workflow_btn")
        button.setIcon(self.style().standardIcon(standard_icon))
        button.setCursor(Qt.PointingHandCursor)
        button.clicked.connect(slot)
        layout.addWidget(button)

    def _apply_modern_theme(self) -> None:
        """Apply selected visual styling and synchronize canvas scheme."""
        self._ui_theme = apply_editor_theme(self, self._ui_theme)
        self._dark_scheme = is_dark_theme(self._ui_theme)
        self._layer_manager.dark_scheme = self._dark_scheme
        self._apply_canvas_scheme(self._dark_scheme)
        logger.debug("Theme applied: %s", self._ui_theme)

    def _connect_signals(self) -> None:
        """Connect internal signals."""
        logger.debug("Internal signal wiring placeholder invoked")
        pass

    def _apply_canvas_scheme(self, dark_scheme: bool) -> None:
        """Apply dark/light scheme to all open canvases."""
        self._layer_manager.dark_scheme = dark_scheme
        for i in range(self._tab_widget.count()):
            canvas = self._tab_widget.widget(i)
            if isinstance(canvas, SchematicCanvas):
                canvas.set_dark_scheme(dark_scheme)
                if hasattr(canvas, "_renderer"):
                    canvas._renderer.render()

    def _load_settings(self) -> None:
        """Load application settings from JSON configuration files."""
        geometry_b64 = self._config_manager.get("ui", "window.geometry", "")
        if isinstance(geometry_b64, str) and geometry_b64:
            try:
                self.restoreGeometry(QByteArray.fromBase64(geometry_b64.encode("ascii")))
            except Exception:
                logger.exception("Failed to restore window geometry from JSON config")

        state_b64 = self._config_manager.get("ui", "window.state", "")
        if isinstance(state_b64, str) and state_b64:
            try:
                self.restoreState(QByteArray.fromBase64(state_b64.encode("ascii")))
            except Exception:
                logger.exception("Failed to restore window state from JSON config")

        recent_files = self._config_manager.get("ui", "recent_files", [])
        if isinstance(recent_files, list):
            self._recent_files = [str(path) for path in recent_files if isinstance(path, str)]
        elif isinstance(recent_files, str) and recent_files:
            self._recent_files = [recent_files]
        else:
            self._recent_files = []

        theme_raw = self._config_manager.get("ui", "theme", "dark")
        self._ui_theme = str(theme_raw or "dark")
        self._dark_scheme = is_dark_theme(self._ui_theme)
        self._layer_manager.dark_scheme = self._dark_scheme

        self._show_grid = bool(self._config_manager.get("ui", "show_grid", True))
        self._snap_to_grid = bool(self._config_manager.get("ui", "snap_to_grid", True))

        if hasattr(self, "_toolbar_setup"):
            self._toolbar_setup.update_grid_button(self._show_grid)
            self._toolbar_setup.update_snap_button(self._snap_to_grid)

            default_style = Qt.ToolButtonTextUnderIcon
            style_raw = self._config_manager.get("ui", "toolbar.style", "ToolButtonTextUnderIcon")
            resolved_style = default_style
            try:
                if isinstance(style_raw, int):
                    resolved_style = Qt.ToolButtonStyle(int(style_raw))
                elif isinstance(style_raw, str) and style_raw.isdigit():
                    resolved_style = Qt.ToolButtonStyle(int(style_raw))
                elif isinstance(style_raw, str):
                    enum_candidate = getattr(Qt.ToolButtonStyle, style_raw, None)
                    if enum_candidate is not None:
                        resolved_style = enum_candidate
            except (TypeError, ValueError):
                resolved_style = default_style

            icon_size = int(self._config_manager.get("ui", "toolbar.icon_size", 20))
            self._toolbar_setup.set_tool_button_style(resolved_style)
            self._toolbar_setup.set_icon_size(icon_size)

            self._toolbar_setup.set_visibility(
                quick=bool(self._config_manager.get("ui", "toolbar.quick_visible", True)),
                draw=bool(self._config_manager.get("ui", "toolbar.draw_visible", True)),
                sim=bool(self._config_manager.get("ui", "toolbar.sim_visible", True)),
            )

        if hasattr(self, "_menu_setup"):
            self._menu_setup.update_grid_action(self._show_grid)
            self._menu_setup.update_snap_action(self._snap_to_grid)
            self._menu_setup.update_theme_actions(self._ui_theme)

        if hasattr(self, "_workflow_dock"):
            self._workflow_dock.setVisible(
                bool(self._config_manager.get("ui", "dock.workflow_visible", True))
            )
        if hasattr(self, "_terminal_console_dock"):
            self._terminal_console_dock.setVisible(
                bool(self._config_manager.get("ui", "dock.terminal_visible", True))
            )

        self._sync_status_indicators()
        logger.info(
            "JSON config loaded (recent_files=%d, theme=%s, dark_scheme=%s, show_grid=%s, snap_to_grid=%s)",
            len(self._recent_files),
            self._ui_theme,
            self._dark_scheme,
            self._show_grid,
            self._snap_to_grid,
        )

    def _save_settings(self) -> None:
        """Save application settings to JSON configuration files."""
        geometry_b64 = bytes(self.saveGeometry().toBase64()).decode("ascii")
        state_b64 = bytes(self.saveState().toBase64()).decode("ascii")

        self._config_manager.set("ui", "window.geometry", geometry_b64)
        self._config_manager.set("ui", "window.state", state_b64)
        self._config_manager.set("ui", "recent_files", self._recent_files[:self.MAX_RECENT_FILES])
        self._config_manager.set("ui", "theme", self._ui_theme)
        self._config_manager.set("ui", "show_grid", self._show_grid)
        self._config_manager.set("ui", "snap_to_grid", self._snap_to_grid)

        if hasattr(self, "_toolbar_setup"):
            style_enum = self._toolbar_setup.current_tool_button_style()
            style_name = getattr(style_enum, "name", "")
            style_value = style_name or str(getattr(style_enum, "value", style_enum))
            self._config_manager.set("ui", "toolbar.style", style_value)
            self._config_manager.set("ui", "toolbar.icon_size", self._toolbar_setup.current_icon_size())

            visibility = self._toolbar_setup.visibility_map()
            self._config_manager.set("ui", "toolbar.quick_visible", visibility["quick"])
            self._config_manager.set("ui", "toolbar.draw_visible", visibility["draw"])
            self._config_manager.set("ui", "toolbar.sim_visible", visibility["sim"])

        if hasattr(self, "_workflow_dock"):
            self._config_manager.set("ui", "dock.workflow_visible", self._workflow_dock.isVisible())
        if hasattr(self, "_terminal_console_dock"):
            self._config_manager.set(
                "ui",
                "dock.terminal_visible",
                self._terminal_console_dock.isVisible(),
            )

        self._config_manager.save_all()
        logger.info(
            "JSON config saved (recent_files=%d, theme=%s, dark_scheme=%s, show_grid=%s, snap_to_grid=%s)",
            len(self._recent_files),
            self._ui_theme,
            self._dark_scheme,
            self._show_grid,
            self._snap_to_grid,
        )

    @Slot()
    def run_simulation(self) -> None:
        """Trigger simulation run (placeholder until backend integration)."""
        if not self._sim_profile_exists:
            self.statusBar().showMessage("Simulation profile not found in schematic properties", 2600)
            logger.warning("Simulation run blocked: no simulation profile")
            return

        self._simulation_running = True
        self._status_setup.update_mode(self._netlist_mode_name())
        self._status_setup.update_simulation("Running")
        self._refresh_simulation_action_states()
        self.statusBar().showMessage("Simulation started (placeholder backend)", 1800)
        logger.info("Simulation run started")

        # Backend integration is pending; mark placeholder completion.
        self._simulation_running = False
        self._has_wave_results = True
        self._status_setup.update_simulation("Results")
        self._refresh_simulation_action_states()
        self.statusBar().showMessage("Simulation completed (placeholder), probe enabled", 2800)
        logger.info("Simulation run completed (placeholder)")

    @Slot()
    def stop_simulation(self) -> None:
        """Stop a running simulation session."""
        if not self._simulation_running:
            self.statusBar().showMessage("No active simulation to stop", 1800)
            logger.info("Stop simulation requested with no active run")
            return

        self._simulation_running = False
        self._status_setup.update_simulation("Stopped")
        self._refresh_simulation_action_states()
        self.statusBar().showMessage("Simulation stopped", 1800)
        logger.info("Simulation stopped by user")

    @Slot()
    def open_waves(self) -> None:
        """Open waveform viewer (placeholder until backend integration)."""
        if not self._has_wave_results:
            self.statusBar().showMessage("No simulation results loaded", 2200)
            logger.warning("Open waves requested without results")
            return

        self.statusBar().showMessage("Waveform viewer not yet implemented", 2400)
        self._status_setup.update_mode(self._netlist_mode_name())
        logger.warning("Open waves requested but not implemented")

    def _set_active_tool(self, tool_name: str, toolbar_key: str | None = None) -> None:
        """Update active tool labels and sticky toolbar highlight."""
        self._current_tool_name = tool_name
        self._status_setup.update_tool(tool_name)
        if toolbar_key:
            self._toolbar_setup.set_active_tool(toolbar_key)
        else:
            self._toolbar_setup.clear_active_tool()

    def _clear_active_tool(self) -> None:
        """Reset active tool indicators to the default pointer/select mode."""
        self._current_tool_name = "Select"
        self._status_setup.update_tool(self._current_tool_name)
        self._toolbar_setup.clear_active_tool()

    def _has_simulation_profile(self) -> bool:
        """Detect if the active schematic contains simulation directives."""
        if self._context is None:
            return False

        blobs = [
            self._context.schprop or "",
            self._context.verilog_prop or "",
            self._context.vhdl_prop or "",
            self._context.spectre_prop or "",
        ]
        text = "\n".join(blobs).lower()
        directives = (".tran", ".ac", ".dc", ".op", ".noise", ".tf", ".pz")
        return any(token in text for token in directives)

    def _refresh_simulation_action_states(self) -> None:
        """Refresh run/probe action availability from current context state."""
        self._sim_profile_exists = self._has_simulation_profile()
        run_enabled = self._sim_profile_exists and not self._simulation_running
        probe_enabled = self._has_wave_results and not self._simulation_running
        stop_enabled = self._simulation_running

        if hasattr(self, "_toolbar_setup"):
            self._toolbar_setup.set_simulation_action_state(
                run_enabled=run_enabled,
                probe_enabled=probe_enabled,
                stop_enabled=stop_enabled,
            )
        if hasattr(self, "_menu_setup"):
            self._menu_setup.set_simulation_actions_state(
                run_enabled=run_enabled,
                probe_enabled=probe_enabled,
                stop_enabled=stop_enabled,
            )

        if self._simulation_running:
            sim_state = "Running"
        elif self._has_wave_results:
            sim_state = "Results"
        elif self._sim_profile_exists:
            sim_state = "Ready"
        else:
            sim_state = "No Profile"
        self._status_setup.update_simulation(sim_state)

    def _sync_status_indicators(self) -> None:
        """Sync status bar and menu/toolbar toggles with current state flags."""
        self._status_setup.update_grid(self._show_grid)
        self._status_setup.update_snap(self._snap_to_grid)
        self._status_setup.update_tool(self._current_tool_name)
        self._status_setup.update_mode(self._netlist_mode_name())
        if hasattr(self, "_menu_setup"):
            self._menu_setup.update_grid_action(self._show_grid)
            self._menu_setup.update_snap_action(self._snap_to_grid)
            self._menu_setup.update_theme_actions(self._ui_theme)
        if hasattr(self, "_toolbar_setup"):
            self._toolbar_setup.update_grid_button(self._show_grid)
            self._toolbar_setup.update_snap_button(self._snap_to_grid)

    def _netlist_mode_name(self) -> str:
        """Return display label for the selected netlist format."""
        if self._netlist_type == NetlistType.VERILOG:
            return "Verilog"
        if self._netlist_type == NetlistType.VHDL:
            return "VHDL"
        return "SPICE"

    def set_ui_theme(self, theme_name: str) -> None:
        """Apply a named UI theme and synchronize canvas colors."""
        self._ui_theme = theme_name
        self._apply_modern_theme()
        self._sync_status_indicators()
        logger.info("UI theme changed to %s", self._ui_theme)

    @Slot()
    def set_theme_dark(self) -> None:
        """Apply the dark editor theme."""
        self.set_ui_theme("dark")

    @Slot()
    def set_theme_light(self) -> None:
        """Apply the light editor theme."""
        self.set_ui_theme("light")

    @Slot()
    def open_simulation_settings(self) -> None:
        """Open simulation settings dialog (placeholder)."""
        self.statusBar().showMessage("Simulation settings dialog not yet implemented", 2400)
        logger.warning("Simulation settings requested but not implemented")

    @Slot()
    def run_erc_drc(self) -> None:
        """Run ERC/DRC checks (placeholder)."""
        self.statusBar().showMessage("ERC/DRC checks not yet implemented", 2400)
        logger.warning("ERC/DRC requested but not implemented")

    @Slot()
    def measure_distance(self) -> None:
        """Measure distance tool (placeholder)."""
        self.statusBar().showMessage("Distance measurement tool not yet implemented", 2400)
        logger.warning("Measure distance requested but not implemented")

    @Slot()
    def view_generated_netlist(self) -> None:
        """Open generated netlist view (placeholder)."""
        self.statusBar().showMessage("Generated netlist view not yet implemented", 2400)
        logger.warning("View netlist requested but not implemented")

    @Slot()
    def open_documentation(self) -> None:
        """Open documentation entry point."""
        QMessageBox.information(
            self,
            "Documentation",
            "Documentation integration is not wired yet.\nUse README.md for current usage notes.",
        )
        logger.info("Documentation dialog shown")

    @Slot()
    def show_about_dialog(self) -> None:
        """Show application about dialog."""
        QMessageBox.about(
            self,
            "About PyXSchem",
            "<h3>PyXSchem</h3>"
            "<p>Modern schematic editor interface and simulator shell.</p>",
        )
        logger.info("About dialog shown")

    @Slot()
    def export_design(self) -> None:
        """Export command placeholder for netlist/image transfers."""
        self.statusBar().showMessage("Export pipeline not yet implemented", 2400)
        logger.warning("Export requested but not implemented")

    @Slot()
    def toggle_terminal_panel(self) -> None:
        """Show or hide the integrated terminal/debug dock."""
        dock = self.terminal_console_dock
        if dock is None:
            return
        dock.setVisible(not dock.isVisible())
        if dock.isVisible():
            dock.raise_()
            dock.show_terminal_tab()

    @Slot()
    def toggle_debug_console(self) -> None:
        """Show the terminal dock focused on debug console output."""
        dock = self.terminal_console_dock
        if dock is None:
            return
        dock.show()
        dock.raise_()
        dock.show_debug_tab()

    @Slot()
    def clear_terminal_output(self) -> None:
        """Clear terminal pane output."""
        dock = self.terminal_console_dock
        if dock is None:
            return
        dock.clear_terminal()

    @Slot()
    def clear_debug_console(self) -> None:
        """Clear debug console pane output."""
        dock = self.terminal_console_dock
        if dock is None:
            return
        dock.clear_debug()

    @Slot()
    def open_command_palette(self) -> None:
        """Show a command palette placeholder entry point."""
        QMessageBox.information(
            self,
            "Command Palette",
            "Command palette is planned for a future iteration.\n"
            "Use menus/toolbars or automation scripts for now.",
        )

    @Slot()
    def reload_plugins(self) -> None:
        """Reload all plugins from configured plugin folders."""
        self._plugin_manager.reload_plugins()
        names = self._plugin_manager.list_plugins()
        message = "Plugins reloaded: " + (", ".join(names) if names else "(none)")
        self.statusBar().showMessage(message, 2800)

    @Slot()
    def show_plugins_folder(self) -> None:
        """Show configured plugin directories."""
        plugin_dirs = self._config_manager.expand_config_paths("plugins", "directories")
        text = "\n".join(str(path) for path in plugin_dirs) or "(none configured)"
        QMessageBox.information(self, "Plugins Folder", text)

    @Slot()
    def show_installed_plugins(self) -> None:
        """Show loaded plugin names and paths."""
        loaded = self._plugin_manager.list_plugins()
        if loaded:
            body = "\n".join(f"- {name}" for name in loaded)
        else:
            body = "No plugins loaded"
        QMessageBox.information(self, "Installed Plugins", body)

    @Slot()
    def run_python_script_dialog(self) -> None:
        """Pick and run a python automation script."""
        start_dir = self._config_manager.get("automation", "last_script", "")
        if not start_dir:
            dirs = self._config_manager.expand_config_paths("automation", "script_directories")
            if dirs:
                start_dir = str(dirs[0])

        script_path, _ = QFileDialog.getOpenFileName(
            self,
            "Run Python Script",
            start_dir,
            "Python Scripts (*.py);;All Files (*)",
        )
        if not script_path:
            return

        self._config_manager.set("automation", "last_script", script_path)
        self._config_manager.save_section("automation")

        try:
            self._automation_runner.run_script(Path(script_path))
            self.statusBar().showMessage(f"Automation script completed: {Path(script_path).name}", 3000)
        except Exception as exc:
            logger.exception("Automation script failed: %s", script_path)
            QMessageBox.critical(
                self,
                "Automation Script Error",
                f"Failed to run script:\n{script_path}\n\n{exc}",
            )

    @Slot()
    def run_workflow_dialog(self) -> None:
        """Pick and run a JSON workflow file."""
        start_dir = self._config_manager.get("automation", "last_workflow", "")
        if not start_dir:
            dirs = self._config_manager.expand_config_paths("automation", "workflow_directories")
            if dirs:
                start_dir = str(dirs[0])

        workflow_path, _ = QFileDialog.getOpenFileName(
            self,
            "Run Workflow",
            start_dir,
            "Workflow Files (*.json);;All Files (*)",
        )
        if not workflow_path:
            return

        self.run_workflow_file(Path(workflow_path))

    def run_workflow_file(self, workflow_path: Path) -> None:
        """Run a selected workflow path and surface failures in UI."""
        self._config_manager.set("automation", "last_workflow", str(workflow_path))
        self._config_manager.save_section("automation")

        try:
            self._automation_runner.run_workflow(workflow_path)
            self.statusBar().showMessage(f"Workflow completed: {workflow_path.name}", 3000)
        except Exception as exc:
            logger.exception("Workflow failed: %s", workflow_path)
            QMessageBox.critical(
                self,
                "Workflow Error",
                f"Failed to run workflow:\n{workflow_path}\n\n{exc}",
            )

    @Slot()
    def start_debug_session(self) -> None:
        """Open debug console as session start placeholder."""
        self.toggle_debug_console()
        self.statusBar().showMessage("Debug session started (console mode placeholder)", 2200)

    @Slot()
    def stop_debug_session(self) -> None:
        """Stop debug session placeholder."""
        self.statusBar().showMessage("Debug session stopped", 1800)

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
    def edit_controller(self) -> Optional[EditController]:
        """Get the current tab's edit controller."""
        canvas = self.canvas
        if canvas and hasattr(canvas, '_edit_controller'):
            return canvas._edit_controller
        return None

    @property
    def drawing_controller(self) -> Optional[DrawingController]:
        """Get the current tab's drawing controller."""
        canvas = self.canvas
        if canvas and hasattr(canvas, '_drawing_controller'):
            return canvas._drawing_controller
        return None

    @property
    def undo_stack(self):
        """Get the current tab's undo stack."""
        canvas = self.canvas
        if canvas and hasattr(canvas, '_undo_stack'):
            return canvas._undo_stack
        return None

    @property
    def layer_manager(self) -> LayerManager:
        """Get the layer manager."""
        return self._layer_manager

    @property
    def workflow_dock(self) -> Optional[QDockWidget]:
        """Get the workflow dock panel."""
        return getattr(self, "_workflow_dock", None)

    @property
    def ui_theme(self) -> str:
        """Get current UI theme key."""
        return self._ui_theme

    @property
    def snap_to_grid_enabled(self) -> bool:
        """Return whether snap-to-grid is enabled."""
        return self._snap_to_grid

    @property
    def config_manager(self) -> JsonConfigManager:
        """Return JSON configuration manager."""
        return self._config_manager

    @property
    def plugin_manager(self) -> PluginManager:
        """Return plugin manager instance."""
        return self._plugin_manager

    @property
    def terminal_console_dock(self) -> Optional[TerminalConsoleDock]:
        """Return terminal/debug dock widget."""
        return getattr(self, "_terminal_console_dock", None)

    def _find_menu_by_title(self, menu_name: str) -> Optional[QMenu]:
        """Find an existing top-level menu by title (ignoring ampersands)."""
        normalized = menu_name.replace("&", "").strip().lower()
        for action in self.menuBar().actions():
            menu = action.menu()
            if menu is None:
                continue
            title = menu.title().replace("&", "").strip().lower()
            if title == normalized:
                return menu
        return None

    def register_plugin_menu_action(
        self,
        menu_name: str,
        label: str,
        callback,
        shortcut: str | None = None,
    ) -> QAction:
        """Register a menu action under a plugin-owned or existing menu."""
        menu = self._find_menu_by_title(menu_name)
        if menu is None:
            menu = self._plugin_menus.get(menu_name)
        if menu is None:
            menu = self.menuBar().addMenu(menu_name)
            self._plugin_menus[menu_name] = menu

        action = menu.addAction(label)
        action.triggered.connect(callback)
        if shortcut:
            action.setShortcut(shortcut)

        self._plugin_menu_actions.append(action)
        return action

    def clear_plugin_menu_actions(self) -> None:
        """Remove previously-registered plugin menu actions and menus."""
        for action in self._plugin_menu_actions:
            parent = action.parent()
            if isinstance(parent, QMenu):
                parent.removeAction(action)
        self._plugin_menu_actions.clear()

        for menu in self._plugin_menus.values():
            self.menuBar().removeAction(menu.menuAction())
        self._plugin_menus.clear()

    # -------------------------------------------------------------------------
    # File Operations
    # -------------------------------------------------------------------------

    @Slot()
    def new_schematic(self) -> None:
        """Create a new empty schematic."""
        context = SchematicContext()
        self._add_schematic_tab(context, "Untitled")
        self._has_wave_results = False
        self._clear_active_tool()
        self._status_setup.update_mode(self._netlist_mode_name())
        self._refresh_simulation_action_states()
        logger.info("Created new schematic tab")

    @Slot()
    def new_symbol(self) -> None:
        """Create a new empty symbol."""
        context = SchematicContext()
        context.current_name = "untitled.sym"
        self._add_schematic_tab(context, "Untitled.sym")
        self._has_wave_results = False
        self._clear_active_tool()
        self._status_setup.update_mode(self._netlist_mode_name())
        self._refresh_simulation_action_states()
        logger.info("Created new symbol tab")

    def _add_schematic_tab(self, context: SchematicContext, title: str) -> int:
        """Add a new tab with a schematic canvas."""
        canvas = SchematicCanvas(layer_manager=self._layer_manager)
        canvas.show_grid = self._show_grid
        canvas.snap_to_grid = self._snap_to_grid

        renderer = SchematicRenderer(canvas)
        renderer.context = context
        canvas._renderer = renderer  # Store reference

        # Instantiate controllers and undo stack per tab
        from pyxschem.commands.base import UndoStack
        edit_ctrl = EditController(canvas, renderer, context)
        draw_ctrl = DrawingController(canvas, renderer, context)
        canvas._edit_controller = edit_ctrl
        canvas._drawing_controller = draw_ctrl
        canvas._undo_stack = UndoStack()

        # Connect canvas signals
        canvas.zoom_changed.connect(self._on_zoom_changed)
        canvas.cursor_moved.connect(self._on_cursor_moved)
        canvas.selection_changed.connect(self._on_selection_changed)

        idx = self._tab_widget.addTab(canvas, title)
        self._tab_widget.setCurrentIndex(idx)

        self._context = context
        self._has_wave_results = False
        self._simulation_running = False
        self._clear_active_tool()
        self.schematic_changed.emit(context)
        self._update_window_title()
        self._status_setup.update_file(context.filename, context.modified)
        self._status_setup.update_layer(context.rectcolor)
        self._sync_status_indicators()
        self._refresh_simulation_action_states()
        logger.info("Added tab index=%d title='%s' file='%s'", idx, title, context.current_name or "untitled")

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

        logger.info("Opening file '%s'", file_path)
        if not file_path.exists():
            QMessageBox.warning(
                self,
                "File Not Found",
                f"The file '{file_path}' does not exist."
            )
            logger.warning("Open failed: file not found '%s'", file_path)
            return False

        try:
            context = read_schematic(str(file_path))
            self._add_schematic_tab(context, file_path.name)
            self._add_recent_file(str(file_path))
            logger.info("Opened file '%s' successfully", file_path)
            return True
        except Exception as e:
            QMessageBox.critical(
                self,
                "Error Opening File",
                f"Failed to open '{file_path}':\n{e}"
            )
            logger.exception("Failed to open file '%s'", file_path)
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
            logger.info("Opened file '%s' in new window", file_path)

    @Slot()
    def save_file(self) -> bool:
        """Save the current schematic."""
        if not self._context:
            logger.warning("Save requested with no active context")
            return False

        if not self._context.current_name or self._context.current_name.startswith("untitled"):
            return self.save_file_as()

        return self._save_to_file(self._context.current_name)

    @Slot()
    def save_file_as(self) -> bool:
        """Save the current schematic with a new name."""
        if not self._context:
            logger.warning("Save As requested with no active context")
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
            logger.warning("Save to '%s' requested with no active context", file_path)
            return False

        try:
            self._context.current_name = file_path
            write_schematic(self._context, file_path)
            self._context.modified = False
            self._update_tab_title()
            self._update_window_title()
            self._add_recent_file(file_path)
            logger.info("Saved file '%s' successfully", file_path)
            return True
        except Exception as e:
            QMessageBox.critical(
                self,
                "Error Saving File",
                f"Failed to save '{file_path}':\n{e}"
            )
            logger.exception("Failed to save file '%s'", file_path)
            return False

    @Slot()
    def reload_file(self) -> None:
        """Reload the current file from disk."""
        if not self._context or not self._context.current_name:
            logger.warning("Reload requested without a file-backed context")
            return

        if self._context.modified:
            result = QMessageBox.question(
                self,
                "Reload File",
                "The schematic has unsaved changes. Are you sure you want to reload?",
                QMessageBox.Yes | QMessageBox.No
            )
            if result != QMessageBox.Yes:
                logger.info("Reload canceled by user for '%s'", self._context.current_name)
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
            logger.info("Reloaded file '%s' successfully", file_path)
        except Exception as e:
            QMessageBox.critical(
                self,
                "Error Reloading File",
                f"Failed to reload file:\n{e}"
            )
            logger.exception("Failed to reload file '%s'", self._context.current_name if self._context else "")

    def _add_recent_file(self, file_path: str) -> None:
        """Add a file to the recent files list."""
        if file_path in self._recent_files:
            self._recent_files.remove(file_path)
        self._recent_files.insert(0, file_path)
        self._recent_files = self._recent_files[:self.MAX_RECENT_FILES]
        self._menu_setup.update_recent_files_menu()
        logger.debug("Updated recent files list (count=%d)", len(self._recent_files))

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
        dc = self.drawing_controller
        if dc:
            dc.start_zoom_box()
            self.statusBar().showMessage("Click to start zoom box, click to finish")
            self._set_active_tool("Zoom Box")

    @Slot()
    def toggle_grid(self) -> None:
        """Toggle grid visibility."""
        self._show_grid = not self._show_grid
        for i in range(self._tab_widget.count()):
            canvas = self._tab_widget.widget(i)
            if isinstance(canvas, SchematicCanvas):
                canvas.show_grid = self._show_grid
        self._sync_status_indicators()
        logger.info("Grid visibility toggled -> %s", self._show_grid)

    @Slot()
    def toggle_snap_to_grid(self) -> None:
        """Toggle snap-to-grid behavior."""
        self._snap_to_grid = not self._snap_to_grid
        for i in range(self._tab_widget.count()):
            canvas = self._tab_widget.widget(i)
            if isinstance(canvas, SchematicCanvas):
                canvas.snap_to_grid = self._snap_to_grid
        self._sync_status_indicators()
        logger.info("Snap-to-grid toggled -> %s", self._snap_to_grid)

    @Slot()
    def toggle_color_scheme(self) -> None:
        """Toggle between dark and light UI themes."""
        if self._ui_theme == "dark":
            self.set_theme_light()
        else:
            self.set_theme_dark()

    @Slot()
    def redraw(self) -> None:
        """Force a redraw of the current schematic."""
        if self.renderer:
            self.renderer.render()
            logger.debug("Redraw requested for active tab")

    # -------------------------------------------------------------------------
    # Edit Operations
    # -------------------------------------------------------------------------

    @Slot()
    def undo(self) -> None:
        """Undo the last operation."""
        canvas = self.canvas
        if canvas and hasattr(canvas, '_undo_stack'):
            desc = canvas._undo_stack.undo()
            if desc:
                self.statusBar().showMessage(f"Undone: {desc}", 2000)
                self._update_tab_title()
                return
        self.statusBar().showMessage("Nothing to undo", 2000)

    @Slot()
    def redo(self) -> None:
        """Redo the last undone operation."""
        canvas = self.canvas
        if canvas and hasattr(canvas, '_undo_stack'):
            desc = canvas._undo_stack.redo()
            if desc:
                self.statusBar().showMessage(f"Redone: {desc}", 2000)
                self._update_tab_title()
                return
        self.statusBar().showMessage("Nothing to redo", 2000)

    @Slot()
    def cut(self) -> None:
        """Cut selected objects to clipboard."""
        ec = self.edit_controller
        if ec:
            ec.cut()
            self._update_tab_title()

    @Slot()
    def copy(self) -> None:
        """Copy selected objects to clipboard."""
        ec = self.edit_controller
        if ec:
            ec.copy()

    @Slot()
    def paste(self) -> None:
        """Paste objects from clipboard."""
        ec = self.edit_controller
        if ec:
            ec.paste()
            self._update_tab_title()

    @Slot()
    def delete_selected(self) -> None:
        """Delete selected objects."""
        ec = self.edit_controller
        if ec and ec.has_selection():
            stack = self.undo_stack
            if stack:
                from pyxschem.commands.edit_commands import DeleteCommand
                cmd = DeleteCommand(self._context, self._renderer)
                stack.push(cmd)
            else:
                ec.delete()
            self._update_tab_title()

    @Slot()
    def select_all(self) -> None:
        """Select all objects."""
        ec = self.edit_controller
        if ec:
            ec.select_all()

    @Slot()
    def deselect_all(self) -> None:
        """Deselect all objects."""
        ec = self.edit_controller
        if ec:
            ec.deselect_all()
        elif self.canvas:
            self.canvas.get_scene().clearSelection()

    @Slot()
    def duplicate(self) -> None:
        """Duplicate selected objects."""
        ec = self.edit_controller
        if ec:
            ec.duplicate()
            self._update_tab_title()

    @Slot()
    def move_selected(self) -> None:
        """Start moving selected objects."""
        if self._context:
            self._context.ui_state = UIState.STARTMOVE
            self._set_active_tool("Move")
            logger.info("UI state set to STARTMOVE")

    @Slot()
    def rotate_selected(self) -> None:
        """Rotate selected objects 90 degrees."""
        ec = self.edit_controller
        if ec:
            ec.rotate(90)
            self._update_tab_title()

    @Slot()
    def flip_horizontal(self) -> None:
        """Flip selected objects horizontally."""
        ec = self.edit_controller
        if ec:
            ec.flip_horizontal()
            self._update_tab_title()

    @Slot()
    def flip_vertical(self) -> None:
        """Flip selected objects vertically."""
        ec = self.edit_controller
        if ec:
            ec.flip_vertical()
            self._update_tab_title()

    # -------------------------------------------------------------------------
    # Drawing Operations
    # -------------------------------------------------------------------------

    @Slot()
    def start_wire(self) -> None:
        """Start drawing a wire."""
        dc = self.drawing_controller
        if dc:
            dc.start_wire()
            self.statusBar().showMessage("Click to start wire, click to add points, double-click to finish")
            self._set_active_tool("Wire", "wire")

    @Slot()
    def start_line(self) -> None:
        """Start drawing a line."""
        dc = self.drawing_controller
        if dc:
            dc.start_line()
            self.statusBar().showMessage("Click to start line, click to end")
            self._set_active_tool("Line")

    @Slot()
    def start_rect(self) -> None:
        """Start drawing a rectangle."""
        dc = self.drawing_controller
        if dc:
            dc.start_rect()
            self.statusBar().showMessage("Click to start rectangle, click to set opposite corner")
            self._set_active_tool("Rectangle")

    @Slot()
    def start_arc(self) -> None:
        """Start drawing an arc."""
        dc = self.drawing_controller
        if dc:
            dc.start_arc()
            self.statusBar().showMessage("Click to set center, drag to set radius")
            self._set_active_tool("Arc")

    @Slot()
    def start_polygon(self) -> None:
        """Start drawing a polygon."""
        dc = self.drawing_controller
        if dc:
            dc.start_polygon()
            self.statusBar().showMessage("Click to add points, double-click to finish")
            self._set_active_tool("Polygon")

    @Slot()
    def start_text(self) -> None:
        """Start placing text."""
        dc = self.drawing_controller
        if dc:
            dc.start_text()
            self.statusBar().showMessage("Click to place text")
            self._set_active_tool("Text", "text")

    @Slot()
    def place_symbol(self) -> None:
        """Open symbol chooser to place a component."""
        if not self._context:
            logger.warning("Place symbol requested without active schematic context")
            self._clear_active_tool()
            return

        from pyxschem.ui.dialogs import SymbolChooserDialog

        dialog = SymbolChooserDialog(self)
        if dialog.exec():
            symbol_path = dialog.selected_symbol
            if symbol_path:
                dc = self.drawing_controller
                if dc:
                    dc.start_symbol(symbol_path)
                self.statusBar().showMessage(f"Click to place {symbol_path}")
                self._set_active_tool("Component", "component")
                logger.info("Symbol selected for placement: %s", symbol_path)
                return

        # If chooser is canceled, clear sticky highlight for component tool.
        self._clear_active_tool()

    @Slot()
    def place_ground(self) -> None:
        """Place a ground symbol (placeholder until symbol backend binds tool)."""
        self._set_active_tool("Ground")
        self.statusBar().showMessage("Ground placement shortcut selected (implementation pending)", 2400)
        logger.warning("Place ground requested but implementation is pending")

    @Slot()
    def place_net_label(self) -> None:
        """Place a net label (placeholder until dedicated label tool is implemented)."""
        self._set_active_tool("Net Label")
        self.statusBar().showMessage("Net label placement selected (implementation pending)", 2400)
        logger.warning("Place net label requested but implementation is pending")

    @Slot()
    def start_probe_mode(self) -> None:
        """Activate probe mode when simulation results are available."""
        if not self._has_wave_results:
            self._clear_active_tool()
            self.statusBar().showMessage("Probe unavailable: run simulation first", 2400)
            logger.warning("Probe requested without loaded simulation results")
            return

        self._set_active_tool("Probe", "probe")
        self.statusBar().showMessage("Probe mode selected (backend probe integration pending)", 2400)
        logger.info("Probe mode selected")

    # -------------------------------------------------------------------------
    # Properties
    # -------------------------------------------------------------------------

    @Slot()
    def edit_properties(self) -> None:
        """Edit properties of selected object."""
        from pyxschem.ui.dialogs import PropertyEditorDialog
        from pyxschem.core.property_parser import get_tok_value

        ec = self.edit_controller
        if not ec:
            return

        # Priority: instances > wires > texts > schematic properties
        selected_instances = ec.get_selected_instances()
        if selected_instances:
            inst = selected_instances[0]
            dialog = PropertyEditorDialog(self, inst.prop_ptr or "", "Edit Instance Properties")
            if dialog.exec():
                inst.prop_ptr = dialog.text
                instname = get_tok_value(dialog.text, "name")
                if instname:
                    inst.instname = instname
                self._context.modified = True
                self._renderer.render()
                self._update_tab_title()
                logger.info("Updated properties for instance '%s'", inst.instname or inst.name)
            return

        selected_wires = ec.get_selected_wires()
        if selected_wires:
            wire = selected_wires[0]
            dialog = PropertyEditorDialog(self, wire.prop_ptr or "", "Edit Wire Properties")
            if dialog.exec():
                wire.prop_ptr = dialog.text
                lab = get_tok_value(dialog.text, "lab")
                if lab:
                    wire.node = lab
                self._context.modified = True
                self._renderer.render()
                self._update_tab_title()
                logger.info("Updated wire properties")
            return

        selected_texts = ec.get_selected_texts()
        if selected_texts:
            text = selected_texts[0]
            dialog = PropertyEditorDialog(self, text.txt_ptr or "", "Edit Text")
            if dialog.exec():
                text.txt_ptr = dialog.text
                self._context.modified = True
                self._renderer.render()
                self._update_tab_title()
                logger.info("Updated text content")
            return

        # Fallback: edit schematic properties
        self.edit_schematic_properties()

    @Slot()
    def edit_schematic_properties(self) -> None:
        """Edit schematic-level properties."""
        from pyxschem.ui.dialogs import PropertyEditorDialog

        if not self._context:
            logger.warning("Edit schematic properties requested without active context")
            return

        dialog = PropertyEditorDialog(self, self._context.schprop or "")
        if dialog.exec():
            self._context.schprop = dialog.text
            self._context.modified = True
            self._update_tab_title()
            self._refresh_simulation_action_states()
            logger.info("Updated schematic properties for '%s'", self._context.current_name or "untitled")

    # -------------------------------------------------------------------------
    # Net Highlighting
    # -------------------------------------------------------------------------

    @Slot()
    def highlight_selected_nets(self) -> None:
        """Highlight all wires on the same net as selected wires/instances."""
        if not self._context:
            return

        ec = self.edit_controller
        if not ec:
            return

        # Run connectivity to get net assignments
        from pyxschem.netlist.connectivity import ConnectivityAnalyzer
        analyzer = ConnectivityAnalyzer(self._context)
        net_map = analyzer.analyze()

        # Collect net names from selected wires
        nets_to_highlight = set()
        for wire in ec.get_selected_wires():
            if wire.node:
                nets_to_highlight.add(wire.node)

        # Also from selected instance pins
        for inst in ec.get_selected_instances():
            if inst.node:
                for node in inst.node:
                    if node:
                        nets_to_highlight.add(node)

        if not nets_to_highlight:
            self.statusBar().showMessage("No nets to highlight", 2000)
            return

        # Highlight wires belonging to those nets
        from pyxschem.core.primitives import SelectionState
        count = 0
        for wire in self._context.wires:
            if wire.node in nets_to_highlight:
                wire.sel = SelectionState.SELECTED
                count += 1

        if self._renderer:
            self._renderer.render()
        self.statusBar().showMessage(f"Highlighted {count} wires on {len(nets_to_highlight)} net(s)", 3000)
        logger.info("Highlighted %d wires on nets: %s", count, nets_to_highlight)

    @Slot()
    def unhighlight_all(self) -> None:
        """Remove all net highlights."""
        ec = self.edit_controller
        if ec:
            ec.deselect_all()
        self.statusBar().showMessage("Highlights cleared", 2000)

    # -------------------------------------------------------------------------
    # Search
    # -------------------------------------------------------------------------

    @Slot()
    def show_search_dialog(self) -> None:
        """Show the search dialog."""
        from pyxschem.ui.dialogs import SearchDialog
        from pyxschem.core.primitives import SelectionState
        from PySide6.QtCore import QPointF

        dialog = SearchDialog(self, self._context)

        def goto_result(r_type, r_idx):
            ec = self.edit_controller
            if ec:
                ec.deselect_all()

            if r_type == "instance" and r_idx < len(self._context.instances):
                inst = self._context.instances[r_idx]
                inst.sel = SelectionState.SELECTED
                if self.canvas:
                    self.canvas.center_on_point(QPointF(inst.x0, inst.y0))
            elif r_type == "wire" and r_idx < len(self._context.wires):
                wire = self._context.wires[r_idx]
                wire.sel = SelectionState.SELECTED
                if self.canvas:
                    cx = (wire.x1 + wire.x2) / 2
                    cy = (wire.y1 + wire.y2) / 2
                    self.canvas.center_on_point(QPointF(cx, cy))
            elif r_type == "text" and r_idx < len(self._context.texts):
                text = self._context.texts[r_idx]
                text.sel = SelectionState.SELECTED
                if self.canvas:
                    self.canvas.center_on_point(QPointF(text.x0, text.y0))

            if self._renderer:
                self._renderer.render()

        dialog.goto_result.connect(goto_result)
        dialog.exec()

    # -------------------------------------------------------------------------
    # Hierarchy Navigation
    # -------------------------------------------------------------------------

    @Slot()
    def descend_schematic(self) -> None:
        """Descend into selected instance's schematic."""
        if not self._context:
            return

        ec = self.edit_controller
        if not ec:
            return

        selected = ec.get_selected_instances()
        if not selected:
            self.statusBar().showMessage("Select an instance to descend into", 2000)
            return

        inst = selected[0]
        # Derive .sch path from .sym path
        sym_path = inst.name
        sch_path = sym_path.replace(".sym", ".sch")

        # Try to resolve the path
        from pyxschem.core.symbol_loader import SymbolLoader
        loader = SymbolLoader()
        resolved = loader.resolve_symbol_path(sch_path, self._context)
        if resolved is None:
            # Try without replacement - maybe it's already a .sch
            resolved = loader.resolve_symbol_path(sym_path, self._context)
        if resolved is None:
            self.statusBar().showMessage(f"Cannot find schematic for {inst.name}", 3000)
            return

        import os
        if not os.path.isfile(resolved):
            self.statusBar().showMessage(f"File not found: {resolved}", 3000)
            return

        # Save current state and descend
        inst_path = inst.instname or inst.name
        self._context.push_hierarchy(resolved, inst_path)

        # Load the sub-schematic
        try:
            from pyxschem.io.schematic_reader import read_schematic
            sub_ctx = read_schematic(resolved)

            # Replace context contents with sub-schematic
            self._context.wires = sub_ctx.wires
            self._context.texts = sub_ctx.texts
            self._context.rects = sub_ctx.rects
            self._context.lines = sub_ctx.lines
            self._context.arcs = sub_ctx.arcs
            self._context.polygons = sub_ctx.polygons
            self._context.instances = sub_ctx.instances
            self._context.symbols = sub_ctx.symbols
            self._context.symbol_map = sub_ctx.symbol_map
            self._context.schprop = sub_ctx.schprop
            self._context.sym_prop = sub_ctx.sym_prop

            if self._renderer:
                self._renderer.render()
            self._update_window_title()
            self.statusBar().showMessage(f"Descended into {inst_path}", 3000)
            logger.info("Descended into '%s' (depth=%d)", resolved, self._context.hierarchy_depth)
        except Exception as e:
            # Roll back hierarchy push
            self._context.pop_hierarchy()
            self.statusBar().showMessage(f"Error: {e}", 5000)
            logger.error("Failed to descend into '%s': %s", resolved, e)

    @Slot()
    def descend_symbol(self) -> None:
        """Descend into selected instance's symbol definition."""
        if not self._context:
            return

        ec = self.edit_controller
        if not ec:
            return

        selected = ec.get_selected_instances()
        if not selected:
            self.statusBar().showMessage("Select an instance to view its symbol", 2000)
            return

        inst = selected[0]
        sym_path = inst.name

        from pyxschem.core.symbol_loader import SymbolLoader
        loader = SymbolLoader()
        resolved = loader.resolve_symbol_path(sym_path, self._context)
        if resolved:
            from pathlib import Path
            self.open_file(Path(resolved))
        else:
            self.statusBar().showMessage(f"Cannot find symbol: {sym_path}", 3000)

    @Slot()
    def go_back(self) -> None:
        """Go back up one level in hierarchy."""
        if not self._context:
            self.statusBar().showMessage("No active context", 2000)
            return

        if not self._context.hierarchy_stack:
            self.statusBar().showMessage("Already at top level", 2000)
            return

        # Get parent schematic path before popping
        parent_path = self._context.hierarchy_stack[-1].schematic_path

        if self._context.pop_hierarchy():
            try:
                from pyxschem.io.schematic_reader import read_schematic
                parent_ctx = read_schematic(parent_path)

                # Restore parent context contents
                self._context.wires = parent_ctx.wires
                self._context.texts = parent_ctx.texts
                self._context.rects = parent_ctx.rects
                self._context.lines = parent_ctx.lines
                self._context.arcs = parent_ctx.arcs
                self._context.polygons = parent_ctx.polygons
                self._context.instances = parent_ctx.instances
                self._context.symbols = parent_ctx.symbols
                self._context.symbol_map = parent_ctx.symbol_map
                self._context.schprop = parent_ctx.schprop
                self._context.sym_prop = parent_ctx.sym_prop

                if self._renderer:
                    self._renderer.render()
                self._update_window_title()
                self.statusBar().showMessage(f"Returned to {self._context.filename}", 3000)
                logger.info("Returned to '%s' (depth=%d)", parent_path, self._context.hierarchy_depth)
            except Exception as e:
                self.statusBar().showMessage(f"Error: {e}", 5000)
                logger.error("Failed to reload parent '%s': %s", parent_path, e)

    # -------------------------------------------------------------------------
    # Netlisting
    # -------------------------------------------------------------------------

    @Slot()
    def generate_netlist(self) -> None:
        """Generate netlist for current schematic."""
        if not self._context:
            self.statusBar().showMessage("No schematic loaded", 2000)
            return

        try:
            if self._netlist_type == NetlistType.SPICE:
                from pyxschem.netlist.spice_netlister import SpiceNetlister
                netlister = SpiceNetlister(self._context)
            elif self._netlist_type == NetlistType.VERILOG:
                from pyxschem.netlist.verilog_netlister import VerilogNetlister
                netlister = VerilogNetlister(self._context)
            elif self._netlist_type == NetlistType.VHDL:
                from pyxschem.netlist.vhdl_netlister import VhdlNetlister
                netlister = VhdlNetlister(self._context)
            else:
                self.statusBar().showMessage(f"Unsupported netlist type", 2000)
                return

            netlist = netlister.generate()

            # Determine output filename
            sch_path = self._context.current_name or "untitled.sch"
            ext_map = {NetlistType.SPICE: ".spice", NetlistType.VERILOG: ".v", NetlistType.VHDL: ".vhdl"}
            ext = ext_map.get(self._netlist_type, ".net")
            out_path = sch_path.rsplit(".", 1)[0] + ext

            from PySide6.QtWidgets import QFileDialog
            out_path, _ = QFileDialog.getSaveFileName(
                self, "Save Netlist", out_path,
                f"Netlist (*{ext});;All Files (*)"
            )
            if out_path:
                with open(out_path, "w", encoding="utf-8") as f:
                    f.write(netlist)
                self.statusBar().showMessage(f"Netlist saved to {out_path}", 5000)
                logger.info("Netlist saved to '%s'", out_path)
        except Exception as e:
            logger.error("Netlist generation failed: %s", e)
            self.statusBar().showMessage(f"Netlist error: {e}", 5000)

    @Slot()
    def set_netlist_type_spice(self) -> None:
        """Set netlist type to SPICE."""
        self._netlist_type = NetlistType.SPICE
        self.statusBar().showMessage("Netlist type: SPICE", 2000)
        self._status_setup.update_mode(self._netlist_mode_name())
        logger.info("Netlist type set to SPICE")

    @Slot()
    def set_netlist_type_verilog(self) -> None:
        """Set netlist type to Verilog."""
        self._netlist_type = NetlistType.VERILOG
        self.statusBar().showMessage("Netlist type: Verilog", 2000)
        self._status_setup.update_mode(self._netlist_mode_name())
        logger.info("Netlist type set to VERILOG")

    @Slot()
    def set_netlist_type_vhdl(self) -> None:
        """Set netlist type to VHDL."""
        self._netlist_type = NetlistType.VHDL
        self.statusBar().showMessage("Netlist type: VHDL", 2000)
        self._status_setup.update_mode(self._netlist_mode_name())
        logger.info("Netlist type set to VHDL")

    # -------------------------------------------------------------------------
    # Tab Management
    # -------------------------------------------------------------------------

    def _on_tab_close_requested(self, index: int) -> None:
        """Handle tab close request."""
        logger.info("Tab close requested for index %d", index)
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
                    logger.info("Tab close canceled by user for '%s'", context.filename)
                    return

        self._tab_widget.removeTab(index)
        logger.info("Closed tab index %d", index)

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
            self._clear_active_tool()
            self.schematic_changed.emit(self._context)
            self._update_window_title()
            if self._context:
                self._status_setup.update_file(self._context.filename, self._context.modified)
                self._status_setup.update_layer(self._context.rectcolor)
            self._sync_status_indicators()
            self._refresh_simulation_action_states()
            logger.info("Active tab changed to index %d", index)

    def _update_tab_title(self) -> None:
        """Update the current tab's title."""
        if not self._context:
            return

        idx = self._tab_widget.currentIndex()
        title = self._context.filename
        if self._context.modified:
            title += " *"
        self._tab_widget.setTabText(idx, title)
        self._status_setup.update_file(self._context.filename, self._context.modified)

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
        logger.debug("Selection changed in canvas")

    # -------------------------------------------------------------------------
    # Event Handlers
    # -------------------------------------------------------------------------

    def closeEvent(self, event: QCloseEvent) -> None:
        """Handle window close event."""
        logger.info("Window close requested")
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
                            logger.warning("Close canceled due to failed save in tab %d", i)
                            return
                    elif result == QMessageBox.Cancel:
                        event.ignore()
                        logger.info("Close canceled by user")
                        return

        if hasattr(self, "_terminal_console_dock"):
            self._terminal_console_dock.detach_log_handler()
        self._plugin_manager.unload_plugins()
        self._save_settings()
        event.accept()
        logger.info("Window close accepted")

    def keyPressEvent(self, event) -> None:
        """Handle key press events."""
        key = event.key()

        # Escape key cancels current operation
        if key == Qt.Key_Escape:
            dc = self.drawing_controller
            if dc and dc.is_drawing:
                dc.cancel()
            if self._context:
                self._context.ui_state = UIState.NONE
            self.deselect_all()
            self._clear_active_tool()
            self.statusBar().clearMessage()
            self._status_setup.update_mode(self._netlist_mode_name())
            event.accept()
            logger.debug("Escape pressed: cleared UI state and selection")
            return

        super().keyPressEvent(event)
