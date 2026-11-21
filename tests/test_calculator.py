"""Проверки модели: 2 и 4 пары, CCA, невозможное питание, пределы стандарта."""

from __future__ import annotations

import math

import pytest
from dataclasses import replace

from calculator import (
    CalcInput,
    build_report,
    calculate,
    conductor_resistance_ohm,
    default_input,
    loop_resistance_ohm,
    max_working_length,
    solve_pd_voltage,
    sweep_length,
)
from data import (
    CATEGORIES,
    GAUGES,
    STANDARDS,
    get_standard,
    selectable_pse_voltages,
    specific_resistance_ohm_per_km,
)


def _case(**overrides: object) -> CalcInput:
    base = default_input()
    return replace(base, **overrides)


def test_reference_tables_match_assignment() -> None:
    by_id = {item.id: item for item in STANDARDS}
    af = by_id["802.3af"]
    at = by_id["802.3at"]
    bt3 = by_id["802.3bt-type3"]
    bt4 = by_id["802.3bt-type4"]

    assert (af.v_pse_min, af.v_pse_max, af.p_pse_max_w, af.p_pd_max_w) == (44.0, 57.0, 15.4, 12.95)
    assert af.v_pd_min == 37.0 and af.pairs == 2 and af.i_pair_max_a == 0.350

    assert (at.v_pse_min, at.v_pse_max, at.p_pse_max_w, at.p_pd_max_w) == (50.0, 57.0, 30.0, 25.5)
    assert at.v_pd_min == 42.5 and at.pairs == 2 and at.i_pair_max_a == 0.600

    assert (bt3.v_pse_min, bt3.v_pse_max, bt3.p_pse_max_w, bt3.p_pd_max_w) == (50.0, 57.0, 60.0, 51.0)
    assert bt3.v_pd_min == 42.5 and bt3.pairs == 4 and bt3.i_pair_max_a == 0.600

    assert (bt4.v_pse_min, bt4.v_pse_max, bt4.p_pse_max_w, bt4.p_pd_max_w) == (52.0, 57.0, 90.0, 71.3)
    assert bt4.v_pd_min == 41.1 and bt4.pairs == 4 and bt4.i_pair_max_a == 0.960

    resistance = {item.awg: item.resistance_cu_ohm_per_km for item in GAUGES}
    assert resistance == {"24": 84.2, "23": 66.8, "22": 53.0}
    assert specific_resistance_ohm_per_km("24", "CCA") == pytest.approx(84.2 * 1.6)


def test_voltage_lists_stay_inside_the_standard() -> None:
    af = selectable_pse_voltages(get_standard("802.3af"))
    at = selectable_pse_voltages(get_standard("802.3at"))
    bt4 = selectable_pse_voltages(get_standard("802.3bt-type4"))
    assert af[0] == 44.0 and 48.0 in af and af[-1] == 57.0
    assert 48.0 not in at and at[0] == 50.0
    assert 48.0 not in bt4 and 50.0 not in bt4 and bt4[0] == 52.0


def test_loop_resistance_two_and_four_pairs() -> None:
    r_wire = conductor_resistance_ohm(84.2, 100.0)
    assert r_wire == pytest.approx(8.42)
    assert loop_resistance_ohm(r_wire, 2) == pytest.approx(r_wire)
    assert loop_resistance_ohm(r_wire, 4) == pytest.approx(r_wire / 2.0)

    two = calculate(_case(standard_id="802.3at", length_m=100.0))
    four = calculate(_case(standard_id="802.3bt-type3", length_m=100.0, p_pd=51.0))
    assert two.pairs == 2 and four.pairs == 4
    assert two.r_wire_ohm == pytest.approx(8.42)
    assert two.r_loop_ohm == pytest.approx(8.42)
    assert four.r_loop_ohm == pytest.approx(4.21)


def test_cca_multiplies_wire_and_loop() -> None:
    copper = calculate(_case())
    cca = calculate(_case(material_id="CCA"))
    assert cca.r_specific_ohm_per_km == pytest.approx(copper.r_specific_ohm_per_km * 1.6)
    assert cca.r_wire_ohm == pytest.approx(copper.r_wire_ohm * 1.6)
    assert cca.r_loop_ohm == pytest.approx(copper.r_loop_ohm * 1.6)
    assert cca.works is False
    assert copper.works is True


def test_constant_power_solution_matches_quadratic() -> None:
    result = calculate(_case())
    assert result.feasible is True
    assert result.r_loop_ohm == pytest.approx(8.42, abs=1e-9)

    v_pd, discriminant = solve_pd_voltage(50.0, 8.42, 25.5)
    assert discriminant > 0
    assert v_pd == pytest.approx(result.v_pd)
    assert v_pd == pytest.approx(45.2556, abs=1e-3)
    # Больший корень, не неустойчивая точка ниже Vpse/2.
    assert v_pd > 25.0


@pytest.mark.parametrize(
    "inp",
    [
        _case(),
        _case(length_m=1.0),
        _case(standard_id="802.3bt-type3", p_pd=51.0, category_id="cat6", awg="23"),
        _case(standard_id="802.3bt-type4", v_pse=52.0, p_pd=71.3, length_m=1.0),
    ],
)
def test_power_balance_identities(inp: CalcInput) -> None:
    result = calculate(inp)
    assert result.feasible and result.v_pd is not None
    assert result.current_a == pytest.approx(inp.p_pd / result.v_pd)
    assert result.delta_u_v == pytest.approx(result.current_a * result.r_loop_ohm)
    assert result.v_pd + result.delta_u_v == pytest.approx(inp.v_pse, abs=1e-9)
    assert result.p_loss_w == pytest.approx(result.current_a**2 * result.r_loop_ohm)
    assert result.p_pse_w == pytest.approx(inp.p_pd + result.p_loss_w)
    assert result.p_pse_w == pytest.approx(inp.v_pse * result.current_a, abs=1e-6)
    if result.pairs == 4:
        assert result.current_per_pair_a == pytest.approx(result.current_a / 2.0)
    else:
        assert result.current_per_pair_a == pytest.approx(result.current_a)


