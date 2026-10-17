import { queryOptions } from "@tanstack/react-query";
import type { TileLayerKind } from "../contracts";
import {
  fetchBulletin,
  fetchCells,
  fetchDams,
  fetchRecord,
  fetchSummary,
  fetchTiles,
  type PublicQuery,
} from "./publicData";

const PUBLIC_STALE_MS = 5 * 60_000;
const TILES_STALE_MS = 30 * 60_000;

export function publicSummaryQuery(query: PublicQuery) {
  return queryOptions({
    queryKey: ["public", "summary", query.region, query.week ?? "latest"],
    queryFn: ({ signal }) => fetchSummary(query, signal),
    staleTime: PUBLIC_STALE_MS,
    retry: false,
  });
}

export function publicCellsQuery(query: PublicQuery) {
  return queryOptions({
    queryKey: ["public", "cells", query.region, query.week ?? "latest"],
    queryFn: ({ signal }) => fetchCells(query, signal),
    staleTime: PUBLIC_STALE_MS,
    retry: false,
  });
}

export function publicDamsQuery(region: string) {
  return queryOptions({
    queryKey: ["public", "dams", region],
    queryFn: ({ signal }) => fetchDams(region, signal),
    staleTime: PUBLIC_STALE_MS,
    retry: false,
  });
}

export function publicRecordQuery(region: string) {
  return queryOptions({
    queryKey: ["public", "record", region],
    queryFn: ({ signal }) => fetchRecord(region, signal),
    staleTime: PUBLIC_STALE_MS,
    retry: false,
  });
}

export function publicBulletinQuery(query: PublicQuery) {
  return queryOptions({
    queryKey: ["public", "bulletin", query.region, query.week ?? "latest"],
    queryFn: ({ signal }) => fetchBulletin(query, signal),
    staleTime: PUBLIC_STALE_MS,
    retry: false,
  });
}

export function publicTilesQuery(layer: TileLayerKind, query: PublicQuery) {
  return queryOptions({
    queryKey: ["public", "tiles", layer, query.region, query.week ?? "latest"],
    queryFn: ({ signal }) => fetchTiles(layer, query, signal),
    staleTime: TILES_STALE_MS,
    refetchOnWindowFocus: false,
    retry: false,
  });
}
