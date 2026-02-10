"""
QGraphicsItem subclasses for schematic primitives.

Each class wraps a primitive dataclass and handles its rendering,
selection, and transformation.
"""

from typing import Optional, List, TYPE_CHECKING
import math

from PySide6.QtCore import Qt, QRectF, QPointF, QLineF
from PySide6.QtGui import (
    QPainter,
    QPen,
    QBrush,
    QColor,
    QPainterPath,
    QPolygonF,
    QFont,
    QFontMetricsF,
    QTransform,
)
from PySide6.QtWidgets import (
    QGraphicsItem,
    QGraphicsLineItem,
    QGraphicsRectItem,
    QGraphicsEllipseItem,
    QGraphicsPolygonItem,
    QGraphicsTextItem,
    QGraphicsItemGroup,
    QStyleOptionGraphicsItem,
    QWidget,
)

from pyxschem.graphics.layers import LayerManager, FillStyle, WIRELAYER, SELLAYER

if TYPE_CHECKING:
    from pyxschem.core.primitives import Wire, Line, Rect, Arc, Polygon, Text
    from pyxschem.core.symbol import Instance, Symbol


class BaseSchematicItem(QGraphicsItem):
    """
    Base class for all schematic items.

    Provides common functionality for layer-based styling,
    selection highlighting, and data binding.
    """

    def __init__(
        self,
        layer: int,
        layer_manager: LayerManager,
        parent: QGraphicsItem = None
    ):
        super().__init__(parent)
        self._layer = layer
        self._layers = layer_manager
        self._selected = False
        self._highlight_color: Optional[QColor] = None

        # Enable selection
        self.setFlag(QGraphicsItem.ItemIsSelectable, True)
        # Cache the item's painting
        self.setCacheMode(QGraphicsItem.DeviceCoordinateCache)

    @property
    def layer(self) -> int:
        """Get the layer number."""
        return self._layer

    @layer.setter
    def layer(self, value: int) -> None:
        """Set the layer number and update appearance."""
        self._layer = value
        self.update()

    def get_pen(self, width: float = None, dash: int = 0) -> QPen:
        """Get the pen for this item's layer."""
        if self._selected:
            return self._layers.get_selection_pen()
        if self._highlight_color:
            pen = QPen(self._highlight_color)
            pen.setWidthF(width or 2.0)
            return pen
        return self._layers.get_pen(self._layer, width, dash)

    def get_brush(self, fill: int = FillStyle.NONE) -> QBrush:
        """Get the brush for this item's layer."""
        return self._layers.get_brush(self._layer, fill)

    def set_highlight(self, color: QColor = None) -> None:
        """Set highlight color (None to clear)."""
        self._highlight_color = color
        self.update()

    def itemChange(self, change, value):
        """Handle selection changes."""
        if change == QGraphicsItem.ItemSelectedChange:
            self._selected = bool(value)
            self.update()
        return super().itemChange(change, value)


class WireItem(BaseSchematicItem):
    """
    Graphics item for electrical wires.

    Wires are always on WIRELAYER and can have bus width for thick lines.
    Junction dots are drawn at wire endpoints when connected.
    """

    def __init__(
        self,
        wire: "Wire",
        layer_manager: LayerManager,
        parent: QGraphicsItem = None
    ):
        super().__init__(WIRELAYER, layer_manager, parent)
        self._wire = wire
        self._show_junction = [False, False]  # [end1, end2]
        self._junction_radius = 3.0

    @property
    def wire(self) -> "Wire":
        """Get the wire data."""
        return self._wire

    def set_junction(self, end1: bool, end2: bool) -> None:
        """Set whether to show junction dots at endpoints."""
        self._show_junction = [end1, end2]
        self.update()

    def boundingRect(self) -> QRectF:
        """Return bounding rectangle."""
        x1, y1, x2, y2 = self._wire.bbox
        # Add margin for bus width and junctions
        margin = max(self._wire.bus * 2, self._junction_radius + 2)
        return QRectF(x1 - margin, y1 - margin,
                      x2 - x1 + 2 * margin, y2 - y1 + 2 * margin)

    def paint(
        self,
        painter: QPainter,
        option: QStyleOptionGraphicsItem,
        widget: QWidget = None
    ) -> None:
        """Draw the wire."""
        # Calculate line width based on bus multiplier
        base_width = 2.0
        width = base_width * max(1.0, self._wire.bus)

        pen = self.get_pen(width)
        painter.setPen(pen)

        # Draw wire line
        painter.drawLine(
            QLineF(self._wire.x1, self._wire.y1,
                   self._wire.x2, self._wire.y2)
        )

        # Draw junction dots
        if self._show_junction[0]:
            self._draw_junction(painter, self._wire.x1, self._wire.y1)
        if self._show_junction[1]:
            self._draw_junction(painter, self._wire.x2, self._wire.y2)

    def _draw_junction(self, painter: QPainter, x: float, y: float) -> None:
        """Draw a junction dot at the specified position."""
        painter.setBrush(self.get_brush(FillStyle.SOLID))
        painter.drawEllipse(
            QPointF(x, y),
            self._junction_radius,
            self._junction_radius
        )


