import base64
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, date, datetime, timedelta

import pytest
from fastapi.testclient import TestClient

import main
from adapters.cells import CellRepository
from adapters.firestore_repos import (
    AgentRunRepository,
    CaseRepository,
    DamRepository,
    EscalationRepository,
    EvidenceRepository,
    MessageRepository,
    RankedDamRepository,
    RankingRepository,
    TaskRepository,
)
from adapters.gemini import ModelGateway
from area_queries import AreaQueries
from case_queries import CaseQueries
from contracts import (
    AgentRun,
    Case,
    ClockSettings,
    Dam,
    Escalation,
    Evidence,
    Message,
    RankedCell,
    RankedDam,
    RankExplanation,
    Task,
    Verdict,
)
from domain.clock import Clock
from domain.rank_explanation import EXPLAIN_PROMPT_VERSION
from tests.fakes import (
    FakeModels,
    FakeVerifier,
    FakeWarehouse,
    InMemoryClockStore,
    InMemoryCollection,
    make_agent_run,
    make_case,
    make_dam,
    make_escalation,
    make_evidence,
    make_ranked_cell,
    make_ranked_dam,
    make_task,
    weekly_row,
)

REAL_NOW = datetime(2026, 10, 17, 12, 0, tzinfo=UTC)


class RecordingSigner:
    def __init__(self):
        self.signed: list[str] = []
        self.fail_for: set[str] = set()

    def signed_get_url_for(self, uri: str) -> str:
        from adapters.storage import InvalidObjectName

        if uri in self.fail_for:
            raise InvalidObjectName(f"{uri!r} is not in the evidence bucket")
        self.signed.append(uri)
        return (
            "https://storage.test/"
            + uri.removeprefix("gs://")
            + "?X-Goog-Signature=abc"
        )


class StubExplainer:
    def __init__(self, result=None):
        self.result = result
        self.calls: list[str] = []

    async def explain(self, cell_id):
        self.calls.append(cell_id)
        return self.result


class World:
    def __init__(self, weekly_rows=None, all_cell_rows=None):
        self.cases = InMemoryCollection(Case)
        self.tasks = InMemoryCollection(Task)
        self.evidence = InMemoryCollection(Evidence)
        self.escalations = InMemoryCollection(Escalation)
        self.ranked_cells = InMemoryCollection(RankedCell)
        self.ranked_dams = InMemoryCollection(RankedDam)
        self.week_cells: dict[str, InMemoryCollection] = {}
        self.week_dams: dict[str, InMemoryCollection] = {}
        self.dams = InMemoryCollection(Dam)
        self.runs: dict[str, InMemoryCollection] = {}
        self.explainer = StubExplainer()
        self.clock = Clock(
            InMemoryClockStore(ClockSettings(offset_seconds=0, updated_by="t")),
            lambda: REAL_NOW,
        )
        from adapters.cells import ALL_CELLS_SQL, WEEKLY_SQL

        self.warehouse = FakeWarehouse(
            {WEEKLY_SQL: weekly_rows or [], ALL_CELLS_SQL: all_cell_rows or []}
        )
        warehouse = self.warehouse
        evidence_repo = EvidenceRepository(self.evidence)
        case_repo = CaseRepository(self.cases)
        self.signer = RecordingSigner()
        self.case_queries = CaseQueries(
            signer=self.signer,
            cases=case_repo,
            tasks=TaskRepository(self.tasks),
            evidence=evidence_repo,
            runs=AgentRunRepository(self.runs_for),
            escalations=EscalationRepository(self.escalations),
            messages=MessageRepository(InMemoryCollection(Message)),
            clock=self.clock,
        )
        self.area_queries = AreaQueries(
            rankings=RankingRepository(
                lambda region: self.ranked_cells,
                lambda region, week: self.week_cells.setdefault(
                    week, InMemoryCollection(RankedCell)
                ),
            ),
            ranked_dams=RankedDamRepository(
                lambda region: self.ranked_dams,
                lambda region, week: self.week_dams.setdefault(
                    week, InMemoryCollection(RankedDam)
                ),
            ),
            cells=CellRepository(warehouse),
            dams=DamRepository(self.dams),
            cases=case_repo,
            evidence=evidence_repo,
            radius_m=1000,
        )

    def runs_for(self, case_id):
        return self.runs.setdefault(case_id, InMemoryCollection(AgentRun))

    def client(self, settings, judge=False):
        gateway = ModelGateway(
            settings.models, {"reasoning": FakeModels([]), "fast": FakeModels([])}
        )
        verifier = FakeVerifier(
            {
                "ops": {"uid": "ops-1", "role": "ops"},
                "volunteer": {"uid": "v1", "role": "volunteer"},
                "plain": {"uid": "u9"},
            }
        )
        app = main.build_app(settings, gateway, verifier)
        app.state.case_queries = self.case_queries
        app.state.area_queries = self.area_queries
        app.state.rank_explainer = self.explainer
        return TestClient(app)

    def add_case(self, case_id="c1", status="open", **overrides):
        self.cases.put(case_id, make_case(id=case_id, status=status, **overrides))


