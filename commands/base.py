"""
Base command and undo stack for PyXSchem.

Implements the command pattern for reversible edit operations.
"""

from abc import ABC, abstractmethod
from typing import List, Optional
import logging

logger = logging.getLogger(__name__)


class Command(ABC):
    """Abstract base class for undoable commands."""

    @abstractmethod
    def execute(self) -> None:
        """Execute the command."""

    @abstractmethod
    def undo(self) -> None:
        """Reverse the command."""

    @property
    @abstractmethod
    def description(self) -> str:
        """Human-readable description of this command."""


class UndoStack:
    """
    Manages a stack of undoable commands.

    Supports push, undo, redo with a configurable maximum depth.
    """

    MAX_DEPTH = 200

    def __init__(self, max_depth: int = MAX_DEPTH):
        self._undo_stack: List[Command] = []
        self._redo_stack: List[Command] = []
        self._max_depth = max_depth

    def push(self, command: Command) -> None:
        """Execute a command and push it onto the undo stack."""
        command.execute()
        self._undo_stack.append(command)
        self._redo_stack.clear()

        # Enforce max depth
        if len(self._undo_stack) > self._max_depth:
            self._undo_stack.pop(0)

        logger.debug("Command pushed: %s (stack depth=%d)", command.description, len(self._undo_stack))

    def undo(self) -> Optional[str]:
        """
        Undo the last command.

        Returns:
            Description of the undone command, or None if nothing to undo.
        """
        if not self._undo_stack:
            return None

        command = self._undo_stack.pop()
        command.undo()
        self._redo_stack.append(command)
        logger.debug("Undo: %s", command.description)
        return command.description

    def redo(self) -> Optional[str]:
        """
        Redo the last undone command.

        Returns:
            Description of the redone command, or None if nothing to redo.
        """
        if not self._redo_stack:
            return None

        command = self._redo_stack.pop()
        command.execute()
        self._undo_stack.append(command)
        logger.debug("Redo: %s", command.description)
        return command.description

    def can_undo(self) -> bool:
        """Check if there are commands to undo."""
        return len(self._undo_stack) > 0

    def can_redo(self) -> bool:
        """Check if there are commands to redo."""
        return len(self._redo_stack) > 0

    def clear(self) -> None:
        """Clear both undo and redo stacks."""
        self._undo_stack.clear()
        self._redo_stack.clear()

    @property
    def undo_description(self) -> Optional[str]:
        """Description of the next command to undo."""
        if self._undo_stack:
            return self._undo_stack[-1].description
        return None

    @property
    def redo_description(self) -> Optional[str]:
        """Description of the next command to redo."""
        if self._redo_stack:
            return self._redo_stack[-1].description
        return None

    @property
    def depth(self) -> int:
        """Current undo stack depth."""
        return len(self._undo_stack)