class LineItem(BaseSchematicItem):
    """
    Graphics item for non-electrical lines.

    Lines are purely graphical elements on a specific layer.
    """

    def __init__(
        self,
        line: "Line",
        layer: int,
        layer_manager: LayerManager,
        parent: QGraphicsItem = None
    ):
        super().__init__(layer, layer_manager, parent)
        self._line = line

    @property
    def line(self) -> "Line":
        """Get the line data."""
        return self._line

    def boundingRect(self) -> QRectF:
        """Return bounding rectangle."""
        x1, y1, x2, y2 = self._line.bbox
        margin = self._line.bus * 2 + 2
        return QRectF(x1 - margin, y1 - margin,
                      x2 - x1 + 2 * margin, y2 - y1 + 2 * margin)

    def paint(
        self,
        painter: QPainter,
        option: QStyleOptionGraphicsItem,
        widget: QWidget = None
    ) -> None:
        """Draw the line."""
        width = max(1.0, self._line.bus)
        pen = self.get_pen(width, self._line.dash)
        painter.setPen(pen)
        painter.drawLine(
            QLineF(self._line.x1, self._line.y1,
                   self._line.x2, self._line.y2)
        )


class RectItem(BaseSchematicItem):
    """
    Graphics item for rectangles/boxes.

    Supports fill modes: none, stipple, solid.
    Also supports rounded corners via ellipse_a/ellipse_b.
    """

    def __init__(
        self,
        rect: "Rect",
        layer: int,
        layer_manager: LayerManager,
        parent: QGraphicsItem = None
    ):
        super().__init__(layer, layer_manager, parent)
        self._rect = rect

    @property
    def rect(self) -> "Rect":
        """Get the rect data."""
        return self._rect

    def boundingRect(self) -> QRectF:
        """Return bounding rectangle."""
        x1, y1, x2, y2 = self._rect.bbox
        margin = self._rect.bus * 2 + 2
        return QRectF(x1 - margin, y1 - margin,
                      x2 - x1 + 2 * margin, y2 - y1 + 2 * margin)

    def paint(
        self,
        painter: QPainter,
        option: QStyleOptionGraphicsItem,
        widget: QWidget = None
    ) -> None:
        """Draw the rectangle."""
        width = max(1.0, self._rect.bus)
        pen = self.get_pen(width, self._rect.dash)
        brush = self.get_brush(self._rect.fill)

        painter.setPen(pen)
        painter.setBrush(brush)

        x1, y1, x2, y2 = self._rect.bbox
        rect = QRectF(x1, y1, x2 - x1, y2 - y1)

        # Check for rounded corners
        if self._rect.ellipse_a > 0 or self._rect.ellipse_b > 0:
            rx = self._rect.ellipse_a
            ry = self._rect.ellipse_b if self._rect.ellipse_b > 0 else rx
            painter.drawRoundedRect(rect, rx, ry)
        else:
            painter.drawRect(rect)


class ArcItem(BaseSchematicItem):
    """
    Graphics item for arcs and circles.

    Arcs are defined by center, radius, start angle, and arc angle.
    A full circle has arc angle of 360 degrees.
    """

    def __init__(
        self,
        arc: "Arc",
        layer: int,
        layer_manager: LayerManager,
        parent: QGraphicsItem = None
    ):
        super().__init__(layer, layer_manager, parent)
        self._arc = arc

    @property
    def arc(self) -> "Arc":
        """Get the arc data."""
        return self._arc

    def boundingRect(self) -> QRectF:
        """Return bounding rectangle."""
        x1, y1, x2, y2 = self._arc.bbox
        margin = self._arc.bus * 2 + 2
        return QRectF(x1 - margin, y1 - margin,
                      x2 - x1 + 2 * margin, y2 - y1 + 2 * margin)

    def paint(
        self,
        painter: QPainter,
        option: QStyleOptionGraphicsItem,
        widget: QWidget = None
    ) -> None:
        """Draw the arc."""
        width = max(1.0, self._arc.bus)
        pen = self.get_pen(width, self._arc.dash)
        brush = self.get_brush(self._arc.fill)

        painter.setPen(pen)
        painter.setBrush(brush)

        # Calculate bounding rectangle for arc
        r = self._arc.r
        rect = QRectF(
            self._arc.x - r,
            self._arc.y - r,
            2 * r,
            2 * r
        )

        # Qt uses 1/16th of a degree for arc angles
        # xschem uses degrees, 0 = right (3 o'clock), counterclockwise
        # Qt also uses counterclockwise, 0 = right
        start_angle = int(self._arc.a * 16)
        span_angle = int(self._arc.b * 16)

        if self._arc.is_circle:
            if self._arc.fill:
                painter.drawEllipse(rect)
            else:
                painter.drawEllipse(rect)
        else:
            if self._arc.fill:
                painter.drawPie(rect, start_angle, span_angle)
            else:
                painter.drawArc(rect, start_angle, span_angle)


