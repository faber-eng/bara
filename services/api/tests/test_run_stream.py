import asyncio
import json
from datetime import UTC, datetime

import pytest

from adapters.firestore_repos import AgentRunRepository, CaseRepository
from case_queries import UnknownCase
from contracts import AgentDecision, AgentRun, Case, ToolCall
from run_stream import RunStreamer, StreamEvent, render
from tests.fakes import InMemoryCollection, make_agent_run, make_case

NOW = datetime(2026, 10, 17, 12, 0, 5, tzinfo=UTC)
DECISION = AgentDecision(
    decision="send a dam check", reason="r", evidence=[], next_check_at=None
)


def call(name):
    return ToolCall(name=name, args={}, result_summary=f"{name} ok", ms=5)


class World:
    def __init__(self, script=()):
        self.cases = InMemoryCollection(Case)
        self.cases.put("c1", make_case(id="c1"))
        self.runs = InMemoryCollection(AgentRun)
        self.script = list(script)
        self.sleeps = []
        self.streamer = RunStreamer(
            cases=CaseRepository(self.cases),
            runs=AgentRunRepository(lambda case_id: self.runs),
            now=lambda: NOW,
            sleep=self.sleep,
            poll_seconds=0.5,
            max_wait_seconds=3,
        )

    async def sleep(self, seconds):
        self.sleeps.append(seconds)
        if self.script:
            self.script.pop(0)(self)

    def collect(self, case_id="c1") -> list[StreamEvent]:
        async def gather():
            return [event async for event in self.streamer.events(case_id)]

        return asyncio.run(gather())

    def put(self, **fields):
        self.runs.put("r1", make_agent_run(**fields))


def names(events):
    return [event.name for event in events]


def test_a_finished_run_replays_its_steps_then_the_final_json():
    world = World()
    world.put(
        tool_calls=[call("rank_areas"), call("get_area_facts")],
        final_json=DECISION,
        status="done",
    )

    events = world.collect()

    assert names(events) == ["open", "tool", "tool", "final"]
    assert [e.data["index"] for e in events[1:3]] == [0, 1]
    assert events[1].data["call"]["name"] == "rank_areas"
    assert events[1].data["seen_at"] == NOW.isoformat()
    assert events[3].data["final_json"]["decision"] == "send a dam check"
    assert events[3].data["status"] == "done"


def test_steps_arrive_one_by_one_while_the_run_is_active():
    steps = [
        lambda w: w.put(tool_calls=[call("rank_areas")], status="running"),
        lambda w: w.put(
            tool_calls=[call("rank_areas"), call("get_area_facts")], status="running"
        ),
        lambda w: w.put(
            tool_calls=[call("rank_areas"), call("get_area_facts")],
            final_json=DECISION,
            status="done",
        ),
    ]
    world = World(steps)

    events = world.collect()

    assert names(events) == ["open", "tool", "tool", "final"]
    assert [e.data["call"]["name"] for e in events[1:3]] == [
        "rank_areas",
        "get_area_facts",
    ]


def test_a_failed_run_ends_with_a_final_event_of_status_failed():
    world = World()
    world.put(status="failed")

    events = world.collect()

    assert names(events) == ["open", "final"]
    assert events[1].data["status"] == "failed"
    assert events[1].data["final_json"] is None


def test_a_case_with_no_run_times_out_with_keepalives_in_between():
    world = World()

    events = world.collect()

    assert names(events) == ["open", "timeout"]
    assert len(world.sleeps) == 6


def test_a_long_wait_sends_keepalives():
    world = World()
    world.streamer = RunStreamer(
        cases=world.streamer._cases,
        runs=world.streamer._runs,
        now=lambda: NOW,
        sleep=world.sleep,
        poll_seconds=0.5,
        max_wait_seconds=25,
    )

    events = world.collect()

    assert names(events).count("keepalive") == 2


def test_the_stream_follows_the_run_it_first_saw():
    world = World()
    world.put(tool_calls=[call("rank_areas")], status="running")

    def a_newer_run_starts(w):
        w.runs.put(
            "r2",
            make_agent_run(
                id="r2",
                started_at=datetime(2026, 10, 17, 12, 5, tzinfo=UTC),
                status="running",
            ),
        )

    def the_first_run_ends(w):
        w.put(tool_calls=[call("rank_areas")], final_json=DECISION, status="done")

    world.script = [a_newer_run_starts, the_first_run_ends]

    events = world.collect()

    assert names(events) == ["open", "tool", "final"]
    assert {e.data["run_id"] for e in events[1:]} == {"r1"}


def test_an_unknown_case_is_refused_before_the_stream_starts():
    with pytest.raises(UnknownCase):
        asyncio.run(World().streamer.require_case("none"))


