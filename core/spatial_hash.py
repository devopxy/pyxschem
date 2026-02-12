"""
Spatial hash table for efficient object lookup.

This module implements a spatial hash table that divides the schematic
coordinate space into a grid of cells. Objects are inserted into all
cells that their bounding box overlaps, enabling O(1) average-case
lookups for objects in a given region.

This is a Python implementation of xschem's spatial hash tables from
netlist.c (inst_spatial_table, wire_spatial_table, object_spatial_table).
"""

from dataclasses import dataclass, field
from enum import IntEnum, auto
from typing import (
    Iterator,
    Generic,
    TypeVar,
    Optional,
    Set,
    Tuple,
    List,
    Dict,
)
import math


# Grid constants matching xschem
BOXSIZE = 400.0  # Size of each spatial hash cell
NBOXES = 50      # Number of cells in each dimension (50x50 grid)


class ObjectType(IntEnum):
    """Object type identifiers for the spatial hash."""
    WIRE = auto()
    INSTANCE = auto()
    RECT = auto()
    LINE = auto()
    ARC = auto()
    POLYGON = auto()
    TEXT = auto()


@dataclass
class HashEntry:
    """Entry in the spatial hash table."""
    obj_type: ObjectType
    index: int           # Index in the object array
    layer: int = 0       # Layer number (for layer-organized objects)


T = TypeVar("T")


class SpatialHashTable(Generic[T]):
    """
    Spatial hash table for efficient object lookup by location.

    The coordinate space is divided into a NBOXES x NBOXES grid where
    each cell is BOXSIZE x BOXSIZE units. Objects are stored by their
    index in all cells that their bounding box overlaps.

    Attributes:
        grid: 2D grid of sets, each containing object indices

    Example:
        >>> table = SpatialHashTable()
        >>> table.insert((0, 0, 100, 100), 0)  # Insert object 0 with bbox
        >>> table.insert((50, 50, 150, 150), 1)  # Insert object 1
        >>> list(table.query((75, 75, 80, 80)))  # Query overlapping objects
        [0, 1]
    """

    def __init__(self):
        # Initialize empty grid - each cell is a set of (obj_index)
        self._grid: List[List[Set[int]]] = [
            [set() for _ in range(NBOXES)]
            for _ in range(NBOXES)
        ]
        self._count = 0

    def _get_cell_range(
        self, x1: float, y1: float, x2: float, y2: float
    ) -> Tuple[int, int, int, int]:
        """
        Get the range of cells that a bounding box overlaps.

        Returns:
            (x1a, y1a, x2a, y2a) - grid cell indices
        """
        # Ensure ordered bbox
        if x2 < x1:
            x1, x2 = x2, x1
        if y2 < y1:
            y1, y2 = y2, y1

        # Calculate grid indices
        x1a = int(math.floor(x1 / BOXSIZE))
        y1a = int(math.floor(y1 / BOXSIZE))
        x2a = int(math.floor(x2 / BOXSIZE))
        y2a = int(math.floor(y2 / BOXSIZE))

        return x1a, y1a, x2a, y2a

    def _wrap_index(self, i: int) -> int:
        """Wrap index to valid range using modulo."""
        idx = i % NBOXES
        if idx < 0:
            idx += NBOXES
        return idx

    def insert(self, bbox: Tuple[float, float, float, float], obj_index: int) -> None:
        """
        Insert an object into the spatial hash table.

        Args:
            bbox: Bounding box as (x1, y1, x2, y2)
            obj_index: Index of the object in its array
        """
        x1, y1, x2, y2 = bbox
        x1a, y1a, x2a, y2a = self._get_cell_range(x1, y1, x2, y2)

        # Insert into all overlapping cells (with wrap limit)
        count_i = 0
        for i in range(x1a, x2a + 1):
            if count_i >= NBOXES:
                break
            count_i += 1
            gi = self._wrap_index(i)

            count_j = 0
            for j in range(y1a, y2a + 1):
                if count_j >= NBOXES:
                    break
                count_j += 1
                gj = self._wrap_index(j)

                self._grid[gi][gj].add(obj_index)

        self._count += 1

    def remove(self, bbox: Tuple[float, float, float, float], obj_index: int) -> None:
        """
        Remove an object from the spatial hash table.

        Args:
            bbox: Bounding box as (x1, y1, x2, y2)
            obj_index: Index of the object in its array
        """
        x1, y1, x2, y2 = bbox
        x1a, y1a, x2a, y2a = self._get_cell_range(x1, y1, x2, y2)

        count_i = 0
        for i in range(x1a, x2a + 1):
            if count_i >= NBOXES:
                break
            count_i += 1
            gi = self._wrap_index(i)

            count_j = 0
            for j in range(y1a, y2a + 1):
                if count_j >= NBOXES:
                    break
                count_j += 1
                gj = self._wrap_index(j)

                self._grid[gi][gj].discard(obj_index)

        self._count -= 1

    def query(
        self, bbox: Tuple[float, float, float, float]
    ) -> Iterator[int]:
        """
        Query all objects that may overlap a bounding box.

        Note: This returns candidates - the actual bounding boxes should
        be checked for precise intersection.

        Args:
            bbox: Query bounding box as (x1, y1, x2, y2)

        Yields:
            Object indices that may overlap the query box
        """
        x1, y1, x2, y2 = bbox
        x1a, y1a, x2a, y2a = self._get_cell_range(x1, y1, x2, y2)

        seen: Set[int] = set()

        count_i = 0
        for i in range(x1a, x2a + 1):
            if count_i >= NBOXES:
                break
            count_i += 1
            gi = self._wrap_index(i)

            count_j = 0
            for j in range(y1a, y2a + 1):
                if count_j >= NBOXES:
                    break
                count_j += 1
                gj = self._wrap_index(j)

                for obj_index in self._grid[gi][gj]:
                    if obj_index not in seen:
                        seen.add(obj_index)
                        yield obj_index

    def query_point(self, x: float, y: float) -> Iterator[int]:
        """
        Query all objects at a specific point.

        Args:
            x, y: Point coordinates

        Yields:
            Object indices that may contain the point
        """
        gi = self._wrap_index(int(math.floor(x / BOXSIZE)))
        gj = self._wrap_index(int(math.floor(y / BOXSIZE)))

        yield from self._grid[gi][gj]

    def clear(self) -> None:
        """Clear all entries from the hash table."""
        for row in self._grid:
            for cell in row:
                cell.clear()
        self._count = 0

    @property
    def count(self) -> int:
        """Number of objects in the hash table."""
        return self._count

    def __len__(self) -> int:
        return self._count


