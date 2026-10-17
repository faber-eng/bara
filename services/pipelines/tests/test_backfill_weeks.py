from datetime import date

import pytest

from jobs import backfill_weeks as job
from jobs.cli import UsageError

WEEK_20 = date(2026, 5, 11)
WEEK_42 = date(2026, 10, 12)


def test_weeks_run_oldest_first_through_the_last_week_inclusive():
    weeks = job.weeks_between(WEEK_20, date(2026, 5, 25))

    assert weeks == [date(2026, 5, 11), date(2026, 5, 18), date(2026, 5, 25)]


def test_the_full_range_has_23_weeks():
    assert len(job.weeks_between(WEEK_20, WEEK_42)) == 23


def test_a_start_after_the_end_is_a_usage_error():
    with pytest.raises(UsageError):
        job.weeks_between(WEEK_42, WEEK_20)


def test_each_week_is_scored_then_published_and_only_the_last_updates_latest():
    calls = []

    def score(week_start):
        calls.append(("score", week_start))
        return {"cells": 3769}

    def publish(week_start, latest):
        calls.append(("publish", week_start, latest))
        return {"cells": 200, "dams": 40}

    weeks = [date(2026, 5, 11), date(2026, 5, 18)]
    summaries = job.backfill(weeks, date(2026, 5, 18), score, publish)

    assert calls == [
        ("score", date(2026, 5, 11)),
        ("publish", date(2026, 5, 11), False),
        ("score", date(2026, 5, 18)),
        ("publish", date(2026, 5, 18), True),
    ]
    assert [s["week"] for s in summaries] == ["2026-W20", "2026-W21"]
    assert summaries[0]["scored"] == {"cells": 3769}
    assert summaries[0]["published"] == {"cells": 200, "dams": 40}


def test_a_range_that_ends_before_the_latest_week_never_refreshes_the_latest_set():
    flags = []

    def publish(week_start, latest):
        flags.append(latest)
        return {}

    weeks = [date(2026, 5, 11), date(2026, 5, 18)]
    job.backfill(weeks, WEEK_42, lambda week_start: {}, publish)

    assert flags == [False, False]
