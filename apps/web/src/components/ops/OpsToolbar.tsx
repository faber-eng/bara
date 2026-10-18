import { type ChangeEvent, useEffect, useRef, useState } from "react";
import type { TileLayerKind } from "../../lib/contracts";
import { type EnabledLayers, LAYER_DEFINITIONS } from "../../lib/ops/mapLayers";
import { OPS_REGIONS } from "../../lib/ops/region";
import { rangeFill } from "./MapControls";

const WEEK_COMMIT_DELAY_MS = 200;

type RegionSwitcherProps = { value: string; onChange: (regionId: string) => void };

export function RegionSwitcher({ value, onChange }: RegionSwitcherProps) {
  return (
    <fieldset className="segmented toolbar-group">
      <legend className="visually-hidden">Region</legend>
      {OPS_REGIONS.map((region) => (
        <button
          key={region.id}
          type="button"
          aria-pressed={region.id === value}
          onClick={() => onChange(region.id)}
        >
          {region.label}
        </button>
      ))}
    </fieldset>
  );
}

type WeekSliderProps = {
  weeks: readonly string[];
  value: string | undefined;
  onCommit: (week: string) => void;
};

function indexOfWeek(weeks: readonly string[], week: string | undefined): number {
  const index = week === undefined ? -1 : weeks.indexOf(week);
  return index < 0 ? weeks.length - 1 : index;
}

export function WeekSlider({ weeks, value, onCommit }: WeekSliderProps) {
  const [draft, setDraft] = useState<{ week: string; base: string | undefined } | null>(null);
  const timerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const shown = draft !== null && draft.base === value ? draft.week : value;
  const index = indexOfWeek(weeks, shown);
  const fill = index / Math.max(1, weeks.length - 1);

  useEffect(
    () => () => {
      if (timerRef.current !== null) clearTimeout(timerRef.current);
    },
    [],
  );

  function handleChange(event: ChangeEvent<HTMLInputElement>) {
    const week = weeks[Number(event.target.value)];
    if (week === undefined) return;
    setDraft({ week, base: value });
    if (timerRef.current !== null) clearTimeout(timerRef.current);
    timerRef.current = setTimeout(() => {
      onCommit(week);
    }, WEEK_COMMIT_DELAY_MS);
  }

  return (
    <label className="week-slider" htmlFor="ops-week">
      <span>Week</span>
      <input
        id="ops-week"
        className="range"
        type="range"
        min={0}
        max={Math.max(0, weeks.length - 1)}
        step={1}
        value={index}
        disabled={weeks.length < 2}
        aria-valuetext={weeks[index]}
        style={rangeFill(fill)}
        onChange={handleChange}
      />
      <output className="num" htmlFor="ops-week">
        {weeks[index] ?? "no weeks"}
      </output>
    </label>
  );
}

type LayerTogglesProps = {
  enabled: EnabledLayers;
  onToggle: (layer: TileLayerKind) => void;
};

export function LayerToggles({ enabled, onToggle }: LayerTogglesProps) {
  return (
    <fieldset className="toolbar-group layer-toggles">
      <legend className="visually-hidden">Map layers</legend>
      {LAYER_DEFINITIONS.map((definition) => (
        <label key={definition.id} className="check layer-toggle">
          <input
            type="checkbox"
            checked={enabled[definition.id]}
            onChange={() => onToggle(definition.id)}
          />
          {definition.label}
        </label>
      ))}
    </fieldset>
  );
}
