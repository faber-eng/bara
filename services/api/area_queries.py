from datetime import date

from adapters.cells import CellRepository
from adapters.firestore_repos import (
    CaseRepository,
    DamRepository,
    EvidenceRepository,
    RankedDamRepository,
    RankingRepository,
)
from contracts import CellFacts, RankedCell, Rankings, TrendPoint
from domain.case_view import past_checks
from domain.geo import nearby
from domain.rankings import newest_week_by_rank
from domain.weeks import iso_week_label

RANKED_CELL_LIMIT = 200
RANKED_DAM_LIMIT = 50
TREND_WEEKS = 8


def current_explanation(ranked: RankedCell | None, week_start: date):
    if ranked is None or ranked.week_start != week_start:
        return None
    return ranked.explanation


class NoRankings(Exception):
    pass


class UnknownCell(Exception):
    pass


class AreaQueries:
    def __init__(
        self,
        *,
        rankings: RankingRepository,
        ranked_dams: RankedDamRepository,
        cells: CellRepository,
        dams: DamRepository,
        cases: CaseRepository,
        evidence: EvidenceRepository,
        radius_m: float,
    ):
        self._rankings = rankings
        self._ranked_dams = ranked_dams
        self._cells = cells
        self._dams = dams
        self._cases = cases
        self._evidence = evidence
        self._radius_m = radius_m

    def rankings(self, region: str, week: str | None) -> Rankings:
        cells = newest_week_by_rank(self._rankings.top(region, RANKED_CELL_LIMIT))
        if week is not None:
            cells = [c for c in cells if iso_week_label(c.week_start) == week]
        if not cells:
            raise NoRankings(region)
        return Rankings(
            region=region,
            week=iso_week_label(cells[0].week_start),
            cells=cells,
            dams=self._ranked_dams.top(region, RANKED_DAM_LIMIT),
        )

    def cell_facts(self, cell_id: str) -> CellFacts:
        weeks = self._cells.weekly(cell_id, TREND_WEEKS)
        if not weeks:
            raise UnknownCell(cell_id)
        latest = weeks[0]
        ranked = self._rankings.cell(latest.region, cell_id)
        in_cell = [case.id for case in self._cases.in_cell(cell_id)]
        return CellFacts(
            cell_id=cell_id,
            region=latest.region,
            components=latest.components,
            drying_score=latest.drying_score,
            rank=latest.rank,
            trend=[
                TrendPoint(
                    week=iso_week_label(week.week_start), drying_score=week.drying_score
                )
                for week in sorted(weeks, key=lambda week: week.week_start)
            ],
            nearby_dams=nearby(
                latest.centroid, self._dams.in_region(latest.region), self._radius_m
            ),
            past_fires=[],
            past_checks=past_checks(self._evidence.for_cases(in_cell)),
            explanation=current_explanation(ranked, latest.week_start),
        )