class PolygonItem(BaseSchematicItem):
    """
    Graphics item for polygons.

    Polygons are defined by arrays of x and y coordinates.
    """

    def __init__(
        self,
        polygon: "Polygon",
        layer: int,
        layer_manager: LayerManager,
        parent: QGraphicsItem = None
    ):
        super().__init__(layer, layer_manager, parent)
        self._polygon = polygon
        self._qpolygon = self._build_qpolygon()

    def _build_qpolygon(self) -> QPolygonF:
        """Build QPolygonF from polygon data."""
        points = []
        for i in range(self._polygon.points):
            points.append(QPointF(self._polygon.x[i], self._polygon.y[i]))
        return QPolygonF(points)

    @property
    def polygon(self) -> "Polygon":
        """Get the polygon data."""
        return self._polygon

    def boundingRect(self) -> QRectF:
        """Return bounding rectangle."""
        x1, y1, x2, y2 = self._polygon.bbox
        margin = self._polygon.bus * 2 + 2
        return QRectF(x1 - margin, y1 - margin,
                      x2 - x1 + 2 * margin, y2 - y1 + 2 * margin)

    def paint(
        self,
        painter: QPainter,
        option: QStyleOptionGraphicsItem,
        widget: QWidget = None
    ) -> None:
        """Draw the polygon."""
        width = max(1.0, self._polygon.bus)
        pen = self.get_pen(width, self._polygon.dash)
        brush = self.get_brush(self._polygon.fill)

        painter.setPen(pen)
        painter.setBrush(brush)
        painter.drawPolygon(self._qpolygon)


class TextItem(BaseSchematicItem):
    """
    Graphics item for text annotations.

    Handles rotation, flip, scaling, and alignment (hcenter, vcenter).
    """

    # Default font settings
    DEFAULT_FONT_FAMILY = "monospace"
    DEFAULT_FONT_SIZE = 10.0
    BASE_CHAR_HEIGHT = 14.0  # Base height for scale=1.0

    def __init__(
        self,
        text: "Text",
        layer_manager: LayerManager,
        parent: QGraphicsItem = None
    ):
        super().__init__(text.layer, layer_manager, parent)
        self._text = text
        self._font = self._create_font()
        self._bounding_rect: Optional[QRectF] = None

    def _create_font(self) -> QFont:
        """Create font based on text settings."""
        font_name = self._text.font or self.DEFAULT_FONT_FAMILY
        font = QFont(font_name)

        # Calculate font size from xscale
        size = self.DEFAULT_FONT_SIZE * self._text.xscale
        font.setPointSizeF(size)

        # Apply style flags
        if self._text.is_bold:
            font.setBold(True)
        if self._text.is_italic:
            font.setItalic(True)

        return font

    @property
    def text(self) -> "Text":
        """Get the text data."""
        return self._text

    def _calculate_text_rect(self) -> QRectF:
        """Calculate the text bounding rectangle before transformation."""
        metrics = QFontMetricsF(self._font)
        lines = self._text.txt_ptr.split('\n')

        # Calculate total width and height
        max_width = 0.0
        total_height = 0.0
        line_height = metrics.height()

        for line in lines:
            width = metrics.horizontalAdvance(line)
            max_width = max(max_width, width)
            total_height += line_height

        return QRectF(0, 0, max_width, total_height)

    def boundingRect(self) -> QRectF:
        """Return bounding rectangle including transformations."""
        if self._bounding_rect is not None:
            return self._bounding_rect

        # Get base text rect
        text_rect = self._calculate_text_rect()

        # Apply transformations
        transform = self._get_transform()
        self._bounding_rect = transform.mapRect(text_rect)

        # Add some margin
        margin = 2
        self._bounding_rect.adjust(-margin, -margin, margin, margin)

        return self._bounding_rect

    def _get_transform(self) -> QTransform:
        """Get the transformation for this text."""
        transform = QTransform()

        # Move to text position
        transform.translate(self._text.x0, self._text.y0)

        # Apply rotation (xschem: 0,1,2,3 = 0,90,180,270)
        if self._text.rot:
            transform.rotate(self._text.rot * 90)

        # Apply flip
        if self._text.flip:
            transform.scale(-1, 1)

        # Apply alignment offset
        text_rect = self._calculate_text_rect()

        offset_x = 0.0
        offset_y = 0.0

        # Horizontal center: 0=left, 1=center, 2=right
        if self._text.hcenter == 1:
            offset_x = -text_rect.width() / 2
        elif self._text.hcenter == 2:
            offset_x = -text_rect.width()

        # Vertical center: 0=bottom, 1=center, 2=top
        if self._text.vcenter == 0:
            offset_y = -text_rect.height()
        elif self._text.vcenter == 1:
            offset_y = -text_rect.height() / 2
        # vcenter == 2 means top, no offset needed

        transform.translate(offset_x, offset_y)

        return transform

    def paint(
        self,
        painter: QPainter,
        option: QStyleOptionGraphicsItem,
        widget: QWidget = None
    ) -> None:
        """Draw the text."""
        color = self._layers.get_qcolor(self._layer)
        if self._selected:
            color = self._layers.selection_qcolor
        elif self._highlight_color:
            color = self._highlight_color

        painter.save()

        # Apply transformation
        transform = self._get_transform()
        painter.setTransform(transform, True)

        # Set up font and color
        painter.setFont(self._font)
        painter.setPen(QPen(color))

        # Draw text lines
        metrics = QFontMetricsF(self._font)
        line_height = metrics.height()
        y = metrics.ascent()

        for line in self._text.txt_ptr.split('\n'):
            painter.drawText(QPointF(0, y), line)
            y += line_height

        painter.restore()


