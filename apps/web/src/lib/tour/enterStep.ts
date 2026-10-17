import type { QueryClient } from "@tanstack/react-query";
import type { RouterHistory } from "@tanstack/react-router";
import { invalidateWorld } from "../judge/invalidate";
import { getJudgeSnapshot, selectPerson } from "../judge/store";
import { clampStep, TOUR_STEPS } from "./steps";
import { goToStep, startTour } from "./store";

type Deps = { history: RouterHistory; queryClient: QueryClient };

function enter(index: number, deps: Deps, begin: (step: number) => void): void {
  const step = clampStep(index);
  const target = TOUR_STEPS[step];
  if (target === undefined) return;
  const personChanged = getJudgeSnapshot().personKey !== target.personKey;
  begin(step);
  selectPerson(target.personKey);
  deps.history.push(target.href);
  if (personChanged) void invalidateWorld(deps.queryClient);
}

export function beginTourAt(index: number, deps: Deps): void {
  enter(index, deps, startTour);
}

export function moveTourTo(index: number, deps: Deps): void {
  enter(index, deps, goToStep);
}
