import json
from datetime import date

import pytest

from adapters.bigquery import Warehouse
from jobs import build_dams as job
from jobs.cli import JobError
from tests.fakes import RecordingBigQueryClient

WEEK = date(2026, 10, 12)
AOI = {
    "type": "Polygon",
    "coordinates": [[[101.95, 0.35], [102.55, 0.35], [102.55, 0.85], [101.95, 0.35]]],
}
LINE = json.dumps({"type": "LineString", "coordinates": [[102.0, 0.5], [102.001, 0.5]]})
SQUARE = json.dumps(
    {
        "type": "Polygon",
        "coordinates": [[[102, 0.4], [102.01, 0.4], [102.01, 0.41], [102, 0.4]]],
    }
)


def candidate_row(x, y, top_rank=None):
    return {
        "cell_id": f"riau-{x}-{y}",
        "osm_id": str(1000 + x * 100 + y),
        "lon": 102.0 + x / 1000,
        "lat": 0.4 + y / 1000,
        "top_rank": top_rank,
        "canal": LINE,
    }


TOP = {(1, 1): 2, (4, 4): 1, (7, 7): 5}
CANDIDATES = [
    candidate_row(x, y, TOP.get((x, y))) for x in range(10) for y in range(10)
]
TOP_CELLS = [
    {"cell_id": "riau-4-4", "rank": 1, "drying_score": 96.5, "geometry": SQUARE},
    {"cell_id": "riau-1-1", "rank": 2, "drying_score": 95.0, "geometry": SQUARE},
]


def run(tmp_path, *, candidates=CANDIDATES, dry_run=False, count=12):
    client = RecordingBigQueryClient(
        responses={"ST_CLOSESTPOINT": candidates, "ST_ASGEOJSON(c.geom)": TOP_CELLS}
    )
    summary = job.build_dams(
        region="riau",
        aoi=AOI,
        week_start=WEEK,
        warehouse=Warehouse(client, project="p", dataset="bara"),
        count=count,
        out_dir=tmp_path,
        dry_run=dry_run,
    )
    return summary, client


def test_writes_the_dams_and_the_reference_files(tmp_path):
    summary, _ = run(tmp_path)

    dams = json.loads((tmp_path / "dams_riau_sample.geojson").read_text())
    reference = json.loads((tmp_path / "dams_riau_reference.geojson").read_text())
    assert len(dams["features"]) == 12 == summary["dams"]
    assert all(f["properties"]["example"] is True for f in dams["features"])
    kinds = [f["properties"]["kind"] for f in reference["features"]]
    assert kinds.count("canal") == 12
    assert kinds.count("top_cell") == 2
    assert {
        f["properties"]["week"]
        for f in reference["features"]
        if f["properties"]["kind"] == "top_cell"
    } == {"2026-W42"}


def test_a_second_run_writes_the_same_bytes(tmp_path):
    run(tmp_path)
    first = (tmp_path / "dams_riau_sample.geojson").read_bytes()
    run(tmp_path)

    assert (tmp_path / "dams_riau_sample.geojson").read_bytes() == first


def test_dry_run_writes_nothing_but_reports_the_same_counts(tmp_path):
    summary, _ = run(tmp_path, dry_run=True)

    assert list(tmp_path.iterdir()) == []
    assert summary["dams"] == 12
    assert summary["dry_run"] is True


def test_summary_names_the_three_top_cell_dams(tmp_path):
    summary, _ = run(tmp_path)

    assert [(d["cell_id"], d["state"]) for d in summary["top_cell_dams"]] == [
        ("riau-4-4", "broken"),
        ("riau-1-1", "damaged"),
        ("riau-7-7", "intact"),
    ]


def test_no_candidates_is_a_job_error(tmp_path):
    with pytest.raises(JobError):
        run(tmp_path, candidates=[])


def test_too_few_top_cells_with_a_canal_is_a_job_error(tmp_path):
    only_two = [
        candidate_row(x, y, {(1, 1): 2, (4, 4): 1}.get((x, y)))
        for x in range(10)
        for y in range(10)
    ]
    with pytest.raises(JobError):
        run(tmp_path, candidates=only_two)


def test_candidate_query_keeps_points_inside_the_aoi_and_off_cell_edges(tmp_path):
    _, client = run(tmp_path)

    sql, config = next(q for q in client.queries if "ST_CLOSESTPOINT" in q[0])
    params = {p.name: p.value for p in config.query_parameters}
    assert "ST_WITHIN(pt, ST_GEOGFROMGEOJSON(@aoi))" in sql
    assert json.loads(params["aoi"]) == AOI
    assert params["edge_m"] == 100
    assert params["top_n"] == 10