OPS = {"Authorization": "Bearer ops"}


def test_the_case_list_returns_summaries_newest_first(settings):
    world = World()
    old = REAL_NOW - timedelta(days=2)
    world.add_case("old", opened_at=old)
    world.add_case("new", opened_at=REAL_NOW)
    world.tasks.put(
        "t1",
        make_task(id="t1", case_id="new", deadline_at=REAL_NOW + timedelta(hours=5)),
    )

    response = world.client(settings).get("/api/cases", headers=OPS)

    assert response.status_code == 200
    body = response.json()
    assert [row["case"]["id"] for row in body] == ["new", "old"]
    assert body[0]["task_status"] == "open"
    assert body[0]["next_deadline_at"] is not None
    assert body[1]["task_status"] is None


def test_the_case_list_pages_with_a_limit_and_a_cursor(settings):
    world = World()
    for index in range(5):
        world.add_case(f"c{index}", opened_at=REAL_NOW - timedelta(hours=index))
    client = world.client(settings)

    first = client.get("/api/cases?limit=2", headers=OPS)
    second = client.get(
        "/api/cases",
        params={"limit": 2, "cursor": first.headers["x-next-cursor"]},
        headers=OPS,
    )
    last = client.get(
        "/api/cases",
        params={"limit": 2, "cursor": second.headers["x-next-cursor"]},
        headers=OPS,
    )

    ids = [[row["case"]["id"] for row in r.json()] for r in (first, second, last)]
    assert ids == [["c0", "c1"], ["c2", "c3"], ["c4"]]
    assert "x-next-cursor" not in last.headers


def test_the_case_list_defaults_to_50_rows(settings):
    world = World()
    for index in range(60):
        world.add_case(f"c{index:02d}", opened_at=REAL_NOW - timedelta(minutes=index))

    response = world.client(settings).get("/api/cases", headers=OPS)

    assert len(response.json()) == 50
    assert "x-next-cursor" in response.headers


@pytest.mark.parametrize("limit", [0, 201])
def test_the_case_list_rejects_a_limit_outside_1_to_200(settings, limit):
    response = World().client(settings).get(f"/api/cases?limit={limit}", headers=OPS)

    assert response.status_code == 422


def test_the_case_list_rejects_a_cursor_with_a_naive_time(settings):
    forged = base64.urlsafe_b64encode(b"2026-01-01T00:00:00|x").decode()

    response = World().client(settings).get(f"/api/cases?cursor={forged}", headers=OPS)

    assert response.status_code == 422


def test_the_case_list_rejects_a_cursor_it_did_not_issue(settings):
    response = (
        World().client(settings).get("/api/cases?cursor=not-a-cursor", headers=OPS)
    )

    assert response.status_code == 422
    assert response.json() == {"detail": "invalid_cursor"}


def test_the_case_list_filters_by_region_and_status(settings):
    world = World()
    world.add_case("a", region="riau", status="open")
    world.add_case("b", region="riau", status="closed")
    world.add_case("c", region="congo_cuvette", status="open")
    client = world.client(settings)

    by_region = client.get("/api/cases?region=riau", headers=OPS).json()
    by_status = client.get("/api/cases?region=riau&status=open", headers=OPS).json()

    assert {row["case"]["id"] for row in by_region} == {"a", "b"}
    assert [row["case"]["id"] for row in by_status] == ["a"]


