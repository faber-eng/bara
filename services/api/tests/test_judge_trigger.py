from datetime import UTC, datetime

import pytest
from fastapi.testclient import TestClient

import main
from adapters.firestore_repos import RankedDamRepository, RankingRepository
from adapters.gemini import ModelGateway
from config import JudgeMode
from contracts import DryingRankedEvent, RankedCell, RankedDam
from tests.fakes import (
    FakeModels,
    FakeVerifier,
    InMemoryCollection,
    make_ranked_cell,
    make_ranked_dam,
)
from trigger import JudgeTrigger

NOW = datetime(2026, 10, 17, 13, 0, tzinfo=UTC)


class FixedClock:
    def now(self):
        return NOW


class RecordingPublisher:
    def __init__(self, error: Exception | None = None):
        self.published = []
        self._error = error

    def publish(self, topic, event):
        if self._error:
            raise self._error
        self.published.append((topic, event))
        return "msg-1"


def make_client(settings, publisher=None, with_rankings=True, judge=True):
    configured = settings.model_copy(
        update={"judge_mode": JudgeMode(enabled=judge, max_resets_per_hour=20)}
    )
    cells = InMemoryCollection(RankedCell)
    dams = InMemoryCollection(RankedDam)
    if with_rankings:
        for rank in range(1, 4):
            cells.put(f"c{rank}", make_ranked_cell(cell_id=f"c{rank}", rank=rank))
        dams.put("d1", make_ranked_dam(dam_id="d1", rank=1))
    publisher = publisher or RecordingPublisher()
    trigger = JudgeTrigger(
        rankings=RankingRepository(lambda region: cells),
        ranked_dams=RankedDamRepository(lambda region: dams),
        publisher=publisher,
        clock=FixedClock(),
        new_id=lambda: "evt-fixed",
        region="riau",
    )
    gateway = ModelGateway(
        configured.models, {"reasoning": FakeModels([]), "fast": FakeModels([])}
    )
    verifier = FakeVerifier(
        {
            "ops-claim": {"uid": "u1", "role": "ops"},
            "volunteer": {"uid": "u2", "role": "volunteer"},
            "plain": {"uid": "u3"},
        }
    )
    app = main.build_app(configured, gateway, verifier)
    app.state.trigger = trigger
    return TestClient(app), publisher


def trigger(client, token="ops-claim", headers=None):
    all_headers = {"Authorization": f"Bearer {token}", **(headers or {})}
    return client.post(
        "/api/judge/trigger", json={"event": "drying.ranked"}, headers=all_headers
    )


def test_an_ops_user_with_a_claim_gets_202_and_the_event_is_published(settings):
    client, publisher = make_client(settings, judge=False)

    response = trigger(client)

    assert response.status_code == 202
    assert response.json() == {"event": "drying.ranked", "message_id": "msg-1"}
    topic, event = publisher.published[0]
    assert topic == "drying.ranked"
    assert isinstance(event, DryingRankedEvent)
    assert event.example is True
    assert event.id == "evt-fixed"
    assert event.payload.week == "2026-W42"
    assert [ref.cell_id for ref in event.payload.top_cells] == ["c1", "c2", "c3"]
    assert [ref.dam_id for ref in event.payload.top_dams] == ["d1"]


def test_the_judge_header_works_while_judge_mode_is_on(settings):
    client, publisher = make_client(settings, judge=True)

    response = trigger(client, "plain", {"X-Bara-Role": "judge"})

    assert response.status_code == 202
    assert len(publisher.published) == 1


@pytest.mark.parametrize("token", ["volunteer", "plain"])
def test_other_roles_are_403_and_nothing_is_published(settings, token):
    client, publisher = make_client(settings, judge=False)

    assert trigger(client, token).status_code == 403
    assert publisher.published == []


def test_the_judge_header_is_ignored_with_judge_mode_off(settings):
    client, publisher = make_client(settings, judge=False)

    response = trigger(client, "plain", {"X-Bara-Role": "judge"})

    assert response.status_code == 403
    assert publisher.published == []


def test_without_a_token_it_is_401(settings):
    client, _ = make_client(settings)

    response = client.post("/api/judge/trigger", json={"event": "drying.ranked"})

    assert response.status_code == 401


def test_no_rankings_is_409(settings):
    client, publisher = make_client(settings, with_rankings=False)

    assert trigger(client).status_code == 409
    assert publisher.published == []


def test_a_publish_failure_is_502(settings):
    client, _ = make_client(
        settings, publisher=RecordingPublisher(TimeoutError("down"))
    )

    assert trigger(client).status_code == 502


def test_an_event_other_than_drying_ranked_is_422(settings):
    client, _ = make_client(settings)

    response = client.post(
        "/api/judge/trigger",
        json={"event": "fire.quiet"},
        headers={"Authorization": "Bearer ops-claim"},
    )

    assert response.status_code == 422
