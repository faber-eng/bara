import { useState } from "react";
import type { AreaCell, AreaRanking } from "../../lib/contracts";
import type { DetailCopy } from "../../lib/copy/detail";
import type { CopyLanguage } from "../../lib/copy/language";
import { formatNumber } from "../../lib/public/format";
import { DetailActions, DetailLayout, DetailText, FactList } from "./DetailSheet";
import { type FactRow, scoreFact } from "./facts";

type CopyState = "idle" | "copied" | "failed";

function areaRows(
  cell: AreaCell,
  ranking: AreaRanking,
  copy: DetailCopy,
  language: CopyLanguage,
): FactRow[] {
  return [
    scoreFact(cell.drying_score, copy, language),
    {
      label: copy.facts.rank,
      value: copy.facts.rankOf(cell.rank, ranking.cells.length),
      meaning: null,
    },
    {
      label: copy.facts.areaSize,
      value: `${formatNumber(Math.round(ranking.area_km2), language)} km²`,
      meaning: null,
    },
    {
      label: copy.facts.peatCells,
      value: formatNumber(ranking.peat_cells, language),
      meaning: null,
    },
  ];
}

function copyStatus(state: CopyState, copy: DetailCopy): string | null {
  if (state === "copied") return copy.areaCell.copied;
  if (state === "failed") return copy.areaCell.copyFailed;
  return null;
}

type AreaCellDetailProps = {
  cell: AreaCell;
  ranking: AreaRanking;
  copy: DetailCopy;
  language: CopyLanguage;
};

export function AreaCellDetail({ cell, ranking, copy, language }: AreaCellDetailProps) {
  const [state, setState] = useState<CopyState>("idle");
  const status = copyStatus(state, copy);

  async function handleCopy() {
    try {
      await navigator.clipboard.writeText(cell.cell_id);
      setState("copied");
    } catch {
      setState("failed");
    }
  }

  return (
    <DetailLayout
      title={copy.areaCell.title(cell.cell_id)}
      chips={
        <span className="chip chip-plain">
          {copy.areaCell.rankOfArea(cell.rank, ranking.cells.length)}
        </span>
      }
    >
      <DetailText label={copy.sections.what}>{copy.areaCell.what}</DetailText>
      <DetailText label={copy.sections.why}>{copy.areaCell.why}</DetailText>
      <FactList label={copy.sections.numbers} rows={areaRows(cell, ranking, copy, language)} />
      <DetailActions label={copy.sections.next}>
        <button type="button" className="btn btn-primary" onClick={() => void handleCopy()}>
          {copy.areaCell.copy}
        </button>
      </DetailActions>
      {status !== null && (
        <p role="status" className="mv-note">
          {status}
        </p>
      )}
    </DetailLayout>
  );
}
