const MINUTE_MS = 60_000;
const MINUTES_PER_HOUR = 60;
const MINUTES_PER_DAY = 1440;
const SIM_TIME_ZONE = "Asia/Jakarta";

export type Countdown = { kind: "due" | "overdue"; days: number; hours: number };

export function countdown(deadlineIso: string, simNowMs: number): Countdown {
  const gapMs = Date.parse(deadlineIso) - simNowMs;
  const minutes = Math.round(Math.abs(gapMs) / MINUTE_MS);
  const days = Math.floor(minutes / MINUTES_PER_DAY);
  const hours = Math.floor((minutes % MINUTES_PER_DAY) / MINUTES_PER_HOUR);
  return { kind: gapMs > 0 ? "due" : "overdue", days, hours };
}

function spanLabel({ days, hours }: Countdown): string {
  if (days === 0 && hours === 0) return "less than 1 h";
  if (days === 0) return `${hours} h`;
  return `${days} d ${hours} h`;
}

export function countdownLabel(value: Countdown): string {
  const prefix = value.kind === "due" ? "Due in" : "Overdue by";
  return `${prefix} ${spanLabel(value)}`;
}

const simTimeFormat = new Intl.DateTimeFormat("en-GB", {
  timeZone: SIM_TIME_ZONE,
  day: "numeric",
  month: "short",
  year: "numeric",
  hour: "2-digit",
  minute: "2-digit",
  hourCycle: "h23",
});

export function formatSimTime(iso: string): string {
  const parts = new Map(simTimeFormat.formatToParts(new Date(iso)).map((p) => [p.type, p.value]));
  const date = `${parts.get("day")} ${parts.get("month")} ${parts.get("year")}`;
  return `${date}, ${parts.get("hour")}:${parts.get("minute")}`;
}

const simShortFormat = new Intl.DateTimeFormat("en-GB", {
  timeZone: SIM_TIME_ZONE,
  day: "numeric",
  month: "short",
  hour: "2-digit",
  minute: "2-digit",
  hourCycle: "h23",
});

export function formatSimTimeShort(iso: string): string {
  const parts = new Map(simShortFormat.formatToParts(new Date(iso)).map((p) => [p.type, p.value]));
  return `${parts.get("day")} ${parts.get("month")} ${parts.get("hour")}:${parts.get("minute")}`;
}
