"""
Schematic Context - Main state container for PyXSchem.

The SchematicContext holds all data for a schematic including:
- Graphical primitives (wires, lines, rects, etc.)
- Symbol definitions
- Component instances
- View state (zoom, pan)
- Spatial hash tables for efficient lookup
- Node hash table for netlisting
"""

from dataclasses import dataclass, field
from enum import IntFlag, auto
from typing import Optional, List, Dict
from pathlib import Path

from pyxschem.core.primitives import (
    Wire,
    Line,
    Rect,
    Arc,
    Polygon,
    Text,
)
from pyxschem.core.symbol import Symbol, Instance


class UIState(IntFlag):
    """UI state flags for current operation."""
    NONE = 0
    STARTWIRE = auto()        # Drawing a wire
    STARTLINE = auto()        # Drawing a line
    STARTRECT = auto()        # Drawing a rectangle
    STARTARC = auto()         # Drawing an arc
    STARTPOLYGON = auto()     # Drawing a polygon
    STARTMOVE = auto()        # Moving objects
    STARTCOPY = auto()        # Copying objects
    STARTMERGE = auto()       # Merging wires
    STARTPAN = auto()         # Panning view
    STARTZOOM = auto()        # Zoom box selection
    SELECTION = auto()        # Selection box active
    PLACE_SYMBOL = auto()     # Placing a symbol
    PLACE_TEXT = auto()       # Placing text


class NetlistType:
    """Netlist format identifiers."""
    SPICE = 1
    VHDL = 2
    VERILOG = 3
    TEDAX = 4
    SPECTRE = 5


@dataclass
class ViewState:
    """
    View transformation state.

    Controls zoom and pan for the schematic canvas.
    Uses the same coordinate system as xschem:
    - xorigin, yorigin: Pan offset in schematic coordinates
    - zoom: Schematic units per pixel (inverse of visual scale)
    - mooz: Pixels per schematic unit (1/zoom)

    Transforms:
        screen_x = (schematic_x + xorigin) * mooz
        schematic_x = screen_x * zoom - xorigin
    """
    xorigin: float = 0.0
    yorigin: float = 0.0
    zoom: float = 1.0

    @property
    def mooz(self) -> float:
        """Inverse zoom factor (pixels per schematic unit)."""
        return 1.0 / self.zoom if self.zoom != 0 else 1.0

    def screen_to_world(self, sx: float, sy: float) -> tuple[float, float]:
        """Convert screen coordinates to world (schematic) coordinates."""
        wx = sx * self.zoom - self.xorigin
        wy = sy * self.zoom - self.yorigin
        return (wx, wy)

    def world_to_screen(self, wx: float, wy: float) -> tuple[float, float]:
        """Convert world coordinates to screen coordinates."""
        sx = (wx + self.xorigin) * self.mooz
        sy = (wy + self.yorigin) * self.mooz
        return (sx, sy)

    def copy(self) -> "ViewState":
        """Create a copy of this view state."""
        return ViewState(
            xorigin=self.xorigin,
            yorigin=self.yorigin,
            zoom=self.zoom,
        )


@dataclass
class HierarchyLevel:
    """State saved when descending into hierarchy."""
    schematic_path: str
    instance_path: str
    view_state: ViewState


