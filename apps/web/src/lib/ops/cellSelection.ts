import type { RankedCell, RankedDam } from "../contracts";

export function selectedCell(
  cells: readonly RankedCell[],
  cellId: string | undefined,
): RankedCell | undefined {
  if (cellId === undefined) return undefined;
  return cells.find((cell) => cell.cell_id === cellId);
}

export function rowSelection(rowCellId: string, selectedCellId: string | undefined): boolean {
  return rowCellId === selectedCellId;
}

export function damCellId(dam: RankedDam): string {
  return dam.cell_id;
}

export function parseCellId(value: unknown): string | undefined {
  return typeof value === "string" && value !== "" ? value : undefined;
}
