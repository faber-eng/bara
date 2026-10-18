import type { Case, CaseSummary, RankedCell, RankedDam } from "../../lib/contracts";
import { componentBars } from "../../lib/ops/componentBars";

export type RankedFilter = "all" | "needsPerson" | "caseOpen";

export const RANKED_FILTERS: readonly RankedFilter[] = ["all", "needsPerson", "caseOpen"];

export type RowReason =
  | { kind: "brokenDam" }
  | { kind: "radar"; value: number }
  | { kind: "rain"; value: number }
  | { kind: "canal"; value: number };

const DRIVER_KEYS = new Set(["s1_anom_db", "rain_deficit_pct", "canal_dist_m"]);

export function openCaseByCell(cases: readonly CaseSummary[] | undefined): Map<string, Case> {
  const byCell = new Map<string, Case>();
  for (const summary of cases ?? []) {
    const record = summary.case;
    if (record.status === "closed" || byCell.has(record.cell_id)) continue;
    byCell.set(record.cell_id, record);
  }
  return byCell;
}

export function brokenDamCells(dams: readonly RankedDam[]): Set<string> {
  const cells = new Set<string>();
  for (const dam of dams) {
    if (dam.last_state === "broken") cells.add(dam.cell_id);
  }
  return cells;
}

function driverReason(cell: RankedCell): RowReason | null {
  let best: { key: string; share: number } | null = null;
  for (const bar of componentBars(cell.components)) {
    if (!DRIVER_KEYS.has(bar.key) || bar.share <= 0) continue;
    if (best === null || bar.share > best.share) best = { key: bar.key, share: bar.share };
  }
  if (best === null) return null;
  const { s1_anom_db, rain_deficit_pct, canal_dist_m } = cell.components;
  if (best.key === "s1_anom_db" && s1_anom_db !== null) return { kind: "radar", value: s1_anom_db };
  if (best.key === "rain_deficit_pct") return { kind: "rain", value: rain_deficit_pct };
  return { kind: "canal", value: canal_dist_m };
}

export function mainReason(cell: RankedCell, brokenDams: ReadonlySet<string>): RowReason | null {
  if (brokenDams.has(cell.cell_id)) return { kind: "brokenDam" };
  return driverReason(cell);
}

export function matchesFilter(filter: RankedFilter, hasCase: boolean): boolean {
  if (filter === "needsPerson") return !hasCase;
  if (filter === "caseOpen") return hasCase;
  return true;
}

export type FilterCounts = Record<RankedFilter, number>;

export function filterCounts(
  cells: readonly RankedCell[],
  openCases: ReadonlyMap<string, Case>,
): FilterCounts {
  let caseOpen = 0;
  for (const cell of cells) {
    if (openCases.has(cell.cell_id)) caseOpen += 1;
  }
  return { all: cells.length, needsPerson: cells.length - caseOpen, caseOpen };
}
