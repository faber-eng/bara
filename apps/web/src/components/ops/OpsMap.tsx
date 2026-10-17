import { useQuery } from "@tanstack/react-query";
import { APIProvider, Map as GoogleMap } from "@vis.gl/react-google-maps";
import { useState } from "react";
import { allCellsQuery, dryingTilesQuery, rankingsQuery } from "../../lib/api/queries";
import { damCellId } from "../../lib/ops/cellSelection";
import {
  buildMapLayers,
  DEFAULT_MAP_TYPE,
  type LayerOpacities,
  layerOpacity,
  type MapTypeId,
} from "../../lib/ops/mapLayers";
import { OPS_MAP_CENTER, OPS_MAP_ZOOM, OPS_REGION, RANKED_CELL_LIMIT } from "../../lib/ops/region";
import { CellPanel } from "./CellPanel";
import { CellsLayer, DamsLayer, type FocusRequest } from "./CellsLayer";
import { MapLegend, MapTypeControl } from "./MapControls";
import { TileOverlay } from "./TileOverlay";

function readMapsKey(): string {
  const key: unknown = import.meta.env.VITE_MAPS_KEY;
  return typeof key === "string" ? key : "";
}

type OpsMapProps = {
  selectedCellId: string | undefined;
  focus: FocusRequest | null;
  onCellSelect: (cellId: string) => void;
  onCellClear: () => void;
};

export function OpsMap({ selectedCellId, focus, onCellSelect, onCellClear }: OpsMapProps) {
  const tiles = useQuery(dryingTilesQuery(OPS_REGION));
  const rankings = useQuery(rankingsQuery(OPS_REGION));
  const allCells = useQuery(allCellsQuery(OPS_REGION));
  const [mapType, setMapType] = useState<MapTypeId>(DEFAULT_MAP_TYPE);
  const [opacities, setOpacities] = useState<LayerOpacities>({});
  const mapsKey = readMapsKey();
  const layers = buildMapLayers(tiles.data);
  const cells = allCells.data?.cells ?? (allCells.isError ? rankings.data?.cells : undefined);

  function handleOpacityChange(layerId: string, opacity: number) {
    setOpacities((previous) => ({ ...previous, [layerId]: opacity }));
  }

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
          mapTypeId={mapType}
          gestureHandling="greedy"
          disableDefaultUI
        >
          {layers.map((layer) => (
            <TileOverlay
              key={layer.id}
              label={layer.label}
              urlTemplate={layer.urlTemplate}
              opacity={layerOpacity(layer, opacities)}
            />
          ))}
          {cells !== undefined && (
            <CellsLayer
              cells={cells}
              selectedCellId={selectedCellId}
              focus={focus}
              onSelect={onCellSelect}
            />
          )}
          {rankings.data && (
            <DamsLayer dams={rankings.data.dams} onSelect={(dam) => onCellSelect(damCellId(dam))} />
          )}
        </GoogleMap>
      </APIProvider>
      <MapTypeControl value={mapType} onChange={setMapType} />
      {allCells.isPending && (
        <p role="status" className="map-note">
          Loading all areas.
        </p>
      )}
      {allCells.isError && (
        <p role="status" className="map-note">
          Only the top {RANKED_CELL_LIMIT} areas are clickable right now.
        </p>
      )}
      {tiles.isError && (
        <p role="status" className="map-note">
          Drying layer is unavailable right now.
        </p>
      )}
      <MapLegend
        layers={layers}
        opacities={opacities}
        week={tiles.data?.week}
        onOpacityChange={handleOpacityChange}
      />
      {selectedCellId !== undefined && (
        <CellPanel key={selectedCellId} cellId={selectedCellId} onClose={onCellClear} />
      )}
    </div>
  );
}
