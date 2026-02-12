"""
Property editor dialog for PyXSchem.

Provides a multi-line text editor for editing component properties,
schematic properties, and other text-based attributes.

Similar to xschem's property edit dialog with:
- Multi-line text editing
- Syntax highlighting (optional)
- Property templates
- Auto-completion for common attributes
"""

from typing import Optional, Dict, List
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QFont, QTextCursor
from PySide6.QtWidgets import (
    QDialog,
    QVBoxLayout,
    QHBoxLayout,
    QTextEdit,
    QLineEdit,
    QPushButton,
    QLabel,
    QWidget,
    QSplitter,
    QListWidget,
    QListWidgetItem,
    QDialogButtonBox,
    QGroupBox,
    QFormLayout,
    QComboBox,
    QCheckBox,
)


class PropertyEditorDialog(QDialog):
    """
    Dialog for editing properties.

    Can be used for:
    - Component instance properties
    - Symbol definition properties
    - Schematic global properties
    - Text element content

    Features:
    - Multi-line text editing
    - Common property suggestions
    - Property name=value parsing
    """

    # Signal emitted when properties change
    properties_changed = Signal(str)

    # Common property names for auto-completion
    COMMON_PROPERTIES = [
        "name", "value", "model", "spice_ignore",
        "lab", "dir", "pinnumber", "pinseq",
        "template", "type", "format", "verilog_format",
        "vhdl_format", "tedax_format", "device",
        "description", "footprint", "hide",
    ]

    def __init__(
        self,
        parent: Optional[QWidget] = None,
        initial_text: str = "",
        title: str = "Edit Properties"
    ):
        super().__init__(parent)

        self.setWindowTitle(title)
        self.setMinimumSize(600, 400)
        self.resize(700, 500)

        self._initial_text = initial_text
        self._text = initial_text

        self._setup_ui()

    def _setup_ui(self) -> None:
        """Set up the dialog UI."""
        layout = QVBoxLayout(self)

        # Main editor area
        splitter = QSplitter(Qt.Horizontal)

        # Left side: Text editor
        editor_widget = QWidget()
        editor_layout = QVBoxLayout(editor_widget)
        editor_layout.setContentsMargins(0, 0, 0, 0)

        label = QLabel("Properties:")
        editor_layout.addWidget(label)

        self._text_edit = QTextEdit()
        self._text_edit.setFont(QFont("Monospace", 10))
        self._text_edit.setPlainText(self._initial_text)
        self._text_edit.setAcceptRichText(False)
        self._text_edit.setLineWrapMode(QTextEdit.NoWrap)
        editor_layout.addWidget(self._text_edit)

        splitter.addWidget(editor_widget)

        # Right side: Property helpers
        helper_widget = QWidget()
        helper_layout = QVBoxLayout(helper_widget)
        helper_layout.setContentsMargins(0, 0, 0, 0)

        # Common properties list
        common_group = QGroupBox("Common Properties")
        common_layout = QVBoxLayout(common_group)

        self._property_list = QListWidget()
        self._property_list.setMaximumWidth(200)
        for prop in self.COMMON_PROPERTIES:
            item = QListWidgetItem(prop)
            self._property_list.addItem(item)
        self._property_list.itemDoubleClicked.connect(self._insert_property)
        common_layout.addWidget(self._property_list)

        helper_layout.addWidget(common_group)

        # Quick add section
        quick_group = QGroupBox("Quick Add")
        quick_layout = QFormLayout(quick_group)

        self._name_edit = QLineEdit()
        self._name_edit.setPlaceholderText("Property name")
        quick_layout.addRow("Name:", self._name_edit)

        self._value_edit = QLineEdit()
        self._value_edit.setPlaceholderText("Value")
        quick_layout.addRow("Value:", self._value_edit)

        add_btn = QPushButton("Add Property")
        add_btn.clicked.connect(self._add_property)
        quick_layout.addRow(add_btn)

        helper_layout.addWidget(quick_group)

        splitter.addWidget(helper_widget)

        # Set splitter sizes (70% editor, 30% helpers)
        splitter.setSizes([500, 200])

        layout.addWidget(splitter)

        # Button box
        button_box = QDialogButtonBox(
            QDialogButtonBox.Ok | QDialogButtonBox.Cancel | QDialogButtonBox.Apply
        )
        button_box.accepted.connect(self.accept)
        button_box.rejected.connect(self.reject)
        button_box.button(QDialogButtonBox.Apply).clicked.connect(self._apply)

        layout.addWidget(button_box)

    def _insert_property(self, item: QListWidgetItem) -> None:
        """Insert a property name at cursor."""
        prop_name = item.text()
        cursor = self._text_edit.textCursor()

        # Check if we're at the start of a line
        cursor.movePosition(QTextCursor.StartOfLine, QTextCursor.KeepAnchor)
        selected = cursor.selectedText()

        if selected.strip():
            # Not at start, insert on new line
            cursor = self._text_edit.textCursor()
            cursor.movePosition(QTextCursor.EndOfLine)
            cursor.insertText(f"\n{prop_name}=")
        else:
            # At start, just insert
            cursor = self._text_edit.textCursor()
            cursor.insertText(f"{prop_name}=")

        self._text_edit.setTextCursor(cursor)
        self._text_edit.setFocus()

    def _add_property(self) -> None:
        """Add a property from the quick add fields."""
        name = self._name_edit.text().strip()
        value = self._value_edit.text().strip()

        if not name:
            return

        # Format the property
        if " " in value or "=" in value or "{" in value:
            # Value needs braces
            prop_text = f'{name}={{{value}}}'
        else:
            prop_text = f'{name}={value}'

        # Append to text
        current = self._text_edit.toPlainText()
        if current and not current.endswith("\n"):
            current += "\n"
        self._text_edit.setPlainText(current + prop_text)

        # Clear inputs
        self._name_edit.clear()
        self._value_edit.clear()
        self._name_edit.setFocus()

    def _apply(self) -> None:
        """Apply changes without closing."""
        self._text = self._text_edit.toPlainText()
        self.properties_changed.emit(self._text)

    @property
    def text(self) -> str:
        """Get the edited text."""
        return self._text_edit.toPlainText()

    def accept(self) -> None:
        """Accept the dialog."""
        self._text = self._text_edit.toPlainText()
        super().accept()

    @staticmethod
    def parse_properties(text: str) -> Dict[str, str]:
        """
        Parse properties text into a dictionary.

        Handles both simple name=value and name={value with spaces} formats.

        Args:
            text: Properties text

        Returns:
            Dictionary of property name -> value
        """
        properties = {}

        # Simple regex-free parsing
        i = 0
        while i < len(text):
            # Skip whitespace
            while i < len(text) and text[i] in ' \t\n':
                i += 1
            if i >= len(text):
                break

            # Find property name
            name_start = i
            while i < len(text) and text[i] not in '= \t\n':
                i += 1
            name = text[name_start:i].strip()

            if not name:
                break

            # Skip whitespace and equals
            while i < len(text) and text[i] in ' \t':
                i += 1
            if i < len(text) and text[i] == '=':
                i += 1
            while i < len(text) and text[i] in ' \t':
                i += 1

            # Get value
            if i >= len(text):
                properties[name] = ""
                break

            if text[i] == '{':
                # Brace-enclosed value
                i += 1
                value_start = i
                brace_depth = 1
                while i < len(text) and brace_depth > 0:
                    if text[i] == '{':
                        brace_depth += 1
                    elif text[i] == '}':
                        brace_depth -= 1
                    i += 1
                value = text[value_start:i-1] if brace_depth == 0 else text[value_start:i]
            else:
                # Simple value until whitespace
                value_start = i
                while i < len(text) and text[i] not in ' \t\n':
                    i += 1
                value = text[value_start:i]

            properties[name] = value

        return properties

    @staticmethod
    def format_properties(properties: Dict[str, str]) -> str:
        """
        Format a property dictionary as text.

        Args:
            properties: Dictionary of property name -> value

        Returns:
            Formatted property string
        """
        lines = []
        for name, value in properties.items():
            if ' ' in value or '=' in value or '{' in value or '}' in value:
                lines.append(f'{name}={{{value}}}')
            else:
                lines.append(f'{name}={value}')
        return '\n'.join(lines)