def test_an_unknown_status_filter_is_422(settings):
    assert (
        World().client(settings).get("/api/cases?status=nope", headers=OPS).status_code
        == 422
    )


def test_case_detail_has_tasks_evidence_runs_and_timeline_in_one_response(settings):
    world = World()
    world.add_case("c1", status="reviewing", opened_at=REAL_NOW)
    world.tasks.put("t1", make_task(id="t1", case_id="c1", created_at=REAL_NOW))
    world.evidence.put(
        "e1",
        make_evidence(
            id="e1",
            case_id="c1",
            task_id="t1",
            captured_at=REAL_NOW + timedelta(hours=1),
        ),
    )
    world.runs_for("c1").put(
        "r1", make_agent_run(id="r1", started_at=REAL_NOW + timedelta(minutes=5))
    )

    body = world.client(settings).get("/api/cases/c1", headers=OPS).json()

    assert body["case"]["id"] == "c1"
    assert [t["id"] for t in body["tasks"]] == ["t1"]
    assert [e["id"] for e in body["evidence"]] == ["e1"]
    assert [r["id"] for r in body["agent_runs"]] == ["r1"]
    assert len(body["timeline"]) >= 4


def test_an_unknown_case_is_404(settings):
    client = World().client(settings)

    assert client.get("/api/cases/none", headers=OPS).status_code == 404
    assert client.post("/api/cases/none/close", headers=OPS).status_code == 404


@pytest.mark.parametrize("status", ["resolved_pending_human", "human_review"])
def test_close_records_closed_by_and_the_sim_time(settings, status):
    world = World()
    world.add_case("c1", status=status)

    response = world.client(settings).post("/api/cases/c1/close", headers=OPS)

    assert response.status_code == 200
    stored = world.cases.get("c1")
    assert stored.status == "closed"
    assert stored.closed_by == "ops-1"
    assert stored.closed_at == REAL_NOW
    assert response.json()["closed_by"] == "ops-1"


@pytest.mark.parametrize(
    "status",
    ["open", "assigned", "reviewing", "overdue", "escalated", "monitoring", "closed"],
)
def test_close_from_any_other_status_is_409_and_changes_nothing(settings, status):
    world = World()
    world.add_case("c1", status=status)

    response = world.client(settings).post("/api/cases/c1/close", headers=OPS)

    assert response.status_code == 409
    assert world.cases.get("c1").status == status
    assert world.cases.get("c1").closed_by is None


@pytest.mark.parametrize(
    "path,method",
    [
        ("/api/cases", "get"),
        ("/api/cases/c1", "get"),
        ("/api/cases/c1/close", "post"),
        ("/api/rankings/riau", "get"),
        ("/api/cells/riau-1-1", "get"),
    ],
)
def test_only_ops_and_judge_may_read(settings, path, method):
    client = World().client(settings)
    call = getattr(client, method)

    assert call(path).status_code == 401
    assert call(path, headers={"Authorization": "Bearer volunteer"}).status_code == 403
    assert call(path, headers={"Authorization": "Bearer plain"}).status_code == 403


def test_the_judge_header_reads_while_judge_mode_is_on(settings):
    from config import JudgeMode

    on = settings.model_copy(
        update={"judge_mode": JudgeMode(enabled=True, max_resets_per_hour=20)}
    )

    response = (
        World()
        .client(on)
        .get(
            "/api/cases",
            headers={"Authorization": "Bearer plain", "X-Bara-Role": "ops"},
        )
    )

    assert response.status_code == 200


def test_rankings_return_the_newest_week_cells_and_dams(settings):
    world = World()
    for rank in (2, 1):
        world.ranked_cells.put(
            f"c{rank}", make_ranked_cell(cell_id=f"c{rank}", rank=rank)
        )
    world.ranked_cells.put(
        "old", make_ranked_cell(cell_id="old", rank=1, week_start=date(2026, 10, 5))
    )
    world.ranked_dams.put("d1", make_ranked_dam(dam_id="d1"))

    body = world.client(settings).get("/api/rankings/riau", headers=OPS).json()

    assert body["region"] == "riau"
    assert body["week"] == "2026-W42"
    assert [c["cell_id"] for c in body["cells"]] == ["c1", "c2"]
    assert [d["dam_id"] for d in body["dams"]] == ["d1"]


