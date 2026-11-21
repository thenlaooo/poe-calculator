"""Светлая и тёмная темы. Палитра общая для виджетов и для графика."""

from __future__ import annotations

from dataclasses import dataclass

from PySide6.QtGui import QColor, QPalette
from PySide6.QtWidgets import QApplication


@dataclass(frozen=True, slots=True)
class Theme:
    name: str
    window_bg: str
    panel_bg: str
    card_bg: str
    text: str
    text_muted: str
    accent: str
    accent_soft: str
    border: str
    input_bg: str
    success: str
    success_bg: str
    danger: str
    danger_bg: str
    warning: str
    warning_bg: str
    plot_face: str
    plot_text: str
    plot_grid: str
    plot_vpd: str
    plot_du: str
    plot_limit: str
    plot_current: str
    plot_max_len: str
    plot_shade: str
    recommendation_bg: str


# Тёплый «бумажный» фон и медный цвет падения — прибор, а не стандартная серая форма Qt.
LIGHT = Theme(
    name="light",
    window_bg="#e7e1d6",
    panel_bg="#f3efe7",
    card_bg="#fbf8f3",
    text="#1c2430",
    text_muted="#5e6874",
    accent="#0f5f59",
    accent_soft="#d7ebe7",
    border="#ddd4c6",
    input_bg="#fffcf7",
    success="#0d6b45",
    success_bg="#d9f2e6",
    danger="#9d2c2c",
    danger_bg="#f8d9d6",
    warning="#8a5a12",
    warning_bg="#f8e7c8",
    plot_face="#fbf8f3",
    plot_text="#1c2430",
    plot_grid="#e4d9c8",
    plot_vpd="#0f5f59",
    plot_du="#b8612d",
    plot_limit="#9d2c2c",
    plot_current="#1c2430",
    plot_max_len="#1d5f8a",
    plot_shade="#9d2c2c",
    recommendation_bg="#fffcf7",
)

DARK = Theme(
    name="dark",
    window_bg="#14181a",
    panel_bg="#1c2224",
    card_bg="#232b2e",
    text="#f0ebe3",
    text_muted="#a7b0aa",
    accent="#6fd0c6",
    accent_soft="#1e3a38",
    border="#3a4548",
    input_bg="#1a2123",
    success="#7ddec0",
    success_bg="#16382e",
    danger="#ffb1a8",
    danger_bg="#3d2222",
    warning="#f0c27a",
    warning_bg="#3a2e1c",
    plot_face="#1a2123",
    plot_text="#f0ebe3",
    plot_grid="#334044",
    plot_vpd="#6fd0c6",
    plot_du="#e39a62",
    plot_limit="#ffb1a8",
    plot_current="#f0ebe3",
    plot_max_len="#8ec8ff",
    plot_shade="#ffb1a8",
    recommendation_bg="#232b2e",
)


def theme_by_name(name: str) -> Theme:
    if name == DARK.name:
        return DARK
    return LIGHT


def apply_theme(app: QApplication, theme: Theme) -> None:
    """Fusion выравнивает виджеты Windows и Ubuntu, палитра красит обе темы."""

    app.setStyle("Fusion")
    palette = QPalette()
    palette.setColor(QPalette.ColorRole.Window, QColor(theme.window_bg))
    palette.setColor(QPalette.ColorRole.WindowText, QColor(theme.text))
    palette.setColor(QPalette.ColorRole.Base, QColor(theme.input_bg))
    palette.setColor(QPalette.ColorRole.AlternateBase, QColor(theme.panel_bg))
    palette.setColor(QPalette.ColorRole.Text, QColor(theme.text))
    palette.setColor(QPalette.ColorRole.Button, QColor(theme.panel_bg))
    palette.setColor(QPalette.ColorRole.ButtonText, QColor(theme.text))
    palette.setColor(QPalette.ColorRole.Highlight, QColor(theme.accent))
    palette.setColor(QPalette.ColorRole.HighlightedText, QColor("#ffffff"))
    palette.setColor(QPalette.ColorRole.ToolTipBase, QColor(theme.card_bg))
    palette.setColor(QPalette.ColorRole.ToolTipText, QColor(theme.text))
    palette.setColor(QPalette.ColorRole.PlaceholderText, QColor(theme.text_muted))
    palette.setColor(QPalette.ColorRole.Mid, QColor(theme.border))
    palette.setColor(QPalette.ColorRole.Dark, QColor(theme.border))
    palette.setColor(QPalette.ColorRole.Shadow, QColor(theme.border))
    palette.setColor(QPalette.ColorRole.Light, QColor(theme.panel_bg))
    for role in (QPalette.ColorRole.Text, QPalette.ColorRole.WindowText, QPalette.ColorRole.ButtonText):
        palette.setColor(QPalette.ColorGroup.Disabled, role, QColor(theme.text_muted))
    app.setPalette(palette)
    app.setStyleSheet(_stylesheet(theme))


