import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { closeCase } from "../../lib/api/caseDetail";
import { allCellsQuery, clockQuery } from "../../lib/api/queries";
import type { CaseDetail, Task } from "../../lib/contracts";
import { type DetailCopy, detailCopy } from "../../lib/copy/detail";
import { type CopyLanguage, useCopyLanguage } from "../../lib/copy/language";
import { canCloseCase } from "../../lib/ops/caseDrawer";
import { ruleEscalationEntries } from "../../lib/ops/timelineOrigin";
import { useCaseDetail } from "../../lib/ops/useCaseDetail";
import { AgentRuns } from "../ops/AgentRuns";
import { CaseTimeline } from "../ops/CaseTimeline";
import { countdownText } from "../ops/Countdown";
import { EvidenceCard } from "../ops/EvidenceCard";
import { QueryState } from "../ops/QueryState";
import { StatusBadge } from "./badges";
import { DetailActions, DetailLayout, DetailSection, DetailText, FactList } from "./DetailSheet";
import { chanceText, type FactRow, scoreFact } from "./facts";
import type { OpsDetail } from "./selection";

const OPEN_TASK_STATUSES: readonly Task["status"][] = ["open", "overdue"];

function CloseButton({ caseId }: { caseId: string }) {
  const queryClient = useQueryClient();
  const close = useMutation({
    mutationFn: () => closeCase(caseId),
    onSettled: () => queryClient.invalidateQueries({ queryKey: ["cases"] }),
  });
  return (
    <>
      <button
        type="button"
        className="btn btn-primary"
        disabled={close.isPending}
        onClick={() => close.mutate()}
      >
        {close.isPending ? "Closing" : "Close case"}
      </button>
      {close.isError && <p role="alert">Could not close the case. Try again.</p>}
    </>
  );
}

function nextDeadline(tasks: readonly Task[]): string | null {
  let next: string | null = null;
  for (const task of tasks) {
    if (!OPEN_TASK_STATUSES.includes(task.status)) continue;
    if (next === null || Date.parse(task.deadline_at) < Date.parse(next)) next = task.deadline_at;
  }
  return next;
}

function useTimeLeft(detail: CaseDetail, copy: DetailCopy): string {
  const clock = useQuery(clockQuery);
  const deadline = nextDeadline(detail.tasks);
  if (deadline === null) return copy.facts.noOpenTask;
  const nowMs = clock.data ? Date.parse(clock.data.now) : Date.now();
  return countdownText({ deadline, nowMs, simClock: clock.data?.judge_mode === true });
}

type CaseFactsProps = { detail: CaseDetail; copy: DetailCopy; language: CopyLanguage };

function useCaseRows({ detail, copy, language }: CaseFactsProps): FactRow[] {
  const record = detail.case;
  const cell = useQuery(allCellsQuery(record.region)).data?.cells.find(
    (item) => item.cell_id === record.cell_id,
  );
  const timeLeft = useTimeLeft(detail, copy);
  const rows: FactRow[] = [];
  const score = record.risk.drying_score ?? cell?.drying_score ?? null;
  if (score !== null) rows.push(scoreFact(score, copy, language));
  if (cell !== undefined)
    rows.push({ label: copy.facts.rank, value: String(cell.rank), meaning: null });
  if (record.risk.p_reignite !== null) {
    rows.push({
      label: copy.facts.reignite,
      value: chanceText(record.risk.p_reignite, language),
      meaning: null,
    });
  }
  rows.push({ label: copy.facts.timeLeft, value: timeLeft, meaning: null });
  rows.push({ label: copy.facts.evidence, value: String(detail.evidence.length), meaning: null });
  return rows;
}

function latestDecision(detail: CaseDetail): string | null {
  for (let index = detail.agent_runs.length - 1; index >= 0; index -= 1) {
    const decision = detail.agent_runs[index]?.final_json;
    if (decision !== undefined && decision !== null)
      return `${decision.decision}: ${decision.reason}`;
  }
  return null;
}

function EvidenceList({ detail, onWhy }: { detail: CaseDetail; onWhy: () => void }) {
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

type CaseBodyProps = CaseFactsProps & { onOpen: (detail: OpsDetail) => void };

function CaseBody({ detail, copy, language, onOpen }: CaseBodyProps) {
  const [openRunId, setOpenRunId] = useState<string | null>(null);
  const record = detail.case;
  const rows = useCaseRows({ detail, copy, language });
  const lastRun = detail.agent_runs.at(-1);
  const closable = canCloseCase(record.status);

  function handleWhy() {
    if (lastRun !== undefined) setOpenRunId(lastRun.id);
  }

  function handleRunToggle(runId: string, open: boolean) {
    if (open) setOpenRunId(runId);
    else setOpenRunId((current) => (current === runId ? null : current));
  }

  return (
    <>
      <DetailText label={copy.sections.what}>{copy.caseWhat[record.type]}</DetailText>
      <DetailText label={copy.sections.why}>
        {latestDecision(detail) ?? copy.case.whyMissing}
      </DetailText>
      <FactList label={copy.sections.numbers} rows={rows} />
      <DetailActions label={copy.sections.next}>
        {closable && <CloseButton caseId={record.id} />}
        <button
          type="button"
          className={closable ? "btn btn-secondary" : "btn btn-primary"}
          onClick={() => onOpen({ kind: "cell", id: record.cell_id })}
        >
          {copy.case.showArea}
        </button>
      </DetailActions>
      <DetailSection label={copy.case.timeline}>
        <CaseTimeline entries={detail.timeline} ruleMade={ruleEscalationEntries(detail)} />
      </DetailSection>
      <DetailSection label={copy.case.evidenceTitle}>
        <EvidenceList detail={detail} onWhy={handleWhy} />
      </DetailSection>
      <DetailSection label={copy.case.agentRuns}>
        <AgentRuns runs={detail.agent_runs} openRunId={openRunId} onOpenChange={handleRunToggle} />
      </DetailSection>
    </>
  );
}

function CaseChips({ detail, copy }: { detail: CaseDetail; copy: DetailCopy }) {
  return (
    <>
      <StatusBadge status={detail.case.status} copy={copy} />
      {detail.case.example && <span className="chip chip-example">{copy.case.example}</span>}
    </>
  );
}

type CaseItemDetailProps = { caseId: string; onOpen: (detail: OpsDetail) => void };

export function CaseItemDetail({ caseId, onOpen }: CaseItemDetailProps) {
  const language = useCopyLanguage();
  const copy = detailCopy(language);
  const detail = useCaseDetail(caseId);
  const record = detail.data?.case;
  const title =
    record === undefined ? caseId : copy.case.title(copy.caseTypes[record.type], record.cell_id);

  return (
    <DetailLayout
      title={title}
      chips={detail.data === undefined ? undefined : <CaseChips detail={detail.data} copy={copy} />}
    >
      <QueryState
        query={detail}
        label="the case"
        emptyText="This case has no detail."
        isEmpty={() => false}
      >
        {(data) => <CaseBody detail={data} copy={copy} language={language} onOpen={onOpen} />}
      </QueryState>
    </DetailLayout>
  );
}