def test_rankings_for_another_week_or_no_data_are_404(settings):
    world = World()
    world.ranked_cells.put("c1", make_ranked_cell(cell_id="c1"))
    client = world.client(settings)

    assert (
        client.get("/api/rankings/riau?week=2026-W10", headers=OPS).status_code == 404
    )
    assert (
        World().client(settings).get("/api/rankings/riau", headers=OPS).status_code
        == 404
    )


def test_rankings_for_a_past_week_read_that_weeks_snapshot(settings):
    world = World()
    world.ranked_cells.put("c1", make_ranked_cell(cell_id="c1", rank=1))
    past = date(2026, 5, 18)
    for rank in (2, 1):
        world.week_cells.setdefault("2026-W21", InMemoryCollection(RankedCell)).put(
            f"c{rank}",
            make_ranked_cell(cell_id=f"c{rank}", rank=rank, week_start=past),
        )
    world.week_dams.setdefault("2026-W21", InMemoryCollection(RankedDam)).put(
        "d9", make_ranked_dam(dam_id="d9")
    )
    client = world.client(settings)

    body = client.get("/api/rankings/riau?week=2026-W21", headers=OPS).json()

    assert body["week"] == "2026-W21"
    assert [c["cell_id"] for c in body["cells"]] == ["c1", "c2"]
    assert [d["dam_id"] for d in body["dams"]] == ["d9"]
    latest = client.get("/api/rankings/riau", headers=OPS).json()
    assert latest["week"] == "2026-W42"


def test_the_latest_week_without_a_snapshot_falls_back_to_the_latest_set(settings):
    world = World()
    world.ranked_cells.put("c1", make_ranked_cell(cell_id="c1"))
    world.ranked_dams.put("d1", make_ranked_dam(dam_id="d1"))

    body = (
        world.client(settings)
        .get("/api/rankings/riau?week=2026-W42", headers=OPS)
        .json()
    )

    assert [c["cell_id"] for c in body["cells"]] == ["c1"]
    assert [d["dam_id"] for d in body["dams"]] == ["d1"]


def test_a_malformed_week_is_422(settings):
    client = World().client(settings)

    assert client.get("/api/rankings/riau?week=abc", headers=OPS).status_code == 422


def test_cell_facts_has_trend_nearby_dams_checks_and_the_stored_explanation(settings):
    rows = [
        weekly_row(week_start=date(2026, 10, 12), drying_score=90.5, rank=1),
        weekly_row(week_start=date(2026, 10, 5), drying_score=80.0, rank=3),
    ]
    world = World(rows)
    world.dams.put("dam-1", make_dam(id="dam-1", last_state="broken"))
    world.ranked_cells.put(
        "riau-1-1",
        make_ranked_cell(
            explanation={
                "text": "dry",
                "cited": {"rain_deficit_pct": 31},
                "prompt_version": EXPLAIN_PROMPT_VERSION,
            }
        ),
    )
    world.add_case("c1", cell_id="riau-1-1")
    world.evidence.put(
        "e1",
        make_evidence(
            id="e1",
            case_id="c1",
            task_id="t1",
            captured_at=REAL_NOW,
            verdict=Verdict(
                subject="canal_dam",
                dam_state="broken",
                smoke="none",
                hot_ground_signs="none",
                open_flame="no",
                transcript=None,
                transcript_en=None,
                reasons=[],
                confidence=0.9,
                needs_human=False,
            ),
        ),
    )

    response = world.client(settings).get("/api/cells/riau-1-1", headers=OPS)

    assert response.status_code == 200
    body = response.json()
    assert body["drying_score"] == 90.5
    assert body["rank"] == 1
    assert [p["week"] for p in body["trend"]] == ["2026-W41", "2026-W42"]
    assert [d["dam_id"] for d in body["nearby_dams"]] == ["dam-1"]
    assert body["past_checks"][0]["dam_state"] == "broken"
    assert body["explanation"]["text"] == "dry"
    assert body["past_fires"] == []


