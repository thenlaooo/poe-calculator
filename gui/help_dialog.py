"""Справка и текст «О программе». Формулы и таблицы рисуются внутри окна."""

from __future__ import annotations

import html

from PySide6.QtWidgets import QDialog, QPushButton, QTextBrowser, QVBoxLayout, QWidget

from calculator import calculate, default_input
from data import (
    APP_TITLE,
    APP_VERSION,
    CATEGORIES,
    CHANNEL_LENGTH_LIMIT_M,
    DISCIPLINE,
    GAUGES,
    REFERENCE_TEMPERATURE_C,
    STANDARDS,
    format_number,
    format_power,
    get_material,
)
from gui.themes import Theme


def about_text() -> str:
    return (
        f"{APP_TITLE}\n"
        f"Версия {APP_VERSION}\n\n"
        f"Учебная программа по дисциплине «{DISCIPLINE}».\n\n"
        "Считает падение напряжения и проверяет, дойдёт ли питание "
        "до PD при выбранном стандарте IEEE 802.3, длине и типе жилы.\n\n"
        f"Номинал жилы взят при {format_number(REFERENCE_TEMPERATURE_C, 0)} °C. "
        "Контакты, патч-корды, нагрев и небаланс пар в модель не входят, "
        "поэтому «работает» здесь не заменяет сертификацию канала.\n\n"
        "Интерфейс: PySide6. График: matplotlib. Расчёт отделён от окна."
    )


def build_help_html(theme: Theme) -> str:
    """Справка из тех же справочников, что и расчёт."""

    sample = calculate(default_input())
    return f"""
    <html><head><style>
    body {{
        color: {theme.text};
        background: {theme.card_bg};
        font-family: "Noto Sans", "Segoe UI", "DejaVu Sans", sans-serif;
        font-size: 14px;
        line-height: 1.45;
    }}
    h2 {{
        color: {theme.accent};
        font-size: 16px;
        margin-top: 18px;
        margin-bottom: 6px;
    }}
    p {{ margin: 6px 0; }}
    table {{
        border-collapse: collapse;
        margin: 8px 0 12px 0;
        width: 100%;
    }}
    th, td {{
        border: 1px solid {theme.border};
        padding: 4px 6px;
        text-align: left;
        vertical-align: top;
    }}
    th {{
        background: {theme.panel_bg};
        color: {theme.text};
    }}
    pre {{
        background: {theme.panel_bg};
        padding: 8px 10px;
        line-height: 1.4;
    }}
    </style></head><body>
    <h2>Назначение</h2>
    <p>Программа оценивает, хватит ли напряжения и бюджета мощности PSE,
    чтобы PD постоянной мощности получил питание по витой паре.
    Длина канала по стандарту СКС — {CHANNEL_LENGTH_LIMIT_M} м. Более длинную
    линию можно посчитать, но окно пометит её как выход за норму.</p>

    <h2>Методика</h2>
    <p>Берётся номинальное сопротивление одной сплошной жилы при
    {format_number(REFERENCE_TEMPERATURE_C, 0)} °C, не максимальное сопротивление по TIA-568.
    Для омеднённого алюминия оно умножается на
    {format_number(get_material("CCA").resistance_factor, 1)}.
    PD не является постоянным резистором: он держит заданную мощность,
    поэтому ток тем больше, чем ниже напряжение на его входе.</p>
    <p>Из двух корней квадратного уравнения используется больший.
    Меньший — неустойчивая точка с тем же потреблением и большим током.
    Отрицательный дискриминант означает, что такой мощности через
    эту петлю не передать вовсе.</p>
    <p>Ток сравнивается с пределом на пару (I<sub>cable</sub>).
    При двух парах весь ток идёт по одной паре туда и по одной обратно.
    При четырёх парах он делится поровну между двумя парсет;
    небаланс жил модель не учитывает.</p>

    <h2>Формулы</h2>
    <pre>Rж = r · L / 1000

2 пары:   Rпетли = Rж          (туда две жилы параллельно и обратно две)
4 пары:   Rпетли = Rж / 2      (туда четыре жилы и обратно четыре)

Vpd = (Vpse + √(Vpse² − 4 · Rпетли · Ppd)) / 2
I = Ppd / Vpd
ΔU = I · Rпетли
Pпотерь = I² · Rпетли
Ppse = Ppd + Pпотерь = Vpse · I</pre>
    <p>Питание считается возможным, только если дискриминант не отрицательный,
    Vpd не ниже минимума стандарта, мощность на выходе PSE не выше
    её предела и ток на пару не выше допустимого.</p>

    <h2>Стандарты PoE</h2>
    <p>Type 3 в этой программе — четырёхпарный класс 6. В самом IEEE 802.3
    младшие классы Type 3 могут питаться и по двум парам.</p>
    {_standards_table()}
    <p>Колонка «петля стандарта» — предел сопротивления одной парсет по IEEE.
    В расчёт она не подставляется. У четырёх пар две такие петли работают
    параллельно, поэтому бюджет эффективного сопротивления около 6,25 Ом.</p>

    <h2>Жилы при {format_number(REFERENCE_TEMPERATURE_C, 0)} °C</h2>
    {_gauge_table()}
    <p>Диаметр приведён для ориентира и в формулу не входит.
    TIA-568 для горизонтального кабеля Cat5e, Cat6 и Cat6a допускает
    сплошную жилу примерно 22–24 AWG. В списках окна оставлены типовые
    сочетания серийных кабелей, а не вся разрешённая вилка.</p>
    {_category_table()}

    <h2>Контрольный пример</h2>
    <p>Стартовые значения окна: {html.escape(sample.standard.title)},
    {format_number(default_input().v_pse, 0)} В,
    {format_power(default_input().p_pd)} Вт,
    {format_number(default_input().length_m, 0)} м,
    {html.escape(sample.category_name)},
    {html.escape(sample.awg)} AWG, медь.</p>
    <p>Rж = {format_number(sample.r_wire_ohm, 2)} Ом,
    Rпетли = {format_number(sample.r_loop_ohm, 2)} Ом,
    Vpd = {format_number(sample.v_pd or 0, 2)} В,
    ток = {format_number(sample.current_a or 0, 3)} А,
    ΔU = {format_number(sample.delta_u_v or 0, 2)} В
    ({format_number(sample.delta_u_percent or 0, 1)} %),
    потери = {format_number(sample.p_loss_w or 0, 2)} Вт,
    PSE = {format_number(sample.p_pse_w or 0, 2)} Вт.
    Вердикт: {"работает" if sample.works else "не работает"}.</p>

    <h2>Чего модель не учитывает</h2>
    <p>Сопротивление разъёмов и патч-кордов, рост сопротивления примерно
    на 0,4 % на каждый градус нагрева меди, небаланс тока между парами,
    падение в диодном мосте PD и ограничение температуры кабеля стандартом.
    Из-за этого номинальная медь на бумаге проходит дальше, чем реальный канал
    с тем же сечением. Сравнение с бюджетом 12,5 Ом или 20 Ом как раз
    показывает этот запас метода.</p>
    </body></html>
    """


