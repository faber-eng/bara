import { useQuery } from "@tanstack/react-query";
import { rankingsQuery } from "../../lib/api/queries";
import type { RankedCell } from "../../lib/contracts";
import { OPS_REGION } from "../../lib/ops/region";
import { QueryState } from "./QueryState";

const SCORE_STEP = 20;
const MAX_SCORE_CLASS = 5;

function scoreClass(score: number): string {
  const level = Math.min(MAX_SCORE_CLASS, Math.floor(score / SCORE_STEP) + 1);
  return `score-${level}`;
}

function radarText(cell: RankedCell): string {
  const value = cell.components.s1_anom_db;
  if (value === null) return "radar n/a";
  const stale = cell.stale_s1 ? " (stale)" : "";
  return `radar ${value.toFixed(1)} dB${stale}`;
}

function factsText(cell: RankedCell): string {
  const canal = `canal ${Math.round(cell.components.canal_dist_m)} m`;
  const rain = `rain deficit ${Math.round(cell.components.rain_deficit_pct * 100)}%`;
  return `${canal} · ${rain} · ${radarText(cell)}`;
}

function RankChange({ value }: { value: number | null }) {
  if (value === null) return <span title="Not ranked last week">new</span>;
  if (value === 0) return <span title="No change">-</span>;
  if (value > 0) return <span title={`Up ${value} places`}>↑{value}</span>;
  return <span title={`Down ${Math.abs(value)} places`}>↓{Math.abs(value)}</span>;
}

function RankedRow({ cell }: { cell: RankedCell }) {
  return (
    <tr>
      <td className="ops-rank">{cell.rank}</td>
      <td>
        <span className={`score-badge ${scoreClass(cell.drying_score)}`}>
          {cell.drying_score.toFixed(1)}
        </span>
      </td>
      <td className="ops-cell">
        <strong>{cell.cell_id}</strong>
        <span className="ops-meta">{factsText(cell)}</span>
        {cell.explanation !== null && (
          <span className="ops-meta ops-explain">
            <span className="chip chip-gemini">Gemini</span> {cell.explanation.text}
          </span>
        )}
      </td>
      <td className="ops-change">
        <RankChange value={cell.rank_change} />
      </td>
    </tr>
  );
}

function RankedTable({ cells, week }: { cells: RankedCell[]; week: string }) {
  const ordered = [...cells].sort((a, b) => a.rank - b.rank);
  return (
    <>
      <table className="ops-table">
        <caption className="visually-hidden">Ranked areas, {week}</caption>
        <thead>
          <tr>
            <th scope="col">Rank</th>
            <th scope="col">Score (0 to 100)</th>
            <th scope="col">Area</th>
            <th scope="col">Vs last week</th>
          </tr>
        </thead>
        <tbody>
          {ordered.map((cell) => (
            <RankedRow key={cell.cell_id} cell={cell} />
          ))}
        </tbody>
      </table>
      <p className="ops-foot">
        Showing {ordered.length} of {ordered.length} cells for {week}. Scores are drying_score, 0 to
        100.
      </p>
    </>
  );
}

export function RankedAreasTab() {
  const rankings = useQuery(rankingsQuery(OPS_REGION));
  return (
    <QueryState
      query={rankings}
      label="ranked areas"
      emptyText="No ranked areas for this week."
      isEmpty={(data) => data.cells.length === 0}
    >
      {(data) => <RankedTable cells={data.cells} week={data.week} />}
    </QueryState>
  );
}
