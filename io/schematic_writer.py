"""
Schematic file writer for PyXSchem.

Writes .sch (schematic) and .sym (symbol) files in the xschem format.

Maintains compatibility with the original xschem file format by:
- Using the same record format and ordering
- Properly escaping special characters in strings
- Using %.16g format for floating point numbers (full precision)
"""

from pathlib import Path
from typing import Optional, TextIO
import numpy as np

from pyxschem.core.primitives import (
    Wire,
    Line,
    Rect,
    Arc,
    Polygon,
    Text,
)
from pyxschem.core.symbol import Symbol, Instance
from pyxschem.core.context import SchematicContext


# Version strings
PYXSCHEM_VERSION = "0.1.0"
XSCHEM_FILE_VERSION = "1.2"


class SchematicWriter:
    """
    Writer for xschem schematic and symbol files.

    Writes a SchematicContext to disk in the standard xschem
    ASCII format. Can write both .sch and .sym files.
    """

    def __init__(self):
        self._file: Optional[TextIO] = None

    def write(self, context: SchematicContext, filepath: Path) -> None:
        """
        Write a schematic to file.

        Args:
            context: SchematicContext to write
            filepath: Output file path
        """
        with open(filepath, "w", encoding="utf-8", newline="\n") as f:
            self._file = f
            self._write_schematic(context)
            self._file = None

    def write_symbol(self, symbol: Symbol, filepath: Path) -> None:
        """
        Write a symbol definition to file.

        Args:
            symbol: Symbol to write
            filepath: Output file path
        """
        with open(filepath, "w", encoding="utf-8", newline="\n") as f:
            self._file = f
            self._write_symbol(symbol)
            self._file = None

    def _write_schematic(self, ctx: SchematicContext) -> None:
        """Write complete schematic to file."""
        assert self._file is not None

        # Version line
        version_str = ctx.version_string
        if not version_str:
            version_str = f"xschem version={PYXSCHEM_VERSION} file_version={XSCHEM_FILE_VERSION}"
        self._file.write("v ")
        self._write_ascii_string(version_str, newline=True)

        # Global properties
        self._file.write("G ")
        self._write_ascii_string(ctx.vhdl_prop, newline=True)

        self._file.write("K ")
        self._write_ascii_string(ctx.sym_prop, newline=True)

        self._file.write("V ")
        self._write_ascii_string(ctx.verilog_prop, newline=True)

        self._file.write("S ")
        self._write_ascii_string(ctx.schprop, newline=True)

        self._file.write("E ")
        self._write_ascii_string(ctx.tedax_prop, newline=True)

        self._file.write("F ")
        self._write_ascii_string(ctx.spectre_prop, newline=True)

        # Lines (by layer)
        self._write_lines(ctx)

        # Boxes/Rects (by layer)
        self._write_boxes(ctx)

        # Arcs (by layer)
        self._write_arcs(ctx)

        # Polygons (by layer)
        self._write_polygons(ctx)

        # Text
        self._write_texts(ctx)

        # Wires
        self._write_wires(ctx)

        # Instances
        self._write_instances(ctx)

    def _write_symbol(self, symbol: Symbol) -> None:
        """Write a symbol definition to file."""
        assert self._file is not None

        # Version line
        self._file.write(f"v {{xschem version={PYXSCHEM_VERSION} file_version={XSCHEM_FILE_VERSION}}}\n")

        # Symbol properties
        self._file.write("K ")
        self._write_ascii_string(symbol.prop_ptr, newline=True)

        # Empty global properties
        self._file.write("G {}\n")
        self._file.write("V {}\n")
        self._file.write("S {}\n")
        self._file.write("E {}\n")
        self._file.write("F {}\n")

        # Lines
        for layer, lines in sorted(symbol.lines.items()):
            for line in lines:
                self._file.write(
                    f"L {layer} {line.x1:.16g} {line.y1:.16g} "
                    f"{line.x2:.16g} {line.y2:.16g} "
                )
                self._write_ascii_string(line.prop_ptr, newline=True)

        # Rects
        for layer, rects in sorted(symbol.rects.items()):
            for rect in rects:
                self._file.write(
                    f"B {layer} {rect.x1:.16g} {rect.y1:.16g} "
                    f"{rect.x2:.16g} {rect.y2:.16g} "
                )
                self._write_ascii_string(rect.prop_ptr, newline=True)

        # Arcs
        for layer, arcs in sorted(symbol.arcs.items()):
            for arc in arcs:
                self._file.write(
                    f"A {layer} {arc.x:.16g} {arc.y:.16g} "
                    f"{arc.r:.16g} {arc.a:.16g} {arc.b:.16g} "
                )
                self._write_ascii_string(arc.prop_ptr, newline=True)

        # Polygons
        for layer, polygons in sorted(symbol.polygons.items()):
            for poly in polygons:
                self._file.write(f"P {layer} {poly.points}")
                for i in range(poly.points):
                    self._file.write(f" {poly.x[i]:.16g} {poly.y[i]:.16g}")
                self._file.write(" ")
                self._write_ascii_string(poly.prop_ptr, newline=True)

        # Texts
        for text in symbol.texts:
            self._file.write("T ")
            self._write_ascii_string(text.txt_ptr, newline=False)
            self._file.write(
                f" {text.x0:.16g} {text.y0:.16g} {text.rot} {text.flip} "
                f"{text.xscale:.16g} {text.yscale:.16g} "
            )
            self._write_ascii_string(text.prop_ptr, newline=True)

    def _write_lines(self, ctx: SchematicContext) -> None:
        """Write all lines organized by layer."""
        assert self._file is not None
        for layer, lines in sorted(ctx.lines.items()):
            for line in lines:
                self._file.write(
                    f"L {layer} {line.x1:.16g} {line.y1:.16g} "
                    f"{line.x2:.16g} {line.y2:.16g} "
                )
                self._write_ascii_string(line.prop_ptr, newline=True)

    def _write_boxes(self, ctx: SchematicContext) -> None:
        """Write all rectangles organized by layer."""
        assert self._file is not None
        for layer, rects in sorted(ctx.rects.items()):
            for rect in rects:
                self._file.write(
                    f"B {layer} {rect.x1:.16g} {rect.y1:.16g} "
                    f"{rect.x2:.16g} {rect.y2:.16g} "
                )
                self._write_ascii_string(rect.prop_ptr, newline=True)

    def _write_arcs(self, ctx: SchematicContext) -> None:
        """Write all arcs organized by layer."""
        assert self._file is not None
        for layer, arcs in sorted(ctx.arcs.items()):
            for arc in arcs:
                self._file.write(
                    f"A {layer} {arc.x:.16g} {arc.y:.16g} "
                    f"{arc.r:.16g} {arc.a:.16g} {arc.b:.16g} "
                )
                self._write_ascii_string(arc.prop_ptr, newline=True)

    def _write_polygons(self, ctx: SchematicContext) -> None:
        """Write all polygons organized by layer."""
        assert self._file is not None
        for layer, polygons in sorted(ctx.polygons.items()):
            for poly in polygons:
                self._file.write(f"P {layer} {poly.points}")
                for i in range(poly.points):
                    self._file.write(f" {poly.x[i]:.16g} {poly.y[i]:.16g}")
                self._file.write(" ")
                self._write_ascii_string(poly.prop_ptr, newline=True)

    def _write_texts(self, ctx: SchematicContext) -> None:
        """Write all text elements."""
        assert self._file is not None
        for text in ctx.texts:
            self._file.write("T ")
            self._write_ascii_string(text.txt_ptr, newline=False)
            self._file.write(
                f" {text.x0:.16g} {text.y0:.16g} {text.rot} {text.flip} "
                f"{text.xscale:.16g} {text.yscale:.16g} "
            )
            self._write_ascii_string(text.prop_ptr, newline=True)

    def _write_wires(self, ctx: SchematicContext) -> None:
        """Write all wire elements."""
        assert self._file is not None
        for wire in ctx.wires:
            self._file.write(
                f"N {wire.x1:.16g} {wire.y1:.16g} "
                f"{wire.x2:.16g} {wire.y2:.16g} "
            )
            self._write_ascii_string(wire.prop_ptr, newline=True)

    def _write_instances(self, ctx: SchematicContext) -> None:
        """Write all component instances."""
        assert self._file is not None
        for inst in ctx.instances:
            self._file.write("C ")
            self._write_ascii_string(inst.name, newline=False)
            self._file.write(
                f" {inst.x0:.16g} {inst.y0:.16g} {inst.rot} {inst.flip} "
            )
            self._write_ascii_string(inst.prop_ptr, newline=True)

            # Handle embedded symbols
            if inst.embed and inst.embedded_symbol is not None:
                self._file.write("[\n")
                self._write_embedded_symbol(inst.embedded_symbol)
                self._file.write("]\n")

    def _write_embedded_symbol(self, symbol: Symbol) -> None:
        """Write an embedded symbol definition."""
        # Write symbol contents (simplified - no version line)
        self._file.write("K ")
        self._write_ascii_string(symbol.prop_ptr, newline=True)

        for layer, lines in sorted(symbol.lines.items()):
            for line in lines:
                self._file.write(
                    f"L {layer} {line.x1:.16g} {line.y1:.16g} "
                    f"{line.x2:.16g} {line.y2:.16g} "
                )
                self._write_ascii_string(line.prop_ptr, newline=True)

        for layer, rects in sorted(symbol.rects.items()):
            for rect in rects:
                self._file.write(
                    f"B {layer} {rect.x1:.16g} {rect.y1:.16g} "
                    f"{rect.x2:.16g} {rect.y2:.16g} "
                )
                self._write_ascii_string(rect.prop_ptr, newline=True)

        for layer, arcs in sorted(symbol.arcs.items()):
            for arc in arcs:
                self._file.write(
                    f"A {layer} {arc.x:.16g} {arc.y:.16g} "
                    f"{arc.r:.16g} {arc.a:.16g} {arc.b:.16g} "
                )
                self._write_ascii_string(arc.prop_ptr, newline=True)

        for layer, polygons in sorted(symbol.polygons.items()):
            for poly in polygons:
                self._file.write(f"P {layer} {poly.points}")
                for i in range(poly.points):
                    self._file.write(f" {poly.x[i]:.16g} {poly.y[i]:.16g}")
                self._file.write(" ")
                self._write_ascii_string(poly.prop_ptr, newline=True)

        for text in symbol.texts:
            self._file.write("T ")
            self._write_ascii_string(text.txt_ptr, newline=False)
            self._file.write(
                f" {text.x0:.16g} {text.y0:.16g} {text.rot} {text.flip} "
                f"{text.xscale:.16g} {text.yscale:.16g} "
            )
            self._write_ascii_string(text.prop_ptr, newline=True)

    def _write_ascii_string(self, s: Optional[str], newline: bool = True) -> None:
        """
        Write a brace-enclosed string with proper escaping.

        Characters that need escaping: \\, {, }
        """
        assert self._file is not None

        if s is None:
            if newline:
                self._file.write("{}\n")
            else:
                self._file.write("{}")
            return

        self._file.write("{")
        for c in s:
            if c in "\\{}":
                self._file.write("\\")
            self._file.write(c)
        self._file.write("}")

        if newline:
            self._file.write("\n")


def write_schematic(context: SchematicContext, filepath: str | Path) -> None:
    """
    Convenience function to write a schematic file.

    Args:
        context: SchematicContext to write
        filepath: Output file path
    """
    writer = SchematicWriter()
    writer.write(context, Path(filepath))