class HelpDialog(QDialog):
    """Немодальное окно справки: его можно держать рядом с расчётом."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("helpDialog")
        self.setWindowTitle("Справка")
        self.resize(760, 640)
        self._browser = QTextBrowser()
        self._browser.setOpenExternalLinks(False)
        self._browser.setOpenLinks(False)
        close = QPushButton("Закрыть")
        close.clicked.connect(self.close)
        layout = QVBoxLayout(self)
        layout.addWidget(self._browser)
        layout.addWidget(close)

    def apply_theme(self, theme: Theme) -> None:
        self.setStyleSheet(
            f"QDialog {{ background: {theme.window_bg}; }}"
            f"QTextBrowser {{ background: {theme.card_bg}; color: {theme.text}; border: none; }}"
        )
        self._browser.setHtml(build_help_html(theme))


def _standards_table() -> str:
    rows = [
        "<tr><th>Стандарт</th><th>PSE, В</th><th>PSE, Вт</th><th>PD, Вт</th>"
        "<th>Мин. PD, В</th><th>Пары</th><th>Ток пары, А</th><th>Петля стандарта, Ом</th></tr>"
    ]
    for item in STANDARDS:
        rows.append(
            "<tr>"
            f"<td>{html.escape(item.short_name)}</td>"
            f"<td>{format_number(item.v_pse_min, 0)}–{format_number(item.v_pse_max, 0)}</td>"
            f"<td>{format_power(item.p_pse_max_w)}</td>"
            f"<td>{format_power(item.p_pd_max_w)}</td>"
            f"<td>{format_number(item.v_pd_min, 1)}</td>"
            f"<td>{item.pairs}</td>"
            f"<td>{format_number(item.i_pair_max_a, 3)}</td>"
            f"<td>{format_number(item.r_pairset_max_ohm, 1)}</td>"
            "</tr>"
        )
    return "<table>" + "".join(rows) + "</table>"


def _gauge_table() -> str:
    factor = get_material("CCA").resistance_factor
    rows = [
        "<tr><th>Сечение</th><th>Диаметр, мм</th><th>Медь, Ом/км</th><th>CCA, Ом/км</th></tr>"
    ]
    for gauge in GAUGES:
        rows.append(
            "<tr>"
            f"<td>{html.escape(gauge.awg)} AWG</td>"
            f"<td>{format_number(gauge.diameter_mm, 3)}</td>"
            f"<td>{format_number(gauge.resistance_cu_ohm_per_km, 1)}</td>"
            f"<td>{format_number(gauge.resistance_cu_ohm_per_km * factor, 2)}</td>"
            "</tr>"
        )
    return "<table>" + "".join(rows) + "</table>"


def _category_table() -> str:
    rows = ["<tr><th>Категория</th><th>Типовые сечения</th><th>Замечание</th></tr>"]
    for category in CATEGORIES:
        gauges = ", ".join(f"{awg} AWG" for awg in category.allowed_awg)
        rows.append(
            "<tr>"
            f"<td>{html.escape(category.name)}</td>"
            f"<td>{html.escape(gauges)}</td>"
            f"<td>{html.escape(category.note)}</td>"
            "</tr>"
        )
    return "<table>" + "".join(rows) + "</table>"
