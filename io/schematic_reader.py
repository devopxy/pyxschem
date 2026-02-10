"""
Schematic file reader for PyXSchem.

Parses .sch (schematic) and .sym (symbol) files in the xschem format.

File format record types:
    v - Version string with metadata
    G - VHDL/global properties (schvhdlprop)
    K - Symbol properties (schsymbolprop)
    V - Verilog properties (schverilogprop)
    S - Schematic properties (schprop)
    E - tEDAx properties (schtedaxprop)
    F - Spectre properties (schspectreprop)
    L - Line: L layer x1 y1 x2 y2 {props}
    B - Box/Rect: B layer x1 y1 x2 y2 {props}
    A - Arc: A layer x y r start_angle arc_angle {props}
    P - Polygon: P layer npoints x1 y1 x2 y2 ... {props}
    T - Text: T {text} x y rot flip xscale yscale {props}
    N - Wire: N x1 y1 x2 y2 {props}
    C - Component: C {symbol.sym} x y rot flip {props}
    [ - Start embedded symbol definition
    ] - End embedded symbol definition
"""

from pathlib import Path
from typing import Optional, TextIO, Tuple
import numpy as np
import logging

from pyxschem.core.primitives import (
    Wire,
    Line,
    Rect,
    Arc,
    Polygon,
    Text,
    TextFlags,
)
from pyxschem.core.symbol import Symbol, Instance
from pyxschem.core.context import SchematicContext
from pyxschem.core.property_parser import get_tok_value


logger = logging.getLogger(__name__)


