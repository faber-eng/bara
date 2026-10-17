import type { TileLayer } from "../contracts";
import { sourceFor } from "../sources";
import { apiRequest } from "./client";
import { ResponseShapeError, readOneOf, readRecord, readString } from "./parse";

const TEMPLATE_TOKENS = ["{x}", "{y}", "{z}"];

export function parseTileLayer(body: unknown): TileLayer {
  const record = readRecord(body, "tile layer");
  const template = readString(record, "url_template", "tile layer");
  if (!TEMPLATE_TOKENS.every((token) => template.includes(token))) {
    throw new ResponseShapeError("tile layer.url_template lacks {x}, {y} or {z}");
  }
  return {
    layer: readOneOf(record, "layer", "tile layer", ["drying"]),
    region: readString(record, "region", "tile layer"),
    week: readString(record, "week", "tile layer"),
    url_template: template,
  };
}

export async function fetchDryingTiles(region: string, signal?: AbortSignal): Promise<TileLayer> {
  if (sourceFor("tiles") === "fixture") {
    return parseTileLayer((await import("@fixtures/tiles_drying.json")).default);
  }
  const path = `/api/tiles/drying?region=${encodeURIComponent(region)}`;
  return parseTileLayer(await apiRequest(path, { signal }));
}
