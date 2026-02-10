"""
Layer management for PyXSchem.

Provides xschem-compatible layer colors and styles for both
light and dark color schemes.
"""

from dataclasses import dataclass, field
from typing import List, Optional, Tuple
from enum import IntEnum

try:
    from PySide6.QtCore import Qt
    from PySide6.QtGui import QColor, QPen, QBrush
except ImportError:
    # Fallback for when PySide6 is not installed
    QColor = None
    QPen = None
    QBrush = None
    Qt = None


# Layer constants matching xschem.h
BACKLAYER = 0
WIRELAYER = 1
GRIDLAYER = 2
SELLAYER = 2  # Selection layer (same as grid)
PROPERTYLAYER = 1
TEXTLAYER = 3
TEXTWIRELAYER = 1  # Color for wire name labels/pins
SYMLAYER = 4
PINLAYER = 5
GENERICLAYER = 3

# Default number of layers
CADLAYERS = 22


class FillStyle(IntEnum):
    """Fill styles for rectangles, arcs, and polygons."""
    NONE = 0
    STIPPLE = 1
    SOLID = 2


@dataclass
class LayerStyle:
    """
    Style information for a single layer.

    Attributes:
        color: RGB hex color string (e.g., "#ff0000")
        qcolor: QColor object (created from color)
        line_width: Default line width for this layer
        visible: Whether layer is visible
        selectable: Whether objects on this layer can be selected
    """
    color: str
    line_width: float = 1.0
    visible: bool = True
    selectable: bool = True
    _qcolor: Optional[object] = field(default=None, repr=False)

    @property
    def qcolor(self) -> Optional[object]:
        """Get QColor object for this layer."""
        if QColor is None:
            return None
        if self._qcolor is None:
            self._qcolor = QColor(self.color)
        return self._qcolor

    def get_pen(self, width: float = None, dash: int = 0) -> Optional[object]:
        """
        Create a QPen for this layer.

        Args:
            width: Line width (uses layer default if None)
            dash: Dash pattern (0 = solid)

        Returns:
            QPen configured for this layer
        """
        if QPen is None or Qt is None:
            return None

        pen = QPen(self.qcolor)
        pen.setWidthF(width if width is not None else self.line_width)
        pen.setCapStyle(Qt.FlatCap)
        pen.setJoinStyle(Qt.BevelJoin)

        if dash > 0:
            pen.setStyle(Qt.DashLine)
            # Could customize dash pattern based on dash value
        else:
            pen.setStyle(Qt.SolidLine)

        return pen

    def get_brush(self, fill: int = FillStyle.NONE) -> Optional[object]:
        """
        Create a QBrush for this layer.

        Args:
            fill: Fill style (0=none, 1=stipple, 2=solid)

        Returns:
            QBrush configured for this layer
        """
        if QBrush is None or Qt is None:
            return None

        if fill == FillStyle.NONE:
            return QBrush(Qt.NoBrush)
        elif fill == FillStyle.STIPPLE:
            brush = QBrush(self.qcolor, Qt.Dense4Pattern)
            return brush
        else:  # SOLID
            return QBrush(self.qcolor, Qt.SolidPattern)


# Default dark color scheme (matching xschem dark_colors)
DARK_COLORS = [
    "#000000",  # 0: BACKLAYER - Background
    "#00ddff",  # 1: WIRELAYER - Wires (cyan)
    "#4f4f4f",  # 2: GRIDLAYER/SELLAYER - Grid/Selection (dark gray)
    "#cccccc",  # 3: TEXTLAYER - Text (light gray)
    "#88dd00",  # 4: SYMLAYER - Symbol shapes (green)
    "#bb2200",  # 5: PINLAYER - Pins (red-brown)
    "#00aaff",  # 6: Blue
    "#ff0000",  # 7: Red
    "#ffff00",  # 8: Yellow
    "#ffffff",  # 9: White
    "#ff00ff",  # 10: Magenta
    "#00ff00",  # 11: Bright green
    "#0044ff",  # 12: Dark blue
    "#aaaa00",  # 13: Dark yellow
    "#aaccaa",  # 14: Light green
    "#ff7777",  # 15: Light red
    "#bfff81",  # 16: Light yellow-green
    "#00ffcc",  # 17: Cyan-green
    "#ce0097",  # 18: Purple
    "#d2d46b",  # 19: Olive
    "#ef6158",  # 20: Salmon
    "#fdb200",  # 21: Orange
]

