from adapters.firestore_repos import ResetRepository
from contracts import Case, Contact, Dam, Escalation, Evidence, Message, Task, Volunteer
from domain.reset_scope import ResetSnapshot, plan_reset
from tests.fakes import (
    InMemoryCollection,
    make_case,
    make_contact,
    make_dam,
    make_escalation,
    make_evidence,
    make_message,
    make_task,
    make_volunteer,
)


def snapshot(**parts):
    empty = {
        "volunteers": [],
        "contacts": [],
        "dams": [],
        "cases": [],
        "tasks": [],
        "evidence": [],
        "messages": [],
        "escalations": [],
    }
    return ResetSnapshot(**{**empty, **parts})


def scenario_case(case_id="c-ex"):
    return {
        "case": make_case(id=case_id, example=True),
        "task": make_task(id=f"t-{case_id}", case_id=case_id, assignee_id="v-ex"),
        "evidence": make_evidence(
            id=f"e-{case_id}",
            case_id=case_id,
            task_id=f"t-{case_id}",
            uploaded_by="v-ex",
        ),
        "message": make_message(id=f"m-{case_id}", case_id=case_id, to_id="v-ex"),
        "escalation": make_escalation(
            id=f"x-{case_id}", case_id=case_id, contact_id="ct-ex"
        ),
    }


def example_world(case):
    return snapshot(
        volunteers=[make_volunteer(id="v-ex", example=True)],
        contacts=[make_contact(id="ct-ex")],
        dams=[make_dam(id="d-ex")],
        cases=[case["case"]],
        tasks=[case["task"]],
        evidence=[case["evidence"]],
        messages=[case["message"]],
        escalations=[case["escalation"]],
    )


def test_example_people_dams_and_a_clean_example_case_are_selected():
    case = scenario_case()

    scope = plan_reset(example_world(case))

    assert scope.volunteer_ids == {"v-ex"}
    assert scope.contact_ids == {"ct-ex"}
    assert scope.dam_ids == {"d-ex"}
    assert scope.case_ids == {"c-ex"}
    assert scope.task_ids == {"t-c-ex"}
    assert scope.evidence_ids == {"e-c-ex"}
    assert scope.message_ids == {"m-c-ex"}
    assert scope.escalation_ids == {"x-c-ex"}


def test_an_example_case_with_a_real_volunteers_task_is_kept_whole():
    case = scenario_case()
    real_task = make_task(id="t-real", case_id="c-ex", assignee_id="v-real")
    world = example_world(case)
    world = snapshot(
        **{**world.__dict__, "tasks": [case["task"], real_task]},
    )

    scope = plan_reset(world)

    assert scope.case_ids == set()
    assert scope.task_ids == set()
    assert scope.evidence_ids == set()
    assert scope.message_ids == set()
    assert scope.escalation_ids == set()
    assert scope.volunteer_ids == {"v-ex"}


def test_evidence_uploaded_by_a_real_uid_keeps_the_case():
    case = scenario_case()
    case["evidence"] = make_evidence(
        id="e-real", case_id="c-ex", task_id="t-c-ex", uploaded_by="v-real"
    )

    scope = plan_reset(example_world(case))

    assert scope.case_ids == set()


def test_a_message_to_a_real_uid_keeps_the_case():
    case = scenario_case()
    case["message"] = make_message(id="m-real", case_id="c-ex", to_id="v-real")

    assert plan_reset(example_world(case)).case_ids == set()


def test_a_real_case_is_never_selected():
    real = make_case(id="c-real", example=False)
    task = make_task(id="t1", case_id="c-real", assignee_id="v-ex")

    scope = plan_reset(snapshot(cases=[real], tasks=[task]))

    assert scope.case_ids == set()
    assert scope.task_ids == set()


def test_real_people_and_dams_are_never_selected():
    world = snapshot(
        volunteers=[make_volunteer(id="v-real", example=False)],
        contacts=[make_contact(id="ct-real", example=False)],
        dams=[make_dam(id="d-real", example=False)],
    )

    scope = plan_reset(world)

    assert scope.volunteer_ids == set()
    assert scope.contact_ids == set()
    assert scope.dam_ids == set()


def test_planning_twice_gives_the_same_scope():
    world = example_world(scenario_case())

    assert plan_reset(world) == plan_reset(world)


