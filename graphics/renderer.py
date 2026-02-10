"""
Schematic renderer for PyXSchem.

Handles rendering a SchematicContext to a SchematicCanvas by
creating appropriate QGraphicsItems for all primitives.
"""

from typing import Optional, Dict, List, TYPE_CHECKING

from PySide6.QtCore import QRectF

from pyxschem.graphics.layers import LayerManager
from pyxschem.graphics.canvas import SchematicCanvas, SchematicScene
from pyxschem.graphics.items import (
    WireItem,
    LineItem,
    RectItem,
    ArcItem,
    PolygonItem,
    TextItem,
    InstanceItem,
)

if TYPE_CHECKING:
    from pyxschem.core.context import SchematicContext
    from pyxschem.core.symbol import Symbol


class SchematicRenderer:
    """
    Renders a SchematicContext to a SchematicCanvas.

    Creates QGraphicsItems for all primitives in the context
    and manages their display on the canvas.
    """

    def __init__(
        self,
        canvas: SchematicCanvas,
        context: "SchematicContext" = None
    ):
        """
        Initialize the renderer.

        Args:
            canvas: The canvas to render to
            context: Optional schematic context to render
        """
        self._canvas = canvas
        self._context: Optional["SchematicContext"] = context
        self._scene = canvas.get_scene()
        self._layers = canvas.layer_manager

        # Item tracking
        self._wire_items: List[WireItem] = []
        self._line_items: Dict[int, List[LineItem]] = {}
        self._rect_items: Dict[int, List[RectItem]] = {}
        self._arc_items: Dict[int, List[ArcItem]] = {}
        self._polygon_items: Dict[int, List[PolygonItem]] = {}
        self._text_items: List[TextItem] = []
        self._instance_items: List[InstanceItem] = []

    @property
    def context(self) -> Optional["SchematicContext"]:
        """Get the current schematic context."""
        return self._context

    @context.setter
    def context(self, value: "SchematicContext") -> None:
        """Set the schematic context and re-render."""
        self._context = value
        self.render()

    def clear(self) -> None:
        """Clear all rendered items."""
        self._scene.clear()
        self._wire_items.clear()
        self._line_items.clear()
        self._rect_items.clear()
        self._arc_items.clear()
        self._polygon_items.clear()
        self._text_items.clear()
        self._instance_items.clear()

    def render(self) -> None:
        """
        Render the current schematic context.

        Creates QGraphicsItems for all primitives and adds them
        to the scene.
        """
        self.clear()

        if self._context is None:
            return

        # Render all primitive types
        self._render_wires()
        self._render_lines()
        self._render_rects()
        self._render_arcs()
        self._render_polygons()
        self._render_texts()
        self._render_instances()

    def _render_wires(self) -> None:
        """Render all wires."""
        for wire in self._context.wires:
            item = WireItem(wire, self._layers)
            self._scene.addItem(item)
            self._wire_items.append(item)

    def _render_lines(self) -> None:
        """Render all lines."""
        for layer, lines in self._context.lines.items():
            if layer not in self._line_items:
                self._line_items[layer] = []
            for line in lines:
                item = LineItem(line, layer, self._layers)
                self._scene.addItem(item)
                self._line_items[layer].append(item)

    def _render_rects(self) -> None:
        """Render all rectangles."""
        for layer, rects in self._context.rects.items():
            if layer not in self._rect_items:
                self._rect_items[layer] = []
            for rect in rects:
                item = RectItem(rect, layer, self._layers)
                self._scene.addItem(item)
                self._rect_items[layer].append(item)

    def _render_arcs(self) -> None:
        """Render all arcs."""
        for layer, arcs in self._context.arcs.items():
            if layer not in self._arc_items:
                self._arc_items[layer] = []
            for arc in arcs:
                item = ArcItem(arc, layer, self._layers)
                self._scene.addItem(item)
                self._arc_items[layer].append(item)

    def _render_polygons(self) -> None:
        """Render all polygons."""
        for layer, polygons in self._context.polygons.items():
            if layer not in self._polygon_items:
                self._polygon_items[layer] = []
            for polygon in polygons:
                item = PolygonItem(polygon, layer, self._layers)
                self._scene.addItem(item)
                self._polygon_items[layer].append(item)

    def _render_texts(self) -> None:
        """Render all text annotations."""
        for text in self._context.texts:
            item = TextItem(text, self._layers)
            self._scene.addItem(item)
            self._text_items.append(item)

    def _render_instances(self) -> None:
        """Render all component instances."""
        for instance in self._context.instances:
            # Get the symbol for this instance
            symbol = self._get_symbol(instance)
            if symbol is None:
                continue

            item = InstanceItem(instance, symbol, self._layers)
            self._scene.addItem(item)
            self._instance_items.append(item)

    def _get_symbol(self, instance) -> Optional["Symbol"]:
        """Get the symbol for an instance."""
        if instance.ptr >= 0 and instance.ptr < len(self._context.symbols):
            return self._context.symbols[instance.ptr]
        return self._context.get_symbol(instance.name)

    def fit_view(self) -> None:
        """Fit the canvas view to show all content."""
        self._canvas.fit_in_view()

    def get_bounding_rect(self) -> QRectF:
        """Get the bounding rectangle of all rendered items."""
        return self._scene.itemsBoundingRect()

    def update_wire_junctions(self) -> None:
        """
        Update wire junction dots.

        Should be called after connectivity analysis to show
        connection points between wires.
        """
        # This would be implemented when connectivity analysis is added
        # For now, just a placeholder
        pass

    def highlight_net(self, net_name: str, color=None) -> None:
        """
        Highlight all wires belonging to a net.

        Args:
            net_name: Name of the net to highlight
            color: Highlight color (uses selection color if None)
        """
        from PySide6.QtGui import QColor

        if color is None:
            color = self._layers.selection_qcolor

        for item in self._wire_items:
            if item.wire.node == net_name:
                item.set_highlight(color)
            else:
                item.set_highlight(None)

    def clear_highlights(self) -> None:
        """Clear all highlights."""
        for item in self._wire_items:
            item.set_highlight(None)
        for item in self._instance_items:
            item.set_highlight(None)

    def get_items_at(self, x: float, y: float) -> List:
        """
        Get all items at a point.

        Args:
            x, y: Point in world coordinates

        Returns:
            List of items at the point
        """
        from PySide6.QtCore import QPointF
        return self._scene.items(QPointF(x, y))

    def get_items_in_rect(self, x1: float, y1: float, x2: float, y2: float) -> List:
        """
        Get all items in a rectangle.

        Args:
            x1, y1, x2, y2: Rectangle corners in world coordinates

        Returns:
            List of items in the rectangle
        """
        rect = QRectF(min(x1, x2), min(y1, y2),
                      abs(x2 - x1), abs(y2 - y1))
        return self._scene.items(rect)
