// Mirror of services/api/contracts.py; change both in the same commit (spec §19.3).

export type IsoDateTime = string;
export type IsoDate = string;
export type IsoWeek = string;
export type Scalar = number | string;

export type CaseType = "dam_risk" | "reignition" | "hotspot";
export type CaseStatus =
  | "open"
  | "assigned"
  | "reviewing"
  | "resolved_pending_human"
  | "human_review"
  | "overdue"
  | "escalated"
  | "monitoring"
  | "closed";
export type TaskType = "dam_check" | "dam_repair" | "patrol_recheck";
export type TaskStatus = "open" | "done" | "overdue" | "reassigned" | "cancelled";
export type EvidenceKind = "photo" | "video" | "audio";
export type MessageThread = "volunteer" | "brigade" | "ops";
export type Channel = "web" | "whatsapp";
export type BulletinSource = "gemini" | "template";
export type Language = "id" | "en" | "ms" | "fr";
export type SampleKind = "photo" | "voice" | "area";

export type Subject = "canal_dam" | "burned_peat" | "smoke_scene" | "other";
export type DamState =
  | "intact"
  | "damaged"
  | "broken"
  | "overtopped"
  | "not_applicable"
  | "unknown";
export type Smoke = "none" | "wisps" | "plume" | "unknown";
export type HotGround = "none" | "possible" | "clear" | "unknown";
export type OpenFlame = "yes" | "no" | "unknown";

export type GeoPoint = { lat: number; lon: number };

export type Region = {
  id: string;
  name: string;
  aoi: string;
  timezone: string;
  language: string;
  full_flow: boolean;
};

export type Verdict = {
  subject: Subject;
  dam_state: DamState;
  smoke: Smoke;
  hot_ground_signs: HotGround;
  open_flame: OpenFlame;
  transcript: string | null;
  transcript_en: string | null;
  reasons: string[];
  confidence: number;
  needs_human: boolean;
};

export type CaseRisk = { drying_score: number | null; p_reignite: number | null };

export type Case = {
  id: string;
  type: CaseType;
  region: string;
  cell_id: string;
  dam_id: string | null;
  event_id: string | null;
  status: CaseStatus;
  risk: CaseRisk;
  opened_at: IsoDateTime;
  closed_by: string | null;
  closed_at: IsoDateTime | null;
  history_flags: { smoke_seen: boolean };
  example: boolean;
};

export type Task = {
  id: string;
  case_id: string;
  type: TaskType;
  assignee_id: string;
  target: GeoPoint;
  deadline_at: IsoDateTime;
  status: TaskStatus;
  cloud_task_name: string | null;
  attempt: number;
  created_at: IsoDateTime;
  done_at: IsoDateTime | null;
};

export type Evidence = {
  id: string;
  task_id: string;
  case_id: string;
  kind: EvidenceKind;
  gcs_uri: string;
  sha256: string;
  point: GeoPoint | null;
  captured_at: IsoDateTime | null;
  verdict: Verdict | null;
  location_ok: boolean | null;
  uploaded_by: string;
  sample: boolean;
};

export type JsonValue =
  | string
  | number
  | boolean
  | null
  | JsonValue[]
  | { [key: string]: JsonValue };

export type ToolCall = {
  name: string;
  args: { [key: string]: JsonValue };
  result_summary: string;
  ms: number;
};

export type AgentDecision = {
  decision: string;
  reason: string;
  evidence: string[];
  next_check_at: IsoDateTime | null;
};

export type AgentRunStatus = "running" | "done" | "failed";

export type AgentRun = {
  id: string;
  trigger: string;
  tool_calls: ToolCall[];
  final_json: AgentDecision | null;
  model: string;
  prompt_version: string;
  started_at: IsoDateTime;
  ms: number;
  status: AgentRunStatus;
};

export type Message = {
  id: string;
  thread: MessageThread;
  to_id: string;
  case_id: string | null;
  lang: string;
  text: string;
  text_en: string;
  channel: Channel;
  created_at: IsoDateTime;
  delivered: boolean;
};

export type TimelineEntry = { at: IsoDateTime; text: string };

export type Escalation = {
  id: string;
  case_id: string;
  contact_id: string;
  brief_id: string;
  brief_en: string;
  pack: { photos: string[]; map_url: string; timeline: TimelineEntry[] };
  created_at: IsoDateTime;
  acknowledged_at: IsoDateTime | null;
};

export type RankingComponents = {
  s1_anom_db: number | null;
  rain_30d_mm: number;
  rain_deficit_pct: number;
  canal_dist_m: number;
  peat_class: 1 | 2;
};

