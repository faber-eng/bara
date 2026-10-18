import { useQuery } from "@tanstack/react-query";
import { allCellsQuery, cellFactsQuery } from "../../lib/api/queries";
import type { CellFacts } from "../../lib/contracts";
import { type DetailCopy, detailCopy } from "../../lib/copy/detail";
import { type CopyLanguage, useCopyLanguage } from "../../lib/copy/language";
import { damColor } from "../../lib/ops/cellLayer";
import { formatFixed, formatNumber } from "../../lib/public/format";
import { ExplanationText } from "../ops/ExplanationText";
import { QueryState } from "../ops/QueryState";
import { DetailActions, DetailLayout, DetailSection, DetailText, FactList } from "./DetailSheet";
import { chanceText, componentFacts, type FactRow, scoreFact } from "./facts";
import { Sparkline } from "./Sparkline";
import type { OpsDetail } from "./selection";
import { useOpenCase } from "./useOpenCase";

const MIN_TREND_POINTS = 2;

function rankRow(rank: number, total: number | null, copy: DetailCopy): FactRow {
  const value = total === null ? String(rank) : copy.facts.rankOf(rank, total);
  return { label: copy.facts.rank, value, meaning: null };
}

type RankChipProps = { rank: number; total: number | null; copy: DetailCopy };

function RankChip({ rank, total, copy }: RankChipProps) {
  const row = rankRow(rank, total, copy);
  return (
    <span className="chip chip-plain">
      {row.label} {row.value}
    </span>
  );
}

type FactsProps = {
  facts: CellFacts;
  total: number | null;
  copy: DetailCopy;
  language: CopyLanguage;
};

function TrendLine({ facts, copy, language }: Omit<FactsProps, "total">) {
  const scores = facts.trend.map((point) => point.drying_score);
  const first = scores[0];
  const last = scores.at(-1);
  if (scores.length < MIN_TREND_POINTS || first === undefined || last === undefined) return null;
  const text = copy.facts.trendText(
    formatFixed(first, 1, language),
    formatFixed(last, 1, language),
    scores.length,
  );
  return (
    <p className="mv-trend">
      <span className="mv-label">{copy.facts.trend}</span>
      <Sparkline values={scores} />
      <span>{text}</span>
    </p>
  );
}

function NearbyDams({ facts, copy, language }: Omit<FactsProps, "total">) {
  if (facts.nearby_dams.length === 0) return null;
  return (
    <DetailSection label={copy.facts.nearbyDams}>
      <ul className="mv-mini">
        {facts.nearby_dams.map((dam) => (
          <li key={dam.dam_id}>
            <span
              className="mv-swatch-dot"
              style={{ background: damColor(dam.last_state) }}
              aria-hidden="true"
            />
            <span>
              {dam.dam_id} · {copy.damStates[dam.last_state]} ·{" "}
              {formatNumber(Math.round(dam.distance_m), language)} m
            </span>
          </li>
        ))}
      </ul>
    </DetailSection>
  );
}

function PastFires({ facts, copy, language }: Omit<FactsProps, "total">) {
  if (facts.past_fires.length === 0) return null;
  return (
    <DetailSection label={copy.facts.pastFires}>
      <ul className="mv-mini">
        {facts.past_fires.map((fire) => {
          const chance = fire.p_reignite === null ? null : chanceText(fire.p_reignite, language);
          return <li key={fire.event_id}>{copy.facts.fireLine(fire.start_date, chance)}</li>;
        })}
      </ul>
    </DetailSection>
  );
}

function CellFactsSections({ facts, total, copy, language }: FactsProps) {
  const rows = [
    scoreFact(facts.drying_score, copy, language),
    rankRow(facts.rank, total, copy),
    ...componentFacts(facts.components, copy, language),
  ];
  return (
    <>
      <DetailSection label={copy.sections.why}>
        <p className="mv-text">
          {facts.explanation === null ? (
            copy.cell.whyMissing
          ) : (
            <ExplanationText explanation={facts.explanation} />
          )}
        </p>
      </DetailSection>
      <FactList label={copy.sections.numbers} rows={rows}>
        <TrendLine facts={facts} copy={copy} language={language} />
      </FactList>
      <NearbyDams facts={facts} copy={copy} language={language} />
      <PastFires facts={facts} copy={copy} language={language} />
    </>
  );
}

type CellActionsProps = {
  cellId: string;
  caseId: string | undefined;
  copy: DetailCopy;
  onOpen: (detail: OpsDetail) => void;
  onZoom: (cellId: string) => void;
};

function CellActions({ cellId, caseId, copy, onOpen, onZoom }: CellActionsProps) {
  const zoomClass = caseId === undefined ? "btn btn-primary" : "btn btn-secondary";
  return (
    <>
      {caseId !== undefined && (
        <button
          type="button"
          className="btn btn-primary"
          onClick={() => onOpen({ kind: "case", id: caseId })}
        >
          {copy.cell.openCase}
        </button>
      )}
      <button type="button" className={zoomClass} onClick={() => onZoom(cellId)}>
        {copy.cell.zoom}
      </button>
    </>
  );
}

type CellDetailProps = {
  cellId: string;
  region: string;
  onOpen: (detail: OpsDetail) => void;
  onZoom: (cellId: string) => void;
};

export function CellDetail({ cellId, region, onOpen, onZoom }: CellDetailProps) {
  const language = useCopyLanguage();
  const copy = detailCopy(language);
  const facts = useQuery(cellFactsQuery(cellId));
  const total = useQuery(allCellsQuery(region)).data?.cells.length ?? null;
  const caseId = useOpenCase(region, (record) => record.cell_id === cellId);
  const rank = facts.data?.rank;

  return (
    <DetailLayout
      title={copy.cell.title(cellId)}
      chips={rank === undefined ? undefined : <RankChip rank={rank} total={total} copy={copy} />}
    >
      <DetailText label={copy.sections.what}>{copy.cell.what}</DetailText>
      <QueryState
        query={facts}
        label="the numbers"
        emptyText={copy.cell.whyMissing}
        isEmpty={() => false}
      >
        {(data) => <CellFactsSections facts={data} total={total} copy={copy} language={language} />}
      </QueryState>
      {caseId !== undefined && <p className="mv-note">{copy.cell.openCaseNote}</p>}
      <DetailActions label={copy.sections.next}>
        <CellActions cellId={cellId} caseId={caseId} copy={copy} onOpen={onOpen} onZoom={onZoom} />
      </DetailActions>
    </DetailLayout>
  );
}
