import type { AreaRanking } from "../../lib/contracts";
import type { AreaCopy } from "../../lib/copy/area";

const SCORE_DECIMALS = 1;

export function AreaResult({ ranking, copy }: { ranking: AreaRanking; copy: AreaCopy }) {
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
      <ol className="area-cells">
        {ranking.cells.map((cell) => (
          <li key={cell.cell_id}>
            {copy.cellScore(
              cell.rank,
              cell.cell_id,
              Number(cell.drying_score.toFixed(SCORE_DECIMALS)),
            )}
          </li>
        ))}
      </ol>
      {ranking.cached && <p className="field-hint">{copy.cachedNote}</p>}
    </section>
  );
}
