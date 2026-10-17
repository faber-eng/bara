import { fireEvent, screen, waitFor, within } from "@testing-library/react";
import type { ReactNode } from "react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { renderApp, stubApi } from "../test-utils";

vi.mock("../lib/auth", () => ({ getIdToken: vi.fn().mockResolvedValue("token-1") }));

const spies = vi.hoisted(() => ({
  select: vi.fn(),
  focus: vi.fn(),
  onSelect: { current: (_cellId: string) => {} },
}));

vi.mock("../lib/ops/cellLayer", () => ({
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
    vi.stubGlobal("google", { maps: { ImageMapType: FakeImageMapType, Size: class {} } });
    stubApi({
      "GET /api/cells/riau-0102": () => Response.json({ ...FACTS, cell_id: "riau-0102" }),
    });
  });

  it("a map click selects the row, opens the panel and does not move the map", async () => {
    renderApp("/ops");
    await screen.findByRole("table");
    await waitFor(() => expect(spies.onSelect.current).not.toBe(undefined));

    spies.onSelect.current("riau-0102");

    const panel = await screen.findByRole("region", { name: "Cell riau-0102" });
    expect(within(panel).getByText("riau-0102")).toBeInTheDocument();
    const pressed = within(screen.getByRole("table")).getByRole("button", { pressed: true });
    expect(pressed).toHaveTextContent("riau-0102");
    expect(spies.focus).not.toHaveBeenCalled();
  });

  it("a row click selects the cell, opens the panel and zooms the map to it", async () => {
    renderApp("/ops");
    await screen.findByRole("table");
    await waitFor(() => expect(spies.select).toHaveBeenCalled());

    fireEvent.click(screen.getByRole("button", { name: "riau-0102" }));

    await screen.findByRole("region", { name: "Cell riau-0102" });
    await waitFor(() => expect(spies.focus).toHaveBeenCalledWith("riau-0102"));
    expect(spies.select).toHaveBeenLastCalledWith("riau-0102");
  });

  it("closing the panel clears the selection", async () => {
    renderApp("/ops?cell=riau-0102");
    const panel = await screen.findByRole("region", { name: "Cell riau-0102" });

    fireEvent.click(within(panel).getByRole("button", { name: "Close" }));

    await waitFor(() =>
      expect(screen.queryByRole("region", { name: "Cell riau-0102" })).not.toBeInTheDocument(),
    );
    const table = await screen.findByRole("table");
    expect(within(table).queryByRole("button", { pressed: true })).not.toBeInTheDocument();
  });
});
