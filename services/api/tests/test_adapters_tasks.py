import os
from datetime import UTC, datetime, timedelta, timezone
from types import SimpleNamespace

import pytest
from google.api_core import exceptions as gax
from google.cloud import tasks_v2

from adapters.tasks import DeadlineScheduler, InvalidTaskId

QUEUE_PATH = "projects/p/locations/asia-southeast1/queues/task-deadlines"
INVOKER = "bara-tasks-invoker@p.iam.gserviceaccount.com"


class RecordingTasksClient:
    def __init__(self):
        self.created = []
        self.deleted = []
        self.missing = False

    def queue_path(self, project, location, queue):
        return f"projects/{project}/locations/{location}/queues/{queue}"

    def create_task(self, *, parent, task):
        self.created.append((parent, task))
        return SimpleNamespace(name=f"{parent}/tasks/generated-1")

    def delete_task(self, *, name):
        self.deleted.append(name)
        if self.missing:
            raise gax.NotFound("gone")


def make_scheduler(client=None):
    client = client or RecordingTasksClient()
    scheduler = DeadlineScheduler(
        client,
        project="p",
        location="asia-southeast1",
        queue="task-deadlines",
        api_url="https://api.example.test",
        invoker_email=INVOKER,
    )
    return scheduler, client


DEADLINE = datetime(2026, 10, 20, 12, 0, tzinfo=UTC)


def test_schedule_creates_one_http_post_on_the_queue():
    scheduler, client = make_scheduler()

    scheduler.schedule("t1", DEADLINE)

    parent, task = client.created[0]
    assert parent == QUEUE_PATH
    assert task.http_request.http_method == tasks_v2.HttpMethod.POST
    assert task.http_request.url == "https://api.example.test/api/internal/deadline/t1"


def test_schedule_uses_the_invoker_account_for_oidc():
    scheduler, client = make_scheduler()

    scheduler.schedule("t1", DEADLINE)

    token = client.created[0][1].http_request.oidc_token
    assert token.service_account_email == INVOKER
    assert token.audience == "https://api.example.test"


def test_schedule_time_is_the_deadline():
    scheduler, client = make_scheduler()

    scheduler.schedule("t1", DEADLINE)

    assert client.created[0][1].schedule_time == DEADLINE


def test_schedule_time_converts_other_zones_to_the_same_instant():
    scheduler, client = make_scheduler()
    jakarta = timezone(timedelta(hours=7))

    scheduler.schedule("t1", DEADLINE.astimezone(jakarta))

    assert client.created[0][1].schedule_time == DEADLINE


def test_schedule_returns_the_cloud_task_name():
    scheduler, _ = make_scheduler()

    assert scheduler.schedule("t1", DEADLINE) == f"{QUEUE_PATH}/tasks/generated-1"


def test_schedule_rejects_a_naive_deadline():
    scheduler, client = make_scheduler()

    with pytest.raises(ValueError):
        scheduler.schedule("t1", datetime(2026, 10, 20, 12, 0))

    assert client.created == []


@pytest.mark.parametrize("task_id", ["", "a/b", "a b", "../x", "t1?x=1"])
def test_schedule_rejects_task_ids_that_would_change_the_path(task_id):
    scheduler, client = make_scheduler()

    with pytest.raises(InvalidTaskId):
        scheduler.schedule(task_id, DEADLINE)

    assert client.created == []


def test_cancel_deletes_the_named_task():
    scheduler, client = make_scheduler()

    scheduler.cancel(f"{QUEUE_PATH}/tasks/generated-1")

    assert client.deleted == [f"{QUEUE_PATH}/tasks/generated-1"]


def test_cancel_of_a_missing_task_is_a_no_op():
    client = RecordingTasksClient()
    client.missing = True
    scheduler, _ = make_scheduler(client)

    scheduler.cancel(f"{QUEUE_PATH}/tasks/gone")


def test_cancel_with_no_name_does_nothing():
    scheduler, client = make_scheduler()

    scheduler.cancel(None)

    assert client.deleted == []


@pytest.mark.live
def test_live_queue_exists():
    project = os.environ["GOOGLE_CLOUD_PROJECT"]
    client = tasks_v2.CloudTasksClient()

    queue = client.get_queue(
        name=client.queue_path(project, "asia-southeast1", "task-deadlines")
    )

    assert queue.name.endswith("task-deadlines")
