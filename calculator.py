"""Расчёт питания PoE при постоянной мощности PD.

Модуль не знает про окна и виджеты. На входе — выбранные параметры,
на выходе — числа, вердикт и текст рекомендации.

Модель петли
------------
Rж — сопротивление одной жилы длины L.

Две пары (802.3af / 802.3at): в каждом направлении две жилы параллельно,
прямая и обратная ветви одинаковы.

    Rпетли = Rж / 2 + Rж / 2 = Rж

Четыре пары (802.3bt Type 3 и Type 4 в этой программе): в каждом
направлении четыре жилы.

    Rпетли = Rж / 4 + Rж / 4 = Rж / 2

Ток на пару — ток одной парсет, его и сравниваем с I_cable.
При двух парах весь ток линии идёт по одной паре туда и по одной
обратно, поэтому ток на пару равен току линии. При четырёх парах
ток делится поровну между двумя парсет. Небаланс стандарт учитывает
отдельно; здесь пары считаются симметричными.

Нагрузка PD
-----------
PD держит постоянную мощность, поэтому ток зависит от напряжения
на его входе:

    Vpse = Vpd + I · Rпетли
    Ppd = Vpd · I

Отсюда квадратное уравнение. Берётся больший корень: меньший —
неустойчивая точка с тем же мощностью и большим током. Если
дискриминант отрицательный, такого режима нет.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, replace

from data import (
    AWG_THIN_TO_THICK,
    CATEGORIES,
    CHANNEL_LENGTH_LIMIT_M,
    LENGTH_MAX_M,
    P_PD_MIN_W,
    PoeStandard,
    format_number,
    get_category,
    get_material,
    get_standard,
    selectable_pse_voltages,
    specific_resistance_ohm_per_km,
)


@dataclass(frozen=True, slots=True)
class CalcInput:
    """Полный набор исходных данных одного расчёта."""

    standard_id: str
    v_pse: float
    p_pd: float
    length_m: float
    category_id: str
    awg: str
    material_id: str


@dataclass(frozen=True, slots=True)
class CalcResult:
    """Электрический результат и проверка пределов стандарта."""

    standard: PoeStandard
    category_name: str
    awg: str
    material_id: str
    material_name: str
    r_specific_ohm_per_km: float
    r_wire_ohm: float
    r_loop_ohm: float
    pairs: int
    discriminant: float
    feasible: bool
    v_pd: float | None
    current_a: float | None
    current_per_pair_a: float | None
    delta_u_v: float | None
    delta_u_percent: float | None
    p_loss_w: float | None
    p_pse_w: float | None
    voltage_ok: bool
    power_ok: bool
    current_ok: bool
    works: bool
    reasons: tuple[str, ...]
    length_exceeds_channel: bool


@dataclass(frozen=True, slots=True)
class SweepPoint:
    length_m: float
    v_pd: float | None
    delta_u_v: float | None
    feasible: bool
    works: bool


@dataclass(frozen=True, slots=True)
class Report:
    """Всё, что окну нужно показать после одного изменения параметров."""

    result: CalcResult
    sweep: tuple[SweepPoint, ...]
    # Наибольшая длина, на которой вердикт ещё «работает».
    # None — не работает даже при нулевой длине. 150 — работает до конца шкалы.
    max_working_length_m: float | None
    recommendation: str


def default_input() -> CalcInput:
    """Стартовая точка: PoE+, минимум напряжения, полная мощность, 100 м, Cat5e."""

    standard = get_standard("802.3at")
    category = get_category("cat5e")
    return CalcInput(
        standard_id=standard.id,
        v_pse=standard.v_pse_min,
        p_pd=standard.p_pd_max_w,
        length_m=100.0,
        category_id=category.id,
        awg=category.typical_awg,
        material_id="Cu",
    )


def conductor_resistance_ohm(r_per_km: float, length_m: float) -> float:
    """Rж = r · L / 1000."""

    return r_per_km * length_m / 1000.0


def loop_resistance_ohm(r_wire_ohm: float, pairs: int) -> float:
    """Сопротивление петли питания для 2 или 4 пар."""

    if pairs == 2:
        return r_wire_ohm
    if pairs == 4:
        return r_wire_ohm / 2.0
    raise ValueError("Модель петли задана только для 2 или 4 пар")


def solve_pd_voltage(
    v_pse: float,
    r_loop_ohm: float,
    p_pd: float,
) -> tuple[float | None, float]:
    """Больший корень уравнения постоянной мощности и сам дискриминант.

    Возвращает (Vpd, D). Vpd равен None, если D < 0 и режима нет.
    """

    discriminant = v_pse * v_pse - 4.0 * r_loop_ohm * p_pd
    # На самой границе float иногда даёт −1e−12 вместо нуля.
    if discriminant < 0.0:
        if discriminant > -1e-8:
            discriminant = 0.0
        else:
            return None, discriminant
    v_pd = (v_pse + math.sqrt(discriminant)) / 2.0
    return v_pd, discriminant


def calculate(inp: CalcInput) -> CalcResult:
    """Один режим: сопротивления, точка питания и вердикт стандарта."""

    standard = get_standard(inp.standard_id)
    category = get_category(inp.category_id)
    material = get_material(inp.material_id)
    _validate(inp, standard, category.allowed_awg)

    r_specific = specific_resistance_ohm_per_km(inp.awg, inp.material_id)
    r_wire = conductor_resistance_ohm(r_specific, inp.length_m)
    r_loop = loop_resistance_ohm(r_wire, standard.pairs)
    v_pd, discriminant = solve_pd_voltage(inp.v_pse, r_loop, inp.p_pd)
    too_long = inp.length_m > CHANNEL_LENGTH_LIMIT_M + 1e-9

    if v_pd is None:
        return CalcResult(
            standard=standard,
            category_name=category.name,
            awg=inp.awg,
            material_id=material.id,
            material_name=material.name,
            r_specific_ohm_per_km=r_specific,
            r_wire_ohm=r_wire,
            r_loop_ohm=r_loop,
            pairs=standard.pairs,
            discriminant=discriminant,
            feasible=False,
            v_pd=None,
            current_a=None,
            current_per_pair_a=None,
            delta_u_v=None,
            delta_u_percent=None,
            p_loss_w=None,
            p_pse_w=None,
            voltage_ok=False,
            power_ok=False,
            current_ok=False,
            works=False,
            reasons=(
                "Питание невозможно: дискриминант меньше нуля, "
                "источник не может отдать заданную мощность через такое сопротивление.",
            ),
            length_exceeds_channel=too_long,
        )

    current = inp.p_pd / v_pd
    current_per_pair = current if standard.pairs == 2 else current / 2.0
    delta_u = current * r_loop
    p_loss = current * current * r_loop
    p_pse = inp.p_pd + p_loss

    voltage_ok = v_pd + 1e-6 >= standard.v_pd_min
    power_ok = p_pse <= standard.p_pse_max_w + 1e-6
    current_ok = current_per_pair <= standard.i_pair_max_a + 1e-9
    reasons: list[str] = []
    if not voltage_ok:
        reasons.append(
            "Напряжение на PD "
            f"{format_number(v_pd, 2)} В ниже минимума стандарта "
            f"{format_number(standard.v_pd_min, 1)} В."
        )
    if not power_ok:
        reasons.append(
            "Мощность на выходе PSE "
            f"{format_number(p_pse, 2)} Вт превышает допустимые "
            f"{format_number(standard.p_pse_max_w, 1)} Вт."
        )
    if not current_ok:
        reasons.append(
            "Ток на пару "
            f"{format_number(current_per_pair, 3)} А превышает допустимые "
            f"{format_number(standard.i_pair_max_a, 3)} А."
        )

    return CalcResult(
        standard=standard,
        category_name=category.name,
        awg=inp.awg,
        material_id=material.id,
        material_name=material.name,
        r_specific_ohm_per_km=r_specific,
        r_wire_ohm=r_wire,
        r_loop_ohm=r_loop,
        pairs=standard.pairs,
        discriminant=discriminant,
        feasible=True,
        v_pd=v_pd,
        current_a=current,
        current_per_pair_a=current_per_pair,
        delta_u_v=delta_u,
        delta_u_percent=delta_u / inp.v_pse * 100.0,
        p_loss_w=p_loss,
        p_pse_w=p_pse,
        voltage_ok=voltage_ok,
        power_ok=power_ok,
        current_ok=current_ok,
        works=not reasons,
        reasons=tuple(reasons),
        length_exceeds_channel=too_long,
    )


def sweep_length(inp: CalcInput) -> tuple[SweepPoint, ...]:
    """Кривые от 0 до 150 м с шагом 1 м для графика."""

    points: list[SweepPoint] = []
    for length in range(LENGTH_MAX_M + 1):
        result = calculate(replace(inp, length_m=float(length)))
        points.append(
            SweepPoint(
                length_m=float(length),
                v_pd=result.v_pd,
                delta_u_v=result.delta_u_v,
                feasible=result.feasible,
                works=result.works,
            )
        )
    return tuple(points)


def max_working_length(inp: CalcInput) -> float | None:
    """Максимальная длина, на которой вердикт ещё положительный.

    С ростом длины растёт только сопротивление. Напряжение на PD падает,
    ток и мощность PSE растут, дискриминант уменьшается. Ограничения
    монотонны, поэтому достаточно двоичного поиска.
    """

    if not calculate(replace(inp, length_m=0.0)).works:
        return None
    if calculate(replace(inp, length_m=float(LENGTH_MAX_M))).works:
        return float(LENGTH_MAX_M)

    low = 0.0
    high = float(LENGTH_MAX_M)
    for _ in range(50):
        mid = (low + high) / 2.0
        if calculate(replace(inp, length_m=mid)).works:
            low = mid
        else:
            high = mid
    return low


def explanation(result: CalcResult) -> str:
    """Короткая строка для таблицы: запас либо причины отказа."""

    if result.works:
        assert result.v_pd is not None
        margin = result.v_pd - result.standard.v_pd_min
        return (
            f"Запас по напряжению {format_number(margin, 1)} В. "
            "Ток и мощность PSE в пределах стандарта."
        )
    return " ".join(result.reasons)


def build_report(inp: CalcInput) -> Report:
    """Результат, кривые, предельная длина и рекомендация одним вызовом."""

    result = calculate(inp)
    farthest = max_working_length(inp)
    text = build_recommendation(inp, result, farthest)
    return Report(
        result=result,
        sweep=sweep_length(inp),
        max_working_length_m=farthest,
        recommendation=text,
    )


def build_recommendation(
    inp: CalcInput,
    result: CalcResult,
    max_working_length_m: float | None,
) -> str:
    """Два или три предложения по правилам, без участия интерфейса."""

    if result.works:
        return _recommendation_when_works(inp, result)
    return _recommendation_when_fails(inp, result, max_working_length_m)


def _validate(inp: CalcInput, standard: PoeStandard, allowed_awg: tuple[str, ...]) -> None:
    if inp.awg not in allowed_awg:
        raise ValueError(
            f"Сечение {inp.awg} AWG не входит в типовой ряд выбранной категории"
        )
    allowed_voltages = selectable_pse_voltages(standard)
    if not any(math.isclose(inp.v_pse, voltage, abs_tol=1e-6) for voltage in allowed_voltages):
        raise ValueError("Напряжение PSE вне допустимого диапазона стандарта")
    if inp.p_pd < P_PD_MIN_W - 1e-9 or inp.p_pd > standard.p_pd_max_w + 1e-6:
        raise ValueError("Мощность PD вне диапазона выбранного стандарта")
    if inp.length_m < -1e-9 or inp.length_m > LENGTH_MAX_M + 1e-6:
        raise ValueError(
            f"Длина должна быть от 0 до {LENGTH_MAX_M} м "
            "(0 м нужен кривой графика, в окне минимум 1 м)"
        )
    if standard.pairs not in (2, 4):
        raise ValueError("Модель петли задана только для 2 или 4 пар")


def _recommendation_when_works(inp: CalcInput, result: CalcResult) -> str:
    assert result.v_pd is not None
    assert result.p_loss_w is not None
    assert result.p_pse_w is not None
    assert result.current_per_pair_a is not None

    margin = result.v_pd - result.standard.v_pd_min
    margin_text = format_number(margin, 1)
    if margin >= 3.0:
        lead = f"Запас по напряжению {margin_text} В, конфигурация надёжна."
    elif margin >= 1.0:
        lead = f"Запас по напряжению {margin_text} В — питание работает, запас умеренный."
    else:
        lead = (
            f"Запас по напряжению всего {margin_text} В: "
            "линия на грани минимума стандарта."
        )

    if result.length_exceeds_channel:
        second = (
            "Длина больше 100 м — выше нормы канала, а контакты, патч-корды "
            "и нагрев в модель не входят, так что в проект её лучше не закладывать."
        )
    else:
        second = (
            f"Потери в кабеле {format_number(result.p_loss_w, 2)} Вт, "
            f"на выходе PSE {format_number(result.p_pse_w, 2)} Вт."
        )

    extra = _comfort_note(inp, result, margin)
    return _join_sentences([lead, second, extra])


def _comfort_note(inp: CalcInput, result: CalcResult, margin: float) -> str | None:
    assert result.current_per_pair_a is not None
    if inp.material_id == "CCA" and margin < 8.0:
        return (
            "Запас есть, но омеднённый алюминий увеличивает сопротивление в 1,6 раза: "
            f"медь {inp.awg} AWG будет надёжнее."
        )
    ratio = result.current_per_pair_a / result.standard.i_pair_max_a
    # 85 % на короткой линии — обычный режим полной мощности при минимуме PSE,
    # а не признак беды. Предупреждаем, когда ток уже почти упёрся в предел.
    if ratio >= 0.92:
        return (
            f"Ток на пару уже {format_number(ratio * 100.0, 0)} % допустимого, "
            "заметного запаса по току нет."
        )
    if margin < 2.0:
        return (
            "При нагреве сопротивление меди растёт примерно на 0,4 % на градус — "
            "такой запас легко съедается температурой и контактами."
        )
    return None


def _recommendation_when_fails(
    inp: CalcInput,
    result: CalcResult,
    max_working_length_m: float | None,
) -> str:
    lead = _failure_lead(result)
    reach = _reach_sentence(inp, max_working_length_m)
    advice = _first_working_advice(inp)
    if advice is None and max_working_length_m is not None:
        if max_working_length_m + 0.05 < inp.length_m:
            meters = max(1, math.floor(max_working_length_m))
            advice = f"Если кабель заменить нельзя, укоротите линию до {meters} м."
    return _join_sentences([lead, reach, advice])


def _failure_lead(result: CalcResult) -> str:
    if not result.feasible:
        return (
            "Питание невозможно: сопротивление петли слишком велико "
            "для заданной мощности."
        )

    details: list[str] = []
    if not result.voltage_ok and result.v_pd is not None:
        details.append(
            f"напряжение на PD {format_number(result.v_pd, 2)} В "
            f"ниже минимума {format_number(result.standard.v_pd_min, 1)} В"
        )
    if not result.power_ok and result.p_pse_w is not None:
        details.append(
            f"мощность PSE {format_number(result.p_pse_w, 2)} Вт "
            f"выше допустимых {format_number(result.standard.p_pse_max_w, 1)} Вт"
        )
    if not result.current_ok and result.current_per_pair_a is not None:
        details.append(
            f"ток на пару {format_number(result.current_per_pair_a, 3)} А "
            f"выше допустимых {format_number(result.standard.i_pair_max_a, 3)} А"
        )
    if not details:
        return "Не работает при таких параметрах."
    body = "; ".join(details)
    return f"Не работает: {body}."


def _reach_sentence(inp: CalcInput, max_working_length_m: float | None) -> str:
    if max_working_length_m is None:
        return (
            "Условия стандарта не выполняются даже на нулевой длине — "
            "для этого напряжения мощность PD слишком велика."
        )
    reach = f"примерно до {format_number(_display_length(max_working_length_m), 1)} м"
    if inp.length_m > CHANNEL_LENGTH_LIMIT_M:
        return (
            f"В этой конфигурации питание сохраняется {reach}, "
            "при этом длина уже выше предела канала 100 м."
        )
    return f"В этой конфигурации питание сохраняется {reach}."


def _first_working_advice(inp: CalcInput) -> str | None:
    """Первая соседняя конфигурация, которая уже проходит по стандарту."""

    for text, candidate in _advice_trials(inp):
        try:
            if calculate(candidate).works:
                return text
        except ValueError:
            continue
    return None


def _advice_trials(inp: CalcInput) -> tuple[tuple[str, CalcInput], ...]:
    trials: list[tuple[str, CalcInput]] = []
    standard = get_standard(inp.standard_id)

    if inp.material_id == "CCA":
        trials.append(
            (
                f"CCA при такой длине не подходит, возьмите медь {inp.awg} AWG.",
                replace(inp, material_id="Cu"),
            )
        )

    trials.extend(_thicker_cable_trials(inp))

    if inp.v_pse < standard.v_pse_max - 0.1:
        trials.append(
            (
                f"Поднимите напряжение PSE до {format_number(standard.v_pse_max, 0)} В.",
                replace(inp, v_pse=standard.v_pse_max),
            )
        )

    for factor in (0.8, 0.6, 0.4):
        reduced = round(max(P_PD_MIN_W, inp.p_pd * factor), 1)
        if reduced < inp.p_pd - 0.05:
            trials.append(
                (
                    f"Снизьте мощность PD до {format_number(reduced, 1)} Вт.",
                    replace(inp, p_pd=reduced),
                )
            )
    return tuple(trials)


def _thicker_cable_trials(inp: CalcInput) -> list[tuple[str, CalcInput]]:
    index = AWG_THIN_TO_THICK.index(inp.awg)
    thicker = AWG_THIN_TO_THICK[index + 1 :]
    # Для CCA сразу советуем медь: оставлять алюминий и лишь утолщать жилу незачем.
    material_id = "Cu"
    trials: list[tuple[str, CalcInput]] = []
    for awg in thicker:
        categories = [item for item in CATEGORIES if awg in item.allowed_awg]
        categories.sort(key=lambda item: 0 if item.id == inp.category_id else 1)
        if not categories:
            continue
        category = categories[0]
        same_category = category.id == inp.category_id
        if inp.material_id == "CCA":
            where = category.name if not same_category else "той же категории"
            text = f"Возьмите медь {awg} AWG ({where})."
        elif same_category:
            text = f"Возьмите более толстую жилу {awg} AWG той же категории."
        else:
            text = f"Возьмите {category.name} с жилой {awg} AWG: у текущей категории её нет."
        trials.append(
            (
                text,
                replace(
                    inp,
                    category_id=category.id,
                    awg=awg,
                    material_id=material_id,
                ),
            )
        )
    return trials


def _display_length(length_m: float) -> float:
    """Округление длины вниз до 0,1 м, чтобы не пообещать нерабочую точку."""

    if length_m >= LENGTH_MAX_M - 1e-6:
        return float(LENGTH_MAX_M)
    return math.floor(length_m * 10.0 + 1e-9) / 10.0


def _join_sentences(parts: list[str | None]) -> str:
    sentences: list[str] = []
    for part in parts:
        if not part:
            continue
        text = " ".join(part.split())
        if text[-1] not in ".!?":
            text += "."
        sentences.append(text)
        if len(sentences) == 3:
            break
    return " ".join(sentences)
