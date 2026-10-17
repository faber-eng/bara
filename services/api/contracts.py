from datetime import date
from typing import Annotated, Literal

from pydantic import (
    AwareDatetime,
    BaseModel,
    ConfigDict,
    Field,
    JsonValue,
    StringConstraints,
    TypeAdapter,
)


class Contract(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


Probability = Annotated[float, Field(ge=0, le=1)]
Percent = Annotated[float, Field(ge=0, le=100)]
Count = Annotated[int, Field(ge=0)]
IsoWeek = Annotated[str, Field(pattern=r"^\d{4}-W\d{2}$")]
Sha256 = Annotated[str, Field(pattern=r"^[0-9a-f]{64}$")]
GcsUri = Annotated[str, Field(pattern=r"^gs://")]
WhatsappNumber = Annotated[str, Field(pattern=r"^\+[1-9]\d{7,14}$")]
InviteCode = Annotated[str, StringConstraints(min_length=1, max_length=128)]
PersonName = Annotated[
    str, StringConstraints(strip_whitespace=True, min_length=1, max_length=80)
]
Scalar = int | float | str

CaseType = Literal["dam_risk", "reignition", "hotspot"]
CaseStatus = Literal[
    "open",
    "assigned",
    "reviewing",
    "resolved_pending_human",
    "human_review",
    "overdue",
    "escalated",
    "monitoring",
    "closed",
]
TaskType = Literal["dam_check", "dam_repair", "patrol_recheck"]
TaskStatus = Literal["open", "done", "overdue", "reassigned", "cancelled"]
VolunteerRole = Literal["volunteer", "repair_team", "patrol"]
EvidenceKind = Literal["photo", "video", "audio"]
MessageThread = Literal["volunteer", "brigade", "ops"]
Channel = Literal["web", "whatsapp"]
BulletinSource = Literal["gemini", "template"]
Language = Literal["id", "en", "ms", "fr"]
SampleKind = Literal["photo", "voice", "area"]
TileLayerKind = Literal["drying"]

Subject = Literal["canal_dam", "burned_peat", "smoke_scene", "other"]
DamState = Literal[
    "intact", "damaged", "broken", "overtopped", "not_applicable", "unknown"
]
Smoke = Literal["none", "wisps", "plume", "unknown"]
HotGround = Literal["none", "possible", "clear", "unknown"]
OpenFlame = Literal["yes", "no", "unknown"]

EventType = Literal[
    "hotspot.detected",
    "fire.quiet",
    "drying.ranked",
    "evidence.received",
    "task.overdue",
    "case.escalated",
]


class GeoPoint(Contract):
    lat: Annotated[float, Field(ge=-90, le=90)]
    lon: Annotated[float, Field(ge=-180, le=180)]


class Verdict(Contract):
    subject: Subject
    dam_state: DamState
    smoke: Smoke
    hot_ground_signs: HotGround
    open_flame: OpenFlame
    transcript: str | None
    transcript_en: str | None
    reasons: Annotated[list[str], Field(max_length=4)]
    confidence: Probability
    needs_human: bool


class Region(Contract):
    id: str
    name: str
    aoi: str
    timezone: str
    language: str
    full_flow: bool


class Channels(Contract):
    web: bool
    whatsapp: str | None


class Volunteer(Contract):
    id: str
    name: str
    role: VolunteerRole
    region: str
    home: GeoPoint
    language: str
    channels: Channels
    available: bool
    example: bool


class Contact(Contract):
    id: str
    name: str
    org: str
    channels: Channels
    region: str
    example: bool


class Dam(Contract):
    id: str
    point: GeoPoint
    canal_osm_id: str | None
    region: str
    last_state: DamState
    last_checked_at: AwareDatetime | None
    example: bool


class CaseRisk(Contract):
    drying_score: Percent | None
    p_reignite: Probability | None


class HistoryFlags(Contract):
    smoke_seen: bool


class Case(Contract):
    id: str
    type: CaseType
    region: str
    cell_id: str
    dam_id: str | None
    event_id: str | None
    status: CaseStatus
    risk: CaseRisk
    opened_at: AwareDatetime
    closed_by: str | None
    closed_at: AwareDatetime | None
    history_flags: HistoryFlags
    example: bool


ReviewAction = Literal["assign", "escalate", "close"]
ReviewNote = Annotated[
    str, StringConstraints(strip_whitespace=True, min_length=1, max_length=500)
]


class ReviewRequest(Contract):
    action: ReviewAction
    note: ReviewNote


class ToolCall(Contract):
    name: str
    args: dict[str, JsonValue]
    result_summary: str
    ms: Count


class AgentDecision(Contract):
    decision: str
    reason: str
    evidence: list[str]
    next_check_at: AwareDatetime | None


AgentRunStatus = Literal["running", "done", "failed"]


class AgentRun(Contract):
    id: str
    trigger: str
    tool_calls: list[ToolCall]
    final_json: AgentDecision | None
    model: str
    prompt_version: str
    started_at: AwareDatetime
    ms: Count
    status: AgentRunStatus = "done"


class Task(Contract):
    id: str
    case_id: str
    type: TaskType
    assignee_id: str
    target: GeoPoint
    deadline_at: AwareDatetime
    status: TaskStatus
    cloud_task_name: str | None
    attempt: Annotated[int, Field(ge=1)]
    created_at: AwareDatetime
    done_at: AwareDatetime | None


class Evidence(Contract):
    id: str
    task_id: str
    case_id: str
    kind: EvidenceKind
    gcs_uri: GcsUri
    sha256: Sha256
    point: GeoPoint | None
    captured_at: AwareDatetime | None
    verdict: Verdict | None
    location_ok: bool | None
    uploaded_by: str
    sample: bool


class Message(Contract):
    id: str
    thread: MessageThread
    to_id: str
    case_id: str | None
    lang: str
    text: str
    text_en: str
    channel: Channel
    created_at: AwareDatetime
    delivered: bool


class TimelineEntry(Contract):
    at: AwareDatetime
    text: str


class EscalationPack(Contract):
    photos: list[str]
    map_url: str
    timeline: list[TimelineEntry]


class Escalation(Contract):
    id: str
    case_id: str
    contact_id: str
    brief_id: str
    brief_en: str
    pack: EscalationPack
    created_at: AwareDatetime
    acknowledged_at: AwareDatetime | None


class RankingComponents(Contract):
    s1_anom_db: float | None
    rain_30d_mm: Annotated[float, Field(ge=0)]
    rain_deficit_pct: Annotated[float, Field(ge=-1, le=1)]
    canal_dist_m: Annotated[float, Field(ge=0)]
    peat_class: Literal[1, 2]


class RankExplanation(Contract):
    text: str
    cited: dict[str, Scalar]


class RankedCell(Contract):
    cell_id: str
    region: str
    week_start: date
    centroid: GeoPoint
    components: RankingComponents
    drying_score: Percent
    rank: Annotated[int, Field(ge=1)]
    rank_change: int | None
    stale_s1: bool
    explanation: RankExplanation | None


class RankedDam(Contract):
    dam_id: str
    region: str
    cell_id: str
    point: GeoPoint
    last_state: DamState
    last_checked_at: AwareDatetime | None
    drying_score: Percent
    rank: Annotated[int, Field(ge=1)]
    example: bool


class ClockSettings(Contract):
    offset_seconds: int
    updated_by: str


class VerdictCacheEntry(Contract):
    id: Sha256
    verdict: Verdict
    model: str
    prompt_version: str


class CitedValue(Contract):
    field: str
    value: Scalar | None


class Bulletin(Contract):
    id: str
    text_id: str
    text_en: str
    cited: list[CitedValue]
    source: BulletinSource
    model: str | None
    prompt_version: str
    created_at: AwareDatetime


class ProcessedEvent(Contract):
    id: str
    type: EventType
    processed_at: AwareDatetime


class TopFeature(Contract):
    feature: str
    attribution: float


class HotspotDetected(Contract):
    cell_id: str
    lat: Annotated[float, Field(ge=-90, le=90)]
    lon: Annotated[float, Field(ge=-180, le=180)]
    frp: float | None
    confidence: float
    source: str


class QuietCell(Contract):
    cell_id: str
    p_reignite: Probability
    top_features: list[TopFeature]


class FireQuiet(Contract):
    event_id: str
    cells: list[QuietCell]


class TopCellRef(Contract):
    cell_id: str
    drying_score: Percent
    rank: Annotated[int, Field(ge=1)]


class TopDamRef(Contract):
    dam_id: str
    cell_id: str
    last_state: DamState
    drying_score: Percent


class DryingRanked(Contract):
    region: str
    week: IsoWeek
    top_cells: list[TopCellRef]
    top_dams: list[TopDamRef]


class EvidenceReceived(Contract):
    evidence_id: str
    task_id: str
    case_id: str


class TaskOverdue(Contract):
    task_id: str
    case_id: str
    attempt: Annotated[int, Field(ge=1)]


class CaseEscalated(Contract):
    case_id: str
    escalation_id: str


class Envelope(Contract):
    id: str
    occurred_at: AwareDatetime
    region: str
    example: bool


class HotspotDetectedEvent(Envelope):
    type: Literal["hotspot.detected"]
    payload: HotspotDetected


class FireQuietEvent(Envelope):
    type: Literal["fire.quiet"]
    payload: FireQuiet


class DryingRankedEvent(Envelope):
    type: Literal["drying.ranked"]
    payload: DryingRanked


class EvidenceReceivedEvent(Envelope):
    type: Literal["evidence.received"]
    payload: EvidenceReceived


class TaskOverdueEvent(Envelope):
    type: Literal["task.overdue"]
    payload: TaskOverdue


class CaseEscalatedEvent(Envelope):
    type: Literal["case.escalated"]
    payload: CaseEscalated


Event = Annotated[
    HotspotDetectedEvent
    | FireQuietEvent
    | DryingRankedEvent
    | EvidenceReceivedEvent
    | TaskOverdueEvent
    | CaseEscalatedEvent,
    Field(discriminator="type"),
]
EventAdapter: TypeAdapter[Event] = TypeAdapter(Event)


class Rankings(Contract):
    region: str
    week: IsoWeek
    cells: list[RankedCell]
    dams: list[RankedDam]


class TrendPoint(Contract):
    week: IsoWeek
    drying_score: Percent


class NearbyDam(Contract):
    dam_id: str
    distance_m: Annotated[float, Field(ge=0)]
    last_state: DamState


class PastFire(Contract):
    event_id: str
    start_date: date
    quiet_date: date | None
    p_reignite: Probability | None


class PastCheck(Contract):
    task_id: str
    checked_at: AwareDatetime
    dam_state: DamState
    smoke: Smoke


class CellFacts(Contract):
    cell_id: str
    region: str
    components: RankingComponents
    drying_score: Percent
    rank: Annotated[int, Field(ge=1)]
    trend: Annotated[list[TrendPoint], Field(max_length=8)]
    nearby_dams: list[NearbyDam]
    past_fires: list[PastFire]
    past_checks: list[PastCheck]
    explanation: RankExplanation | None


class SignedEvidence(Evidence):
    gcs_uri: str


class CaseDetail(Contract):
    case: Case
    tasks: list[Task]
    evidence: list[SignedEvidence]
    agent_runs: list[AgentRun]
    timeline: list[TimelineEntry]


class UploadRequest(Contract):
    task_id: str
    kind: EvidenceKind
    content_type: str
    size_bytes: Annotated[int, Field(gt=0)]
    sample: bool


class UploadTicket(Contract):
    evidence_id: str
    upload_url: str
    headers: dict[str, str]


class CompleteRequest(Contract):
    point: GeoPoint | None
    captured_at: AwareDatetime


class PendingUpload(Contract):
    id: str
    task_id: str
    case_id: str
    kind: EvidenceKind
    content_type: str
    object_name: str
    sample: bool
    uploaded_by: str
    created_at: AwareDatetime


class Inbox(Contract):
    tasks: list[Task]
    messages: list[Message]
    evidence: list[Evidence]


class ClockState(Contract):
    now: AwareDatetime
    offset_seconds: int
    judge_mode: bool


class CaseSummary(Contract):
    case: Case
    next_deadline_at: AwareDatetime | None
    task_status: TaskStatus | None


class JoinRequest(Contract):
    invite_code: InviteCode
    name: PersonName
    home: GeoPoint
    language: Language
    whatsapp: WhatsappNumber | None


class JoinResponse(Contract):
    volunteer_id: str
    created: bool


class SampleItem(Contract):
    id: str
    kind: SampleKind
    label: str
    credit: str
    url: str


class DataAsOf(Contract):
    s1_pass_date: date
    ranking_run_at: AwareDatetime


class PublicSummary(Contract):
    region: str
    week: IsoWeek
    high_risk_cells: Count
    dams_broken: Count
    cases_open: Count
    cases_escalated: Count
    cases_closed: Count
    median_days_to_repair: Annotated[float, Field(ge=0)] | None
    tasks_on_time_pct: Percent | None
    data_as_of: DataAsOf


RecordKind = Literal["opened", "task", "overdue", "escalated", "closed"]


class PublicCell(Contract):
    cell_id: str
    centroid: GeoPoint
    drying_score: Percent
    rank: Annotated[int, Field(ge=1)]
    rank_change: int | None
    components: RankingComponents


class PublicCells(Contract):
    region: str
    week: IsoWeek
    cells: list[PublicCell]


class PublicDam(Contract):
    id: str
    point: GeoPoint
    last_state: DamState
    last_checked_at: AwareDatetime | None
    repair_due_at: AwareDatetime | None


class RecordLine(Contract):
    at: AwareDatetime
    cell_id: str
    kind: RecordKind
    text: str


class PublicBulletin(Contract):
    region: str
    week: IsoWeek
    text_id: str | None
    text_en: str | None
    cited: list[CitedValue]
    source: BulletinSource | None
    created_at: AwareDatetime | None


class HealthModels(Contract):
    reasoning: str
    fast: str


class Health(Contract):
    status: str
    models: HealthModels
    fallback_used: bool
    git_sha: str


class TileLayer(Contract):
    layer: TileLayerKind
    region: str
    week: IsoWeek
    url_template: str
