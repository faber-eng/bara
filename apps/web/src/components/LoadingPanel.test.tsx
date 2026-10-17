import { act, render, screen } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { setCopyLanguage } from "../lib/copy/language";
import { LoadingPanel, SLOW_LOAD_MS } from "./LoadingPanel";

describe("LoadingPanel", () => {
  beforeEach(() => {
    vi.useFakeTimers();
    setCopyLanguage("id");
  });

  afterEach(() => {
    vi.useRealTimers();
    setCopyLanguage("id");
  });

  it("announces loading as a polite status in Indonesian first", () => {
    render(<LoadingPanel />);

    const status = screen.getByRole("status");
    expect(status).toHaveAttribute("aria-live", "polite");
    expect(status).toHaveTextContent("Memuat Bara…");
    expect(screen.queryByText(/Server sedang bangun/)).not.toBeInTheDocument();
  });

  it("follows the copy language", () => {
    setCopyLanguage("en");
    render(<LoadingPanel />);

    expect(screen.getByRole("status")).toHaveTextContent("Loading Bara…");
  });

  it("adds the waking-up line only after the slow delay", () => {
    render(<LoadingPanel />);

    act(() => {
      vi.advanceTimersByTime(SLOW_LOAD_MS - 1);
    });
    expect(screen.queryByText(/Server sedang bangun/)).not.toBeInTheDocument();

    act(() => {
      vi.advanceTimersByTime(1);
    });
    expect(screen.getByText(/Server sedang bangun/)).toBeInTheDocument();
  });

  it("shows the English waking-up line", () => {
    setCopyLanguage("en");
    render(<LoadingPanel />);

    act(() => {
      vi.advanceTimersByTime(SLOW_LOAD_MS);
    });
    expect(screen.getByText(/The server is waking up/)).toBeInTheDocument();
  });

  it("clears its timer on unmount", () => {
    const { unmount } = render(<LoadingPanel />);
    unmount();

    expect(vi.getTimerCount()).toBe(0);
  });
});
