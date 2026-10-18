from fastapi.testclient import TestClient

from adapters.firestore_repos import CaseRepository, RankingRepository
from casework.trigger_gate import TriggerGate
from contracts import Case, RankedCell
from tests.fakes import (
    InMemoryCollection,
    InMemoryTriggerGateStore,
    make_case,
    make_ranked_cell,
)
from tests.test_judge_trigger import (
    NOW,
    FixedClock,
    MovingClock,
    RecordingPublisher,
    make_client,
)
from trigger import AreaRequest

OPS = {"Authorization": "Bearer ops-claim"}


def make_send_client(settings, cases=(), publisher=None, example=True):
    client, _ = make_client(settings)
    cells = InMemoryCollection(RankedCell)
    cells.put(
        "riau-1-1", make_ranked_cell(cell_id="riau-1-1", rank=4, drying_score=93.5)
    )
    cells.put("riau-2-2", make_ranked_cell(cell_id="riau-2-2", rank=5))
    case_store = InMemoryCollection(Case)
    for case in cases:
        case_store.put(case.id, case)
    publisher = publisher or RecordingPublisher()
    app = client.app
    app.state.area_request = AreaRequest(
        rankings=RankingRepository(lambda region: cells),
        cases=CaseRepository(case_store),
        publisher=publisher,
        clock=FixedClock(),
        new_id=lambda: "evt-send",
        region="riau",
        example=example,
    )
    app.state.send_gate = TriggerGate(InMemoryTriggerGateStore(), MovingClock())
    return TestClient(app), publisher


def send(client, cell_id="riau-1-1", headers=OPS):
    return client.post(f"/api/ops/cells/{cell_id}/send", headers=headers)


def test_sending_someone_publishes_a_drying_event_for_that_one_area(settings):
    client, publisher = make_send_client(settings)

    response = send(client)

    assert response.status_code == 202
    assert response.json() == {"cell_id": "riau-1-1", "message_id": "msg-1"}
    [(topic, event)] = publisher.published
    assert topic == "drying.ranked"
    area = event.payload.requested_cell
    assert (area.cell_id, area.rank, area.drying_score) == ("riau-1-1", 4, 93.5)
    assert (event.id, event.occurred_at, event.example) == ("evt-send", NOW, True)


def test_outside_demo_mode_the_event_is_real(settings):
    client, publisher = make_send_client(settings, example=False)

    send(client)

    assert publisher.published[0][1].example is False


def test_an_unknown_area_is_404(settings):
    client, publisher = make_send_client(settings)

    response = send(client, cell_id="riau-9-9")

    assert (response.status_code, response.json()["detail"]) == (404, "unknown_cell")
    assert publisher.published == []


def test_an_area_with_a_live_case_is_409(settings):
    live = make_case(id="case-1", cell_id="riau-1-1", dam_id=None, status="assigned")
    client, publisher = make_send_client(settings, cases=[live])

    response = send(client)

    assert (response.status_code, response.json()["detail"]) == (409, "case_open")
    assert publisher.published == []


def test_a_closed_case_does_not_block_a_new_one(settings):
    done = make_case(id="case-1", cell_id="riau-1-1", dam_id=None, status="closed")
    client, _ = make_send_client(settings, cases=[done])

    assert send(client).status_code == 202


def test_a_second_send_within_a_minute_is_429(settings):
    client, _ = make_send_client(settings)

    send(client)
    response = send(client)

    assert response.status_code == 429
    assert "Retry-After" in response.headers


def test_an_unknown_area_does_not_use_the_send_slot(settings):
    client, _ = make_send_client(settings)

    send(client, cell_id="riau-9-9")

    assert send(client).status_code == 202


def test_an_area_with_a_live_case_does_not_use_the_send_slot(settings):
    live = make_case(id="case-1", cell_id="riau-1-1", dam_id=None, status="assigned")
    client, _ = make_send_client(settings, cases=[live])

    assert send(client).status_code == 409

    assert send(client, cell_id="riau-2-2").status_code == 202


def test_a_valid_send_uses_the_slot_for_the_next_area(settings):
    client, _ = make_send_client(settings)

    assert send(client).status_code == 202

    assert send(client, cell_id="riau-2-2").status_code == 429


def test_a_volunteer_cannot_send_someone(settings):
    client, _ = make_send_client(settings)

    response = send(client, headers={"Authorization": "Bearer volunteer"})

    assert response.status_code == 403


def test_a_publish_failure_is_502(settings):
    client, _ = make_send_client(settings, publisher=RecordingPublisher(TimeoutError()))

    response = send(client)

    assert (response.status_code, response.json()["detail"]) == (502, "publish_failed")
