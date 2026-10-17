import { useSyncExternalStore } from "react";

export type CopyLanguage = "id" | "en";

const STORAGE_KEY = "bara.copy-language";
const DEFAULT_COPY_LANGUAGE: CopyLanguage = "en";

function isCopyLanguage(value: string | null): value is CopyLanguage {
  return value === "id" || value === "en";
}

function readStored(): CopyLanguage {
  try {
    const stored = localStorage.getItem(STORAGE_KEY);
    return isCopyLanguage(stored) ? stored : DEFAULT_COPY_LANGUAGE;
  } catch {
    return DEFAULT_COPY_LANGUAGE;
  }
}

function writeStored(language: CopyLanguage): void {
  try {
    localStorage.setItem(STORAGE_KEY, language);
  } catch {
    return;
  }
}

function syncDocumentLang(language: CopyLanguage): void {
  if (typeof document !== "undefined") document.documentElement.lang = language;
}

let current: CopyLanguage = readStored();
syncDocumentLang(current);
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
  writeStored(next);
  syncDocumentLang(next);
  for (const listener of listeners) listener();
}

export function useCopyLanguage(): CopyLanguage {
  return useSyncExternalStore(subscribe, getSnapshot);
}
