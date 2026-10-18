import asyncio
import logging
from collections.abc import Callable
from dataclasses import dataclass
from typing import Protocol

from adapters.firestore_repos import (
    AgentRunRepository,
    CaseChanged,
    CaseRepository,
    CaseworkStore,
    ContactRepository,
    DamRepository,
    EscalationRepository,
    EvidenceRepository,
    StatusChange,
    TaskRepository,
    VolunteerRepository,
)
from adapters.storage import SIGNING_ERRORS
from casework.brief import BRIEF_PROMPT_VERSION, Brief
from contracts import (
    Case,
    CaseEscalated,
    CaseEscalatedEvent,
    Contact,
    Escalation,
    EscalationPack,
    Event,
    EventType,
    Evidence,
    GeoPoint,
    Message,
    Task,
    TimelineEntry,
)
from domain.brief import BriefFacts
from domain.case_machine import can_transition
from domain.case_view import assignee_ids, build_timeline
from domain.channels import Channel, OutboundMessage
from domain.clock import Clock
from domain.escalation import (
    field_signs,
    map_url,
    overdue_task,
    pack_photos,
    photo_count,
    pick_contact,
    smoke_in,
)

logger = logging.getLogger(__name__)

BRIGADE_LANGUAGE = "id"


class EscalationRejected(Exception):
    pass


class UnknownEscalation(Exception):
    pass


class NotYourEscalation(Exception):
    pass


class Briefer(Protocol):
    async def write(self, facts: BriefFacts) -> Brief: ...


class Centroids(Protocol):
    def centroid(self, cell_id: str) -> GeoPoint | None: ...


class Publisher(Protocol):
    def publish(self, topic: EventType, event: Event) -> str: ...


class PhotoSigner(Protocol):
    def signed_get_url_for(self, uri: str) -> str: ...


def log_fields(event: str, case_id: str, **fields: object) -> dict[str, object]:
    return {"fields": {"event": event, "case_id": case_id, **fields}}


def brigade_message(escalation: Escalation, brief: Brief) -> OutboundMessage:
    return OutboundMessage(
        to_id=escalation.contact_id,
        thread="brigade",
        case_id=escalation.case_id,
        lang=BRIGADE_LANGUAGE,
        text=brief.brief_id,
        text_en=brief.brief_en,
    )


@dataclass(frozen=True)
class EscalationInputs:
    case: Case
    contact: Contact
    evidence: list[Evidence]
    timeline: list[TimelineEntry]
    map_url: str
    facts: BriefFacts


class Escalator:
    def __init__(
        self,
        *,
        cases: CaseRepository,
        tasks: TaskRepository,
        evidence: EvidenceRepository,
        runs: AgentRunRepository,
        dams: DamRepository,
        contacts: ContactRepository,
        escalations: EscalationRepository,
        volunteers: VolunteerRepository,
        cells: Centroids,
        casework: CaseworkStore,
        brief: Briefer,
        channel: Channel,
        publisher: Publisher,
        clock: Clock,
        new_id: Callable[[], str],
    ):
        self._cases = cases
        self._tasks = tasks
        self._evidence = evidence
        self._runs = runs
        self._dams = dams
        self._contacts = contacts
        self._escalations = escalations
        self._volunteers = volunteers
        self._cells = cells
        self._casework = casework
        self._brief = brief
        self._channel = channel
        self._publisher = publisher
        self._clock = clock
        self._new_id = new_id

    async def escalate(self, case_id: str, reason: str) -> Escalation:
        gathered = await asyncio.to_thread(self._gather, case_id)
        if isinstance(gathered, Escalation):
            return gathered
        brief = await self._brief.write(gathered.facts)
        return await asyncio.to_thread(self._finish, gathered, brief, reason)

    def _gather(self, case_id: str) -> Escalation | EscalationInputs:
        case = self._case(case_id)
        existing = self._already_escalated(case)
        if existing is not None:
            return existing
        if not can_transition(case.status, "escalated"):
            raise EscalationRejected(f"a {case.status} case cannot be escalated")
        contact = self._contact(case)
        point = self._point(case)
        evidence = self._evidence.for_cases([case_id])
        tasks = self._tasks.for_case(case_id)
        names = self._volunteers.names(assignee_ids(tasks))
        timeline = build_timeline(
            case, tasks, evidence, self._runs.for_case(case_id), [], [], names
        )
        url = map_url(point) if point is not None else ""
        return EscalationInputs(
            case, contact, evidence, timeline, url, self._facts(case, tasks, evidence)
        )

    def _finish(
        self, inputs: EscalationInputs, brief: Brief, reason: str
    ) -> Escalation:
        case, contact, evidence = inputs.case, inputs.contact, inputs.evidence
        timeline, url, case_id = inputs.timeline, inputs.map_url, inputs.case.id
        escalation = Escalation(
            id=self._new_id(),
            case_id=case_id,
            contact_id=contact.id,
            brief_id=brief.brief_id,
            brief_en=brief.brief_en,
            pack=EscalationPack(
                photos=pack_photos(evidence), map_url=url, timeline=timeline
            ),
            created_at=self._clock.now(),
            acknowledged_at=None,
        )
        message = self._channel.build(brigade_message(escalation, brief))
        try:
            self._store(case, escalation, message)
        except CaseChanged as error:
            return self._winner_of_race(case.id, error)
        self._log_escalated(escalation, brief, reason)
        self._publish(case, escalation)
        return escalation

    def _already_escalated(self, case: Case) -> Escalation | None:
        if case.status != "escalated":
            return None
        return self._escalations.open_for_case(case.id)

    def _winner_of_race(self, case_id: str, error: CaseChanged) -> Escalation:
        winner = self._already_escalated(self._case(case_id))
        if winner is None:
            raise EscalationRejected(
                f"case {case_id} changed while escalating; read it again"
            ) from error
        return winner

    def _case(self, case_id: str) -> Case:
        case = self._cases.get(case_id)
        if case is None:
            raise EscalationRejected(f"no case {case_id!r}")
        return case

    def _contact(self, case: Case) -> Contact:
        contact = pick_contact(self._contacts.for_region(case.region), case.example)
        if contact is None:
            raise EscalationRejected(f"no brigade contact in {case.region}")
        return contact

    def _point(self, case: Case) -> GeoPoint | None:
        dam = self._dams.get(case.dam_id) if case.dam_id is not None else None
        if dam is not None:
            return dam.point
        return self._cells.centroid(case.cell_id)

    @staticmethod
    def _facts(case: Case, tasks: list[Task], evidence: list[Evidence]) -> BriefFacts:
        signs = field_signs(evidence)
        return BriefFacts(
            case_type=case.type,
            cell_id=case.cell_id,
            dam_id=case.dam_id,
            drying_score=case.risk.drying_score,
            p_reignite=case.risk.p_reignite,
            smoke_seen_before=case.history_flags.smoke_seen and not smoke_in(signs),
            field_signs=signs,
            overdue_task=overdue_task(tasks),
            photo_count=photo_count(evidence),
        )

    def _store(self, case: Case, escalation: Escalation, message: Message) -> None:
        self._casework.commit_escalation(
            escalation=escalation,
            message=message,
            case_change=StatusChange(case.id, case.status, "escalated"),
        )

    @staticmethod
    def _log_escalated(escalation: Escalation, brief: Brief, reason: str) -> None:
        logger.info(
            "case escalated",
            extra=log_fields(
                "case_escalated",
                escalation.case_id,
                escalation_id=escalation.id,
                contact_id=escalation.contact_id,
                brief_source=brief.source,
                brief_prompt_version=BRIEF_PROMPT_VERSION,
                reason=reason,
            ),
        )

    def _publish(self, case: Case, escalation: Escalation) -> None:
        event = CaseEscalatedEvent(
            id=self._new_id(),
            type="case.escalated",
            occurred_at=escalation.created_at,
            region=case.region,
            example=case.example,
            payload=CaseEscalated(case_id=case.id, escalation_id=escalation.id),
        )
        try:
            self._publisher.publish("case.escalated", event)
        except Exception as error:
            logger.exception(
                "escalation publish failed",
                extra=log_fields(
                    "escalation_publish_failed",
                    case.id,
                    escalation_id=escalation.id,
                    kind=type(error).__name__,
                ),
            )


