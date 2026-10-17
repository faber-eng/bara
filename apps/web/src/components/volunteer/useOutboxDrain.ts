import { useQuery, useQueryClient } from "@tanstack/react-query";
import { useEffect } from "react";
import { drainOutbox } from "../../lib/volunteer/drain";
import { inboxKey } from "./inboxQuery";
import { outboxKey, outboxQuery } from "./outboxQuery";

const RETRY_INTERVAL_MS = 30_000;

export type OutboxView = { waiting: number; sendNow: () => void };

export function useOutboxDrain(volunteerId: string): OutboxView {
  const queryClient = useQueryClient();
  const count = useQuery(outboxQuery(volunteerId));

  async function drain() {
    if (navigator.onLine === false) return;
    const result = await drainOutbox(volunteerId).catch(() => null);
    void queryClient.invalidateQueries({ queryKey: outboxKey(volunteerId) });
    if (result !== null && result.sent > 0) {
      void queryClient.invalidateQueries({ queryKey: inboxKey(volunteerId) });
    }
  }

  // biome-ignore lint/correctness/useExhaustiveDependencies: drain only closes over volunteerId and the stable client
  useEffect(() => {
    void drain();
    window.addEventListener("online", drain);
    const timer = setInterval(drain, RETRY_INTERVAL_MS);
    return () => {
      window.removeEventListener("online", drain);
      clearInterval(timer);
    };
  }, [volunteerId]);

  return { waiting: count.data ?? 0, sendNow: () => void drain() };
}
