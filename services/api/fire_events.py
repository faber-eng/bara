import asyncio
import logging
from typing import Protocol

from adapters.firestore_repos import CaseRepository, TaskRepository, VolunteerRepository
from casework.assignment import AssignmentRejected, AssignmentRequest
from contracts import (
    Case,
    CaseRisk,
    Event,
    FireQuietEvent,
    GeoPoint,
    HistoryFlags,
    QuietCell,
    Volunteer,
)
from domain.clock import Clock
from domain.people import nearest_people
from events import MalformedPush

logger = logging.getLogger(__name__)

RECHECK_HINT = (
    "Look at the burned peat ground in cell {cell_id} for smoke or heat, "
    "{hours} hours after the fire looked out."
)


class RecheckIncomplete(Exception):
    pass


class Assigner(Protocol):
    async def assign(self, request: AssignmentRequest): ...


class CellCentroids(Protocol):
    def centroid(self, cell_id: str) -> GeoPoint | None: ...


def log_extra(event: str, **fields: object) -> dict[str, dict[str, object]]:
    return {"fields": {"event": event, **fields}}


def most_likely_cells(cells: list[QuietCell], spots: int) -> list[QuietCell]:
    ranked = sorted(cells, key=lambda cell: (-cell.p_reignite, cell.cell_id))
    return ranked[:spots]


def reignition_case_id(fire_event_id: str) -> str:
    return f"case-reignition-{fire_event_id}"


def build_reignition_case(event: FireQuietEvent, top: QuietCell, clock: Clock) -> Case:
    return Case(
        id=reignition_case_id(event.payload.event_id),
        type="reignition",
        region=event.region,
        cell_id=top.cell_id,
        dam_id=None,
        event_id=event.payload.event_id,
        status="open",
        risk=CaseRisk(drying_score=None, p_reignite=top.p_reignite),
        opened_at=clock.now(),
        closed_by=None,
        closed_at=None,
        history_flags=HistoryFlags(smoke_seen=False),
        example=event.example,
    )


class FireQuietHandler:
    def __init__(
        self,
        *,
        cases: CaseRepository,
        tasks: TaskRepository,
        volunteers: VolunteerRepository,
        cells: CellCentroids,
        assigner: Assigner,
        clock: Clock,
        spots: int,
        recheck_hours: int,
    ):
        self._cases = cases
        self._tasks = tasks
        self._volunteers = volunteers
        self._cells = cells
        self._assigner = assigner
        self._clock = clock
        self._spots = spots
        self._recheck_hours = recheck_hours

    def handle(self, message_id: str, event: Event) -> None:
        if not isinstance(event, FireQuietEvent):
            raise MalformedPush("not a fire.quiet event")
        spots = most_likely_cells(event.payload.cells, self._spots)
        if not spots:
            return
        case = build_reignition_case(event, spots[0], self._clock)
        created = self._cases.create(case)
        missing = spots if created else self._without_task(case, spots)
        if not missing:
            logger.info(
                "reignition rechecks exist",
                extra=log_extra(
                    "reignition_case_exists",
                    message_id=message_id,
                    case_id=case.id,
                ),
            )
            return
        retryable = asyncio.run(self._schedule_all(case, missing))
        if retryable:
            raise RecheckIncomplete(f"{case.id}: not scheduled for {retryable}")

    def _without_task(self, case: Case, spots: list[QuietCell]) -> list[QuietCell]:
        targets = [task.target for task in self._tasks.for_case(case.id)]
        return [
            spot for spot in spots if self._cells.centroid(spot.cell_id) not in targets
        ]

    async def _schedule_all(self, case: Case, spots: list[QuietCell]) -> list[str]:
        patrols = self._volunteers.available("patrol")
        first, rest = spots[0], spots[1:]
        done = {
            first.cell_id: await self._schedule_recheck(case, first.cell_id, patrols)
        }
        outcomes = await asyncio.gather(
            *(self._schedule_recheck(case, spot.cell_id, patrols) for spot in rest)
        )
        done.update(zip((spot.cell_id for spot in rest), outcomes, strict=True))
        return [cell_id for cell_id, ok in done.items() if not ok]

    async def _schedule_recheck(
        self, case: Case, cell_id: str, patrols: list[Volunteer]
    ) -> bool:
        patrol = self._nearest_patrol(cell_id, patrols)
        if patrol is None:
            logger.warning(
                "no patrol for recheck",
                extra=log_extra("recheck_no_patrol", case_id=case.id, cell_id=cell_id),
            )
            return True
        request = AssignmentRequest(
            case_id=case.id,
            assignee_id=patrol.id,
            task_type="patrol_recheck",
            instructions_hint=RECHECK_HINT.format(
                cell_id=cell_id, hours=self._recheck_hours
            ),
            deadline_hours=self._recheck_hours,
            target_cell_id=cell_id,
        )
        try:
            await self._assigner.assign(request)
        except AssignmentRejected as error:
            self._log_not_scheduled(case, cell_id, error)
            return True
        except Exception:
            logger.exception(
                "recheck failed",
                extra=log_extra("recheck_failed", case_id=case.id, cell_id=cell_id),
            )
            return False
        return True

    @staticmethod
    def _log_not_scheduled(case: Case, cell_id: str, error: Exception) -> None:
        logger.warning(
            "recheck not scheduled",
            extra=log_extra(
                "recheck_not_scheduled",
                case_id=case.id,
                cell_id=cell_id,
                kind=type(error).__name__,
                reason=str(error),
            ),
        )

    def _nearest_patrol(
        self, cell_id: str, patrols: list[Volunteer]
    ) -> Volunteer | None:
        centroid = self._cells.centroid(cell_id)
        if centroid is None:
            return None
        nearest = nearest_people(centroid, patrols, 1)
        return nearest[0].volunteer if nearest else None
