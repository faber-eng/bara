const STORAGE_KEY = "bara.judgeBar";
const PHONE_QUERY = "(max-width: 700px)";

export type JudgeBarState = "open" | "closed";

const listeners = new Set<() => void>();
let snapshot: JudgeBarState = readStored();

function defaultState(): JudgeBarState {
  if (typeof window.matchMedia !== "function") return "open";
  return window.matchMedia(PHONE_QUERY).matches ? "closed" : "open";
}

function readStored(): JudgeBarState {
  try {
    const stored = localStorage.getItem(STORAGE_KEY);
    if (stored === "open" || stored === "closed") return stored;
    return defaultState();
  } catch {
    return defaultState();
  }
}

function writeStored(state: JudgeBarState): void {
  try {
    localStorage.setItem(STORAGE_KEY, state);
  } catch {
    return;
  }
}

function publish(next: JudgeBarState): void {
  snapshot = next;
  for (const listener of listeners) listener();
}

export function subscribeJudgeBar(listener: () => void): () => void {
  listeners.add(listener);
  return () => listeners.delete(listener);
}

export function getJudgeBarSnapshot(): JudgeBarState {
  return snapshot;
}

export function setJudgeBar(state: JudgeBarState): void {
  writeStored(state);
  publish(state);
}

export function reloadJudgeBar(): void {
  publish(readStored());
}
