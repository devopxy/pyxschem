"""
Bus label expansion for PyXSchem.

This module expands bus notation in net labels to individual signals.

Expansion rules:
    A[7:0]      → A[7],A[6],A[5],A[4],A[3],A[2],A[1],A[0]
    A[0:3]      → A[0],A[1],A[2],A[3]
    3*VDD       → VDD,VDD,VDD
    VDD*3       → VDD,VDD,VDD (each signal repeated)
    A,B,C       → A,B,C (already expanded)
    D[1:0],CLK  → D[1],D[0],CLK

This is a Python implementation of xschem's expandlabel.y parser.
"""

import re
from typing import List, Tuple, Optional
from dataclasses import dataclass


@dataclass
class ExpandedLabel:
    """Result of label expansion."""
    signals: List[str]  # List of individual signal names
    multiplicity: int   # Total number of signals


def expand_label(label: str) -> ExpandedLabel:
    """
    Expand a bus label into individual signals.

    Args:
        label: Bus label like "A[7:0]" or "3*VDD"

    Returns:
        ExpandedLabel with list of signals and multiplicity

    Examples:
        >>> expand_label("A[7:0]")
        ExpandedLabel(signals=['A[7]', 'A[6]', ..., 'A[0]'], multiplicity=8)
        >>> expand_label("3*VDD")
        ExpandedLabel(signals=['VDD', 'VDD', 'VDD'], multiplicity=3)
    """
    if not label or not label.strip():
        return ExpandedLabel(signals=[], multiplicity=0)

    label = label.strip()
    signals = _expand_expression(label)
    return ExpandedLabel(signals=signals, multiplicity=len(signals))


def expand_bus(label: str) -> Tuple[List[str], int]:
    """
    Expand a bus label (convenience function).

    Args:
        label: Bus label

    Returns:
        (list of signals, multiplicity)
    """
    result = expand_label(label)
    return result.signals, result.multiplicity


def _expand_expression(expr: str) -> List[str]:
    """
    Expand a label expression recursively.

    Handles:
    - Comma-separated lists: A,B,C
    - Multiplication prefix: 3*signal
    - Multiplication suffix: signal*3
    - Bus ranges: A[7:0], B[0:3]
    - Combinations: 2*A[1:0],B
    """
    expr = expr.strip()
    if not expr:
        return []

    # Handle comma-separated signals at top level
    signals = _split_top_level_commas(expr)
    if len(signals) > 1:
        result = []
        for sig in signals:
            result.extend(_expand_expression(sig))
        return result

    # Single expression - check for multiplication
    mult_match = re.match(r'^(\d+)\s*\*\s*(.+)$', expr)
    if mult_match:
        count = int(mult_match.group(1))
        rest = mult_match.group(2)
        expanded = _expand_expression(rest)
        # N*signal means repeat the whole list N times
        return expanded * count

    mult_match = re.match(r'^(.+?)\s*\*\s*(\d+)$', expr)
    if mult_match:
        base = mult_match.group(1)
        count = int(mult_match.group(2))
        expanded = _expand_expression(base)
        # signal*N means repeat each signal N times
        result = []
        for sig in expanded:
            result.extend([sig] * count)
        return result

    # Check for bus range notation
    result = _expand_bus_range(expr)
    if result is not None:
        return result

    # Plain signal name
    return [expr]


def _split_top_level_commas(expr: str) -> List[str]:
    """
    Split expression by commas at top level only.

    Respects brackets so A[1,2],B splits to ['A[1,2]', 'B'].
    """
    parts = []
    current = []
    bracket_depth = 0
    paren_depth = 0

    for char in expr:
        if char == '[':
            bracket_depth += 1
        elif char == ']':
            bracket_depth -= 1
        elif char == '(':
            paren_depth += 1
        elif char == ')':
            paren_depth -= 1
        elif char == ',' and bracket_depth == 0 and paren_depth == 0:
            parts.append(''.join(current).strip())
            current = []
            continue
        current.append(char)

    if current:
        parts.append(''.join(current).strip())

    return [p for p in parts if p]


def _expand_bus_range(expr: str) -> Optional[List[str]]:
    """
    Expand bus range notation like A[7:0] or B[0:3].

    Returns None if not a bus range expression.
    """
    # Match patterns like: name[start:end] or name[start:end]suffix
    # Also handles: name[index] (single bit)

    # Pattern for range: name[start:end]suffix
    range_match = re.match(
        r'^([a-zA-Z_][a-zA-Z0-9_]*)\[(-?\d+):(-?\d+)\](.*)$',
        expr
    )
    if range_match:
        name = range_match.group(1)
        start = int(range_match.group(2))
        end = int(range_match.group(3))
        suffix = range_match.group(4)

        if start <= end:
            indices = range(start, end + 1)
        else:
            indices = range(start, end - 1, -1)

        return [f"{name}[{i}]{suffix}" for i in indices]

    # Pattern for single index with suffix expansion
    # e.g., A[3]B[1:0] would need recursive handling
    # For now, handle simple cases

    # Check for patterns like name<start:end> (angle bracket notation)
    angle_match = re.match(
        r'^([a-zA-Z_][a-zA-Z0-9_]*)<(-?\d+):(-?\d+)>(.*)$',
        expr
    )
    if angle_match:
        name = angle_match.group(1)
        start = int(angle_match.group(2))
        end = int(angle_match.group(3))
        suffix = angle_match.group(4)

        if start <= end:
            indices = range(start, end + 1)
        else:
            indices = range(start, end - 1, -1)

        return [f"{name}<{i}>{suffix}" for i in indices]

    # Pattern for range without brackets: A7:0 -> A7,A6,...,A0
    nobracket_match = re.match(
        r'^([a-zA-Z_][a-zA-Z0-9_]*)(-?\d+):(-?\d+)(.*)$',
        expr
    )
    if nobracket_match:
        name = nobracket_match.group(1)
        start = int(nobracket_match.group(2))
        end = int(nobracket_match.group(3))
        suffix = nobracket_match.group(4)

        if start <= end:
            indices = range(start, end + 1)
        else:
            indices = range(start, end - 1, -1)

        return [f"{name}{i}{suffix}" for i in indices]

    return None


def get_bus_width(label: str) -> int:
    """
    Get the bus width (number of signals) for a label.

    Args:
        label: Bus label

    Returns:
        Number of signals after expansion
    """
    return expand_label(label).multiplicity


def is_bus(label: str) -> bool:
    """
    Check if a label represents a bus (multiple signals).

    Args:
        label: Net label

    Returns:
        True if label expands to multiple signals
    """
    return get_bus_width(label) > 1


def get_signal_at_index(label: str, index: int) -> str:
    """
    Get the signal name at a specific index in the expanded bus.

    Args:
        label: Bus label
        index: Index (0-based)

    Returns:
        Signal name at the given index

    Raises:
        IndexError: If index is out of range
    """
    signals = expand_label(label).signals
    if index < 0 or index >= len(signals):
        raise IndexError(f"Index {index} out of range for bus width {len(signals)}")
    return signals[index]
