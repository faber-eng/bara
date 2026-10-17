from collections.abc import Mapping
from datetime import datetime
from zoneinfo import ZoneInfo

from adapters.firestore_repos import (
    BulletinRepository,
    CaseRepository,
    DamRepository,
    EscalationRepository,
    EvidenceRepository,
    RankingRepository,
    RankingRunRepository,
    TaskRepository,
)
from contracts import (
    Case,
    Escalation,
    PublicBulletin,
    PublicCells,
    PublicDam,
    PublicSummary,
    RankedCell,
    RecordLine,
)
from domain.public_summary import (
    build_summary,
    public_dams,
    response_record,
    week_window,
)
from domain.rankings import newest_week_by_rank
from domain.weeks import iso_week_label
from public.serializers import serialize_bulletin, serialize_cells

RANKED_CELL_LIMIT = 200
CELL_LIMIT = 50
RECORD_LIMIT = 50


class UnknownRegion(Exception):
    pass


class NoRankings(Exception):
    pass


class PublicQueries:
    def __init__(
        self,
        *,
        rankings: RankingRepository,
        dams: DamRepository,
        cases: CaseRepository,
        tasks: TaskRepository,
        evidence: EvidenceRepository,
        escalations: EscalationRepository,
        bulletins: BulletinRepository,
        ranking_runs: RankingRunRepository,
        zones: Mapping[str, str],
    ):
        self._rankings = rankings
        self._dams = dams
        self._cases = cases
        self._tasks = tasks
        self._evidence = evidence
        self._escalations = escalations
        self._bulletins = bulletins
        self._ranking_runs = ranking_runs
        self._zones = zones

    def zone(self, region: str) -> ZoneInfo:
        name = self._zones.get(region)
        if name is None:
            raise UnknownRegion(region)
        return ZoneInfo(name)

    def week_cells(self, region: str, week: str | None) -> list[RankedCell]:
        self.zone(region)
        cells = newest_week_by_rank(self._rankings.top(region, RANKED_CELL_LIMIT))
        if week is not None:
            cells = [c for c in cells if iso_week_label(c.week_start) == week]
        if not cells:
            raise NoRankings(region)
        return cells

    def cells(self, region: str, week: str | None, limit: int) -> PublicCells:
        ranked = self.week_cells(region, week)
        label = iso_week_label(ranked[0].week_start)
        return serialize_cells(region, label, ranked, limit)

    def summary(self, region: str, week: str | None, now: datetime) -> PublicSummary:
        ranked = self.week_cells(region, week)
        week_start = ranked[0].week_start
        cases = self._cases.search(region, None)
        case_ids = [case.id for case in cases]
        return build_summary(
            region=region,
            week_start=week_start,
            window=week_window(week_start, self.zone(region)),
            now=now,
            cells=ranked,
            dams=self._dams.in_region(region),
            cases=cases,
            tasks=self._tasks.for_cases(case_ids),
            evidence=self._evidence.for_cases(case_ids),
            run=self._ranking_runs.get(region, iso_week_label(week_start)),
        )

    def dams(self, region: str) -> list[PublicDam]:
        self.zone(region)
        cases = self._cases.search(region, None)
        tasks = self._tasks.for_cases([case.id for case in cases])
        return public_dams(self._dams.in_region(region), cases, tasks)

    def record(self, region: str, limit: int) -> list[RecordLine]:
        zone = self.zone(region)
        cases = self._cases.search(region, None)
        tasks = self._tasks.for_cases([case.id for case in cases])
        return response_record(
            cases, tasks, self._escalations_by_case(cases), zone, limit
        )

    def bulletin(self, region: str, week: str | None) -> PublicBulletin:
        self.zone(region)
        label = week or self._newest_week(region)
        found = self._bulletins.get(f"{region}_{label}")
        return serialize_bulletin(region, label, found)

    def _newest_week(self, region: str) -> str:
        return iso_week_label(self.week_cells(region, None)[0].week_start)

    def _escalations_by_case(self, cases: list[Case]) -> dict[str, list[Escalation]]:
        grouped: dict[str, list[Escalation]] = {}
        for escalation in self._escalations.for_cases([case.id for case in cases]):
            grouped.setdefault(escalation.case_id, []).append(escalation)
        return grouped