def test_a_missing_explanation_is_made_on_the_cell_route_only(settings):
    world = World([weekly_row()])
    world.ranked_cells.put("riau-1-1", make_ranked_cell())
    world.explainer.result = RankExplanation(
        text="dry", cited={"rank": 1}, prompt_version=EXPLAIN_PROMPT_VERSION
    )
    client = world.client(settings)

    listed = client.get("/api/rankings/riau", headers=OPS)
    detail = client.get("/api/cells/riau-1-1", headers=OPS)

    assert listed.status_code == 200
    assert world.explainer.calls == ["riau-1-1"]
    assert detail.json()["explanation"]["text"] == "dry"


def test_a_stored_explanation_is_not_made_again(settings):
    world = World([weekly_row()])
    world.ranked_cells.put(
        "riau-1-1",
        make_ranked_cell(
            explanation={
                "text": "kept",
                "cited": {"rank": 1},
                "prompt_version": EXPLAIN_PROMPT_VERSION,
            }
        ),
    )

    body = world.client(settings).get("/api/cells/riau-1-1", headers=OPS).json()

    assert body["explanation"]["text"] == "kept"
    assert world.explainer.calls == []


def test_a_cell_of_a_region_without_the_full_flow_gets_no_model_explanation(settings):
    world = World([weekly_row(cell_id="congo_cuvette-1-1", region="congo_cuvette")])

    response = world.client(settings).get("/api/cells/congo_cuvette-1-1", headers=OPS)

    assert response.status_code == 200
    assert response.json()["explanation"] is None
    assert world.explainer.calls == []


def test_an_explanation_of_an_older_prompt_version_is_made_again(settings):
    world = World([weekly_row()])
    world.ranked_cells.put(
        "riau-1-1",
        make_ranked_cell(
            explanation={
                "text": "raw 96.84",
                "cited": {"rank": 1},
                "prompt_version": "explain-v1",
            }
        ),
    )
    world.explainer.result = RankExplanation(
        text="new", cited={"rank": 1}, prompt_version=EXPLAIN_PROMPT_VERSION
    )

    body = world.client(settings).get("/api/cells/riau-1-1", headers=OPS).json()

    assert body["explanation"]["text"] == "new"
    assert world.explainer.calls == ["riau-1-1"]


def test_an_explanation_with_no_prompt_version_is_made_again(settings):
    world = World([weekly_row()])
    world.ranked_cells.put(
        "riau-1-1",
        make_ranked_cell(explanation={"text": "old", "cited": {"rank": 1}}),
    )

    world.client(settings).get("/api/cells/riau-1-1", headers=OPS)

    assert world.explainer.calls == ["riau-1-1"]


def test_the_rankings_list_hides_an_explanation_of_an_older_prompt_version(settings):
    world = World([weekly_row()])
    world.ranked_cells.put(
        "riau-1-1",
        make_ranked_cell(
            explanation={
                "text": "raw 96.84",
                "cited": {},
                "prompt_version": "explain-v1",
            }
        ),
    )

    body = world.client(settings).get("/api/rankings/riau", headers=OPS).json()

    assert body["cells"][0]["explanation"] is None


def test_a_failed_explanation_leaves_the_cell_with_null(settings):
    world = World([weekly_row()])

    response = world.client(settings).get("/api/cells/riau-1-1", headers=OPS)

    assert response.status_code == 200
    assert response.json()["explanation"] is None


def test_a_cell_without_drying_data_is_404(settings):
    response = World().client(settings).get("/api/cells/none", headers=OPS)

    assert response.status_code == 404


def test_an_explanation_from_an_older_week_is_not_shown(settings):
    world = World([weekly_row(week_start=date(2026, 10, 12))])
    world.ranked_cells.put(
        "riau-1-1",
        make_ranked_cell(
            week_start=date(2026, 10, 5),
            explanation={"text": "old", "cited": {}},
        ),
    )

    body = world.client(settings).get("/api/cells/riau-1-1", headers=OPS).json()

    assert body["explanation"] is None


