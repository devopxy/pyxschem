"""
Math expression evaluator for PyXSchem.

Evaluates mathematical expressions embedded in property strings using
the expr() and expr_eng() syntax.

Syntax:
    expr(2*pi)      → 6.283185307179586
    expr(sin(1.57)) → 0.9999996829318346
    expr_eng(1e-9)  → 1n
    expr_eng4(1e-9) → 1.000n

Supported functions:
    sin, cos, tan, asin, acos, atan, log, ln, exp, sqrt, int, round

Supported constants:
    pi, e, k (Boltzmann), h (Planck), echarge, abszero, c (speed of light)

This is a Python implementation of xschem's eval_expr.y parser.
"""

import re
import math
from typing import Optional, Dict, Callable


# Mathematical constants
CONSTANTS: Dict[str, float] = {
    "pi": math.pi,
    "e": math.e,
    "k": 1.380649e-23,      # Boltzmann constant
    "h": 6.62607e-34,       # Planck constant
    "echarge": 1.60217646e-19,  # Elementary charge
    "abszero": 273.15,      # Absolute zero in Celsius
    "c": 2.99792458e8,      # Speed of light
}

# Mathematical functions
FUNCTIONS: Dict[str, Callable[[float], float]] = {
    "sin": math.sin,
    "cos": math.cos,
    "tan": math.tan,
    "asin": math.asin,
    "acos": math.acos,
    "atan": math.atan,
    "log": math.log10,
    "ln": math.log,
    "exp": math.exp,
    "sqrt": math.sqrt,
    "int": lambda x: math.ceil(x) if x < 0 else math.floor(x),
    "round": round,
    "round1": lambda x: round(x, 1),
    "round6": lambda x: round(x, 6),
    "abs": abs,
    "floor": math.floor,
    "ceil": math.ceil,
}

# SPICE engineering suffixes
SPICE_SUFFIXES = {
    "T": 1e12,
    "G": 1e9,
    "MEG": 1e6,
    "K": 1e3,
    "M": 1e-3,
    "U": 1e-6,
    "N": 1e-9,
    "P": 1e-12,
    "F": 1e-15,
    "A": 1e-18,
}

# Engineering notation suffixes for output
ENG_SUFFIXES = [
    (1e18, "E"),
    (1e15, "P"),  # Note: conflicts with pico, use context
    (1e12, "T"),
    (1e9, "G"),
    (1e6, "M"),
    (1e3, "k"),
    (1e0, ""),
    (1e-3, "m"),
    (1e-6, "u"),
    (1e-9, "n"),
    (1e-12, "p"),
    (1e-15, "f"),
    (1e-18, "a"),
]


def eval_expr(text: str) -> str:
    """
    Evaluate all expr() expressions in a string.

    Args:
        text: String containing expr(...) expressions

    Returns:
        String with expr() replaced by evaluated values

    Example:
        >>> eval_expr("value=expr(2*pi)")
        'value=6.283185307179586'
    """
    return _process_expressions(text, engineering=False)


def eval_expr_eng(text: str, digits: int = 3) -> str:
    """
    Evaluate all expr_eng() expressions with engineering notation output.

    Args:
        text: String containing expr_eng(...) expressions
        digits: Number of significant digits

    Returns:
        String with expr_eng() replaced by engineering notation values

    Example:
        >>> eval_expr_eng("value=expr_eng(1e-9)")
        'value=1n'
    """
    return _process_expressions(text, engineering=True, digits=digits)


def _process_expressions(text: str, engineering: bool = False, digits: int = 3) -> str:
    """Process all expression types in text."""
    if not text:
        return text

    result = text

    # Process expr_eng4() first (most specific)
    result = _replace_expr_type(result, "expr_eng4", engineering=True, digits=4)

    # Process expr_eng()
    result = _replace_expr_type(result, "expr_eng", engineering=True, digits=digits)

    # Process expr()
    result = _replace_expr_type(result, "expr", engineering=False, digits=digits)

    return result


def _replace_expr_type(text: str, expr_type: str, engineering: bool, digits: int) -> str:
    """Replace all occurrences of a specific expression type."""
    pattern = re.escape(expr_type) + r'\s*\('

    result = []
    i = 0

    while i < len(text):
        match = re.match(pattern, text[i:])
        if match:
            # Find the matching closing parenthesis
            start = i + match.end()
            end, expr_str = _find_matching_paren(text, start)

            if end is not None:
                try:
                    value = _evaluate_expression(expr_str)
                    if engineering:
                        result.append(_to_engineering(value, digits))
                    else:
                        result.append(f"{value:.15g}")
                except Exception:
                    # On error, keep original expression without expr() wrapper
                    result.append(expr_str)

                i = end + 1  # Skip past closing paren
            else:
                result.append(text[i])
                i += 1
        else:
            result.append(text[i])
            i += 1

    return "".join(result)