export type RankExplanation = { text: string; cited: { [field: string]: Scalar } };

export type RankedCell = {
  cell_id: string;
  region: string;
  week_start: IsoDate;
  centroid: GeoPoint;
  components: RankingComponents;
  drying_score: number;
  rank: number;
  rank_change: number | null;
  stale_s1: boolean;
  explanation: RankExplanation | null;
};

export type RankedDam = {
  dam_id: string;
  region: string;
  cell_id: string;
  point: GeoPoint;
  last_state: DamState;
  last_checked_at: IsoDateTime | null;
  drying_score: number;
  rank: number;
  example: boolean;
};

export type Rankings = {
  region: string;
  week: IsoWeek;
  cells: RankedCell[];
  dams: RankedDam[];
};

export type CellFacts = {
  cell_id: string;
  region: string;
  components: RankingComponents;
  drying_score: number;
  rank: number;
  trend: { week: IsoWeek; drying_score: number }[];
  nearby_dams: { dam_id: string; distance_m: number; last_state: DamState }[];
  past_fires: {
    event_id: string;
    start_date: IsoDate;
    quiet_date: IsoDate | null;
    p_reignite: number | null;
  }[];
  past_checks: { task_id: string; checked_at: IsoDateTime; dam_state: DamState; smoke: Smoke }[];
  explanation: RankExplanation | null;
};

export type CaseDetail = {
  case: Case;
  tasks: Task[];
  evidence: Evidence[];
  agent_runs: AgentRun[];
  timeline: TimelineEntry[];
};

export type CitedValue = { field: string; value: Scalar | null };

export type Bulletin = {
  id: string;
  text_id: string;
  text_en: string;
  cited: CitedValue[];
  source: BulletinSource;
  model: string | null;
  prompt_version: string;
  created_at: IsoDateTime;
};

export type UploadRequest = {
  task_id: string;
  kind: EvidenceKind;
  content_type: string;
  size_bytes: number;
  sample: boolean;
};

export type UploadTicket = {
  evidence_id: string;
  upload_url: string;
  headers: Record<string, string>;
};

export type CompleteRequest = { point: GeoPoint | null; captured_at: IsoDateTime };

export type Inbox = { tasks: Task[]; messages: Message[]; evidence: Evidence[] };

export type ClockState = { now: IsoDateTime; offset_seconds: number; judge_mode: boolean };

export type CaseSummary = {
  case: Case;
  next_deadline_at: IsoDateTime | null;
  task_status: TaskStatus | null;
};

export type JoinRequest = {
  invite_code: string;
  name: string;
  home: GeoPoint;
  language: Language;
  whatsapp: string | null;
};

export type JoinResponse = { volunteer_id: string; created: boolean };

export type SampleItem = {
  id: string;
  kind: SampleKind;
  label: string;
  credit: string;
  url: string;
};

export type PublicSummary = {
  region: string;
  week: IsoWeek;
  high_risk_cells: number;
  dams_broken: number;
  cases_open: number;
  cases_escalated: number;
  cases_closed: number;
  median_days_to_repair: number | null;
  tasks_on_time_pct: number | null;
  data_as_of: { s1_pass_date: IsoDate; ranking_run_at: IsoDateTime };
};

export type RecordKind = "opened" | "task" | "overdue" | "escalated" | "closed";

export type PublicCell = {
  cell_id: string;
  centroid: GeoPoint;
  drying_score: number;
  rank: number;
  rank_change: number | null;
  components: RankingComponents;
};

export type PublicCells = {
  region: string;
  week: IsoWeek;
  cells: PublicCell[];
};

export type PublicDam = {
  id: string;
  point: GeoPoint;
  last_state: DamState;
  last_checked_at: IsoDateTime | null;
  repair_due_at: IsoDateTime | null;
};

export type RecordLine = {
  at: IsoDateTime;
  cell_id: string;
  kind: RecordKind;
  text: string;
};

export type PublicBulletin = {
  region: string;
  week: IsoWeek;
  text_id: string | null;
  text_en: string | null;
  cited: CitedValue[];
  source: BulletinSource | null;
  created_at: IsoDateTime | null;
};

export type Health = {
  status: string;
  models: { reasoning: string; fast: string };
  fallback_used: boolean;
  git_sha: string;
};

export type TileLayerKind = "drying" | "peat" | "burn_scars" | "reignition";

export type TileLayer = {
  layer: TileLayerKind;
  region: string;
  week: IsoWeek;
  url_template: string;
};
