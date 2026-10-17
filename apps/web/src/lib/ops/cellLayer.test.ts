import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import type { RankedCell, RankedDam } from "../contracts";
import { createCellLayer, createDamLayer, damColor } from "./cellLayer";

type Listener = (event: unknown) => void;

class FakeData {
  static instances: FakeData[] = [];
  features = new Map<string, { id: string; properties: Record<string, unknown> }>();
  overrides = new Map<string, unknown>();
  listeners = new Map<string, Listener>();
  style: unknown;
  mapRef: unknown;
  addCalls = 0;
  constructor(options: { map: unknown; style: unknown }) {
    this.style = options.style;
    this.mapRef = options.map;
    FakeData.instances.push(this);
  }
  add(feature: { id: string; properties: Record<string, unknown> }) {
    this.addCalls++;
    this.features.set(feature.id, feature);
  }
  getFeatureById(id: string) {
    return this.features.get(id);
  }
  overrideStyle(feature: { id: string }, style: unknown) {
    this.overrides.set(feature.id, style);
  }
  revertStyle(feature: { id: string }) {
    this.overrides.delete(feature.id);
  }
  styles: unknown[] = [];
  setStyle(style: unknown) {
    this.styles.push(style);
    this.style = style;
  }
  setMap(map: unknown) {
    this.mapRef = map;
  }
  addListener(name: string, handler: Listener) {
    this.listeners.set(name, handler);
    return { remove: () => this.listeners.delete(name) };
  }
}

function makeMap() {
  const listeners = new Map<string, Listener>();
  return {
    listeners,
    zoom: 8,
    addListener: (name: string, handler: Listener) => {
      listeners.set(name, handler);
      return { remove: () => listeners.delete(name) };
    },
    getZoom() {
      return this.zoom;
    },
    setZoom: vi.fn(function (this: { zoom: number }, zoom: number) {
      this.zoom = zoom;
    }),
    panTo: vi.fn(),
    setOptions: vi.fn(),
  };
}

function cell(id: string, lat: number, lon: number, score: number): RankedCell {
  return {
    cell_id: id,
    region: "riau",
    week_start: "2026-10-12",
    centroid: { lat, lon },
    components: {
      s1_anom_db: null,
      rain_30d_mm: 1,
      rain_deficit_pct: 0.5,
      canal_dist_m: 10,
      peat_class: 1,
    },
    drying_score: score,
    rank: 1,
    rank_change: null,
    stale_s1: false,
    explanation: null,
  };
}

function latLng(lat: number, lon: number) {
  return { latLng: { lat: () => lat, lng: () => lon } };
}

const CELLS = [cell("a", 0.5, 102.1, 95), cell("b", 0.5, 102.3, 10)];

