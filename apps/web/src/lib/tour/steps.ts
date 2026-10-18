import type { ScenarioEvent } from "../api/trigger";

export const TOUR_STEP_IDS = [
  "world",
  "ranking",
  "assign",
  "stream",
  "evidence",
  "quiet",
  "clock",
  "brigade",
  "anywhere",
] as const;

export type TourStepId = (typeof TOUR_STEP_IDS)[number];

export type TourAction =
  | { kind: "trigger"; event: ScenarioEvent }
  | { kind: "advance"; hours: number };

export type TourStep = {
  id: TourStepId;
  href: string;
  personKey: string;
  action?: TourAction;
};

export const TOUR_STEPS: readonly TourStep[] = [
  { id: "world", href: "/public", personKey: "ops" },
  { id: "ranking", href: "/ops", personKey: "ops" },
  {
    id: "assign",
    href: "/ops?tab=cases",
    personKey: "ops",
    action: { kind: "trigger", event: "drying.ranked" },
  },
  { id: "stream", href: "/ops?tab=cases", personKey: "ops" },
  { id: "evidence", href: "/v/vol-ari", personKey: "vol-ari" },
  {
    id: "quiet",
    href: "/ops?tab=cases",
    personKey: "ops",
    action: { kind: "trigger", event: "fire.quiet" },
  },
  {
    id: "clock",
    href: "/ops?tab=cases",
    personKey: "ops",
    action: { kind: "advance", hours: 48 },
  },
  { id: "brigade", href: "/brigade", personKey: "contact-daops-pekanbaru" },
  { id: "anywhere", href: "/ops?region=congo_cuvette", personKey: "ops" },
];

export const FIRST_STEP = 0;
export const LAST_STEP = TOUR_STEPS.length - 1;

export function clampStep(step: number): number {
  if (!Number.isInteger(step)) return FIRST_STEP;
  return Math.min(Math.max(step, FIRST_STEP), LAST_STEP);
}