class InstanceItem(QGraphicsItemGroup):
    """
    Graphics item for component instances.

    An instance groups all the graphical elements of a symbol
    and applies the instance transformation (position, rotation, flip).
    """

    def __init__(
        self,
        instance: "Instance",
        symbol: "Symbol",
        layer_manager: LayerManager,
        parent: QGraphicsItem = None
    ):
        super().__init__(parent)
        self._instance = instance
        self._symbol = symbol
        self._layers = layer_manager
        self._highlight_color: Optional[QColor] = None

        # Enable selection
        self.setFlag(QGraphicsItem.ItemIsSelectable, True)

        # Build child items
        self._build_symbol_items()

        # Apply instance transformation
        self._apply_transform()

    def _build_symbol_items(self) -> None:
        """Create graphics items for all symbol elements."""
        # Add lines
        for layer, lines in self._symbol.lines.items():
            for line in lines:
                item = LineItem(line, layer, self._layers)
                self.addToGroup(item)

        # Add rects
        for layer, rects in self._symbol.rects.items():
            for rect in rects:
                item = RectItem(rect, layer, self._layers)
                self.addToGroup(item)

        # Add arcs
        for layer, arcs in self._symbol.arcs.items():
            for arc in arcs:
                item = ArcItem(arc, layer, self._layers)
                self.addToGroup(item)

        # Add polygons
        for layer, polygons in self._symbol.polygons.items():
            for polygon in polygons:
                item = PolygonItem(polygon, layer, self._layers)
                self.addToGroup(item)

        # Add texts
        for text in self._symbol.texts:
            item = TextItem(text, self._layers)
            self.addToGroup(item)

    def _apply_transform(self) -> None:
        """Apply instance transformation (position, rotation, flip)."""
        # Start with identity transform
        transform = QTransform()

        # Move to instance position
        transform.translate(self._instance.x0, self._instance.y0)

        # Apply flip (before rotation, around the origin)
        if self._instance.flip:
            transform.scale(-1, 1)

        # Apply rotation (0,1,2,3 = 0,90,180,270 degrees)
        if self._instance.rot:
            transform.rotate(self._instance.rot * 90)

        self.setTransform(transform)

    @property
    def instance(self) -> "Instance":
        """Get the instance data."""
        return self._instance

    @property
    def symbol(self) -> "Symbol":
        """Get the symbol data."""
        return self._symbol

    def set_highlight(self, color: QColor = None) -> None:
        """Set highlight color for all child items."""
        self._highlight_color = color
        for item in self.childItems():
            if hasattr(item, 'set_highlight'):
                item.set_highlight(color)

    def boundingRect(self) -> QRectF:
        """Return bounding rectangle."""
        return self.childrenBoundingRect()
