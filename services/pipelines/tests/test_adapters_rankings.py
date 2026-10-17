import json
from datetime import UTC, date, datetime

import pytest

from adapters.events import EventPublisher, UnpublishableTopic
from adapters.rankings_store import BATCH_LIMIT, RankingsStore
from domain.rankings import ranking_event
from tests.fakes import FakeFirestore, FakePubSub


def documents(prefix, count, start=1):
    return {f"{prefix}-{n}": {"n": n} for n in range(start, start + count)}


def test_replace_writes_new_docs_then_deletes_only_the_stale_ones():
    client = FakeFirestore(
        {"rankings/riau/cells/old-1": {}, "rankings/riau/cells/keep": {"v": 0}}
    )
    store = RankingsStore(client)

    result = store.replace("riau", "cells", {"keep": {"v": 1}, "new": {"v": 2}})

    assert client.docs == {
        "rankings/riau/cells/keep": {"v": 1},
        "rankings/riau/cells/new": {"v": 2},
    }
    assert (result.written, result.deleted) == (2, 1)
    operations = [op for commit in client.commits for op, _ in commit]
    assert operations.index("delete") > max(
        i for i, op in enumerate(operations) if op == "set"
    )


def test_replace_leaves_other_regions_and_collections_alone():
    client = FakeFirestore(
        {
            "rankings/congo/cells/a": {},
            "rankings/riau/dams/d": {},
            "rankings/riau/cells/x": {},
        }
    )

    RankingsStore(client).replace("riau", "cells", {"y": {}})

    assert set(client.docs) == {
        "rankings/congo/cells/a",
        "rankings/riau/dams/d",
        "rankings/riau/cells/y",
    }


def test_replace_splits_writes_into_batches_within_the_firestore_limit():
    client = FakeFirestore()

    RankingsStore(client).replace("riau", "cells", documents("c", BATCH_LIMIT + 5))

    assert all(len(commit) <= BATCH_LIMIT for commit in client.commits)
    assert len(client.docs) == BATCH_LIMIT + 5


def test_replace_with_nothing_clears_the_collection():
    client = FakeFirestore({"rankings/riau/dams/d": {}})

    result = RankingsStore(client).replace("riau", "dams", {})

    assert client.docs == {}
    assert result.deleted == 1


def make_event():
    return ranking_event(
        "riau",
        date(2026, 10, 12),
        [],
        [],
        "evt-1",
        datetime(2026, 10, 17, tzinfo=UTC),
    )


def test_publisher_sends_the_event_json_to_its_topic_and_returns_the_message_id():
    client = FakePubSub(message_id="m-42")

    message_id = EventPublisher(client, "p").publish(make_event())

    path, data, attributes = client.published[0]
    assert message_id == "m-42"
    assert path == "projects/p/topics/drying.ranked"
    assert attributes == {"type": "drying.ranked"}
    body = json.loads(data)
    assert body["type"] == "drying.ranked"
    assert body["example"] is False


def test_publisher_refuses_a_type_that_is_not_an_event_topic():
    event = make_event()
    object.__setattr__(event, "type", "nope")

    with pytest.raises(UnpublishableTopic):
        EventPublisher(FakePubSub(), "p").publish(event)
