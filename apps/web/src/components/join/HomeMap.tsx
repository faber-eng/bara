import { APIProvider, Map as GoogleMap, Marker, useMap } from "@vis.gl/react-google-maps";
import { useEffect } from "react";
import type { GeoPoint } from "../../lib/contracts";
import { OPS_MAP_CENTER } from "../../lib/ops/region";

const HOME_MAP_ZOOM = 9;

export function readMapsKey(): string {
  const key: unknown = import.meta.env.VITE_MAPS_KEY;
  return typeof key === "string" ? key : "";
}

type HomeMapProps = { value: GeoPoint | null; onPick: (point: GeoPoint) => void };

function PanToValue({ value }: { value: GeoPoint | null }) {
  const map = useMap();
  useEffect(() => {
    if (map !== null && value !== null) map.panTo({ lat: value.lat, lng: value.lon });
  }, [map, value]);
  return null;
}

export function HomeMap({ value, onPick }: HomeMapProps) {
  const center = value === null ? OPS_MAP_CENTER : { lat: value.lat, lng: value.lon };
  return (
    <div className="home-map">
      <APIProvider apiKey={readMapsKey()}>
        <GoogleMap
          defaultCenter={center}
          defaultZoom={HOME_MAP_ZOOM}
          gestureHandling="greedy"
          disableDefaultUI
          onClick={(event) => {
            const at = event.detail.latLng;
            if (at !== null) onPick({ lat: at.lat, lon: at.lng });
          }}
        >
          <PanToValue value={value} />
          {value !== null && <Marker position={{ lat: value.lat, lng: value.lon }} />}
        </GoogleMap>
      </APIProvider>
    </div>
  );
}
