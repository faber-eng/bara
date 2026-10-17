import type { ClockState } from "../contracts";
import { setJudgeMode } from "../judge/store";
import { sourceFor } from "../sources";
import { apiRequest } from "./client";
import { clearFixtureOverrides } from "./fixtureOverrides";
import { readBoolean, readNumber, readRecord, readString } from "./parse";

const CLOCK_PATH = "/api/clock";
const ADVANCE_PATH = "/api/judge/advance";
const RESET_PATH = "/api/judge/reset";
const CLOCK_TIMEOUT_MS = 15_000;
const SECONDS_PER_HOUR = 3_600;
const MS_PER_SECOND = 1_000;

export function parseClockState(body: unknown): ClockState {
  const record = readRecord(body, "clock");
  return {
    now: readString(record, "now", "clock"),
    offset_seconds: readNumber(record, "offset_seconds", "clock"),
    judge_mode: readBoolean(record, "judge_mode", "clock"),
  };
}

let fixtureOffsetSeconds = 0;

async function readFixtureState(): Promise<ClockState> {
  const base = parseClockState((await import("@fixtures/clock.json")).default);
  const nowMs = Date.parse(base.now) + fixtureOffsetSeconds * MS_PER_SECOND;
  return {
    now: fixtureOffsetSeconds === 0 ? base.now : new Date(nowMs).toISOString(),
    offset_seconds: fixtureOffsetSeconds,
    judge_mode: base.judge_mode,
  };
}

export async function fixtureClockNowMs(): Promise<number> {
  return Date.parse((await readFixtureState()).now);
}

async function applyJudgeMode(read: () => Promise<ClockState>): Promise<ClockState> {
  try {
    const state = await read();
    setJudgeMode(state.judge_mode);
    return state;
  } catch (error) {
    setJudgeMode(false);
    throw error;
  }
}

export function fetchClock(signal?: AbortSignal): Promise<ClockState> {
  if (sourceFor("clock") === "fixture") return applyJudgeMode(readFixtureState);
  return applyJudgeMode(async () =>
    parseClockState(await apiRequest(CLOCK_PATH, { signal, timeoutMs: CLOCK_TIMEOUT_MS })),
  );
}

export async function advanceClock(hours: number): Promise<ClockState> {
  if (sourceFor("clock") === "fixture") {
    fixtureOffsetSeconds += hours * SECONDS_PER_HOUR;
    return readFixtureState();
  }
  return parseClockState(await apiRequest(ADVANCE_PATH, { method: "POST", body: { hours } }));
}

export async function resetClock(): Promise<ClockState> {
  clearFixtureOverrides();
  if (sourceFor("clock") === "fixture") {
    fixtureOffsetSeconds = 0;
    return readFixtureState();
  }
  return parseClockState(await apiRequest(RESET_PATH, { method: "POST" }));
}
