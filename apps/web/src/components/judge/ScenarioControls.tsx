import { useMutation, useQueryClient } from "@tanstack/react-query";
import { useEffect, useState } from "react";
import { ApiError } from "../../lib/api/client";
import { type ScenarioEvent, triggerScenario } from "../../lib/api/trigger";
import { useCopyLanguage } from "../../lib/copy/language";
import { type ScenarioCopy, scenarioCopy } from "../../lib/copy/scenario";
import { sourceFor } from "../../lib/sources";

const REFETCH_EVERY_MS = 5_000;
const REFETCH_WINDOW_MS = 90_000;
const FORBIDDEN = 403;
const CONFLICT = 409;
const RATE_LIMITED = 429;

function failureMessage(error: unknown, copy: ScenarioCopy): string {
  if (!(error instanceof ApiError)) return copy.failed;
  if (error.status === FORBIDDEN) return copy.forbidden;
  if (error.status === RATE_LIMITED) return copy.rateLimited;
  if (error.status === CONFLICT) return copy.noRanking;
  return copy.failed;
}

function useCasesRefetch(watchId: number | null, stop: () => void) {
  const queryClient = useQueryClient();

  useEffect(() => {
    if (watchId === null) return;
    const refetch = setInterval(
      () => void queryClient.invalidateQueries({ queryKey: ["cases"] }, { cancelRefetch: false }),
      REFETCH_EVERY_MS,
    );
    const finish = setTimeout(stop, REFETCH_WINDOW_MS);
    return () => {
      clearInterval(refetch);
      clearTimeout(finish);
    };
  }, [watchId, queryClient, stop]);
}

export function ScenarioControls() {
  const copy = scenarioCopy(useCopyLanguage());
  const [watchId, setWatchId] = useState<number | null>(null);
  const trigger = useMutation({
    mutationFn: triggerScenario,
    onSuccess: () => setWatchId(Date.now()),
  });
  useCasesRefetch(watchId, () => setWatchId(null));

  if (sourceFor("clock") === "fixture") return null;

  function start(event: ScenarioEvent) {
    trigger.mutate(event);
  }

  return (
    <>
      <button
        type="button"
        className="btn btn-primary"
        disabled={trigger.isPending}
        onClick={() => start("drying.ranked")}
      >
        {copy.rankingLabel}
      </button>
      <button
        type="button"
        className="btn btn-primary"
        disabled={trigger.isPending}
        onClick={() => start("fire.quiet")}
      >
        {copy.quietLabel}
      </button>
      {watchId !== null && (
        <p role="status" className="judge-note">
          {copy.started}
        </p>
      )}
      {trigger.isError && (
        <p role="alert" className="judge-alert">
          {failureMessage(trigger.error, copy)}
        </p>
      )}
    </>
  );
}
