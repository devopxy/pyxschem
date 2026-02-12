"""Terminal and debug console dock widgets for PyXSchem."""

from __future__ import annotations

from datetime import datetime
import logging
import os
from pathlib import Path
from typing import Optional

from PySide6.QtCore import QObject, QProcess, Qt, Signal
from PySide6.QtGui import QTextCursor
from PySide6.QtWidgets import (
    QDockWidget,
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QPlainTextEdit,
    QLineEdit,
    QPushButton,
    QTabWidget,
)


logger = logging.getLogger(__name__)


class _LogEmitter(QObject):
    """Qt signal bridge for logging handler."""

    line_ready = Signal(str)


class DockLogHandler(logging.Handler):
    """Log handler that forwards records to the debug dock."""

    def __init__(self, emitter: _LogEmitter):
        super().__init__()
        self._emitter = emitter

    def emit(self, record: logging.LogRecord) -> None:
        """Emit one formatted log line."""
        try:
            line = self.format(record)
        except Exception:
            line = record.getMessage()
        self._emitter.line_ready.emit(line)


class TerminalConsoleDock(QDockWidget):
    """Dock widget containing terminal output and a debug console."""

    def __init__(self, parent=None):
        super().__init__("Terminal / Debug", parent)
        self.setObjectName("terminal_console_dock")
        self.setAllowedAreas(Qt.BottomDockWidgetArea | Qt.LeftDockWidgetArea | Qt.RightDockWidgetArea)
        self.setFeatures(
            QDockWidget.DockWidgetMovable
            | QDockWidget.DockWidgetFloatable
            | QDockWidget.DockWidgetClosable
        )

        self._tabs: Optional[QTabWidget] = None
        self._terminal_output: Optional[QPlainTextEdit] = None
        self._terminal_input: Optional[QLineEdit] = None
        self._debug_output: Optional[QPlainTextEdit] = None
        self._process: Optional[QProcess] = None

        self._log_emitter = _LogEmitter()
        self._log_handler: Optional[DockLogHandler] = None

        self._setup_ui()
        self._setup_process()

    def _setup_ui(self) -> None:
        """Build dock UI."""
        root = QWidget(self)
        layout = QVBoxLayout(root)
        layout.setContentsMargins(6, 6, 6, 6)
        layout.setSpacing(6)

        self._tabs = QTabWidget(root)

        terminal_tab = QWidget(self._tabs)
        terminal_layout = QVBoxLayout(terminal_tab)
        terminal_layout.setContentsMargins(0, 0, 0, 0)
        terminal_layout.setSpacing(5)

        self._terminal_output = QPlainTextEdit(terminal_tab)
        self._terminal_output.setReadOnly(True)
        self._terminal_output.setObjectName("terminal_output")
        self._terminal_output.setLineWrapMode(QPlainTextEdit.NoWrap)
        terminal_layout.addWidget(self._terminal_output, 1)

        input_row = QHBoxLayout()
        input_row.setContentsMargins(0, 0, 0, 0)
        input_row.setSpacing(5)

        self._terminal_input = QLineEdit(terminal_tab)
        self._terminal_input.setPlaceholderText("Run shell command (example: ls -la)")
        self._terminal_input.returnPressed.connect(self._run_from_input)
        input_row.addWidget(self._terminal_input, 1)

        run_button = QPushButton("Run", terminal_tab)
        run_button.clicked.connect(self._run_from_input)
        input_row.addWidget(run_button)

        clear_terminal_button = QPushButton("Clear", terminal_tab)
        clear_terminal_button.clicked.connect(self.clear_terminal)
        input_row.addWidget(clear_terminal_button)

        terminal_layout.addLayout(input_row)

        debug_tab = QWidget(self._tabs)
        debug_layout = QVBoxLayout(debug_tab)
        debug_layout.setContentsMargins(0, 0, 0, 0)
        debug_layout.setSpacing(5)

        self._debug_output = QPlainTextEdit(debug_tab)
        self._debug_output.setReadOnly(True)
        self._debug_output.setObjectName("debug_console")
        self._debug_output.setLineWrapMode(QPlainTextEdit.NoWrap)
        debug_layout.addWidget(self._debug_output, 1)

        debug_buttons = QHBoxLayout()
        debug_buttons.setContentsMargins(0, 0, 0, 0)
        debug_buttons.setSpacing(5)

        clear_debug_button = QPushButton("Clear", debug_tab)
        clear_debug_button.clicked.connect(self.clear_debug)
        debug_buttons.addWidget(clear_debug_button)
        debug_buttons.addStretch(1)

        debug_layout.addLayout(debug_buttons)

        self._tabs.addTab(terminal_tab, "Terminal")
        self._tabs.addTab(debug_tab, "Debug Console")
        layout.addWidget(self._tabs, 1)

        self.setWidget(root)

    def _setup_process(self) -> None:
        """Configure command process used by terminal panel."""
        self._process = QProcess(self)
        self._process.readyReadStandardOutput.connect(self._read_stdout)
        self._process.readyReadStandardError.connect(self._read_stderr)
        self._process.finished.connect(self._on_process_finished)

    def attach_log_handler(self) -> None:
        """Attach log listener and stream records into debug console."""
        if self._log_handler is not None:
            return

        self._log_handler = DockLogHandler(self._log_emitter)
        self._log_handler.setLevel(logging.DEBUG)
        self._log_handler.setFormatter(
            logging.Formatter("%(asctime)s | %(levelname)-8s | %(name)s | %(message)s", "%H:%M:%S")
        )
        self._log_emitter.line_ready.connect(self.append_debug)
        logging.getLogger().addHandler(self._log_handler)

    def detach_log_handler(self) -> None:
        """Detach the debug log listener from root logger."""
        if self._log_handler is None:
            return
        logging.getLogger().removeHandler(self._log_handler)
        self._log_handler = None

    def run_command(self, command: str) -> None:
        """Run one shell command and stream output into terminal tab."""
        command = command.strip()
        if not command or self._process is None:
            return

        if self._process.state() != QProcess.NotRunning:
            self.append_terminal("[terminal] Process already running; wait for completion")
            return

        self.append_terminal(f"$ {command}")

        shell = os.environ.get("SHELL", "/bin/bash")
        shell_name = Path(shell).name
        if shell_name in {"bash", "zsh", "sh", "dash", "fish"}:
            self._process.start(shell, ["-lc", command])
        else:
            # Fallback if shell does not support -lc.
            self._process.start(command)

    def _run_from_input(self) -> None:
        """Run command from text field."""
        if self._terminal_input is None:
            return
        command = self._terminal_input.text()
        if not command.strip():
            return
        self._terminal_input.clear()
        self.run_command(command)

    def _read_stdout(self) -> None:
        """Append stdout from current process."""
        if self._process is None:
            return
        data = bytes(self._process.readAllStandardOutput()).decode("utf-8", errors="replace")
        if data:
            self.append_terminal(data.rstrip("\n"))

    def _read_stderr(self) -> None:
        """Append stderr from current process."""
        if self._process is None:
            return
        data = bytes(self._process.readAllStandardError()).decode("utf-8", errors="replace")
        if data:
            self.append_terminal(data.rstrip("\n"))

    def _on_process_finished(self, code: int, status: QProcess.ExitStatus) -> None:
        """Handle command completion."""
        status_text = "ok" if status == QProcess.NormalExit and code == 0 else "error"
        self.append_terminal(f"[terminal] Process finished (exit={code}, status={status_text})")

    def append_terminal(self, text: str) -> None:
        """Append one line to terminal output."""
        if self._terminal_output is None or not text:
            return
        timestamp = datetime.now().strftime("%H:%M:%S")
        self._terminal_output.appendPlainText(f"{timestamp}  {text}")
        self._terminal_output.moveCursor(QTextCursor.End)

    def append_debug(self, text: str) -> None:
        """Append one line to debug console output."""
        if self._debug_output is None or not text:
            return
        self._debug_output.appendPlainText(text)
        self._debug_output.moveCursor(QTextCursor.End)

    def clear_terminal(self) -> None:
        """Clear terminal output."""
        if self._terminal_output is not None:
            self._terminal_output.clear()

    def clear_debug(self) -> None:
        """Clear debug console output."""
        if self._debug_output is not None:
            self._debug_output.clear()

    def show_terminal_tab(self) -> None:
        """Switch to terminal tab."""
        if self._tabs is not None:
            self._tabs.setCurrentIndex(0)

    def show_debug_tab(self) -> None:
        """Switch to debug console tab."""
        if self._tabs is not None:
            self._tabs.setCurrentIndex(1)

    def closeEvent(self, event) -> None:
        """Detach handlers on close."""
        self.detach_log_handler()
        super().closeEvent(event)
