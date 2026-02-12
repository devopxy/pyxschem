"""JSON-backed application configuration for PyXSchem."""

from __future__ import annotations

from copy import deepcopy
import json
import logging
import os
from pathlib import Path
from typing import Any


logger = logging.getLogger(__name__)


DEFAULT_CONFIGS: dict[str, dict[str, Any]] = {
    "ui": {
        "window": {
            "geometry": "",
            "state": "",
            "minimum_size": [1024, 768],
        },
        "recent_files": [],
        "theme": "dark",
        "show_grid": True,
        "snap_to_grid": True,
        "toolbar": {
            "style": "ToolButtonTextUnderIcon",
            "icon_size": 20,
            "quick_visible": True,
            "draw_visible": True,
            "sim_visible": True,
        },
        "dock": {
            "workflow_visible": True,
            "terminal_visible": True,
        },
    },
    "menus": {
        "enable_vscode_menus": True,
        "reserved_shortcuts": ["Esc", "Escape"],
        "shortcuts": {
            "file.clear_symbol": "Ctrl+Shift+N",
            "file.open_new_window": "Alt+O",
            "file.new_tab": "Ctrl+T",
            "file.save_as": "Ctrl+Shift+S",
            "file.reload": "Alt+S",
            "file.export_pdf_ps": "*",
            "file.export_png": "Ctrl+*",
            "file.export_svg": "Alt+*",
            "file.close_schematic": "Ctrl+W",
            "file.quit": "Ctrl+Q",
            "edit.undo": "U",
            "edit.redo": "Shift+U",
            "edit.select_all": "Ctrl+A",
            "edit.duplicate": "C",
            "edit.horizontal_flip": "Shift+F",
            "edit.vertical_flip": "Shift+V",
            "edit.push_schematic": "E",
            "edit.push_symbol": "I",
            "edit.pop": "Ctrl+E",
            "view.zoom_in": "Shift+Z",
            "view.zoom_box": "Z",
            "options.double_snap_threshold": "Shift+G",
            "properties.edit": "Q",
            "properties.edit_header": "Shift+B",
            "tools.search": "Ctrl+F",
            "symbol.attach_labels": "Shift+H",
            "highlight.highlight_selected": "K",
            "highlight.unhighlight_all": "Shift+K",
            "help.help": "?"
        },
        "vscode_like_menus": [
            {
                "title": "&Selection",
                "items": [
                    {"label": "Select All", "callback": "select_all", "shortcut": "Ctrl+A"},
                    {"label": "Deselect All", "callback": "deselect_all"},
                    {"separator": True},
                    {"label": "Duplicate", "callback": "duplicate", "shortcut": "Ctrl+D"},
                ],
            },
            {
                "title": "&Go",
                "items": [
                    {"label": "Go Back", "callback": "go_back", "shortcut": "Alt+Left"},
                    {"label": "Command Palette...", "callback": "open_command_palette", "shortcut": "Ctrl+Shift+P"},
                ],
            },
            {
                "title": "&Run",
                "items": [
                    {"label": "Run Simulation", "callback": "run_simulation", "shortcut": "F5"},
                    {"label": "Stop Simulation", "callback": "stop_simulation", "shortcut": "Shift+F5"},
                    {"separator": True},
                    {"label": "Run Python Script...", "callback": "run_python_script_dialog"},
                    {"label": "Run Workflow...", "callback": "run_workflow_dialog"},
                ],
            },
            {
                "title": "&Terminal",
                "items": [
                    {"label": "Toggle Terminal Panel", "callback": "toggle_terminal_panel", "shortcut": "Ctrl+Alt+T"},
                    {"label": "Clear Terminal Output", "callback": "clear_terminal_output"},
                    {"label": "Clear Debug Console", "callback": "clear_debug_console"},
                ],
            },
            {
                "title": "E&xtensions",
                "items": [
                    {"label": "Reload Plugins", "callback": "reload_plugins"},
                    {"label": "Plugins Folder", "callback": "show_plugins_folder"},
                    {"label": "Installed Plugins", "callback": "show_installed_plugins"},
                ],
            },
            {
                "title": "&Debug",
                "items": [
                    {"label": "Start Debug Session", "callback": "start_debug_session", "shortcut": "F6"},
                    {"label": "Stop Debug Session", "callback": "stop_debug_session", "shortcut": "Shift+F6"},
                    {"label": "Toggle Debug Console", "callback": "toggle_debug_console"},
                ],
            },
        ],
    },
    "plugins": {
        "enabled": True,
        "directories": [
            "~/.pyxschem/plugins",
            "./.pyxschem/plugins",
        ],
        "files": [],
        "disabled": [],
    },
    "automation": {
        "enabled": True,
        "script_directories": [
            "~/.pyxschem/scripts",
            "./.pyxschem/scripts",
        ],
        "workflow_directories": [
            "~/.pyxschem/workflows",
            "./.pyxschem/workflows",
        ],
        "last_script": "",
        "last_workflow": "",
    },
}


