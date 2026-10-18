import { fireEvent, screen, waitFor, within } from "@testing-library/react";
import type { ReactNode } from "react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { setCopyLanguage } from "../../lib/copy/language";
import type { DamMarker } from "../../lib/ops/cellLayer";
import { outlineMapsApi, renderApp, stubApi } from "../../test-utils";

vi.mock("../../lib/auth", () => ({ getIdToken: vi.fn().mockResolvedValue("token-1") }));

const spies = vi.hoisted(() => ({
  onCell: { current: (_cellId: string) => {} },
  onDam: { current: (_dam: DamMarker) => {} },
}));

vi.mock("../../lib/ops/cellLayer", async (importOriginal) => ({
  ...(await importOriginal<typeof import("../../lib/ops/cellLayer")>()),
  createCellLayer: (
    _map: unknown,
    _cells: unknown,
    handlers: { onSelect: (id: string) => void },
  ) => {
    spies.onCell.current = handlers.onSelect;
    return { select: vi.fn(), highlight: vi.fn(), focus: vi.fn(), destroy: vi.fn() };
  },
  createDamLayer: (_map: unknown, _dams: unknown, onSelect: (dam: DamMarker) => void) => {
    spies.onDam.current = onSelect;
    return { destroy: vi.fn() };
  },
}));

const fakeMap = {
  fitBounds: vi.fn(),
  setOptions: vi.fn(),
  addListener: () => ({ remove: vi.fn() }),
  overlayMapTypes: { push: vi.fn(), getArray: () => [], removeAt: vi.fn(), insertAt: vi.fn() },
};

vi.mock("@vis.gl/react-google-maps", () => ({
  APIProvider: ({ children }: { children: ReactNode }) => <div>{children}</div>,
  Map: ({ children }: { children: ReactNode }) => <div data-testid="map">{children}</div>,
  useMap: () => fakeMap,
}));

const CELL = {
  cell_id: "riau-0412",
  centroid: { lat: 0.5, lon: 102 },
  drying_score: 91.4,
  rank: 1,
  rank_change: 3,
  components: {
    s1_anom_db: -5.1,
    rain_30d_mm: 182.6,
    rain_deficit_pct: 0.2,
    canal_dist_m: 180,
    peat_class: 1,
  },
};

const DAM = {
  id: "dam-riau-017",
  point: { lat: 0.5, lon: 102 },
  last_state: "overtopped",
  last_checked_at: null,
  repair_due_at: null,
};

const SUMMARY = {
  region: "riau",
  week: "2026-W42",
  high_risk_cells: 12,
  dams_broken: 3,
  cases_open: 4,
  cases_escalated: 1,
  cases_closed: 2,
  median_days_to_repair: null,
  tasks_on_time_pct: 80,
  data_as_of: { s1_pass_date: "2026-10-12", ranking_run_at: "2026-10-11T17:00:00Z" },
};

function handlers() {
  return {
    "GET /api/public/riau/summary": () => Response.json(SUMMARY),
    "GET /api/public/riau/cells?limit=200": () =>
      Response.json({ region: "riau", week: "2026-W42", cells: [CELL] }),
    "GET /api/public/riau/bulletin": () => Response.json({}, { status: 404 }),
    "GET /api/public/riau/record?limit=50": () => Response.json([]),
    "GET /api/public/riau/dams": () => Response.json([DAM]),
  };
}

describe("public map details", () => {
  beforeEach(() => {
    setCopyLanguage("en");
    vi.stubEnv("VITE_MAPS_KEY", "test-key");
    vi.stubGlobal("google", {
      maps: { ImageMapType: class {}, Size: class {}, ...outlineMapsApi },
    });
    stubApi(handlers());
  });

  afterEach(() => {
    vi.unstubAllEnvs();
    vi.unstubAllGlobals();
  });

  it("opens the dam dialog from a dam click and names its state in plain words", async () => {
    renderApp("/public");
    await screen.findByRole("region", { name: "Map key" });
    await waitFor(() => expect(spies.onDam.current).not.toBe(undefined));

    spies.onDam.current({ dam_id: DAM.id, point: DAM.point, last_state: "overtopped" });

    const dialog = await screen.findByRole("dialog", { name: /dam-riau-017/ });
    expect(dialog).toHaveTextContent("Water over the top");
    expect(dialog).toHaveTextContent("Never checked");
    expect(dialog).not.toHaveTextContent("overtopped");
  });

  it("opens the cell dialog with units and closes it with Esc", async () => {
    renderApp("/public");
    await screen.findByRole("region", { name: "Map key" });

    spies.onCell.current("riau-0412");

    const dialog = await screen.findByRole("dialog", { name: "Area riau-0412" });
    expect(dialog).toHaveTextContent("91.4 / 100");
    expect(dialog).toHaveTextContent("180 m");
    expect(
      within(dialog).getByRole("button", { name: "Download this week's data" }),
    ).toBeInTheDocument();
    fireEvent.keyDown(dialog, { key: "Escape" });
    await waitFor(() => expect(screen.queryByRole("dialog")).not.toBeInTheDocument());
  });
});
