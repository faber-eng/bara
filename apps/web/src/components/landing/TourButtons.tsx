import { useQueryClient } from "@tanstack/react-query";
import { Link, useRouter } from "@tanstack/react-router";
import { useSyncExternalStore } from "react";
import type { LandingCopy } from "../../lib/copy/landing";
import { beginTourAt } from "../../lib/tour/enterStep";
import { FIRST_STEP, TOUR_STEPS } from "../../lib/tour/steps";
import { getTourSnapshot, subscribeTour } from "../../lib/tour/store";

export function TourButtons({ copy }: { copy: LandingCopy }) {
  const router = useRouter();
  const queryClient = useQueryClient();
  const { step } = useSyncExternalStore(subscribeTour, getTourSnapshot);
  const deps = { history: router.history, queryClient };
  const resuming = step > FIRST_STEP;

  return (
    <div className="landing-actions">
      <button
        type="button"
        className="btn btn-primary btn-lg"
        onClick={() => beginTourAt(FIRST_STEP, deps)}
      >
        {copy.startTour}
      </button>
      {resuming && (
        <button
          type="button"
          className="btn btn-secondary btn-lg"
          onClick={() => beginTourAt(step, deps)}
        >
          {copy.resumeTour(step + 1, TOUR_STEPS.length)}
        </button>
      )}
      <Link to="/public" className="btn btn-secondary btn-lg">
        {copy.explore}
      </Link>
    </div>
  );
}
