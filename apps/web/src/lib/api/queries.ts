import { queryOptions } from "@tanstack/react-query";
import { brigadeContactId } from "../brigade/contact";
import type { TileLayerKind } from "../contracts";
import { fetchAllCells } from "./allCells";
import { fetchCaseDetail } from "./caseDetail";
import { fetchCases } from "./cases";
import { fetchCellFacts } from "./cellFacts";
import { fetchClock } from "./clock";
import { fetchBrigadeInbox } from "./escalations";
import { fetchRankings } from "./rankings";
import { fetchTileLayer } from "./tiles";

const CLOCK_REFRESH_MS = 60_000;
const CLOCK_RETRIES = 2;
const CLOCK_RETRY_DELAY_MS = 1_000;
const OPS_STALE_MS = 30_000;
export const OPS_REFRESH_MS = 10_000;
const WEEK_STALE_MS = 10 * 60_000;
const TILES_STALE_MS = 30 * 60_000;
const ALL_CELLS_STALE_MS = 30 * 60_000;

export const clockQuery = queryOptions({
  queryKey: ["clock"],
  queryFn: ({ signal }) => fetchClock(signal),
  staleTime: CLOCK_REFRESH_MS,
  refetchInterval: CLOCK_REFRESH_MS,
  retry: CLOCK_RETRIES,
  retryDelay: CLOCK_RETRY_DELAY_MS,
});

export function rankingsQuery(region: string, week?: string) {
  return queryOptions({
    queryKey: ["rankings", region, week ?? "latest"],
    queryFn: ({ signal }) => fetchRankings(region, week, signal),
    staleTime: week === undefined ? OPS_STALE_MS : WEEK_STALE_MS,
    refetchOnWindowFocus: false,
    retry: false,
  });
}

export function allCellsQuery(region: string) {
  return queryOptions({
    queryKey: ["cells", "all", region],
    queryFn: ({ signal }) => fetchAllCells(region, signal),
    staleTime: ALL_CELLS_STALE_MS,
    refetchOnWindowFocus: false,
    retry: false,
  });
}

export function casesQuery(region: string) {
  return queryOptions({
    queryKey: ["cases", region],
    queryFn: ({ signal }) => fetchCases(region, signal),
    staleTime: OPS_STALE_MS,
    refetchInterval: OPS_REFRESH_MS,
    refetchIntervalInBackground: false,
    retry: false,
  });
}

const WEEKLY_LAYERS: readonly TileLayerKind[] = ["drying", "burn_scars", "reignition"];

export function tileLayerQuery(layer: TileLayerKind, region: string, week?: string) {
  const weekKey = WEEKLY_LAYERS.includes(layer) ? (week ?? "latest") : "static";
  const requestedWeek = weekKey === "static" ? undefined : week;
  return queryOptions({
    queryKey: ["tiles", layer, region, weekKey],
    queryFn: ({ signal }) => fetchTileLayer(layer, region, requestedWeek, signal),
    staleTime: TILES_STALE_MS,
    refetchOnWindowFocus: false,
    retry: false,
  });
}

export function cellFactsQuery(cellId: string) {
  return queryOptions({
    queryKey: ["cells", "detail", cellId],
    queryFn: ({ signal }) => fetchCellFacts(cellId, signal),
    staleTime: OPS_STALE_MS,
    retry: false,
  });
}

export function caseDetailQuery(caseId: string) {
  return queryOptions({
    queryKey: ["cases", "detail", caseId],
    queryFn: ({ signal }) => fetchCaseDetail(caseId, signal),
    staleTime: OPS_STALE_MS,
    retry: false,
  });
}

export function brigadeContactQuery(judgeMode: boolean) {
  return queryOptions({
    queryKey: ["brigade", "contact", judgeMode],
    queryFn: brigadeContactId,
    staleTime: Number.POSITIVE_INFINITY,
    retry: false,
  });
}

export function brigadeInboxQuery(contactId: string | undefined) {
  return queryOptions({
    queryKey: ["brigade", "inbox", contactId],
    queryFn: ({ signal }) => fetchBrigadeInbox(contactId ?? "", signal),
    enabled: contactId !== undefined,
    staleTime: OPS_STALE_MS,
    refetchInterval: OPS_REFRESH_MS,
    refetchIntervalInBackground: false,
    retry: false,
  });
}
