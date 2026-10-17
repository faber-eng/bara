import "@testing-library/jest-dom/vitest";
import { cleanup, configure } from "@testing-library/react";
import { afterEach, beforeEach, vi } from "vitest";

configure({ asyncUtilTimeout: 4000 });

beforeEach(() => {
  vi.stubEnv("VITE_SOURCE_CLOCK", "fixture");
});

afterEach(() => {
  cleanup();
});
