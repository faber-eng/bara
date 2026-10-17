import type { GeoPoint } from "../contracts";

export const CELL_SIZE_M = 1000;

const METERS_PER_DEGREE = 111_320;
const BUCKET_DEG = 0.02;

export type CellSquare = { south: number; north: number; west: number; east: number };
export type IndexableCell = { cell_id: string; centroid: GeoPoint };

type IndexedCell<T extends IndexableCell> = { cell: T; square: CellSquare };

export type CellIndex<T extends IndexableCell> = {
  buckets: Map<string, IndexedCell<T>[]>;
  maxHalfDeg: number;
};

export function cellSquare(centroid: GeoPoint): CellSquare {
  const halfLat = CELL_SIZE_M / 2 / METERS_PER_DEGREE;
  const halfLon = halfLat / Math.cos((centroid.lat * Math.PI) / 180);
  return {
    south: centroid.lat - halfLat,
    north: centroid.lat + halfLat,
    west: centroid.lon - halfLon,
    east: centroid.lon + halfLon,
  };
}

export function cellRing(centroid: GeoPoint): [number, number][] {
  const { south, north, west, east } = cellSquare(centroid);
  return [
    [west, south],
    [east, south],
    [east, north],
    [west, north],
    [west, south],
  ];
}

function bucketKey(row: number, column: number): string {
  return `${row}:${column}`;
}

function bucketOf(value: number): number {
  return Math.floor(value / BUCKET_DEG);
}

export function buildCellIndex<T extends IndexableCell>(cells: readonly T[]): CellIndex<T> {
  const buckets = new Map<string, IndexedCell<T>[]>();
  let maxHalfDeg = 0;
  for (const cell of cells) {
    const square = cellSquare(cell.centroid);
    maxHalfDeg = Math.max(
      maxHalfDeg,
      square.east - cell.centroid.lon,
      square.north - cell.centroid.lat,
    );
    const key = bucketKey(bucketOf(cell.centroid.lat), bucketOf(cell.centroid.lon));
    const bucket = buckets.get(key);
    if (bucket) bucket.push({ cell, square });
    else buckets.set(key, [{ cell, square }]);
  }
  return { buckets, maxHalfDeg };
}

function contains(square: CellSquare, point: GeoPoint, toleranceDeg: number): boolean {
  return (
    point.lat >= square.south - toleranceDeg &&
    point.lat <= square.north + toleranceDeg &&
    point.lon >= square.west - toleranceDeg &&
    point.lon <= square.east + toleranceDeg
  );
}

function distanceSquared(a: GeoPoint, b: GeoPoint): number {
  return (a.lat - b.lat) ** 2 + (a.lon - b.lon) ** 2;
}

export function findCellAt<T extends IndexableCell>(
  index: CellIndex<T>,
  point: GeoPoint,
  toleranceDeg: number,
): T | undefined {
  const reach = Math.ceil((index.maxHalfDeg + toleranceDeg) / BUCKET_DEG);
  const row = bucketOf(point.lat);
  const column = bucketOf(point.lon);
  let best: T | undefined;
  let bestDistance = Number.POSITIVE_INFINITY;
  for (let r = row - reach; r <= row + reach; r++) {
    for (let c = column - reach; c <= column + reach; c++) {
      for (const entry of index.buckets.get(bucketKey(r, c)) ?? []) {
        if (!contains(entry.square, point, toleranceDeg)) continue;
        const distance = distanceSquared(entry.cell.centroid, point);
        if (distance < bestDistance) {
          best = entry.cell;
          bestDistance = distance;
        }
      }
    }
  }
  return best;
}
