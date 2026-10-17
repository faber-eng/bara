import type { Scalar } from "../contracts";

export type ExplanationSegment = { start: number; text: string; fields: string[] };

const NUMBER_PATTERN = /-?\d+(?:\.\d+)?/g;

const PERCENT = 100;

function decimalsIn(token: string): number {
  return token.split(".")[1]?.length ?? 0;
}

function roundTo(value: number, decimals: number): number {
  const factor = 10 ** decimals;
  return Math.round(value * factor) / factor;
}

function showsValue(token: string, field: string, entry: Scalar): boolean {
  const value = Number(entry);
  if (Number.isNaN(value)) return false;
  const shown = Number(token);
  const decimals = decimalsIn(token);
  if (roundTo(value, decimals) === shown) return true;
  const isFraction = field.endsWith("_pct") && Math.abs(value) <= 1;
  return isFraction && roundTo(value * PERCENT, decimals) === shown;
}

export function fieldsForNumber(token: string, cited: { [field: string]: Scalar }): string[] {
  return Object.entries(cited)
    .filter(([field, entry]) => showsValue(token, field, entry))
    .map(([field]) => field);
}

export function segmentExplanation(
  text: string,
  cited: { [field: string]: Scalar },
): ExplanationSegment[] {
  const segments: ExplanationSegment[] = [];
  let cursor = 0;
  for (const match of text.matchAll(NUMBER_PATTERN)) {
    const fields = fieldsForNumber(match[0], cited);
    if (fields.length === 0) continue;
    if (match.index > cursor)
      segments.push({ start: cursor, text: text.slice(cursor, match.index), fields: [] });
    segments.push({ start: match.index, text: match[0], fields });
    cursor = match.index + match[0].length;
  }
  if (cursor < text.length) segments.push({ start: cursor, text: text.slice(cursor), fields: [] });
  return segments;
}
