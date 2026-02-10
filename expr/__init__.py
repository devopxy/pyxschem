"""
Expression system for PyXSchem.

This module provides:
- Bus expansion: A[7:0] → A[7],A[6],...,A[0]
- Math evaluation: expr(2*pi) → 6.283185...
"""

from pyxschem.expr.bus_expander import expand_label, expand_bus
from pyxschem.expr.math_eval import eval_expr, eval_expr_eng

__all__ = [
    "expand_label",
    "expand_bus",
    "eval_expr",
    "eval_expr_eng",
]
