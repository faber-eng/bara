from datetime import UTC, datetime, timedelta

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


def test_format_local_names_the_day_and_the_zone_of_the_region():
    moment = datetime(2026, 10, 21, 3, 59, tzinfo=UTC)

    assert format_local(moment, "Asia/Jakarta") == "Wed 21 Oct, 10:59 WIB"
    assert format_local(moment, "Africa/Kinshasa") == "Wed 21 Oct, 04:59 WAT"
    assert format_wib(moment) == "Wed 21 Oct, 10:59 WIB"


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

    timeline = build_timeline(case, [task], [evidence], [run], [], [])

    assert [entry.at for entry in timeline] == sorted(entry.at for entry in timeline)
    texts = [entry.text for entry in timeline]
    assert texts[0].startswith("Case opened")
    assert any("assign_check" in text for text in texts)
    assert any("vol-ari" in text for text in texts)
    assert any("broken" in text for text in texts)
    assert texts[-1] == "Case closed by ops-1"


def test_a_failed_run_appears_as_a_failed_run():
    run = make_agent_run(started_at=at(2), final_json=None)

    texts = [
        e.text
        for e in build_timeline(make_case(opened_at=at(0)), [], [], [run], [], [])
    ]

    assert any("failed" in text.lower() for text in texts)


def test_evidence_without_a_capture_time_is_left_out_of_the_timeline():
    evidence = make_evidence(captured_at=None, verdict=verdict())

    timeline = build_timeline(make_case(opened_at=at(0)), [], [evidence], [], [], [])

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

    timeline = build_timeline(make_case(opened_at=at(0)), [], [], [], [escalation], [])

    assert [(entry.at, entry.text) for entry in timeline[1:]] == [
        (at(5), "Escalated to brigade contact-daops"),
        (at(7), "Brigade contact-daops acknowledged"),
    ]


def test_an_open_escalation_shows_only_the_handover():
    escalation = make_escalation(contact_id="contact-daops", created_at=at(5))

    timeline = build_timeline(make_case(opened_at=at(0)), [], [], [], [escalation], [])

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

    timeline = build_timeline(make_case(opened_at=at(0)), [task], [], [], [], [])

    assert "Task patrol_recheck given to patrol-hana, due Tue 20 Oct, 05:04 WIB" in [
        entry.text for entry in timeline
    ]
