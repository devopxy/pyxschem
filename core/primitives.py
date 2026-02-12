"""
Primitive graphical elements for schematics.

This module defines all the basic drawing primitives used in xschem files:
- Wire: Electrical connection between components
- Line: Non-electrical line for drawing
- Rect: Rectangle/box primitive
- Arc: Arc or circle
- Polygon: Multi-point polygon
- Text: Text annotation

All primitives use dataclasses for clean, type-hinted data structures.
"""

from dataclasses import dataclass, field
from enum import IntFlag, auto
from typing import Optional, List
import numpy as np
from numpy.typing import NDArray


# Layer constants (matching xschem.h)
BACKLAYER = 0
WIRELAYER = 1
GRIDLAYER = 2
TEXTLAYER = 3
SYMLAYER = 4
PINLAYER = 5
SELLAYER = 6
PROPERTYLAYER = 7
# Additional layers up to 40+ are available


class SelectionState(IntFlag):
    """Selection state flags for graphical objects."""
    NONE = 0
    SELECTED = auto()      # Object is selected
    SELECTED1 = auto()     # First point selected (for wires/lines)
    SELECTED2 = auto()     # Second point selected
    SELECTED3 = auto()     # Third point (polygons)
    SELECTED4 = auto()     # Fourth point


class TextFlags(IntFlag):
    """Text formatting flags."""
    NONE = 0
    BOLD = auto()
    ITALIC = auto()
    OBLIQUE = auto()


@dataclass
class Wire:
    """
    Electrical wire connecting components.

    Wires are always on WIRELAYER and represent electrical connections.
    They can be assigned node names during netlisting.

    Attributes:
        x1, y1: First endpoint coordinates
        x2, y2: Second endpoint coordinates
        node: Assigned net name after netlisting (e.g., "VDD", "#net0")
        prop_ptr: Property string (e.g., "lab=CLK bus=1")
        bus: Bus width multiplier for thick bus lines
        sel: Selection state
        end1, end2: Connection status at endpoints (-1 = unconnected)
    """
    x1: float
    y1: float
    x2: float
    y2: float
    node: Optional[str] = None
    prop_ptr: Optional[str] = None
    bus: float = 1.0
    sel: SelectionState = SelectionState.NONE
    end1: int = -1
    end2: int = -1

    @property
    def bbox(self) -> tuple[float, float, float, float]:
        """Return bounding box (x1, y1, x2, y2) with x1 <= x2, y1 <= y2."""
        return (
            min(self.x1, self.x2),
            min(self.y1, self.y2),
            max(self.x1, self.x2),
            max(self.y1, self.y2),
        )

    @property
    def is_horizontal(self) -> bool:
        """Check if wire is horizontal."""
        return abs(self.y2 - self.y1) < 1e-9

    @property
    def is_vertical(self) -> bool:
        """Check if wire is vertical."""
        return abs(self.x2 - self.x1) < 1e-9

    def length(self) -> float:
        """Calculate wire length."""
        dx = self.x2 - self.x1
        dy = self.y2 - self.y1
        return (dx * dx + dy * dy) ** 0.5


@dataclass
class Line:
    """
    Non-electrical line for drawing.

    Lines are purely graphical elements on a specific layer.
    They don't participate in netlisting.

    Attributes:
        x1, y1: First endpoint coordinates
        x2, y2: Second endpoint coordinates
        prop_ptr: Property string
        dash: Dash pattern (0 = solid, >0 = dash length)
        bus: Line width multiplier
        sel: Selection state
    """
    x1: float
    y1: float
    x2: float
    y2: float
    prop_ptr: Optional[str] = None
    dash: int = 0
    bus: float = 1.0
    sel: SelectionState = SelectionState.NONE

    @property
    def bbox(self) -> tuple[float, float, float, float]:
        """Return bounding box."""
        return (
            min(self.x1, self.x2),
            min(self.y1, self.y2),
            max(self.x1, self.x2),
            max(self.y1, self.y2),
        )


@dataclass
class Rect:
    """
    Rectangle/box primitive.

    Rectangles can be used for symbol pins (on PINLAYER), graphs,
    images, or general drawing.

    Attributes:
        x1, y1: First corner coordinates
        x2, y2: Opposite corner coordinates
        prop_ptr: Property string (e.g., "name=A dir=in")
        fill: Fill mode (0=none, 1=stipple, 2=solid)
        dash: Outline dash pattern
        bus: Line width multiplier
        ellipse_a, ellipse_b: Ellipse arc parameters (for rounded corners)
        flags: Special flags (bit0=graph, bit1=unlocked_x, bit10=image)
        extra_ptr: Extra data (e.g., embedded image reference)
        sel: Selection state
    """
    x1: float
    y1: float
    x2: float
    y2: float
    prop_ptr: Optional[str] = None
    fill: int = 0
    dash: int = 0
    bus: float = 1.0
    ellipse_a: int = 0
    ellipse_b: int = 0
    flags: int = 0
    extra_ptr: object = None
    sel: SelectionState = SelectionState.NONE

    @property
    def bbox(self) -> tuple[float, float, float, float]:
        """Return normalized bounding box."""
        return (
            min(self.x1, self.x2),
            min(self.y1, self.y2),
            max(self.x1, self.x2),
            max(self.y1, self.y2),
        )

    @property
    def width(self) -> float:
        """Rectangle width."""
        return abs(self.x2 - self.x1)

    @property
    def height(self) -> float:
        """Rectangle height."""
        return abs(self.y2 - self.y1)

    @property
    def center(self) -> tuple[float, float]:
        """Rectangle center point."""
        return ((self.x1 + self.x2) / 2, (self.y1 + self.y2) / 2)

    @property
    def is_graph(self) -> bool:
        """Check if this rect is a graph container."""
        return bool(self.flags & 1)

    @property
    def is_image(self) -> bool:
        """Check if this rect is an image container."""
        return bool(self.flags & (1 << 10))


