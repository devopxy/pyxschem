"""
Search dialog for PyXSchem.

Allows searching for instances, nets, properties, and text content
within the current schematic.
"""

from typing import Optional, List, Tuple, TYPE_CHECKING
import logging

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QDialog,
    QVBoxLayout,
    QHBoxLayout,
    QLineEdit,
    QPushButton,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QComboBox,
    QDialogButtonBox,
    QWidget,
)

if TYPE_CHECKING:
    from pyxschem.core.context import SchematicContext

logger = logging.getLogger(__name__)


class SearchDialog(QDialog):
    """
    Search dialog for finding elements in a schematic.

    Supports searching by:
    - Instance name (e.g., "R1", "M1")
    - Net name
    - Property value
    - Text content
    """

    # Signal emitted when user wants to go to a result: (type, index)
    goto_result = Signal(str, int)

    SEARCH_TYPES = [
        "All",
        "Instance name",
        "Net name",
        "Property value",
        "Text content",
    ]

    def __init__(self, parent: Optional[QWidget] = None, context: "SchematicContext" = None):
        super().__init__(parent)
        self._context = context
        self._results: List[Tuple[str, int, str]] = []

        self.setWindowTitle("Search")
        self.setMinimumSize(500, 400)
        self.resize(550, 450)

        self._setup_ui()

    def _setup_ui(self) -> None:
        layout = QVBoxLayout(self)

        # Search input row
        search_row = QHBoxLayout()

        self._type_combo = QComboBox()
        self._type_combo.addItems(self.SEARCH_TYPES)
        search_row.addWidget(self._type_combo)

        self._search_input = QLineEdit()
        self._search_input.setPlaceholderText("Enter search term...")
        self._search_input.returnPressed.connect(self._do_search)
        search_row.addWidget(self._search_input)

        self._search_btn = QPushButton("Search")
        self._search_btn.clicked.connect(self._do_search)
        search_row.addWidget(self._search_btn)

        layout.addLayout(search_row)

        # Results
        self._results_label = QLabel("Results:")
        layout.addWidget(self._results_label)

        self._results_list = QListWidget()
        self._results_list.itemDoubleClicked.connect(self._on_item_double_clicked)
        layout.addWidget(self._results_list)

        # Buttons
        buttons = QDialogButtonBox(QDialogButtonBox.Close)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def _do_search(self) -> None:
        """Execute the search."""
        if not self._context:
            return

        term = self._search_input.text().strip()
        if not term:
            return

        search_type = self._type_combo.currentText()
        self._results.clear()
        self._results_list.clear()

        term_lower = term.lower()

        # Search instances
        if search_type in ("All", "Instance name", "Property value"):
            for i, inst in enumerate(self._context.instances):
                if search_type in ("All", "Instance name"):
                    if inst.instname and term_lower in inst.instname.lower():
                        self._results.append(("instance", i, f"Instance: {inst.instname} ({inst.name})"))
                        continue
                if search_type in ("All", "Property value"):
                    if inst.prop_ptr and term_lower in inst.prop_ptr.lower():
                        desc = inst.instname or inst.name
                        self._results.append(("instance", i, f"Instance prop: {desc}"))

        # Search wires (net names)
        if search_type in ("All", "Net name"):
            for i, wire in enumerate(self._context.wires):
                if wire.node and term_lower in wire.node.lower():
                    self._results.append(("wire", i, f"Net: {wire.node}"))
                elif wire.prop_ptr and term_lower in wire.prop_ptr.lower():
                    self._results.append(("wire", i, f"Wire prop match"))

        # Search texts
        if search_type in ("All", "Text content"):
            for i, text in enumerate(self._context.texts):
                if text.txt_ptr and term_lower in text.txt_ptr.lower():
                    self._results.append(("text", i, f"Text: {text.txt_ptr[:50]}"))

        # Populate list
        for r_type, r_idx, r_desc in self._results:
            self._results_list.addItem(r_desc)

        self._results_label.setText(f"Results: {len(self._results)} found")

    def _on_item_double_clicked(self, item: QListWidgetItem) -> None:
        """Handle double-click on a result."""
        row = self._results_list.row(item)
        if 0 <= row < len(self._results):
            r_type, r_idx, _ = self._results[row]
            self.goto_result.emit(r_type, r_idx)
