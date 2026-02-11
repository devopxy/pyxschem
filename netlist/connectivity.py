"""
Connectivity analyzer for PyXSchem.

Implements the wire-to-wire and wire-to-pin connectivity algorithm
used to determine net assignments for netlisting.

Algorithm:
1. Build a spatial hash of all wire endpoints
2. Use union-find to group wires that touch at endpoints
3. For each instance pin, transform pin position and find touching wires
4. Propagate explicit names from labels/pins and wire lab= properties
5. Auto-name any unnamed nets (#net0, #net1, ...)
"""

import math
import logging
from typing import Optional, Dict, List, Set, Tuple

from pyxschem.core.context import SchematicContext
from pyxschem.core.symbol import Symbol, Instance, SymbolType
from pyxschem.core.property_parser import get_tok_value

logger = logging.getLogger(__name__)

# Tolerance for endpoint matching
EPS = 0.5


class UnionFind:
    """Disjoint-set / union-find data structure."""

    def __init__(self, n: int):
        self._parent = list(range(n))
        self._rank = [0] * n

    def find(self, x: int) -> int:
        while self._parent[x] != x:
            self._parent[x] = self._parent[self._parent[x]]
            x = self._parent[x]
        return x

    def union(self, a: int, b: int) -> None:
        ra, rb = self.find(a), self.find(b)
        if ra == rb:
            return
        if self._rank[ra] < self._rank[rb]:
            ra, rb = rb, ra
        self._parent[rb] = ra
        if self._rank[ra] == self._rank[rb]:
            self._rank[ra] += 1


