"""
Property string parser for PyXSchem.

Handles parsing and manipulation of property strings in the format:
    name=value key="quoted value" other=data

This replaces the token.c functions from the original xschem:
- get_tok_value: Extract a token's value
- subst_token: Replace or add a token
- has_token: Check if token exists
"""

from typing import Optional, Dict, Tuple
from enum import Enum, auto
import re


class TokenState(Enum):
    """Parser state machine states."""
    BEGIN = auto()      # Looking for token start
    TOKEN = auto()      # Reading token name
    ENDTOK = auto()     # Finished token, looking for =
    SEP = auto()        # Found =, looking for value
    VALUE = auto()      # Reading value
    END = auto()        # Finished value


def get_tok_value(prop_str: Optional[str], token: str, with_quotes: bool = False) -> str:
    """
    Extract the value of a token from a property string.

    Args:
        prop_str: Property string like "name=R1 value=10k"
        token: Token name to find (e.g., "value")
        with_quotes: If True, keep surrounding quotes in returned value

    Returns:
        Token value, or empty string if not found

    Examples:
        >>> get_tok_value("name=R1 value=10k", "value")
        '10k'
        >>> get_tok_value('desc="Hello World" name=C1', "desc")
        'Hello World'
        >>> get_tok_value('desc="Hello World"', "desc", with_quotes=True)
        '"Hello World"'
    """
    if not prop_str or not token:
        return ""

    state = TokenState.BEGIN
    current_token = []
    current_value = []
    in_quotes = False
    escape_next = False
    found_token = False

    i = 0
    while i < len(prop_str):
        c = prop_str[i]

        if state == TokenState.BEGIN:
            if c.isspace() or c == '\n':
                i += 1
                continue
            if c == '=':
                # Malformed, skip
                i += 1
                continue
            # Start of token
            current_token = [c]
            state = TokenState.TOKEN
            i += 1

        elif state == TokenState.TOKEN:
            if c == '=':
                # Check if this is our token
                tok_name = ''.join(current_token)
                if tok_name == token:
                    found_token = True
                state = TokenState.SEP
                i += 1
            elif c.isspace() or c == '\n':
                # Token without value
                if ''.join(current_token) == token:
                    return ""  # Token exists but has no value
                current_token = []
                state = TokenState.BEGIN
                i += 1
            else:
                current_token.append(c)
                i += 1

        elif state == TokenState.SEP:
            if c.isspace() and c != '\n':
                # Skip spaces after =
                i += 1
                continue
            # Start of value
            current_value = []
            in_quotes = False
            escape_next = False
            if c == '"':
                in_quotes = True
                if with_quotes:
                    current_value.append(c)
                i += 1
            elif c == '\n':
                # Empty value
                if found_token:
                    return ""
                state = TokenState.BEGIN
                i += 1
            else:
                current_value.append(c)
                i += 1
            state = TokenState.VALUE

        elif state == TokenState.VALUE:
            if escape_next:
                current_value.append(c)
                escape_next = False
                i += 1
            elif c == '\\':
                escape_next = True
                if with_quotes:
                    current_value.append(c)
                i += 1
            elif in_quotes:
                if c == '"':
                    if with_quotes:
                        current_value.append(c)
                    if found_token:
                        return ''.join(current_value)
                    state = TokenState.BEGIN
                    i += 1
                else:
                    current_value.append(c)
                    i += 1
            else:
                if c.isspace() or c == '\n':
                    if found_token:
                        return ''.join(current_value)
                    state = TokenState.BEGIN
                    i += 1
                else:
                    current_value.append(c)
                    i += 1

    # End of string
    if found_token and state == TokenState.VALUE:
        return ''.join(current_value)

    return ""


def has_token(prop_str: Optional[str], token: str) -> bool:
    """
    Check if a token exists in a property string.

    Args:
        prop_str: Property string
        token: Token name to find

    Returns:
        True if token exists (even with empty value)
    """
    if not prop_str or not token:
        return False

    # Simple regex-based check
    # Token can be at start, after whitespace, or after newline
    pattern = rf'(?:^|\s){re.escape(token)}(?:=|$|\s)'
    return bool(re.search(pattern, prop_str))


