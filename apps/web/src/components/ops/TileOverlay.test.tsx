import { render } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { TileOverlay } from "./TileOverlay";

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
    insertAt: (index: number, layer: unknown) => layers.splice(index, 0, layer),
  },
};
let currentMap: typeof fakeMap | null = fakeMap;

vi.mock("@vis.gl/react-google-maps", () => ({ useMap: () => currentMap }));

class FakeImageMapType {
  options: TileOptions;
  constructor(options: TileOptions) {
    this.options = options;
  }
  setOpacity(value: number) {
    this.options.opacity = value;
  }
}

describe("TileOverlay", () => {
  beforeEach(() => {
    layers.length = 0;
    currentMap = fakeMap;
    vi.stubGlobal("google", {
      maps: { ImageMapType: FakeImageMapType, Size: class {} },
    });
  });

  it("registers an ImageMapType that fills the template", () => {
    render(
      <TileOverlay
        label="Drying score"
        urlTemplate="https://t.example/{z}/{x}/{y}"
        opacity={0.7}
      />,
    );

    expect(layers).toHaveLength(1);
    const layer = layers[0] as FakeImageMapType;
    expect(layer.options.getTileUrl({ x: 3, y: 4 }, 5)).toBe("https://t.example/5/3/4");
  });

  it("keeps the same layer object and reloads its tiles when the template changes", () => {
    const view = render(
      <TileOverlay
        label="Drying score"
        urlTemplate="https://a.example/{z}/{x}/{y}"
        opacity={0.7}
      />,
    );
    const original = layers[0];
    const insertSpy = vi.spyOn(fakeMap.overlayMapTypes, "insertAt");
    view.rerender(
      <TileOverlay
        label="Drying score"
        urlTemplate="https://b.example/{z}/{x}/{y}"
        opacity={0.7}
      />,
    );

    expect(layers).toHaveLength(1);
    expect(layers[0]).toBe(original);
    expect(insertSpy).toHaveBeenCalledTimes(1);
    const layer = layers[0] as FakeImageMapType;
    expect(layer.options.getTileUrl({ x: 1, y: 1 }, 2)).toBe("https://b.example/2/1/1");
  });

  it("changes the opacity in place without rebuilding the layer", () => {
    const view = render(
      <TileOverlay
        label="Drying score"
        urlTemplate="https://a.example/{z}/{x}/{y}"
        opacity={0.7}
      />,
    );
    const layer = layers[0] as FakeImageMapType;

    view.rerender(
      <TileOverlay
        label="Drying score"
        urlTemplate="https://a.example/{z}/{x}/{y}"
        opacity={0.2}
      />,
    );

    expect(layers).toHaveLength(1);
    expect(layers[0]).toBe(layer);
    expect(layer.options.opacity).toBe(0.2);
  });

  it("starts at the given opacity", () => {
    render(
      <TileOverlay
        label="Drying score"
        urlTemplate="https://a.example/{z}/{x}/{y}"
        opacity={0.4}
      />,
    );

    expect((layers[0] as FakeImageMapType).options.opacity).toBe(0.4);
  });

  it("removes the layer on unmount", () => {
    const view = render(
      <TileOverlay
        label="Drying score"
        urlTemplate="https://a.example/{z}/{x}/{y}"
        opacity={0.7}
      />,
    );

    view.unmount();

    expect(layers).toHaveLength(0);
  });

  it("does nothing until the map is ready", () => {
    currentMap = null;

    render(
      <TileOverlay
        label="Drying score"
        urlTemplate="https://a.example/{z}/{x}/{y}"
        opacity={0.7}
      />,
    );

    expect(layers).toHaveLength(0);
  });
});
