import type { EvidenceEval, FieldAccuracy } from "../eval/report";

const PHOTO_KIND = "photo";
const DAM_STATE_FIELD = "dam_state";

export function photoDamState(evidence: EvidenceEval | null): FieldAccuracy | null {
  const photos = evidence?.sets.find((set) => set.kind === PHOTO_KIND);
  return photos?.fields.find((field) => field.field === DAM_STATE_FIELD) ?? null;
}
