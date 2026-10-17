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
