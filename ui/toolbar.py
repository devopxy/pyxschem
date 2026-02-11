"""
Toolbar setup for PyXSchem.

Implements a VS Code-inspired layout with:
- Core toolbar: high-frequency schematic actions
- Placement toolbar: editing and placement helpers
- Analysis toolbar: simulation and utility operations
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Optional, Callable
import logging

from PySide6.QtCore import Qt, QSize, QRectF, QPointF
from PySide6.QtGui import QAction, QActionGroup, QIcon, QPainter, QPen, QColor, QPixmap, QPolygonF
from PySide6.QtWidgets import QToolBar, QWidget, QSizePolicy, QStyle

if TYPE_CHECKING:
    from pyxschem.ui.main_window import MainWindow


logger = logging.getLogger(__name__)


class ToolBarSetup:
    """
    Sets up icon-first toolbars for the main window.

    The first toolbar (``toolbar`` property) remains available for
    compatibility with existing tests and integrations.
    """

    def __init__(self, main_window: "MainWindow"):
        self._window = main_window
        self._toolbar: Optional[QToolBar] = None
        self._draw_toolbar: Optional[QToolBar] = None
        self._sim_toolbar: Optional[QToolBar] = None

        self._actions: dict[str, QAction] = {}
        self._tool_actions: dict[str, QAction] = {}
        self._tool_action_group: Optional[QActionGroup] = None
        self._icon_cache: dict[tuple[str, bool], QIcon] = {}

        self._grid_action: Optional[QAction] = None
        self._snap_action: Optional[QAction] = None
        self._run_action: Optional[QAction] = None
        self._probe_action: Optional[QAction] = None
        self._stop_action: Optional[QAction] = None

    @property
    def toolbar(self) -> Optional[QToolBar]:
        """Return the primary (core actions) toolbar."""
        return self._toolbar

    @property
    def draw_toolbar(self) -> Optional[QToolBar]:
        """Return placement/edit toolbar."""
        return self._draw_toolbar

    @property
    def sim_toolbar(self) -> Optional[QToolBar]:
        """Return analysis toolbar."""
        return self._sim_toolbar

    @property
    def all_toolbars(self) -> list[QToolBar]:
        """Return all instantiated toolbars."""
        return [
            tb
            for tb in (self._toolbar, self._draw_toolbar, self._sim_toolbar)
            if tb is not None
        ]

    def setup_toolbar(self) -> None:
        """Create all toolbars."""
        self._toolbar = self._create_toolbar("Core", "core_toolbar")
        self._draw_toolbar = self._create_toolbar("Placement", "place_toolbar")
        self._sim_toolbar = self._create_toolbar("Analysis", "analysis_toolbar")

        self._window.addToolBar(Qt.TopToolBarArea, self._toolbar)
        self._window.addToolBar(Qt.TopToolBarArea, self._draw_toolbar)
        self._window.addToolBar(Qt.TopToolBarArea, self._sim_toolbar)

        self._tool_action_group = QActionGroup(self._window)
        self._tool_action_group.setExclusive(True)

        self._populate_core_toolbar(self._toolbar)
        self._populate_place_toolbar(self._draw_toolbar)
        self._populate_analysis_toolbar(self._sim_toolbar)
        logger.info("Toolbars initialized")

    def set_tool_button_style(self, style: Qt.ToolButtonStyle) -> None:
        """Set tool button style for all toolbars."""
        for toolbar in self.all_toolbars:
            toolbar.setToolButtonStyle(style)

    def current_tool_button_style(self) -> Qt.ToolButtonStyle:
        """Return the currently used toolbar button style."""
        if self._toolbar is None:
            return Qt.ToolButtonTextUnderIcon
        return self._toolbar.toolButtonStyle()

    def set_icon_size(self, size: int) -> None:
        """Set icon size (in pixels) for all toolbars."""
        size = max(14, min(size, 48))
        icon_size = QSize(size, size)
        for toolbar in self.all_toolbars:
            toolbar.setIconSize(icon_size)

    def current_icon_size(self) -> int:
        """Return icon size in pixels."""
        if self._toolbar is None:
            return 20
        return self._toolbar.iconSize().width()

    def set_visibility(
        self,
        quick: Optional[bool] = None,
        draw: Optional[bool] = None,
        sim: Optional[bool] = None,
    ) -> None:
        """Set visibility of individual toolbars."""
        if quick is not None and self._toolbar is not None:
            self._toolbar.setVisible(quick)
        if draw is not None and self._draw_toolbar is not None:
            self._draw_toolbar.setVisible(draw)
        if sim is not None and self._sim_toolbar is not None:
            self._sim_toolbar.setVisible(sim)

    def visibility_map(self) -> dict[str, bool]:
        """Return current visibility state for each toolbar."""
        return {
            "quick": self._toolbar.isVisible() if self._toolbar else False,
            "draw": self._draw_toolbar.isVisible() if self._draw_toolbar else False,
            "sim": self._sim_toolbar.isVisible() if self._sim_toolbar else False,
        }

    def set_active_tool(self, tool_key: str) -> None:
        """Highlight a sticky tool action by key."""
        action = self._tool_actions.get(tool_key)
        if action and action.isEnabled() and not action.isChecked():
            action.setChecked(True)

    def clear_active_tool(self) -> None:
        """Clear highlighted sticky tool action."""
        if self._tool_action_group is None:
            return
        self._tool_action_group.setExclusive(False)
        for action in self._tool_actions.values():
            action.setChecked(False)
        self._tool_action_group.setExclusive(True)

    def set_simulation_action_state(
        self,
        *,
        run_enabled: bool,
        probe_enabled: bool,
        stop_enabled: bool,
    ) -> None:
        """Apply enable/disable states for simulation-centric actions."""
        if self._run_action is not None:
            self._run_action.setEnabled(run_enabled)
        if self._probe_action is not None:
            self._probe_action.setEnabled(probe_enabled)
        if self._stop_action is not None:
            self._stop_action.setEnabled(stop_enabled)

    def _create_toolbar(self, title: str, object_name: str) -> QToolBar:
        """Create a configured toolbar with flat icon layout."""
        toolbar = QToolBar(title)
        toolbar.setObjectName(object_name)
        toolbar.setMovable(True)
        toolbar.setFloatable(True)
        toolbar.setIconSize(QSize(20, 20))
        toolbar.setToolButtonStyle(Qt.ToolButtonTextUnderIcon)
        return toolbar

    def _line_icon(self, name: str, highlighted: bool = False) -> QIcon:
        """Create a minimal line icon similar to codicon-like glyphs."""
        key = (name, highlighted)
        cached = self._icon_cache.get(key)
        if cached is not None:
            return cached

        size = 22
        pixmap = QPixmap(size, size)
        pixmap.fill(Qt.transparent)

        painter = QPainter(pixmap)
        painter.setRenderHint(QPainter.Antialiasing, True)
        color = QColor("#ffffff" if highlighted else "#c8c8c8")
        pen = QPen(color, 1.7, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin)
        painter.setPen(pen)
        painter.setBrush(Qt.NoBrush)

        if name == "new":
            painter.drawRect(QRectF(4, 3, 12, 16))
            painter.drawLine(13, 3, 16, 6)
            painter.drawLine(10, 11, 10, 16)
            painter.drawLine(7, 13.5, 13, 13.5)
        elif name == "open":
            painter.drawLine(3, 8, 8, 8)
            painter.drawLine(8, 8, 10, 6)
            painter.drawLine(10, 6, 18, 6)
            painter.drawLine(4, 8, 2, 17)
            painter.drawLine(2, 17, 17, 17)
            painter.drawLine(17, 17, 19, 9)
            painter.drawLine(19, 9, 9, 9)
        elif name == "save":
            painter.drawRect(QRectF(4, 4, 14, 14))
            painter.drawLine(7, 4, 7, 9)
            painter.drawLine(7, 9, 15, 9)
            painter.drawRect(QRectF(8, 12, 6, 4))
        elif name == "export":
            painter.drawRect(QRectF(4, 9, 10, 9))
            painter.drawLine(9, 3, 17, 3)
            painter.drawLine(17, 3, 17, 11)
            painter.drawLine(9, 3, 17, 11)
        elif name == "undo":
            painter.drawArc(QRectF(5, 6, 12, 10), 40 * 16, 220 * 16)
            painter.drawLine(6, 10, 3, 7)
            painter.drawLine(6, 10, 3, 13)
        elif name == "redo":
            painter.drawArc(QRectF(5, 6, 12, 10), -80 * 16, -220 * 16)
            painter.drawLine(16, 10, 19, 7)
            painter.drawLine(16, 10, 19, 13)
        elif name == "cut":
            painter.drawLine(6, 6, 16, 16)
            painter.drawLine(16, 6, 6, 16)
            painter.drawEllipse(QRectF(4, 4, 4, 4))
            painter.drawEllipse(QRectF(14, 4, 4, 4))
        elif name == "copy":
            painter.drawRect(QRectF(5, 6, 9, 10))
            painter.drawRect(QRectF(8, 4, 9, 10))
        elif name == "paste":
            painter.drawRect(QRectF(6, 5, 10, 13))
            painter.drawRect(QRectF(8, 3, 6, 3))
        elif name == "zoom_in":
            painter.drawEllipse(QRectF(4, 4, 11, 11))
            painter.drawLine(12.5, 12.5, 18, 18)
            painter.drawLine(9.5, 7, 9.5, 12)
            painter.drawLine(7, 9.5, 12, 9.5)
        elif name == "zoom_out":
            painter.drawEllipse(QRectF(4, 4, 11, 11))
            painter.drawLine(12.5, 12.5, 18, 18)
            painter.drawLine(7, 9.5, 12, 9.5)
        elif name == "zoom_fit":
            painter.drawLine(4, 8, 4, 4)
            painter.drawLine(4, 4, 8, 4)
            painter.drawLine(18, 8, 18, 4)
            painter.drawLine(14, 4, 18, 4)
            painter.drawLine(4, 14, 4, 18)
            painter.drawLine(4, 18, 8, 18)
            painter.drawLine(18, 14, 18, 18)
            painter.drawLine(14, 18, 18, 18)
        elif name == "grid":
            for x in (6, 10, 14):
                for y in (6, 10, 14):
                    painter.drawPoint(QPointF(x, y))
        elif name == "wire":
            poly = QPolygonF([QPointF(4, 15), QPointF(9, 10), QPointF(14, 10), QPointF(18, 6)])
            painter.drawPolyline(poly)
            painter.drawEllipse(QRectF(3, 14, 2, 2))
            painter.drawEllipse(QRectF(8, 9, 2, 2))
            painter.drawEllipse(QRectF(13, 9, 2, 2))
            painter.drawEllipse(QRectF(17, 5, 2, 2))
        elif name == "component":
            painter.drawLine(3, 11, 6, 11)
            painter.drawLine(16, 11, 19, 11)
            painter.drawLine(6, 11, 8, 9)
            painter.drawLine(8, 9, 10, 13)
            painter.drawLine(10, 13, 12, 9)
            painter.drawLine(12, 9, 14, 13)
            painter.drawLine(14, 13, 16, 11)
        elif name == "ground":
            painter.drawLine(11, 4, 11, 10)
            painter.drawLine(6, 10, 16, 10)
            painter.drawLine(7.5, 13, 14.5, 13)
            painter.drawLine(9, 16, 13, 16)
        elif name == "net_label":
            painter.drawLine(4, 11, 6, 11)
            painter.drawLine(6, 7, 14, 7)
            painter.drawLine(14, 7, 18, 11)
            painter.drawLine(18, 11, 14, 15)
            painter.drawLine(14, 15, 6, 15)
            painter.drawLine(6, 15, 6, 7)
            painter.drawText(QRectF(8, 7, 6, 8), Qt.AlignCenter, "A")
        elif name == "text":
            painter.drawLine(5, 6, 17, 6)
            painter.drawLine(11, 6, 11, 18)
        elif name == "run":
            painter.drawPolygon(QPolygonF([QPointF(7, 5), QPointF(17, 11), QPointF(7, 17)]))
        elif name == "stop":
            painter.drawRect(QRectF(6, 6, 10, 10))
        elif name == "probe":
            painter.drawEllipse(QRectF(6, 6, 10, 10))
            painter.drawLine(11, 3, 11, 9)
            painter.drawLine(11, 13, 11, 19)
            painter.drawLine(3, 11, 9, 11)
            painter.drawLine(13, 11, 19, 11)
        elif name == "settings":
            painter.drawEllipse(QRectF(7, 7, 8, 8))
            painter.drawLine(11, 3, 11, 6)
            painter.drawLine(11, 16, 11, 19)
            painter.drawLine(3, 11, 6, 11)
            painter.drawLine(16, 11, 19, 11)
            painter.drawLine(5, 5, 7, 7)
            painter.drawLine(15, 15, 17, 17)
            painter.drawLine(5, 17, 7, 15)
            painter.drawLine(15, 7, 17, 5)
        elif name == "check":
            painter.drawLine(4, 12, 9, 16)
            painter.drawLine(9, 16, 18, 6)
        elif name == "measure":
            painter.drawLine(4, 15, 18, 7)
            for tick_x, tick_y in ((6, 13), (9, 12), (12, 10), (15, 9)):
                painter.drawLine(tick_x, tick_y, tick_x - 1, tick_y - 2)
        elif name == "netlist":
            painter.drawText(QRectF(3, 4, 16, 14), Qt.AlignCenter, "{}")
        elif name == "docs":
            painter.drawRect(QRectF(5, 4, 12, 14))
            painter.drawLine(11, 4, 11, 18)
        elif name == "about":
            painter.drawEllipse(QRectF(5, 5, 12, 12))
            painter.drawPoint(QPointF(11, 8))
            painter.drawLine(11, 10, 11, 14)
        else:
            painter.drawRect(QRectF(4, 4, 14, 14))

        painter.end()
        icon = QIcon(pixmap)
        self._icon_cache[key] = icon
        return icon

    def _make_action(
        self,
        key: str,
        text: str,
        tooltip: str,
        callback: Callable,
        *,
        icon_name: Optional[str] = None,
        standard_icon: Optional[QStyle.StandardPixmap] = None,
        checkable: bool = False,
        checked: bool = False,
        shortcut: str | None = None,
    ) -> QAction:
        """Create a reusable toolbar action."""
        if icon_name:
            icon = self._line_icon(icon_name)
        elif standard_icon is not None:
            icon = self._window.style().standardIcon(standard_icon)
        else:
            icon = QIcon()

        action = QAction(icon, text, self._window)
        action.setToolTip(tooltip)

        if shortcut:
            action.setShortcut(shortcut)
        if checkable:
            action.setCheckable(True)
            action.setChecked(checked)
        action.triggered.connect(callback)

        self._actions[key] = action
        return action

    def _make_mode_action(
        self,
        key: str,
        text: str,
        tooltip: str,
        callback: Callable,
        *,
        icon_name: str,
        shortcut: str | None = None,
    ) -> QAction:
        """Create a sticky tool action that remains highlighted until changed."""
        action = self._make_action(
            key,
            text,
            tooltip,
            lambda checked: checked and callback(),
            icon_name=icon_name,
            checkable=True,
            shortcut=shortcut,
        )
        if self._tool_action_group is not None:
            self._tool_action_group.addAction(action)
        self._tool_actions[key] = action
        return action

    def _add_spacer(self, toolbar: QToolBar) -> None:
        """Insert an expanding spacer to visually group toolbar segments."""
        spacer = QWidget()
        spacer.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
        toolbar.addWidget(spacer)

    def _populate_core_toolbar(self, toolbar: QToolBar) -> None:
        """Populate the clean, high-frequency top row."""
        toolbar.addAction(
            self._make_action(
                "new",
                "New",
                "Create new schematic",
                self._window.new_schematic,
                icon_name="new",
                shortcut="Ctrl+N",
            )
        )
        toolbar.addAction(
            self._make_action(
                "open",
                "Open",
                "Open existing schematic",
                self._window.open_file,
                icon_name="open",
                shortcut="Ctrl+O",
            )
        )
        toolbar.addAction(
            self._make_action(
                "save",
                "Save",
                "Save current schematic",
                self._window.save_file,
                icon_name="save",
                shortcut="Ctrl+S",
            )
        )
        toolbar.addSeparator()

        toolbar.addAction(
            self._make_action(
                "undo",
                "Undo",
                "Undo last action",
                self._window.undo,
                icon_name="undo",
                shortcut="Ctrl+Z",
            )
        )
        toolbar.addAction(
            self._make_action(
                "redo",
                "Redo",
                "Redo last undone action",
                self._window.redo,
                icon_name="redo",
                shortcut="Ctrl+Shift+Z",
            )
        )
        toolbar.addSeparator()

        toolbar.addAction(
            self._make_mode_action(
                "wire",
                "Wire",
                "Draw wire / net",
                self._window.start_wire,
                icon_name="wire",
                shortcut="W",
            )
        )
        toolbar.addAction(
            self._make_mode_action(
                "component",
                "Component",
                "Place component from library",
                self._window.place_symbol,
                icon_name="component",
                shortcut="Ctrl+I",
            )
        )
        toolbar.addAction(
            self._make_action(
                "ground",
                "Ground",
                "Place ground symbol",
                self._window.place_ground,
                icon_name="ground",
                shortcut="G",
            )
        )
        toolbar.addAction(
            self._make_action(
                "net_label",
                "Net Label",
                "Place net label",
                self._window.place_net_label,
                icon_name="net_label",
                shortcut="A",
            )
        )
        toolbar.addAction(
            self._make_mode_action(
                "text",
                "Text",
                "Place text annotation",
                self._window.start_text,
                icon_name="text",
                shortcut="T",
            )
        )
        toolbar.addSeparator()

        self._run_action = self._make_action(
            "run",
            "Run",
            "Run simulation",
            self._window.run_simulation,
            icon_name="run",
        )
        toolbar.addAction(self._run_action)

        self._probe_action = self._make_mode_action(
            "probe",
            "Probe",
            "Probe node / element",
            self._window.start_probe_mode,
            icon_name="probe",
            shortcut="P",
        )
        toolbar.addAction(self._probe_action)

        toolbar.addSeparator()

        toolbar.addAction(
            self._make_action(
                "zoom_out",
                "Zoom Out",
                "Zoom out",
                self._window.zoom_out,
                icon_name="zoom_out",
                shortcut="Ctrl+-",
            )
        )
        toolbar.addAction(
            self._make_action(
                "zoom_fit",
                "Zoom Fit",
                "Fit schematic to view",
                self._window.zoom_fit,
                icon_name="zoom_fit",
                shortcut="F",
            )
        )
        toolbar.addAction(
            self._make_action(
                "zoom_in",
                "Zoom In",
                "Zoom in",
                self._window.zoom_in,
                icon_name="zoom_in",
                shortcut="Ctrl+=",
            )
        )

    def _populate_place_toolbar(self, toolbar: QToolBar) -> None:
        """Populate extended editing and placement controls."""
        toolbar.addAction(
            self._make_action(
                "export",
                "Export",
                "Export netlist/image/transfer data",
                self._window.export_design,
                icon_name="export",
            )
        )
        toolbar.addSeparator()

        toolbar.addAction(
            self._make_action(
                "cut",
                "Cut",
                "Cut selection",
                self._window.cut,
                icon_name="cut",
                shortcut="Ctrl+X",
            )
        )
        toolbar.addAction(
            self._make_action(
                "copy",
                "Copy",
                "Copy selection",
                self._window.copy,
                icon_name="copy",
                shortcut="Ctrl+C",
            )
        )
        toolbar.addAction(
            self._make_action(
                "paste",
                "Paste",
                "Paste from clipboard",
                self._window.paste,
                icon_name="paste",
                shortcut="Ctrl+V",
            )
        )
        toolbar.addAction(
            self._make_action(
                "delete",
                "Delete",
                "Delete selection",
                self._window.delete_selected,
                standard_icon=QStyle.SP_TrashIcon,
                shortcut="Delete",
            )
        )
        toolbar.addSeparator()

        self._grid_action = self._make_action(
            "grid_toggle",
            "Grid",
            "Show/hide grid",
            lambda checked: self._window.toggle_grid(),
            icon_name="grid",
            checkable=True,
            checked=True,
            shortcut="%",
        )
        toolbar.addAction(self._grid_action)

        self._snap_action = self._make_action(
            "snap_toggle",
            "Snap",
            "Enable/disable snap to grid",
            lambda checked: self._window.toggle_snap_to_grid(),
            standard_icon=QStyle.SP_DialogApplyButton,
            checkable=True,
            checked=True,
            shortcut="Y",
        )
        toolbar.addAction(self._snap_action)
        toolbar.addSeparator()

        toolbar.addAction(
            self._make_action(
                "line",
                "Line",
                "Draw line",
                self._window.start_line,
                standard_icon=QStyle.SP_FileDialogListView,
                shortcut="L",
            )
        )
        toolbar.addAction(
            self._make_action(
                "rect",
                "Rect",
                "Draw rectangle",
                self._window.start_rect,
                standard_icon=QStyle.SP_DirClosedIcon,
                shortcut="R",
            )
        )
        toolbar.addAction(
            self._make_action(
                "arc",
                "Arc",
                "Draw arc",
                self._window.start_arc,
                standard_icon=QStyle.SP_BrowserReload,
            )
        )
        toolbar.addAction(
            self._make_action(
                "polygon",
                "Polygon",
                "Draw polygon",
                self._window.start_polygon,
                standard_icon=QStyle.SP_DirOpenIcon,
            )
        )
        toolbar.addSeparator()

        toolbar.addAction(
            self._make_action(
                "move",
                "Move",
                "Move selected objects",
                self._window.move_selected,
                standard_icon=QStyle.SP_ArrowRight,
                shortcut="M",
            )
        )
        toolbar.addAction(
            self._make_action(
                "rotate",
                "Rotate",
                "Rotate selected objects",
                self._window.rotate_selected,
                standard_icon=QStyle.SP_BrowserStop,
                shortcut="Shift+R",
            )
        )

    def _populate_analysis_toolbar(self, toolbar: QToolBar) -> None:
        """Populate analysis and utility controls."""
        toolbar.addAction(
            self._make_action(
                "netlist",
                "Netlist",
                "Generate design netlist",
                self._window.generate_netlist,
                icon_name="netlist",
                shortcut="N",
            )
        )
        self._stop_action = self._make_action(
            "stop",
            "Stop",
            "Stop simulation",
            self._window.stop_simulation,
            icon_name="stop",
        )
        toolbar.addAction(self._stop_action)

        toolbar.addAction(
            self._make_action(
                "sim_settings",
                "Settings",
                "Simulation settings",
                self._window.open_simulation_settings,
                icon_name="settings",
            )
        )
        toolbar.addSeparator()

        toolbar.addAction(
            self._make_action(
                "erc_drc",
                "ERC/DRC",
                "Run electrical/design rule checks",
                self._window.run_erc_drc,
                icon_name="check",
            )
        )
        toolbar.addAction(
            self._make_action(
                "measure",
                "Measure",
                "Measure distance",
                self._window.measure_distance,
                icon_name="measure",
            )
        )
        toolbar.addAction(
            self._make_action(
                "view_netlist",
                "View Netlist",
                "View generated netlist",
                self._window.view_generated_netlist,
                icon_name="netlist",
            )
        )
        toolbar.addSeparator()

        toolbar.addAction(
            self._make_action(
                "docs",
                "Docs",
                "Open documentation",
                self._window.open_documentation,
                icon_name="docs",
            )
        )
        toolbar.addAction(
            self._make_action(
                "about",
                "About",
                "About this editor",
                self._window.show_about_dialog,
                icon_name="about",
            )
        )

    def update_grid_button(self, checked: bool) -> None:
        """Update the grid button toggle state."""
        if self._grid_action is not None:
            self._grid_action.setChecked(checked)

    def update_snap_button(self, checked: bool) -> None:
        """Update the snap button toggle state."""
        if self._snap_action is not None:
            self._snap_action.setChecked(checked)
