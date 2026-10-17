from datetime import date

import pytest

from domain.reignition_features import (
    MissingMeasurement,
    cells_by_date,
    event_windows,
    split_for,
    training_rows,
)
from ee_lib.config import SplitYears
from ee_lib.weeks import DateRange

YEARS = SplitYears(train=(2015, 2024), valid=2025, test=2026)
QUIET = date(2019, 8, 10)


def event(**overrides):
    base = {
        "event_id": "riau-1-1-20190801",
        "cell_id": "riau-1-1",
        "region": "riau",
        "quiet_date": QUIET,
        "reignited": 1,
        "peat_class": 1,
        "canal_dist_m": 250.0,
        "detection_days": 4,
        "max_t21": 330.5,
        "mean_confidence": 62.5,
        "prior_years_burned": 3,
    }
    return {**base, **overrides}


MEASURE = {
    "cell_id": "riau-1-1",
    "quiet_date": "2019-08-10",
    "s1_anom_db": -1.5,
    "rain_7d_before_mm": 2,
    "rain_14d_before_mm": 10.5,
    "rain_7d_after_mm": None,
}


@pytest.mark.parametrize(
    ("year", "split"),
    [(2015, "train"), (2024, "train"), (2025, "valid"), (2026, "test"), (2014, None)],
)
def test_split_is_by_quiet_year(year, split):
    assert split_for(year, YEARS) == split


def test_event_windows_end_at_the_quiet_date():
    windows = event_windows(QUIET, s1_days=12, chirps_last=date(2026, 9, 30))

    assert windows.s1 == DateRange(date(2019, 7, 29), QUIET)
    assert windows.rain_7d_before == DateRange(date(2019, 8, 3), QUIET)
    assert windows.rain_14d_before == DateRange(date(2019, 7, 27), QUIET)
    assert windows.rain_7d_after == DateRange(QUIET, date(2019, 8, 17))


def test_a_rain_window_past_the_last_chirps_day_is_not_measured():
    quiet = date(2026, 9, 27)

    windows = event_windows(quiet, s1_days=12, chirps_last=date(2026, 9, 30))

    assert windows.rain_7d_before == DateRange(date(2026, 9, 20), quiet)
    assert windows.rain_7d_after is None


def test_a_rain_window_ending_the_day_after_the_last_chirps_day_is_measured():
    quiet = date(2026, 9, 24)

    windows = event_windows(quiet, s1_days=12, chirps_last=date(2026, 9, 30))

    assert windows.rain_7d_after == DateRange(quiet, date(2026, 10, 1))


def test_training_rows_join_the_event_its_measures_and_peat_fraction():
    rows = training_rows([event()], [MEASURE], {"riau-1-1": 0.75}, YEARS)

    row = rows[0]
    assert row.split == "train"
    assert row.reignited == 1
    assert row.peat_class == 1
    assert row.peat_fraction == 0.75
    assert row.canal_dist_m == 250.0
    assert row.s1_anom_db == -1.5
    assert row.rain_7d_before_mm == 2.0
    assert row.rain_14d_before_mm == 10.5
    assert row.rain_7d_after_mm is None
    assert row.detection_days == 4
    assert row.max_t21 == 330.5
    assert row.mean_confidence == 62.5
    assert row.month == 8
    assert row.prior_years_burned == 3


def test_an_unlabeled_test_event_keeps_a_null_label():
    quiet = date(2026, 10, 1)
    measure = {**MEASURE, "quiet_date": "2026-10-01"}

    rows = training_rows(
        [event(quiet_date=quiet, reignited=None)], [measure], {"riau-1-1": 1.0}, YEARS
    )

    assert rows[0].split == "test"
    assert rows[0].reignited is None


def test_events_outside_the_split_years_are_skipped():
    measure = {**MEASURE, "quiet_date": "2014-08-10"}

    rows = training_rows(
        [event(quiet_date=date(2014, 8, 10))], [measure], {"riau-1-1": 1.0}, YEARS
    )

    assert rows == []


def test_a_missing_measure_is_an_error():
    with pytest.raises(MissingMeasurement, match="riau-1-1-20190801"):
        training_rows([event()], [], {"riau-1-1": 1.0}, YEARS)


def test_a_missing_peat_fraction_is_an_error():
    with pytest.raises(MissingMeasurement, match="peat_fraction"):
        training_rows([event()], [MEASURE], {}, YEARS)


def test_cells_by_date_groups_the_event_cells():
    events = [
        event(),
        event(cell_id="riau-1-2"),
        event(cell_id="riau-1-3", quiet_date=date(2019, 9, 1)),
    ]

    assert cells_by_date(events) == {
        QUIET: ["riau-1-1", "riau-1-2"],
        date(2019, 9, 1): ["riau-1-3"],
    }
