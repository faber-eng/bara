from datetime import UTC, datetime
from pathlib import Path

import pytest

from adapters.firestore_repos import ResetRepository
from contracts import (
    AgentRun,
    Case,
    ClockSettings,
    Contact,
    Dam,
    Escalation,
    Evidence,
    Message,
    Task,
    Volunteer,
)
from domain.clock import Clock
from domain.scenario import load_scenario
from scenario_reset import ScenarioResetter
from tests.fakes import (
    InMemoryClockStore,
    InMemoryCollection,
    make_agent_run,
    make_case,
    make_escalation,
    make_evidence,
    make_message,
    make_task,
    make_volunteer,
)

DATA = Path(__file__).resolve().parents[3] / "data"
REAL_NOW = datetime(2026, 10, 17, 12, 0, tzinfo=UTC)


class World:
    def __init__(self):
        self.volunteers = InMemoryCollection(Volunteer)
        self.contacts = InMemoryCollection(Contact)
        self.dams = InMemoryCollection(Dam)
        self.cases = InMemoryCollection(Case)
        self.tasks = InMemoryCollection(Task)
        self.evidence = InMemoryCollection(Evidence)
        self.messages = InMemoryCollection(Message)
        self.escalations = InMemoryCollection(Escalation)
        self.runs: dict[str, InMemoryCollection] = {}
        self.clock_store = InMemoryClockStore(
            ClockSettings(offset_seconds=48 * 3600, updated_by="judge")
        )
        self.clock = Clock(self.clock_store, lambda: REAL_NOW)
        self.resetter = ScenarioResetter(
            repository=ResetRepository(
                volunteers=self.volunteers,
                contacts=self.contacts,
                dams=self.dams,
                cases=self.cases,
                tasks=self.tasks,
                evidence=self.evidence,
                messages=self.messages,
                escalations=self.escalations,
                agent_runs_for=self.runs_for,
            ),
            clock=self.clock,
            scenario=load_scenario(DATA),
        )

    def runs_for(self, case_id: str) -> InMemoryCollection:
        return self.runs.setdefault(case_id, InMemoryCollection(AgentRun))

    def state(self) -> dict:
        collections = {
            "volunteers": self.volunteers,
            "contacts": self.contacts,
            "dams": self.dams,
            "cases": self.cases,
            "tasks": self.tasks,
            "evidence": self.evidence,
            "messages": self.messages,
            "escalations": self.escalations,
        }
        dump = {
            name: sorted(item.model_dump_json() for item in collection.where())
            for name, collection in collections.items()
        }
        dump["agent_runs"] = {
            case_id: sorted(run.model_dump_json() for run in runs.where())
            for case_id, runs in self.runs.items()
            if runs.where()
        }
        dump["clock"] = self.clock_store.get().model_dump_json()
        return dump

    def add_example_case(self, case_id="c-ex", assignee="vol-ari"):
        self.cases.put(
            case_id, make_case(id=case_id, example=True, dam_id="dam-riau-009")
        )
        self.tasks.put(
            f"t-{case_id}",
            make_task(id=f"t-{case_id}", case_id=case_id, assignee_id=assignee),
        )
        self.evidence.put(
            f"e-{case_id}",
            make_evidence(
                id=f"e-{case_id}",
                case_id=case_id,
                task_id=f"t-{case_id}",
                uploaded_by=assignee,
            ),
        )
        self.messages.put(
            f"m-{case_id}",
            make_message(id=f"m-{case_id}", case_id=case_id, to_id=assignee),
        )
        self.escalations.put(
            f"x-{case_id}",
            make_escalation(
                id=f"x-{case_id}", case_id=case_id, contact_id="contact-daops-pekanbaru"
            ),
        )
        self.runs_for(case_id).put("r1", make_agent_run(id="r1"))


def test_a_reset_of_an_empty_project_seeds_people_contact_and_forty_dams():
    world = World()

    summary = world.resetter.reset("reset")

    assert len(world.volunteers.where()) == 10
    assert len(world.contacts.where()) == 1
    assert len(world.dams.where()) == 40
    assert summary.seeded == {"volunteers": 10, "contacts": 1, "dams": 40}


def test_the_clock_offset_goes_back_to_zero():
    world = World()

    world.resetter.reset("reset")

    assert world.clock.offset_seconds() == 0


def test_an_example_case_with_its_children_and_agent_runs_is_deleted():
    world = World()
    world.resetter.reset("reset")
    world.add_example_case()

    summary = world.resetter.reset("reset")

    assert world.cases.where() == []
    assert world.tasks.where() == []
    assert world.evidence.where() == []
    assert world.messages.where() == []
    assert world.escalations.where() == []
    assert world.runs_for("c-ex").where() == []
    assert summary.deleted["cases"] == 1


def test_a_real_volunteer_with_a_task_and_evidence_survives_a_reset():
    world = World()
    world.volunteers.put("real-1", make_volunteer(id="real-1", example=False))
    world.cases.put("c-real", make_case(id="c-real", example=False))
    world.tasks.put(
        "t-real", make_task(id="t-real", case_id="c-real", assignee_id="real-1")
    )
    world.evidence.put(
        "e-real",
        make_evidence(
            id="e-real", case_id="c-real", task_id="t-real", uploaded_by="real-1"
        ),
    )

    world.resetter.reset("reset")

    assert world.volunteers.get("real-1") is not None
    assert world.tasks.get("t-real") is not None
    assert world.evidence.get("e-real") is not None
    assert world.cases.get("c-real") is not None


def test_an_example_case_that_a_real_volunteer_works_on_survives_with_its_runs():
    world = World()
    world.volunteers.put("real-1", make_volunteer(id="real-1", example=False))
    world.add_example_case("c-shared", assignee="real-1")

    world.resetter.reset("reset")

    assert world.cases.get("c-shared") is not None
    assert world.runs_for("c-shared").get("r1") is not None


def test_two_resets_give_identical_state_whatever_happened_in_between():
    world = World()
    world.resetter.reset("reset")
    first = world.state()

    world.add_example_case()
    world.dams.put(
        "dam-riau-009",
        world.dams.get("dam-riau-009").model_copy(update={"last_state": "intact"}),
    )
    world.volunteers.put(
        "vol-ari",
        world.volunteers.get("vol-ari").model_copy(update={"available": False}),
    )
    world.clock_store.add_seconds(3600, "judge")
    world.resetter.reset("reset")
    second = world.state()
    world.resetter.reset("reset")
    third = world.state()

    assert first == second == third


def test_a_plan_deletes_and_seeds_nothing():
    world = World()
    world.resetter.reset("reset")
    world.add_example_case()
    before = world.state()

    summary = world.resetter.plan()

    assert world.state() == before
    assert summary.deleted["cases"] == 1
    assert summary.seeded["dams"] == 40


@pytest.mark.parametrize("count", [1, 3])
def test_the_summary_counts_every_deleted_collection(count):
    world = World()
    world.resetter.reset("reset")
    for n in range(count):
        world.add_example_case(f"c{n}")

    summary = world.resetter.plan()

    assert summary.deleted["cases"] == count
    assert summary.deleted["tasks"] == count
    assert summary.deleted["volunteers"] == 10
