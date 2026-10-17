import { queryOptions } from "@tanstack/react-query";
import { countOutboxItems } from "../../lib/volunteer/outbox";

export function outboxKey(volunteerId: string) {
  return ["outbox", volunteerId] as const;
}

export function outboxQuery(volunteerId: string) {
  return queryOptions({
    queryKey: outboxKey(volunteerId),
    queryFn: () => countOutboxItems(volunteerId),
    staleTime: 0,
    retry: false,
  });
}
