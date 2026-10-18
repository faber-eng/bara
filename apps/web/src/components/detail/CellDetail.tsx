import { useQuery } from "@tanstack/react-query";
import { allCellsQuery, cellFactsQuery } from "../../lib/api/queries";
import type { CellFacts, RankExplanation } from "../../lib/contracts";
import { type DetailCopy, detailCopy } from "../../lib/copy/detail";
import { type CopyLanguage, useCopyLanguage } from "../../lib/copy/language";
import { damColor } from "../../lib/ops/cellLayer";
import { regionById } from "../../lib/ops/region";
import { formatFixed, formatNumber } from "../../lib/public/format";
import { ExplanationHow, ExplanationText } from "../ops/ExplanationText";
import { QueryState } from "../ops/QueryState";
import {
  DetailAbout,
  DetailActions,
  DetailLayout,
  DetailSection,
  FactGroupsSection,
} from "./DetailSheet";
import { chanceText, componentGroups } from "./facts";
import { ScoreKeyFact } from "./ScoreKeyFact";
import { SendSomeone } from "./SendSomeone";
import { Sparkline } from "./Sparkline";
import type { OpsDetail } from "./selection";
import { useOpenCase } from "./useOpenCase";

const MIN_TREND_POINTS = 2;

type FactsProps = {
  facts: CellFacts;
  total: number | null;
  copy: DetailCopy;
  language: CopyLanguage;
};

function TrendAside({ facts, copy, language }: Omit<FactsProps, "total">) {
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
    <div className="mv-trend">
      <Sparkline values={scores} />
      <span className="mv-trend-text">
        {copy.facts.trend}: {text}
      </span>
    </div>
  );
}

function CellKeyFact({ facts, total, copy, language }: FactsProps) {
  return (
    <ScoreKeyFact
      score={facts.drying_score}
      rank={facts.rank}
      total={total}
      copy={copy}
      language={language}
      aside={<TrendAside facts={facts} copy={copy} language={language} />}
    />
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

function WhyText({ explanation, copy }: { explanation: RankExplanation | null; copy: DetailCopy }) {
  if (explanation === null) return <p className="mv-text">{copy.cell.whyMissing}</p>;
  return <ExplanationText explanation={explanation} copy={copy} />;
}

function CellFactsSections({ facts, copy, language }: Omit<FactsProps, "total">) {
  return (
    <>
      <DetailSection label={copy.sections.why}>
        <WhyText explanation={facts.explanation} copy={copy} />
        {facts.explanation !== null && (
          <ExplanationHow explanation={facts.explanation} copy={copy} />
        )}
      </DetailSection>
      <FactGroupsSection
        label={copy.sections.numbers}
        groups={componentGroups(facts.components, copy, language)}
      />
      <NearbyDams facts={facts} copy={copy} language={language} />
      <PastFires facts={facts} copy={copy} language={language} />
    </>
  );
}

type CellActionsProps = {
  cellId: string;
  caseId: string | undefined;
  canSend: boolean;
  copy: DetailCopy;
  onOpen: (detail: OpsDetail) => void;
  onZoom: (cellId: string) => void;
};

function CellActions({ cellId, caseId, canSend, copy, onOpen, onZoom }: CellActionsProps) {
  const zoomIsPrimary = caseId === undefined && !canSend;
  const zoomClass = zoomIsPrimary ? "btn btn-primary" : "btn btn-secondary";
  return (
    <>
      {canSend && <SendSomeone cellId={cellId} copy={copy.cell.send} />}
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
  const canSend = caseId === undefined && regionById(region).casework;

  return (
    <DetailLayout title={copy.cell.title(cellId)}>
      {facts.data !== undefined && (
        <CellKeyFact facts={facts.data} total={total} copy={copy} language={language} />
      )}
      <DetailActions>
        <CellActions
          cellId={cellId}
          caseId={caseId}
          canSend={canSend}
          copy={copy}
          onOpen={onOpen}
          onZoom={onZoom}
        />
      </DetailActions>
      {caseId !== undefined && <p className="mv-note">{copy.cell.openCaseNote}</p>}
      <QueryState
        query={facts}
        label="the numbers"
        emptyText={copy.cell.whyMissing}
        isEmpty={() => false}
      >
        {(data) => <CellFactsSections facts={data} copy={copy} language={language} />}
      </QueryState>
      <DetailAbout label={copy.sections.what}>{copy.cell.what}</DetailAbout>
    </DetailLayout>
  );
}