class ConnectivityAnalyzer:
    """
    Analyzes connectivity of a schematic.

    After calling analyze(), wire.node and instance.node[] are populated
    with net names.
    """

    def __init__(self, context: SchematicContext):
        self._context = context
        self._net_counter = 0

    def analyze(self) -> Dict[str, List]:
        """
        Run full connectivity analysis.

        Returns:
            Dictionary mapping net name -> list of (type, index) tuples
            where type is 'wire', 'pin', etc.
        """
        ctx = self._context
        n_wires = len(ctx.wires)
        if n_wires == 0 and not ctx.instances:
            return {}

        logger.info("Starting connectivity analysis (%d wires, %d instances)",
                     n_wires, len(ctx.instances))

        # Step 1: Union-find over wire endpoints
        uf = UnionFind(n_wires)
        self._connect_touching_wires(uf, n_wires)

        # Step 2: Build endpoint -> wire-group map
        group_endpoints = self._build_endpoint_map(uf, n_wires)

        # Step 3: Assign explicit names from labels and wire properties
        group_names: Dict[int, str] = {}
        self._propagate_label_names(uf, group_names, n_wires)
        self._propagate_wire_lab_names(uf, group_names, n_wires)

        # Step 4: Connect instance pins to wire groups
        self._connect_instance_pins(uf, group_names, group_endpoints, n_wires)

        # Step 5: Auto-name remaining groups
        self._auto_name_groups(uf, group_names, n_wires)

        # Step 6: Write back to wires
        for i, wire in enumerate(ctx.wires):
            group = uf.find(i)
            wire.node = group_names.get(group, f"#net{group}")

        # Build net map
        net_map: Dict[str, List] = {}
        for i, wire in enumerate(ctx.wires):
            if wire.node:
                if wire.node not in net_map:
                    net_map[wire.node] = []
                net_map[wire.node].append(("wire", i))

        for i, inst in enumerate(ctx.instances):
            if inst.node:
                for pin_idx, node in enumerate(inst.node):
                    if node:
                        if node not in net_map:
                            net_map[node] = []
                        net_map[node].append(("pin", i, pin_idx))

        logger.info("Connectivity analysis complete: %d nets", len(net_map))
        return net_map

    def _connect_touching_wires(self, uf: UnionFind, n_wires: int) -> None:
        """Union wires that share an endpoint."""
        ctx = self._context
        # Simple O(n^2) for now; could use spatial hash for large schematics
        for i in range(n_wires):
            wi = ctx.wires[i]
            for j in range(i + 1, n_wires):
                wj = ctx.wires[j]
                if self._endpoints_touch(wi, wj):
                    uf.union(i, j)

    def _endpoints_touch(self, w1, w2) -> bool:
        """Check if two wires share an endpoint."""
        pts1 = [(w1.x1, w1.y1), (w1.x2, w1.y2)]
        pts2 = [(w2.x1, w2.y1), (w2.x2, w2.y2)]
        for p1 in pts1:
            for p2 in pts2:
                if abs(p1[0] - p2[0]) < EPS and abs(p1[1] - p2[1]) < EPS:
                    return True
        # Also check if endpoint of one lies on the other wire (T-junction)
        for p in pts1:
            if self._point_on_wire(p[0], p[1], w2):
                return True
        for p in pts2:
            if self._point_on_wire(p[0], p[1], w1):
                return True
        return False

    def _point_on_wire(self, px: float, py: float, w) -> bool:
        """Check if a point lies on a wire segment."""
        x1, y1, x2, y2 = w.x1, w.y1, w.x2, w.y2
        # Check collinearity and bounding box
        cross = (px - x1) * (y2 - y1) - (py - y1) * (x2 - x1)
        if abs(cross) > EPS * max(abs(x2 - x1), abs(y2 - y1), 1.0):
            return False
        if (min(x1, x2) - EPS <= px <= max(x1, x2) + EPS and
                min(y1, y2) - EPS <= py <= max(y1, y2) + EPS):
            return True
        return False

    def _build_endpoint_map(self, uf: UnionFind, n_wires: int) -> Dict[Tuple[float, float], Set[int]]:
        """Build map from snapped endpoint -> set of wire groups."""
        ctx = self._context
        ep_map: Dict[Tuple[float, float], Set[int]] = {}
        for i in range(n_wires):
            w = ctx.wires[i]
            group = uf.find(i)
            for pt in [(w.x1, w.y1), (w.x2, w.y2)]:
                snapped = (round(pt[0] / EPS) * EPS, round(pt[1] / EPS) * EPS)
                if snapped not in ep_map:
                    ep_map[snapped] = set()
                ep_map[snapped].add(group)
        return ep_map

    def _propagate_label_names(self, uf: UnionFind, group_names: Dict[int, str], n_wires: int) -> None:
        """Propagate net names from label/pin instances."""
        ctx = self._context
        for inst in ctx.instances:
            sym = self._get_symbol(inst)
            if sym is None:
                continue

            if sym.type not in (SymbolType.LABEL, SymbolType.IPIN, SymbolType.OPIN, SymbolType.IOPIN):
                continue

            # Get the label text from properties
            lab = None
            if inst.prop_ptr:
                lab = get_tok_value(inst.prop_ptr, "lab")
            if not lab:
                lab = inst.lab
            if not lab:
                continue

            # Find which wire group this label's pin touches
            pin_pos = self._get_pin_positions(inst, sym)
            for px, py in pin_pos:
                for i in range(n_wires):
                    w = ctx.wires[i]
                    if self._point_on_wire(px, py, w) or (
                        (abs(px - w.x1) < EPS and abs(py - w.y1) < EPS) or
                        (abs(px - w.x2) < EPS and abs(py - w.y2) < EPS)
                    ):
                        group = uf.find(i)
                        group_names[group] = lab
                        break

    def _propagate_wire_lab_names(self, uf: UnionFind, group_names: Dict[int, str], n_wires: int) -> None:
        """Propagate net names from wire lab= properties."""
        ctx = self._context
        for i, wire in enumerate(ctx.wires):
            if wire.prop_ptr:
                lab = get_tok_value(wire.prop_ptr, "lab")
                if lab:
                    group = uf.find(i)
                    group_names[group] = lab

    def _connect_instance_pins(self, uf: UnionFind, group_names: Dict[int, str],
                                group_endpoints: Dict, n_wires: int) -> None:
        """Connect instance pins to wire groups and assign node names."""
        ctx = self._context
        for inst_idx, inst in enumerate(ctx.instances):
            sym = self._get_symbol(inst)
            if sym is None:
                continue

            # Skip label/pin types - they're already handled
            if sym.type in (SymbolType.LABEL, SymbolType.IPIN, SymbolType.OPIN, SymbolType.IOPIN):
                continue

            pin_positions = self._get_pin_positions(inst, sym)
            pin_names = sym.get_pin_names()
            inst.init_nodes(len(pin_positions))

            for pin_idx, (px, py) in enumerate(pin_positions):
                # Find wire group at this pin position
                assigned = False
                for i in range(n_wires):
                    w = ctx.wires[i]
                    if self._point_on_wire(px, py, w) or (
                        (abs(px - w.x1) < EPS and abs(py - w.y1) < EPS) or
                        (abs(px - w.x2) < EPS and abs(py - w.y2) < EPS)
                    ):
                        group = uf.find(i)
                        net_name = group_names.get(group)
                        if net_name:
                            inst.set_node(pin_idx, net_name)
                        else:
                            # Auto-assign later
                            inst.set_node(pin_idx, f"#wire_group_{group}")
                        assigned = True
                        break

                if not assigned:
                    # Unconnected pin
                    inst.set_node(pin_idx, None)

    def _auto_name_groups(self, uf: UnionFind, group_names: Dict[int, str], n_wires: int) -> None:
        """Assign auto-generated names to unnamed wire groups."""
        seen_groups: Set[int] = set()
        for i in range(n_wires):
            group = uf.find(i)
            if group not in seen_groups and group not in group_names:
                group_names[group] = f"#net{self._net_counter}"
                self._net_counter += 1
                seen_groups.add(group)

        # Update instance nodes that reference wire groups
        for inst in self._context.instances:
            if inst.node:
                for pin_idx in range(len(inst.node)):
                    node = inst.node[pin_idx]
                    if node and node.startswith("#wire_group_"):
                        group = int(node.split("_")[-1])
                        inst.node[pin_idx] = group_names.get(group, node)

    def _get_symbol(self, inst: Instance) -> Optional[Symbol]:
        """Get the symbol for an instance."""
        ctx = self._context
        if inst.ptr >= 0 and inst.ptr < len(ctx.symbols):
            return ctx.symbols[inst.ptr]
        return ctx.get_symbol(inst.name)

    def _get_pin_positions(self, inst: Instance, sym: Symbol) -> List[Tuple[float, float]]:
        """Get transformed pin positions for an instance."""
        positions = []
        for pin_rect in sym.pins:
            # Pin center
            cx = (pin_rect.x1 + pin_rect.x2) / 2.0
            cy = (pin_rect.y1 + pin_rect.y2) / 2.0

            # Apply flip
            if inst.flip:
                cx = -cx

            # Apply rotation
            rot = inst.rot % 4
            if rot == 1:
                cx, cy = -cy, cx
            elif rot == 2:
                cx, cy = -cx, -cy
            elif rot == 3:
                cx, cy = cy, -cx

            # Translate to instance position
            positions.append((inst.x0 + cx, inst.y0 + cy))

        return positions
