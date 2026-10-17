export type PublicRegion = {
  id: string;
  label: { id: string; en: string };
  center: { lat: number; lng: number };
  zoom: number;
  timeZone: string;
  rankingOnly: boolean;
};

const RIAU: PublicRegion = {
  id: "riau",
  label: { id: "Riau", en: "Riau" },
  center: { lat: 0.5, lng: 102.1 },
  zoom: 9,
  timeZone: "Asia/Jakarta",
  rankingOnly: false,
};

export const PUBLIC_REGIONS: readonly PublicRegion[] = [
  RIAU,
  {
    id: "congo_cuvette",
    label: { id: "Kongo", en: "Congo" },
    center: { lat: 0.4, lng: 18.2 },
    zoom: 7,
    timeZone: "Africa/Brazzaville",
    rankingOnly: true,
  },
];

export function findPublicRegion(id: string | undefined): PublicRegion {
  const found = PUBLIC_REGIONS.find((region) => region.id === id);
  return found ?? RIAU;
}
