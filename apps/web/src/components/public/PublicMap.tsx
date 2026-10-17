import { useQuery } from "@tanstack/react-query";
import { APIProvider, Map as GoogleMap } from "@vis.gl/react-google-maps";
import { useEffect, useMemo, useState } from "react";
import type { PublicQuery } from "../../lib/api/publicData";
import { publicDamsQuery, publicRecordQuery, publicTilesQuery } from "../../lib/api/publicQueries";
import type { PublicCell, PublicDam, TileLayerKind } from "../../lib/contracts";
import type { CopyLanguage } from "../../lib/copy/language";
import type { PublicCopy } from "../../lib/copy/public";
import { type DamMarker, damColor } from "../../lib/ops/cellLayer";
import { DEFAULT_MAP_TYPE, type MapTypeId } from "../../lib/ops/mapLayers";
import { formatNumber } from "../../lib/public/format";
import { openCaseCells } from "../../lib/public/openCases";
import type { PublicRegion } from "../../lib/public/regions";
import { CellsLayer, DamsLayer } from "../ops/CellsLayer";
import { MapTypeControl } from "../ops/MapControls";
import { TileOverlay } from "../ops/TileOverlay";
import { OpenCaseOutlines } from "./OpenCaseOutlines";

type OverlayKind = Extract<TileLayerKind, "drying" | "burn_scars" | "reignition">;

const OVERLAYS: readonly OverlayKind[] = ["drying", "burn_scars", "reignition"];
const OVERLAY_OPACITY: Record<OverlayKind, number> = {
  drying: 0.7,
  burn_scars: 0.6,
  reignition: 0.7,
};

function readMapsKey(): string {
  const key: unknown = import.meta.env.VITE_MAPS_KEY;
  return typeof key === "string" ? key : "";
}

function toMarker(dam: PublicDam): DamMarker {
  return { dam_id: dam.id, point: dam.point, last_state: dam.last_state };
}

function overlayLabel(copy: PublicCopy, kind: OverlayKind): string {
  if (kind === "drying") return copy.map.drying;
  if (kind === "burn_scars") return copy.map.burnScars;
  return copy.map.reignition;
}

type OverlayState = Record<OverlayKind, boolean>;

function OverlayLayer({
  kind,
  query,
  label,
  onUnavailable,
}: {
  kind: OverlayKind;
  query: PublicQuery;
  label: string;
  onUnavailable: (kind: OverlayKind) => void;
}) {
  const tiles = useQuery(publicTilesQuery(kind, query));
  const failed = tiles.isError;

  useEffect(() => {
    if (failed) onUnavailable(kind);
  }, [failed, kind, onUnavailable]);

  if (tiles.data === undefined) return null;
  return (
    <TileOverlay
      label={label}
      urlTemplate={tiles.data.url_template}
      opacity={OVERLAY_OPACITY[kind]}
    />
  );
}

type LayerPickerProps = {
  copy: PublicCopy;
  active: OverlayState;
  broken: ReadonlySet<OverlayKind>;
  onToggle: (kind: OverlayKind) => void;
};

function LayerPicker({ copy, active, broken, onToggle }: LayerPickerProps) {
  return (
    <fieldset className="pub-layers">
      <legend className="visually-hidden">{copy.map.layers}</legend>
      {OVERLAYS.map((kind) => (
        <label key={kind} className="check">
          <input
            type="checkbox"
            checked={active[kind]}
            disabled={broken.has(kind)}
            onChange={() => onToggle(kind)}
          />
          <span>
            {overlayLabel(copy, kind)}
            {broken.has(kind) && ` (${copy.map.layerUnavailable})`}
          </span>
        </label>
      ))}
    </fieldset>
  );
}

