import { useQueries, useQuery } from "@tanstack/react-query";
import { APIProvider, Map as GoogleMap, useMap } from "@vis.gl/react-google-maps";
import { useEffect, useMemo, useRef, useState } from "react";
import { isNotFoundError } from "../../lib/api/client";
import { allCellsQuery, casesQuery, rankingsQuery, tileLayerQuery } from "../../lib/api/queries";
import type { TileLayerKind } from "../../lib/contracts";
import { detailCopy } from "../../lib/copy/detail";
import { useCopyLanguage } from "../../lib/copy/language";
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
import { MapKey, type MapKeyMark } from "../map/MapKey";
import { OpenCaseOutlines } from "../public/OpenCaseOutlines";
import { CellsLayer, DamsLayer, type FocusRequest } from "./CellsLayer";
import { LayerOverlay } from "./LayerOverlay";
import { LayerOpacityControls, MapTypeControl } from "./MapControls";
import { LayerToggles, RegionSwitcher, WeekSlider } from "./OpsToolbar";
import { openCaseByCell } from "./rankedRows";

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

const LAYER_MARKS: Partial<Record<TileLayerKind, MapKeyMark>> = {
  peat: "peat",
  burn_scars: "burnScar",
  reignition: "reignition",
};

function opsMarks(casework: boolean, kinds: readonly TileLayerKind[]): MapKeyMark[] {
  const marks: MapKeyMark[] = ["cell", "dam"];
  if (casework) marks.push("case");
  for (const kind of kinds) {
    const mark = LAYER_MARKS[kind];
    if (mark !== undefined) marks.push(mark);
  }
  return marks;
}

type OpsMapProps = {
  region: string;
  week: string | undefined;
  selectedCellId: string | undefined;
  highlightedCellId: string | undefined;
  focus: FocusRequest | null;
  onRegionChange: (regionId: string) => void;
  onWeekChange: (week: string | undefined) => void;
  onCellSelect: (cellId: string) => void;
  onDamSelect: (damId: string) => void;
  onCaseSelect: (caseId: string) => void;
};

export function OpsMap({
  region,
  week,
  selectedCellId,
  highlightedCellId,
  focus,
  onRegionChange,
  onWeekChange,
  onCellSelect,
  onDamSelect,
  onCaseSelect,
}: OpsMapProps) {
  const copy = detailCopy(useCopyLanguage());
  const regionInfo = regionById(region);
  const latestRankings = useQuery(rankingsQuery(region));
  const allCells = useQuery(allCellsQuery(region));
  const cases = useQuery({ ...casesQuery(region), enabled: regionInfo.casework });
  const openCases = useMemo(() => openCaseByCell(cases.data), [cases.data]);
  const openCellIds = useMemo(() => [...openCases.keys()], [openCases]);
  const latest = latestRankings.data?.week;
  const asked = requestWeek(week, latest);
  const [mapType, setMapType] = useState<MapTypeId>(DEFAULT_MAP_TYPE);
  const [opacities, setOpacities] = useState<LayerOpacities>({});
  const [enabled, setEnabled] = useState<EnabledLayers>(defaultEnabledLayers);
  const mapsKey = readMapsKey();
  const kinds = enabledKinds(enabled);
  const shownWeek = selectedWeek(week, latest);
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

  function handleOutlineSelect(cellId: string) {
    const record = openCases.get(cellId);
    if (record !== undefined) onCaseSelect(record.id);
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
          value={shownWeek}
          onCommit={handleWeekCommit}
        />
        <LayerToggles enabled={enabled} onToggle={handleToggle} />
      </div>
      <div className="ops-map-canvas mv-host">
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
                highlightedCellId={highlightedCellId}
                focus={focus}
                onSelect={onCellSelect}
              />
            )}
            {cells !== undefined && regionInfo.casework && (
              <OpenCaseOutlines
                cells={cells}
                openCellIds={openCellIds}
                onSelect={handleOutlineSelect}
              />
            )}
            {!noData && latestRankings.data && (
              <DamsLayer
                dams={latestRankings.data.dams}
                onSelect={(dam) => onDamSelect(dam.dam_id)}
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
        <MapKey marks={opsMarks(regionInfo.casework, kinds)} copy={copy} screen="ops">
          <LayerOpacityControls
            title={copy.key.opacity}
            emptyText={copy.key.noLayers}
            definitions={kinds.map(definitionFor)}
            opacities={opacities}
            onOpacityChange={handleOpacityChange}
          />
          {shownWeek !== undefined && <p className="mv-key-note">{copy.key.week(shownWeek)}</p>}
        </MapKey>
      </div>
    </div>
  );
}
