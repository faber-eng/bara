import "@testing-library/jest-dom/vitest";
import "fake-indexeddb/auto";
import { cleanup, configure } from "@testing-library/react";
import { afterEach, beforeEach, vi } from "vitest";

configure({ asyncUtilTimeout: 4000 });

const OFFLINE_HEALTH = {
  status: "ok",
  models: { reasoning: "gemini-3.1-pro-preview", fast: "gemini-3.5-flash" },
  fallback_used: false,
  git_sha: "0123456789abcdef",
};

function offlineFetch(path: string): Promise<Response> {
  if (path === "/api/health") return Promise.resolve(Response.json(OFFLINE_HEALTH));
  return Promise.resolve(new Response("not found", { status: 404 }));
}

function stubOfflineFetch() {
  vi.stubGlobal("fetch", offlineFetch);
}

beforeEach(() => {
  stubOfflineFetch();
  vi.stubEnv("VITE_SOURCE_CLOCK", "fixture");
  vi.stubEnv("VITE_SOURCE_TILES", "fixture");
  vi.stubEnv("VITE_SOURCE_RANKINGS", "fixture");
  vi.stubEnv("VITE_SOURCE_CASES", "fixture");
  vi.stubEnv("VITE_SOURCE_CASEDETAIL", "fixture");
  vi.stubEnv("VITE_SOURCE_ESCALATIONS", "fixture");
  vi.stubEnv("VITE_SOURCE_INBOX", "fixture");
});

afterEach(() => {
  cleanup();
  if (typeof localStorage !== "undefined") localStorage.clear();
  stubOfflineFetch();
});
