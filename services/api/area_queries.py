import json
import threading
import time
from collections.abc import Callable
from dataclasses import dataclass
from datetime import date

from adapters.cells import CellPoint, CellRepository
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
from domain.rank_explanation import is_current
from domain.rankings import newest_week_by_rank
from domain.weeks import iso_week_label

RANKED_CELL_LIMIT = 200
RANKED_DAM_LIMIT = 50
TREND_WEEKS = 8
ALL_CELLS_TTL_SECONDS = 300.0
ALL_CELLS_LOCK_TIMEOUT_SECONDS = 60.0
COORD_DECIMALS = 5
SCORE_DECIMALS = 1


def needs_explanation(facts: CellFacts, explained_region: str) -> bool:
    if facts.region != explained_region:
        return False
    return facts.explanation is None and facts.rank <= RANKED_CELL_LIMIT


def current_explanation(ranked: RankedCell | None, week_start: date):
    if ranked is None or ranked.week_start != week_start:
        return None
    if not is_current(ranked.explanation):
        return None
    return ranked.explanation


@dataclass(frozen=True)
class AllCells:
    region: str
    week: str
    body: bytes


@dataclass(frozen=True)
class CachedCells:
    value: AllCells
    expires_at: float


def compact_row(point: CellPoint) -> list:
    return [
        point.cell_id,
        round(point.lat, COORD_DECIMALS),
        round(point.lon, COORD_DECIMALS),
        round(point.drying_score, SCORE_DECIMALS),
        point.rank,
    ]


def to_all_cells(region: str, points: list[CellPoint]) -> AllCells:
    week = iso_week_label(points[0].week_start)
    document = {
        "region": region,
        "week": week,
        "cells": [compact_row(point) for point in points],
    }
    body = json.dumps(document, separators=(",", ":")).encode()
    return AllCells(region=region, week=week, body=body)


def without_stale_explanation(cell: RankedCell) -> RankedCell:
    if is_current(cell.explanation):
        return cell
    return cell.model_copy(update={"explanation": None})


def without_stale_explanations(cells: list[RankedCell]) -> list[RankedCell]:
    return [without_stale_explanation(cell) for cell in cells]


class NoRankings(Exception):
    pass


class UnknownCell(Exception):
    pass


class CellsBusy(Exception):
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
        clock: Callable[[], float] = time.monotonic,
    ):
        self._rankings = rankings
        self._ranked_dams = ranked_dams
        self._cells = cells
        self._dams = dams
        self._cases = cases
        self._evidence = evidence
        self._radius_m = radius_m
        self._clock = clock
        self._all_cells_lock = threading.Lock()
        self._all_cells: dict[str, CachedCells] = {}

    def rankings(self, region: str, week: str | None) -> Rankings:
        if week is None:
            return self._latest_rankings(region, None)
        cells = self._rankings.top_in_week(region, week, RANKED_CELL_LIMIT)
        if not cells:
            return self._latest_rankings(region, week)
        return Rankings(
            region=region,
            week=week,
            cells=without_stale_explanations(cells),
            dams=self._ranked_dams.top_in_week(region, week, RANKED_DAM_LIMIT),
        )

    def all_cells(self, region: str) -> AllCells:
        cached = self._fresh_cells(region)
        if cached is not None:
            return cached
        if not self._all_cells_lock.acquire(timeout=ALL_CELLS_LOCK_TIMEOUT_SECONDS):
            raise CellsBusy(region)
        try:
            cached = self._fresh_cells(region)
            if cached is not None:
                return cached
            return self._load_all_cells(region)
        finally:
            self._all_cells_lock.release()

    def _fresh_cells(self, region: str) -> AllCells | None:
        entry = self._all_cells.get(region)
        if entry is None or entry.expires_at <= self._clock():
            return None
        return entry.value

    def _load_all_cells(self, region: str) -> AllCells:
        points = self._cells.all_cells(region)
        if not points:
            raise NoRankings(region)
        value = to_all_cells(region, points)
        self._all_cells[region] = CachedCells(
            value=value, expires_at=self._clock() + ALL_CELLS_TTL_SECONDS
        )
        return value

    def _latest_rankings(self, region: str, week: str | None) -> Rankings:
        cells = newest_week_by_rank(self._rankings.top(region, RANKED_CELL_LIMIT))
        if week is not None:
            cells = [c for c in cells if iso_week_label(c.week_start) == week]
        if not cells:
            raise NoRankings(region)
        return Rankings(
            region=region,
            week=iso_week_label(cells[0].week_start),
            cells=without_stale_explanations(cells),
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