def test_a_case_deleted_during_close_is_404(settings):
    world = World()
    world.add_case("c1", status="human_review")
    repo = world.case_queries._cases
    real_close = repo.mark_closed

    def vanish(case_id, closed_by, closed_at):
        world.cases.delete_many([case_id])
        real_close(case_id, closed_by, closed_at)

    repo.mark_closed = vanish

    assert (
        world.client(settings).post("/api/cases/c1/close", headers=OPS).status_code
        == 404
    )


def test_case_detail_signs_evidence_urls_and_never_returns_a_gs_uri(settings):
    world = World()
    world.add_case("c1")
    world.evidence.put(
        "e1",
        make_evidence(
            id="e1", case_id="c1", gcs_uri="gs://example-bara-evidence/e1.jpg"
        ),
    )

    body = world.client(settings).get("/api/cases/c1", headers=OPS).json()

    url = body["evidence"][0]["gcs_uri"]
    assert url.startswith("https://storage.test/example-bara-evidence/e1.jpg?")
    assert world.signer.signed == ["gs://example-bara-evidence/e1.jpg"]


def test_evidence_outside_the_bucket_is_not_signed_and_keeps_its_uri(settings, caplog):
    world = World()
    world.add_case("c1")
    world.evidence.put(
        "e1", make_evidence(id="e1", case_id="c1", gcs_uri="gs://other-bucket/e1.jpg")
    )
    world.signer.fail_for = {"gs://other-bucket/e1.jpg"}

    response = world.client(settings).get("/api/cases/c1", headers=OPS)

    assert response.status_code == 200
    assert response.json()["evidence"][0]["gcs_uri"] == "gs://other-bucket/e1.jpg"
    assert any(
        getattr(r, "fields", {}).get("event") == "case_evidence_unsigned"
        for r in caplog.records
    )


def test_one_unsignable_file_does_not_hide_the_others(settings):
    world = World()
    world.add_case("c1")
    world.evidence.put(
        "a", make_evidence(id="a", case_id="c1", gcs_uri="gs://bad/a.jpg")
    )
    world.evidence.put(
        "b", make_evidence(id="b", case_id="c1", gcs_uri="gs://ok/b.jpg")
    )
    world.signer.fail_for = {"gs://bad/a.jpg"}

    evidence = (
        world.client(settings).get("/api/cases/c1", headers=OPS).json()["evidence"]
    )

    assert evidence[0]["gcs_uri"] == "gs://bad/a.jpg"
    assert evidence[1]["gcs_uri"].startswith("https://")


def test_the_stored_evidence_keeps_its_gs_uri(settings):
    world = World()
    world.add_case("c1")
    world.evidence.put(
        "e1", make_evidence(id="e1", case_id="c1", gcs_uri="gs://ok/e1.jpg")
    )

    world.client(settings).get("/api/cases/c1", headers=OPS)

    assert world.evidence.get("e1").gcs_uri == "gs://ok/e1.jpg"


def test_case_detail_timeline_shows_the_brigade_ack(settings):
    world = World()
    world.add_case("c1", status="monitoring", opened_at=REAL_NOW)
    world.escalations.put(
        "x1",
        make_escalation(
            case_id="c1",
            contact_id="contact-daops",
            created_at=REAL_NOW + timedelta(hours=1),
            acknowledged_at=REAL_NOW + timedelta(hours=2),
        ),
    )
    world.escalations.put("x2", make_escalation(id="x2", case_id="other"))

    body = world.client(settings).get("/api/cases/c1", headers=OPS).json()

    texts = [entry["text"] for entry in body["timeline"]]
    assert texts[-2:] == [
        "Escalated to brigade contact-daops",
        "Brigade contact-daops acknowledged",
    ]


def all_row(cell_id, rank, score, lat=0.5, lon=101.4):
    return {
        "cell_id": cell_id,
        "week_start": date(2026, 10, 12),
        "lat": lat,
        "lon": lon,
        "drying_score": score,
        "rank": rank,
    }


