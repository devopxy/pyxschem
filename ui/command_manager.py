"""
Virtuoso-style command state machine for PyXSchem.

This module centralizes keyboard-driven command dispatch and modal state:
- Global states: IDLE and ACTIVE_COMMAND
- Universal Esc behavior
- Contextual F3 behavior
- Noun-verb and verb-noun command invocation paths
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum, auto
import logging
from typing import Callable, Optional, TYPE_CHECKING

from PySide6.QtCore import QObject, QEvent, Qt
from PySide6.QtGui import QKeyEvent
from PySide6.QtWidgets import (
    QApplication,
    QAbstractSpinBox,
    QComboBox,
    QLineEdit,
    QPlainTextEdit,
    QTextEdit,
    QWidget,
)

if TYPE_CHECKING:
    from pyxschem.ui.main_window import MainWindow


logger = logging.getLogger(__name__)


class CommandState(Enum):
    """Primary editor command state."""

    IDLE = auto()
    ACTIVE_COMMAND = auto()


@dataclass
class CommandSpec:
    """Metadata for a command bound in the command manager."""

    command_id: str
    handler: Callable[[], object]
    enters_active: bool = False
    supports_noun_verb: bool = False
    supports_verb_noun: bool = True
    requires_selection: bool = False
    f3_handler: Optional[Callable[[], None]] = None


class CommandManager(QObject):
    """
    Single-threaded command state machine for schematic interactions.

    The manager installs an application event filter to intercept key presses
    while the main window is active and routes them through registered command
    specs and keybindings.
    """

    def __init__(self, window: "MainWindow"):
        super().__init__(window)
        self._window = window
        self._state = CommandState.IDLE
        self._active_command: Optional[str] = None
        self._commands: dict[str, CommandSpec] = {}
        self._bindings: dict[tuple[int, int], str] = {}
        self._installed = False
        self._modifier_mask = (
            Qt.ControlModifier | Qt.ShiftModifier | Qt.AltModifier | Qt.MetaModifier
        )

        self._register_default_commands()
        self._register_default_bindings()
        self.install()

    @property
    def state(self) -> CommandState:
        """Return current primary command state."""
        return self._state

    @property
    def active_command(self) -> Optional[str]:
        """Return currently active command id, if any."""
        return self._active_command

    def install(self) -> None:
        """Install the command manager as a global key event filter."""
        if self._installed:
            return
        app = QApplication.instance()
        if app is None:
            logger.warning("CommandManager install skipped: QApplication unavailable")
            return
        app.installEventFilter(self)
        self._installed = True
        logger.info("CommandManager installed")

    def shutdown(self) -> None:
        """Remove global key event filter and reset command state."""
        if not self._installed:
            return
        app = QApplication.instance()
        if app is not None:
            app.removeEventFilter(self)
        self._installed = False
        self.set_idle()
        logger.info("CommandManager shut down")

    def register_command(
        self,
        command_id: str,
        handler: Callable[[], object],
        *,
        enters_active: bool = False,
        supports_noun_verb: bool = False,
        supports_verb_noun: bool = True,
        requires_selection: bool = False,
        f3_handler: Optional[Callable[[], None]] = None,
    ) -> None:
        """Register or replace a command specification."""
        self._commands[command_id] = CommandSpec(
            command_id=command_id,
            handler=handler,
            enters_active=enters_active,
            supports_noun_verb=supports_noun_verb,
            supports_verb_noun=supports_verb_noun,
            requires_selection=requires_selection,
            f3_handler=f3_handler,
        )

    def bind_key(
        self,
        key: Qt.Key | int,
        command_id: str,
        modifiers: Qt.KeyboardModifiers = Qt.NoModifier,
    ) -> None:
        """Bind a normalized key chord to a command id."""
        self._bindings[self._chord(key, modifiers)] = command_id

    def set_active_command(self, command_id: str) -> None:
        """Transition state machine to ACTIVE_COMMAND."""
        self._state = CommandState.ACTIVE_COMMAND
        self._active_command = command_id
        logger.debug("Command state -> ACTIVE_COMMAND (%s)", command_id)

    def set_idle(self) -> None:
        """Transition state machine to IDLE."""
        self._state = CommandState.IDLE
        self._active_command = None
        logger.debug("Command state -> IDLE")

    def dispatch_command(self, command_id: str) -> bool:
        """Dispatch a command by id. Returns True if handled."""
        if command_id == "escape":
            return self._handle_escape()
        if command_id == "context_options":
            return self._handle_context_options()

        spec = self._commands.get(command_id)
        if spec is None:
            return False

        has_selection = self._window.has_selection_buffer()
        path = "verb-noun"
        if spec.supports_noun_verb and has_selection:
            path = "noun-verb"
        elif spec.requires_selection and not has_selection and not spec.supports_verb_noun:
            self._window.statusBar().showMessage("Selection required for command", 1800)
            return True

        try:
            result = spec.handler()
        except Exception:
            logger.exception("Command '%s' failed", command_id)
            self.set_idle()
            return True

        should_activate = spec.enters_active and (result is not False)
        if (
            not should_activate
            and spec.enters_active
            and spec.supports_verb_noun
            and not has_selection
        ):
            # Structure support for verb-noun mode even when the concrete
            # command backend is not fully interactive yet.
            should_activate = True

        if should_activate:
            self.set_active_command(command_id)
        else:
            self.set_idle()

        logger.info("Command dispatched: %s (%s)", command_id, path)
        return True

    def handle_key_event(self, event: QKeyEvent) -> bool:
        """Handle a key event and dispatch mapped commands."""
        if event.type() != QEvent.KeyPress:
            return False
        if event.isAutoRepeat():
            return False

        command_id = self._bindings.get(self._event_chord(event))
        if command_id is None:
            return False

        handled = self.dispatch_command(command_id)
        if handled:
            event.accept()
        return handled

    def eventFilter(self, watched: QObject, event: QEvent) -> bool:
        """Intercept key events from widgets belonging to the main window."""
        if event.type() != QEvent.KeyPress:
            return False
        if not isinstance(event, QKeyEvent):
            return False
        if not self._should_handle_keypress(watched, event):
            return False
        return self.handle_key_event(event)

    def _register_default_commands(self) -> None:
        """Register the default Virtuoso-compatible command set."""
        self.register_command("undo", self._window.undo)
        self.register_command("redo", self._window.redo)
        self.register_command("fit_all", self._window.zoom_fit)
        self.register_command("zoom_out", self._window.zoom_out)
        self.register_command("zoom_in", self._window.zoom_in)
        self.register_command("create_ruler", self._window.create_ruler)
        self.register_command("clear_rulers", self._window.clear_all_rulers)
        self.register_command(
            "instantiate_component",
            self._window.instantiate_component,
            enters_active=True,
        )
        self.register_command(
            "start_wire",
            self._window.start_wire,
            enters_active=True,
            f3_handler=self._window.open_wire_options,
        )
        self.register_command(
            "start_bus",
            self._window.start_bus,
            enters_active=True,
            f3_handler=self._window.open_wire_options,
        )
        self.register_command(
            "create_label",
            self._window.create_label,
            enters_active=True,
        )
        self.register_command(
            "create_pin",
            self._window.create_pin,
            enters_active=True,
        )
        self.register_command("open_properties", self._window.open_properties)
        self.register_command(
            "move",
            self._window.start_move_command,
            enters_active=True,
            supports_noun_verb=True,
            f3_handler=self._window.open_transform_options,
        )
        self.register_command(
            "copy",
            self._window.start_copy_command,
            enters_active=True,
            supports_noun_verb=True,
            f3_handler=self._window.open_transform_options,
        )
        self.register_command("delete_selected", self._window.delete_selected)
        self.register_command(
            "descend_read",
            lambda: self._window.descend_hierarchy(mode="READ"),
        )
        self.register_command(
            "descend_edit",
            lambda: self._window.descend_hierarchy(mode="EDIT"),
        )
        self.register_command("ascend", self._window.ascend_hierarchy)
        self.register_command("check_and_save", self._window.check_and_save)

    def _register_default_bindings(self) -> None:
        """Bind default keys to command ids."""
        self.bind_key(Qt.Key_U, "undo")
        self.bind_key(Qt.Key_U, "redo", Qt.ShiftModifier)
        self.bind_key(Qt.Key_F, "fit_all")
        self.bind_key(Qt.Key_Z, "zoom_out", Qt.ShiftModifier)
        self.bind_key(Qt.Key_Z, "zoom_in", Qt.ControlModifier)
        self.bind_key(Qt.Key_K, "create_ruler")
        self.bind_key(Qt.Key_K, "clear_rulers", Qt.ShiftModifier)

        self.bind_key(Qt.Key_I, "instantiate_component")
        self.bind_key(Qt.Key_W, "start_wire")
        self.bind_key(Qt.Key_W, "start_bus", Qt.ShiftModifier)
        self.bind_key(Qt.Key_L, "create_label")
        self.bind_key(Qt.Key_P, "create_pin")
        self.bind_key(Qt.Key_Q, "open_properties")
        self.bind_key(Qt.Key_M, "move")
        self.bind_key(Qt.Key_C, "copy")
        self.bind_key(Qt.Key_Delete, "delete_selected")

        self.bind_key(Qt.Key_E, "descend_read")
        self.bind_key(Qt.Key_E, "descend_edit", Qt.ShiftModifier)
        self.bind_key(Qt.Key_E, "ascend", Qt.ControlModifier)
        self.bind_key(Qt.Key_X, "check_and_save", Qt.ShiftModifier)

        self.bind_key(Qt.Key_Escape, "escape")
        self.bind_key(Qt.Key_F3, "context_options")

    def _handle_escape(self) -> bool:
        """Implement the universal Esc rule."""
        dc = self._window.drawing_controller
        has_active_draw_mode = bool(dc and dc.is_drawing)
        if self._state == CommandState.ACTIVE_COMMAND or has_active_draw_mode:
            self._window.abort_active_command(self._active_command)
            self.set_idle()
        else:
            self._window.clear_selection_buffer()
            self.set_idle()
        logger.info("Esc handled (state=%s)", self._state.name)
        return True

    def _handle_context_options(self) -> bool:
        """Implement contextual F3 options for the active command."""
        if self._state != CommandState.ACTIVE_COMMAND or not self._active_command:
            self._window.statusBar().showMessage("No active command options", 1800)
            return True

        spec = self._commands.get(self._active_command)
        if spec and spec.f3_handler:
            spec.f3_handler()
        else:
            self._window.open_command_options(self._active_command)
        logger.info("F3 handled for command '%s'", self._active_command)
        return True

    def _should_handle_keypress(self, watched: QObject, event: QKeyEvent) -> bool:
        """Return True when keypress should be handled by command manager."""
        if not self._window.isVisible():
            return False
        if not self._belongs_to_window(watched):
            return False

        focus = QApplication.focusWidget()
        if focus is not None and focus.window() is not self._window:
            return False
        if (
            focus is not None
            and self._is_text_input_widget(focus)
            and event.key() not in (Qt.Key_Escape, Qt.Key_F3)
        ):
            return False
        return True

    def _belongs_to_window(self, watched: QObject) -> bool:
        """Check whether a watched QObject belongs to the managed window."""
        if watched is self._window:
            return True
        if isinstance(watched, QWidget):
            return self._window.isAncestorOf(watched)
        parent = watched.parent()
        while parent is not None:
            if parent is self._window:
                return True
            parent = parent.parent()
        return False

    @staticmethod
    def _is_text_input_widget(widget: QWidget) -> bool:
        """Return True when widget is text-entry focused."""
        if isinstance(widget, (QLineEdit, QTextEdit, QPlainTextEdit, QAbstractSpinBox)):
            return True
        if isinstance(widget, QComboBox):
            return widget.isEditable()
        return False

    def _event_chord(self, event: QKeyEvent) -> tuple[int, int]:
        """Build normalized chord tuple from key event."""
        key_value = int(event.key())
        mods = event.modifiers() & self._modifier_mask
        mods_value = int(getattr(mods, "value", mods))
        return (mods_value, key_value)

    def _chord(
        self,
        key: Qt.Key | int,
        modifiers: Qt.KeyboardModifiers = Qt.NoModifier,
    ) -> tuple[int, int]:
        """Build normalized chord tuple from key + modifiers."""
        key_value = int(getattr(key, "value", key))
        mods = modifiers & self._modifier_mask
        mods_value = int(getattr(mods, "value", mods))
        return (mods_value, key_value)
