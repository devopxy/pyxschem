"""
QGraphicsView-based schematic canvas for PyXSchem.

Provides a high-performance canvas for viewing and editing schematics
with smooth zoom/pan, grid display, and rubber-band selection.
"""

from typing import Optional, Tuple, Callable, List
import math

from PySide6.QtCore import Qt, QRectF, QPointF, Signal, QLineF
from PySide6.QtGui import (
    QPainter,
    QPen,
    QBrush,
    QColor,
    QWheelEvent,
    QMouseEvent,
    QKeyEvent,
    QTransform,
)
from PySide6.QtWidgets import (
    QGraphicsView,
    QGraphicsScene,
    QGraphicsRectItem,
    QRubberBand,
)

from pyxschem.graphics.layers import LayerManager, GRIDLAYER


class SchematicScene(QGraphicsScene):
    """
    QGraphicsScene for schematic content.

    Manages all graphical items and provides efficient spatial indexing
    through Qt's built-in BSP tree.
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        # Set a large scene rect to allow unlimited panning
        self.setSceneRect(-1e6, -1e6, 2e6, 2e6)

        # Use BSP tree for efficient item lookup
        self.setItemIndexMethod(QGraphicsScene.BspTreeIndex)

    def clear_schematic(self) -> None:
        """Clear all schematic items from the scene."""
        self.clear()


class SchematicCanvas(QGraphicsView):
    """
    Main schematic canvas widget based on QGraphicsView.

    Features:
    - Smooth zoom with mouse wheel (centered on cursor)
    - Pan with middle mouse button or Ctrl+drag
    - Grid display with automatic level-of-detail
    - Rubber-band selection
    - Coordinate tracking

    Signals:
        zoom_changed: Emitted when zoom level changes (zoom_factor)
        cursor_moved: Emitted when cursor moves (world_x, world_y)
        selection_changed: Emitted when selection changes
    """

    zoom_changed = Signal(float)
    cursor_moved = Signal(float, float)
    selection_changed = Signal()

    # Zoom limits
    MIN_ZOOM = 0.001
    MAX_ZOOM = 100.0
    ZOOM_FACTOR = 1.15  # Zoom step per wheel notch

    # Grid settings
    GRID_SPACING = 20.0  # Base grid spacing in schematic units
    SNAP_SPACING = 10.0  # Snap grid spacing

    def __init__(self, parent=None, layer_manager: LayerManager = None):
        super().__init__(parent)

        # Create scene
        self._scene = SchematicScene(self)
        self.setScene(self._scene)

        # Layer manager
        self._layers = layer_manager or LayerManager(dark_scheme=True)

        # View state
        self._zoom = 1.0
        self._panning = False
        self._pan_start = QPointF()
        self._last_pan_pos = QPointF()

        # Grid
        self._show_grid = True
        self._grid_spacing = self.GRID_SPACING
        self._snap_to_grid = True
        self._snap_spacing = self.SNAP_SPACING

        # Selection
        self._rubber_band: Optional[QRubberBand] = None
        self._selection_start = QPointF()
        self._selecting = False

        # Configure view
        self._setup_view()

    def _setup_view(self) -> None:
        """Configure QGraphicsView settings for optimal performance."""
        # Rendering hints
        self.setRenderHint(QPainter.Antialiasing, True)
        self.setRenderHint(QPainter.SmoothPixmapTransform, True)
        self.setRenderHint(QPainter.TextAntialiasing, True)

        # Optimization settings
        self.setViewportUpdateMode(QGraphicsView.SmartViewportUpdate)
        self.setCacheMode(QGraphicsView.CacheBackground)
        self.setOptimizationFlag(QGraphicsView.DontAdjustForAntialiasing, True)

        # Scrollbar policy - we handle panning ourselves
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)

        # Enable mouse tracking for cursor position updates
        self.setMouseTracking(True)

        # Transform settings
        self.setTransformationAnchor(QGraphicsView.NoAnchor)
        self.setResizeAnchor(QGraphicsView.NoAnchor)

        # Set background color
        self._update_background()

        # Drag mode
        self.setDragMode(QGraphicsView.NoDrag)

    def _update_background(self) -> None:
        """Update background color from layer manager."""
        bg_color = self._layers.background_qcolor
        if bg_color:
            self.setBackgroundBrush(QBrush(bg_color))

    @property
    def layer_manager(self) -> LayerManager:
        """Get the layer manager."""
        return self._layers

    @layer_manager.setter
    def layer_manager(self, manager: LayerManager) -> None:
        """Set the layer manager and update display."""
        self._layers = manager
        self._update_background()
        self.viewport().update()

    @property
    def zoom(self) -> float:
        """Current zoom factor (1.0 = 100%)."""
        return self._zoom

    @property
    def show_grid(self) -> bool:
        """Whether grid is displayed."""
        return self._show_grid

    @show_grid.setter
    def show_grid(self, value: bool) -> None:
        """Set grid visibility."""
        self._show_grid = value
        self.resetCachedContent()
        self.viewport().update()

    @property
    def snap_to_grid(self) -> bool:
        """Whether snap-to-grid is enabled."""
        return self._snap_to_grid

    @snap_to_grid.setter
    def snap_to_grid(self, value: bool) -> None:
        """Set snap-to-grid mode."""
        self._snap_to_grid = value

    def screen_to_world(self, screen_pos: QPointF) -> QPointF:
        """Convert screen coordinates to world (schematic) coordinates."""
        return self.mapToScene(screen_pos.toPoint())

    def world_to_screen(self, world_pos: QPointF) -> QPointF:
        """Convert world coordinates to screen coordinates."""
        return self.mapFromScene(world_pos)

    def snap_point(self, point: QPointF) -> QPointF:
        """
        Snap a point to the grid if snap is enabled.

        Args:
            point: Point in world coordinates

        Returns:
            Snapped point in world coordinates
        """
        if not self._snap_to_grid:
            return point

        snap = self._snap_spacing
        x = round(point.x() / snap) * snap
        y = round(point.y() / snap) * snap
        return QPointF(x, y)

    def set_zoom(self, zoom: float, center: QPointF = None) -> None:
        """
        Set zoom level.

        Args:
            zoom: New zoom factor (1.0 = 100%)
            center: Point to keep fixed (in scene coordinates)
        """
        # Clamp zoom
        zoom = max(self.MIN_ZOOM, min(self.MAX_ZOOM, zoom))

        if abs(zoom - self._zoom) < 1e-9:
            return

        # Get center point in scene coordinates
        if center is None:
            center = self.mapToScene(self.viewport().rect().center())

        # Calculate scale factor
        scale = zoom / self._zoom

        # Apply transform
        self.scale(scale, scale)
        self._zoom = zoom

        # Emit signal
        self.zoom_changed.emit(self._zoom)

        # Redraw grid with new scale
        self.resetCachedContent()

    def zoom_in(self, center: QPointF = None) -> None:
        """Zoom in by one step."""
        self.set_zoom(self._zoom * self.ZOOM_FACTOR, center)

    def zoom_out(self, center: QPointF = None) -> None:
        """Zoom out by one step."""
        self.set_zoom(self._zoom / self.ZOOM_FACTOR, center)

    def fit_in_view(self, rect: QRectF = None, margin: float = 50) -> None:
        """
        Fit the view to show all content or a specific rectangle.

        Args:
            rect: Rectangle to fit (uses scene bounding rect if None)
            margin: Margin in pixels around the content
        """
        if rect is None:
            rect = self._scene.itemsBoundingRect()

        if rect.isEmpty():
            return

        # Add margin
        rect = rect.adjusted(-margin, -margin, margin, margin)

        # Fit in view preserving aspect ratio
        self.fitInView(rect, Qt.KeepAspectRatio)

        # Calculate resulting zoom
        view_rect = self.viewport().rect()
        scale_x = view_rect.width() / rect.width()
        scale_y = view_rect.height() / rect.height()
        self._zoom = min(scale_x, scale_y)

        self.zoom_changed.emit(self._zoom)
        self.resetCachedContent()

    def center_on_point(self, point: QPointF) -> None:
        """Center the view on a point in world coordinates."""
        self.centerOn(point)

    # =========================================================================
    # Event handlers
    # =========================================================================

    def wheelEvent(self, event: QWheelEvent) -> None:
        """Handle mouse wheel for zooming."""
        # Get mouse position in scene coordinates before zoom
        mouse_scene_pos = self.mapToScene(event.position().toPoint())

        # Calculate zoom direction
        angle = event.angleDelta().y()
        if angle > 0:
            factor = self.ZOOM_FACTOR
        elif angle < 0:
            factor = 1.0 / self.ZOOM_FACTOR
        else:
            return

        # Apply zoom
        new_zoom = self._zoom * factor
        new_zoom = max(self.MIN_ZOOM, min(self.MAX_ZOOM, new_zoom))

        if abs(new_zoom - self._zoom) < 1e-9:
            return

        # Scale and adjust to keep mouse position fixed
        self.scale(factor, factor)

        # Get new mouse scene position and adjust
        new_mouse_scene_pos = self.mapToScene(event.position().toPoint())
        delta = new_mouse_scene_pos - mouse_scene_pos
        self.translate(delta.x(), delta.y())

        self._zoom = new_zoom
        self.zoom_changed.emit(self._zoom)
        self.resetCachedContent()

    def mousePressEvent(self, event: QMouseEvent) -> None:
        """Handle mouse press for pan and selection."""
        if event.button() == Qt.MiddleButton:
            # Start panning
            self._panning = True
            self._pan_start = event.position()
            self._last_pan_pos = event.position()
            self.setCursor(Qt.ClosedHandCursor)
            event.accept()

        elif event.button() == Qt.LeftButton:
            if event.modifiers() & Qt.ControlModifier:
                # Ctrl+left click = pan
                self._panning = True
                self._pan_start = event.position()
                self._last_pan_pos = event.position()
                self.setCursor(Qt.ClosedHandCursor)
                event.accept()
            else:
                # Start rubber-band selection
                self._selection_start = event.position()
                self._selecting = True
                if self._rubber_band is None:
                    self._rubber_band = QRubberBand(QRubberBand.Rectangle, self)
                self._rubber_band.setGeometry(
                    int(self._selection_start.x()),
                    int(self._selection_start.y()),
                    0, 0
                )
                self._rubber_band.show()
                event.accept()

        else:
            super().mousePressEvent(event)

    def mouseMoveEvent(self, event: QMouseEvent) -> None:
        """Handle mouse move for pan and selection."""
        # Emit cursor position
        world_pos = self.mapToScene(event.position().toPoint())
        self.cursor_moved.emit(world_pos.x(), world_pos.y())

        if self._panning:
            # Pan the view
            delta = event.position() - self._last_pan_pos
            self._last_pan_pos = event.position()

            # Translate the view
            self.translate(delta.x() / self._zoom, delta.y() / self._zoom)
            event.accept()

        elif self._selecting and self._rubber_band:
            # Update rubber band
            current = event.position()
            x = min(self._selection_start.x(), current.x())
            y = min(self._selection_start.y(), current.y())
            w = abs(current.x() - self._selection_start.x())
            h = abs(current.y() - self._selection_start.y())
            self._rubber_band.setGeometry(int(x), int(y), int(w), int(h))
            event.accept()

        else:
            super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event: QMouseEvent) -> None:
        """Handle mouse release for pan and selection."""
        if self._panning:
            self._panning = False
            self.setCursor(Qt.ArrowCursor)
            event.accept()

        elif self._selecting and self._rubber_band:
            self._selecting = False
            self._rubber_band.hide()

            # Get selection rectangle in scene coordinates
            rect = self._rubber_band.geometry()
            scene_rect = QRectF(
                self.mapToScene(rect.topLeft()),
                self.mapToScene(rect.bottomRight())
            )

            # Select items in rectangle
            if not (event.modifiers() & Qt.ShiftModifier):
                # Clear previous selection unless Shift is held
                self._scene.clearSelection()

            # Select items in the rectangle
            path = self._scene.selectionArea()
            items = self._scene.items(scene_rect, Qt.IntersectsItemShape)
            for item in items:
                if item.flags() & item.ItemIsSelectable:
                    item.setSelected(True)

            self.selection_changed.emit()
            event.accept()

        else:
            super().mouseReleaseEvent(event)

    def keyPressEvent(self, event: QKeyEvent) -> None:
        """Handle keyboard shortcuts."""
        key = event.key()

        if key == Qt.Key_F:
            # Fit all
            self.fit_in_view()
            event.accept()

        elif key == Qt.Key_Plus or key == Qt.Key_Equal:
            # Zoom in
            self.zoom_in()
            event.accept()

        elif key == Qt.Key_Minus:
            # Zoom out
            self.zoom_out()
            event.accept()

        elif key == Qt.Key_0:
            # Reset zoom to 1:1
            self.set_zoom(1.0)
            event.accept()

        elif key == Qt.Key_G:
            # Toggle grid
            self.show_grid = not self.show_grid
            event.accept()

        elif key == Qt.Key_Escape:
            # Clear selection
            self._scene.clearSelection()
            self.selection_changed.emit()
            event.accept()

        else:
            super().keyPressEvent(event)

    # =========================================================================
    # Grid drawing
    # =========================================================================

    def drawBackground(self, painter: QPainter, rect: QRectF) -> None:
        """Draw background with grid."""
        # Draw background color
        super().drawBackground(painter, rect)

        if not self._show_grid:
            return

        # Get visible area in scene coordinates
        visible_rect = self.mapToScene(self.viewport().rect()).boundingRect()

        # Calculate grid spacing based on zoom level
        # Adjust grid to stay readable at any zoom
        base_spacing = self._grid_spacing
        screen_spacing = base_spacing * self._zoom

        # Find appropriate grid level
        min_screen_spacing = 10  # Minimum pixels between grid lines
        if screen_spacing < min_screen_spacing:
            # Calculate multiplier to make grid visible
            multiplier = math.ceil(min_screen_spacing / screen_spacing)
            # Round to nice values (2, 5, 10, 20, 50, 100, ...)
            nice_values = [2, 5, 10]
            for nv in nice_values:
                if multiplier <= nv:
                    multiplier = nv
                    break
            else:
                # Use power of 10
                multiplier = 10 ** math.ceil(math.log10(multiplier))
            base_spacing *= multiplier

        # Set up pen for grid
        grid_color = self._layers.get_qcolor(GRIDLAYER)
        if grid_color is None:
            return

        pen = QPen(grid_color)
        pen.setWidthF(0)  # Cosmetic pen (1 pixel regardless of zoom)
        pen.setCosmetic(True)
        painter.setPen(pen)

        # Calculate grid bounds
        left = math.floor(visible_rect.left() / base_spacing) * base_spacing
        right = math.ceil(visible_rect.right() / base_spacing) * base_spacing
        top = math.floor(visible_rect.top() / base_spacing) * base_spacing
        bottom = math.ceil(visible_rect.bottom() / base_spacing) * base_spacing

        # Draw grid lines
        # Limit number of lines for performance
        max_lines = 200

        # Vertical lines
        x = left
        count = 0
        while x <= right and count < max_lines:
            painter.drawLine(QLineF(x, visible_rect.top(), x, visible_rect.bottom()))
            x += base_spacing
            count += 1

        # Horizontal lines
        y = top
        count = 0
        while y <= bottom and count < max_lines:
            painter.drawLine(QLineF(visible_rect.left(), y, visible_rect.right(), y))
            y += base_spacing
            count += 1

    # =========================================================================
    # Public API
    # =========================================================================

    def get_scene(self) -> SchematicScene:
        """Get the graphics scene."""
        return self._scene

    def get_selected_items(self) -> List:
        """Get list of selected items."""
        return self._scene.selectedItems()

    def clear_selection(self) -> None:
        """Clear all selected items."""
        self._scene.clearSelection()
        self.selection_changed.emit()

    def select_all(self) -> None:
        """Select all selectable items."""
        for item in self._scene.items():
            if item.flags() & item.ItemIsSelectable:
                item.setSelected(True)
        self.selection_changed.emit()

    def get_visible_rect(self) -> QRectF:
        """Get the currently visible rectangle in world coordinates."""
        return self.mapToScene(self.viewport().rect()).boundingRect()

    def set_dark_scheme(self, dark: bool) -> None:
        """Switch between dark and light color schemes."""
        self._layers.dark_scheme = dark
        self._update_background()
        self.resetCachedContent()
        self.viewport().update()
