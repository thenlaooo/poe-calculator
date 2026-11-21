"""Смоук окна: границы длины, CCA + Type 4, тема, справка, без исключений."""

from __future__ import annotations

import csv
import json
import os
import tempfile
from pathlib import Path

import pytest
from PySide6.QtCore import QSettings
from PySide6.QtGui import QAction, QPalette
from PySide6.QtWidgets import (
    QApplication,
    QComboBox,
    QDialog,
    QDoubleSpinBox,
    QLabel,
    QPushButton,
    QSpinBox,
    QTableWidget,
    QTextBrowser,
    QWidget,
)

from gui.help_dialog import about_text, build_help_html
from gui.main_window import MainWindow
from gui.themes import LIGHT


@pytest.fixture(scope="module")
def qapp(tmp_path_factory: pytest.TempPathFactory) -> QApplication:
    folder = tmp_path_factory.mktemp("qsettings")
    QSettings.setDefaultFormat(QSettings.Format.IniFormat)
    QSettings.setPath(QSettings.Format.IniFormat, QSettings.Scope.UserScope, str(folder))
    application = QApplication.instance()
    if not isinstance(application, QApplication):
        application = QApplication([])
    application.setOrganizationName("NSTK")
    application.setApplicationName("PoEVoltageDropTest")
    return application


def _cell(table: QTableWidget, name: str) -> str:
    for row in range(table.rowCount()):
        title = table.item(row, 0)
        value = table.item(row, 1)
        if title is not None and title.text() == name and value is not None:
            return value.text()
    raise AssertionError(f"В таблице нет строки «{name}»")


def test_help_text_comes_from_the_data_module() -> None:
    page = build_help_html(LIGHT)
    assert "Rж = r · L / 1000" in page
    assert "71,3" in page
    assert "84,2" in page
    assert "12,95" in page
    assert "Направляющие среды" in about_text()


def test_window_covers_boundaries_theme_and_help(qapp: QApplication, capfd: pytest.CaptureFixture[str]) -> None:
    window = MainWindow()
    window.show()
    qapp.processEvents()

    table = window.findChild(QTableWidget, "resultTable")
    length = window.findChild(QSpinBox, "lengthSpin")
    hint = window.findChild(QLabel, "lengthHint")
    recommendation = window.findChild(QLabel, "recommendationLabel")
    assert table is not None and length is not None and hint is not None and recommendation is not None

    assert _cell(table, "Вердикт") == "Работает"
    assert "Запас" in recommendation.text()
    assert length.value() == 100
    assert "Норма" in hint.text()

    length.setValue(1)
    assert _cell(table, "Вердикт") == "Работает"
    length.setValue(150)
    assert _cell(table, "Вердикт") == "Не работает"
    assert "100" in hint.text()
    assert "100" in recommendation.text()

    standard = window.findChild(QComboBox, "standardCombo")
    category = window.findChild(QComboBox, "categoryCombo")
    material = window.findChild(QComboBox, "materialCombo")
    assert standard is not None and category is not None and material is not None
    for combo in (standard, category, material):
        for index in range(combo.count()):
            combo.setCurrentIndex(index)
            for meters in (1, 100, 150):
                length.setValue(meters)
                assert _cell(table, "Вердикт") in {"Работает", "Не работает"}
                assert recommendation.text().count(".") >= 2

    category.setCurrentIndex(category.findData("cat5e"))
    standard.setCurrentIndex(standard.findData("802.3bt-type4"))
    material.setCurrentIndex(material.findData("CCA"))
    power = window.findChild(QDoubleSpinBox, "powerSpin")
    voltage = window.findChild(QComboBox, "voltageCombo")
    assert power is not None and voltage is not None
    assert power.value() == pytest.approx(71.3)
    assert float(voltage.currentData()) == pytest.approx(52.0)

    length.setValue(1)
    assert _cell(table, "Вердикт") == "Работает"
    length.setValue(100)
    assert _cell(table, "Вердикт") == "Не работает"
    assert "—" not in _cell(table, "Напряжение на PD, В")
    length.setValue(150)
    assert _cell(table, "Вердикт") == "Не работает"
    assert _cell(table, "Напряжение на PD, В") == "—"
    assert "невозможно" in recommendation.text().lower()

    plot = window.findChild(QWidget, "plotWidget")
    assert plot is not None
    assert plot.figure.axes[0].lines  # type: ignore[attr-defined]

    window.findChild(QAction, "themeDark").trigger()
    qapp.processEvents()
    assert qapp.palette().color(QPalette.ColorRole.Window).name() == "#14181a"
    assert QSettings().value("ui/theme") == "dark"

    window.findChild(QAction, "actionHelp").trigger()
    qapp.processEvents()
    dialog = window.findChild(QDialog, "helpDialog")
    assert dialog is not None and dialog.isVisible()
    browser = dialog.findChild(QTextBrowser)
    assert browser is not None
    assert "802.3bt" in browser.toHtml()
    assert "84,2" in browser.toHtml()
    dialog.close()

    window.findChild(QPushButton, "resetButton").click()
    assert length.value() == 100
    assert _cell(table, "Вердикт") == "Работает"

    window.close()
    restored = MainWindow()
    restored.show()
    qapp.processEvents()
    assert qapp.palette().color(QPalette.ColorRole.Window).name() == "#14181a"
    restored.findChild(QAction, "themeLight").trigger()
    assert QSettings().value("ui/theme") == "light"
    restored.close()

    captured = capfd.readouterr()
    assert "Traceback" not in captured.err
    assert "Traceback" not in captured.out


