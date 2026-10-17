import asyncio
import os
import uuid
from datetime import UTC, datetime

import pytest
from google.cloud import tasks_v2

from adapters.cells import CellRepository
from adapters.channels import WebChannel
from adapters.factory import DEADLINE_QUEUE, utcnow
from adapters.firestore_repos import (
    CASES,
    MESSAGES,
    TASKS,
    CaseRepository,
    CaseworkStore,
    DamRepository,
    TaskRepository,
    VolunteerRepository,
)
from adapters.gemini import ModelGateway, build_vertex_clients
from adapters.tasks import DeadlineScheduler
from casework.assignment import AssignmentRequest, TaskAssigner
from casework.messenger import Messenger, sentence_count
from config import load_settings, region_timezones
from contracts import Case, Dam, Message, Task, Volunteer
from domain.clock import Clock
from tests.fakes import (
    FakeWarehouse,
    InMemoryClockStore,
    InMemoryCollection,
    InMemoryTransactor,
    make_case,
    make_dam,
    make_volunteer,
)


def collection_with(model, items, key):
    collection = InMemoryCollection(model)
    for item in items:
        collection.put(getattr(item, key), item)
    return collection


@pytest.mark.live
def test_a_live_assignment_writes_an_indonesian_message_and_a_cloud_task():
    settings = load_settings(os.environ)
    api_url = os.environ.get("BARA_API_URL", "https://bara-api.invalid")
    client = tasks_v2.CloudTasksClient()
    scheduler = DeadlineScheduler(
        client,
        project=settings.project,
        location=settings.region,
        queue=DEADLINE_QUEUE,
        api_url=api_url,
        invoker_email=settings.tasks_invoker_email,
    )
    clock = Clock(InMemoryClockStore(None), utcnow)
    tasks = InMemoryCollection(Task)
    messages = InMemoryCollection(Message)
    cases = collection_with(Case, [make_case(id="case-live", dam_id="dam-live")], "id")
    gateway = ModelGateway(settings.models, build_vertex_clients(settings))
    assigner = TaskAssigner(
        cases=CaseRepository(cases),
        volunteers=VolunteerRepository(
            collection_with(Volunteer, [make_volunteer(id="v-live")], "id")
        ),
        dams=DamRepository(collection_with(Dam, [make_dam(id="dam-live")], "id")),
        cells=CellRepository(FakeWarehouse()),
        tasks=TaskRepository(tasks),
        casework=CaseworkStore(
            InMemoryTransactor({CASES: cases, TASKS: tasks, MESSAGES: messages})
        ),
        channel=WebChannel(clock, lambda: "msg-live"),
        messenger=Messenger(gateway, settings.default_language),
        scheduler=scheduler,
        clock=clock,
        default_deadline_hours=settings.tasks.default_deadline_hours,
        timezones=region_timezones(settings.config_dir),
        new_id=lambda: f"live-{uuid.uuid4().hex[:12]}",
    )
    before = datetime.now(UTC)

    assignment = asyncio.run(
        assigner.assign(
            AssignmentRequest(
                case_id="case-live",
                assignee_id="v-live",
                task_type="dam_check",
                instructions_hint="Check whether the dam wall is broken.",
                deadline_hours=None,
            )
        )
    )

    task = assignment.task
    message = assignment.message
    print(task.model_dump_json(indent=2))
    print(message.model_dump_json(indent=2))
    try:
        cloud_task = client.get_task(name=task.cloud_task_name)
        assert cloud_task.schedule_time == task.deadline_at
        assert cloud_task.http_request.url.endswith(f"/api/internal/deadline/{task.id}")
    finally:
        scheduler.cancel(task.cloud_task_name)
    assert tasks.get(task.id) == task
    assert (task.deadline_at - before).total_seconds() >= 72 * 3600
    assert messages.get("msg-live") == message
    assert message.lang == "id"
    assert 1 <= sentence_count(message.text) <= 3
    assert "dam-live" in message.text
    assert cases.get("case-live").status == "assigned"
