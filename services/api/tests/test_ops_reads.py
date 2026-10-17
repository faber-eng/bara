from datetime import UTC, date, datetime, timedelta

import pytest
from fastapi.testclient import TestClient

import main
from adapters.cells import CellRepository
from adapters.firestore_repos import (
    AgentRunRepository,
    CaseRepository,
    DamRepository,
    EvidenceRepository,
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
    Evidence,
    RankedCell,
    RankedDam,
    Task,
    Verdict,
)
from domain.clock import Clock
from tests.fakes import (
    FakeModels,
    FakeVerifier,
    FakeWarehouse,
    InMemoryClockStore,
    InMemoryCollection,
    make_agent_run,
    make_case,
    make_dam,
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


class World:
    def __init__(self, weekly_rows=None):
        self.cases = InMemoryCollection(Case)
        self.tasks = InMemoryCollection(Task)
        self.evidence = InMemoryCollection(Evidence)
        self.ranked_cells = InMemoryCollection(RankedCell)
        self.ranked_dams = InMemoryCollection(RankedDam)
        self.dams = InMemoryCollection(Dam)
        self.runs: dict[str, InMemoryCollection] = {}
        self.clock = Clock(
            InMemoryClockStore(ClockSettings(offset_seconds=0, updated_by="t")),
            lambda: REAL_NOW,
        )
        from adapters.cells import WEEKLY_SQL

        warehouse = FakeWarehouse({WEEKLY_SQL: weekly_rows or []})
        evidence_repo = EvidenceRepository(self.evidence)
        case_repo = CaseRepository(self.cases)
        self.signer = RecordingSigner()
        self.case_queries = CaseQueries(
            signer=self.signer,
            cases=case_repo,
            tasks=TaskRepository(self.tasks),
            evidence=evidence_repo,
            runs=AgentRunRepository(self.runs_for),
            clock=self.clock,
        )
        self.area_queries = AreaQueries(
            rankings=RankingRepository(lambda region: self.ranked_cells),
            ranked_dams=RankedDamRepository(lambda region: self.ranked_dams),
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
            explanation={"text": "dry", "cited": {"rain_deficit_pct": 0.31}}
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