def _find_matching_paren(text: str, start: int) -> tuple[Optional[int], str]:
    """Find the matching closing parenthesis and extract the expression."""
    depth = 1
    i = start

    while i < len(text) and depth > 0:
        if text[i] == '(':
            depth += 1
        elif text[i] == ')':
            depth -= 1
        i += 1

    if depth == 0:
        return i - 1, text[start:i - 1]
    return None, ""


def _evaluate_expression(expr_str: str) -> float:
    """
    Evaluate a mathematical expression string.

    Args:
        expr_str: Expression like "2*pi" or "sin(1.57)"

    Returns:
        Evaluated result
    """
    # Preprocess: handle SPICE suffixes in numbers
    expr_str = _preprocess_spice_numbers(expr_str)

    # Replace constants
    for name, value in CONSTANTS.items():
        # Use word boundaries to avoid partial matches
        expr_str = re.sub(rf'\b{name}\b', str(value), expr_str)

    # Replace functions with Python equivalents
    for name, func in FUNCTIONS.items():
        # Functions are called with parentheses
        pattern = rf'\b{name}\s*\('
        replacement = f"_fn_{name}("
        expr_str = re.sub(pattern, replacement, expr_str)

    # Build evaluation context
    eval_context = {f"_fn_{name}": func for name, func in FUNCTIONS.items()}
    eval_context["__builtins__"] = {}  # Restrict builtins for safety

    try:
        result = eval(expr_str, eval_context)
        return float(result)
    except Exception as e:
        raise ValueError(f"Failed to evaluate expression '{expr_str}': {e}")


def _preprocess_spice_numbers(expr: str) -> str:
    """
    Convert SPICE notation numbers to Python floats.

    Examples:
        1k → 1e3
        10u → 10e-6
        3.3MEG → 3.3e6
    """
    # Pattern to match number followed by suffix
    pattern = r'(\d+\.?\d*)\s*(T|G|MEG|K|M|U|N|P|F|A)\b'

    def replace_suffix(match):
        number = float(match.group(1))
        suffix = match.group(2).upper()
        if suffix in SPICE_SUFFIXES:
            return str(number * SPICE_SUFFIXES[suffix])
        return match.group(0)

    return re.sub(pattern, replace_suffix, expr, flags=re.IGNORECASE)


def _to_engineering(value: float, digits: int = 3) -> str:
    """
    Convert a value to engineering notation string.

    Args:
        value: Numeric value
        digits: Number of significant digits

    Returns:
        Engineering notation string like "1.5k" or "10n"
    """
    if value == 0:
        return "0"

    abs_value = abs(value)
    sign = "-" if value < 0 else ""

    for threshold, suffix in ENG_SUFFIXES:
        if abs_value >= threshold * 0.9999:  # Small tolerance for rounding
            scaled = abs_value / threshold
            if digits <= 0:
                return f"{sign}{scaled:.0f}{suffix}"
            else:
                # Format with appropriate precision
                formatted = f"{scaled:.{digits}g}"
                return f"{sign}{formatted}{suffix}"

    # Very small value
    return f"{value:.{digits}g}"


def parse_spice_value(value_str: str) -> float:
    """
    Parse a SPICE-format value string to float.

    Args:
        value_str: Value like "10k", "1.5u", "3.3MEG"

    Returns:
        Float value

    Example:
        >>> parse_spice_value("10k")
        10000.0
        >>> parse_spice_value("1.5u")
        1.5e-6
    """
    value_str = value_str.strip()
    if not value_str:
        return 0.0

    # Check for suffix
    for suffix, multiplier in SPICE_SUFFIXES.items():
        if value_str.upper().endswith(suffix):
            num_part = value_str[:-len(suffix)]
            try:
                return float(num_part) * multiplier
            except ValueError:
                pass

    # Try direct conversion
    try:
        return float(value_str)
    except ValueError:
        return 0.0


def format_spice_value(value: float) -> str:
    """
    Format a float as a SPICE-format value string.

    Args:
        value: Numeric value

    Returns:
        SPICE notation string

    Example:
        >>> format_spice_value(10000)
        '10k'
        >>> format_spice_value(1.5e-6)
        '1.5u'
    """
    return _to_engineering(value, digits=4)
