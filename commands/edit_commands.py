"""
Concrete edit commands for PyXSchem undo/redo.

Each command captures the state needed to execute and reverse an operation.
"""

from typing import List, Dict, Optional, Any, TYPE_CHECKING
from dataclasses import dataclass, field
from copy import deepcopy
import logging

from pyxschem.commands.base import Command

if TYPE_CHECKING:
    from pyxschem.core.context import SchematicContext
    from pyxschem.graphics.renderer import SchematicRenderer

logger = logging.getLogger(__name__)


@dataclass
class _Snapshot:
    """Snapshot of selected items for undo."""
    wires: List = field(default_factory=list)
    texts: List = field(default_factory=list)
    rects: Dict[int, List] = field(default_factory=dict)
    lines: Dict[int, List] = field(default_factory=dict)
    arcs: Dict[int, List] = field(default_factory=dict)
    polygons: Dict[int, List] = field(default_factory=dict)
    instances: List = field(default_factory=list)
    # Indices for removal
    wire_indices: List[int] = field(default_factory=list)
    text_indices: List[int] = field(default_factory=list)
    instance_indices: List[int] = field(default_factory=list)


def _take_selected_snapshot(context: "SchematicContext") -> _Snapshot:
    """Capture a deep copy of all selected items and their indices."""
    from pyxschem.core.primitives import SelectionState

    snap = _Snapshot()

    for i, w in enumerate(context.wires):
        if w.sel & SelectionState.SELECTED:
            snap.wires.append(deepcopy(w))
            snap.wire_indices.append(i)

    for i, t in enumerate(context.texts):
        if t.sel & SelectionState.SELECTED:
            snap.texts.append(deepcopy(t))
            snap.text_indices.append(i)

    for i, inst in enumerate(context.instances):
        if inst.sel & SelectionState.SELECTED:
            snap.instances.append(deepcopy(inst))
            snap.instance_indices.append(i)

    for layer, rects in context.rects.items():
        selected = [deepcopy(r) for r in rects if r.sel & SelectionState.SELECTED]
        if selected:
            snap.rects[layer] = selected

    for layer, lines in context.lines.items():
        selected = [deepcopy(l) for l in lines if l.sel & SelectionState.SELECTED]
        if selected:
            snap.lines[layer] = selected

    for layer, arcs in context.arcs.items():
        selected = [deepcopy(a) for a in arcs if a.sel & SelectionState.SELECTED]
        if selected:
            snap.arcs[layer] = selected

    for layer, polys in context.polygons.items():
        selected = [deepcopy(p) for p in polys if p.sel & SelectionState.SELECTED]
        if selected:
            snap.polygons[layer] = selected

    return snap


class DeleteCommand(Command):
    """Delete selected items, reversible."""

    def __init__(self, context: "SchematicContext", renderer: "SchematicRenderer"):
        self._context = context
        self._renderer = renderer
        self._snapshot: Optional[_Snapshot] = None

    @property
    def description(self) -> str:
        return "Delete"

    def execute(self) -> None:
        from pyxschem.core.primitives import SelectionState

        # Capture before deleting
        self._snapshot = _take_selected_snapshot(self._context)

        # Remove selected items (reverse index order to avoid shifting)
        for i in sorted(self._snapshot.wire_indices, reverse=True):
            del self._context.wires[i]
        for i in sorted(self._snapshot.text_indices, reverse=True):
            del self._context.texts[i]
        for i in sorted(self._snapshot.instance_indices, reverse=True):
            del self._context.instances[i]

        for layer, rects in list(self._context.rects.items()):
            self._context.rects[layer] = [r for r in rects if not (r.sel & SelectionState.SELECTED)]
        for layer, lines in list(self._context.lines.items()):
            self._context.lines[layer] = [l for l in lines if not (l.sel & SelectionState.SELECTED)]
        for layer, arcs in list(self._context.arcs.items()):
            self._context.arcs[layer] = [a for a in arcs if not (a.sel & SelectionState.SELECTED)]
        for layer, polys in list(self._context.polygons.items()):
            self._context.polygons[layer] = [p for p in polys if not (p.sel & SelectionState.SELECTED)]

        self._context.modified = True
        self._renderer.render()

    def undo(self) -> None:
        if not self._snapshot:
            return

        # Re-insert items at their original indices
        for i, w in zip(self._snapshot.wire_indices, self._snapshot.wires):
            self._context.wires.insert(i, deepcopy(w))
        for i, t in zip(self._snapshot.text_indices, self._snapshot.texts):
            self._context.texts.insert(i, deepcopy(t))
        for i, inst in zip(self._snapshot.instance_indices, self._snapshot.instances):
            self._context.instances.insert(i, deepcopy(inst))

        for layer, rects in self._snapshot.rects.items():
            if layer not in self._context.rects:
                self._context.rects[layer] = []
            self._context.rects[layer].extend(deepcopy(rects))
        for layer, lines in self._snapshot.lines.items():
            if layer not in self._context.lines:
                self._context.lines[layer] = []
            self._context.lines[layer].extend(deepcopy(lines))
        for layer, arcs in self._snapshot.arcs.items():
            if layer not in self._context.arcs:
                self._context.arcs[layer] = []
            self._context.arcs[layer].extend(deepcopy(arcs))
        for layer, polys in self._snapshot.polygons.items():
            if layer not in self._context.polygons:
                self._context.polygons[layer] = []
            self._context.polygons[layer].extend(deepcopy(polys))

        self._context.modified = True
        self._renderer.render()


