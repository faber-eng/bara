from datetime import UTC, datetime, timedelta

import pytest

from domain.assignment import (
    MAX_DEADLINE_HOURS,
    InvalidDeadline,
    deadline_hours,
    local_deadline,
    next_attempt,
    real_schedule_time,
    status_after_assign,
    tasks_to_reassign,
)
from domain.case_machine import IllegalTransition
from tests.fakes import make_task

DEFAULTS = {"dam_check": 72, "dam_repair": 168, "patrol_recheck": 24}


@pytest.mark.parametrize(
    ("task_type", "hours"), [("dam_check", 72), ("dam_repair", 168)]
)
def test_no_requested_deadline_uses_the_task_type_default(task_type, hours):
    assert deadline_hours(None, task_type, DEFAULTS) == hours


def test_a_requested_deadline_wins_over_the_default():
    assert deadline_hours(48, "dam_check", DEFAULTS) == 48


@pytest.mark.parametrize("hours", [0, -1, MAX_DEADLINE_HOURS + 1])
def test_a_requested_deadline_out_of_range_is_rejected(hours):
    with pytest.raises(InvalidDeadline):
        deadline_hours(hours, "dam_check", DEFAULTS)


def test_the_cloud_tasks_limit_is_the_largest_deadline():
    assert deadline_hours(MAX_DEADLINE_HOURS, "dam_check", DEFAULTS) == 720


@pytest.mark.parametrize(
    "status", ["open", "human_review", "overdue", "monitoring", "reviewing"]
)
def test_a_case_with_an_assign_edge_becomes_assigned(status):
    assert status_after_assign(status) == "assigned"


def test_an_assigned_case_stays_assigned():
    assert status_after_assign("assigned") == "assigned"


@pytest.mark.parametrize("status", ["resolved_pending_human", "escalated", "closed"])
def test_a_case_without_an_assign_edge_is_rejected(status):
    with pytest.raises(IllegalTransition):
        status_after_assign(status)


def test_the_real_schedule_time_removes_the_sim_offset():
    deadline = datetime(2026, 7, 23, 1, 0, tzinfo=UTC)

    at = real_schedule_time(deadline, offset_seconds=-3600)

    assert at == deadline + timedelta(hours=1)


def test_with_no_offset_the_real_schedule_time_is_the_deadline():
    deadline = datetime(2026, 10, 20, 12, 0, tzinfo=UTC)

    assert real_schedule_time(deadline, offset_seconds=0) == deadline


def test_a_first_task_is_attempt_one():
    assert next_attempt("open", []) == 1


def test_a_task_on_an_overdue_case_counts_one_more_than_the_last_attempt():
    prior = [
        make_task(id="t1", attempt=1, status="reassigned"),
        make_task(id="t2", attempt=2, status="overdue"),
    ]

    assert next_attempt("overdue", prior) == 3


def test_a_recheck_on_a_monitoring_case_starts_again_at_one():
    prior = [make_task(id="t1", attempt=2, status="done")]

    assert next_attempt("monitoring", prior) == 1


def test_only_overdue_tasks_of_an_overdue_case_are_reassigned():
    prior = [
        make_task(id="t1", status="overdue"),
        make_task(id="t2", status="done"),
    ]

    assert tasks_to_reassign("overdue", prior) == ["t1"]
    assert tasks_to_reassign("open", prior) == []


def test_the_local_deadline_names_the_weekday_and_the_zone():
    deadline = datetime(2026, 10, 20, 6, 0, tzinfo=UTC)

    assert (
        local_deadline(deadline, "Asia/Jakarta") == "Tuesday 20 October 2026, 13:00 WIB"
    )