class SchematicReader:
    """
    Parser for xschem schematic and symbol files.

    Reads the ASCII file format and populates a SchematicContext
    with all parsed primitives, symbols, and instances.

    The parser uses a simple state machine to read records line by line.
    String values are enclosed in braces {like this} with escaping for
    special characters (\\, {, }).
    """

    # Maximum number of layers supported
    MAX_LAYERS = 45

    def __init__(self):
        self._file: Optional[TextIO] = None
        self._context: Optional[SchematicContext] = None
        self._pending_char: Optional[str] = None

    def read(self, filepath: Path) -> SchematicContext:
        """
        Read a schematic or symbol file.

        Args:
            filepath: Path to .sch or .sym file

        Returns:
            Populated SchematicContext

        Raises:
            FileNotFoundError: If file doesn't exist
            ValueError: If file is malformed
        """
        self._context = SchematicContext()
        self._context.current_name = str(filepath)
        logger.info("Reading schematic file '%s'", filepath)

        with open(filepath, "r", encoding="utf-8", errors="replace") as f:
            self._file = f
            self._read_xschem_file()
            self._file = None

        assert self._context is not None
        logger.info(
            (
                "Read complete '%s' (wires=%d lines=%d rects=%d arcs=%d "
                "polygons=%d texts=%d instances=%d)"
            ),
            filepath,
            len(self._context.wires),
            sum(len(lines) for lines in self._context.lines.values()),
            sum(len(rects) for rects in self._context.rects.values()),
            sum(len(arcs) for arcs in self._context.arcs.values()),
            sum(len(polys) for polys in self._context.polygons.values()),
            len(self._context.texts),
            len(self._context.instances),
        )

        return self._context

    def read_symbol(self, filepath: Path) -> Symbol:
        """
        Read a symbol file and return a Symbol object.

        Args:
            filepath: Path to .sym file

        Returns:
            Symbol definition
        """
        ctx = self.read(filepath)
        logger.info("Converting context to symbol '%s'", filepath)
        return self._context_to_symbol(ctx, str(filepath))

    def _context_to_symbol(self, ctx: SchematicContext, name: str) -> Symbol:
        """Convert a loaded context to a Symbol object."""
        symbol = Symbol(name=name)
        symbol.lines = dict(ctx.lines)
        symbol.rects = dict(ctx.rects)
        symbol.arcs = dict(ctx.arcs)
        symbol.polygons = dict(ctx.polygons)
        symbol.texts = list(ctx.texts)
        symbol.prop_ptr = ctx.sym_prop

        if symbol.prop_ptr:
            symbol.type = get_tok_value(symbol.prop_ptr, "type")
            symbol.templ = get_tok_value(symbol.prop_ptr, "template")
            symbol.format = get_tok_value(symbol.prop_ptr, "format")
            symbol.verilog_format = get_tok_value(symbol.prop_ptr, "verilog_format")
            symbol.vhdl_format = get_tok_value(symbol.prop_ptr, "vhdl_format")
            symbol.spectre_format = get_tok_value(symbol.prop_ptr, "spectre_format")
            symbol.tedax_format = get_tok_value(symbol.prop_ptr, "tedax_format")

        symbol.calculate_bbox()
        return symbol

    def _read_xschem_file(self) -> None:
        """Main parsing loop for xschem file."""
        assert self._file is not None
        assert self._context is not None

        while True:
            tag = self._read_tag()
            if tag is None:
                break

            if tag == "v":
                self._load_version()
            elif tag == "#":
                self._read_line()  # Comment, skip
            elif tag == "G":
                self._context.vhdl_prop = self._load_ascii_string()
            elif tag == "K":
                self._context.sym_prop = self._load_ascii_string()
            elif tag == "V":
                self._context.verilog_prop = self._load_ascii_string()
            elif tag == "S":
                self._context.schprop = self._load_ascii_string()
            elif tag == "E":
                self._context.tedax_prop = self._load_ascii_string()
            elif tag == "F":
                self._context.spectre_prop = self._load_ascii_string()
            elif tag == "L":
                self._load_line()
            elif tag == "B":
                self._load_box()
            elif tag == "A":
                self._load_arc()
            elif tag == "P":
                self._load_polygon()
            elif tag == "T":
                self._load_text()
            elif tag == "N":
                self._load_wire()
            elif tag == "C":
                self._load_inst()
            elif tag == "[":
                self._skip_embedded_symbol()
            elif tag == "{":
                # Stray brace, try to read as string
                logger.warning("Encountered stray '{' while parsing; attempting recovery")
                self._unget_char("{")
                self._load_ascii_string()
            else:
                # Unknown tag, skip rest of line
                logger.warning("Unknown record tag '%s'; skipping line", tag)
                self._read_line()

            # Discard remaining characters on line
            self._read_line()

    def _read_tag(self) -> Optional[str]:
        """Read the next record tag, skipping whitespace."""
        assert self._file is not None

        while True:
            c = self._get_char()
            if c is None:
                return None
            if c.isspace():
                continue
            return c

    def _get_char(self) -> Optional[str]:
        """Read a single character from the file."""
        if self._pending_char is not None:
            c = self._pending_char
            self._pending_char = None
            return c
        c = self._file.read(1)
        return c if c else None

    def _unget_char(self, c: str) -> None:
        """Push a character back to be read again."""
        self._pending_char = c

    def _read_line(self) -> str:
        """Read remaining characters until newline."""
        assert self._file is not None
        chars = []
        while True:
            c = self._get_char()
            if c is None or c == "\n":
                break
            chars.append(c)
        return "".join(chars)

    def _skip_whitespace(self) -> None:
        """Skip whitespace except newlines."""
        while True:
            c = self._get_char()
            if c is None:
                break
            if c == "\n" or not c.isspace():
                self._unget_char(c)
                break

    def _read_float(self) -> float:
        """Read a floating point number."""
        self._skip_whitespace()
        chars = []
        while True:
            c = self._get_char()
            if c is None:
                break
            if c.isspace() or c in "{}":
                self._unget_char(c)
                break
            chars.append(c)
        return float("".join(chars)) if chars else 0.0

    def _read_int(self) -> int:
        """Read an integer number."""
        self._skip_whitespace()
        chars = []
        while True:
            c = self._get_char()
            if c is None:
                break
            if c.isspace() or c in "{}":
                self._unget_char(c)
                break
            chars.append(c)
        return int("".join(chars)) if chars else 0

    def _load_ascii_string(self) -> Optional[str]:
        """
        Load a brace-enclosed string with escape handling.

        Format: {content with \\ \{ \} escapes}
        """
        assert self._file is not None

        # Find opening brace
        while True:
            c = self._get_char()
            if c is None:
                return None
            if c == "{":
                break

        chars = []
        escape = False

        while True:
            c = self._get_char()
            if c is None:
                raise ValueError("EOF reached, missing close brace in string")
            if c == "\r":
                continue

            if escape:
                chars.append(c)
                escape = False
            elif c == "\\":
                escape = True
            elif c == "}":
                break
            else:
                chars.append(c)

        return "".join(chars) if chars else None

    def _load_version(self) -> None:
        """Load version string and extract metadata."""
        assert self._context is not None

        version_str = self._load_ascii_string()
        if version_str:
            self._context.version_string = version_str
            file_version = get_tok_value(version_str, "file_version")
            if file_version:
                self._context.file_version = file_version
            else:
                self._context.file_version = "1.0"
            logger.debug(
                "Version record loaded (version_string='%s', file_version='%s')",
                version_str,
                self._context.file_version,
            )

    def _load_line(self) -> None:
        """Load a line record: L layer x1 y1 x2 y2 {props}"""
        assert self._context is not None

        layer = self._read_int()
        if layer < 0 or layer >= self.MAX_LAYERS:
            logger.warning("Skipping line on invalid layer index %d", layer)
            self._read_line()
            return

        x1 = self._read_float()
        y1 = self._read_float()
        x2 = self._read_float()
        y2 = self._read_float()
        prop_ptr = self._load_ascii_string()

        # Parse properties
        dash = 0
        bus = 1.0
        if prop_ptr:
            dash_str = get_tok_value(prop_ptr, "dash")
            if dash_str:
                dash = max(0, int(dash_str))
            bus_str = get_tok_value(prop_ptr, "bus")
            if bus_str:
                try:
                    bus = float(bus_str)
                except ValueError:
                    pass

        line = Line(
            x1=min(x1, x2),
            y1=min(y1, y2) if x1 == x2 else (y1 if x1 < x2 else y2),
            x2=max(x1, x2),
            y2=max(y1, y2) if x1 == x2 else (y2 if x1 < x2 else y1),
            prop_ptr=prop_ptr,
            dash=dash,
            bus=bus,
        )
        self._context.add_line(layer, line)
        logger.debug("Loaded line on layer=%d bbox=%s", layer, line.bbox)

    def _load_box(self) -> None:
        """Load a rectangle record: B layer x1 y1 x2 y2 {props}"""
        assert self._context is not None

        layer = self._read_int()
        if layer < 0 or layer >= self.MAX_LAYERS:
            logger.warning("Skipping box on invalid layer index %d", layer)
            self._read_line()
            return

        x1 = self._read_float()
        y1 = self._read_float()
        x2 = self._read_float()
        y2 = self._read_float()
        prop_ptr = self._load_ascii_string()

        # Parse properties
        fill = 1
        dash = 0
        bus = 1.0
        ellipse_a = -1
        ellipse_b = -1
        flags = 0

        if prop_ptr:
            fill_str = get_tok_value(prop_ptr, "fill")
            if fill_str == "full":
                fill = 2
            elif fill_str.lower() == "false":
                fill = 0

            dash_str = get_tok_value(prop_ptr, "dash")
            if dash_str:
                dash = max(0, int(dash_str))

            bus_str = get_tok_value(prop_ptr, "bus")
            if bus_str:
                try:
                    bus = float(bus_str)
                except ValueError:
                    pass

            ellipse_str = get_tok_value(prop_ptr, "ellipse")
            if ellipse_str:
                parts = ellipse_str.replace(",", " ").split()
                if len(parts) >= 2:
                    try:
                        ellipse_a = int(parts[0])
                        ellipse_b = int(parts[1])
                    except ValueError:
                        ellipse_a = 0
                        ellipse_b = 360

            # Check for graph flag
            graph_str = get_tok_value(prop_ptr, "flags")
            if graph_str:
                try:
                    flags = int(graph_str)
                except ValueError:
                    pass

        rect = Rect(
            x1=min(x1, x2),
            y1=min(y1, y2),
            x2=max(x1, x2),
            y2=max(y1, y2),
            prop_ptr=prop_ptr,
            fill=fill,
            dash=dash,
            bus=bus,
            ellipse_a=ellipse_a,
            ellipse_b=ellipse_b,
            flags=flags,
        )
        self._context.add_rect(layer, rect)
        logger.debug("Loaded box on layer=%d bbox=%s fill=%d", layer, rect.bbox, rect.fill)

    def _load_arc(self) -> None:
        """Load an arc record: A layer x y r start_angle arc_angle {props}"""
        assert self._context is not None

        layer = self._read_int()
        if layer < 0 or layer >= self.MAX_LAYERS:
            logger.warning("Skipping arc on invalid layer index %d", layer)
            self._read_line()
            return

        x = self._read_float()
        y = self._read_float()
        r = self._read_float()
        a = self._read_float()
        b = self._read_float()
        prop_ptr = self._load_ascii_string()

        # Parse properties
        fill = 0
        dash = 0
        bus = 1.0

        if prop_ptr:
            fill_str = get_tok_value(prop_ptr, "fill")
            if fill_str == "full":
                fill = 2
            elif fill_str.lower() == "true":
                fill = 1

            dash_str = get_tok_value(prop_ptr, "dash")
            if dash_str:
                dash = max(0, int(dash_str))

            bus_str = get_tok_value(prop_ptr, "bus")
            if bus_str:
                try:
                    bus = float(bus_str)
                except ValueError:
                    pass

        arc = Arc(
            x=x,
            y=y,
            r=r,
            a=a,
            b=b,
            prop_ptr=prop_ptr,
            fill=fill,
            dash=dash,
            bus=bus,
        )
        self._context.add_arc(layer, arc)
        logger.debug("Loaded arc on layer=%d center=(%s,%s) r=%s", layer, x, y, r)

    def _load_polygon(self) -> None:
        """Load a polygon record: P layer npoints x1 y1 x2 y2 ... {props}"""
        assert self._context is not None

        layer = self._read_int()
        npoints = self._read_int()

        if layer < 0 or layer >= self.MAX_LAYERS or npoints < 0:
            logger.warning("Skipping polygon with invalid layer=%d or npoints=%d", layer, npoints)
            self._read_line()
            return

        x_coords = []
        y_coords = []
        for _ in range(npoints):
            x_coords.append(self._read_float())
            y_coords.append(self._read_float())

        prop_ptr = self._load_ascii_string()

        # Parse properties
        fill = 0
        dash = 0
        bus = 1.0

        if prop_ptr:
            fill_str = get_tok_value(prop_ptr, "fill")
            if fill_str == "full":
                fill = 2
            elif fill_str.lower() == "true":
                fill = 1

            dash_str = get_tok_value(prop_ptr, "dash")
            if dash_str:
                dash = max(0, int(dash_str))

            bus_str = get_tok_value(prop_ptr, "bus")
            if bus_str:
                try:
                    bus = float(bus_str)
                except ValueError:
                    pass

        polygon = Polygon(
            x=np.array(x_coords, dtype=np.float64),
            y=np.array(y_coords, dtype=np.float64),
            selected_point=np.zeros(npoints, dtype=np.uint16),
            prop_ptr=prop_ptr,
            fill=fill,
            dash=dash,
            bus=bus,
        )
        self._context.add_polygon(layer, polygon)
        logger.debug("Loaded polygon on layer=%d points=%d", layer, npoints)

    def _load_text(self) -> None:
        """Load a text record: T {text} x y rot flip xscale yscale {props}"""
        assert self._context is not None

        txt_ptr = self._load_ascii_string()
        if txt_ptr is None:
            txt_ptr = ""

        x0 = self._read_float()
        y0 = self._read_float()
        rot = self._read_int()
        flip = self._read_int()
        xscale = self._read_float()
        yscale = self._read_float()
        prop_ptr = self._load_ascii_string()

        # Parse properties for text formatting
        hcenter = 0
        vcenter = 0
        layer = 3  # Default TEXTLAYER
        font = None
        flags = TextFlags.NONE

        if prop_ptr:
            hcenter_str = get_tok_value(prop_ptr, "hcenter")
            if hcenter_str.lower() == "true":
                hcenter = 1

            vcenter_str = get_tok_value(prop_ptr, "vcenter")
            if vcenter_str.lower() == "true":
                vcenter = 1

            layer_str = get_tok_value(prop_ptr, "layer")
            if layer_str:
                try:
                    layer = int(layer_str)
                except ValueError:
                    pass

            font_str = get_tok_value(prop_ptr, "font")
            if font_str:
                font = font_str

            weight_str = get_tok_value(prop_ptr, "weight")
            if weight_str.lower() == "bold":
                flags |= TextFlags.BOLD

            slant_str = get_tok_value(prop_ptr, "slant")
            if slant_str.lower() == "italic":
                flags |= TextFlags.ITALIC
            elif slant_str.lower() == "oblique":
                flags |= TextFlags.OBLIQUE

        text = Text(
            txt_ptr=txt_ptr,
            x0=x0,
            y0=y0,
            rot=rot,
            flip=flip,
            xscale=xscale,
            yscale=yscale,
            prop_ptr=prop_ptr,
            hcenter=hcenter,
            vcenter=vcenter,
            layer=layer,
            font=font,
            flags=flags,
        )
        self._context.add_text(text)
        logger.debug(
            "Loaded text at (%.3f, %.3f) rot=%d layer=%d chars=%d",
            x0,
            y0,
            rot,
            layer,
            len(txt_ptr),
        )

    def _load_wire(self) -> None:
        """Load a wire record: N x1 y1 x2 y2 {props}"""
        assert self._context is not None

        x1 = self._read_float()
        y1 = self._read_float()
        x2 = self._read_float()
        y2 = self._read_float()
        prop_ptr = self._load_ascii_string()

        # Parse bus property
        bus = 1.0
        if prop_ptr:
            bus_str = get_tok_value(prop_ptr, "bus")
            if bus_str:
                try:
                    bus = float(bus_str)
                except ValueError:
                    pass

        # Order coordinates (horizontal/vertical preference)
        if x1 > x2 or (x1 == x2 and y1 > y2):
            x1, x2 = x2, x1
            y1, y2 = y2, y1

        wire = Wire(
            x1=x1,
            y1=y1,
            x2=x2,
            y2=y2,
            prop_ptr=prop_ptr,
            bus=bus,
        )
        self._context.add_wire(wire)
        logger.debug("Loaded wire bbox=%s bus=%s", wire.bbox, wire.bus)

    def _load_inst(self) -> None:
        """Load a component instance: C {symbol.sym} x y rot flip {props}"""
        assert self._context is not None

        name = self._load_ascii_string()
        if not name:
            logger.warning("Skipping instance record with empty symbol name")
            return

        # Add .sym extension for old format
        if self._context.file_version == "1.0" and not name.endswith(".sym"):
            name += ".sym"

        x0 = self._read_float()
        y0 = self._read_float()
        rot = self._read_int()
        flip = self._read_int()
        prop_ptr = self._load_ascii_string()

        instance = Instance(
            name=name,
            x0=x0,
            y0=y0,
            rot=rot,
            flip=flip,
            prop_ptr=prop_ptr,
        )

        # Extract instance name from properties
        if prop_ptr:
            instname = get_tok_value(prop_ptr, "name")
            if instname:
                instance.instname = instname

        self._context.add_instance(instance)
        logger.debug(
            "Loaded instance symbol='%s' at (%.3f, %.3f) rot=%d flip=%d",
            name,
            x0,
            y0,
            rot,
            flip,
        )

    def _skip_embedded_symbol(self) -> None:
        """Skip an embedded symbol definition between [ and ]."""
        logger.info("Skipping embedded symbol block")
        self._read_line()  # Skip rest of [ line

        depth = 1
        while depth > 0:
            line = self._read_line()
            if line is None:
                break
            stripped = line.strip()
            if stripped.startswith("]"):
                depth -= 1
            elif stripped.startswith("["):
                depth += 1
        logger.debug("Finished skipping embedded symbol block")


def read_schematic(filepath: str | Path) -> SchematicContext:
    """
    Convenience function to read a schematic file.

    Args:
        filepath: Path to .sch or .sym file

    Returns:
        Populated SchematicContext
    """
    reader = SchematicReader()
    return reader.read(Path(filepath))
