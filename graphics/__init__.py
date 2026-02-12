"""
Graphics subsystem for PyXSchem.

This package provides Qt/PySide6-based rendering for schematics:
- SchematicCanvas: QGraphicsView-based canvas with zoom/pan
- Layer management with xschem-compatible colors
- QGraphicsItem subclasses for all primitive types
- Text rendering with rotation and alignment
- Selection and interaction handling
"""

from pyxschem.graphics.layers import (
    LayerManager,
    LayerStyle,
    FillStyle,
    CADLAYERS,
    BACKLAYER,
    WIRELAYER,
    GRIDLAYER,
    SELLAYER,
    TEXTLAYER,
    SYMLAYER,
    PINLAYER,
)
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
from pyxschem.graphics.renderer import SchematicRenderer

__all__ = [
    # Layer management
    "LayerManager",
    "LayerStyle",
    "FillStyle",
    "CADLAYERS",
    "BACKLAYER",
    "WIRELAYER",
    "GRIDLAYER",
    "SELLAYER",
    "TEXTLAYER",
    "SYMLAYER",
    "PINLAYER",
    # Canvas
    "SchematicCanvas",
    "SchematicScene",
    # Items
    "WireItem",
    "LineItem",
    "RectItem",
    "ArcItem",
    "PolygonItem",
    "TextItem",
    "InstanceItem",
    # Renderer
    "SchematicRenderer",
]
