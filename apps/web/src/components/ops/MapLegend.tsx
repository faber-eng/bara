const RAMP_STEPS = [1, 2, 3, 4, 5] as const;

export function MapLegend({ week }: { week: string | undefined }) {
  return (
    <div className="map-legend">
      <div className="map-legend-title">Drying score (0 to 100)</div>
      <div className="risk-ramp" aria-hidden="true">
        {RAMP_STEPS.map((step) => (
          <span key={step} style={{ background: `var(--risk-${step})` }} />
        ))}
      </div>
      <div className="legend-scale num map-legend-scale">
        <span>0</span>
        <span>50</span>
        <span>100</span>
      </div>
      {week !== undefined && (
        <p className="map-legend-note">Week {week}. Sentinel-1, rain and canals.</p>
      )}
    </div>
  );
}
