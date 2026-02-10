"""
File I/O module for PyXSchem.

This module handles reading and writing of xschem schematic (.sch) and
symbol (.sym) files, maintaining full compatibility with the original
xschem file format.
"""

from pyxschem.io.schematic_reader import SchematicReader, read_schematic
from pyxschem.io.schematic_writer import SchematicWriter, write_schematic

__all__ = [
    "SchematicReader",
    "SchematicWriter",
    "read_schematic",
    "write_schematic",
]