function MapLegendKeys({ copy }: { copy: PublicCopy }) {
  return (
    <div className="map-legend pub-legend">
      <div className="map-legend-title">{copy.map.drying}</div>
      <div className="risk-ramp" aria-hidden="true">
        {[1, 2, 3, 4, 5].map((step) => (
          <span key={step} style={{ background: `var(--risk-${step})` }} />
        ))}
      </div>
      <div className="legend-scale num map-legend-scale">
        <span>{copy.map.lowScore}</span>
        <span>{copy.map.highScore}</span>
      </div>
      <div className="legend-keys">
        <span>
          <i style={{ background: damColor("broken") }} />
          {copy.map.damBroken}
        </span>
        <span>
          <i style={{ background: damColor("damaged") }} />
          {copy.map.damDamaged}
        </span>
        <span>
          <i style={{ background: damColor("intact") }} />
          {copy.map.damIntact}
        </span>
        <span>
          <i className="key-case" />
          {copy.map.openCase}
        </span>
      </div>
    </div>
  );
}

type PublicMapProps = {
  region: PublicRegion;
  query: PublicQuery;
  cells: readonly PublicCell[];
  copy: PublicCopy;
  language: CopyLanguage;
  onReady: () => void;
};

export function PublicMap({ region, query, cells, copy, language, onReady }: PublicMapProps) {
  const dams = useQuery({ ...publicDamsQuery(region.id), enabled: !region.rankingOnly });
  const record = useQuery({ ...publicRecordQuery(region.id), enabled: !region.rankingOnly });
  const [mapType, setMapType] = useState<MapTypeId>(DEFAULT_MAP_TYPE);
  const [active, setActive] = useState<OverlayState>({
    drying: true,
    burn_scars: false,
    reignition: false,
  });
  const [broken, setBroken] = useState<ReadonlySet<OverlayKind>>(new Set());
  const [selectedId, setSelectedId] = useState<string | undefined>(undefined);
  const markers = useMemo(() => (dams.data ?? []).map(toMarker), [dams.data]);
  const openIds = useMemo(() => openCaseCells(record.data ?? []), [record.data]);
  const selected = cells.find((cell) => cell.cell_id === selectedId);
  const mapsKey = readMapsKey();

  function toggle(kind: OverlayKind) {
    setActive((previous) => ({ ...previous, [kind]: !previous[kind] }));
  }

  function markBroken(kind: OverlayKind) {
    setBroken((previous) => (previous.has(kind) ? previous : new Set(previous).add(kind)));
    setActive((previous) => ({ ...previous, [kind]: false }));
  }

  if (mapsKey === "") {
    return (
      <div className="ops-map pub-map">
        <p role="status" className="map-note">
          {copy.map.keyMissing}
        </p>
      </div>
    );
  }

  return (
    <div className="ops-map pub-map">
      <APIProvider apiKey={mapsKey}>
        <GoogleMap
          defaultCenter={region.center}
          defaultZoom={region.zoom}
          mapTypeId={mapType}
          gestureHandling="cooperative"
          disableDefaultUI
          onTilesLoaded={onReady}
        >
          {OVERLAYS.filter((kind) => active[kind]).map((kind) => (
            <OverlayLayer
              key={kind}
              kind={kind}
              query={query}
              label={overlayLabel(copy, kind)}
              onUnavailable={markBroken}
            />
          ))}
          <CellsLayer
            cells={cells}
            selectedCellId={selectedId}
            focus={null}
            onSelect={setSelectedId}
          />
          <DamsLayer dams={markers} onSelect={() => undefined} />
          <OpenCaseOutlines cells={cells} openCellIds={openIds} />
        </GoogleMap>
      </APIProvider>
      <MapTypeControl value={mapType} onChange={setMapType} />
      <LayerPicker copy={copy} active={active} broken={broken} onToggle={toggle} />
      <MapLegendKeys copy={copy} />
      {selected !== undefined && (
        <p role="status" className="map-note pub-cell-note">
          {copy.map.cell(selected.cell_id, formatNumber(selected.drying_score, language))}
        </p>
      )}
    </div>
  );
}
