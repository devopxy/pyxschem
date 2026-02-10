"""
Edit controller for PyXSchem.

Handles edit operations:
- Selection management
- Copy/Cut/Paste with clipboard
- Delete
- Move
- Rotate and flip
- Duplicate
"""

from enum import Enum, auto
from typing import Optional, List, Set, Tuple, TYPE_CHECKING
from dataclasses import dataclass, field
from copy import deepcopy
import logging

from PySide6.QtCore import Qt, QPointF, QMimeData
from PySide6.QtWidgets import QApplication
from PySide6.QtGui import QClipboard

if TYPE_CHECKING:
    from pyxschem.core.context import SchematicContext
    from pyxschem.core.primitives import Wire, Line, Rect, Arc, Polygon, Text
    from pyxschem.core.symbol import Instance
    from pyxschem.graphics import SchematicCanvas, SchematicRenderer


logger = logging.getLogger(__name__)


@dataclass
class ClipboardData:
    """Data stored in clipboard for paste operations."""
    wires: List["Wire"] = field(default_factory=list)
    lines: dict = field(default_factory=dict)  # layer -> list
    rects: dict = field(default_factory=dict)
    arcs: dict = field(default_factory=dict)
    polygons: dict = field(default_factory=dict)
    texts: List["Text"] = field(default_factory=list)
    instances: List["Instance"] = field(default_factory=list)
    # Reference point for relative paste positioning
    reference_point: Optional[Tuple[float, float]] = None


