"""Lightweight plugin system for extending PyXSchem."""

from __future__ import annotations

from dataclasses import dataclass
import importlib.util
import logging
from pathlib import Path
from types import ModuleType
from typing import Callable, Optional, TYPE_CHECKING, Any

from pyxschem.config import JsonConfigManager

if TYPE_CHECKING:
    from pyxschem.ui.main_window import MainWindow


logger = logging.getLogger(__name__)


@dataclass
class LoadedPlugin:
    """Runtime information for a loaded plugin."""

    name: str
    path: Path
    module: ModuleType
    deactivate: Optional[Callable[["PluginAPI"], None]] = None


class PluginAPI:
    """API exposed to plugin modules."""

    def __init__(self, window: "MainWindow", manager: "PluginManager", plugin_name: str):
        self._window = window
        self._manager = manager
        self.plugin_name = plugin_name

    @property
    def window(self) -> "MainWindow":
        """Return current MainWindow object."""
        return self._window

    def register_menu_action(
        self,
        menu_name: str,
        label: str,
        callback: Callable[[], None],
        shortcut: str | None = None,
    ) -> Any:
        """Register a menu action from a plugin."""
        return self._window.register_plugin_menu_action(menu_name, label, callback, shortcut)

    def register_command(self, name: str, callback: Callable[..., Any]) -> None:
        """Register a plugin command callable."""
        self._manager.register_command(name, callback)

    def config(self) -> dict[str, Any]:
        """Return plugins section config for this session."""
        return self._window.config_manager.section("plugins")

    def log(self, message: str, *args: Any) -> None:
        """Log from plugin context."""
        logger.info("[%s] " + message, self.plugin_name, *args)


class PluginManager:
    """Loads and manages extension plugins from configured directories."""

    def __init__(self, window: "MainWindow", config_manager: JsonConfigManager):
        self._window = window
        self._config = config_manager
        self._plugins: list[LoadedPlugin] = []
        self._commands: dict[str, Callable[..., Any]] = {}

    def list_plugins(self) -> list[str]:
        """Return currently loaded plugin names."""
        return [plugin.name for plugin in self._plugins]

    def register_command(self, name: str, callback: Callable[..., Any]) -> None:
        """Register plugin command callback by name."""
        self._commands[name] = callback

    def run_command(self, name: str, *args: Any, **kwargs: Any) -> Any:
        """Run a registered plugin command."""
        callback = self._commands.get(name)
        if callback is None:
            raise KeyError(f"Plugin command '{name}' is not registered")
        return callback(*args, **kwargs)

    def discover_plugins(self) -> list[Path]:
        """Discover plugin file paths from JSON configuration."""
        if not self._config.get("plugins", "enabled", True):
            return []

        disabled = {
            name.lower()
            for name in self._config.get("plugins", "disabled", [])
            if isinstance(name, str)
        }

        candidates: list[Path] = []
        seen: set[Path] = set()

        for directory in self._config.expand_config_paths("plugins", "directories"):
            if not directory.exists() or not directory.is_dir():
                continue
            for path in sorted(directory.glob("*.py")):
                resolved = path.resolve()
                if resolved in seen:
                    continue
                if resolved.stem.lower() in disabled:
                    continue
                candidates.append(resolved)
                seen.add(resolved)

        for entry in self._config.get("plugins", "files", []):
            if not isinstance(entry, str) or not entry.strip():
                continue
            path = Path(entry).expanduser()
            if not path.is_absolute():
                path = (Path.cwd() / path).resolve()
            else:
                path = path.resolve()

            if not path.exists() or path.suffix != ".py":
                continue
            if path in seen:
                continue
            if path.stem.lower() in disabled:
                continue

            candidates.append(path)
            seen.add(path)

        return candidates

    def load_plugins(self) -> None:
        """Load plugins from configured directories."""
        if not self._config.get("plugins", "enabled", True):
            logger.info("Plugin system disabled by configuration")
            return

        discovered = self.discover_plugins()
        logger.info("Discovered %d plugin file(s)", len(discovered))

        for path in discovered:
            plugin = self._load_plugin(path)
            if plugin is not None:
                self._plugins.append(plugin)

        logger.info("Loaded %d plugin(s)", len(self._plugins))

    def unload_plugins(self) -> None:
        """Unload plugins and remove menu contributions."""
        for plugin in reversed(self._plugins):
            if plugin.deactivate is None:
                continue
            try:
                api = PluginAPI(self._window, self, plugin.name)
                plugin.deactivate(api)
            except Exception:
                logger.exception("Plugin '%s' deactivate() failed", plugin.name)

        self._plugins.clear()
        self._commands.clear()
        self._window.clear_plugin_menu_actions()

    def reload_plugins(self) -> None:
        """Reload all plugins from disk."""
        self.unload_plugins()
        self.load_plugins()

    def _load_plugin(self, path: Path) -> Optional[LoadedPlugin]:
        """Load one plugin module by file path."""
        plugin_name = path.stem
        module_name = f"pyxschem_user_plugin_{plugin_name}_{abs(hash(str(path))) & 0xFFFF_FFFF:x}"

        try:
            spec = importlib.util.spec_from_file_location(module_name, path)
            if spec is None or spec.loader is None:
                logger.warning("Unable to load plugin spec from '%s'", path)
                return None

            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)

            activate = getattr(module, "activate", None)
            if not callable(activate):
                logger.warning("Plugin '%s' missing activate(api) callable", path)
                return None

            api = PluginAPI(self._window, self, plugin_name)
            activate(api)

            deactivate = getattr(module, "deactivate", None)
            if deactivate is not None and not callable(deactivate):
                deactivate = None

            logger.info("Loaded plugin '%s' from '%s'", plugin_name, path)
            return LoadedPlugin(plugin_name, path, module, deactivate)
        except Exception:
            logger.exception("Failed to load plugin '%s'", path)
            return None
