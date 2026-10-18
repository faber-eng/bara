import { useMutation, useQueryClient } from "@tanstack/react-query";
import { useEffect, useRef, useState } from "react";
import { closeCase } from "../../lib/api/caseDetail";

import type { CaseDetail } from "../../lib/contracts";
import { canCloseCase, spaced } from "../../lib/ops/caseDrawer";
import { statusChip } from "../../lib/ops/statusChip";
import { ruleEscalationEntries } from "../../lib/ops/timelineOrigin";
import { useCaseDetail } from "../../lib/ops/useCaseDetail";
import { AgentRuns } from "./AgentRuns";
import { CaseTimeline } from "./CaseTimeline";
import { EvidenceCard } from "./EvidenceCard";
import { QueryState } from "./QueryState";

function CloseButton({ caseId }: { caseId: string }) {
  const queryClient = useQueryClient();
  const close = useMutation({
    mutationFn: () => closeCase(caseId),
    onSettled: () => queryClient.invalidateQueries({ queryKey: ["cases"] }),
  });
  return (
    <div className="drawer-close">
      <button
        type="button"
        className="btn btn-primary btn-sm"
        disabled={close.isPending}
        onClick={() => close.mutate()}
      >
        {close.isPending ? "Closing" : "Close case"}
      </button>
      {close.isError && <p role="alert">Could not close the case. Try again.</p>}
    </div>
  );
}

function DrawerHead({ detail }: { detail: CaseDetail }) {
  const record = detail.case;
  const chip = statusChip(record.status);
  const headingRef = useRef<HTMLHeadingElement>(null);
  useEffect(() => headingRef.current?.focus(), []);
  return (
    <header className="drawer-head">
      <h2 ref={headingRef} tabIndex={-1}>
        {record.cell_id} · {spaced(record.type)}
      </h2>
      <p>
        <span className={`chip ${chip.className}`}>{chip.label}</span>
        {record.example && <span className="chip chip-example">Example data</span>}
      </p>
      {canCloseCase(record.status) && <CloseButton caseId={record.id} />}
    </header>
  );
}

function EvidenceSection({ detail, onWhy }: { detail: CaseDetail; onWhy: () => void }) {
  if (detail.evidence.length === 0) return <p className="ops-meta">No evidence yet.</p>;
  const canExplain = detail.agent_runs.length > 0;
  return (
    <ul className="evidence-list">
      {detail.evidence.map((evidence) => (
        <EvidenceCard key={evidence.id} evidence={evidence} canExplain={canExplain} onWhy={onWhy} />
      ))}
    </ul>
  );
}

function DrawerBody({ detail }: { detail: CaseDetail }) {
  const [openRunId, setOpenRunId] = useState<string | null>(null);
  const lastRun = detail.agent_runs.at(-1);

  function handleWhy() {
    if (lastRun !== undefined) setOpenRunId(lastRun.id);
  }

  function handleRunToggle(runId: string, open: boolean) {
    if (open) setOpenRunId(runId);
    else setOpenRunId((current) => (current === runId ? null : current));
  }

  return (
    <>
      <DrawerHead detail={detail} />
      <section className="drawer-section" aria-label="Timeline">
        <h3>Timeline</h3>
        <CaseTimeline entries={detail.timeline} ruleMade={ruleEscalationEntries(detail)} />
      </section>
      <section className="drawer-section" aria-label="Evidence">
        <h3>Evidence</h3>
        <EvidenceSection detail={detail} onWhy={handleWhy} />
      </section>
      <section className="drawer-section" aria-label="Agent runs">
        <h3>Agent runs</h3>
        <AgentRuns runs={detail.agent_runs} openRunId={openRunId} onOpenChange={handleRunToggle} />
      </section>
    </>
  );
}

type CaseDrawerProps = { caseId: string; onBack: () => void };

export function CaseDrawer({ caseId, onBack }: CaseDrawerProps) {
  const detail = useCaseDetail(caseId);
  return (
    <section className="drawer" aria-label="Case detail">
      <button type="button" className="btn btn-quiet btn-sm" onClick={onBack}>
        Back to list
      </button>
      <QueryState
        query={detail}
        label="the case"
        emptyText="This case has no detail."
        isEmpty={() => false}
      >
        {(data) => <DrawerBody key={data.case.id} detail={data} />}
      </QueryState>
    </section>
  );
}
