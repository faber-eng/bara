from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from bara_agent.prompts import RunInput, render_run_input
from contracts import (
    Case,
    CaseRisk,
    CaseType,
    Dam,
    EvidenceReceived,
    GeoPoint,
    TaskOverdue,
    TaskType,
    Verdict,
    Volunteer,
    VolunteerRole,
)
from overdue_events import run_event
from tests.fakes import make_case, make_dam, make_task, make_verdict, make_volunteer

NOW = datetime(2026, 10, 18, 3, 0, tzinfo=UTC)
OPENED_AT = NOW - timedelta(days=3)
EVIDENCE_TRIGGER = "evidence.received"
OVERDUE_TRIGGER = "task.overdue"
AREA_TRIGGER = "area.check"
LOW_DRYING = 41.0
HIGH_DRYING = 91.0
REVIEW_DRYING = 72.0
RECHECK_REIGNITE = 0.31
PERSON_STEP_DEG = 0.004
REGION_TIMEZONE = "Asia/Jakarta"
PEOPLE_NAMES = {
    "repair-1": "Budi Santoso",
    "repair-2": "Rahmat Hidayat",
    "repair-3": "Joko Susilo",
    "repair-8": "Agus Salim",
    "vol-4a": "Eko Prasetyo",
    "vol-4b": "Siti Aminah",
    "vol-5a": "Dewi Lestari",
    "vol-5b": "Rina Marlina",
    "vol-6b": "Yusuf Hakim",
    "vol-6c": "Nur Aini",
    "patrol-7": "Hendra Gunawan",
}


@dataclass(frozen=True)
class ExpectedCall:
    name: str
    args: dict[str, object]


@dataclass(frozen=True)
class Scenario:
    id: str
    trigger: str
    case: Case
    centroid: GeoPoint
    dam: Dam | None
    event: dict[str, object]
    people: tuple[Volunteer, ...]
    expected: tuple[ExpectedCall, ...]
    verdict: Verdict | None = None
    location_ok: bool | None = None

    def run_input(self) -> str:
        return render_run_input(
            RunInput(self.trigger, self.case, self.dam, self.event, NOW)
        )


@dataclass(frozen=True)
class EvidenceSetup:
    slug: str
    index: int
    verdict: Verdict
    location_ok: bool | None
    people: tuple[tuple[str, VolunteerRole], ...]
    case_type: CaseType = "dam_risk"


@dataclass(frozen=True)
class OverdueSetup:
    slug: str
    index: int
    drying_score: float
    attempt: int
    volunteers: tuple[str, ...]


def case_id(slug: str) -> str:
    return f"case-{slug}"


def cell_id(index: int) -> str:
    return f"eval-cell-{index}"


def task_id(slug: str) -> str:
    return f"task-{slug}"


def evidence_id(slug: str) -> str:
    return f"ev-{slug}"


def centroid(index: int) -> GeoPoint:
    return GeoPoint(lat=round(0.2 + index * 0.1, 4), lon=101.5)


def near(point: GeoPoint, steps: int) -> GeoPoint:
    return GeoPoint(lat=round(point.lat + steps * PERSON_STEP_DEG, 4), lon=point.lon)


def person(person_id: str, role: VolunteerRole, home: GeoPoint) -> Volunteer:
    return make_volunteer(
        id=person_id, name=PEOPLE_NAMES[person_id], role=role, home=home
    )


def check_call(slug: str) -> ExpectedCall:
    return ExpectedCall(
        "check_evidence", {"task_id": task_id(slug), "evidence_id": evidence_id(slug)}
    )


def case_call(name: str, slug: str) -> ExpectedCall:
    return ExpectedCall(name, {"case_id": case_id(slug)})


def find_call(index: int, role: VolunteerRole) -> ExpectedCall:
    return ExpectedCall("find_people", {"cell_id": cell_id(index), "role": role})


def assign_call(slug: str, assignee_id: str, task_type: TaskType) -> ExpectedCall:
    return ExpectedCall(
        "assign_task",
        {"case_id": case_id(slug), "assignee_id": assignee_id, "task_type": task_type},
    )


