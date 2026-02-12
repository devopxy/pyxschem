"""
Symbol and Instance classes for PyXSchem.

Symbols are reusable component definitions loaded from .sym files.
Instances are placed occurrences of symbols in a schematic.
"""

from dataclasses import dataclass, field
from enum import IntFlag, auto
from typing import Optional, List, Dict

from pyxschem.core.primitives import (
    SelectionState,
    Line,
    Rect,
    Arc,
    Polygon,
    Text,
    PINLAYER,
)


class InstanceFlags(IntFlag):
    """Flags for instances and symbols."""
    NONE = 0
    EMBEDDED = auto()           # Symbol is embedded in schematic
    PIN_OR_LABEL = auto()       # Is a pin or label symbol
    HILIGHT_CONN = auto()       # Highlight connected nets
    HIDE_INST = auto()          # Hide instance in schematic
    SPICE_IGNORE = auto()       # Ignore in SPICE netlist
    VERILOG_IGNORE = auto()     # Ignore in Verilog netlist
    VHDL_IGNORE = auto()        # Ignore in VHDL netlist
    TEDAX_IGNORE = auto()       # Ignore in tEDAx netlist
    SPECTRE_IGNORE = auto()     # Ignore in Spectre netlist
    IGNORE_INST = auto()        # Ignore instance
    HIDE_SYMBOL_TEXTS = auto()  # Hide symbol texts
    LVS_IGNORE_SHORT = auto()   # Ignore shorts in LVS
    LVS_IGNORE_OPEN = auto()    # Ignore opens in LVS
    SPICE_SHORT = auto()        # Short all pins in SPICE


class SymbolType:
    """Symbol type identifiers matching xschem conventions."""
    SUBCIRCUIT = "subcircuit"
    PRIMITIVE = "primitive"
    LABEL = "label"
    IPIN = "ipin"
    OPIN = "opin"
    IOPIN = "iopin"
    NETLIST_COMMANDS = "netlist_commands"
    NOCONN = "noconn"
    PROBE = "probe"
    BUS_TAP = "bus_tap"
    LAUNCHER = "launcher"


@dataclass
class Symbol:
    """
    Symbol definition loaded from a .sym file.

    A symbol contains graphical elements (lines, rects, arcs, polygons, text)
    organized by layer, plus metadata like type and template properties.

    Attributes:
        name: Symbol file path (e.g., "devices/resistor.sym")
        base_name: Base name without path for virtual symbols
        minx, miny, maxx, maxy: Bounding box coordinates
        lines: Lines per layer {layer: [Line, ...]}
        rects: Rectangles per layer (pins are on PINLAYER)
        arcs: Arcs per layer
        polygons: Polygons per layer
        texts: Text annotations
        prop_ptr: Symbol properties string
        type: Symbol type (subcircuit, primitive, label, etc.)
        templ: Template string with default properties
        flags: Symbol flags
    """
    name: str
    base_name: Optional[str] = None
    minx: float = 0.0
    miny: float = 0.0
    maxx: float = 0.0
    maxy: float = 0.0

    # Per-layer graphical elements
    lines: Dict[int, List[Line]] = field(default_factory=dict)
    rects: Dict[int, List[Rect]] = field(default_factory=dict)
    arcs: Dict[int, List[Arc]] = field(default_factory=dict)
    polygons: Dict[int, List[Polygon]] = field(default_factory=dict)
    texts: List[Text] = field(default_factory=list)

    # Properties
    prop_ptr: Optional[str] = None
    type: Optional[str] = None
    templ: Optional[str] = None
    parent_prop_ptr: Optional[str] = None
    flags: InstanceFlags = InstanceFlags.NONE

    # Format strings for netlisting
    format: Optional[str] = None
    verilog_format: Optional[str] = None
    vhdl_format: Optional[str] = None
    spectre_format: Optional[str] = None
    tedax_format: Optional[str] = None

    @property
    def bbox(self) -> tuple[float, float, float, float]:
        """Return symbol bounding box."""
        return (self.minx, self.miny, self.maxx, self.maxy)

    @property
    def width(self) -> float:
        """Symbol width."""
        return self.maxx - self.minx

    @property
    def height(self) -> float:
        """Symbol height."""
        return self.maxy - self.miny

    @property
    def pins(self) -> List[Rect]:
        """Get all pin rectangles from PINLAYER."""
        return self.rects.get(PINLAYER, [])

    @property
    def pin_count(self) -> int:
        """Number of pins in this symbol."""
        return len(self.pins)

    def get_pin_names(self) -> List[str]:
        """Extract pin names from PINLAYER rectangles."""
        from pyxschem.core.property_parser import get_tok_value
        names = []
        for pin in self.pins:
            if pin.prop_ptr:
                name = get_tok_value(pin.prop_ptr, "name")
                names.append(name if name else "")
            else:
                names.append("")
        return names

    def calculate_bbox(self) -> None:
        """Recalculate bounding box from all elements."""
        all_x: List[float] = []
        all_y: List[float] = []

        for layer_lines in self.lines.values():
            for line in layer_lines:
                all_x.extend([line.x1, line.x2])
                all_y.extend([line.y1, line.y2])

        for layer_rects in self.rects.values():
            for rect in layer_rects:
                all_x.extend([rect.x1, rect.x2])
                all_y.extend([rect.y1, rect.y2])

        for layer_arcs in self.arcs.values():
            for arc in layer_arcs:
                all_x.extend([arc.x - arc.r, arc.x + arc.r])
                all_y.extend([arc.y - arc.r, arc.y + arc.r])

        for layer_polys in self.polygons.values():
            for poly in layer_polys:
                if poly.points > 0:
                    all_x.extend(poly.x.tolist())
                    all_y.extend(poly.y.tolist())

        for text in self.texts:
            all_x.append(text.x0)
            all_y.append(text.y0)

        if all_x and all_y:
            self.minx = min(all_x)
            self.maxx = max(all_x)
            self.miny = min(all_y)
            self.maxy = max(all_y)

    def is_pin_or_label(self) -> bool:
        """Check if symbol is a pin or label type."""
        return self.type in (
            SymbolType.IPIN,
            SymbolType.OPIN,
            SymbolType.IOPIN,
            SymbolType.LABEL,
        )


