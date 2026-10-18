import type { CaseStatus } from "../../lib/contracts";
import type { DetailCopy } from "../../lib/copy/detail";
import { statusChip } from "../../lib/ops/statusChip";
import { scoreLevel } from "./facts";

export function ScoreBadge({ score }: { score: number }) {
  return <span className={`score-badge score-${scoreLevel(score)} num`}>{score.toFixed(1)}</span>;
}

type StatusBadgeProps = { status: CaseStatus; copy: DetailCopy };

export function StatusBadge({ status, copy }: StatusBadgeProps) {
  return <span className={`chip ${statusChip(status).className}`}>{copy.statuses[status]}</span>;
}