def test_two_cases_one_kept_one_selected():
    clean = scenario_case("c-a")
    shared = scenario_case("c-b")
    real_task = make_task(id="t-real", case_id="c-b", assignee_id="v-real")
    world = snapshot(
        volunteers=[make_volunteer(id="v-ex", example=True)],
        contacts=[make_contact(id="ct-ex")],
        cases=[clean["case"], shared["case"]],
        tasks=[clean["task"], shared["task"], real_task],
        evidence=[clean["evidence"], shared["evidence"]],
        messages=[clean["message"], shared["message"]],
        escalations=[clean["escalation"], shared["escalation"]],
    )

    scope = plan_reset(world)

    assert scope.case_ids == {"c-a"}
    assert scope.task_ids == {"t-c-a"}
    assert scope.evidence_ids == {"e-c-a"}


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
        self.repo = ResetRepository(
            volunteers=self.volunteers,
            contacts=self.contacts,
            dams=self.dams,
            cases=self.cases,
            tasks=self.tasks,
            evidence=self.evidence,
            messages=self.messages,
            escalations=self.escalations,
        )


def seed_case(world, case_id, example, assignee="v-ex"):
    world.cases.put(case_id, make_case(id=case_id, example=example))
    world.tasks.put(
        f"t-{case_id}",
        make_task(id=f"t-{case_id}", case_id=case_id, assignee_id=assignee),
    )
    world.evidence.put(
        f"e-{case_id}",
        make_evidence(
            id=f"e-{case_id}",
            case_id=case_id,
            task_id=f"t-{case_id}",
            uploaded_by=assignee,
        ),
    )
    world.messages.put(
        f"m-{case_id}", make_message(id=f"m-{case_id}", case_id=case_id, to_id=assignee)
    )
    world.escalations.put(
        f"x-{case_id}",
        make_escalation(id=f"x-{case_id}", case_id=case_id, contact_id="ct-ex"),
    )


def test_the_repository_snapshot_loads_example_rows_and_their_children():
    world = World()
    world.volunteers.put("v-ex", make_volunteer(id="v-ex", example=True))
    world.volunteers.put("v-real", make_volunteer(id="v-real", example=False))
    world.contacts.put("ct-ex", make_contact(id="ct-ex"))
    world.dams.put("d-ex", make_dam(id="d-ex"))
    world.dams.put("d-real", make_dam(id="d-real", example=False))
    seed_case(world, "c-ex", example=True)
    seed_case(world, "c-real", example=False, assignee="v-real")

    loaded = world.repo.snapshot()

    assert {v.id for v in loaded.volunteers} == {"v-ex"}
    assert {d.id for d in loaded.dams} == {"d-ex"}
    assert {c.id for c in loaded.cases} == {"c-ex"}
    assert {t.id for t in loaded.tasks} == {"t-c-ex"}
    assert {e.id for e in loaded.evidence} == {"e-c-ex"}


def test_a_real_volunteer_with_a_task_on_an_example_case_survives_the_reset():
    world = World()
    world.volunteers.put("v-ex", make_volunteer(id="v-ex", example=True))
    world.volunteers.put("v-real", make_volunteer(id="v-real", example=False))
    seed_case(world, "c-ex", example=True)
    world.tasks.put(
        "t-real", make_task(id="t-real", case_id="c-ex", assignee_id="v-real")
    )
    world.evidence.put(
        "e-real",
        make_evidence(
            id="e-real", case_id="c-ex", task_id="t-real", uploaded_by="v-real"
        ),
    )

    scope = plan_reset(world.repo.snapshot())

    assert scope.volunteer_ids == {"v-ex"}
    assert scope.case_ids == set()
    assert "t-real" not in scope.task_ids
    assert "e-real" not in scope.evidence_ids


def test_the_snapshot_handles_more_cases_than_one_in_query_chunk():
    world = World()
    world.volunteers.put("v-ex", make_volunteer(id="v-ex", example=True))
    world.contacts.put("ct-ex", make_contact(id="ct-ex"))
    for index in range(75):
        seed_case(world, f"c-{index}", example=True)

    loaded = world.repo.snapshot()

    assert len(loaded.cases) == 75
    assert len(loaded.tasks) == 75
    assert len(plan_reset(loaded).case_ids) == 75