class InstancePropertyDialog(PropertyEditorDialog):
    """
    Specialized property editor for component instances.

    Adds instance-specific features:
    - Symbol template display
    - Pin connections
    - Instance name editing
    """

    def __init__(
        self,
        parent: Optional[QWidget] = None,
        initial_text: str = "",
        instance_name: str = "",
        symbol_template: str = ""
    ):
        self._instance_name = instance_name
        self._symbol_template = symbol_template

        super().__init__(parent, initial_text, f"Edit Instance: {instance_name}")

    def _setup_ui(self) -> None:
        """Set up the dialog UI with instance-specific widgets."""
        layout = QVBoxLayout(self)

        # Instance info at top
        info_layout = QHBoxLayout()

        info_layout.addWidget(QLabel("Instance:"))
        self._name_display = QLineEdit(self._instance_name)
        self._name_display.setMaximumWidth(150)
        info_layout.addWidget(self._name_display)

        info_layout.addStretch()
        layout.addLayout(info_layout)

        # Symbol template (read-only)
        if self._symbol_template:
            template_group = QGroupBox("Symbol Template")
            template_layout = QVBoxLayout(template_group)

            template_edit = QTextEdit()
            template_edit.setFont(QFont("Monospace", 9))
            template_edit.setPlainText(self._symbol_template)
            template_edit.setReadOnly(True)
            template_edit.setMaximumHeight(80)
            template_layout.addWidget(template_edit)

            layout.addWidget(template_group)

        # Main property editor
        props_group = QGroupBox("Instance Properties")
        props_layout = QVBoxLayout(props_group)

        self._text_edit = QTextEdit()
        self._text_edit.setFont(QFont("Monospace", 10))
        self._text_edit.setPlainText(self._initial_text)
        self._text_edit.setAcceptRichText(False)
        props_layout.addWidget(self._text_edit)

        layout.addWidget(props_group)

        # Button box
        button_box = QDialogButtonBox(
            QDialogButtonBox.Ok | QDialogButtonBox.Cancel
        )
        button_box.accepted.connect(self.accept)
        button_box.rejected.connect(self.reject)
        layout.addWidget(button_box)

    @property
    def instance_name(self) -> str:
        """Get the edited instance name."""
        return self._name_display.text()
