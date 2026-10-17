import os

import pytest
from google.api_core import exceptions as gax

from adapters.store import DocumentNotFound, Filter, FirestoreCollection
from contracts import Task
from tests.fakes import InMemoryCollection, StubFirestoreClient, make_task


@pytest.fixture(params=["memory", "firestore"])
def tasks(request):
    if request.param == "memory":
        return InMemoryCollection(Task)
    return FirestoreCollection(StubFirestoreClient(), "tasks", Task)


def test_put_then_get_round_trips(tasks):
    task = make_task()

    tasks.put(task.id, task)

    assert tasks.get(task.id) == task


def test_get_of_a_missing_document_is_none(tasks):
    assert tasks.get("missing") is None


def test_put_overwrites(tasks):
    tasks.put("t1", make_task())

    tasks.put("t1", make_task(status="done"))

    assert tasks.get("t1").status == "done"


def test_create_if_absent_is_true_then_false(tasks):
    first = make_task(attempt=1)
    second = make_task(attempt=2)

    assert tasks.create_if_absent("t1", first) is True
    assert tasks.create_if_absent("t1", second) is False
    assert tasks.get("t1") == first


def test_update_changes_only_the_given_fields(tasks):
    tasks.put("t1", make_task())

    tasks.update("t1", {"status": "overdue"})

    updated = tasks.get("t1")
    assert updated.status == "overdue"
    assert updated.assignee_id == "v1"


def test_update_of_a_missing_document_raises(tasks):
    with pytest.raises(DocumentNotFound):
        tasks.update("missing", {"status": "done"})


def test_where_equality_filters(tasks):
    tasks.put("a", make_task(id="a", status="open"))
    tasks.put("b", make_task(id="b", status="done"))

    found = tasks.where(Filter("status", "==", "open"))

    assert [task.id for task in found] == ["a"]


def test_where_combines_filters_with_and(tasks):
    tasks.put("a", make_task(id="a", status="open", attempt=1))
    tasks.put("b", make_task(id="b", status="open", attempt=2))

    found = tasks.where(Filter("status", "==", "open"), Filter("attempt", ">=", 2))

    assert [task.id for task in found] == ["b"]


def test_where_with_no_match_is_empty(tasks):
    tasks.put("a", make_task(id="a"))

    assert tasks.where(Filter("status", "==", "cancelled")) == []


def test_firestore_collection_names_the_collection_it_writes():
    client = StubFirestoreClient()

    FirestoreCollection(client, "tasks", Task).put("t1", make_task())

    assert list(client.stores["tasks"]) == ["t1"]
    assert client.stores["tasks"]["t1"]["target"] == {"lat": 0.5, "lon": 101.4}


def test_firestore_collection_does_not_swallow_other_errors():
    class BrokenClient(StubFirestoreClient):
        def collection(self, name):
            raise gax.PermissionDenied("no")

    with pytest.raises(gax.PermissionDenied):
        FirestoreCollection(BrokenClient(), "tasks", Task).get("t1")


@pytest.mark.live
def test_live_firestore_reads_a_missing_document():
    from google.cloud import firestore

    client = firestore.Client(project=os.environ["GOOGLE_CLOUD_PROJECT"])

    assert FirestoreCollection(client, "bara_live_probe", Task).get("none") is None
