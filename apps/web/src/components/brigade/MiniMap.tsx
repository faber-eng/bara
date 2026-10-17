import { APIProvider, Map as GoogleMap, Marker } from "@vis.gl/react-google-maps";
import { useState } from "react";
import { isSafeMapUrl, mapPoint } from "../../lib/brigade/pack";
import type { GeoPoint } from "../../lib/contracts";
import { readMapsKey } from "../join/HomeMap";

const COORD_DIGITS = 4;
const MINI_MAP_ZOOM = 13;

function MapUnavailable() {
  return (
    <div className="mini-map-box mini-map-empty" role="img" aria-label="Map not available">
      Map not available
    </div>
  );
}

function PointMap({ point, onError }: { point: GeoPoint; onError: () => void }) {
  const position = { lat: point.lat, lng: point.lon };
  return (
    <div className="mini-map-box">
      <APIProvider apiKey={readMapsKey()} onError={onError}>
        <GoogleMap
          defaultCenter={position}
          defaultZoom={MINI_MAP_ZOOM}
          mapTypeId="hybrid"
          gestureHandling="cooperative"
          disableDefaultUI
        >
          <Marker position={position} />
        </GoogleMap>
      </APIProvider>
    </div>
  );
}

export function MiniMap({ mapUrl }: { mapUrl: string }) {
  const point = mapPoint(mapUrl);
  const [failed, setFailed] = useState(false);
  const canDraw = point !== null && !failed && readMapsKey() !== "";
  return (
    <div className="mini-map">
      {canDraw ? <PointMap point={point} onError={() => setFailed(true)} /> : <MapUnavailable />}
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