class MoveCommand(Command):
    """Move selected items by dx, dy."""

    def __init__(self, context: "SchematicContext", renderer: "SchematicRenderer", dx: float, dy: float):
        self._context = context
        self._renderer = renderer
        self._dx = dx
        self._dy = dy
        self._snapshot = _take_selected_snapshot(context)

    @property
    def description(self) -> str:
        return f"Move ({self._dx:.0f}, {self._dy:.0f})"

    def execute(self) -> None:
        self._apply_offset(self._dx, self._dy)

    def undo(self) -> None:
        self._apply_offset(-self._dx, -self._dy)

    def _apply_offset(self, dx: float, dy: float) -> None:
        from pyxschem.core.primitives import SelectionState

        for w in self._context.wires:
            if w.sel & SelectionState.SELECTED:
                w.x1 += dx; w.y1 += dy
                w.x2 += dx; w.y2 += dy

        for t in self._context.texts:
            if t.sel & SelectionState.SELECTED:
                t.x0 += dx; t.y0 += dy

        for inst in self._context.instances:
            if inst.sel & SelectionState.SELECTED:
                inst.x0 += dx; inst.y0 += dy
                inst.x1 += dx; inst.y1 += dy
                inst.x2 += dx; inst.y2 += dy

        for layer_rects in self._context.rects.values():
            for r in layer_rects:
                if r.sel & SelectionState.SELECTED:
                    r.x1 += dx; r.y1 += dy
                    r.x2 += dx; r.y2 += dy

        for layer_lines in self._context.lines.values():
            for l in layer_lines:
                if l.sel & SelectionState.SELECTED:
                    l.x1 += dx; l.y1 += dy
                    l.x2 += dx; l.y2 += dy

        for layer_arcs in self._context.arcs.values():
            for a in layer_arcs:
                if a.sel & SelectionState.SELECTED:
                    a.x += dx; a.y += dy

        for layer_polys in self._context.polygons.values():
            for p in layer_polys:
                if p.sel & SelectionState.SELECTED:
                    p.x += dx; p.y += dy

        self._context.modified = True
        self._renderer.render()