def test_events_render_as_server_sent_events():
    text = render(StreamEvent("tool", {"index": 0}))

    assert text == 'event: tool\ndata: {"index": 0}\n\n'
    assert json.loads(text.split("data: ")[1]) == {"index": 0}
    assert render(StreamEvent("keepalive", {})) == ": keepalive\n\n"


def route_client(settings, world):
    from fastapi.testclient import TestClient

    import main
    from adapters.gemini import ModelGateway
    from tests.fakes import FakeModels, FakeVerifier

    gateway = ModelGateway(
        settings.models, {"reasoning": FakeModels([]), "fast": FakeModels([])}
    )
    verifier = FakeVerifier(
        {
            "ops": {"uid": "ops-1", "role": "ops"},
            "volunteer": {"uid": "v1", "role": "volunteer"},
        }
    )
    app = main.build_app(settings, gateway, verifier)
    app.state.run_streamer = world.streamer
    return TestClient(app)


def test_the_route_streams_server_sent_events_to_ops(settings):
    world = World()
    world.put(tool_calls=[call("rank_areas")], final_json=DECISION, status="done")

    response = route_client(settings, world).get(
        "/api/cases/c1/stream", headers={"Authorization": "Bearer ops"}
    )

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/event-stream")
    assert "no-transform" in response.headers["cache-control"]
    assert [
        line for line in response.text.splitlines() if line.startswith("event:")
    ] == ["event: open", "event: tool", "event: final"]


def test_the_route_is_404_for_an_unknown_case_and_closed_to_volunteers(settings):
    client = route_client(settings, World())

    ops = client.get("/api/cases/none/stream", headers={"Authorization": "Bearer ops"})
    volunteer = client.get(
        "/api/cases/c1/stream", headers={"Authorization": "Bearer volunteer"}
    )
    anonymous = client.get("/api/cases/c1/stream")

    assert ops.status_code == 404
    assert volunteer.status_code == 403
    assert anonymous.status_code == 401


def test_the_direct_cloud_run_url_allows_the_web_origin_to_stream(settings):
    world = World()
    client = route_client(settings, world)

    allowed = client.options(
        "/api/cases/c1/stream",
        headers={
            "Origin": "https://example-project.web.app",
            "Access-Control-Request-Method": "GET",
            "Access-Control-Request-Headers": "authorization,x-bara-role",
        },
    )
    refused = client.options(
        "/api/cases/c1/stream",
        headers={
            "Origin": "https://evil.example",
            "Access-Control-Request-Method": "GET",
        },
    )

    assert allowed.status_code == 200
    assert allowed.headers["access-control-allow-origin"] == (
        "https://example-project.web.app"
    )
    assert refused.status_code == 400


ALLOWED_ORIGINS = [
    "https://example-project.web.app",
    "https://example-project.firebaseapp.com",
    "http://localhost:5173",
]


def preflight(client, path, origin, method="GET"):
    return client.options(
        path,
        headers={
            "Origin": origin,
            "Access-Control-Request-Method": method,
            "Access-Control-Request-Headers": "authorization,x-bara-role",
        },
    )


def test_each_listed_origin_is_allowed_on_the_stream_route(settings):
    client = route_client(settings, World())

    for origin in ALLOWED_ORIGINS:
        response = preflight(client, "/api/cases/c1/stream", origin)
        assert response.status_code == 200
        assert response.headers["access-control-allow-origin"] == origin
        assert "GET" in response.headers["access-control-allow-methods"]
        allowed = response.headers["access-control-allow-headers"].lower()
        assert "authorization" in allowed and "x-bara-role" in allowed


def test_an_unlisted_origin_is_refused_on_the_stream_route(settings):
    client = route_client(settings, World())

    for origin in [
        "https://evil.example",
        "https://example-project.web.app.evil.example",
    ]:
        assert preflight(client, "/api/cases/c1/stream", origin).status_code == 400


def test_a_stream_get_from_an_allowed_origin_carries_the_origin_header(settings):
    client = route_client(settings, World())

    response = client.get(
        "/api/cases/c1/stream",
        headers={"Authorization": "Bearer ops", "Origin": ALLOWED_ORIGINS[0]},
    )

    assert response.headers["access-control-allow-origin"] == ALLOWED_ORIGINS[0]


def test_other_routes_get_no_cors_headers(settings):
    client = route_client(settings, World())

    for path in ["/api/health", "/api/cases/c1/close", "/api/cases/c1/streams"]:
        response = preflight(client, path, ALLOWED_ORIGINS[0])
        assert "access-control-allow-origin" not in response.headers
        get = client.get(
            path,
            headers={"Authorization": "Bearer ops", "Origin": ALLOWED_ORIGINS[0]},
        )
        assert "access-control-allow-origin" not in get.headers
