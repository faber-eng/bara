import { APIProvider, Map as GoogleMap, useMap } from "@vis.gl/react-google-maps";
import { useEffect, useRef } from "react";
import type { AreaCell, GeoPoint } from "../../lib/contracts";
import type { DetailCopy } from "../../lib/copy/detail";
import { OPS_MAP_CENTER, OPS_MAP_ZOOM } from "../../lib/ops/region";
import { RISK_COLORS, scoreColor } from "../../lib/ops/scoreColor";
import { MapKey, type MapKeyMark } from "../map/MapKey";
import { TileOverlay } from "../ops/TileOverlay";

const DRAFT_STYLE = {
  strokeColor: RISK_COLORS[4],
  strokeWeight: 2,
  fillColor: RISK_COLORS[2],
  fillOpacity: 0.25,
  clickable: false,
};
const CELL_STYLE = {
  strokeColor: "#ffffff",
  strokeWeight: 1,
  fillOpacity: 0.85,
  clickable: true,
};
const CELL_RADIUS_M = 450;
const FIT_PADDING_PX = 48;

function toLatLng(point: GeoPoint): google.maps.LatLngLiteral {
  return { lat: point.lat, lng: point.lon };
}

function DraftPolygon({ points, fitToken }: { points: GeoPoint[]; fitToken: number }) {
  const map = useMap();
  const polygonRef = useRef<google.maps.Polygon | null>(null);
  const pointsRef = useRef(points);
  pointsRef.current = points;

  useEffect(() => {
    if (map === null) return;
    const polygon = new google.maps.Polygon({ ...DRAFT_STYLE, map });
    polygonRef.current = polygon;
    return () => {
      polygonRef.current = null;
      polygon.setMap(null);
    };
  }, [map]);

  useEffect(() => {
    polygonRef.current?.setPath(points.map(toLatLng));
  }, [points]);

  useEffect(() => {
    if (map === null || fitToken === 0 || pointsRef.current.length === 0) return;
    const bounds = new google.maps.LatLngBounds();
    for (const point of pointsRef.current) bounds.extend(toLatLng(point));
    map.fitBounds(bounds, FIT_PADDING_PX);
  }, [map, fitToken]);

  return null;
}

type ResultCellsProps = { cells: AreaCell[]; onSelect: (cellId: string) => void };

function ResultCells({ cells, onSelect }: ResultCellsProps) {
  const map = useMap();
  const onSelectRef = useRef(onSelect);
  onSelectRef.current = onSelect;

  useEffect(() => {
    if (map === null) return;
    const circles = cells.map((cell) => {
      const circle = new google.maps.Circle({
        ...CELL_STYLE,
        map,
        fillColor: scoreColor(cell.drying_score),
        center: toLatLng(cell.centroid),
        radius: CELL_RADIUS_M,
      });
      circle.addListener("click", () => onSelectRef.current(cell.cell_id));
      return circle;
    });
    return () => {
      for (const circle of circles) {
        google.maps.event.clearInstanceListeners(circle);
        circle.setMap(null);
      }
    };
  }, [map, cells]);

  return null;
}

function areaMarks(points: number, cells: number): MapKeyMark[] {
  const marks: MapKeyMark[] = [];
  if (points > 0) marks.push("areaShape");
  if (cells > 0) marks.push("areaCell");
  return marks;
}

type AreaMapProps = {
  mapsKey: string;
  points: GeoPoint[];
  fitToken: number;
  cells: AreaCell[];
  tileUrlTemplate: string | null;
  tileLabel: string;
  disabled: boolean;
  keyCopy: DetailCopy;
  onAddPoint: (point: GeoPoint) => void;
  onCellSelect: (cellId: string) => void;
};

export function AreaMap({
  mapsKey,
  points,
  fitToken,
  cells,
  tileUrlTemplate,
  tileLabel,
  disabled,
  keyCopy,
  onAddPoint,
  onCellSelect,
}: AreaMapProps) {
  const marks = areaMarks(points.length, cells.length);
  return (
    <div className="area-map mv-host">
      <APIProvider apiKey={mapsKey}>
        <GoogleMap
          defaultCenter={OPS_MAP_CENTER}
          defaultZoom={OPS_MAP_ZOOM}
          mapTypeId="hybrid"
          gestureHandling="greedy"
          disableDefaultUI
          draggableCursor="crosshair"
          onClick={(event) => {
            const latLng = event.detail.latLng;
            if (disabled || latLng === null) return;
            onAddPoint({ lat: latLng.lat, lon: latLng.lng });
          }}
        >
          {tileUrlTemplate !== null && (
            <TileOverlay label={tileLabel} urlTemplate={tileUrlTemplate} opacity={0.7} />
          )}
          <DraftPolygon points={points} fitToken={fitToken} />
          <ResultCells cells={cells} onSelect={onCellSelect} />
        </GoogleMap>
      </APIProvider>
      {marks.length > 0 && <MapKey marks={marks} copy={keyCopy} screen="area" />}
    </div>
  );
}
