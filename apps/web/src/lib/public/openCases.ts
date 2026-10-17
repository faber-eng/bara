import type { RecordLine } from "../contracts";

export function openCaseCells(record: readonly RecordLine[]): string[] {
  const latest = new Map<string, RecordLine>();
  for (const line of record) {
    const seen = latest.get(line.cell_id);
    if (seen === undefined || seen.at < line.at) latest.set(line.cell_id, line);
  }
  const open: string[] = [];
  for (const [cellId, line] of latest) {
    if (line.kind !== "closed") open.push(cellId);
  }
  return open;
}
