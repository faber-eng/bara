import re
from datetime import UTC, datetime, timedelta

import pytest

from contracts import AgentDecision, Verdict
from domain.case_view import (
    build_timeline,
    format_local,
    format_wib,
    past_checks,
    summarize_case,
)
from tests.fakes import (
    make_agent_run,
    make_case,
    make_escalation,
    make_evidence,
    make_task,
)

T0 = datetime(2026, 7, 20, 1, 0, tzinfo=UTC)
NAMES = {"vol-ari": "Ari Wijaya"}
SNAKE = re.compile(r"\b[a-z0-9]+_[a-z0-9_]+\b")


def test_format_local_names_the_day_and_the_zone_of_the_region():
    moment = datetime(2026, 10, 21, 3, 59, tzinfo=UTC)

    assert format_local(moment, "Asia/Jakarta") == "Wed 21 Oct, 10:59 WIB"
    assert format_local(moment, "Africa/Kinshasa") == "Wed 21 Oct, 04:59 WAT"
    assert format_wib(moment) == "Wed 21 Oct, 10:59 WIB"


def test_format_local_writes_the_day_and_month_in_the_reader_language():
    moment = datetime(2026, 10, 21, 6, 6, tzinfo=UTC)

    assert format_local(moment, "Asia/Jakarta", "id") == "Rab 21 Okt, 13.06 WIB"
    assert format_local(moment, "Asia/Jakarta", "en") == "Wed 21 Oct, 13:06 WIB"
    assert format_local(moment, "Asia/Jakarta", "ms") == "Rab 21 Okt, 13:06 WIB"
    assert format_local(moment, "Asia/Jakarta", "fr") == "mer. 21 oct., 13 h 06 WIB"


def at(hours):
    return T0 + timedelta(hours=hours)


def verdict(**overrides):
    fields = {
        "subject": "canal_dam",
        "dam_state": "broken",
        "smoke": "none",
        "hot_ground_signs": "none",
        "open_flame": "no",
        "transcript": None,
        "transcript_en": None,
        "reasons": ["gap"],
        "confidence": 0.9,
        "needs_human": False,
    }
    return Verdict(**{**fields, **overrides})


def test_a_case_with_no_tasks_has_no_deadline_and_no_status():
    summary = summarize_case(make_case(), [])

    assert summary.next_deadline_at is None
    assert summary.task_status is None


def test_the_summary_takes_the_earliest_open_deadline_and_its_status():
    tasks = [
        make_task(id="late", deadline_at=at(72), status="open"),
        make_task(id="soon", deadline_at=at(24), status="open"),
        make_task(id="done", deadline_at=at(1), status="done"),
    ]

    summary = summarize_case(make_case(), tasks)

    assert summary.next_deadline_at == at(24)
    assert summary.task_status == "open"


def test_an_overdue_task_counts_so_the_list_can_show_it():
    tasks = [
        make_task(id="a", deadline_at=at(50), status="open"),
        make_task(id="b", deadline_at=at(10), status="overdue"),
    ]

    summary = summarize_case(make_case(), tasks)

    assert summary.task_status == "overdue"
    assert summary.next_deadline_at == at(10)


def test_cancelled_and_reassigned_tasks_are_ignored():
    tasks = [
        make_task(id="a", status="cancelled"),
        make_task(id="b", status="reassigned"),
    ]

    assert summarize_case(make_case(), tasks).task_status is None


def test_the_timeline_is_oldest_first_and_covers_case_task_evidence_run_and_close():
    case = make_case(
        opened_at=at(0), status="closed", closed_by="ops-1", closed_at=at(30)
    )
    task = make_task(
        id="t1",
        created_at=at(1),
        deadline_at=at(73),
        done_at=at(5),
        status="done",
        assignee_id="vol-ari",
    )
    evidence = make_evidence(
        id="e1", task_id="t1", captured_at=at(4), verdict=verdict()
    )
    run = make_agent_run(
        id="r1",
        started_at=at(2),
        final_json=AgentDecision(
            decision="assign_check",
            reason="score high",
            evidence=["rank_areas"],
            next_check_at=None,
        ),
    )

    timeline = build_timeline(case, [task], [evidence], [run], [], [], NAMES)

    assert [entry.at for entry in timeline] == sorted(entry.at for entry in timeline)
    texts = [entry.text for entry in timeline]
    assert texts[0].startswith("Case opened")
    assert any("assign check" in text for text in texts)
    assert any("Ari Wijaya" in text for text in texts)
    assert any("broken" in text for text in texts)
    assert texts[-1] == "Case closed by ops-1"
    assert not any(SNAKE.search(text) for text in texts)


def test_a_failed_run_appears_as_a_failed_run():
    run = make_agent_run(started_at=at(2), final_json=None)

    texts = [
        e.text
        for e in build_timeline(make_case(opened_at=at(0)), [], [], [run], [], [], {})
    ]

    assert any("failed" in text.lower() for text in texts)


def test_evidence_without_a_capture_time_is_left_out_of_the_timeline():
    evidence = make_evidence(captured_at=None, verdict=verdict())

    timeline = build_timeline(
        make_case(opened_at=at(0)), [], [evidence], [], [], [], {}
    )

    assert len(timeline) == 1


