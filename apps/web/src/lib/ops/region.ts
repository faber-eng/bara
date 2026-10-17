export type OpsRegion = {
  id: string;
  label: string;
  casework: boolean;
  center: { lat: number; lng: number };
  zoom: number;
  note: string | null;
};

export const OPS_REGIONS: readonly OpsRegion[] = [
  {
    id: "riau",
    label: "Riau",
    casework: true,
    center: { lat: 0.5, lng: 102.1 },
    zoom: 10,
    note: null,
  },
  {
    id: "congo_cuvette",
    label: "Congo",
    casework: false,
    center: { lat: 0.5, lng: 18.2 },
    zoom: 8,
    note: "Congo shows rankings and map layers only. There are no cases or review actions here.",
  },
];

export const DEFAULT_REGION_ID = "riau";
export const OPS_REGION = DEFAULT_REGION_ID;
export const OPS_MAP_CENTER = { lat: 0.5, lng: 102.1 };
export const OPS_MAP_ZOOM = 10;
export const RANKED_CELL_LIMIT = 200;
export const RANKED_MAX_ZOOM = 11;
export const RANKED_FIT_PADDING_PX = 48;

export function parseRegionId(value: unknown): string | undefined {
  return OPS_REGIONS.find((region) => region.id === value)?.id;
}

export function regionById(id: string | undefined): OpsRegion {
  const found = OPS_REGIONS.find((region) => region.id === id);
  return found ?? (OPS_REGIONS[0] as OpsRegion);
}
