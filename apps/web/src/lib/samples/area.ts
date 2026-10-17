import { ResponseShapeError, readArray, readRecord, readString } from "../api/parse";

export type AreaSummary = { name: string; vertices: number };

function ringVertices(ring: unknown): number {
  const points = readArray(ring, "ring");
  return Math.max(points.length - 1, 0);
}

function polygonVertices(geometry: Record<string, unknown>): number {
  const rings = readArray(geometry.coordinates, "coordinates");
  return rings.reduce<number>((total, ring) => total + ringVertices(ring), 0);
}

function featureName(feature: Record<string, unknown>): string {
  const properties = readRecord(feature.properties, "properties");
  return readString(properties, "name", "properties");
}

export function summarizeArea(geojson: unknown): AreaSummary {
  const collection = readRecord(geojson, "area");
  const features = readArray(collection.features, "features");
  const first = features[0];
  if (first === undefined) throw new ResponseShapeError("the area has no feature");
  const feature = readRecord(first, "feature");
  const geometry = readRecord(feature.geometry, "geometry");
  if (geometry.type !== "Polygon") throw new ResponseShapeError("the area is not a polygon");
  return { name: featureName(feature), vertices: polygonVertices(geometry) };
}
