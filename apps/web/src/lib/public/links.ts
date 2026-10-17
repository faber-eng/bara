export type DownloadKind = "csv" | "geojson";

export function exportPath(region: string, week: string, kind: DownloadKind): string {
  const extension = kind === "csv" ? "csv" : "geojson";
  return `/api/public/${encodeURIComponent(region)}/export.${extension}?week=${encodeURIComponent(week)}`;
}

export function apiRootPath(region: string): string {
  return `/api/public/${encodeURIComponent(region)}`;
}

export const LICENSE = {
  name: "CC BY-NC-SA 4.0",
  url: "https://creativecommons.org/licenses/by-nc-sa/4.0/",
};

export const CREDITS: readonly string[] = [
  "Peat mask: Global Peatland Map 2.0, Greifswald Mire Centre (CC BY-NC-SA 4.0)",
  "Radar: contains modified Copernicus Sentinel-1 data",
  "Rainfall: CHIRPS, Climate Hazards Center, UC Santa Barbara",
  "Canals: OpenStreetMap contributors (ODbL)",
];
