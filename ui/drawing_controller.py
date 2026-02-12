"""
Drawing controller for PyXSchem.

Handles interactive drawing operations:
- Wire drawing (click to start, click to add points, double-click to finish)
- Line drawing
- Rectangle drawing (click corners)
- Arc drawing (center, radius, angles)
- Polygon drawing (multiple points)
- Text placement
- Symbol placement

This controller manages the drawing state machine and coordinates
between mouse events and the schematic context.
"""

from enum import Enum, auto
from typing import Optional, List, Tuple, TYPE_CHECKING
from dataclasses import dataclass, field
import logging

from PySide6.QtCore import Qt, QPointF
from PySide6.QtGui import QPen, QColor
from PySide6.QtWidgets import QGraphicsLineItem, QGraphicsRectItem, QGraphicsEllipseItem

if TYPE_CHECKING:
    from pyxschem.core.context import SchematicContext
    from pyxschem.graphics import SchematicCanvas, SchematicRenderer


logger = logging.getLogger(__name__)


class DrawingMode(Enum):
    """Active drawing mode."""
    NONE = auto()
    WIRE = auto()
    LINE = auto()
    RECT = auto()
    ARC = auto()
    POLYGON = auto()
    TEXT = auto()
    SYMBOL = auto()
    SELECT = auto()
    ZOOM_BOX = auto()
    MOVE = auto()
    COPY = auto()


@dataclass
class DrawingState:
    """State for the current drawing operation."""
    mode: DrawingMode = DrawingMode.NONE
    start_point: Optional[QPointF] = None
    current_point: Optional[QPointF] = None
    points: List[QPointF] = field(default_factory=list)
    layer: int = 4
    # For arc drawing
    arc_center: Optional[QPointF] = None
    arc_radius: float = 0.0
    arc_start_angle: float = 0.0
    # For symbol placement
    symbol_path: Optional[str] = None
    # Preview items (rubber-band)
    preview_items: List = field(default_factory=list)


