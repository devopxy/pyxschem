"""
Format string processor for PyXSchem netlisting.

Processes xschem @-substitution format strings used in symbol definitions
to generate netlist lines.

Substitution rules:
- @pinlist     -> space-separated node names for all pins
- @name        -> instance name
- @symname     -> symbol base name
- @symref      -> symbol full path
- @body        -> template properties (excluding name/format)
- @token       -> value of 'token' from instance properties
- @@token      -> value of 'token' from instance props, with default from template
- @#n          -> node name of pin n (0-based)
- @#name:net   -> node name of pin named 'name'
- \\n          -> newline
- \\t          -> tab
"""

import re
import logging
from typing import Optional, List

from pyxschem.core.property_parser import get_tok_value

logger = logging.getLogger(__name__)


class FormatProcessor:
    """Processes @-substitution format strings for netlist generation."""

    # Pattern to match @token, @@token, @#n, @pinlist, etc.
    _TOKEN_RE = re.compile(r'@@?(?:#(\w+(?::net)?)|pinlist|name|symname|symref|body|(\w+))')

    @staticmethod
    def process(
        fmt: str,
        inst_props: str,
        templ_props: str,
        inst_name: str,
        sym_name: str,
        pin_names: List[str],
        node_names: List[Optional[str]],
    ) -> str:
        """
        Process a format string with @-substitutions.

        Args:
            fmt: Format string from symbol definition
            inst_props: Instance property string
            templ_props: Symbol template property string
            inst_name: Instance name (e.g., "R1")
            sym_name: Symbol name (e.g., "devices/resistor.sym")
            pin_names: List of pin names from symbol
            node_names: List of node names assigned to pins

        Returns:
            Processed string with all substitutions applied
        """
        if not fmt:
            return ""

        result = fmt

        # Handle escape sequences first
        result = result.replace("\\n", "\n")
        result = result.replace("\\t", "\t")

        # @pinlist -> space-separated node names
        pinlist = " ".join(n if n else "?" for n in node_names)
        result = result.replace("@pinlist", pinlist)

        # @name -> instance name
        result = result.replace("@name", inst_name or "?")

        # @symname -> symbol base name (without path and .sym)
        base = sym_name.rsplit("/", 1)[-1].replace(".sym", "")
        result = result.replace("@symname", base)

        # @symref -> full symbol reference
        result = result.replace("@symref", sym_name)

        # @body -> template props minus name/format/type
        body = FormatProcessor._extract_body(inst_props, templ_props)
        result = result.replace("@body", body)

        # @#n -> node by pin index (0-based)
        def replace_pin_ref(match):
            ref = match.group(1)
            if ref is not None:
                # @#name:net or @#n
                if ref.endswith(":net"):
                    pin_name = ref[:-4]
                    for i, pn in enumerate(pin_names):
                        if pn == pin_name:
                            return node_names[i] if i < len(node_names) and node_names[i] else "?"
                    return "?"
                else:
                    try:
                        idx = int(ref)
                        if 0 <= idx < len(node_names) and node_names[idx]:
                            return node_names[idx]
                        return "?"
                    except ValueError:
                        # Try as pin name
                        for i, pn in enumerate(pin_names):
                            if pn == ref:
                                return node_names[i] if i < len(node_names) and node_names[i] else "?"
                        return "?"

            token = match.group(2)
            if token:
                if match.group(0).startswith("@@"):
                    # @@token: instance prop with template fallback
                    val = get_tok_value(inst_props, token)
                    if not val:
                        val = get_tok_value(templ_props, token)
                    return val if val else ""
                else:
                    # @token: instance prop only
                    val = get_tok_value(inst_props, token)
                    return val if val else ""
            return match.group(0)

        result = FormatProcessor._TOKEN_RE.sub(replace_pin_ref, result)

        return result

    @staticmethod
    def _extract_body(inst_props: str, templ_props: str) -> str:
        """Extract body text (template props minus name/format/type)."""
        # Use template as base, override with instance values
        props = templ_props or ""

        # Tokens to exclude from body
        exclude = {"name", "format", "type", "verilog_format", "vhdl_format",
                    "spectre_format", "tedax_format", "template"}

        parts = []
        # Simple token=value parser
        tokens = FormatProcessor._parse_props(props)
        for key, val in tokens.items():
            if key not in exclude:
                # Check if instance overrides this
                inst_val = get_tok_value(inst_props or "", key)
                if inst_val:
                    parts.append(f"{key}={inst_val}")
                else:
                    parts.append(f"{key}={val}")

        return " ".join(parts)

    @staticmethod
    def _parse_props(props: str) -> dict:
        """Parse a property string into key=value pairs."""
        result = {}
        if not props:
            return result

        i = 0
        while i < len(props):
            # Skip whitespace
            while i < len(props) and props[i].isspace():
                i += 1
            if i >= len(props):
                break

            # Read key
            key_start = i
            while i < len(props) and props[i] not in ("=", " ", "\t", "\n"):
                i += 1

            key = props[key_start:i]
            if not key:
                break

            # Skip =
            if i < len(props) and props[i] == "=":
                i += 1
            else:
                result[key] = ""
                continue

            # Read value
            if i < len(props) and props[i] == '"':
                # Quoted value
                i += 1
                val_start = i
                while i < len(props) and props[i] != '"':
                    if props[i] == '\\':
                        i += 1
                    i += 1
                val = props[val_start:i]
                if i < len(props):
                    i += 1  # Skip closing quote
            elif i < len(props) and props[i] == '{':
                # Brace-enclosed value
                i += 1
                depth = 1
                val_start = i
                while i < len(props) and depth > 0:
                    if props[i] == '{':
                        depth += 1
                    elif props[i] == '}':
                        depth -= 1
                    elif props[i] == '\\':
                        i += 1
                    i += 1
                val = props[val_start:i - 1]
            else:
                val_start = i
                while i < len(props) and not props[i].isspace():
                    i += 1
                val = props[val_start:i]

            result[key] = val

        return result
