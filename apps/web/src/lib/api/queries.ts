import { queryOptions } from "@tanstack/react-query";
import { fetchCases } from "./cases";
import { fetchClock } from "./clock";
import { fetchRankings } from "./rankings";
import { fetchDryingTiles } from "./tiles";

const CLOCK_REFRESH_MS = 60_000;
const OPS_STALE_MS = 30_000;
const TILES_STALE_MS = 5 * 60_000;

export const clockQuery = queryOptions({
  queryKey: ["clock"],
  queryFn: ({ signal }) => fetchClock(signal),
  staleTime: CLOCK_REFRESH_MS,
  refetchInterval: CLOCK_REFRESH_MS,
  retry: false,
});

export function rankingsQuery(region: string) {
  return queryOptions({
    queryKey: ["rankings", region],
    queryFn: ({ signal }) => fetchRankings(region, signal),
    staleTime: OPS_STALE_MS,
    retry: false,
  });
}

export function casesQuery(region: string) {
  return queryOptions({
    queryKey: ["cases", region],
    queryFn: ({ signal }) => fetchCases(region, signal),
    staleTime: OPS_STALE_MS,
    retry: false,
  });
}

export function dryingTilesQuery(region: string) {
  return queryOptions({
    queryKey: ["tiles", "drying", region],
    queryFn: ({ signal }) => fetchDryingTiles(region, signal),
    staleTime: TILES_STALE_MS,
    retry: false,
  });
}
