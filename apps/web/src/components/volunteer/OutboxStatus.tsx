import type { VolunteerCopy } from "../../lib/copy/volunteer";
import { useOutboxDrain } from "./useOutboxDrain";

type OutboxStatusProps = { copy: VolunteerCopy; volunteerId: string };

export function OutboxStatus({ copy, volunteerId }: OutboxStatusProps) {
  const outbox = useOutboxDrain(volunteerId);
  if (outbox.waiting === 0) return null;
  return (
    <div role="status" className="banner banner-warn">
      <p>{copy.outboxWaiting(outbox.waiting)}</p>
      <button type="button" className="btn btn-secondary btn-sm" onClick={outbox.sendNow}>
        {copy.outboxSendNow}
      </button>
    </div>
  );
}