def test_all_cells_returns_compact_rows_with_a_cache_header(settings):
    world = World(all_cell_rows=[all_row("a", 1, 90.54, 0.123456789, 101.987654321)])

    response = world.client(settings).get("/api/cells?region=riau", headers=OPS)

    assert response.status_code == 200
    assert response.headers["cache-control"] == "private, max-age=300"
    assert response.json() == {
        "region": "riau",
        "week": "2026-W42",
        "cells": [["a", 0.12346, 101.98765, 90.5, 1]],
    }


def test_all_cells_runs_one_query_for_repeat_requests(settings):
    world = World(all_cell_rows=[all_row("a", 1, 90.0)])
    client = world.client(settings)

    for _ in range(3):
        client.get("/api/cells?region=riau", headers=OPS)

    assert len(world.warehouse.queries) == 1


def test_all_cells_runs_one_query_for_concurrent_cold_requests(settings):
    world = World(all_cell_rows=[all_row("a", 1, 90.0)])
    queries = world.area_queries

    with ThreadPoolExecutor(max_workers=8) as pool:
        results = list(pool.map(lambda _: queries.all_cells("riau"), range(8)))

    assert len(world.warehouse.queries) == 1
    assert all(result is results[0] for result in results)


def test_all_cells_reads_again_after_the_ttl(settings):
    world = World(all_cell_rows=[all_row("a", 1, 90.0)])
    now = [0.0]
    world.area_queries._clock = lambda: now[0]

    world.area_queries.all_cells("riau")
    now[0] = 299.0
    world.area_queries.all_cells("riau")
    now[0] = 301.0
    world.area_queries.all_cells("riau")

    assert len(world.warehouse.queries) == 2


def test_all_cells_of_a_region_without_data_is_404_and_not_cached(settings):
    world = World()
    client = world.client(settings)

    assert client.get("/api/cells?region=riau", headers=OPS).status_code == 404
    assert client.get("/api/cells?region=riau", headers=OPS).status_code == 404
    assert len(world.warehouse.queries) == 2


def test_all_cells_needs_a_region_and_the_ops_role(settings):
    client = World().client(settings)

    assert client.get("/api/cells", headers=OPS).status_code == 422
    assert client.get("/api/cells?region=riau").status_code == 401
    volunteer = {"Authorization": "Bearer volunteer"}
    assert client.get("/api/cells?region=riau", headers=volunteer).status_code == 403


def test_an_unranked_cell_returns_facts_without_a_model_call(settings):
    world = World([weekly_row(cell_id="riau-9-9", rank=3000, drying_score=12.0)])

    response = world.client(settings).get("/api/cells/riau-9-9", headers=OPS)

    assert response.status_code == 200
    body = response.json()
    assert (body["rank"], body["drying_score"]) == (3000, 12.0)
    assert body["explanation"] is None
    assert world.explainer.calls == []


def test_all_cells_of_an_unconfigured_region_is_404_without_a_query(settings):
    world = World(all_cell_rows=[all_row("a", 1, 90.0)])

    response = world.client(settings).get("/api/cells?region=atlantis", headers=OPS)

    assert response.status_code == 404
    assert world.warehouse.queries == []


def test_all_cells_gives_up_with_503_when_the_load_lock_stays_taken(
    settings, monkeypatch
):
    import area_queries

    monkeypatch.setattr(area_queries, "ALL_CELLS_LOCK_TIMEOUT_SECONDS", 0.01)
    world = World(all_cell_rows=[all_row("a", 1, 90.0)])
    world.area_queries._all_cells_lock.acquire()

    response = world.client(settings).get("/api/cells?region=riau", headers=OPS)

    assert response.status_code == 503
    assert world.warehouse.queries == []


class EmptyStream:
    async def require_case(self, case_id):
        return None

    async def events(self, case_id):
        for event in ():
            yield event


def test_the_agent_stream_is_not_compressed(settings):
    client = World().client(settings)
    client.app.state.run_streamer = EmptyStream()

    response = client.get(
        "/api/cases/c1/stream", headers={**OPS, "Accept-Encoding": "gzip"}
    )

    assert response.headers["content-type"].startswith("text/event-stream")
    assert "content-encoding" not in response.headers
