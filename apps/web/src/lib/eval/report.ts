export type DryingYear = {
  year: number;
  weeks: number;
  hotspots: number;
  captured: number;
  captureRate: number | null;
  lift: number | null;
};

export type DryingEval = {
  runAt: string;
  topShare: number;
  years: DryingYear[];
};

export type ModelScore = {
  name: string;
  auc: number | null;
  precisionTop10: number;
};

export type ReignitionEval = {
  runAt: string;
  split: string;
  events: number;
  positives: number;
  model: ModelScore;
  served: ModelScore | null;
  baseline: ModelScore;
};

export type FieldAccuracy = { field: string; correct: number; n: number; accuracy: number | null };

export type EvidenceSet = { kind: string; n: number; failed: number; fields: FieldAccuracy[] };

export type EvidenceEval = { runAt: string; model: string; sets: EvidenceSet[] };

export type AgentEval = {
  runAt: string;
  model: string;
  cases: number;
  passed: number;
  passRate: number;
};

export type EvalReport = {
  generatedAt: string;
  drying: DryingEval | null;
  reignition: ReignitionEval | null;
  evidence: EvidenceEval | null;
  agent: AgentEval | null;
};

export type EvalParse = { ok: true; report: EvalReport } | { ok: false; reason: string };

type Section<T> = { present: boolean; value: T | null };

const ISO_TIME = /^\d{4}-\d{2}-\d{2}T/;

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}

function readNumber(value: unknown): number | null {
  return typeof value === "number" && Number.isFinite(value) ? value : null;
}

type NullableNumber = { valid: boolean; value: number | null };

function readNullableNumber(value: unknown): NullableNumber {
  if (value === null) return { valid: true, value: null };
  const number = readNumber(value);
  return { valid: number !== null, value: number };
}

function readString(value: unknown): string | null {
  return typeof value === "string" && value !== "" ? value : null;
}

function readTime(value: unknown): string | null {
  return typeof value === "string" && ISO_TIME.test(value) ? value : null;
}

function readList<T>(value: unknown, read: (item: unknown) => T | null): T[] | null {
  if (!Array.isArray(value)) return null;
  const items: T[] = [];
  for (const raw of value) {
    const item = read(raw);
    if (item === null) return null;
    items.push(item);
  }
  return items;
}

function readSection<T>(
  root: Record<string, unknown>,
  key: string,
  read: (value: unknown) => T | null,
): Section<T> {
  if (root[key] === undefined) return { present: false, value: null };
  return { present: true, value: read(root[key]) };
}

function readYear(raw: unknown): DryingYear | null {
  if (!isRecord(raw)) return null;
  const year = readNumber(raw.year);
  const weeks = readNumber(raw.weeks);
  const hotspots = readNumber(raw.hotspots);
  const captured = readNumber(raw.captured);
  const captureRate = readNullableNumber(raw.capture_rate);
  const lift = readNullableNumber(raw.lift);
  if (year === null || weeks === null || hotspots === null) return null;
  if (captured === null || !captureRate.valid || !lift.valid) return null;
  return { year, weeks, hotspots, captured, captureRate: captureRate.value, lift: lift.value };
}

function readDrying(raw: unknown): DryingEval | null {
  if (!isRecord(raw)) return null;
  const runAt = readTime(raw.run_at);
  const topShare = readNumber(raw.top_share);
  const years = readList(raw.years, readYear);
  if (runAt === null || topShare === null || years === null) return null;
  return { runAt, topShare, years };
}

function readScore(raw: unknown): ModelScore | null {
  if (!isRecord(raw)) return null;
  const name = readString(raw.name);
  const auc = readNullableNumber(raw.auc);
  const precisionTop10 = readNumber(raw.precision_top10);
  if (name === null || !auc.valid || precisionTop10 === null) return null;
  return { name, auc: auc.value, precisionTop10 };
}

function readReignition(raw: unknown): ReignitionEval | null {
  if (!isRecord(raw)) return null;
  const runAt = readTime(raw.run_at);
  const split = readString(raw.split);
  const events = readNumber(raw.events);
  const positives = readNumber(raw.positives);
  const model = readScore(raw.model);
  const baseline = readScore(raw.baseline);
  const served = "served" in raw ? readScore(raw.served) : null;
  if (runAt === null || split === null || events === null || positives === null) return null;
  if (model === null || baseline === null) return null;
  if ("served" in raw && served === null) return null;
  return { runAt, split, events, positives, model, served, baseline };
}

function readField(raw: unknown): FieldAccuracy | null {
  if (!isRecord(raw)) return null;
  const field = readString(raw.field);
  const correct = readNumber(raw.correct);
  const n = readNumber(raw.n);
  const accuracy = readNullableNumber(raw.accuracy);
  if (field === null || correct === null || n === null || !accuracy.valid) return null;
  return { field, correct, n, accuracy: accuracy.value };
}

function readSet(raw: unknown): EvidenceSet | null {
  if (!isRecord(raw)) return null;
  const kind = readString(raw.kind);
  const n = readNumber(raw.n);
  const failed = readNumber(raw.failed);
  const fields = readList(raw.fields, readField);
  if (kind === null || n === null || failed === null || fields === null) return null;
  return { kind, n, failed, fields };
}

function readEvidence(raw: unknown): EvidenceEval | null {
  if (!isRecord(raw)) return null;
  const runAt = readTime(raw.run_at);
  const model = readString(raw.model);
  const sets = readList(raw.sets, readSet);
  if (runAt === null || model === null || sets === null) return null;
  return { runAt, model, sets };
}

function readAgent(raw: unknown): AgentEval | null {
  if (!isRecord(raw)) return null;
  const runAt = readTime(raw.run_at);
  const model = readString(raw.model);
  const cases = readNumber(raw.cases);
  const passed = readNumber(raw.passed);
  const passRate = readNumber(raw.pass_rate);
  if (runAt === null || model === null || cases === null) return null;
  if (passed === null || passRate === null) return null;
  return { runAt, model, cases, passed, passRate };
}

function firstBroken(sections: Record<string, Section<unknown>>): string | null {
  for (const [key, section] of Object.entries(sections)) {
    if (section.present && section.value === null) return key;
  }
  return null;
}

export function parseEvalReport(input: unknown): EvalParse {
  if (!isRecord(input)) return { ok: false, reason: "eval report is not an object" };
  const generatedAt = readTime(input.generated_at);
  if (generatedAt === null) return { ok: false, reason: "generated_at is missing or not a time" };
  const drying = readSection(input, "drying", readDrying);
  const reignition = readSection(input, "reignition", readReignition);
  const evidence = readSection(input, "evidence", readEvidence);
  const agent = readSection(input, "agent", readAgent);
  const broken = firstBroken({ drying, reignition, evidence, agent });
  if (broken !== null) return { ok: false, reason: `${broken} is malformed` };
  return {
    ok: true,
    report: {
      generatedAt,
      drying: drying.value,
      reignition: reignition.value,
      evidence: evidence.value,
      agent: agent.value,
    },
  };
}
