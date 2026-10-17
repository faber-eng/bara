import { useSyncExternalStore } from "react";

export type CopyLanguage = "id" | "en";

let current: CopyLanguage = "id";
const listeners = new Set<() => void>();

function subscribe(listener: () => void): () => void {
  listeners.add(listener);
  return () => listeners.delete(listener);
}

function getSnapshot(): CopyLanguage {
  return current;
}

export function setCopyLanguage(next: CopyLanguage): void {
  if (next === current) return;
  current = next;
  for (const listener of listeners) listener();
}

export function useCopyLanguage(): CopyLanguage {
  return useSyncExternalStore(subscribe, getSnapshot);
}
