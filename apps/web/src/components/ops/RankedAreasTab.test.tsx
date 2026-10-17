import fixture from "@fixtures/rankings_riau_200.json";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, within } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { RankedAreasTab } from "./RankedAreasTab";

vi.mock("../../lib/auth", () => ({ getIdToken: vi.fn().mockResolvedValue("token-1") }));

function renderTab() {
  const queryClient = new QueryClient();
  return render(
    <QueryClientProvider client={queryClient}>
      <RankedAreasTab />
    </QueryClientProvider>,
  );
}

function bodyRows() {
  return screen.getAllByRole("row").slice(1);
}

describe("RankedAreasTab", () => {
  afterEach(() => {
    vi.unstubAllEnvs();
    vi.unstubAllGlobals();
  });

  it("renders 200 rows plus the header, in rank order", async () => {
    renderTab();

    await screen.findByRole("table", { name: /Ranked areas/ });
    const rows = screen.getAllByRole("row");
    expect(rows).toHaveLength(201);
    const ranks = bodyRows().map((row) => within(row).getAllByRole("cell")[0]?.textContent);
    expect(ranks).toEqual(Array.from({ length: 200 }, (_, index) => String(index + 1)));
  });

  it("shows units on the numbers", async () => {
    renderTab();
    await screen.findByRole("table");

    const first = fixture.cells[0];
    const row = bodyRows()[0] as HTMLElement;
    expect(within(row).getByText(first?.cell_id as string)).toBeInTheDocument();
    expect(row).toHaveTextContent(/canal \d+ m/);
    expect(row).toHaveTextContent(/rain deficit \d+%/);
    expect(row).toHaveTextContent(/radar (-?\d+\.\d dB|n\/a)/);
    expect(screen.getByRole("columnheader", { name: /Score \(0 to 100\)/ })).toBeInTheDocument();
  });

  it("renders a null rank change, a null s1 value and a missing explanation without breaking", async () => {
    renderTab();
    await screen.findByRole("table");

    expect(screen.getAllByText("new").length).toBe(
      fixture.cells.filter((cell) => cell.rank_change === null).length,
    );
    expect(screen.getAllByText(/radar n\/a/).length).toBe(
      fixture.cells.filter((cell) => cell.components.s1_anom_db === null).length,
    );
  });

  it("shows the Gemini chip only for cells with an explanation", async () => {
    renderTab();
    await screen.findByRole("table");

    const explained = fixture.cells.filter((cell) => cell.explanation !== null).length;
    expect(screen.getAllByText("Gemini")).toHaveLength(explained);
    expect(explained).toBeGreaterThan(0);
  });

  it("shows a loading state first", () => {
    vi.stubEnv("VITE_SOURCE_RANKINGS", "live");
    vi.stubGlobal("fetch", vi.fn().mockReturnValue(new Promise(() => {})));
    renderTab();

    expect(screen.getByRole("status")).toHaveTextContent("Loading ranked areas");
  });

  it("shows an empty state", async () => {
    vi.stubEnv("VITE_SOURCE_RANKINGS", "live");
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(Response.json({ ...fixture, cells: [], dams: [] })),
    );
    renderTab();

    expect(await screen.findByText("No ranked areas for this week.")).toBeInTheDocument();
  });

  it("shows an error with a retry that recovers", async () => {
    vi.stubEnv("VITE_SOURCE_RANKINGS", "live");
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce(new Response("boom", { status: 500 }))
      .mockResolvedValue(Response.json(fixture));
    vi.stubGlobal("fetch", fetchMock);
    renderTab();

    expect(await screen.findByRole("alert")).toHaveTextContent("Could not load ranked areas");
    fireEvent.click(screen.getByRole("button", { name: "Try again" }));

    expect(await screen.findByRole("table")).toBeInTheDocument();
  });

  it.each([401, 403])("says the account lacks the ops role on a %i", async (status) => {
    vi.stubEnv("VITE_SOURCE_RANKINGS", "live");
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(new Response("no", { status })));
    renderTab();

    expect(await screen.findByRole("alert")).toHaveTextContent(
      "This account does not have the ops role",
    );
  });
});
