import { useMutation, useQueryClient } from "@tanstack/react-query";
import { ApiError } from "../../lib/api/client";
import { advanceClock, resetClock } from "../../lib/api/clock";
import { clockQuery } from "../../lib/api/queries";
import type { ClockState } from "../../lib/contracts";
import { invalidateWorldSettled } from "../../lib/judge/invalidate";

const ADVANCE_HOURS = [6, 24, 48] as const;
const RATE_LIMITED = 429;

function resetMessage(error: unknown): string {
  if (error instanceof ApiError && error.status === RATE_LIMITED) {
    return "Reset is rate-limited. Wait a minute and try again.";
  }
  return "Could not reset the scenario. Try again.";
}

export function ClockControls() {
  const queryClient = useQueryClient();

  async function applyClock(state: ClockState) {
    queryClient.setQueryData(clockQuery.queryKey, state);
    await invalidateWorldSettled(queryClient);
  }

  const advance = useMutation({ mutationFn: advanceClock, onSuccess: applyClock });
  const reset = useMutation({ mutationFn: resetClock, onSuccess: applyClock });
  const busy = advance.isPending || reset.isPending;

  function handleAdvance(hours: number) {
    reset.reset();
    advance.mutate(hours);
  }

  function handleReset() {
    advance.reset();
    reset.mutate();
  }

  return (
    <>
      {ADVANCE_HOURS.map((hours) => (
        <button
          key={hours}
          type="button"
          className="btn btn-primary"
          disabled={busy}
          onClick={() => handleAdvance(hours)}
        >
          +{hours}h
        </button>
      ))}
      <button type="button" className="btn btn-secondary" disabled={busy} onClick={handleReset}>
        Reset scenario
      </button>
      {advance.isError && (
        <p role="alert" className="judge-alert">
          Could not move the clock. Try again.
        </p>
      )}
      {reset.isError && (
        <p role="alert" className="judge-alert">
          {resetMessage(reset.error)}
        </p>
      )}
    </>
  );
}