class RotateCommand(Command):
    """Rotate selected items by degrees around center."""

    def __init__(self, context: "SchematicContext", renderer: "SchematicRenderer",
                 degrees: int, cx: float, cy: float):
        self._context = context
        self._renderer = renderer
        self._degrees = degrees
        self._cx = cx
        self._cy = cy
        self._snapshot = _take_selected_snapshot(context)

    @property
    def description(self) -> str:
        return f"Rotate {self._degrees}\u00b0"

    def execute(self) -> None:
        self._rotate(self._degrees)

    def undo(self) -> None:
        self._rotate(-self._degrees)

    def _rotate(self, degrees: int) -> None:
        import math
        from pyxschem.core.primitives import SelectionState

        rad = math.radians(degrees)
        cos_a = round(math.cos(rad))
        sin_a = round(math.sin(rad))
        cx, cy = self._cx, self._cy

        def rot_point(x, y):
            dx, dy = x - cx, y - cy
            return cx + dx * cos_a - dy * sin_a, cy + dx * sin_a + dy * cos_a

        for w in self._context.wires:
            if w.sel & SelectionState.SELECTED:
                w.x1, w.y1 = rot_point(w.x1, w.y1)
                w.x2, w.y2 = rot_point(w.x2, w.y2)

        for t in self._context.texts:
            if t.sel & SelectionState.SELECTED:
                t.x0, t.y0 = rot_point(t.x0, t.y0)
                t.rot = (t.rot + (degrees // 90)) % 4

        for inst in self._context.instances:
            if inst.sel & SelectionState.SELECTED:
                inst.x0, inst.y0 = rot_point(inst.x0, inst.y0)
                inst.rot = (inst.rot + (degrees // 90)) % 4

        for layer_rects in self._context.rects.values():
            for r in layer_rects:
                if r.sel & SelectionState.SELECTED:
                    r.x1, r.y1 = rot_point(r.x1, r.y1)
                    r.x2, r.y2 = rot_point(r.x2, r.y2)

        for layer_lines in self._context.lines.values():
            for l in layer_lines:
                if l.sel & SelectionState.SELECTED:
                    l.x1, l.y1 = rot_point(l.x1, l.y1)
                    l.x2, l.y2 = rot_point(l.x2, l.y2)

        for layer_arcs in self._context.arcs.values():
            for a in layer_arcs:
                if a.sel & SelectionState.SELECTED:
                    a.x, a.y = rot_point(a.x, a.y)
                    a.a = (a.a + degrees) % 360

        for layer_polys in self._context.polygons.values():
            for p in layer_polys:
                if p.sel & SelectionState.SELECTED:
                    for i in range(p.points):
                        p.x[i], p.y[i] = rot_point(p.x[i], p.y[i])

        self._context.modified = True
        self._renderer.render()


class FlipCommand(Command):
    """Flip selected items horizontally or vertically."""

    def __init__(self, context: "SchematicContext", renderer: "SchematicRenderer",
                 horizontal: bool, cx: float, cy: float):
        self._context = context
        self._renderer = renderer
        self._horizontal = horizontal
        self._cx = cx
        self._cy = cy

    @property
    def description(self) -> str:
        axis = "horizontal" if self._horizontal else "vertical"
        return f"Flip {axis}"

    def execute(self) -> None:
        self._flip()

    def undo(self) -> None:
        # Flip is its own inverse
        self._flip()

    def _flip(self) -> None:
        from pyxschem.core.primitives import SelectionState

        cx, cy = self._cx, self._cy

        for w in self._context.wires:
            if w.sel & SelectionState.SELECTED:
                if self._horizontal:
                    w.x1 = 2 * cx - w.x1
                    w.x2 = 2 * cx - w.x2
                else:
                    w.y1 = 2 * cy - w.y1
                    w.y2 = 2 * cy - w.y2

        for t in self._context.texts:
            if t.sel & SelectionState.SELECTED:
                if self._horizontal:
                    t.x0 = 2 * cx - t.x0
                    t.flip ^= 1
                else:
                    t.y0 = 2 * cy - t.y0

        for inst in self._context.instances:
            if inst.sel & SelectionState.SELECTED:
                if self._horizontal:
                    inst.x0 = 2 * cx - inst.x0
                    inst.flip ^= 1
                else:
                    inst.y0 = 2 * cy - inst.y0

        for layer_rects in self._context.rects.values():
            for r in layer_rects:
                if r.sel & SelectionState.SELECTED:
                    if self._horizontal:
                        r.x1 = 2 * cx - r.x1
                        r.x2 = 2 * cx - r.x2
                    else:
                        r.y1 = 2 * cy - r.y1
                        r.y2 = 2 * cy - r.y2

        for layer_lines in self._context.lines.values():
            for l in layer_lines:
                if l.sel & SelectionState.SELECTED:
                    if self._horizontal:
                        l.x1 = 2 * cx - l.x1
                        l.x2 = 2 * cx - l.x2
                    else:
                        l.y1 = 2 * cy - l.y1
                        l.y2 = 2 * cy - l.y2

        for layer_arcs in self._context.arcs.values():
            for a in layer_arcs:
                if a.sel & SelectionState.SELECTED:
                    if self._horizontal:
                        a.x = 2 * cx - a.x
                    else:
                        a.y = 2 * cy - a.y

        for layer_polys in self._context.polygons.values():
            for p in layer_polys:
                if p.sel & SelectionState.SELECTED:
                    for i in range(p.points):
                        if self._horizontal:
                            p.x[i] = 2 * cx - p.x[i]
                        else:
                            p.y[i] = 2 * cy - p.y[i]

        self._context.modified = True
        self._renderer.render()


class PasteCommand(Command):
    """Paste items from clipboard, reversible."""

    def __init__(self, context: "SchematicContext", renderer: "SchematicRenderer",
                 wires=None, texts=None, instances=None,
                 rects=None, lines=None, arcs=None, polygons=None):
        self._context = context
        self._renderer = renderer
        self._wires = deepcopy(wires or [])
        self._texts = deepcopy(texts or [])
        self._instances = deepcopy(instances or [])
        self._rects = deepcopy(rects or {})
        self._lines = deepcopy(lines or {})
        self._arcs = deepcopy(arcs or {})
        self._polygons = deepcopy(polygons or {})

    @property
    def description(self) -> str:
        return "Paste"

    def execute(self) -> None:
        for w in self._wires:
            self._context.wires.append(deepcopy(w))
        for t in self._texts:
            self._context.texts.append(deepcopy(t))
        for inst in self._instances:
            self._context.instances.append(deepcopy(inst))
        for layer, rects in self._rects.items():
            if layer not in self._context.rects:
                self._context.rects[layer] = []
            self._context.rects[layer].extend(deepcopy(rects))
        for layer, lines in self._lines.items():
            if layer not in self._context.lines:
                self._context.lines[layer] = []
            self._context.lines[layer].extend(deepcopy(lines))
        for layer, arcs in self._arcs.items():
            if layer not in self._context.arcs:
                self._context.arcs[layer] = []
            self._context.arcs[layer].extend(deepcopy(arcs))
        for layer, polys in self._polygons.items():
            if layer not in self._context.polygons:
                self._context.polygons[layer] = []
            self._context.polygons[layer].extend(deepcopy(polys))

        self._context.modified = True
        self._renderer.render()

    def undo(self) -> None:
        # Remove the items that were pasted (from the end)
        n_wires = len(self._wires)
        n_texts = len(self._texts)
        n_instances = len(self._instances)

        if n_wires:
            del self._context.wires[-n_wires:]
        if n_texts:
            del self._context.texts[-n_texts:]
        if n_instances:
            del self._context.instances[-n_instances:]

        for layer, rects in self._rects.items():
            if layer in self._context.rects:
                n = len(rects)
                del self._context.rects[layer][-n:]
        for layer, lines in self._lines.items():
            if layer in self._context.lines:
                n = len(lines)
                del self._context.lines[layer][-n:]
        for layer, arcs in self._arcs.items():
            if layer in self._context.arcs:
                n = len(arcs)
                del self._context.arcs[layer][-n:]
        for layer, polys in self._polygons.items():
            if layer in self._context.polygons:
                n = len(polys)
                del self._context.polygons[layer][-n:]

        self._context.modified = True
        self._renderer.render()


class AddPrimitiveCommand(Command):
    """Add a single primitive (wire, line, rect, etc.), reversible."""

    def __init__(self, context: "SchematicContext", renderer: "SchematicRenderer",
                 primitive_type: str, primitive: Any, layer: int = 0):
        self._context = context
        self._renderer = renderer
        self._type = primitive_type
        self._primitive = deepcopy(primitive)
        self._layer = layer

    @property
    def description(self) -> str:
        return f"Add {self._type}"

    def execute(self) -> None:
        if self._type == "wire":
            self._context.add_wire(self._primitive)
        elif self._type == "text":
            self._context.add_text(self._primitive)
        elif self._type == "instance":
            self._context.add_instance(self._primitive)
        elif self._type == "rect":
            self._context.add_rect(self._layer, self._primitive)
        elif self._type == "line":
            self._context.add_line(self._layer, self._primitive)
        elif self._type == "arc":
            self._context.add_arc(self._layer, self._primitive)
        elif self._type == "polygon":
            self._context.add_polygon(self._layer, self._primitive)
        self._renderer.render()

    def undo(self) -> None:
        if self._type == "wire":
            if self._context.wires:
                self._context.wires.pop()
        elif self._type == "text":
            if self._context.texts:
                self._context.texts.pop()
        elif self._type == "instance":
            if self._context.instances:
                self._context.instances.pop()
        elif self._type == "rect":
            if self._layer in self._context.rects and self._context.rects[self._layer]:
                self._context.rects[self._layer].pop()
        elif self._type == "line":
            if self._layer in self._context.lines and self._context.lines[self._layer]:
                self._context.lines[self._layer].pop()
        elif self._type == "arc":
            if self._layer in self._context.arcs and self._context.arcs[self._layer]:
                self._context.arcs[self._layer].pop()
        elif self._type == "polygon":
            if self._layer in self._context.polygons and self._context.polygons[self._layer]:
                self._context.polygons[self._layer].pop()
        self._context.modified = True
        self._renderer.render()


class PropertyChangeCommand(Command):
    """Change a property value on an object, reversible."""

    def __init__(self, context: "SchematicContext", renderer: "SchematicRenderer",
                 obj: Any, attr: str, new_value: Any):
        self._context = context
        self._renderer = renderer
        self._obj = obj
        self._attr = attr
        self._old_value = getattr(obj, attr)
        self._new_value = new_value

    @property
    def description(self) -> str:
        return f"Change {self._attr}"

    def execute(self) -> None:
        setattr(self._obj, self._attr, self._new_value)
        self._context.modified = True
        self._renderer.render()

    def undo(self) -> None:
        setattr(self._obj, self._attr, self._old_value)
        self._context.modified = True
        self._renderer.render()
