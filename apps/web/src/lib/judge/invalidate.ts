import type { QueryClient } from "@tanstack/react-query";

export function invalidateWorld(queryClient: QueryClient): Promise<void> {
  return queryClient.invalidateQueries({ predicate: (query) => query.queryKey[0] !== "health" });
}
