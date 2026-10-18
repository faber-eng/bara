import type { Evidence, EvidenceKind, TaskType } from "../contracts";

export const PICK_KINDS = ["photo", "voice", "video"] as const;
export type PickKind = (typeof PICK_KINDS)[number];

const KINDS_BY_TASK = {
  dam_check: ["photo", "voice", "video"],
  dam_repair: ["photo", "video"],
  patrol_recheck: ["photo", "voice", "video"],
} as const satisfies Record<TaskType, readonly PickKind[]>;

const EVIDENCE_KIND_OF = {
  photo: "photo",
  voice: "audio",
  video: "video",
} as const satisfies Record<PickKind, EvidenceKind>;

export function kindsForTask(type: TaskType): readonly PickKind[] {
  return KINDS_BY_TASK[type];
}

export function evidenceKindOf(kind: PickKind): EvidenceKind {
  return EVIDENCE_KIND_OF[kind];
}

export function sentKindsFor(evidence: readonly Evidence[], taskId: string): Set<EvidenceKind> {
  const sent = new Set<EvidenceKind>();
  for (const item of evidence) {
    if (item.task_id === taskId) sent.add(item.kind);
  }
  return sent;
}