describe("createCellLayer", () => {
  beforeEach(() => {
    FakeData.instances = [];
    vi.stubGlobal("requestAnimationFrame", (run: () => void) => {
      run();
      return 1;
    });
    vi.stubGlobal("cancelAnimationFrame", () => {});
    vi.stubGlobal("google", {
      maps: {
        Data: Object.assign(FakeData, { Polygon: class {} }),
        LatLng: class {},
      },
    });
  });
  afterEach(() => vi.unstubAllGlobals());

  it("adds every cell to one Data layer once, with one click listener on the map", () => {
    const map = makeMap();

    createCellLayer(map as never, CELLS, { onSelect: vi.fn() });

    expect(FakeData.instances).toHaveLength(1);
    expect(FakeData.instances[0]?.addCalls).toBe(2);
    expect([...map.listeners.keys()].sort()).toEqual(["click", "mousemove", "zoom_changed"]);
  });

  it("selects the cell under a map click by point, not by shape", () => {
    const map = makeMap();
    const onSelect = vi.fn();
    createCellLayer(map as never, CELLS, { onSelect });

    map.listeners.get("click")?.(latLng(0.5001, 102.3001));

    expect(onSelect).toHaveBeenCalledWith("b");
  });

  it("ignores a click outside every cell", () => {
    const map = makeMap();
    const onSelect = vi.fn();
    createCellLayer(map as never, CELLS, { onSelect });

    map.listeners.get("click")?.(latLng(0.9, 102.9));

    expect(onSelect).not.toHaveBeenCalled();
  });

  it("highlights the hovered cell and clears it on leaving, without adding features", () => {
    const map = makeMap();
    createCellLayer(map as never, CELLS, { onSelect: vi.fn() });
    const data = FakeData.instances[0] as FakeData;

    map.listeners.get("mousemove")?.(latLng(0.5, 102.1));
    expect(data.overrides.has("a")).toBe(true);
    map.listeners.get("mousemove")?.(latLng(0.9, 102.9));

    expect(data.overrides.size).toBe(0);
    expect(data.addCalls).toBe(2);
  });

  it("restyles only the previous and the new selected cell", () => {
    const map = makeMap();
    const layer = createCellLayer(map as never, CELLS, { onSelect: vi.fn() });
    const data = FakeData.instances[0] as FakeData;

    layer.select("a");
    layer.select("b");

    expect([...data.overrides.keys()]).toEqual(["b"]);
    layer.select(undefined);
    expect(data.overrides.size).toBe(0);
    expect(data.addCalls).toBe(2);
  });

  it("pans and zooms to a cell, never zooming out", () => {
    const map = makeMap();
    const layer = createCellLayer(map as never, CELLS, { onSelect: vi.fn() });

    layer.focus("b");

    expect(map.panTo).toHaveBeenCalledWith({ lat: 0.5, lng: 102.3 });
    expect(map.zoom).toBe(14);
    map.zoom = 16;
    layer.focus("a");
    expect(map.zoom).toBe(16);
  });

  it("removes its listeners and the Data layer on destroy", () => {
    const map = makeMap();
    const layer = createCellLayer(map as never, CELLS, { onSelect: vi.fn() });

    layer.destroy();

    expect(map.listeners.size).toBe(0);
    expect(FakeData.instances[0]?.mapRef).toBeNull();
  });

  it("draws cells with a minimum pixel stroke below zoom 12 and thin polygons from zoom 12", () => {
    const map = makeMap();
    createCellLayer(map as never, CELLS, { onSelect: vi.fn() });
    const data = FakeData.instances[0] as FakeData;
    const feature = { getProperty: () => 95 };
    const styleOf = () =>
      (data.style as (f: unknown) => { strokeWeight: number; fillOpacity: number })(feature);

    expect(styleOf().strokeWeight).toBe(3);
    expect(styleOf().fillOpacity).toBe(0.35);
    map.zoom = 12;
    map.listeners.get("zoom_changed")?.({});
    expect(data.styles).toHaveLength(1);
    expect(styleOf().strokeWeight).toBe(1);
    map.zoom = 13;
    map.listeners.get("zoom_changed")?.({});
    expect(data.styles).toHaveLength(1);
    map.zoom = 9;
    map.listeners.get("zoom_changed")?.({});
    expect(styleOf().strokeWeight).toBe(3);
  });

  it("builds a 3,769 cell layer and answers clicks", () => {
    const many = Array.from({ length: 3769 }, (_, i) =>
      cell(`c${i}`, -1 + (i % 60) * 0.02, 101 + Math.floor(i / 60) * 0.02, i % 100),
    );
    const map = makeMap();
    const onSelect = vi.fn();
    createCellLayer(map as never, many, { onSelect });
    map.listeners.get("click")?.(latLng(-1 + 7 * 0.02, 101 + 9 * 0.02));

    expect(onSelect).toHaveBeenCalledWith("c547");
  });
});

describe("createDamLayer", () => {
  beforeEach(() => {
    FakeData.instances = [];
    vi.stubGlobal("google", {
      maps: {
        Data: Object.assign(FakeData, { Point: class {} }),
        SymbolPath: { CIRCLE: 0 },
      },
    });
  });
  afterEach(() => vi.unstubAllGlobals());

  const DAM = {
    dam_id: "dam-1",
    cell_id: "a",
    point: { lat: 0.5, lon: 102.1 },
    last_state: "broken",
  } as RankedDam;

  it("selects the dam that was clicked", () => {
    const onSelect = vi.fn();
    createDamLayer(makeMap() as never, [DAM], onSelect);

    FakeData.instances[0]?.listeners.get("click")?.({ feature: { getId: () => "dam-1" } });

    expect(onSelect).toHaveBeenCalledWith(DAM);
  });

  it("colours each dam state", () => {
    expect(damColor("broken")).not.toBe(damColor("intact"));
    expect(damColor("unknown")).toBe(damColor("not_applicable"));
  });
});
