from datetime import date

import pytest

from domain.eval_report import (
    TOP_SHARE,
    WeekCapture,
    complete_weeks,
    reignition_summary,
    year_summary,
)


def week(day, hotspots, captured, cells=100):
    return WeekCapture(
        week_start=day, cells=cells, hotspots=hotspots, captured=captured
    )


def test_year_summary_pools_hotspots_over_the_weeks():
    weeks = [
        week(date(2019, 8, 5), hotspots=30, captured=12),
        week(date(2019, 8, 12), hotspots=10, captured=4),
        week(date(2019, 8, 19), hotspots=0, captured=0),
    ]

    summary = year_summary(2019, weeks)

    assert summary == {
        "year": 2019,
        "weeks": 3,
        "hotspots": 40,
        "captured": 16,
        "capture_rate": 0.4,
        "lift": pytest.approx(0.4 / TOP_SHARE),
    }


def test_a_year_without_hotspots_has_no_rate():
    summary = year_summary(2026, [week(date(2026, 5, 11), hotspots=0, captured=0)])

    assert summary["capture_rate"] is None
    assert summary["lift"] is None


def test_complete_weeks_drop_a_week_whose_follow_window_passes_the_data():
    weeks = [week(date(2026, 8, 3), 5, 1), week(date(2026, 9, 21), 0, 0)]

    kept = complete_weeks(weeks, through=date(2026, 10, 15))

    assert [w.week_start for w in kept] == [date(2026, 8, 3)]


def test_reignition_summary_takes_the_newest_test_rows():
    rows = [
        {
            "evaluated_at": "2026-10-17T17:09:14+00:00",
            "model": "reignition_v1",
            "split": "test",
            "events": 118,
            "positives": 13,
            "auc": 0.1,
            "precision_top10": 0.1,
            "recall_top10": 0.1,
        },
        {
            "evaluated_at": "2026-10-17T17:21:49+00:00",
            "model": "reignition_v1",
            "split": "test",
            "events": 118,
            "positives": 13,
            "auc": 0.662,
            "precision_top10": 0.25,
            "recall_top10": 0.231,
        },
        {
            "evaluated_at": "2026-10-17T17:21:49+00:00",
            "model": "reignition_v1_no_rain_after",
            "split": "test",
            "events": 118,
            "positives": 13,
            "auc": 0.637,
            "precision_top10": 0.0,
            "recall_top10": 0.0,
        },
        {
            "evaluated_at": "2026-10-17T17:21:49+00:00",
            "model": "detection_days_baseline",
            "split": "test",
            "events": 118,
            "positives": 13,
            "auc": 0.708,
            "precision_top10": 0.276,
            "recall_top10": 0.255,
        },
        {
            "evaluated_at": "2026-10-17T17:21:49+00:00",
            "model": "reignition_v1",
            "split": "valid",
            "events": 117,
            "positives": 39,
            "auc": 0.805,
            "precision_top10": 0.833,
            "recall_top10": 0.256,
        },
    ]

    summary = reignition_summary("riau", rows)

    assert summary["run_at"] == "2026-10-17T17:21:49+00:00"
    assert summary["split"] == "test"
    assert summary["events"] == 118
    assert summary["positives"] == 13
    assert summary["model"] == {
        "name": "reignition_v1",
        "auc": 0.662,
        "precision_top10": 0.25,
        "recall_top10": 0.231,
    }
    assert summary["served"]["name"] == "reignition_v1_no_rain_after"
    assert summary["baseline"]["auc"] == 0.708


def test_reignition_summary_refuses_a_run_without_the_baseline():
    rows = [
        {
            "evaluated_at": "2026-10-17T17:21:49+00:00",
            "model": "reignition_v1",
            "split": "test",
            "events": 118,
            "positives": 13,
            "auc": 0.662,
            "precision_top10": 0.25,
            "recall_top10": 0.231,
        },
    ]

    with pytest.raises(ValueError):
        reignition_summary("riau", rows)