def _stylesheet(theme: Theme) -> str:
    return f"""
    QMainWindow, QDialog {{
        background: {theme.window_bg};
        color: {theme.text};
    }}
    QWidget#centralWidget {{
        background: {theme.window_bg};
    }}
    QWidget#sidePanel, QScrollArea#sideScroll {{
        background: {theme.panel_bg};
        border: none;
    }}
    QWidget#resultPanel {{
        background: {theme.window_bg};
    }}
    QLabel {{
        color: {theme.text};
        background: transparent;
    }}
    QGroupBox {{
        font-weight: 600;
        border: 1px solid {theme.border};
        border-radius: 10px;
        margin-top: 14px;
        padding: 16px 12px 12px 12px;
        background: {theme.card_bg};
        color: {theme.text};
    }}
    QGroupBox::title {{
        subcontrol-origin: margin;
        subcontrol-position: top left;
        left: 12px;
        padding: 0 4px;
        color: {theme.accent};
        background: transparent;
    }}
    QComboBox, QSpinBox, QDoubleSpinBox {{
        background: {theme.input_bg};
        color: {theme.text};
        border: 1px solid {theme.border};
        border-radius: 6px;
        padding: 6px 8px;
        min-height: 22px;
    }}
    QComboBox:focus, QSpinBox:focus, QDoubleSpinBox:focus {{
        border: 1px solid {theme.accent};
    }}
    QComboBox::drop-down {{
        border: none;
        width: 22px;
    }}
    QComboBox QAbstractItemView {{
        background: {theme.input_bg};
        color: {theme.text};
        selection-background-color: {theme.accent_soft};
        selection-color: {theme.text};
        border: 1px solid {theme.border};
        outline: none;
    }}
    QPushButton#resetButton {{
        background: transparent;
        color: {theme.text};
        border: 1px solid {theme.border};
        border-radius: 6px;
        padding: 8px 14px;
    }}
    QPushButton#resetButton:hover {{
        border-color: {theme.accent};
        color: {theme.accent};
    }}
    QMenuBar {{
        background: {theme.window_bg};
        color: {theme.text};
        border-bottom: 1px solid {theme.border};
    }}
    QMenuBar::item:selected {{
        background: {theme.accent_soft};
    }}
    QMenu {{
        background: {theme.card_bg};
        color: {theme.text};
        border: 1px solid {theme.border};
    }}
    QMenu::item:selected {{
        background: {theme.accent_soft};
    }}
    QTableWidget {{
        background: {theme.card_bg};
        color: {theme.text};
        gridline-color: {theme.border};
        border: 1px solid {theme.border};
        border-radius: 8px;
        selection-background-color: {theme.card_bg};
        selection-color: {theme.text};
    }}
    QHeaderView::section {{
        background: {theme.panel_bg};
        color: {theme.text_muted};
        border: none;
        border-bottom: 1px solid {theme.border};
        padding: 6px 8px;
        font-weight: 600;
    }}
    QToolTip {{
        background: {theme.card_bg};
        color: {theme.text};
        border: 1px solid {theme.border};
        padding: 4px 6px;
    }}
    QScrollBar:vertical {{
        background: {theme.panel_bg};
        width: 10px;
        margin: 0;
    }}
    QScrollBar::handle:vertical {{
        background: {theme.border};
        border-radius: 4px;
        min-height: 24px;
    }}
    QScrollBar::add-line, QScrollBar::sub-line {{
        height: 0;
    }}
    QSplitter::handle {{
        background: {theme.window_bg};
    }}
    """
