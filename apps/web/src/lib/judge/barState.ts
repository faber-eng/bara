const STORAGE_KEY = "bara.judgeBar";

export type JudgeBarState = "open" | "closed";

const listeners = new Set<() => void>();
let snapshot: JudgeBarState = readStored();

function readStored(): JudgeBarState {
  try {
    return localStorage.getItem(STORAGE_KEY) === "closed" ? "closed" : "open";
  } catch {
    return "open";
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