@dataclass
class Instance:
    """
    Placed instance of a symbol in a schematic.

    Instances reference a symbol and have their own position, rotation,
    flip state, and properties. During netlisting, each instance gets
    node assignments for its pins.

    Attributes:
        name: Symbol reference path (e.g., "devices/resistor.sym")
        ptr: Index into the symbols array
        x0, y0: Instance origin position
        x1, y1, x2, y2: Transformed bounding box
        rot: Rotation (0, 1, 2, 3 = 0, 90, 180, 270 degrees)
        flip: Horizontal flip (0 or 1)
        prop_ptr: Instance properties string
        embed: True if symbol is embedded in schematic
        color: Highlight color index (-1 = none)
        flags: Instance flags
        node: Per-pin node name assignments
        lab: Label attribute (for pin/label symbols)
        instname: Instance name (e.g., "R1", "M1", "X1")
        sel: Selection state
    """
    name: str
    ptr: int = -1
    x0: float = 0.0
    y0: float = 0.0
    x1: float = 0.0
    y1: float = 0.0
    x2: float = 0.0
    y2: float = 0.0
    rot: int = 0
    flip: int = 0
    prop_ptr: Optional[str] = None
    embed: bool = False
    color: int = -1
    flags: InstanceFlags = InstanceFlags.NONE
    node: Optional[List[Optional[str]]] = None
    lab: Optional[str] = None
    instname: Optional[str] = None
    sel: SelectionState = SelectionState.NONE

    # Embedded symbol definition (if embed=True)
    embedded_symbol: Optional[Symbol] = None

    @property
    def bbox(self) -> tuple[float, float, float, float]:
        """Return instance bounding box."""
        return (
            min(self.x1, self.x2),
            min(self.y1, self.y2),
            max(self.x1, self.x2),
            max(self.y1, self.y2),
        )

    @property
    def rotation_degrees(self) -> float:
        """Get rotation in degrees."""
        return self.rot * 90.0

    def init_nodes(self, pin_count: int) -> None:
        """Initialize node array for the given pin count."""
        self.node = [None] * pin_count

    def get_node(self, pin_index: int) -> Optional[str]:
        """Get node name for a specific pin."""
        if self.node is None or pin_index >= len(self.node):
            return None
        return self.node[pin_index]

    def set_node(self, pin_index: int, node_name: str) -> None:
        """Set node name for a specific pin."""
        if self.node is None:
            raise ValueError("Node array not initialized")
        if pin_index < len(self.node):
            self.node[pin_index] = node_name

    def calculate_bbox(self, symbol: Symbol) -> None:
        """
        Calculate transformed bounding box from symbol.

        Applies rotation and flip transforms to symbol bbox
        and translates to instance position.
        """
        sx1, sy1, sx2, sy2 = symbol.bbox

        # Apply flip
        if self.flip:
            sx1, sx2 = -sx2, -sx1

        # Apply rotation
        rot = self.rot % 4
        if rot == 1:  # 90 degrees
            sx1, sy1, sx2, sy2 = -sy2, sx1, -sy1, sx2
        elif rot == 2:  # 180 degrees
            sx1, sy1, sx2, sy2 = -sx2, -sy2, -sx1, -sy1
        elif rot == 3:  # 270 degrees
            sx1, sy1, sx2, sy2 = sy1, -sx2, sy2, -sx1

        # Translate to instance position
        self.x1 = self.x0 + sx1
        self.y1 = self.y0 + sy1
        self.x2 = self.x0 + sx2
        self.y2 = self.y0 + sy2
