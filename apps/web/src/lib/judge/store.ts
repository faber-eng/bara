import { DEFAULT_PERSON_KEY, personFor } from "./people";

const STORAGE_KEY = "bara.judge.person";

export type JudgeSnapshot = { judgeMode: boolean; personKey: string };

let snapshot: JudgeSnapshot = { judgeMode: false, personKey: DEFAULT_PERSON_KEY };
const listeners = new Set<() => void>();

function readStoredKey(): string {
  try {
    const stored = localStorage.getItem(STORAGE_KEY);
    return stored !== null && personFor(stored) ? stored : DEFAULT_PERSON_KEY;
  } catch {
    return DEFAULT_PERSON_KEY;
  }
}

function writeStoredKey(key: string | null): void {
  try {
    if (key === null) localStorage.removeItem(STORAGE_KEY);
    else localStorage.setItem(STORAGE_KEY, key);
  } catch {
    return;
  }
}

function publish(next: JudgeSnapshot): void {
  snapshot = next;
  for (const listener of listeners) listener();
}

export function subscribeJudge(listener: () => void): () => void {
  listeners.add(listener);
  return () => listeners.delete(listener);
}

export function getJudgeSnapshot(): JudgeSnapshot {
  return snapshot;
}

export function setJudgeMode(on: boolean): void {
  if (on === snapshot.judgeMode) return;
  if (on) {
    publish({ judgeMode: true, personKey: readStoredKey() });
    return;
  }
  writeStoredKey(null);
  publish({ judgeMode: false, personKey: DEFAULT_PERSON_KEY });
}

export function selectPerson(key: string): void {
  if (!snapshot.judgeMode || !personFor(key)) return;
  writeStoredKey(key);
  publish({ judgeMode: true, personKey: key });
}

export function roleHeaderValue(): string | undefined {
  if (!snapshot.judgeMode) return undefined;
  return personFor(snapshot.personKey)?.role;
}
