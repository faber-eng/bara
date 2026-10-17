from datetime import datetime

from contracts import (
    DryingRanked,
    DryingRankedEvent,
    FireQuiet,
    FireQuietEvent,
    RankedCell,
    RankedDam,
    TopCellRef,
    TopDamRef,
)
from domain.rankings import newest_week_by_rank
from domain.scenario import Scenario
from domain.weeks import iso_week_label

TOP_REFS = 10


class NoRankings(Exception):
    pass


def build_drying_ranked_event(
    *,
    region: str,
    cells: list[RankedCell],
    dams: list[RankedDam],
    event_id: str,
    occurred_at: datetime,
) -> DryingRankedEvent:
    current = newest_week_by_rank(cells)[:TOP_REFS]
    if not current:
        raise NoRankings(region)
    payload = DryingRanked(
        region=region,
        week=iso_week_label(current[0].week_start),
        top_cells=[
            TopCellRef(
                cell_id=cell.cell_id, drying_score=cell.drying_score, rank=cell.rank
            )
            for cell in current
        ],
        top_dams=[
            TopDamRef(
                dam_id=dam.dam_id,
                cell_id=dam.cell_id,
                last_state=dam.last_state,
                drying_score=dam.drying_score,
            )
            for dam in sorted(dams, key=lambda dam: dam.rank)[:TOP_REFS]
        ],
    )
    return DryingRankedEvent(
        id=event_id,
        occurred_at=occurred_at,
        region=region,
        example=True,
        type="drying.ranked",
        payload=payload,
    )


def build_fire_quiet_event(
    *, scenario: Scenario, event_id: str, occurred_at: datetime
) -> FireQuietEvent:
    fire = scenario.spec.fire_event
    return FireQuietEvent(
        id=event_id,
        occurred_at=occurred_at,
        region=scenario.spec.region,
        example=True,
        type="fire.quiet",
        payload=FireQuiet(event_id=fire.event_id, cells=list(fire.cells)),
    )
