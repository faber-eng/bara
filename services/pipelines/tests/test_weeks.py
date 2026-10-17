from datetime import UTC, date, datetime, timedelta, timezone
from zoneinfo import ZoneInfo

import pytest

from ee_lib.weeks import (
    DateRange,
    FutureWeek,
    InvalidWeek,
    current_week,
    drying_window,
    iso_week,
    local_today,
    rain_end,
    resolve_week,
    same_day_in_year,
    week_label,
    window_end,
)

JAKARTA = ZoneInfo("Asia/Jakarta")


def test_iso_week_is_the_monday_of_that_week():
    assert iso_week("2026-W42") == date(2026, 10, 12)


def test_week_label_round_trips():
    assert week_label(date(2026, 10, 12)) == "2026-W42"
    assert week_label(date(2026, 10, 18)) == "2026-W42"


@pytest.mark.parametrize(
    "label",
    ["2026-42", "2026-W4", "2026W42", "26-W42", "2026-W00", "2026-W54", "", None],
)
def test_a_bad_week_raises(label):
    with pytest.raises(InvalidWeek):
        iso_week(label)


def test_week_53_exists_only_in_long_years():
    assert iso_week("2026-W53") == date(2026, 12, 28)
    with pytest.raises(InvalidWeek):
        iso_week("2027-W53")


def test_current_week_uses_the_region_timezone():
    now = datetime(2026, 10, 18, 17, 30, tzinfo=UTC)

    assert current_week(now, JAKARTA) == "2026-W43"


def test_sunday_late_evening_local_stays_in_its_week():
    now = datetime(2026, 10, 18, 23, 0, tzinfo=JAKARTA)

    assert current_week(now, JAKARTA) == "2026-W42"


def test_local_today_rejects_a_naive_datetime():
    with pytest.raises(ValueError):
        local_today(datetime(2026, 10, 18, 12, 0), JAKARTA)


def test_local_today_converts_from_another_offset():
    now = datetime(2026, 10, 18, 20, 0, tzinfo=timezone(timedelta(hours=-5)))

    assert local_today(now, JAKARTA) == date(2026, 10, 19)


def test_window_end_is_the_end_of_a_past_week():
    assert window_end(date(2026, 10, 5), today=date(2026, 10, 17)) == date(2026, 10, 12)


def test_window_end_is_tomorrow_during_the_current_week():
    assert window_end(date(2026, 10, 12), today=date(2026, 10, 17)) == date(
        2026, 10, 18
    )


def test_rain_end_stops_after_the_last_chirps_day():
    assert rain_end(date(2026, 10, 18), chirps_last=date(2026, 9, 30)) == date(
        2026, 10, 1
    )


def test_rain_end_is_the_window_end_when_chirps_covers_it():
    assert rain_end(date(2026, 8, 3), chirps_last=date(2026, 9, 30)) == date(2026, 8, 3)


def test_drying_window_builds_every_range():
    window = drying_window(
        date(2026, 10, 12),
        today=date(2026, 10, 17),
        chirps_last=date(2026, 9, 30),
        s1_days=12,
        rain_days=30,
    )

    assert window.s1_recent == DateRange(date(2026, 10, 6), date(2026, 10, 18))
    assert window.s1_previous == DateRange(date(2026, 9, 24), date(2026, 10, 6))
    assert window.rain == DateRange(date(2026, 9, 1), date(2026, 10, 1))


def test_resolve_week_defaults_to_the_current_week():
    now = datetime(2026, 10, 17, 4, 0, tzinfo=UTC)

    assert resolve_week(None, now, JAKARTA) == date(2026, 10, 12)


def test_resolve_week_accepts_a_past_week():
    now = datetime(2026, 10, 17, 4, 0, tzinfo=UTC)

    assert resolve_week("2026-W20", now, JAKARTA) == date(2026, 5, 11)


def test_resolve_week_rejects_a_future_week():
    now = datetime(2026, 10, 17, 4, 0, tzinfo=UTC)

    with pytest.raises(FutureWeek, match="2026-W43"):
        resolve_week("2026-W43", now, JAKARTA)


def test_resolve_week_rejects_a_bad_label():
    now = datetime(2026, 10, 17, 4, 0, tzinfo=UTC)

    with pytest.raises(InvalidWeek):
        resolve_week("next week", now, JAKARTA)


def test_same_day_in_year_moves_the_year():
    assert same_day_in_year(date(2026, 9, 1), 2001) == date(2001, 9, 1)


def test_same_day_in_year_maps_a_leap_day_to_february_28():
    assert same_day_in_year(date(2024, 2, 29), 2023) == date(2023, 2, 28)
