import { useQuery } from "@tanstack/react-query";
import { APIProvider, Map as GoogleMap } from "@vis.gl/react-google-maps";
import { useEffect, useMemo, useState } from "react";
import type { PublicQuery } from "../../lib/api/publicData";
import { publicDamsQuery, publicRecordQuery, publicTilesQuery } from "../../lib/api/publicQueries";
import type { PublicCell, PublicDam, TileLayerKind } from "../../lib/contracts";
import { type DetailCopy, detailCopy } from "../../lib/copy/detail";
import type { CopyLanguage } from "../../lib/copy/language";
import type { PublicCopy } from "../../lib/copy/public";
import type { DamMarker } from "../../lib/ops/cellLayer";
import { DEFAULT_MAP_TYPE, type MapTypeId } from "../../lib/ops/mapLayers";
import { openCaseCells } from "../../lib/public/openCases";
import type { PublicRegion } from "../../lib/public/regions";
import { DetailSheet } from "../detail/DetailSheet";
import { PublicCellDetail, PublicDamDetail } from "../detail/PublicDetails";
import { MapKey, type MapKeyMark } from "../map/MapKey";
import { CellsLayer, DamsLayer } from "../ops/CellsLayer";
import { MapTypeControl } from "../ops/MapControls";
import { TileOverlay } from "../ops/TileOverlay";
import { OpenCaseOutlines } from "./OpenCaseOutlines";

type OverlayKind = Extract<TileLayerKind, "drying" | "burn_scars" | "reignition">;

const OVERLAYS: readonly OverlayKind[] = ["drying", "burn_scars", "reignition"];
const OPEN_DATA_HEADING_ID = "pub-data-title";
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
    <fieldset className="pub-layers mv-layers">
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

type Selection = { kind: "cell" | "dam"; id: string };

function publicMarks(region: PublicRegion, active: OverlayState): MapKeyMark[] {
  const marks: MapKeyMark[] = ["cell"];
  if (!region.rankingOnly) marks.push("dam", "case");
  if (active.burn_scars) marks.push("burnScar");
  if (active.reignition) marks.push("reignition");
  return marks;
}

function scrollToOpenData() {
  document.getElementById(OPEN_DATA_HEADING_ID)?.scrollIntoView({ block: "start" });
}

type SelectionBodyProps = {
  selection: Selection;
  cells: readonly PublicCell[];
  dams: readonly PublicDam[];
  openIds: readonly string[];
  copy: DetailCopy;
  language: CopyLanguage;
  timeZone: string;
  onDownload: () => void;
};

function SelectionBody({
  selection,
  cells,
  dams,
  openIds,
  copy,
  language,
  timeZone,
  onDownload,
}: SelectionBodyProps) {
  if (selection.kind === "dam") {
    const dam = dams.find((item) => item.id === selection.id);
    if (dam === undefined) return null;
    return (
      <PublicDamDetail
        dam={dam}
        copy={copy}
        language={language}
        timeZone={timeZone}
        onDownload={onDownload}
      />
    );
  }
  const cell = cells.find((item) => item.cell_id === selection.id);
  if (cell === undefined) return null;
  return (
    <PublicCellDetail
      cell={cell}
      openCase={openIds.includes(cell.cell_id)}
      copy={copy}
      language={language}
      onDownload={onDownload}
    />
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
  const [selection, setSelection] = useState<Selection | null>(null);
  const markers = useMemo(() => (dams.data ?? []).map(toMarker), [dams.data]);
  const openIds = useMemo(() => openCaseCells(record.data ?? []), [record.data]);
  const detail = detailCopy(language);
  const selectedCellId = selection?.kind === "cell" ? selection.id : undefined;
  const mapsKey = readMapsKey();

  function selectCell(cellId: string) {
    setSelection({ kind: "cell", id: cellId });
  }

  function selectDam(dam: DamMarker) {
    setSelection({ kind: "dam", id: dam.dam_id });
  }

  function handleDownload() {
    setSelection(null);
    scrollToOpenData();
  }

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
    <div className="ops-map pub-map mv-host">
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
            selectedCellId={selectedCellId}
            focus={null}
            onSelect={selectCell}
          />
          <DamsLayer dams={markers} onSelect={selectDam} />
          <OpenCaseOutlines cells={cells} openCellIds={openIds} />
        </GoogleMap>
      </APIProvider>
      <MapTypeControl value={mapType} onChange={setMapType} />
      <LayerPicker copy={copy} active={active} broken={broken} onToggle={toggle} />
      <MapKey marks={publicMarks(region, active)} copy={detail} screen="public" />
      {selection !== null && (
        <DetailSheet closeLabel={detail.close} onClose={() => setSelection(null)}>
          <SelectionBody
            selection={selection}
            cells={cells}
            dams={dams.data ?? []}
            openIds={openIds}
            copy={detail}
            language={language}
            timeZone={region.timeZone}
            onDownload={handleDownload}
          />
        </DetailSheet>
      )}
    </div>
  );
}
