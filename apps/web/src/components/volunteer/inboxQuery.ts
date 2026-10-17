import { queryOptions } from "@tanstack/react-query";
import { fetchInbox } from "../../lib/api/volunteer";

const INBOX_STALE_MS = 15_000;
const INBOX_REFRESH_MS = 10_000;

export function inboxKey(volunteerId: string) {
  return ["inbox", volunteerId] as const;
}

export function inboxQuery(volunteerId: string) {
  return queryOptions({
    queryKey: inboxKey(volunteerId),
    queryFn: ({ signal }) => fetchInbox(volunteerId, signal),
    staleTime: INBOX_STALE_MS,
    refetchInterval: INBOX_REFRESH_MS,
    retry: false,
  });
}
