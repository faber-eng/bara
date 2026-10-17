import type { GeoPoint } from "../contracts";

export const MAX_AREA_KM2 = 2500;
export const MIN_CORNERS = 3;
const EARTH_RADIUS_M = 6_371_000;
const M2_PER_KM2 = 1_000_000;

export type GeoJsonPolygon = { type: "Polygon"; coordinates: number[][][] };

function toRadians(degrees: number): number {
  return (degrees * Math.PI) / 180;
}

export function closedRing(points: GeoPoint[]): GeoPoint[] {
  const first = points[0];
  if (first === undefined) return [];
  return [...points, first];
}

export function areaKm2(points: GeoPoint[]): number {
  if (points.length < MIN_CORNERS) return 0;
  const ring = closedRing(points);
  let total = 0;
  for (let index = 0; index < ring.length - 1; index += 1) {
    const from = ring[index];
    const to = ring[index + 1];
    if (from === undefined || to === undefined) continue;
    const delta = toRadians(to.lon - from.lon);
    total += delta * (2 + Math.sin(toRadians(from.lat)) + Math.sin(toRadians(to.lat)));
  }
  return (Math.abs(total) * EARTH_RADIUS_M ** 2) / 2 / M2_PER_KM2;
}

export function toGeoJsonPolygon(points: GeoPoint[]): GeoJsonPolygon {
  const ring = closedRing(points).map((point) => [point.lon, point.lat]);
  return { type: "Polygon", coordinates: [ring] };
}

export type DraftState = "empty" | "too_few" | "too_large" | "ready";

export function draftState(points: GeoPoint[]): DraftState {
  if (points.length === 0) return "empty";
  if (points.length < MIN_CORNERS) return "too_few";
  if (areaKm2(points) > MAX_AREA_KM2) return "too_large";
  return "ready";
}
