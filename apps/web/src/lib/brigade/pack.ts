import type { GeoPoint } from "../contracts";

const MAP_BASE = "https://maps.invalid";

function toCoordinate(text: string): number | null {
  if (text.trim() === "") return null;
  const value = Number(text);
  return Number.isFinite(value) ? value : null;
}

export function mapPoint(mapUrl: string): GeoPoint | null {
  if (!URL.canParse(mapUrl, MAP_BASE)) return null;
  const query = new URL(mapUrl, MAP_BASE).searchParams.get("query");
  if (query === null) return null;
  const parts = query.split(",");
  if (parts.length !== 2) return null;
  const [lat, lon] = parts.map(toCoordinate);
  if (lat === null || lon === null || lat === undefined || lon === undefined) return null;
  return { lat, lon };
}

export function isSafeMapUrl(mapUrl: string): boolean {
  return mapUrl.startsWith("https://");
}
