import { ApiError } from "../api/client";
import type { ReviewAction } from "../contracts";

export const REVIEW_ACTIONS: readonly { id: ReviewAction; label: string; hint: string }[] = [
  { id: "assign", label: "Assign", hint: "Send the nearest volunteer to check again." },
  { id: "escalate", label: "Escalate", hint: "Send the case and its pack to the brigade." },
  { id: "close", label: "Close", hint: "Close the case with your note." },
];

const FAILURE_TEXT: Record<string, string> = {
  case_not_found: "This case no longer exists.",
  not_in_review: "This case is no longer in human review. Someone else may have acted on it.",
  review_rejected: "The case state does not allow that action now.",
  escalation_rejected: "The brigade escalation was refused. Check the case status.",
};

const GENERIC_FAILURE = "Could not save the review. Try again.";

export function reviewFailureText(error: Error): string {
  if (!(error instanceof ApiError)) return GENERIC_FAILURE;
  if (error.detail === null) return GENERIC_FAILURE;
  return FAILURE_TEXT[error.detail] ?? GENERIC_FAILURE;
}
