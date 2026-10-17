import { buildHeaders } from "./client";

export type StreamEvent = { name: string; data: string };

const EVENT_SEPARATOR = "\n\n";

function streamBase(): string {
  const base: unknown = import.meta.env.VITE_STREAM_BASE;
  return typeof base === "string" ? base : "";
}

export function streamUrl(caseId: string): string {
  return `${streamBase()}/api/cases/${encodeURIComponent(caseId)}/stream`;
}

function parseBlock(block: string): StreamEvent | null {
  let name = "message";
  const data: string[] = [];
  for (const line of block.split("\n")) {
    if (line.startsWith("event:")) name = line.slice("event:".length).trim();
    if (line.startsWith("data:")) data.push(line.slice("data:".length).trim());
  }
  if (data.length === 0) return null;
  return { name, data: data.join("\n") };
}

export function splitEvents(buffer: string): { events: StreamEvent[]; rest: string } {
  const blocks = buffer.replaceAll("\r\n", "\n").split(EVENT_SEPARATOR);
  const rest = blocks.pop() ?? "";
  const events: StreamEvent[] = [];
  for (const block of blocks) {
    const event = parseBlock(block);
    if (event !== null) events.push(event);
  }
  return { events, rest };
}

async function readEvents(
  body: ReadableStream<Uint8Array>,
  onEvent: (event: StreamEvent) => void,
): Promise<void> {
  const reader = body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";
  for (;;) {
    const { done, value } = await reader.read();
    if (done) return;
    buffer += decoder.decode(value, { stream: true });
    const parsed = splitEvents(buffer);
    buffer = parsed.rest;
    for (const event of parsed.events) onEvent(event);
  }
}

export async function streamCase(
  caseId: string,
  onEvent: (event: StreamEvent) => void,
  signal: AbortSignal,
): Promise<void> {
  const path = `/api/cases/${encodeURIComponent(caseId)}/stream`;
  const response = await fetch(streamUrl(caseId), {
    headers: await buildHeaders(path, false),
    signal,
  });
  if (!response.ok || response.body === null) {
    throw new Error(`GET ${path} returned ${response.status}`);
  }
  await readEvents(response.body, onEvent);
}
