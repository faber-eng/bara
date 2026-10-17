import type { TileLayer, TileLayerKind } from "../contracts";
import { sourceFor } from "../sources";
import { apiRequest } from "./client";
import { ResponseShapeError, readOneOf, readRecord, readString } from "./parse";

export const TILE_LAYER_KINDS: readonly TileLayerKind[] = [
  "drying",
  "peat",
  "burn_scars",
  "reignition",
];
const TEMPLATE_TOKENS = ["{x}", "{y}", "{z}"];

export function parseTileLayer(body: unknown): TileLayer {
  const record = readRecord(body, "tile layer");
  const template = readString(record, "url_template", "tile layer");
  if (!TEMPLATE_TOKENS.every((token) => template.includes(token))) {
    throw new ResponseShapeError("tile layer.url_template lacks {x}, {y} or {z}");
  }
  return {
    layer: readOneOf(record, "layer", "tile layer", TILE_LAYER_KINDS),
    region: readString(record, "region", "tile layer"),
    week: readString(record, "week", "tile layer"),
    url_template: template,
  };
}

export function tilePath(layer: TileLayerKind, region: string, week: string | undefined): string {
  const base = `/api/tiles/${layer}?region=${encodeURIComponent(region)}`;
  return week === undefined ? base : `${base}&week=${encodeURIComponent(week)}`;
}

export async function fetchTileLayer(
  layer: TileLayerKind,
  region: string,
  week: string | undefined,
  signal?: AbortSignal,
): Promise<TileLayer> {
  if (sourceFor("tiles") === "fixture") {
    return { ...parseTileLayer((await import("@fixtures/tiles_drying.json")).default), layer };
  }
  return parseTileLayer(await apiRequest(tilePath(layer, region, week), { signal }));
}
