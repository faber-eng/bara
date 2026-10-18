import { useState } from "react";
import type { AreaCell, AreaRanking } from "../../lib/contracts";
import type { DetailCopy } from "../../lib/copy/detail";
import type { CopyLanguage } from "../../lib/copy/language";
import { formatNumber } from "../../lib/public/format";
import { DetailAbout, DetailActions, DetailLayout, DetailText, FactSection } from "./DetailSheet";
import type { FactRow } from "./facts";
import { ScoreKeyFact } from "./ScoreKeyFact";

type CopyState = "idle" | "copied" | "failed";

function areaRows(ranking: AreaRanking, language: CopyLanguage, copy: DetailCopy): FactRow[] {
  return [
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
    <DetailLayout title={copy.areaCell.title(cell.cell_id)}>
      <ScoreKeyFact
        score={cell.drying_score}
        rank={cell.rank}
        total={ranking.cells.length}
        copy={copy}
        language={language}
      />
      <DetailActions>
        <button type="button" className="btn btn-primary" onClick={() => void handleCopy()}>
          {copy.areaCell.copy}
        </button>
      </DetailActions>
      {status !== null && (
        <p role="status" className="mv-note">
          {status}
        </p>
      )}
      <DetailText label={copy.sections.why}>{copy.areaCell.why}</DetailText>
      <FactSection label={copy.sections.numbers} rows={areaRows(ranking, language, copy)} />
      <DetailAbout label={copy.sections.what}>{copy.areaCell.what}</DetailAbout>
    </DetailLayout>
  );
}
