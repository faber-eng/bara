import type { AreaCell, AreaRanking } from "../../lib/contracts";
import type { AreaCopy } from "../../lib/copy/area";
import type { DetailCopy } from "../../lib/copy/detail";
import { ScoreBadge } from "../detail/badges";

type AreaRowProps = {
  cell: AreaCell;
  total: number;
  selected: boolean;
  detail: DetailCopy;
  onSelect: (cellId: string) => void;
};

function AreaRow({ cell, total, selected, detail, onSelect }: AreaRowProps) {
  return (
    <li>
      <button
        type="button"
        className="mv-row"
        aria-pressed={selected}
        onClick={() => onSelect(cell.cell_id)}
      >
        <span className="mv-row-main">
          <strong className="mv-row-title">{cell.cell_id}</strong>
          <span className="mv-row-meta">{detail.areaCell.rankOfArea(cell.rank, total)}</span>
        </span>
        <ScoreBadge score={cell.drying_score} />
      </button>
    </li>
  );
}

type AreaResultProps = {
  ranking: AreaRanking;
  copy: AreaCopy;
  detail: DetailCopy;
  selectedCellId: string | undefined;
  onSelect: (cellId: string) => void;
};

export function AreaResult({ ranking, copy, detail, selectedCellId, onSelect }: AreaResultProps) {
  if (ranking.status === "no_peat") {
    return (
      <p role="status" className="card card-sunk">
        {copy.noPeat}
      </p>
    );
  }
  return (
    <section className="card area-result" aria-label={copy.resultTitle(ranking.week)}>
      <h2 className="join-heading">{copy.resultTitle(ranking.week)}</h2>
      <p className="field-hint">{copy.resultMeta(ranking.peat_cells, ranking.area_km2)}</p>
      <ol className="mv-list">
        {ranking.cells.map((cell) => (
          <AreaRow
            key={cell.cell_id}
            cell={cell}
            total={ranking.cells.length}
            selected={cell.cell_id === selectedCellId}
            detail={detail}
            onSelect={onSelect}
          />
        ))}
      </ol>
      {ranking.cached && <p className="field-hint">{copy.cachedNote}</p>}
    </section>
  );
}
