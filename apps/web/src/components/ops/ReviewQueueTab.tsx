import { useQuery } from "@tanstack/react-query";
import { casesQuery } from "../../lib/api/queries";
import type { CaseSummary } from "../../lib/contracts";
import { detailCopy } from "../../lib/copy/detail";
import { useCopyLanguage } from "../../lib/copy/language";
import { regionById } from "../../lib/ops/region";
import { ScoreBadge } from "../detail/badges";
import { QueryState } from "./QueryState";

function inReview(summary: CaseSummary): boolean {
  return summary.case.status === "human_review";
}

type ReviewRowProps = { summary: CaseSummary; onOpen: (caseId: string) => void };

function ReviewRow({ summary, onOpen }: ReviewRowProps) {
  const copy = detailCopy(useCopyLanguage());
  const record = summary.case;
  const score = record.risk.drying_score;
  return (
    <li>
      <button type="button" className="ops-row mv-row" onClick={() => onOpen(record.id)}>
        <span className="mv-row-main">
          <strong className="mv-row-title">
            {copy.caseTypes[record.type]} · {record.cell_id}
          </strong>
          <span className="chip chip-human-review mv-row-chip">{copy.review.chip}</span>
        </span>
        {score !== null && <ScoreBadge score={score} />}
      </button>
    </li>
  );
}

function NothingToReview({ onShowCases }: { onShowCases: () => void }) {
  return (
    <div className="mv-empty">
      <h2 className="mv-empty-title">Nothing to review</h2>
      <p>
        A photo or voice verdict lands here when Gemini is unsure (confidence under the review
        limit) or a volunteer reports a problem.
      </p>
      <button type="button" className="btn btn-secondary btn-sm" onClick={onShowCases}>
        Show open cases
      </button>
    </div>
  );
}

type ReviewQueueTabProps = {
  region: string;
  onOpen: (caseId: string) => void;
  onShowCases: () => void;
};

export function ReviewQueueTab({ region, onOpen, onShowCases }: ReviewQueueTabProps) {
  const info = regionById(region);
  const cases = useQuery({ ...casesQuery(region), enabled: info.casework });

  if (!info.casework) return <p className="ops-state">{info.note}</p>;
  return (
    <QueryState
      query={cases}
      label="the review queue"
      emptyText="Nothing to review"
      empty={<NothingToReview onShowCases={onShowCases} />}
      isEmpty={(data) => !data.some(inReview)}
    >
      {(data) => (
        <ul className="ops-list ops-list--cases mv-list">
          {data.filter(inReview).map((summary) => (
            <ReviewRow key={summary.case.id} summary={summary} onOpen={onOpen} />
          ))}
        </ul>
      )}
    </QueryState>
  );
}
