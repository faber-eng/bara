import type { SampleItem, SampleKind } from "../contracts";
import { apiRequest } from "./client";
import { readArray, readOneOf, readRecord, readString } from "./parse";

const SAMPLE_FILE_TIMEOUT_MS = 20_000;

const SAMPLE_KINDS: readonly SampleKind[] = ["photo", "voice", "area"];

function parseSample(value: unknown): SampleItem {
  const record = readRecord(value, "sample");
  return {
    id: readString(record, "id", "sample"),
    kind: readOneOf(record, "kind", "sample", SAMPLE_KINDS),
    label: readString(record, "label", "sample"),
    credit: readString(record, "credit", "sample"),
    url: readString(record, "url", "sample"),
  };
}

export function parseSamples(body: unknown): SampleItem[] {
  return readArray(body, "samples").map(parseSample);
}

export async function fetchSamples(kind: SampleKind, signal?: AbortSignal): Promise<SampleItem[]> {
  return parseSamples(await apiRequest(`/api/samples?kind=${kind}`, { signal }));
}

export class SampleFileError extends Error {
  override name = "SampleFileError";
}

export async function fetchSampleFile(item: SampleItem, signal?: AbortSignal): Promise<Blob> {
  const timeout = AbortSignal.timeout(SAMPLE_FILE_TIMEOUT_MS);
  const response = await fetch(item.url, {
    signal: signal === undefined ? timeout : AbortSignal.any([signal, timeout]),
  });
  if (!response.ok) throw new SampleFileError(`Sample ${item.id} returned ${response.status}`);
  return response.blob();
}
