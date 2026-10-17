import asyncio
import json
import os
import uuid

import pytest
from google.cloud import bigquery

from adapters.bigquery import DATASET, Warehouse
from adapters.cells import CellRepository
from adapters.channels import WebChannel
from adapters.factory import utcnow
from adapters.firestore_repos import (
    CASES,
    MESSAGES,
    TASKS,
    AgentRunRepository,
    CaseRepository,
    CaseworkStore,
    DamRepository,
    RankingRepository,
    TaskRepository,
    VolunteerRepository,
)
from adapters.gemini import ModelGateway, build_agent_model, build_vertex_clients
from bara_agent.agent import build_tools
from bara_agent.run import AgentService
from casework.assignment import TaskAssigner
from casework.messenger import Messenger
from config import load_settings, region_timezones
from contracts import (
    AgentRun,
    Case,
    Dam,
    GeoPoint,
    Message,
    RankedCell,
    Task,
    Volunteer,
)
from domain.clock import Clock
from tests.fakes import (
    InMemoryClockStore,
    InMemoryCollection,
    InMemoryTransactor,
    make_case,
    make_dam,
    make_volunteer,
)

TOP_CELLS_SQL = f"""
SELECT d.cell_id, d.region, d.week_start, d.s1_anom_db, d.stale_s1,
       d.rain_30d_mm, d.rain_deficit_pct, d.canal_dist_m, d.peat_class,
       d.drying_score, d.rank,
       ST_Y(c.centroid) AS lat, ST_X(c.centroid) AS lon
FROM {DATASET}.cell_weekly_drying AS d
JOIN {DATASET}.cells AS c ON c.cell_id = d.cell_id
WHERE d.region = @region
  AND d.week_start = (
    SELECT MAX(week_start) FROM {DATASET}.cell_weekly_drying WHERE region = @region
  )
ORDER BY d.rank
LIMIT 10
"""


class UnusedChecker:
    async def check(self, task_id, evidence_id):
        raise AssertionError("not called")


class UnusedEscalator:
    async def escalate(self, case_id, reason):
        raise AssertionError("not called")


def ranked_cell(row: dict) -> RankedCell:
    return RankedCell.model_validate(
        {
            "cell_id": row["cell_id"],
            "region": row["region"],
            "week_start": row["week_start"],
            "centroid": {"lat": row["lat"], "lon": row["lon"]},
            "components": {
                key: row[key]
                for key in (
                    "s1_anom_db",
                    "rain_30d_mm",
                    "rain_deficit_pct",
                    "canal_dist_m",
                    "peat_class",
                )
            },
            "drying_score": row["drying_score"],
            "rank": row["rank"],
            "rank_change": None,
            "stale_s1": row["stale_s1"],
            "explanation": None,
        }
    )


def offset(point: GeoPoint, d_lat: float, d_lon: float) -> GeoPoint:
    return GeoPoint(lat=point.lat + d_lat, lon=point.lon + d_lon)


def new_id() -> str:
    return uuid.uuid4().hex


def collection_with(model, items, key):
    collection = InMemoryCollection(model)
    for item in items:
        collection.put(getattr(item, key), item)
    return collection


@pytest.mark.live
def test_a_live_dam_risk_run_on_flash_with_real_bigquery():
    settings = load_settings(os.environ)
    warehouse = Warehouse(
        bigquery.Client(project=settings.project), settings.project, DATASET
    )
    top = [
        ranked_cell(row) for row in warehouse.query(TOP_CELLS_SQL, {"region": "riau"})
    ]
    assert len(top) == 10
    first = top[0]
    near_dam = make_dam(id="dam-live-near", point=offset(first.centroid, 0.003, 0.0))
    far_dam = make_dam(id="dam-live-far", point=offset(first.centroid, 0.2, 0.2))
    people = [
        make_volunteer(
            id="vol-real",
            name="Ari",
            home=offset(first.centroid, 0.02, 0.0),
            example=False,
        ),
        make_volunteer(
            id="vol-sample",
            name="Budi",
            home=offset(first.centroid, 0.01, 0.0),
            example=True,
        ),
    ]
    case = make_case(id="case-live", cell_id=first.cell_id, dam_id=near_dam.id)
    rankings = collection_with(RankedCell, top, "cell_id")
    dams = DamRepository(collection_with(Dam, [near_dam, far_dam], "id"))
    runs = InMemoryCollection(AgentRun)
    tasks = InMemoryCollection(Task)
    messages = InMemoryCollection(Message)
    case_docs = collection_with(Case, [case], "id")
    cases = CaseRepository(case_docs)
    casework = CaseworkStore(
        InMemoryTransactor({CASES: case_docs, TASKS: tasks, MESSAGES: messages})
    )
    volunteers = VolunteerRepository(collection_with(Volunteer, people, "id"))
    clock = Clock(InMemoryClockStore(None), utcnow)
    gateway = ModelGateway(settings.models, build_vertex_clients(settings))
    service = AgentService(
        model=build_agent_model(settings),
        tools=build_tools(
            rankings=RankingRepository(lambda region: rankings),
            cells=CellRepository(warehouse),
            dams=dams,
            volunteers=volunteers,
            assigner=TaskAssigner(
                cases=cases,
                volunteers=volunteers,
                dams=dams,
                cells=CellRepository(warehouse),
                tasks=TaskRepository(tasks),
                casework=casework,
                channel=WebChannel(clock, new_id),
                messenger=Messenger(gateway, settings.default_language),
                scheduler=None,
                clock=clock,
                default_deadline_hours=settings.tasks.default_deadline_hours,
                timezones=region_timezones(settings.config_dir),
                new_id=new_id,
            ),
            checker=UnusedChecker(),
            escalator=UnusedEscalator(),
            radius_m=settings.grid_cell_m,
        ),
        cases=cases,
        dams=dams,
        runs=AgentRunRepository(lambda case_id: runs),
        clock=clock,
        max_llm_calls=settings.agent.max_llm_calls,
    )

    run = asyncio.run(service.run_case("drying.ranked", case.id, "live-run-1"))

    print(json.dumps(run.model_dump(mode="json"), indent=2))
    assert runs.get("live-run-1") == run
    assert run.final_json is not None
    called = {call.name for call in run.tool_calls}
    assert set(run.final_json.evidence) <= called
    assert len(run.tool_calls) >= 3
    assert all(not call.result_summary.startswith("error") for call in run.tool_calls)
    assert "get_area_facts" in called
    assert "assign_task" in called
    [task] = tasks.where()
    assert task.assignee_id == "vol-sample"
    assert task.target == near_dam.point
    [message] = messages.where()
    assert message.to_id == "vol-sample"
    assert message.lang == "id"
