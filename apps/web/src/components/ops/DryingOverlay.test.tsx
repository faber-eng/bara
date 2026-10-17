import { render } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { DryingOverlay } from "./DryingOverlay";

type TileOptions = {
  getTileUrl: (coord: { x: number; y: number }, zoom: number) => string | null;
  opacity: number;
};

const layers: unknown[] = [];
const fakeMap = {
  overlayMapTypes: {
    push: (layer: unknown) => layers.push(layer),
    getArray: () => layers,
    removeAt: (index: number) => layers.splice(index, 1),
  },
};
let currentMap: typeof fakeMap | null = fakeMap;

vi.mock("@vis.gl/react-google-maps", () => ({ useMap: () => currentMap }));

class FakeImageMapType {
  options: TileOptions;
  constructor(options: TileOptions) {
    this.options = options;
  }
}

describe("DryingOverlay", () => {
  beforeEach(() => {
    layers.length = 0;
    currentMap = fakeMap;
    vi.stubGlobal("google", {
      maps: { ImageMapType: FakeImageMapType, Size: class {} },
    });
  });

  it("registers an ImageMapType that fills the template", () => {
    render(<DryingOverlay urlTemplate="https://t.example/{z}/{x}/{y}" />);

    expect(layers).toHaveLength(1);
    const layer = layers[0] as FakeImageMapType;
    expect(layer.options.getTileUrl({ x: 3, y: 4 }, 5)).toBe("https://t.example/5/3/4");
  });

  it("replaces the layer when the template changes", () => {
    const view = render(<DryingOverlay urlTemplate="https://a.example/{z}/{x}/{y}" />);
    view.rerender(<DryingOverlay urlTemplate="https://b.example/{z}/{x}/{y}" />);

    expect(layers).toHaveLength(1);
    const layer = layers[0] as FakeImageMapType;
    expect(layer.options.getTileUrl({ x: 1, y: 1 }, 2)).toBe("https://b.example/2/1/1");
  });

  it("removes the layer on unmount", () => {
    const view = render(<DryingOverlay urlTemplate="https://a.example/{z}/{x}/{y}" />);

    view.unmount();

    expect(layers).toHaveLength(0);
  });

  it("does nothing until the map is ready", () => {
    currentMap = null;

    render(<DryingOverlay urlTemplate="https://a.example/{z}/{x}/{y}" />);

    expect(layers).toHaveLength(0);
  });
});
