import type { ScenarioEvent } from "../api/trigger";

export type TourAction =
  | { kind: "trigger"; event: ScenarioEvent; label: string }
  | { kind: "advance"; hours: number; label: string };

export type TourStep = {
  id: string;
  title: string;
  body: string;
  href: string;
  personKey: string;
  action?: TourAction;
};

export const TOUR_STEPS: readonly TourStep[] = [
  {
    id: "world",
    title: "The world, with no sign-in",
    body: "Anyone can open this page. It shows this week's peat risk in Riau, the response record and a written bulletin.",
    href: "/public",
    personKey: "ops",
  },
  {
    id: "ranking",
    title: "Ops: the ranked areas",
    body: "Use the week slider, then open the number one area. Gemini explains the rank and cites the numbers behind it.",
    href: "/ops",
    personKey: "ops",
  },
  {
    id: "assign",
    title: "Start the weekly ranking",
    body: "This sends the drying.ranked event. An agent opens cases for the top areas and picks people. It takes about 30 seconds.",
    href: "/ops?tab=cases",
    personKey: "ops",
    action: { kind: "trigger", event: "drying.ranked", label: "Start: weekly ranking" },
  },
  {
    id: "stream",
    title: "Watch the agent decide",
    body: "Open a case in the list. The drawer streams each agent step as it happens: ranking, facts, people, task.",
    href: "/ops?tab=cases",
    personKey: "ops",
  },
  {
    id: "evidence",
    title: "Volunteer Ari sends evidence",
    body: "You are now Ari on a phone view. Press Photo, then Use a sample to send a broken-dam photo. The verdict appears in seconds.",
    href: "/v/vol-ari",
    personKey: "vol-ari",
  },
  {
    id: "quiet",
    title: "After the fire",
    body: "A fire has gone quiet. This sends the fire.quiet event. The map shows the burn scar and the areas that may burn again.",
    href: "/ops?tab=cases",
    personKey: "ops",
    action: { kind: "trigger", event: "fire.quiet", label: "Start: fire goes quiet" },
  },
  {
    id: "clock",
    title: "Move the clock 48 hours",
    body: "The agent planned a patrol recheck in 48 hours. Move the clock and watch cases become overdue and escalate.",
    href: "/ops?tab=cases",
    personKey: "ops",
    action: { kind: "advance", hours: 48, label: "+48h" },
  },
  {
    id: "brigade",
    title: "The brigade inbox",
    body: "The brigade gets one brief with the photo, the map and the timeline, in Indonesian and English.",
    href: "/brigade",
    personKey: "contact-daops-pekanbaru",
  },
  {
    id: "anywhere",
    title: "Anywhere in the world",
    body: "Congo ranks with the same method. You can also draw any area and rank it live.",
    href: "/ops?region=congo_cuvette",
    personKey: "ops",
  },
];

export const FIRST_STEP = 0;
export const LAST_STEP = TOUR_STEPS.length - 1;

export function clampStep(step: number): number {
  if (!Number.isInteger(step)) return FIRST_STEP;
  return Math.min(Math.max(step, FIRST_STEP), LAST_STEP);
}