class TypedSpatialHashTable:
    """
    Spatial hash table that stores object type and layer information.

    This is used for mixed-type queries where objects of different
    types (wires, instances, rects, etc.) need to be stored together.
    """

    def __init__(self):
        self._grid: List[List[List[HashEntry]]] = [
            [[] for _ in range(NBOXES)]
            for _ in range(NBOXES)
        ]
        self._count = 0

    def _get_cell_range(
        self, x1: float, y1: float, x2: float, y2: float
    ) -> Tuple[int, int, int, int]:
        """Get the range of cells that a bounding box overlaps."""
        if x2 < x1:
            x1, x2 = x2, x1
        if y2 < y1:
            y1, y2 = y2, y1

        x1a = int(math.floor(x1 / BOXSIZE))
        y1a = int(math.floor(y1 / BOXSIZE))
        x2a = int(math.floor(x2 / BOXSIZE))
        y2a = int(math.floor(y2 / BOXSIZE))

        return x1a, y1a, x2a, y2a

    def _wrap_index(self, i: int) -> int:
        """Wrap index to valid range using modulo."""
        idx = i % NBOXES
        if idx < 0:
            idx += NBOXES
        return idx

    def insert(
        self,
        bbox: Tuple[float, float, float, float],
        obj_type: ObjectType,
        index: int,
        layer: int = 0,
    ) -> None:
        """
        Insert an object into the spatial hash table.

        Args:
            bbox: Bounding box as (x1, y1, x2, y2)
            obj_type: Type of object
            index: Index of the object in its array
            layer: Layer number (for layer-organized objects)
        """
        x1, y1, x2, y2 = bbox
        x1a, y1a, x2a, y2a = self._get_cell_range(x1, y1, x2, y2)
        entry = HashEntry(obj_type=obj_type, index=index, layer=layer)

        count_i = 0
        for i in range(x1a, x2a + 1):
            if count_i >= NBOXES:
                break
            count_i += 1
            gi = self._wrap_index(i)

            count_j = 0
            for j in range(y1a, y2a + 1):
                if count_j >= NBOXES:
                    break
                count_j += 1
                gj = self._wrap_index(j)

                self._grid[gi][gj].append(entry)

        self._count += 1

    def remove(
        self,
        bbox: Tuple[float, float, float, float],
        obj_type: ObjectType,
        index: int,
        layer: int = 0,
    ) -> None:
        """Remove an object from the spatial hash table."""
        x1, y1, x2, y2 = bbox
        x1a, y1a, x2a, y2a = self._get_cell_range(x1, y1, x2, y2)

        count_i = 0
        for i in range(x1a, x2a + 1):
            if count_i >= NBOXES:
                break
            count_i += 1
            gi = self._wrap_index(i)

            count_j = 0
            for j in range(y1a, y2a + 1):
                if count_j >= NBOXES:
                    break
                count_j += 1
                gj = self._wrap_index(j)

                self._grid[gi][gj] = [
                    e for e in self._grid[gi][gj]
                    if not (e.obj_type == obj_type and e.index == index and e.layer == layer)
                ]

        self._count -= 1

    def query(
        self,
        bbox: Tuple[float, float, float, float],
        obj_type: Optional[ObjectType] = None,
    ) -> Iterator[HashEntry]:
        """
        Query all objects that may overlap a bounding box.

        Args:
            bbox: Query bounding box as (x1, y1, x2, y2)
            obj_type: Optional filter by object type

        Yields:
            HashEntry objects that may overlap the query box
        """
        x1, y1, x2, y2 = bbox
        x1a, y1a, x2a, y2a = self._get_cell_range(x1, y1, x2, y2)

        seen: Set[Tuple[ObjectType, int, int]] = set()

        count_i = 0
        for i in range(x1a, x2a + 1):
            if count_i >= NBOXES:
                break
            count_i += 1
            gi = self._wrap_index(i)

            count_j = 0
            for j in range(y1a, y2a + 1):
                if count_j >= NBOXES:
                    break
                count_j += 1
                gj = self._wrap_index(j)

                for entry in self._grid[gi][gj]:
                    if obj_type is not None and entry.obj_type != obj_type:
                        continue

                    key = (entry.obj_type, entry.index, entry.layer)
                    if key not in seen:
                        seen.add(key)
                        yield entry

    def query_point(
        self, x: float, y: float, obj_type: Optional[ObjectType] = None
    ) -> Iterator[HashEntry]:
        """Query all objects at a specific point."""
        gi = self._wrap_index(int(math.floor(x / BOXSIZE)))
        gj = self._wrap_index(int(math.floor(y / BOXSIZE)))

        seen: Set[Tuple[ObjectType, int, int]] = set()

        for entry in self._grid[gi][gj]:
            if obj_type is not None and entry.obj_type != obj_type:
                continue

            key = (entry.obj_type, entry.index, entry.layer)
            if key not in seen:
                seen.add(key)
                yield entry

    def clear(self) -> None:
        """Clear all entries from the hash table."""
        for row in self._grid:
            for cell in row:
                cell.clear()
        self._count = 0

    @property
    def count(self) -> int:
        """Number of objects in the hash table."""
        return self._count


