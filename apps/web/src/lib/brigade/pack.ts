import type { GeoPoint } from "../contracts";

export function mapPoint(mapUrl: string): GeoPoint | null {
  const query = new URL(mapUrl, "https://maps.invalid").searchParams.get("query");
  if (query === null) return null;
  const [lat, lon] = query.split(",").map(Number);
  if (lat === undefined || lon === undefined) return null;
  if (!Number.isFinite(lat) || !Number.isFinite(lon)) return null;
  return { lat, lon };
}

export function isSafeMapUrl(mapUrl: string): boolean {
  return mapUrl.startsWith("https://");
}