def subst_token(
    prop_str: Optional[str],
    token: str,
    new_value: Optional[str],
    add_if_missing: bool = True
) -> str:
    """
    Substitute or add a token in a property string.

    Args:
        prop_str: Original property string
        token: Token name to modify
        new_value: New value (None to remove token)
        add_if_missing: If True, add token if not present

    Returns:
        Modified property string

    Examples:
        >>> subst_token("W=1 L=0.1", "W", "5")
        'W=5 L=0.1'
        >>> subst_token("W=1 L=0.1", "m", "2")
        'W=1 L=0.1 m=2'
        >>> subst_token("W=1 L=0.1", "L", None)
        'W=1'
    """
    if not prop_str:
        if new_value is not None and add_if_missing:
            return f"{token}={_quote_if_needed(new_value)}"
        return ""

    result = []
    state = TokenState.BEGIN
    current_token = []
    token_start = 0
    token_found = False
    i = 0

    while i <= len(prop_str):
        c = prop_str[i] if i < len(prop_str) else '\0'

        if state == TokenState.BEGIN:
            if c == '\0':
                break
            if c.isspace() or c == '\n':
                result.append(c)
                i += 1
                continue
            # Start of token
            token_start = len(result)
            current_token = [c]
            state = TokenState.TOKEN
            result.append(c)
            i += 1

        elif state == TokenState.TOKEN:
            if c == '=' or c.isspace() or c == '\n' or c == '\0':
                tok_name = ''.join(current_token)
                if tok_name == token:
                    token_found = True
                    # Remove token from result
                    result = result[:token_start]
                    if c == '=':
                        state = TokenState.SEP
                        i += 1
                    else:
                        if new_value is not None:
                            if result and not result[-1].isspace():
                                result.append(' ')
                            result.append(f"{token}={_quote_if_needed(new_value)}")
                        state = TokenState.BEGIN
                        if c != '\0':
                            result.append(c)
                            i += 1
                else:
                    if c != '\0':
                        result.append(c)
                    i += 1
                    if c == '=':
                        state = TokenState.SEP
                    else:
                        state = TokenState.BEGIN
                current_token = []
            else:
                current_token.append(c)
                result.append(c)
                i += 1

        elif state == TokenState.SEP:
            if c == '\0':
                if token_found and new_value is not None:
                    result.append(f"{token}={_quote_if_needed(new_value)}")
                break
            if c == '"':
                if not token_found:
                    result.append(c)
                i += 1
                state = TokenState.VALUE
                in_quotes = True
            elif c.isspace() and c != '\n':
                if not token_found:
                    result.append(c)
                i += 1
            elif c == '\n':
                if token_found and new_value is not None:
                    result.append(f"{token}={_quote_if_needed(new_value)}")
                    result.append(c)
                elif not token_found:
                    result.append(c)
                i += 1
                state = TokenState.BEGIN
            else:
                if not token_found:
                    result.append(c)
                i += 1
                state = TokenState.VALUE
                in_quotes = False

        elif state == TokenState.VALUE:
            if c == '\0':
                if token_found and new_value is not None:
                    result.append(f"{token}={_quote_if_needed(new_value)}")
                break
            elif c == '\\' and i + 1 < len(prop_str):
                if not token_found:
                    result.append(c)
                    result.append(prop_str[i + 1])
                i += 2
            elif c == '"' and 'in_quotes' in dir() and in_quotes:
                if not token_found:
                    result.append(c)
                i += 1
                if token_found and new_value is not None:
                    if result and not result[-1].isspace():
                        result.append(' ')
                    result.append(f"{token}={_quote_if_needed(new_value)}")
                state = TokenState.BEGIN
            elif (c.isspace() or c == '\n') and not ('in_quotes' in dir() and in_quotes):
                if not token_found:
                    result.append(c)
                elif new_value is not None:
                    if result and not result[-1].isspace():
                        result.append(' ')
                    result.append(f"{token}={_quote_if_needed(new_value)}")
                    result.append(c)
                i += 1
                state = TokenState.BEGIN
            else:
                if not token_found:
                    result.append(c)
                i += 1

    # Add token if not found
    if not token_found and new_value is not None and add_if_missing:
        result_str = ''.join(result).rstrip()
        if result_str:
            result_str += ' '
        result_str += f"{token}={_quote_if_needed(new_value)}"
        return result_str

    return ''.join(result).strip()


