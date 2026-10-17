import { isSafeMapUrl, mapPoint } from "../../lib/brigade/pack";

const COORD_DIGITS = 4;

export function MiniMap({ mapUrl }: { mapUrl: string }) {
  const point = mapPoint(mapUrl);
  return (
    <div className="mini-map">
      <svg viewBox="0 0 300 180" role="img" aria-label="Mini map of the escalation location">
        <rect width="300" height="180" className="m-land" />
        <path d="M0 130 C 80 110, 160 150, 300 120" className="m-river" />
        <path d="M0 30 L 300 50" className="m-canal" />
        <circle cx="150" cy="90" r="14" className="m-sel" />
      </svg>
      {point !== null && (
        <p className="ops-meta">
          {point.lat.toFixed(COORD_DIGITS)}, {point.lon.toFixed(COORD_DIGITS)}
        </p>
      )}
      {isSafeMapUrl(mapUrl) && (
        <a className="link" href={mapUrl} target="_blank" rel="noreferrer">
          Open in Google Maps
        </a>
      )}
    </div>
  );
}
