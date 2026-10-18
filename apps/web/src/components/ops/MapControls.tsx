import type { CSSProperties } from "react";
import {
  clampOpacity,
  type LayerDefinition,
  type LayerOpacities,
  MAP_TYPES,
  type MapTypeId,
} from "../../lib/ops/mapLayers";

const SLIDER_STEPS = 100;

export function rangeFill(share: number): CSSProperties {
  return { "--fill": `${Math.round(share * 100)}%` };
}

type MapTypeControlProps = { value: MapTypeId; onChange: (type: MapTypeId) => void };

export function MapTypeControl({ value, onChange }: MapTypeControlProps) {
  return (
    <fieldset className="map-types">
      <legend className="visually-hidden">Map type</legend>
      {MAP_TYPES.map((type) => (
        <button
          key={type.id}
          type="button"
          className="map-type-button"
          aria-pressed={type.id === value}
          onClick={() => onChange(type.id)}
        >
          {type.label}
        </button>
      ))}
    </fieldset>
  );
}

type OpacityRowProps = {
  definition: LayerDefinition;
  opacity: number;
  onOpacityChange: (layerId: string, opacity: number) => void;
};

function OpacityRow({ definition, opacity, onOpacityChange }: OpacityRowProps) {
  const inputId = `opacity-${definition.id}`;
  return (
    <label className="mv-opacity" htmlFor={inputId}>
      <span>{definition.label}</span>
      <input
        id={inputId}
        className="range"
        type="range"
        min={0}
        max={SLIDER_STEPS}
        value={Math.round(opacity * SLIDER_STEPS)}
        style={rangeFill(opacity)}
        onChange={(event) =>
          onOpacityChange(definition.id, clampOpacity(Number(event.target.value) / SLIDER_STEPS))
        }
      />
    </label>
  );
}

type LayerOpacityControlsProps = {
  title: string;
  emptyText: string;
  definitions: readonly LayerDefinition[];
  opacities: LayerOpacities;
  onOpacityChange: (layerId: string, opacity: number) => void;
};

export function LayerOpacityControls({
  title,
  emptyText,
  definitions,
  opacities,
  onOpacityChange,
}: LayerOpacityControlsProps) {
  return (
    <details className="mv-key-more">
      <summary>{title}</summary>
      {definitions.map((definition) => (
        <OpacityRow
          key={definition.id}
          definition={definition}
          opacity={opacities[definition.id] ?? definition.defaultOpacity}
          onOpacityChange={onOpacityChange}
        />
      ))}
      {definitions.length === 0 && <p className="mv-key-note">{emptyText}</p>}
    </details>
  );
}
