"""Главное окно: параметры слева, таблица и график справа, рекомендация снизу."""

from __future__ import annotations

import json
import math
from contextlib import contextmanager
from collections.abc import Iterator

from PySide6.QtCore import QSettings, Qt, QByteArray
from PySide6.QtGui import QAction, QBrush, QColor, QFontMetrics, QKeySequence, QResizeEvent
from PySide6.QtWidgets import (
    QApplication,
    QComboBox,
    QDoubleSpinBox,
    QFileDialog,
    QFormLayout,
    QFrame,
    QGroupBox,
    QHeaderView,
    QLabel,
    QMainWindow,
    QMenu,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QSpinBox,
    QSplitter,
    QStatusBar,
    QTableWidget,
    QTableWidgetItem,
    QToolBar,
    QVBoxLayout,
    QWidget,
)

from calculator import CalcInput, Report, build_report, default_input, explanation
from data import (
    APP_TITLE,
    CATEGORIES,
    MATERIALS,
    P_PD_MIN_W,
    STANDARDS,
    format_number,
    format_power,
    get_standard,
    selectable_pse_voltages,
)
from gui.help_dialog import HelpDialog, about_text
from gui.plot_widget import PlotWidget
from gui.themes import Theme, apply_theme, theme_by_name


_ROWS: tuple[str, ...] = (
    "Сопротивление жилы, Ом",
    "Сопротивление петли, Ом",
    "Ток линии",
    "Ток на пару",
    "Падение напряжения, В",
    "Падение напряжения, %",
    "Напряжение на PD, В",
    "Потери в кабеле, Вт",
    "Мощность на выходе PSE, Вт",
    "Вердикт",
    "Пояснение",
)


class MainWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle(APP_TITLE)
        self.setMinimumSize(1080, 820)
        self._theme = theme_by_name(_stored_theme_name())
        app = QApplication.instance()
        if not isinstance(app, QApplication):
            raise RuntimeError("Сначала создайте QApplication")
        apply_theme(app, self._theme)
        self._help_dialog: HelpDialog | None = None
        self._report: Report | None = None
        self._power_pinned_to_max = True
        self._fitting_table = False
        self._build_ui()
        self._build_menu()
        self._build_toolbar()
        self._build_statusbar()
        self._sync_theme_checks()
        self._paint_chrome()
        self._restore_geometry()
        self.apply_input(default_input())

    def apply_input(self, inp: CalcInput) -> None:
        """Ставит параметры и сразу пересчитывает. Так же работает «Сбросить»."""

        with self._signals_blocked():
            _select(self._standard_combo, inp.standard_id)
            self._reload_voltages(inp.v_pse)
            standard = get_standard(inp.standard_id)
            self._power_spin.setMaximum(standard.p_pd_max_w)
            self._power_spin.setValue(inp.p_pd)
            self._power_pinned_to_max = abs(inp.p_pd - standard.p_pd_max_w) < 0.001
            self._length_spin.setValue(int(round(inp.length_m)))
            _select(self._category_combo, inp.category_id)
            self._reload_awg(inp.awg)
            _select(self._material_combo, inp.material_id)
        self._recalculate()

    def _build_ui(self) -> None:
        central = QWidget()
        central.setObjectName("centralWidget")
        self.setCentralWidget(central)
        root = QVBoxLayout(central)
        root.setContentsMargins(12, 12, 12, 12)
        root.setSpacing(10)

        self._splitter = QSplitter(Qt.Orientation.Horizontal)
        self._splitter.setChildrenCollapsible(False)
        self._splitter.addWidget(self._build_side())
        self._splitter.addWidget(self._build_results())
        self._splitter.setStretchFactor(0, 0)
        self._splitter.setStretchFactor(1, 1)
        self._splitter.setSizes([400, 760])
        root.addWidget(self._splitter, stretch=1)
        root.addWidget(self._build_recommendation())

        self._standard_combo.currentIndexChanged.connect(self._on_standard_changed)
        self._voltage_combo.currentIndexChanged.connect(self._recalculate)
        self._power_spin.valueChanged.connect(self._on_power_changed)
        self._length_spin.valueChanged.connect(self._recalculate)
        self._category_combo.currentIndexChanged.connect(self._on_category_changed)
        self._awg_combo.currentIndexChanged.connect(self._recalculate)
        self._material_combo.currentIndexChanged.connect(self._recalculate)
        self._reset_button.clicked.connect(self._reset)
        self._copy_rec_button.clicked.connect(self._copy_recommendation)
        self._export_button.clicked.connect(self._export_report)

    def _build_side(self) -> QWidget:
        panel = QWidget()
        panel.setObjectName("sidePanel")
        panel.setMinimumWidth(340)
        panel.setMaximumWidth(460)
        # Minimum по высоте равен sizeHint: узкое окно прокручивает панель, а не сжимает подписи.
        panel.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Minimum)
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(14, 8, 14, 8)
        layout.setSpacing(8)

        self._side_title = QLabel("Калькулятор PoE")
        self._side_subtitle = QLabel("Падение напряжения с учётом длины и типа жилы")
        self._side_subtitle.setWordWrap(True)
        layout.addWidget(self._side_title)
        layout.addWidget(self._side_subtitle)

        power_box = QGroupBox("Питание")
        power_form = QFormLayout(power_box)
        power_form.setHorizontalSpacing(10)
        power_form.setVerticalSpacing(8)
        self._standard_combo = QComboBox()
        self._standard_combo.setObjectName("standardCombo")
        for standard in STANDARDS:
            self._standard_combo.addItem(standard.title, standard.id)
        self._standard_combo.setToolTip(
            "Тип PoE задаёт диапазон PSE, мощность, минимум на PD, число пар и ток."
        )
        self._standard_hint = QLabel()
        self._standard_hint.setWordWrap(True)
        self._voltage_combo = QComboBox()
        self._voltage_combo.setObjectName("voltageCombo")
        self._voltage_combo.setToolTip("По умолчанию — минимум стандарта. 48 В скрыто, если стандарт его не допускает.")
        self._power_spin = QDoubleSpinBox()
        self._power_spin.setObjectName("powerSpin")
        self._power_spin.setDecimals(2)
        self._power_spin.setSingleStep(0.05)
        self._power_spin.setMinimum(P_PD_MIN_W)
        self._power_spin.setMaximum(100.0)
        self._power_spin.setSuffix(" Вт")
        self._power_spin.setToolTip("Не выше максимума PD для выбранного стандарта. По умолчанию взят этот максимум.")
        power_form.addRow("Стандарт PoE", self._standard_combo)
        power_form.addRow(self._standard_hint)
        power_form.addRow("Напряжение PSE", self._voltage_combo)
        power_form.addRow("Мощность PD", self._power_spin)
        layout.addWidget(power_box)

        cable_box = QGroupBox("Кабель")
        cable_form = QFormLayout(cable_box)
        cable_form.setHorizontalSpacing(10)
        cable_form.setVerticalSpacing(8)
        self._length_spin = QSpinBox()
        self._length_spin.setObjectName("lengthSpin")
        self._length_spin.setRange(1, 150)
        self._length_spin.setSuffix(" м")
        self._length_spin.setToolTip("От 1 до 150 м. Свыше 100 м длина уже вне нормы канала.")
        self._length_hint = QLabel()
        self._length_hint.setObjectName("lengthHint")
        self._length_hint.setWordWrap(True)
        self._category_combo = QComboBox()
        self._category_combo.setObjectName("categoryCombo")
        for category in CATEGORIES:
            self._category_combo.addItem(category.name, category.id)
        self._category_combo.setToolTip("Категория ограничивает типовые сечения серийного кабеля.")
        self._awg_combo = QComboBox()
        self._awg_combo.setObjectName("awgCombo")
        self._awg_combo.setToolTip("Меньший номер AWG — толще жила и меньше сопротивление.")
        self._material_combo = QComboBox()
        self._material_combo.setObjectName("materialCombo")
        for material in MATERIALS:
            self._material_combo.addItem(material.name, material.id)
        self._material_combo.setToolTip(
            "CCA — омеднённый алюминий: удельное сопротивление меди умножается на 1,6."
        )
        self._resistance_hint = QLabel()
        self._resistance_hint.setWordWrap(True)
        cable_form.addRow("Длина", self._length_spin)
        cable_form.addRow(self._length_hint)
        cable_form.addRow("Категория", self._category_combo)
        cable_form.addRow("Сечение жилы", self._awg_combo)
        cable_form.addRow("Материал", self._material_combo)
        cable_form.addRow(self._resistance_hint)
        layout.addWidget(cable_box)

        layout.addStretch(1)
        self._auto_note = QLabel("Результат пересчитывается сразу при изменении любого поля.")
        self._auto_note.setWordWrap(True)
        self._reset_button = QPushButton("Сбросить")
        self._reset_button.setObjectName("resetButton")
        self._reset_button.setToolTip("Вернуть PoE+, 50 В, 25,5 Вт, 100 м, Cat5e, 24 AWG, медь.")
        layout.addWidget(self._auto_note)
        layout.addWidget(self._reset_button)

        scroll = QScrollArea()
        scroll.setObjectName("sideScroll")
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll.setWidget(panel)
        scroll.setMinimumWidth(360)
        return scroll

    def _build_results(self) -> QWidget:
        panel = QWidget()
        panel.setObjectName("resultPanel")
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(8, 0, 0, 0)
        layout.setSpacing(8)
        self._result_title = QLabel("Результаты")
        self._summary = QLabel()
        self._summary.setWordWrap(True)
        layout.addWidget(self._result_title)
        layout.addWidget(self._summary)

        self._table = QTableWidget(len(_ROWS), 2)
        self._table.setObjectName("resultTable")
        self._table.setHorizontalHeaderLabels(("Параметр", "Значение"))
        self._table.verticalHeader().setVisible(False)
        self._table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self._table.setSelectionMode(QTableWidget.SelectionMode.NoSelection)
        self._table.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self._table.setWordWrap(True)
        self._table.setCornerButtonEnabled(False)
        header = self._table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        header.setDefaultAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
        for row, name in enumerate(_ROWS):
            name_item = QTableWidgetItem(name)
            value_item = QTableWidgetItem("—")
            name_item.setFlags(Qt.ItemFlag.ItemIsEnabled)
            value_item.setFlags(Qt.ItemFlag.ItemIsEnabled)
            self._table.setItem(row, 0, name_item)
            self._table.setItem(row, 1, value_item)
        layout.addWidget(self._table)

        self._plot = PlotWidget()
        self._plot.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        layout.addWidget(self._plot, stretch=1)
        return panel

    def _build_recommendation(self) -> QFrame:
        frame = QFrame()
        frame.setObjectName("recommendationFrame")
        layout = QVBoxLayout(frame)
        layout.setContentsMargins(14, 10, 14, 12)
        layout.setSpacing(4)

        title_row = QWidget()
        title_layout = QVBoxLayout(title_row)
        title_layout.setContentsMargins(0, 0, 0, 0)
        title_layout.setSpacing(4)

        self._recommendation_title = QLabel("Рекомендация")
        self._recommendation_title.setObjectName("recommendationTitle")

        btn_row = QWidget()
        btn_layout = QVBoxLayout(btn_row)
        btn_layout.setContentsMargins(0, 0, 0, 0)
        btn_layout.setSpacing(4)

        self._copy_rec_button = QPushButton("Копировать")
        self._copy_rec_button.setObjectName("copyRecButton")
        self._copy_rec_button.setToolTip("Скопировать рекомендацию в буфер обмена (Ctrl+Shift+C)")
        self._copy_rec_button.setFixedHeight(24)

        self._export_button = QPushButton("Экспорт…")
        self._export_button.setObjectName("exportButton")
        self._export_button.setToolTip("Сохранить отчёт в JSON или CSV (Ctrl+E)")
        self._export_button.setFixedHeight(24)

        btn_layout.addWidget(self._copy_rec_button)
        btn_layout.addWidget(self._export_button)

        title_layout.addWidget(self._recommendation_title)
        title_layout.addWidget(btn_row)

        self._recommendation_label = QLabel("—")
        self._recommendation_label.setObjectName("recommendationLabel")
        self._recommendation_label.setWordWrap(True)
        self._recommendation_label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        self._recommendation_label.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop)
        self._recommendation_label.setMinimumHeight(52)

        layout.addWidget(title_row)
        layout.addWidget(self._recommendation_label)
        return frame

    def _build_menu(self) -> None:
        file_menu = self.menuBar().addMenu("Файл")
        export_action = QAction("Экспорт отчёта…", self)
        export_action.setShortcut(QKeySequence("Ctrl+E"))
        export_action.triggered.connect(self._export_report)
        file_menu.addAction(export_action)
        file_menu.addSeparator()
        quit_action = QAction("Выход", self)
        quit_action.setShortcut(QKeySequence.StandardKey.Quit)
        quit_action.triggered.connect(self.close)
        file_menu.addAction(quit_action)

        view_menu = self.menuBar().addMenu("Вид")
        self._action_light = QAction("Светлая тема", self)
        self._action_light.setObjectName("themeLight")
        self._action_light.setCheckable(True)
        self._action_dark = QAction("Тёмная тема", self)
        self._action_dark.setObjectName("themeDark")
        self._action_dark.setCheckable(True)
        self._action_light.triggered.connect(lambda: self._set_theme("light"))
        self._action_dark.triggered.connect(lambda: self._set_theme("dark"))
        view_menu.addAction(self._action_light)
        view_menu.addAction(self._action_dark)

        presets_menu = self.menuBar().addMenu("Пресеты")
        self._add_presets(presets_menu)

        help_menu = self.menuBar().addMenu("Справка")
        help_action = QAction("Справка", self)
        help_action.setObjectName("actionHelp")
        help_action.setShortcut(QKeySequence.StandardKey.HelpContents)
        help_action.triggered.connect(self._open_help)
        about_action = QAction("О программе", self)
        about_action.setObjectName("actionAbout")
        about_action.triggered.connect(self._open_about)
        help_menu.addAction(help_action)
        help_menu.addAction(about_action)

    def _build_toolbar(self) -> None:
        toolbar = QToolBar("Основная панель")
        toolbar.setObjectName("mainToolbar")
        toolbar.setMovable(False)
        toolbar.setFloatable(False)
        self.addToolBar(toolbar)

        reset_action = QAction("Сбросить", self)
        reset_action.setShortcut(QKeySequence("Ctrl+R"))
        reset_action.setToolTip("Вернуть стартовые значения (Ctrl+R)")
        reset_action.triggered.connect(self._reset)
        toolbar.addAction(reset_action)

        toolbar.addSeparator()

        self._theme_action = QAction("Тёмная тема", self)
        self._theme_action.setCheckable(True)
        self._theme_action.setToolTip("Переключить тему (Ctrl+T)")
        self._theme_action.setShortcut(QKeySequence("Ctrl+T"))
        self._theme_action.triggered.connect(self._toggle_theme)
        toolbar.addAction(self._theme_action)

        toolbar.addSeparator()

        copy_action = QAction("Копировать рекомендацию", self)
        copy_action.setShortcut(QKeySequence("Ctrl+Shift+C"))
        copy_action.triggered.connect(self._copy_recommendation)
        toolbar.addAction(copy_action)

    def _build_statusbar(self) -> None:
        status = QStatusBar()
        status.setObjectName("mainStatusBar")
        self.setStatusBar(status)
        self._status_label = QLabel("Готово")
        status.addPermanentWidget(self._status_label)

    def _add_presets(self, menu: QMenu) -> None:
        presets = [
            ("PoE (802.3af) — 48 В, 12,95 Вт, 100 м, Cat5e", {
                "standard_id": "802.3af", "v_pse": 48.0, "p_pd": 12.95,
                "length_m": 100.0, "category_id": "cat5e", "awg": "24", "material_id": "Cu"
            }),
            ("PoE+ (802.3at) — 50 В, 25,5 Вт, 100 м, Cat5e", {
                "standard_id": "802.3at", "v_pse": 50.0, "p_pd": 25.5,
                "length_m": 100.0, "category_id": "cat5e", "awg": "24", "material_id": "Cu"
            }),
            ("PoE++ Type 3 — 50 В, 51 Вт, 100 м, Cat6", {
                "standard_id": "802.3bt-type3", "v_pse": 50.0, "p_pd": 51.0,
                "length_m": 100.0, "category_id": "cat6", "awg": "23", "material_id": "Cu"
            }),
            ("PoE++ Type 4 — 52 В, 71,3 Вт, 100 м, Cat6a", {
                "standard_id": "802.3bt-type4", "v_pse": 52.0, "p_pd": 71.3,
                "length_m": 100.0, "category_id": "cat6a", "awg": "23", "material_id": "Cu"
            }),
            ("Длинная линия Type 4 — 57 В, 71,3 Вт, 150 м, Cat6a 22 AWG", {
                "standard_id": "802.3bt-type4", "v_pse": 57.0, "p_pd": 71.3,
                "length_m": 150.0, "category_id": "cat6a", "awg": "22", "material_id": "Cu"
            }),
            ("CCA vs Cu сравнение — Type 2, 100 м", {
                "standard_id": "802.3at", "v_pse": 50.0, "p_pd": 25.5,
                "length_m": 100.0, "category_id": "cat5e", "awg": "24", "material_id": "CCA"
            }),
        ]
        for name, params in presets:
            action = QAction(name, self)
            action.triggered.connect(lambda checked=False, p=params: self._apply_preset(p))
            menu.addAction(action)

    def _apply_preset(self, params: dict) -> None:
        self.apply_input(CalcInput(**params))
        self._status_label.setText(f"Применён пресет: {params['standard_id']}, {params['length_m']} м, {params['awg']} AWG")

    def _toggle_theme(self) -> None:
        new_theme = "dark" if self._theme.name == "light" else "light"
        self._set_theme(new_theme)

    def _copy_recommendation(self) -> None:
        if self._report is not None:
            QApplication.clipboard().setText(self._report.recommendation)
            self._status_label.setText("Рекомендация скопирована в буфер обмена")

    def _export_report(self) -> None:
        if self._report is None:
            return
        path, selected_filter = QFileDialog.getSaveFileName(
            self, "Экспорт отчёта", "poe_report.json",
            "JSON (*.json);;CSV (*.csv)"
        )
        if not path:
            return
        try:
            if path.endswith(".csv"):
                self._export_csv(path)
            else:
                self._export_json(path)
            self._status_label.setText(f"Отчёт сохранён: {path}")
        except Exception as exc:
            QMessageBox.warning(self, "Ошибка экспорта", str(exc))

    def _export_json(self, path: str) -> None:
        result = self._report.result
        inp = self._selected_input()
        data = {
            "input": {
                "standard": inp.standard_id,
                "v_pse_v": inp.v_pse,
                "p_pd_w": inp.p_pd,
                "length_m": inp.length_m,
                "category": inp.category_id,
                "awg": inp.awg,
                "material": inp.material_id,
            },
            "result": {
                "works": result.works,
                "feasible": result.feasible,
                "v_pd_v": result.v_pd,
                "current_a": result.current_a,
                "current_per_pair_a": result.current_per_pair_a,
                "delta_u_v": result.delta_u_v,
                "delta_u_percent": result.delta_u_percent,
                "p_loss_w": result.p_loss_w,
                "p_pse_w": result.p_pse_w,
                "voltage_ok": result.voltage_ok,
                "power_ok": result.power_ok,
                "current_ok": result.current_ok,
                "length_exceeds_channel": result.length_exceeds_channel,
                "max_working_length_m": self._report.max_working_length_m,
                "reasons": list(result.reasons),
            },
            "recommendation": self._report.recommendation,
        }
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

    def _export_csv(self, path: str) -> None:
        result = self._report.result
        inp = self._selected_input()
        import csv
        with open(path, "w", encoding="utf-8", newline="") as f:
            writer = csv.writer(f, delimiter=";")
            writer.writerow(["Параметр", "Значение"])
            writer.writerow(["Стандарт", inp.standard_id])
            writer.writerow(["Напряжение PSE, В", inp.v_pse])
            writer.writerow(["Мощность PD, Вт", inp.p_pd])
            writer.writerow(["Длина, м", inp.length_m])
            writer.writerow(["Категория", inp.category_id])
            writer.writerow(["Сечение, AWG", inp.awg])
            writer.writerow(["Материал", inp.material_id])
            writer.writerow([])
            writer.writerow(["Результат", ""])
            writer.writerow(["Работает", "Да" if result.works else "Нет"])
            writer.writerow(["Напряжение на PD, В", result.v_pd if result.v_pd is not None else "—"])
            writer.writerow(["Ток линии, А", result.current_a if result.current_a is not None else "—"])
            writer.writerow(["Ток на пару, А", result.current_per_pair_a if result.current_per_pair_a is not None else "—"])
            writer.writerow(["Падение напряжения, В", result.delta_u_v if result.delta_u_v is not None else "—"])
            writer.writerow(["Падение напряжения, %", result.delta_u_percent if result.delta_u_percent is not None else "—"])
            writer.writerow(["Потери в кабеле, Вт", result.p_loss_w if result.p_loss_w is not None else "—"])
            writer.writerow(["Мощность PSE, Вт", result.p_pse_w if result.p_pse_w is not None else "—"])
            writer.writerow(["Макс. рабочая длина, м", self._report.max_working_length_m if self._report.max_working_length_m is not None else "—"])
            writer.writerow([])
            writer.writerow(["Рекомендация", self._report.recommendation])

    def _restore_geometry(self) -> None:
        settings = QSettings()
        geometry = settings.value("window/geometry")
        if isinstance(geometry, QByteArray):
            self.restoreGeometry(geometry)
        state = settings.value("window/state")
        if isinstance(state, QByteArray):
            self.restoreState(state)
        splitter_sizes = settings.value("window/splitterSizes")
        if isinstance(splitter_sizes, list):
            self._splitter.setSizes([int(s) for s in splitter_sizes])

    def _save_geometry(self) -> None:
        settings = QSettings()
        settings.setValue("window/geometry", self.saveGeometry())
        settings.setValue("window/state", self.saveState())
        if hasattr(self, "_splitter"):
            settings.setValue("window/splitterSizes", self._splitter.sizes())

    def closeEvent(self, event) -> None:
        self._save_geometry()
        super().closeEvent(event)

    def _on_standard_changed(self) -> None:
        preferred = self._voltage_combo.currentData()
        with self._signals_blocked():
            self._reload_voltages(float(preferred) if preferred is not None else None)
            self._sync_power_to_standard()
        self._recalculate()

    def _on_category_changed(self) -> None:
        current = self._awg_combo.currentData()
        with self._signals_blocked():
            self._reload_awg(str(current) if current is not None else None)
        self._recalculate()

    def _on_power_changed(self) -> None:
        standard = get_standard(str(self._standard_combo.currentData()))
        self._power_pinned_to_max = abs(self._power_spin.value() - standard.p_pd_max_w) < 0.001
        self._recalculate()

    def _sync_power_to_standard(self) -> None:
        standard = get_standard(str(self._standard_combo.currentData()))
        self._power_spin.setMaximum(standard.p_pd_max_w)
        if self._power_pinned_to_max:
            self._power_spin.setValue(standard.p_pd_max_w)
        elif self._power_spin.value() > standard.p_pd_max_w + 1e-9:
            self._power_spin.setValue(standard.p_pd_max_w)

    def _reload_voltages(self, preferred: float | None) -> None:
        standard = get_standard(str(self._standard_combo.currentData()))
        self._voltage_combo.clear()
        for voltage in selectable_pse_voltages(standard):
            self._voltage_combo.addItem(_voltage_label(standard, voltage), voltage)
        target = standard.v_pse_min if preferred is None else preferred
        index = 0
        for row in range(self._voltage_combo.count()):
            if math.isclose(float(self._voltage_combo.itemData(row)), target, abs_tol=1e-6):
                index = row
                break
        self._voltage_combo.setCurrentIndex(index)

    def _reload_awg(self, preferred: str | None) -> None:
        category_id = str(self._category_combo.currentData())
        category = next(item for item in CATEGORIES if item.id == category_id)
        self._awg_combo.clear()
        for awg in category.allowed_awg:
            self._awg_combo.addItem(f"{awg} AWG", awg)
        target = preferred if preferred in category.allowed_awg else category.typical_awg
        _select(self._awg_combo, target)

    def _recalculate(self) -> None:
        try:
            report = build_report(self._selected_input())
        except ValueError as exc:
            self._report = None
            self._recommendation_label.setText(str(exc))
            self._paint_recommendation("bad")
            return
        self._report = report
        self._fill_summary(report)
        self._fill_table(report)
        self._plot.update_chart(
            report.sweep,
            length_m=float(self._length_spin.value()),
            v_pd_min=report.result.standard.v_pd_min,
            max_working_length_m=report.max_working_length_m,
            theme=self._theme,
        )
        self._recommendation_label.setText(report.recommendation)
        kind = "ok" if report.result.works and not report.result.length_exceeds_channel else "warn"
        if not report.result.works:
            kind = "bad"
        self._paint_recommendation(kind)
        self._paint_hints(report)

    def _selected_input(self) -> CalcInput:
        return CalcInput(
            standard_id=str(self._standard_combo.currentData()),
            v_pse=float(self._voltage_combo.currentData()),
            p_pd=float(self._power_spin.value()),
            length_m=float(self._length_spin.value()),
            category_id=str(self._category_combo.currentData()),
            awg=str(self._awg_combo.currentData()),
            material_id=str(self._material_combo.currentData()),
        )

    def _fill_summary(self, report: Report) -> None:
        result = report.result
        material = "медь" if result.material_id == "Cu" else "CCA"
        self._summary.setText(
            f"{result.standard.short_name} · "
            f"{format_number(self._selected_input().v_pse, 0)} В · "
            f"{format_power(self._selected_input().p_pd)} Вт · "
            f"{self._length_spin.value()} м · "
            f"{result.category_name} · {result.awg} AWG · {material}"
        )

    def _fill_table(self, report: Report) -> None:
        result = report.result
        values = {
            "Сопротивление жилы, Ом": format_number(result.r_wire_ohm, 4),
            "Сопротивление петли, Ом": format_number(result.r_loop_ohm, 4),
            "Ток линии": _format_current(result.current_a),
            "Ток на пару": _format_current(result.current_per_pair_a),
            "Падение напряжения, В": _format_optional(result.delta_u_v, 2),
            "Падение напряжения, %": _format_optional(result.delta_u_percent, 1),
            "Напряжение на PD, В": _format_optional(result.v_pd, 2),
            "Потери в кабеле, Вт": _format_optional(result.p_loss_w, 2),
            "Мощность на выходе PSE, Вт": _format_optional(result.p_pse_w, 2),
            "Вердикт": "Работает" if result.works else "Не работает",
            "Пояснение": _explanation(report),
        }
        for row, name in enumerate(_ROWS):
            value_item = self._table.item(row, 1)
            name_item = self._table.item(row, 0)
            assert value_item is not None and name_item is not None
            value_item.setText(values[name])
            role = "normal"
            if name == "Вердикт":
                role = "success" if result.works else "danger"
            align = Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter
            if name == "Пояснение":
                align = Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop
            value_item.setTextAlignment(align)
            name_item.setTextAlignment(align)
            self._paint_item(name_item, "normal")
            self._paint_item(value_item, role)
        self._fit_table()

    def _fit_table(self) -> None:
        if self._fitting_table:
            return
        self._fitting_table = True
        try:
            self._fit_table_rows()
        finally:
            self._fitting_table = False

    def _fit_table_rows(self) -> None:
        metrics = QFontMetrics(self._table.font())
        width = max(self._table.columnWidth(1), 280)
        for row, name in enumerate(_ROWS):
            item = self._table.item(row, 1)
            text = item.text() if item is not None else ""
            if name == "Пояснение":
                rect = metrics.boundingRect(
                    0,
                    0,
                    width - 16,
                    1000,
                    int(Qt.TextFlag.TextWordWrap),
                    text,
                )
                self._table.setRowHeight(row, max(28, min(rect.height() + 12, 56)))
            else:
                self._table.setRowHeight(row, 26)
        height = self._table.horizontalHeader().height() + 2 * self._table.frameWidth() + 8
        for row in range(self._table.rowCount()):
            height += self._table.rowHeight(row)
        if self._table.height() != height:
            self._table.setFixedHeight(height)

    def _paint_item(self, item: QTableWidgetItem, role: str) -> None:
        theme = self._theme
        if role == "success":
            background, foreground, bold = theme.success_bg, theme.success, True
        elif role == "danger":
            background, foreground, bold = theme.danger_bg, theme.danger, True
        else:
            background, foreground, bold = theme.card_bg, theme.text, False
        item.setBackground(QBrush(QColor(background)))
        item.setForeground(QBrush(QColor(foreground)))
        font = item.font()
        font.setBold(bold)
        item.setFont(font)

    def _paint_hints(self, report: Report) -> None:
        theme = self._theme
        if self._length_spin.value() > 100:
            self._length_hint.setText("Длина больше 100 м — выше нормы канала.")
            length_color = theme.warning
        else:
            self._length_hint.setText("Норма канала структурированной кабельной системы — 100 м.")
            length_color = theme.text_muted
        self._length_hint.setStyleSheet(f"color: {length_color}; background: transparent;")
        muted = f"color: {theme.text_muted}; background: transparent;"
        self._standard_hint.setStyleSheet(muted)
        self._resistance_hint.setStyleSheet(muted)
        self._auto_note.setStyleSheet(muted)
        self._summary.setStyleSheet(muted)
        standard = report.result.standard
        self._standard_hint.setText(
            f"PSE {format_number(standard.v_pse_min, 0)}–{format_number(standard.v_pse_max, 0)} В, "
            f"до {format_power(standard.p_pse_max_w)} Вт на PSE и "
            f"{format_power(standard.p_pd_max_w)} Вт на PD, минимум на PD "
            f"{format_number(standard.v_pd_min, 1)} В, {standard.pairs} пары, "
            f"ток на пару до {format_number(standard.i_pair_max_a, 3)} А."
        )
        self._resistance_hint.setText(
            "Удельное сопротивление одной жилы при 20 °C: "
            f"{format_number(report.result.r_specific_ohm_per_km, 2)} Ом/км."
        )

    def _paint_recommendation(self, kind: str) -> None:
        theme = self._theme
        if kind == "ok":
            border = theme.success
        elif kind == "warn":
            border = theme.warning
        else:
            border = theme.danger
        self._recommendation_frame().setStyleSheet(
            f"""
            QFrame#recommendationFrame {{
                background: {theme.recommendation_bg};
                border: 1px solid {theme.border};
                border-left: 4px solid {border};
                border-radius: 10px;
            }}
            QLabel {{
                background: transparent;
                color: {theme.text};
            }}
            QLabel#recommendationTitle {{
                color: {border};
                font-weight: 600;
            }}
            """
        )

    def _recommendation_frame(self) -> QFrame:
        frame = self.findChild(QFrame, "recommendationFrame")
        if frame is None:
            raise RuntimeError("Блок рекомендации не собран")
        return frame

    def _paint_chrome(self) -> None:
        theme = self._theme
        title = f"color: {theme.text}; background: transparent; font-size: 18px; font-weight: 600;"
        self._side_title.setStyleSheet(title)
        self._result_title.setStyleSheet(title)
        self._side_subtitle.setStyleSheet(f"color: {theme.text_muted}; background: transparent;")

    def _set_theme(self, name: str) -> None:
        self._theme = theme_by_name(name)
        app = QApplication.instance()
        if isinstance(app, QApplication):
            apply_theme(app, self._theme)
        QSettings().setValue("ui/theme", self._theme.name)
        self._sync_theme_checks()
        self._theme_action.setChecked(self._theme.name == "dark")
        self._theme_action.setText("Светлая тема" if self._theme.name == "dark" else "Тёмная тема")
        self._paint_chrome()
        if self._report is not None:
            self._fill_table(self._report)
            self._plot.update_chart(
                self._report.sweep,
                length_m=float(self._length_spin.value()),
                v_pd_min=self._report.result.standard.v_pd_min,
                max_working_length_m=self._report.max_working_length_m,
                theme=self._theme,
            )
            kind = "ok" if self._report.result.works and not self._report.result.length_exceeds_channel else "warn"
            if not self._report.result.works:
                kind = "bad"
            self._paint_recommendation(kind)
            self._paint_hints(self._report)
        if self._help_dialog is not None:
            self._help_dialog.apply_theme(self._theme)

    def _sync_theme_checks(self) -> None:
        self._action_light.blockSignals(True)
        self._action_dark.blockSignals(True)
        self._action_light.setChecked(self._theme.name == "light")
        self._action_dark.setChecked(self._theme.name == "dark")
        self._action_light.blockSignals(False)
        self._action_dark.blockSignals(False)
        if hasattr(self, "_theme_action"):
            self._theme_action.blockSignals(True)
            self._theme_action.setChecked(self._theme.name == "dark")
            self._theme_action.setText("Светлая тема" if self._theme.name == "dark" else "Тёмная тема")
            self._theme_action.blockSignals(False)

    def _reset(self) -> None:
        self.apply_input(default_input())

    def _open_help(self) -> None:
        if self._help_dialog is None:
            self._help_dialog = HelpDialog(self)
        self._help_dialog.apply_theme(self._theme)
        self._help_dialog.show()
        self._help_dialog.raise_()
        self._help_dialog.activateWindow()

    def _open_about(self) -> None:
        QMessageBox.about(self, "О программе", about_text())

    def resizeEvent(self, event: QResizeEvent) -> None:
        super().resizeEvent(event)
        if self._report is not None:
            self._fit_table()

    @contextmanager
    def _signals_blocked(self) -> Iterator[None]:
        widgets = (
            self._standard_combo,
            self._voltage_combo,
            self._power_spin,
            self._length_spin,
            self._category_combo,
            self._awg_combo,
            self._material_combo,
        )
        for widget in widgets:
            widget.blockSignals(True)
        try:
            yield
        finally:
            for widget in widgets:
                widget.blockSignals(False)


def _stored_theme_name() -> str:
    value = QSettings().value("ui/theme", "light")
    return str(value) if value is not None else "light"


def _select(combo: QComboBox, data: object) -> None:
    index = combo.findData(data)
    combo.setCurrentIndex(0 if index < 0 else index)


def _voltage_label(standard, voltage: float) -> str:
    text = f"{voltage:.0f} В"
    marks: list[str] = []
    if math.isclose(voltage, standard.v_pse_min, abs_tol=1e-9):
        marks.append("минимум")
    if math.isclose(voltage, standard.v_pse_max, abs_tol=1e-9):
        marks.append("максимум")
    if marks:
        text += " · " + " и ".join(marks)
    return text


def _format_optional(value: float | None, digits: int) -> str:
    if value is None:
        return "—"
    return format_number(value, digits)


def _format_current(value: float | None) -> str:
    if value is None:
        return "—"
    return f"{format_number(value, 3)} А ({format_number(value * 1000.0, 0)} мА)"


def _explanation(report: Report) -> str:
    return explanation(report.result)