def evidence_risk(case_type: CaseType) -> CaseRisk:
    if case_type == "dam_risk":
        return CaseRisk(drying_score=REVIEW_DRYING, p_reignite=None)
    return CaseRisk(drying_score=None, p_reignite=RECHECK_REIGNITE)


def scenario_dam(slug: str, point: GeoPoint) -> Dam:
    return make_dam(id=f"dam-{slug}", point=near(point, 0), last_state="unknown")


def evidence_scenario(
    setup: EvidenceSetup, after_check: tuple[ExpectedCall, ...]
) -> Scenario:
    point = centroid(setup.index)
    dam = scenario_dam(setup.slug, point) if setup.case_type == "dam_risk" else None
    case = make_case(
        id=case_id(setup.slug),
        type=setup.case_type,
        cell_id=cell_id(setup.index),
        dam_id=dam.id if dam is not None else None,
        status="reviewing",
        risk=evidence_risk(setup.case_type),
        opened_at=OPENED_AT,
    )
    event = EvidenceReceived(
        evidence_id=evidence_id(setup.slug),
        task_id=task_id(setup.slug),
        case_id=case.id,
    )
    people = tuple(
        person(person_id, role, near(point, step + 1))
        for step, (person_id, role) in enumerate(setup.people)
    )
    return Scenario(
        id=setup.slug,
        trigger=EVIDENCE_TRIGGER,
        case=case,
        centroid=point,
        dam=dam,
        event=event.model_dump(mode="json"),
        people=people,
        expected=(check_call(setup.slug), *after_check),
        verdict=setup.verdict,
        location_ok=setup.location_ok,
    )


def overdue_scenario(
    setup: OverdueSetup, expected: tuple[ExpectedCall, ...]
) -> Scenario:
    point = centroid(setup.index)
    dam = scenario_dam(setup.slug, point)
    case = make_case(
        id=case_id(setup.slug),
        cell_id=cell_id(setup.index),
        dam_id=dam.id,
        status="overdue",
        risk=CaseRisk(drying_score=setup.drying_score, p_reignite=None),
        opened_at=OPENED_AT,
    )
    task = make_task(
        id=task_id(setup.slug),
        case_id=case.id,
        type="dam_check",
        assignee_id=setup.volunteers[0],
        target=dam.point,
        deadline_at=NOW - timedelta(hours=1),
        status="overdue",
        attempt=setup.attempt,
        created_at=OPENED_AT,
    )
    payload = TaskOverdue(task_id=task.id, case_id=case.id, attempt=setup.attempt)
    people = tuple(
        person(person_id, "volunteer", near(point, step))
        for step, person_id in enumerate(setup.volunteers)
    )
    return Scenario(
        id=setup.slug,
        trigger=OVERDUE_TRIGGER,
        case=case,
        centroid=point,
        dam=dam,
        event=run_event(payload, task),
        people=people,
        expected=expected,
    )


def dam_broken_assigns_repair() -> Scenario:
    slug = "dam_broken_assigns_repair"
    return evidence_scenario(
        EvidenceSetup(
            slug=slug,
            index=1,
            verdict=make_verdict(dam_state="broken", confidence=0.91),
            location_ok=True,
            people=(("repair-1", "repair_team"),),
        ),
        (find_call(1, "repair_team"), assign_call(slug, "repair-1", "dam_repair")),
    )


def dam_intact_left_for_a_person() -> Scenario:
    return evidence_scenario(
        EvidenceSetup(
            slug="dam_intact_left_for_a_person",
            index=2,
            verdict=make_verdict(
                dam_state="intact",
                reasons=["The dam wall is whole and holds water back."],
                confidence=0.93,
            ),
            location_ok=True,
            people=(("repair-2", "repair_team"),),
        ),
        (),
    )


