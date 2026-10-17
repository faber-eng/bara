import { useQueryClient } from "@tanstack/react-query";
import { useEffect } from "react";
import { streamCase } from "../api/caseStream";
import { caseDetailQuery } from "../api/queries";
import { sourceFor } from "../sources";
import { followCase } from "./followCase";

function sleepMs(ms: number): Promise<void> {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

export function useCaseFollow(caseId: string): void {
  const queryClient = useQueryClient();
  useEffect(() => {
    if (sourceFor("caseDetail") !== "live") return;
    const controller = new AbortController();
    void followCase({
      stream: (onEvent) => streamCase(caseId, onEvent, controller.signal),
      refresh: () => queryClient.fetchQuery({ ...caseDetailQuery(caseId), staleTime: 0 }),
      signal: controller.signal,
      sleep: sleepMs,
    });
    return () => controller.abort();
  }, [caseId, queryClient]);
}
