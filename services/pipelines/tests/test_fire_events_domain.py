from datetime import date, timedelta

import pytest

from domain.fire_events import (
    EventRules,
    InvalidSighting,
    Sighting,
    build_events,
    detection_buffer_m,
    sighting,
)

RULES = EventRules(
    quiet_days=3,
    label_window_days=(3, 30),
    first_year=2015,
    last_year=2026,
)
OBSERVED_UNTIL = date(2026, 10, 16)
START = date(2019, 8, 1)


def seen(day_offset: int, *, inside=True, cell="riau-1-1", t21=320.0, conf=60.0):
    return Sighting(
        cell_id=cell,
        day=START + timedelta(days=day_offset),
        inside=inside,
        t21=t21,
        confidence=conf,
    )


def build(sightings, observed_until=OBSERVED_UNTIL, rules=RULES):
    return build_events("riau", sightings, rules, observed_until)


def test_consecutive_days_with_gaps_of_two_days_are_one_event():
    events = build([seen(0), seen(1), seen(4), seen(5)])

    assert len(events) == 1
    event = events[0]
    assert event.start_date == START
    assert event.last_detection_date == START + timedelta(days=5)
    assert event.detection_days == 4


def test_a_gap_of_three_empty_days_starts_a_new_event():
    events = build([seen(0), seen(4)])

    assert [event.start_date for event in events] == [
        START,
        START + timedelta(days=4),
    ]


def test_quiet_date_is_the_last_detection_plus_quiet_days():
    event = build([seen(0), seen(2)])[0]

    assert event.quiet_date == START + timedelta(days=5)


def test_a_nearby_detection_delays_the_quiet_date():
    event = build([seen(0), seen(2, inside=False)])[0]

    assert event.last_detection_date == START
    assert event.quiet_date == START + timedelta(days=5)


def test_nearby_detections_alone_make_no_event():
    assert build([seen(0, inside=False), seen(1, inside=False)]) == []


def test_event_stats_come_from_detections_inside_the_cell():
    event = build(
        [
            seen(0, t21=310.0, conf=40.0),
            seen(0, t21=330.0, conf=80.0),
            seen(1, inside=False, t21=400.0, conf=100.0),
        ]
    )[0]

    assert event.detection_days == 1
    assert event.max_t21 == 330.0
    assert event.mean_confidence == 60.0


def test_a_detection_in_the_label_window_marks_the_event_reignited():
    events = build([seen(0), seen(3 + 3 + 3, inside=False)])

    assert events[0].quiet_date == START + timedelta(days=3)
    assert events[0].reignited == 1


@pytest.mark.parametrize("after_quiet", [3, 30])
def test_the_label_window_bounds_are_inclusive(after_quiet):
    quiet = 3
    events = build([seen(0), seen(quiet + after_quiet, inside=False)])

    assert events[0].reignited == 1


def test_a_detection_after_the_label_window_is_not_a_reignition():
    events = build([seen(0), seen(3 + 31)])

    assert events[0].reignited == 0


def test_the_label_is_unknown_until_the_window_is_observed():
    quiet = START + timedelta(days=3)

    events = build([seen(0)], observed_until=quiet + timedelta(days=29))

    assert events[0].reignited is None


def test_an_event_that_has_not_gone_quiet_by_the_last_day_is_left_out():
    assert build([seen(0)], observed_until=START + timedelta(days=2)) == []


def test_events_outside_the_years_are_left_out():
    rules = EventRules(
        quiet_days=3, label_window_days=(3, 30), first_year=2020, last_year=2026
    )

    assert build([seen(0)], rules=rules) == []


def test_each_cell_has_its_own_events_with_a_stable_id():
    events = build([seen(0, cell="riau-1-2"), seen(0, cell="riau-1-1")])

    assert [event.event_id for event in events] == [
        "riau-1-1-20190801",
        "riau-1-2-20190801",
    ]
    assert {event.region for event in events} == {"riau"}


def test_sighting_reads_a_bigquery_row():
    row = {
        "cell_id": "riau-1-1",
        "detect_date": START,
        "inside": True,
        "t21": 312.5,
        "confidence": 36,
    }

    assert sighting(row) == Sighting("riau-1-1", START, True, 312.5, 36.0)


def test_sighting_refuses_a_row_without_a_date():
    row = {
        "cell_id": "riau-1-1",
        "detect_date": None,
        "inside": True,
        "t21": 312.5,
        "confidence": 36,
    }

    with pytest.raises(InvalidSighting, match="detect_date"):
        sighting(row)


def test_the_gap_rule_follows_quiet_days():
    rules = EventRules(
        quiet_days=5, label_window_days=(3, 30), first_year=2015, last_year=2026
    )

    events = build([seen(0), seen(4)], rules=rules)

    assert len(events) == 1
    assert events[0].quiet_date == START + timedelta(days=9)


def test_an_event_quiet_on_the_last_observed_day_is_written():
    events = build([seen(0)], observed_until=START + timedelta(days=3))

    assert len(events) == 1


def test_the_label_is_known_when_the_window_ends_on_the_last_observed_day():
    quiet = START + timedelta(days=3)

    events = build([seen(0)], observed_until=quiet + timedelta(days=30))

    assert events[0].reignited == 0


def test_a_detection_before_the_label_window_starts_a_new_event_only():
    events = build([seen(0), seen(3 + 2)])

    assert events[0].quiet_date == START + timedelta(days=3)
    assert events[0].reignited == 0
    assert events[1].start_date == START + timedelta(days=5)


def test_events_after_the_last_year_are_left_out():
    rules = EventRules(
        quiet_days=3, label_window_days=(3, 30), first_year=2015, last_year=2018
    )

    assert build([seen(0)], rules=rules) == []


def test_the_detection_buffer_covers_the_radius_from_any_cell_corner():
    assert detection_buffer_m(label_radius_m=1000, grid_cell_m=1000) == 2000
