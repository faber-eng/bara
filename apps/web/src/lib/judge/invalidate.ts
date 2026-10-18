import type { QueryClient } from "@tanstack/react-query";

export function invalidateWorld(queryClient: QueryClient): Promise<void> {
  return queryClient.invalidateQueries({ predicate: (query) => query.queryKey[0] !== "health" });
}

export const AGENT_SETTLE_MS = 15_000;

export async function invalidateWorldSettled(queryClient: QueryClient): Promise<void> {
  await invalidateWorld(queryClient);
  setTimeout(() => void invalidateWorld(queryClient), AGENT_SETTLE_MS);
}
