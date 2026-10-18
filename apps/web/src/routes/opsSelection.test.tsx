import { fireEvent, screen, waitFor, within } from "@testing-library/react";
import type { ReactNode } from "react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { outlineMapsApi, renderApp, stubApi } from "../test-utils";

vi.mock("../lib/auth", () => ({ getIdToken: vi.fn().mockResolvedValue("token-1") }));

const spies = vi.hoisted(() => ({
  select: vi.fn(),
  focus: vi.fn(),
  onSelect: { current: (_cellId: string) => {} },
}));

vi.mock("../lib/ops/cellLayer", async (importOriginal) => ({
  ...(await importOriginal<typeof import("../lib/ops/cellLayer")>()),
  createCellLayer: (
    _map: unknown,
    _cells: unknown,
    handlers: { onSelect: (id: string) => void },
  ) => {
    spies.onSelect.current = handlers.onSelect;
    return { select: spies.select, focus: spies.focus, destroy: vi.fn() };
  },
  createDamLayer: () => ({ destroy: vi.fn() }),
}));

const fakeMap = {
  fitBounds: vi.fn(),
  setOptions: vi.fn(),
  addListener: () => ({ remove: vi.fn() }),
  overlayMapTypes: { push: vi.fn(), getArray: () => [], removeAt: vi.fn() },
};

vi.mock("@vis.gl/react-google-maps", () => ({
  APIProvider: ({ children }: { children: ReactNode }) => <div>{children}</div>,
  Map: ({ children }: { children: ReactNode }) => <div data-testid="map">{children}</div>,
  useMap: () => fakeMap,
}));

class FakeImageMapType {
  setOpacity() {}
}

const FACTS = {
  cell_id: "x",
  region: "riau",
  components: {
    s1_anom_db: null,
    rain_30d_mm: 1,
    rain_deficit_pct: 0.5,
    canal_dist_m: 10,
    peat_class: 1,
  },
  drying_score: 70,
  rank: 4,
  trend: [],
  nearby_dams: [],
  past_fires: [],
  past_checks: [],
  explanation: null,
};

describe("/ops selection", () => {
  beforeEach(() => {
    spies.select.mockReset();
    spies.focus.mockReset();
    vi.stubEnv("VITE_MAPS_KEY", "test-key");
    vi.stubGlobal("google", {
      maps: { ImageMapType: FakeImageMapType, Size: class {}, ...outlineMapsApi },
    });
    stubApi({
      "GET /api/cells/riau-0102": () => Response.json({ ...FACTS, cell_id: "riau-0102" }),
    });
  });

  function rankedList() {
    return screen.findByRole("list", { name: /Ranked areas/ });
  }

  function dialogText(): string {
    return screen.getByRole("dialog", { name: "Area riau-0102" }).textContent ?? "";
  }

  async function closeDialog() {
    const dialog = screen.getByRole("dialog", { name: "Area riau-0102" });
    fireEvent.click(within(dialog).getByRole("button", { name: "Close" }));
    await waitFor(() => expect(screen.queryByRole("dialog")).not.toBeInTheDocument());
  }

  it("a map click opens the cell dialog, marks the row and does not move the map", async () => {
    renderApp("/ops");
    await rankedList();
    await waitFor(() => expect(spies.onSelect.current).not.toBe(undefined));

    spies.onSelect.current("riau-0102");

    const dialog = await screen.findByRole("dialog", { name: "Area riau-0102" });
    expect(
      within(dialog).getByText("This square is a 1 km peat area.", { exact: false }),
    ).toBeInTheDocument();
    const pressed = within(await rankedList()).getByRole("button", { pressed: true });
    expect(pressed).toHaveTextContent("riau-0102");
    expect(spies.focus).not.toHaveBeenCalled();
  });

  it("a row click opens the same dialog and zooms the map to the cell", async () => {
    renderApp("/ops");
    await waitFor(() => expect(spies.select).toHaveBeenCalled());
    spies.onSelect.current("riau-0102");
    await within(await screen.findByRole("dialog")).findByText("Drying score");
    const fromMap = dialogText();
    await closeDialog();

    fireEvent.click(within(await rankedList()).getByRole("button", { name: /riau-0102/ }));

    await within(await screen.findByRole("dialog")).findByText("Drying score");
    expect(dialogText()).toBe(fromMap);
    await waitFor(() => expect(spies.focus).toHaveBeenCalledWith("riau-0102"));
    expect(spies.select).toHaveBeenLastCalledWith("riau-0102");
  });

  it("closing the dialog clears the selection and returns focus to the row", async () => {
    renderApp("/ops");
    const row = within(await rankedList()).getByRole("button", { name: /riau-0102/ });
    row.focus();
    fireEvent.click(row);
    await screen.findByRole("dialog", { name: "Area riau-0102" });

    fireEvent.keyDown(screen.getByRole("dialog"), { key: "Escape" });

    await waitFor(() => expect(screen.queryByRole("dialog")).not.toBeInTheDocument());
    const list = await rankedList();
    expect(within(list).queryByRole("button", { pressed: true })).not.toBeInTheDocument();
    expect(within(list).getByRole("button", { name: /riau-0102/ })).toHaveFocus();
  });
});
