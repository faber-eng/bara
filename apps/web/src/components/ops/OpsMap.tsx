import { useQuery } from "@tanstack/react-query";
import { APIProvider, Map as GoogleMap } from "@vis.gl/react-google-maps";
import { dryingTilesQuery } from "../../lib/api/queries";
import { OPS_MAP_CENTER, OPS_MAP_ZOOM, OPS_REGION } from "../../lib/ops/region";
import { DryingOverlay } from "./DryingOverlay";
import { MapLegend } from "./MapLegend";

function readMapsKey(): string {
  const key: unknown = import.meta.env.VITE_MAPS_KEY;
  return typeof key === "string" ? key : "";
}

export function OpsMap() {
  const tiles = useQuery(dryingTilesQuery(OPS_REGION));
  const mapsKey = readMapsKey();

  if (mapsKey === "") {
    return (
      <div className="ops-map">
        <p role="alert" className="map-note">
          Map key is missing. Set VITE_MAPS_KEY and build again.
        </p>
      </div>
    );
  }

  return (
    <div className="ops-map">
      <APIProvider apiKey={mapsKey}>
        <GoogleMap
          defaultCenter={OPS_MAP_CENTER}
          defaultZoom={OPS_MAP_ZOOM}
          gestureHandling="greedy"
          disableDefaultUI
        >
          {tiles.data && <DryingOverlay urlTemplate={tiles.data.url_template} />}
        </GoogleMap>
      </APIProvider>
      {tiles.isError && (
        <p role="status" className="map-note">
          Drying layer is unavailable right now.
        </p>
      )}
      <MapLegend week={tiles.data?.week} />
    </div>
  );
}
