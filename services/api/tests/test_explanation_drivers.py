import pytest

from domain.rank_explanation import (
    Driver,
    ExplanationRejected,
    check_points,
    driver_effect,
    drivers_of,
)

WEIGHTS = {"s1_anom_db": 0.45, "rain_deficit_pct": 0.30, "canal_dist_m": 0.15}


@pytest.mark.parametrize(
    "value,effect",
    [(-4.2, "raises"), (1.3, "lowers"), (0.04, "small"), (-0.04, "small")],
)
def test_a_drier_radar_signal_raises_the_score(value, effect):
    assert driver_effect("s1_anom_db", value) == effect


@pytest.mark.parametrize(
    "fraction,effect",
    [(0.31, "raises"), (-0.05, "lowers"), (0.004, "small")],
)
def test_less_rain_than_normal_raises_and_more_rain_lowers(fraction, effect):
    assert driver_effect("rain_deficit_pct", fraction) == effect


@pytest.mark.parametrize("metres,effect", [(140.0, "raises"), (2500.0, "small")])
def test_a_canal_close_by_raises_and_a_far_canal_adds_little(metres, effect):
    assert driver_effect("canal_dist_m", metres) == effect


def test_drivers_come_largest_weight_first_with_whole_percent_weights():
    values = {"canal_dist_m": 2500.0, "s1_anom_db": -5.1, "rain_deficit_pct": -0.05}

    assert drivers_of(values, WEIGHTS) == [
        Driver("s1_anom_db", "raises", 45),
        Driver("rain_deficit_pct", "lowers", 30),
        Driver("canal_dist_m", "small", 15),
    ]


def test_a_missing_value_has_no_driver():
    assert drivers_of({"s1_anom_db": -5.1}, WEIGHTS) == [
        Driver("s1_anom_db", "raises", 45)
    ]


EXPECTED = [
    Driver("s1_anom_db", "raises", 45),
    Driver("rain_deficit_pct", "lowers", 30),
]


def test_points_that_match_every_driver_in_order_pass():
    check_points([("s1_anom_db", "raises"), ("rain_deficit_pct", "lowers")], EXPECTED)


def test_a_point_whose_effect_contradicts_the_data_is_rejected():
    with pytest.raises(ExplanationRejected, match="rain_deficit_pct effect"):
        check_points(
            [("s1_anom_db", "raises"), ("rain_deficit_pct", "raises")], EXPECTED
        )


@pytest.mark.parametrize(
    "points",
    [
        [("s1_anom_db", "raises")],
        [("rain_deficit_pct", "lowers"), ("s1_anom_db", "raises")],
        [("s1_anom_db", "raises"), ("s1_anom_db", "raises")],
    ],
)
def test_points_that_skip_reorder_or_repeat_a_driver_are_rejected(points):
    with pytest.raises(ExplanationRejected, match="points"):
        check_points(points, EXPECTED)