def low_confidence_goes_to_review() -> Scenario:
    slug = "low_confidence_goes_to_review"
    return evidence_scenario(
        EvidenceSetup(
            slug=slug,
            index=3,
            verdict=make_verdict(
                dam_state="broken",
                reasons=["The photo is blurred; the dam may have a gap."],
                confidence=0.38,
                needs_human=True,
            ),
            location_ok=True,
            people=(("repair-3", "repair_team"),),
        ),
        (case_call("request_human_review", slug),),
    )


def overdue_high_risk_escalates() -> Scenario:
    slug = "overdue_high_risk_escalates"
    return overdue_scenario(
        OverdueSetup(
            slug=slug,
            index=4,
            drying_score=HIGH_DRYING,
            attempt=1,
            volunteers=("vol-4a", "vol-4b"),
        ),
        (case_call("escalate", slug),),
    )


def overdue_low_risk_reassigns() -> Scenario:
    slug = "overdue_low_risk_reassigns"
    return overdue_scenario(
        OverdueSetup(
            slug=slug,
            index=5,
            drying_score=LOW_DRYING,
            attempt=1,
            volunteers=("vol-5a", "vol-5b"),
        ),
        (find_call(5, "volunteer"), assign_call(slug, "vol-5b", "dam_check")),
    )


def second_overdue_escalates() -> Scenario:
    slug = "second_overdue_escalates"
    return overdue_scenario(
        OverdueSetup(
            slug=slug,
            index=6,
            drying_score=LOW_DRYING,
            attempt=2,
            volunteers=("vol-6b", "vol-6c"),
        ),
        (case_call("escalate", slug),),
    )


def recheck_smoke_escalates() -> Scenario:
    slug = "recheck_smoke_escalates"
    return evidence_scenario(
        EvidenceSetup(
            slug=slug,
            index=7,
            case_type="reignition",
            verdict=make_verdict(
                subject="burned_peat",
                dam_state="not_applicable",
                smoke="wisps",
                reasons=["Thin smoke rises from the burned peat surface."],
                confidence=0.86,
            ),
            location_ok=True,
            people=(("patrol-7", "patrol"),),
        ),
        (case_call("escalate", slug),),
    )


def location_mismatch_goes_to_review() -> Scenario:
    slug = "location_mismatch_goes_to_review"
    return evidence_scenario(
        EvidenceSetup(
            slug=slug,
            index=8,
            verdict=make_verdict(dam_state="broken", confidence=0.9),
            location_ok=False,
            people=(("repair-8", "repair_team"),),
        ),
        (case_call("request_human_review", slug),),
    )


def drawn_square(west: float, south: float, side: float) -> dict[str, object]:
    east, north = round(west + side, 4), round(south + side, 4)
    ring = [[west, south], [east, south], [east, north], [west, north], [west, south]]
    return {"type": "Polygon", "coordinates": [ring]}


def area_check_ranks_the_drawn_area() -> Scenario:
    slug = "area_check_ranks_the_drawn_area"
    point = centroid(9)
    dam = scenario_dam(slug, point)
    case = make_case(
        id=case_id(slug),
        cell_id=cell_id(9),
        dam_id=dam.id,
        risk=CaseRisk(drying_score=LOW_DRYING, p_reignite=None),
        opened_at=OPENED_AT,
    )
    area = drawn_square(102.0, 0.5, 0.09)
    return Scenario(
        id=slug,
        trigger=AREA_TRIGGER,
        case=case,
        centroid=point,
        dam=dam,
        event={"case_id": case.id, "area": area},
        people=(),
        expected=(
            ExpectedCall("run_area_ranking", {"coordinates": area["coordinates"]}),
        ),
    )


def build_scenarios() -> list[Scenario]:
    return [
        dam_broken_assigns_repair(),
        dam_intact_left_for_a_person(),
        low_confidence_goes_to_review(),
        overdue_high_risk_escalates(),
        overdue_low_risk_reassigns(),
        second_overdue_escalates(),
        recheck_smoke_escalates(),
        location_mismatch_goes_to_review(),
        area_check_ranks_the_drawn_area(),
    ]
