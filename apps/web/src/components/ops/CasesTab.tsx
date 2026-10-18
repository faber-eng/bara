import { useQuery } from "@tanstack/react-query";
import { casesQuery, clockQuery } from "../../lib/api/queries";
import type { CaseSummary } from "../../lib/contracts";
import { detailCopy } from "../../lib/copy/detail";
import { useCopyLanguage } from "../../lib/copy/language";
import { regionById } from "../../lib/ops/region";
import { StatusBadge } from "../detail/badges";
import { Countdown } from "./Countdown";
import { QueryState } from "./QueryState";

type CaseRowProps = {
  summary: CaseSummary;
  nowMs: number;
  simClock: boolean;
  selected: boolean;
  onSelect: (caseId: string) => void;
};

function CaseRow({ summary, nowMs, simClock, selected, onSelect }: CaseRowProps) {
  const copy = detailCopy(useCopyLanguage());
  const record = summary.case;
  return (
    <li>
      <button
        type="button"
        className="ops-row mv-row"
        aria-pressed={selected}
        onClick={() => onSelect(record.id)}
      >
        <span className="mv-row-main">
          <strong className="mv-row-title">
            {copy.caseTypes[record.type]} · {record.cell_id}
          </strong>
          <StatusBadge status={record.status} copy={copy} />
        </span>
        {summary.next_deadline_at === null ? (
          <span className="mv-row-meta">No open task</span>
        ) : (
          <Countdown deadline={summary.next_deadline_at} nowMs={nowMs} simClock={simClock} />
        )}
      </button>
    </li>
  );
}

type CasesTabProps = {
  region: string;
  selectedCaseId: string | undefined;
  onSelect: (caseId: string) => void;
};

export function CasesTab({ region, selectedCaseId, onSelect }: CasesTabProps) {
  const info = regionById(region);
  const cases = useQuery({ ...casesQuery(region), enabled: info.casework });
  const clock = useQuery(clockQuery);
  const nowMs = clock.data ? Date.parse(clock.data.now) : Date.now();
  const simClock = clock.data?.judge_mode === true;

  if (!info.casework) return <p className="ops-state">{info.note}</p>;
  return (
    <QueryState
      query={cases}
      label="cases"
      emptyText="No cases yet."
      isEmpty={(data) => data.length === 0}
    >
      {(data) => (
        <>
          <ul className="ops-list ops-list--cases mv-list">
            {data.map((summary) => (
              <CaseRow
                key={summary.case.id}
                summary={summary}
                nowMs={nowMs}
                simClock={simClock}
                selected={summary.case.id === selectedCaseId}
                onSelect={onSelect}
              />
            ))}
          </ul>
          <p className="ops-foot">
            Showing {data.length} of {data.length} cases. Countdowns follow the sim clock, not the
            wall clock.
          </p>
        </>
      )}
    </QueryState>
  );
}