class Acknowledger:
    def __init__(
        self,
        *,
        escalations: EscalationRepository,
        cases: CaseRepository,
        casework: CaseworkStore,
        clock: Clock,
    ):
        self._escalations = escalations
        self._cases = cases
        self._casework = casework
        self._clock = clock

    def ack(self, escalation_id: str, owner_id: str | None) -> Escalation:
        escalation = self._escalations.get(escalation_id)
        if escalation is None:
            raise UnknownEscalation(escalation_id)
        if owner_id is not None and owner_id != escalation.contact_id:
            raise NotYourEscalation(escalation_id)
        if escalation.acknowledged_at is not None:
            return escalation
        acknowledged_at = self._clock.now()
        try:
            self._casework.commit_ack(
                escalation_id=escalation_id,
                acknowledged_at=acknowledged_at,
                case_change=self._case_change(escalation.case_id),
            )
        except CaseChanged:
            return self._stored_after_race(escalation_id)
        return escalation.model_copy(update={"acknowledged_at": acknowledged_at})

    def _case_change(self, case_id: str) -> StatusChange | None:
        case = self._cases.get(case_id)
        if case is None or case.status != "escalated":
            return None
        return StatusChange(case_id, "escalated", "monitoring")

    def _stored_after_race(self, escalation_id: str) -> Escalation:
        stored = self._escalations.get(escalation_id)
        if stored is None or stored.acknowledged_at is None:
            raise EscalationRejected(f"escalation {escalation_id} changed; try again")
        return stored


class BrigadeInbox:
    def __init__(self, *, escalations: EscalationRepository, signer: PhotoSigner):
        self._escalations = escalations
        self._signer = signer

    def read(self, contact_id: str) -> list[Escalation]:
        escalations = self._escalations.open_for_contact(contact_id)
        newest_first = sorted(
            escalations, key=lambda item: (item.created_at, item.id), reverse=True
        )
        return [self.signed(item) for item in newest_first]

    def signed(self, escalation: Escalation) -> Escalation:
        photos: list[str] = []
        for uri in escalation.pack.photos:
            url = self._signed_url(escalation, uri)
            if url is not None:
                photos.append(url)
        pack = escalation.pack.model_copy(update={"photos": photos})
        return escalation.model_copy(update={"pack": pack})

    def _signed_url(self, escalation: Escalation, uri: str) -> str | None:
        try:
            return self._signer.signed_get_url_for(uri)
        except SIGNING_ERRORS as error:
            logger.warning(
                "escalation photo skipped",
                extra=log_fields(
                    "escalation_photo_skipped",
                    escalation.case_id,
                    escalation_id=escalation.id,
                    kind=type(error).__name__,
                ),
            )
            return None
