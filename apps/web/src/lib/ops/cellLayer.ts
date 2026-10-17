import type { RankedCell, RankedDam } from "../contracts";
import { buildCellIndex, cellRing, findCellAt } from "./cellGrid";
import { scoreColor } from "./scoreColor";

const HIT_TOLERANCE_PX = 8;
const WORLD_TILE_PX = 256;
const FOCUS_ZOOM = 14;
const FILL_OPACITY = 0.55;

const BASE_STYLE = { clickable: false, strokeWeight: 1, fillOpacity: FILL_OPACITY } as const;
const HOVER_STYLE = { strokeWeight: 3, strokeColor: "#ffffff", fillOpacity: 0.85 } as const;
const SELECTED_STYLE = {
  strokeWeight: 4,
  strokeColor: "#0b3d2e",
  fillOpacity: 0.9,
  zIndex: 2,
} as const;

export type CellLayerHandlers = { onSelect: (cellId: string) => void };

export type CellLayer = {
  select: (cellId: string | undefined) => void;
  focus: (cellId: string) => void;
  destroy: () => void;
};

function toleranceDeg(zoom: number): number {
  return (HIT_TOLERANCE_PX * 360) / (WORLD_TILE_PX * 2 ** zoom);
}

function cellStyle(feature: google.maps.Data.Feature): google.maps.Data.StyleOptions {
  const score = Number(feature.getProperty("score"));
  const color = scoreColor(score);
  return { ...BASE_STYLE, fillColor: color, strokeColor: color };
}

function addCellFeatures(data: google.maps.Data, cells: readonly RankedCell[]): void {
  for (const cell of cells) {
    data.add({
      id: cell.cell_id,
      geometry: new google.maps.Data.Polygon([
        cellRing(cell.centroid).map(([lon, lat]) => new google.maps.LatLng(lat, lon)),
      ]),
      properties: { score: cell.drying_score },
    });
  }
}

export function createCellLayer(
  map: google.maps.Map,
  cells: readonly RankedCell[],
  handlers: CellLayerHandlers,
): CellLayer {
  const data = new google.maps.Data({ map, style: cellStyle });
  addCellFeatures(data, cells);
  const index = buildCellIndex(cells);
  const byId = new Map(cells.map((cell) => [cell.cell_id, cell]));
  let hoveredId: string | undefined;
  let selectedId: string | undefined;
  let frame = 0;

  function styleOf(cellId: string): google.maps.Data.StyleOptions | undefined {
    if (cellId === selectedId) return SELECTED_STYLE;
    if (cellId === hoveredId) return HOVER_STYLE;
    return undefined;
  }

  function restyle(cellId: string | undefined): void {
    if (cellId === undefined) return;
    const feature = data.getFeatureById(cellId);
    if (feature === undefined) return;
    const style = styleOf(cellId);
    if (style === undefined) data.revertStyle(feature);
    else data.overrideStyle(feature, style);
  }

  function hitAt(latLng: google.maps.LatLng | null | undefined): RankedCell | undefined {
    if (!latLng) return undefined;
    const point = { lat: latLng.lat(), lon: latLng.lng() };
    return findCellAt(index, point, toleranceDeg(map.getZoom() ?? 0));
  }

  function hover(cellId: string | undefined): void {
    if (cellId === hoveredId) return;
    const previous = hoveredId;
    hoveredId = cellId;
    restyle(previous);
    restyle(cellId);
    map.setOptions({ draggableCursor: cellId === undefined ? undefined : "pointer" });
  }

  const clickListener = map.addListener("click", (event: google.maps.MapMouseEvent) => {
    const hit = hitAt(event.latLng);
    if (hit) handlers.onSelect(hit.cell_id);
  });
  const moveListener = map.addListener("mousemove", (event: google.maps.MapMouseEvent) => {
    cancelAnimationFrame(frame);
    frame = requestAnimationFrame(() => hover(hitAt(event.latLng)?.cell_id));
  });

  return {
    select(cellId) {
      const previous = selectedId;
      selectedId = cellId;
      restyle(previous);
      restyle(cellId);
    },
    focus(cellId) {
      const cell = byId.get(cellId);
      if (cell === undefined) return;
      map.panTo({ lat: cell.centroid.lat, lng: cell.centroid.lon });
      map.setZoom(Math.max(map.getZoom() ?? 0, FOCUS_ZOOM));
    },
    destroy() {
      cancelAnimationFrame(frame);
      clickListener.remove();
      moveListener.remove();
      data.setMap(null);
    },
  };
}

const DAM_COLORS: Record<RankedDam["last_state"], string> = {
  intact: "#2f7d4f",
  damaged: "#d98f1f",
  broken: "#b3261e",
  overtopped: "#7a3bb0",
  not_applicable: "#6b6b6b",
  unknown: "#6b6b6b",
};

export function damColor(state: RankedDam["last_state"]): string {
  return DAM_COLORS[state];
}

export type DamLayer = { destroy: () => void };

export function createDamLayer(
  map: google.maps.Map,
  dams: readonly RankedDam[],
  onSelect: (dam: RankedDam) => void,
): DamLayer {
  const byId = new Map(dams.map((dam) => [dam.dam_id, dam]));
  const data = new google.maps.Data({
    map,
    style: (feature) => ({
      clickable: true,
      title: String(feature.getProperty("title")),
      icon: {
        path: google.maps.SymbolPath.CIRCLE,
        scale: 8,
        fillColor: String(feature.getProperty("color")),
        fillOpacity: 1,
        strokeColor: "#ffffff",
        strokeWeight: 2,
      },
      zIndex: 3,
    }),
  });
  for (const dam of dams) {
    data.add({
      id: dam.dam_id,
      geometry: new google.maps.Data.Point({ lat: dam.point.lat, lng: dam.point.lon }),
      properties: { color: damColor(dam.last_state), title: `${dam.dam_id}: ${dam.last_state}` },
    });
  }
  const listener = data.addListener("click", (event: google.maps.Data.MouseEvent) => {
    const dam = byId.get(String(event.feature.getId()));
    if (dam) onSelect(dam);
  });
  return {
    destroy() {
      listener.remove();
      data.setMap(null);
    },
  };
}
