import fixture from "@fixtures/rankings_riau_200.json";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, within } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { RankedAreasTab } from "./RankedAreasTab";

vi.mock("../../lib/auth", () => ({ getIdToken: vi.fn().mockResolvedValue("token-1") }));

function renderTab(selectedCellId?: string, onCellSelect = vi.fn(), onCellHighlight = vi.fn()) {
  const queryClient = new QueryClient();
  return render(
    <QueryClientProvider client={queryClient}>
      <RankedAreasTab
        region="riau"
        week={undefined}
        selectedCellId={selectedCellId}
        onCellSelect={onCellSelect}
        onCellHighlight={onCellHighlight}
      />
    </QueryClientProvider>,
  );
}

function rankedList() {
  return screen.findByRole("list", { name: /Ranked areas/ });
}

function rowButtons(list: HTMLElement) {
  return within(list).getAllByRole("button");
}

describe("RankedAreasTab", () => {
  afterEach(() => {
    vi.unstubAllEnvs();
    vi.unstubAllGlobals();
  });

  it("renders 200 compact rows in rank order", async () => {
    renderTab();

    const rows = rowButtons(await rankedList());
    expect(rows).toHaveLength(200);
    const ids = rows.map((row) => row.querySelector(".mv-row-title")?.textContent);
    const ordered = [...fixture.cells].sort((a, b) => a.rank - b.rank).map((cell) => cell.cell_id);
    expect(ids).toEqual(ordered);
  });

  it("shows a bold id, one score and one status per row, nothing more", async () => {
    renderTab();
    const first = fixture.cells.find((cell) => cell.rank === 1);
    if (first === undefined) throw new Error("fixture has no rank 1");

    const row = rowButtons(await rankedList())[0] as HTMLElement;
    expect(within(row).getByText(first.cell_id).tagName).toBe("STRONG");
    expect(row).toHaveTextContent(first.drying_score.toFixed(1));
    expect(row).not.toHaveTextContent(/canal|radar|Gemini/);
  });

  it("says a cell is new when it has no rank change", async () => {
    renderTab();
    await rankedList();

    expect(screen.getAllByText(/(^|· )new$/).length).toBe(
      fixture.cells.filter((cell) => cell.rank_change === null).length,
    );
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

    expect(await rankedList()).toBeInTheDocument();
  });

  it.each([401, 403])("says the account lacks the ops role on a %i", async (status) => {
    vi.stubEnv("VITE_SOURCE_RANKINGS", "live");
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(new Response("no", { status })));
    renderTab();

    expect(await screen.findByRole("alert")).toHaveTextContent(
      "This account does not have the ops role",
    );
  });

  it("marks the selected row and reports a row click", async () => {
    const onCellSelect = vi.fn();
    const second = fixture.cells.find((cell) => cell.rank === 2);
    renderTab(second?.cell_id, onCellSelect);
    const list = await rankedList();

    const selected = within(list).getByRole("button", { pressed: true });
    expect(selected).toHaveTextContent(second?.cell_id as string);
    expect(selected).toHaveClass("ops-cell-button");
    const first = fixture.cells.find((cell) => cell.rank === 1);
    fireEvent.click(
      within(list).getByRole("button", { name: new RegExp(first?.cell_id as string) }),
    );

    expect(onCellSelect).toHaveBeenCalledWith(first?.cell_id);
  });

  it("marks no row when nothing is selected", async () => {
    renderTab();
    const list = await rankedList();

    expect(within(list).queryByRole("button", { pressed: true })).not.toBeInTheDocument();
  });

  it("asks for the week when one is chosen", async () => {
    vi.stubEnv("VITE_SOURCE_RANKINGS", "live");
    const fetchMock = vi.fn().mockResolvedValue(Response.json(fixture));
    vi.stubGlobal("fetch", fetchMock);
    render(
      <QueryClientProvider client={new QueryClient()}>
        <RankedAreasTab
          region="congo_cuvette"
          week="2026-W25"
          selectedCellId={undefined}
          onCellSelect={vi.fn()}
          onCellHighlight={vi.fn()}
        />
      </QueryClientProvider>,
    );

    await rankedList();
    expect(fetchMock.mock.calls[0]?.[0]).toBe("/api/rankings/congo_cuvette?week=2026-W25");
  });

  it("shows a clean empty state for a region with no ranking yet", async () => {
    vi.stubEnv("VITE_SOURCE_RANKINGS", "live");
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(Response.json({ detail: "no_rankings" }, { status: 404 })),
    );
    render(
      <QueryClientProvider client={new QueryClient()}>
        <RankedAreasTab
          region="congo_cuvette"
          week={undefined}
          selectedCellId={undefined}
          onCellSelect={vi.fn()}
          onCellHighlight={vi.fn()}
        />
      </QueryClientProvider>,
    );

    expect(await screen.findByText("No ranked areas for Congo yet.")).toBeInTheDocument();
    expect(screen.queryByRole("alert")).not.toBeInTheDocument();
  });

  it("heads the list with the week and counts, and filters by case", async () => {
    renderTab();
    await rankedList();

    expect(screen.getByText(`Week ${fixture.week} · 200 ranked areas`)).toBeInTheDocument();
    const caseOpen = await screen.findByRole("button", { name: /Case open 1/ });
    expect(screen.getByRole("button", { name: /Needs a person 199/ })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /All 200/ })).toHaveAttribute("aria-pressed", "true");

    fireEvent.click(caseOpen);

    const rows = rowButtons(await rankedList());
    expect(rows).toHaveLength(1);
    expect(rows[0]).toHaveTextContent("riau-0277");
    expect(rows[0]).toHaveTextContent("Needs review");
  });

  it("shows the case chip only for a cell with an open case", async () => {
    renderTab();
    const list = await rankedList();

    expect(await within(list).findAllByText("Needs review")).toHaveLength(1);
    expect(within(list).getByRole("button", { name: /riau-0199/ })).not.toHaveTextContent("Closed");
  });

  it("names a broken dam as the main reason", async () => {
    renderTab();
    const list = await rankedList();

    expect(within(list).getByRole("button", { name: /riau-0103/ })).toHaveTextContent(
      "Broken dam in this area",
    );
  });

  it("moves through rows with the arrow keys and highlights the focused cell", async () => {
    const onCellHighlight = vi.fn();
    renderTab(undefined, vi.fn(), onCellHighlight);
    const list = await rankedList();
    const rows = rowButtons(list);
    rows[0]?.focus();

    fireEvent.keyDown(list, { key: "ArrowDown" });
    expect(rows[1]).toHaveFocus();
    fireEvent.keyDown(list, { key: "ArrowUp" });
    expect(rows[0]).toHaveFocus();
    expect(onCellHighlight).toHaveBeenLastCalledWith(
      rows[0]?.querySelector(".mv-row-title")?.textContent,
    );

    fireEvent.mouseLeave(list);
    expect(onCellHighlight).toHaveBeenLastCalledWith(undefined);
  });
});
