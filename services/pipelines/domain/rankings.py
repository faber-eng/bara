import json
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import date, datetime
from typing import Final

from pydantic import ValidationError

from api_contracts import contracts
from ee_lib.weeks import week_label

DAM_STATE_BONUS: Final[dict[str, float]] = {
    "broken": 15.0,
    "overtopped": 15.0,
    "damaged": 8.0,
    "unknown": 3.0,
    "intact": 0.0,
    "not_applicable": 0.0,
}
EVENT_TOP_CELLS = 10
EVENT_TOP_DAMS = 10


class RankingRowError(ValueError):
    pass


class MalformedDamFile(ValueError):
    pass


@dataclass(frozen=True)
class DamLocation:
    id: str
    region: str
    lon: float
    lat: float
    state: str
    checked_at: datetime | None
    example: bool


def ranked_cell(row: Mapping[str, object]):
    previous = row["prev_rank"]
    change = None if previous is None else previous - row["rank"]
    try:
        return contracts.RankedCell.model_validate(
            {
                "cell_id": row["cell_id"],
                "region": row["region"],
                "week_start": row["week_start"],
                "centroid": {"lat": row["lat"], "lon": row["lon"]},
                "components": {
                    "s1_anom_db": row["s1_anom_db"],
                    "rain_30d_mm": row["rain_30d_mm"],
                    "rain_deficit_pct": row["rain_deficit_pct"],
                    "canal_dist_m": row["canal_dist_m"],
                    "peat_class": row["peat_class"],
                },
                "drying_score": row["drying_score"],
                "rank": row["rank"],
                "rank_change": change,
                "stale_s1": row["stale_s1"],
                "explanation": None,
            }
        )
    except ValidationError as error:
        raise RankingRowError(f"cell {row['cell_id']}: {error}") from error


def cell_document(cell) -> dict[str, object]:
    return {**cell.model_dump(), "week_start": cell.week_start.isoformat()}


def dam_document(dam) -> dict[str, object]:
    return dam.model_dump()


def dam_risk(cell_score: float, state: str) -> float:
    return cell_score + DAM_STATE_BONUS[state]


def parse_dams(document: Mapping[str, object]) -> list[DamLocation]:
    locations: list[DamLocation] = []
    seen: set[str] = set()
    for feature in document["features"]:
        dam = dam_location(feature)
        if dam.id in seen:
            raise MalformedDamFile(f"dam {dam.id} appears twice")
        seen.add(dam.id)
        locations.append(dam)
    return locations


def dam_location(feature: Mapping[str, object]) -> DamLocation:
    lon, lat = feature["geometry"]["coordinates"]
    try:
        dam = contracts.Dam.model_validate(
            {**feature["properties"], "point": {"lat": lat, "lon": lon}}
        )
    except ValidationError as error:
        raise MalformedDamFile(f"dam feature does not match Dam: {error}") from error
    return DamLocation(
        id=dam.id,
        region=dam.region,
        lon=dam.point.lon,
        lat=dam.point.lat,
        state=dam.last_state,
        checked_at=dam.last_checked_at,
        example=dam.example,
    )


def dam_cells_param(dams: Sequence[DamLocation]) -> str:
    return json.dumps([{"id": d.id, "lon": d.lon, "lat": d.lat} for d in dams])


def rank_dams(
    dams: Sequence[DamLocation],
    scored: Mapping[str, tuple[str, float]],
    limit: int,
) -> list:
    located = [dam for dam in dams if dam.id in scored]
    ordered = sorted(
        located, key=lambda dam: (-dam_risk(scored[dam.id][1], dam.state), dam.id)
    )
    return [
        ranked_dam(dam, scored[dam.id], rank)
        for rank, dam in enumerate(ordered[:limit], start=1)
    ]


def ranked_dam(dam: DamLocation, scored: tuple[str, float], rank: int):
    cell_id, score = scored
    return contracts.RankedDam(
        dam_id=dam.id,
        region=dam.region,
        cell_id=cell_id,
        point=contracts.GeoPoint(lat=dam.lat, lon=dam.lon),
        last_state=dam.state,
        last_checked_at=dam.checked_at,
        drying_score=score,
        rank=rank,
        example=dam.example,
    )


def ranking_event(
    region: str,
    week_start: date,
    cells: Sequence,
    dams: Sequence,
    event_id: str,
    occurred_at: datetime,
):
    return contracts.DryingRankedEvent(
        id=event_id,
        occurred_at=occurred_at,
        region=region,
        example=False,
        type="drying.ranked",
        payload=contracts.DryingRanked(
            region=region,
            week=week_label(week_start),
            top_cells=[
                contracts.TopCellRef(
                    cell_id=cell.cell_id,
                    drying_score=cell.drying_score,
                    rank=cell.rank,
                )
                for cell in cells[:EVENT_TOP_CELLS]
            ],
            top_dams=[
                contracts.TopDamRef(
                    dam_id=dam.dam_id,
                    cell_id=dam.cell_id,
                    last_state=dam.last_state,
                    drying_score=dam.drying_score,
                )
                for dam in dams[:EVENT_TOP_DAMS]
            ],
        ),
    )