class EditController:
    """
    Controls edit operations on the schematic.

    Manages selection, clipboard operations, and transformation
    of selected objects.
    """

    # Custom MIME type for clipboard
    MIME_TYPE = "application/x-pyxschem-selection"

    def __init__(
        self,
        canvas: "SchematicCanvas",
        renderer: "SchematicRenderer",
        context: "SchematicContext"
    ):
        self._canvas = canvas
        self._renderer = renderer
        self._context = context
        self._clipboard = ClipboardData()
        logger.info("EditController initialized")

    # -------------------------------------------------------------------------
    # Selection operations
    # -------------------------------------------------------------------------

    def select_all(self) -> None:
        """Select all objects in the schematic."""
        from pyxschem.core.primitives import SelectionState

        for wire in self._context.wires:
            wire.sel = SelectionState.SELECTED

        for texts in self._context.texts:
            texts.sel = SelectionState.SELECTED

        for layer_rects in self._context.rects.values():
            for rect in layer_rects:
                rect.sel = SelectionState.SELECTED

        for layer_lines in self._context.lines.values():
            for line in layer_lines:
                line.sel = SelectionState.SELECTED

        for layer_arcs in self._context.arcs.values():
            for arc in layer_arcs:
                arc.sel = SelectionState.SELECTED

        for layer_polys in self._context.polygons.values():
            for poly in layer_polys:
                poly.sel = SelectionState.SELECTED

        for inst in self._context.instances:
            inst.sel = SelectionState.SELECTED

        self._renderer.render()
        logger.info("Select all completed")

    def deselect_all(self) -> None:
        """Deselect all objects."""
        from pyxschem.core.primitives import SelectionState

        for wire in self._context.wires:
            wire.sel = SelectionState.NONE

        for text in self._context.texts:
            text.sel = SelectionState.NONE

        for layer_rects in self._context.rects.values():
            for rect in layer_rects:
                rect.sel = SelectionState.NONE

        for layer_lines in self._context.lines.values():
            for line in layer_lines:
                line.sel = SelectionState.NONE

        for layer_arcs in self._context.arcs.values():
            for arc in layer_arcs:
                arc.sel = SelectionState.NONE

        for layer_polys in self._context.polygons.values():
            for poly in layer_polys:
                poly.sel = SelectionState.NONE

        for inst in self._context.instances:
            inst.sel = SelectionState.NONE

        self._canvas.get_scene().clearSelection()
        self._renderer.render()
        logger.info("Deselect all completed")

    def get_selected_wires(self) -> List["Wire"]:
        """Get all selected wires."""
        from pyxschem.core.primitives import SelectionState
        return [w for w in self._context.wires if w.sel & SelectionState.SELECTED]

    def get_selected_texts(self) -> List["Text"]:
        """Get all selected texts."""
        from pyxschem.core.primitives import SelectionState
        return [t for t in self._context.texts if t.sel & SelectionState.SELECTED]

    def get_selected_rects(self) -> dict:
        """Get all selected rectangles by layer."""
        from pyxschem.core.primitives import SelectionState
        result = {}
        for layer, rects in self._context.rects.items():
            selected = [r for r in rects if r.sel & SelectionState.SELECTED]
            if selected:
                result[layer] = selected
        return result

    def get_selected_instances(self) -> List["Instance"]:
        """Get all selected instances."""
        from pyxschem.core.primitives import SelectionState
        return [i for i in self._context.instances if i.sel & SelectionState.SELECTED]

    def has_selection(self) -> bool:
        """Check if anything is selected."""
        from pyxschem.core.primitives import SelectionState

        for wire in self._context.wires:
            if wire.sel & SelectionState.SELECTED:
                return True

        for text in self._context.texts:
            if text.sel & SelectionState.SELECTED:
                return True

        for layer_rects in self._context.rects.values():
            for rect in layer_rects:
                if rect.sel & SelectionState.SELECTED:
                    return True

        for layer_lines in self._context.lines.values():
            for line in layer_lines:
                if line.sel & SelectionState.SELECTED:
                    return True

        for layer_arcs in self._context.arcs.values():
            for arc in layer_arcs:
                if arc.sel & SelectionState.SELECTED:
                    return True

        for layer_polys in self._context.polygons.values():
            for poly in layer_polys:
                if poly.sel & SelectionState.SELECTED:
                    return True

        for inst in self._context.instances:
            if inst.sel & SelectionState.SELECTED:
                return True

        return False

    # -------------------------------------------------------------------------
    # Clipboard operations
    # -------------------------------------------------------------------------

    def copy(self) -> None:
        """Copy selected objects to clipboard."""
        from pyxschem.core.primitives import SelectionState

        self._clipboard = ClipboardData()

        # Copy wires
        for wire in self._context.wires:
            if wire.sel & SelectionState.SELECTED:
                self._clipboard.wires.append(deepcopy(wire))

        # Copy texts
        for text in self._context.texts:
            if text.sel & SelectionState.SELECTED:
                self._clipboard.texts.append(deepcopy(text))

        # Copy rects
        for layer, rects in self._context.rects.items():
            for rect in rects:
                if rect.sel & SelectionState.SELECTED:
                    if layer not in self._clipboard.rects:
                        self._clipboard.rects[layer] = []
                    self._clipboard.rects[layer].append(deepcopy(rect))

        # Copy lines
        for layer, lines in self._context.lines.items():
            for line in lines:
                if line.sel & SelectionState.SELECTED:
                    if layer not in self._clipboard.lines:
                        self._clipboard.lines[layer] = []
                    self._clipboard.lines[layer].append(deepcopy(line))

        # Copy arcs
        for layer, arcs in self._context.arcs.items():
            for arc in arcs:
                if arc.sel & SelectionState.SELECTED:
                    if layer not in self._clipboard.arcs:
                        self._clipboard.arcs[layer] = []
                    self._clipboard.arcs[layer].append(deepcopy(arc))

        # Copy polygons
        for layer, polys in self._context.polygons.items():
            for poly in polys:
                if poly.sel & SelectionState.SELECTED:
                    if layer not in self._clipboard.polygons:
                        self._clipboard.polygons[layer] = []
                    self._clipboard.polygons[layer].append(deepcopy(poly))

        # Copy instances
        for inst in self._context.instances:
            if inst.sel & SelectionState.SELECTED:
                self._clipboard.instances.append(deepcopy(inst))

        # Calculate reference point (center of selection bbox)
        self._clipboard.reference_point = self._calculate_selection_center()
        logger.info(
            (
                "Copied selection to clipboard (wires=%d lines=%d rects=%d arcs=%d "
                "polygons=%d texts=%d instances=%d)"
            ),
            len(self._clipboard.wires),
            sum(len(v) for v in self._clipboard.lines.values()),
            sum(len(v) for v in self._clipboard.rects.values()),
            sum(len(v) for v in self._clipboard.arcs.values()),
            sum(len(v) for v in self._clipboard.polygons.values()),
            len(self._clipboard.texts),
            len(self._clipboard.instances),
        )

    def cut(self) -> None:
        """Cut selected objects (copy + delete)."""
        self.copy()
        self.delete()
        logger.info("Cut operation completed")

    def paste(self, offset: Tuple[float, float] = (20.0, 20.0)) -> None:
        """
        Paste objects from clipboard.

        Args:
            offset: Offset from original position or paste location
        """
        from pyxschem.core.primitives import SelectionState

        if not self._has_clipboard_data():
            logger.warning("Paste requested with empty clipboard")
            return

        # Deselect everything first
        self.deselect_all()

        ox, oy = offset

        # Paste wires
        for wire in self._clipboard.wires:
            new_wire = deepcopy(wire)
            new_wire.x1 += ox
            new_wire.y1 += oy
            new_wire.x2 += ox
            new_wire.y2 += oy
            new_wire.sel = SelectionState.SELECTED
            self._context.add_wire(new_wire)

        # Paste texts
        for text in self._clipboard.texts:
            new_text = deepcopy(text)
            new_text.x0 += ox
            new_text.y0 += oy
            new_text.sel = SelectionState.SELECTED
            self._context.add_text(new_text)

        # Paste rects
        for layer, rects in self._clipboard.rects.items():
            for rect in rects:
                new_rect = deepcopy(rect)
                new_rect.x1 += ox
                new_rect.y1 += oy
                new_rect.x2 += ox
                new_rect.y2 += oy
                new_rect.sel = SelectionState.SELECTED
                self._context.add_rect(layer, new_rect)

        # Paste lines
        for layer, lines in self._clipboard.lines.items():
            for line in lines:
                new_line = deepcopy(line)
                new_line.x1 += ox
                new_line.y1 += oy
                new_line.x2 += ox
                new_line.y2 += oy
                new_line.sel = SelectionState.SELECTED
                self._context.add_line(layer, new_line)

        # Paste arcs
        for layer, arcs in self._clipboard.arcs.items():
            for arc in arcs:
                new_arc = deepcopy(arc)
                new_arc.x += ox
                new_arc.y += oy
                new_arc.sel = SelectionState.SELECTED
                self._context.add_arc(layer, new_arc)

        # Paste polygons
        for layer, polys in self._clipboard.polygons.items():
            for poly in polys:
                new_poly = deepcopy(poly)
                new_poly.x = new_poly.x + ox
                new_poly.y = new_poly.y + oy
                new_poly.sel = SelectionState.SELECTED
                self._context.add_polygon(layer, new_poly)

        # Paste instances
        for inst in self._clipboard.instances:
            new_inst = deepcopy(inst)
            new_inst.x0 += ox
            new_inst.y0 += oy
            new_inst.sel = SelectionState.SELECTED
            self._context.add_instance(new_inst)

        self._renderer.render()
        logger.info("Paste completed with offset=(%.3f, %.3f)", ox, oy)

    def _has_clipboard_data(self) -> bool:
        """Check if clipboard has data."""
        return (
            bool(self._clipboard.wires) or
            bool(self._clipboard.texts) or
            bool(self._clipboard.rects) or
            bool(self._clipboard.lines) or
            bool(self._clipboard.arcs) or
            bool(self._clipboard.polygons) or
            bool(self._clipboard.instances)
        )

    def _calculate_selection_center(self) -> Tuple[float, float]:
        """Calculate the center of the selection bounding box."""
        all_x = []
        all_y = []

        for wire in self._clipboard.wires:
            all_x.extend([wire.x1, wire.x2])
            all_y.extend([wire.y1, wire.y2])

        for text in self._clipboard.texts:
            all_x.append(text.x0)
            all_y.append(text.y0)

        for rects in self._clipboard.rects.values():
            for rect in rects:
                all_x.extend([rect.x1, rect.x2])
                all_y.extend([rect.y1, rect.y2])

        for inst in self._clipboard.instances:
            all_x.append(inst.x0)
            all_y.append(inst.y0)

        if all_x and all_y:
            return (
                (min(all_x) + max(all_x)) / 2,
                (min(all_y) + max(all_y)) / 2
            )
        return (0.0, 0.0)

    # -------------------------------------------------------------------------
    # Delete operation
    # -------------------------------------------------------------------------

    def delete(self) -> None:
        """Delete selected objects."""
        from pyxschem.core.primitives import SelectionState

        wires_before = len(self._context.wires)
        texts_before = len(self._context.texts)
        instances_before = len(self._context.instances)

        # Delete wires
        self._context.wires = [
            w for w in self._context.wires
            if not (w.sel & SelectionState.SELECTED)
        ]

        # Delete texts
        self._context.texts = [
            t for t in self._context.texts
            if not (t.sel & SelectionState.SELECTED)
        ]

        # Delete rects
        for layer in list(self._context.rects.keys()):
            self._context.rects[layer] = [
                r for r in self._context.rects[layer]
                if not (r.sel & SelectionState.SELECTED)
            ]

        # Delete lines
        for layer in list(self._context.lines.keys()):
            self._context.lines[layer] = [
                l for l in self._context.lines[layer]
                if not (l.sel & SelectionState.SELECTED)
            ]

        # Delete arcs
        for layer in list(self._context.arcs.keys()):
            self._context.arcs[layer] = [
                a for a in self._context.arcs[layer]
                if not (a.sel & SelectionState.SELECTED)
            ]

        # Delete polygons
        for layer in list(self._context.polygons.keys()):
            self._context.polygons[layer] = [
                p for p in self._context.polygons[layer]
                if not (p.sel & SelectionState.SELECTED)
            ]

        # Delete instances
        self._context.instances = [
            i for i in self._context.instances
            if not (i.sel & SelectionState.SELECTED)
        ]

        self._context.modified = True
        self._renderer.render()
        logger.info(
            "Delete completed (wires_removed=%d texts_removed=%d instances_removed=%d)",
            wires_before - len(self._context.wires),
            texts_before - len(self._context.texts),
            instances_before - len(self._context.instances),
        )

    # -------------------------------------------------------------------------
    # Move operation
    # -------------------------------------------------------------------------

    def move(self, dx: float, dy: float) -> None:
        """
        Move selected objects by offset.

        Args:
            dx: X offset
            dy: Y offset
        """
        from pyxschem.core.primitives import SelectionState

        # Move wires
        for wire in self._context.wires:
            if wire.sel & SelectionState.SELECTED:
                wire.x1 += dx
                wire.y1 += dy
                wire.x2 += dx
                wire.y2 += dy

        # Move texts
        for text in self._context.texts:
            if text.sel & SelectionState.SELECTED:
                text.x0 += dx
                text.y0 += dy

        # Move rects
        for layer_rects in self._context.rects.values():
            for rect in layer_rects:
                if rect.sel & SelectionState.SELECTED:
                    rect.x1 += dx
                    rect.y1 += dy
                    rect.x2 += dx
                    rect.y2 += dy

        # Move lines
        for layer_lines in self._context.lines.values():
            for line in layer_lines:
                if line.sel & SelectionState.SELECTED:
                    line.x1 += dx
                    line.y1 += dy
                    line.x2 += dx
                    line.y2 += dy

        # Move arcs
        for layer_arcs in self._context.arcs.values():
            for arc in layer_arcs:
                if arc.sel & SelectionState.SELECTED:
                    arc.x += dx
                    arc.y += dy

        # Move polygons
        for layer_polys in self._context.polygons.values():
            for poly in layer_polys:
                if poly.sel & SelectionState.SELECTED:
                    poly.x = poly.x + dx
                    poly.y = poly.y + dy

        # Move instances
        for inst in self._context.instances:
            if inst.sel & SelectionState.SELECTED:
                inst.x0 += dx
                inst.y0 += dy

        self._context.modified = True
        self._renderer.render()
        logger.info("Move completed (dx=%.3f, dy=%.3f)", dx, dy)

    # -------------------------------------------------------------------------
    # Rotate operation
    # -------------------------------------------------------------------------

    def rotate(self, degrees: int = 90) -> None:
        """
        Rotate selected objects around their center.

        Args:
            degrees: Rotation angle (90, 180, 270)
        """
        from pyxschem.core.primitives import SelectionState
        import math

        # Calculate center of selection
        center = self._get_selection_center()
        if center is None:
            logger.warning("Rotate requested without selection")
            return

        cx, cy = center
        rad = math.radians(degrees)
        cos_a = math.cos(rad)
        sin_a = math.sin(rad)

        def rotate_point(x: float, y: float) -> Tuple[float, float]:
            """Rotate a point around the center."""
            dx = x - cx
            dy = y - cy
            new_x = cx + dx * cos_a - dy * sin_a
            new_y = cy + dx * sin_a + dy * cos_a
            return (new_x, new_y)

        # Rotate wires
        for wire in self._context.wires:
            if wire.sel & SelectionState.SELECTED:
                wire.x1, wire.y1 = rotate_point(wire.x1, wire.y1)
                wire.x2, wire.y2 = rotate_point(wire.x2, wire.y2)

        # Rotate texts
        for text in self._context.texts:
            if text.sel & SelectionState.SELECTED:
                text.x0, text.y0 = rotate_point(text.x0, text.y0)
                text.rot = (text.rot + degrees // 90) % 4

        # Rotate rects
        for layer_rects in self._context.rects.values():
            for rect in layer_rects:
                if rect.sel & SelectionState.SELECTED:
                    rect.x1, rect.y1 = rotate_point(rect.x1, rect.y1)
                    rect.x2, rect.y2 = rotate_point(rect.x2, rect.y2)

        # Rotate lines
        for layer_lines in self._context.lines.values():
            for line in layer_lines:
                if line.sel & SelectionState.SELECTED:
                    line.x1, line.y1 = rotate_point(line.x1, line.y1)
                    line.x2, line.y2 = rotate_point(line.x2, line.y2)

        # Rotate arcs
        for layer_arcs in self._context.arcs.values():
            for arc in layer_arcs:
                if arc.sel & SelectionState.SELECTED:
                    arc.x, arc.y = rotate_point(arc.x, arc.y)
                    arc.a = (arc.a + degrees) % 360

        # Rotate polygons
        for layer_polys in self._context.polygons.values():
            for poly in layer_polys:
                if poly.sel & SelectionState.SELECTED:
                    import numpy as np
                    for i in range(len(poly.x)):
                        new_x, new_y = rotate_point(poly.x[i], poly.y[i])
                        poly.x[i] = new_x
                        poly.y[i] = new_y

        # Rotate instances
        for inst in self._context.instances:
            if inst.sel & SelectionState.SELECTED:
                inst.x0, inst.y0 = rotate_point(inst.x0, inst.y0)
                inst.rot = (inst.rot + degrees // 90) % 4

        self._context.modified = True
        self._renderer.render()
        logger.info("Rotate completed (degrees=%d center=%s)", degrees, center)

    # -------------------------------------------------------------------------
    # Flip operations
    # -------------------------------------------------------------------------

    def flip_horizontal(self) -> None:
        """Flip selected objects horizontally around their center."""
        from pyxschem.core.primitives import SelectionState

        center = self._get_selection_center()
        if center is None:
            logger.warning("Horizontal flip requested without selection")
            return

        cx, cy = center

        def flip_x(x: float) -> float:
            return 2 * cx - x

        # Flip wires
        for wire in self._context.wires:
            if wire.sel & SelectionState.SELECTED:
                wire.x1 = flip_x(wire.x1)
                wire.x2 = flip_x(wire.x2)

        # Flip texts
        for text in self._context.texts:
            if text.sel & SelectionState.SELECTED:
                text.x0 = flip_x(text.x0)
                text.flip = 1 - text.flip

        # Flip rects
        for layer_rects in self._context.rects.values():
            for rect in layer_rects:
                if rect.sel & SelectionState.SELECTED:
                    rect.x1 = flip_x(rect.x1)
                    rect.x2 = flip_x(rect.x2)

        # Flip lines
        for layer_lines in self._context.lines.values():
            for line in layer_lines:
                if line.sel & SelectionState.SELECTED:
                    line.x1 = flip_x(line.x1)
                    line.x2 = flip_x(line.x2)

        # Flip arcs
        for layer_arcs in self._context.arcs.values():
            for arc in layer_arcs:
                if arc.sel & SelectionState.SELECTED:
                    arc.x = flip_x(arc.x)
                    # Flip arc angles
                    arc.a = 180 - arc.a - arc.b

        # Flip polygons
        for layer_polys in self._context.polygons.values():
            for poly in layer_polys:
                if poly.sel & SelectionState.SELECTED:
                    import numpy as np
                    poly.x = 2 * cx - poly.x

        # Flip instances
        for inst in self._context.instances:
            if inst.sel & SelectionState.SELECTED:
                inst.x0 = flip_x(inst.x0)
                inst.flip = 1 - inst.flip

        self._context.modified = True
        self._renderer.render()
        logger.info("Horizontal flip completed (center=%s)", center)

    def flip_vertical(self) -> None:
        """Flip selected objects vertically around their center."""
        from pyxschem.core.primitives import SelectionState

        center = self._get_selection_center()
        if center is None:
            logger.warning("Vertical flip requested without selection")
            return

        cx, cy = center

        def flip_y(y: float) -> float:
            return 2 * cy - y

        # Flip wires
        for wire in self._context.wires:
            if wire.sel & SelectionState.SELECTED:
                wire.y1 = flip_y(wire.y1)
                wire.y2 = flip_y(wire.y2)

        # Flip texts
        for text in self._context.texts:
            if text.sel & SelectionState.SELECTED:
                text.y0 = flip_y(text.y0)
                # Vertical flip with rotation adjustment
                if text.rot in [0, 2]:
                    text.flip = 1 - text.flip
                else:
                    text.rot = (text.rot + 2) % 4

        # Flip rects
        for layer_rects in self._context.rects.values():
            for rect in layer_rects:
                if rect.sel & SelectionState.SELECTED:
                    rect.y1 = flip_y(rect.y1)
                    rect.y2 = flip_y(rect.y2)

        # Flip lines
        for layer_lines in self._context.lines.values():
            for line in layer_lines:
                if line.sel & SelectionState.SELECTED:
                    line.y1 = flip_y(line.y1)
                    line.y2 = flip_y(line.y2)

        # Flip arcs
        for layer_arcs in self._context.arcs.values():
            for arc in layer_arcs:
                if arc.sel & SelectionState.SELECTED:
                    arc.y = flip_y(arc.y)
                    # Flip arc angles
                    arc.a = -arc.a - arc.b

        # Flip polygons
        for layer_polys in self._context.polygons.values():
            for poly in layer_polys:
                if poly.sel & SelectionState.SELECTED:
                    import numpy as np
                    poly.y = 2 * cy - poly.y

        # Flip instances
        for inst in self._context.instances:
            if inst.sel & SelectionState.SELECTED:
                inst.y0 = flip_y(inst.y0)
                # Vertical flip combines flip and rotation
                if inst.rot in [0, 2]:
                    inst.flip = 1 - inst.flip
                else:
                    inst.rot = (inst.rot + 2) % 4

        self._context.modified = True
        self._renderer.render()
        logger.info("Vertical flip completed (center=%s)", center)

    def _get_selection_center(self) -> Optional[Tuple[float, float]]:
        """Get the center of the current selection."""
        from pyxschem.core.primitives import SelectionState

        all_x = []
        all_y = []

        for wire in self._context.wires:
            if wire.sel & SelectionState.SELECTED:
                all_x.extend([wire.x1, wire.x2])
                all_y.extend([wire.y1, wire.y2])

        for text in self._context.texts:
            if text.sel & SelectionState.SELECTED:
                all_x.append(text.x0)
                all_y.append(text.y0)

        for layer_rects in self._context.rects.values():
            for rect in layer_rects:
                if rect.sel & SelectionState.SELECTED:
                    all_x.extend([rect.x1, rect.x2])
                    all_y.extend([rect.y1, rect.y2])

        for layer_lines in self._context.lines.values():
            for line in layer_lines:
                if line.sel & SelectionState.SELECTED:
                    all_x.extend([line.x1, line.x2])
                    all_y.extend([line.y1, line.y2])

        for inst in self._context.instances:
            if inst.sel & SelectionState.SELECTED:
                all_x.append(inst.x0)
                all_y.append(inst.y0)

        if all_x and all_y:
            return (
                (min(all_x) + max(all_x)) / 2,
                (min(all_y) + max(all_y)) / 2
            )
        return None

    # -------------------------------------------------------------------------
    # Duplicate operation
    # -------------------------------------------------------------------------

    def duplicate(self, offset: Tuple[float, float] = (20.0, 20.0)) -> None:
        """
        Duplicate selected objects with an offset.

        Args:
            offset: Offset from original position
        """
        self.copy()
        self.paste(offset)
        logger.info("Duplicate completed with offset=(%.3f, %.3f)", offset[0], offset[1])
