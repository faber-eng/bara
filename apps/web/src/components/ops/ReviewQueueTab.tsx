import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { type FormEvent, useState } from "react";
import { casesQuery } from "../../lib/api/queries";
import { isValidNote, REVIEW_NOTE_MAX, reviewCase } from "../../lib/api/review";
import type { CaseSummary, ReviewAction } from "../../lib/contracts";
import { spaced } from "../../lib/ops/caseDrawer";
import { regionById } from "../../lib/ops/region";
import { REVIEW_ACTIONS, reviewFailureText } from "../../lib/ops/reviewForm";
import { QueryState } from "./QueryState";

type ReviewFormProps = { summary: CaseSummary; onDone: () => void };

function ReviewForm({ summary, onDone }: ReviewFormProps) {
  const queryClient = useQueryClient();
  const [action, setAction] = useState<ReviewAction>("assign");
  const [note, setNote] = useState("");
  const review = useMutation({
    mutationFn: () => reviewCase(summary.case.id, { action, note }),
    onSuccess: onDone,
    onSettled: async () => {
      await Promise.all([
        queryClient.invalidateQueries({ queryKey: ["cases"] }),
        queryClient.invalidateQueries({ queryKey: ["brigade", "inbox"] }),
      ]);
    },
  });

  function handleSubmit(event: FormEvent) {
    event.preventDefault();
    if (isValidNote(note) && !review.isPending) review.mutate();
  }

  return (
    <form
      className="review-form"
      onSubmit={handleSubmit}
      aria-label={`Review ${summary.case.cell_id}`}
    >
      <fieldset>
        <legend>Action</legend>
        {REVIEW_ACTIONS.map((option) => (
          <label key={option.id} className="review-action">
            <input
              type="radio"
              name={`action-${summary.case.id}`}
              checked={action === option.id}
              onChange={() => setAction(option.id)}
            />
            <span>
              <strong>{option.label}</strong> <span className="ops-meta">{option.hint}</span>
            </span>
          </label>
        ))}
      </fieldset>
      <label className="review-note">
        <span>Note (required)</span>
        <textarea
          value={note}
          maxLength={REVIEW_NOTE_MAX}
          rows={3}
          onChange={(event) => setNote(event.target.value)}
        />
      </label>
      <button
        type="submit"
        className="btn btn-primary btn-sm"
        disabled={review.isPending || !isValidNote(note)}
      >
        {review.isPending ? "Saving" : "Save review"}
      </button>
      {review.isError && <p role="alert">{reviewFailureText(review.error)}</p>}
    </form>
  );
}

type ReviewRowProps = {
  summary: CaseSummary;
  open: boolean;
  onToggle: (caseId: string) => void;
  onOpenCase: (caseId: string) => void;
};

function ReviewRow({ summary, open, onToggle, onOpenCase }: ReviewRowProps) {
  const record = summary.case;
  return (
    <li className={open ? "is-selected" : undefined}>
      <div className="review-row">
        <span className="ops-cell">
          <strong>
            {record.cell_id} · {spaced(record.type)}
          </strong>
          <span className="ops-meta">Opened {record.opened_at}</span>
        </span>
        <span className="review-row-actions">
          <button
            type="button"
            className="btn btn-quiet btn-sm"
            onClick={() => onOpenCase(record.id)}
          >
            Open case
          </button>
          <button
            type="button"
            className="btn btn-secondary btn-sm"
            aria-expanded={open}
            onClick={() => onToggle(record.id)}
          >
            Review
          </button>
        </span>
      </div>
      {open && <ReviewForm summary={summary} onDone={() => onToggle(record.id)} />}
    </li>
  );
}

type ReviewQueueTabProps = { region: string; onCaseSelect: (caseId: string) => void };

export function ReviewQueueTab({ region, onCaseSelect }: ReviewQueueTabProps) {
  const info = regionById(region);
  const cases = useQuery({ ...casesQuery(region), enabled: info.casework });
  const [openId, setOpenId] = useState<string | null>(null);

  function handleToggle(caseId: string) {
    setOpenId((current) => (current === caseId ? null : caseId));
  }

  if (!info.casework) return <p className="ops-state">{info.note}</p>;
  return (
    <QueryState
      query={cases}
      label="the review queue"
      emptyText="Nothing waits for human review."
      isEmpty={(data) => data.every((summary) => summary.case.status !== "human_review")}
    >
      {(data) => (
        <ul className="ops-list ops-list--cases">
          {data
            .filter((summary) => summary.case.status === "human_review")
            .map((summary) => (
              <ReviewRow
                key={summary.case.id}
                summary={summary}
                open={summary.case.id === openId}
                onToggle={handleToggle}
                onOpenCase={onCaseSelect}
              />
            ))}
        </ul>
      )}
    </QueryState>
  );
}
