import { APIProvider, Map as GoogleMap, useMap } from "@vis.gl/react-google-maps";
import { useEffect, useRef } from "react";
import type { AreaCell, GeoPoint } from "../../lib/contracts";
import { OPS_MAP_CENTER, OPS_MAP_ZOOM } from "../../lib/ops/region";
import { TileOverlay } from "../ops/TileOverlay";

const DRAFT_STYLE = {
  strokeColor: "#8a3a12",
  strokeWeight: 2,
  fillColor: "#c4612a",
  fillOpacity: 0.18,
  clickable: false,
};
const CELL_STYLE = {
  strokeColor: "#2f5d3a",
  strokeWeight: 1,
  fillColor: "#2f5d3a",
  fillOpacity: 0.35,
  clickable: false,
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

function ResultCells({ cells }: { cells: AreaCell[] }) {
  const map = useMap();

  useEffect(() => {
    if (map === null) return;
    const circles = cells.map(
      (cell) =>
        new google.maps.Circle({
          ...CELL_STYLE,
          map,
          center: toLatLng(cell.centroid),
          radius: CELL_RADIUS_M,
        }),
    );
    return () => {
      for (const circle of circles) circle.setMap(null);
    };
  }, [map, cells]);

  return null;
}

type AreaMapProps = {
  mapsKey: string;
  points: GeoPoint[];
  fitToken: number;
  cells: AreaCell[];
  tileUrlTemplate: string | null;
  tileLabel: string;
  disabled: boolean;
  onAddPoint: (point: GeoPoint) => void;
};

export function AreaMap({
  mapsKey,
  points,
  fitToken,
  cells,
  tileUrlTemplate,
  tileLabel,
  disabled,
  onAddPoint,
}: AreaMapProps) {
  return (
    <div className="area-map">
      <APIProvider apiKey={mapsKey}>
        <GoogleMap
          defaultCenter={OPS_MAP_CENTER}
          defaultZoom={OPS_MAP_ZOOM}
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
          <ResultCells cells={cells} />
        </GoogleMap>
      </APIProvider>
    </div>
  );
}
