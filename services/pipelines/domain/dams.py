import hashlib
import math
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Final

TOP_STATES: Final = ("broken", "damaged", "intact")
STATE_SLOTS: Final = (
    ("intact", 11),
    ("damaged", 4),
    ("broken", 3),
    ("overtopped", 1),
    ("unknown", 1),
)
SCENARIO_START = datetime(2026, 7, 20, 8, 0, tzinfo=timezone(timedelta(hours=7)))
MAX_DAYS_BEFORE = 60
HASH_HEX_DIGITS = 8


class DamShapeError(ValueError):
    pass


@dataclass(frozen=True)
class Candidate:
    cell_id: str
    osm_id: str
    lon: float
    lat: float
    top_rank: int | None
    canal: dict


@dataclass(frozen=True)
class DamPlan:
    id: str
    region: str
    cell_id: str
    osm_id: str
    lon: float
    lat: float
    state: str
    checked_at: datetime | None
    top_rank: int | None
    canal: dict


def cell_grid_index(cell_id: str) -> tuple[int, int]:
    parts = cell_id.rsplit("-", 2)
    if len(parts) != 3 or not (parts[1].isdigit() and parts[2].isdigit()):
        raise DamShapeError(f"cell id {cell_id!r} is not '<region>-<x>-<y>'")
    return int(parts[1]), int(parts[2])


def grid_distance(a: tuple[int, int], b: tuple[int, int]) -> float:
    return math.hypot(a[0] - b[0], a[1] - b[1])


def nearest_chosen(index: tuple[int, int], chosen: list[tuple[int, int]]) -> float:
    return min(grid_distance(index, other) for other in chosen)


def spread(
    pool: list[Candidate], seeds: list[tuple[int, int]], count: int
) -> list[Candidate]:
    remaining = sorted(pool, key=lambda item: item.cell_id)
    chosen_index = list(seeds)
    picked: list[Candidate] = []
    while remaining and len(picked) < count:
        best = remaining[0]
        if chosen_index:
            best = max(
                remaining,
                key=lambda item: nearest_chosen(
                    cell_grid_index(item.cell_id), chosen_index
                ),
            )
        picked.append(best)
        chosen_index.append(cell_grid_index(best.cell_id))
        remaining.remove(best)
    return picked


def digest_number(key: str) -> int:
    return int(hashlib.sha256(key.encode()).hexdigest()[:HASH_HEX_DIGITS], 16)


def state_slots() -> list[str]:
    return [state for state, weight in STATE_SLOTS for _ in range(weight)]


def mixed_state(item: Candidate) -> str:
    slots = state_slots()
    return slots[digest_number(f"{item.cell_id}:{item.osm_id}") % len(slots)]


def prior_check(item: Candidate, state: str) -> datetime | None:
    if state == "unknown":
        return None
    number = digest_number(f"checked:{item.cell_id}:{item.osm_id}")
    days = 1 + number % MAX_DAYS_BEFORE
    hours = number // MAX_DAYS_BEFORE % 8
    return SCENARIO_START - timedelta(days=days, hours=hours)


def top_candidates(candidates: list[Candidate]) -> list[Candidate]:
    ranked = sorted(
        (item for item in candidates if item.top_rank is not None),
        key=lambda item: (item.top_rank, item.cell_id),
    )
    if len(ranked) < len(TOP_STATES):
        raise DamShapeError(
            f"need {len(TOP_STATES)} top-ranked cells with a canal, found {len(ranked)}"
        )
    return ranked[: len(TOP_STATES)]


def plan_dams(region: str, candidates: list[Candidate], count: int) -> list[DamPlan]:
    top = top_candidates(candidates)
    states = {item.cell_id: state for item, state in zip(top, TOP_STATES, strict=True)}
    pool = [item for item in candidates if item.top_rank is None]
    seeds = [cell_grid_index(item.cell_id) for item in top]
    chosen = [*top, *spread(pool, seeds, count - len(top))]
    chosen.sort(key=lambda item: cell_grid_index(item.cell_id))
    return [
        dam_plan(region, number, item, states.get(item.cell_id))
        for number, item in enumerate(chosen, start=1)
    ]


def dam_plan(
    region: str, number: int, item: Candidate, fixed_state: str | None
) -> DamPlan:
    state = fixed_state or mixed_state(item)
    return DamPlan(
        id=f"dam-{region}-{number:03d}",
        region=region,
        cell_id=item.cell_id,
        osm_id=item.osm_id,
        lon=item.lon,
        lat=item.lat,
        state=state,
        checked_at=prior_check(item, state),
        top_rank=item.top_rank if fixed_state else None,
        canal=item.canal,
    )


def dam_feature(dam: DamPlan) -> dict:
    checked = None if dam.checked_at is None else dam.checked_at.isoformat()
    return {
        "type": "Feature",
        "geometry": {"type": "Point", "coordinates": [dam.lon, dam.lat]},
        "properties": {
            "id": dam.id,
            "canal_osm_id": dam.osm_id,
            "region": dam.region,
            "last_state": dam.state,
            "last_checked_at": checked,
            "example": True,
        },
    }


def reference_features(dams: list[DamPlan], top_cells: list[dict]) -> list[dict]:
    canals = [
        {
            "type": "Feature",
            "geometry": dam.canal,
            "properties": {"kind": "canal", "osm_id": dam.osm_id, "dam_id": dam.id},
        }
        for dam in dams
    ]
    cells = [
        {
            "type": "Feature",
            "geometry": cell["geometry"],
            "properties": {
                "kind": "top_cell",
                "cell_id": cell["cell_id"],
                "rank": cell["rank"],
                "week": cell["week"],
                "drying_score": cell["drying_score"],
            },
        }
        for cell in top_cells
    ]
    return [*canals, *cells]
