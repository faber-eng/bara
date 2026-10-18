import type { GeoPoint } from "../contracts";

const MAX_LAT = 90;
const MAX_LON = 180;
const NUMBER = /^[+-]?\d+(\.\d+)?$/;
const SEPARATORS = /[\s,;]+/;

function readNumbers(text: string): number[] | null {
  const tokens = text
    .replace(/[()]/g, " ")
    .split(SEPARATORS)
    .filter((token) => token !== "");
  if (tokens.length !== 2) return null;
  if (!tokens.every((token) => NUMBER.test(token))) return null;
  return tokens.map(Number);
}

export function parseCoordinates(text: string): GeoPoint | null {
  const numbers = readNumbers(text);
  if (numbers === null) return null;
  const [lat, lon] = numbers;
  if (lat === undefined || lon === undefined) return null;
  if (Math.abs(lat) > MAX_LAT || Math.abs(lon) > MAX_LON) return null;
  return { lat, lon };
}
