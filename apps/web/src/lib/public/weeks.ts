const WEEK_PATTERN = /^(\d{4})-W(\d{2})$/;
const DAY_MS = 86_400_000;
const WEEK_DAYS = 7;
export const FIRST_PUBLIC_WEEK = "2026-W20";
export const WEEK_CHOICES = 12;

export function parseWeekLabel(value: unknown): string | undefined {
  return typeof value === "string" && WEEK_PATTERN.test(value) ? value : undefined;
}

function mondayOf(label: string): Date {
  const match = WEEK_PATTERN.exec(label);
  const year = Number(match?.[1]);
  const week = Number(match?.[2]);
  const januaryFourth = new Date(Date.UTC(year, 0, 4));
  const dayOfWeek = januaryFourth.getUTCDay() === 0 ? 7 : januaryFourth.getUTCDay();
  const firstMonday = januaryFourth.getTime() - (dayOfWeek - 1) * DAY_MS;
  return new Date(firstMonday + (week - 1) * WEEK_DAYS * DAY_MS);
}

function labelOf(monday: Date): string {
  const thursday = new Date(monday.getTime() + 3 * DAY_MS);
  const year = thursday.getUTCFullYear();
  const yearStart = Date.UTC(year, 0, 1);
  const week = Math.floor((thursday.getTime() - yearStart) / (DAY_MS * WEEK_DAYS)) + 1;
  return `${year}-W${String(week).padStart(2, "0")}`;
}

export function weekChoices(latest: string, count = WEEK_CHOICES): string[] {
  const start = mondayOf(latest).getTime();
  const labels: string[] = [];
  for (let step = 0; step < count; step += 1) {
    const label = labelOf(new Date(start - step * WEEK_DAYS * DAY_MS));
    if (label < FIRST_PUBLIC_WEEK) break;
    labels.push(label);
  }
  return labels;
}
