import { useQueries, useQuery } from "@tanstack/react-query";
import { APIProvider, Map as GoogleMap, useMap } from "@vis.gl/react-google-maps";
import { useEffect, useRef, useState } from "react";
import { isNotFoundError } from "../../lib/api/client";
import { allCellsQuery, rankingsQuery, tileLayerQuery } from "../../lib/api/queries";
import type { TileLayerKind } from "../../lib/contracts";
import { damCellId } from "../../lib/ops/cellSelection";
import {
  DEFAULT_MAP_TYPE,
  defaultEnabledLayers,
  definitionFor,
  type EnabledLayers,
  enabledKinds,
  type LayerOpacities,
  type MapTypeId,
} from "../../lib/ops/mapLayers";
import { LAYER_START, markStart, WEEK_START } from "../../lib/ops/perf";
import { RANKED_CELL_LIMIT, regionById } from "../../lib/ops/region";
import { useWeekPrefetch } from "../../lib/ops/useWeekPrefetch";
import { requestWeek, selectedWeek, weekRange } from "../../lib/ops/weeks";
import { CellPanel } from "./CellPanel";
import { CellsLayer, DamsLayer, type FocusRequest } from "./CellsLayer";
import { LayerOverlay } from "./LayerOverlay";
import { MapLegend, MapTypeControl } from "./MapControls";
import { LayerToggles, RegionSwitcher, WeekSlider } from "./OpsToolbar";

function readMapsKey(): string {
  const key: unknown = import.meta.env.VITE_MAPS_KEY;
  return typeof key === "string" ? key : "";
}

function Recenter({ regionId }: { regionId: string }) {
  const map = useMap();
  const appliedRef = useRef(regionId);
  useEffect(() => {
    if (map === null || appliedRef.current === regionId) return;
    appliedRef.current = regionId;
    const { center, zoom } = regionById(regionId);
    map.setCenter(center);
    map.setZoom(zoom);
  }, [map, regionId]);
  return null;
}

type OpsMapProps = {
  region: string;
  week: string | undefined;
  selectedCellId: string | undefined;
  focus: FocusRequest | null;
  onRegionChange: (regionId: string) => void;
  onWeekChange: (week: string | undefined) => void;
  onCellSelect: (cellId: string) => void;
  onCellClear: () => void;
};

export function OpsMap({
  region,
  week,
  selectedCellId,
  focus,
  onRegionChange,
  onWeekChange,
  onCellSelect,
  onCellClear,
}: OpsMapProps) {
  const regionInfo = regionById(region);
  const latestRankings = useQuery(rankingsQuery(region));
  const allCells = useQuery(allCellsQuery(region));
  const latest = latestRankings.data?.week;
  const asked = requestWeek(week, latest);
  const [mapType, setMapType] = useState<MapTypeId>(DEFAULT_MAP_TYPE);
  const [opacities, setOpacities] = useState<LayerOpacities>({});
  const [enabled, setEnabled] = useState<EnabledLayers>(defaultEnabledLayers);
  const mapsKey = readMapsKey();
  const kinds = enabledKinds(enabled);
  const tileQueries = useQueries({
    queries: kinds.map((kind) => tileLayerQuery(kind, region, asked)),
  });
  const failedKinds = kinds.filter((_, index) => tileQueries[index]?.isError);
  const noData = isNotFoundError(latestRankings.error);
  const cells = noData ? undefined : (allCells.data?.cells ?? latestRankings.data?.cells);
  useWeekPrefetch({ region, week, latest, enabled });

  function handleOpacityChange(layerId: string, opacity: number) {
    setOpacities((previous) => ({ ...previous, [layerId]: opacity }));
  }

  function handleToggle(layer: TileLayerKind) {
    markStart(LAYER_START);
    setEnabled((previous) => ({ ...previous, [layer]: !previous[layer] }));
  }

  function handleWeekCommit(next: string) {
    markStart(WEEK_START);
    onWeekChange(requestWeek(next, latest));
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
      <div className="map-toolbar">
        <RegionSwitcher value={region} onChange={onRegionChange} />
        <WeekSlider
          key={region}
          weeks={weekRange(latest)}
          value={selectedWeek(week, latest)}
          onCommit={handleWeekCommit}
        />
        <LayerToggles enabled={enabled} onToggle={handleToggle} />
      </div>
      <div className="ops-map-canvas">
        <APIProvider apiKey={mapsKey}>
          <GoogleMap
            defaultCenter={regionInfo.center}
            defaultZoom={regionInfo.zoom}
            mapTypeId={mapType}
            gestureHandling="greedy"
            disableDefaultUI
          >
            <Recenter regionId={region} />
            {kinds.map((kind) => (
              <LayerOverlay
                key={kind}
                kind={kind}
                region={region}
                week={asked}
                opacity={opacities[kind] ?? definitionFor(kind).defaultOpacity}
              />
            ))}
            {cells !== undefined && (
              <CellsLayer
                key={region}
                cells={cells}
                selectedCellId={selectedCellId}
                focus={focus}
                onSelect={onCellSelect}
              />
            )}
            {!noData && latestRankings.data && (
              <DamsLayer
                dams={latestRankings.data.dams}
                onSelect={(dam) => onCellSelect(damCellId(dam))}
              />
            )}
          </GoogleMap>
        </APIProvider>
        <MapTypeControl value={mapType} onChange={setMapType} />
        <div className="map-notes">
          {regionInfo.note !== null && (
            <p role="status" className="map-note">
              {regionInfo.note}
            </p>
          )}
          {noData && (
            <p role="status" className="map-note">
              No ranking data for {regionInfo.label} yet.
            </p>
          )}
          {!noData && allCells.isPending && (
            <p role="status" className="map-note">
              Loading all areas.
            </p>
          )}
          {!noData && allCells.isError && allCells.data === undefined && (
            <p role="status" className="map-note">
              Only the top {RANKED_CELL_LIMIT} areas are clickable right now.
            </p>
          )}
          {failedKinds.map((kind) => (
            <p key={kind} role="status" className="map-note">
              {definitionFor(kind).label} layer is unavailable right now.
            </p>
          ))}
        </div>
        <MapLegend
          definitions={kinds.map(definitionFor)}
          opacities={opacities}
          week={selectedWeek(week, latest)}
          onOpacityChange={handleOpacityChange}
        />
        {selectedCellId !== undefined && (
          <CellPanel key={selectedCellId} cellId={selectedCellId} onClose={onCellClear} />
        )}
      </div>
    </div>
  );
}
