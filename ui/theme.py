"""
VS Code-inspired UI themes for PyXSchem.

Provides dark and light editor themes with flat toolbars,
monochrome icon surfaces, and status-bar accents.
"""

from __future__ import annotations

from dataclasses import dataclass

from PySide6.QtGui import QFont, QFontDatabase
from PySide6.QtWidgets import QApplication, QMainWindow


_FONT_CANDIDATES = (
    "Segoe UI",
    "Noto Sans",
    "Ubuntu",
    "Cantarell",
)


@dataclass(frozen=True)
class ThemeSpec:
    """Color tokens for a single UI theme."""

    background: str
    panel: str
    panel_alt: str
    border: str
    text: str
    text_muted: str
    accent: str
    hover: str
    active: str
    disabled: str
    status_bg: str
    status_text: str


_THEMES: dict[str, ThemeSpec] = {
    "dark": ThemeSpec(
        background="#1e1e1e",
        panel="#252526",
        panel_alt="#2d2d30",
        border="#3c3c3c",
        text="#cccccc",
        text_muted="#9da5b4",
        accent="#007acc",
        hover="#2a2d2e",
        active="#094771",
        disabled="#666666",
        status_bg="#007acc",
        status_text="#ffffff",
    ),
    "light": ThemeSpec(
        background="#f3f3f3",
        panel="#ffffff",
        panel_alt="#f7f7f7",
        border="#d4d4d4",
        text="#1f1f1f",
        text_muted="#4a4a4a",
        accent="#005fb8",
        hover="#e9edf3",
        active="#cfe8ff",
        disabled="#9a9a9a",
        status_bg="#007acc",
        status_text="#ffffff",
    ),
}


def available_themes() -> tuple[str, ...]:
    """Return available UI theme names."""
    return tuple(_THEMES.keys())


def is_dark_theme(theme_name: str) -> bool:
    """Return True if the theme should use dark canvas colors."""
    return theme_name.lower() != "light"


def _pick_font_family() -> str:
    """Pick the first available UI font family from preferred candidates."""
    app = QApplication.instance()
    if app is None:
        return "Sans Serif"

    families = set(QFontDatabase().families())
    for family in _FONT_CANDIDATES:
        if family in families:
            return family
    return app.font().family() or "Sans Serif"


def apply_editor_theme(window: QMainWindow, theme_name: str = "dark") -> str:
    """Apply the selected VS Code-like theme to a main window.

    Returns:
        The normalized theme key that was applied.
    """
    theme_key = (theme_name or "dark").lower()
    if theme_key not in _THEMES:
        theme_key = "dark"

    theme = _THEMES[theme_key]

    family = _pick_font_family()
    window_font = QFont(family, 10)
    window_font.setStyleStrategy(QFont.PreferAntialias)
    window.setFont(window_font)

    window.setProperty("uiTheme", theme_key)
    window.setStyleSheet(
        f"""
        QMainWindow {{
            background: {theme.background};
            color: {theme.text};
        }}

        QMenuBar {{
            background: {theme.panel};
            color: {theme.text};
            border-bottom: 1px solid {theme.border};
            spacing: 2px;
            padding: 2px 4px;
        }}

        QMenuBar::item {{
            padding: 5px 10px;
            border-radius: 2px;
            background: transparent;
        }}

        QMenuBar::item:selected {{
            background: {theme.hover};
            color: {theme.text};
        }}

        QMenu {{
            background: {theme.panel};
            border: 1px solid {theme.border};
            color: {theme.text};
            padding: 4px;
        }}

        QMenu::item {{
            padding: 5px 20px;
            border-radius: 2px;
        }}

        QMenu::item:selected {{
            background: {theme.hover};
            color: {theme.text};
        }}

        QToolBar {{
            background: {theme.panel};
            border: 1px solid {theme.border};
            spacing: 1px;
            padding: 2px 4px;
            margin: 2px 4px;
        }}

        QToolBar#core_toolbar {{
            background: {theme.panel_alt};
        }}

        QToolButton {{
            background: transparent;
            border: 1px solid transparent;
            border-radius: 2px;
            color: {theme.text};
            padding: 4px 7px;
            margin: 0px;
        }}

        QToolButton:hover {{
            background: {theme.hover};
            color: {theme.accent};
        }}

        QToolButton:pressed {{
            background: {theme.active};
            color: #ffffff;
        }}

        QToolButton:checked {{
            background: {theme.active};
            border-color: {theme.accent};
            color: #ffffff;
        }}

        QToolButton:disabled {{
            color: {theme.disabled};
        }}

        QTabWidget::pane {{
            border: 1px solid {theme.border};
            background: {theme.background};
            top: -1px;
        }}

        QTabBar::tab {{
            background: {theme.panel};
            color: {theme.text_muted};
            border: 1px solid {theme.border};
            border-bottom: none;
            padding: 5px 12px;
            margin-right: 2px;
        }}

        QTabBar::tab:selected {{
            background: {theme.background};
            color: {theme.text};
        }}

        QStatusBar {{
            background: {theme.status_bg};
            color: {theme.status_text};
            border-top: 1px solid {theme.border};
        }}

        QLabel#status_item {{
            color: {theme.status_text};
            background: transparent;
            padding: 2px 7px;
        }}

        QLabel#status_item_weak {{
            color: #d8ecff;
            background: transparent;
            padding: 2px 7px;
        }}

        QLabel#status_item_ok {{
            color: #8de06f;
            background: transparent;
            font-weight: 600;
            padding: 2px 7px;
        }}

        QDockWidget {{
            color: {theme.text};
        }}

        QDockWidget::title {{
            background: {theme.panel};
            border: 1px solid {theme.border};
            padding: 6px 10px;
        }}

        QWidget#workflow_panel {{
            background: {theme.background};
            border-left: 1px solid {theme.border};
            border-right: 1px solid {theme.border};
            border-bottom: 1px solid {theme.border};
        }}

        QPushButton#workflow_btn {{
            background: {theme.panel};
            color: {theme.text};
            border: 1px solid {theme.border};
            border-radius: 3px;
            padding: 6px 9px;
            text-align: left;
            font-weight: 600;
        }}

        QPushButton#workflow_btn:hover {{
            background: {theme.hover};
            border-color: {theme.accent};
            color: {theme.text};
        }}

        QComboBox {{
            background: {theme.panel};
            color: {theme.text};
            border: 1px solid {theme.border};
            border-radius: 2px;
            padding: 4px 20px 4px 7px;
            min-width: 100px;
        }}

        QComboBox:hover {{
            border-color: {theme.accent};
        }}

        QDockWidget#terminal_console_dock {{
            border-top: 1px solid {theme.border};
        }}

        QPlainTextEdit#terminal_output,
        QPlainTextEdit#debug_console {{
            background: {theme.panel_alt};
            color: {theme.text};
            border: 1px solid {theme.border};
            selection-background-color: {theme.active};
        }}

        QLineEdit {{
            background: {theme.panel};
            color: {theme.text};
            border: 1px solid {theme.border};
            border-radius: 2px;
            padding: 4px 6px;
        }}

        QLineEdit:focus {{
            border-color: {theme.accent};
        }}
        """
    )

    return theme_key
