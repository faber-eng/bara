from datetime import date
from zoneinfo import ZoneInfo

from contracts import RankingRun, Task
from domain.public_summary import week_window
from tests.fakes import InMemoryCollection, make_escalation
from tests.public_world import NOW, WEEK, PublicWorld, at

ZONE = ZoneInfo("Asia/Jakarta")


def test_the_week_window_is_the_local_monday_to_monday():
    window = week_window(date(2026, 10, 12), ZONE)

    assert window.start == at(11, 17)
    assert window.end == at(18, 17)


def test_each_summary_field_equals_the_hand_counted_value():
    summary = PublicWorld().queries().summary("riau", WEEK, NOW)

    assert summary.week == WEEK
    assert summary.high_risk_cells == 3
    assert summary.dams_broken == 2
    assert summary.cases_open == 2
    assert summary.cases_escalated == 2
    assert summary.cases_closed == 2
    assert summary.median_days_to_repair == 2.5
    assert summary.tasks_on_time_pct == 50.0


def test_data_as_of_without_a_run_record_falls_back_to_the_week_start():
    summary = PublicWorld().queries().summary("riau", WEEK, NOW)

    assert summary.data_as_of.s1_pass_date == date(2026, 10, 12)
    assert summary.data_as_of.ranking_run_at == at(11, 17)


def test_data_as_of_reads_the_stored_run_record():
    world = PublicWorld()
    ran_at = at(14, 3)
    world.ranking_runs.put(
        WEEK,
        RankingRun(ran_at=ran_at, s1_pass_date=date(2026, 10, 13), cells=200, dams=50),
    )

    summary = world.queries().summary("riau", WEEK, NOW)

    assert summary.data_as_of.s1_pass_date == date(2026, 10, 13)
    assert summary.data_as_of.ranking_run_at == ran_at


def test_a_week_with_no_tasks_due_has_no_on_time_percentage():
    world = PublicWorld()
    world.tasks = InMemoryCollection(Task)

    summary = world.queries().summary("riau", None, NOW)

    assert summary.tasks_on_time_pct is None
    assert summary.median_days_to_repair is None


def test_dams_of_other_regions_and_other_weeks_do_not_count():
    summary = PublicWorld().queries().summary("riau", None, NOW)

    assert summary.dams_broken == 2
    assert summary.high_risk_cells == 3


def test_the_dam_list_gives_the_open_repair_due_date():
    dams = {dam.id: dam for dam in PublicWorld().queries().dams("riau")}

    assert set(dams) == {"dam-1", "dam-2", "dam-3"}
    assert dams["dam-1"].repair_due_at == at(22)
    assert dams["dam-2"].repair_due_at is None
    assert dams["dam-3"].repair_due_at is None


def test_the_record_is_newest_first_in_plain_words():
    lines = PublicWorld().queries().record("riau", 50)

    assert [line.at for line in lines] == sorted((l.at for l in lines), reverse=True)
    texts = {line.text for line in lines}
    assert "Repair due 22 Oct in riau-assigned." in texts
    assert "Sent to the fire brigade for riau-escalated." in texts
    assert "Case closed in riau-closed-a." in texts
    assert "A task in riau-overdue is overdue." in texts


def test_the_record_honours_its_limit():
    assert len(PublicWorld().queries().record("riau", 3)) == 3


def test_cells_are_ranked_and_limited():
    result = PublicWorld().queries().cells("riau", None, 2)

    assert result.week == WEEK
    assert [cell.rank for cell in result.cells] == [1, 2]


def test_now_is_inside_the_scenario_week():
    assert week_window(date(2026, 10, 12), ZONE).contains(NOW)


def test_a_task_not_yet_due_does_not_lower_the_on_time_percentage():
    world = PublicWorld()
    world.add_task(
        "t-later",
        "assigned",
        "dam_check",
        "uid-ari",
        created_at=at(16),
        deadline_at=at(18),
        status="open",
    )

    assert world.queries().summary("riau", WEEK, NOW).tasks_on_time_pct == 50.0


def test_an_overdue_repair_keeps_its_due_date():
    world = PublicWorld()
    world.tasks.update("t-pending", {"status": "overdue"})

    dams = {dam.id: dam for dam in world.queries().dams("riau")}

    assert dams["dam-1"].repair_due_at == at(22)


def test_a_case_that_left_escalation_keeps_its_brigade_line():
    world = PublicWorld()
    world.cases.update("monitoring", {"status": "assigned"})
    world.escalations.put(
        "x-old", make_escalation(id="x-old", case_id="monitoring", created_at=at(14))
    )

    texts = [line.text for line in world.queries().record("riau", 50)]

    assert "Sent to the fire brigade for riau-monitoring." in texts
