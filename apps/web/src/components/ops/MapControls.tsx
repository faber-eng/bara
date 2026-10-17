import {
  clampOpacity,
  type LayerDefinition,
  type LayerOpacities,
  type LegendSpec,
  MAP_TYPES,
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

function LegendKey({ legend }: { legend: LegendSpec }) {
  if (legend.kind === "swatches") {
    return (
      <ul className="legend-swatches">
        {legend.items.map((item) => (
          <li key={item.label}>
            <span className="legend-swatch" style={{ background: item.color }} aria-hidden="true" />
            {item.label}
          </li>
        ))}
      </ul>
    );
  }
  return (
    <>
      <div className="risk-ramp" aria-hidden="true">
        {RAMP_STEPS.map((step) => (
          <span key={step} style={{ background: `var(--risk-${step})` }} />
        ))}
      </div>
      <div className="legend-scale num map-legend-scale">
        <span>{legend.low}</span>
        <span>{legend.high}</span>
      </div>
    </>
  );
}

function legendTitle(definition: LayerDefinition): string {
  return definition.legend.kind === "ramp" ? `${definition.label} (0 to 100)` : definition.label;
}

type LayerRowProps = {
  definition: LayerDefinition;
  opacity: number;
  onOpacityChange: (layerId: string, opacity: number) => void;
};

function LayerRow({ definition, opacity, onOpacityChange }: LayerRowProps) {
  const inputId = `opacity-${definition.id}`;
  return (
    <div className="map-layer">
      <div className="map-legend-title">{legendTitle(definition)}</div>
      <LegendKey legend={definition.legend} />
      <label className="map-opacity" htmlFor={inputId}>
        <span>Opacity</span>
        <input
          id={inputId}
          type="range"
          min={0}
          max={SLIDER_STEPS}
          value={Math.round(opacity * SLIDER_STEPS)}
          onChange={(event) =>
            onOpacityChange(definition.id, clampOpacity(Number(event.target.value) / SLIDER_STEPS))
          }
        />
      </label>
    </div>
  );
}

type MapLegendProps = {
  definitions: readonly LayerDefinition[];
  opacities: LayerOpacities;
  week: string | undefined;
  onOpacityChange: (layerId: string, opacity: number) => void;
};

export function MapLegend({ definitions, opacities, week, onOpacityChange }: MapLegendProps) {
  return (
    <section className="map-legend" aria-label="Map legend">
      {definitions.map((definition) => (
        <LayerRow
          key={definition.id}
          definition={definition}
          opacity={opacities[definition.id] ?? definition.defaultOpacity}
          onOpacityChange={onOpacityChange}
        />
      ))}
      {definitions.length === 0 && <p className="map-legend-note">No map layers are on.</p>}
      {week !== undefined && <p className="map-legend-note">Week {week}.</p>}
    </section>
  );
}
