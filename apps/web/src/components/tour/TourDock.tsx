import { useMutation, useQueryClient } from "@tanstack/react-query";
import { useRouter } from "@tanstack/react-router";
import { useSyncExternalStore } from "react";
import { advanceClock } from "../../lib/api/clock";
import { clockQuery } from "../../lib/api/queries";
import { triggerScenario } from "../../lib/api/trigger";
import { scenarioCopy } from "../../lib/copy/scenario";
import { invalidateWorld } from "../../lib/judge/invalidate";
import { moveTourTo } from "../../lib/tour/enterStep";
import { LAST_STEP, TOUR_STEPS, type TourAction } from "../../lib/tour/steps";
import { finishTour, getTourSnapshot, skipTour, subscribeTour } from "../../lib/tour/store";
import { failureMessage } from "../judge/ScenarioControls";

function useTourAction() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async (action: TourAction) => {
      if (action.kind === "trigger") return void (await triggerScenario(action.event));
      const state = await advanceClock(action.hours);
      queryClient.setQueryData(clockQuery.queryKey, state);
      await invalidateWorld(queryClient);
    },
  });
}

export function TourDock() {
  const { open, step } = useSyncExternalStore(subscribeTour, getTourSnapshot);
  const router = useRouter();
  const queryClient = useQueryClient();
  const run = useTourAction();
  const current = TOUR_STEPS[step];
  if (!open || current === undefined) return null;

  const deps = { history: router.history, queryClient };
  const isFirst = step === 0;
  const isLast = step === LAST_STEP;
  const action = current.action;

  function move(index: number) {
    run.reset();
    moveTourTo(index, deps);
  }

  return (
    <aside className="tour-dock" aria-label="Guided tour">
      <p className="tour-progress">
        Step {step + 1} of {TOUR_STEPS.length}
      </p>
      <h2 className="tour-title">{current.title}</h2>
      <p className="tour-body">{current.body}</p>
      {action && (
        <button
          type="button"
          className="btn btn-primary btn-sm"
          disabled={run.isPending}
          onClick={() => run.mutate(action)}
        >
          {action.label}
        </button>
      )}
      {run.isSuccess && (
        <p role="status" className="tour-note">
          Done. Wait about 30 seconds for the result, then press Next.
        </p>
      )}
      {run.isError && (
        <p role="alert" className="tour-note tour-alert">
          {failureMessage(run.error, scenarioCopy("en"))}
        </p>
      )}
      <div className="tour-buttons">
        <button type="button" className="btn btn-quiet btn-sm" onClick={skipTour}>
          Skip tour
        </button>
        {!isFirst && (
          <button type="button" className="btn btn-secondary btn-sm" onClick={() => move(step - 1)}>
            Back
          </button>
        )}
        {isLast ? (
          <TourFinish onFinish={finishTour} />
        ) : (
          <button type="button" className="btn btn-primary btn-sm" onClick={() => move(step + 1)}>
            Next
          </button>
        )}
      </div>
    </aside>
  );
}

function TourFinish({ onFinish }: { onFinish: () => void }) {
  return (
    <button type="button" className="btn btn-primary btn-sm" onClick={onFinish}>
      Finish
    </button>
  );
}
