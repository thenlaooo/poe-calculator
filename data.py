"""Справочные данные стандартов PoE и медных жил.

Все числа, которыми пользуется расчёт и справка, собраны здесь.
Источники, с которыми сверены значения:

* IEEE 802.3-2022, раздел 33 — Type 1 (802.3af) и Type 2 (802.3at):
  диапазон напряжения PSE, мощность PSE и PD, минимум напряжения на PD,
  ток пары, две пары.
* IEEE 802.3-2022, раздел 145 — Type 3 и Type 4 (802.3bt).
  Для Type 3 в программу заложен четырёхпарный класс 6 (60 Вт / 51 Вт,
  минимум PSE 50 В, минимум PD 42,5 В): так задано учебное задание.
  Сам стандарт для классов 1–4 допускает и двухпарный Type 3.
  Type 4 — четырёхпарный класс 8 (90 Вт / 71,3 Вт, минимум PSE 52 В,
  минимум PD 41,1 В).
* Предельный ток пары — I_cable стандарта: 0,350 А, 0,600 А, 0,600 А
  и 0,960 А. Для Type 4 рабочий ток при полной мощности ниже предела
  кабеля (около 0,865 А на пару при минимуме напряжения PSE).
* Удельное сопротивление одной сплошной медной жилы при 20 °C —
  номинал отожжённой меди по таблице AWG, не максимум TIA-568:
  24 AWG — 84,2 Ом/км (25,67 Ом/кфут), 23 AWG — 66,8 Ом/км
  (20,36 Ом/кфут), 22 AWG — 53,0 Ом/км (16,14 Ом/кфут ≈ 52,95,
  в расчёте округление условия задачи).
* Коэффициент 1,6 для CCA задан условием. У чистого алюминия
  сопротивление относительно меди того же порядка.

Сопротивление петли канала по IEEE (20 Ом и 12,5 Ом) в расчёт
не подставляется: оно приведено в справке, чтобы сравнивать модель
с бюджетом стандарта.
"""

from __future__ import annotations

from dataclasses import dataclass


APP_TITLE = "Калькулятор падения напряжения PoE"
APP_VERSION = "1.0"
DISCIPLINE = "Направляющие среды в телекоммуникациях"
ORGANIZATION = "NSTK"
APPLICATION_ID = "PoEVoltageDrop"

# Номинал жилы задан при этой температуре. Нагрева в модели нет.
REFERENCE_TEMPERATURE_C = 20.0

# Предел постоянного канала по TIA-568 / ISO/IEC 11801 и IEEE 802.3.
CHANNEL_LENGTH_LIMIT_M = 100
LENGTH_MIN_M = 1
LENGTH_MAX_M = 150
LENGTH_PLOT_MIN_M = 0

# Нижняя граница спинбокса мощности. Ноль не несёт смысла для PD.
P_PD_MIN_W = 0.1

# Типовые напряжения блоков питания PoE. Минимум стандарта добавляется
# отдельно, даже если его нет в этом ряду (44 В у 802.3af).
TYPICAL_PSE_VOLTAGES_V: tuple[float, ...] = (48.0, 50.0, 52.0, 54.0, 56.0, 57.0)

# От тонкой жилы к толстой. Меньший номер AWG — больше сечение.
AWG_THIN_TO_THICK: tuple[str, ...] = ("24", "23", "22")


@dataclass(frozen=True, slots=True)
class PoeStandard:
    """Один тип PoE так, как его считает эта учебная модель."""

    id: str
    title: str
    short_name: str
    v_pse_min: float
    v_pse_max: float
    p_pse_max_w: float
    p_pd_max_w: float
    v_pd_min: float
    pairs: int
    i_pair_max_a: float
    # Предел сопротивления одной парсет-петли по стандарту, только для справки.
    r_pairset_max_ohm: float
    note: str


@dataclass(frozen=True, slots=True)
class WireGauge:
    """Номинал сплошной медной жилы при 20 °C."""

    awg: str
    resistance_cu_ohm_per_km: float
    diameter_mm: float


@dataclass(frozen=True, slots=True)
class CableCategory:
    """Категория и сечения, которые реально встречаются в серийном кабеле.

    TIA-568 для горизонтального кабеля Cat5e/Cat6/Cat6a допускает
    сплошную жилу примерно 22–24 AWG. В списке оставлены типовые
    сочетания, а не вся разрешённая вилка: иначе выбор сечения
    не зависит от категории.
    """

    id: str
    name: str
    allowed_awg: tuple[str, ...]
    typical_awg: str
    note: str


@dataclass(frozen=True, slots=True)
class ConductorMaterial:
    id: str
    name: str
    # Множитель к удельному сопротивлению меди.
    resistance_factor: float


