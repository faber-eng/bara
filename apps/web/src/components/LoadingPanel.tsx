import { useEffect, useState } from "react";
import { useCopyLanguage } from "../lib/copy/language";
import { loadingCopy } from "../lib/copy/loading";
import { EmberMark } from "./EmberMark";

export const SLOW_LOAD_MS = 4000;

function useSlowLoad(): boolean {
  const [slow, setSlow] = useState(false);
  useEffect(() => {
    const timer = setTimeout(() => setSlow(true), SLOW_LOAD_MS);
    return () => clearTimeout(timer);
  }, []);
  return slow;
}

export function LoadingPanel() {
  const copy = loadingCopy(useCopyLanguage());
  const slow = useSlowLoad();
  return (
    <section className="loading-panel" role="status" aria-live="polite">
      <span className="loading-mark">
        <EmberMark />
      </span>
      <p className="loading-title">{copy.title}</p>
      <span className="spinner" aria-hidden="true" />
      {slow && <p className="loading-waking">{copy.waking}</p>}
    </section>
  );
}

export function LoadingScreen() {
  return (
    <main className="shell-main shell-main-loading">
      <LoadingPanel />
    </main>
  );
}

export function InlineLoading({ text }: { text: string }) {
  return (
    <p role="status" className="loading-inline">
      <span className="spinner" aria-hidden="true" />
      {text}
    </p>
  );
}