def _quote_if_needed(value: str) -> str:
    """Add quotes around value if it contains spaces or special chars."""
    if not value:
        return '""'
    if ' ' in value or '\n' in value or '"' in value or '=' in value:
        # Escape quotes in value
        escaped = value.replace('\\', '\\\\').replace('"', '\\"')
        return f'"{escaped}"'
    return value


def parse_properties(prop_str: Optional[str]) -> Dict[str, str]:
    """
    Parse all tokens from a property string into a dictionary.

    Args:
        prop_str: Property string like "name=R1 value=10k"

    Returns:
        Dictionary of {token: value}

    Example:
        >>> parse_properties("name=R1 value=10k W=1.5u")
        {'name': 'R1', 'value': '10k', 'W': '1.5u'}
    """
    result: Dict[str, str] = {}
    if not prop_str:
        return result

    state = TokenState.BEGIN
    current_token = []
    current_value = []
    in_quotes = False
    escape_next = False

    i = 0
    while i <= len(prop_str):
        c = prop_str[i] if i < len(prop_str) else '\0'

        if state == TokenState.BEGIN:
            if c == '\0':
                break
            if c.isspace() or c == '\n':
                i += 1
                continue
            current_token = [c]
            state = TokenState.TOKEN
            i += 1

        elif state == TokenState.TOKEN:
            if c == '=':
                state = TokenState.SEP
                i += 1
            elif c.isspace() or c == '\n' or c == '\0':
                # Token without value
                tok_name = ''.join(current_token)
                if tok_name:
                    result[tok_name] = ""
                current_token = []
                state = TokenState.BEGIN
                if c != '\0':
                    i += 1
            else:
                current_token.append(c)
                i += 1

        elif state == TokenState.SEP:
            current_value = []
            in_quotes = False
            escape_next = False
            if c == '"':
                in_quotes = True
                i += 1
            elif c.isspace() and c != '\n':
                i += 1
                continue
            elif c == '\n' or c == '\0':
                tok_name = ''.join(current_token)
                if tok_name:
                    result[tok_name] = ""
                current_token = []
                state = TokenState.BEGIN
                if c != '\0':
                    i += 1
            else:
                current_value.append(c)
                i += 1
            state = TokenState.VALUE

        elif state == TokenState.VALUE:
            if escape_next:
                current_value.append(c)
                escape_next = False
                i += 1
            elif c == '\\':
                escape_next = True
                i += 1
            elif in_quotes and c == '"':
                tok_name = ''.join(current_token)
                if tok_name:
                    result[tok_name] = ''.join(current_value)
                current_token = []
                current_value = []
                state = TokenState.BEGIN
                i += 1
            elif not in_quotes and (c.isspace() or c == '\n' or c == '\0'):
                tok_name = ''.join(current_token)
                if tok_name:
                    result[tok_name] = ''.join(current_value)
                current_token = []
                current_value = []
                state = TokenState.BEGIN
                if c != '\0':
                    i += 1
            else:
                current_value.append(c)
                i += 1

    return result


def format_properties(props: Dict[str, str]) -> str:
    """
    Format a dictionary of properties into a property string.

    Args:
        props: Dictionary of {token: value}

    Returns:
        Formatted property string
    """
    parts = []
    for key, value in props.items():
        parts.append(f"{key}={_quote_if_needed(value)}")
    return ' '.join(parts)
