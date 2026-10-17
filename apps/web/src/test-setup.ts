import "@testing-library/jest-dom/vitest";
import { cleanup, configure } from "@testing-library/react";
import { afterEach, beforeEach, vi } from "vitest";

configure({ asyncUtilTimeout: 4000 });

beforeEach(() => {
  vi.stubEnv("VITE_SOURCE_CLOCK", "fixture");
  vi.stubEnv("VITE_SOURCE_TILES", "fixture");
  vi.stubEnv("VITE_SOURCE_RANKINGS", "fixture");
  vi.stubEnv("VITE_SOURCE_CASES", "fixture");
  vi.stubEnv("VITE_SOURCE_CASEDETAIL", "fixture");
  vi.stubEnv("VITE_SOURCE_INBOX", "fixture");
});

afterEach(() => {
  cleanup();
});