# Default light color scheme (matching xschem light_colors)
LIGHT_COLORS = [
    "#ffffff",  # 0: BACKLAYER - Background (white)
    "#0099cc",  # 1: WIRELAYER - Wires (teal)
    "#aaaaaa",  # 2: GRIDLAYER/SELLAYER - Grid/Selection (gray)
    "#222222",  # 3: TEXTLAYER - Text (dark gray)
    "#229900",  # 4: SYMLAYER - Symbol shapes (green)
    "#bb2200",  # 5: PINLAYER - Pins (red-brown)
    "#0066cc",  # 6: Blue
    "#ff0000",  # 7: Red
    "#888800",  # 8: Dark yellow
    "#00aaaa",  # 9: Teal
    "#880088",  # 10: Purple
    "#00ff00",  # 11: Bright green
    "#0000cc",  # 12: Dark blue
    "#666600",  # 13: Olive
    "#557755",  # 14: Gray-green
    "#aa2222",  # 15: Dark red
    "#7ccc40",  # 16: Yellow-green
    "#00ffcc",  # 17: Cyan-green
    "#ce0097",  # 18: Purple
    "#d2d46b",  # 19: Olive
    "#ef6158",  # 20: Salmon
    "#fdb200",  # 21: Orange
]


class LayerManager:
    """
    Manages layer colors and styles for the schematic canvas.

    Provides access to layer colors, pens, and brushes for drawing
    schematic elements. Supports both light and dark color schemes.
    """

    def __init__(self, dark_scheme: bool = True, num_layers: int = CADLAYERS):
        """
        Initialize layer manager.

        Args:
            dark_scheme: Use dark color scheme if True, light if False
            num_layers: Number of layers to manage
        """
        self._dark_scheme = dark_scheme
        self._num_layers = num_layers
        self._layers: List[LayerStyle] = []
        self._selection_color = "#ff8800"  # Orange for selection
        self._build_layers()

    def _build_layers(self) -> None:
        """Build layer styles from color scheme."""
        colors = DARK_COLORS if self._dark_scheme else LIGHT_COLORS
        self._layers = []

        for i in range(self._num_layers):
            if i < len(colors):
                color = colors[i]
            else:
                # Cycle through colors for additional layers
                color = colors[i % len(colors)]

            # Set default line widths
            if i == WIRELAYER:
                line_width = 2.0
            elif i == PINLAYER:
                line_width = 1.5
            else:
                line_width = 1.0

            self._layers.append(LayerStyle(
                color=color,
                line_width=line_width,
            ))

    @property
    def dark_scheme(self) -> bool:
        """Whether using dark color scheme."""
        return self._dark_scheme

    @dark_scheme.setter
    def dark_scheme(self, value: bool) -> None:
        """Set color scheme and rebuild layers."""
        if value != self._dark_scheme:
            self._dark_scheme = value
            self._build_layers()

    @property
    def background_color(self) -> str:
        """Get background color."""
        return self._layers[BACKLAYER].color

    @property
    def background_qcolor(self) -> Optional[object]:
        """Get background QColor."""
        return self._layers[BACKLAYER].qcolor

    @property
    def grid_color(self) -> str:
        """Get grid color."""
        return self._layers[GRIDLAYER].color

    @property
    def selection_color(self) -> str:
        """Get selection highlight color."""
        return self._selection_color

    @property
    def selection_qcolor(self) -> Optional[object]:
        """Get selection QColor."""
        if QColor is None:
            return None
        return QColor(self._selection_color)

    def get_layer(self, layer: int) -> LayerStyle:
        """
        Get style for a specific layer.

        Args:
            layer: Layer index

        Returns:
            LayerStyle for the specified layer
        """
        if 0 <= layer < len(self._layers):
            return self._layers[layer]
        return self._layers[0]  # Fallback to background

    def get_color(self, layer: int) -> str:
        """Get color string for a layer."""
        return self.get_layer(layer).color

    def get_qcolor(self, layer: int) -> Optional[object]:
        """Get QColor for a layer."""
        return self.get_layer(layer).qcolor

    def get_pen(self, layer: int, width: float = None, dash: int = 0) -> Optional[object]:
        """Get QPen for a layer."""
        return self.get_layer(layer).get_pen(width, dash)

    def get_brush(self, layer: int, fill: int = FillStyle.NONE) -> Optional[object]:
        """Get QBrush for a layer."""
        return self.get_layer(layer).get_brush(fill)

    def get_selection_pen(self, width: float = 2.0) -> Optional[object]:
        """Get pen for selection highlighting."""
        if QPen is None or Qt is None:
            return None
        pen = QPen(self.selection_qcolor)
        pen.setWidthF(width)
        pen.setStyle(Qt.DashLine)
        return pen

    def set_layer_visible(self, layer: int, visible: bool) -> None:
        """Set visibility for a layer."""
        if 0 <= layer < len(self._layers):
            self._layers[layer].visible = visible

    def is_layer_visible(self, layer: int) -> bool:
        """Check if a layer is visible."""
        if 0 <= layer < len(self._layers):
            return self._layers[layer].visible
        return True

    def __len__(self) -> int:
        """Number of layers."""
        return len(self._layers)

    def __getitem__(self, layer: int) -> LayerStyle:
        """Get layer style by index."""
        return self.get_layer(layer)
