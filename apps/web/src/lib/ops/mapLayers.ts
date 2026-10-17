import type { TileLayer } from "../contracts";

export type MapTypeId = "roadmap" | "terrain" | "hybrid";

export const MAP_TYPES: readonly { id: MapTypeId; label: string }[] = [
  { id: "roadmap", label: "Map" },
  { id: "terrain", label: "Terrain" },
  { id: "hybrid", label: "Satellite" },
];

export const DEFAULT_MAP_TYPE: MapTypeId = "hybrid";

export type MapLayerSpec = {
  id: string;
  label: string;
  urlTemplate: string;
  defaultOpacity: number;
  legend: { low: string; high: string };
};

export type LayerOpacities = Record<string, number>;

const DRYING_OPACITY = 0.7;

export function buildMapLayers(drying: TileLayer | undefined): MapLayerSpec[] {
  const layers: MapLayerSpec[] = [];
  if (drying !== undefined) {
    layers.push({
      id: "drying",
      label: "Drying score",
      urlTemplate: drying.url_template,
      defaultOpacity: DRYING_OPACITY,
      legend: { low: "0", high: "100" },
    });
  }
  return layers;
}

export function layerOpacity(layer: MapLayerSpec, overrides: LayerOpacities): number {
  return overrides[layer.id] ?? layer.defaultOpacity;
}

export function clampOpacity(value: number): number {
  if (Number.isNaN(value)) return 0;
  return Math.min(1, Math.max(0, value));
}
