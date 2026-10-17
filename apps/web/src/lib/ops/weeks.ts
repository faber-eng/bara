export const FIRST_WEEK = "2026-W20";

const WEEK_PATTERN = /^(\d{4})-W(\d{2})$/;
const MAX_WEEKS = 106;

type WeekParts = { year: number; week: number };

function partsOf(label: string): WeekParts | undefined {
  const match = WEEK_PATTERN.exec(label);
  if (match === null) return undefined;
  return { year: Number(match[1]), week: Number(match[2]) };
}

function labelOf({ year, week }: WeekParts): string {
  return `${year}-W${String(week).padStart(2, "0")}`;
}

function isLeapYear(year: number): boolean {
  return (year % 4 === 0 && year % 100 !== 0) || year % 400 === 0;
}

function weeksInYear(year: number): number {
  const jan1 = new Date(Date.UTC(year, 0, 1)).getUTCDay();
  const longYear = jan1 === 4 || (isLeapYear(year) && jan1 === 3);
  return longYear ? 53 : 52;
}

function nextWeek({ year, week }: WeekParts): WeekParts {
  if (week < weeksInYear(year)) return { year, week: week + 1 };
  return { year: year + 1, week: 1 };
}

function isBefore(a: WeekParts, b: WeekParts): boolean {
  return a.year < b.year || (a.year === b.year && a.week < b.week);
}

export function parseWeek(value: unknown): string | undefined {
  if (typeof value !== "string") return undefined;
  const parts = partsOf(value);
  if (parts === undefined || parts.week < 1 || parts.week > weeksInYear(parts.year)) {
    return undefined;
  }
  return value;
}

export function weekRange(latest: string | undefined): string[] {
  const last = latest === undefined ? undefined : partsOf(latest);
  const first = partsOf(FIRST_WEEK);
  if (first === undefined || last === undefined || isBefore(last, first)) return [FIRST_WEEK];
  const weeks: string[] = [];
  let cursor = first;
  while (weeks.length < MAX_WEEKS) {
    weeks.push(labelOf(cursor));
    if (!isBefore(cursor, last)) break;
    cursor = nextWeek(cursor);
  }
  return weeks;
}

export function neighbourWeeks(weeks: readonly string[], week: string): string[] {
  const index = weeks.indexOf(week);
  if (index < 0) return [];
  const neighbours = [weeks[index - 1], weeks[index + 1]];
  return neighbours.filter((neighbour): neighbour is string => neighbour !== undefined);
}

export function requestWeek(
  week: string | undefined,
  latest: string | undefined,
): string | undefined {
  if (week === undefined || week === latest) return undefined;
  return week;
}

export function selectedWeek(
  week: string | undefined,
  latest: string | undefined,
): string | undefined {
  return week ?? latest;
}

export function effectiveWeek(
  week: string | undefined,
  latest: string | undefined,
): string | undefined {
  if (week === undefined) return undefined;
  if (latest === undefined) return week;
  if (week === latest) return undefined;
  return weekRange(latest).includes(week) ? week : undefined;
}