@dataclass
class Arc:
    """
    Arc or circle primitive.

    Arcs are defined by center, radius, start angle, and arc angle.
    A full circle has a = 0, b = 360.

    Attributes:
        x, y: Center coordinates
        r: Radius
        a: Start angle in degrees (0 = right, counterclockwise)
        b: Arc angle in degrees
        prop_ptr: Property string
        fill: Fill mode (0=none, 1=stipple, 2=solid)
        dash: Outline dash pattern
        bus: Line width multiplier
        sel: Selection state
    """
    x: float
    y: float
    r: float
    a: float
    b: float
    prop_ptr: Optional[str] = None
    fill: int = 0
    dash: int = 0
    bus: float = 1.0
    sel: SelectionState = SelectionState.NONE

    @property
    def bbox(self) -> tuple[float, float, float, float]:
        """Return bounding box (conservative, uses full circle)."""
        return (
            self.x - self.r,
            self.y - self.r,
            self.x + self.r,
            self.y + self.r,
        )

    @property
    def is_circle(self) -> bool:
        """Check if this arc is a full circle."""
        return abs(self.b) >= 360.0


@dataclass
class Polygon:
    """
    Multi-point polygon.

    Polygons are defined by arrays of x and y coordinates.
    Uses NumPy arrays for efficient storage and operations.

    Attributes:
        x: Array of x coordinates
        y: Array of y coordinates
        selected_point: Array of selection flags per point
        prop_ptr: Property string
        fill: Fill mode (0=none, 1=stipple, 2=solid)
        dash: Outline dash pattern
        bus: Line width multiplier
        sel: Selection state
    """
    x: NDArray[np.float64] = field(default_factory=lambda: np.array([], dtype=np.float64))
    y: NDArray[np.float64] = field(default_factory=lambda: np.array([], dtype=np.float64))
    selected_point: NDArray[np.uint16] = field(
        default_factory=lambda: np.array([], dtype=np.uint16)
    )
    prop_ptr: Optional[str] = None
    fill: int = 0
    dash: int = 0
    bus: float = 1.0
    sel: SelectionState = SelectionState.NONE

    @property
    def points(self) -> int:
        """Number of points in the polygon."""
        return len(self.x)

    @property
    def bbox(self) -> tuple[float, float, float, float]:
        """Return bounding box."""
        if len(self.x) == 0:
            return (0.0, 0.0, 0.0, 0.0)
        return (
            float(np.min(self.x)),
            float(np.min(self.y)),
            float(np.max(self.x)),
            float(np.max(self.y)),
        )

    @classmethod
    def from_points(cls, points: List[tuple[float, float]], **kwargs) -> "Polygon":
        """Create polygon from list of (x, y) tuples."""
        x = np.array([p[0] for p in points], dtype=np.float64)
        y = np.array([p[1] for p in points], dtype=np.float64)
        return cls(x=x, y=y, **kwargs)


@dataclass
class Text:
    """
    Text annotation element.

    Text elements display text at a specified position with rotation,
    flip, and scaling options.

    Attributes:
        txt_ptr: The text content to display
        x0, y0: Anchor position
        rot: Rotation (0, 1, 2, 3 = 0, 90, 180, 270 degrees)
        flip: Horizontal flip (0 or 1)
        xscale, yscale: Text scale factors
        prop_ptr: Property string (e.g., "layer=3 hcenter=true")
        hcenter: Horizontal centering (0=left, 1=center, 2=right)
        vcenter: Vertical centering (0=bottom, 1=center, 2=top)
        layer: Display layer (default TEXTLAYER)
        font: Font name (None = default)
        flags: Text formatting flags (bold, italic, oblique)
        floater_instname: For floater texts, the instance name to follow
        sel: Selection state
    """
    txt_ptr: str
    x0: float
    y0: float
    rot: int = 0
    flip: int = 0
    xscale: float = 1.0
    yscale: float = 1.0
    prop_ptr: Optional[str] = None
    hcenter: int = 0
    vcenter: int = 0
    layer: int = TEXTLAYER
    font: Optional[str] = None
    flags: TextFlags = TextFlags.NONE
    floater_instname: Optional[str] = None
    sel: SelectionState = SelectionState.NONE

    @property
    def rotation_degrees(self) -> float:
        """Get rotation in degrees."""
        return self.rot * 90.0

    @property
    def is_bold(self) -> bool:
        """Check if text is bold."""
        return bool(self.flags & TextFlags.BOLD)

    @property
    def is_italic(self) -> bool:
        """Check if text is italic."""
        return bool(self.flags & TextFlags.ITALIC)
