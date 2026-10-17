import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, within } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { resetClock } from "../../lib/api/clock";
import { CasesTab } from "./CasesTab";

vi.mock("../../lib/auth", () => ({ getIdToken: vi.fn().mockResolvedValue("token-1") }));

function renderTab(selected: string | undefined = undefined, onSelect = vi.fn()) {
  const queryClient = new QueryClient();
  render(
    <QueryClientProvider client={queryClient}>
      <CasesTab selectedCaseId={selected} onSelect={onSelect} />
    </QueryClientProvider>,
  );
  return onSelect;
}

function rowFor(cell: string): HTMLElement {
  return screen.getByRole("button", { name: new RegExp(cell) });
}

describe("CasesTab", () => {
  beforeEach(async () => {
    await resetClock();
  });

  it("lists the nine fixture cases", async () => {
    renderTab();

    await screen.findByRole("button", { name: /riau-0412/ });
    expect(screen.getAllByRole("button")).toHaveLength(9);
  });

  it.each([
    ["riau-0412", "chip-assigned", "Assigned"],
    ["riau-0610", "chip-open", "Open"],
    ["riau-0388", "chip-reviewing", "Reviewing"],
    ["riau-0455", "chip-overdue", "Overdue"],
    ["riau-0301", "chip-resolved", "Resolved, pending human"],
    ["riau-0277", "chip-human-review", "Human review"],
    ["riau-0533", "chip-escalated", "Escalated"],
    ["riau-0540", "chip-monitoring", "Monitoring"],
    ["riau-0199", "chip-closed", "Closed"],
  ])("shows %s with the %s chip", async (cell, className, label) => {
    renderTab();

    const row = await screen.findByRole("button", { name: new RegExp(cell) });
    const chip = within(row).getByText(label);
    expect(chip).toHaveClass("chip", className);
  });

  it("shows countdowns on the sim clock", async () => {
    renderTab();

    expect(await screen.findByText("Due in 3 d 9 h (sim clock)")).toBeInTheDocument();
    expect(screen.getByText("Due in less than 1 h (sim clock)")).toBeInTheDocument();
    const late = screen.getByText("Overdue by 2 h (sim clock)");
    expect(late).toHaveClass("countdown-late");
  });

  it("shows no countdown for a case without an open task", async () => {
    renderTab();

    const row = await screen.findByRole("button", { name: /riau-0610/ });
    expect(within(row).queryByText(/sim clock/)).not.toBeInTheDocument();
    expect(within(row).getByText("No open task")).toBeInTheDocument();
  });

  it("reports the selected case and marks it", async () => {
    const onSelect = renderTab("case-0003");

    const row = await screen.findByRole("button", { name: /riau-0388/ });
    expect(row).toHaveAttribute("aria-pressed", "true");
    expect(rowFor("riau-0412")).toHaveAttribute("aria-pressed", "false");

    fireEvent.click(rowFor("riau-0412"));

    expect(onSelect).toHaveBeenCalledWith("case-0001");
  });

  it("shows the empty state", async () => {
    vi.stubEnv("VITE_SOURCE_CASES", "live");
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(Response.json([])));
    renderTab();

    expect(await screen.findByText("No cases yet.")).toBeInTheDocument();
    vi.unstubAllEnvs();
    vi.unstubAllGlobals();
  });

  it("shows an error with retry", async () => {
    vi.stubEnv("VITE_SOURCE_CASES", "live");
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(new Response("x", { status: 500 })));
    renderTab();

    expect(await screen.findByRole("alert")).toHaveTextContent("Could not load cases");
    expect(screen.getByRole("button", { name: "Try again" })).toBeInTheDocument();
    vi.unstubAllEnvs();
    vi.unstubAllGlobals();
  });

  it("shows the ops role message on a 403", async () => {
    vi.stubEnv("VITE_SOURCE_CASES", "live");
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(new Response("x", { status: 403 })));
    renderTab();

    expect(await screen.findByRole("alert")).toHaveTextContent(
      "This account does not have the ops role",
    );
    vi.unstubAllEnvs();
    vi.unstubAllGlobals();
  });
});