def test_impossible_when_discriminant_is_negative() -> None:
    # Type 4, CCA, 24 AWG, 150 м: петля слишком велика для 71,3 Вт при 52 В.
    result = calculate(
        _case(
            standard_id="802.3bt-type4",
            v_pse=52.0,
            p_pd=71.3,
            length_m=150.0,
            material_id="CCA",
        )
    )
    assert result.feasible is False
    assert result.v_pd is None
    assert result.works is False
    assert result.discriminant < 0
    assert "дискриминант" in result.reasons[0]
    assert "невозможно" in build_report(
        _case(
            standard_id="802.3bt-type4",
            v_pse=52.0,
            p_pd=71.3,
            length_m=150.0,
            material_id="CCA",
        )
    ).recommendation


def test_type4_cca_passes_at_1m_and_fails_voltage_at_100m() -> None:
    short = calculate(
        _case(
            standard_id="802.3bt-type4",
            v_pse=52.0,
            p_pd=71.3,
            length_m=1.0,
            material_id="CCA",
        )
    )
    hundred = calculate(
        _case(
            standard_id="802.3bt-type4",
            v_pse=52.0,
            p_pd=71.3,
            length_m=100.0,
            material_id="CCA",
        )
    )
    assert short.works is True
    assert hundred.feasible is True
    assert hundred.voltage_ok is False
    assert hundred.works is False


def test_limits_fail_together_on_nominal_copper_past_the_budget() -> None:
    """На минимуме PSE числа Type 2 согласованы: 25,5 Вт, 42,5 В и 0,6 А.

    Чуть длиннее бюджетной петли одновременно проседают напряжение,
    ток и мощность PSE.
    """

    result = calculate(_case(length_m=150.0))
    assert result.works is False
    assert result.voltage_ok is False
    assert result.current_ok is False
    assert result.power_ok is False
    assert result.length_exceeds_channel is True


def test_only_pse_power_fails_when_source_voltage_is_high() -> None:
    result = calculate(_case(v_pse=57.0, length_m=150.0, material_id="CCA"))
    assert result.feasible is True
    assert result.voltage_ok is True
    assert result.current_ok is True
    assert result.power_ok is False
    assert result.works is False


def test_length_over_100m_does_not_fail_a_light_load() -> None:
    result = calculate(
        _case(
            standard_id="802.3af",
            v_pse=48.0,
            p_pd=3.0,
            length_m=150.0,
            category_id="cat6a",
            awg="22",
        )
    )
    assert result.works is True
    assert result.length_exceeds_channel is True
    text = build_report(
        _case(
            standard_id="802.3af",
            v_pse=48.0,
            p_pd=3.0,
            length_m=150.0,
            category_id="cat6a",
            awg="22",
        )
    ).recommendation
    assert "100" in text
    assert "надёжна" in text or "Запас" in text


def test_cca_recommendation_asks_for_copper() -> None:
    report = build_report(_case(material_id="CCA"))
    assert report.result.works is False
    assert "CCA" in report.recommendation
    assert "медь 24 AWG" in report.recommendation


def test_max_working_length_is_shorter_for_cca_and_monotonic() -> None:
    copper = max_working_length(_case())
    cca = max_working_length(_case(material_id="CCA"))
    assert copper is not None and cca is not None
    assert 100.0 < copper < 150.0
    assert cca < copper
    assert calculate(_case(length_m=copper)).works is True
    assert calculate(_case(length_m=min(150.0, copper + 0.2))).works is False


def test_sweep_covers_full_scale_and_stops_when_power_is_impossible() -> None:
    report = build_report(
        _case(
            standard_id="802.3bt-type4",
            v_pse=52.0,
            p_pd=71.3,
            length_m=150.0,
            material_id="CCA",
        )
    )
    assert [point.length_m for point in report.sweep] == [float(i) for i in range(151)]
    assert report.sweep[0].feasible is True
    assert report.sweep[-1].feasible is False
    assert any(point.v_pd is None for point in report.sweep)


def test_rejected_combinations() -> None:
    with pytest.raises(ValueError):
        calculate(_case(category_id="cat5e", awg="22"))
    with pytest.raises(ValueError):
        calculate(_case(standard_id="802.3at", v_pse=48.0))
    with pytest.raises(ValueError):
        calculate(_case(length_m=151.0))
    with pytest.raises(ValueError):
        calculate(_case(p_pd=40.0))


def test_zero_length_is_the_open_circuit_point() -> None:
    result = calculate(_case(length_m=0.0))
    assert result.r_loop_ohm == pytest.approx(0.0)
    assert result.v_pd == pytest.approx(50.0)
    assert result.delta_u_v == pytest.approx(0.0)
    assert result.p_loss_w == pytest.approx(0.0)
    assert result.works is True


def test_categories_only_offer_their_gauges() -> None:
    allowed = {item.id: item.allowed_awg for item in CATEGORIES}
    assert allowed["cat5e"] == ("24",)
    assert "22" not in allowed["cat6"]
    assert "24" not in allowed["cat6a"]


def test_larger_root_is_chosen_not_the_unstable_one() -> None:
    v_pd, discriminant = solve_pd_voltage(50.0, 8.42, 25.5)
    other = (50.0 - math.sqrt(discriminant)) / 2.0
    assert v_pd > other
    assert other < 25.0
