"""Python automation and workflow execution for PyXSchem."""

from __future__ import annotations

import builtins
import json
import logging
from pathlib import Path
import time
from types import SimpleNamespace
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from pyxschem.ui.main_window import MainWindow


logger = logging.getLogger(__name__)


class AutomationAPI:
    """Utility API exposed to user automation scripts."""

    def __init__(self, window: "MainWindow"):
        self.window = window

    def new_schematic(self) -> None:
        self.window.new_schematic()

    def open_file(self, file_path: str) -> bool:
        return self.window.open_file(Path(file_path))

    def save_file(self, file_path: str | None = None) -> bool:
        if file_path:
            return self.window._save_to_file(file_path)
        return self.window.save_file()

    def run_simulation(self) -> None:
        self.window.run_simulation()

    def set_theme(self, theme_name: str) -> None:
        self.window.set_ui_theme(theme_name)

    def toggle_grid(self) -> None:
        self.window.toggle_grid()

    def toggle_snap(self) -> None:
        self.window.toggle_snap_to_grid()

    def status(self, message: str, timeout_ms: int = 2000) -> None:
        self.window.statusBar().showMessage(message, timeout_ms)

    def command(self, command_name: str, *args: Any, **kwargs: Any) -> Any:
        callback = getattr(self.window, command_name, None)
        if not callable(callback):
            raise AttributeError(f"Unknown command '{command_name}'")
        return callback(*args, **kwargs)

    def plugin_command(self, command_name: str, *args: Any, **kwargs: Any) -> Any:
        return self.window.plugin_manager.run_command(command_name, *args, **kwargs)

    def run_workflow(self, workflow_path: str) -> None:
        self.window.run_workflow_file(Path(workflow_path))

    def sleep(self, seconds: float) -> None:
        time.sleep(seconds)

    def log(self, message: str, *args: Any) -> None:
        logger.info("[script] " + message, *args)


class ScriptAutomationRunner:
    """Executes Python scripts and JSON workflow files."""

    def __init__(self, window: "MainWindow"):
        self._window = window

    def run_script(self, script_path: Path) -> None:
        """Run one python automation script file."""
        script_path = script_path.expanduser().resolve()
        if not script_path.exists():
            raise FileNotFoundError(f"Script not found: {script_path}")

        source = script_path.read_text(encoding="utf-8")
        api = AutomationAPI(self._window)

        globals_dict = {
            "__name__": "__pyxschem_script__",
            "__file__": str(script_path),
            "__builtins__": builtins.__dict__,
            "app": api,
            "window": self._window,
            "context": self._window.context,
            "Path": Path,
            "json": json,
        }

        logger.info("Running automation script '%s'", script_path)
        exec(compile(source, str(script_path), "exec"), globals_dict, globals_dict)
        logger.info("Completed automation script '%s'", script_path)

    def run_workflow(self, workflow_path: Path) -> None:
        """Run a JSON-defined workflow."""
        workflow_path = workflow_path.expanduser().resolve()
        if not workflow_path.exists():
            raise FileNotFoundError(f"Workflow not found: {workflow_path}")

        data = json.loads(workflow_path.read_text(encoding="utf-8"))
        steps = data.get("steps", [])
        if not isinstance(steps, list):
            raise ValueError("Workflow 'steps' must be a list")

        api = AutomationAPI(self._window)
        workflow_name = data.get("name") or workflow_path.stem
        logger.info("Running workflow '%s' (%d steps)", workflow_name, len(steps))

        runtime = SimpleNamespace(workflow_path=workflow_path, workflow_name=workflow_name)

        for index, step in enumerate(steps, start=1):
            if not isinstance(step, dict):
                raise ValueError(f"Workflow step #{index} is not an object")

            step_type = str(step.get("type", "command")).lower()
            logger.info("Workflow step %d/%d: %s", index, len(steps), step_type)

            if step_type == "command":
                name = step.get("name")
                if not isinstance(name, str) or not name:
                    raise ValueError(f"Workflow step #{index} missing command name")
                args = step.get("args", [])
                kwargs = step.get("kwargs", {})
                if not isinstance(args, list):
                    raise ValueError(f"Workflow step #{index} args must be a list")
                if not isinstance(kwargs, dict):
                    raise ValueError(f"Workflow step #{index} kwargs must be an object")
                api.command(name, *args, **kwargs)
            elif step_type == "script":
                script = step.get("path")
                if not isinstance(script, str) or not script:
                    raise ValueError(f"Workflow step #{index} missing script path")
                script_path = (workflow_path.parent / script).resolve()
                self.run_script(script_path)
            elif step_type == "plugin_command":
                name = step.get("name")
                if not isinstance(name, str) or not name:
                    raise ValueError(f"Workflow step #{index} missing plugin command name")
                args = step.get("args", [])
                kwargs = step.get("kwargs", {})
                if not isinstance(args, list):
                    raise ValueError(f"Workflow step #{index} args must be a list")
                if not isinstance(kwargs, dict):
                    raise ValueError(f"Workflow step #{index} kwargs must be an object")
                api.plugin_command(name, *args, **kwargs)
            elif step_type == "message":
                text = str(step.get("text", ""))
                timeout_ms = int(step.get("timeout_ms", 2000))
                api.status(text, timeout_ms)
            elif step_type == "sleep":
                seconds = float(step.get("seconds", 0.0))
                api.sleep(seconds)
            else:
                raise ValueError(f"Unsupported workflow step type '{step_type}'")

        logger.info("Completed workflow '%s'", runtime.workflow_name)
