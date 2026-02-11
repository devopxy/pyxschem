"""
Symbol loader for PyXSchem.

Loads .sym files and caches them for reuse. Resolves relative paths
against configured library directories and the current schematic's directory.
"""

import os
import logging
from pathlib import Path
from typing import Optional, Dict, List

from pyxschem.core.symbol import Symbol
from pyxschem.core.context import SchematicContext

logger = logging.getLogger(__name__)


class SymbolLoader:
    """
    Loads and caches symbol definitions from .sym files.

    Symbols are cached by their resolved absolute path so that multiple
    instances of the same symbol share one Symbol object.
    """

    # Default library paths to search for symbols
    DEFAULT_LIBRARY_PATHS = [
        "/usr/share/xschem",
        "/usr/local/share/xschem",
        "~/.xschem",
    ]

    def __init__(self, library_paths: Optional[List[str]] = None):
        self._cache: Dict[str, Symbol] = {}
        self._library_paths = self._resolve_library_paths(library_paths)

    def _resolve_library_paths(self, paths: Optional[List[str]]) -> List[str]:
        """Build the list of library search directories."""
        result = []

        if paths:
            for p in paths:
                expanded = os.path.expanduser(p)
                if os.path.isdir(expanded):
                    result.append(expanded)

        # Add defaults
        for p in self.DEFAULT_LIBRARY_PATHS:
            expanded = os.path.expanduser(p)
            if os.path.isdir(expanded) and expanded not in result:
                result.append(expanded)

        # Check XSCHEM_LIBRARY_PATH environment variable
        env_path = os.environ.get("XSCHEM_LIBRARY_PATH")
        if env_path:
            for p in env_path.split(":"):
                if os.path.isdir(p) and p not in result:
                    result.append(p)

        return result

    def resolve_symbol_path(self, name: str, context: Optional[SchematicContext] = None) -> Optional[str]:
        """
        Resolve a symbol name to an absolute file path.

        Search order:
        1. Absolute path (if name is already absolute)
        2. Relative to current schematic directory
        3. Each library path

        Args:
            name: Symbol name/path (e.g., "devices/resistor.sym")
            context: Current schematic context for relative path resolution

        Returns:
            Absolute path to .sym file, or None if not found
        """
        # Already absolute
        if os.path.isabs(name) and os.path.isfile(name):
            return name

        # Relative to current schematic directory
        if context and context.current_name:
            sch_dir = os.path.dirname(os.path.abspath(context.current_name))
            candidate = os.path.join(sch_dir, name)
            if os.path.isfile(candidate):
                return os.path.abspath(candidate)

        # Search library paths
        for lib_path in self._library_paths:
            candidate = os.path.join(lib_path, name)
            if os.path.isfile(candidate):
                return os.path.abspath(candidate)

        logger.warning("Symbol '%s' not found in any search path", name)
        return None

    def load_symbol(self, name: str, context: SchematicContext) -> Optional[Symbol]:
        """
        Load a symbol, using the cache if possible.

        If the symbol is already in the context's symbol_map, returns that.
        Otherwise resolves the path, loads the .sym file, adds it to
        the context, and caches it.

        Args:
            name: Symbol name/path
            context: Schematic context to add the symbol to

        Returns:
            Loaded Symbol, or None if the file could not be found/parsed
        """
        # Check context first
        existing = context.get_symbol(name)
        if existing is not None:
            return existing

        # Check loader cache
        resolved = self.resolve_symbol_path(name, context)
        if resolved is None:
            return None

        if resolved in self._cache:
            symbol = self._cache[resolved]
            # Add to context if not already there
            if context.get_symbol(name) is None:
                symbol_copy = self._copy_symbol(symbol, name)
                context.add_symbol(symbol_copy)
                return symbol_copy
            return context.get_symbol(name)

        # Load from file
        try:
            from pyxschem.io.schematic_reader import SchematicReader

            reader = SchematicReader()
            symbol = reader.read_symbol(Path(resolved))
            symbol.name = name  # Use the original reference name
            self._cache[resolved] = symbol

            # Add to context
            context.add_symbol(symbol)
            logger.info("Loaded symbol '%s' from '%s' (%d pins)", name, resolved, symbol.pin_count)
            return symbol
        except Exception as e:
            logger.error("Failed to load symbol '%s': %s", name, e)
            return None

    def _copy_symbol(self, symbol: Symbol, name: str) -> Symbol:
        """Create a shallow copy of a cached symbol with a new name."""
        from copy import copy
        sym = copy(symbol)
        sym.name = name
        return sym

    def clear_cache(self) -> None:
        """Clear the symbol cache."""
        self._cache.clear()
