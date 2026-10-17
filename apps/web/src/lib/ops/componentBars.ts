import type { RankingComponents } from "../contracts";

export type ComponentBar = { key: string; label: string; share: number; value: string };

const RADAR_FULL_DB = 3;
const CANAL_DECAY_M = 1000;
const PEAT_WEIGHTS: Record<RankingComponents["peat_class"], number> = { 1: 1, 2: 0.6 };
const PERCENT = 100;

export function clampShare(value: number): number {
  if (Number.isNaN(value)) return 0;
  return Math.min(1, Math.max(0, value));
}

function radarBar(components: RankingComponents): ComponentBar {
  const dB = components.s1_anom_db;
  if (dB === null) return { key: "s1_anom_db", label: "Radar", share: 0, value: "n/a" };
  return {
    key: "s1_anom_db",
    label: "Radar",
    share: clampShare(-dB / RADAR_FULL_DB),
    value: `${dB.toFixed(1)} dB`,
  };
}

export function componentBars(components: RankingComponents): ComponentBar[] {
  return [
    radarBar(components),
    {
      key: "rain_deficit_pct",
      label: "Rain deficit",
      share: clampShare(components.rain_deficit_pct),
      value: `${Math.round(components.rain_deficit_pct * PERCENT)}%`,
    },
    {
      key: "canal_dist_m",
      label: "Canal",
      share: clampShare(Math.exp(-components.canal_dist_m / CANAL_DECAY_M)),
      value: `${Math.round(components.canal_dist_m)} m`,
    },
    {
      key: "peat_class",
      label: "Peat",
      share: PEAT_WEIGHTS[components.peat_class],
      value: `class ${components.peat_class}`,
    },
  ];
}