def test_past_checks_come_from_evidence_with_a_verdict_and_a_capture_time():
    good = make_evidence(id="e1", task_id="t1", captured_at=at(4), verdict=verdict())
    no_time = make_evidence(id="e2", captured_at=None, verdict=verdict())
    no_verdict = make_evidence(id="e3", captured_at=at(3), verdict=None)

    checks = past_checks([no_verdict, no_time, good])

    assert [(c.task_id, c.dam_state, c.smoke) for c in checks] == [
        ("t1", "broken", "none")
    ]


def test_an_acknowledged_escalation_shows_the_handover_and_the_ack():
    escalation = make_escalation(
        contact_id="contact-daops", created_at=at(5), acknowledged_at=at(7)
    )

    timeline = build_timeline(
        make_case(opened_at=at(0)), [], [], [], [escalation], [], {}
    )

    assert [(entry.at, entry.text) for entry in timeline[1:]] == [
        (at(5), "Escalated to brigade contact-daops"),
        (at(7), "Brigade contact-daops acknowledged"),
    ]


def test_an_open_escalation_shows_only_the_handover():
    escalation = make_escalation(contact_id="contact-daops", created_at=at(5))

    timeline = build_timeline(
        make_case(opened_at=at(0)), [], [], [], [escalation], [], {}
    )

    assert [entry.text for entry in timeline[1:]] == [
        "Escalated to brigade contact-daops"
    ]


def test_a_task_entry_shows_the_due_time_in_wib_not_raw_iso():
    task = make_task(
        id="t1",
        created_at=at(1),
        deadline_at=datetime(2026, 10, 19, 22, 4, 58, 204295, tzinfo=UTC),
        assignee_id="patrol-hana",
        type="patrol_recheck",
    )

    timeline = build_timeline(
        make_case(opened_at=at(0)), [task], [], [], [], [], {"patrol-hana": "Hana"}
    )

    assert (
        "Task given to Hana: re-check the burned land, due Tue 20 Oct, 05:04 WIB"
        in [entry.text for entry in timeline]
    )


def texts_for(case=None, tasks=(), evidence=(), runs=(), names=None):
    timeline = build_timeline(
        case or make_case(opened_at=at(0)),
        list(tasks),
        list(evidence),
        list(runs),
        [],
        [],
        NAMES if names is None else names,
    )
    return [entry.text for entry in timeline]


@pytest.mark.parametrize(
    "case_type,dam_id,expected",
    [
        ("dam_risk", "dam-riau-017", "Case opened: dam at risk, canal dam 017"),
        ("reignition", None, "Case opened: fire may restart, cell riau-1-1"),
        ("hotspot", None, "Case opened: hotspot, cell riau-1-1"),
        ("dam_risk", "dam-x", "Case opened: dam at risk, canal dam dam-x"),
    ],
)
def test_the_case_opened_entry_is_plain(case_type, dam_id, expected):
    case = make_case(type=case_type, dam_id=dam_id, cell_id="riau-1-1", opened_at=at(0))

    assert texts_for(case)[0] == expected


def test_a_task_names_the_person_and_the_plain_task():
    task = make_task(
        type="dam_check",
        assignee_id="vol-ari",
        created_at=at(1),
        deadline_at=datetime(2026, 10, 21, 3, 59, tzinfo=UTC),
        done_at=at(3),
    )

    assert texts_for(tasks=[task])[1:] == [
        "Task given to Ari Wijaya: check the canal dam, due Wed 21 Oct, 10:59 WIB",
        "Task done: check the canal dam",
    ]


@pytest.mark.parametrize(
    "assignee,name",
    [("vol-gunawan", "Gunawan"), ("patrol-hana", "Patrol Hana"), ("ops", "Ops")],
)
def test_a_person_without_a_name_is_named_from_the_id(assignee, name):
    task = make_task(type="dam_repair", assignee_id=assignee, created_at=at(1))

    assert texts_for(tasks=[task], names={})[1].startswith(
        f"Task given to {name}: repair the canal dam, due"
    )


@pytest.mark.parametrize(
    "kind,state,expected",
    [
        ("photo", "broken", "Photo checked: dam broken, smoke none"),
        ("video", "not_applicable", "Video checked: dam not applicable, smoke none"),
        ("audio", "unknown", "Voice note checked: dam unknown, smoke none"),
    ],
)
def test_checked_evidence_is_plain(kind, state, expected):
    evidence = make_evidence(
        kind=kind, captured_at=at(4), verdict=verdict(dam_state=state)
    )

    assert texts_for(evidence=[evidence])[1] == expected


def test_unchecked_evidence_says_it_was_received():
    evidence = make_evidence(kind="audio", captured_at=at(4), verdict=None)

    assert texts_for(evidence=[evidence])[1] == "Voice note received"


def test_an_agent_decision_reads_as_one_plain_line():
    run = make_agent_run(
        started_at=at(2),
        final_json=AgentDecision(
            decision="Wait for the volunteer's photo.",
            reason="The task is open; assign_task already ran.",
            evidence=[],
            next_check_at=None,
        ),
    )

    assert texts_for(runs=[run])[1] == (
        "Agent decision: wait for the volunteer's photo. "
        "The task is open; assign task already ran."
    )


def test_a_failed_run_names_its_trigger_in_plain_words():
    run = make_agent_run(started_at=at(2), final_json=None, trigger="task.overdue")

    assert texts_for(runs=[run])[1] == "Agent run failed (task overdue)"