STANDARDS: tuple[PoeStandard, ...] = (
    PoeStandard(
        id="802.3af",
        title="IEEE 802.3af (Type 1, PoE)",
        short_name="802.3af Type 1",
        v_pse_min=44.0,
        v_pse_max=57.0,
        p_pse_max_w=15.4,
        p_pd_max_w=12.95,
        v_pd_min=37.0,
        pairs=2,
        i_pair_max_a=0.350,
        r_pairset_max_ohm=20.0,
        note="Две пары, классы 1–3. Бюджет канала в стандарте — до 20 Ом.",
    ),
    PoeStandard(
        id="802.3at",
        title="IEEE 802.3at (Type 2, PoE+)",
        short_name="802.3at Type 2",
        v_pse_min=50.0,
        v_pse_max=57.0,
        p_pse_max_w=30.0,
        p_pd_max_w=25.5,
        v_pd_min=42.5,
        pairs=2,
        i_pair_max_a=0.600,
        r_pairset_max_ohm=12.5,
        note="Две пары, класс 4. Бюджет петли канала — до 12,5 Ом.",
    ),
    PoeStandard(
        id="802.3bt-type3",
        title="IEEE 802.3bt (Type 3)",
        short_name="802.3bt Type 3",
        v_pse_min=50.0,
        v_pse_max=57.0,
        p_pse_max_w=60.0,
        p_pd_max_w=51.0,
        v_pd_min=42.5,
        pairs=4,
        i_pair_max_a=0.600,
        r_pairset_max_ohm=12.5,
        note=(
            "Четырёхпарный класс 6. В стандарте Type 3 для младших классов "
            "бывает и двухпарным; здесь считаются четыре пары."
        ),
    ),
    PoeStandard(
        id="802.3bt-type4",
        title="IEEE 802.3bt (Type 4)",
        short_name="802.3bt Type 4",
        v_pse_min=52.0,
        v_pse_max=57.0,
        p_pse_max_w=90.0,
        p_pd_max_w=71.3,
        v_pd_min=41.1,
        pairs=4,
        i_pair_max_a=0.960,
        r_pairset_max_ohm=12.5,
        note="Четырёхпарный класс 8. Ток пары ограничен 0,960 А.",
    ),
)


GAUGES: tuple[WireGauge, ...] = (
    WireGauge("24", 84.2, 0.511),
    WireGauge("23", 66.8, 0.573),
    WireGauge("22", 53.0, 0.644),
)


CATEGORIES: tuple[CableCategory, ...] = (
    CableCategory(
        id="cat5e",
        name="Cat5e",
        allowed_awg=("24",),
        typical_awg="24",
        note="Серийный горизонтальный кабель обычно 24 AWG.",
    ),
    CableCategory(
        id="cat6",
        name="Cat6",
        allowed_awg=("23", "24"),
        typical_awg="23",
        note="Чаще всего 23 AWG, встречается и 24 AWG.",
    ),
    CableCategory(
        id="cat6a",
        name="Cat6a",
        allowed_awg=("23", "22"),
        typical_awg="23",
        note="Обычно 23 AWG, у части экранированных кабелей 22 AWG.",
    ),
)


MATERIALS: tuple[ConductorMaterial, ...] = (
    ConductorMaterial("Cu", "Медь (Cu)", 1.0),
    ConductorMaterial("CCA", "CCA", 1.6),
)


def get_standard(standard_id: str) -> PoeStandard:
    for item in STANDARDS:
        if item.id == standard_id:
            return item
    raise ValueError(f"Неизвестный стандарт PoE: {standard_id}")


def get_gauge(awg: str) -> WireGauge:
    for item in GAUGES:
        if item.awg == awg:
            return item
    raise ValueError(f"Неизвестное сечение жилы: {awg} AWG")


def get_category(category_id: str) -> CableCategory:
    for item in CATEGORIES:
        if item.id == category_id:
            return item
    raise ValueError(f"Неизвестная категория кабеля: {category_id}")


def get_material(material_id: str) -> ConductorMaterial:
    for item in MATERIALS:
        if item.id == material_id:
            return item
    raise ValueError(f"Неизвестный материал жилы: {material_id}")


def selectable_pse_voltages(standard: PoeStandard) -> tuple[float, ...]:
    """Минимум и максимум стандарта плюс типовые значения внутри диапазона."""

    values = {standard.v_pse_min, standard.v_pse_max}
    for voltage in TYPICAL_PSE_VOLTAGES_V:
        if standard.v_pse_min <= voltage <= standard.v_pse_max:
            values.add(voltage)
    return tuple(sorted(values))


def specific_resistance_ohm_per_km(awg: str, material_id: str) -> float:
    """Удельное сопротивление одной жилы, Ом/км, при 20 °C."""

    gauge = get_gauge(awg)
    material = get_material(material_id)
    return gauge.resistance_cu_ohm_per_km * material.resistance_factor


def format_number(value: float, digits: int) -> str:
    """Число с десятичной запятой для русских подписей."""

    return f"{value:.{digits}f}".replace(".", ",")


def format_power(value: float) -> str:
    """Мощность без лишних нулей: 30, 25,5 или 12,95."""

    if abs(value - round(value)) < 1e-9:
        return format_number(value, 0)
    if abs(value * 10 - round(value * 10)) < 1e-6:
        return format_number(value, 1)
    return format_number(value, 2)