def boxes_overlap(
    box1: Tuple[float, float, float, float],
    box2: Tuple[float, float, float, float],
) -> bool:
    """
    Check if two bounding boxes overlap.

    Args:
        box1: First box as (x1, y1, x2, y2)
        box2: Second box as (x1, y1, x2, y2)

    Returns:
        True if boxes overlap
    """
    ax1, ay1, ax2, ay2 = box1
    bx1, by1, bx2, by2 = box2

    # Ensure ordered
    if ax2 < ax1:
        ax1, ax2 = ax2, ax1
    if ay2 < ay1:
        ay1, ay2 = ay2, ay1
    if bx2 < bx1:
        bx1, bx2 = bx2, bx1
    if by2 < by1:
        by1, by2 = by2, by1

    # Check overlap
    return ax1 <= bx2 and ax2 >= bx1 and ay1 <= by2 and ay2 >= by1


def point_in_box(
    x: float, y: float, box: Tuple[float, float, float, float]
) -> bool:
    """
    Check if a point is inside a bounding box.

    Args:
        x, y: Point coordinates
        box: Box as (x1, y1, x2, y2)

    Returns:
        True if point is inside box
    """
    x1, y1, x2, y2 = box
    if x2 < x1:
        x1, x2 = x2, x1
    if y2 < y1:
        y1, y2 = y2, y1

    return x1 <= x <= x2 and y1 <= y <= y2
