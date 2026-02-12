"""
Symbol chooser dialog for PyXSchem.

Provides a file browser interface for selecting symbols:
- Directory tree view of symbol libraries
- Symbol preview pane
- Search functionality
- Recent symbols list
- Favorites
"""

from pathlib import Path
from typing import Optional, List
import os

from PySide6.QtCore import Qt, Signal, QDir, QModelIndex
from PySide6.QtGui import QStandardItemModel, QStandardItem
from PySide6.QtWidgets import (
    QDialog,
    QVBoxLayout,
    QHBoxLayout,
    QSplitter,
    QTreeView,
    QListWidget,
    QListWidgetItem,
    QLineEdit,
    QPushButton,
    QLabel,
    QWidget,
    QFileSystemModel,
    QDialogButtonBox,
    QGroupBox,
    QAbstractItemView,
    QHeaderView,
    QComboBox,
)


class SymbolChooserDialog(QDialog):
    """
    Dialog for browsing and selecting symbols from libraries.

    Features:
    - File system browser filtered to .sym files
    - Symbol preview (rendered view)
    - Search by name
    - Recent symbols list
    - Library path configuration
    """

    # Signal emitted when a symbol is selected
    symbol_selected = Signal(str)  # Symbol file path

    # Default library paths to search
    DEFAULT_LIBRARY_PATHS = [
        "/usr/share/xschem",
        "/usr/local/share/xschem",
        "~/.xschem",
    ]

    def __init__(
        self,
        parent: Optional[QWidget] = None,
        library_paths: Optional[List[str]] = None,
    ):
        super().__init__(parent)

        self.setWindowTitle("Choose Symbol")
        self.setMinimumSize(800, 600)
        self.resize(900, 650)

        self._library_paths = library_paths or self._get_default_paths()
        self._selected_symbol: Optional[str] = None
        self._recent_symbols: List[str] = []

        self._setup_ui()
        self._populate_tree()

    def _get_default_paths(self) -> List[str]:
        """Get default library paths that exist."""
        paths = []
        for path in self.DEFAULT_LIBRARY_PATHS:
            expanded = os.path.expanduser(path)
            if os.path.isdir(expanded):
                paths.append(expanded)

        # Also check XSCHEM_LIBRARY_PATH environment variable
        env_path = os.environ.get("XSCHEM_LIBRARY_PATH")
        if env_path:
            for path in env_path.split(":"):
                if os.path.isdir(path) and path not in paths:
                    paths.append(path)

        return paths

    def _setup_ui(self) -> None:
        """Set up the dialog UI."""
        layout = QVBoxLayout(self)

        # Search bar at top
        search_layout = QHBoxLayout()

        search_layout.addWidget(QLabel("Search:"))
        self._search_edit = QLineEdit()
        self._search_edit.setPlaceholderText("Type to filter symbols...")
        self._search_edit.textChanged.connect(self._on_search_changed)
        search_layout.addWidget(self._search_edit)

        layout.addLayout(search_layout)

        # Main content area
        splitter = QSplitter(Qt.Horizontal)

        # Left: Library tree
        left_widget = QWidget()
        left_layout = QVBoxLayout(left_widget)
        left_layout.setContentsMargins(0, 0, 0, 0)

        # Library path selector
        path_layout = QHBoxLayout()
        path_layout.addWidget(QLabel("Library:"))
        self._path_combo = QComboBox()
        self._path_combo.addItems(self._library_paths)
        self._path_combo.currentTextChanged.connect(self._on_library_changed)
        path_layout.addWidget(self._path_combo, 1)
        left_layout.addLayout(path_layout)

        # File tree
        self._file_model = QFileSystemModel()
        self._file_model.setNameFilters(["*.sym"])
        self._file_model.setNameFilterDisables(False)

        self._tree_view = QTreeView()
        self._tree_view.setModel(self._file_model)
        self._tree_view.setAnimated(True)
        self._tree_view.setIndentation(20)
        self._tree_view.setSortingEnabled(True)

        # Hide all columns except name
        self._tree_view.header().setSectionResizeMode(0, QHeaderView.Stretch)
        for i in range(1, 4):
            self._tree_view.hideColumn(i)

        self._tree_view.clicked.connect(self._on_tree_clicked)
        self._tree_view.doubleClicked.connect(self._on_tree_double_clicked)
        left_layout.addWidget(self._tree_view)

        splitter.addWidget(left_widget)

        # Middle: Symbol list (flat view for search results)
        middle_widget = QWidget()
        middle_layout = QVBoxLayout(middle_widget)
        middle_layout.setContentsMargins(0, 0, 0, 0)

        middle_layout.addWidget(QLabel("Symbols:"))
        self._symbol_list = QListWidget()
        self._symbol_list.setSelectionMode(QAbstractItemView.SingleSelection)
        self._symbol_list.itemClicked.connect(self._on_symbol_clicked)
        self._symbol_list.itemDoubleClicked.connect(self._on_symbol_double_clicked)
        middle_layout.addWidget(self._symbol_list)

        splitter.addWidget(middle_widget)

        # Right: Preview pane
        right_widget = QWidget()
        right_layout = QVBoxLayout(right_widget)
        right_layout.setContentsMargins(0, 0, 0, 0)

        right_layout.addWidget(QLabel("Preview:"))

        # Preview placeholder (would be a SchematicCanvas in full implementation)
        self._preview_widget = QWidget()
        self._preview_widget.setMinimumWidth(250)
        self._preview_widget.setStyleSheet(
            "background-color: #1a1a1a; border: 1px solid #444;"
        )
        right_layout.addWidget(self._preview_widget, 1)

        # Symbol info
        info_group = QGroupBox("Symbol Info")
        info_layout = QVBoxLayout(info_group)

        self._info_label = QLabel("Select a symbol to view info")
        self._info_label.setWordWrap(True)
        info_layout.addWidget(self._info_label)

        right_layout.addWidget(info_group)

        splitter.addWidget(right_widget)

        # Set splitter proportions
        splitter.setSizes([250, 250, 300])

        layout.addWidget(splitter)

        # Recent symbols section
        recent_group = QGroupBox("Recent Symbols")
        recent_layout = QHBoxLayout(recent_group)

        self._recent_list = QListWidget()
        self._recent_list.setFlow(QListWidget.LeftToRight)
        self._recent_list.setMaximumHeight(60)
        self._recent_list.setWrapping(False)
        self._recent_list.setSpacing(5)
        self._recent_list.itemDoubleClicked.connect(self._on_recent_double_clicked)
        recent_layout.addWidget(self._recent_list)

        layout.addWidget(recent_group)

        # Selected file display
        selection_layout = QHBoxLayout()
        selection_layout.addWidget(QLabel("Selected:"))
        self._selection_edit = QLineEdit()
        self._selection_edit.setReadOnly(True)
        selection_layout.addWidget(self._selection_edit)
        layout.addLayout(selection_layout)

        # Button box
        button_box = QDialogButtonBox(
            QDialogButtonBox.Ok | QDialogButtonBox.Cancel
        )
        button_box.accepted.connect(self.accept)
        button_box.rejected.connect(self.reject)
        self._ok_button = button_box.button(QDialogButtonBox.Ok)
        self._ok_button.setEnabled(False)
        layout.addWidget(button_box)

    def _populate_tree(self) -> None:
        """Populate the file tree with the current library path."""
        if self._library_paths:
            root_path = self._library_paths[0]
            self._file_model.setRootPath(root_path)
            self._tree_view.setRootIndex(self._file_model.index(root_path))

    def _on_library_changed(self, path: str) -> None:
        """Handle library path change."""
        if os.path.isdir(path):
            self._file_model.setRootPath(path)
            self._tree_view.setRootIndex(self._file_model.index(path))

    def _on_search_changed(self, text: str) -> None:
        """Handle search text change."""
        self._symbol_list.clear()

        if len(text) < 2:
            return

        # Search for matching symbols
        current_path = self._path_combo.currentText()
        if not current_path:
            return

        text_lower = text.lower()
        for root, dirs, files in os.walk(current_path):
            for file in files:
                if file.endswith(".sym") and text_lower in file.lower():
                    full_path = os.path.join(root, file)
                    rel_path = os.path.relpath(full_path, current_path)
                    item = QListWidgetItem(rel_path)
                    item.setData(Qt.UserRole, full_path)
                    self._symbol_list.addItem(item)

            # Limit results
            if self._symbol_list.count() > 100:
                break

    def _on_tree_clicked(self, index: QModelIndex) -> None:
        """Handle tree item click."""
        file_path = self._file_model.filePath(index)
        if file_path.endswith(".sym"):
            self._select_symbol(file_path)

    def _on_tree_double_clicked(self, index: QModelIndex) -> None:
        """Handle tree item double-click."""
        file_path = self._file_model.filePath(index)
        if file_path.endswith(".sym"):
            self._select_symbol(file_path)
            self.accept()

    def _on_symbol_clicked(self, item: QListWidgetItem) -> None:
        """Handle symbol list item click."""
        file_path = item.data(Qt.UserRole)
        if file_path:
            self._select_symbol(file_path)

    def _on_symbol_double_clicked(self, item: QListWidgetItem) -> None:
        """Handle symbol list item double-click."""
        file_path = item.data(Qt.UserRole)
        if file_path:
            self._select_symbol(file_path)
            self.accept()

    def _on_recent_double_clicked(self, item: QListWidgetItem) -> None:
        """Handle recent symbol double-click."""
        file_path = item.data(Qt.UserRole)
        if file_path and os.path.exists(file_path):
            self._select_symbol(file_path)
            self.accept()

    def _select_symbol(self, file_path: str) -> None:
        """Select a symbol and update the preview."""
        self._selected_symbol = file_path
        self._selection_edit.setText(file_path)
        self._ok_button.setEnabled(True)

        # Update info label
        name = os.path.basename(file_path)
        dirname = os.path.dirname(file_path)

        info_text = f"<b>{name}</b><br>"
        info_text += f"Path: {dirname}<br>"

        # Try to read symbol properties
        try:
            with open(file_path, 'r') as f:
                content = f.read(2000)  # Read first 2KB

            # Extract type from K record
            for line in content.split('\n'):
                if line.startswith('K '):
                    if 'type=' in line:
                        type_start = line.find('type=') + 5
                        type_end = line.find(' ', type_start)
                        if type_end == -1:
                            type_end = len(line)
                        symbol_type = line[type_start:type_end].strip('{}')
                        info_text += f"Type: {symbol_type}<br>"
                        break

        except Exception:
            pass

        self._info_label.setText(info_text)

        # TODO: Render preview

    @property
    def selected_symbol(self) -> Optional[str]:
        """Get the selected symbol path."""
        return self._selected_symbol

    def accept(self) -> None:
        """Accept the dialog."""
        if self._selected_symbol:
            # Add to recent
            if self._selected_symbol not in self._recent_symbols:
                self._recent_symbols.insert(0, self._selected_symbol)
                self._recent_symbols = self._recent_symbols[:10]

            self.symbol_selected.emit(self._selected_symbol)

        super().accept()

    def set_recent_symbols(self, symbols: List[str]) -> None:
        """Set the list of recent symbols."""
        self._recent_symbols = symbols[:10]
        self._recent_list.clear()

        for path in self._recent_symbols:
            if os.path.exists(path):
                name = os.path.basename(path)
                item = QListWidgetItem(name)
                item.setData(Qt.UserRole, path)
                item.setToolTip(path)
                self._recent_list.addItem(item)

    def get_recent_symbols(self) -> List[str]:
        """Get the list of recent symbols."""
        return self._recent_symbols.copy()
