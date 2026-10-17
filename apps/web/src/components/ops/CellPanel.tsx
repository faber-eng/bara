import { useQuery } from "@tanstack/react-query";
import { cellFactsQuery } from "../../lib/api/queries";
import type { CellFacts, RankingComponents } from "../../lib/contracts";
import { QueryState } from "./QueryState";

type CellPanelProps = { cellId: string; onClose: () => void };

function componentRows(components: RankingComponents): [string, string][] {
  const radar = components.s1_anom_db === null ? "n/a" : `${components.s1_anom_db.toFixed(1)} dB`;
  return [
    ["Radar change", radar],
    ["Rain, 30 days", `${components.rain_30d_mm.toFixed(1)} mm`],
    ["Rain deficit", `${Math.round(components.rain_deficit_pct * 100)}%`],
    ["Canal distance", `${Math.round(components.canal_dist_m)} m`],
    ["Peat class", String(components.peat_class)],
  ];
}

function CellFactsBody({ facts }: { facts: CellFacts }) {
  return (
    <>
      <div className="cell-panel-stats">
        <span>
          <span className="cell-panel-label">Drying score</span>
          <strong className="num">{facts.drying_score.toFixed(1)}</strong>
        </span>
        <span>
          <span className="cell-panel-label">Rank</span>
          <strong className="num">{facts.rank}</strong>
        </span>
      </div>
      <dl className="cell-panel-components">
        {componentRows(facts.components).map(([name, value]) => (
          <div key={name}>
            <dt>{name}</dt>
            <dd className="num">{value}</dd>
          </div>
        ))}
      </dl>
      {facts.explanation !== null && (
        <p className="cell-panel-explain">
          <span className="chip chip-gemini">Gemini</span> {facts.explanation.text}
        </p>
      )}
      {facts.nearby_dams.length > 0 && (
        <p className="ops-meta">
          {facts.nearby_dams.length} dam{facts.nearby_dams.length === 1 ? "" : "s"} nearby:{" "}
          {facts.nearby_dams.map((dam) => `${dam.dam_id} (${dam.last_state})`).join(", ")}
        </p>
      )}
    </>
  );
}

export function CellPanel({ cellId, onClose }: CellPanelProps) {
  const facts = useQuery(cellFactsQuery(cellId));
  return (
    <section className="cell-panel" aria-label={`Cell ${cellId}`}>
      <header className="cell-panel-head">
        <h2>{cellId}</h2>
        <button type="button" className="btn btn-secondary btn-sm" onClick={onClose}>
          Close
        </button>
      </header>
      <QueryState
        query={facts}
        label="cell details"
        emptyText="No details for this cell."
        isEmpty={() => false}
      >
        {(data) => <CellFactsBody facts={data} />}
      </QueryState>
    </section>
  );
}
