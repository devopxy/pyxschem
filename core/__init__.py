"""
Core data models for PyXSchem.

This module contains all the fundamental data structures used throughout
the application, including primitives, symbols, instances, and the main
schematic context.
"""

from pyxschem.core.primitives import (
    SelectionState,
    Wire,
    Line,
    Rect,
    Arc,
    Polygon,
    Text,
    BACKLAYER,
    WIRELAYER,
    GRIDLAYER,
    TEXTLAYER,
    SYMLAYER,
    PINLAYER,
)
from pyxschem.core.symbol import Symbol, Instance, InstanceFlags
from pyxschem.core.context import SchematicContext, ViewState
from pyxschem.core.spatial_hash import (
    SpatialHashTable,
    TypedSpatialHashTable,
    ObjectType,
    HashEntry,
    boxes_overlap,
    point_in_box,
    BOXSIZE,
    NBOXES,
)

__all__ = [
    "SelectionState",
    "Wire",
    "Line",
    "Rect",
    "Arc",
    "Polygon",
    "Text",
    "Symbol",
    "Instance",
    "InstanceFlags",
    "SchematicContext",
    "ViewState",
    "BACKLAYER",
    "WIRELAYER",
    "GRIDLAYER",
    "TEXTLAYER",
    "SYMLAYER",
    "PINLAYER",
    "SpatialHashTable",
    "TypedSpatialHashTable",
    "ObjectType",
    "HashEntry",
    "boxes_overlap",
    "point_in_box",
    "BOXSIZE",
    "NBOXES",
]
