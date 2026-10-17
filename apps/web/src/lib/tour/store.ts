import { clampStep, FIRST_STEP } from "./steps";

const STORAGE_KEY = "bara.tour";

export type TourState = { open: boolean; step: number };

const CLOSED_AT_START: TourState = { open: false, step: FIRST_STEP };

let snapshot: TourState = readStored();
const listeners = new Set<() => void>();

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null;
}

function parseStored(raw: string | null): TourState {
  if (raw === null) return CLOSED_AT_START;
  try {
    const value: unknown = JSON.parse(raw);
    if (!isRecord(value)) return CLOSED_AT_START;
    const step = typeof value.step === "number" ? clampStep(value.step) : FIRST_STEP;
    return { open: value.open === true, step };
  } catch {
    return CLOSED_AT_START;
  }
}

function readStored(): TourState {
  try {
    return parseStored(localStorage.getItem(STORAGE_KEY));
  } catch {
    return CLOSED_AT_START;
  }
}

function writeStored(state: TourState): void {
  try {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(state));
  } catch {
    return;
  }
}

function publish(next: TourState): void {
  snapshot = next;
  writeStored(next);
  for (const listener of listeners) listener();
}

export function subscribeTour(listener: () => void): () => void {
  listeners.add(listener);
  return () => listeners.delete(listener);
}

export function getTourSnapshot(): TourState {
  return snapshot;
}

export function startTour(step = FIRST_STEP): void {
  publish({ open: true, step: clampStep(step) });
}

export function goToStep(step: number): void {
  publish({ open: true, step: clampStep(step) });
}

export function skipTour(): void {
  publish({ open: false, step: snapshot.step });
}

export function finishTour(): void {
  publish({ open: false, step: FIRST_STEP });
}
