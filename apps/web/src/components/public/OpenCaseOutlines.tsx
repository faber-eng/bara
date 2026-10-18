import { useMap } from "@vis.gl/react-google-maps";
import { useEffect, useRef } from "react";
import type { CellPoint } from "../../lib/contracts";
import { cellRing } from "../../lib/ops/cellGrid";

const OUTLINE_STYLE = {
  fillOpacity: 0,
  strokeColor: "#212529",
  strokeWeight: 3,
  zIndex: 2,
} as const;

type OutlineCell = Pick<CellPoint, "cell_id" | "centroid">;

type OpenCaseOutlinesProps = {
  cells: readonly OutlineCell[];
  openCellIds: readonly string[];
  onSelect?: (cellId: string) => void;
};

export function OpenCaseOutlines({ cells, openCellIds, onSelect }: OpenCaseOutlinesProps) {
  const map = useMap();
  const onSelectRef = useRef(onSelect);
  const clickable = onSelect !== undefined;

  useEffect(() => {
    onSelectRef.current = onSelect;
  }, [onSelect]);

  useEffect(() => {
    if (map === null) return;
    const open = new Set(openCellIds);
    const data = new google.maps.Data({ map, style: { ...OUTLINE_STYLE, clickable } });
    for (const cell of cells) {
      if (!open.has(cell.cell_id)) continue;
      const ring = cellRing(cell.centroid).map(([lon, lat]) => new google.maps.LatLng(lat, lon));
      data.add({ id: cell.cell_id, geometry: new google.maps.Data.Polygon([ring]) });
    }
    const listener = data.addListener("click", (event: google.maps.Data.MouseEvent) => {
      onSelectRef.current?.(String(event.feature.getId()));
    });
    return () => {
      listener.remove();
      data.setMap(null);
    };
  }, [map, cells, openCellIds, clickable]);

  return null;
}
