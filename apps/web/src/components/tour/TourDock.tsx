import { useMutation, useQueryClient } from "@tanstack/react-query";
import { useRouter } from "@tanstack/react-router";
import { useSyncExternalStore } from "react";
import { advanceClock } from "../../lib/api/clock";
import { clockQuery } from "../../lib/api/queries";
import { triggerScenario } from "../../lib/api/trigger";
import { useCopyLanguage } from "../../lib/copy/language";
import { type ScenarioCopy, scenarioCopy } from "../../lib/copy/scenario";
import { type TourCopy, tourCopy } from "../../lib/copy/tour";
import { invalidateWorld } from "../../lib/judge/invalidate";
import { moveTourTo } from "../../lib/tour/enterStep";
import { FIRST_STEP, LAST_STEP, TOUR_STEPS, type TourAction } from "../../lib/tour/steps";
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

function actionLabel(action: TourAction, copy: TourCopy, scenario: ScenarioCopy): string {
  if (action.kind === "advance") return copy.advanceLabel(action.hours);
  if (action.event === "drying.ranked") return scenario.rankingLabel;
  return scenario.quietLabel;
}

export function TourDock() {
  const { open, step } = useSyncExternalStore(subscribeTour, getTourSnapshot);
  const router = useRouter();
  const queryClient = useQueryClient();
  const run = useTourAction();
  const language = useCopyLanguage();
  const copy = tourCopy(language);
  const scenario = scenarioCopy(language);
  const current = TOUR_STEPS[step];
  if (!open || current === undefined) return null;

  const deps = { history: router.history, queryClient };
  const isFirst = step === FIRST_STEP;
  const isLast = step === LAST_STEP;
  const action = current.action;
  const stepCopy = copy.steps[current.id];

  function move(index: number) {
    run.reset();
    moveTourTo(index, deps);
  }

  return (
    <aside className="tour-dock" aria-label={copy.dockLabel}>
      <p className="tour-progress">{copy.progress(step + 1, TOUR_STEPS.length)}</p>
      <h2 className="tour-title">{stepCopy.title}</h2>
      <p className="tour-body">{stepCopy.body}</p>
      {action && (
        <button
          type="button"
          className="btn btn-primary btn-sm"
          disabled={run.isPending}
          onClick={() => run.mutate(action)}
        >
          {actionLabel(action, copy, scenario)}
        </button>
      )}
      {run.isSuccess && (
        <p role="status" className="tour-note">
          {action?.kind === "advance" ? copy.clockMoved : copy.triggerSent}
        </p>
      )}
      {run.isError && (
        <p role="alert" className="tour-note tour-alert">
          {failureMessage(run.error, scenario)}
        </p>
      )}
      <div className="tour-buttons">
        <button type="button" className="btn btn-quiet btn-sm" onClick={skipTour}>
          {copy.skip}
        </button>
        {!isFirst && (
          <button type="button" className="btn btn-secondary btn-sm" onClick={() => move(step - 1)}>
            {copy.back}
          </button>
        )}
        {isLast ? (
          <button type="button" className="btn btn-primary btn-sm" onClick={finishTour}>
            {copy.finish}
          </button>
        ) : (
          <button type="button" className="btn btn-primary btn-sm" onClick={() => move(step + 1)}>
            {copy.next}
          </button>
        )}
      </div>
    </aside>
  );
}
