import {
  clampOpacity,
  type LayerOpacities,
  layerOpacity,
  MAP_TYPES,
  type MapLayerSpec,
  type MapTypeId,
} from "../../lib/ops/mapLayers";

const RAMP_STEPS = [1, 2, 3, 4, 5] as const;
const SLIDER_STEPS = 100;

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

type LayerRowProps = {
  layer: MapLayerSpec;
  opacity: number;
  onOpacityChange: (layerId: string, opacity: number) => void;
};

function LayerRow({ layer, opacity, onOpacityChange }: LayerRowProps) {
  const inputId = `opacity-${layer.id}`;
  return (
    <div className="map-layer">
      <div className="map-legend-title">{layer.label} (0 to 100)</div>
      <div className="risk-ramp" aria-hidden="true">
        {RAMP_STEPS.map((step) => (
          <span key={step} style={{ background: `var(--risk-${step})` }} />
        ))}
      </div>
      <div className="legend-scale num map-legend-scale">
        <span>{layer.legend.low} low</span>
        <span>{layer.legend.high} high</span>
      </div>
      <label className="map-opacity" htmlFor={inputId}>
        <span>Opacity</span>
        <input
          id={inputId}
          type="range"
          min={0}
          max={SLIDER_STEPS}
          value={Math.round(opacity * SLIDER_STEPS)}
          onChange={(event) =>
            onOpacityChange(layer.id, clampOpacity(Number(event.target.value) / SLIDER_STEPS))
          }
        />
      </label>
    </div>
  );
}

type MapLegendProps = {
  layers: readonly MapLayerSpec[];
  opacities: LayerOpacities;
  week: string | undefined;
  onOpacityChange: (layerId: string, opacity: number) => void;
};

export function MapLegend({ layers, opacities, week, onOpacityChange }: MapLegendProps) {
  return (
    <div className="map-legend">
      {layers.map((layer) => (
        <LayerRow
          key={layer.id}
          layer={layer}
          opacity={layerOpacity(layer, opacities)}
          onOpacityChange={onOpacityChange}
        />
      ))}
      {week !== undefined && (
        <p className="map-legend-note">Week {week}. Sentinel-1, rain and canals.</p>
      )}
    </div>
  );
}
