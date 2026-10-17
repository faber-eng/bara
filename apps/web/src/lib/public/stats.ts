import type { PublicSummary } from "../contracts";
import type { StatKey } from "../copy/public";

export type StatReading = { key: StatKey; value: number | null; escalated?: number };

export function statReadings(summary: PublicSummary, rankingOnly: boolean): StatReading[] {
  const ranking: StatReading[] = [{ key: "high_risk_cells", value: summary.high_risk_cells }];
  if (rankingOnly) return ranking;
  return [
    ...ranking,
    { key: "dams_broken", value: summary.dams_broken },
    { key: "cases_open", value: summary.cases_open, escalated: summary.cases_escalated },
    { key: "median_days_to_repair", value: summary.median_days_to_repair },
    { key: "tasks_on_time_pct", value: summary.tasks_on_time_pct },
  ];
}