def _deep_merge(default: dict[str, Any], current: dict[str, Any]) -> dict[str, Any]:
    """Merge current config into defaults recursively."""
    merged = deepcopy(default)
    for key, value in current.items():
        if isinstance(value, dict) and isinstance(merged.get(key), dict):
            merged[key] = _deep_merge(merged[key], value)
        else:
            merged[key] = value
    return merged


def _path_get(data: dict[str, Any], dotted_path: str, default: Any = None) -> Any:
    """Read a nested key from dotted path notation."""
    node: Any = data
    for part in dotted_path.split("."):
        if not isinstance(node, dict) or part not in node:
            return default
        node = node[part]
    return node


def _path_set(data: dict[str, Any], dotted_path: str, value: Any) -> None:
    """Set a nested key using dotted path notation."""
    node = data
    parts = dotted_path.split(".")
    for part in parts[:-1]:
        if part not in node or not isinstance(node[part], dict):
            node[part] = {}
        node = node[part]
    node[parts[-1]] = value


class JsonConfigManager:
    """Manages PyXSchem configuration files stored as JSON."""

    def __init__(self, config_dir: str | Path | None = None):
        base_dir = os.environ.get("PYXSCHEM_CONFIG_DIR")
        root = Path(base_dir or config_dir or Path.home() / ".pyxschem" / "config")
        self._config_dir = root.expanduser().resolve()
        self._config_dir.mkdir(parents=True, exist_ok=True)

        self._paths: dict[str, Path] = {
            section: self._config_dir / f"{section}.json"
            for section in DEFAULT_CONFIGS
        }
        self._data: dict[str, dict[str, Any]] = {}

        self._load_all()

    @property
    def config_dir(self) -> Path:
        """Return configuration directory path."""
        return self._config_dir

    def file_path(self, section: str) -> Path:
        """Return configuration file path for a section."""
        return self._paths[section]

    def sections(self) -> tuple[str, ...]:
        """Return known configuration section names."""
        return tuple(self._data.keys())

    def section(self, section: str) -> dict[str, Any]:
        """Return a deep copy of a full section."""
        data = self._data.get(section)
        if data is None:
            return {}
        return deepcopy(data)

    def get(self, section: str, dotted_path: str, default: Any = None) -> Any:
        """Get a value from a section by dotted path."""
        data = self._data.get(section)
        if data is None:
            return default
        return _path_get(data, dotted_path, default)

    def set(self, section: str, dotted_path: str, value: Any) -> None:
        """Set a value in a section by dotted path."""
        if section not in self._data:
            self._data[section] = {}
        _path_set(self._data[section], dotted_path, value)

    def save_section(self, section: str) -> None:
        """Write one configuration section to disk."""
        if section not in self._data:
            return

        path = self._paths[section]
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("w", encoding="utf-8") as handle:
            json.dump(self._data[section], handle, indent=2, sort_keys=True)
            handle.write("\n")

    def save_all(self) -> None:
        """Write all configuration sections to disk."""
        for section in self._data:
            self.save_section(section)

    def expand_config_paths(self, section: str, dotted_path: str) -> list[Path]:
        """Expand configured filesystem paths relative to CWD if needed."""
        raw_values = self.get(section, dotted_path, [])
        expanded: list[Path] = []
        if not isinstance(raw_values, list):
            return expanded

        for entry in raw_values:
            if not isinstance(entry, str) or not entry.strip():
                continue
            path = Path(entry).expanduser()
            if not path.is_absolute():
                path = (Path.cwd() / path).resolve()
            expanded.append(path)
        return expanded

    def ensure_runtime_directories(self) -> None:
        """Create script/workflow/plugin directories declared in JSON config."""
        groups = [
            ("plugins", "directories"),
            ("automation", "script_directories"),
            ("automation", "workflow_directories"),
        ]
        for section, key in groups:
            for path in self.expand_config_paths(section, key):
                try:
                    path.mkdir(parents=True, exist_ok=True)
                except OSError as exc:
                    logger.warning(
                        "Unable to create runtime directory '%s' from %s.%s: %s",
                        path,
                        section,
                        key,
                        exc,
                    )

    def _load_all(self) -> None:
        """Load every config file, creating defaults when needed."""
        for section, default in DEFAULT_CONFIGS.items():
            path = self._paths[section]
            loaded: dict[str, Any] = {}

            if path.exists():
                try:
                    with path.open("r", encoding="utf-8") as handle:
                        parsed = json.load(handle)
                        if isinstance(parsed, dict):
                            loaded = parsed
                        else:
                            logger.warning("Config '%s' is not a JSON object; resetting to defaults", path)
                except (OSError, json.JSONDecodeError) as exc:
                    logger.warning("Failed to load config '%s': %s", path, exc)
            else:
                logger.info("Creating default config file '%s'", path)

            self._data[section] = _deep_merge(default, loaded)
            self.save_section(section)

        self.ensure_runtime_directories()