@dataclass
class SchematicContext:
    """
    Main container for all schematic data.

    This is the central data structure that replaces the C Xschem_ctx struct.
    It contains all primitives, symbols, instances, and state information
    for one schematic document.

    Attributes:
        wires: List of all wires
        texts: List of all text annotations
        rects: Rectangles organized by layer {layer: [Rect, ...]}
        lines: Lines organized by layer
        arcs: Arcs organized by layer
        polygons: Polygons organized by layer
        instances: List of all component instances
        symbols: List of loaded symbol definitions

        current_name: Current schematic file path
        version_string: xschem version that created the file
        file_version: File format version (e.g., "1.2")

        view: Current view state (zoom, pan)
        ui_state: Current UI operation mode
        ui_state2: Secondary UI state flags

        netlist_type: Current netlist format (SPICE, Verilog, etc.)
        modified: True if schematic has unsaved changes

        hierarchy_stack: Stack for hierarchy navigation
        rectcolor: Current drawing layer
    """

    # Graphical primitives
    wires: List[Wire] = field(default_factory=list)
    texts: List[Text] = field(default_factory=list)
    rects: Dict[int, List[Rect]] = field(default_factory=dict)
    lines: Dict[int, List[Line]] = field(default_factory=dict)
    arcs: Dict[int, List[Arc]] = field(default_factory=dict)
    polygons: Dict[int, List[Polygon]] = field(default_factory=dict)

    # Symbols and instances
    instances: List[Instance] = field(default_factory=list)
    symbols: List[Symbol] = field(default_factory=list)
    symbol_map: Dict[str, int] = field(default_factory=dict)  # name -> index

    # File information
    current_name: str = ""
    version_string: str = ""
    file_version: str = "1.2"

    # Global properties (G, K, V, S, E, F from file format)
    schprop: Optional[str] = None       # Schematic properties
    sym_prop: Optional[str] = None      # Symbol properties (K)
    vhdl_prop: Optional[str] = None     # VHDL properties (V)
    verilog_prop: Optional[str] = None  # Verilog properties (S)
    tedax_prop: Optional[str] = None    # tEDAx properties (E)
    spectre_prop: Optional[str] = None  # Spectre properties (F)

    # View state
    view: ViewState = field(default_factory=ViewState)

    # UI state
    ui_state: UIState = UIState.NONE
    ui_state2: int = 0

    # Hierarchy navigation
    hierarchy_stack: List[HierarchyLevel] = field(default_factory=list)

    # Netlisting
    netlist_type: int = NetlistType.SPICE
    hilight_nets: bool = False

    # Drawing state
    rectcolor: int = 4  # Current layer for new objects
    modified: bool = False

    # Grid and snap
    snap: float = 10.0
    grid: float = 20.0

    @property
    def filename(self) -> str:
        """Get just the filename without path."""
        if self.current_name:
            return Path(self.current_name).name
        return "untitled"

    @property
    def is_symbol(self) -> bool:
        """Check if current file is a symbol (.sym)."""
        return self.current_name.endswith(".sym")

    def clear(self) -> None:
        """Clear all schematic data."""
        self.wires.clear()
        self.texts.clear()
        self.rects.clear()
        self.lines.clear()
        self.arcs.clear()
        self.polygons.clear()
        self.instances.clear()
        self.symbols.clear()
        self.symbol_map.clear()
        self.hierarchy_stack.clear()

        self.current_name = ""
        self.schprop = None
        self.sym_prop = None
        self.vhdl_prop = None
        self.verilog_prop = None
        self.tedax_prop = None
        self.spectre_prop = None

        self.view = ViewState()
        self.ui_state = UIState.NONE
        self.modified = False

    def add_wire(self, wire: Wire) -> int:
        """Add a wire and return its index."""
        self.wires.append(wire)
        self.modified = True
        return len(self.wires) - 1

    def add_text(self, text: Text) -> int:
        """Add a text and return its index."""
        self.texts.append(text)
        self.modified = True
        return len(self.texts) - 1

    def add_instance(self, instance: Instance) -> int:
        """Add an instance and return its index."""
        self.instances.append(instance)
        self.modified = True
        return len(self.instances) - 1

    def add_rect(self, layer: int, rect: Rect) -> int:
        """Add a rectangle to a layer and return its index."""
        if layer not in self.rects:
            self.rects[layer] = []
        self.rects[layer].append(rect)
        self.modified = True
        return len(self.rects[layer]) - 1

    def add_line(self, layer: int, line: Line) -> int:
        """Add a line to a layer and return its index."""
        if layer not in self.lines:
            self.lines[layer] = []
        self.lines[layer].append(line)
        self.modified = True
        return len(self.lines[layer]) - 1

    def add_arc(self, layer: int, arc: Arc) -> int:
        """Add an arc to a layer and return its index."""
        if layer not in self.arcs:
            self.arcs[layer] = []
        self.arcs[layer].append(arc)
        self.modified = True
        return len(self.arcs[layer]) - 1

    def add_polygon(self, layer: int, polygon: Polygon) -> int:
        """Add a polygon to a layer and return its index."""
        if layer not in self.polygons:
            self.polygons[layer] = []
        self.polygons[layer].append(polygon)
        self.modified = True
        return len(self.polygons[layer]) - 1

    def get_symbol(self, name: str) -> Optional[Symbol]:
        """Get a symbol by name, or None if not loaded."""
        idx = self.symbol_map.get(name)
        if idx is not None and idx < len(self.symbols):
            return self.symbols[idx]
        return None

    def add_symbol(self, symbol: Symbol) -> int:
        """Add a symbol and return its index."""
        idx = len(self.symbols)
        self.symbols.append(symbol)
        self.symbol_map[symbol.name] = idx
        return idx

    def push_hierarchy(self, schematic_path: str, instance_path: str) -> None:
        """Save current state and descend into a subcircuit."""
        level = HierarchyLevel(
            schematic_path=self.current_name,
            instance_path=instance_path,
            view_state=self.view.copy(),
        )
        self.hierarchy_stack.append(level)
        self.current_name = schematic_path
        self.view = ViewState()

    def pop_hierarchy(self) -> bool:
        """Return from a subcircuit to parent level."""
        if not self.hierarchy_stack:
            return False
        level = self.hierarchy_stack.pop()
        self.current_name = level.schematic_path
        self.view = level.view_state
        return True

    @property
    def hierarchy_depth(self) -> int:
        """Current depth in hierarchy (0 = top level)."""
        return len(self.hierarchy_stack)

    def get_hierarchy_path(self) -> str:
        """Get full hierarchy path as string."""
        parts = [level.instance_path for level in self.hierarchy_stack]
        return "/".join(parts) if parts else "/"

    def calculate_bbox(self) -> tuple[float, float, float, float]:
        """Calculate bounding box of all objects."""
        all_x: List[float] = []
        all_y: List[float] = []

        for wire in self.wires:
            x1, y1, x2, y2 = wire.bbox
            all_x.extend([x1, x2])
            all_y.extend([y1, y2])

        for text in self.texts:
            all_x.append(text.x0)
            all_y.append(text.y0)

        for layer_rects in self.rects.values():
            for rect in layer_rects:
                x1, y1, x2, y2 = rect.bbox
                all_x.extend([x1, x2])
                all_y.extend([y1, y2])

        for layer_lines in self.lines.values():
            for line in layer_lines:
                x1, y1, x2, y2 = line.bbox
                all_x.extend([x1, x2])
                all_y.extend([y1, y2])

        for layer_arcs in self.arcs.values():
            for arc in layer_arcs:
                x1, y1, x2, y2 = arc.bbox
                all_x.extend([x1, x2])
                all_y.extend([y1, y2])

        for layer_polys in self.polygons.values():
            for poly in layer_polys:
                x1, y1, x2, y2 = poly.bbox
                all_x.extend([x1, x2])
                all_y.extend([y1, y2])

        for inst in self.instances:
            x1, y1, x2, y2 = inst.bbox
            all_x.extend([x1, x2])
            all_y.extend([y1, y2])

        if all_x and all_y:
            return (min(all_x), min(all_y), max(all_x), max(all_y))
        return (0.0, 0.0, 0.0, 0.0)