class DrawingController:
    """
    Controls interactive drawing operations.

    Manages the state machine for drawing primitives and coordinates
    between user input and schematic modifications.
    """

    # Rubber-band line style
    RUBBER_BAND_COLOR = QColor(255, 255, 0, 180)  # Yellow with alpha
    RUBBER_BAND_WIDTH = 1.0

    def __init__(
        self,
        canvas: "SchematicCanvas",
        renderer: "SchematicRenderer",
        context: "SchematicContext"
    ):
        self._canvas = canvas
        self._renderer = renderer
        self._context = context
        self._state = DrawingState()
        logger.info("DrawingController initialized")

    @property
    def mode(self) -> DrawingMode:
        """Get the current drawing mode."""
        return self._state.mode

    @property
    def is_drawing(self) -> bool:
        """Check if a drawing operation is active."""
        return self._state.mode != DrawingMode.NONE

    def start_wire(self, layer: int = 1) -> None:
        """Start wire drawing mode."""
        self._clear_preview()
        self._state = DrawingState(mode=DrawingMode.WIRE, layer=layer)
        logger.info("Drawing mode -> WIRE (layer=%d)", layer)

    def start_line(self, layer: int = 4) -> None:
        """Start line drawing mode."""
        self._clear_preview()
        self._state = DrawingState(mode=DrawingMode.LINE, layer=layer)
        logger.info("Drawing mode -> LINE (layer=%d)", layer)

    def start_rect(self, layer: int = 4) -> None:
        """Start rectangle drawing mode."""
        self._clear_preview()
        self._state = DrawingState(mode=DrawingMode.RECT, layer=layer)
        logger.info("Drawing mode -> RECT (layer=%d)", layer)

    def start_arc(self, layer: int = 4) -> None:
        """Start arc drawing mode."""
        self._clear_preview()
        self._state = DrawingState(mode=DrawingMode.ARC, layer=layer)
        logger.info("Drawing mode -> ARC (layer=%d)", layer)

    def start_polygon(self, layer: int = 4) -> None:
        """Start polygon drawing mode."""
        self._clear_preview()
        self._state = DrawingState(mode=DrawingMode.POLYGON, layer=layer)
        logger.info("Drawing mode -> POLYGON (layer=%d)", layer)

    def start_text(self) -> None:
        """Start text placement mode."""
        self._clear_preview()
        self._state = DrawingState(mode=DrawingMode.TEXT)
        logger.info("Drawing mode -> TEXT")

    def start_symbol(self, symbol_path: str) -> None:
        """Start symbol placement mode."""
        self._clear_preview()
        self._state = DrawingState(mode=DrawingMode.SYMBOL, symbol_path=symbol_path)
        logger.info("Drawing mode -> SYMBOL (%s)", symbol_path)

    def start_zoom_box(self) -> None:
        """Start zoom box selection mode."""
        self._clear_preview()
        self._state = DrawingState(mode=DrawingMode.ZOOM_BOX)
        logger.info("Drawing mode -> ZOOM_BOX")

    def start_move(self) -> None:
        """Start interactive move mode.

        Two-click workflow: first click sets reference point,
        second click sets destination. The delta is applied to
        all selected objects.
        """
        self._clear_preview()
        self._state = DrawingState(mode=DrawingMode.MOVE)
        logger.info("Drawing mode -> MOVE")

    def start_copy_mode(self) -> None:
        """Start interactive copy mode (duplicate + move)."""
        self._clear_preview()
        self._state = DrawingState(mode=DrawingMode.COPY)
        logger.info("Drawing mode -> COPY")

    def cancel(self) -> None:
        """Cancel the current drawing operation."""
        self._clear_preview()
        self._state = DrawingState()
        logger.info("Drawing operation canceled")

    def handle_mouse_press(self, point: QPointF, button: Qt.MouseButton, modifiers: Qt.KeyboardModifiers) -> bool:
        """
        Handle mouse press event.

        Args:
            point: Position in schematic coordinates
            button: Mouse button pressed
            modifiers: Keyboard modifiers

        Returns:
            True if the event was handled
        """
        if button != Qt.LeftButton:
            return False

        if self._state.mode == DrawingMode.NONE:
            return False

        # Snap to grid if enabled
        if self._canvas.snap_to_grid:
            point = self._canvas.snap_point(point)

        if self._state.mode == DrawingMode.WIRE:
            return self._handle_wire_click(point)
        elif self._state.mode == DrawingMode.LINE:
            return self._handle_line_click(point)
        elif self._state.mode == DrawingMode.RECT:
            return self._handle_rect_click(point)
        elif self._state.mode == DrawingMode.ARC:
            return self._handle_arc_click(point)
        elif self._state.mode == DrawingMode.POLYGON:
            return self._handle_polygon_click(point)
        elif self._state.mode == DrawingMode.TEXT:
            return self._handle_text_click(point)
        elif self._state.mode == DrawingMode.SYMBOL:
            return self._handle_symbol_click(point)
        elif self._state.mode == DrawingMode.ZOOM_BOX:
            return self._handle_zoom_box_click(point)
        elif self._state.mode == DrawingMode.MOVE:
            return self._handle_move_click(point)
        elif self._state.mode == DrawingMode.COPY:
            return self._handle_copy_click(point)

        return False

    def handle_mouse_move(self, point: QPointF) -> bool:
        """
        Handle mouse move event.

        Args:
            point: Position in schematic coordinates

        Returns:
            True if the event was handled
        """
        if self._state.mode == DrawingMode.NONE:
            return False

        # Snap to grid if enabled
        if self._canvas.snap_to_grid:
            point = self._canvas.snap_point(point)

        self._state.current_point = point
        self._update_preview()
        return True

    def handle_mouse_double_click(self, point: QPointF, button: Qt.MouseButton) -> bool:
        """
        Handle mouse double-click event.

        Args:
            point: Position in schematic coordinates
            button: Mouse button pressed

        Returns:
            True if the event was handled
        """
        if button != Qt.LeftButton:
            return False

        # Double-click finishes multi-point operations
        if self._state.mode == DrawingMode.WIRE:
            return self._finish_wire()
        elif self._state.mode == DrawingMode.POLYGON:
            return self._finish_polygon()

        return False

    # -------------------------------------------------------------------------
    # Wire drawing
    # -------------------------------------------------------------------------

    def _handle_wire_click(self, point: QPointF) -> bool:
        """Handle click during wire drawing."""
        if self._state.start_point is None:
            # First click - start wire
            self._state.start_point = point
            self._state.points = [point]
        else:
            # Add point
            self._state.points.append(point)
            # Create wire segment
            prev = self._state.points[-2]
            self._create_wire_segment(prev, point)
            self._state.start_point = point

        return True

    def _finish_wire(self) -> bool:
        """Finish wire drawing."""
        self._clear_preview()
        self._state = DrawingState(mode=DrawingMode.WIRE, layer=self._state.layer)
        self._renderer.render()
        logger.debug("Finished wire polyline")
        return True

    def _create_wire_segment(self, p1: QPointF, p2: QPointF) -> None:
        """Create a wire segment in the context."""
        from pyxschem.core.primitives import Wire

        wire = Wire(
            x1=p1.x(), y1=p1.y(),
            x2=p2.x(), y2=p2.y()
        )
        self._context.add_wire(wire)
        logger.debug("Created wire segment (%s,%s)->(%s,%s)", p1.x(), p1.y(), p2.x(), p2.y())

    # -------------------------------------------------------------------------
    # Line drawing
    # -------------------------------------------------------------------------

    def _handle_line_click(self, point: QPointF) -> bool:
        """Handle click during line drawing."""
        if self._state.start_point is None:
            # First click - start line
            self._state.start_point = point
        else:
            # Second click - finish line
            self._create_line(self._state.start_point, point)
            self._clear_preview()
            # Ready for next line
            self._state.start_point = None

        return True

    def _create_line(self, p1: QPointF, p2: QPointF) -> None:
        """Create a line in the context."""
        from pyxschem.core.primitives import Line

        line = Line(
            x1=p1.x(), y1=p1.y(),
            x2=p2.x(), y2=p2.y()
        )
        self._context.add_line(self._state.layer, line)
        self._renderer.render()
        logger.debug("Created line on layer=%d", self._state.layer)

    # -------------------------------------------------------------------------
    # Rectangle drawing
    # -------------------------------------------------------------------------

    def _handle_rect_click(self, point: QPointF) -> bool:
        """Handle click during rectangle drawing."""
        if self._state.start_point is None:
            # First click - start rectangle
            self._state.start_point = point
        else:
            # Second click - finish rectangle
            self._create_rect(self._state.start_point, point)
            self._clear_preview()
            # Ready for next rectangle
            self._state.start_point = None

        return True

    def _create_rect(self, p1: QPointF, p2: QPointF) -> None:
        """Create a rectangle in the context."""
        from pyxschem.core.primitives import Rect

        rect = Rect(
            x1=p1.x(), y1=p1.y(),
            x2=p2.x(), y2=p2.y()
        )
        self._context.add_rect(self._state.layer, rect)
        self._renderer.render()
        logger.debug("Created rect on layer=%d", self._state.layer)

    # -------------------------------------------------------------------------
    # Arc drawing
    # -------------------------------------------------------------------------

    def _handle_arc_click(self, point: QPointF) -> bool:
        """Handle click during arc drawing."""
        if self._state.arc_center is None:
            # First click - set center
            self._state.arc_center = point
            self._state.start_point = point
        elif self._state.arc_radius == 0:
            # Second click - set radius
            import math
            dx = point.x() - self._state.arc_center.x()
            dy = point.y() - self._state.arc_center.y()
            self._state.arc_radius = math.sqrt(dx*dx + dy*dy)
            self._state.arc_start_angle = math.degrees(math.atan2(-dy, dx))
        else:
            # Third click - finish arc
            import math
            dx = point.x() - self._state.arc_center.x()
            dy = point.y() - self._state.arc_center.y()
            end_angle = math.degrees(math.atan2(-dy, dx))

            arc_angle = end_angle - self._state.arc_start_angle
            if arc_angle < 0:
                arc_angle += 360

            self._create_arc(
                self._state.arc_center,
                self._state.arc_radius,
                self._state.arc_start_angle,
                arc_angle
            )
            self._clear_preview()
            # Reset for next arc
            self._state.arc_center = None
            self._state.arc_radius = 0
            self._state.start_point = None

        return True

    def _create_arc(self, center: QPointF, radius: float, start: float, sweep: float) -> None:
        """Create an arc in the context."""
        from pyxschem.core.primitives import Arc

        arc = Arc(
            x=center.x(), y=center.y(),
            r=radius,
            a=start, b=sweep
        )
        self._context.add_arc(self._state.layer, arc)
        self._renderer.render()
        logger.debug("Created arc on layer=%d radius=%.3f", self._state.layer, radius)

    # -------------------------------------------------------------------------
    # Polygon drawing
    # -------------------------------------------------------------------------

    def _handle_polygon_click(self, point: QPointF) -> bool:
        """Handle click during polygon drawing."""
        self._state.points.append(point)
        return True

    def _finish_polygon(self) -> bool:
        """Finish polygon drawing."""
        if len(self._state.points) >= 3:
            self._create_polygon(self._state.points)
        self._clear_preview()
        self._state = DrawingState(mode=DrawingMode.POLYGON, layer=self._state.layer)
        return True

    def _create_polygon(self, points: List[QPointF]) -> None:
        """Create a polygon in the context."""
        from pyxschem.core.primitives import Polygon

        point_list = [(p.x(), p.y()) for p in points]
        poly = Polygon.from_points(point_list)
        self._context.add_polygon(self._state.layer, poly)
        self._renderer.render()
        logger.debug("Created polygon on layer=%d points=%d", self._state.layer, len(points))

    # -------------------------------------------------------------------------
    # Text placement
    # -------------------------------------------------------------------------

    def _handle_text_click(self, point: QPointF) -> bool:
        """Handle click during text placement."""
        from pyxschem.ui.dialogs import TextInputDialog
        from pyxschem.core.primitives import Text

        text, ok = TextInputDialog.get_text(
            self._canvas,
            "Enter Text",
            "Text:"
        )

        if ok and text:
            txt = Text(
                txt_ptr=text,
                x0=point.x(), y0=point.y()
            )
            self._context.add_text(txt)
            self._renderer.render()
            logger.debug("Placed text at (%.3f, %.3f)", point.x(), point.y())

        return True

    # -------------------------------------------------------------------------
    # Symbol placement
    # -------------------------------------------------------------------------

    def _handle_symbol_click(self, point: QPointF) -> bool:
        """Handle click during symbol placement."""
        if not self._state.symbol_path:
            return False

        from pyxschem.core.symbol_loader import SymbolLoader
        from pyxschem.core.symbol import Instance
        from pyxschem.core.property_parser import get_tok_value

        loader = SymbolLoader()
        symbol = loader.load_symbol(self._state.symbol_path, self._context)
        if symbol is None:
            logger.error("Could not load symbol '%s'", self._state.symbol_path)
            return True

        # Build default properties from template
        props = symbol.templ or ""
        instname = self._generate_unique_name(symbol)

        # Insert instance name into properties
        if instname:
            if props and "name=" not in props:
                props = f"name={instname} {props}"
            elif not props:
                props = f"name={instname}"

        # Look up symbol index in context
        sym_idx = self._context.symbol_map.get(symbol.name, -1)
        if sym_idx == -1:
            # Fallback: symbol was added but map key might differ (path normalization)
            for i, sym in enumerate(self._context.symbols):
                if sym is symbol:
                    sym_idx = i
                    break

        instance = Instance(
            name=self._state.symbol_path,
            ptr=sym_idx,
            x0=point.x(),
            y0=point.y(),
            rot=0,
            flip=0,
            prop_ptr=props,
            instname=instname,
        )
        instance.calculate_bbox(symbol)
        self._context.add_instance(instance)
        self._renderer.render()

        logger.info(
            "Placed instance '%s' of '%s' at (%.1f, %.1f)",
            instname, self._state.symbol_path, point.x(), point.y(),
        )
        return True

    def _generate_unique_name(self, symbol) -> str:
        """Generate a unique instance name based on symbol type."""
        from pyxschem.core.symbol import SymbolType

        # Determine prefix from symbol type
        sym_type = symbol.type or ""
        if sym_type == SymbolType.SUBCIRCUIT:
            prefix = "x"
        elif sym_type == SymbolType.PRIMITIVE:
            # Try to guess from symbol name
            base = symbol.name.rsplit("/", 1)[-1].replace(".sym", "")
            prefix_map = {
                "resistor": "R", "res": "R",
                "capacitor": "C", "cap": "C", "capa": "C",
                "inductor": "L", "ind": "L",
                "voltage": "V", "vsource": "V",
                "current": "I", "isource": "I",
                "diode": "D",
                "npn": "Q", "pnp": "Q",
                "nmos": "M", "pmos": "M", "mosfet": "M",
            }
            prefix = prefix_map.get(base.lower(), base[0].upper() if base else "U")
        elif sym_type in (SymbolType.LABEL, SymbolType.IPIN, SymbolType.OPIN, SymbolType.IOPIN):
            prefix = "lab"
        else:
            prefix = "U"

        # Find next available number
        existing = set()
        for inst in self._context.instances:
            if inst.instname and inst.instname.startswith(prefix):
                suffix = inst.instname[len(prefix):]
                try:
                    existing.add(int(suffix))
                except ValueError:
                    pass

        n = 1
        while n in existing:
            n += 1
        return f"{prefix}{n}"

    # -------------------------------------------------------------------------
    # Zoom box
    # -------------------------------------------------------------------------

    def _handle_zoom_box_click(self, point: QPointF) -> bool:
        """Handle click during zoom box selection."""
        if self._state.start_point is None:
            self._state.start_point = point
        else:
            # Zoom to box
            self._canvas.fit_to_rect(
                self._state.start_point.x(), self._state.start_point.y(),
                point.x(), point.y()
            )
            self._clear_preview()
            self._state = DrawingState()

        return True

    # -------------------------------------------------------------------------
    # Move / Copy
    # -------------------------------------------------------------------------

    def _handle_move_click(self, point: QPointF) -> bool:
        """Handle click during interactive move.

        First click sets reference point, second click finalizes the move.
        """
        if self._state.start_point is None:
            self._state.start_point = point
            logger.debug("Move reference point set at (%.1f, %.1f)", point.x(), point.y())
        else:
            dx = point.x() - self._state.start_point.x()
            dy = point.y() - self._state.start_point.y()

            ec = getattr(self._canvas, '_edit_controller', None)
            undo_stack = getattr(self._canvas, '_undo_stack', None)

            if undo_stack and ec:
                try:
                    from pyxschem.commands.edit_commands import MoveCommand
                    cmd = MoveCommand(self._context, self._renderer, dx, dy)
                    undo_stack.push(cmd)
                except Exception:
                    if ec:
                        ec.move(dx, dy)
            elif ec:
                ec.move(dx, dy)

            self._clear_preview()
            self._state = DrawingState()
            logger.info("Move completed: dx=%.1f, dy=%.1f", dx, dy)
        return True

    def _handle_copy_click(self, point: QPointF) -> bool:
        """Handle click during interactive copy.

        First click sets reference point, second click duplicates + moves.
        """
        if self._state.start_point is None:
            self._state.start_point = point
            logger.debug("Copy reference point set at (%.1f, %.1f)", point.x(), point.y())
        else:
            dx = point.x() - self._state.start_point.x()
            dy = point.y() - self._state.start_point.y()

            ec = getattr(self._canvas, '_edit_controller', None)
            if ec:
                ec.copy()
                ec.paste(offset=(dx, dy))

            self._clear_preview()
            self._state = DrawingState()
            logger.info("Copy completed: dx=%.1f, dy=%.1f", dx, dy)
        return True

    def _draw_move_preview(self, dx: float, dy: float) -> None:
        """Draw ghost outlines showing where selected items will move to."""
        from pyxschem.core.primitives import SelectionState

        scene = self._canvas.get_scene()
        pen = QPen(self.RUBBER_BAND_COLOR, self.RUBBER_BAND_WIDTH)
        pen.setStyle(Qt.DashLine)

        for wire in self._context.wires:
            if wire.sel & SelectionState.SELECTED:
                line = QGraphicsLineItem(
                    wire.x1 + dx, wire.y1 + dy,
                    wire.x2 + dx, wire.y2 + dy
                )
                line.setPen(pen)
                scene.addItem(line)
                self._state.preview_items.append(line)

        for layer_lines in self._context.lines.values():
            for ln in layer_lines:
                if ln.sel & SelectionState.SELECTED:
                    line = QGraphicsLineItem(
                        ln.x1 + dx, ln.y1 + dy,
                        ln.x2 + dx, ln.y2 + dy
                    )
                    line.setPen(pen)
                    scene.addItem(line)
                    self._state.preview_items.append(line)

        for layer_rects in self._context.rects.values():
            for r in layer_rects:
                if r.sel & SelectionState.SELECTED:
                    x1, y1, x2, y2 = r.bbox
                    rect = QGraphicsRectItem(x1 + dx, y1 + dy, x2 - x1, y2 - y1)
                    rect.setPen(pen)
                    scene.addItem(rect)
                    self._state.preview_items.append(rect)

        for inst in self._context.instances:
            if inst.sel & SelectionState.SELECTED:
                x1, y1, x2, y2 = inst.bbox
                rect = QGraphicsRectItem(x1 + dx, y1 + dy, x2 - x1, y2 - y1)
                rect.setPen(pen)
                scene.addItem(rect)
                self._state.preview_items.append(rect)

        for text in self._context.texts:
            if text.sel & SelectionState.SELECTED:
                x, y = text.x0 + dx, text.y0 + dy
                # Small cross marker for text position
                size = 5
                line_h = QGraphicsLineItem(x - size, y, x + size, y)
                line_h.setPen(pen)
                scene.addItem(line_h)
                self._state.preview_items.append(line_h)
                line_v = QGraphicsLineItem(x, y - size, x, y + size)
                line_v.setPen(pen)
                scene.addItem(line_v)
                self._state.preview_items.append(line_v)

    # -------------------------------------------------------------------------
    # Preview (rubber-band) handling
    # -------------------------------------------------------------------------

    def _update_preview(self) -> None:
        """Update the rubber-band preview."""
        self._clear_preview()

        if self._state.current_point is None:
            return

        scene = self._canvas.get_scene()
        pen = QPen(self.RUBBER_BAND_COLOR, self.RUBBER_BAND_WIDTH)
        pen.setStyle(Qt.DashLine)

        if self._state.mode == DrawingMode.WIRE or self._state.mode == DrawingMode.LINE:
            if self._state.start_point:
                line = QGraphicsLineItem(
                    self._state.start_point.x(), self._state.start_point.y(),
                    self._state.current_point.x(), self._state.current_point.y()
                )
                line.setPen(pen)
                scene.addItem(line)
                self._state.preview_items.append(line)

        elif self._state.mode == DrawingMode.RECT or self._state.mode == DrawingMode.ZOOM_BOX:
            if self._state.start_point:
                x = min(self._state.start_point.x(), self._state.current_point.x())
                y = min(self._state.start_point.y(), self._state.current_point.y())
                w = abs(self._state.current_point.x() - self._state.start_point.x())
                h = abs(self._state.current_point.y() - self._state.start_point.y())
                rect = QGraphicsRectItem(x, y, w, h)
                rect.setPen(pen)
                scene.addItem(rect)
                self._state.preview_items.append(rect)

        elif self._state.mode == DrawingMode.ARC:
            if self._state.arc_center and self._state.arc_radius == 0:
                # Drawing radius line
                line = QGraphicsLineItem(
                    self._state.arc_center.x(), self._state.arc_center.y(),
                    self._state.current_point.x(), self._state.current_point.y()
                )
                line.setPen(pen)
                scene.addItem(line)
                self._state.preview_items.append(line)
            elif self._state.arc_center and self._state.arc_radius > 0:
                # Draw circle preview
                r = self._state.arc_radius
                ellipse = QGraphicsEllipseItem(
                    self._state.arc_center.x() - r,
                    self._state.arc_center.y() - r,
                    r * 2, r * 2
                )
                ellipse.setPen(pen)
                scene.addItem(ellipse)
                self._state.preview_items.append(ellipse)

        elif self._state.mode in (DrawingMode.MOVE, DrawingMode.COPY):
            if self._state.start_point:
                dx = self._state.current_point.x() - self._state.start_point.x()
                dy = self._state.current_point.y() - self._state.start_point.y()
                self._draw_move_preview(dx, dy)

        elif self._state.mode == DrawingMode.POLYGON:
            if self._state.points:
                # Draw lines between points
                for i in range(len(self._state.points)):
                    if i < len(self._state.points) - 1:
                        p1 = self._state.points[i]
                        p2 = self._state.points[i + 1]
                    else:
                        p1 = self._state.points[i]
                        p2 = self._state.current_point
                    line = QGraphicsLineItem(p1.x(), p1.y(), p2.x(), p2.y())
                    line.setPen(pen)
                    scene.addItem(line)
                    self._state.preview_items.append(line)

                # Closing line
                if len(self._state.points) > 1:
                    p1 = self._state.current_point
                    p2 = self._state.points[0]
                    line = QGraphicsLineItem(p1.x(), p1.y(), p2.x(), p2.y())
                    line.setPen(pen)
                    scene.addItem(line)
                    self._state.preview_items.append(line)

    def _clear_preview(self) -> None:
        """Clear all preview items."""
        scene = self._canvas.get_scene()
        for item in self._state.preview_items:
            try:
                scene.removeItem(item)
            except RuntimeError:
                # C++ object already deleted (e.g. scene.clear() from renderer)
                pass
        self._state.preview_items.clear()
        logger.debug("Cleared preview items")
