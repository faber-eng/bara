import type { JsonValue } from "../contracts";

export class ResponseShapeError extends Error {
  override name = "ResponseShapeError";
}

export type JsonRecord = Record<string, unknown>;

export function readRecord(value: unknown, label: string): JsonRecord {
  if (typeof value !== "object" || value === null || Array.isArray(value)) {
    throw new ResponseShapeError(`${label} is not an object`);
  }
  return value as JsonRecord;
}

export function readArray(value: unknown, label: string): unknown[] {
  if (!Array.isArray(value)) throw new ResponseShapeError(`${label} is not an array`);
  return value;
}

export function readString(record: JsonRecord, key: string, label: string): string {
  const value = record[key];
  if (typeof value !== "string") throw new ResponseShapeError(`${label}.${key} is not a string`);
  return value;
}

export function readNumber(record: JsonRecord, key: string, label: string): number {
  const value = record[key];
  if (typeof value !== "number" || Number.isNaN(value)) {
    throw new ResponseShapeError(`${label}.${key} is not a number`);
  }
  return value;
}

export function readBoolean(record: JsonRecord, key: string, label: string): boolean {
  const value = record[key];
  if (typeof value !== "boolean") throw new ResponseShapeError(`${label}.${key} is not a boolean`);
  return value;
}

export function readNullable<T>(
  record: JsonRecord,
  key: string,
  label: string,
  read: (record: JsonRecord, key: string, label: string) => T,
): T | null {
  return record[key] === null ? null : read(record, key, label);
}

export function readOneOf<T extends string>(
  record: JsonRecord,
  key: string,
  label: string,
  allowed: readonly T[],
): T {
  const value = readString(record, key, label);
  const match = allowed.find((candidate) => candidate === value);
  if (match === undefined) throw new ResponseShapeError(`${label}.${key} is not a known value`);
  return match;
}

export function readJsonValue(value: unknown, label: string): JsonValue {
  if (value === null || typeof value === "string" || typeof value === "boolean") return value;
  if (typeof value === "number" && !Number.isNaN(value)) return value;
  if (Array.isArray(value)) return value.map((item) => readJsonValue(item, label));
  if (typeof value === "object") return readJsonObject(value as JsonRecord, label);
  throw new ResponseShapeError(`${label} is not JSON`);
}

function readJsonObject(record: JsonRecord, label: string): { [key: string]: JsonValue } {
  const result: { [key: string]: JsonValue } = {};
  for (const [key, item] of Object.entries(record)) result[key] = readJsonValue(item, label);
  return result;
}

export function readJsonObjectAt(
  record: JsonRecord,
  key: string,
  label: string,
): { [key: string]: JsonValue } {
  return readJsonObject(readRecord(record[key], `${label}.${key}`), `${label}.${key}`);
}

export function readStringArray(record: JsonRecord, key: string, label: string): string[] {
  return readArray(record[key], `${label}.${key}`).map((item) => {
    if (typeof item !== "string") throw new ResponseShapeError(`${label}.${key} has a non-string`);
    return item;
  });
}
