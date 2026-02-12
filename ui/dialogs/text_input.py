"""
Text input dialog for PyXSchem.

Simple dialog for entering text values like:
- Snap value
- Grid spacing
- Search text
- Custom values
"""

from typing import Optional, Any
from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialog,
    QVBoxLayout,
    QHBoxLayout,
    QLineEdit,
    QPushButton,
    QLabel,
    QWidget,
    QDialogButtonBox,
)


class TextInputDialog(QDialog):
    """
    Simple text input dialog.

    Similar to xschem's input_line function.

    Args:
        parent: Parent widget
        prompt: Prompt text to display
        initial_value: Initial value in the input field
        title: Dialog title
    """

    def __init__(
        self,
        parent: Optional[QWidget] = None,
        prompt: str = "Enter value:",
        initial_value: str = "",
        title: str = "Input"
    ):
        super().__init__(parent)

        self.setWindowTitle(title)
        self.setMinimumWidth(300)

        self._value: Optional[str] = None

        self._setup_ui(prompt, initial_value)

    def _setup_ui(self, prompt: str, initial_value: str) -> None:
        """Set up the dialog UI."""
        layout = QVBoxLayout(self)

        # Prompt label
        label = QLabel(prompt)
        layout.addWidget(label)

        # Input field
        self._input = QLineEdit()
        self._input.setText(initial_value)
        self._input.selectAll()
        self._input.returnPressed.connect(self.accept)
        layout.addWidget(self._input)

        # Button box
        button_box = QDialogButtonBox(
            QDialogButtonBox.Ok | QDialogButtonBox.Cancel
        )
        button_box.accepted.connect(self.accept)
        button_box.rejected.connect(self.reject)
        layout.addWidget(button_box)

        # Focus input
        self._input.setFocus()

    @property
    def value(self) -> Optional[str]:
        """Get the entered value."""
        return self._value

    def accept(self) -> None:
        """Accept the dialog."""
        self._value = self._input.text()
        super().accept()

    @staticmethod
    def get_text(
        parent: Optional[QWidget],
        title: str,
        prompt: str,
        initial_value: str = ""
    ) -> tuple[str, bool]:
        """
        Static convenience method to get text from user.

        Args:
            parent: Parent widget
            title: Dialog title
            prompt: Prompt text
            initial_value: Initial value

        Returns:
            Tuple of (text, accepted)
        """
        dialog = TextInputDialog(parent, prompt, initial_value, title)
        result = dialog.exec()
        return (dialog.value or "", result == QDialog.Accepted)

    @staticmethod
    def get_float(
        parent: Optional[QWidget],
        title: str,
        prompt: str,
        initial_value: float = 0.0
    ) -> tuple[float, bool]:
        """
        Static convenience method to get a float from user.

        Args:
            parent: Parent widget
            title: Dialog title
            prompt: Prompt text
            initial_value: Initial value

        Returns:
            Tuple of (value, accepted)
        """
        text, ok = TextInputDialog.get_text(parent, title, prompt, str(initial_value))
        if ok:
            try:
                return (float(text), True)
            except ValueError:
                return (initial_value, False)
        return (initial_value, False)

    @staticmethod
    def get_int(
        parent: Optional[QWidget],
        title: str,
        prompt: str,
        initial_value: int = 0
    ) -> tuple[int, bool]:
        """
        Static convenience method to get an integer from user.

        Args:
            parent: Parent widget
            title: Dialog title
            prompt: Prompt text
            initial_value: Initial value

        Returns:
            Tuple of (value, accepted)
        """
        text, ok = TextInputDialog.get_text(parent, title, prompt, str(initial_value))
        if ok:
            try:
                return (int(text), True)
            except ValueError:
                return (initial_value, False)
        return (initial_value, False)


class ConfirmDialog(QDialog):
    """
    Confirmation dialog.

    Similar to xschem's alert_ function.
    """

    def __init__(
        self,
        parent: Optional[QWidget] = None,
        message: str = "Are you sure?",
        title: str = "Confirm"
    ):
        super().__init__(parent)

        self.setWindowTitle(title)
        self.setMinimumWidth(300)

        self._setup_ui(message)

    def _setup_ui(self, message: str) -> None:
        """Set up the dialog UI."""
        layout = QVBoxLayout(self)

        # Message label
        label = QLabel(message)
        label.setWordWrap(True)
        layout.addWidget(label)

        # Button box
        button_box = QDialogButtonBox(
            QDialogButtonBox.Yes | QDialogButtonBox.No
        )
        button_box.accepted.connect(self.accept)
        button_box.rejected.connect(self.reject)
        layout.addWidget(button_box)

    @staticmethod
    def confirm(
        parent: Optional[QWidget],
        message: str,
        title: str = "Confirm"
    ) -> bool:
        """
        Static convenience method to show confirmation dialog.

        Args:
            parent: Parent widget
            message: Message to display
            title: Dialog title

        Returns:
            True if user clicked Yes
        """
        dialog = ConfirmDialog(parent, message, title)
        return dialog.exec() == QDialog.Accepted
