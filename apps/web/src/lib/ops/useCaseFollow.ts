import { useQueryClient } from "@tanstack/react-query";
import { useEffect, useState } from "react";
import { streamCase } from "../api/caseStream";
import { caseDetailQuery } from "../api/queries";
import { sourceFor } from "../sources";
import { followCase } from "./followCase";

function sleepMs(ms: number): Promise<void> {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

export function useCaseFollow(caseId: string): boolean {
  const queryClient = useQueryClient();
  const [streaming, setStreaming] = useState(false);
  useEffect(() => {
    if (sourceFor("caseDetail") !== "live") return;
    const controller = new AbortController();
    setStreaming(true);
    void followCase({
      stream: (onEvent) => streamCase(caseId, onEvent, controller.signal),
      refresh: () => queryClient.fetchQuery({ ...caseDetailQuery(caseId), staleTime: 0 }),
      signal: controller.signal,
      sleep: sleepMs,
    }).finally(() => {
      if (!controller.signal.aborted) setStreaming(false);
    });
    return () => controller.abort();
  }, [caseId, queryClient]);
  return streaming;
}
