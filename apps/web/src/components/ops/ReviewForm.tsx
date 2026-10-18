import { useMutation, useQueryClient } from "@tanstack/react-query";
import { type FormEvent, useState } from "react";
import { isValidNote, REVIEW_NOTE_MAX, reviewCase } from "../../lib/api/review";
import type { Case, ReviewAction } from "../../lib/contracts";
import { REVIEW_ACTIONS, reviewFailureText } from "../../lib/ops/reviewForm";

type ReviewFormProps = { record: Pick<Case, "id" | "cell_id">; onDone: () => void };

export function ReviewForm({ record, onDone }: ReviewFormProps) {
  const queryClient = useQueryClient();
  const [action, setAction] = useState<ReviewAction>("assign");
  const [note, setNote] = useState("");
  const review = useMutation({
    mutationFn: () => reviewCase(record.id, { action, note }),
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
    <form className="review-form" onSubmit={handleSubmit} aria-label={`Review ${record.cell_id}`}>
      <fieldset>
        <legend>Action</legend>
        {REVIEW_ACTIONS.map((option) => (
          <label key={option.id} className="check review-action">
            <input
              type="radio"
              name={`action-${record.id}`}
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
          className="textarea"
          value={note}
          maxLength={REVIEW_NOTE_MAX}
          rows={3}
          onChange={(event) => setNote(event.target.value)}
        />
      </label>
      <button
        type="submit"
        className="btn btn-primary"
        disabled={review.isPending || !isValidNote(note)}
      >
        {review.isPending ? "Saving" : "Save review"}
      </button>
      {review.isError && <p role="alert">{reviewFailureText(review.error)}</p>}
    </form>
  );
}
