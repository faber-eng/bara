import type { TileLayerKind } from "../contracts";

export type MapTypeId = "roadmap" | "terrain" | "hybrid";

export const MAP_TYPES: readonly { id: MapTypeId; label: string }[] = [
  { id: "roadmap", label: "Map" },
  { id: "terrain", label: "Terrain" },
  { id: "hybrid", label: "Satellite" },
];

export const DEFAULT_MAP_TYPE: MapTypeId = "hybrid";

export type LegendSpec =
  | { kind: "ramp"; low: string; high: string }
  | { kind: "swatches"; items: readonly { color: string; label: string }[] };

export type LayerOpacities = Record<string, number>;

export type LayerDefinition = {
  id: TileLayerKind;
  label: string;
  weekly: boolean;
  defaultOpacity: number;
  defaultOn: boolean;
  legend: LegendSpec;
};

export const LAYER_DEFINITIONS: readonly LayerDefinition[] = [
  {
    id: "drying",
    label: "Drying score",
    weekly: true,
    defaultOpacity: 0.45,
    defaultOn: true,
    legend: { kind: "ramp", low: "0 low", high: "100 high" },
  },
  {
    id: "peat",
    label: "Peat",
    weekly: false,
    defaultOpacity: 0.6,
    defaultOn: false,
    legend: {
      kind: "swatches",
      items: [
        { color: "#8fb996", label: "Peat class 1" },
        { color: "#2f5d3a", label: "Peat class 2" },
      ],
    },
  },
  {
    id: "burn_scars",
    label: "Burn scars",
    weekly: true,
    defaultOpacity: 0.7,
    defaultOn: false,
    legend: { kind: "swatches", items: [{ color: "#4a2c1a", label: "Burned area" }] },
  },
  {
    id: "reignition",
    label: "Re-ignition risk",
    weekly: true,
    defaultOpacity: 0.7,
    defaultOn: false,
    legend: { kind: "ramp", low: "0 low", high: "1 high" },
  },
];

export type EnabledLayers = Record<TileLayerKind, boolean>;

export function defaultEnabledLayers(): EnabledLayers {
  return {
    drying: true,
    peat: false,
    burn_scars: false,
    reignition: false,
  };
}

export function enabledKinds(enabled: EnabledLayers): TileLayerKind[] {
  return LAYER_DEFINITIONS.filter((definition) => enabled[definition.id]).map(
    (definition) => definition.id,
  );
}

export function definitionFor(kind: TileLayerKind): LayerDefinition {
  const found = LAYER_DEFINITIONS.find((definition) => definition.id === kind);
  return found ?? (LAYER_DEFINITIONS[0] as LayerDefinition);
}

export function clampOpacity(value: number): number {
  if (Number.isNaN(value)) return 0;
  return Math.min(1, Math.max(0, value));
}