def test_toolbar_and_shortcuts(qapp: QApplication) -> None:
    """Проверка тулбара и горячих клавиш."""
    window = MainWindow()
    window.show()
    qapp.processEvents()

    toolbar = window.findChild(QWidget, "mainToolbar")
    assert toolbar is not None

    # Проверяем действия на тулбаре
    actions = toolbar.actions()
    action_texts = [a.text() for a in actions]
    assert "Сбросить" in action_texts
    assert "Тёмная тема" in action_texts or "Светлая тема" in action_texts
    assert "Копировать рекомендацию" in action_texts

    # Проверяем меню через меню бар
    menu_bar = window.menuBar()
    file_menu = None
    presets_menu = None
    for action in menu_bar.actions():
        menu = action.menu()
        if menu:
            if menu.title() == "Файл":
                file_menu = menu
            elif menu.title() == "Пресеты":
                presets_menu = menu

    assert file_menu is not None
    assert presets_menu is not None

    window.close()


def test_statusbar(qapp: QApplication) -> None:
    """Проверка статусбара."""
    window = MainWindow()
    window.show()
    qapp.processEvents()

    status_bar = window.statusBar()
    assert status_bar is not None
    # Проверяем, что статусбар имеет нашу метку
    # QStatusBar не имеет count(), проверяем через children
    children = status_bar.findChildren(QLabel)
    assert len(children) > 0

    window.close()


def test_presets_menu(qapp: QApplication) -> None:
    """Проверка меню пресетов."""
    window = MainWindow()
    window.show()
    qapp.processEvents()

    table = window.findChild(QTableWidget, "resultTable")
    length = window.findChild(QSpinBox, "lengthSpin")
    recommendation = window.findChild(QLabel, "recommendationLabel")

    # Находим меню Пресеты через меню бар
    menu_bar = window.menuBar()
    presets_menu = None
    for action in menu_bar.actions():
        menu = action.menu()
        if menu and menu.title() == "Пресеты":
            presets_menu = menu
            break

    assert presets_menu is not None

    # Находим действия пресетов
    actions = presets_menu.actions()
    assert len(actions) >= 6  # должно быть 6 пресетов

    # Проверяем первый пресет (PoE 802.3af)
    actions[0].trigger()
    qapp.processEvents()
    assert length.value() == 100
    standard = window.findChild(QComboBox, "standardCombo")
    assert standard.currentData() == "802.3af"

    # Проверяем пресет CCA vs Cu (последний)
    actions[-1].trigger()
    qapp.processEvents()
    material = window.findChild(QComboBox, "materialCombo")
    assert material.currentData() == "CCA"
    assert _cell(table, "Вердикт") == "Не работает"

    window.close()


def test_export_json(qapp: QApplication, tmp_path: Path) -> None:
    """Проверка экспорта в JSON."""
    window = MainWindow()
    window.show()
    qapp.processEvents()

    # Экспортируем отчёт
    export_path = tmp_path / "test_report.json"
    from calculator import CalcInput, build_report
    from data import get_standard

    report = build_report(CalcInput(
        standard_id="802.3at",
        v_pse=50.0,
        p_pd=25.5,
        length_m=100.0,
        category_id="cat5e",
        awg="24",
        material_id="Cu",
    ))

    # Используем метод экспорта окна
    window._export_json(str(export_path))
    qapp.processEvents()

    assert export_path.exists()
    with open(export_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    assert data["input"]["standard"] == "802.3at"
    assert data["input"]["v_pse_v"] == 50.0
    assert data["result"]["works"] is True
    assert "recommendation" in data

    window.close()


def test_export_csv(qapp: QApplication, tmp_path: Path) -> None:
    """Проверка экспорта в CSV."""
    window = MainWindow()
    window.show()
    qapp.processEvents()

    export_path = tmp_path / "test_report.csv"
    window._export_csv(str(export_path))
    qapp.processEvents()

    assert export_path.exists()
    with open(export_path, "r", encoding="utf-8") as f:
        reader = csv.reader(f, delimiter=";")
        rows = list(reader)

    # Проверяем структуру CSV
    assert rows[0] == ["Параметр", "Значение"]
    # Найдём строку со стандартом
    standard_rows = [r for r in rows if r and r[0] == "Стандарт"]
    assert len(standard_rows) == 1
    assert standard_rows[0][1] == "802.3at"

    window.close()


def test_copy_recommendation(qapp: QApplication) -> None:
    """Проверка копирования рекомендации в буфер обмена."""
    window = MainWindow()
    window.show()
    qapp.processEvents()

    window._copy_recommendation()
    qapp.processEvents()

    clipboard = QApplication.clipboard()
    text = clipboard.text()
    assert "Запас" in text or "не работает" in text.lower()

    window.close()


def test_window_geometry_persistence(qapp: QApplication, tmp_path_factory: pytest.TempPathFactory) -> None:
    """Проверка сохранения геометрии окна."""
    folder = tmp_path_factory.mktemp("qsettings2")
    QSettings.setDefaultFormat(QSettings.Format.IniFormat)
    QSettings.setPath(QSettings.Format.IniFormat, QSettings.Scope.UserScope, str(folder))

    window1 = MainWindow()
    window1.show()
    qapp.processEvents()

    # Изменяем размер
    window1.resize(1300, 900)
    window1.close()

    # Создаём новое окно с теми же настройками
    window2 = MainWindow()
    window2.show()
    qapp.processEvents()

    # Геометрия должна восстановиться (примерно)
    # Точный размер может отличаться из-за WM, но настройки должны загрузиться
    assert window2.width() > 1000
    assert window2.height() > 800

    window2.close()
