import { useQuery } from "@tanstack/react-query";
import { casesQuery, clockQuery } from "../../lib/api/queries";
import type { CaseSummary } from "../../lib/contracts";
import { OPS_REGION } from "../../lib/ops/region";
import { statusChip } from "../../lib/ops/statusChip";
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
  const chip = statusChip(summary.case.status);
  return (
    <li className={selected ? "is-selected" : undefined}>
      <button
        type="button"
        className="ops-row"
        aria-pressed={selected}
        onClick={() => onSelect(summary.case.id)}
      >
        <span className="ops-cell">
          <strong>
            {summary.case.cell_id} · {summary.case.type}
          </strong>
          {summary.next_deadline_at === null ? (
            <span className="ops-meta">No open task</span>
          ) : (
            <Countdown deadline={summary.next_deadline_at} nowMs={nowMs} simClock={simClock} />
          )}
        </span>
        <span className={`chip ${chip.className}`}>{chip.label}</span>
      </button>
    </li>
  );
}

type CasesTabProps = { selectedCaseId: string | undefined; onSelect: (caseId: string) => void };

export function CasesTab({ selectedCaseId, onSelect }: CasesTabProps) {
  const cases = useQuery(casesQuery(OPS_REGION));
  const clock = useQuery(clockQuery);
  const nowMs = clock.data ? Date.parse(clock.data.now) : Date.now();
  const simClock = clock.data?.judge_mode === true;

  return (
    <QueryState
      query={cases}
      label="cases"
      emptyText="No cases yet."
      isEmpty={(data) => data.length === 0}
    >
      {(data) => (
        <>
          <ul className="ops-list ops-list--cases">
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
